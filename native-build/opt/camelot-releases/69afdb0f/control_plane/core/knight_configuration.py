# SPDX-License-Identifier: MIT

"""Knight configuration snapshot for cartridges, Excalibur, and switchboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARTIFACT_RELATIVE_PATH = Path("03_VAULT") / "runtime_state" / "knight_configuration_latest.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _cartridge_snapshot(home: Path) -> dict[str, Any]:
    cartridge_dir = home / "03_VAULT" / "training" / "configs" / "cartridges"
    names = sorted(path.stem for path in cartridge_dir.glob("*.yaml")) if cartridge_dir.exists() else []
    return {
        "active_count": len(names),
        "names": names,
        "source": str(cartridge_dir),
    }


def _excalibur_snapshot(home: Path) -> dict[str, Any]:
    roster_json = home / "01_KERNEL" / "agora" / "agents" / "roster.json"
    roster_yaml = home / "01_KERNEL" / "EXCALIBUR" / "roster.yaml"
    agents: list[str] = []

    data = _read_json(roster_json)
    if isinstance(data, dict):
        raw_agents = data.get("agents", [])
    elif isinstance(data, list):
        raw_agents = data
    else:
        raw_agents = []

    if isinstance(raw_agents, list):
        agents = [
            item.get("name") or item.get("id") or "unknown"
            if isinstance(item, dict)
            else str(item)
            for item in raw_agents
        ]

    if not agents and roster_yaml.exists():
        agents = [
            line.strip()
            for line in roster_yaml.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    source = roster_json if roster_json.exists() else roster_yaml
    return {
        "count": len(agents),
        "agents": agents,
        "source": str(source),
    }


def _switchboard_snapshot(home: Path) -> dict[str, Any]:
    manifest = home / "logs" / "switchboard_manifest.json"
    data = _read_json(manifest)
    if isinstance(data, dict):
        raw_entries = data.get("terminals", [])
    elif isinstance(data, list):
        raw_entries = data
    else:
        raw_entries = []

    terminals: list[str] = []
    if isinstance(raw_entries, list):
        terminals = [
            item.get("id") or item.get("name") or "unknown"
            if isinstance(item, dict)
            else str(item)
            for item in raw_entries
        ]

    return {
        "count": len(terminals),
        "terminals": terminals,
        "source": str(manifest),
    }


def _warp_workflow_snapshot(home: Path) -> dict[str, Any]:
    workflow_dir = home / ".warp" / "workflows"
    workflows = sorted(path.name for path in workflow_dir.glob("*.yaml")) if workflow_dir.exists() else []
    return {
        "count": len(workflows),
        "workflows": workflows,
        "source": str(workflow_dir),
    }


def write_knight_configuration(home: Path) -> dict[str, Any]:
    """Build, persist, and return the shared knight/cartridge configuration."""
    home = Path(home)
    artifact_path = home / ARTIFACT_RELATIVE_PATH
    from control_plane.infra.hermes_commander_fabric import write_hermes_commander_fabric

    snapshot: dict[str, Any] = {
        "status": "OK",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(home),
        "artifact_path": str(artifact_path),
        "cartridges": _cartridge_snapshot(home),
        "excalibur_roster": _excalibur_snapshot(home),
        "switchboard_roster": _switchboard_snapshot(home),
        "warp_workflows": _warp_workflow_snapshot(home),
        "hermes_commander": write_hermes_commander_fabric(root=home),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return snapshot
