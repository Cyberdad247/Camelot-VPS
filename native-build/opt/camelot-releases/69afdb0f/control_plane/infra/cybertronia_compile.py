#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""cybertronia_compile.py -- Phase 2 compiler for the Cybertronia 3D Graph Sync Forge.

Reads Phase 1 telemetry (``control_plane/cybertronia_audit.py``) and emits
four artifacts into ``03_VAULT/runtime_state/cybertronia_graph_compile/``::

    lattice_vectors.json    -- {scan_id, schema_version, vectors: Record<NodeId, Vector25>}
    graph_delta.json        -- Phase 4 SSE stream's initial delta (upsert ops only)
    entiremap.md            -- redacted node map (sensitive basenames masked)
    compile_cursor.json     -- {last_digest, last_seen_at_ms, lag_batches,
                                divergence_pending}; consumed by
                                GET /api/cybertronia-graph/sync-status

The compiler is the contract-of-record bridge between metadata-only Phase 1
and the Python-side Phase 4 transport. The served ``compile_cursor.json``
ties the upcoming real GraphSnapshot's digest to a stable sha256 anchor so
the PWA Cockpit and Anya Dashboard can mount :class:`GraphSnapshotStub` per
spec §4.3 with no flash-of-empty-canvas.

Stability rules (Draft 0.3):

* Vector25 values use **safe neutral defaults** (``0.0`` for unknown metrics,
  ``1.0`` for compile-time health). ``NaN`` is forbidden here because the
  ``InstancedMesh`` renderer's STRIDE_SENTINEL (spec §4.2) treats it as a
  "not yet assigned" idle-frame; using neutral 0/1.0 keeps math stable and
  avoids that trap.
* Vector25 field names verbatim against spec §1; tests pin order + count.
* Schema versions pinned: ``cybertronia.snapshot/v1`` (lattice) and
  ``cybertronia.delta/v1`` (graph_delta).
* Atomic writes via write-temp + ``os.replace`` (mirrors cybertronia_audit).

CLI::

    python -m control_plane.cybertronia_compile compile [--from-telemetry PATH]
    python -m control_plane.cybertronia_compile status
    python -m control_plane.cybertronia_compile cursor
