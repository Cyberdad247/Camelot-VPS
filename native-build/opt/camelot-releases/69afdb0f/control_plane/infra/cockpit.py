# SPDX-License-Identifier: MIT

"""Truthful cockpit snapshot and runic exec helpers for Warp/PowerShell."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    psutil = None

from control_plane.runes.runic_router import route_rune


def _detect_home() -> Path:
    env = os.environ.get("CAMELOT_OS_HOME")
    if env and Path(env).is_dir():
        return Path(env)
    return Path(__file__).resolve().parent.parent


CAMELOT_HOME = _detect_home()
RUNTIME_STATE = CAMELOT_HOME / "03_VAULT" / "runtime_state"
CACHE_PATH = RUNTIME_STATE / "cockpit_prompt_latest.json"
LAST_COMMAND_PATH = RUNTIME_STATE / "cockpit_last_command.json"
QUEUE_FILE = CAMELOT_HOME / "logs" / "harness_queue.jsonl"
DONE_FILE = CAMELOT_HOME / "logs" / "worker_done.txt"
WARP_SYNC_PATH = RUNTIME_STATE / "warp_workflow_sync_latest.json"
KNIGHT_CONFIG_PATH = RUNTIME_STATE / "knight_configuration_latest.json"
AWAKEN_BOOT_PATH = RUNTIME_STATE / "awaken_boot_latest.json"

PROMPT_TTL_SECONDS = float(os.environ.get("CAMELOT_COCKPIT_TTL_SECONDS", "8"))
REFRESH_COOLDOWN_SECONDS = float(os.environ.get("CAMELOT_COCKPIT_REFRESH_COOLDOWN_SECONDS", "3"))
PROBE_TIMEOUT_SECONDS = float(os.environ.get("CAMELOT_COCKPIT_PROBE_TIMEOUT_SECONDS", "0.2"))

SERVICE_PROBES: list[tuple[str, str, int]] = [
    ("CLIProxy", "127.0.0.1", 8080),
    ("KineticEdge", "127.0.0.1", 3001),
    ("OmniVoice", "127.0.0.1", 3002),
    ("Holotable", "127.0.0.1", 3000),
    ("KittenTTS", "127.0.0.1", 8300),
    ("SirOctavian", "127.0.0.1", 8400),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _safe_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _probe_port(host: str, port: int, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _queue_stats() -> dict[str, int]:
    total = 0
    done = 0
    if QUEUE_FILE.exists():
        try:
            total = sum(1 for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines() if line.strip())
        except Exception:
            total = 0
    if DONE_FILE.exists():
        try:
            done = sum(1 for line in DONE_FILE.read_text(encoding="utf-8").splitlines() if line.strip())
        except Exception:
            done = 0
    pending = max(0, total - done)
    return {"total": total, "done": done, "pending": pending}


def _system_metrics() -> dict[str, Any]:
    if psutil is None:
        return {
            "cpu_percent": None,
            "memory_percent": None,
            "memory_used_gb": None,
            "memory_total_gb": None,
            "source": "unavailable",
        }
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": round(float(psutil.cpu_percent(interval=0.0)), 1),
        "memory_percent": round(float(vm.percent), 1),
        "memory_used_gb": round((vm.total - vm.available) / (1024**3), 2),
        "memory_total_gb": round(vm.total / (1024**3), 2),
        "source": "psutil",
    }


def _service_metrics() -> dict[str, Any]:
    probes = {
        name: _probe_port(host, port)
        for name, host, port in SERVICE_PROBES
    }
    green = sum(1 for ok in probes.values() if ok)
    if green == len(probes):
        state = "GREEN"
    elif green == 0:
        state = "WARN"
    else:
        state = "DEGRADED"
    return {
        "state": state,
        "green": green,
        "total": len(probes),
        "probes": probes,
    }


def _read_knight_configuration() -> dict[str, Any]:
    data = _safe_read_json(KNIGHT_CONFIG_PATH) or {}
    repo_workflows = CAMELOT_HOME / ".warp" / "workflows"
    live_workflow_count = None
    if repo_workflows.exists():
        live_workflow_count = len(list(repo_workflows.glob("*.y*ml")))
    return {
        "status": data.get("status", "MISSING" if not data else "UNKNOWN"),
        "cartridge_count": data.get("cartridges", {}).get("active_count"),
        "switchboard_terminals": data.get("switchboard_roster", {}).get("count"),
        "warp_workflow_count": live_workflow_count if live_workflow_count is not None else data.get("warp_workflows", {}).get("count"),
    }


def _read_warp_sync() -> dict[str, Any]:
    data = _safe_read_json(WARP_SYNC_PATH) or {}
    return {
        "status": data.get("status", "MISSING" if not data else "UNKNOWN"),
        "workflow_count": data.get("workflow_count"),
        "updated_count": data.get("updated_count"),
        "timestamp_utc": data.get("timestamp_utc"),
    }


def _read_awaken_snapshot() -> dict[str, Any]:
    data = _safe_read_json(AWAKEN_BOOT_PATH) or {}
    return {
        "status": data.get("status", "MISSING" if not data else "UNKNOWN"),
        "required_ok": data.get("required"),
        "optional_ok": data.get("optional"),
        "roster": data.get("roster"),
    }


def _memory_banner(system: dict[str, Any]) -> str | None:
    memory_percent = system.get("memory_percent")
    if isinstance(memory_percent, (int, float)) and memory_percent >= 85.0:
        return f"Memory pressure {memory_percent:.1f}%"
    return None


def refresh_snapshot(*, trigger: str = "manual") -> dict[str, Any]:
    generated = utc_now()
    system = _system_metrics()
    services = _service_metrics()
    queue = _queue_stats()
    last_command = _safe_read_json(LAST_COMMAND_PATH) or {}
    warp = _read_warp_sync()
    knight_config = _read_knight_configuration()
    awaken = _read_awaken_snapshot()
    memory_banner = _memory_banner(system)
    payload = {
        "status": "OK",
        "generated_utc": generated.isoformat(),
        "fresh_until_utc": (generated + timedelta(seconds=PROMPT_TTL_SECONDS)).isoformat(),
        "ttl_seconds": PROMPT_TTL_SECONDS,
        "stale": False,
        "age_seconds": 0.0,
        "trigger": trigger,
        "mode": os.environ.get("CAMELOT_COCKPIT_MODE", "off"),
        "system": system,
        "services": services,
        "queue": queue,
        "last_command": {
            "input": last_command.get("input"),
            "classification": last_command.get("classification"),
            "rune": last_command.get("rune"),
            "knight": last_command.get("knight"),
            "mode": last_command.get("mode"),
            "status": last_command.get("status"),
            "latency_ms": last_command.get("latency_ms"),
            "queued": last_command.get("queued"),
            "timestamp_utc": last_command.get("timestamp_utc"),
        },
        "warp": warp,
        "knight_configuration": knight_config,
        "awaken": awaken,
        "memory_banner": memory_banner,
    }
    _safe_write_json(CACHE_PATH, payload)
    return payload


def _with_freshness(payload: dict[str, Any], *, missing: bool = False) -> dict[str, Any]:
    generated = _parse_utc(payload.get("generated_utc"))
    now = utc_now()
    age_seconds = None if generated is None else max(0.0, round((now - generated).total_seconds(), 2))
    stale = missing or generated is None or age_seconds is None or age_seconds > PROMPT_TTL_SECONDS
    payload = dict(payload)
    payload["age_seconds"] = age_seconds
    payload["stale"] = stale
    if missing:
        payload["status"] = "MISSING"
        payload["stale_reason"] = "snapshot_missing"
    elif stale:
        payload["stale_reason"] = "expired"
    else:
        payload["stale_reason"] = None
    payload.setdefault("ttl_seconds", PROMPT_TTL_SECONDS)
    payload.setdefault("mode", os.environ.get("CAMELOT_COCKPIT_MODE", "off"))
    return payload


def _missing_payload() -> dict[str, Any]:
    return {
        "status": "MISSING",
        "generated_utc": None,
        "fresh_until_utc": None,
        "ttl_seconds": PROMPT_TTL_SECONDS,
        "mode": os.environ.get("CAMELOT_COCKPIT_MODE", "off"),
        "system": _system_metrics(),
        "services": {"state": "WARN", "green": 0, "total": len(SERVICE_PROBES), "probes": {}},
        "queue": _queue_stats(),
        "last_command": _safe_read_json(LAST_COMMAND_PATH) or {},
        "warp": _read_warp_sync(),
        "knight_configuration": _read_knight_configuration(),
        "awaken": _read_awaken_snapshot(),
        "memory_banner": None,
    }


def _maybe_spawn_refresh(current: dict[str, Any], *, reason: str) -> None:
    last_request = _parse_utc(current.get("refresh_requested_utc"))
    if last_request is not None and (utc_now() - last_request).total_seconds() < REFRESH_COOLDOWN_SECONDS:
        return

    marked = dict(current)
    marked["refresh_requested_utc"] = utc_now_iso()
    try:
        _safe_write_json(CACHE_PATH, marked)
    except Exception:
        return

    cmd = [
        sys.executable,
        "-c",
        "from control_plane.cockpit import refresh_snapshot; refresh_snapshot(trigger='background')",
    ]
    kwargs: dict[str, Any] = {
        "cwd": str(CAMELOT_HOME),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000
    else:  # pragma: no cover - Windows is primary target
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kwargs)
    except Exception:
        return


def prompt_payload(*, spawn_refresh: bool = True) -> dict[str, Any]:
    cached = _safe_read_json(CACHE_PATH)
    if cached is None:
        payload = _with_freshness(_missing_payload(), missing=True)
        if spawn_refresh:
            _maybe_spawn_refresh(payload, reason="missing")
        return payload

    payload = _with_freshness(cached)
    if payload.get("stale") and spawn_refresh:
        _maybe_spawn_refresh(payload, reason="stale")
    return payload


def _extract_rune_input(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped:
        return None
    first_line = stripped.splitlines()[0].strip()
    if not (first_line.startswith("//") or first_line.startswith("Omega_")):
        return None
    if " " in first_line:
        rune, param = first_line.split(" ", 1)
    else:
        rune, param = first_line, ""
    return rune, param.strip()


def write_last_command(payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    record["timestamp_utc"] = record.get("timestamp_utc") or utc_now_iso()
    _safe_write_json(LAST_COMMAND_PATH, record)
    return record


def cockpit_exec(text: str) -> dict[str, Any]:
    started = time.perf_counter()
    parsed = _extract_rune_input(text)
    if parsed is None:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        result = {
            "status": "SHELL_PASSTHROUGH",
            "routed": False,
            "classification": "shell",
            "input": text,
            "reason": "input is not runic; execute it directly in the shell",
            "latency_ms": latency_ms,
        }
        write_last_command(result)
        return result

    rune, param = parsed

    # Approval grant gating (CAMELOT_COCKPIT_REQUIRE_APPROVAL_GRANT)
    if os.environ.get("CAMELOT_COCKPIT_REQUIRE_APPROVAL_GRANT") == "true":
        from control_plane import approval_grants

        grant = os.environ.get("CAMELOT_COCKPIT_APPROVAL_GRANT", "")
        try:
            claims = approval_grants.verify_and_consume(grant, text)
        except approval_grants.ApprovalGrantError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            result = {
                "status": "APPROVAL_REJECTED",
                "routed": False,
                "classification": "runic",
                "input": text,
                "rune": rune,
                "reason": str(exc),
                "latency_ms": latency_ms,
            }
            write_last_command(result)
            return result
        context = {"surface": "cockpit", "approval_grant": claims}
    else:
        context = {"surface": "cockpit"}

    routed = route_rune(rune, param, context=context)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    result = {
        "status": "ROUTED" if routed.queued else "QUEUE_WARN",
        "routed": True,
        "classification": "runic",
        "input": text,
        "rune": routed.rune,
        "knight": routed.knight,
        "mode": routed.mode,
        "directive": routed.directive,
        "task_id": routed.task_id,
        "queued": routed.queued,
        "queue_error": routed.queue_error,
        "metadata": routed.metadata,
        "latency_ms": latency_ms,
    }
    write_last_command(result)
    return result
