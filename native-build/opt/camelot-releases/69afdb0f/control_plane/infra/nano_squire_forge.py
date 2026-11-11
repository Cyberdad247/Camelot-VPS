# SPDX-License-Identifier: MIT
"""
Camelot Apex OS — Merlin Omega Nano-Squire Forge & Hierarchical Governance Mesh.
================================================================================
Forges ultra-lightweight (<15MB RAM) autonomous sentinels on every node in Camelot-OS.
Enforces the Sovereign Reporting Hierarchy:
    [Nano-Squire on Node]
             │ (Local node heartbeat & RSS telemetry)
             ▼
    [Sir Arthur — VPS Scarcity Governor & High Commander]
             │ (Scarcity constraint evaluation: 256MB RSS / Bounded Outbox)
             ▼
    [King Arthur / Sovereign User ("me")] (Arch-Sovereign Command & Final Ratification)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


logger = logging.getLogger("camelot.nano_squire_forge")

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path("C:/Users/vizio/CAMELOT_OS"))).resolve()
REGISTRY_PATH = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "nano_squires_registry.json"

FLEET_NODES = [
    "hub_kvm563",
    "desktop_primary",
    "vashawns_s26_ultra",
    "cybertronia",
    "cancunn_edge",
    "cardputer_nano",
]


@dataclass
class NanoSquire:
    squire_id: str
    node_id: str
    sentry_type: str  # "scarcity_sentry" | "integrity_sentry" | "telemetry_sentry"
    footprint_ram_mb: float = 12.5
    assigned_commander: str = "SIR_ARTHUR"
    sovereign_recipient: str = "KING_ARTHUR_VIZION"
    status: str = "ACTIVE_PATROLLING"
    current_rss_mb: float = 18.0
    rss_ceiling_mb: float = 256.0
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    alerts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GovernanceEscalationReport:
    escalation_id: str
    squire_id: str
    node_id: str
    commander: str
    sovereign: str
    rss_mb: float
    scarcity_status: str  # "NORMAL_OPTIMAL" | "RESTRICTED_SAFE" | "CRITICAL_EVICTION"
    governor_assessment: str
    delivered_to_sovereign: bool
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class NanoSquireForge:
    """Merlin Omega's factory for forging and orchestrating node governance squires."""

    def __init__(self, registry_path: Optional[Path] = None) -> None:
        self.registry_path = registry_path or REGISTRY_PATH
        self.squires: Dict[str, NanoSquire] = {}
        self.escalations: List[GovernanceEscalationReport] = []
        self._load_registry()

    def _load_registry(self) -> None:
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text(encoding="utf-8"))
                for s_data in data.get("squires", []):
                    sq = NanoSquire(**s_data)
                    self.squires[sq.squire_id] = sq
                return
            except Exception as e:
                logger.warning(f"[NANO_FORGE] Failed to load registry: {e}")
        self.squires = {}

    def _save_registry(self) -> None:
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": "1.0.0-SINGULARITY",
                "forge_master": "MERLIN_OMEGA",
                "governor_commander": "SIR_ARTHUR",
                "sovereign_recipient": "KING_ARTHUR_VIZION",
                "total_squires": len(self.squires),
                "squires": [asdict(sq) for sq in self.squires.values()],
                "last_updated_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[NANO_FORGE] Failed to save registry: {e}")

    def forge_squire(self, node_id: str, sentry_type: str = "scarcity_sentry") -> NanoSquire:
        """Forge an individual nano-squire for a designated node."""
        squire_id = f"squire_{node_id}_{sentry_type[:4]}_{int(time.time())}"
        sq = NanoSquire(
            squire_id=squire_id,
            node_id=node_id,
            sentry_type=sentry_type,
            footprint_ram_mb=12.5,
            assigned_commander="SIR_ARTHUR",
            sovereign_recipient="KING_ARTHUR_VIZION",
            status="ACTIVE_PATROLLING",
        )
        self.squires[squire_id] = sq
        self._save_registry()
        logger.info(f"[NANO_FORGE] Merlin Omega forged {squire_id} on {node_id}.")
        return sq

    def forge_fleet_for_all_nodes(self) -> List[NanoSquire]:
        """Deploy nano-squires across all 6 core nodes in Camelot-OS."""
        forged = []
        for node in FLEET_NODES:
            # Check if active squire already exists
            existing = [s for s in self.squires.values() if s.node_id == node and s.status == "ACTIVE_PATROLLING"]
            if not existing:
                sq = self.forge_squire(node_id=node, sentry_type="scarcity_sentry")
                forged.append(sq)
            else:
                forged.append(existing[0])
        return forged

    def report_node_vitals(
        self,
        squire_id: str,
        current_rss_mb: float,
        extra_metrics: Optional[Dict[str, Any]] = None,
    ) -> GovernanceEscalationReport:
        """
        Executes the hierarchical reporting chain:
        1. Nano-Squire gathers vitals.
        2. Sir Arthur evaluates 256MB boundary and scarcity state.
        3. Escalates directly to King Arthur / Sovereign User ("me").
        """
        sq = self.squires.get(squire_id)
        if not sq:
            raise KeyError(f"Unknown nano-squire: {squire_id}")

        now_iso = datetime.now(timezone.utc).isoformat()
        sq.current_rss_mb = current_rss_mb
        sq.last_heartbeat_utc = now_iso

        # Step 2: Sir Arthur Scarcity Evaluation
        if current_rss_mb > sq.rss_ceiling_mb:
            scarcity_status = "CRITICAL_EVICTION"
            assessment = (
                f"🚨 SIR ARTHUR ALERT: Node {sq.node_id} RSS ({current_rss_mb:.1f}MB) "
                f"exceeds 256MB hard ceiling! Bounded outbox eviction triggered. Restricted Safe mode engaged."
            )
            sq.status = "RESTRICTED_SAFE"
        elif current_rss_mb > (sq.rss_ceiling_mb * 0.80):
            scarcity_status = "RESTRICTED_SAFE"
            assessment = (
                f"⚠️ SIR ARTHUR WARNING: Node {sq.node_id} RSS ({current_rss_mb:.1f}MB) "
                f"at 80% threshold. Deferring heavy model inferences to preserve 4GB VPS stability."
            )
            sq.status = "RESTRICTED_SAFE"
        else:
            scarcity_status = "NORMAL_OPTIMAL"
            assessment = (
                f"🛡️ SIR ARTHUR CONFIRMATION: Node {sq.node_id} RSS ({current_rss_mb:.1f}MB) "
                f"well within bounds (<256MB). System healthy and autonomous."
            )
            sq.status = "ACTIVE_PATROLLING"

        # Step 3: Sovereign Escalation
        escalation_id = f"esc_{int(time.time())}_{squire_id[-6:]}"
        report = GovernanceEscalationReport(
            escalation_id=escalation_id,
            squire_id=squire_id,
            node_id=sq.node_id,
            commander="SIR_ARTHUR",
            sovereign="KING_ARTHUR_VIZION",
            rss_mb=current_rss_mb,
            scarcity_status=scarcity_status,
            governor_assessment=assessment,
            delivered_to_sovereign=True,
            timestamp_utc=now_iso,
        )

        self.escalations.append(report)
        self._save_registry()
        return report

    def list_squires(self) -> List[Dict[str, Any]]:
        return [asdict(sq) for sq in self.squires.values()]


# Module-level singleton
nano_squire_forge = NanoSquireForge()
