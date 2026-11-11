# SPDX-License-Identifier: MIT

"""Forge Law bootstrap cartridge compiler and guarded kinetic executor.

The source documents remain human-readable. Execution is driven exclusively by
the adjacent ``forge.json`` contract so Markdown can never become an implicit
command language.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CAMELOT_HOME = Path(__file__).resolve().parents[1]
DEFAULT_STORE = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "forge_law"
DEFAULT_LEDGER = CAMELOT_HOME / "03_VAULT" / "Missions" / "verification_ledger.jsonl"
PROTOCOL_VERSION = "forge-law/v1"
SOURCE_FILES = ("blueprint.md", "tasks.md", "verification.md", "forge.json")
CARTRIDGE_STATES = {
    "drafted",
    "validated",
    "awaiting_approval",
    "approved",
    "executing",
    "verified",
    "failed",
    "rolled_back",
}
OPERATION_TYPES = {"write_file", "run_check", "build", "service_restart"}
PROTECTED_PATHS = {
    "provenance_ledger.md",
    "docs/provenance_ledger.md",
    "03_vault/provenance_ledger.md",
    "03_vault/missions/verification_ledger.jsonl",
    "03_vault/training/configs/provenance_ledger.md",
}
_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|private[_-]?key|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"
)


class ForgeLawError(ValueError):
    """Raised when a cartridge violates the Forge Law contract."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _within(path: Path, root: Path) -> Path:
    root = root.resolve()
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ForgeLawError(f"path escapes declared target root: {path}") from exc
    return resolved


def _relative_target(value: Any, root: Path) -> tuple[str, Path]:
    if not isinstance(value, str) or not value.strip():
        raise ForgeLawError("write_file path must be a non-empty string")
    raw = value.replace("\\", "/").strip()
    while raw.startswith("./"):
        raw = raw[2:]
    if Path(raw).is_absolute() or not raw:
        raise ForgeLawError(f"absolute or empty target path is forbidden: {value}")
    normalized = Path(raw).as_posix().lower()
    if Path(raw).name.lower() in {".env", ".env.local", ".env.production", "credentials.json", "secrets.json"}:
        raise ForgeLawError(f"secret-bearing target path is forbidden: {raw}")
    if normalized in PROTECTED_PATHS:
        raise ForgeLawError(f"protected ledger path is not writable: {raw}")
    target = _within(root / raw, root)
    parent = target.parent
    while parent != root and parent.exists():
        if parent.is_symlink():
            raise ForgeLawError(f"symlink traversal is forbidden: {raw}")
        parent = parent.parent
    if target.exists() and target.is_symlink():
        raise ForgeLawError(f"symlink target is forbidden: {raw}")
    return raw, target