"""
from __future__ import annotations

__version__ = "9000.15-CYB-2"

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Path contract (mirror cybertronia_audit.py) ──────────────────────────────

CAMELOT_HOME = Path(
    os.environ.get("CAMELOT_HOME", str(Path(__file__).resolve().parent.parent))
)

PHASE1_ROOT         = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "cybertronia_graph"
PHASE2_ROOT         = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "cybertronia_graph_compile"

PHASE1_TELEMETRY    = PHASE1_ROOT    / "node_telemetry.json"
PHASE1_CURSOR       = PHASE1_ROOT    / "cursor.json"
PHASE1_SCAN_META    = PHASE1_ROOT    / "scan.meta.json"

LATTICE_VECTORS     = PHASE2_ROOT    / "lattice_vectors.json"
GRAPH_DELTA_FILE    = PHASE2_ROOT    / "graph_delta.json"
REDACTED_ENTIREMAP  = PHASE2_ROOT    / "entiremap.md"
COMPILE_CURSOR      = PHASE2_ROOT    / "compile_cursor.json"

# ── Spec §1 lockbox ─────────────────────────────────────────────────────────

LAYERS: tuple[str, ...] = (
    "bin", "control_plane", "02_FORGE", "03_VAULT", "runtime",
)
# (path-prefix, layer) — order matters; first match wins.
_LAYER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("bin/",         "bin"),
    ("control_plane/", "control_plane"),
    ("02_FORGE/",    "02_FORGE"),
    ("03_VAULT/",    "03_VAULT"),
)
# `runtime` is the catch-all.

KIND_TO_INDEX: dict[str, int] = {
    "file":             0,
    "dir":              1,
    "symlink":          2,
    "runtime_service":  3,
    "process_group":    4,
    "listener_port":    5,
    "volume":           6,
}

# Vector25 field names verbatim — DO NOT REORDER. Tests pin order + count.
VECTOR25_FIELD_NAMES: tuple[str, ...] = (
    "layer", "type", "path depth", "size", "file count",
    "recency", "churn", "cpu cost", "memory cost", "storage cost",
    "runtime state", "health", "exposure", "in_degree", "out_degree",
    "centrality", "betweenness", "pagerank", "community", "criticality",
    "sensitivity", "mutability", "provenance", "sync state", "resource pressure",
)
EXPECTED_VECTOR_LEN: int = 25

SCHEMA_VERSION_SNAPSHOT: str = "cybertronia.snapshot/v1"
SCHEMA_VERSION_DELTA:    str = "cybertronia.delta/v1"

# ── Sensitivity heuristics (draft 0.3 — redaction is granular to basename) ──

SENSITIVE_BASENAME_PREFIXES: tuple[str, ...] = (
    ".env", "credentials",
)
SENSITIVE_SUFFIXES: tuple[str, ...] = (
    ".key", ".pem", ".p12", ".pfx", ".tfstate", ".credentials",
)
# Phase 1 telemetry already root-relative (cybertronia_audit), so absolute
# paths are not a concern here; we mask sensitive basenames wholesale.

# ── Numeric encoding tables (compile-time = local, healthy, active) ─────────

# v[10] runtime state: 0=active, 1=dormant, 2=errored, 3=offline
_RUNTIME_STATE_ACTIVE   = 0.0
_RUNTIME_STATE_DORMANT  = 1.0
# v[22] provenance: 1=local, 0.5=remote, 0=redaction-mask
_PROVENANCE_LOCAL       = 1.0
# v[23] sync state: 0=synced, 1=pending, 2=diverged
_SYNC_STATE_SYNCED      = 0.0

_NODE_ID_SCOPE_FILE = "file"


# ── helpers ─────────────────────────────────────────────────────────────────

def _utc_now_iso(timespec: str = "seconds") -> str:
    return datetime.now(timezone.utc).isoformat(timespec=timespec)


def _utc_now_ms() -> int:
    return int(time.time() * 1000)


def _sha256_hex(payload: dict) -> str:
    """``"sha256:" + hex(json.dumps(payload, sort_keys=True))`` — caller-friendly."""
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _segments(rel: str) -> list[str]:
    return [s for s in re.split(r"[\\/]+", rel) if s]


def atomic_write_json(path: Path, payload: dict) -> None:
    """Mirror of cybertronia_audit.atomic_write_json; committing-Python-side."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # Windows fsync is best-effort (see cybertronia_audit).
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_compile_cursor(path: Optional[Path] = None) -> Optional[dict]:
    """Read the latest compile cursor; returns ``None`` if Phase 2 hasn't run yet.

    ``COMPILE_CURSOR`` is resolved at CALL time (not import time) so test
    monkeypatching of the module-level constant works correctly.
    """
    if path is None:
        path = COMPILE_CURSOR  # resolved at call time → honors monkeypatch
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ── Vector25 derivation ─────────────────────────────────────────────────────

def derive_layer(rel_path: str) -> str:
    """Pin a node to one of LAYERS using the leading path prefix; default ``runtime``."""
    p = rel_path.replace("\\", "/")
    for prefix, layer in _LAYER_PREFIXES:
        if p.startswith(prefix):
            return layer
    return "runtime"


def derive_kind_index(kind: str) -> int:
    """Map ``NodeKind`` to its one-hot index; default ``0`` (file) for unknowns."""
    return KIND_TO_INDEX.get(kind, 0)


def is_sensitive_basename(basename: str) -> bool:
    """Two-way mask: prefix or suffix; matched case-insensitively."""
    low = basename.lower()
    if any(low.startswith(pfx) for pfx in SENSITIVE_BASENAME_PREFIXES):
        return True
    if any(low.endswith(suf) for suf in SENSITIVE_SUFFIXES):
        return True
    return False


def derive_sensitivity(basename: str) -> int:
    """0=low, 1=med, 2=high. Heuristic on basename only."""
    if is_sensitive_basename(basename):
        return 2  # high
    if basename.startswith(".") and basename not in (".gitignore", ".gitkeep"):
        return 1  # med (config-like)
    return 0  # low


def derive_node_id(rel_path: str) -> str:
    """``sha256(scope + "/" + path)[:16]`` per spec Glossary for file nodes."""
    h = hashlib.sha256(
        (_NODE_ID_SCOPE_FILE + "/" + rel_path).encode("utf-8")
    ).hexdigest()
    return h[:16]


