# SPDX-License-Identifier: MIT

"""Lady Mnemosyne Cloudbrain custody audit.

Report-only audit for Camelot's memory surfaces: NotebookLM short-term brain,
long-term Cloudbrain, source/library operations, sync queue, and ledger mirrors.
No NotebookLM writes are performed here.
"""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNTIME_DIR = REPO_ROOT / "03_VAULT" / "runtime_state"
QUEUE_PATH = RUNTIME_DIR / "cloudbrain_sync_queue.jsonl"
REPORT_PATH = REPO_ROOT / "docs" / "reports" / "lady_mnemosyne_cloudbrain_audit.md"
ARTIFACT_PATH = RUNTIME_DIR / "lady_mnemosyne_cloudbrain_audit_latest.json"

LADY_MNEMOSYNE_OWNER = {
    "owner": "LADY_MNEMOSYNE",
    "persona": "Cloudbrain librarian and memory governor",
    "authority": "report_first",
    "mutation_policy": "No purge, merge, publication, or NotebookLM write without explicit operator command.",
}

SURFACE_ASSIGNMENTS = [
    {
        "surface": "NotebookLM canonical sync",
        "service": "notebooklm_sync",
        "primary_owner": "LADY_MNEMOSYNE",
        "supporting_knights": ["MERLIN_OMEGA", "SIR_SENTINEL"],
        "guardrail": "Prefer update existing note; queue failures; preserve content as source fallback only in sync path.",
    },
    {
        "surface": "NotebookLM library/source inventory",
        "service": "notebooklm_sources_list|add|delete",
        "primary_owner": "LADY_MNEMOSYNE",
        "supporting_knights": ["LADY_APIS", "SIR_MASON"],
        "guardrail": "List is safe; add/delete require explicit command and provenance.",
    },
    {
        "surface": "NotebookLM synthesis",
        "service": "notebooklm_synthesize",
        "primary_owner": "LADY_MNEMOSYNE",
        "supporting_knights": ["MERLIN_OMEGA"],
        "guardrail": "Read-only synthesis; cache responses; never treat synthesis as source of truth without provenance.",
    },
    {
        "surface": "Long-term Cloudbrain memory",
        "service": "cloudbrain_memory",
        "primary_owner": "LADY_MNEMOSYNE",
        "supporting_knights": ["LORD_ARCHIVIST", "SIR_SENTINEL"],
        "guardrail": "Local-first recall; high-privacy recall must not route remote.",
    },
    {
        "surface": "Cloudbrain sync queue",
        "service": "cloudbrain_queue",
        "primary_owner": "LADY_MNEMOSYNE",
        "supporting_knights": ["SIR_HEIMDALL", "SIR_CODEX"],
        "guardrail": "Flush retries are explicit; failed events remain queued with last_error and timestamp.",
    },
    {
        "surface": "Ledger mirrors",
        "service": "ledger_reconcile",
        "primary_owner": "LADY_MNEMOSYNE",
        "supporting_knights": ["SIR_SENTINEL", "LORD_ARCHIVIST"],
        "guardrail": "Do not hand-edit PROVENANCE_LEDGER.md; use ledger reconcile/update commands only.",
    },
]


