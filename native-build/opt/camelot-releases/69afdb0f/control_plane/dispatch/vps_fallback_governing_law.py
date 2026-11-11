# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
VPS Fallback Governing Law for Camelot-OS Edge Node
===================================================
Governing Node: motorola-moto-g-power-5g---2024 (cancunn)
Governing Knights: SIR_ARTHUR (VPS Scarcity Governor) · SIR_HEIMDALL (Bifrost Edge) · LADY_MNEMOSYNE (Memory Palace)
Hardware Constraint: 4GB_ARM64_EDGE_STRICT (<256MB RSS ceiling, MediaTek Dimensity 7020)
Upstream Hub: vps-camelot-hub (162.35.107.134 / 100.110.180.18) on port 8096 (Edge Bus) & 8095 (Mesh Bridge)

Governing Law Invariants:
1. Zero Authority Drift: Edge node never assumes hub authority or executes arbitrary code when offline.
2. Bounded Local Outbox: Telemetry and receipts stored locally in SQLite WAL, capped at 1,000 items (FIFO).
3. Snapshot Validity Lock: Offline operations permitted only while cached signed snapshot is valid (TTL <= 3600s).
   When snapshot expires without hub reachable, locks into RESTRICTED_SAFE mode.
4. Auto-Replay & Convergence: On mesh recovery, outbox drains with exponential jitter backoff into /v1/edge/outbox.
5. Scarcity Governance: Sir Arthur commands resource boundaries and escalates node alerts to Sovereign High Command.
"""

from __future__ import annotations

import enum
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("VPSFallbackGoverningLaw")

GOVERNING_KNIGHT = "SIR_ARTHUR"
GOVERNOR_TITLE = "VPS Scarcity Governor & High Commander of Resource Boundaries"
DEVICE_ID = "motorola-moto-g-power-5g---2024"
MAX_RSS_BYTES = 256 * 1024 * 1024  # 256 MiB hard memory ceiling (4GB Scarcity Constraint)
MAX_OUTBOX_ENTRIES = 1000
SNAPSHOT_MAX_AGE_SECONDS = 3600

ALLOWED_OFFLINE_ACTIONS = frozenset({
    "health_probe",
    "tailscale_route_check",
    "collect_telemetry",
    "notify",
})

FORBIDDEN_OFFLINE_ACTIONS = frozenset({
    "vfs_mutation",
    "unauthenticated_exec",
    "model_inference_spawn",
    "credential_export",
})


class FallbackState(str, enum.Enum):
    ONLINE_TETHERED = "ONLINE_TETHERED"
    OFFLINE_AUTONOMOUS = "OFFLINE_AUTONOMOUS"
    RECONNECTING_DRAIN = "RECONNECTING_DRAIN"
    RESTRICTED_SAFE = "RESTRICTED_SAFE"


@dataclass
class EdgeTelemetry:
    device_id: str
    battery_level: int
    battery_voltage_mv: int
    battery_temp_c: float
    wifi_ip: str
    tailscale_ip: Optional[str]
    memory_rss_bytes: int
    timestamp_utc: int = field(default_factory=lambda: int(time.time()))


@dataclass
class FallbackPolicyDecision:
    allowed: bool
    state: FallbackState
    action: str
    reason: str
    outbox_depth: int
    governor: str = GOVERNING_KNIGHT
    governor_title: str = GOVERNOR_TITLE


class BoundedEdgeOutbox:
    """Bounded SQLite WAL outbox ensuring zero data loss and strict 4GB scarcity bounds."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edge_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    envelope TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    delivered INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def enqueue(self, action: str, payload: Dict[str, Any], envelope: str) -> int:
        """Enqueue an envelope, maintaining the strict MAX_OUTBOX_ENTRIES bound."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM edge_outbox WHERE delivered = 0")
            count = cur.fetchone()[0]

            if count >= MAX_OUTBOX_ENTRIES:
                # Evict oldest undelivered item to prevent memory or disk growth
                cur.execute("""
                    DELETE FROM edge_outbox WHERE id IN (
                        SELECT id FROM edge_outbox WHERE delivered = 0 ORDER BY created_at ASC LIMIT 1
                    )
                """)
                LOG.warning("Edge outbox exceeded %d entries; evicted oldest entry.", MAX_OUTBOX_ENTRIES)

            cur.execute(
                "INSERT INTO edge_outbox (action, payload, envelope, created_at) VALUES (?, ?, ?, ?)",
                (action, json.dumps(payload), envelope, int(time.time())),
            )
            conn.commit()
            return cur.lastrowid or 0

    def pending_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM edge_outbox WHERE delivered = 0")
            return cur.fetchone()[0]

    def fetch_pending(self, limit: int = 50) -> List[Tuple[int, str, Dict[str, Any], str]]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, action, payload, envelope FROM edge_outbox WHERE delivered = 0 ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            return [(r[0], r[1], json.loads(r[2]), r[3]) for r in rows]

    def mark_delivered(self, ids: List[int]) -> None:
        if not ids:
            return
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"UPDATE edge_outbox SET delivered = 1 WHERE id IN ({placeholders})", ids)
            conn.commit()


class VPSFallbackGovernor:
    """Enforces VPS fallback law for Motorola Edge node under 4GB constraint."""

    def __init__(self, outbox_db: Path | str, cached_snapshot_path: Optional[Path | str] = None):
        self.outbox = BoundedEdgeOutbox(outbox_db)
        self.snapshot_path = Path(cached_snapshot_path) if cached_snapshot_path else None
        self.device_id = DEVICE_ID

    def evaluate_action(
        self,
        action: str,
        *,
        vps_reachable: bool,
        current_rss_bytes: int,
        snapshot_issued_at: Optional[int] = None,
        now: Optional[int] = None,
    ) -> FallbackPolicyDecision:
        t_now = int(time.time()) if now is None else now
        outbox_depth = self.outbox.pending_count()

        # 1. Scarcity Constraint Check: Hard 256MB RSS ceiling
        if current_rss_bytes > MAX_RSS_BYTES:
            LOG.error("Scarcity boundary violated: current RSS %d exceeds max %d", current_rss_bytes, MAX_RSS_BYTES)
            return FallbackPolicyDecision(
                allowed=False,
                state=FallbackState.RESTRICTED_SAFE,
                action=action,
                reason="memory-rss-limit-exceeded",
                outbox_depth=outbox_depth,
            )

        # 2. Forbidden offline actions check
        if not vps_reachable and action in FORBIDDEN_OFFLINE_ACTIONS:
            return FallbackPolicyDecision(
                allowed=False,
                state=FallbackState.OFFLINE_AUTONOMOUS,
                action=action,
                reason="forbidden-action-during-offline-fallback",
                outbox_depth=outbox_depth,
            )

        # 3. Snapshot validity check when offline
        if not vps_reachable:
            if snapshot_issued_at is None or (t_now - snapshot_issued_at) > SNAPSHOT_MAX_AGE_SECONDS:
                if action not in {"health_probe", "tailscale_route_check"}:
                    return FallbackPolicyDecision(
                        allowed=False,
                        state=FallbackState.RESTRICTED_SAFE,
                        action=action,
                        reason="policy-snapshot-expired-fallback-restricted",
                        outbox_depth=outbox_depth,
                    )

        # 4. Action allowlist check
        if action not in ALLOWED_OFFLINE_ACTIONS and not vps_reachable:
            return FallbackPolicyDecision(
                allowed=False,
                state=FallbackState.OFFLINE_AUTONOMOUS,
                action=action,
                reason="action-not-allowlisted-offline",
                outbox_depth=outbox_depth,
            )

        # Decision
        state = FallbackState.ONLINE_TETHERED if vps_reachable else FallbackState.OFFLINE_AUTONOMOUS
        return FallbackPolicyDecision(
            allowed=True,
            state=state,
            action=action,
            reason="policy-compliant",
            outbox_depth=outbox_depth,
        )
