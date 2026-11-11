# SPDX-License-Identifier: MIT

"""VPS Hermes_Prime integration contract for startup and global CLI surfaces.

This module is intentionally non-secret.  It exposes the known VPS/Bifrost
topology, optional read-only probes, and the operator command surface without
serializing credentials or opening remote sessions.
"""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from control_plane.dispatch.vps_hermes_links import (
    HERMES_PRIME_UUID,
    VPS_NODE_ID,
    VPS_PUBLIC_IP,
    VPS_TAILSCALE_IP,
    build_vps_hermes_inference_links,
)

VPS_HOST_SERVER = "KVM563"
VPS_VM_ID = "vps3573819"
VPS_HOSTNAME = "vps3573819.trouble-free.net"
ASSIGNED_KNIGHT = "HERMES_PRIME"
GLOBAL_STARTUP_COMMAND = "awaken"
GLOBAL_CLI_COMMAND = "camelot hermes"
_DEFAULT_PROBE_TIMEOUT = 0.75

PortProbe = Callable[[str, int, float], bool]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _topology_path(root: Path) -> Path:
    return root / "03_VAULT" / "runtime_state" / "sovereign_mesh_topology.json"


def _load_vps_node(root: Path) -> dict[str, Any]:
    try:
        topology = json.loads(_topology_path(root).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
        return {}
    nodes = topology.get("nodes", {})
    node = nodes.get(VPS_NODE_ID, {})
    return node if isinstance(node, dict) else {}


def resolve_vps_public_ip(*, root: Path | None = None) -> str:
    """Resolve the VPS public IP from topology, falling back to the stable constant."""
    node = _load_vps_node(root or _repo_root())
    return str(node.get("public_ip") or VPS_PUBLIC_IP)


def resolve_vps_tailscale_ip(*, root: Path | None = None) -> str:
    """Resolve the VPS mesh IP from topology, falling back to the shared link map."""
    node = _load_vps_node(root or _repo_root())
    return str(node.get("tailscale_ip") or VPS_TAILSCALE_IP)


def _probe_port(host: str, port: int, timeout: float = _DEFAULT_PROBE_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _service_entry(
    *,
    name: str,
    host: str,
    port: int,
    url: str | None = None,
    surface: str,
    state: str = "CONFIGURED",
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "host": host,
        "port": port,
        "surface": surface,
        "state": state,
    }
    if url:
        entry["url"] = url
    return entry


def build_vps_hermes_prime_contract(
    *,
    root: Path | None = None,
    public_ip: str | None = None,
    tailscale_ip: str | None = None,
) -> dict[str, Any]:
    """Return the non-secret VPS Hermes_Prime startup contract."""
    home = root or _repo_root()
    resolved_public_ip = public_ip or resolve_vps_public_ip(root=home)
    resolved_tailscale_ip = tailscale_ip or resolve_vps_tailscale_ip(root=home)
    inference_links = build_vps_hermes_inference_links(
        public_ip=resolved_public_ip,
        tailscale_ip=resolved_tailscale_ip,
    )
    cliproxy = inference_links["cliproxy_sie"]
    bifrost = cliproxy["bifrost_bridge"]

    return {
        "status": "CONFIGURED",
        "node_id": VPS_NODE_ID,
        "host_server": VPS_HOST_SERVER,
        "vm_id": VPS_VM_ID,
        "hostname": VPS_HOSTNAME,
        "public_ip": resolved_public_ip,
        "tailscale_ip": resolved_tailscale_ip,
        "assigned_knight": ASSIGNED_KNIGHT,
        "hermes_prime_uuid": HERMES_PRIME_UUID,
        "global_startup_command": GLOBAL_STARTUP_COMMAND,
        "global_cli_command": GLOBAL_CLI_COMMAND,
        "services": {
            "ssh": _service_entry(
                name="VPS SSH",
                host=resolved_public_ip,
                port=22,
                surface="remote_admin",
            ),
            "bifrost_gateway": _service_entry(
                name="Bifrost Gateway",
                host=resolved_tailscale_ip,
                port=3001,
                url=bifrost["gateway_url"],
                surface="bifrost_bridge",
            ),
            "mesh_bridge": _service_entry(
                name="Hermes Mesh Bridge",
                host=resolved_tailscale_ip,
                port=8095,
                url=bifrost["mesh_bridge_url"],
                surface="hermes_api",
            ),
        },
        "inference_links": inference_links,
        "auth": {
            "token_header": bifrost["auth"]["token_header"],
            "lease_header": bifrost["auth"]["lease_header"],
            "secret_values_serialized": False,
        },
        "secret_values_serialized": False,
        "generated_utc": _utc_now(),
    }


def summarize_vps_hermes_prime(
    *,
    root: Path | None = None,
    public_ip: str | None = None,
    tailscale_ip: str | None = None,
    probe_live: bool = False,
    port_probe: PortProbe | None = None,
) -> dict[str, Any]:
    """Return configured or live-probed VPS Hermes_Prime status."""
    contract = build_vps_hermes_prime_contract(
        root=root,
        public_ip=public_ip,
        tailscale_ip=tailscale_ip,
    )
    contract["probe_live"] = bool(probe_live)

    if not probe_live:
        contract["summary"] = (
            f"{ASSIGNED_KNIGHT} configured on {contract['host_server']} / "
            f"{contract['vm_id']} with Bifrost :3001 and mesh :8095; use "
            f"`{GLOBAL_CLI_COMMAND} --probe-live` for live checks"
        )
        return contract

    probe = port_probe or _probe_port
    services = contract["services"]
    for service in services.values():
        service["state"] = (
            "ONLINE"
            if probe(str(service["host"]), int(service["port"]), _DEFAULT_PROBE_TIMEOUT)
            else "OFFLINE"
        )

    bridge_online = (
        services["bifrost_gateway"]["state"] == "ONLINE"
        and services["mesh_bridge"]["state"] == "ONLINE"
    )
    contract["status"] = "ONLINE" if bridge_online else "DEGRADED"
    contract["summary"] = (
        f"{ASSIGNED_KNIGHT} {contract['status']} on VPS mesh "
        f"{contract['tailscale_ip']} (Bifrost={services['bifrost_gateway']['state']}, "
        f"mesh={services['mesh_bridge']['state']}, ssh={services['ssh']['state']})"
    )
    contract["checked_utc"] = _utc_now()
    return contract


def write_vps_hermes_prime_status(
    *,
    root: Path | None = None,
    probe_live: bool = False,
) -> dict[str, Any]:
    """Persist a runtime evidence snapshot for startup/status surfaces."""
    home = root or _repo_root()
    status = summarize_vps_hermes_prime(root=home, probe_live=probe_live)
    artifact = home / "03_VAULT" / "runtime_state" / "vps_hermes_prime_latest.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(status, indent=2), encoding="utf-8")
    status["artifact"] = str(artifact)
    return status


def boot_vps_hermes_prime(
    home: Path,
    *,
    probe_live: bool | None = None,
) -> tuple[bool, str]:
    """Startup hook for VPS Hermes_Prime.

    The default path is non-blocking and validates the contract only.  Set
    CAMELOT_VPS_HERMES_PROBE=1 or pass probe_live=True for TCP checks.
    """
    should_probe = (
        os.environ.get("CAMELOT_VPS_HERMES_PROBE", "").strip() == "1"
        if probe_live is None
        else probe_live
    )
    try:
        status = write_vps_hermes_prime_status(root=home, probe_live=should_probe)
    except Exception as exc:
        return False, f"VPS Hermes_Prime integration failed: {type(exc).__name__}: {exc}"

    ok = status.get("status") in {"CONFIGURED", "ONLINE", "DEGRADED"}
    return bool(ok), (
        f"VPS Hermes_Prime {status.get('status')} for {ASSIGNED_KNIGHT} "
        f"via {GLOBAL_CLI_COMMAND}; Bifrost {status['tailscale_ip']}:3001, "
        f"mesh {status['tailscale_ip']}:8095"
    )


def format_vps_hermes_prime_status(status: dict[str, Any]) -> str:
    """Render a compact human-readable status string for direct global CLI use."""
    services = status.get("services", {})
    lines = [
        f"VPS Hermes_Prime: {status.get('status', 'UNKNOWN')}",
        f"Node: {status.get('host_server')} / {status.get('vm_id')} ({status.get('node_id')})",
        f"Knight: {status.get('assigned_knight')} [{status.get('hermes_prime_uuid')}]",
        f"Public: {status.get('public_ip')}  Mesh: {status.get('tailscale_ip')}",
        f"Startup: {status.get('global_startup_command')}  Command: {status.get('global_cli_command')}",
    ]
    for key in ("bifrost_gateway", "mesh_bridge", "ssh"):
        service = services.get(key, {})
        label = service.get("name", key)
        url = service.get("url") or f"{service.get('host')}:{service.get('port')}"
        lines.append(f"- {label}: {service.get('state', 'UNKNOWN')} {url}")
    lines.append(f"Secrets serialized: {status.get('secret_values_serialized')}")
    return "\n".join(lines)
