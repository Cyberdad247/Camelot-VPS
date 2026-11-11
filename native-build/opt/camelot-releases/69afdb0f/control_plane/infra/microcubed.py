# SPDX-License-Identifier: MIT

"""Microcubed SmolVM task housing for Camelot-OS.

Microcubed creates small, traceable task houses for knights and Nano-Knights.
The first implementation is a filesystem isolation contract: it prepares a
bounded workspace, writes a task contract, and optionally appends a queue
directive. It does not execute untrusted work by itself.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "03_VAULT" / "runtime_state" / "microcubed"
QUEUE_FILE = REPO_ROOT / "logs" / "harness_queue.jsonl"
LATEST_PATH = STATE_DIR / "microcubed_latest.json"
INDEX_PATH = STATE_DIR / "microcubed_index.jsonl"

DEFAULT_ALLOWED_TOOLS = ["read", "write_workspace", "run_tests", "ledger_report"]
DEFAULT_RESOURCE_CAPS = {
    "timeout_seconds": 900,
    "max_files": 250,
    "max_write_mb": 25,
    "network": "disabled_by_default",
}

KNOWN_KNIGHTS = {
    "sir_forge",
    "sir_sentinel",
    "sir_debug",
    "sir_codex",
    "sir_boris",
    "sir_alex",
    "sir_link",
    "sir_helio",
    "sir_ghost",
    "lady_apis",
    "squire_clean",
    "squire_format",
    "squire_audit",
    "squire_myrmidon",
}

DANGEROUS_COMMAND_PATTERNS = [
    r"\bdel\b",
    r"\brd\b",
    r"\brmdir\b",
    r"\brm\b",
    r"remove-item",
    r"\bformat\b",
    r"\bshutdown\b",
    r"restart-computer",
    r"git\s+reset\s+--hard",
    r"set-executionpolicy",
    r"\breg\s+delete\b",
]


@dataclass(frozen=True)
class MicrocubedRequest:
    objective: str
    knight: str = "sir_forge"
    house: str | None = None
    tenant: str | None = None
    timeout_seconds: int = 900
    max_write_mb: int = 25
    queue: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, *, fallback: str = "task") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:64] or fallback


def _safe_knight(knight: str) -> str:
    normalized = knight.strip().lower().replace("-", "_")
    if not re.fullmatch(r"[a-z0-9_]+", normalized):
        raise ValueError(f"Invalid knight id: {knight!r}")
    return normalized


def _task_id(objective: str, knight: str) -> str:
    digest = hashlib.sha256(f"{knight}\n{objective}\n{_utc_now()}".encode("utf-8")).hexdigest()
    return f"mc3-{digest[:10]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _append_queue(contract: dict[str, Any]) -> dict[str, Any]:
    task_id = contract["task_id"]
    entry = {
        "id": f"{task_id}-queue",
        "knight": contract["tenant"],
        "directive": (
            "Microcubed SmolVM house ready: "
            f"{contract['paths']['contract']} :: objective={contract['objective']}"
        ),
        "priority": 2,
        "submitted": _utc_now(),
        "microcubed_house": contract["house_id"],
    }
    _append_jsonl(QUEUE_FILE, entry)
    return {"queued": True, "queue_file": str(QUEUE_FILE), "entry": entry}


def _safe_house_id(house_id: str) -> str:
    safe_house = _slug(house_id, fallback="")
    if not safe_house or safe_house != house_id:
        raise ValueError(f"Invalid house id: {house_id!r}")
    return safe_house


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_contract(house_id: str) -> dict[str, Any]:
    safe_house = _safe_house_id(house_id)
    contract_path = STATE_DIR / "houses" / safe_house / "contract.json"
    if not contract_path.exists():
        raise FileNotFoundError(f"Microcubed house not found: {house_id}")
    return _load_json(contract_path)


def _relative_files(path: Path) -> list[str]:
    if not path.exists():
        return []
    files: list[str] = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            files.append(item.relative_to(path).as_posix())
    return files


def _workspace_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def _execution_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _update_contract_status(contract: dict[str, Any], status: str) -> None:
    contract["status"] = status
    contract["updated_utc"] = _utc_now()
    _write_json(Path(contract["paths"]["contract"]), contract)
    if LATEST_PATH.exists():
        latest = _load_json(LATEST_PATH)
        if latest.get("house_id") == contract.get("house_id"):
            _write_json(LATEST_PATH, contract)


def _update_manifest(contract: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    manifest_path = Path(contract["paths"]["manifest"])
    manifest = _load_json(manifest_path) if manifest_path.exists() else {"house_id": contract["house_id"]}
    manifest.update(updates)
    manifest["updated_utc"] = _utc_now()
    _write_json(manifest_path, manifest)
    return manifest


def preflight_command(contract: dict[str, Any], command: list[str]) -> dict[str, Any]:
    findings: list[str] = []
    if not command:
        findings.append("Command is required.")

    joined = " ".join(str(part) for part in command).lower()
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, joined):
            findings.append(f"Blocked dangerous command pattern: {pattern}")

    workspace = Path(contract["paths"]["workspace"]).resolve()
    house = Path(contract["paths"]["house"]).resolve()
    try:
        workspace.relative_to(house)
    except ValueError:
        findings.append("Workspace must remain inside the Microcubed house.")

    if contract.get("status") == "RUNNING":
        findings.append("House is already RUNNING.")

    if findings:
        return {"status": "BLOCKED_BY_SENTINEL", "findings": findings}
    return {"status": "PASSED", "findings": []}


def build_contract(request: MicrocubedRequest) -> dict[str, Any]:
    if not request.objective.strip():
        raise ValueError("Microcubed objective is required")

    knight = _safe_knight(request.knight)
    tenant = _safe_knight(request.tenant or knight)
    task_id = _task_id(request.objective, tenant)
    house_slug = _slug(request.house or request.objective, fallback=task_id)
    house_id = f"{house_slug}-{task_id}"
    house_dir = STATE_DIR / "houses" / house_id

    resource_caps = dict(DEFAULT_RESOURCE_CAPS)
    resource_caps["timeout_seconds"] = max(1, int(request.timeout_seconds))
    resource_caps["max_write_mb"] = max(1, int(request.max_write_mb))

    contract = {
        "status": "PLANNED",
        "protocol": "microcubed-smolvm-v1",
        "task_id": task_id,
        "house_id": house_id,
        "objective": request.objective.strip(),
        "knight": knight,
        "tenant": tenant,
        "known_tenant": tenant in KNOWN_KNIGHTS,
        "created_utc": _utc_now(),
        "resource_caps": resource_caps,
        "allowed_tools": list(DEFAULT_ALLOWED_TOOLS),
        "guardrails": [
            "No command execution during forge unless explicitly queued.",
            "Writes must stay inside the house workspace.",
            "Secrets, credentials, and destructive operations require HITL.",
            "Outputs must be summarized into manifest.json before teardown.",
        ],
        "paths": {
            "house": str(house_dir),
            "workspace": str(house_dir / "workspace"),
            "inbox": str(house_dir / "inbox"),
            "outbox": str(house_dir / "outbox"),
            "logs": str(house_dir / "logs"),
            "contract": str(house_dir / "contract.json"),
            "manifest": str(house_dir / "manifest.json"),
        },
    }
    return contract


def plan_house(request: MicrocubedRequest) -> dict[str, Any]:
    contract = build_contract(request)
    return {
        "status": "PLANNED",
        "contract": contract,
        "next_command": (
            "camelot microcubed forge "
            f"\"{contract['objective']}\" --knight {contract['tenant']}"
        ),
    }


def forge_house(request: MicrocubedRequest) -> dict[str, Any]:
    contract = build_contract(request)
    house_dir = Path(contract["paths"]["house"])
    for key in ("workspace", "inbox", "outbox", "logs"):
        Path(contract["paths"][key]).mkdir(parents=True, exist_ok=True)

    contract["status"] = "READY"
    manifest = {
        "status": "READY",
        "house_id": contract["house_id"],
        "task_id": contract["task_id"],
        "tenant": contract["tenant"],
        "objective": contract["objective"],
        "created_utc": contract["created_utc"],
        "updated_utc": _utc_now(),
        "workspace_files": [],
        "outbox_files": [],
        "teardown_ready": False,
    }
    _write_json(Path(contract["paths"]["contract"]), contract)
    _write_json(Path(contract["paths"]["manifest"]), manifest)
    _write_json(LATEST_PATH, contract)
    _append_jsonl(
        INDEX_PATH,
        {
            "event": "forge",
            "house_id": contract["house_id"],
            "task_id": contract["task_id"],
            "tenant": contract["tenant"],
            "objective": contract["objective"],
            "timestamp": _utc_now(),
        },
    )

    queue_result = {"queued": False}
    if request.queue:
        queue_result = _append_queue(contract)

    return {
        "status": "READY",
        "house": str(house_dir),
        "contract": contract,
        "manifest": manifest,
        "queue": queue_result,
    }


def status() -> dict[str, Any]:
    houses_dir = STATE_DIR / "houses"
    houses: list[dict[str, Any]] = []
    if houses_dir.exists():
        for contract_path in sorted(houses_dir.glob("*/contract.json")):
            try:
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            houses.append(
                {
                    "house_id": contract.get("house_id"),
                    "task_id": contract.get("task_id"),
                    "tenant": contract.get("tenant"),
                    "objective": contract.get("objective"),
                    "status": contract.get("status"),
                    "contract": str(contract_path),
                }
            )
    latest = None
    if LATEST_PATH.exists():
        latest = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    return {
        "status": "OK",
        "state_dir": str(STATE_DIR),
        "house_count": len(houses),
        "houses": houses,
        "latest": latest,
    }


def execute_house(
    house_id: str,
    command: list[str],
    *,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    contract = _load_contract(house_id)
    preflight = preflight_command(contract, command)
    if preflight["status"] != "PASSED":
        _update_contract_status(contract, "BLOCKED_BY_SENTINEL")
        manifest = _update_manifest(
            contract,
            {
                "status": "BLOCKED_BY_SENTINEL",
                "preflight": preflight,
                "teardown_ready": False,
            },
        )
        _append_jsonl(
            INDEX_PATH,
            {
                "event": "execute_blocked",
                "house_id": contract["house_id"],
                "tenant": contract["tenant"],
                "timestamp": _utc_now(),
                "findings": preflight["findings"],
            },
        )
        return {
            "status": "BLOCKED_BY_SENTINEL",
            "house_id": contract["house_id"],
            "preflight": preflight,
            "manifest": manifest,
        }

    workspace = Path(contract["paths"]["workspace"])
    logs_dir = Path(contract["paths"]["logs"])
    workspace.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    timeout = int(timeout_seconds or contract["resource_caps"]["timeout_seconds"])
    output_log = logs_dir / f"execute_{_execution_stamp()}.json"

    _update_contract_status(contract, "RUNNING")
    _update_manifest(
        contract,
        {
            "status": "RUNNING",
            "preflight": preflight,
            "last_command": command,
            "teardown_ready": False,
        },
    )

    stdout = ""
    stderr = ""
    returncode: int | None
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        returncode = None
        timed_out = True

    workspace_files = _relative_files(workspace)
    outbox_files = _relative_files(Path(contract["paths"]["outbox"]))
    output_payload = {
        "house_id": contract["house_id"],
        "tenant": contract["tenant"],
        "command": command,
        "cwd": str(workspace),
        "timeout_seconds": timeout,
        "timed_out": timed_out,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "workspace_files": workspace_files,
        "outbox_files": outbox_files,
        "timestamp": _utc_now(),
    }
    _write_json(output_log, output_payload)

    max_bytes = int(contract["resource_caps"]["max_write_mb"]) * 1024 * 1024
    status_value = "COMPLETE" if returncode == 0 and not timed_out else "FAILED"
    if _workspace_bytes(workspace) > max_bytes:
        status_value = "FAILED_RESOURCE_LIMIT"

    _update_contract_status(contract, status_value)
    manifest = _update_manifest(
        contract,
        {
            "status": status_value,
            "preflight": preflight,
            "workspace_files": workspace_files,
            "outbox_files": outbox_files,
            "teardown_ready": status_value == "COMPLETE",
            "last_execution": {
                "command": command,
                "cwd": str(workspace),
                "returncode": returncode,
                "timed_out": timed_out,
                "output_log": str(output_log),
            },
        },
    )
    _append_jsonl(
        INDEX_PATH,
        {
            "event": "execute",
            "house_id": contract["house_id"],
            "tenant": contract["tenant"],
            "status": status_value,
            "returncode": returncode,
            "timestamp": _utc_now(),
        },
    )
    return {
        "status": status_value,
        "house_id": contract["house_id"],
        "preflight": preflight,
        "execution": {
            "command": command,
            "cwd": str(workspace),
            "returncode": returncode,
            "timed_out": timed_out,
            "output_log": str(output_log),
        },
        "manifest": manifest,
    }


def inspect_house(house_id: str) -> dict[str, Any]:
    contract = _load_contract(house_id)
    manifest_path = Path(contract["paths"]["manifest"])
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    last_execution = manifest.get("last_execution") or {}
    output_log = last_execution.get("output_log")
    last_output = None
    if output_log and Path(output_log).exists():
        last_output = _load_json(Path(output_log))

    workspace = Path(contract["paths"]["workspace"])
    outbox = Path(contract["paths"]["outbox"])
    logs = Path(contract["paths"]["logs"])
    recent_logs = [str(path) for path in sorted(logs.glob("*.json"))[-5:]] if logs.exists() else []

    return {
        "status": "OK",
        "house_id": contract["house_id"],
        "task_id": contract["task_id"],
        "tenant": contract["tenant"],
        "objective": contract["objective"],
        "house_status": contract.get("status"),
        "manifest_status": manifest.get("status"),
        "teardown_ready": bool(manifest.get("teardown_ready")),
        "paths": contract["paths"],
        "contract": contract,
        "manifest": manifest,
        "workspace_files": _relative_files(workspace),
        "outbox_files": _relative_files(outbox),
        "recent_logs": recent_logs,
        "last_execution": last_execution,
        "last_output": last_output,
    }


def teardown_house(house_id: str, *, archive: bool = True) -> dict[str, Any]:
    _safe_house_id(house_id)

    house_dir = STATE_DIR / "houses" / house_id
    if not house_dir.exists():
        return {"status": "MISSING", "house_id": house_id, "house": str(house_dir)}

    if archive:
        archive_dir = STATE_DIR / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / f"{house_id}.zip"
        if target.exists():
            target.unlink()
        shutil.make_archive(str(target.with_suffix("")), "zip", root_dir=house_dir)
    else:
        target = None

    shutil.rmtree(house_dir)
    _append_jsonl(
        INDEX_PATH,
        {
            "event": "teardown",
            "house_id": house_id,
            "archive": str(target) if target else None,
            "timestamp": _utc_now(),
        },
    )
    return {
        "status": "TORN_DOWN",
        "house_id": house_id,
        "archive": str(target) if target else None,
    }