def redact_basename(basename: str) -> str:
    """Replace basename with bracketed badge when sensitive; preserve canonical form otherwise.

    Uses NFKC normalization so non-ASCII basenames collapse to a comparable
    form (avoids unicode-variant redaction drift).
    """
    normalized = unicodedata.normalize("NFKC", basename)
    if is_sensitive_basename(normalized):
        return "[REDACTED]"
    return normalized


def compile_vector(
    node: dict,
    runtime_ctx: dict,
    *,
    now_iso: str,
) -> list[float]:
    """Derive a 25-float Vector25 from Phase 1 metadata + runtime context.

    Unknown axes use NEUTRAL DEFAULTS (0.0 for metrics, 1.0 for compile-time
    health). NaN is forbidden — see module docstring.
    """
    rel_path = str(node.get("path", "")).replace("\\", "/")
    basename = Path(rel_path).name
    size     = max(0, int(node.get("size", 0) or 0))
    mtime    = float(node.get("mtime") or time.time())
    kind     = str(node.get("kind", "file"))

    # ───────────────── known fields (deterministic) ─────────────────
    layer_idx = LAYERS.index(derive_layer(rel_path))
    type_idx  = derive_kind_index(kind)
    depth     = len(_segments(rel_path))
    size_log  = math.log2(size + 1) if size > 0 else 0.0
    file_cnt  = 1.0 if kind == "file" else 0.0

    # Recency 0 (just touched) .. 1 (very stale).
    try:
        now_epoch = datetime.fromisoformat(
            now_iso.replace("Z", "+00:00")
        ).timestamp()
    except (ValueError, AttributeError):
        now_epoch = time.time()
    age_sec   = max(0.0, now_epoch - mtime)
    MAX_AGE   = 365.0 * 24.0 * 3600.0
    recency   = max(0.0, min(1.0, age_sec / MAX_AGE))

    # Storage cost (file bytes / volume total) — clamp 0..1; >1 truncated to 1.
    vol_total = max(1.0, float(runtime_ctx.get("volumes_total_bytes") or 1.0))
    storage_cost = min(1.0, size / vol_total)

    # Resource pressure = (mem_total - mem_avail) / mem_total.
    mem_total = max(1.0, float(runtime_ctx.get("mem_total_mib") or 1.0))
    mem_avail = min(mem_total, max(0.0, float(runtime_ctx.get("mem_avail_mib") or mem_total)))
    resource_pressure = (mem_total - mem_avail) / mem_total

    # ───────────────── neutral-default fields ───────────────────────
    sensitivity_base = derive_sensitivity(basename)
    sensitivity = float(sensitivity_base)
    mutability  = 1.0 if kind == "file" else 0.0

    rt_active   = _RUNTIME_STATE_ACTIVE   if kind == "file" else _RUNTIME_STATE_DORMANT

    v: list[float] = [
        float(layer_idx),   #  0  layer            (one-hot int 0..4)
        float(type_idx),    #  1  type             (one-hot int 0..6)
        float(depth),       #  2  path depth       (segment count)
        size_log,           #  3  size             (log2(bytes + 1))
        file_cnt,           #  4  file count       (1 if file; 0 else — Phase H fills)
        recency,            #  5  recency          (0..1)
        0.0,                #  6  churn            (Phase H)
        0.0,                #  7  cpu cost         (no per-node RSS yet)
        0.0,                #  8  memory cost      (no per-node RSS yet)
        storage_cost,       #  9  storage cost
        rt_active,          # 10  runtime state    (0=active, 1=dormant)
        1.0,                # 11  health           (compile-time = healthy)
        0.0,                # 12  exposure         (no port for files)
        0.0,                # 13  in_degree
        0.0,                # 14  out_degree
        0.0,                # 15  centrality       (Phase H)
        0.0,                # 16  betweenness      (Phase H)
        0.0,                # 17  pagerank         (Phase H)
        0.0,                # 18  community        (Phase H)
        0.0,                # 19  criticality      (Phase H)
        sensitivity,        # 20  sensitivity      (0..2 → 0.0/1.0/2.0)
        mutability,         # 21  mutability       (0|1)
        _PROVENANCE_LOCAL,  # 22  provenance       (local at compile time)
        _SYNC_STATE_SYNCED, # 23  sync state       (synced at compile time)
        resource_pressure,  # 24  resource pressure (rolling CPU+RAM)
    ]
    if len(v) != EXPECTED_VECTOR_LEN:
        raise AssertionError(
            f"compile_vector produced {len(v)} floats, expected {EXPECTED_VECTOR_LEN}"
        )
    return v