def _source_hashes(source: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in SOURCE_FILES:
        path = source / name
        if not path.is_file():
            raise ForgeLawError(f"required Forge Law source is missing: {path}")
        hashes[name] = _digest_bytes(path.read_bytes())
    return hashes


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForgeLawError(f"invalid JSON contract: {path}") from exc
    if not isinstance(value, dict):
        raise ForgeLawError(f"JSON contract must be an object: {path}")
    return value


def _topological_operations(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {op["id"]: op for op in operations}
    ordered: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(operation_id: str) -> None:
        if operation_id in visited:
            return
        if operation_id in visiting:
            raise ForgeLawError(f"operation dependency cycle includes {operation_id}")
        visiting.add(operation_id)
        for dependency in by_id[operation_id].get("dependsOn", []):
            if dependency not in by_id:
                raise ForgeLawError(f"operation {operation_id} depends on unknown operation {dependency}")
            visit(dependency)
        visiting.remove(operation_id)
        visited.add(operation_id)
        ordered.append(by_id[operation_id])

    for operation_id in by_id:
        visit(operation_id)
    return ordered


def _validate_argv(operation: dict[str, Any]) -> None:
    argv = operation.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise ForgeLawError(f"operation {operation['id']} requires a non-empty argv array")
    executable = Path(argv[0]).name.lower()
    tail = [item.lower() for item in argv[1:]]
    allowed = False
    if executable in {"python", "python.exe", "py", "py.exe"}:
        allowed = len(tail) >= 2 and tail[0] == "-m" and tail[1] in {"pytest", "compileall"}
    elif executable in {"npm", "npm.cmd"}:
        allowed = len(tail) >= 2 and tail[0] in {"run", "test"} and (tail[0] == "test" or tail[1] in {"test", "typecheck", "build", "verify"})
    elif executable in {"cargo", "cargo.exe"}:
        allowed = bool(tail) and tail[0] in {"test", "check", "build"}
    elif executable in {"go", "go.exe"}:
        allowed = bool(tail) and tail[0] == "test"
    if not allowed:
        raise ForgeLawError(f"operation {operation['id']} uses a command outside the exact argv policy")


def validate_source(source: str | Path, *, root: Path = CAMELOT_HOME) -> dict[str, Any]:
    source_path = _within(Path(source) if Path(source).is_absolute() else root / source, root)
    contract = _load_json(source_path / "forge.json")
    if contract.get("protocolVersion") != PROTOCOL_VERSION:
        raise ForgeLawError(f"protocolVersion must be {PROTOCOL_VERSION}")
    title = contract.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise ForgeLawError("title must be between 1 and 160 characters")
    if contract.get("targetRoot", ".") != ".":
        raise ForgeLawError("forge-law/v1 only permits the Camelot repository target root")
    operations = contract.get("operations")
    if not isinstance(operations, list) or not 1 <= len(operations) <= 128:
        raise ForgeLawError("operations must contain between 1 and 128 entries")
    seen: set[str] = set()
    inline_bytes = 0
    normalized: list[dict[str, Any]] = []
    for raw in operations:
        if not isinstance(raw, dict):
            raise ForgeLawError("each operation must be an object")
        operation = dict(raw)
        operation_id = operation.get("id")
        if not isinstance(operation_id, str) or not _ID.fullmatch(operation_id) or operation_id in seen:
            raise ForgeLawError(f"invalid or duplicate operation id: {operation_id}")
        seen.add(operation_id)
        operation_type = operation.get("type")
        if operation_type not in OPERATION_TYPES:
            raise ForgeLawError(f"unsupported operation type: {operation_type}")
        dependencies = operation.get("dependsOn", [])
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            raise ForgeLawError(f"operation {operation_id} has invalid dependencies")
        operation["dependsOn"] = dependencies
        if operation_type == "write_file":
            relative, _ = _relative_target(operation.get("path"), root)
            content = operation.get("content")
            if not isinstance(content, str):
                raise ForgeLawError(f"operation {operation_id} requires string content")
            encoded = content.encode("utf-8")
            inline_bytes += len(encoded)
            if len(encoded) > 1_048_576 or inline_bytes > 5_242_880:
                raise ForgeLawError("inline write content exceeds Forge Law limits")
            if _SECRET.search(content):
                raise ForgeLawError(f"operation {operation_id} appears to contain a secret")
            operation["path"] = relative
        elif operation_type in {"run_check", "build"}:
            _validate_argv(operation)
            cwd = operation.get("cwd", ".")
            if not isinstance(cwd, str):
                raise ForgeLawError(f"operation {operation_id} cwd must be a string")
            operation["cwd"] = _within(root / cwd, root).relative_to(root).as_posix() or "."
            timeout = operation.get("timeoutSeconds", 300)
            if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 900:
                raise ForgeLawError(f"operation {operation_id} timeout must be between 1 and 900 seconds")
            operation["timeoutSeconds"] = timeout
        else:
            service = operation.get("service")
            if not isinstance(service, str) or not _ID.fullmatch(service):
                raise ForgeLawError(f"operation {operation_id} requires a normalized service id")
        normalized.append(operation)
    ordered = _topological_operations(normalized)
    verification = contract.get("verification", [])
    if not isinstance(verification, list) or not verification or not all(item in seen for item in verification):
        raise ForgeLawError("verification must reference one or more declared operation ids")
    risk = contract.get("risk", {})
    if not isinstance(risk, dict):
        raise ForgeLawError("risk must be an object")
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "title": title.strip(),
        "targetRoot": ".",
        "operations": ordered,
        "verification": verification,
        "risk": {
            "level": risk.get("level", "medium"),
            "requiresOperatorApproval": True,
            "serviceRestartApproval": "separate",
        },
        "sourceDir": source_path.relative_to(root).as_posix(),
        "sourceHashes": _source_hashes(source_path),
    }


def _matching_verification(hashes: dict[str, str], ledger: Path) -> dict[str, Any]:
    if not ledger.is_file():
        raise ForgeLawError("verification ledger is unavailable")
    from control_plane.infra.ledger_sync import compute_entry_hash

    match: dict[str, Any] | None = None
    previous_hash: str | None = None
    for line_number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ForgeLawError(f"verification ledger contains invalid JSON at line {line_number}") from exc
        if not isinstance(entry, dict):
            raise ForgeLawError(f"verification ledger entry {line_number} is not an object")
        if entry.get("parent_hash") != previous_hash or entry.get("entry_hash") != compute_entry_hash(entry):
            raise ForgeLawError(f"verification ledger integrity failed at line {line_number}")
        previous_hash = entry.get("entry_hash")
        results = entry.get("results") if isinstance(entry, dict) else None
        if match is None and (
            entry.get("success") is True
            and isinstance(results, dict)
            and results.get("event_type") == "forge_upgrade_verified"
            and results.get("source_hashes") == hashes
        ):
            match = {
                "runId": entry.get("run_id"),
                "entryId": entry.get("entry_id"),
                "entryHash": entry.get("entry_hash"),
                "timestampUtc": entry.get("timestamp_utc"),
            }
    if match is None:
        raise ForgeLawError("no successful forge_upgrade_verified ledger entry matches the source hashes")
    return match


def _state_path(cartridge_id: str, store: Path) -> Path:
    return store / "state" / f"{cartridge_id}.json"


def _cartridge_path(cartridge_id: str, store: Path) -> Path:
    if not re.fullmatch(r"forge-[0-9a-f]{16}", cartridge_id):
        raise ForgeLawError("invalid cartridge id")
    return store / "cartridges" / f"{cartridge_id}.json"


def _render_markdown(cartridge: dict[str, Any]) -> str:
    lines = [
        f"# {cartridge['title']}",
        "",
        f"- Cartridge: `{cartridge['id']}`",
        f"- Protocol: `{cartridge['protocolVersion']}`",
        f"- Digest: `{cartridge['digest']}`",
        f"- Source: `{cartridge['sourceDir']}`",
        "- Execution: Iron Gate approval required",
        "",
        "## Kinetic DAG",
        "",
    ]
    for operation in cartridge["operations"]:
        dependencies = ", ".join(operation.get("dependsOn", [])) or "none"
        lines.append(f"- `{operation['id']}`: `{operation['type']}` (depends on: {dependencies})")
    lines.extend(["", "## Verification", ""])
    lines.extend(f"- `{operation_id}`" for operation_id in cartridge["verification"])
    lines.extend(["", "This view is generated from the signed JSON contract; it is not executable Markdown.", ""])
    return "\n".join(lines)


def _write_state(cartridge_id: str, state: str, store: Path, **details: Any) -> dict[str, Any]:
    if state not in CARTRIDGE_STATES:
        raise ForgeLawError(f"invalid cartridge state: {state}")
    path = _state_path(cartridge_id, store)
    previous = _load_json(path) if path.exists() else {}
    history = previous.get("history", []) if isinstance(previous.get("history"), list) else []
    event = {"state": state, "timestampUtc": _utcnow(), **details}
    value = {"cartridgeId": cartridge_id, "state": state, "updatedAt": event["timestampUtc"], "history": [*history, event][-100:]}
    _atomic_json(path, value)
    return value


def crystallize_source(
    source: str | Path,
    *,
    root: Path = CAMELOT_HOME,
    store: Path = DEFAULT_STORE,
    ledger: Path = DEFAULT_LEDGER,
) -> dict[str, Any]:
    contract = validate_source(source, root=root)
    evidence = _matching_verification(contract["sourceHashes"], ledger)
    payload = {**contract, "verificationEvidence": evidence}
    digest = _digest_bytes(_canonical(payload))
    cartridge = {"id": f"forge-{digest[:16]}", "digest": digest, "createdAt": _utcnow(), **payload}
    path = _cartridge_path(cartridge["id"], store)
    if path.exists():
        existing = _load_json(path)
        existing_payload = {key: value for key, value in existing.items() if key not in {"id", "digest", "createdAt"}}
        if existing.get("id") != cartridge["id"] or existing.get("digest") != digest or existing_payload != payload:
            raise ForgeLawError("immutable cartridge id collision")
        cartridge = existing
    else:
        _atomic_json(path, cartridge)
        markdown = store / "cartridges" / f"{cartridge['id']}.md"
        markdown.write_text(_render_markdown(cartridge), encoding="utf-8")
    state_path = _state_path(cartridge["id"], store)
    if not state_path.exists():
        state = _write_state(cartridge["id"], "validated", store, sourceHashes=contract["sourceHashes"])
    else:
        state = _load_json(state_path)
    return {**cartridge, "state": state.get("state", "drafted")}


def inspect_cartridge(cartridge_id: str, *, store: Path = DEFAULT_STORE) -> dict[str, Any]:
    cartridge = _load_json(_cartridge_path(cartridge_id, store))
    expected = cartridge.get("digest")
    payload = {key: value for key, value in cartridge.items() if key not in {"id", "digest", "createdAt"}}
    if not isinstance(expected, str) or not _DIGEST.fullmatch(expected) or _digest_bytes(_canonical(payload)) != expected:
        raise ForgeLawError("cartridge digest verification failed")
    state_path = _state_path(cartridge_id, store)
    state = _load_json(state_path) if state_path.exists() else {"state": "drafted", "history": []}
    return {**cartridge, "state": state.get("state"), "stateUpdatedAt": state.get("updatedAt"), "history": state.get("history", [])}


def list_cartridges(*, store: Path = DEFAULT_STORE) -> list[dict[str, Any]]:
    directory = store / "cartridges"
    if not directory.exists():
        return []
    values: list[dict[str, Any]] = []
    for path in sorted(directory.glob("forge-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            cartridge = inspect_cartridge(path.stem, store=store)
            values.append({
                "id": cartridge["id"],
                "title": cartridge["title"],
                "digest": cartridge["digest"],
                "state": cartridge["state"],
                "createdAt": cartridge["createdAt"],
                "sourceDir": cartridge["sourceDir"],
                "risk": cartridge["risk"],
                "operationCount": len(cartridge["operations"]),
            })
        except ForgeLawError:
            continue
    return values


def submit_cartridge(cartridge_id: str, *, store: Path = DEFAULT_STORE) -> dict[str, Any]:
    cartridge = inspect_cartridge(cartridge_id, store=store)
    state = _write_state(cartridge_id, "awaiting_approval", store, digest=cartridge["digest"])
    return {"cartridgeId": cartridge_id, "digest": cartridge["digest"], "state": state["state"], "command": f"//EXECUTE_PROMPT {cartridge_id}"}


def approval_binding(cartridge_id: str, *, store: Path = DEFAULT_STORE) -> dict[str, str]:
    cartridge = inspect_cartridge(cartridge_id, store=store)
    return {"cartridgeDigest": cartridge["digest"], "targetRoot": cartridge["targetRoot"]}


def _rollback(backups: list[dict[str, Any]], root: Path) -> None:
    for item in reversed(backups):
        target = _within(root / item["path"], root)
        if item["existed"]:
            backup = Path(item["backup"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
        elif target.exists():
            target.unlink()


def _run_operation(operation: dict[str, Any], root: Path) -> dict[str, Any]:
    cwd = _within(root / operation.get("cwd", "."), root)
    started = _utcnow()
    completed = subprocess.run(
        operation["argv"],
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=False,
        timeout=operation.get("timeoutSeconds", 300),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    result = {
        "id": operation["id"],
        "type": operation["type"],
        "startedAt": started,
        "completedAt": _utcnow(),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
    }
    if completed.returncode != 0:
        raise ForgeLawError(f"operation {operation['id']} failed with exit code {completed.returncode}: {json.dumps(result)}")
    return result


def execute_cartridge(
    cartridge_id: str,
    approval: dict[str, Any] | None,
    *,
    root: Path = CAMELOT_HOME,
    store: Path = DEFAULT_STORE,
) -> dict[str, Any]:
    cartridge = inspect_cartridge(cartridge_id, store=store)
    if not approval or approval.get("version") != 2:
        raise ForgeLawError("Forge execution requires an Iron Gate v2 approval grant")
    if approval.get("cartridge_digest") != cartridge["digest"] or approval.get("target_root") != cartridge["targetRoot"]:
        raise ForgeLawError("approval grant does not match the immutable cartridge")
    _write_state(cartridge_id, "approved", store, approvalId=approval.get("approval_id"), digest=cartridge["digest"])
    _write_state(cartridge_id, "executing", store, executor="lukas_omega")
    run_dir = store / "runs" / cartridge_id / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_dir = run_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    try:
        for operation in cartridge["operations"]:
            operation_type = operation["type"]
            if operation_type == "write_file":
                relative, target = _relative_target(operation["path"], root)
                backup = backup_dir / relative
                existed = target.exists()
                if existed:
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                backups.append({"path": relative, "existed": existed, "backup": str(backup)})
                target.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
                try:
                    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                        handle.write(operation["content"])
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temp_name, target)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
                results.append({"id": operation["id"], "type": operation_type, "path": relative, "sha256": _digest_bytes(target.read_bytes())})
            elif operation_type in {"run_check", "build"}:
                results.append(_run_operation(operation, root))
            else:
                raise ForgeLawError("service_restart requires a distinct restart approval and is disabled in the cartridge executor")
        completed = {"cartridgeId": cartridge_id, "digest": cartridge["digest"], "state": "verified", "results": results, "completedAt": _utcnow()}
        _atomic_json(run_dir / "receipt.json", completed)
        _write_state(cartridge_id, "verified", store, runReceipt=str((run_dir / "receipt.json").relative_to(root) if run_dir.is_relative_to(root) else run_dir))
        return completed
    except Exception as exc:
        _write_state(cartridge_id, "failed", store, error=str(exc)[:4000])
        _rollback(backups, root)
        _write_state(cartridge_id, "rolled_back", store, error=str(exc)[:4000])
        raise


def cartridge_id_from_command(command: str) -> str | None:
    match = re.fullmatch(r"\s*//EXECUTE_PROMPT\s+(forge-[0-9a-f]{16})\s*", command, re.IGNORECASE)
    return match.group(1).lower() if match else None
