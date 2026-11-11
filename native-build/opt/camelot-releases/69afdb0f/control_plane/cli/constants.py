# SPDX-License-Identifier: MIT

"""Shared constants, home detection, and help text for the Camelot-OS CLI."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Home detection
# ---------------------------------------------------------------------------

def _detect_home() -> Path:
    env = os.environ.get("CAMELOT_OS_HOME")
    if env and Path(env).is_dir():
        return Path(env)
    candidates = [
        Path.home() / "CAMELOT_OS",
        Path(__file__).resolve().parent.parent.parent,
    ]
    for candidate in candidates:
        if (candidate / "03_VAULT" / "training" / "configs" / "hud.py").exists():
            return candidate
    return Path(__file__).resolve().parent.parent.parent


CAMELOT_HOME = _detect_home()

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

STREAM_DELAY = float(os.getenv("CAMELOT_OS_STREAM_DELAY", "0.004"))
PROGRESS_DELAY = float(os.getenv("CAMELOT_OS_PROGRESS_DELAY", "0.12"))

# ---------------------------------------------------------------------------
# Runic / cartridge constants
# ---------------------------------------------------------------------------

BARE_SWARM_DIRECTIVE = "//SWARM"
BARE_SWARM_OBJECTIVE = "bootstrap swarm invoke sequence"
ACTIVE_CARTRIDGE_PATH = ".camelot/active_cartridge.txt"

MODE_CARTRIDGE_MAP: dict[str, str] = {
    "COGNITIVE": "COGNITIVE",
    "RESEARCH": "RESEARCH",
    "ENGINEER": "ENGINEER",
    "CREATIVE": "CREATIVE",
    "MARKETING": "MARKETING",
    "LEGAL": "LEGAL",
    "BRAINSTORM": "BRAINSTORM",
    "CRITICAL_THINKING": "CRITICAL_THINKING",
}

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

HELP_LINES: list[str] = [
    "Core commands:",
    "/who                 show active knight, provider, model, and last route",
    "/route <intent>      preview which knight and model will handle an intent",
    "/status              run Camelot health/status probes",
    "/hermes              show VPS Hermes_Prime and Bifrost bridge status",
    "/llm <model>         pin chat model",
    "/provider <name>     pin chat provider",
    "/chat [intent]       enter Sovereign Chat Interface",
    "/commands            show the full command surface",
    "/exit",
]

FULL_HELP_LINES: list[str] = [
    "Commands:",
    "/help or //HELP",
    "/who",
    "/commands",
    "/route <intent>",
    "/status",
    "/orchestrator [--mode <boot|status|knights|triage|persona|notify|awaken|conversation>]",
    "hermes [--json] [--probe-live]",
    "bifrost route <intent> [--json]",
    "bifrost status [--probe] [--json]",
    "bifrost validate [path] [--json]",
    "contracts validate [path] [--json]",
    "/memory <agent>",
    "/research <objective>",
    "/northstar <objective>",
    "/blueprint <objective>",
    "/precise <objective>",
    "/chat [intent] [--llm <model>] [--provider <name>]",
    "/llm <model>          (pin model)",
    "/provider <name>      (pin provider)",
    "/ledger-status",
    "glyph list",
    "glyph load thread_audit_max",
    "glyph activate [thread_audit_max]",
    "glyph expand <atom_id>",
    "glyph audit [atom_id]",
    "glyph execute <atom_id> [--approve]",
    "forge-unify activate",
    "forge-unify status",
    "forge-unify route <intent>",
    "forge-unify forensic-check [--refresh-baseline]",
    "/sarda <intent>",
    "team self-test",
    "codex status",
    "codex integrate [--actor <name>]",
    "codex sync",
    "bio-swarm status",
    "bio-swarm preflight",
    "bio-swarm once --fixture",
    "nano-swarm status",
    "nano-swarm supervise <status|start|stop|restart> [--node <name>]",
    "microcubed status",
    'microcubed plan "objective" --knight sir_forge',
    'microcubed forge "objective" --knight sir_forge [--queue]',
    "microcubed inspect <house_id>",
    "microcubed execute <house_id> -- <command>",
    "microcubed teardown <house_id>",
    "cloudbrain config show",
    "cloudbrain config set <ENV_VAR> <url>",
    "cloudbrain config clear <ENV_VAR>",
    "cloudbrain config diagnose",
    "cloudbrain config discover --app-name <name> [--write]",
    "cloudbrain config write-example [path]",
    "gemini-ext status",
    "gemini-ext list",
    "gemini-ext inspect <name>",
    "//SWARM",
    "//MODE <name> [objective]",
    "//CARTRIDGE <name> [objective]",
    "//COGNITIVE [objective]",
    "//RESEARCH [objective]",
    "//ENGINEER [objective]",
    "//CREATIVE [objective]",
    "//MARKETING [objective]",
    "//LEGAL [objective]",
    "//BRAINSTORM [objective]",
    "//CRITICAL_THINKING [objective]",
    "/exit",
]

# ---------------------------------------------------------------------------
# Modal discovery map
# ---------------------------------------------------------------------------

MODAL_DISCOVERY_MAP: dict[str, str] = {
    "CAMELOT_RESEARCH_AGENCY_URL": "research_agency",
    "CAMELOT_RESEARCH_AGENCY_HEALTH_URL": "research_agency_health_endpoint",
    "CAMELOT_NORTHSTAR_URL": "northstar_war_room",
    "CAMELOT_NORTHSTAR_HEALTH_URL": "northstar_health_endpoint",
    "CAMELOT_BLUEPRINT_URL": "development_blueprint",
    "CAMELOT_BLUEPRINT_HEALTH_URL": "development_blueprint_health_endpoint",
    "CAMELOT_PRECISE_MODE_URL": "precise_mode",
    "CAMELOT_PRECISE_MODE_HEALTH_URL": "precise_mode_health_endpoint",
}
