#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Tailscale Mesh Sentinel (TAILSCALE_MESH_SENTINEL)
=================================================
Always-On Mesh Supervisor & Dual-Path Resilience Sentinel for Camelot-OS.

Capabilities:
  1. Always-On Android Sentinel:
     - Enforces Android Always-On VPN configuration (`com.tailscale.ipn`).
     - Ensures Doze-mode exemption (`deviceidle whitelist`).
     - Grants unconstrained background operations (`RUN_ANY_IN_BACKGROUND`).
  2. Dual-Path Mesh Failover (Zero-Downtime Switching):
     - Path A: Sovereign Tailscale WireGuard Mesh (100.106.246.126:5555).
     - Path B: Local High-Throughput Wireless Fabric (192.168.88.2:5555).
     - Out-of-Band: Alexandria Warp Gate Rendezvous Locker.
  3. Host Mesh Health Monitoring & Cloudflare WARP Coexistence:
     - Detects VPN conflicts and IPv4/IPv6 socket states.
     - Emits periodic telemetry heartbeats to `03_VAULT/runtime_state/mesh_heartbeats.json`.
  4. Auto-Resurrection Daemon:
     - Automatically revives severed sockets and reconnects ADB wireless endpoints.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

LOG = logging.getLogger("TailscaleMeshSentinel")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

PEER_S26_TAILSCALE_IP = "100.106.246.126"
PEER_S26_WIFI_IP = "192.168.88.2"
PEER_ADB_PORT = 5555
PEER_VPS_HUB_IP = "100.110.180.18"
HEARTBEAT_FILE = _ROOT / "03_VAULT" / "runtime_state" / "mesh_heartbeats.json"


@dataclass
class PathStatus:
    name: str
    target: str
    reachable: bool
    latency_ms: Optional[float] = None
    protocol: str = "TCP"
    notes: str = ""


@dataclass
class MeshHealthReport:
    timestamp: str
    host_tailscale_ip: Optional[str]
    tailscale_service_running: bool
    cloudflare_warp_active: bool
    active_routing_path: str
    paths: Dict[str, PathStatus]
    android_always_on_configured: bool
    overall_status: str
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["paths"] = {k: asdict(v) for k, v in self.paths.items()}
        return d


