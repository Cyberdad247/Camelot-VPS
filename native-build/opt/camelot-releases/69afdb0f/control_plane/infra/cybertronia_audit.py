#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""cybertronia_audit.py -- Metadata-only resource-guarded audit for Cybertronia.

P1.CYB-1. Reads ONLY file metadata (path, size, mtime, kind); file content
is never opened. Rechecks ``psutil.virtual_memory().available`` every 500
files OR 250 ms (whichever lands first); raises :class:`MemoryFloorBreached`
if available_mem drops below 800 MiB. Pre-flight aborts the scan entirely
if the floor is already breached on entry.

Atomic JSON flush is via a sibling .tmp file (``tempfile.mkstemp``),
``os.fsync`` to commit byte-level writes, then ``os.replace`` to publish
the artifact in a single directory-entry transition. A startup sweeper
removes orphan ``*.tmp`` siblings.

Artifacts (under ``03_VAULT/runtime_state/cybertronia_graph/``)::

    node_telemetry.json   -- {scan_id, schema, nodes[], runtime, summary?, checkpoint}
    cursor.json           -- scan cursor for deterministic resume (same scan_id)
    scan.meta.json        -- final-exit summary, written only on completion/abort

The **cursor** is the contract for resume: scan_id is a deterministic
sha256-derived 16-hex of ``(root, started_at_iso)``; ``last_path`` is
root-relative so the absolute scan root can be re-supplied by the operator
or calling script on the next invocation.

Exclusion philosophy is intentionally inline (NOT coupled to ``squires.ghost``):
GHOST is a post-processing content scanner; the audit module is metadata-only.
The list mirrors GHOST's high-value carve-outs so post-scan redaction is
zero-drift across the two flows.

CLI::

    python -m control_plane.cybertronia_audit scan <path> [--resume-from-cursor]
    python -m control_plane.cybertronia_audit resume
    python -m control_plane.cybertronia_audit status
    python -m control_plane.cybertronia_audit verify
    python -m control_plane.cybertronia_audit sweep
