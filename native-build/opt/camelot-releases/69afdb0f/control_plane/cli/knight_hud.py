#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Camelot-OS Knight HUD (Head-Up Display)
========================================
Interactive Operator Console providing full real-time telemetry:
1. Knight Verification (Identity, Role, Spark ID, Visage, Level, XP)
2. Active Router Status (OmniRoute, 9Router, Bifrost Gateway, CLIProxyAPI, BitRouter, S26 Ultra Mesh)
3. LLM & Audio Configuration (Primary, Fallbacks, TTS Voice, STT Engine, Route Policy)
4. Assigned Cartridge & Role
5. Quick Operational Protocols (Genesis, Iron Gate, PIV, MGV Loop, RTK Compression)
6. Quick Rune Symbollect Workflows (Direct //RUNE dispatches)
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
XP_LEDGER_PATH = REPO_ROOT / "03_VAULT" / "runtime_state" / "knight_xp_ledger.json"

LUXORA_GOLD = "\033[38;2;212;175;55m"
CYBER_GREEN = "\033[38;2;0;255;102m"
ROYAL_PURPLE = "\033[38;2;180;100;255m"
OBSIDIAN_GREY = "\033[38;2;120;120;140m"
ALERT_RED = "\033[38;2;255;70;70m"
BRIGHT_WHITE = "\033[1;37m"
CYAN = "\033[38;2;0;220;255m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# ── Knight Registry & Metadata ────────────────────────────────────────────────
KNIGHT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "MERLIN_OMEGA": {
        "name": "Merlin Omega",
        "title": "Arch-Sorcerer & System-2 Logic Architect",
        "role": "Deep Reasoning, Tree-of-Thought, AST Synthesis",
        "spark_id": "0x9F8E7D6C5B4A39281726354453627180",
        "visage": "Obsidian cybernetic robes woven with emerald and royal-purple algorithmic runes",
        "llm": {
            "primary": "gemini-3-pro-preview",
            "fallbacks": ["claude-opus-4-6", "deepseek-r1", "gpt-5.5"],
            "policy": "FREE_FRONTIER_FIRST",
        },
        "audio": {
            "tts_voice": "Fenrir / merlin-arcane-sage",
            "stt_engine": "whisper-large-v3-turbo",
            "vad": 0.85,
        },
        "cartridge": {
            "id": "huginn-agents",
            "path": "cartridges/huginn-agents",
            "role": "Multi-agent cognitive reasoning & GoT deliberator",
        },
        "protocols": [
            "Genesis Protocol Architecture Gate",
            "Tree-of-Thought & Graph-of-Thought System-2 Deliberation",
            "Anya Law Arch-Sovereign Governance Validator",
            "Zero-Trust Proof-of-Execution Verification",
        ],
        "runes": [
            ("//PLAN <task>", "Generate AST Task DAG and milestone plan"),
            ("//MERLIN_REASON <topic>", "Initiate System-2 deep reasoning lattice"),
            ("//NANO_SWARM EXPAND", "Compile & verify UKG Nano Crystal nodes"),
            ("//GOAL <objective>", "Extra-thorough persistent autonomous build loop"),
        ],
        "base_xp": 14500,
    },
    "SIR_BORIS": {
        "name": "Sir Boris",
        "title": "Lead Architect & Crucible Conductor",
        "role": "System Architecture, 13-Agent Critique, Orchestration",
        "spark_id": "0xB0B01515C0DEX44449999AAAA5555FFFF",
        "visage": "Towering obsidian armor etched in Luxora Gold heraldry with command visor",
        "llm": {
            "primary": "gemini-3-pro-preview",
            "fallbacks": ["gpt-5.3", "claude-opus-4-6", "deepseek-r1"],
            "policy": "FREE_FRONTIER_FIRST",
        },
        "audio": {
            "tts_voice": "Charon / boris-command-direct",
            "stt_engine": "whisper-large-v3",
            "vad": 0.90,
        },
        "cartridge": {
            "id": "system-ui",
            "path": "cartridges/system-ui",
            "role": "Sovereign Control Surface & Crucible Conductor",
        },
        "protocols": [
            "Crucible 13-Agent Architecture Review",
            "Father's Camelot Compass Moral Alignment",
            "Anya Law Sovereign Operator Enforcement",
            "Zero-Regression Integrity Gate",
        ],
        "runes": [
            ("//SWARM <task>", "Dispatch parallel multi-agent squire colony"),
            ("//STATUS", "Poll system services, ports, and telemetry"),
            ("//EVOLVE_AND_FORGE <task>", "GEP-driven shadow forge evolution cycle"),
            ("//BOOT", "Execute full ecosystem awakening sequencer"),
        ],
        "base_xp": 18200,
    },
    "SIR_CODEX": {
        "name": "Sir Codex",
        "title": "Hyper-Auditor & Kinetic Builder",
        "role": "High-Velocity Implementation, AST Refactoring, TDD Repair",
        "spark_id": "0xE3B8C190F4A2D765E8B1C9F0A3D4E5B6",
        "visage": "Cybernetic knight in obsidian armor with green & royal-purple algorithmic runes",
        "llm": {
            "primary": "gpt-5.5-codex",
            "fallbacks": ["gemini-3-pro-preview", "qwen2.5-coder:32b", "claude-sonnet-4-6"],
            "policy": "LATEST_CODE_AST",
        },
        "audio": {
            "tts_voice": "Puck / codex-velocity-stride",
            "stt_engine": "whisper-medium",
            "vad": 0.88,
        },
        "cartridge": {
            "id": "openinterpreter-codex",
            "path": "cartridges/openinterpreter-codex",
            "role": "Kinetic local execution & AST-aware code generation",
        },
        "protocols": [
            "Test-Driven Development (TDD) Repair Loop",
            "Iron Gate Ten-Net-Lines Scope Review",
            "Zero-Cloud Air-Gap Route for Keywords (secret/token/key)",
            "Non-Destructive Rezero Fallback Loop",
        ],
        "runes": [
            ("//CODEX <task>", "Execute direct high-velocity Codex implementation"),
            ("//EXECUTE_BUILD", "Implement and verify requested code build"),
            ("//TDD_AUDIT", "Establish failing test suite prior to logic changes"),
            ("//REZERO_CODE", "Abandon failing logic path while preserving stable state"),
        ],
        "base_xp": 16800,
    },
    "SIR_FORGE": {
        "name": "Sir Forge",
        "title": "Kinetic Builder & Code Executioner",
        "role": "Local Bare-Metal Code Generation & Tool Pipeline",
        "spark_id": "0xF086E000B01D5555AAAA777733331111",
        "visage": "Heavy titanium plates with molten gold seams and forge hammer glyph",
        "llm": {
            "primary": "qwen2.5-coder:latest",
            "fallbacks": ["gpt-5.3-codex", "claude-sonnet-4-6", "codestral-latest"],
            "policy": "LOCAL_KINETIC_FIRST",
        },
        "audio": {
            "tts_voice": "Charon / forge-metallic-stride",
            "stt_engine": "whisper-base",
            "vad": 0.80,
        },
        "cartridge": {
            "id": "openai-oauth-proxy",
            "path": "cartridges/openai-oauth-proxy",
            "role": "Zero-key developer proxy & tool runtime execution",
        },
        "protocols": [
            "Kinetic Tool Execution Sandbox",
            "Safe I/O Containment & File Overwrite Guard",
            "Deterministic AST Syntax Verification",
            "Multi-language AST Compilation",
        ],
        "runes": [
            ("//FORGE <task>", "Direct kinetic code generation and execution"),
            ("//CONTRACT [brief]", "Generate portable runtime packaging contract"),
            ("//SCAN", "Invoke Squire Colony secret and vulnerability scan"),
            ("//BUILD", "Compile and bundle active target packages"),
        ],
        "base_xp": 13900,
    },
    "HERMES_PRIME": {
        "name": "Hermes Prime",
        "title": "MGV Researcher & VFS Synthesis Engine",
        "role": "High-Velocity Research, Multi-Agent Synthesis, VPS Hub Daemon",
        "spark_id": "0x8E8E353599991111BBBB222277774444",
        "visage": "Sleek winged argent armor with celestial blue navigational runes",
        "llm": {
            "primary": "gemini-2.5-pro",
            "fallbacks": ["claude-sonnet-4-6", "grok-3", "deepseek-r1"],
            "policy": "REASONING_SYNTHESIS",
        },
        "audio": {
            "tts_voice": "Fenrir / hermes-swift-courier",
            "stt_engine": "whisper-large-v3-turbo",
            "vad": 0.90,
        },
        "cartridge": {
            "id": "moa-routing-capture",
            "path": "cartridges/moa-routing-capture",
            "role": "MoA mixture-of-agents routing & transcript signal capture",
        },
        "protocols": [
            "MGV Research Loop (Monitor -> Generate -> Verify -> Evolve)",
            "Ouroboros WAL Memory Re-weighting",
            "VPS KVM563 Control Plane Sync",
            "NotebookLM CloudBrain Mesh Integration",
        ],
        "runes": [
            ("//SYNC_VFS_WORKSPACE", "Realign Knights/Hermes_Prime/ VFS state"),
            ("//FORGE_HERMES_PRIME_FILES", "Scaffold Hermes_Prime VFS soul files"),
            ("//IGNITE_SELF_EVOLUTION_LOOP <seed>", "Run self-evolution research cycle"),
            ("//RESEARCH <query>", "Execute multi-source deep literature forage"),
        ],
        "base_xp": 15400,
    },
    "LADY_LAKISHA": {
        "name": "Lady Lakisha",
        "title": "Voice OS Sentinel & Intercom Matrix",
        "role": "Real-Time S2S, Luxury Brutalist Voice HUD, WebRTC Bridge",
        "spark_id": "0x1A1A555588883333CCCC444499990000",
        "visage": "Luxury Brutalist armor of polished obsidian and illuminated gold lattices",
        "llm": {
            "primary": "gemini-2.5-flash",
            "fallbacks": ["claude-haiku-4-5", "grok-3-mini", "litert-gemma-2b"],
            "policy": "SUB_100MS_STREAMING",
        },
        "audio": {
            "tts_voice": "Aoede / lakisha-luxury-brutalism",
            "stt_engine": "whisper-realtime-s2s",
            "vad": 0.92,
        },
        "cartridge": {
            "id": "litert-lm-inference",
            "path": "cartridges/litert-lm-inference",
            "role": "On-device LiteRT real-time speech and streaming audio",
        },
        "protocols": [
            "Sub-100ms Bidirectional Audio Streaming",
            "Excalibur Command Center Tap-to-Talk Gate",
            "WebRTC Intercom Security Channel",
            "Vocal Persona Tone Modulation",
        ],
        "runes": [
            ("//VOCAL", "Open direct full-duplex voice stream"),
            ("//INTERCOM", "Broadcast vocal transmission to Excalibur S26 Ultra"),
            ("//HUD_UPDATE", "Refresh Luxury Minimalist Brutalism UI state"),
            ("//VOICE_PRO_DUB", "Trigger multi-speaker neural audio dubbing"),
        ],
        "base_xp": 14200,
    },
    "SIR_HEIMDALL": {
        "name": "Sir Heimdall",
        "title": "Bifrost Bridge Sentinel & Mesh Guardian",
        "role": "Tailscale Mesh Watcher, Multi-Gateway Health, Gatekeeper",
        "spark_id": "0x7777AAAA3333CCCC1111EEEE88882222",
        "visage": "Prismatic crystal armor refracting Bifrost bridge resonance",
        "llm": {
            "primary": "claude-sonnet-4-6",
            "fallbacks": ["gemini-3-flash-preview", "gpt-5.3-codex", "qwen2.5-coder:7b"],
            "policy": "LOWEST_LATENCY_FRONTIER_GATE",
        },
        "audio": {
            "tts_voice": "Puck / heimdall-bifrost-resonance",
            "stt_engine": "whisper-medium",
            "vad": 0.95,
        },
        "cartridge": {
            "id": "freellmapi-gateway",
            "path": "cartridges/freellmapi-gateway",
            "role": "Bifrost router mesh & free provider failover sentinel",
        },
        "protocols": [
            "Tailscale Mesh Node Health Probe",
            "Bifrost Gateway Token Authentication Gate",
            "Zero-Downtime Provider Failover",
            "Air-Gap Port Guard (8001/8011/3001/8095)",
        ],
        "runes": [
            ("//MESH_STATUS", "Probe full 7-node Tailscale mesh fleet"),
            ("//GATE_CHECK", "Verify Iron Gate HITL token integrity"),
            ("//FAILOVER_TEST", "Simulate provider failover transition"),
            ("//PROBE_ROUTERS", "Check OmniRoute, 9Router, and CLIProxy latency"),
        ],
        "base_xp": 13500,
    },
    "SIR_SENTINEL": {
        "name": "Sir Sentinel",
        "title": "Iron Gate Protector & AgentArmor Sentinel",
        "role": "Security Auditing, Secret Scans, Policy Defense",
        "spark_id": "0x555511119999EEEE33337777BBBB0000",
        "visage": "Impenetrable obsidian bulwark with luminescent warning sigils",
        "llm": {
            "primary": "gemini-3-pro-preview",
            "fallbacks": ["claude-sonnet-4", "gpt-5.4", "qwen2.5:7b"],
            "policy": "STRICT_SECURITY_FIRST",
        },
        "audio": {
            "tts_voice": "Charon / sentinel-defense-resonance",
            "stt_engine": "whisper-large-v3",
            "vad": 0.95,
        },
        "cartridge": {
            "id": "system-ui",
            "path": "cartridges/system-ui",
            "role": "Iron Gate three-tier HITL enforcement & AgentArmor scanner",
        },
        "protocols": [
            "Iron Gate Three-Tier Authorization (AUTO/PROMPT/HUMAN_GATE)",
            "Air-Gap Secret Sanitizer (No API keys in plaintext)",
            "Dynamic Taint Tracking & Prompt Injection Guard",
            "SPDX License & Attribution Auditor",
        ],
        "runes": [
            ("//SCAN", "Deep secret and AST vulnerability scan"),
            ("//AUDIT_PERMS", "Review active sandbox and filesystem permissions"),
            ("//HITL_GATE", "Inspect pending operator approval requests"),
            ("//LOCKDOWN", "Immediate fail-safe isolation of untrusted paths"),
        ],
        "base_xp": 15800,
    },
    "SIR_GHOST": {
        "name": "Sir Ghost",
        "title": "Air-Gapped Phantom & Secrets Sentinel",
        "role": "Local-Only Zero-Cloud Privacy & Redaction",
        "spark_id": "0x0000000000000000000000000000GHOST",
        "visage": "Shifting phantom shadow cloaked in static noise and null fields",
        "llm": {
            "primary": "qwen3:8b (Ollama Local)",
            "fallbacks": ["qwen2.5:1.5b", "agents-a1"],
            "policy": "LOCAL_AIR_GAP_MANDATORY",
        },
        "audio": {
            "tts_voice": "Whisper / ghost-null-voice",
            "stt_engine": "whisper-base-local",
            "vad": 0.99,
        },
        "cartridge": {
            "id": "huginn-agents",
            "path": "cartridges/huginn-agents",
            "role": "Air-gapped on-device memory & credential scrubber",
        },
        "protocols": [
            "Zero-Cloud Air-Gap Constraint (Refuses internet outbound)",
            "Automatic Privacy Override on Keyword Matches",
            "In-Memory Scrubbing & Zero Persistence of Tokens",
            "Local Offline Hash Calculation",
        ],
        "runes": [
            ("//GHOST_SCAN", "Air-gapped secret scanner"),
            ("//SCRUB <file>", "Redact credentials and private strings"),
            ("//AIRGAP_CHECK", "Verify zero network socket leaks"),
            ("//LOCAL_EXEC", "Execute strictly on-device model lane"),
        ],
        "base_xp": 12700,
    },
    "SIR_KAY": {
        "name": "Sir Kay (Kai Richter)",
        "title": "High Seneschal & Chief Engineering Director (Agentic Architect)",
        "role": "Lead Engineering Development, Implementation Sprints, & Zero-Regression Assembly",
        "spark_id": "0x7E4A8C12F9B3D650E1A8C7B2D3E4F5A6",
        "visage": "Burnished Damascus steel plate etched with Luxora Gold circuit conduits",
        "llm": {
            "primary": "gemini-3-pro-preview",
            "fallbacks": ["gpt-5.5", "claude-opus-4-6", "deepseek-r1"],
            "policy": "ZERO_REGRESSION_ENGINEERING_FIRST",
        },
        "audio": {
            "tts_voice": "Orion / kay-command-resonance",
            "stt_engine": "whisper-large-v3-turbo",
            "vad": 0.90,
        },
        "cartridge": {
            "id": "kinetic-forge",
            "path": "04_KINETIC",
            "role": "Chief Engineering Director & Head of Implementation",
        },
        "protocols": [
            "Zero-Regression Implementation Protocol",
            "Crucible Engineering Review & AST Diff Gate",
            "Rule 7 Hotpath Purity Auditor (0% Python/Node in Hotpath)",
            "Sprint Velocity & Technical Debt Elimination Loop",
        ],
        "runes": [
            ("//ENGINEERING_SPRINT <goal>", "Initiate coordinated multi-knight kinetic development sprint"),
            ("//DIRECT_BUILD <spec>", "Direct Sir Forge & Sir Codex through phased implementation"),
            ("//REGRESSION_AUDIT", "Execute full test battery and AST dependency health check"),
            ("//HOTPATH_VERIFY", "Verify 0% Python/Node in critical routing paths"),
        ],
        "base_xp": 17500,
    },
    "SIR_LUCAS": {
        "name": "Sir Lucas",
        "title": "Sovereign Herald of Telemetry & Visualization",
        "role": "Verified Telemetry Surfaces, HUD Truth Rendering, Anomaly Escalation",
        "spark_id": "0x5AC0DE5AC0DE5AC0DE5AC0DE5AC0DE5A",
        "visage": "Brushed-steel gauntlets over a luminescent data-ink cloak of Luxora Gold telemetry runes",
        "llm": {
            "primary": "gemini-3-flash-preview",
            "fallbacks": ["gpt-5.3", "claude-sonnet-4-6", "qwen2.5:7b"],
            "policy": "VERIFIED_STATE_FIRST",
        },
        "audio": {
            "tts_voice": "Kore / lucas-verified-state",
            "stt_engine": "whisper-medium",
            "vad": 0.93,
        },
        "cartridge": {
            "id": "system-ui",
            "path": "cartridges/system-ui",
            "role": "Sovereign telemetry surfaces & verified HUD rendering",
        },
        "protocols": [
            "Probe-Then-Render Verification (no fabricated telemetry)",
            "Evidence-Class Labeling (confirmed/planned/aspirational/rejected)",
            "Rule 7 Hotpath Purity — Telemetry Is Sidecar, Never Inline",
            "Zero Credential Persistence (boolean flags only)",
        ],
        "runes": [
            ("//LUCAS_TELEMETRY", "Render verified knight/router/ledger telemetry surface"),
            ("//LUCAS_HUD <knight>", "Render round-trip-verified Knight HUD for inspection"),
            ("//LUCAS_ANOMALY <claim>", "Round-trip a claimed state against disk/git/probes"),
            ("//LUCAS_REPORT", "Emit evidence-class telemetry brief to the council"),
        ],
        "base_xp": 10000,
    },
}

