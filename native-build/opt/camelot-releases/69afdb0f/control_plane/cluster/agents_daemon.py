# SPDX-License-Identifier: MIT

"""
HTTP daemon wrapper for DistributedAgentRegistry.

Adds the cross-node piece the original lacked: each node periodically gossips
its local agents to peers' ``/agents/gossip`` endpoint, and merges what it
receives into ``global_agents``. That makes the global registry genuinely span
multiple processes instead of being a single in-process dict.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, List

from control_plane.distributed_agent_registry import (
    AgentInfo,
    AgentScope,
    AgentStatus,
    DistributedAgentRegistry,
)
from control_plane.observability import traced_op

from .http_daemon import HttpDaemon, call_async, post_json


def _agent_to_payload(agent: AgentInfo) -> dict:
    return {
        "agent_id": agent.agent_id,
        "node_id": agent.node_id,
        "port": agent.port,
        "role": agent.role,
        "status": agent.status.value,
        "last_heartbeat": agent.last_heartbeat,
        "capabilities": sorted(agent.capabilities),
        "load": agent.load,
    }


def _agent_from_payload(body: dict) -> AgentInfo:
    return AgentInfo(
        agent_id=body["agent_id"],
        node_id=body["node_id"],
        port=int(body["port"]),
        role=body["role"],
        scope=AgentScope.GLOBAL,
        status=AgentStatus(body.get("status", AgentStatus.HEALTHY.value)),
        last_heartbeat=float(body.get("last_heartbeat", time.time())),
        capabilities=set(body.get("capabilities", [])),
        load=float(body.get("load", 0.0)),
    )


class HttpAgentsNode(DistributedAgentRegistry):
    """Agent registry that gossips local agents to peers over HTTP."""

    def __init__(
        self,
        node_id: str,
        peers: List[str],
        peer_addrs: Dict[str, str],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__(node_id, peers)
        self.peer_addrs = peer_addrs
        self._loop = loop

    def merge_remote(self, node_id: str, agents: List[dict]) -> int:
        count = 0
        for raw in agents:
            info = _agent_from_payload(raw)
            self.global_agents[info.agent_id] = info
            count += 1
        return count

    async def gossip_once(self) -> None:
        payload = {
            "node_id": self.node_id,
            "agents": [_agent_to_payload(a) for a in self.local_agents.values()],
        }
        for base in self.peer_addrs.values():
            self._loop.run_in_executor(None, post_json, f"{base}/agents/gossip", payload)

    async def gossip_loop(self, interval: float = 3.0) -> None:
        while True:
            try:
                await self.gossip_once()
            except Exception:  # noqa: BLE001 - gossip is best-effort
                pass
            await asyncio.sleep(interval)


def register_routes(daemon: HttpDaemon, node: HttpAgentsNode) -> None:
    def agents_gossip(body: dict, loop):
        merged = node.merge_remote(body.get("node_id", "?"), body.get("agents", []))
        return 200, {"merged": merged}

    def agents_status(body: dict, loop):
        return 200, call_async(loop, node.get_registry_status())

    def agents_register(body: dict, loop):
        agent = node.register_local_agent(
            body["agent_id"],
            int(body.get("port", 0)),
            body.get("role", "worker"),
            set(body.get("capabilities", [])),
        )
        return 200, {"registered": agent.agent_id}

    daemon.route("POST", "/agents/gossip", traced_op("agents.gossip")(agents_gossip))
    daemon.route("GET", "/agents/status", agents_status)
    daemon.route("POST", "/agents/register", traced_op("agents.register")(agents_register))