"""
from __future__ import annotations

__version__ = "9000.14-CYB-1"

import argparse
import gc
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

try:
    import psutil  # type: ignore[import-not-found]
    _PSUTIL_OK = True
except ImportError:                      # pragma: no cover - capability gate
    psutil = None                       # type: ignore[assignment]
    _PSUTIL_OK = False


# ---------------------------------------------------------------------------
# Paths (workspace-relative; honor CAMELOT_HOME env override)
# ---------------------------------------------------------------------------

CAMELOT_HOME = Path(
    os.environ.get("CAMELOT_HOME", str(Path(__file__).resolve().parent.parent))
)
RUNTIME_ROOT = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "cybertronia_graph"
TELEMETRY_FILE = RUNTIME_ROOT / "node_telemetry.json"
CURSOR_FILE    = RUNTIME_ROOT / "cursor.json"
SCAN_META_FILE = RUNTIME_ROOT / "scan.meta.json"


# ---------------------------------------------------------------------------
# Gates (frozen; tests pin these)
# ---------------------------------------------------------------------------

MEMORY_FLOOR_BYTES   = 800 * 1024 * 1024          # 800 MiB abort floor per spec
MEMORY_TARGET_BYTES  = 1500 * 1024 * 1024         # 1500 MiB audit target
RECHECK_FILES        = 500                        # every N files
RECHECK_MS           = 250                        # every N ms
GC_EVERY_K_FILES     = 10_000                     # checkpoint interval
SWEEP_ON_START       = True                       # remove orphan .tmp siblings

PROBE_LISTENING_PORTS = True
PROBE_TOP_N_PROCS     = 25


# ---------------------------------------------------------------------------
# Exclusion rules (inline; mirrors squires/ghost.py philosophy, no coupling)
# ---------------------------------------------------------------------------

EXCLUDE_DIR_NAMES: frozenset[str] = frozenset({
    ".git", "node_modules", ".venv", "venv", ".cache", "__pycache__",
    ".next", ".tsbuildinfo", ".turbo", ".worktrees", "target", "build",
    "dist", ".ruff_cache", ".cargo", ".qdrant", ".colony", ".hive",
    ".secrets_backup",
})

EXCLUDE_FILE_GLOBS: tuple[str, ...] = (
    # databases
    "*.db", "*.db-journal", "*.sqlite", "*.sqlite3", "*.sqlite-journal",
    # vector + lance + arrow
    "*.parquet", "*.arrow", "*.lance",
    # model weights
    "*.pkl", "*.pth", "*.pt", "*.onnx", "*.safetensors", "*.gguf",
    # logs / scratch
    "*.log", "*.err.log", "*.out.log", "*.tmp", "*.swp", "*.bak",
)

EXCLUDE_NAME_PREFIXES: tuple[str, ...] = (
    ".env",                                     # .env, .env.local, .env.production
    ".secrets_backup",
    "credentials",
)


# ---------------------------------------------------------------------------
# Exceptions (typed boundary errors)
# ---------------------------------------------------------------------------

class MemoryFloorBreached(RuntimeError):
    """Available memory fell below the configured floor (800 MiB default)."""


class CapabilityMissing(RuntimeError):
    """Hard-required capability is unavailable on this host."""

    def __init__(self, message: str, missing: tuple[str, ...] = ()):
        super().__init__(message)
        self.missing = missing


class CursorInvalid(ValueError):
    """cursor.json does not match the schema; auto-resume refused."""


# ---------------------------------------------------------------------------
# Capability + memory probes
# ---------------------------------------------------------------------------

def check_capabilities() -> dict:
    """Static capability probe. Raises :class:`CapabilityMissing` if psutil
    is not importable. The audit module never lies about the floor; if we
    cannot read available_mem we abort the entire scan.
    """
    missing: list[str] = []
    if not _PSUTIL_OK:
        missing.append("psutil")
    if missing:
        raise CapabilityMissing(
            "cybertronia_audit requires: " + ", ".join(missing) +
            ". Activate the .venv or install psutil>=5.9.",
            missing=tuple(missing),
        )
    return {
        "psutil": "ok",
        "platform": sys.platform,
        "process_rss_mib": round(_rss_mib(), 1),
    }


def available_mem_bytes() -> int:
    """Return ``psutil.virtual_memory().available``.

    Substituting a placeholder is forbidden by the spec; we either have the
    real probe or we abort.
    """
    if not _PSUTIL_OK:
        raise CapabilityMissing("psutil unavailable; cannot read available_mem")
    return int(psutil.virtual_memory().available)


def _rss_mib() -> float:
    proc = psutil.Process(os.getpid())
    return float(proc.memory_info().rss) / (1024 ** 2)


# ---------------------------------------------------------------------------
# Atomic JSON writer (write-temp + fsync + os.replace)
# ---------------------------------------------------------------------------

def atomic_write_json(path: Path, payload: dict) -> None:
    """Write ``payload`` to ``path`` atomically.

    Crash semantics:

    * Crash BEFORE ``fsync``: only the ``.tmp`` is corrupted; ``path`` is
      unchanged.
    * Crash AFTER ``fsync`` BEFORE ``replace``: ``.tmp`` is durable; ``path``
      is stale.
    * Crash AFTER ``replace``: ``path`` is durable; ``.tmp`` may be orphaned
      (sweeper cleans it on the next start).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # Windows fsync is best-effort; the directory journal still
                # commits the byte-stream.
                pass
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def sweep_stale_tmp_files(path: Path) -> list[str]:
    """Remove orphan ``*.tmp`` siblings of ``path`` left by a prior crash."""
    removed: list[str] = []
    for sibling in path.parent.glob(path.name + ".*.tmp"):
        try:
            sibling.unlink()
            removed.append(str(sibling))
        except OSError:
            pass
    return removed


