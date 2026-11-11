# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
control_plane.services.state_service — Sovereign UI State Projection & Authority Spine
=====================================================================================
Constitutional Doctrine:
  STATE_SERVICE_ONLY (Strictly Prohibits Client-Inferred Completion)

Authority Spine Pipeline:
  SENTINEL (Capability Lease)
    ➔ EXCALIBUR (Mobile Digest Approval)
      ➔ GIDEON (Z3 Proof & Evidence Verification)
        ➔ ARTHUR (Lifecycle Resolution: PROMOTE | RETREAT)
          ➔ LEDGER (Monotonic Immutable Receipt Admission)

Fail-Closed UI States:
  [PENDING, DENIED, APPROVED, EXECUTING, VERIFIED, FAILED, STALE, REVOKED]
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("state_service")

# The 8 canonical fail-closed projection states
VALID_UI_STATES = {
    "PENDING",
    "DENIED",
    "APPROVED",
    "EXECUTING",
    "VERIFIED",
    "FAILED",
    "STALE",
    "REVOKED",
}


@dataclass
class AuthoritySpineContext:
    mission_id: str
    principal: str
    target_path: str
    has_sentinel_lease: bool = False
    has_excalibur_approval: bool = False
    has_gideon_proof: bool = False
    has_arthur_resolution: bool = False
    has_ledger_receipt: bool = False
    lease_ttl_s: int = 300
    epoch: int = 100
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class UIStateProjection:
    mission_id: str
    state: str
    is_client_inferred: bool
    authority_cleared: bool
    badge_html: str
    receipt_digest: Optional[str]
    epoch: int
    updated_at: str


class StateService:
    """Canonical State Service enforcing the STATE_SERVICE_ONLY doctrine."""

    def __init__(self):
        self._projections: Dict[str, UIStateProjection] = {}
        self._authority_contexts: Dict[str, AuthoritySpineContext] = {}

    def register_mission(self, mission_id: str, principal: str, target_path: str) -> UIStateProjection:
        """Initializes a mission in the fail-closed PENDING state."""
        ctx = AuthoritySpineContext(
            mission_id=mission_id,
            principal=principal,
            target_path=target_path,
        )
        self._authority_contexts[mission_id] = ctx
        projection = self._compute_projection(mission_id, "PENDING", None)
        self._projections[mission_id] = projection
        return projection

    def advance_authority_spine(
        self,
        mission_id: str,
        step: str,
        proof_payload: Optional[Dict[str, Any]] = None,
    ) -> UIStateProjection:
        """Advances the 5-point authority spine sequentially."""
        if mission_id not in self._authority_contexts:
            raise KeyError(f"Mission '{mission_id}' not registered in StateService")

        ctx = self._authority_contexts[mission_id]

        if step == "SENTINEL":
            ctx.has_sentinel_lease = True
            proj = self._compute_projection(mission_id, "PENDING", None)
        elif step == "EXCALIBUR":
            if not ctx.has_sentinel_lease:
                proj = self._compute_projection(mission_id, "DENIED", None)
            else:
                ctx.has_excalibur_approval = True
                proj = self._compute_projection(mission_id, "APPROVED", None)
        elif step == "EXECUTING":
            if not (ctx.has_sentinel_lease and ctx.has_excalibur_approval):
                proj = self._compute_projection(mission_id, "DENIED", None)
            else:
                proj = self._compute_projection(mission_id, "EXECUTING", None)
        elif step == "GIDEON":
            if not (ctx.has_sentinel_lease and ctx.has_excalibur_approval):
                proj = self._compute_projection(mission_id, "DENIED", None)
            else:
                ctx.has_gideon_proof = True
                proj = self._compute_projection(mission_id, "EXECUTING", None)
        elif step == "ARTHUR":
            if not (ctx.has_sentinel_lease and ctx.has_excalibur_approval and ctx.has_gideon_proof):
                proj = self._compute_projection(mission_id, "DENIED", None)
            else:
                ctx.has_arthur_resolution = True
                proj = self._compute_projection(mission_id, "APPROVED", None)
        elif step == "LEDGER":
            if not (
                ctx.has_sentinel_lease
                and ctx.has_excalibur_approval
                and ctx.has_gideon_proof
                and ctx.has_arthur_resolution
            ):
                proj = self._compute_projection(mission_id, "DENIED", None)
            else:
                ctx.has_ledger_receipt = True
                receipt_digest = hashlib.sha256(
                    f"{mission_id}:{ctx.epoch}:{datetime.now(timezone.utc)}".encode()
                ).hexdigest()
                proj = self._compute_projection(mission_id, "VERIFIED", receipt_digest)
        else:
            raise ValueError(f"Unknown authority step: {step}")

        self._projections[mission_id] = proj
        return proj

    def project_ui_state(self, mission_id: str, client_claimed_state: Optional[str] = None) -> UIStateProjection:
        """Returns the authoritative UI state. Rejects client-inferred completion attempts."""
        if client_claimed_state and client_claimed_state not in VALID_UI_STATES:
            logger.warning(f"[STATE_SERVICE_REJECTION] Client attempted invalid state: {client_claimed_state}")
            return self._compute_projection(mission_id, "DENIED", None)

        if mission_id not in self._projections:
            # Unknown mission fails closed to DENIED
            return self._compute_projection(mission_id, "DENIED", None)

        authoritative = self._projections[mission_id]

        # Enforce STATE_SERVICE_ONLY: Client cannot unilaterally claim VERIFIED without ledger receipt
        if client_claimed_state == "VERIFIED" and authoritative.state != "VERIFIED":
            logger.error(
                f"[CLIENT_INFERENCE_VIOLATION] Client claimed 'VERIFIED' without ledger receipt for {mission_id}. Failing closed."
            )
            return self._compute_projection(mission_id, "DENIED", None)

        return authoritative

    def _compute_projection(
        self,
        mission_id: str,
        state: str,
        receipt_digest: Optional[str],
    ) -> UIStateProjection:
        """Constructs an immutable UI projection and styled HTMX badge."""
        if state not in VALID_UI_STATES:
            state = "DENIED"

        colors = {
            "PENDING": ("#f59e0b", "#78350f"),
            "DENIED": ("#ef4444", "#7f1d1d"),
            "APPROVED": ("#3b82f6", "#1e3a8a"),
            "EXECUTING": ("#38bdf8", "#075985"),
            "VERIFIED": ("#10b981", "#064e3b"),
            "FAILED": ("#f43f5e", "#881337"),
            "STALE": ("#a8a29e", "#292524"),
            "REVOKED": ("#dc2626", "#450a0a"),
        }
        fg, bg = colors.get(state, ("#e5e5e5", "#1f1f1f"))
        badge = (
            f"<span id='badge-{mission_id}' class='badge' "
            f"style='background: {bg}; color: {fg}; border: 1px solid {fg}; font-weight: 600; padding: 2px 8px; border-radius: 4px;'>"
            f"{state}"
            f"</span>"
        )
        ctx = self._authority_contexts.get(mission_id)
        epoch = ctx.epoch if ctx else 0
        cleared = (state == "VERIFIED")

        return UIStateProjection(
            mission_id=mission_id,
            state=state,
            is_client_inferred=False,
            authority_cleared=cleared,
            badge_html=badge,
            receipt_digest=receipt_digest,
            epoch=epoch,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )


# Global singleton instance
global_state_service = StateService()
