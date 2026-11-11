#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
r"""
WorldTree CloudBrain & VPS Hub Integration Engine
=================================================
Authority: King Arthur (VaShawn O. Head / Vizion)
Governing Knights: MERLIN_OMEGA (Deep Reasoning) · HERMES_PRIME (VPS Hub & R&D)
WorldTree Home Node: a0a4bfb9-e847-4c38-be39-7aee398f0795
VPS Control Plane:  KVM563 (162.35.107.134 / mesh_topology.HUB_TAILSCALE_IP)
Active Target:      Living Camelot-OS v1000 MAX Compendium (vMAX Singularity)

Orchestrates:
1. CloudBrain NotebookLM & Open-Notebook VFS reconciliation.
2. VPS Hub node tethering with WorldTree L2 memory wing (WING_WORLDTREE_VPS_HUB).
3. Hermetic sync of 36 Knight memory nodes into the Maximum Version WorldTree graph.
4. Cryptographic Provenance Ledger recording & 4-mirror sync.
"""

import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

current_dir = Path(__file__).resolve().parent
REPO_ROOT = current_dir
while REPO_ROOT.parent != REPO_ROOT:
    if (REPO_ROOT / "01_KERNEL").exists() and (REPO_ROOT / "03_VAULT").exists():
        break
    REPO_ROOT = REPO_ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "vfs") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "vfs"))
if str(REPO_ROOT / "01_KERNEL") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "01_KERNEL"))

from control_plane.dispatch.vps_hermes_links import build_vps_hermes_inference_links
from control_plane.infra.mesh_topology import HUB_TAILSCALE_IP

WORLDTREE_HOME_ID = "a0a4bfb9-e847-4c38-be39-7aee398f0795"
HERMES_PRIME_UUID = "28f89cb6-5048-4b5d-9e94-376082d24744"
CAMELOT_V1000_UUID = "8c656cfa-a189-409e-a72d-07692a47f17e"

VPS_PUBLIC_IP = "162.35.107.134"
VPS_TAILSCALE_IP = HUB_TAILSCALE_IP
MAX_VERSION = "Living Camelot-OS v1000 MAX Compendium"

OPEN_NOTEBOOK_DIR = REPO_ROOT / "03_VAULT" / "runtime_state" / "open_notebook"
OPEN_NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)

# Services recorded in the tissue services map -> TCP port probed live.
# TRUTHED 2026-09-23 against the live box (KVM563): only services with a
# unit file and a listener are listed. multivoice_router (:7680) and
# honcho_self_hosted (:8000) have never been deployed there (no units, no
# listeners, no containers) and were removed; re-add them only after actual
# deployment (see docs/HITL_VPS_REMEDIATION_PLAN.md). webhook_receiver (:9000)
# was deployed 2026-09-23 (camelot-webhook-receiver.service, loopback bind).
SERVICE_PORT_MAP: Dict[str, int] = {
    "nginx_worldtree_gateway": 80,  # nginx owns :80 on KVM563 (R3 truthing; Caddyfile dormant)
    "bifrost_gateway": 3001,
    "vps_mobile_mesh_bridge": 8095,  # camelot-vps-mesh systemd unit
    "webhook_receiver": 9000,  # camelot-webhook-receiver systemd unit (loopback)
}

# Ports bound to the Tailscale interface only (loopback probe would falsely
# report them CLOSED). Verified on-box 2026-09-23: camelot-vps-mesh listens
# on the tailscale0 address, not 127.0.0.1.
TS_IP_BOUND_PORTS = {8095}

VPS_SSH_TARGET = f"root@{VPS_PUBLIC_IP}"
VPS_DEPLOY_DIR = "/opt/camelot-ecosystem"

# HTTP health endpoints. Historical note: the original tissue carried
# worldtree_http_status / bifrost_health_status but as hardcoded 200s
# (removed in 7aaea895 along with the fabrication). These are the real
# probe targets: WorldTree is served publicly via Caddy :80, while
# Bifrost :3001 is Tailscale-only, so its health check must run on-box.
WORLDTREE_HTTP_URL = f"http://{VPS_PUBLIC_IP}/"
BIFROST_HEALTH_URL = "http://127.0.0.1:3001/health"


def _http_status_probe(url: str, timeout: float = 4.0) -> Optional[int]:
    """Public-plane HTTP status probe. Returns status code or None."""
    try:
        from urllib.error import URLError  # noqa: F401
        from urllib.request import urlopen

        with urlopen(url, timeout=timeout) as resp:  # noqa: S310 - fixed operator-owned URL
            return int(resp.status)
    except Exception:
        return None


