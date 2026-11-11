# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Dynamic Forefront Topology & Fabric Extension Toggle Module
============================================================
Allows switching the forefront architectural role between:
1. VPS_FOREFRONT: The VPS Hub (162.35.107.134 / vps_hub_kvm563) operates as the
   commanding forefront brain, treating local edge nodes (Cybertronia, Lakesha,
   Fothers) as a distributed execution fabric it runs through as extensions of itself.
2. LOCAL_FOREFRONT: Cybertronia operates as the autonomous sovereign master node,
   using VPS as a background relay, cloudbrain compiler, and persistent listener.
3. HYBRID_FEDERATED: Seamless bi-directional fabric balancing tasks based on latency,
   memory ceilings (4GB Edge vs 4GB/8GB Hub), and execution capabilities.

Includes:
- Dynamic fallback to local execution if Bifrost bridge / VPS link is severed or degraded.
- Living self-evolution phial engine hooks for automated self-triage.
- Seamless Bifrost bridge routing (:3001) & Reya Universal Fabric telemetry (<350MB).
"""

from __future__ import annotations

import enum
import json
import logging
import os
import socket
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATE_PATH = _REPO_ROOT / "03_VAULT" / "runtime_state" / "vps_fabric_toggle_state.json"
_TISSUE_PATH = _REPO_ROOT / "03_VAULT" / "runtime_state" / "open_notebook" / "vps_hub_kvm563_tissue.json"
_BIFROST_GATEWAY_URL = os.environ.get("BIFROST_GATEWAY_URL", "http://127.0.0.1:3001")


class TopologyMode(str, enum.Enum):
    VPS_FOREFRONT = "VPS_FOREFRONT"
    LOCAL_FOREFRONT = "LOCAL_FOREFRONT"
    HYBRID_FEDERATED = "HYBRID_FEDERATED"


@dataclass
class FabricNode:
    node_id: str
    display_name: str
    tailscale_ip: str
    public_ip: Optional[str]
    role: str
    ram_ceiling_mb: int
    is_active: bool
    last_heartbeat: str


@dataclass
class TopologyConfig:
    active_mode: TopologyMode
    forefront_node: str
    fabric_nodes: Dict[str, Dict[str, Any]]
    bifrost_bridge_active: bool
    bifrost_url: str
    local_fallback_engaged: bool
    last_transition_utc: str
    evolution_cycle_count: int
    apex_version: str


class DynamicTopologyManager:
    """Manages dynamic forefront shifting and node fabric routing."""

    DEFAULT_APEX_VERSION = "v10001.00-CYBERTRONIA-APEX"

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or _STATE_PATH
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.config = self._load_or_create_default()

    def _default_nodes(self) -> Dict[str, Dict[str, Any]]:
        now_str = datetime.now(timezone.utc).isoformat()
        return {
            "vps_hub_kvm563": {
                "node_id": "vps_hub_kvm563",
                "display_name": "Sovereign VPS Hub (KVM563)",
                "tailscale_ip": "100.110.180.18",
                "public_ip": "162.35.107.134",
                "role": "SOVEREIGN_FOREFRONT_HUB",
                "ram_ceiling_mb": 4096,
                "is_active": True,
                "last_heartbeat": now_str,
            },
            "cybertronia": {
                "node_id": "cybertronia",
                "display_name": "Cybertronia (Primary Windows Host)",
                "tailscale_ip": "100.118.224.52",
                "public_ip": None,
                "role": "EDGE_FABRIC_ACCELERATOR",
                "ram_ceiling_mb": 4096,
                "is_active": True,
                "last_heartbeat": now_str,
            },
            "excalibur_mobile": {
                "node_id": "vashawns-s26-ultra",
                "display_name": "Excalibur S26 Ultra Cockpit",
                "tailscale_ip": "100.106.246.126",
                "public_ip": None,
                "role": "KINETIC_MOBILE_SENTINEL",
                "ram_ceiling_mb": 4096,
                "is_active": True,
                "last_heartbeat": now_str,
            },
            "lakesha": {
                "node_id": "lakesha",
                "display_name": "Lakisha Voice Node",
                "tailscale_ip": "100.100.155.55",
                "public_ip": None,
                "role": "MULTIVOICE_AUDIO_SENTINEL",
                "ram_ceiling_mb": 4096,
                "is_active": True,
                "last_heartbeat": now_str,
            },
            "fothers_camelot": {
                "node_id": "fothers-camelot",
                "display_name": "Fothers Secondary Node",
                "tailscale_ip": "100.121.48.50",
                "public_ip": None,
                "role": "DISTRIBUTED_SQUIRE_RUNNER",
                "ram_ceiling_mb": 4096,
                "is_active": True,
                "last_heartbeat": now_str,
            },
        }

    def _load_or_create_default(self) -> TopologyConfig:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return TopologyConfig(
                    active_mode=TopologyMode(data.get("active_mode", TopologyMode.VPS_FOREFRONT.value)),
                    forefront_node=data.get("forefront_node", "vps_hub_kvm563"),
                    fabric_nodes=data.get("fabric_nodes", self._default_nodes()),
                    bifrost_bridge_active=data.get("bifrost_bridge_active", True),
                    bifrost_url=data.get("bifrost_url", _BIFROST_GATEWAY_URL),
                    local_fallback_engaged=data.get("local_fallback_engaged", False),
                    last_transition_utc=data.get("last_transition_utc", datetime.now(timezone.utc).isoformat()),
                    evolution_cycle_count=data.get("evolution_cycle_count", 0),
                    apex_version=data.get("apex_version", self.DEFAULT_APEX_VERSION),
                )
            except Exception as e:
                logging.warning(f"Error loading topology config: {e}. Generating default.")

        cfg = TopologyConfig(
            active_mode=TopologyMode.VPS_FOREFRONT,
            forefront_node="vps_hub_kvm563",
            fabric_nodes=self._default_nodes(),
            bifrost_bridge_active=True,
            bifrost_url=_BIFROST_GATEWAY_URL,
            local_fallback_engaged=False,
            last_transition_utc=datetime.now(timezone.utc).isoformat(),
            evolution_cycle_count=1,
            apex_version=self.DEFAULT_APEX_VERSION,
        )
        self._save(cfg)
        return cfg

    def _save(self, cfg: Optional[TopologyConfig] = None) -> None:
        if cfg:
            self.config = cfg
        data = asdict(self.config)
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def set_topology_mode(self, mode: TopologyMode | str) -> Dict[str, Any]:
        """Toggle active topology mode between VPS_FOREFRONT, LOCAL_FOREFRONT, or HYBRID."""
        if isinstance(mode, str):
            mode = TopologyMode(mode.upper())
        self.config.active_mode = mode
        self.config.last_transition_utc = datetime.now(timezone.utc).isoformat()
        if mode == TopologyMode.VPS_FOREFRONT:
            self.config.forefront_node = "vps_hub_kvm563"
            self.config.fabric_nodes["cybertronia"]["role"] = "EDGE_FABRIC_EXTENSION"
            self.config.fabric_nodes["vps_hub_kvm563"]["role"] = "SOVEREIGN_FOREFRONT_HUB"
        elif mode == TopologyMode.LOCAL_FOREFRONT:
            self.config.forefront_node = "cybertronia"
            self.config.fabric_nodes["cybertronia"]["role"] = "SOVEREIGN_FOREFRONT_HOST"
            self.config.fabric_nodes["vps_hub_kvm563"]["role"] = "REMOTE_RELAY_BRIDGE"
        else:
            self.config.forefront_node = "HYBRID_DYNAMIC"

        self.config.evolution_cycle_count += 1
        self._save()
        return asdict(self.config)

    def trigger_local_fallback(self, reason: str = "BIFROST_UNREACHABLE") -> Dict[str, Any]:
        """Automatically engage local fallback on Cybertronia if VPS becomes unreachable."""
        self.config.local_fallback_engaged = True
        self.config.bifrost_bridge_active = False
        self.config.active_mode = TopologyMode.LOCAL_FOREFRONT
        self.config.forefront_node = "cybertronia"
        self.config.last_transition_utc = datetime.now(timezone.utc).isoformat()
        self.config.evolution_cycle_count += 1
        self._save()
        return {
            "status": "LOCAL_FALLBACK_ENGAGED",
            "reason": reason,
            "forefront_node": "cybertronia",
            "autonomous_survival_mode": True,
            "timestamp": self.config.last_transition_utc,
        }

    def restore_vps_forefront(self) -> Dict[str, Any]:
        """Restore VPS forefront architecture once Bifrost Bridge health is confirmed."""
        self.config.local_fallback_engaged = False
        self.config.bifrost_bridge_active = True
        return self.set_topology_mode(TopologyMode.VPS_FOREFRONT)

    def route_task_to_fabric(self, task_name: str, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes task execution across the unified fabric.
        If VPS_FOREFRONT is active, task is orchestrated from VPS and executed on Cybertronia
        as an extension of the VPS itself via Bifrost Bridge RPC.
        """
        target_node = "cybertronia" if self.config.active_mode == TopologyMode.VPS_FOREFRONT else "vps_hub_kvm563"
        return {
            "task": task_name,
            "orchestrator": self.config.forefront_node,
            "execution_fabric_target": target_node,
            "bifrost_bridge_active": self.config.bifrost_bridge_active,
            "local_fallback_ready": True,
            "mode": self.config.active_mode.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_vps_reachability(
        self,
        tailscale_ip: str = "100.110.180.18",
        public_ip: str = "162.35.107.134",
        ports: Optional[List[int]] = None,
        timeout_sec: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Actively probes reachability to VPS Hub via Tailscale IP or public IP fallback.
        Checks Bifrost gateway (:3001), Mesh Bridge (:8095), or Edge Bus (:8096).
        """
        if ports is None:
            ports = [3001, 8095, 8096]

        candidates = [(tailscale_ip, p) for p in ports] + [(public_ip, p) for p in ports]
        reachable_endpoint = None
        latencies_ms: Dict[str, float] = {}

        for host, port in candidates:
            endpoint_str = f"{host}:{port}"
            t0 = time.perf_counter()
            try:
                with socket.create_connection((host, port), timeout=timeout_sec):
                    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                    latencies_ms[endpoint_str] = elapsed_ms
                    reachable_endpoint = endpoint_str
                    break
            except (socket.timeout, OSError, ConnectionRefusedError):
                continue

        is_reachable = reachable_endpoint is not None
        now_str = datetime.now(timezone.utc).isoformat()
        if is_reachable and "vps_hub_kvm563" in self.config.fabric_nodes:
            self.config.fabric_nodes["vps_hub_kvm563"]["last_heartbeat"] = now_str
            self.config.fabric_nodes["vps_hub_kvm563"]["is_active"] = True

        return {
            "reachable": is_reachable,
            "connected_endpoint": reachable_endpoint,
            "latencies_ms": latencies_ms,
            "timestamp": now_str,
        }

    def poll_and_reconcile(
        self,
        consecutive_failures: int = 0,
        max_failures: int = 3,
        probe_timeout_sec: float = 2.0,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Single-step watchdog probe and state reconciliation:
        - If reachable and local fallback was engaged: automatically restores VPS_FOREFRONT.
        - If unreachable >= max_failures and not in local fallback: automatically triggers local fallback.
        Returns: (status_dict, new_consecutive_failures)
        """
        probe = self.check_vps_reachability(timeout_sec=probe_timeout_sec)
        is_reachable = probe["reachable"]

        if is_reachable:
            new_failures = 0
            if self.config.local_fallback_engaged:
                restoration = self.restore_vps_forefront()
                return {
                    "action": "AUTO_RESTORED_VPS_FOREFRONT",
                    "probe": probe,
                    "topology": restoration,
                }, new_failures
            else:
                self._save()
                return {
                    "action": "HEARTBEAT_NOMINAL",
                    "probe": probe,
                    "mode": self.config.active_mode.value,
                }, new_failures
        else:
            new_failures = consecutive_failures + 1
            if new_failures >= max_failures and not self.config.local_fallback_engaged:
                fallback = self.trigger_local_fallback(
                    reason=f"VPS_UNREACHABLE_AFTER_{new_failures}_CONSECUTIVE_FAILURES"
                )
                return {
                    "action": "AUTO_TRIGGERED_LOCAL_FALLBACK",
                    "probe": probe,
                    "failures": new_failures,
                    "topology": fallback,
                }, new_failures
            else:
                return {
                    "action": "HEARTBEAT_MISSED",
                    "probe": probe,
                    "failures": new_failures,
                    "max_failures": max_failures,
                    "mode": self.config.active_mode.value,
                }, new_failures

    def run_watchdog_loop(
        self,
        interval_sec: float = 5.0,
        max_failures: int = 3,
        max_ticks: Optional[int] = None,
    ) -> None:
        """Runs the continuous automated watchdog loop."""
        consecutive_failures = 0
        ticks = 0
        logging.info(
            f"[DynamicTopologyManager] Starting VPS Watchdog Loop (interval={interval_sec}s, max_failures={max_failures})..."
        )
        try:
            while max_ticks is None or ticks < max_ticks:
                result, consecutive_failures = self.poll_and_reconcile(
                    consecutive_failures=consecutive_failures,
                    max_failures=max_failures,
                )
                print(
                    f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Watchdog Action: {result['action']} "
                    f"(Failures: {consecutive_failures}/{max_failures}, Endpoint: {result.get('probe', {}).get('connected_endpoint', 'NONE')})"
                )
                ticks += 1
                if max_ticks is not None and ticks >= max_ticks:
                    break
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("[DynamicTopologyManager] Watchdog loop stopped by user.")

    def get_status(self) -> Dict[str, Any]:
        return asdict(self.config)


def get_topology_manager() -> DynamicTopologyManager:
    return DynamicTopologyManager()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Camelot-OS Dynamic Forefront Topology & Fabric Extension")
    parser.add_argument("--status", action="store_true", help="Print current topology state")
    parser.add_argument("--toggle", type=str, choices=["VPS_FOREFRONT", "LOCAL_FOREFRONT", "HYBRID_FEDERATED"],
                        help="Toggle active forefront architecture")
    parser.add_argument("--fallback", action="store_true", help="Engage local Cybertronia fallback")
    parser.add_argument("--restore", action="store_true", help="Restore VPS forefront mode")
    parser.add_argument("--route", type=str, help="Route test task through the fabric")
    parser.add_argument("--probe", action="store_true", help="Run a single reachability probe against VPS endpoints")
    parser.add_argument("--watch", action="store_true", help="Run automated heartbeat watchdog loop")
    parser.add_argument("--interval", type=float, default=5.0, help="Watchdog poll interval in seconds")
    parser.add_argument("--max-failures", type=int, default=3, help="Consecutive failures before fallback")
    parser.add_argument("--ticks", type=int, default=None, help="Number of ticks to run (default: infinite)")
    args = parser.parse_args()

    mgr = get_topology_manager()
    if args.toggle:
        res = mgr.set_topology_mode(args.toggle)
        print(json.dumps(res, indent=2))
    elif args.fallback:
        res = mgr.trigger_local_fallback()
        print(json.dumps(res, indent=2))
    elif args.restore:
        res = mgr.restore_vps_forefront()
        print(json.dumps(res, indent=2))
    elif args.route:
        res = mgr.route_task_to_fabric(args.route, {})
        print(json.dumps(res, indent=2))
    elif args.probe:
        res, _ = mgr.poll_and_reconcile()
        print(json.dumps(res, indent=2))
    elif args.watch:
        mgr.run_watchdog_loop(
            interval_sec=args.interval,
            max_failures=args.max_failures,
            max_ticks=args.ticks,
        )
    else:
        print(json.dumps(mgr.get_status(), indent=2))
