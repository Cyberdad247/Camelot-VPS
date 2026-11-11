# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""Sovereign Pipeline: Zero-Trust End-to-End Execution Pipeline (Phase 9).
==========================================================================
Coordinates the full 6-stage lifecycle orchestrator:
    - Stage 1 (Ingress & Idempotency):
        Validates TaskProposal, checks compound SHA-256 idempotency key,
        and enforces Sovereign Authority Vector (A_epoch).
    - Stage 2 (Zero-Trust Security Gate):
        Evaluates SecurityWarden permissions & emits manifest-bound Capability Lease.
    - Stage 3 (Bounded Sandbox Execution):
        Executes bounded runtime (<50MB limit) with scoped VFS and canonical evidence emission.
    - Stage 4 (Sir Gideon 13-Gate Independent Audit):
        Evaluates all 13 canonical gates and signs Gideon Verdict (camelot-gideon-verdict/1).
    - Stage 5 (King Arthur Sovereign Resolution & Atomic Merkle Commit):
        Enforces Arthur Crown Seal (T3/T4), commits Receipt to Tenant Merkle Chain,
        and finalizes idempotency journal record.
    - Stage 6 (Telemetry Streaming & BFF Pub-Sub Integration):
        Dispatches verified receipt and evidence events to subscribers.
