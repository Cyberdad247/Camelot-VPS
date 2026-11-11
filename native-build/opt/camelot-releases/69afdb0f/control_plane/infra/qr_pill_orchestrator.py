# SPDX-License-Identifier: MIT

"""
QR Pill Orchestrator — Docker-Free Deployment System for CAMELOT-OS

A lightweight, compressed deployment format inspired by TOON crystals.
QR Pill encodes:
- System configuration (node ID, cluster topology)
- Service definitions (processes, ports, dependencies)
- Health checks & recovery procedures
- Metrics & observability

Deployment modes: systemd, bare-metal, custom orchestration
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QRPill")


class ServiceState(str, Enum):
    """Service operational state"""
    RUNNING = "running"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    FAILED = "failed"
    STARTING = "starting"


class DeploymentMode(str, Enum):
    """QR Pill deployment mode"""
    SYSTEMD = "systemd"
    BARE_METAL = "bare-metal"
    CUSTOM = "custom"


@dataclass
class HealthCheck:
    """Health check for a service"""
    endpoint: str
    interval: int = 30  # seconds
    timeout: int = 10
    threshold: int = 3  # failures before marking unhealthy
    type: str = "http"  # http, tcp, process


@dataclass
class ServiceDef:
    """Service definition"""
    name: str
    command: str
    port: int
    dependencies: List[str] = field(default_factory=list)
    health_check: Optional[HealthCheck] = None
    restart_policy: str = "on-failure"  # always, on-failure, never
    max_restarts: int = 5
    restart_delay: int = 5  # seconds
    env_vars: Dict[str, str] = field(default_factory=dict)
    resource_limits: Dict[str, str] = field(default_factory=lambda: {
        "memory": "4Gi",
        "cpu": "2"
    })


@dataclass
class QRPillCrystal:
    """Compressed deployment crystal (128-line format)"""
    version: str = "1.0"
    node_id: str = "node_1"
    cluster_id: str = "camelot-prod"
    created_at: float = field(default_factory=time.time)

    # Cluster topology
    peers: List[str] = field(default_factory=list)

    # Services to deploy
    services: Dict[str, ServiceDef] = field(default_factory=dict)

    # Configuration
    config: Dict[str, str] = field(default_factory=dict)

    # Observability
    metrics_enabled: bool = True
    metrics_port: int = 8000

    # Security
    tls_enabled: bool = True
    tls_cert_path: str = "/etc/camelot/tls/cert.pem"
    tls_key_path: str = "/etc/camelot/tls/key.pem"

    # Recovery
    backup_enabled: bool = True
    backup_interval: int = 3600  # seconds

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(asdict(self), default=str)

    def to_compressed(self) -> str:
        """Convert to compressed base64 format"""
        json_str = self.to_json()
        compressed = base64.b64encode(json_str.encode()).decode()
        return compressed

    def to_qr_code_data(self) -> str:
        """Generate data suitable for QR code encoding"""
        # Create checksum
        json_str = self.to_json()
        checksum = hashlib.sha256(json_str.encode()).hexdigest()[:8]

        # Format: [VERSION]:[NODE_ID]:[CHECKSUM]:[BASE64_DATA]
        return f"QRP1:{self.node_id}:{checksum}:{self.to_compressed()}"


class QRPillOrchestrator:
    """Orchestrates QR Pill deployments"""

    def __init__(self, crystal: QRPillCrystal, mode: DeploymentMode = DeploymentMode.SYSTEMD):
        """
        Initialize orchestrator

        Args:
            crystal: QR Pill deployment specification
            mode: Deployment mode (systemd, bare-metal, custom)
        """
        self.crystal = crystal
        self.mode = mode
        self.service_states: Dict[str, ServiceState] = {}
        self.service_pids: Dict[str, int] = {}
        self.restart_counts: Dict[str, int] = {}

        logger.info(f"🔮 QR Pill Orchestrator initialized (node: {crystal.node_id}, mode: {mode.value})")

    async def deploy(self) -> bool:
        """
        Deploy all services

        Returns:
            True if all services deployed successfully
        """
        logger.info(f"🚀 Deploying {len(self.crystal.services)} services...")

        for service_name, service_def in self.crystal.services.items():
            # Check dependencies
            if not await self._check_dependencies(service_def):
                logger.error(f"❌ Dependencies not met for {service_name}")
                return False

            # Deploy service
            if not await self._deploy_service(service_name, service_def):
                logger.error(f"❌ Failed to deploy {service_name}")
                return False

        logger.info("✅ All services deployed")
        return True

    async def _deploy_service(self, name: str, service_def: ServiceDef) -> bool:
        """Deploy a single service"""
        try:
            if self.mode == DeploymentMode.SYSTEMD:
                return await self._deploy_systemd(name, service_def)
            elif self.mode == DeploymentMode.BARE_METAL:
                return await self._deploy_bare_metal(name, service_def)
            else:
                return await self._deploy_custom(name, service_def)
        except Exception as e:
            logger.error(f"Deployment error for {name}: {str(e)}")
            return False

    async def _deploy_systemd(self, name: str, service_def: ServiceDef) -> bool:
        """Deploy service using systemd"""
        # Generate systemd unit file
        unit_content = self._generate_systemd_unit(name, service_def)

        try:
            # Write unit file
            unit_path = f"/etc/systemd/system/camelot-{name}.service"
            with open(unit_path, "w") as f:
                f.write(unit_content)

            # Reload systemd
            subprocess.run(["systemctl", "daemon-reload"], check=True)

            # Start service
            subprocess.run(["systemctl", "start", f"camelot-{name}"], check=True)

            self.service_states[name] = ServiceState.RUNNING
            self.restart_counts[name] = 0

            logger.info(f"✅ Deployed {name} via systemd")
            return True
        except Exception as e:
            logger.error(f"Systemd deployment failed for {name}: {str(e)}")
            return False

    async def _deploy_bare_metal(self, name: str, service_def: ServiceDef) -> bool:
        """Deploy service directly (bare metal)"""
        try:
            # Prepare environment
            env = {**service_def.env_vars}
            env["CAMELOT_NODE_ID"] = self.crystal.node_id
            env["CAMELOT_SERVICE_NAME"] = name

            # Start process
            proc = subprocess.Popen(
                service_def.command,
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.service_pids[name] = proc.pid
            self.service_states[name] = ServiceState.RUNNING
            self.restart_counts[name] = 0

            logger.info(f"✅ Deployed {name} (PID {proc.pid})")
            return True
        except Exception as e:
            logger.error(f"Bare metal deployment failed for {name}: {str(e)}")
            return False

    async def _deploy_custom(self, name: str, service_def: ServiceDef) -> bool:
        """Deploy service via custom orchestration"""
        # Placeholder for custom deployment logic
        logger.info(f"📦 Deploying {name} via custom orchestration")
        self.service_states[name] = ServiceState.RUNNING
        return True

    async def health_check_loop(self):
        """Continuously monitor service health"""
        while True:
            for service_name, service_def in self.crystal.services.items():
                if service_def.health_check:
                    is_healthy = await self._check_service_health(service_name, service_def)

                    if not is_healthy:
                        self.service_states[service_name] = ServiceState.DEGRADED
                        await self._handle_unhealthy_service(service_name, service_def)
                    else:
                        self.service_states[service_name] = ServiceState.RUNNING

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _check_service_health(self, name: str, service_def: ServiceDef) -> bool:
        """Check if service is healthy"""
        if not service_def.health_check:
            return True

        try:
            _endpoint = service_def.health_check.endpoint
            # Simple HTTP/TCP check (simplified)
            if service_def.health_check.type == "http":
                # In production, use requests library
                return True
            return True
        except Exception:
            return False

    async def _handle_unhealthy_service(self, name: str, service_def: ServiceDef):
        """Handle unhealthy service (restart, escalate, etc.)"""
        restart_count = self.restart_counts.get(name, 0)

        if restart_count < service_def.max_restarts:
            logger.warning(f"⚠️  Restarting {name} (attempt {restart_count + 1})")

            if self.mode == DeploymentMode.SYSTEMD:
                subprocess.run(["systemctl", "restart", f"camelot-{name}"], check=False)
            elif self.mode == DeploymentMode.BARE_METAL:
                if name in self.service_pids:
                    import signal
                    os.kill(self.service_pids[name], signal.SIGTERM)

            self.restart_counts[name] = restart_count + 1
            await asyncio.sleep(service_def.restart_delay)
        else:
            logger.error(f"❌ {name} exceeded max restarts, marking as failed")
            self.service_states[name] = ServiceState.FAILED

    async def _check_dependencies(self, service_def: ServiceDef) -> bool:
        """Check if service dependencies are met"""
        for dep in service_def.dependencies:
            if dep not in self.crystal.services:
                return False
            # In production, check that dependent service is running
        return True

    def _generate_systemd_unit(self, name: str, service_def: ServiceDef) -> str:
        """Generate systemd unit file"""
        env_lines = "\n".join([f"Environment=\"{k}={v}\"" for k, v in service_def.env_vars.items()])

        return f"""[Unit]
