#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Cognitive Service — HTTP front for the Tier-2/3 stack on cybertronia.

Endpoints (CORS-open for the deployed dashboard):
  GET  /healthz               -> status, vault count, cloud reachability
  POST /ingest  {text,source} -> Graphify extract -> MemCastle store
  POST /forage  {url}         -> fetch a URL, strip HTML, ingest its text
  GET  /search?q=&k=          -> MemCastle KNN
  POST /sync    {query}       -> //sync push+pull (MemCastle <-> NotebookLM)
  GET  /config                -> current persisted config (e.g. sync_interval)
  POST /config  {...}         -> merge + persist config, applied live by the scheduler

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
import subprocess
import sys
import threading
import time
import urllib.error
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

GF = graphify.Graphify()
BRIDGE = mcsync._DEFAULT_BRIDGE          # patchable in tests
_LOCK = threading.Lock()                  # serializes all SQLite access

# --- Config surface (persisted to disk so settings survive a restart) ---
CONFIG_PATH = Path(os.environ.get(
    "COGNITIVE_CONFIG_PATH",
    str(_CP.parent / "03_VAULT" / "runtime_state" / "cognitive_config.json"),
))
DEFAULT_CONFIG = {"sync_interval": 0.0, "sync_query": "Periodic Camelot-OS state sync."}
_CONFIG_LOCK = threading.Lock()


def load_config() -> dict:
    with _CONFIG_LOCK:
        try:
            return {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text())}
        except Exception:
            return dict(DEFAULT_CONFIG)


def save_config(updates: dict) -> dict:
    with _CONFIG_LOCK:
        try:
            current = {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text())}
        except Exception:
            current = dict(DEFAULT_CONFIG)
        current.update({k: v for k, v in updates.items() if k in DEFAULT_CONFIG})
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(current, indent=2))
        return current


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


# --- Fleet status (the Bifrost-bridge process view feeding the 3D UI) ---
DAEMONS = [
    {"name": "go_router", "url": "http://127.0.0.1:8077/healthz", "role": "SSE rune router (Go)"},
    {"name": "bifrost_sidecar", "url": "http://127.0.0.1:8011/", "role": "Bifrost bridge (Go)"},
    {"name": "cognitive_service", "url": None, "role": "Graphify/MemCastle/sync (Python)"},
]


def _probe(url, timeout: float = 2.0) -> bool:
    if url is None:
        return True  # self
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # reachable but non-200 (e.g. sidecar 404) still means UP
    except Exception:
        return False


def fleet_daemons() -> list[dict]:
    return [{"name": d["name"], "role": d["role"], "up": _probe(d["url"])} for d in DAEMONS]


def tailnet_nodes() -> dict:
    try:
        raw = subprocess.run(["tailscale", "status", "--json"],
                             capture_output=True, text=True, timeout=6).stdout
        data = json.loads(raw)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "nodes": []}

    def fmt(n: dict, is_self: bool) -> dict:
        host = n.get("HostName") or (n.get("DNSName", "") or "").split(".")[0]
        return {"name": host, "ip": (n.get("TailscaleIPs") or [None])[0],
                "os": n.get("OS"), "online": bool(n.get("Online", is_self)), "self": is_self}

    nodes = []
    if data.get("Self"):
        nodes.append(fmt(data["Self"], True))
    for peer in (data.get("Peer") or {}).values():
        nodes.append(fmt(peer, False))
    return {"tailnet": data.get("MagicDNSSuffix"), "nodes": nodes}


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
        elif u.path == "/fleet":
            with _LOCK:
                items = GF.mc.count()
            ok, reason = mcsync._cloud_ok(BRIDGE)
            self._send(200, {"daemons": fleet_daemons(), "tailnet": tailnet_nodes(),
                             "vault_items": items, "cloud_reachable": ok, "cloud": reason})
        elif u.path == "/search":
            query = (q.get("q") or [""])[0]
            k = int((q.get("k") or ["5"])[0])
            if not query:
                self._send(400, {"error": "missing q"})
                return
            with _LOCK:
                results = GF.mc.search(query, k=k)
            self._send(200, {"query": query, "results": results})
        elif u.path == "/config":
            self._send(200, load_config())
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
        elif u.path == "/config":
            if "sync_interval" in data:
                try:
                    if isinstance(data["sync_interval"], bool):
                        raise TypeError
                    data["sync_interval"] = float(data["sync_interval"])
                except (TypeError, ValueError):
                    self._send(400, {"error": "sync_interval must be a number"})
                    return
                if data["sync_interval"] < 0:
                    self._send(400, {"error": "sync_interval must be >= 0"})
                    return
            if "sync_query" in data:
                if not isinstance(data["sync_query"], str) or not data["sync_query"].strip():
                    self._send(400, {"error": "sync_query must be a non-empty string"})
                    return
            self._send(200, save_config(data))
        else:
            self._send(404, {"error": "not found"})


def _scheduler_loop():
    """Periodic //sync, interval read fresh from the persisted config each
    cycle so POST /config can change cadence without a restart (edge-first:
    skips cleanly when cloud is down)."""
    while True:
        cfg = load_config()
        interval = cfg["sync_interval"]
        time.sleep(interval if interval > 0 else 5.0)
        if interval <= 0:
            continue
        try:
            with _LOCK:
                query = load_config().get("sync_query") or "Periodic Camelot-OS state sync."
                mcsync.sync(GF.mc, query, bridge=BRIDGE)
        except Exception:
            pass  # never let the scheduler crash the service


def serve(addr: str = "127.0.0.1", port: int = 8090) -> HTTPServer:
    return HTTPServer((addr, port), Handler)


def main():
    port = int(os.environ.get("COGNITIVE_PORT", "8090"))
    env_interval = os.environ.get("COGNITIVE_SYNC_INTERVAL")
    if env_interval and not CONFIG_PATH.exists():
        save_config({"sync_interval": float(env_interval)})  # seed first boot only
    threading.Thread(target=_scheduler_loop, daemon=True).start()
    interval = load_config()["sync_interval"]
    if interval > 0:
        print(f"[cognitive_service] scheduled //sync every {interval}s", flush=True)
    httpd = serve("0.0.0.0", port)
    with _LOCK:
        n = GF.mc.count()
    print(f"[cognitive_service] serving on :{port} (vault items={n})", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
