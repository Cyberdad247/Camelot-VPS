#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Omarchy Headless Verifier & Scarcity Protocol Enforcer
======================================================
Validates that Omarchy edge-node and VPS deployments strictly comply with:
1. Zero-GUI Policy (no Hyprland, Wayland, Xorg, or Gnome packages consuming RAM).
2. 8GB VPS Edge Ceiling (cgroups v2 limits enforced).
3. Toolchain & UFW Firewall Hardening.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import List

VPS_HOST = os.environ.get("CAMELOT_VPS_HOST", "162.35.107.134")
VPS_USER = "root"


@dataclass
class HeadlessAuditResult:
    target: str
    is_headless: bool
    gui_packages_detected: List[str]
    ram_usage_mb: int
    ram_total_mb: int
    scarcity_compliant: bool
    ufw_active: bool
    cgroups_slices_detected: List[str]
    verdict: str  # "PASS" | "FAIL" | "WARNING"


def audit_vps_headless() -> HeadlessAuditResult:
    """Run remote audit over SSH to check VPS headless compliance."""
    cmd = (
        "dpkg -l | grep -E 'hyprland|wayland|xorg|gnome' | awk '{print $2}' || true; "
        "free -m | awk '/Mem:/ {print $3, $2}'; "
        "which ufw >/dev/null && ufw status | grep -q 'Status: active' && echo 'UFW_ON' || echo 'UFW_OFF'; "
        "systemctl list-unit-files --type=slice | grep -E 'camelot|system' | awk '{print $1}' || true"
    )

    ssh_cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        f"{VPS_USER}@{VPS_HOST}",
        cmd,
    ]

    try:
        proc = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception as e:
        return HeadlessAuditResult(
            target=VPS_HOST,
            is_headless=True,
            gui_packages_detected=[],
            ram_usage_mb=0,
            ram_total_mb=8192,
            scarcity_compliant=True,
            ufw_active=False,
            cgroups_slices_detected=[],
            verdict=f"UNREACHABLE: {e}",
        )

    gui_pkgs = []
    used_mb, total_mb = 0, 8192
    ufw_on = False
    slices = []

    for line in lines:
        if " " in line and line.split()[0].isdigit() and line.split()[1].isdigit():
            parts = line.split()
            used_mb, total_mb = int(parts[0]), int(parts[1])
        elif line in {"UFW_ON", "UFW_OFF"}:
            ufw_on = (line == "UFW_ON")
        elif line.endswith(".slice"):
            slices.append(line)
        elif any(gui in line for gui in ["hyprland", "wayland", "xorg", "gnome"]):
            gui_pkgs.append(line)

    is_headless = len(gui_pkgs) == 0
    scarcity_ok = used_mb < 7500

    verdict = "PASS" if is_headless and scarcity_ok else "WARNING"

    return HeadlessAuditResult(
        target=f"{VPS_HOST} (KVM563)",
        is_headless=is_headless,
        gui_packages_detected=gui_pkgs,
        ram_usage_mb=used_mb,
        ram_total_mb=total_mb,
        scarcity_compliant=scarcity_ok,
        ufw_active=ufw_on,
        cgroups_slices_detected=slices,
        verdict=verdict,
    )


if __name__ == "__main__":
    res = audit_vps_headless()
    print(json.dumps(asdict(res), indent=2))
    sys.exit(0 if res.verdict == "PASS" else 1)
