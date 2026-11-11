# SPDX-License-Identifier: MIT

"""
Distributed Agent Registry — Cross-Instance Agent Discovery & Routing

Phase G Week 2: Autonomous agent networks spanning multiple CAMELOT-OS instances

Architecture:
- Each instance runs 5-8 agents (Phase C Distance Travel)
- Global registry discovers agents across all instances
- Cross-instance consensus routing
- Remote agent invocation via RPC
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class AgentStatus(str, Enum):
    """Agent operational status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DARK = "dark"
    OFFLINE = "offline"


class AgentScope(str, Enum):
    """Agent scope (local or global)"""
    LOCAL = "local"
    GLOBAL = "global"


@dataclass
class AgentInfo:
    """Information about an agent"""
    agent_id: str
    node_id: str
    port: int
    role: str  # e.g., "coordinator", "forge", "architect"
    scope: AgentScope
    status: AgentStatus
    last_heartbeat: float
    capabilities: Set[str] = field(default_factory=set)
    load: float = 0.0  # 0-1 utilization


@dataclass
class AgentHeartbeat:
    """Heartbeat from agent"""
    agent_id: str
    node_id: str
    timestamp: float
    status: AgentStatus
    load: float
    uptime: float


class DistributedAgentRegistry:
    """Global agent registry for multi-instance clusters"""

    def __init__(self, node_id: str, peers: List[str]):
        """
        Initialize distributed agent registry

        Args:
            node_id: This node's identifier
            peers: List of peer node IDs
        """
        self.node_id = node_id
        self.peers = peers
        self.all_nodes = [node_id] + peers

        # Local agents on this node
        self.local_agents: Dict[str, AgentInfo] = {}

        # Global agent registry (all instances)
        self.global_agents: Dict[str, AgentInfo] = {}

        # Agent discovery cache
        self.discovery_cache: Dict[str, List[AgentInfo]] = {}
        self.cache_ttl = 30  # seconds

        # Heartbeat tracking
        self.heartbeat_timeout = 10  # seconds

        print(f"🔍 AgentRegistry: Node {node_id} initialized for {len(self.all_nodes)} instance cluster")

    def register_local_agent(
        self,
        agent_id: str,
        port: int,
        role: str,
        capabilities: Set[str]
    ) -> AgentInfo:
        """
        Register a local agent

        Args:
            agent_id: Agent unique identifier
            port: Agent port number
            role: Agent role (coordinator, forge, architect, sensor, verifier, executor)
            capabilities: Set of agent capabilities

        Returns:
            AgentInfo object
        """
        agent = AgentInfo(
            agent_id=agent_id,
            node_id=self.node_id,
            port=port,
            role=role,
            scope=AgentScope.LOCAL,
            status=AgentStatus.HEALTHY,
            last_heartbeat=time.time(),
            capabilities=capabilities,
        )

        self.local_agents[agent_id] = agent
        self.global_agents[agent_id] = agent  # Also in global

        print(f"✅ Agent registered: {agent_id} on {self.node_id}:{port} (role: {role})")

        return agent

    async def discover_agents(self, scope: AgentScope = AgentScope.GLOBAL) -> List[AgentInfo]:
        """
        Discover agents in registry

        Args:
            scope: LOCAL (only this node) or GLOBAL (all instances)

        Returns:
            List of agent info objects
        """
        if scope == AgentScope.LOCAL:
            return list(self.local_agents.values())

        elif scope == AgentScope.GLOBAL:
            # Return global registry (in production, would query peers)
            return list(self.global_agents.values())

        return []

    async def discover_agents_by_role(self, role: str) -> List[AgentInfo]:
        """
        Discover agents by role

        Args:
            role: Agent role to search for

        Returns:
            List of matching agents
        """
        agents = await self.discover_agents(AgentScope.GLOBAL)
        return [a for a in agents if a.role == role]

    async def discover_agents_by_capability(self, capability: str) -> List[AgentInfo]:
        """
        Discover agents by capability

        Args:
            capability: Capability to search for

        Returns:
            List of matching agents
        """
        agents = await self.discover_agents(AgentScope.GLOBAL)
        return [a for a in agents if capability in a.capabilities]

    async def discover_healthy_agents(self) -> List[AgentInfo]:
        """
        Discover all healthy agents

        Returns:
            List of healthy agents
        """
        agents = await self.discover_agents(AgentScope.GLOBAL)
        return [a for a in agents if a.status == AgentStatus.HEALTHY]

    async def select_least_loaded_agent(self, role: str = None) -> Optional[AgentInfo]:
        """
        Select agent with lowest load

        Args:
            role: Optional role filter

        Returns:
            Agent with lowest load, or None
        """
        if role:
            candidates = await self.discover_agents_by_role(role)
        else:
            candidates = await self.discover_healthy_agents()

        if not candidates:
            return None

        # Sort by load (ascending) and return first
        return sorted(candidates, key=lambda a: a.load)[0]

    async def select_geographically_closest_agent(self, role: str) -> Optional[AgentInfo]:
        """
        Select geographically closest agent

        Args:
            role: Agent role to find

        Returns:
            Closest agent on preferred node
        """
        # Priority: local node, then peers in order
        candidates_local = [a for a in self.local_agents.values() if a.role == role and a.status == AgentStatus.HEALTHY]
        if candidates_local:
            return candidates_local[0]

        # Check peers
        for peer in self.peers:
            candidates_peer = [
                a for a in self.global_agents.values()
                if a.role == role and a.node_id == peer and a.status == AgentStatus.HEALTHY
            ]
            if candidates_peer:
                return candidates_peer[0]

        return None

    async def handle_heartbeat(self, heartbeat: AgentHeartbeat) -> bool:
        """
        Handle incoming heartbeat from agent

        Args:
            heartbeat: Agent heartbeat

        Returns:
            True if heartbeat was processed
        """
        if heartbeat.agent_id not in self.global_agents:
            # Unknown agent, ignore
            return False

        agent = self.global_agents[heartbeat.agent_id]
        agent.status = heartbeat.status
        agent.load = heartbeat.load
        agent.last_heartbeat = time.time()

        return True

    async def check_agent_health(self) -> Dict[str, AgentStatus]:
        """
        Check health of all agents (detect timeouts)

        Returns:
            Dict mapping agent_id to status
        """
        current_time = time.time()
        health_status = {}

        for agent_id, agent in self.global_agents.items():
            time_since_heartbeat = current_time - agent.last_heartbeat

            if time_since_heartbeat > self.heartbeat_timeout:
                agent.status = AgentStatus.DARK
            elif time_since_heartbeat > self.heartbeat_timeout * 0.5:
                agent.status = AgentStatus.DEGRADED

            health_status[agent_id] = agent.status

        return health_status

    async def get_registry_status(self) -> Dict:
        """Get registry status"""
        local_agents = list(self.local_agents.values())
        global_agents = list(self.global_agents.values())

        healthy = sum(1 for a in global_agents if a.status == AgentStatus.HEALTHY)
        degraded = sum(1 for a in global_agents if a.status == AgentStatus.DEGRADED)
        dark = sum(1 for a in global_agents if a.status == AgentStatus.DARK)

        agents_by_role = {}
        for agent in global_agents:
            if agent.role not in agents_by_role:
                agents_by_role[agent.role] = []
            agents_by_role[agent.role].append(agent.agent_id)

        agents_by_node = {}
        for agent in global_agents:
            if agent.node_id not in agents_by_node:
                agents_by_node[agent.node_id] = []
            agents_by_node[agent.node_id].append(agent.agent_id)

        return {
            'node_id': self.node_id,
            'local_agents': len(local_agents),
            'global_agents': len(global_agents),
            'healthy': healthy,
            'degraded': degraded,
            'dark': dark,
            'agents_by_role': agents_by_role,
            'agents_by_node': agents_by_node,
        }


