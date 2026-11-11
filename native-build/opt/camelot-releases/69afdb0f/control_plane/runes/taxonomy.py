# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Taxonomy Ledger — Unified Semantic Maps for Omni-Router
=======================================================
Consolidates intent categories, routing keywords, terminal maps, and
privacy configurations for both semantic and runic dispatchers.
"""
from enum import Enum


class IntentCategory(Enum):
    FORGE        = "forge"        # implement, build, scaffold
    CODE         = "code"         # debug, fix, refactor, review
    RESEARCH     = "research"     # search, explain, look up
    MEMORY       = "memory"       # recall, context, history
    OPS          = "ops"          # status, metrics, health, factory
    SECURITY     = "security"     # audit, scan, armor
    VOICE        = "voice"        # tts, audio, speak (cascaded pipeline)
    NATIVE_AUDIO = "native_audio" # omni realtime audio (GPT-4o/Gemini Live)
    GENERAL      = "general"      # fallback

# Ordered keyword lists — first match wins within each category
INTENT_KEYWORDS: dict[IntentCategory, list[str]] = {
    IntentCategory.FORGE: [
        "forge", "implement", "build", "create", "generate", "scaffold",
        "write code", "develop", "author", "draft",
    ],
    IntentCategory.CODE: [
        "debug", "fix", "refactor", "review code", "test", "error",
        "bug", "exception", "trace", "lint", "syntax",
    ],
    IntentCategory.RESEARCH: [
        "search", "find", "look up", "research", "what is", "explain",
        "summarize", "analyze", "investigate", "survey",
    ],
    IntentCategory.MEMORY: [
        "remember", "recall", "memory", "context", "history",
        "stored", "ledger", "archive", "retrieve",
    ],
    IntentCategory.OPS: [
        "status", "metrics", "health", "monitor", "throughput",
        "uptime", "factory", "dashboard", "telemetry", "alerts",
    ],
    IntentCategory.SECURITY: [
        "audit", "scan", "security", "vulnerability", "sentinel",
        "armor", "threat", "exploit", "secrets", "compliance",
    ],
    IntentCategory.VOICE: [
        "speak", "tts", "audio", "voice", "say", "pronounce",
        "synthesize", "narrate", "kitten",
    ],
    IntentCategory.NATIVE_AUDIO: [
        "realtime audio", "omni", "native audio", "live voice", "audio-in",
        "voice call", "webrtc", "livekit", "gemini live", "gpt-4o realtime",
        "no text", "direct audio",
    ],
}

# Preferred terminal IDs per category — ordered by priority (first = most preferred)
INTENT_TERMINAL_MAP: dict[IntentCategory, list[str]] = {
    IntentCategory.FORGE:    ["sir_boris", "sir_forge_master", "sir_forge", "sir_gravity", "sir_helio"],
    IntentCategory.CODE:     ["sir_boris", "sir_codex", "sir_hermes", "sir_forge"],
    IntentCategory.RESEARCH: ["sir_helio", "sir_kimi", "sir_mnemo", "sir_boris"],
    IntentCategory.MEMORY:   ["sir_mnemo", "sir_helio", "sir_boris"],
    IntentCategory.OPS:      ["sir_octavian", "sir_link", "sir_boris"],
    IntentCategory.SECURITY: ["sir_sentinel", "sir_gideon", "sir_ghost"],
    IntentCategory.VOICE:        ["sir_sonus", "sir_link", "sir_boris"],
    IntentCategory.NATIVE_AUDIO: ["sir_link", "sir_helio", "sir_alex"],
    IntentCategory.GENERAL:      ["sir_alex", "sir_boris", "sir_helio", "sir_link"],
}

# Universal privacy keywords that instantly trigger SIR_GHOST air-gap override
PRIVACY_KEYWORDS: frozenset[str] = frozenset({"secret", "local", "private", "credential", "key", "password"})

# Fallback semantic routing overrides for soul_router scoring
KEYWORD_ROUTES: dict[str, str] = {
    "orchestration": "sir_boris", "architecture": "sir_boris", "vocal": "sir_boris",
    "cognitive": "sir_alex", "reasoning": "sir_alex", "critical": "sir_alex",
    "bridge": "sir_link", "ui": "sir_link",
    "memory": "sir_mnemo", "archive": "sir_mnemo", "recall": "sir_mnemo",
    "technical": "sir_forge", "code_gen": "sir_forge",
    "agentforge": "sir_forge_master", "swarm_forge": "sir_forge_master", "forge_swarm": "sir_forge_master",
    "agent_spawn": "sir_forge_master", "phial_sync": "sir_forge_master", "swarm_orchestrate": "sir_forge_master",
    "security_review": "sir_sentinel", "audit": "sir_sentinel",
    "velocity": "sir_codex", "prototype": "sir_codex",
    "1m_context": "sir_helio", "cloud_burst": "sir_helio",
    "ouroboros": "sir_ouroboros", "mamba": "sir_ouroboros", "infinite_context": "sir_ouroboros",
    "bifrost": "sir_heimdall", "mesh": "sir_heimdall", "sentinel": "sir_heimdall", "zero_trust": "sir_heimdall",
    "openclaw": "sir_openclaw", "trend_research": "sir_openclaw",
    "rustclaw": "sir_rustclaw", "cmyk": "sir_rustclaw",
    "shopify": "sir_hermes", "graphql": "sir_hermes", "webhook": "sir_hermes",
    "nanobot": "lady_nanobot", "nfc": "lady_nanobot", "webgl": "lady_nanobot",
    "zeroclaw": "sir_zeroclaw", "trademark": "sir_zeroclaw", "affiliate_abuse": "sir_zeroclaw",
}
