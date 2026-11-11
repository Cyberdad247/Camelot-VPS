# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Rotel VPS Mesh Forwarder
========================
Binds edge Rotel thought traces on Cybertronia to the VPS Hub telemetry ingest.
"""

from __future__ import annotations

import datetime
from typing import Any
import requests

from control_plane.infra.mesh_topology import HUB_TAILSCALE_IP


class RotelVPSForwarder:
    def __init__(self, hub_ip: str = HUB_TAILSCALE_IP, port: int = 8095, timeout_s: float = 1.0):
        self.hub_ip = hub_ip
        self.port = port
        self.timeout_s = timeout_s
        self.endpoint = f"http://{self.hub_ip}:{self.port}/telemetry/event"

    def forward_trace(self, trace: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "source_node": "cybertronia",
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            **trace,
        }
        try:
            resp = requests.post(self.endpoint, json=payload, timeout=self.timeout_s)
            if resp.status_code in (200, 201, 202):
                return {"success": True, "status_code": resp.status_code, "response": resp.json()}
            return {"success": False, "status_code": resp.status_code, "error": resp.text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
