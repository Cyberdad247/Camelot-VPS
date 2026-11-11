# SPDX-License-Identifier: MIT

"""Frontier chat node registry and break-glass support sessions.

This module intentionally stores only token hashes for support access. The
clear token is returned once to the local operator when a session is activated.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNTIME_STATE = REPO_ROOT / "03_VAULT" / "runtime_state"
FRONTIER_STATE_PATH = RUNTIME_STATE / "frontier_nodes_latest.json"
VERIFICATION_LEDGER = REPO_ROOT / "03_VAULT" / "Missions" / "verification_ledger.jsonl"

DEFAULT_NODES = [
    {
        "node_id": "chatgpt_frontier",
        "provider": "openai",
        "surface": "ChatGPT / OpenAI API",
        "role": "strategic_planner",
        "permissions": ["status", "route", "cloudbrain_query", "ledger_append"],
        "memory_tiers": ["flash", "short"],
        "status": "available",
    },
    {
        "node_id": "claude_frontier",
        "provider": "anthropic",
        "surface": "Claude / Claude Code",
        "role": "architecture_and_review",
        "permissions": ["status", "route", "code_review", "ledger_append"],
        "memory_tiers": ["flash", "short"],
        "status": "available",
    },
    {
        "node_id": "gemini_frontier",
        "provider": "google",
        "surface": "Gemini / Gemini CLI",
        "role": "long_context_research",
        "permissions": ["status", "route", "cloudbrain_query", "research"],
        "memory_tiers": ["flash", "short"],
        "status": "available",
    },
    {
        "node_id": "codex_frontier",
        "provider": "openai",
        "surface": "Codex",
        "role": "implementation_node",
        "permissions": ["status", "route", "dashboard", "ledger_append"],
        "memory_tiers": ["flash", "short"],
        "status": "available",
    },
    {
        "node_id": "local_private_frontier",
        "provider": "local",
        "surface": "Local Qwen / Ollama",
        "role": "private_fallback",
        "permissions": ["status", "route", "local_only"],
        "memory_tiers": ["flash", "long"],
        "status": "available",
    },
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _read_state() -> dict[str, Any]:
    if FRONTIER_STATE_PATH.exists():
        try:
            state = json.loads(FRONTIER_STATE_PATH.read_text(encoding="utf-8", errors="replace"))
            if isinstance(state, dict):
                return _normalize_state(state)
        except json.JSONDecodeError:
            pass
    return _normalize_state({})


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    nodes = state.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        nodes = DEFAULT_NODES
    support = state.get("support")
    if not isinstance(support, dict):
        support = {"status": "disabled", "active_session": None, "sessions": []}
    support.setdefault("status", "disabled")
    support.setdefault("active_session", None)
    support.setdefault("sessions", [])
    events = state.get("events")
    if not isinstance(events, list):
        events = []
    return {
        "schema": "camelot.frontier_nodes.v1",
        "generated_utc": state.get("generated_utc") or iso_now(),
        "nodes": nodes,
        "support": support,
        "events": events[-100:],
    }


def _write_state(state: dict[str, Any]) -> dict[str, Any]:
    FRONTIER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["generated_utc"] = iso_now()
    FRONTIER_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return state


def _ledger(event: dict[str, Any], *, provenance: bool = False) -> None:
    entry = {
        "timestamp_utc": iso_now(),
        "system": "frontier_nodes",
        **event,
    }
    VERIFICATION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with VERIFICATION_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    if provenance:
        from control_plane.ledger_sync import append_provenance_entry

        summary = str(event.get("summary") or event.get("action") or "frontier node event")
        append_provenance_entry(
            title="Frontier Portal",
            actor="CAMELOT_OS",
            scope=[summary],
            verification=["frontier_nodes._ledger"],
            tag="frontier_nodes",
        )


def public_state() -> dict[str, Any]:
    state = _read_state()
    support = dict(state["support"])
    active = support.get("active_session")
    if active and active.get("expires_utc"):
        try:
            expired = datetime.fromisoformat(active["expires_utc"]) <= utc_now()
        except ValueError:
            expired = True
        if expired:
            active["status"] = "expired"
            support["status"] = "expired"
            support["active_session"] = active
            state["support"] = support
            _write_state(state)
    return _sanitize_state(state)


def _sanitize_state(state: dict[str, Any]) -> dict[str, Any]:
    clean = json.loads(json.dumps(state))
    for session in clean.get("support", {}).get("sessions", []):
        session.pop("token_hash", None)
    active = clean.get("support", {}).get("active_session")
    if isinstance(active, dict):
        active.pop("token_hash", None)
    clean["artifact_path"] = str(FRONTIER_STATE_PATH.relative_to(REPO_ROOT))
    return clean


def register_node(payload: dict[str, Any]) -> dict[str, Any]:
    state = _read_state()
    node_id = str(payload.get("node_id") or "").strip()
    if not node_id:
        raise ValueError("node_id is required")
    node = {
        "node_id": node_id,
        "provider": str(payload.get("provider") or "unknown"),
        "surface": str(payload.get("surface") or node_id),
        "role": str(payload.get("role") or "frontier_node"),
        "permissions": list(payload.get("permissions") or ["status", "route"]),
        "memory_tiers": list(payload.get("memory_tiers") or ["flash"]),
        "status": str(payload.get("status") or "online"),
        "last_seen_utc": iso_now(),
    }
    state["nodes"] = [existing for existing in state["nodes"] if existing.get("node_id") != node_id]
    state["nodes"].append(node)
    state["events"].append({"action": "node_registered", "node_id": node_id, "timestamp_utc": iso_now()})
    _write_state(state)
    _ledger({"action": "node_registered", "node_id": node_id, "summary": f"Registered frontier node {node_id}"})
    return _sanitize_state(state)


def activate_support_session(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    state = _read_state()
    duration_minutes = int(payload.get("duration_minutes") or 120)
    duration_minutes = max(5, min(duration_minutes, 24 * 60))
    reason = str(payload.get("reason") or "operator activated support")
    session_id = f"support_{utc_now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"
    token = secrets.token_urlsafe(24)
    expires = utc_now() + timedelta(minutes=duration_minutes)
    session = {
        "session_id": session_id,
        "status": "active",
        "created_utc": iso_now(),
        "expires_utc": expires.isoformat(),
        "duration_minutes": duration_minutes,
        "reason": reason,
        "token_hash": _token_hash(token),
        "portal_path": f"/support/{session_id}",
        "permissions": ["status", "cloudbrain_query", "ledger_append", "route"],
    }
    state["support"]["status"] = "active"
    state["support"]["active_session"] = session
    state["support"]["sessions"].append(session)
    state["events"].append({"action": "support_activated", "session_id": session_id, "timestamp_utc": iso_now()})
    _write_state(state)
    _ledger(
        {
            "action": "support_activated",
            "session_id": session_id,
            "summary": f"Break-glass support activated for {duration_minutes} minutes",
        },
        provenance=True,
    )
    clean = _sanitize_state(state)
    clean["one_time_token"] = token
    clean["support_url"] = session["portal_path"]
    return clean


def revoke_support_session(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    state = _read_state()
    requested = str(payload.get("session_id") or "").strip()
    active = state["support"].get("active_session")
    session_id = requested or (active or {}).get("session_id")
    if not session_id:
        state["support"]["status"] = "disabled"
        state["support"]["active_session"] = None
        return _sanitize_state(_write_state(state))

    for session in state["support"]["sessions"]:
        if session.get("session_id") == session_id:
            session["status"] = "revoked"
            session["revoked_utc"] = iso_now()
    if active and active.get("session_id") == session_id:
        active["status"] = "revoked"
        active["revoked_utc"] = iso_now()
    state["support"]["status"] = "disabled"
    state["support"]["active_session"] = None
    state["events"].append({"action": "support_revoked", "session_id": session_id, "timestamp_utc": iso_now()})
    _write_state(state)
    _ledger(
        {
            "action": "support_revoked",
            "session_id": session_id,
            "summary": f"Break-glass support revoked for {session_id}",
        },
        provenance=True,
    )
    return _sanitize_state(state)


def validate_support_session(session_id: str, token: str) -> dict[str, Any]:
    state = _read_state()
    active = state["support"].get("active_session") or {}
    if active.get("session_id") != session_id or active.get("status") != "active":
        return {"valid": False, "reason": "session is not active"}
    if active.get("token_hash") != _token_hash(token):
        return {"valid": False, "reason": "token mismatch"}
    try:
        if datetime.fromisoformat(active["expires_utc"]) <= utc_now():
            return {"valid": False, "reason": "session expired"}
    except Exception:
        return {"valid": False, "reason": "invalid expiry"}
    _ledger({"action": "support_validated", "session_id": session_id, "summary": "Support portal token validated"})
    return {
        "valid": True,
        "session_id": session_id,
        "expires_utc": active.get("expires_utc"),
        "permissions": active.get("permissions", []),
    }
