# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Supabase Realtime Bridge — pg_notify Escalation Queue
======================================================
Connects Lukas_Omega to the Supabase escalation queue for SARDA status
propagation and HITL approval requests. Uses pg_notify for sub-2s latency.

Transport: Tailscale mesh (when available) or direct HTTPS.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SARDA_CHANNEL = "sarda_events"
ESCALATION_TABLE = "sarda_escalations"


@dataclass
class EscalationEvent:
    """An event pushed to the Supabase escalation queue."""
    event_type: str  # sarda_start, sarda_complete, hitl_request, critique_fail
    task_id: str
    source_agent: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    resolved: bool = False

    def to_row(self) -> dict:
        return {
            "event_type": self.event_type,
            "task_id": self.task_id,
            "source_agent": self.source_agent,
            "payload": json.dumps(self.payload),
            "timestamp": self.timestamp,
            "resolved": self.resolved,
        }


# ---------------------------------------------------------------------------
# SQL Migration (run once via Supabase MCP or dashboard)
# ---------------------------------------------------------------------------

MIGRATION_SQL = """
-- SARDA Escalation Queue
CREATE TABLE IF NOT EXISTS sarda_escalations (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    task_id TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE
);

-- pg_notify trigger for realtime push
CREATE OR REPLACE FUNCTION notify_sarda_event()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('sarda_events', row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sarda_event_trigger ON sarda_escalations;
CREATE TRIGGER sarda_event_trigger
    AFTER INSERT ON sarda_escalations
    FOR EACH ROW
    EXECUTE FUNCTION notify_sarda_event();

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_sarda_task ON sarda_escalations(task_id);
CREATE INDEX IF NOT EXISTS idx_sarda_unresolved ON sarda_escalations(resolved) WHERE resolved = FALSE;
"""


# ---------------------------------------------------------------------------
# Bridge Client
# ---------------------------------------------------------------------------

class SupabaseBridge:
    """Supabase Realtime Bridge for SARDA escalation events.

    Pushes events to the sarda_escalations table, which triggers pg_notify
    for sub-2s delivery to any listening client (dashboard, mobile, etc).
    """

    def __init__(
        self,
        url: str = SUPABASE_URL,
        key: str = SUPABASE_KEY,
    ):
        self.url = url.rstrip("/")
        self.key = key
        self._configured = bool(url and key)

    @property
    def configured(self) -> bool:
        return self._configured

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def push_event(self, event: EscalationEvent) -> dict:
        """Insert an escalation event into Supabase (triggers pg_notify)."""
        if not self._configured:
            return {"status": "skipped", "reason": "Supabase not configured"}

        if not HAS_HTTPX:
            return {"status": "skipped", "reason": "httpx not installed"}

        endpoint = f"{self.url}/rest/v1/{ESCALATION_TABLE}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                endpoint,
                json=event.to_row(),
                headers=self._headers(),
            )
            if resp.status_code in (200, 201):
                return {"status": "pushed", "data": resp.json()}
            return {
                "status": "error",
                "code": resp.status_code,
                "body": resp.text,
            }

    async def get_unresolved(self, limit: int = 20) -> list[dict]:
        """Fetch unresolved escalation events."""
        if not self._configured or not HAS_HTTPX:
            return []

        endpoint = (
            f"{self.url}/rest/v1/{ESCALATION_TABLE}"
            f"?resolved=eq.false&order=timestamp.desc&limit={limit}"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(endpoint, headers=self._headers())
            if resp.status_code == 200:
                return resp.json()
            return []

    async def resolve_event(self, event_id: int) -> bool:
        """Mark an escalation event as resolved."""
        if not self._configured or not HAS_HTTPX:
            return False

        endpoint = f"{self.url}/rest/v1/{ESCALATION_TABLE}?id=eq.{event_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                endpoint,
                json={"resolved": True},
                headers=self._headers(),
            )
            return resp.status_code in (200, 204)

    def get_migration_sql(self) -> str:
        """Return the SQL migration for creating the escalation table."""
        return MIGRATION_SQL


# ---------------------------------------------------------------------------
# Convenience functions for SARDA integration
# ---------------------------------------------------------------------------

async def notify_sarda_start(bridge: SupabaseBridge, task_id: str, intent: str):
    """Notify that a SARDA cycle has begun."""
    return await bridge.push_event(EscalationEvent(
        event_type="sarda_start",
        task_id=task_id,
        source_agent="sarda_engine",
        payload={"intent": intent},
    ))


async def notify_sarda_complete(
    bridge: SupabaseBridge, task_id: str, passed: bool, confidence: float
):
    """Notify that a SARDA cycle completed with critique results."""
    return await bridge.push_event(EscalationEvent(
        event_type="sarda_complete",
        task_id=task_id,
        source_agent="sarda_engine",
        payload={"critique_passed": passed, "confidence": confidence},
    ))


async def request_hitl(bridge: SupabaseBridge, task_id: str, reason: str):
    """Escalate to HITL — requires human approval before proceeding."""
    return await bridge.push_event(EscalationEvent(
        event_type="hitl_request",
        task_id=task_id,
        source_agent="sarda_engine",
        payload={"reason": reason, "awaiting": True},
    ))
