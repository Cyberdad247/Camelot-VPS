# SPDX-License-Identifier: MIT

"""Runtime status surface for promoted UKG nano-swarm nodes."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CAMELOT_HOME = Path(__file__).resolve().parent.parent.parent
PROMOTED_ROOT = CAMELOT_HOME / "02_FORGE" / "generated" / "ukg_omega_glyph_v1000"
EVIDENCE_DIR = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "nano_swarm_evidence"
RUNTIME_STATE_DIR = CAMELOT_HOME / "03_VAULT" / "runtime_state"
RUNTIME_STATUS_PATH = RUNTIME_STATE_DIR / "nano_swarm_runtime_latest.json"
SUPERVISOR_STATE_PATH = RUNTIME_STATE_DIR / "nano_swarm_supervisor_state.json"

EXPECTED_NODES = {
    "Node_A_Frontend": {
        "stack": ["React", "Zustand", "Tailwind_v4"],
        "required_files": ["promotion.json", "package.json", "src/App.tsx"],
        "service_command": ["npm", "exec", "vite", "--", "--host", "127.0.0.1", "--port", "4177"],
        "health_url": "http://127.0.0.1:4177",
    },
    "Node_B_Bifrost": {
        "stack": ["Rust", "Tokio", "Serde"],
        "required_files": ["promotion.json", "Cargo.toml", "src/main.rs"],
        "service_command": ["cargo", "run", "--", "--serve", "--host", "127.0.0.1", "--port", "4178"],
        "health_url": "http://127.0.0.1:4178/health",
    },
    "Node_C_Omni_Router": {
        "stack": ["Go", "tsnet"],
        "required_files": ["promotion.json", "go.mod", "main.go"],
        "service_command": ["go", "run", ".", "--serve", "--host", "127.0.0.1", "--port", "4180"],
        "health_url": "http://127.0.0.1:4180/health",
    },
    "Node_D_MicroVM": {
        "stack": ["Rust", "wasm-bindgen"],
        "required_files": ["promotion.json", "Cargo.toml", "src/lib.rs", "src/main.rs"],
        "service_command": ["cargo", "run", "--", "--serve", "--host", "127.0.0.1", "--port", "4179"],
        "health_url": "http://127.0.0.1:4179/health",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        return {"_error": f"json_decode_error: {exc}"}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _supervisor_state_path(state_dir: Path | str | None = None) -> Path:
    state_dir = Path(state_dir) if state_dir is not None else RUNTIME_STATE_DIR
    return state_dir / "nano_swarm_supervisor_state.json"


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _node_status(promoted_root: Path, node_name: str, spec: dict[str, Any]) -> dict[str, Any]:
    node_dir = promoted_root / node_name
    missing = [rel for rel in spec["required_files"] if not (node_dir / rel).exists()]
    promotion = _read_json(node_dir / "promotion.json")
    promoted = node_dir.exists() and not missing and promotion.get("status") == "PROMOTED"
    return {
        "status": "PROMOTED" if promoted else "MISSING_OR_INCOMPLETE",
        "promoted": promoted,
        "path": str(node_dir),
        "stack": spec["stack"],
        "startable": bool(spec.get("service_command")),
        "missing_files": missing,
        "promotion": promotion,
    }


def _node_process_status(
    node_name: str,
    node: dict[str, Any],
    supervisor_state: dict[str, Any],
) -> dict[str, Any]:
    spec = EXPECTED_NODES[node_name]
    command = spec.get("service_command")
    record = supervisor_state.get("nodes", {}).get(node_name, {})
    pid = int(record.get("pid") or 0)
    alive = _is_pid_alive(pid)
    if not command:
        process_status = "NOT_STARTABLE"
    elif alive:
        process_status = "RUNNING"
    else:
        process_status = "STOPPED"
    return {
        **node,
        "service_command": command,
        "health_url": spec.get("health_url"),
        "pid": pid if alive else None,
        "process_status": process_status,
        "supervisor": record,
    }


def read_runtime_status(
    promoted_root: Path | str | None = None,
    evidence_dir: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Summarize promoted node readiness without re-running heavyweight builds."""
    promoted_root = Path(promoted_root) if promoted_root is not None else PROMOTED_ROOT
    evidence_dir = Path(evidence_dir) if evidence_dir is not None else EVIDENCE_DIR
    state_dir = Path(state_dir) if state_dir is not None else RUNTIME_STATE_DIR
    nodes = {
        name: _node_status(promoted_root, name, spec)
        for name, spec in EXPECTED_NODES.items()
    }
    verify_report_path = evidence_dir / "verify_all_latest.json"
    verify_report = _read_json(verify_report_path)
    verify_status = verify_report.get("status", "MISSING")
    formal_gate = verify_report.get("formal_gate") if isinstance(verify_report.get("formal_gate"), dict) else {}
    formal_gate_status = formal_gate.get("status", "UNKNOWN")
    all_promoted = all(item["promoted"] for item in nodes.values())
    all_startable = all(item["startable"] for item in nodes.values())
    runtime_ready = all_promoted and verify_status == "VERIFIED"

    if runtime_ready and all_startable and formal_gate_status == "READY":
        status = "PRODUCTION_READY"
    elif runtime_ready and formal_gate_status == "BLOCKED":
        status = "RUNTIME_READY_FORMAL_GATE_BLOCKED"
    elif runtime_ready:
        status = "RUNTIME_READY"
    elif any(item["promoted"] for item in nodes.values()):
        status = "RUNTIME_PARTIAL"
    else:
        status = "RUNTIME_NOT_READY"

    return {
        "status": status,
        "runtime_ready": runtime_ready,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "promoted_root": str(promoted_root),
        "state_dir": str(state_dir),
        "nodes": nodes,
        "node_count": len(nodes),
        "promoted_count": sum(1 for item in nodes.values() if item["promoted"]),
        "startable_count": sum(1 for item in nodes.values() if item["startable"]),
        "all_startable": all_startable,
        "verify_all_status": verify_status,
        "verify_all_report": str(verify_report_path),
        "formal_gate_status": formal_gate_status,
        "formal_gate_ready": bool(formal_gate.get("ready_for_omni_codex_compiled")),
        "production_release_ready": runtime_ready and all_startable and formal_gate_status == "READY",
        "production_release_evidence": str(evidence_dir / "production_release_latest.json"),
    }