# ── Build artifacts from a Phase 1 telemetry payload ───────────────────────

@dataclass
class RuntimeAggregate:
    """Distilled runtime context; computed once, shared across vector compiles."""
    mem_total_mib:        float = 1.0
    mem_avail_mib:        float = 1.0
    volumes_total_bytes:  float = 1.0

    @classmethod
    def from_runtime(cls, runtime: dict) -> "RuntimeAggregate":
        mem_total = float(runtime.get("mem_total_mib") or 1.0)
        mem_avail = float(runtime.get("mem_avail_mib") or mem_total)
        vol_total = 0.0
        for v in (runtime.get("volumes") or []):
            try:
                vol_total += float(v.get("total_gib") or 0.0) * 1024.0 ** 3
            except (TypeError, ValueError):
                continue
        return cls(
            mem_total_mib=max(1.0, mem_total),
            mem_avail_mib=min(mem_total, max(0.0, mem_avail)),
            volumes_total_bytes=max(1.0, vol_total),
        )


def build_lattice_vectors(
    scan_id: str,
    nodes: list[dict],
    runtime: dict,
    *,
    now_iso: str,
) -> dict:
    """Build the ``lattice_vectors.json`` payload in memory. Atomic write is the caller's."""
    runtime_agg = RuntimeAggregate.from_runtime(runtime or {})
    ctx = {
        "mem_total_mib":       runtime_agg.mem_total_mib,
        "mem_avail_mib":       runtime_agg.mem_avail_mib,
        "volumes_total_bytes": runtime_agg.volumes_total_bytes,
    }
    vectors: dict[str, list[float]] = {}
    for node in nodes:
        rel = str(node.get("path", "")).replace("\\", "/")
        if not rel:
            continue
        nid = derive_node_id(rel)
        vectors[nid] = compile_vector(node, ctx, now_iso=now_iso)
    return {
        "schema_version": SCHEMA_VERSION_SNAPSHOT,
        "scan_id":        scan_id,
        "vector_field_names": list(VECTOR25_FIELD_NAMES),
        "vector_len":     EXPECTED_VECTOR_LEN,
        "vector_count":   len(vectors),
        "vectors":        vectors,
    }


def build_graph_delta(
    scan_id: str,
    base_digest: str,
    node_paths: list[str],
    *,
    received_at_ms: int,
) -> dict:
    """Build the initial SSE delta — append-only ``upsert`` ops, LWW HLT ordered.

    Each op carries ``occurred_hlt = (physical_ms, occurrence_idx)`` so a
    second compile run produces the SAME delta (deterministic for sha256).
    """
    physical_ms = received_at_ms
    operations: list[dict] = []
    for idx, rel in enumerate(node_paths):
        nid = derive_node_id(rel)
        operations.append({
            "kind": "upsert",
            "node_id": nid,
            "fields": {"path": rel},
            "occurred_hlt": [physical_ms, idx],
        })
    return {
        "schema_version": SCHEMA_VERSION_DELTA,
        "scan_id":        scan_id,
        "base_digest":    base_digest,
        "received_at_ms": received_at_ms,
        "hlt":            [physical_ms, len(operations)],
        "operations":     operations,
    }


def build_redacted_entiremap(
    scan_id: str,
    nodes: list[dict],
) -> str:
    """Single-bullet-per-node markdown; sensitive basenames get ``[REDACTED]`` badge."""
    out_lines: list[str] = [
        f"# Cybertronia entire-map (redacted) — scan_id `{scan_id}`",
        "",
        "> Generated by Phase 2 (`control_plane/cybertronia_compile.py`).",
        "> Sensitive basenames are masked; all paths are root-relative.",
        "",
        "| layer | kind | sensitivity | node_id | path |",
        "|-------|------|-------------|---------|------|",
    ]
    for node in sorted(
        nodes, key=lambda n: (str(n.get("path", "")), str(n.get("kind", "")))
    ):
        rel = str(node.get("path", "")).replace("\\", "/")
        if not rel:
            continue
        layer     = derive_layer(rel)
        kind      = str(node.get("kind", "file"))
        basename  = Path(rel).name
        sens      = derive_sensitivity(basename)
        sens_name = ("low", "med", "high")[sens]
        nid       = derive_node_id(rel)
        safe_bnm  = redact_basename(basename)
        if safe_bnm == "[REDACTED]":
            rendered_path = f"`{layer}/[REDACTED]`"
        else:
            rendered_path = f"`{rel}`"
        out_lines.append(
            f"| {layer} | {kind} | {sens_name} | `{nid}` | {rendered_path} |"
        )
    out_lines.append("")
    if not nodes:
        out_lines.append("_no nodes in this scan; redaction map empty_")
        out_lines.append("")
    return "\n".join(out_lines)


