# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Omarchy Multi-Agent Matrix Harmonizer
=====================================
Harmonizes Omarchy's mise-managed agent CLI launchers with Camelot's Sovereign
Knight Pantheon:
- `claude`   -> SIR_BORIS (Claude Code / Lead Architect)
- `codex`    -> SIR_CODEX (OpenAI Codex / Kinetic Implementer)
- `helios`   -> SIR_HELIOS (Google Antigravity CLI / FastMCP / CloudBrain Synergy)
- `agy`      -> SIR_HELIOS (Google Antigravity CLI / CloudBrain Node Tether)
- `hermes`   -> HERMES_PRIME (NousResearch Hermes Agent VPS Layer)
- `opencode` -> SIR_FORGE (Kinetic Code Generation)
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_CAMELOT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_CAMELOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_CAMELOT_ROOT))


def get_cloudbrain_node_for_knight(knight_id: str) -> Dict[str, Any]:
    """Dynamically resolve CloudBrain node UUID and domain tags from 01_KERNEL."""
    try:
        import importlib
        cb_mod = importlib.import_module("01_KERNEL.memory.cloudbrain_connector")
        KNIGHT_NOTEBOOKS = getattr(cb_mod, "KNIGHT_NOTEBOOKS", {})
        NOTEBOOK_DOMAIN_TAGS = getattr(cb_mod, "NOTEBOOK_DOMAIN_TAGS", {})
        uuid = KNIGHT_NOTEBOOKS.get(knight_id, "ab8aa359-2b3b-4bc1-b41f-34979cdc184e")
        tags = NOTEBOOK_DOMAIN_TAGS.get(knight_id, ["cloudbrain", "sir_helios", "notebooklm"])
        return {"uuid": uuid, "tags": tags}
    except Exception:
        return {
            "uuid": "ab8aa359-2b3b-4bc1-b41f-34979cdc184e",
            "tags": ["cloudbrain", "sir_helios", "notebooklm", "antigravity"],
        }


@dataclass
class AgentMapping:
    omarchy_cmd: str
    knight_id: str
    engine: str
    rune_alias: str
    role: str
    proxy_target: str
    cloudbrain_uuid: Optional[str] = None
    cloudbrain_tags: Optional[List[str]] = None


# Dynamically resolve Sir Helios CloudBrain coordinates
_helios_cb = get_cloudbrain_node_for_knight("SIR_HELIOS")
_hermes_cb = get_cloudbrain_node_for_knight("HERMES_PRIME")
_codex_cb = get_cloudbrain_node_for_knight("SIR_CODEX")
_boris_cb = get_cloudbrain_node_for_knight("SIR_BORIS")

OMARCHY_KNIGHT_MATRIX: Dict[str, AgentMapping] = {
    "hermes": AgentMapping(
        omarchy_cmd="hermes",
        knight_id="HERMES_PRIME",
        engine="Hermes Agent v0.20.5 (VPS Docker :8642/:9119)",
        rune_alias="//HERMES",
        role="Autonomous Recursive Execution & Dialectic Synthesis",
        proxy_target="vps://162.35.107.134:8642",
        cloudbrain_uuid=_hermes_cb["uuid"],
        cloudbrain_tags=_hermes_cb["tags"],
    ),
    "codex": AgentMapping(
        omarchy_cmd="codex",
        knight_id="SIR_CODEX",
        engine="GPT-5.5 Codex (Kinetic DGM-H)",
        rune_alias="//CODEX",
        role="Kinetic Implementer & Formal AST Logic Architect",
        proxy_target="local://camelot/control_plane",
        cloudbrain_uuid=_codex_cb["uuid"],
        cloudbrain_tags=_codex_cb["tags"],
    ),
    "claude": AgentMapping(
        omarchy_cmd="claude",
        knight_id="SIR_BORIS",
        engine="Claude 3.7 Sonnet / Opus (Crucible)",
        rune_alias="//FORGE",
        role="Lead System Architect & 13-Agent Crucible Conductor",
        proxy_target="local://camelot/agora",
        cloudbrain_uuid=_boris_cb["uuid"],
        cloudbrain_tags=_boris_cb["tags"],
    ),
    "helios": AgentMapping(
        omarchy_cmd="helios",
        knight_id="SIR_HELIOS",
        engine="Sir Helios (Google Antigravity CLI / FastMCP / Gemini 3.8 Flash)",
        rune_alias="//HELIOS",
        role="Voice OS & Autonomous CloudBrain Synergy Engine",
        proxy_target="local://camelot/sir_helios",
        cloudbrain_uuid=_helios_cb["uuid"],
        cloudbrain_tags=_helios_cb["tags"],
    ),
    "agy": AgentMapping(
        omarchy_cmd="agy",
        knight_id="SIR_HELIOS",
        engine="Sir Helios (Google Antigravity CLI / FastMCP / Gemini)",
        rune_alias="//FLEET",
        role="NotebookLM CloudBrain Synergy & Dual-Brain Bridge (Sir Helios)",
        proxy_target="local://camelot/sir_helios",
        cloudbrain_uuid=_helios_cb["uuid"],
        cloudbrain_tags=_helios_cb["tags"],
    ),
}


