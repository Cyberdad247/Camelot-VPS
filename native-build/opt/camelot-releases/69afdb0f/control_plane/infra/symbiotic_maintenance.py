# SPDX-License-Identifier: MIT

"""Symbiotic maintenance pipeline executed during Camelot-OS activation.

# HITL: file-ops pre-approved — writes bounded to runtime state snapshots and compressed archives
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

try:
    import requests
except ImportError:
    requests = None


class MCPHiveLink:
    """Agentic bridge for Model Context Protocol (MCP) cluster interaction."""

    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = endpoint or os.environ.get("CAMELOT_MCP_ENDPOINT", "http://localhost:8080/mcp")

    def query_cluster(self, prompt: str) -> dict[str, Any]:
        """Execute a natural language query against the cluster via MCP."""
        if not requests:
            return {"status": "ERROR", "message": "requests library not installed"}
            
        payload = {"method": "query", "params": {"prompt": prompt}}
        try:
            resp = requests.post(self.endpoint, json=payload, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "FAIL", "code": resp.status_code}
        except Exception as e:
            return {"status": "EXCEPTION", "error": str(e)}


_SKIP_DIRS = {
    ".git",
    ".venv",
    ".venv_camelot",
    "node_modules",
    "dist",
    "build",
    "99_ARCHIVE",
}
_CACHE_TARGETS = (
    ".pytest_cache",
    ".pytest-tmp",
    "data/.pytest_cache",
    "data/.pytest_tmp",
    "logs/tmp",
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail(text: str, lines: int = 8) -> str:
    payload = [line for line in text.splitlines() if line.strip()]
    return "\n".join(payload[-lines:])


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _iter_repo_files(root: Path, *, max_files: int) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in _SKIP_DIRS]
        for name in names:
            files.append(Path(current) / name)
            if len(files) >= max_files:
                return files
    return files


def _sha1(path: Path) -> str | None:
    h = hashlib.sha1()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _directory_audit(root: Path, *, quick: bool) -> dict[str, Any]:
    default_max = "2500" if quick else "4000"
    max_files = int(os.environ.get("CAMELOT_SYMBIOTIC_MAX_FILES", default_max))
    if quick:
        max_files = min(max_files, 2500)

    scanned = 0
    total_bytes = 0
    ext_counter: Counter[str] = Counter()
    hottest_files: list[tuple[int, Path]] = []
    stale_logs: list[dict[str, Any]] = []
    duplicate_candidates: dict[int, list[Path]] = defaultdict(list)
    now_ts = time.time()

    for path in _iter_repo_files(root, max_files=max_files):
        try:
            stat = path.stat()
        except OSError:
            continue

        scanned += 1
        total_bytes += stat.st_size
        ext_counter[path.suffix.lower() or "<none>"] += 1

        hottest_files.append((stat.st_size, path))
        hottest_files.sort(key=lambda item: item[0], reverse=True)
        if len(hottest_files) > 12:
            hottest_files.pop()

        age_days = round((now_ts - stat.st_mtime) / 86400, 1)
        if stat.st_size >= 2_000_000 and age_days >= 21 and path.name.endswith((".log", ".jsonl")):
            stale_logs.append(
                {
                    "path": str(path.relative_to(root)),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "age_days": age_days,
                }
            )

        if stat.st_size <= 5_000_000:
            duplicate_candidates[stat.st_size].append(path)

    duplicate_groups: list[list[str]] = []
    for _size, paths in duplicate_candidates.items():
        if len(paths) < 2:
            continue
        digests: dict[str, list[Path]] = defaultdict(list)
        for path in paths[:16]:
            digest = _sha1(path)
            if digest:
                digests[digest].append(path)
        for _digest, dupes in digests.items():
            if len(dupes) > 1:
                duplicate_groups.append([str(path.relative_to(root)) for path in dupes])
            if len(duplicate_groups) >= 8:
                break
        if len(duplicate_groups) >= 8:
            break

    cache_sizes = {}
    for target in _CACHE_TARGETS:
        absolute = root / target
        if absolute.exists():
            cache_sizes[target] = round(_path_size(absolute) / (1024 * 1024), 3)

    top_extensions = [{"extension": ext, "count": count} for ext, count in ext_counter.most_common(8)]
    largest_files = [
        {"path": str(path.relative_to(root)), "size_mb": round(size / (1024 * 1024), 2)}
        for size, path in hottest_files[:10]
    ]

    recommendations: list[str] = []
    if cache_sizes:
        recommendations.append("Purge cache footprints on boot to reclaim ephemeral storage.")
    if stale_logs:
        recommendations.append("Compress stale log artifacts older than 21 days.")
    if duplicate_groups:
        recommendations.append("Review duplicate binary/text assets for dedupe opportunities.")

    return {
        "summary": {
            "scanned_files": scanned,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "max_files_budget": max_files,
        },
        "top_extensions": top_extensions,
        "largest_files": largest_files,
        "stale_logs": stale_logs[:10],
        "duplicate_groups": duplicate_groups[:6],
        "cache_sizes_mb": cache_sizes,
        "recommendations": recommendations,
    }


def _run_command(command: list[str], cwd: Path, *, timeout_s: int) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
        duration_ms = round((time.perf_counter() - t0) * 1000)
        return {
            "name": " ".join(command[:3]),
            "command": command,
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "duration_ms": duration_ms,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        return {
            "name": " ".join(command[:3]),
            "command": command,
            "ok": False,
            "returncode": 124,
            "duration_ms": duration_ms,
            "stderr_tail": f"timeout after {timeout_s}s",
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - t0) * 1000)
        return {
            "name": " ".join(command[:3]),
            "command": command,
            "ok": False,
            "returncode": 1,
            "duration_ms": duration_ms,
            "stderr_tail": f"{type(exc).__name__}: {exc}",
        }


def _self_error_checks(root: Path, *, quick: bool) -> dict[str, Any]:
    lint_targets = ["control_plane", "bin"] if quick else ["control_plane", "bin", "squires"]
    checks = [
        _run_command([sys.executable, "-m", "compileall", "-q", *lint_targets], root, timeout_s=25 if quick else 60),
        _run_command([sys.executable, "-m", "ruff", "check", *lint_targets], root, timeout_s=25 if quick else 60),
    ]
    passed = sum(1 for check in checks if check["ok"])
    return {
        "ok": passed == len(checks),
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
    }


def _collect_pycache_dirs(root: Path, *, limit: int = 1500) -> list[Path]:
    matches: list[Path] = []
    for current, dirs, _ in os.walk(root):
        dirs[:] = [name for name in dirs if name not in _SKIP_DIRS]
        for name in list(dirs):
            if name == "__pycache__":
                matches.append(Path(current) / name)
                if len(matches) >= limit:
                    return matches
    return matches


def _purge_ephemeral(root: Path) -> dict[str, Any]:
    if not _truthy(os.environ.get("CAMELOT_SYMBIOTIC_PURGE", "1")):
        return {"enabled": False, "removed_entries": 0, "reclaimed_mb": 0.0, "removed_paths": []}

    targets = [root / target for target in _CACHE_TARGETS if (root / target).exists()]
    targets.extend(_collect_pycache_dirs(root))
    removed = 0
    reclaimed = 0
    removed_paths: list[str] = []
    errors: list[str] = []

    for target in targets:
        size_before = _path_size(target)
        try:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=False)
            elif target.is_file():
                target.unlink(missing_ok=True)
            removed += 1
            reclaimed += size_before
            if len(removed_paths) < 20:
                removed_paths.append(str(target.relative_to(root)))
        except Exception as exc:
            if len(errors) < 10:
                errors.append(f"{target}: {type(exc).__name__}: {exc}")

    return {
        "enabled": True,
        "removed_entries": removed,
        "reclaimed_mb": round(reclaimed / (1024 * 1024), 3),
        "removed_paths": removed_paths,
        "errors": errors,
    }


def _compress_stale_logs(root: Path) -> dict[str, Any]:
    if not _truthy(os.environ.get("CAMELOT_SYMBIOTIC_COMPRESS", "1")):
        return {"enabled": False, "compressed_files": 0, "saved_mb": 0.0, "compressed_paths": []}

    retention_days = int(os.environ.get("CAMELOT_SYMBIOTIC_LOG_RETENTION_DAYS", "7"))
    min_size_bytes = int(os.environ.get("CAMELOT_SYMBIOTIC_LOG_MIN_BYTES", "65536"))
    log_root = root / "logs"
    if not log_root.exists():
        return {"enabled": True, "compressed_files": 0, "saved_mb": 0.0, "compressed_paths": []}

    now_ts = time.time()
    compressed = 0
    saved_bytes = 0
    compressed_paths: list[str] = []
    errors: list[str] = []

    for path in log_root.rglob("*"):
        if not path.is_file() or path.name.endswith(".gz"):
            continue
        if not (
            path.name.endswith(".log")
            or path.name.endswith(".jsonl")
            or ".log." in path.name
            or path.name.endswith(".txt")
        ):
            continue

        try:
            stat = path.stat()
        except OSError:
            continue
        age_days = (now_ts - stat.st_mtime) / 86400
        if age_days < retention_days or stat.st_size < min_size_bytes:
            continue

        gz_path = path.with_name(path.name + ".gz")
        if gz_path.exists():
            continue
        try:
            with path.open("rb") as source, gzip.open(gz_path, "wb", compresslevel=6) as target:
                shutil.copyfileobj(source, target)
            gz_size = gz_path.stat().st_size
            path.unlink(missing_ok=True)
            compressed += 1
            saved_bytes += max(0, stat.st_size - gz_size)
            if len(compressed_paths) < 20:
                compressed_paths.append(str(gz_path.relative_to(root)))
        except Exception as exc:
            if len(errors) < 10:
                errors.append(f"{path}: {type(exc).__name__}: {exc}")

    return {
        "enabled": True,
        "compressed_files": compressed,
        "saved_mb": round(saved_bytes / (1024 * 1024), 3),
        "compressed_paths": compressed_paths,
        "errors": errors,
    }


def _resource_profile(root: Path) -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    disk = shutil.disk_usage(root)
    disk_free_pct = (disk.free / disk.total) * 100 if disk.total else 0

    mem_total = 0
    mem_available = 0
    mem_pressure = 0.0
    if psutil is not None:
        try:
            vm = psutil.virtual_memory()
            mem_total = int(vm.total)
            mem_available = int(vm.available)
            mem_pressure = round(float(vm.percent) / 100.0, 3)
        except Exception:
            pass

    profile = "balanced"
    if mem_pressure >= 0.75 or disk_free_pct < 10:
        profile = "constrained"
    elif mem_pressure <= 0.45 and disk_free_pct >= 20:
        profile = "performance"

    worker_factor = {"constrained": 0.35, "balanced": 0.6, "performance": 0.8}[profile]
    recommended_workers = max(1, min(cpu_count, int(round(cpu_count * worker_factor))))

    os.environ["CAMELOT_RESOURCE_PROFILE"] = profile
    os.environ["CAMELOT_RECOMMENDED_WORKERS"] = str(recommended_workers)

    return {
        "profile": profile,
        "cpu_count": cpu_count,
        "recommended_workers": recommended_workers,
        "memory_total_mb": round(mem_total / (1024 * 1024), 1) if mem_total else 0.0,
        "memory_available_mb": round(mem_available / (1024 * 1024), 1) if mem_available else 0.0,
        "memory_pressure": mem_pressure,
        "disk_free_pct": round(disk_free_pct, 2),
        "platform": sys.platform,
    }


def _write_artifacts(root: Path, payload: dict[str, Any]) -> dict[str, str]:
    runtime_file = root / "03_VAULT" / "runtime_state" / "symbiotic_maintenance_latest.json"
    history_file = root / "logs" / "symbiotic_maintenance.jsonl"
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.parent.mkdir(parents=True, exist_ok=True)
    runtime_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with history_file.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return {
        "runtime_file": str(runtime_file),
        "history_file": str(history_file),
    }


def _prune_git_worktrees(root: Path) -> dict[str, Any]:
    import subprocess
    pruned_count = 0
    removed_branches = []
    errors = []
    
    try:
        subprocess.run(["git", "worktree", "prune"], cwd=str(root), capture_output=True)
        res = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=str(root), capture_output=True, text=True)
        if res.returncode == 0:
            current_wt = {}
            worktrees = []
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    if current_wt:
                        worktrees.append(current_wt)
                        current_wt = {}
                elif line.startswith("worktree "):
                    current_wt["path"] = line[9:]
                elif line.startswith("branch "):
                    current_wt["branch"] = line[7:].replace("refs/heads/", "")
            if current_wt:
                worktrees.append(current_wt)
                
            for wt in worktrees:
                wt_path_str = wt.get("path", "")
                if not wt_path_str:
                    continue
                wt_path = Path(wt_path_str)
                if wt_path.resolve() == root.resolve():
                    continue
                
                path_lower = wt_path_str.lower()
                is_transient = (
                    ".claude/worktrees" in path_lower or
                    "/.worktrees" in path_lower or
                    ("phase" in path_lower and path_lower.endswith("-wt"))
                )
                if is_transient:
                    rm_res = subprocess.run(["git", "worktree", "remove", "--force", wt_path_str], cwd=str(root), capture_output=True, text=True)
                    if rm_res.returncode == 0:
                        pruned_count += 1
                        branch = wt.get("branch", "")
                        if branch and branch not in ("main", "master"):
                            del_res = subprocess.run(["git", "branch", "-D", branch], cwd=str(root), capture_output=True, text=True)
                            if del_res.returncode == 0:
                                removed_branches.append(branch)
                    else:
                        errors.append(f"Failed to remove worktree {wt_path_str}: {rm_res.stderr.strip()}")
    except Exception as e:
        errors.append(f"Worktree pruner exception: {e}")
        
    return {
        "pruned_worktrees": pruned_count,
        "removed_branches": removed_branches,
        "errors": errors
    }


def boot_symbiotic_maintenance(home: Path, *, quick: bool = False) -> tuple[bool, str]:
    if _truthy(os.environ.get("CAMELOT_SYMBIOTIC_DISABLE")):
        return True, "symbiotic maintenance disabled via CAMELOT_SYMBIOTIC_DISABLE=1"

    strict = _truthy(os.environ.get("CAMELOT_SYMBIOTIC_STRICT"))
    started_at = time.perf_counter()

    try:
        audit = _directory_audit(home, quick=quick)
        checks = _self_error_checks(home, quick=quick)
        purge = _purge_ephemeral(home)
        compression = _compress_stale_logs(home)
        resources = _resource_profile(home)
        worktree_prune = _prune_git_worktrees(home)
        duration_ms = round((time.perf_counter() - started_at) * 1000)

        lint_ok = checks["ok"]
        ok = lint_ok if strict else True
        payload = {
            "engine": "SYMBIOTIC_MAINTENANCE",
            "generated_utc": _utc_now(),
            "strict_mode": strict,
            "quick_mode": quick,
            "status": "OK" if ok else "WARN",
            "duration_ms": duration_ms,
            "audit": audit,
            "checks": checks,
            "purge": purge,
            "compression": compression,
            "resources": resources,
            "worktree_prune": worktree_prune,
        }
        artifact_paths = _write_artifacts(home, payload)
        payload["artifacts"] = artifact_paths
        (home / "03_VAULT" / "runtime_state" / "symbiotic_maintenance_latest.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        msg = (
            "symbiont "
            f"scan={audit['summary']['scanned_files']} "
            f"lint={checks['passed_checks']}/{checks['total_checks']} "
            f"purged={purge['removed_entries']} "
            f"pruned_worktrees={worktree_prune['pruned_worktrees']} "
            f"compressed={compression['compressed_files']} "
            f"profile={resources['profile']} "
            f"({duration_ms}ms)"
        )
        if strict and not lint_ok:
            msg += " [strict lint gate]"
        return ok, msg
    except Exception as exc:  # pragma: no cover
        payload = {
            "engine": "SYMBIOTIC_MAINTENANCE",
            "generated_utc": _utc_now(),
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }
        try:
            _write_artifacts(home, payload)
        except Exception:
            pass
        return False, f"symbiont exception: {type(exc).__name__}: {exc}"