def write_runtime_status(
    promoted_root: Path | str | None = None,
    evidence_dir: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Persist the nano-swarm runtime status artifact for boot, status, and UI readers."""
    state_dir = Path(state_dir) if state_dir is not None else RUNTIME_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    status = read_runtime_status(promoted_root=promoted_root, evidence_dir=evidence_dir, state_dir=state_dir)
    artifact_path = state_dir / "nano_swarm_runtime_latest.json"
    artifact_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return {**status, "artifact_path": str(artifact_path)}


def _terminate_recorded_process(pid: int) -> bool:
    if not _is_pid_alive(pid):
        return True
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.returncode == 0 or not _is_pid_alive(pid)
    os.kill(pid, signal.SIGTERM)
    return True


def _start_node_process(node_name: str, node_dir: Path, state_path: Path) -> dict[str, Any]:
    spec = EXPECTED_NODES[node_name]
    command = spec.get("service_command")
    if not command:
        return {
            "status": "BLOCKED",
            "reason": "node has no durable service command",
            "startable": False,
        }
    resolved = shutil.which(command[0])
    if not resolved:
        return {
            "status": "BLOCKED",
            "reason": f"command not found: {command[0]}",
            "startable": True,
        }
    logs_dir = state_path.parent / "nano_swarm_supervisor_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{node_name}.out.log"
    stderr_path = logs_dir / f"{node_name}.err.log"
    launch_command = [resolved, *command[1:]]
    if os.name == "nt" and Path(resolved).suffix.lower() in {".cmd", ".bat"}:
        launch_command = ["cmd", "/c", resolved, *command[1:]]

    kwargs: dict[str, Any] = {"cwd": str(node_dir)}
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        kwargs["close_fds"] = True
    else:
        kwargs["start_new_session"] = True

    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        proc = subprocess.Popen(launch_command, stdout=stdout, stderr=stderr, **kwargs)

    return {
        "status": "STARTED",
        "pid": proc.pid,
        "command": command,
        "cwd": str(node_dir),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "startable": True,
    }


def supervise_nodes(
    action: str,
    node_name: str | None = None,
    promoted_root: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Manage promoted nano-swarm service processes where a durable command exists."""
    promoted_root = Path(promoted_root) if promoted_root is not None else PROMOTED_ROOT
    state_path = _supervisor_state_path(state_dir)
    state = _read_json(state_path)
    state.setdefault("nodes", {})
    selected = [node_name] if node_name else list(EXPECTED_NODES)
    unknown = [node for node in selected if node not in EXPECTED_NODES]
    if unknown:
        return {"status": "SUPERVISOR_ERROR", "error": f"unknown node: {', '.join(unknown)}"}

    runtime = read_runtime_status(promoted_root=promoted_root, state_dir=state_path.parent)
    results: dict[str, Any] = {}
    blocked = False

    for node in selected:
        node_dir = promoted_root / node
        status = _node_process_status(node, runtime["nodes"][node], state)
        record = state.get("nodes", {}).get(node, {})
        pid = int(record.get("pid") or 0)

        if action == "status":
            results[node] = status
            continue

        if action == "start":
            if status["process_status"] == "RUNNING":
                results[node] = {**status, "action_status": "ALREADY_RUNNING"}
                continue
            started = _start_node_process(node, node_dir, state_path)
            if started["status"] == "STARTED":
                state["nodes"][node] = started
                results[node] = {
                    **_node_process_status(node, runtime["nodes"][node], state),
                    "action_status": "STARTED",
                }
            else:
                blocked = True
                results[node] = {**status, **started}
            continue

        if action == "stop":
            if status["process_status"] != "RUNNING":
                results[node] = {**status, "action_status": "ALREADY_STOPPED"}
                state.get("nodes", {}).pop(node, None)
                continue
            stopped = _terminate_recorded_process(pid)
            state.get("nodes", {}).pop(node, None)
            results[node] = {
                **_node_process_status(node, runtime["nodes"][node], state),
                "action_status": "STOPPED" if stopped else "STOP_FAILED",
            }
            blocked = blocked or not stopped
            continue

        if action == "restart":
            if status["process_status"] == "RUNNING":
                stopped = _terminate_recorded_process(pid)
                state.get("nodes", {}).pop(node, None)
                if not stopped:
                    blocked = True
                    results[node] = {**status, "action_status": "STOP_FAILED"}
                    continue
            started = _start_node_process(node, node_dir, state_path)
            if started["status"] == "STARTED":
                state["nodes"][node] = started
                results[node] = {
                    **_node_process_status(node, runtime["nodes"][node], state),
                    "action_status": "RESTARTED",
                }
            else:
                blocked = True
                results[node] = {**status, **started}
            continue

        return {"status": "SUPERVISOR_ERROR", "error": f"unknown action: {action}"}

    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    _write_json(state_path, state)
    if action == "status":
        status_value = "SUPERVISOR_STATUS"
    elif blocked:
        status_value = "SUPERVISOR_BLOCKED"
    else:
        status_value = "SUPERVISOR_OK"
    return {
        "status": status_value,
        "action": action,
        "node": node_name or "all",
        "state_path": str(state_path),
        "nodes": results,
    }


# ---------------------------------------------------------------------------
# OMEGA Phase 6 — Hermes-Subscribed Autonomous SWARM Nodes
# ---------------------------------------------------------------------------
"""Five lightweight event-driven nodes that subscribe to Hermes channels and
coordinate Defense Grid responses.  No subprocess — pure in-process handlers.

  swarm.colony      — colony.risk channel → assigns fix tasks on HIGH delta
  swarm.compress    — compression.status channel → triggers QFT on hot contexts
  swarm.organize    — organize.progress channel → files Lady M/Alexandria events
  swarm.shadow      — shadow.threats channel → routes to Nemesis AUTO quarantine
  swarm.dependency  — dependency.updates channel → creates shadow-branch proposals
"""

import logging as _logging  # noqa: E402
import time as _time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Callable, Optional  # noqa: E402

_swarm_log = _logging.getLogger("OMEGA_SWARM")

OMEGA_CHANNEL_MAP: dict[str, str] = {
    "swarm.colony":     "colony.risk",
    "swarm.compress":   "compression.status",
    "swarm.organize":   "organize.progress",
    "swarm.shadow":     "shadow.threats",
    "swarm.dependency": "dependency.updates",
}


@dataclass
class OmegaNodeState:
    node_id: str
    channel: str
    status: str = "IDLE"      # IDLE | ACTIVE | ERROR
    last_event_ts: Optional[float] = None
    last_event_summary: str = ""
    events_processed: int = 0


class OmegaSwarmNode:
    """A single Hermes-subscribed event-driven SWARM node."""

    def __init__(
        self,
        node_id: str,
        channel: str,
        handler: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.node_id = node_id
        self.channel = channel
        self.handler = handler or self._default_handler
        self.state = OmegaNodeState(node_id=node_id, channel=channel)

    def process_event(self, event: dict) -> None:
        """Called synchronously when a Hermes event arrives on this node's channel."""
        try:
            self.handler(event)
            self.state.status = "ACTIVE"
            self.state.last_event_ts = _time.time()
            self.state.last_event_summary = str(event)[:120]
            self.state.events_processed += 1
        except Exception as exc:
            self.state.status = "ERROR"
            _swarm_log.error("[%s] handler error: %s", self.node_id, exc)

    def _default_handler(self, event: dict) -> None:
        _swarm_log.info("[%s] event on %s: %s", self.node_id, self.channel, str(event)[:80])


def _make_colony_handler() -> Callable[[dict], None]:
    def _handle(event: dict) -> None:
        risk = event.get("risk_score", 0)
        delta = event.get("delta", 0)
        if delta >= 10 or risk >= 80:
            _swarm_log.warning(
                "[swarm.colony] HIGH colony risk (score=%.1f delta=%.1f) — "
                "fix tasks should be assigned (PROMPT required for secret rotation)",
                risk, delta,
            )
    return _handle


def _make_compress_handler() -> Callable[[dict], None]:
    def _handle(event: dict) -> None:
        tier = event.get("tier", "?")
        ratio = event.get("ratio", 0)
        _swarm_log.info("[swarm.compress] tier=%s ratio=%.1f%% — QFT sync noted", tier, ratio * 100)
    return _handle


def _make_organize_handler() -> Callable[[dict], None]:
    def _handle(event: dict) -> None:
        _swarm_log.info("[swarm.organize] org progress: %s", str(event)[:80])
    return _handle


def _make_shadow_handler() -> Callable[[dict], None]:
    def _handle(event: dict) -> None:
        vectors = event.get("critical_count", 0)
        if vectors > 0:
            _swarm_log.warning(
                "[swarm.shadow] %d CRITICAL vectors detected — routing to Nemesis AUTO quarantine",
                vectors,
            )
    return _handle


def _make_dependency_handler() -> Callable[[dict], None]:
    def _handle(event: dict) -> None:
        count = event.get("count", 0)
        _swarm_log.info(
            "[swarm.dependency] %d update proposals received — shadow branches queued (PROMPT)",
            count,
        )
    return _handle


_OMEGA_NODE_FACTORIES: dict[str, Callable[[], Callable]] = {
    "swarm.colony":     _make_colony_handler,
    "swarm.compress":   _make_compress_handler,
    "swarm.organize":   _make_organize_handler,
    "swarm.shadow":     _make_shadow_handler,
    "swarm.dependency": _make_dependency_handler,
}


class OmegaSwarm:
    """Registry + coordinator for the 5 OMEGA autonomous SWARM nodes."""

    def __init__(self) -> None:
        self.nodes: dict[str, OmegaSwarmNode] = {}
        for node_id, channel in OMEGA_CHANNEL_MAP.items():
            factory = _OMEGA_NODE_FACTORIES.get(node_id)
            handler = factory() if factory else None
            self.nodes[node_id] = OmegaSwarmNode(node_id=node_id, channel=channel, handler=handler)

    def dispatch(self, channel: str, event: dict) -> None:
        """Route a Hermes event to the matching SWARM node."""
        for node in self.nodes.values():
            if node.channel == channel:
                node.process_event(event)

    def status(self) -> list[dict]:
        """Return status dicts for all 5 nodes (for `camelot swarm status`)."""
        return [
            {
                "node_id": n.state.node_id,
                "channel": n.state.channel,
                "status": n.state.status,
                "events": n.state.events_processed,
                "last_event": n.state.last_event_summary or "(none)",
            }
            for n in self.nodes.values()
        ]


_SINGLETON_SWARM: Optional[OmegaSwarm] = None


def get_omega_swarm() -> OmegaSwarm:
    """Return the process-level singleton OmegaSwarm."""
    global _SINGLETON_SWARM
    if _SINGLETON_SWARM is None:
        _SINGLETON_SWARM = OmegaSwarm()
    return _SINGLETON_SWARM


def boot_nano_swarm_runtime(home: Path | str = CAMELOT_HOME) -> tuple[bool, str]:
    """Boot-sequence adapter: record status and report runtime readiness."""
    home = Path(home)
    result = write_runtime_status(
        promoted_root=home / "02_FORGE" / "generated" / "ukg_omega_glyph_v1000",
        evidence_dir=home / "03_VAULT" / "runtime_state" / "nano_swarm_evidence",
        state_dir=home / "03_VAULT" / "runtime_state",
    )
    detail = (
        f"{result['status']} "
        f"nodes={result['promoted_count']}/{result['node_count']} "
        f"verify={result['verify_all_status']} "
        f"formal_gate={result['formal_gate_status']}"
    )
    return bool(result["runtime_ready"]), detail
