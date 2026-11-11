# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""Sir Gideon, The Independent Verifier (`camelot-gideon-verdict/1`).
===================================================================
Phase 4 Independent Verification Gate of the Sovereign Production Hardening Spine.

Core Axioms:
    - Gideon decides pass or block only; it does not narrate (that is Scribe's role).
    - An effect CANNOT be authorized or committed without a valid, signed Gideon verdict.
    - Evaluates all 13 canonical gates defined in packages/contracts/gideon-verdict.schema.json:
        1. contract_conformance
        2. path_scope_conformance
        3. diff_integrity
        4. test_result_validity
        5. dependency_risk
        6. secret_exposure
        7. security_regression
        8. accessibility_baseline
        9. rollback_availability
        10. lifecycle_cleanup
        11. memory_provenance_for_material_claims
        12. declared_risk_tier_matches_observable_effect
        13. declared_effect_class_consistent
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519

# The 13 canonical gates defined in packages/contracts/gideon-verdict.schema.json
CANONICAL_GIDEON_GATES = [
    "contract_conformance",
    "path_scope_conformance",
    "diff_integrity",
    "test_result_validity",
    "dependency_risk",
    "secret_exposure",
    "security_regression",
    "accessibility_baseline",
    "rollback_availability",
    "lifecycle_cleanup",
    "memory_provenance_for_material_claims",
    "declared_risk_tier_matches_observable_effect",
    "declared_effect_class_consistent",
]

# Canonical Effect Classes (17 from effect-manifest / capability-lease)
CANONICAL_EFFECT_CLASSES = frozenset({
    "ro.fetch",
    "ro.audit",
    "internal.synth",
    "workspace.test",
    "workspace.patch",
    "promote.worktree.merge",
    "promote.deploy",
    "external.publish.draft",
    "external.publish.publish",
    "external.email.send",
    "payment.invoice.draft",
    "payment.invoice.issue",
    "payment.capture",
    "payment.refund",
    "device.calendar.write",
    "device.sms.send",
    "device.call.initiate",
    "promote.failover",
})

# Minimum Risk Tier Requirements for High-Impact Effect Classes
EFFECT_CLASS_MIN_RISK_TIERS = {
    "ro.fetch": "T0",
    "ro.audit": "T0",
    "internal.synth": "T1",
    "workspace.test": "T1",
    "workspace.patch": "T2",
    "external.publish.draft": "T2",
    "payment.invoice.draft": "T2",
    "device.calendar.write": "T2",
    "promote.worktree.merge": "T3",
    "external.publish.publish": "T3",
    "external.email.send": "T3",
    "payment.invoice.issue": "T3",
    "device.sms.send": "T3",
    "device.call.initiate": "T3",
    "promote.deploy": "T4",
    "payment.capture": "T4",
    "payment.refund": "T4",
    "promote.failover": "T4",
}

RISK_TIER_ORDINAL = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}

SECRET_PATTERNS = [
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*\\?['\"]?[a-zA-Z0-9_\-]{16,}\\?['\"]?"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
    re.compile(r"(?i)password\s*[:=]\s*\\?['\"][^'\"]{8,}\\?['\"]"),
]

REGRESSION_PATTERNS = [
    re.compile(r"(?i)disable\s+row\s+level\s+security"),
    re.compile(r"(?i)drop\s+policy"),
    re.compile(r"(?i)bypass\s+sentinel"),
    re.compile(r"(?i)no_verify_signature"),
]


def sha256_canonical(data: Any) -> str:
    """Compute SHA-256 over RFC 8785 JSON canonical string."""
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()}"