# ---------------------------------------------------------------------------
# Cursor schema
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Cursor:
    """Resume contract. ``last_path`` is ROOT-RELATIVE so a resume against
    a moved workspace or different cwd remains valid; the operator or the
    calling CLI supplies the absolute scan root again.
    """

    scan_id:    str                       # 16-hex sha256 of (root, started_at)
    last_path:  str                       # root-relative path of last visited file
    files_seen: int
    started_at: str                       # ISO8601 UTC, frozen across resumes
    updated_at: str                       # ISO8601 UTC, refreshed per checkpoint
    excl_hits:  int = 0
    bytes_seen: int = 0
    notes:      str = ""                  # free-form, e.g. abort/interrupt reason

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "Cursor":
        required = {
            "scan_id", "last_path", "files_seen", "started_at", "updated_at",
        }
        missing_keys = required - set(raw.keys())
        if missing_keys:
            raise CursorInvalid(
                f"cursor.json missing required keys: {sorted(missing_keys)}"
            )
        # FIX-3: reject empty identifiers — two empty scan_ids would collide
        # in Phase 2's compiler dedup-by-scan_id, and an empty last_path means
        # the scan hasn't progressed far enough to resume safely.
        scan_id   = str(raw["scan_id"]).strip()
        last_path = str(raw["last_path"]).strip()
        if not scan_id:
            raise CursorInvalid(
                "cursor.scan_id is empty; refusing auto-resume"
            )
        if not last_path:
            raise CursorInvalid(
                "cursor.last_path is empty; the saved scan hasn't "
                "progressed enough to resume safely"
            )
        return cls(
            scan_id    = scan_id,
            last_path  = last_path,
            files_seen = int(raw["files_seen"]),
            started_at = str(raw["started_at"]),
            updated_at = str(raw["updated_at"]),
            excl_hits  = int(raw.get("excl_hits", 0)),
            bytes_seen = int(raw.get("bytes_seen", 0)),
            notes      = str(raw.get("notes", "")),
        )


def load_cursor(path: Path = CURSOR_FILE) -> Optional[Cursor]:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CursorInvalid(f"cursor.json is not valid JSON: {e}") from e
    return Cursor.from_dict(raw)


def save_cursor(cursor: Cursor) -> None:
    atomic_write_json(CURSOR_FILE, cursor.to_dict())


# ---------------------------------------------------------------------------
# Exclusion predicate (kept inline so post-scan redaction is zero-drift
# with the audit pass)
# ---------------------------------------------------------------------------

# Hoisted: import re is at top of module (FIX-2, per code-review).
_SEGMENT_SEPARATORS_RE = re.compile(r"[\\/]+")


def _segments(rel: str) -> list[str]:
    return [s for s in _SEGMENT_SEPARATORS_RE.split(rel) if s]


_EXACT_GLOB_PATTERNS = tuple(pat for pat in EXCLUDE_FILE_GLOBS if "*" not in pat)
# FIX-4: PREFIX and SUFFIX bucket filters were SWAPPED at file origin.
# The on-disk PREFIX filter `pat.startswith(*) and not pat.endswith(*)`
# matched every `*.<ext>` SUFFIX-shaped glob and dumped all 20 patterns
# into the PREFIX bucket, while SUFFIX became empty -- so every `*.db`,
# `*.safetensors`, `*.onnx`, `*.log`, `*.tmp` file silently fell through
# is_excluded as if it were a legitimate source file. match-function
# semantics were correct (_matches_suffix uses `pat[1:]`, _matches_prefix
# uses `pat[:-1]`) so the fix is purely bucket reassignment.
_PREFIX_GLOB_PATTERNS = tuple(pat for pat in EXCLUDE_FILE_GLOBS if pat.endswith("*") and not pat.startswith("*"))
_SUFFIX_GLOB_PATTERNS = tuple(pat for pat in EXCLUDE_FILE_GLOBS if pat.startswith("*") and not pat.endswith("*"))
_CONTAINS_GLOB_PATTERNS = tuple(pat for pat in EXCLUDE_FILE_GLOBS if pat.startswith("*") and pat.endswith("*"))


def _matches_exact(low: str) -> bool:
    return any(low == pat.lower() for pat in _EXACT_GLOB_PATTERNS)


