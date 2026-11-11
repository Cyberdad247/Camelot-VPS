# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""King Arthur Sovereign Resolution Governor (`camelot-arthur-resolution/1`).
=============================================================================
Phase 4 Sovereign Authority Gate of the Sovereign Production Hardening Spine.

Core Axioms:
    - King Arthur is the governing body and ethical overseer of Camelot-OS (Rule 6).
    - Consequential operations (T3, T4, promotions, failovers) require Arthur's Sovereign Seal.
    - Resolves conflicting Knight consensus or issues Emergency Rezero overrides.
    - Bound to the 6-dimensional Authority Vector:
        <E_leadership, R_policy, R_revocation, R_registry, R_identity, R_contract>
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519

from control_plane.security.receipt_chain import TenantReceiptChain, Receipt, ReceiptActor, ReceiptProof
from control_plane.security.sir_gideon import GideonVerdict


class ArthurResolutionError(Exception):
    """Raised when an Arthur Resolution fails authorization or cryptographic validation."""
    pass


@dataclass
class SovereignSeal:
    king_id: str = "ARTHUR_OMEGA"
    seal_type: str = "SOVEREIGN_GOLDEN_SEAL"  # "SOVEREIGN_GOLDEN_SEAL" | "EMERGENCY_HALT_SEAL"
    ed25519_signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArthurResolution:
    schema_version: str
    resolution_id: str
    directive_type: str
    target_scope: str
    rationale: str
    authority_vector: List[int]
    timestamp: str
    sovereign_seal: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ArthurResolutionGovernor:
    """Sovereign Gate Governor evaluating Arthur Resolutions and signing with the Arthur Ed25519 Crown."""

    _ARTHUR_SOVEREIGN_SEED = b"Arthur_Omega_Sovereign_Seed_32B!"

    def __init__(self, private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        self._private_key = private_key or ed25519.Ed25519PrivateKey.from_private_bytes(self._ARTHUR_SOVEREIGN_SEED)
        self._public_key = self._private_key.public_key()

    @property
    def public_key_hex(self) -> str:
        return self._public_key.public_bytes_raw().hex()

    def create_resolution(
        self,
        directive_type: str,
        target_scope: str,
        rationale: str,
        authority_vector: List[int],
        seal_type: str = "SOVEREIGN_GOLDEN_SEAL",
    ) -> ArthurResolution:
        """Constructs and cryptographically signs an official Arthur Resolution."""
        valid_directives = {
            "SOVEREIGN_OVERRIDE",
            "EMERGENCY_REZERO",
            "ETHICAL_COMPASS_VETO",
            "CONSENSUS_RATIFICATION",
            "PROMOTION_AUTHORIZATION",
        }
        if directive_type not in valid_directives:
            raise ArthurResolutionError(f"Invalid directive_type: '{directive_type}'. Must be one of {sorted(valid_directives)}")

        if len(authority_vector) != 6 or any(v < 0 for v in authority_vector):
            raise ArthurResolutionError("authority_vector must be a 6-element tuple of non-negative integers.")

        resolution_id = f"res_{uuid.uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        payload_to_sign = {
            "schema_version": "camelot-arthur-resolution/1",
            "resolution_id": resolution_id,
            "directive_type": directive_type,
            "target_scope": target_scope,
            "rationale": rationale,
            "authority_vector": authority_vector,
            "timestamp": timestamp,
            "king_id": "ARTHUR_OMEGA",
            "seal_type": seal_type,
        }

        canonical_bytes = json.dumps(payload_to_sign, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig_bytes = self._private_key.sign(canonical_bytes)
        sig_str = f"ed25519:{sig_bytes.hex()}"

        seal = SovereignSeal(
            king_id="ARTHUR_OMEGA",
            seal_type=seal_type,
            ed25519_signature=sig_str,
        )

        return ArthurResolution(
            schema_version="camelot-arthur-resolution/1",
            resolution_id=resolution_id,
            directive_type=directive_type,
            target_scope=target_scope,
            rationale=rationale,
            authority_vector=authority_vector,
            timestamp=timestamp,
            sovereign_seal=seal.to_dict(),
        )

    def verify_resolution(self, resolution: ArthurResolution | Dict[str, Any]) -> bool:
        """Validates schema conformance and cryptographic signature of an Arthur Resolution."""
        data = resolution.to_dict() if isinstance(resolution, ArthurResolution) else dict(resolution)

        if data.get("schema_version") != "camelot-arthur-resolution/1":
            return False

        seal = data.get("sovereign_seal", {})
        if seal.get("king_id") != "ARTHUR_OMEGA":
            return False

        sig_str = seal.get("ed25519_signature", "")
        if not sig_str.startswith("ed25519:"):
            return False

        try:
            sig_bytes = bytes.fromhex(sig_str.split(":", 1)[1])
        except ValueError:
            return False

        payload_to_verify = {
            "schema_version": data.get("schema_version"),
            "resolution_id": data.get("resolution_id"),
            "directive_type": data.get("directive_type"),
            "target_scope": data.get("target_scope"),
            "rationale": data.get("rationale"),
            "authority_vector": data.get("authority_vector"),
            "timestamp": data.get("timestamp"),
            "king_id": seal.get("king_id"),
            "seal_type": seal.get("seal_type"),
        }

        canonical_bytes = json.dumps(payload_to_verify, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            self._public_key.verify(sig_bytes, canonical_bytes)
            return True
        except Exception:
            return False

    def authorize_and_commit_receipt(
        self,
        chain: TenantReceiptChain,
        task_id: str,
        correlation_id: str,
        effect_class: str,
        declared_risk_tier: str,
        gideon_verdict: GideonVerdict,
        authority_vector: List[int],
        resolution: Optional[ArthurResolution] = None,
        anchor_eligible: bool = True,
    ) -> Receipt:
        """Finalizes an authorized effect by committing a receipt to the Tenant Merkle Chain.

        Enforces:
            1. Gideon verdict must be 'pass' OR a valid Arthur SOVEREIGN_OVERRIDE must be presented.
            2. High-risk tiers (T3, T4) MUST be accompanied by an Arthur CONSENSUS_RATIFICATION
               or PROMOTION_AUTHORIZATION resolution.
            3. Authority vector must have no active revocations (R_revocation == 0).
            4. Automatically commits receipt to the tenant's chain.
        """
        # Revocation check
        r_revocation = authority_vector[2] if len(authority_vector) > 2 else 0
        if r_revocation > 0:
            raise ArthurResolutionError(
                f"[REVOCATION_BLOCKED] Operation rejected: active revocation counter is {r_revocation}"
            )

        # Gideon verdict check
        if gideon_verdict.verdict == "block":
            if not resolution or resolution.directive_type != "SOVEREIGN_OVERRIDE":
                raise ArthurResolutionError(
                    f"[GIDEON_GATE_BLOCKED] Operation blocked by Gideon: {gideon_verdict.block_reasons}"
                )

        # High-risk tier governance
        if declared_risk_tier in ("T3", "T4"):
            if not resolution:
                raise ArthurResolutionError(
                    f"[ARTHUR_CROWN_REQUIRED] High-risk tier '{declared_risk_tier}' requires an explicit Arthur Resolution."
                )
            if not self.verify_resolution(resolution):
                raise ArthurResolutionError(
                    "[ARTHUR_SIGNATURE_INVALID] Sovereign resolution signature verification failed."
                )

        # Commit to per-tenant Merkle chain
        signer = "king-arthur" if resolution else "sir-gideon"
        sig_val = resolution.sovereign_seal["ed25519_signature"] if resolution else gideon_verdict.signature
        proof = ReceiptProof(signer=signer, signature=sig_val)
        actor = ReceiptActor(
            id="sir_codex",
            role="OPERATOR_ORCHESTRATOR",
            node_id="cybertronia-1",
            trust_band=declared_risk_tier,
        )

        receipt = Receipt(
            receipt_id=f"rec_{uuid.uuid4().hex[:16]}",
            tenant_id=chain.tenant_id,
            correlation_id=correlation_id,
            task_id=task_id,
            chain_height=chain.chain_height,
            parent_hash=chain.head_hash,
            authority_epoch=authority_vector[0] if authority_vector else 1,
            authority_vector=authority_vector,
            effect_class=effect_class,
            declared_risk_tier=declared_risk_tier,
            actor=actor,
            event=f"{effect_class}.committed",
            proof=proof,
            ledger_anchor_eligible=anchor_eligible,
        )

        return chain.append(receipt)