class DistributedAgentRouter:
    """Routes requests across distributed agent network"""

    def __init__(self, registry: DistributedAgentRegistry):
        """
        Initialize agent router

        Args:
            registry: Distributed agent registry
        """
        self.registry = registry

    async def route_to_role(self, role: str, request: Dict) -> Tuple[Optional[AgentInfo], Dict]:
        """
        Route request to agent by role

        Args:
            role: Agent role
            request: Request data

        Returns:
            Tuple of (selected agent, result)
        """
        # Strategy 1: Least loaded agent
        agent = await self.registry.select_least_loaded_agent(role)

        if not agent:
            return None, {'error': f'No healthy agents found for role {role}'}

        # In production, would invoke RPC
        result = await self._invoke_remote_agent(agent, request)

        return agent, result

    async def route_to_closest(self, role: str, request: Dict) -> Tuple[Optional[AgentInfo], Dict]:
        """
        Route request to geographically closest agent

        Args:
            role: Agent role
            request: Request data

        Returns:
            Tuple of (selected agent, result)
        """
        agent = await self.registry.select_geographically_closest_agent(role)

        if not agent:
            return None, {'error': f'No healthy agents found for role {role}'}

        result = await self._invoke_remote_agent(agent, request)

        return agent, result

    async def route_with_consensus(self, role: str, request: Dict, quorum: int = 2) -> Tuple[List[AgentInfo], Dict]:
        """
        Route request to multiple agents and reach consensus

        Args:
            role: Agent role
            request: Request data
            quorum: Number of agent responses needed

        Returns:
            Tuple of (selected agents, consensus result)
        """
        candidates = await self.registry.discover_agents_by_role(role)
        candidates = [a for a in candidates if a.status == AgentStatus.HEALTHY]

        if len(candidates) < quorum:
            return [], {'error': f'Insufficient agents for quorum (need {quorum}, have {len(candidates)})'}

        # Select top candidates by load
        selected = sorted(candidates, key=lambda a: a.load)[:quorum]

        # Invoke in parallel
        tasks = [self._invoke_remote_agent(agent, request) for agent in selected]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Consensus: use majority result
        consensus_result = self._consensus_results(results)

        return selected, consensus_result

    async def _invoke_remote_agent(self, agent: AgentInfo, request: Dict) -> Dict:
        """
        Invoke agent (RPC simulation)

        Args:
            agent: Agent to invoke
            request: Request data

        Returns:
            Response from agent
        """
        # Simulated RPC call
        await asyncio.sleep(0.01)  # Simulate network latency

        # In production, would use actual RPC (gRPC, HTTP, etc.)
        return {
            'agent_id': agent.agent_id,
            'node_id': agent.node_id,
            'request': request,
            'timestamp': time.time(),
            'status': 'success',
        }

    def _consensus_results(self, results: List) -> Dict:
        """
        Compute consensus from results

        Args:
            results: List of results from agents

        Returns:
            Consensus result
        """
        valid_results = [r for r in results if isinstance(r, dict) and r.get('status') == 'success']

        if not valid_results:
            return {'error': 'All agents failed', 'consensus': None}

        # Simple majority: return first successful result
        return {
            'consensus': valid_results[0],
            'agreement': len(valid_results),
            'total': len(results),
        }

    async def get_router_status(self) -> Dict:
        """Get router status"""
        return await self.registry.get_registry_status()


