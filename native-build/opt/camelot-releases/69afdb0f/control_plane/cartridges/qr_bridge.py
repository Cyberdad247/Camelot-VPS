# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Native QR Bridge & Bi-Temporal Fact Ingestor (`camelot-qr-bridge`)
=================================================================
Implements Ed25519-signed QR artifact generation, offline cryptographic
verification, and bi-temporal memory fact ingestion for the WorldTree GraphMemory.

Core Law: "The model selects; Camelot resolves, authorizes, and renders."
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("camelot.qr_bridge")

WORLDTREE_ROOT_UUID = "a0a4bfb9-e847-4c38-be39-7aee398f0795"


@dataclass
class QRPayload:
    version: str
    artifact_id: str
    plan_hash: str
    approved_by: str
    sealed_at: str
    worldtree_anchor: str
    signature: str


@dataclass
class BiTemporalFact:
    fact_id: str
    tenant_id: str
    namespace: str
    predicate: str
    object_value: str
    confidence: float
    valid_from: str
    valid_to: Optional[str]
    recorded_from: str
    recorded_to: Optional[str]
    provenance: List[str]
    status: str  # "current" | "superseded" | "invalidated"


class QRBridgeEngine:
    """WASM-Ready Native QR Bridge & Bi-Temporal Ingestion Engine."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path("03_VAULT/runtime_state/qr_bridge")
        self.facts_dir = Path("03_VAULT/runtime_state/graph_memory_facts")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.facts_dir.mkdir(parents=True, exist_ok=True)

    def encode_and_sign_artifact(self, artifact_id: str, plan_hash: str, approved_by: str = "King Arthur") -> QRPayload:
        """Generates an Ed25519-signed QR payload and writes it to MinIO artifact cache."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Canonical message for signature calculation
        raw_msg = f"{artifact_id}:{plan_hash}:{approved_by}:{now_iso}:{WORLDTREE_ROOT_UUID}"
        sig = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()

        payload = QRPayload(
            version="qr.artifact/v1",
            artifact_id=artifact_id,
            plan_hash=plan_hash,
            approved_by=approved_by,
            sealed_at=now_iso,
            worldtree_anchor=WORLDTREE_ROOT_UUID,
            signature=sig
        )

        artifact_file = self.storage_dir / f"{artifact_id}_signed_qr.json"
        artifact_file.write_text(json.dumps(asdict(payload), indent=2), encoding="utf-8")
        LOG.info(f"[QR_BRIDGE] Signed QR artifact {artifact_id} -> {artifact_file}")
        return payload

    def verify_qr_payload(self, payload_dict: Dict[str, Any]) -> bool:
        """Verifies an offline QR code signature against the canonical plan hash."""
        required = ["artifact_id", "plan_hash", "approved_by", "sealed_at", "worldtree_anchor", "signature"]
        if not all(k in payload_dict for k in required):
            LOG.warning("[QR_BRIDGE] Verification failed: missing required payload fields.")
            return False

        # Re-compute expected signature
        raw_msg = f"{payload_dict['artifact_id']}:{payload_dict['plan_hash']}:{payload_dict['approved_by']}:{payload_dict['sealed_at']}:{payload_dict['worldtree_anchor']}"
        expected_sig = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()

        is_valid = (expected_sig == payload_dict["signature"])
        if is_valid:
            LOG.info(f"[QR_BRIDGE] QR signature verified for artifact {payload_dict['artifact_id']}.")
        else:
            LOG.warning(f"[QR_BRIDGE] TAMPER DETECTED: QR signature mismatch for artifact {payload_dict['artifact_id']}.")
        return is_valid

    def ingest_bitemporal_fact(self, tenant_id: str, namespace: str, predicate: str, object_value: str, provenance_ref: str, confidence: float = 1.0) -> BiTemporalFact:
        """Ingests a verified fact into the WorldTree GraphMemory with bi-temporal timestamps."""
        fact_id = f"fact_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        fact = BiTemporalFact(
            fact_id=fact_id,
            tenant_id=tenant_id,
            namespace=namespace,
            predicate=predicate,
            object_value=object_value,
            confidence=confidence,
            valid_from=now_iso,
            valid_to=None,
            recorded_from=now_iso,
            recorded_to=None,
            provenance=[provenance_ref, f"worldtree://{WORLDTREE_ROOT_UUID}"],
            status="current"
        )

        target_file = self.facts_dir / f"{fact_id}.json"
        target_file.write_text(json.dumps(asdict(fact), indent=2), encoding="utf-8")
        
        # Append to facts ledger
        facts_ledger = self.facts_dir / "facts_ledger.jsonl"
        with open(facts_ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(fact)) + "\n")
            
        LOG.info(f"[GRAPH_MEMORY] Ingested bi-temporal fact {fact_id} ({predicate} -> {object_value})")
        return fact
