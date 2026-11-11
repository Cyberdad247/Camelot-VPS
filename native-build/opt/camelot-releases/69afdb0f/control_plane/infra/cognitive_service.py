#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Cognitive Service — HTTP front for the Tier-2/3 stack on cybertronia.

Endpoints (CORS-open for the deployed dashboard):
  GET  /healthz               -> status, vault count, cloud reachability
  POST /ingest  {text,source} -> Graphify extract -> MemCastle store
  POST /forage  {url}         -> fetch a URL, strip HTML, ingest its text
  GET  /search?q=&k=          -> MemCastle KNN
  POST /sync    {query}       -> //sync push+pull (MemCastle <-> NotebookLM)

  Cybertronia 3D Graph Sync Forge (Phase 4 — STUB until Phase 2 ships):
  GET  /api/cybertronia-graph/snapshot     -> 501 + hand-off payload (§8 row 1)
  GET  /api/cybertronia-graph/stream       -> 501 + hand-off payload (§8 row 2)
  GET  /api/cybertronia-graph/nodes/:id    -> 501 + hand-off payload (§8 row 3)
  GET  /api/cybertronia-graph/sync-status  -> 501 + hand-off payload (§8 row 4)

  Phase 4 wiring is **purely additive on a green Phase 1 audit** (35/35 PASS,
  FIX-1..FIX-4 reviewer-approved). Replacing each 501 body with a real handler
  does NOT alter the audit pipeline, the do_GET routing, or the pre-SSE
  GraphSnapshotStub bootstrap (spec §4.3).

forage is the GROUNDED replacement for the fictional "OpenViking OSINT fleet":
a real urllib fetch + HTML strip + Graphify ingest. No distributed WASM scrapers,
no Lightpanda — just a real web fetch into the real pipeline.