def _matches_suffix(low: str) -> bool:
    return any(low.endswith(pat[1:].lower()) for pat in _SUFFIX_GLOB_PATTERNS)


def _matches_prefix(low: str) -> bool:
    return any(low.startswith(pat[:-1].lower()) for pat in _PREFIX_GLOB_PATTERNS)


def _matches_contains(low: str) -> bool:
    return any(pat[1:-1].lower() in low for pat in _CONTAINS_GLOB_PATTERNS)


def is_excluded(rel_path: str, name: str) -> bool:
    """Return True if ``rel_path`` (root-relative) or ``name`` (basename) is excluded.

    The exact/suffix/prefix/contains split avoids any fnmatch dependency
    *and* avoids an import-time cache — crawls in the millions of files
    can otherwise grow the fnmatch _cache unboundedly.
    """
    if name.startswith(EXCLUDE_NAME_PREFIXES):
        return True
    segments = _segments(rel_path)
    for seg in segments:
        if seg in EXCLUDE_DIR_NAMES:
            return True
    low = name.lower()
    if _matches_exact(low):
        return True
    if _matches_prefix(low):
        return True
    if _matches_suffix(low):
        return True
    if _matches_contains(low):
        return True
    return False


# ---------------------------------------------------------------------------
# Walk stats + memory recheck
# ---------------------------------------------------------------------------

@dataclass
class WalkStats:
    files_seen:        int = 0
    bytes_seen:        int = 0
    excl_hits:         int = 0
    last_check_files:  int = 0
    last_check_ms:     float = 0.0
    aborted:           Optional[str] = None

    def should_recheck_files(self) -> bool:
        return (self.files_seen - self.last_check_files) >= RECHECK_FILES

    def should_recheck_ms(self) -> bool:
        return ((time.monotonic() - self.last_check_ms) * 1000.0) >= RECHECK_MS


def memory_recheck(stats: WalkStats, label: str = "") -> None:
    """Consolidated recheck entrypoint. Raises MemoryFloorBreached on dip.

    Called from inside the walker via the cadence check on
    :func:`WalkStats.should_recheck_files` / ``should_recheck_ms``.
    """
    avail = available_mem_bytes()
    stats.last_check_files = stats.files_seen
    stats.last_check_ms = time.monotonic()
    if avail < MEMORY_FLOOR_BYTES:
        stats.aborted = (
            f"{label}:available<800MiB({avail // (1024 * 1024)}MiB)"
        )
        raise MemoryFloorBreached(
            f"available_mem={avail} bytes < floor {MEMORY_FLOOR_BYTES}; recheck label={label!r}"
        )


