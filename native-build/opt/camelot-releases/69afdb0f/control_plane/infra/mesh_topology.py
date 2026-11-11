# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Camelot-OS — Canonical Tailscale Mesh Topology
==============================================

The **single source of truth** for which nodes exist on the `Cyberdad247@github`
tailnet and what each one is.

Three modules previously each carried their own copy of this list
(`hermes_heimdall_sentinel.MESH_INVENTORY`,
`heimdall_bifrost_governance.CANONICAL_MESH_INVENTORY`,
`mesh_sentinel.TailscaleMeshSentinel.RULE_5_INVENTORY`). They drifted: two listed
nodes that were not on the tailnet at all, one omitted the hub entirely, and one
attributed the hub's address to a different node. Each copy is now a *projection*
of the data below, so a node can only be added or moved in one place.

Scope note (Rule 4 / Rule 5): the entries here are **tailnet identities**. The VPS
is reachable at a public WAN address and on the tailnet; only the tailnet address
belongs in this table, so that no mesh surface routes over the open internet by
accident.

Maintaining this file
---------------------
Verify against the live tailnet before editing::

    tailscale status

A node absent from that output must not be listed in ``MESH_NODES``. A node whose
address cannot be reached can only ever report ``OFFLINE``, which is noise that
masks a real node going down — that is the failure this module exists to prevent.

Run as a module::

    python -m control_plane.infra.mesh_topology            # print the topology
    python -m control_plane.infra.mesh_topology --test      # self-test
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class MeshNode:
    """One tailnet node. Every field is verified against live `tailscale status`."""

    id: str
    """Stable snake_case identifier, matching the tailscale hostname's shape."""

    name: str
    """The real tailscale hostname (may contain hyphens)."""

    ip: str
    """Tailnet IPv4 address (100.64.0.0/10 CGNAT range)."""

    role: str
    """What this node does for Camelot-OS."""

    scarcity: str
    """Resource class, for the scarcity governor. Never a hard RAM figure."""

    governing_knight: Optional[str] = None
    """Knight accountable for the node, where one is assigned."""

    status: str = "ACTIVE"
    """observed in the live tailnet as of the last reconciliation."""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# The VPS hub. Named constants because several modules need the address on its
# own and should not re-declare the literal.
HUB_NODE_ID = "vps_camelot_hub"
HUB_TAILSCALE_IP = "100.110.180.18"
HUB_PUBLIC_IP = "162.35.107.134"

# Reconciled against live `tailscale status` on 2026-09-15.
MESH_NODES: tuple[MeshNode, ...] = (
    MeshNode(
        id="cybertronia",
        name="cybertronia",
        ip="100.118.224.52",
        role="Primary Windows Orchestrator & Local VFS Factory",
        scarcity="8GB_BOUND",
    ),
    MeshNode(
        id="vashawns_s26_ultra",
        name="vashawns-s26-ultra",
        ip="100.106.246.126",
        role="Excalibur Command Center (Kinetic Mobile Sentinel & Cockpit / Android 16)",
        scarcity="MOBILE_ARM64",
    ),
    MeshNode(
        id="fothers_camelot",
        name="fothers-camelot",
        ip="100.121.48.49",
        role="Windows Sovereign Secondary Node & Failover Rig",
        scarcity="SOVEREIGN_NODE",
    ),
    MeshNode(
        id="lakesha",
        name="lakesha",
        ip="100.100.155.55",
        role="Lakisha Voice OS Host & Secondary Surface",
        scarcity="AUDIO_SENSORY",
    ),
    MeshNode(
        id=HUB_NODE_ID,
        name="vps-camelot-hub",
        ip=HUB_TAILSCALE_IP,
        role=f"Camelot-OS Hub & Control Plane (KVM563 / {HUB_PUBLIC_IP})",
        scarcity="HUB",
        governing_knight="HERMES_PRIME",
    ),
    MeshNode(
        id="macbook_pro_3",
        name="macbook-pro-3",
        ip="100.113.101.43",
        role="macOS Workstation (advertises an exit node; role unconfirmed)",
        scarcity="UNKNOWN",
    ),
    MeshNode(
        id="motorola_moto_g_power",
        name="motorola-moto-g-power-5g---2024",
        ip="100.89.129.105",
        role="Auxiliary Kinetic Mobile Sentinel & Backup Telemetry Relay",
        scarcity="MOBILE_ARM64",
        governing_knight="SIR_HEIMDALL",
    ),
)

# Named in AGENTS.md Rule 5 historically but absent from the live tailnet.
# Held separately so operational surfaces never advertise them as reachable.
ABSENT_MESH_NODES: tuple[MeshNode, ...] = (
    MeshNode(
        id="camelot_relay_modal",
        name="camelot-relay-modal",
        ip="100.84.98.39",
        role="Linux Cloud Relay Node & Modal Inference Bridge",
        scarcity="REMOTE_COMPUTE",
        status="ABSENT_FROM_TAILNET",
    ),
    MeshNode(
        id="kba_services",
        name="kba-services",
        ip="100.71.218.75",
        role="Linux Remote Services Node",
        scarcity="SERVICE",
        status="ABSENT_FROM_TAILNET",
    ),
)


def node_ids() -> tuple[str, ...]:
    return tuple(n.id for n in MESH_NODES)


def node_by_id(node_id: str) -> Optional[MeshNode]:
    """Return the node with this id, or None. Accepts the hostname form too."""
    for node in MESH_NODES:
        if node_id in (node.id, node.name):
            return node
    return None


def active_ips() -> tuple[str, ...]:
    return tuple(n.ip for n in MESH_NODES)