"""
from __future__ import annotations

import datetime
from datetime import timezone
import enum
import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from control_plane.dispatch.idempotency_guardian import (
    IdempotencyConflictError,
    IdempotencyDecision,
    IdempotencyGuardian,
    IdempotencyPayloadMismatchError,
)
from control_plane.infra.scarcity_guardian import (
    ScarcityGuardian,
    verify_zero_docker_compliance,
)
from control_plane.sandbox.wasmtime_runner import (
    BoundedExecutionEnvelope,
    HostEvidenceEnclave,
    HostVFSEnclave,
    WasmtimeSandboxRunner,
)
from control_plane.security.arthur_resolution import (
    ArthurResolution,
    ArthurResolutionGovernor,
)
from control_plane.security.authority_vector import AuthorityVector
from control_plane.security.receipt_chain import (
    Receipt,
    SovereignMerkleCheckpoint,
    SovereignMerkleCheckpointGovernor,
    TenantReceiptChain,
)
from control_plane.security.sir_gideon import (
    GideonVerdict,
    GideonVerifier,
    sha256_canonical,
)
from security.warden import SecurityDecision, SecurityWarden, warden as default_warden

LOG = logging.getLogger("camelot.sovereign_pipeline")


class PipelineStage(str, enum.Enum):
    INGRESS_IDEMPOTENCY = "INGRESS_IDEMPOTENCY"
    SECURITY_GATE = "SECURITY_GATE"
    BOUNDED_EXECUTION = "BOUNDED_EXECUTION"
    INDEPENDENT_AUDIT = "INDEPENDENT_AUDIT"
    SOVEREIGN_RESOLUTION = "SOVEREIGN_RESOLUTION"
    TELEMETRY_DISPATCH = "TELEMETRY_DISPATCH"


class PipelineStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    REPLAYED = "REPLAYED"
    BLOCKED = "BLOCKED"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"


@dataclass
class TaskProposal:
    """Inbound task proposal submitted to the Sovereign Pipeline."""

    task_id: str
    tenant_id: str
    correlation_id: str
    idempotency_key: str
    manifest: Dict[str, Any]
    authority_vector: Union[AuthorityVector, Sequence[int]]
    intent: str
    effect_class: str = "workspace.test"
    declared_risk_tier: str = "T1"
    subject: Dict[str, Any] = field(
        default_factory=lambda: {
            "node_id": "cybertronia-1",
            "workload_id": "workload_default",
            "cartridge_id": "cartridge_default",
            "node_trust_band": "attested",
        }
    )
    target_paths: List[str] = field(default_factory=list)
    write_paths: List[str] = field(default_factory=list)
    guest_fn: Optional[Callable[[HostVFSEnclave, HostEvidenceEnclave], Any]] = None
    virtual_fs: Optional[Dict[str, str]] = None
    simulated_memory_mb: float = 12.0
    test_runs: Optional[List[Dict[str, Any]]] = None
    operator_approved: bool = False
    arthur_resolution: Optional[ArthurResolution] = None

    def get_authority_vector(self) -> AuthorityVector:
        if isinstance(self.authority_vector, AuthorityVector):
            return self.authority_vector
        return AuthorityVector.from_sequence(self.authority_vector)

    def compute_manifest_hash(self) -> str:
        h = self.manifest.get("manifest_hash")
        if h and h.startswith("sha256:"):
            return h
        return f"sha256:{sha256_canonical(self.manifest)}"


@dataclass
class PipelineExecutionResult:
    """Result of end-to-end execution through the Sovereign Pipeline."""

    task_id: str
    correlation_id: str
    tenant_id: str
    status: PipelineStatus
    current_stage: PipelineStage
    idempotency_decision: IdempotencyDecision
    security_decision: Optional[SecurityDecision] = None
    lease: Optional[Dict[str, Any]] = None
    execution_envelope: Optional[BoundedExecutionEnvelope] = None
    gideon_verdict: Optional[GideonVerdict] = None
    arthur_resolution: Optional[ArthurResolution] = None
    receipt: Optional[Receipt] = None
    checkpoint: Optional[SovereignMerkleCheckpoint] = None
    telemetry_events: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    retry_after_sec: Optional[int] = None
    duration_ms: float = 0.0
    executed_at: str = field(default_factory=lambda: datetime.datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "idempotency_decision": self.idempotency_decision.value,
            "security_decision": self.security_decision.to_dict() if self.security_decision is not None else None,
            "lease_id": self.lease.get("lease_id") if self.lease else None,
            "execution_status": self.execution_envelope.status if self.execution_envelope else None,
            "gideon_verdict": self.gideon_verdict.verdict if self.gideon_verdict else None,
            "arthur_resolution_id": self.arthur_resolution.resolution_id if self.arthur_resolution else None,
            "receipt_id": self.receipt.receipt_id if self.receipt else None,
            "receipt_ref": f"receipt://vfs/chain/{self.receipt.receipt_id}" if self.receipt else None,
            "telemetry_count": len(self.telemetry_events),
            "error_message": self.error_message,
            "retry_after_sec": self.retry_after_sec,
            "duration_ms": self.duration_ms,
            "executed_at": self.executed_at,
        }


class SovereignPipeline:
    """The Sovereign Lifecycle Orchestrator for Camelot-OS.

    Coordinates all 6 stages of execution under zero-trust, bare-metal,
    hardware-scarcity constraints.
    """

    def __init__(
        self,
        idempotency_guardian: Optional[IdempotencyGuardian] = None,
        security_warden: Optional[SecurityWarden] = None,
        sandbox_runner: Optional[WasmtimeSandboxRunner] = None,
        gideon_verifier: Optional[GideonVerifier] = None,
        arthur_governor: Optional[ArthurResolutionGovernor] = None,
        scarcity_guardian: Optional[ScarcityGuardian] = None,
        checkpoint_governor: Optional[SovereignMerkleCheckpointGovernor] = None,
        trusted_authority_vector: Optional[AuthorityVector] = None,
        auto_ratify_high_risk: bool = False,
    ):
        self.idempotency_guardian = idempotency_guardian or IdempotencyGuardian()
        self.security_warden = security_warden or default_warden
        self.sandbox_runner = sandbox_runner or WasmtimeSandboxRunner()
        self.gideon_verifier = gideon_verifier or GideonVerifier()
        self.arthur_governor = arthur_governor or ArthurResolutionGovernor()
        self.scarcity_guardian = scarcity_guardian or ScarcityGuardian()
        self.checkpoint_governor = checkpoint_governor or SovereignMerkleCheckpointGovernor()
        self.trusted_authority_vector = trusted_authority_vector or AuthorityVector.genesis()
        self.auto_ratify_high_risk = auto_ratify_high_risk
        self._tenant_chains: Dict[str, TenantReceiptChain] = {}
        self._telemetry_subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe_telemetry(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a telemetry subscriber (e.g. Bifrost SSE / WebSocket broadcaster)."""
        self._telemetry_subscribers.append(callback)

    def _broadcast_telemetry(self, event: Dict[str, Any]) -> None:
        """Broadcasts an event envelope to all registered subscribers."""
        for sub in self._telemetry_subscribers:
            try:
                sub(event)
            except Exception as e:
                LOG.debug(f"Telemetry dispatch error: {e}")

    def get_tenant_chain(self, tenant_id: str) -> TenantReceiptChain:
        """Returns or instantiates an isolated per-tenant Merkle receipt chain."""
        if tenant_id not in self._tenant_chains:
            chain = TenantReceiptChain(tenant_id)
            self._tenant_chains[tenant_id] = chain
            self.checkpoint_governor.register_chain(chain)
        return self._tenant_chains[tenant_id]

    def update_trusted_authority_vector(self, new_vector: AuthorityVector) -> None:
        """Updates host authority vector (e.g. upon leadership or revocation advance)."""
        self.trusted_authority_vector = new_vector

    def execute(self, proposal: TaskProposal) -> PipelineExecutionResult:
        """Executes a TaskProposal through the complete 6-stage pipeline."""
        t0 = time.time()
        telemetry_events: List[Dict[str, Any]] = []

        # Validate basic identifier contracts
        if not re.match(r"^task_[A-Za-z0-9_-]+$", proposal.task_id):
            return self._build_error_result(
                proposal=proposal,
                stage=PipelineStage.INGRESS_IDEMPOTENCY,
                error=f"Invalid task_id format: '{proposal.task_id}'",
                t0=t0,
            )
        if not re.match(r"^tenant_[A-Za-z0-9_-]+$", proposal.tenant_id):
            return self._build_error_result(
                proposal=proposal,
                stage=PipelineStage.INGRESS_IDEMPOTENCY,
                error=f"Invalid tenant_id format: '{proposal.tenant_id}'",
                t0=t0,
            )
        if not re.match(r"^cor_[A-Za-z0-9_-]+$", proposal.correlation_id):
            return self._build_error_result(
                proposal=proposal,
                stage=PipelineStage.INGRESS_IDEMPOTENCY,
                error=f"Invalid correlation_id format: '{proposal.correlation_id}'",
                t0=t0,
            )

        manifest_hash = proposal.compute_manifest_hash()
        proposal_vector = proposal.get_authority_vector()

        # =====================================================================
        # STAGE 1: Ingress & Idempotency + Authority Vector Evaluation
        # =====================================================================
        # 1. Authority Vector Evaluation (Monotonic Dominance & Revocation Gate)
        is_valid_auth, auth_reason = self.trusted_authority_vector.validate_lease(proposal_vector)
        if not is_valid_auth:
            err_msg = f"[AUTHORITY_VECTOR_REJECTED] {auth_reason}"
            evt = self._create_telemetry_event(
                proposal=proposal,
                kind="pipeline.stage1.authority_rejected",
                payload={"reason": auth_reason, "proposal_vector": proposal_vector.to_list()},
                integrity="failed",
            )
            telemetry_events.append(evt)
            self._broadcast_telemetry(evt)
            return PipelineExecutionResult(
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                tenant_id=proposal.tenant_id,
                status=PipelineStatus.BLOCKED,
                current_stage=PipelineStage.INGRESS_IDEMPOTENCY,
                idempotency_decision=IdempotencyDecision.REJECTED,
                error_message=err_msg,
                duration_ms=round((time.time() - t0) * 1000.0, 2),
                telemetry_events=telemetry_events,
            )

        # 2. Idempotency Assertion
        try:
            decision, record = self.idempotency_guardian.acquire_or_replay(
                key=proposal.idempotency_key,
                tenant_id=proposal.tenant_id,
                manifest_hash=manifest_hash,
                correlation_id=proposal.correlation_id,
                ttl_seconds=300.0,
            )
        except IdempotencyPayloadMismatchError as e:
            evt = self._create_telemetry_event(
                proposal=proposal,
                kind="pipeline.stage1.payload_mismatch",
                payload={"error": str(e), "manifest_hash": manifest_hash},
                integrity="failed",
            )
            telemetry_events.append(evt)
            self._broadcast_telemetry(evt)
            return PipelineExecutionResult(
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                tenant_id=proposal.tenant_id,
                status=PipelineStatus.BLOCKED,
                current_stage=PipelineStage.INGRESS_IDEMPOTENCY,
                idempotency_decision=IdempotencyDecision.REJECTED,
                error_message=str(e),
                duration_ms=round((time.time() - t0) * 1000.0, 2),
                telemetry_events=telemetry_events,
            )
        except IdempotencyConflictError as e:
            return PipelineExecutionResult(
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                tenant_id=proposal.tenant_id,
                status=PipelineStatus.CONFLICT,
                current_stage=PipelineStage.INGRESS_IDEMPOTENCY,
                idempotency_decision=IdempotencyDecision.CONFLICT,
                error_message=str(e),
                retry_after_sec=e.retry_after_sec,
                duration_ms=round((time.time() - t0) * 1000.0, 2),
                telemetry_events=telemetry_events,
            )

        if decision == IdempotencyDecision.REPLAY:
            evt = self._create_telemetry_event(
                proposal=proposal,
                kind="pipeline.stage1.replay",
                payload={"receipt_ref": record.receipt_ref if record else None},
                receipt_ref=record.receipt_ref if record else None,
            )
            telemetry_events.append(evt)
            self._broadcast_telemetry(evt)
            return PipelineExecutionResult(
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                tenant_id=proposal.tenant_id,
                status=PipelineStatus.REPLAYED,
                current_stage=PipelineStage.INGRESS_IDEMPOTENCY,
                idempotency_decision=IdempotencyDecision.REPLAY,
                error_message=None,
                duration_ms=round((time.time() - t0) * 1000.0, 2),
                telemetry_events=telemetry_events,
            )

        # =====================================================================
        # STAGE 2: Zero-Trust Security Gate & Capability Lease Issuance
        # =====================================================================
        agent_id = proposal.subject.get("node_id", "cybertronia-1")
        sec_decision = self.security_warden.verify_permission(
            agent_id=agent_id,
            resource_type="kinetic_action",
            action=proposal.effect_class,
            target=proposal.intent,
            trust_level="KERNEL",
            raise_on_deny=False,
        )

        if sec_decision.decision == "deny":
            self.idempotency_guardian.reject(
                proposal.idempotency_key,
                proposal.tenant_id,
                manifest_hash,
                reason=sec_decision.reason,
            )
            evt = self._create_telemetry_event(
                proposal=proposal,
                kind="pipeline.stage2.security_denied",
                payload=sec_decision.to_dict(),
                integrity="failed",
            )
            telemetry_events.append(evt)
            self._broadcast_telemetry(evt)
            return PipelineExecutionResult(
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                tenant_id=proposal.tenant_id,
                status=PipelineStatus.BLOCKED,
                current_stage=PipelineStage.SECURITY_GATE,
                idempotency_decision=IdempotencyDecision.PROCEED,
                security_decision=sec_decision,
                error_message=sec_decision.reason,
                duration_ms=round((time.time() - t0) * 1000.0, 2),
                telemetry_events=telemetry_events,
            )

        if sec_decision.decision == "require_approval" and not proposal.operator_approved:
            self.idempotency_guardian.reject(
                proposal.idempotency_key,
                proposal.tenant_id,
                manifest_hash,
                reason=sec_decision.reason,
            )
            evt = self._create_telemetry_event(
                proposal=proposal,
                kind="pipeline.stage2.approval_required",
                payload=sec_decision.to_dict(),
                integrity="pending",
            )
            telemetry_events.append(evt)
            self._broadcast_telemetry(evt)
            return PipelineExecutionResult(
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                tenant_id=proposal.tenant_id,
                status=PipelineStatus.BLOCKED,
                current_stage=PipelineStage.SECURITY_GATE,
                idempotency_decision=IdempotencyDecision.PROCEED,
                security_decision=sec_decision,
                error_message=sec_decision.reason,
                duration_ms=round((time.time() - t0) * 1000.0, 2),
                telemetry_events=telemetry_events,
            )

        # Issue manifest-bound Capability Lease (`camelot-lease/1`)
        lease = self._issue_capability_lease(proposal, manifest_hash, proposal_vector, sec_decision)
        evt_lease = self._create_telemetry_event(
            proposal=proposal,
            kind="pipeline.stage2.lease_issued",
            payload={"lease_id": lease["lease_id"], "permissions": lease["permissions"]},
        )
        telemetry_events.append(evt_lease)
        self._broadcast_telemetry(evt_lease)

        # =====================================================================
        # STAGE 3: Bounded Sandbox Execution (<50MB RAM Limit)
        # =====================================================================
        # 1. Scarcity & Bare-Metal Pre-Flight Checks
        try:
            verify_zero_docker_compliance()
        except Exception as exc:
            self.idempotency_guardian.reject(
                proposal.idempotency_key, proposal.tenant_id, manifest_hash, reason=str(exc)
            )
            return self._build_error_result(
                proposal=proposal,
                stage=PipelineStage.BOUNDED_EXECUTION,
                error=f"[SCARCITY_PREFLIGHT_VIOLATION] {str(exc)}",
                t0=t0,
                telemetry_events=telemetry_events,
            )

        # 2. Guest Execution under Wasmtime Sandbox
        guest_fn = proposal.guest_fn or self._default_guest_program(proposal)
        envelope = self.sandbox_runner.execute_bounded_runtime(
            task_id=proposal.task_id,
            lease=lease,
            guest_fn=guest_fn,
            simulated_memory_mb=proposal.simulated_memory_mb,
            virtual_fs=proposal.virtual_fs,
        )

        # Ingest all evidence envelopes emitted by the guest during Stage 3
        telemetry_events.extend(envelope.evidence_envelopes)
        for ev in envelope.evidence_envelopes:
            self._broadcast_telemetry(ev)

        if envelope.status != "SUCCESS":
            self.idempotency_guardian.reject(
                proposal.idempotency_key,
                proposal.tenant_id,
                manifest_hash,
                reason=envelope.error_message,
            )
            return PipelineExecutionResult(
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                tenant_id=proposal.tenant_id,
                status=PipelineStatus.BLOCKED,
                current_stage=PipelineStage.BOUNDED_EXECUTION,
                idempotency_decision=IdempotencyDecision.PROCEED,
                security_decision=sec_decision,
                lease=lease,
                execution_envelope=envelope,
                error_message=envelope.error_message,
                duration_ms=round((time.time() - t0) * 1000.0, 2),
                telemetry_events=telemetry_events,
            )

        # =====================================================================
        # STAGE 4: Sir Gideon 13-Gate Independent Forensic Audit
        # =====================================================================
        gideon_verdict = self.gideon_verifier.evaluate_manifest_and_evidence(
            task_id=proposal.task_id,
            tenant_id=proposal.tenant_id,
            correlation_id=proposal.correlation_id,
            manifest=proposal.manifest,
            evidence_envelopes=envelope.evidence_envelopes,
            test_runs=proposal.test_runs,
            lease=lease,
        )

        # Verify signature on Gideon's verdict
        if not self.gideon_verifier.verify_verdict_signature(gideon_verdict):
            err = "[GIDEON_VERDICT_TAMPERED] Sir Gideon verdict signature validation failed."
            self.idempotency_guardian.reject(proposal.idempotency_key, proposal.tenant_id, manifest_hash, reason=err)
            return self._build_error_result(
                proposal=proposal,
                stage=PipelineStage.INDEPENDENT_AUDIT,
                error=err,
                t0=t0,
                telemetry_events=telemetry_events,
            )

        # If Gideon blocked, check for King Arthur Sovereign Override
        if gideon_verdict.verdict == "block":
            override = False
            if proposal.arthur_resolution:
                if (
                    proposal.arthur_resolution.directive_type == "SOVEREIGN_OVERRIDE"
                    and self.arthur_governor.verify_resolution(proposal.arthur_resolution)
                ):
                    override = True

            if not override:
                reason = "; ".join(gideon_verdict.block_reasons)
                self.idempotency_guardian.reject(
                    proposal.idempotency_key, proposal.tenant_id, manifest_hash, reason=reason
                )
                evt_verdict = self._create_telemetry_event(
                    proposal=proposal,
                    kind="pipeline.stage4.gideon_blocked",
                    payload=gideon_verdict.to_dict(),
                    integrity="failed",
                )
                telemetry_events.append(evt_verdict)
                self._broadcast_telemetry(evt_verdict)
                return PipelineExecutionResult(
                    task_id=proposal.task_id,
                    correlation_id=proposal.correlation_id,
                    tenant_id=proposal.tenant_id,
                    status=PipelineStatus.BLOCKED,
                    current_stage=PipelineStage.INDEPENDENT_AUDIT,
                    idempotency_decision=IdempotencyDecision.PROCEED,
                    security_decision=sec_decision,
                    lease=lease,
                    execution_envelope=envelope,
                    gideon_verdict=gideon_verdict,
                    error_message=reason,
                    duration_ms=round((time.time() - t0) * 1000.0, 2),
                    telemetry_events=telemetry_events,
                )

        evt_gideon = self._create_telemetry_event(
            proposal=proposal,
            kind="pipeline.stage4.gideon_passed",
            payload={"verdict_id": gideon_verdict.verdict_id, "gates": gideon_verdict.gates},
        )
        telemetry_events.append(evt_gideon)
        self._broadcast_telemetry(evt_gideon)

        # =====================================================================
        # STAGE 5: King Arthur Sovereign Resolution & Atomic Merkle Commit
        # =====================================================================
        resolution = proposal.arthur_resolution

        # High-risk governance (T3/T4) requires an explicit Arthur Resolution
        if proposal.declared_risk_tier in ("T3", "T4"):
            if not resolution:
                if self.auto_ratify_high_risk:
                    resolution = self.arthur_governor.create_resolution(
                        directive_type="CONSENSUS_RATIFICATION",
                        target_scope=proposal.task_id,
                        rationale=f"Auto-ratified by Sovereign King Arthur for task {proposal.task_id}",
                        authority_vector=proposal_vector.to_list(),
                    )
                else:
                    err = f"[ARTHUR_CROWN_REQUIRED] High-risk tier '{proposal.declared_risk_tier}' requires Arthur Resolution."
                    self.idempotency_guardian.reject(
                        proposal.idempotency_key, proposal.tenant_id, manifest_hash, reason=err
                    )
                    return self._build_error_result(
                        proposal=proposal,
                        stage=PipelineStage.SOVEREIGN_RESOLUTION,
                        error=err,
                        t0=t0,
                        telemetry_events=telemetry_events,
                    )

            # Cryptographically verify the resolution
            if not self.arthur_governor.verify_resolution(resolution):
                err = "[ARTHUR_SIGNATURE_INVALID] Sovereign resolution signature verification failed."
                self.idempotency_guardian.reject(
                    proposal.idempotency_key, proposal.tenant_id, manifest_hash, reason=err
                )
                return self._build_error_result(
                    proposal=proposal,
                    stage=PipelineStage.SOVEREIGN_RESOLUTION,
                    error=err,
                    t0=t0,
                    telemetry_events=telemetry_events,
                )

        chain = self.get_tenant_chain(proposal.tenant_id)

        try:
            receipt = self.arthur_governor.authorize_and_commit_receipt(
                chain=chain,
                task_id=proposal.task_id,
                correlation_id=proposal.correlation_id,
                effect_class=proposal.effect_class,
                declared_risk_tier=proposal.declared_risk_tier,
                gideon_verdict=gideon_verdict,
                authority_vector=proposal_vector.to_list(),
                resolution=resolution,
            )
        except Exception as exc:
            self.idempotency_guardian.reject(
                proposal.idempotency_key, proposal.tenant_id, manifest_hash, reason=str(exc)
            )
            return self._build_error_result(
                proposal=proposal,
                stage=PipelineStage.SOVEREIGN_RESOLUTION,
                error=f"[MERKLE_COMMIT_FAILED] {str(exc)}",
                t0=t0,
                telemetry_events=telemetry_events,
            )

        # Commit to Idempotency Store
        receipt_ref = f"receipt://vfs/chain/{receipt.receipt_id}"
        self.idempotency_guardian.commit(
            key=proposal.idempotency_key,
            tenant_id=proposal.tenant_id,
            manifest_hash=manifest_hash,
            receipt_ref=receipt_ref,
            response_body=receipt.to_dict(),
        )

        # Optional Merkle Checkpoint aggregation
        checkpoint = None
        if receipt.ledger_anchor_eligible:
            checkpoint = self.checkpoint_governor.create_signed_checkpoint(
                authority_epoch=proposal_vector.e_leadership
            )

        # =====================================================================
        # STAGE 6: Telemetry Streaming & BFF Pub-Sub Integration
        # =====================================================================
        evt_commit = self._create_telemetry_event(
            proposal=proposal,
            kind="pipeline.stage6.committed",
            payload={
                "receipt_id": receipt.receipt_id,
                "chain_height": chain.chain_height,
                "head_hash": chain.head_hash,
                "merkle_anchor_eligible": receipt.ledger_anchor_eligible,
            },
            receipt_ref=receipt_ref,
        )
        telemetry_events.append(evt_commit)
        self._broadcast_telemetry(evt_commit)

        return PipelineExecutionResult(
            task_id=proposal.task_id,
            correlation_id=proposal.correlation_id,
            tenant_id=proposal.tenant_id,
            status=PipelineStatus.SUCCESS,
            current_stage=PipelineStage.TELEMETRY_DISPATCH,
            idempotency_decision=IdempotencyDecision.PROCEED,
            security_decision=sec_decision,
            lease=lease,
            execution_envelope=envelope,
            gideon_verdict=gideon_verdict,
            arthur_resolution=resolution,
            receipt=receipt,
            checkpoint=checkpoint,
            telemetry_events=telemetry_events,
            error_message=None,
            duration_ms=round((time.time() - t0) * 1000.0, 2),
        )

    def _issue_capability_lease(
        self,
        proposal: TaskProposal,
        manifest_hash: str,
        proposal_vector: AuthorityVector,
        sec_decision: SecurityDecision,
    ) -> Dict[str, Any]:
        """Issues a structured Capability Lease conforming to `camelot-lease/1`."""
        lease_id = f"lease_{uuid.uuid4().hex[:16]}"
        now = datetime.datetime.now(timezone.utc)
        valid_until = (now + datetime.timedelta(minutes=15)).isoformat()

        read_scopes = list(proposal.target_paths or proposal.manifest.get("target_paths", []))
        if not read_scopes:
            read_scopes = ["vfs/workspaces", "docs/architecture"]

        write_scopes = list(proposal.write_paths or proposal.manifest.get("write_paths", []))

        max_mem = float(proposal.manifest.get("max_memory_mb", 50.0))
        bounded_mem = min(max_mem, 50.0)

        return {
            "schema_version": "camelot-lease/1",
            "lease_id": lease_id,
            "authority_epoch": proposal_vector.e_leadership,
            "authority_vector": proposal_vector.to_list(),
            "manifest_hash": manifest_hash,
            "task_id": proposal.task_id,
            "correlation_id": proposal.correlation_id,
            "tenant_id": proposal.tenant_id,
            "effect_class": proposal.effect_class,
            "declared_risk_tier": proposal.declared_risk_tier,
            "subject": proposal.subject,
            "permissions": {
                "path_scopes": {
                    "read_scopes": read_scopes,
                    "write_scopes": write_scopes,
                },
                "vfs": {
                    "read": read_scopes,
                    "write": write_scopes,
                },
                "process": {"allowlist": []},
                "network": "disabled",
                "secrets": [],
            },
            "limits": {
                "max_memory_mb": bounded_mem,
                "timeout_sec": 5.0,
                "timeout_s": 5,
                "valid_until": valid_until,
                "expires_at": valid_until,
                "max_actions": 100,
            },
            "properties": {
                "transferable": False,
                "renewable": False,
                "revocable": True,
            },
            "derived_capabilities_provenance": {
                "algorithm": "camelot-derive-capabilities/1",
                "algorithm_version": "1.0.0",
                "spec_section": "§13.3",
                "input_checksums": {
                    "effect_manifest_hash": manifest_hash,
                    "policy_decision_hash": f"sha256:{hashlib.sha256(sec_decision.reason.encode()).hexdigest()}",
                    "cartridge_manifest_hash": "sha256:" + "0" * 64,
                    "persona_class_hash": "sha256:" + "0" * 64,
                },
                "derived_at_authority_epoch": proposal_vector.e_leadership,
            },
        }

    def _default_guest_program(
        self, proposal: TaskProposal
    ) -> Callable[[HostVFSEnclave, HostEvidenceEnclave], Any]:
        """Provides a safe deterministic default guest program."""
        def guest(vfs: HostVFSEnclave, ev: HostEvidenceEnclave) -> Dict[str, Any]:
            read_count = 0
            if proposal.virtual_fs:
                for p in vfs.allowed_read_scopes:
                    try:
                        vfs.read(p)
                        read_count += 1
                    except Exception:
                        pass
            ev.emit(
                kind="pipeline.guest.execution",
                payload_redacted={
                    "task_id": proposal.task_id,
                    "intent": proposal.intent,
                    "read_scopes_count": len(vfs.allowed_read_scopes),
                    "read_count": read_count,
                },
                integrity="verified",
            )
            return {
                "status": "GUEST_EXECUTION_COMPLETED",
                "task_id": proposal.task_id,
                "files_read": read_count,
            }

        return guest

    def _create_telemetry_event(
        self,
        proposal: TaskProposal,
        kind: str,
        payload: Dict[str, Any],
        integrity: str = "verified",
        receipt_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Constructs an operator-evidence/1 event envelope."""
        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        envelope = {
            "schema_version": "operator-evidence/1",
            "event_id": event_id,
            "task_id": proposal.task_id,
            "correlation_id": proposal.correlation_id,
            "tenant_id": proposal.tenant_id,
            "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "actor": {
                "knight_id": "sir_codex",
                "role": "SOVEREIGN_PIPELINE",
                "trust_band": proposal.declared_risk_tier,
            },
            "integrity": integrity,
            "parent_hash": "sha256:" + "0" * 64,
            "payload_redacted": payload,
        }
        if receipt_ref:
            envelope["receipt_ref"] = receipt_ref
        return envelope

    def _build_error_result(
        self,
        proposal: TaskProposal,
        stage: PipelineStage,
        error: str,
        t0: float,
        telemetry_events: Optional[List[Dict[str, Any]]] = None,
    ) -> PipelineExecutionResult:
        evts = telemetry_events or []
        evt = self._create_telemetry_event(
            proposal=proposal,
            kind=f"pipeline.{stage.value.lower()}.error",
            payload={"error": error},
            integrity="failed",
        )
        evts.append(evt)
        self._broadcast_telemetry(evt)
        return PipelineExecutionResult(
            task_id=proposal.task_id,
            correlation_id=proposal.correlation_id,
            tenant_id=proposal.tenant_id,
            status=PipelineStatus.ERROR,
            current_stage=stage,
            idempotency_decision=IdempotencyDecision.PROCEED,
            error_message=error,
            duration_ms=round((time.time() - t0) * 1000.0, 2),
            telemetry_events=evts,
        )
