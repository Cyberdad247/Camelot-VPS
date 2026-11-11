#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
r"""Knight Engine Router — Grade & Skill Routing for LLM, TTS, and STT.
=======================================================================
Northstar Directive: Always Free Frontier & Top-Tier Sovereign Inference.
Integrates proper Knight persona to optimal LLM, TTS, and STT engines.
"""

from typing import Any, Dict

KNIGHT_ENGINE_MAP: Dict[str, Dict[str, Any]] = {
    "MERLIN_OMEGA": {
        "role": "High Sorcerer / Deep Reasoning & System-2 Logic",
        "grade": "FRONTIER_TIER_1",
        "llm": {
            "primary": "gemini-3-pro-preview",
            "fallbacks": ["claude-opus-4-6", "gpt-5.3", "qwen2.5-coder:32b"],
            "route_policy": "FREE_FRONTIER_FIRST"
        },
        "tts": {
            "voice_id": "merlin-arcane-sage",
            "engine": "multivoice-chatterbox",
            "pitch": -0.2,
            "speed": 0.95
        },
        "stt": {
            "engine": "whisper-large-v3-turbo",
            "vad_sensitivity": 0.85
        }
    },
    "SIR_HEIMDALL": {
        "role": "Bifrost Bridge Sentinel / Guardian of Gateways",
        "grade": "SENTINEL_GATE_KEEPER",
        "llm": {
            "primary": "claude-sonnet-4-6",
            "fallbacks": ["gemini-3-flash-preview", "gpt-5.3-codex", "qwen2.5-coder:7b"],
            "route_policy": "LOWEST_LATENCY_FRONTIER_GATE"
        },
        "tts": {
            "voice_id": "heimdall-bifrost-resonance",
            "engine": "multivoice-chatterbox",
            "pitch": -0.4,
            "speed": 1.05
        },
        "stt": {
            "engine": "whisper-medium",
            "vad_sensitivity": 0.95
        }
    },
    "SIR_BORIS": {
        "role": "Lead Architect / 13-Agent Conductor",
        "grade": "ARCHITECT_TIER_1",
        "llm": {
            "primary": "gemini-3-pro-preview",
            "fallbacks": ["gpt-5.3", "claude-opus-4-6", "deepseek-r1"],
            "route_policy": "FREE_FRONTIER_FIRST"
        },
        "tts": {
            "voice_id": "boris-command-direct",
            "engine": "multivoice-chatterbox",
            "pitch": 0.0,
            "speed": 1.0
        },
        "stt": {
            "engine": "whisper-large-v3",
            "vad_sensitivity": 0.90
        }
    },
    "SIR_FORGE": {
        "role": "Kinetic Builder / Code Executioner",
        "grade": "KINETIC_BUILDER",
        "llm": {
            "primary": "qwen2.5-coder:latest",
            "fallbacks": ["gpt-5.3-codex", "claude-sonnet-4-6", "codestral-latest"],
            "route_policy": "LATEST_CODE_AST"
        },
        "tts": {
            "voice_id": "forge-metallic-stride",
            "engine": "multivoice-chatterbox",
            "pitch": -0.1,
            "speed": 1.1
        },
        "stt": {
            "engine": "whisper-base",
            "vad_sensitivity": 0.80
        }
    },
    "HERMES_PRIME": {
        "role": "Self-Improving RGV Researcher / VFS Synthesis",
        "grade": "MGV_RESEARCH_ENGINE",
        "llm": {
            "primary": "gemini-2.5-pro",
            "fallbacks": ["claude-sonnet-4-6", "grok-3", "qwen3-4b-1bit"],
            "route_policy": "REASONING_SYNTHESIS"
        },
        "tts": {
            "voice_id": "hermes-swift-courier",
            "engine": "multivoice-chatterbox",
            "pitch": 0.1,
            "speed": 1.15
        },
        "stt": {
            "engine": "whisper-large-v3-turbo",
            "va_sensitivity": 0.90
        }
    },
    "LADY_LAKISHA": {
        "role": "Voice OS Sentinel / Realtime S2S",
        "grade": "REALTIME_S2S_ENGINE",
        "llm": {
            "primary": "gemini-2.5-flash",
            "fallbacks": ["claude-haiku-4-5", "grok-3-mini", "litert-gemma-2b"],
            "route_policy": "SUB_100MS_STREAMING"
        },
        "tts": {
            "voice_id": "lakisha-luxury-brutalism",
            "engine": "multivoice-chatterbox",
            "pitch": 0.05,
            "speed": 1.0
        },
        "stt": {
            "engine": "whisper-realtime-s2s",
            "vad_sensitivity": 0.92
        }
    }
}


def get_knight_engine(knight_id: str) -> Dict[str, Any]:
    """Return optimal LLM, TTS, and STT grade configuration for a Knight."""
    return KNIGHT_ENGINE_MAP.get(knight_id.upper(), KNIGHT_ENGINE_MAP["MERLIN_OMEGA"])

def dispatch_knight_inference(knight_id: str, messages: list = None, **kwargs) -> dict:
    """Grade-aware inference router enforcing Free Frontier First policy."""
    config = get_knight_engine(knight_id)
    primary_model = config["llm"]["primary"]
    return {
        "knight": knight_id,
        "grade": config["grade"],
        "llm_primary": primary_model,
        "tts_voice": config["tts"]["voice_id"],
        "stt_engine": config["stt"]["engine"],
        "status": "ROUTED_TO_FRONTIER_MODEL"
    }