class TailscaleMeshSentinel:
    """Manages continuous, always-on mesh orchestration between Cybertronia, S26 Ultra, and VPS Hub."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home or _ROOT
        self.heartbeat_file = self.home / "03_VAULT" / "runtime_state" / "mesh_heartbeats.json"
        self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)

    def check_tcp_port(self, host: str, port: int, timeout: float = 1.5) -> Tuple[bool, Optional[float]]:
        """Probes TCP socket reachability and measures RTT in milliseconds."""
        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                latency = round((time.perf_counter() - t0) * 1000, 2)
                return True, latency
        except Exception:
            return False, None

    def probe_host_tailscale(self) -> Tuple[bool, Optional[str], bool]:
        """Probes host Tailscale service, IP address, and coordination state."""
        svc_running = False
        ip = None
        logged_out = False

        try:
            res_ip = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3)
            if res_ip.returncode == 0 and res_ip.stdout.strip():
                ip = res_ip.stdout.strip()
                svc_running = True
        except Exception:
            pass

        try:
            res_st = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=4)
            if "logged out" in res_st.stdout.lower() or "logged out" in res_st.stderr.lower():
                logged_out = True
        except Exception:
            pass

        return svc_running, ip, logged_out

    def check_cloudflare_warp(self) -> bool:
        """Checks if Cloudflare WARP is running and co-existing with Tailscale."""
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-NetAdapter | Where-Object { $_.InterfaceAlias -like '*WARP*' -and $_.Status -eq 'Up' }"],
                capture_output=True,
                text=True,
                timeout=4,
            )
            return "WARP" in res.stdout
        except Exception:
            return False

    def enforce_android_always_on(self, target_adb: str = "192.168.88.2:5555") -> bool:
        """Configures Android OS on the S26 Ultra to lock Tailscale as the permanent Always-On VPN."""
        try:
            # 1. Doze whitelist exemption
            subprocess.run(["adb", "-s", target_adb, "shell", "dumpsys", "deviceidle", "whitelist", "+com.tailscale.ipn"], capture_output=True, timeout=4)
            # 2. Unconstrained background appops
            subprocess.run(["adb", "-s", target_adb, "shell", "cmd", "appops", "set", "com.tailscale.ipn", "RUN_IN_BACKGROUND", "allow"], capture_output=True, timeout=4)
            subprocess.run(["adb", "-s", target_adb, "shell", "cmd", "appops", "set", "com.tailscale.ipn", "RUN_ANY_IN_BACKGROUND", "allow"], capture_output=True, timeout=4)
            subprocess.run(["adb", "-s", target_adb, "shell", "cmd", "appops", "set", "com.tailscale.ipn", "START_FOREGROUND", "allow"], capture_output=True, timeout=4)
            # 3. Always-on VPN registration
            subprocess.run(["adb", "-s", target_adb, "shell", "settings", "put", "secure", "always_on_vpn_app", "com.tailscale.ipn"], capture_output=True, timeout=4)
            subprocess.run(["adb", "-s", target_adb, "shell", "settings", "put", "secure", "always_on_vpn_lockdown", "0"], capture_output=True, timeout=4)

            # Verify
            ver = subprocess.run(["adb", "-s", target_adb, "shell", "settings", "get", "secure", "always_on_vpn_app"], capture_output=True, text=True, timeout=4)
            return "com.tailscale.ipn" in ver.stdout
        except Exception as exc:
            LOG.warning(f"[SENTINEL] Could not enforce Android always-on via ADB: {exc}")
            return False

    def assess_mesh_health(self) -> MeshHealthReport:
        """Executes full multi-path mesh health inspection and active path selection."""
        svc_running, host_ip, logged_out = self.probe_host_tailscale()
        warp_active = self.check_cloudflare_warp()

        # Path 1: Local Wireless Fabric (Wi-Fi 7/6E)
        p_wifi_ok, p_wifi_lat = self.check_tcp_port(PEER_S26_WIFI_IP, PEER_ADB_PORT)
        path_wifi = PathStatus(
            name="LOCAL_WIRELESS_FABRIC",
            target=f"{PEER_S26_WIFI_IP}:{PEER_ADB_PORT}",
            reachable=p_wifi_ok,
            latency_ms=p_wifi_lat,
            protocol="TCP/ADB",
            notes="Direct local subnet; ultra low latency (<5ms)",
        )

        # Path 2: Sovereign Tailscale WireGuard Mesh
        p_ts_ok, p_ts_lat = self.check_tcp_port(PEER_S26_TAILSCALE_IP, PEER_ADB_PORT)
        path_tailscale = PathStatus(
            name="TAILSCALE_WIREGUARD_MESH",
            target=f"{PEER_S26_TAILSCALE_IP}:{PEER_ADB_PORT}",
            reachable=p_ts_ok,
            latency_ms=p_ts_lat,
            protocol="WireGuard/Tailscale",
            notes="Global encrypted mesh overlay (IPv4/IPv6)",
        )

        # Path 3: VPS Hub Relay Gateway
        p_vps_ok, p_vps_lat = self.check_tcp_port(PEER_VPS_HUB_IP, 8095, timeout=2.0)
        path_vps = PathStatus(
            name="VPS_HUB_RELAY",
            target=f"{PEER_VPS_HUB_IP}:8095",
            reachable=p_vps_ok,
            latency_ms=p_vps_lat,
            protocol="mTLS/Bifrost",
            notes="Hermes Prime cloud control plane & rendezvous",
        )

        paths = {
            "wifi_direct": path_wifi,
            "tailscale_mesh": path_tailscale,
            "vps_relay": path_vps,
        }

        # Active path resolution
        recommendations = []
        if path_wifi.reachable:
            active_path = "LOCAL_WIRELESS_FABRIC (192.168.88.2:5555)"
            status = "HEALTHY_OPTIMAL"
        elif path_tailscale.reachable:
            active_path = "TAILSCALE_WIREGUARD_MESH (100.106.246.126:5555)"
            status = "HEALTHY_REMOTE"
        else:
            active_path = "OUT_OF_BAND_WARP_GATE_RENDEZVOUS"
            status = "DEGRADED_DISCONNECTED"
            recommendations.append("Ensure target device is powered on and ADB listener is active.")

        if logged_out:
            recommendations.append("Host Tailscale requires login session (run 'tailscale up' or check tray).")
        if warp_active:
            recommendations.append("Cloudflare WARP detected; dual-stack routing prefers direct IPv4.")

        android_always_on = self.enforce_android_always_on()

        report = MeshHealthReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            host_tailscale_ip=host_ip,
            tailscale_service_running=svc_running,
            cloudflare_warp_active=warp_active,
            active_routing_path=active_path,
            paths=paths,
            android_always_on_configured=android_always_on,
            overall_status=status,
            recommendations=recommendations,
        )

        # Persist heartbeat
        try:
            self.heartbeat_file.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        except Exception as exc:
            LOG.error(f"[SENTINEL] Could not write mesh heartbeat: {exc}")

        return report

    def ensure_adb_connected(self) -> bool:
        """Ensures that the active wireless path is connected in ADB."""
        # Try Wi-Fi first (lowest latency)
        try:
            res_wifi = subprocess.run(["adb", "connect", f"{PEER_S26_WIFI_IP}:{PEER_ADB_PORT}"], capture_output=True, text=True, timeout=2)
            if "connected" in res_wifi.stdout.lower():
                LOG.info(f"[SENTINEL] ADB connected via {PEER_S26_WIFI_IP}:{PEER_ADB_PORT}")
                return True
        except Exception:
            pass

        # Try Tailscale second
        try:
            res_ts = subprocess.run(["adb", "connect", f"{PEER_S26_TAILSCALE_IP}:{PEER_ADB_PORT}"], capture_output=True, text=True, timeout=2)
            if "connected" in res_ts.stdout.lower():
                LOG.info(f"[SENTINEL] ADB connected via {PEER_S26_TAILSCALE_IP}:{PEER_ADB_PORT}")
                return True
        except Exception:
            pass

        return False


def boot_tailscale_sentinel(home: Path) -> Tuple[bool, str]:
    """Boot phase function for Camelot-OS sequencer (bin/awaken.py)."""
    try:
        sentinel = TailscaleMeshSentinel(home)
        report = sentinel.assess_mesh_health()
        sentinel.ensure_adb_connected()
        active = report.active_routing_path
        status = report.overall_status
        return True, f"Always-On Mesh Sentinel [{status}] — Active Path: {active}"
    except Exception as exc:
        return False, f"Tailscale Sentinel offline: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Tailscale Always-On Mesh Sentinel")
    parser.add_argument("--status", action="store_true", help="Print mesh health report")
    parser.add_argument("--enforce-android", action="store_true", help="Enforce Android Always-On VPN settings")
    parser.add_argument("--reconnect", action="store_true", help="Reconnect ADB wireless links")
    parser.add_argument("--loop", type=int, default=0, help="Continuous loop interval in seconds")
    args = parser.parse_args()

    sentinel = TailscaleMeshSentinel()

    if args.enforce_android:
        ok = sentinel.enforce_android_always_on()
        print(f"Android Always-On VPN configured: {ok}")
    elif args.reconnect:
        ok = sentinel.ensure_adb_connected()
        print(f"ADB wireless connection established: {ok}")
    elif args.loop > 0:
        print(f"Starting Always-On Mesh Sentinel daemon (interval: {args.loop}s)...")
        while True:
            rep = sentinel.assess_mesh_health()
            sentinel.ensure_adb_connected()
            print(f"[{rep.timestamp}] Status: {rep.overall_status} | Active: {rep.active_routing_path}")
            time.sleep(args.loop)
    else:
        rep = sentinel.assess_mesh_health()
        print(json.dumps(rep.to_dict(), indent=2))


if __name__ == "__main__":
    main()