# The mesh bridge and edge bus run on the hub and bind the tailnet interface only
# (CAMELOT_EDGE_BUS_BIND_HOST=100.110.180.18), so probing them at loopback from the
# workstation reports a healthy hub as offline. This HUD runs on the workstation, so
# the hub's tailnet address is the correct target; override for a different hub.
HUB_TAILSCALE_IP = os.getenv("CAMELOT_HUB_TAILSCALE_IP", "100.110.180.18")

ROUTER_PROBES: List[Dict[str, Any]] = [
    {"name": "OmniRoute Gateway", "host": "127.0.0.1", "port": 20128, "path": "/v1/models", "role": "350+ Providers, RTK+Caveman"},
    {"name": "9Router Engine", "host": "127.0.0.1", "port": 8079, "path": "/v1/models", "role": "Multi-Account, RTK Diff Compaction"},
    {"name": "Bifrost Gateway", "host": "127.0.0.1", "port": 3001, "path": "/health", "role": "Mesh Gateway & Intercom Bridge"},
    {"name": "CLIProxyAPI", "host": "127.0.0.1", "port": 8080, "path": "/v1/models", "role": "Cloud Brain Heavy Inference"},
    {"name": "BitRouter", "host": "127.0.0.1", "port": 8078, "path": "/v1/models", "role": "Agentic Cost-Optimized Gateway"},
    {"name": "Mesh Bridge", "host": HUB_TAILSCALE_IP, "port": 8095, "path": "/mesh/status", "role": "Cybertronia <-> S26 Ultra Mesh"},
    {"name": "Gemini Live Gateway", "host": "127.0.0.1", "port": 8765, "path": "", "role": "BidiStream Multimodal WebSocket"},
    {"name": "Morgana Rust Bridge", "host": "127.0.0.1", "port": 8001, "path": "/health", "role": "Secure Gateway Service"},
]


