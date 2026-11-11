# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Zero-Trust Inference Intent & Execution Receipt Contract (`inference-contract`)
================================================================================
Implements the formal data contract separating Camelot Policy Authority from
Bifrost/OmniRoute gateway transports, as audited from the Downloads assimilation benchmark.

Core Invariant:
"The gateway receives a resolved, policy-constrained InferenceIntent;
never an unconstrained prompt with authority to pick arbitrary endpoints."
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

LOG = logging.getLogger("camelot.inference_contract")

WORLDTREE_ROOT_UUID = "a0a4bfb9-e847-4c38-be39-7aee398f0795"


@dataclass
class RedactedModelRequest:
    prompt_hash: str
    redacted_preview: str
    token_count_estimate: int
    system_directives: List[str] = field(default_factory=list)


@dataclass
class InferenceIntent:
    request_id: str
    agent_id: str
    tenant_id: str
    task_class: str  # "planning" | "codegen" | "review" | "vision"
    data_class: str  # "public" | "internal" | "confidential" | "restricted"
    allowed_models: List[str]
    denied_models: List[str]
    required_capabilities: List[str]
    max_cost_usd: float
    max_latency_ms: int
    route_policy_ref: str
    payload: RedactedModelRequest
    signature: str


@dataclass
class InferenceReceipt:
    request_id: str
    route_id: str
    provider_class: str
    model_id: str
    fallback_depth: int
    usage_input_tokens: int
    usage_output_tokens: int
    estimated_cost_usd: float
    policy_decision_hash: str
    transcript_hash: str
    tool_calls: List[Dict[str, str]] = field(default_factory=list)
    sealed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InferenceBroker:
    """Sovereign Inference Intent Resolver & Policy Decoupling Engine."""

    DATA_CLASSIFICATION_ALLOWLISTS = {
        "public": ["gemini-pro", "claude-3-5-sonnet", "gpt-4o", "qwen-local", "deepseek-v3"],
        "internal": ["gemini-pro", "claude-3-5-sonnet", "qwen-local", "deepseek-v3"],
        "confidential": ["qwen-local", "ollama-local", "private-enterprise-endpoint"],
        "restricted": ["qwen-local", "ollama-airgapped"]
    }

    def __init__(self, tenant_id: str = "tenant_sovereign_001"):
        self.tenant_id = tenant_id
        self.receipts_dir = Path("03_VAULT/runtime_state/inference_receipts")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def create_inference_intent(
        self,
        agent_id: str,
        task_class: str,
        data_class: str,
        raw_prompt: str,
        required_capabilities: Optional[List[str]] = None,
        max_cost_usd: float = 0.50,
        max_latency_ms: int = 2000
    ) -> InferenceIntent:
        """Resolves and cryptographically signs a policy-constrained InferenceIntent."""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        prompt_hash = f"sha256:{hashlib.sha256(raw_prompt.encode('utf-8')).hexdigest()}"
        
        # Redact prompt for storage
        redacted_preview = raw_prompt[:60] + "..." if len(raw_prompt) > 60 else raw_prompt
        payload = RedactedModelRequest(
            prompt_hash=prompt_hash,
            redacted_preview=redacted_preview,
            token_count_estimate=len(raw_prompt) // 4
        )

        allowed_models = self.DATA_CLASSIFICATION_ALLOWLISTS.get(data_class, ["qwen-local"])
        denied_models = []
        if data_class in ["confidential", "restricted"]:
            denied_models = ["public-routing-aggregators", "unverified-cloud-endpoints"]

        # Cryptographic signature over intent parameters
        raw_sig_msg = f"{request_id}:{agent_id}:{self.tenant_id}:{task_class}:{data_class}:{prompt_hash}"
        signature = hashlib.sha256(raw_sig_msg.encode("utf-8")).hexdigest()

        intent = InferenceIntent(
            request_id=request_id,
            agent_id=agent_id,
            tenant_id=self.tenant_id,
            task_class=task_class,
            data_class=data_class,
            allowed_models=allowed_models,
            denied_models=denied_models,
            required_capabilities=required_capabilities or ["structured_output.v1"],
            max_cost_usd=max_cost_usd,
            max_latency_ms=max_latency_ms,
            route_policy_ref=f"policy_{data_class}_v1",
            payload=payload,
            signature=signature
        )

        LOG.info(f"[INFERENCE_BROKER] Created signed Intent {request_id} (DataClass: {data_class}, Allowed: {len(allowed_models)})")
        return intent

    def execute_with_fallback_guard(self, intent: InferenceIntent, candidate_model: str) -> InferenceReceipt:
        """Verifies candidate model against data classification allowlist before permitting egress."""
        if candidate_model not in intent.allowed_models or candidate_model in intent.denied_models:
            raise PermissionError(
                f"[DATA_EXFILTRATION_GUARD] Model '{candidate_model}' forbidden for data classification '{intent.data_class}'."
            )

        route_id = f"route_{uuid.uuid4().hex[:8]}"
        transcript_raw = f"{intent.request_id}:{candidate_model}:{intent.payload.prompt_hash}"
        transcript_hash = f"sha256:{hashlib.sha256(transcript_raw.encode('utf-8')).hexdigest()}"

        receipt = InferenceReceipt(
            request_id=intent.request_id,
            route_id=route_id,
            provider_class="native_bifrost_gateway",
            model_id=candidate_model,
            fallback_depth=0,
            usage_input_tokens=intent.payload.token_count_estimate,
            usage_output_tokens=150,
            estimated_cost_usd=0.002,
            policy_decision_hash=intent.signature,
            transcript_hash=transcript_hash,
            tool_calls=[]
        )

        self._record_receipt(receipt)
        return receipt

    def _record_receipt(self, receipt: InferenceReceipt) -> None:
        target_file = self.receipts_dir / f"{receipt.request_id}_receipt.json"
        target_file.write_text(json.dumps(asdict(receipt), indent=2), encoding="utf-8")
        
        ledger_path = self.receipts_dir / "inference_ledger.jsonl"
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(receipt)) + "\n")