def _load_bridge() -> Any | None:
    bridge_path = REPO_ROOT / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
    if not bridge_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("camelot_notebooklm_bridge_audit", bridge_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_queue() -> list[dict[str, Any]]:
    if not QUEUE_PATH.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in QUEUE_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            events.append({"event_type": "decode_error", "error": str(exc), "raw": line[:500]})
    return events


def _classify_queue_event(event: dict[str, Any]) -> dict[str, Any]:
    error = str(event.get("last_error") or event.get("error") or "")
    lowered = error.lower()
    if "cyk0xb" in lowered or "null result data" in lowered:
        classification = "notebooklm_rpc_null_result"
        recommendation = "Retry after NotebookLM auth refresh; if note create fails again, preserve snapshot as text source."
    elif "auth" in lowered or "login" in lowered or "credential" in lowered:
        classification = "notebooklm_auth"
        recommendation = "Run notebooklm login in an interactive terminal and retry queue flush."
    elif "timeout" in lowered:
        classification = "notebooklm_timeout"
        recommendation = "Retry with a smaller sync summary or after NotebookLM service latency clears."
    elif error:
        classification = "cloudbrain_sync_failure"
        recommendation = "Inspect event payload and retry one event with cloudbrain queue flush --limit 1."
    else:
        classification = "queued_without_error"
        recommendation = "Flush when ready; no error recorded."
    return {
        "event_type": event.get("event_type"),
        "command": event.get("command"),
        "queued_utc": event.get("queued_utc"),
        "classification": classification,
        "recommendation": recommendation,
        "error": error,
    }


def _auth_status(bridge: Any | None) -> dict[str, Any]:
    if bridge is None or not hasattr(bridge, "session_age_check"):
        return {"status": "UNKNOWN", "message": "notebooklm_bridge.py unavailable or lacks session_age_check"}
    try:
        status = bridge.session_age_check()
    except Exception as exc:  # pragma: no cover - environment-dependent
        return {"status": "ERROR", "message": f"{type(exc).__name__}: {exc}"}
    if status.get("critical"):
        state = "CRITICAL"
    elif status.get("warn"):
        state = "WARN"
    elif status.get("exists"):
        state = "READY"
    else:
        state = "MISSING"
    return {"status": state, **status}


def _brain_roles(bridge: Any | None) -> dict[str, Any]:
    return {
        "short_term_working_memory": {
            "service": "NotebookLM",
            "owner": "LADY_MNEMOSYNE",
            "notebook_id": getattr(bridge, "CANONICAL_NOTEBOOK_ID", None),
            "notebook_title": getattr(bridge, "CANONICAL_NOTEBOOK_TITLE", None),
            "config_env": "CAMELOT_LIVING_NOTEBOOK_URL",
        },
        "long_term_cloudbrain": {
            "service": "Open Notebook/Appwrite via Excalibur bridge",
            "owner": "LADY_MNEMOSYNE",
            "config_env": ["CAMELOT_EXCALIBUR_BRIDGE_URL", "CAMELOT_EXCALIBUR_HEALTH_URL"],
        },
        "deprecated": {
            "CAMELOT_CLOUDBRAIN_URL": os.getenv("CAMELOT_CLOUDBRAIN_URL") or None,
            "guidance": "Use CAMELOT_LIVING_NOTEBOOK_URL for NotebookLM and CAMELOT_EXCALIBUR_* for long-term brain.",
        },
    }


def _compute_findings(auth: dict[str, Any], queue: list[dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    if auth.get("status") in {"CRITICAL", "MISSING", "ERROR"}:
        findings.append({
            "severity": "P0",
            "title": "NotebookLM auth is not ready",
            "detail": str(auth.get("message") or auth.get("status")),
        })
    elif auth.get("status") == "WARN":
        findings.append({
            "severity": "P1",
            "title": "NotebookLM auth is aging",
            "detail": str(auth.get("message")),
        })

    classified = [_classify_queue_event(event) for event in queue]
    rpc_null = [item for item in classified if item["classification"] == "notebooklm_rpc_null_result"]
    if rpc_null:
        findings.append({
            "severity": "P1",
            "title": "NotebookLM RPC returned null result data",
            "detail": "CREATE_NOTE/update path should be retried after auth refresh and guarded with source fallback.",
        })
    if queue:
        findings.append({
            "severity": "P1",
            "title": "Cloudbrain queue has pending events",
            "detail": f"{len(queue)} event(s) pending; Lady Mnemosyne owns flush triage.",
        })

    state = "MNEMOSYNE_READY" if not findings else "MNEMOSYNE_TRIAGE_REQUIRED"
    if any(item["severity"] == "P0" for item in findings):
        state = "MNEMOSYNE_BLOCKED"
    return state, findings


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Lady Mnemosyne Cloudbrain Audit",
        "",
        f"- Generated UTC: {payload['generated_utc']}",
        f"- State: {payload['state']}",
        f"- Owner: {payload['owner']['owner']}",
        f"- Queue Pending: {payload['queue']['pending']}",
        f"- NotebookLM Auth: {payload['auth'].get('status')}",
        "",
        "## Findings",
    ]
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"- {item['severity']} | {item['title']}: {item['detail']}")
    else:
        lines.append("- No blocking findings detected by report-only audit.")
    lines.extend(["", "## Surface Ownership"])
    for item in payload["assignments"]:
        lines.append(f"- {item['surface']} -> {item['primary_owner']} ({item['service']})")
    lines.extend(["", "## Queue Events"])
    if payload["queue"]["classified_events"]:
        for item in payload["queue"]["classified_events"]:
            lines.append(f"- {item['classification']} | {item.get('command')}: {item['recommendation']}")
    else:
        lines.append("- Queue empty.")
    lines.extend(["", "## Guardrail"])
    lines.append(payload["owner"]["mutation_policy"])
    lines.append("")
    return "\n".join(lines)


def run_lady_mnemosyne_cloudbrain_audit(*, write: bool = True) -> dict[str, Any]:
    bridge = _load_bridge()
    queue = _read_queue()
    auth = _auth_status(bridge)
    state, findings = _compute_findings(auth, queue)
    payload: dict[str, Any] = {
        "schema": "camelot.lady-mnemosyne-cloudbrain-audit/v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "owner": LADY_MNEMOSYNE_OWNER,
        "auth": auth,
        "brain_roles": _brain_roles(bridge),
        "assignments": SURFACE_ASSIGNMENTS,
        "queue": {
            "path": str(QUEUE_PATH),
            "exists": QUEUE_PATH.exists(),
            "pending": len(queue),
            "classified_events": [_classify_queue_event(event) for event in queue[-10:]],
        },
        "findings": findings,
        "verification": [
            "python -m control_plane.camelot_cli cloudbrain mnemosyne-audit --json",
            "python -m control_plane.camelot_cli cloudbrain queue status",
            "python -m control_plane.camelot_cli cloudbrain queue flush --limit 1",
        ],
    }
    if write:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(render_markdown(payload), encoding="utf-8")
        payload["artifact_path"] = str(ARTIFACT_PATH)
        payload["report_path"] = str(REPORT_PATH)
    return payload


if __name__ == "__main__":
    print(json.dumps(run_lady_mnemosyne_cloudbrain_audit(), indent=2))
