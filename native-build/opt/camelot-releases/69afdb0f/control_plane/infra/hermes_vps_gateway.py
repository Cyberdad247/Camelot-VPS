# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Camelot-OS — Hermes VPS Gateway & Remote Control
=================================================
Connects Camelot-OS local agents to the remote NousResearch Hermes Agent running
on VPS Hub KVM563 (162.35.107.134 / 100.110.180.18).

The hub runs Hermes as the native systemd unit ``hermes-agent.service`` with the
binary at ``HERMES_BIN``. No container runtime is invoked from this module
(Rule 7: 0% container in the hot path).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import webbrowser
from typing import Any, Dict, List

from control_plane.infra.mesh_topology import HUB_TAILSCALE_IP

VPS_HOST = os.environ.get("CAMELOT_VPS_HOST", "162.35.107.134")
VPS_TAILSCALE_IP = os.environ.get("CAMELOT_VPS_TS_IP", HUB_TAILSCALE_IP)
VPS_USER = "root"

# Native install paths on the hub. Keep in sync with infra/systemd/hermes-agent.service.
HERMES_BIN = "/usr/local/bin/hermes"
HERMES_UNIT = "hermes-agent.service"

DASHBOARD_URL = f"http://{VPS_HOST}/"
DASHBOARD_TS_URL = f"http://{VPS_TAILSCALE_IP}/"
OPENAI_GATEWAY_URL = f"http://{VPS_HOST}/api/v1"
OPENAI_GATEWAY_TS_URL = f"http://{VPS_TAILSCALE_IP}/api/v1"


def get_hermes_endpoints() -> Dict[str, str]:
    return {
        "dashboard_public": DASHBOARD_URL,
        "dashboard_tailscale": DASHBOARD_TS_URL,
        "api_gateway_public": OPENAI_GATEWAY_URL,
        "api_gateway_tailscale": OPENAI_GATEWAY_TS_URL,
        "ssh_target": f"{VPS_USER}@{VPS_HOST}",
        "unit_name": HERMES_UNIT,
        "hermes_bin": HERMES_BIN,
    }


def open_hermes_dashboard(use_tailscale: bool = False) -> str:
    url = DASHBOARD_TS_URL if use_tailscale else DASHBOARD_URL
    webbrowser.open(url)
    return url


def run_hermes_cli(args: List[str] | str, timeout: int = 30) -> Dict[str, Any]:
    """Execute a Hermes CLI command natively on the VPS hub.

    Runs the binary directly over ssh. Arguments are quoted with
    :func:`shlex.quote` because ssh joins its argv into a single string that the
    remote shell re-splits — an unquoted argument containing spaces would
    otherwise be broken into several arguments.
    """
    if isinstance(args, list):
        cmd_str = " ".join(shlex.quote(str(a)) for a in args)
    else:
        cmd_str = str(args).strip()

    remote_cmd = f"{HERMES_BIN} {cmd_str}".strip()
    ssh_cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=8",
        f"{VPS_USER}@{VPS_HOST}",
        remote_cmd,
    ]

    try:
        proc = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "status": "SUCCESS" if proc.returncode == 0 else "ERROR",
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": remote_cmd,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "command": remote_cmd,
        }
    except Exception as exc:
        return {
            "status": "EXCEPTION",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "command": remote_cmd,
        }


def get_hermes_status() -> Dict[str, Any]:
    """Retrieve live status of Hermes on the VPS."""
    version_res = run_hermes_cli(["--version"], timeout=8)
    config_res = run_hermes_cli(["config", "get", "model"], timeout=8)
    sessions_res = run_hermes_cli(["sessions", "list"], timeout=8)

    return {
        "status": "ONLINE" if version_res["status"] == "SUCCESS" else "DEGRADED",
        "endpoints": get_hermes_endpoints(),
        "version": version_res.get("stdout", ""),
        "model_config": config_res.get("stdout", ""),
        "recent_sessions": sessions_res.get("stdout", ""),
    }


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(json.dumps(get_hermes_status(), indent=2))
    elif "--dashboard" in sys.argv:
        u = open_hermes_dashboard()
        print(f"Opened dashboard at {u}")
    elif len(sys.argv) > 1:
        args_to_run = [a for a in sys.argv[1:] if not a.startswith("--")]
        res = run_hermes_cli(args_to_run)
        print(res.get("stdout") or res.get("stderr"))
    else:
        print(json.dumps(get_hermes_status(), indent=2))