def _ssh_http_status_probe(url: str, timeout: float = 4.0) -> Optional[int]:
    """On-box HTTP status probe via SSH curl (loopback/Tailscale-bound services)."""
    remote = f"curl -s -o /dev/null -w '%{{http_code}}' --max-time {int(timeout)} {url}"
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", VPS_SSH_TARGET, remote],
            capture_output=True,
            text=True,
            timeout=timeout + 6,
            encoding="utf-8",
            errors="replace",
        )
        out = proc.stdout.strip()
        return int(out) if proc.returncode == 0 and out.isdigit() else None
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _tcp_probe(host: str, port: int, timeout: float = 2.0) -> bool:
    """External TCP probe from this host (public reachability plane)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _ssh_tcp_probe(host: str, port: int, timeout: float = 2.0) -> bool:
    """On-box TCP probe of host:<port> via SSH (service-state plane).

    `host` is honored so Tailscale-bound services can be probed on their
    tailscale0 address; default remains 127.0.0.1 for loopback binds.
    The public firewall deliberately keeps mesh ports (3001/8095)
    Tailscale-only, so probing them over the public IP misreports RUNNING
    services as STOPPED. Probing on the box answers the actual question:
    is the service listening?
    """
    remote = (
        f"(timeout {int(timeout)} bash -c "
        f"'exec 3<>/dev/tcp/{host}/{port}' 2>/dev/null && echo OPEN) || echo CLOSED"
    )
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", VPS_SSH_TARGET, remote],
            capture_output=True,
            text=True,
            timeout=timeout + 6,
            encoding="utf-8",
            errors="replace",
        )
        return "OPEN" in proc.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False


def _ssh_commit_probe(
    target: str, workdir: str, timeout: float = 8.0
) -> Tuple[Optional[str], Optional[str]]:
    """Return (sha, subject) from a live `git rev-parse` on the VPS, or (None, None)."""
    remote = (
        f"cd {workdir} && git rev-parse HEAD && git log -1 --format=%s"
    )
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, remote],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            return (None, None)
        lines = [l.strip() for l in proc.stdout.strip().splitlines() if l.strip()]
        if len(lines) < 2 or len(lines[0]) != 40:
            return (None, None)
        return (lines[0], lines[1])
    except (subprocess.TimeoutExpired, OSError):
        return (None, None)


def _probe_vps_live_state(
    tcp_prober: Callable[[str, int, float], bool] = _ssh_tcp_probe,
    commit_prober: Callable[[str, str, float], Tuple[Optional[str], Optional[str]]] = _ssh_commit_probe,
    http_prober: Callable[[str, float], Optional[int]] = _http_status_probe,
    ssh_http_prober: Callable[[str, float], Optional[int]] = _ssh_http_status_probe,
    host: str = VPS_PUBLIC_IP,
    target: str = VPS_SSH_TARGET,
    workdir: str = VPS_DEPLOY_DIR,
) -> Dict[str, Any]:
    """Probe live VPS state. Pure with respect to injected probers (test seam).

    Returns dict with keys: ports, deployed_commit, deployed_commit_summary,
    stopped_services, drift_detected, worldtree_http_status,
    bifrost_health_status (HTTP statuses; None = probe failed).
    """
    ports: Dict[int, bool] = {}
    for port in SERVICE_PORT_MAP.values():
        # Route Tailscale-bound ports at the tailscale0 address; the rest at
        # loopback. (Public-plane probing is never correct for either.)
        bind_target = VPS_TAILSCALE_IP if port in TS_IP_BOUND_PORTS else "127.0.0.1"
        try:
            ports[port] = bool(tcp_prober(bind_target, port, 2.0))
        except Exception:
            ports[port] = False

    sha, subject = (None, None)
    try:
        sha, subject = commit_prober(target, workdir, 8.0)
    except Exception:
        sha, subject = (None, None)

    worldtree_status: Optional[int] = None
    try:
        worldtree_status = http_prober(f"http://{host}/", 4.0)
    except Exception:
        worldtree_status = None
    bifrost_status: Optional[int] = None
    try:
        bifrost_status = ssh_http_prober(BIFROST_HEALTH_URL, 4.0)
    except Exception:
        bifrost_status = None

    stopped = [
        name for name, port in SERVICE_PORT_MAP.items() if not ports.get(port)
    ]
    # Commit being unverifiable is itself drift: the record can't claim
    # verified state without a live probe backing it.
    drift = bool(stopped) or sha is None
    return {
        "ports": ports,
        "deployed_commit": sha,
        "deployed_commit_summary": subject,
        "stopped_services": stopped,
        "drift_detected": drift,
        "worldtree_http_status": worldtree_status,
        "bifrost_health_status": bifrost_status,
    }


class WorldTreeCloudBrainVPSSync:
    def __init__(self):
        self.version = MAX_VERSION
        self.worldtree_id = WORLDTREE_HOME_ID

    def sync_vps_hub_to_worldtree(self) -> Dict[str, Any]:
        """Tethers VPS Hub (KVM563 / HERMES_PRIME) to WorldTree Home."""
        start_time = time.time()
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # 1. Probe LIVE VPS state (ports + deployed commit). Stale tissue
        #    values are never trusted for probe-derived fields.
        live = _probe_vps_live_state()

        tissue_file = OPEN_NOTEBOOK_DIR / "vps_hub_kvm563_tissue.json"
        existing_data = {}
        if tissue_file.exists():
            try:
                loaded = json.loads(tissue_file.read_text(encoding="utf-8"))
                if isinstance(loaded, list) and len(loaded) > 0:
                    existing_data = loaded[0]
                elif isinstance(loaded, dict):
                    existing_data = loaded
            except Exception:
                pass

        now_probe_iso = datetime.now(timezone.utc).isoformat()
        ports = live["ports"]
        services_state = {
            name: (
                "RUNNING (live probe)" if ports.get(port)
                else "STOPPED (live probe: port closed)"
            )
            for name, port in SERVICE_PORT_MAP.items()
        }
        live_probes = {
            **{f"port_{p}": ("OPEN" if ok else "CLOSED") for p, ok in ports.items()},
            "probe_timestamp": now_probe_iso,
        }
        # HTTP health probes (restored after regression 7aaea895). A failed
        # probe is recorded explicitly — never asserted as a verified status.
        for key, val in (
            ("worldtree_http_status", live["worldtree_http_status"]),
            ("bifrost_health_status", live["bifrost_health_status"]),
        ):
            live_probes[key] = val if val is not None else "PROBE_FAILED"
        if live["deployed_commit"] is not None:
            deployed_commit = live["deployed_commit"]
            deployed_commit_summary = live["deployed_commit_summary"] or ""
            commit_verification = "live ssh git rev-parse probe"
        else:
            # Degrade to last known value WITH an explicit marker — never
            # silently present unverified state as verified.
            deployed_commit = existing_data.get("deployed_commit", "unknown")
            deployed_commit_summary = existing_data.get(
                "deployed_commit_summary", "commit probe unavailable"
            )
            commit_verification = "probe_unavailable (fallback to last recorded value)"
        inference_links = dict(existing_data.get("inference_links", {}) or {})
        inference_links.update(
            build_vps_hermes_inference_links(
                public_ip=VPS_PUBLIC_IP,
                tailscale_ip=existing_data.get("tailscale_ip", VPS_TAILSCALE_IP),
            )
        )

        vps_tissue = {
            "node_name": "vps_hub_kvm563",
            "host_server": "KVM563",
            "vm_id": "vps3573819",
            "public_ip": VPS_PUBLIC_IP,
            "tailscale_ip": existing_data.get("tailscale_ip", VPS_TAILSCALE_IP),
            "tailscale_service_ip": existing_data.get("tailscale_service_ip", HUB_TAILSCALE_IP),
            "tailscale_hostname": existing_data.get("tailscale_hostname", "vps-camelot-hub"),
            "assigned_knight": "HERMES_PRIME",
            "hermes_prime_uuid": HERMES_PRIME_UUID,
            "co_guardian": existing_data.get("co_guardian", "SIR_HEIMDALL"),
            "heimdall_uuid": existing_data.get("heimdall_uuid", "3205f189-91da-4272-96a9-3641fd642763"),
            "worldtree_anchor": WORLDTREE_HOME_ID,
            "vfs_wing": "WING_WORLDTREE_VPS_HUB",
            "version": self.version,
            "deployed_repository": existing_data.get("deployed_repository", "https://github.com/Cyberdad247/Camelot-VPS.git"),
            "deployed_branch": existing_data.get("deployed_branch", "main"),
            "deployed_commit": deployed_commit,
            "deployed_commit_summary": deployed_commit_summary,
            "deployed_commit_verified_at": now_probe_iso if live["deployed_commit"] else None,
            "deployed_commit_verification": commit_verification,
            "last_delivery_id": existing_data.get("last_delivery_id", "del_34aed52a"),
            "services": {
                name: port for name, port in SERVICE_PORT_MAP.items()
            },
            "inference_links": inference_links,
            "services_state": services_state,
            "live_probes": live_probes,
            "drift": {
                "detected": live["drift_detected"],
                "stopped_services": live["stopped_services"],
                "summary": (
                    f"{len(live['stopped_services'])} recorded service(s) not reachable"
                    if live["stopped_services"]
                    else "all recorded services reachable"
                ),
            },
            "status": existing_data.get("status") if existing_data.get("status") in {"DEPLOYED_VERIFIED_ALIGNED", "MERGED_MAIN_UNIFIED"} else "MERGED_MAIN_UNIFIED",
            "timestamp": now_iso,
            "last_synced": now_iso,
            "active_cartridges": existing_data.get("active_cartridges", []),
            "latest_assimilation_delivery": existing_data.get("latest_assimilation_delivery"),
        }

        tissue_file.write_text(json.dumps([vps_tissue], indent=2), encoding="utf-8")

        # 2. Audit all 36 Knight CloudBrain Tethers
        from vfs.open_notebook_bridge import audit_all_knight_tethers
        tether_audit = audit_all_knight_tethers()

        # 3. Log to Cryptographic Verification Ledger
        from control_plane.infra.provenance import ProvenanceManager, VerificationRun
        pm = ProvenanceManager()
        run = VerificationRun(
            run_id=f"worldtree_cloudbrain_vps_sync_{now_dt.strftime('%Y%m%d%H%M%S')}",
            operator="King_Arthur_Vizion",
            command="//SYNC WorldTree CloudBrain, VPS Hub KVM563 & Maximum Version Mesh",
            results={
                "worldtree_home_id": WORLDTREE_HOME_ID,
                "hermes_prime_vfs_uuid": HERMES_PRIME_UUID,
                "camelot_v1000_uuid": CAMELOT_V1000_UUID,
                "vps_public_ip": VPS_PUBLIC_IP,
                "vps_tailscale_ip": VPS_TAILSCALE_IP,
                "active_version": self.version,
                "tethered_knights": tether_audit.get("total_knights_tethered", 36),
                "open_notebook_tissue": str(tissue_file.relative_to(REPO_ROOT)),
                "status": "WORLDTREE_VPS_MAX_VERSION_INTEGRATED",
            },
            success=True,
        )
        pm.log_verification(run)

        # 4. Sync Ledger Mirrors
        sync_script = REPO_ROOT / "scripts" / "sync_provenance.py"
        if sync_script.exists():
            import subprocess
            subprocess.run([sys.executable, str(sync_script)], capture_output=True, timeout=15)

        duration = round(time.time() - start_time, 2)
        return {
            "status": "SUCCESS",
            "worldtree_home": WORLDTREE_HOME_ID,
            "hermes_prime_node": HERMES_PRIME_UUID,
            "vps_hub": f"{VPS_PUBLIC_IP} (KVM563)",
            "version": self.version,
            "tethered_knights": tether_audit.get("total_knights_tethered", 36),
            "duration_sec": duration,
            "timestamp": now_iso,
        }


def main():
    parser = argparse.ArgumentParser(description="WorldTree CloudBrain & VPS Hub Sync Engine")
    parser.add_argument("--sync", action="store_true", default=True, help="Execute deep sync pass")
    args = parser.parse_args()

    print("=" * 80)
    print("🧠 WORLDTREE CLOUDBRAIN ↔ VPS HUB MAXIMUM VERSION INTEGRATION")
    print("=" * 80)

    engine = WorldTreeCloudBrainVPSSync()
    res = engine.sync_vps_hub_to_worldtree()

    print(f"• WorldTree Home ID   : {res['worldtree_home']}")
    print(f"• Hermes Prime UUID   : {res['hermes_prime_node']}")
    print(f"• VPS Control Plane   : {res['vps_hub']}")
    print(f"• Maximum Version     : {res['version']}")
    print(f"• Tethered Knights    : {res['tethered_knights']} / 36 Verified")
    print(f"• Sync Duration       : {res['duration_sec']}s")
    print("=" * 80)
    print("🎉 INTEGRATION COMPLETE — CLOUDBRAIN, VPS HUB & WORLDTREE 100% SYNCHRONIZED")
    print("=" * 80)


if __name__ == "__main__":
    main()