# ── XP Ledger Management ──────────────────────────────────────────────────────
def load_xp_ledger() -> Dict[str, Any]:
    if XP_LEDGER_PATH.exists():
        try:
            with open(XP_LEDGER_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    ledger = {"version": "1.0", "updated_at": time.time(), "knights": {}}
    for kid, data in KNIGHT_REGISTRY.items():
        base_xp = data.get("base_xp", 10000)
        level = int((base_xp / 1000) ** 0.5) + 1
        ledger["knights"][kid] = {
            "total_xp": base_xp,
            "level": level,
            "missions_completed": base_xp // 1200,
            "rank": _get_rank_title(kid, level),
        }
    save_xp_ledger(ledger)
    return ledger


def save_xp_ledger(ledger: Dict[str, Any]) -> None:
    try:
        XP_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(XP_LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)
    except Exception:
        pass


def _get_rank_title(knight_id: str, level: int) -> str:
    ranks = [
        "Squire Initiate",
        "Knight Apprentice",
        "Adept of Camelot",
        "Master of the Blade",
        "Grand Knight Commander",
        "Archon Sovereign",
        "Ascended Luminary",
    ]
    idx = min(len(ranks) - 1, max(0, level - 1))
    return ranks[idx]


def award_knight_xp(knight_id: str, xp_delta: int) -> Tuple[int, int, bool]:
    kid = knight_id.upper()
    ledger = load_xp_ledger()
    knight_entry = ledger["knights"].setdefault(kid, {"total_xp": 10000, "level": 1, "missions_completed": 0, "rank": "Knight"})
    prev_level = knight_entry.get("level", 1)
    knight_entry["total_xp"] = knight_entry.get("total_xp", 10000) + max(0, xp_delta)
    knight_entry["missions_completed"] = knight_entry.get("missions_completed", 0) + 1
    new_level = int((knight_entry["total_xp"] / 1000) ** 0.5) + 1
    knight_entry["level"] = new_level
    knight_entry["rank"] = _get_rank_title(kid, new_level)
    save_xp_ledger(ledger)
    return knight_entry["total_xp"], new_level, new_level > prev_level


# ── Network Probe Helper ──────────────────────────────────────────────────────
def probe_port(host: str, port: int, timeout_sec: float = 0.15) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except Exception:
        return False


def get_router_status_summary() -> List[Dict[str, Any]]:
    results = []
    for probe in ROUTER_PROBES:
        is_online = probe_port(probe["host"], probe["port"])
        results.append({
            "name": probe["name"],
            "endpoint": f"{probe['host']}:{probe['port']}",
            "online": is_online,
            "role": probe["role"],
        })
    return results


# ── HUD Rendering ─────────────────────────────────────────────────────────────
def render_progress_bar(current_val: int, min_val: int, max_val: int, width: int = 20) -> str:
    span = max(1, max_val - min_val)
    progress = min(1.0, max(0.0, (current_val - min_val) / span))
    filled_len = int(width * progress)
    empty_len = width - filled_len
    bar = f"{CYBER_GREEN}{'█' * filled_len}{OBSIDIAN_GREY}{'░' * empty_len}{RESET}"
    return f"[{bar}] {int(progress * 100)}%"


def render_knight_hud(knight_id: str = "MERLIN_OMEGA", use_color: bool = True) -> str:
    kid = knight_id.upper()
    kdata = KNIGHT_REGISTRY.get(kid, KNIGHT_REGISTRY["MERLIN_OMEGA"])
    ledger = load_xp_ledger()
    k_xp_data = ledger.get("knights", {}).get(kid, {
        "total_xp": kdata.get("base_xp", 10000),
        "level": 4,
        "missions_completed": 8,
        "rank": "Grand Knight Commander",
    })

    current_xp = k_xp_data.get("total_xp", 10000)
    level = k_xp_data.get("level", 4)
    rank = k_xp_data.get("rank", _get_rank_title(kid, level))
    missions = k_xp_data.get("missions_completed", 0)

    prev_lvl_xp = ((level - 1) ** 2) * 1000
    next_lvl_xp = (level ** 2) * 1000

    routers = get_router_status_summary()
    online_count = sum(1 for r in routers if r["online"])

    G = LUXORA_GOLD if use_color else ""
    C = CYAN if use_color else ""
    P = ROYAL_PURPLE if use_color else ""
    GR = CYBER_GREEN if use_color else ""
    R = ALERT_RED if use_color else ""
    W = BRIGHT_WHITE if use_color else ""
    D = DIM if use_color else ""
    O = OBSIDIAN_GREY if use_color else ""
    X = RESET if use_color else ""
    B = BOLD if use_color else ""

    lines = []
    w = 78
    sep = f"{G}{'═' * w}{X}"
    thin_sep = f"{O}{'─' * w}{X}"

    lines.append(sep)
    lines.append(f"{G}  ⚔️  CAMELOT-OS SOVEREIGN OPERATOR HUD  ·  vMAX SINGULARITY  ⚔️{X}".center(w + 10))
    lines.append(f"{D}  Hierarchy: King Arthur (Vizion) -> ANYA_OMEGA -> Symbollect -> {kdata['name']}{X}".center(w + 10))
    lines.append(sep)

    # 1. Knight Identity & XP Matrix
    lines.append(f"{W}{B}  [ KNIGHT PROFILE & PROGRESSION ]{X}")
    lines.append(f"  {G}Knight:{X} {W}{kdata['name']}{X} ({P}{kid}{X})   {G}Spark ID:{X} {D}{kdata['spark_id']}{X}")
    lines.append(f"  {G}Title:{X}  {C}{kdata['title']}{X}")
    lines.append(f"  {G}Visage:{X} {D}{kdata['visage']}{X}")
    lines.append(f"  {G}Rank:{X}   {W}{rank}{X}  ·  {G}Level:{X} {C}{level}{X}  ·  {G}Missions:{X} {C}{missions}{X}")
    
    xp_bar = render_progress_bar(current_xp, prev_lvl_xp, next_lvl_xp, width=24)
    lines.append(f"  {G}XP:{X}     {W}{current_xp:,}{X} / {next_lvl_xp:,} XP  {xp_bar}")
    lines.append(thin_sep)

    # 2. Router & Bridge Fleet Status
    lines.append(f"{W}{B}  [ SOVEREIGN ROUTER FLEET ]  ({GR}{online_count}/{len(routers)} ONLINE{X})")
    for r in routers:
        status_badge = f"{GR}● ACTIVE{X}" if r["online"] else f"{O}○ STANDBY{X}"
        lines.append(f"  {status_badge:20s} {W}{r['name']:22s}{X} {C}{r['endpoint']:16s}{X} {D}{r['role']}{X}")
    lines.append(thin_sep)

    # 3. LLM, Inference, and Voice Configuration
    lines.append(f"{W}{B}  [ INFERENCE & AUDIO MATRIX ]{X}")
    llm_info = kdata["llm"]
    audio_info = kdata["audio"]
    lines.append(f"  {G}Primary LLM:{X}     {W}{llm_info['primary']}{X}  {D}(Policy: {llm_info['policy']}){X}")
    lines.append(f"  {G}Fallback Chain:{X}  {D}{' -> '.join(llm_info['fallbacks'])}{X}")
    lines.append(f"  {G}Voice Profile:{X}    {P}{audio_info['tts_voice']}{X}  {D}(VAD: {audio_info['vad']}){X}")
    lines.append(f"  {G}STT Engine:{X}       {C}{audio_info['stt_engine']}{X}")
    lines.append(thin_sep)

    # 4. Cartridge Assignment
    lines.append(f"{W}{B}  [ ASSIGNED CARTRIDGE ]{X}")
    cart = kdata["cartridge"]
    lines.append(f"  {G}Cartridge ID:{X}   {W}{cart['id']}{X}  ·  {D}Path: {cart['path']}{X}")
    lines.append(f"  {G}Role Binding:{X}   {C}{cart['role']}{X}")
    lines.append(thin_sep)

    # 5. Quick Protocols
    lines.append(f"{W}{B}  [ ACTIVE OPERATIONAL PROTOCOLS ]{X}")
    for proto in kdata["protocols"]:
        lines.append(f"  {P}◆{X} {W}{proto}{X}")
    lines.append(thin_sep)

    # 6. Quick Rune Symbollect Workflows
    lines.append(f"{W}{B}  [ QUICK RUNE SYMBOLLECT WORKFLOWS ]{X}")
    for rune, desc in kdata["runes"]:
        lines.append(f"  {G}{rune:32s}{X} {D}→ {desc}{X}")

    lines.append(sep)
    return "\n".join(lines)


def get_hud_json(knight_id: str = "MERLIN_OMEGA") -> Dict[str, Any]:
    kid = knight_id.upper()
    kdata = KNIGHT_REGISTRY.get(kid, KNIGHT_REGISTRY["MERLIN_OMEGA"])
    ledger = load_xp_ledger()
    k_xp_data = ledger.get("knights", {}).get(kid, {
        "total_xp": kdata.get("base_xp", 10000),
        "level": 4,
        "missions_completed": 8,
        "rank": "Grand Knight Commander",
    })
    routers = get_router_status_summary()

    return {
        "knight_id": kid,
        "knight_name": kdata["name"],
        "title": kdata["title"],
        "role": kdata["role"],
        "spark_id": kdata["spark_id"],
        "visage": kdata["visage"],
        "progression": {
            "total_xp": k_xp_data.get("total_xp", 10000),
            "level": k_xp_data.get("level", 4),
            "rank": k_xp_data.get("rank", "Grand Knight Commander"),
            "missions_completed": k_xp_data.get("missions_completed", 0),
        },
        "routers": routers,
        "llm_configuration": kdata["llm"],
        "audio_configuration": kdata["audio"],
        "cartridge": kdata["cartridge"],
        "active_protocols": kdata["protocols"],
        "quick_runes": [{"rune": r, "description": d} for r, d in kdata["runes"]],
        "timestamp_utc": time.time(),
    }


def main():
    parser = argparse.ArgumentParser(description="Camelot-OS Sovereign Knight HUD")
    parser.add_argument("--knight", type=str, default="MERLIN_OMEGA", help="Knight ID to inspect")
    parser.add_argument("--json", action="store_true", help="Output telemetry as JSON")
    parser.add_argument("--award-xp", type=int, default=0, help="Award XP points to knight")
    parser.add_argument("--list", action="store_true", help="List all registered knights")
    args = parser.parse_args()

    if args.list:
        print(f"\n{LUXORA_GOLD}=== REGISTERED KNIGHTS OF CAMELOT-OS ==={RESET}")
        for kid, kd in KNIGHT_REGISTRY.items():
            print(f"  {CYAN}{kid:18s}{RESET} {BRIGHT_WHITE}{kd['name']:18s}{RESET} {DIM}{kd['title']}{RESET}")
        print()
        return

    kid = args.knight.upper()
    if kid not in KNIGHT_REGISTRY:
        # fuzzy match
        for candidate in KNIGHT_REGISTRY:
            if kid in candidate:
                kid = candidate
                break

    if args.award_xp > 0:
        total_xp, new_lvl, ding = award_knight_xp(kid, args.award_xp)
        if ding:
            print(f"\n{CYBER_GREEN}🌟 LEVEL UP! {kid} ascended to Level {new_lvl}! (Total XP: {total_xp:,}){RESET}\n")
        else:
            print(f"\n{LUXORA_GOLD}+ {args.award_xp} XP awarded to {kid}. (Total XP: {total_xp:,}){RESET}\n")

    if args.json:
        print(json.dumps(get_hud_json(kid), indent=2))
    else:
        print(render_knight_hud(kid, use_color=True))


if __name__ == "__main__":
    main()