def preflight_check() -> dict:
    """Pre-flight probe. Returns a dict of the gate state for the CLI status
    print. Raises :class:`MemoryFloorBreached` if the floor is already breached
    on entry; raises :class:`CapabilityMissing` if psutil is missing.
    """
    cap = check_capabilities()
    avail = available_mem_bytes()
    payload = {
        "capabilities": cap,
        "available_mem_mib": int(avail // (1024 ** 2)),
        "floor_mib": MEMORY_FLOOR_BYTES // (1024 ** 2),
        "target_mib": MEMORY_TARGET_BYTES // (1024 ** 2),
        "floor_pass": avail >= MEMORY_FLOOR_BYTES,
        "target_pass": avail >= MEMORY_TARGET_BYTES,
    }
    if not payload["floor_pass"]:
        raise MemoryFloorBreached(
            f"pre-flight available_mem={avail} < floor {MEMORY_FLOOR_BYTES}"
        )
    return payload


# ---------------------------------------------------------------------------
# Metadata-only per-file record (NEVER reads file content)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileMeta:
    path:        str            # root-relative, POSIX separators
    size:        int
    mtime:       float          # epoch seconds
    is_file:     bool
    is_dir:      bool
    is_symlink:  bool

    def to_dict(self) -> dict:
        return {
            "path":  self.path,
            "size":  self.size,
            "mtime": datetime.fromtimestamp(self.mtime, tz=timezone.utc)
                                     .isoformat(timespec="seconds"),
            "kind":  ("dir" if self.is_dir else
                      "symlink" if self.is_symlink else "file"),
        }


def _stat_metadata_only(root: Path, p: Path) -> FileMeta:
    """Stat a single path WITHOUT reading content. Symlinks are reported as
    is_symlink=True; size is the link's target stat (low-cost, helpful for
    the lattice's exposure axis later).
    """
    st = p.stat() if not p.is_symlink() else p.stat(follow_symlinks=False)
    rel = str(p.relative_to(root)).replace("\\", "/")
    return FileMeta(
        path       = rel,
        size       = int(st.st_size),
        mtime      = float(st.st_mtime),
        is_file    = p.is_file(),
        is_dir     = p.is_dir(),
        is_symlink = p.is_symlink(),
    )


# ---------------------------------------------------------------------------
# Walker -- os.scandir for cheap streaming enumeration
# ---------------------------------------------------------------------------

def iter_metadata(root: Path, stats: WalkStats) -> Iterator[FileMeta]:
    """Yield :class:`FileMeta` for every non-excluded path under ``root``.

    Memory contract:
      * No slurp-list anywhere; ``os.scandir`` yields DirEntry lazily.
      * Checkpoint cadence drives PERIODIC gc.collect() (every
        ``GC_EVERY_K_FILES``) so inhabited memory stays bounded across
        multi-million-file walks.
    """
    if not root.exists():
        raise FileNotFoundError(f"scan root does not exist: {root}")
    root = root.resolve()

    def _emit(p: Path) -> Iterator[FileMeta]:
        name = p.name
        rel  = str(p.relative_to(root)).replace("\\", "/")
        if is_excluded(rel, name):
            stats.excl_hits += 1
            return
        try:
            meta = _stat_metadata_only(root, p)
        except (OSError, PermissionError):
            return
        stats.files_seen += 1
        stats.bytes_seen += meta.size
        if stats.should_recheck_files() or stats.should_recheck_ms():
            memory_recheck(stats, label=f"after {stats.files_seen} files")
        yield meta

    stack: list[Path] = [root]
    while stack:
        here = stack.pop()
        try:
            entries = list(os.scandir(here))
        except (OSError, PermissionError):
            continue
        for entry in entries:
            p = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                # FIX-1: pre-check exclusion BEFORE descending so node_modules,
                # target, __pycache__, .git, dist, build, venv, .venv, etc. are
                # not enumerated at all. This is the difference between an
                # 800 MiB safe run and a floor-trip on the first monorepo hit.
                rel_self = str(p.relative_to(root)).replace("\\", "/")
                if is_excluded(rel_self, p.name):
                    stats.excl_hits += 1
                    continue
                yield from _emit(p)
                if entry.is_dir(follow_symlinks=True):
                    stack.append(p)
            else:
                yield from _emit(p)


# ---------------------------------------------------------------------------
# Runtime telemetry (processes + listening ports + volumes + cpu)
# ---------------------------------------------------------------------------

@dataclass
class RuntimeTelemetry:
    cpu_arch:      str
    cpu_count_log: int
    mem_total_mib: int
    mem_avail_mib: int
    volumes:       list = field(default_factory=list)
    listen_ports:  list = field(default_factory=list)
    top_procs:     list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cpu_arch":      self.cpu_arch,
            "cpu_count_log": self.cpu_count_log,
            "mem_total_mib": self.mem_total_mib,
            "mem_avail_mib": self.mem_avail_mib,
            "volumes":       self.volumes,
            "listen_ports":  self.listen_ports,
            "top_procs":     self.top_procs,
        }


def _machine_arch() -> str:
    try:
        import platform
        return " ".join(platform.architecture()) + " " + platform.machine()
    except Exception:
        return sys.platform


