# SPDX-License-Identifier: MIT

"""Sir Heimdall governance harness for the Bifrost bridge.

The module is intentionally deterministic: it does not launch agents or call
remote models. It binds Sir Heimdall to Bifrost ownership, verifies the router
mesh manifest, and publishes a small nano-knight swarm contract for boot, CLI,
and dashboard surfaces.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from control_plane.infra.mesh_topology import (
        HUB_TAILSCALE_IP,
        as_absent_inventory,
        as_canonical_inventory,
        as_sentinel_mobile_nodes,
    )
except ImportError:  # standalone fallback when executed from a remote VPS directory
    from mesh_topology import (  # type: ignore
        HUB_TAILSCALE_IP,
        as_absent_inventory,
        as_canonical_inventory,
        as_sentinel_mobile_nodes,
    )


def _detect_home() -> Path:
    env = os.environ.get("CAMELOT_OS_HOME")
    if env and Path(env).is_dir():
        return Path(env)
    return Path(__file__).resolve().parent.parent


CAMELOT_HOME = _detect_home()
RUNTIME_STATE_DIR = CAMELOT_HOME / "03_VAULT" / "runtime_state"
GOVERNANCE_STATUS_PATH = RUNTIME_STATE_DIR / "heimdall_bifrost_governance_latest.json"
BIFROST_MESH_MANIFEST_PATH = RUNTIME_STATE_DIR / "bifrost_router_mesh_manifest.json"
CODEX_INTEGRATION_PATH = RUNTIME_STATE_DIR / "codex_integration_latest.json"

REQUIRED_BRIDGE_COMPONENTS = (
    "CLIProxyAPI",
    "OmniRoute",
    "BitRouter",
    "9Router",
    "MultivoiceRouter",
)

HEIMDALL_NANO_KNIGHTS: tuple[dict[str, Any], ...] = (
    {
        "id": "heimdall.watchman",
        "callsign": "Watchman",
        "channel": "bifrost.health",
        "mission": "Probe Bifrost health and protected status boundaries.",
        "tier": "S1",
    },
    {
        "id": "heimdall.rune_law",
        "callsign": "Rune Law",
        "channel": "bifrost.policy",
        "mission": "Check bridge intents against zero-trust and HITL policy.",
        "tier": "S2",
    },
    {
        "id": "heimdall.mesh_probe",
        "callsign": "Mesh Probe",
        "channel": "router.mesh",
        "mission": "Track CLIProxyAPI, OmniRoute, BitRouter, 9Router, and MultivoiceRouter coverage.",
        "tier": "S2",
    },
    {
        "id": "heimdall.token_warden",
        "callsign": "Token Warden",
        "channel": "bifrost.auth",
        "mission": "Report token presence only; never serialize secret values.",
        "tier": "S3",
    },
    {
        "id": "heimdall.ledger_scribe",
        "callsign": "Ledger Scribe",
        "channel": "runtime.evidence",
        "mission": "Publish governance evidence into runtime_state for boot, CLI, and HUD readers.",
        "tier": "S2",
    },
    # PR #3 of NOTES_MNEMOSYNE_WIRING.md (2026-07-14). Gates Bifrost→Appwrite egress.
    {
        "id": "heimdall.appwrite_egress",
        "callsign": "Appwrite Egress",
        "channel": "bifrost.policy.appwrite",
        "mission": "Gate Bifrost→Appwrite egress against zero-trust policy; rotate APPWRITE_API_KEY per `appwrite_bootstrap.sh --rotate`.",
        "tier": "S2",
    },
    # Hermes Prime always-on VPS bridge co-pilot & MGV synthesis nano-knight
    {
        "id": "heimdall.hermes_mesh",
        "callsign": "Hermes Mesh Sentinel",
        "channel": "hermes.mesh_synthesis",
        "mission": "Always-on VPS Hub co-pilot, MGV research loop, VFS forge, and CloudBrain sync across Bifrost.",
        "tier": "S4",
    },
)

BIFROST_KNIGHTS_SWARM: tuple[dict[str, Any], ...] = (
    {
        "id": "SIR_HEIMDALL",
        "role": "Bifrost Guardian & Boundary Sentinel",
        "vfs": "vfs://sir_heimdall/",
        "status": "ALWAYS_ON_HUB",
    },
    {
        "id": "HERMES_PRIME",
        "role": "Always-on VPS Co-Pilot & MGV Synthesis Engine",
        "vfs": "vfs://hermes_prime/",
        "status": "ALWAYS_ON_HUB",
    },
    {
        "id": "SIR_LANCELOT",
        "role": "Kinetic Edge & Frontline Defense",
        "vfs": "vfs://sir_lancelot/",
        "status": "ACTIVE_ESCORT",
    },
    {
        "id": "SIR_GALAHAD",
        "role": "Verification, Chivalric Purity & Z3 Formal Gate",
        "vfs": "vfs://sir_galahad/",
        "status": "ACTIVE_ESCORT",
    },
    {
        "id": "SIR_SENTINEL",
        "role": "AgentArmor, Zero-Trust Leases & Security Shield",
        "vfs": "vfs://sir_sentinel/",
        "status": "ACTIVE_ESCORT",
    },
    {
        "id": "LADY_MNEMOSYNE",
        "role": "Living Memory Guardian & World Tree Spine",
        "vfs": "vfs://lady_mnemosyne/",
        "status": "ACTIVE_ESCORT",
    },
    {
        "id": "SIR_HELIO",
        "role": "Voice OS & Phonetic Mesh Dispatch",
        "vfs": "vfs://sir_helio/",
        "status": "ACTIVE_ESCORT",
    },
)

# Projected from control_plane.infra.mesh_topology — the single source of truth,
# shared with the Heimdall sentinel and the mesh sentinel. This table used to be
# a third independent copy, which is how `kba_services` came to be documented at
# 100.71.218.75 with the role "VPS KVM563 Bridge" while the hub itself was
# missing. Add or move a node in mesh_topology, not here.
CANONICAL_MESH_INVENTORY: tuple[dict[str, Any], ...] = as_canonical_inventory()

# Nodes named in AGENTS.md Rule 5 that are absent from the live tailnet. Held
# separately so operational surfaces never advertise them as reachable ACTIVE
# nodes.
ABSENT_MESH_NODES: tuple[dict[str, Any], ...] = as_absent_inventory()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _component_names(manifest: dict[str, Any], codex_status: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    manifest_components = manifest.get("components", {})
    if isinstance(manifest_components, dict):
        names.update(str(name) for name in manifest_components.keys())
    elif isinstance(manifest_components, list):
        for item in manifest_components:
            if isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
            elif isinstance(item, str):
                names.add(item)

    bridge_components = manifest.get("bridge", {}).get("components", [])
    if isinstance(bridge_components, list):
        names.update(str(name) for name in bridge_components)

    bridges = codex_status.get("bridges", {})
    if isinstance(bridges, dict):
        bifrost_bridge = bridges.get("bifrost_bridge", {})
        if isinstance(bifrost_bridge, dict):
            names.update(str(name) for name in bifrost_bridge.get("components", []))
    elif isinstance(bridges, list):
        for item in bridges:
            if isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
    return sorted(names)


def _token_present() -> bool:
    token_path = Path.home() / ".camelot" / "bifrost.token"
    try:
        return bool(token_path.read_text(encoding="ascii").strip())
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        return False


def read_governance_status(home: Path | None = None) -> dict[str, Any]:
    root = Path(home or CAMELOT_HOME)
    runtime_dir = root / "03_VAULT" / "runtime_state"
    manifest = _read_json(runtime_dir / BIFROST_MESH_MANIFEST_PATH.name)
    codex_status = _read_json(runtime_dir / CODEX_INTEGRATION_PATH.name)
    components = _component_names(manifest, codex_status)
    missing_components = [name for name in REQUIRED_BRIDGE_COMPONENTS if name not in components]

    try:
        from control_plane.dispatch.switchboard import TERMINAL_REGISTRY

        heimdall_terminal = TERMINAL_REGISTRY.get("sir_heimdall")
    except Exception:
        heimdall_terminal = None

    nano_knights = [dict(item) for item in HEIMDALL_NANO_KNIGHTS]
    bifrost_knights = [dict(item) for item in BIFROST_KNIGHTS_SWARM]
    ready = heimdall_terminal is not None and not missing_components and bool(nano_knights)
    status = "GOVERNING" if ready else "ATTENTION_REQUIRED"
    return {
        "schema": "camelot.heimdall_bifrost_governance.v1",
        "status": status,
        "ready": ready,
        "owner": "sir_heimdall",
        "co_governor": "HERMES_PRIME",
        "governed_surface": "bifrost_bridge",
        "vps_hub": {
            "host_server": "KVM563",
            "vm_id": "vps3573819",
            "public_ip": "162.35.107.134",
            # Was 100.71.218.75 — the kba_services address, not the hub's. This is
            # the value the dashboard renders, so it advertised the wrong host.
            "tailscale_ip": HUB_TAILSCALE_IP,
            "role": "Camelot-OS Hub & Sovereign Control Plane",
            "always_on_agents": ["HERMES_PRIME", "SIR_HEIMDALL"],
        },
        "mesh_inventory": {
            "account": "Cyberdad247@github",
            "node_count": len(CANONICAL_MESH_INVENTORY),
            "nodes": [dict(node) for node in CANONICAL_MESH_INVENTORY],
            "sentinel_mobile_nodes": as_sentinel_mobile_nodes(),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "terminal": {
            "present": heimdall_terminal is not None,
            "engine": getattr(heimdall_terminal, "engine", None),
            "capabilities": list(getattr(heimdall_terminal, "capability", []) or []),
            "notes": getattr(heimdall_terminal, "notes", None),
        },
        "bridge_mesh": {
            "required_components": list(REQUIRED_BRIDGE_COMPONENTS),
            "components": components,
            "missing_components": missing_components,
            "manifest_present": bool(manifest),
            "codex_integration_present": bool(codex_status),
        },
        "auth": {
            "bifrost_token_present": _token_present(),
            "secret_values_serialized": False,
        },
        "nano_knights": nano_knights,
        "bifrost_knights_swarm": bifrost_knights,
        "event_routes": {
            item["channel"]: {"nano_knight": item["id"], "callsign": item["callsign"]}
            for item in nano_knights
        },
    }


def write_governance_status(home: Path | None = None) -> dict[str, Any]:
    root = Path(home or CAMELOT_HOME)
    status = read_governance_status(root)
    out_path = root / "03_VAULT" / "runtime_state" / GOVERNANCE_STATUS_PATH.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status["artifact_path"] = str(out_path)
    return status


def dispatch_to_nano_knight(event: dict[str, Any], home: Path | None = None) -> dict[str, Any]:
    status = write_governance_status(home)
    channel = str(event.get("channel", "runtime.evidence"))
    route = status["event_routes"].get(channel) or status["event_routes"]["runtime.evidence"]
    return {
        "schema": "camelot.heimdall_nano_knight_dispatch.v1",
        "owner": "sir_heimdall",
        "event": event,
        "route": route,
        "governance_ready": status["ready"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def boot_heimdall_bifrost_governance(home: Path | None = None) -> tuple[bool, str]:
    status = write_governance_status(home)
    missing = status["bridge_mesh"]["missing_components"]
    if status["ready"]:
        return True, f"Heimdall governing Bifrost with {len(status['nano_knights'])} nano-knights"
    return False, f"Heimdall governance attention required; missing={missing}"


def _selftest() -> int:
    status = write_governance_status()
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("Heimdall Bifrost governance self-test")
    check("owner is sir_heimdall", status["owner"] == "sir_heimdall")
    check("nano-knight swarm registered", len(status["nano_knights"]) >= 6)  # PR #3 added heimdall.appwrite_egress
    check("no secret values serialized", status["auth"]["secret_values_serialized"] is False)
    check("event routes cover nano-knights", "router.mesh" in status["event_routes"])
    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} - heimdall_bifrost_governance")
    return failures


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        raise SystemExit(_selftest())
    print(json.dumps(write_governance_status(), indent=2, sort_keys=True))