def build_compile_cursor(
    last_digest: str,
    last_seen_at_ms: int,
    *,
    lag_batches: int = 0,
    divergence_pending: bool = False,
) -> dict:
    """Final artifact read by ``GET /api/cybertronia-graph/sync-status``.

    ``last_digest`` is the sha256 of lattice_vectors.json payload MINUS its
    own ``base_digest`` field — that way the on-disk file's ``base_digest``
    equals the cursor pointer verbatim, and a consumer can verify by NOT
    including the ``base_digest`` field in the recomputation. SSE consumers
    that recompute over the full on-disk payload WILL see false divergence
    (by 1 sha256-input-block) — see ``contract_ref.verify_hint`` below.
    """
    return {
        "schema_version":     SCHEMA_VERSION_SNAPSHOT,
        "last_digest":        last_digest,
        "last_seen_at_ms":    last_seen_at_ms,
        "lag_batches":        lag_batches,
        "divergence_pending": divergence_pending,
        "contract_ref": {
            "spec":     "CAMELOT_OS/docs/cybertronia-graph-ui-spec.md",
            "section":  "§8 SSE endpoint shape · row 4 (sync-status)",
            "impl":     "control_plane/cybertronia_compile.py (Phase 2)",
            "consumer": "control_plane/cognitive_service.py sync-status handler",
            "verify_hint": (
                "last_digest is sha256(lattice_payload WITHOUT its 'base_digest' field). "
                "Recomputing over the full on-disk lattice_payload WILL diverge (off-by-one "
                "block). To verify, drop the 'base_digest' key and sha256 of the remainder; "
                "that result MUST equal cursor['last_digest'] verbatim."
            ),
        },
    }


# ── Top-level compile driver ─────────────────────────────────────────────────

def compile_from_telemetry(
    telemetry: dict,
    *,
    now_iso: Optional[str] = None,
    received_at_ms: Optional[int] = None,
) -> dict:
    """Read a Phase 1 ``node_telemetry.json`` dict and emit the four artifacts.

    Returns the four payloads written (each as a dict) so test code can
    assert against shape + content WITHOUT taking a dependency on disk.
    Atomic disk writes are a separate side-effect — call
    :func:`publish_artifacts` for that.
    """
    now_iso        = now_iso or _utc_now_iso()
    received_at_ms = received_at_ms or _utc_now_ms()

    scan_id = str(telemetry.get("scan_id") or "").strip()
    if not scan_id:
        raise ValueError("telemetry.scan_id is empty; refusing to compile")
    nodes   = list(telemetry.get("nodes") or [])
    runtime = telemetry.get("runtime") or {}

    lattice = build_lattice_vectors(
        scan_id=scan_id,
        nodes=nodes,
        runtime=runtime,
        now_iso=now_iso,
    )
    # base_digest anchors the SSE stream's first delta to lattice_vectors.json
    # so the consumer's atomic-swap (spec §4.3 step 2) can verify continuity.
    base_digest    = _sha256_hex(lattice)
    lattice["base_digest"] = base_digest

    node_paths = sorted(
        {str(n.get("path", "")).replace("\\", "/") for n in nodes if n.get("path")},
        key=str,
    )
    delta = build_graph_delta(
        scan_id=scan_id,
        base_digest=base_digest,
        node_paths=node_paths,
        received_at_ms=received_at_ms,
    )
    entiremap  = build_redacted_entiremap(scan_id, nodes)
    delta_digest = _sha256_hex(delta)  # not stored; useful in tests
    cursor = build_compile_cursor(
        last_digest        = base_digest,
        last_seen_at_ms    = received_at_ms,
        lag_batches        = 0,
        divergence_pending = False,
    )
    return {
        "scan_id":      scan_id,
        "now_iso":      now_iso,
        "received_at_ms": received_at_ms,
        "lattice":      lattice,
        "delta":        delta,
        "entiremap":    entiremap,
        "cursor":       cursor,
        "_meta":        {
            "base_digest":  base_digest,
            "delta_digest": delta_digest,
            "nodes_seen":   len(nodes),
        },
    }