def absent_ips() -> tuple[str, ...]:
    """Addresses of nodes named historically but absent from the live tailnet.

    No operational surface may publish these as reachable. Consumers use this set
    to filter, so a projection can never advertise a phantom.
    """
    return tuple(n.ip for n in ABSENT_MESH_NODES)


def ip_of(node_id: str) -> str:
    """Address for a node id.

    Raises rather than returning a default, so a renamed or misspelled node id
    fails at import time instead of silently pointing at the wrong host.
    """
    node = node_by_id(node_id)
    if node is None:
        raise KeyError(
            f"unknown mesh node {node_id!r}; known ids: {', '.join(node_ids())}"
        )
    return node.ip


def hub_node() -> MeshNode:
    node = node_by_id(HUB_NODE_ID)
    assert node is not None, "hub node missing from MESH_NODES"
    return node


# ── Projections ───────────────────────────────────────────────────────────────
# Each consumer keeps its historical shape so no caller breaks. Do not add a new
# private copy of the node list in a consumer — add a projection here instead.


def as_sentinel_inventory() -> dict[str, dict[str, Any]]:
    """Shape used by `hermes_heimdall_sentinel.MESH_INVENTORY`."""
    return {
        n.id: {"ip": n.ip, "role": n.role, "scarcity": n.scarcity} for n in MESH_NODES
    }


def as_canonical_inventory() -> tuple[dict[str, Any], ...]:
    """Shape used by `heimdall_bifrost_governance.CANONICAL_MESH_INVENTORY`.

    `governing_knight` is omitted where unassigned, matching the previous output
    byte-for-byte so existing assertions on those entries still hold.
    """
    out: list[dict[str, Any]] = []
    for n in MESH_NODES:
        entry: dict[str, Any] = {
            "id": n.id,
            "name": n.name,
            "tailscale_ip": n.ip,
            "role": n.role,
            "status": n.status,
        }
        if n.governing_knight:
            entry["governing_knight"] = n.governing_knight
        out.append(entry)
    return tuple(out)


def as_absent_inventory() -> tuple[dict[str, Any], ...]:
    """Shape used by the `ABSENT_MESH_NODES` tables."""
    return tuple(
        {
            "id": n.id,
            "name": n.name,
            "tailscale_ip": n.ip,
            "role": n.role,
            "status": n.status,
        }
        for n in ABSENT_MESH_NODES
    )


def as_rule5_inventory() -> list[dict[str, Any]]:
    """Shape used by `mesh_sentinel.TailscaleMeshSentinel.RULE_5_INVENTORY`."""
    return [{"name": n.name, "ip": n.ip, "role": n.role} for n in MESH_NODES]


# Mobile sentinels, with the cockpit tier each fills. Topology data, so it lives
# here rather than beside the status payload that renders it.
_MOBILE_SENTINEL_TIERS: tuple[tuple[str, str], ...] = (
    ("vashawns_s26_ultra", "PRIMARY_COCKPIT"),
    ("motorola_moto_g_power", "AUXILIARY_SENTINEL"),
)


def as_sentinel_mobile_nodes() -> list[dict[str, Any]]:
    """Shape used by the governance status `mesh_inventory.sentinel_mobile_nodes`."""
    out: list[dict[str, Any]] = []
    for node_id, tier in _MOBILE_SENTINEL_TIERS:
        node = node_by_id(node_id)
        if node is not None:
            out.append({"name": node.name, "ip": node.ip, "tier": tier})
    return out


def topology_snapshot() -> dict[str, Any]:
    return {
        "node_count": len(MESH_NODES),
        "absent_count": len(ABSENT_MESH_NODES),
        "hub_tailscale_ip": HUB_TAILSCALE_IP,
        "hub_public_ip": HUB_PUBLIC_IP,
        "nodes": [n.as_dict() for n in MESH_NODES],
        "absent_nodes": [n.as_dict() for n in ABSENT_MESH_NODES],
    }


def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("mesh_topology self-test")

    check("node ids unique", len(set(node_ids())) == len(MESH_NODES))
    check("node ips unique", len(set(active_ips())) == len(MESH_NODES))
    check("every ip is in the CGNAT tailnet range",
          all(n.ip.startswith("100.") for n in MESH_NODES))
    check("no node duplicated across active and absent",
          not ({n.id for n in MESH_NODES} & {n.id for n in ABSENT_MESH_NODES}))
    check("hub declares the documented tailnet ip", hub_node().ip == HUB_TAILSCALE_IP)

    # Projections must all describe the same set of nodes.
    check("sentinel projection covers every node",
          set(as_sentinel_inventory()) == set(node_ids()))
    check("canonical projection covers every node",
          {e["id"] for e in as_canonical_inventory()} == set(node_ids()))
    check("rule5 projection covers every node",
          len(as_rule5_inventory()) == len(MESH_NODES))
    check("all projections agree on the address set",
          {v["ip"] for v in as_sentinel_inventory().values()}
          == {e["tailscale_ip"] for e in as_canonical_inventory()}
          == {e["ip"] for e in as_rule5_inventory()})
    check("every mobile sentinel tier resolves to a real node",
          all(e["ip"] in active_ips() for e in as_sentinel_mobile_nodes()))
    check("absent addresses never intersect the active set",
          not (set(active_ips()) & set(absent_ips())))

    try:
        json.dumps(topology_snapshot())
        check("snapshot is JSON-serializable", True)
    except (TypeError, ValueError):
        check("snapshot is JSON-serializable", False)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — mesh_topology")
    return failures


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print(json.dumps(topology_snapshot(), indent=2))