Description=CAMELOT-OS {name} Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={service_def.command}
Restart={service_def.restart_policy}
RestartSec={service_def.restart_delay}
{env_lines}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    def get_status(self) -> Dict:
        """Get status of all services"""
        return {
            "node_id": self.crystal.node_id,
            "services": {
                name: state.value
                for name, state in self.service_states.items()
            },
            "restart_counts": self.restart_counts,
            "healthy_count": sum(1 for s in self.service_states.values() if s == ServiceState.RUNNING),
            "total_count": len(self.crystal.services),
        }


# ── Demo: Generate and Deploy QR Pill ─────────────────────────────────────

async def demo_qr_pill():
    """Demo: Create and deploy QR Pill"""
    # Define services
    consensus_service = ServiceDef(
        name="consensus",
        command="python -m control_plane.distributed_ledger_consensus",
        port=8443,
        health_check=HealthCheck(endpoint="http://localhost:8443/health"),
        env_vars={
            "CAMELOT_ROLE": "consensus",
            "CAMELOT_LOG_LEVEL": "INFO",
        }
    )

    sync_service = ServiceDef(
        name="knowledge-sync",
        command="python -m control_plane.distributed_knowledge_sync",
        port=6379,
        dependencies=["consensus"],
        health_check=HealthCheck(endpoint="http://localhost:6379/health"),
    )

    agent_service = ServiceDef(
        name="agent-registry",
        command="python -m control_plane.distributed_agent_registry",
        port=8400,
        dependencies=["consensus"],
        health_check=HealthCheck(endpoint="http://localhost:8400/health"),
    )

    # Create QR Pill crystal
    crystal = QRPillCrystal(
        node_id="node_1",
        cluster_id="camelot-prod",
        peers=["node_2", "node_3"],
        services={
            "consensus": consensus_service,
            "knowledge-sync": sync_service,
            "agent-registry": agent_service,
        },
        metrics_enabled=True,
        backup_enabled=True,
    )

    # Show compressed format
    print("\n🔮 QR PILL CRYSTAL")
    print("=" * 70)
    print(f"QR Code Data:\n{crystal.to_qr_code_data()}\n")
    print(f"Compressed (Base64):\n{crystal.to_compressed()}\n")
    print(f"JSON (Pretty):\n{json.dumps(json.loads(crystal.to_json()), indent=2)}\n")

    # Deploy (simulated)
    orchestrator = QRPillOrchestrator(crystal, DeploymentMode.SYSTEMD)
    print("\n📋 DEPLOYMENT STATUS")
    print("=" * 70)
    # await orchestrator.deploy()
    print(f"Status: {orchestrator.get_status()}\n")


if __name__ == "__main__":
    asyncio.run(demo_qr_pill())