def publish_artifacts(artifacts: dict) -> dict:
    """Atomic-write each artifact to PHASE2_ROOT; return paths written."""
    PHASE2_ROOT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(LATTICE_VECTORS,    artifacts["lattice"])
    atomic_write_json(GRAPH_DELTA_FILE,   artifacts["delta"])
    REDACTED_ENTIREMAP.write_text(
        artifacts["entiremap"], encoding="utf-8"
    )
    atomic_write_json(COMPILE_CURSOR,     artifacts["cursor"])
    return {
        "lattice_vectors":     LATTICE_VECTORS,
        "graph_delta":         GRAPH_DELTA_FILE,
        "entiremap":           REDACTED_ENTIREMAP,
        "compile_cursor":      COMPILE_CURSOR,
    }


def compile_from_phase1_path(
    telemetry_path: Path = PHASE1_TELEMETRY,
    *,
    publish: bool = True,
) -> dict:
    """CLI entrypoint: read telemetry, build, optionally publish."""
    if not telemetry_path.exists():
        raise FileNotFoundError(
            f"Phase 1 telemetry not found at {telemetry_path}; run "
            "`python -m control_plane.cybertronia_audit scan <root>` first."
        )
    try:
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Phase 1 telemetry invalid JSON: {e}") from e
    artifacts = compile_from_telemetry(telemetry)
    if publish:
        paths = publish_artifacts(artifacts)
        artifacts["_published_paths"] = {k: str(v) for k, v in paths.items()}
    return artifacts


# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m control_plane.cybertronia_compile",
        description=(
            "Phase 2 compiler: convert Phase 1 audit telemetry "
            "(`control_plane/cybertronia_audit.py`) into the 4 contract "
            "artifacts consumed by Phase 4 transport (`cognitive_service.py`)."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser(
        "compile",
        help="Phase 1 telemetry → 4 contract artifacts (default: scan tree + publish)",
    )
    s.add_argument(
        "--from-telemetry",
        default=str(PHASE1_TELEMETRY),
        help="path to Phase 1 node_telemetry.json",
    )
    s.add_argument(
        "--no-publish",
        action="store_true",
        help="build artifacts in memory only (test path)",
    )

    sub.add_parser("status", help="print Phase 1/2 footprint + schema_versions")
    sub.add_parser("cursor",  help="print compile_cursor.json contents (or 'absent')")

    return p


def _cli() -> int:
    args = _build_parser().parse_args()
    if args.cmd == "status":
        out = {
            "version":                __version__,
            "phase1_root":            str(PHASE1_ROOT),
            "phase2_root":            str(PHASE2_ROOT),
            "telemetry_exists":       PHASE1_TELEMETRY.exists(),
            "lattice_vectors_exists": LATTICE_VECTORS.exists(),
            "graph_delta_exists":     GRAPH_DELTA_FILE.exists(),
            "entiremap_exists":       REDACTED_ENTIREMAP.exists(),
            "compile_cursor_exists":  COMPILE_CURSOR.exists(),
            "schema_versions":        [SCHEMA_VERSION_SNAPSHOT, SCHEMA_VERSION_DELTA],
            "vector_field_names":     list(VECTOR25_FIELD_NAMES),
            "vector_len":             EXPECTED_VECTOR_LEN,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "cursor":
        cur = read_compile_cursor()
        if cur is None:
            print(json.dumps({
                "status":   "absent",
                "expected_path": str(COMPILE_CURSOR),
                "hint":     "run `python -m control_plane.cybertronia_compile compile` first",
            }, indent=2))
            return 0
        print(json.dumps(cur, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "compile":
        artifacts = compile_from_phase1_path(
            Path(args.from_telemetry).resolve(),
            publish=not args.no_publish,
        )
        out = {
            "scan_id":        artifacts["scan_id"],
            "nodes_seen":     artifacts["_meta"]["nodes_seen"],
            "base_digest":    artifacts["_meta"]["base_digest"],
            "delta_digest":   artifacts["_meta"]["delta_digest"],
            "delta_ops":      len(artifacts["delta"]["operations"]),
            "published_paths": artifacts.get("_published_paths", {}),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
