# SPDX-License-Identifier: MIT

"""Repository-side ledger update and sync utilities for Camelot-OS."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
LEDGER_PATH = REPO_ROOT / "PROVENANCE_LEDGER.md"
MIRROR_LEDGER_PATHS = [
    REPO_ROOT / "03_VAULT" / "PROVENANCE_LEDGER.md",
    REPO_ROOT / "03_VAULT" / "training" / "configs" / "PROVENANCE_LEDGER.md",
    REPO_ROOT / "03_VAULT" / "knowledge_vault" / "PROVENANCE_LEDGER.md",
    REPO_ROOT / "control_plane" / "PROVENANCE_LEDGER.md",
    REPO_ROOT / "docs" / "PROVENANCE_LEDGER.md",
    REPO_ROOT / "docs" / "architecture" / "PROVENANCE_LEDGER.md",
]

VERIFICATION_LEDGER_PATH = REPO_ROOT / "03_VAULT" / "Missions" / "verification_ledger.jsonl"
CP_VERIFICATION_LEDGER_PATH = REPO_ROOT / "control_plane" / "03_VAULT" / "Missions" / "verification_ledger.jsonl"


def compute_entry_hash(entry: dict[str, Any]) -> str:
    """SHA256 over the entry's payload (everything except `entry_hash`).

    Single source of truth for the verification-ledger chain algorithm.

    MUST stay byte-for-byte identical to the inline algorithm previously
    embedded in:
      - ``control_plane.system_triage._verification_ledger_integrity``
        (the rapid triage validator)
      - ``scripts.repair_verification_ledger_chain.compute_entry_hash``
        (the deterministic atomic repair tool)

    If you change one, change all callers by re-importing this function.
    """
    payload = {key: value for key, value in entry.items() if key != "entry_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _read_bifrost_token() -> str | None:
    token_path = Path.home() / ".camelot" / "bifrost.token"
    try:
        token = token_path.read_text(encoding="ascii").strip()
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        return None
    return token or None


def ledger_status() -> dict[str, Any]:
    exists = LEDGER_PATH.exists()
    size = LEDGER_PATH.stat().st_size if exists else 0
    tail = ""
    mirrors = []
    if exists:
        root_text = LEDGER_PATH.read_text(encoding="utf-8", errors="replace")
        tail = "\n".join(root_text.splitlines()[-12:])
        mirrors = [
            {
                "path": str(path),
                "exists": path.exists(),
                "aligned": path.exists() and path.read_text(encoding="utf-8", errors="replace") == root_text,
            }
            for path in MIRROR_LEDGER_PATHS
        ]
    verification_status = verification_ledger_status()
    return {
        "ledger_path": str(LEDGER_PATH),
        "exists": exists,
        "size_bytes": size,
        "tail": tail,
        "mirrors": mirrors,
        "mirrors_aligned": bool(mirrors) and all(item["aligned"] for item in mirrors),
        "verification_ledger": verification_status,
    }


def verification_ledger_status() -> dict[str, Any]:
    """Inspect integrity and counts across all verification ledgers."""
    from scripts.repair_verification_ledger_chain import _walk

    results = {}
    for name, path in [("root", VERIFICATION_LEDGER_PATH), ("control_plane", CP_VERIFICATION_LEDGER_PATH)]:
        if not path.exists():
            results[name] = {"path": str(path), "exists": False, "entries": 0, "valid": False, "error": "file_not_found"}
        else:
            cnt, err, _ = _walk(path)
            results[name] = {
                "path": str(path),
                "exists": True,
                "entries": cnt,
                "valid": err is None,
                "error": err,
            }
    aligned = (
        results.get("root", {}).get("exists")
        and results.get("control_plane", {}).get("exists")
        and results["root"]["entries"] == results["control_plane"]["entries"]
        and results["root"]["valid"]
        and results["control_plane"]["valid"]
    )
    results["ledgers_aligned"] = bool(aligned)
    return results


def append_verification_entry(
    *,
    run_id: str,
    operator: str,
    command: str,
    results: dict[str, Any],
    success: bool = True,
    timestamp_utc: str | None = None,
    target_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Append a cryptographically chained entry to verification_ledger.jsonl and its mirrors."""
    if target_paths is None:
        target_paths = [VERIFICATION_LEDGER_PATH, CP_VERIFICATION_LEDGER_PATH]

    # Find the canonical ledger (the one with the longest valid chain)
    entries: list[dict[str, Any]] = []
    for p in target_paths:
        if p.exists():
            lines = []
            for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if l.strip():
                    try:
                        lines.append(json.loads(l))
                    except json.JSONDecodeError:
                        pass
            if len(lines) > len(entries):
                entries = lines

    last_hash = entries[-1].get("entry_hash") if entries else None
    next_id = len(entries) + 1
    ts = timestamp_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "run_id": run_id,
        "timestamp_utc": ts,
        "operator": operator,
        "command": command,
        "results": results,
        "success": success,
        "entry_id": next_id,
        "parent_hash": last_hash,
    }
    entry["entry_hash"] = compute_entry_hash(entry)

    entry_line = json.dumps(entry) + "\n"
    for path in target_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 0:
            with path.open("rb") as reader:
                reader.seek(-1, 2)
                if reader.read(1) != b"\n":
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write("\n")
        with path.open("a", encoding="utf-8") as f:
            f.write(entry_line)

    return entry


