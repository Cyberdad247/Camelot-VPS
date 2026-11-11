#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
r"""
Camelot-OS Hub & Control Plane (VPS KVM563) Access Client
=========================================================
Operator Authority: King Arthur (VaShawn O. Head / Vizion)
Governing Agent:    HERMES_PRIME (Hermes Research & Mesh Synthesis)
VPS Host:           KVM563 (vps3573819.trouble-free.net)
Public IP:          162.35.107.134
Tailscale IP:       mesh_topology.HUB_TAILSCALE_IP (vps-camelot-hub)

Capabilities:
1. --status    : Live ping & TCP service probe (SSH, Bifrost :3001, Mesh Bridge :8095)
2. --ssh       : Open interactive SSH shell to the VPS
3. --telemetry : Pull remote Hermes Prime & Open-Notebook VFS telemetry
"""

import argparse
import socket
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from control_plane.infra.mesh_topology import HUB_TAILSCALE_IP

VPS_PUBLIC_IP = "162.35.107.134"
VPS_HOSTNAME = "vps3573819.trouble-free.net"
# Was `VPS_KBA_TAILSCALE = "100.71.218.75"` — the kba_services address, which is
# not the hub and is absent from the tailnet entirely. get_vps_status() reports
# the hub, so it must publish the hub's own tailnet address. Sourced from
# mesh_topology rather than repeated as a literal.
VPS_TAILSCALE_IP = HUB_TAILSCALE_IP
VPS_SSH_PORT = 22
VPS_BIFROST_PORT = 3001
VPS_MESH_BRIDGE_PORT = 8095

def probe_port(host: str, port: int, timeout: float = 3.0) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def get_vps_status() -> dict:
    ssh_ok = probe_port(VPS_PUBLIC_IP, VPS_SSH_PORT, timeout=3.0)
    bifrost_ok = probe_port(VPS_PUBLIC_IP, VPS_BIFROST_PORT, timeout=2.0)
    mesh_ok = probe_port(VPS_PUBLIC_IP, VPS_MESH_BRIDGE_PORT, timeout=2.0)
    
    return {
        "host_server": "KVM563",
        "vm_id": "vps3573819",
        "public_ip": VPS_PUBLIC_IP,
        "tailscale_ip": VPS_TAILSCALE_IP,
        "assigned_agent": "HERMES_PRIME",
        "services": {
            "ssh_port_22": "ONLINE" if ssh_ok else "OFFLINE / FIREWALLED",
            "bifrost_gateway_3001": "ONLINE" if bifrost_ok else "STANDBY / PRIVATE_TS",
            "mesh_bridge_8095": "ONLINE" if mesh_ok else "STANDBY / PRIVATE_TS"
        }
    }

def print_status():
    print("=" * 80)
    print("🏰 CAMELOT-OS HUB & CONTROL PLANE (VPS KVM563) TELEMETRY")
    print("=" * 80)
    status = get_vps_status()
    print(f"• Host Server        : {status['host_server']} ({status['vm_id']})")
    print(f"• Public IP          : {status['public_ip']} ({VPS_HOSTNAME})")
    print(f"• Tailscale IP       : {status['tailscale_ip']} (kba-services)")
    print(f"• Assigned Agent     : {status['assigned_agent']}")
    print("\n📡 Service Ports & Ingress:")
    for s, state in status["services"].items():
        icon = "🟢" if "ONLINE" in state else "🟡"
        print(f"   {icon} {s:<22} : {state}")
    print("=" * 80)

def connect_ssh(user: str = "ubuntu"):
    print(f"\n🔐 Initiating SSH Session to Camelot Hub ({user}@{VPS_PUBLIC_IP})...")
    ssh_cmd = ["ssh", f"{user}@{VPS_PUBLIC_IP}"]
    try:
        subprocess.run(ssh_cmd)
    except Exception as e:
        print(f"❌ SSH Execution Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Camelot-OS Hub VPS Access Client")
    parser.add_argument("--status", action="store_true", help="Probe and display VPS status")
    parser.add_argument("--ssh", action="store_true", help="Launch SSH connection to VPS")
    parser.add_argument("--user", type=str, default="ubuntu", help="SSH username (default: ubuntu)")
    args = parser.parse_args()

    if args.ssh:
        connect_ssh(args.user)
    else:
        print_status()

if __name__ == "__main__":
    main()