A background scheduler runs //sync every COGNITIVE_SYNC_INTERVAL seconds (0 =
off). All MemCastle access is serialized by a lock so the scheduler thread and
HTTP handler thread never touch SQLite concurrently.
"""
from __future__ import annotations

import html
import importlib.util
import json
import os
import re
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_CP = Path(__file__).resolve().parent
sys.path.insert(0, str(_CP))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _CP / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


memcastle = _load("memcastle")
graphify = _load("graphify")
mcsync = _load("memcastle_sync")
cybertronia_compile = _load("cybertronia_compile")

GF = graphify.Graphify()
BRIDGE = mcsync._DEFAULT_BRIDGE          # patchable in tests
_LOCK = threading.Lock()                  # serializes all SQLite access

# ── Cybertronia 3D Graph Sync Forge — Phase 4 SSE stub (additive) ─────────────
# When Phase 1 audit is green (35/35 PASS, FIX-1..FIX-4 reviewer-approved) but
# the Phase 2 compiler (cybertronia_compile.py) has not produced a GraphSnapshot
# cache yet, these 4 GET endpoints return 501 + a hand-off payload so the PWA
# Cockpit lazy cartridge and the Anya Dashboard graph panel mount the
# GraphSnapshotStub (spec §4.3) and learn exactly which Phase 4 contract will
# replace the stub. Wiring is therefore purely additive: replacing the 501 body
# with a real handler does NOT require touching this routing table or the
# audit pipeline.
_CYBERTRONIA_GRAPH_SPEC_PATH   = "CAMELOT_OS/docs/cybertronia-graph-ui-spec.md"
_CYBERTRONIA_GRAPH_SPEC_SECTION = "§8 SSE endpoint shape"
_CYBERTRONIA_AUDIT_BLURB       = "Phase 1 audit GREEN — 35/35 PASS (FIX-1..FIX-4)"


def _cyber_hand_off(
    endpoint: str,
    section_suffix: str,
    expected_status: int,
    expected_response_class: str,
    *,
    extra: dict | None = None,
) -> dict:
    """Build the 501 hand-off payload Phase 4 will replace.

    Anchored on `cybertronia-graph-ui-spec.md` so the PWA Cockpit cartridge
    (lazy mount), the Anya Dashboard panel (pre-SSE bootstrap in §4.3), and
    any future Goose-side cross-worktree mirror test all read the same
    spec §8 row — no drift.
    """
    sl = section_suffix.lower()
    if "snapshot" in sl or "nodes" in sl:
        schema_version = "cybertronia.snapshot/v1"
    elif "stream" in sl:
        schema_version = "cybertronia.delta/v1"
    else:
        schema_version = "n/a"
    payload: dict = {
        "status":                  "not_implemented",
        "phase": {
            "audit":     "green",          # Phase 1 — shipped + reviewer-approved
            "compile":   "pending",        # Phase 2 — cybertronia_compile.py TBD
            "transport": "not_yet_built",  # Phase 4 — this stub
        },
        "endpoint":                endpoint,
        "method":                  "GET",
        "expected_status":         expected_status,            # 200 / 304
        "expected_response_class": expected_response_class,
        "expected_phase":          "Phase 4 SSE",
        "contract_ref": {
            "spec":           _CYBERTRONIA_GRAPH_SPEC_PATH,
            "section":        f"{_CYBERTRONIA_GRAPH_SPEC_SECTION} · {section_suffix}",
            "schema_version": schema_version,
            "impl_phase":     "Phase 4",
        },
        "phase4_hand_off": {
            "plan":     (
                "Replace the 501 body with the real handler reading from the "
                "Phase 2 GraphSnapshot cache. Do NOT alter do_GET routing, the "
                "audit pipeline, or the pre-SSE bootstrap."
            ),
            "dependency": (
                "Phase 2 (cybertronia_compile.py) shipped — produces "
                "lattice_vectors.json + graph_delta.json + redacted entiremap.md."
            ),
            "additive":             True,
            "consumer_invariants": [
                "GraphSnapshot shape frozen by spec §1 (digest = sha256, schema_version pinned)",
                "BrainSync LWW merge per spec §2 (tombstone-is-sticky)",
                "ETag / digest convergence for /snapshot → 304 Not Modified",
                "Pre-SSE bootstrap via GraphSnapshotStub (spec §4.3) "
                "— see also /sync-status last_digest",
            ],
        },
        "pre_sse_bootstrap": {
            "type":             "GraphSnapshotStub",
            "snapshot":         None,
            "fallback_2d":      True,
            "source":           "audit-cursor",
            "spec_ref":         "§4.3 Pre-SSE bootstrap",
            "scan_id":          None,   # filled from cursor.last_path by /snapshot
            "cursor_last_path": None,
            "completed_at":     None,
            "nodes_total":      0,
            "fallback_reason":  "sse_not_yet_built",
        },
        "audit_blurb": _CYBERTRONIA_AUDIT_BLURB,
    }
    if extra:
        payload.update(extra)
    return payload


def html_to_text(raw: str) -> str:
    """Strip scripts/styles/tags and unescape entities -> plain text."""
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


def fetch_url(url: str, timeout: float = 15.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Camelot-Forager/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read(2_000_000).decode(charset, errors="replace")  # cap 2 MB


def forage(gf, url: str, fetcher=None) -> dict:
    """Real web forage: fetch URL -> text -> Graphify ingest -> MemCastle.

    `fetcher` is injectable (defaults to the module-level fetch_url, looked up
    dynamically) so the pipeline is tested without network.
    """
    f = fetcher or fetch_url
    try:
        raw = f(url)
    except Exception as e:
        return {"status": "error", "url": url, "reason": f"{type(e).__name__}: {e}"}
    text = html_to_text(raw)
    if not text:
        return {"status": "error", "url": url, "reason": "no text extracted"}
    with _LOCK:
        triplets = gf.ingest(text, source=url)
        total = gf.mc.count()
    return {"status": "ok", "url": url, "chars": len(text),
            "triplets": len(triplets), "vault_total": total}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/healthz":
            ok, reason = mcsync._cloud_ok(BRIDGE)
            with _LOCK:
                items = GF.mc.count()
            self._send(200, {"status": "ok", "vault_items": items,
                             "cloud_reachable": ok, "cloud": reason})
        elif u.path == "/search":
            query = (q.get("q") or [""])[0]
            k = int((q.get("k") or ["5"])[0])
            if not query:
                self._send(400, {"error": "missing q"})
                return
            with _LOCK:
                results = GF.mc.search(query, k=k)
            self._send(200, {"query": query, "results": results})
        elif self._dispatch_cybertronia_graph(u.path):
            return
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        data = self._body_json()
        if u.path == "/ingest":
            text = data.get("text", "")
            if not text:
                self._send(400, {"error": "missing text"})
                return
            with _LOCK:
                triplets = GF.ingest(text, source=data.get("source", "service"))
                total = GF.mc.count()
            self._send(200, {
                "triplets": [{"head": t.head, "relation": t.relation, "tail": t.tail} for t in triplets],
                "count": len(triplets), "vault_total": total,
            })
        elif u.path == "/forage":
            url = data.get("url", "")
            if not url:
                self._send(400, {"error": "missing url"})
                return
            self._send(200, forage(GF, url))
        elif u.path == "/sync":
            query = data.get("query", "Summarize the current Camelot-OS state.")
            with _LOCK:
                result = mcsync.sync(GF.mc, query, bridge=BRIDGE)
            self._send(200, result)
        else:
            self._send(404, {"error": "not found"})

    # ── Cybertronia 3D Graph Sync Forge — Phase 4 SSE stub dispatch ───────────
    # Phase 4 wiring is purely additive: this method only fires when the path
    # matches /api/cybertronia-graph/*; it never steals routes from do_GET.
    # Returns True iff this path belongs to the cybertronia-graph family and
    # the response is set; False means defer to the generic 404.
    def _dispatch_cybertronia_graph(self, path: str) -> bool:
        prefix = "/api/cybertronia-graph/"
        if not path.startswith(prefix):
            return False
        suffix = path[len(prefix):]
        if suffix == "snapshot":
            # spec §8 row 1 — one-shot GraphSnapshot; 304 Not Modified on digest
            self._send(501, _cyber_hand_off(
                endpoint="/api/cybertronia-graph/snapshot",
                section_suffix="row 1 (snapshot)",
                expected_status=200,
                expected_response_class="GraphSnapshot (with 304 Not Modified on If-None-Match)",
            ))
            return True
        if suffix == "stream":
            # spec §8 row 2 — text/event-stream with cadence ≥ 160 ms
            self._send(501, _cyber_hand_off(
                endpoint="/api/cybertronia-graph/stream",
                section_suffix="row 2 (stream)",
                expected_status=200,
                expected_response_class="text/event-stream (GraphDelta batches)",
                extra={"media_type_target": "text/event-stream",
                       "cadence_floor_ms":  160},
            ))
            return True
        if suffix == "sync-status":
            # spec §8 row 4 — convergence-token echo for atomic swap (§4.3 step 2).
            # Phase 4 wiring is purely additive: this is the FIRST endpoint to
            # return a real handler. Reads compile_cursor.json produced by
            # control_plane/cybertronia_compile.py and returns the 4 spec §8
            # fields. When Phase 2 hasn't shipped, returns a 200 with null/0
            # fallback so PWA Cockpit + Anya can still mount GraphSnapshotStub
            # with no flash of empty canvas (spec §4.3).
            cursor = cybertronia_compile.read_compile_cursor()
            phase2_ready = cursor is not None
            payload: dict = {
                "status": "ok" if phase2_ready else "phase2_not_ready",
                "last_digest":        (cursor or {}).get("last_digest"),
                "last_seen_at_ms":    int((cursor or {}).get("last_seen_at_ms") or 0),
                "lag_batches":        int((cursor or {}).get("lag_batches", 0)),
                "divergence_pending": bool((cursor or {}).get("divergence_pending", False)),
                "phase": {
                    "audit":     "green",                                # Phase 1 — shipped + reviewer-approved
                    "compile":   "ready"   if phase2_ready  else "pending",
                    "transport": "live",                                  # this handler
                },
                "contract_ref": {
                    "spec":     _CYBERTRONIA_GRAPH_SPEC_PATH,
                    "section":  f"{_CYBERTRONIA_GRAPH_SPEC_SECTION} · row 4 (sync-status)",
                    "impl":     "real_handler",
                    "impl_src": "control_plane/cybertronia_compile.py (Phase 2 cursor)",
                },
                "phase4_hand_off": {
                    "plan":         "Read compile_cursor.json; serve the 4 spec §8 fields verbatim.",
                    "additive":     True,
                    "audit_blurb":  _CYBERTRONIA_AUDIT_BLURB,
                },
                "audit_blurb": _CYBERTRONIA_AUDIT_BLURB,
            }
            self._send(200, payload)
            return True
        if suffix == "nodes" or suffix.startswith("nodes/"):
            # `nodes` (bare, no `:id` segment) IS the documented pattern,
            # so it's a *malformed* hit — 400, never 404 (unknown endpoint)
            # and never 501 (no future handler reads a missing id).
            node_id = "" if suffix == "nodes" else suffix[len("nodes/"):]
            if not node_id or "/" in node_id or not node_id.strip():
                # Defensive: real handler will return 404 for *unknown* ids,
                # but a malformed id is a 400 — never a 501.
                self._send(400, {
                    "error":        "invalid or empty node id",
                    "path_pattern": "/api/cybertronia-graph/nodes/:id",
                    "contract_ref": f"{_CYBERTRONIA_GRAPH_SPEC_PATH} §8 {_CYBERTRONIA_GRAPH_SPEC_SECTION} · row 3",
                })
                return True
            # spec §8 row 3 — NodeRef JSON or 404
            self._send(501, _cyber_hand_off(
                endpoint="/api/cybertronia-graph/nodes/:id",
                section_suffix="row 3 (nodes/:id)",
                expected_status=200,
                expected_response_class="NodeRef JSON (or 404 if not in current snapshot)",
                extra={"node_id": node_id},
            ))
            return True
        # Matched the prefix but suffix is unknown — surface a 404 (do_GET
        # should NOT fall through to the generic 404 path for this family).
        self._send(404, {
            "error":        "unknown cybertronia-graph endpoint",
            "endpoint":     path,
            "known_prefix": "/api/cybertronia-graph/",
            "available":   ["snapshot", "stream", "sync-status", "nodes/:id"],
            "contract_ref": f"{_CYBERTRONIA_GRAPH_SPEC_PATH} §8 {_CYBERTRONIA_GRAPH_SPEC_SECTION}",
        })
        return True


def _scheduler_loop(interval: float):
    """Periodic //sync (edge-first: skips cleanly when cloud is down)."""
    while True:
        time.sleep(interval)
        try:
            with _LOCK:
                mcsync.sync(GF.mc, "Periodic Camelot-OS state sync.", bridge=BRIDGE)
        except Exception:
            pass  # never let the scheduler crash the service


def serve(addr: str = "127.0.0.1", port: int = 8090) -> HTTPServer:
    return HTTPServer((addr, port), Handler)


def main():
    port = int(os.environ.get("COGNITIVE_PORT", "8090"))
    interval = float(os.environ.get("COGNITIVE_SYNC_INTERVAL", "0") or "0")
    if interval > 0:
        threading.Thread(target=_scheduler_loop, args=(interval,), daemon=True).start()
        print(f"[cognitive_service] scheduled //sync every {interval}s", flush=True)
    httpd = serve("0.0.0.0", port)
    with _LOCK:
        n = GF.mc.count()
    print(f"[cognitive_service] serving on :{port} (vault items={n})", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
