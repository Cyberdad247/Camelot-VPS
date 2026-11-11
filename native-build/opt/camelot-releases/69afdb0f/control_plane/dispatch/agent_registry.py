# SPDX-License-Identifier: MIT

"""
Agent Registry — Multi-agent network definitions.

Agents in the CAMELOT network:
  1. Hermes (kinetic, tool-calling agent)
  2. OpenClaw (open-source reasoning)
  3. NanoBot (lightweight, edge deployment)
  4. ZeroClaw (zero-trust, privacy-focused)
  5. RustClaw (systems/performance specialist)

Usage:
    registry = AgentRegistry()
    agent = registry.get("hermes")
    all_agents = registry.list_agents()
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentDefinition:
    """Agent network definition."""
    agent_id: str
    name: str
    description: str
    model: str
    capabilities: list[str]
    host: str
    port: int
    memory_pyramid: bool = True  # Uses knowledge pyramid
    sync_enabled: bool = True  # Participates in memory sync
    cost_tier: str = "free"
    status: str = "ready"

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def redis_key(self) -> str:
        return f"agent:{self.agent_id}"


class AgentRegistry:
    """Registry and definitions for all agents in network."""

    def __init__(self) -> None:
        self.agents: dict[str, AgentDefinition] = self._init_agents()

    def _init_agents(self) -> dict[str, AgentDefinition]:
        """Initialize agent definitions."""
        return {
            "hermes": AgentDefinition(
                agent_id="hermes",
                name="Hermes",
                description="Nous Hermes Agent — kinetic tool-calling autonomous agent",
                model="hermes-2-pro",
                capabilities=[
                    "tool_use",
                    "autonomous",
                    "reasoning",
                    "code_generation",
                    "file_ops",
                    "terminal",
                ],
                host="127.0.0.1",
                port=8401,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="free",
            ),
            "openclaw": AgentDefinition(
                agent_id="openclaw",
                name="OpenClaw",
                description="Open-source reasoning engine — chain-of-thought, tree-of-thought",
                model="openclaw-reasoning",
                capabilities=[
                    "reasoning",
                    "analysis",
                    "research",
                    "synthesis",
                    "planning",
                ],
                host="127.0.0.1",
                port=8402,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="free",
            ),
            "nanobot": AgentDefinition(
                agent_id="nanobot",
                name="NanoBot",
                description="Lightweight edge agent — minimal latency, local-first",
                model="nanobot-1.5b",
                capabilities=[
                    "inference",
                    "edge_deployment",
                    "low_latency",
                    "privacy",
                    "offline",
                ],
                host="127.0.0.1",
                port=8403,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="free",
            ),
            "zeroclaw": AgentDefinition(
                agent_id="zeroclaw",
                name="ZeroClaw",
                description="Zero-trust privacy agent — encryption, sandboxing, audit",
                model="zeroclaw-secure",
                capabilities=[
                    "security",
                    "encryption",
                    "sandboxing",
                    "audit",
                    "compliance",
                    "zero_trust",
                ],
                host="127.0.0.1",
                port=8404,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="medium",
            ),
            "rustclaw": AgentDefinition(
                agent_id="rustclaw",
                name="RustClaw",
                description="Systems specialist — performance, optimization, infrastructure",
                model="rustclaw-systems",
                capabilities=[
                    "systems",
                    "performance",
                    "optimization",
                    "infrastructure",
                    "benchmarking",
                    "profiling",
                ],
                host="127.0.0.1",
                port=8405,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="free",
            ),
            "apis": AgentDefinition(
                agent_id="apis",
                name="Apis",
                description="Real-time sensing and intelligence gathering — system observability, metrics, signals",
                model="apis-intelligence",
                capabilities=[
                    "observability",
                    "metrics",
                    "sensing",
                    "signal_processing",
                    "anomaly_detection",
                    "real_time",
                ],
                host="127.0.0.1",
                port=8406,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="free",
            ),
            "galahad": AgentDefinition(
                agent_id="galahad",
                name="Galahad",
                description="Purity verification and integrity guardian — validation, verification, audit trails",
                model="galahad-verifier",
                capabilities=[
                    "verification",
                    "validation",
                    "integrity_checking",
                    "audit",
                    "compliance_verification",
                    "cryptographic_proof",
                ],
                host="127.0.0.1",
                port=8407,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="medium",
            ),
            "lancelot": AgentDefinition(
                agent_id="lancelot",
                name="Lancelot",
                description="Kinetic dispatch and urgency prioritization — rapid response, mission-critical execution",
                model="lancelot-kinetic",
                capabilities=[
                    "rapid_dispatch",
                    "urgency_prioritization",
                    "mission_critical",
                    "real_time_execution",
                    "latency_sensitive",
                    "failover_handling",
                ],
                host="127.0.0.1",
                port=8408,
                memory_pyramid=True,
                sync_enabled=True,
                cost_tier="high",
            ),
        }

    def get(self, agent_id: str) -> Optional[AgentDefinition]:
        """Get agent definition by ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> list[AgentDefinition]:
        """List all agents."""
        return list(self.agents.values())

    def list_agent_ids(self) -> list[str]:
        """List all agent IDs."""
        return list(self.agents.keys())

    def get_agents_with_capability(self, capability: str) -> list[AgentDefinition]:
        """Get agents with specific capability."""
        return [a for a in self.agents.values() if capability in a.capabilities]

    def get_agents_by_cost_tier(self, tier: str) -> list[AgentDefinition]:
        """Get agents by cost tier (free, low, medium, high)."""
        return [a for a in self.agents.values() if a.cost_tier == tier]

    def update_status(self, agent_id: str, status: str) -> None:
        """Update agent status (ready, busy, offline, error)."""
        if agent_id in self.agents:
            self.agents[agent_id].status = status

    def summary(self) -> dict:
        """Get registry summary."""
        return {
            "total_agents": len(self.agents),
            "agents": [
                {
                    "id": a.agent_id,
                    "name": a.name,
                    "status": a.status,
                    "capabilities": a.capabilities,
                    "cost_tier": a.cost_tier,
                }
                for a in self.agents.values()
            ],
        }


# ── Module-level singleton ────────────────────────────────────────────────

_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get or create shared AgentRegistry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def get_agent(agent_id: str) -> Optional[AgentDefinition]:
    """Convenience: get agent by ID."""
    registry = get_agent_registry()
    return registry.get(agent_id)


def list_agents() -> list[AgentDefinition]:
    """Convenience: list all agents."""
    registry = get_agent_registry()
    return registry.list_agents()
