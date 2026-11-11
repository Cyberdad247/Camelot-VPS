# SPDX-License-Identifier: MIT

"""Sir Hermes commander automation and memory-fabric contract.

This module centralizes the non-secret integration layer that lets Sir Hermes
coordinate registered knights through Hermes automation while preserving each
knight's existing CloudBrain, VFS, MemPalace, Open-Notebook, HITL, and privacy
boundaries.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_plane.core.knight_agent import load_roster
from control_plane.dispatch.switchboard import TERMINAL_REGISTRY

ARTIFACT_RELATIVE_PATH = Path("03_VAULT") / "runtime_state" / "hermes_commander_fabric_latest.json"
COMMANDER_KNIGHT = "sir_hermes"
COMMANDER_ROLE = "COMMANDER_KNIGHT"
WORLDTREE_HOME_ID = "a0a4bfb9-e847-4c38-be39-7aee398f0795"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_cloudbrain_maps() -> tuple[dict[str, str], dict[str, list[str]]]:
    try:
        connector = importlib.import_module("01_KERNEL.memory.cloudbrain_connector")
    except Exception:
        return {}, {}
    notebooks = getattr(connector, "KNIGHT_NOTEBOOKS", {})
    domain_tags = getattr(connector, "NOTEBOOK_DOMAIN_TAGS", {})
    return (
        dict(notebooks) if isinstance(notebooks, dict) else {},
        dict(domain_tags) if isinstance(domain_tags, dict) else {},
    )


def _registered_knight_ids() -> list[str]:
    roster_ids = set(load_roster().keys())
    terminal_ids = {
        terminal_id
        for terminal_id in TERMINAL_REGISTRY
        if terminal_id.startswith(("sir_", "lady_", "merlin_"))
    }
    notebooks, _ = _load_cloudbrain_maps()
    notebook_ids = {
        knight_id.lower()
        for knight_id in notebooks
        if knight_id.startswith(("SIR_", "LADY_", "MERLIN_", "HERMES_", "ANYA_"))
    }
    return sorted(roster_ids | terminal_ids | notebook_ids | {COMMANDER_KNIGHT})


def _cloudbrain_uuid(knight_id: str, notebooks: dict[str, str]) -> str:
    return str(notebooks.get(knight_id.upper()) or WORLDTREE_HOME_ID)


def _domain_tags(knight_id: str, domain_tags: dict[str, list[str]]) -> list[str]:
    raw = domain_tags.get(knight_id.upper(), [])
    return list(raw) if isinstance(raw, list) else []


def _fabric_link(
    *,
    root: Path,
    knight_id: str,
    notebooks: dict[str, str],
    domain_tags: dict[str, list[str]],
) -> dict[str, Any]:
    capability = load_roster().get(knight_id)
    terminal = TERMINAL_REGISTRY.get(knight_id)
    privacy_level = capability.privacy_level if capability else 0.0
    requires_air_gap = bool(capability.requires_air_gap) if capability else False
    safety_boundary = (
        "HITL_AND_PRIVACY_GATES_PRESERVED"
        if not requires_air_gap
        else "HITL_AND_PRIVACY_GATES_PRESERVED"
    )
    return {
        "knight_id": knight_id,
        "commander_knight": COMMANDER_KNIGHT,
        "automation": {
            "enabled": True,
            "controller": COMMANDER_KNIGHT,
            "channel": f"hermes://automation/{knight_id}",
            "remote_execution_allowed": False,
            "safety_boundary": safety_boundary,
            "privacy_level": privacy_level,
            "requires_air_gap": requires_air_gap,
        },
        "memory_fabric": {
            "enabled": True,
            "cloudbrain_uuid": _cloudbrain_uuid(knight_id, notebooks),
            "worldtree_home": WORLDTREE_HOME_ID,
            "vfs_path": f"vfs://worldtree/knights/{knight_id}/tether.json",
            "mempalace_wing": f"WING_WORLDTREE_{knight_id.upper()}",
            "open_viking_node": f"open_viking://worldtree/{knight_id}",
            "open_notebook_local": str(
                root / "03_VAULT" / "runtime_state" / "open_notebook" / f"{knight_id}_tissue.json"
            ),
            "domain_tags": _domain_tags(knight_id, domain_tags),
        },
        "switchboard": {
            "registered": terminal is not None,
            "engine": terminal.engine if terminal else None,
            "capability": list(terminal.capability) if terminal else [],
        },
        "secret_values_serialized": False,
    }


def build_hermes_commander_fabric(*, root: Path | None = None) -> dict[str, Any]:
    """Build the in-memory Sir Hermes commander contract."""
    home = root or Path(__file__).resolve().parents[2]
    notebooks, domain_tags = _load_cloudbrain_maps()
    knight_links = {
        knight_id: _fabric_link(
            root=home,
            knight_id=knight_id,
            notebooks=notebooks,
            domain_tags=domain_tags,
        )
        for knight_id in _registered_knight_ids()
    }
    return {
        "status": "CONFIGURED",
        "commander_knight": COMMANDER_KNIGHT,
        "commander_role": COMMANDER_ROLE,
        "commander_capabilities": [
            "commander",
            "hermes_automation",
            "memory_fabric",
            "all_knight_coordination",
            "cloudbrain_tethering",
            "vfs_synthesis",
        ],
        "target_count": len(knight_links),
        "knight_links": knight_links,
        "secret_values_serialized": False,
        "generated_utc": _utc_now(),
    }


def write_hermes_commander_fabric(*, root: Path | None = None) -> dict[str, Any]:
    """Persist the Sir Hermes commander fabric snapshot."""
    home = root or Path(__file__).resolve().parents[2]
    fabric = build_hermes_commander_fabric(root=home)
    artifact_path = home / ARTIFACT_RELATIVE_PATH
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(fabric, indent=2, sort_keys=True), encoding="utf-8")
    fabric["artifact_path"] = str(artifact_path)
    return fabric