def reconcile_verification_ledgers() -> dict[str, Any]:
    """Ensure root and control_plane verification ledgers are aligned and cryptographically valid."""
    from scripts.repair_verification_ledger_chain import repair, _walk

    paths = [VERIFICATION_LEDGER_PATH, CP_VERIFICATION_LEDGER_PATH]
    best_path = None
    best_count = -1

    # First check if any is already clean and long
    for p in paths:
        if p.exists():
            cnt, err, _ = _walk(p)
            if err is None and cnt > best_count:
                best_count = cnt
                best_path = p

    # If neither was clean, repair them
    if best_path is None:
        for p in paths:
            if p.exists():
                res = repair(p, dry_run=False)
                if res.get("post_validate_error") is None and res.get("entries", 0) > best_count:
                    best_count = res["entries"]
                    best_path = p

    if best_path is None:
        return {"status": "NO_VALID_LEDGER", "count": 0}

    canonical_content = best_path.read_bytes()
    updated = []
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or p.read_bytes() != canonical_content:
            p.write_bytes(canonical_content)
            updated.append(str(p))

    return {
        "status": "ALIGNED",
        "canonical_source": str(best_path),
        "entries": best_count,
        "synced_mirrors": updated,
    }


def append_provenance_entry(*, title: str, actor: str, scope: list[str], verification: list[str], tag: str) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y-%m-%d")
    block_lines = [
        "---",
        f"## [{timestamp}] {title}",
        f"- **Actor**: {actor}",
        "- **Scope**:",
    ]
    block_lines.extend(f"  - {item}" for item in scope)
    block_lines.append("- **Verification performed**:")
    block_lines.extend(f"  - `{item}`" for item in verification)
    block_lines.append(f"- **Tag**: {tag}")
    block = "\n".join(block_lines) + "\n"
    with LEDGER_PATH.open("a", encoding="utf-8") as handle:
        if LEDGER_PATH.stat().st_size > 0:
            with LEDGER_PATH.open("rb") as reader:
                reader.seek(-1, 2)
                if reader.read(1) != b"\n":
                    handle.write("\n")
        handle.write(block)
    return {
        "status": "UPDATED",
        "ledger_path": str(LEDGER_PATH),
        "title": title,
        "tag": tag,
    }


def reconcile_ledger_mirrors() -> dict[str, Any]:
    """Copy the root provenance ledger to tracked mirror locations."""
    if not LEDGER_PATH.exists():
        return {"status": "MISSING_ROOT_LEDGER", "ledger_path": str(LEDGER_PATH), "mirrors": []}

    root_text = LEDGER_PATH.read_text(encoding="utf-8", errors="replace")
    mirrors: list[dict[str, Any]] = []
    for path in MIRROR_LEDGER_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        before = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
        if before != root_text:
            path.write_text(root_text, encoding="utf-8")
            action = "updated" if before is not None else "created"
        else:
            action = "already_aligned"
        mirrors.append({"path": str(path), "action": action, "aligned": True})

    return {
        "status": "RECONCILED",
        "ledger_path": str(LEDGER_PATH),
        "mirrors": mirrors,
        "mirrors_aligned": True,
    }


def reconcile_all_ledgers() -> dict[str, Any]:
    """Master reconciliation of both Provenance Ledgers and Verification Ledgers."""
    prov_res = reconcile_ledger_mirrors()
    verif_res = reconcile_verification_ledgers()
    return {
        "status": "ALL_LEDGERS_RECONCILED",
        "provenance": prov_res,
        "verification": verif_res,
    }


async def sync_to_kernel(intent: str, *, kernel_url: str = "http://127.0.0.1:8001") -> dict[str, Any]:
    health_url = f"{kernel_url.rstrip('/')}/health"
    dispatch_url = f"{kernel_url.rstrip('/')}/agent/dispatch"
    token = _read_bifrost_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["x-camelot-token"] = token
    async with httpx.AsyncClient(timeout=10.0) as client:
        health = await client.get(health_url)
        health.raise_for_status()
        result = await client.post(
            dispatch_url,
            headers=headers,
            json={"intent": intent, "agent_id": "MERLIN", "execution_target": "ledger_sync"},
        )
        result.raise_for_status()
        return {
            "status": "SYNCED",
            "kernel_url": kernel_url,
            "dispatch_url": dispatch_url,
            "auth": "token" if token else "missing",
            "health": health.json(),
            "result": result.json(),
        }


if __name__ == "__main__":
    print("[LEDGER_SYNC] Reconciling all ledgers across Camelot-OS...")
    reconciled = reconcile_all_ledgers()
    print(json.dumps(reconciled, indent=2))
    print("\n[LEDGER_SYNC] Current Status:")
    print(json.dumps(ledger_status(), indent=2))