def collect_runtime_telemetry() -> RuntimeTelemetry:
    """One-shot runtime probe. Read-only; no file content reads."""
    vm = psutil.virtual_memory()
    rt = RuntimeTelemetry(
        cpu_arch      = _machine_arch(),
        cpu_count_log = int(psutil.cpu_count(logical=True) or 0),
        mem_total_mib = int(vm.total // (1024 ** 2)),
        mem_avail_mib = int(vm.available // (1024 ** 2)),
    )
    try:
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            rt.volumes.append({
                "device":    part.device,
                "mount":     part.mountpoint,
                "fstype":    part.fstype,
                "total_gib": round(usage.total / (1024 ** 3), 2),
                "used_gib":  round(usage.used  / (1024 ** 3), 2),
                "free_gib":  round(usage.free  / (1024 ** 3), 2),
            })
    except Exception:
        pass

    if PROBE_LISTENING_PORTS:
        try:
            for c in psutil.net_connections(kind="inet"):
                if c.status == psutil.CONN_LISTEN and c.laddr:
                    rt.listen_ports.append({
                        "proto": "tcp" if c.type == psutil.SOCK_STREAM else "udp",
                        "addr":  c.laddr.ip,
                        "port":  c.laddr.port,
                        "pid":   c.pid,
                    })
        except (psutil.AccessDenied, OSError):
            pass

    try:
        rows: list[dict] = []
        for p in psutil.process_iter(["name", "pid"]):
            try:
                m = p.memory_info()
                rows.append({
                    "pid":     p.info["pid"],
                    "name":    p.info["name"] or "",
                    "rss_mib": int(m.rss // (1024 ** 2)),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        rows.sort(key=lambda r: r["rss_mib"], reverse=True)
        rt.top_procs = rows[:PROBE_TOP_N_PROCS]
    except Exception:
        pass
    return rt


# ---------------------------------------------------------------------------
# Scan driver -- public entrypoint
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    scan_id:        str
    root:           str
    started_at:     str
    completed_at:   Optional[str]
    files_recorded: int
    bytes_recorded: int
    excl_hits:      int
    exit_reason:    str                          # "complete" | "memory_abort" | "interrupted" | "in_progress"
    nodes:          list = field(default_factory=list)


def _scan_id_for(root: Path, started_at: str) -> str:
    h = hashlib.sha256(
        (str(root.resolve()) + "|" + started_at).encode("utf-8")
    ).hexdigest()
    return h[:16]


def sweep_at_start() -> list[str]:
    """Remove orphan ``*.tmp`` siblings under the runtime root."""
    if not RUNTIME_ROOT.exists():
        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        return []
    removed: list[str] = []
    for prefix in (TELEMETRY_FILE, CURSOR_FILE, SCAN_META_FILE):
        removed.extend(sweep_stale_tmp_files(prefix))
    return removed


def start_scan(root: Path, resume: Optional[Cursor] = None) -> ScanResult:
    """Run a metadata-only scan honoring the 500-file/250-ms memory gate.

    On :class:`MemoryFloorBreached` OR :class:`KeyboardInterrupt`, partial
    state is flushed (cursor + telemetry with partial ``nodes[]``) so the
    caller can call :func:`start_scan` again with the same cursor (same
    ``scan_id``) to continue. This is the resume contract.
    """
    check_capabilities()
    avail = available_mem_bytes()
    if avail < MEMORY_FLOOR_BYTES:
        raise MemoryFloorBreached(
            f"pre-flight available_mem={avail} < floor {MEMORY_FLOOR_BYTES}"
        )

    if SWEEP_ON_START:
        sweep_at_start()

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    stats = WalkStats()
    rt = collect_runtime_telemetry()

    started_at = (
        resume.started_at if resume
        else datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    scan_id = resume.scan_id if resume else _scan_id_for(root, started_at)
    cursor = Cursor(
        scan_id    = scan_id,
        last_path  = resume.last_path if resume else "",
        files_seen = 0,
        started_at = started_at,
        updated_at = started_at,
    )
    result = ScanResult(
        scan_id        = scan_id,
        root           = str(root.resolve()),
        started_at     = started_at,
        completed_at   = None,
        files_recorded = 0,
        bytes_recorded = 0,
        excl_hits      = 0,
        exit_reason    = "in_progress",
    )

    async_nodes: list[dict] = []
    try:
        for fm in iter_metadata(root, stats):
            async_nodes.append(fm.to_dict())
            cursor.last_path  = fm.path
            cursor.files_seen = stats.files_seen
            cursor.excl_hits  = stats.excl_hits
            cursor.bytes_seen = stats.bytes_seen
            cursor.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if stats.files_seen and stats.files_seen % GC_EVERY_K_FILES == 0:
                flush_checkpoint(scan_id, cursor, async_nodes, rt, result)
                async_nodes.clear()
                gc.collect()
    except MemoryFloorBreached as e:
        cursor.notes = f"memory_abort:{e}"
        result.exit_reason = "memory_abort"
        flush_checkpoint(scan_id, cursor, async_nodes, rt, result)
        return result
    except KeyboardInterrupt:
        cursor.notes = "interrupted:KeyboardInterrupt"
        result.exit_reason = "interrupted"
        flush_checkpoint(scan_id, cursor, async_nodes, rt, result)
        return result

    result.completed_at   = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result.files_recorded = stats.files_seen
    result.bytes_recorded = stats.bytes_seen
    result.excl_hits      = stats.excl_hits
    result.exit_reason    = "complete"
    result.nodes          = async_nodes
    flush_final(scan_id, cursor, result, rt)
    return result


def _telemetry_payload(scan_id: str, cursor: Cursor, nodes: list,
                      rt: RuntimeTelemetry, result: ScanResult,
                      *, checkpoint: bool) -> dict:
    return {
        "scan_id":      scan_id,
        "schema":       "cybertronia.telemetry/v1",
        "root":         result.root,
        "started_at":   result.started_at,
        "completed_at": result.completed_at,
        "nodes":        nodes,
        "runtime":      rt.to_dict(),
        "summary": None if checkpoint else {
            "files_recorded": result.files_recorded,
            "bytes_recorded": result.bytes_recorded,
            "excl_hits":      result.excl_hits,
            "exit_reason":    result.exit_reason,
        },
        "checkpoint":   checkpoint,
        "cursor":       cursor.to_dict(),
    }


def flush_checkpoint(scan_id: str, cursor: Cursor, nodes: list,
                     rt: RuntimeTelemetry, result: ScanResult) -> None:
    """Write ``node_telemetry.json`` (with checkpoint=True) + ``cursor.json``.

    No ``scan.meta.json`` on checkpoint -- that file is written only on
    final exit by :func:`flush_final`.
    """
    payload = _telemetry_payload(scan_id, cursor, nodes, rt, result,
                                 checkpoint=True)
    atomic_write_json(TELEMETRY_FILE, payload)
    save_cursor(cursor)


def flush_final(scan_id: str, cursor: Cursor, result: ScanResult,
                rt: RuntimeTelemetry) -> None:
    cursor.notes = result.exit_reason
    save_cursor(cursor)
    payload = _telemetry_payload(scan_id, cursor, result.nodes,
                                 rt, result, checkpoint=False)
    atomic_write_json(TELEMETRY_FILE, payload)
    atomic_write_json(SCAN_META_FILE, {
        "scan_id":        scan_id,
        "root":           result.root,
        "started_at":     result.started_at,
        "completed_at":   result.completed_at,
        "exit_reason":    result.exit_reason,
        "files_recorded": result.files_recorded,
        "bytes_recorded": result.bytes_recorded,
        "excl_hits":      result.excl_hits,
    })


# ---------------------------------------------------------------------------
# Verify -- post-scan integrity gate
# ---------------------------------------------------------------------------

def verify_telemetry(path: Path = TELEMETRY_FILE) -> dict:
    """Quick invariants on a flushed telemetry file. Pure read."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    nodes = raw.get("nodes") or []
    allowed_keys = {"path", "size", "mtime", "kind"}
    return {
        "schema_ok":       raw.get("schema") == "cybertronia.telemetry/v1",
        "has_scan_id":     bool(raw.get("scan_id")),
        "node_count":      len(nodes),
        "no_content_field": all(set(d.keys()) <= allowed_keys for d in nodes),
        "summary_present":  raw.get("summary") is not None or bool(raw.get("checkpoint")),
        "completed_at":     raw.get("completed_at"),
        "runtime_present":  isinstance(raw.get("runtime"), dict),
    }


# ---------------------------------------------------------------------------
# CLI (python -m control_plane.cybertronia_audit)
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m control_plane.cybertronia_audit",
        description="Cybertronia metadata-only resource-guarded audit "
                    "(code-only; live scans require operator pre-flight)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Run a metadata-only scan (operator-gated)")
    s.add_argument("path")
    s.add_argument("--resume-from-cursor",
                   help="path to cursor.json used for deterministic resume")

    r = sub.add_parser("resume",
                       help="Resume from cursor.json at the default path")
    r.add_argument("--from-cursor", default=str(CURSOR_FILE))

    sub.add_parser("status",
                   help="Print capabilities + memory floor + cursor/telemetry presence")
    sub.add_parser("sweep",
                   help="Remove orphan *.tmp siblings under the runtime root")
    sub.add_parser("verify",
                   help="Verify node_telemetry.json invariants (no live scan)")
    return p


def _cli() -> int:
    args = _build_parser().parse_args()

    if args.cmd == "status":
        try:
            pre = preflight_check()
        except (MemoryFloorBreached, CapabilityMissing) as e:
            pre = {"error": type(e).__name__, "detail": str(e)}
        print(json.dumps({
            "runtime_root":  str(RUNTIME_ROOT),
            "telemetry_exists": TELEMETRY_FILE.exists(),
            "cursor_exists":    CURSOR_FILE.exists(),
            "scan_meta_exists": SCAN_META_FILE.exists(),
            "preflight":     pre,
        }, indent=2))
        return 0

    if args.cmd == "sweep":
        removed = sweep_at_start()
        print(json.dumps({"removed_count": len(removed), "removed": removed}, indent=2))
        return 0

    if args.cmd == "verify":
        if not TELEMETRY_FILE.exists():
            print(json.dumps({"error": "telemetry_missing",
                              "expected_path": str(TELEMETRY_FILE)}, indent=2))
            return 2
        print(json.dumps(verify_telemetry(), indent=2))
        return 0

    if args.cmd == "scan":
        root = Path(args.path).resolve()
        resume = None
        if args.resume_from_cursor:
            resume = Cursor.from_dict(
                json.loads(Path(args.resume_from_cursor).read_text(encoding="utf-8"))
            )
        elif CURSOR_FILE.exists():
            try:
                resume = load_cursor()
            except CursorInvalid:
                resume = None
        result = start_scan(root, resume=resume)
        print(json.dumps({
            "scan_id":        result.scan_id,
            "files_recorded": result.files_recorded,
            "bytes_recorded": result.bytes_recorded,
            "excl_hits":      result.excl_hits,
            "exit_reason":    result.exit_reason,
            "completed_at":   result.completed_at,
        }, indent=2))
        return 0

    if args.cmd == "resume":
        cursor = load_cursor(Path(args.from_cursor))
        if cursor is None:
            print(json.dumps({"error": "no_cursor",
                              "path": args.from_cursor}, indent=2))
            return 2
        # Resume replays the walker from a fresh path arg supplied by the
        # caller later; for now, we re-attach the root from the SCAN_META_FILE
        # if present, else refuse.
        meta_root: Optional[Path] = None
        if SCAN_META_FILE.exists():
            try:
                meta = json.loads(SCAN_META_FILE.read_text(encoding="utf-8"))
                meta_root = Path(meta["root"]).resolve()
            except (json.JSONDecodeError, KeyError):
                meta_root = None
        if meta_root is None:
            print(json.dumps({"error": "no_scan_meta",
                              "hint": "pass --path <root> via `scan --resume-from-cursor` instead"},
                             indent=2))
            return 2
        result = start_scan(meta_root, resume=cursor)
        print(json.dumps({
            "scan_id":        result.scan_id,
            "files_recorded": result.files_recorded,
            "exit_reason":    result.exit_reason,
            "completed_at":   result.completed_at,
        }, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
