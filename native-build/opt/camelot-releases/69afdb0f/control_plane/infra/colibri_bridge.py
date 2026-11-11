# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
# SPDX-License-Identifier: MIT
"""Colibri MoE Infrastructure Bridge for Camelot-OS Control Plane.

Exposes Colibri MoE disk-streaming runtime as a unified service for Camelot-OS
reasoning orchestrators, Knight harnesses, and local LLM dispatch.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("camelot.infra.colibri_bridge")


def _get_streamer_module():
    return importlib.import_module("01_KERNEL.reasoning.colibri_moe_streamer")


@dataclass
class ColibriInferenceRequest:
    """Inference request payload for Colibri MoE Streamer."""
    prompt_tokens: List[int]
    max_tokens: int = 32
    temperature: float = 0.0
    gbnf_grammar: Optional[str] = None
    stream_response: bool = False


@dataclass
class ColibriInferenceResponse:
    """Inference response and performance telemetry from Colibri MoE Streamer."""
    generated_tokens: List[int]
    tokens_count: int
    telemetry: Dict[str, Any]
    model_name: str


class ColibriBridgeService:
    """Control Plane Bridge managing the Colibri MoE Streaming Engine."""

    def __init__(self, config_overrides: Optional[Dict[str, Any]] = None) -> None:
        streamer_mod = _get_streamer_module()
        cfg_kwargs = config_overrides or {}
        self.config = streamer_mod.ColibriConfig(**cfg_kwargs)
        self.runtime = streamer_mod.ColibriMoEStreamerRuntime(self.config)
        self._planner = streamer_mod.ColibriResourcePlanner

    def get_hardware_plan(self) -> Dict[str, Any]:
        """Compute the 744B memory layout and disk streaming plan."""
        report = self._planner.plan_model(self.config)
        return {
            "model_name": report.model_name,
            "total_params_b": report.total_params_b,
            "dense_params_b": report.dense_params_b,
            "moe_params_b": report.moe_params_b,
            "dense_resident_bytes": report.dense_resident_bytes,
            "expert_single_bytes": report.expert_single_bytes,
            "hot_store_ram_bytes": report.hot_store_ram_bytes,
            "kv_cache_per_token_bytes": report.kv_cache_per_token_bytes,
            "max_context_tokens_in_ram": report.max_context_tokens_in_ram,
            "projected_resident_ram_gb": report.projected_resident_ram_gb,
            "fits_ram_budget": report.fits_ram_budget,
            "storage_footprint_gb": report.storage_footprint_gb,
        }

    def execute_reasoning(self, req: ColibriInferenceRequest) -> ColibriInferenceResponse:
        """Run speculative MoE generation with MTP and GBNF grammar guidance."""
        if req.gbnf_grammar:
            self.runtime.set_grammar(req.gbnf_grammar)

        tokens = self.runtime.generate(
            prompt_tokens=req.prompt_tokens,
            max_new_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        telemetry = self.runtime.get_telemetry()
        return ColibriInferenceResponse(
            generated_tokens=tokens,
            tokens_count=len(tokens),
            telemetry=telemetry,
            model_name=self.config.model_name,
        )

    def trigger_repin_pass(self, layer: int) -> Optional[Dict[str, Any]]:
        """Trigger dynamic LFRU cache re-pinning on the specified layer."""
        return self.runtime.cache.repin_pass(layer)

    def persist_kv_cache(self, filepath: str) -> int:
        """Persist compressed MLA KV cache to disk using COLIKV1 binary format."""
        return self.runtime.kv_cache.serialize_to_disk(filepath)

    def load_kv_cache(self, filepath: str) -> int:
        """Load compressed MLA KV cache from COLIKV1 binary file."""
        streamer_mod = _get_streamer_module()
        loaded = streamer_mod.CompressedKVCache.load_from_disk(self.config, filepath)
        self.runtime.kv_cache = loaded
        return loaded.length()