def get_agent_matrix() -> Dict[str, Any]:
    """Return serialized mapping of Omarchy agent commands to Camelot Knights."""
    return {
        "status": "HARMONIZED",
        "total_agents": len(OMARCHY_KNIGHT_MATRIX),
        "agents": {k: asdict(v) for k, v in OMARCHY_KNIGHT_MATRIX.items()},
    }


def generate_omarchy_mise_stub(agent_name: str) -> str:
    """Generate shell launcher script for an Omarchy mise stub with CloudBrain dynamic injection."""
    mapping = OMARCHY_KNIGHT_MATRIX.get(agent_name.lower())
    if not mapping:
        raise ValueError(f"Unknown agent: {agent_name}")

    if mapping.omarchy_cmd == "hermes":
        # The hub runs Hermes as the native systemd unit hermes-agent.service.
        # This path must not invoke a container runtime (Rule 7: 0% container in
        # the hot path). Host is overridable so the stub is not pinned to the
        # public WAN address.
        #
        # ssh joins its remaining arguments into a single string that the remote
        # shell then splits, so arguments are escaped locally with printf '%q '
        # rather than forwarded as a bare "$@" (which would split on spaces).
        return "\n".join(
            [
                "#!/bin/bash",
                "# Omarchy <-> Camelot Hermes proxy stub.",
                "# The hub runs Hermes natively via hermes-agent.service.",
                "# No container runtime is involved in this path.",
                "set -euo pipefail",
                'HUB="${CAMELOT_HUB_HOST:-162.35.107.134}"',
                "ARGS=$(printf '%q ' \"$@\")",
                'exec ssh -o BatchMode=yes "root@$HUB" "/usr/local/bin/hermes $ARGS"',
                "",
            ]
        )

    if mapping.omarchy_cmd in {"helios", "agy"}:
        return (
            "#!/bin/bash\n"
            f"# Omarchy <-> Camelot {mapping.knight_id} (CloudBrain Dynamic Launcher)\n"
            f'export CAMELOT_KNIGHT_ID="{mapping.knight_id}"\n'
            f'export CLOUDBRAIN_NODE_UUID="{mapping.cloudbrain_uuid}"\n'
            f'python3 -m control_plane.runes.runic_router "{mapping.rune_alias} $*"\n'
        )

    return (
        f"#!/bin/bash\n"
        f"# Omarchy <-> Camelot {mapping.knight_id} Launcher Stub\n"
        f'export CLOUDBRAIN_NODE_UUID="{mapping.cloudbrain_uuid}"\n'
        f'python3 -m control_plane.runes.runic_router "{mapping.rune_alias} $*"\n'
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Omarchy Multi-Agent Matrix Harmonizer")
    parser.add_argument("agent", nargs="?", default=None, help="Agent name (helios, agy, hermes, codex, claude)")
    parser.add_argument("--stub", action="store_true", help="Generate mise launcher stub")
    args = parser.parse_args()

    if args.agent and args.stub:
        print(generate_omarchy_mise_stub(args.agent))
    elif args.agent:
        mapping = OMARCHY_KNIGHT_MATRIX.get(args.agent.lower())
        if mapping:
            print(json.dumps(asdict(mapping), indent=2))
        else:
            print(f"Unknown agent: {args.agent}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps(get_agent_matrix(), indent=2))