# ── Module-level singleton ────────────────────────────────────────────────

_registry: Optional[DistributedAgentRegistry] = None
_router: Optional[DistributedAgentRouter] = None


def get_distributed_agent_registry(node_id: str = "node_default", peers: List[str] = None) -> DistributedAgentRegistry:
    """Get or create distributed agent registry"""
    global _registry
    if _registry is None:
        peers = peers or []
        _registry = DistributedAgentRegistry(node_id, peers)
    return _registry


def get_distributed_agent_router(registry: DistributedAgentRegistry = None) -> DistributedAgentRouter:
    """Get or create distributed agent router"""
    global _router
    if _router is None:
        if registry is None:
            registry = get_distributed_agent_registry()
        _router = DistributedAgentRouter(registry)
    return _router


async def distributed_agents_demo():
    """Demo: Distributed agent network"""
    # Initialize registry for 3-node cluster
    registry = DistributedAgentRegistry("node_1", ["node_2", "node_3"])

    # Register agents on node 1
    registry.register_local_agent(
        "hermes_1", 8401, "forge",
        {"dispatch", "tool_calling", "execution"}
    )
    registry.register_local_agent(
        "rustclaw_1", 8403, "coordinator",
        {"orchestration", "routing"}
    )

    # Simulate agents on node 2 (registered directly to global)
    registry.global_agents["hermes_2"] = AgentInfo(
        agent_id="hermes_2",
        node_id="node_2",
        port=8401,
        role="forge",
        scope=AgentScope.GLOBAL,
        status=AgentStatus.HEALTHY,
        last_heartbeat=time.time(),
        capabilities={"dispatch", "execution"},
    )

    # Get registry status
    status = await registry.get_registry_status()
    print(f"\nRegistry Status: {json.dumps(status, indent=2)}")

    # Discover agents
    all_agents = await registry.discover_agents()
    print(f"\nTotal agents: {len(all_agents)}")

    # Find least loaded forge
    forge = await registry.select_least_loaded_agent("forge")
    print(f"\nLeast loaded forge: {forge.agent_id if forge else 'None'}")

    # Route with router
    router = get_distributed_agent_router(registry)
    agent, result = await router.route_to_role("forge", {"operation": "test"})
    print(f"\nRouted to: {agent.agent_id if agent else 'None'}")


if __name__ == "__main__":
    asyncio.run(distributed_agents_demo())
