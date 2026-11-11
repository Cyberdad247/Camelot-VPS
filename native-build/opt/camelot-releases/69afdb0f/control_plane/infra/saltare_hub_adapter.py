# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Saltare Hub Adapter
===================
Executes remote MCP tool dispatches originating from Hermes Prime on VPS Hub
by arbitrating through local Saltare gateway (:8090).
"""

from __future__ import annotations

from typing import Any
import requests


class SaltareHubAdapter:
    def __init__(self, local_port: int = 8090, timeout_s: float = 2.0):
        self.local_port = local_port
        self.timeout_s = timeout_s
        self.url = f"http://127.0.0.1:{self.local_port}/v1/tools/execute"

    def dispatch_hub_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "origin": "vps_camelot_hub",
            "tool": tool_name,
            "arguments": arguments,
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=self.timeout_s)
            if resp.status_code == 200:
                data = resp.json()
                return {"success": True, "result": data.get("result", data)}
            return {"success": False, "status_code": resp.status_code, "error": resp.text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
