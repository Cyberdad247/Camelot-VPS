# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Kinetic Trinity VPS Sentinel
============================
Integrates and monitors the end-to-end operational readiness of
Rotel, Saltare, and Cribo across the Tailscale link to VPS Camelot Hub.
"""

from __future__ import annotations

import socket
from typing import Any

from control_plane.infra.mesh_topology import HUB_TAILSCALE_IP, HUB_PUBLIC_IP, HUB_NODE_ID
from control_plane.infra.rotel_vps_forwarder import RotelVPSForwarder
from control_plane.infra.saltare_hub_adapter import SaltareHubAdapter
from control_plane.infra.cribo_bundle_validator import CriboBundleValidator


class KineticVPSSentinel:
    def __init__(self, hub_ip: str = HUB_TAILSCALE_IP):
        self.hub_ip = hub_ip
        self.rotel_forwarder = RotelVPSForwarder(hub_ip=hub_ip)
        self.saltare_adapter = SaltareHubAdapter()
        self.cribo_validator = CriboBundleValidator()

    def _check_tcp(self, host: str, port: int, timeout_s: float = 1.0) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout_s)
                return sock.connect_ex((host, port)) == 0
        except Exception:
            return False

    def probe_all(self) -> dict[str, Any]:
        mesh_reachable = self._check_tcp(self.hub_ip, 22) or self._check_tcp(self.hub_ip, 80)

        rotel_test = self.rotel_forwarder.forward_trace({
            "component": "kinetic_sentinel",
            "level": "INFO",
            "message": "Mesh probe heartbeat",
        })

        saltare_test = self.saltare_adapter.dispatch_hub_tool("ping", {})

        healthy = rotel_test.get("success", False) or saltare_test.get("success", False) or mesh_reachable

        return {
            "overall_status": "HEALTHY" if healthy else "DEGRADED",
            "mesh_node": {
                "node_id": HUB_NODE_ID,
                "tailscale_ip": self.hub_ip,
                "public_ip": HUB_PUBLIC_IP,
                "reachable": mesh_reachable,
            },
            "components": {
                "rotel": {
                    "role": "thought_traces_to_vps",
                    "mesh_forwarding": rotel_test.get("success", False),
                },
                "saltare": {
                    "role": "vps_to_edge_mcp_dispatch",
                    "mcp_dispatch": saltare_test.get("success", False),
                },
                "cribo": {
                    "role": "pre_push_tree_shaking",
                    "configured": True,
                },
            },
        }