@dataclass
class GideonVerdict:
    schema_version: str
    verdict_id: str
    task_id: str
    correlation_id: str
    tenant_id: str
    manifest_hash: str
    verdict: str  # "pass" | "block"
    gates: List[str]
    issued_at: str
    signature: str
    block_reasons: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GideonVerifier:
    """Independent zero-trust forensic verifier engine."""

    # Default deterministic key for Sir Gideon (32 bytes)
    _GIDEON_DEFAULT_SEED = b"Sir_Gideon_Forensic_Auditor_32B!"

    def __init__(self, private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        self._private_key = private_key or ed25519.Ed25519PrivateKey.from_private_bytes(self._GIDEON_DEFAULT_SEED)
        self._public_key = self._private_key.public_key()

    @property
    def public_key_hex(self) -> str:
        return self._public_key.public_bytes_raw().hex()

    def evaluate_manifest_and_evidence(
        self,
        task_id: str,
        tenant_id: str,
        correlation_id: str,
        manifest: Dict[str, Any],
        evidence_envelopes: List[Dict[str, Any]],
        test_runs: Optional[List[Dict[str, Any]]] = None,
        lease: Optional[Dict[str, Any]] = None,
    ) -> GideonVerdict:
        """Evaluates all 13 canonical gates against candidate manifest, evidence, tests, and lease."""
        block_reasons: List[str] = []
        evidence_refs: List[str] = []
        evaluated_gates = list(CANONICAL_GIDEON_GATES)

        manifest_hash = manifest.get("manifest_hash")
        if not manifest_hash:
            # Fallback: compute hash of manifest content
            manifest_hash = sha256_canonical(manifest)

        # Gate 1: contract_conformance
        if not re.match(r"^task_[A-Za-z0-9_-]+$", task_id):
            block_reasons.append(f"[G1:CONTRACT_CONFORMANCE] Invalid task_id format: '{task_id}'")
        if not re.match(r"^tenant_[A-Za-z0-9_-]+$", tenant_id):
            block_reasons.append(f"[G1:CONTRACT_CONFORMANCE] Invalid tenant_id format: '{tenant_id}'")
        if not re.match(r"^cor_[A-Za-z0-9_-]+$", correlation_id):
            block_reasons.append(f"[G1:CONTRACT_CONFORMANCE] Invalid correlation_id format: '{correlation_id}'")

        # Gate 2: path_scope_conformance
        target_paths = manifest.get("target_paths", [])
        allowed_writes = lease.get("permissions", {}).get("path_scopes", {}).get("write_scopes", []) if lease else []
        for p in target_paths:
            norm_p = p.replace("\\", "/").strip("/")
            if ".." in norm_p or norm_p.startswith("/") or re.search(r"(?:^|[\\/])\.\.(?:[\\/]|$)", p):
                block_reasons.append(f"[G2:PATH_SCOPE_CONFORMANCE] Directory traversal attempt rejected: '{p}'")
            elif allowed_writes and not any(norm_p == s or norm_p.startswith(f"{s}/") for s in allowed_writes):
                block_reasons.append(f"[G2:PATH_SCOPE_CONFORMANCE] Path '{p}' not in lease write scopes: {allowed_writes}")

        # Gate 3: diff_integrity
        diff_payload = manifest.get("diff_payload")
        if diff_payload is not None:
            expected_hash = manifest.get("diff_hash") or manifest.get("manifest_hash")
            computed_diff_hash = f"sha256:{hashlib.sha256(diff_payload.encode('utf-8')).hexdigest()}"
            if expected_hash and computed_diff_hash != expected_hash:
                block_reasons.append(f"[G3:DIFF_INTEGRITY] Diff payload hash {computed_diff_hash} != expected {expected_hash}")

        # Gate 4: test_result_validity
        if test_runs is not None:
            if not test_runs:
                block_reasons.append("[G4:TEST_RESULT_VALIDITY] Test runs required for promotion but none provided")
            for t in test_runs:
                status = t.get("status")
                failed_count = t.get("failed", 0)
                if status != "passed" or failed_count > 0:
                    block_reasons.append(f"[G4:TEST_RESULT_VALIDITY] Test run '{t.get('suite_id')}' failed (status={status}, failed={failed_count})")
                ref = t.get("receipt_ref")
                if ref:
                    evidence_refs.append(ref)

        # Gate 5: dependency_risk
        dependencies = manifest.get("new_dependencies", [])
        unapproved_deps = [d for d in dependencies if d.get("is_vetted") is False]
        if unapproved_deps:
            block_reasons.append(f"[G5:DEPENDENCY_RISK] Unvetted third-party dependencies detected: {unapproved_deps}")

        # Gate 6: secret_exposure
        content_to_scan = json.dumps(manifest) + " " + json.dumps(evidence_envelopes)
        for pattern in SECRET_PATTERNS:
            if pattern.search(content_to_scan):
                block_reasons.append("[G6:SECRET_EXPOSURE] Potential plaintext secret or credential token detected")
                break

        # Gate 7: security_regression
        for pattern in REGRESSION_PATTERNS:
            if pattern.search(content_to_scan):
                block_reasons.append("[G7:SECURITY_REGRESSION] Attempted security control downgrade or RLS bypass detected")
                break

        # Gate 8: accessibility_baseline
        if manifest.get("is_ui_component", False):
            if not manifest.get("a11y_audited", False):
                block_reasons.append("[G8:ACCESSIBILITY_BASELINE] UI component missing verified accessibility audit baseline")

        # Gate 9: rollback_availability
        if manifest.get("effect_class") in ("promote.deploy", "workspace.patch", "promote.worktree.merge"):
            if not manifest.get("rollback_snapshot_ref"):
                block_reasons.append("[G9:ROLLBACK_AVAILABILITY] Destructive/promotional effect missing rollback snapshot reference")

        # Gate 10: lifecycle_cleanup
        if manifest.get("requires_cleanup", True) and not manifest.get("cleanup_plan_ref"):
            block_reasons.append("[G10:LIFECYCLE_CLEANUP] Effect manifest missing lifecycle cleanup specification")

        # Gate 11: memory_provenance_for_material_claims
        material_claims = manifest.get("material_claims", [])
        for claim in material_claims:
            if not claim.get("provenance_entry_id"):
                block_reasons.append(f"[G11:MEMORY_PROVENANCE] Material claim '{claim.get('claim_id')}' missing provenance entry link")

        # Gate 12: declared_risk_tier_matches_observable_effect
        effect_class = manifest.get("effect_class", "workspace.test")
        declared_tier = manifest.get("declared_risk_tier", "T1")
        min_tier = EFFECT_CLASS_MIN_RISK_TIERS.get(effect_class, "T1")
        if RISK_TIER_ORDINAL.get(declared_tier, 0) < RISK_TIER_ORDINAL.get(min_tier, 0):
            block_reasons.append(
                f"[G12:RISK_TIER_MISMATCH] Declared risk tier '{declared_tier}' is insufficient for effect class '{effect_class}' (requires >= {min_tier})"
            )

        # Gate 13: declared_effect_class_consistent
        if effect_class not in CANONICAL_EFFECT_CLASSES:
            block_reasons.append(f"[G13:EFFECT_CLASS_INCONSISTENT] Unknown effect class: '{effect_class}'")

        # Gather evidence envelope refs
        for env in evidence_envelopes:
            ref = env.get("receipt_ref")
            if ref:
                evidence_refs.append(ref)
            if env.get("integrity") == "failed":
                block_reasons.append(f"[EVIDENCE_TAMPER] Evidence envelope '{env.get('event_id')}' reported integrity failure")

        verdict_status = "pass" if len(block_reasons) == 0 else "block"
        verdict_id = f"gv_{uuid.uuid4().hex[:16]}"
        issued_at = datetime.now(timezone.utc).isoformat()

        # Build payload for cryptographic signing
        payload_to_sign = {
            "schema_version": "camelot-gideon-verdict/1",
            "verdict_id": verdict_id,
            "task_id": task_id,
            "correlation_id": correlation_id,
            "tenant_id": tenant_id,
            "manifest_hash": manifest_hash,
            "verdict": verdict_status,
            "gates": evaluated_gates,
            "block_reasons": block_reasons,
            "evidence_refs": sorted(set(evidence_refs)),
            "issued_at": issued_at,
        }

        canonical_bytes = json.dumps(payload_to_sign, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature_bytes = self._private_key.sign(canonical_bytes)
        signature_str = f"ed25519:{signature_bytes.hex()}"

        return GideonVerdict(
            schema_version="camelot-gideon-verdict/1",
            verdict_id=verdict_id,
            task_id=task_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            manifest_hash=manifest_hash,
            verdict=verdict_status,
            gates=evaluated_gates,
            block_reasons=block_reasons,
            evidence_refs=sorted(set(evidence_refs)),
            issued_at=issued_at,
            signature=signature_str,
        )

    def verify_verdict_signature(self, verdict: GideonVerdict | Dict[str, Any]) -> bool:
        """Verifies that a Gideon verdict was signed by Gideon's authentic key and not tampered with."""
        data = verdict.to_dict() if isinstance(verdict, GideonVerdict) else dict(verdict)
        sig_str = data.get("signature", "")
        if not sig_str.startswith("ed25519:"):
            return False

        sig_hex = sig_str.split(":", 1)[1]
        try:
            sig_bytes = bytes.fromhex(sig_hex)
        except ValueError:
            return False

        payload_to_verify = {
            "schema_version": data.get("schema_version"),
            "verdict_id": data.get("verdict_id"),
            "task_id": data.get("task_id"),
            "correlation_id": data.get("correlation_id"),
            "tenant_id": data.get("tenant_id"),
            "manifest_hash": data.get("manifest_hash"),
            "verdict": data.get("verdict"),
            "gates": data.get("gates"),
            "block_reasons": data.get("block_reasons", []),
            "evidence_refs": data.get("evidence_refs", []),
            "issued_at": data.get("issued_at"),
        }
        canonical_bytes = json.dumps(payload_to_verify, sort_keys=True, separators=(",", ":")).encode("utf-8")

        try:
            self._public_key.verify(sig_bytes, canonical_bytes)
            return True
        except Exception:
            return False
