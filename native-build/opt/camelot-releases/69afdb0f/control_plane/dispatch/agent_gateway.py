# SPDX-License-Identifier: MIT

"""
Agent Gateway — Bifrost bridge for cross-agent distance travel.

Enables agents to dispatch work to each other via Bifrost:
  - Agent A asks Agent B for help
  - Maintains knowledge pyramid context across agents
  - Consensus-based dispatch routing
  - Automatic fallback on agent unavailability

Usage:
    gateway = AgentGateway()
    result = await gateway.dispatch_to_agent(
        source_agent="hermes",
        target_agent="openclaw",
        task="Reason about this problem..."
    )
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from typing import AsyncIterator, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class AgentGateway:
    """Bifrost gateway for inter-agent dispatch."""

    def __init__(self) -> None:
        self.redis_client = None
        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis for gateway communication."""
        try:
            import redis

            self.redis_client = redis.Redis(
                host="localhost", port=6379, decode_responses=True
            )
            self.redis_client.ping()
            print("[GATEWAY] Redis ready for agent dispatch", file=sys.stderr)
        except Exception as e:
            print(f"[GATEWAY] Redis init failed: {e}", file=sys.stderr)

    async def dispatch_to_agent(
        self,
        source_agent: str,
        target_agent: str,
        task: str,
        system: str = "",
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Dispatch task from one agent to another via Bifrost.

        Yields response chunks as they arrive.
        """
        dispatch_id = str(uuid.uuid4())[:8]

        try:
            # Log dispatch request
            request = {
                "dispatch_id": dispatch_id,
                "source_agent": source_agent,
                "target_agent": target_agent,
                "task": task,
                "system": system,
                "timestamp": time.time(),
            }

            if self.redis_client:
                self.redis_client.setex(
                    f"dispatch:{dispatch_id}:request",
                    3600,
                    json.dumps(request),
                )

            # Route via Bifrost to target agent's knight
            from control_plane.bifrost import Bifrost

            bf = Bifrost()

            # Map agent to knight (conceptual; in reality, agent hosts knights)
            agent_to_knight_map = {
                "hermes": "sir_hermes",
                "openclaw": "sir_boris",  # Reasoning → boris
                "nanobot": "sir_ghost",  # Edge → local
                "zeroclaw": "sir_sentinel",  # Security → sentinel
                "rustclaw": "sir_ghost",  # Systems → ghost (local perf)
            }

            knight_id = agent_to_knight_map.get(target_agent, "sir_boris")

            # Build enriched system prompt with source context
            enriched_system = f"""
{system}

Inter-agent dispatch:
  Source: {source_agent}
  Target: {target_agent}
  Dispatch ID: {dispatch_id}

Context: You are assisting another agent in the CAMELOT network.
Provide your best analysis and be explicit about reasoning.
"""

            # Stream response via Bifrost
            async for chunk in bf.stream(knight_id, task, enriched_system, max_tokens):
                yield chunk

                # Log response chunks
                if self.redis_client:
                    self.redis_client.append(
                        f"dispatch:{dispatch_id}:response",
                        chunk,
                    )

        except Exception as e:
            yield f"\n[GATEWAY] Dispatch failed: {e}"

    async def dispatch_to_best_agent(
        self,
        source_agent: str,
        task: str,
        capability: str,
        system: str = "",
    ) -> tuple[str, AsyncIterator[str]]:
        """Dispatch to best agent matching capability.

        Returns (selected_agent_id, response_stream)
        """
        from control_plane.consensus_layer import get_consensus_layer

        consensus = get_consensus_layer()

        # Find candidates
        from control_plane.agent_registry import get_agent_registry

        registry = get_agent_registry()
        candidates = registry.get_agents_with_capability(capability)

        if not candidates:
            raise ValueError(f"No agents found with capability: {capability}")

        candidate_ids = [a.agent_id for a in candidates]

        # Consensus vote on best agent
        selected = await consensus.vote_on_routing(task, candidate_ids)

        if not selected:
            selected = candidate_ids[0]

        # Dispatch
        response_stream = self.dispatch_to_agent(
            source_agent, selected, task, system
        )

        return selected, response_stream

    async def parallel_dispatch(
        self,
        source_agent: str,
        target_agents: list[str],
        task: str,
        system: str = "",
    ) -> dict[str, str]:
        """Dispatch same task to multiple agents in parallel.

        Returns {agent_id: response_text}
        """
        async def dispatch_and_collect(agent_id: str) -> tuple[str, str]:
            chunks = []
            async for chunk in self.dispatch_to_agent(
                source_agent, agent_id, task, system
            ):
                chunks.append(chunk)
            return agent_id, "".join(chunks)

        tasks = [dispatch_and_collect(agent_id) for agent_id in target_agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        response_dict = {}
        for result in results:
            if isinstance(result, tuple):
                agent_id, response = result
                response_dict[agent_id] = response
            elif isinstance(result, Exception):
                print(f"[GATEWAY] Parallel dispatch error: {result}", file=sys.stderr)

        return response_dict

    async def get_dispatch_history(
        self,
        dispatch_id: str,
    ) -> dict:
        """Get history of a dispatch."""
        if not self.redis_client:
            return {}

        try:
            request = self.redis_client.get(f"dispatch:{dispatch_id}:request")
            response = self.redis_client.get(f"dispatch:{dispatch_id}:response")

            return {
                "dispatch_id": dispatch_id,
                "request": json.loads(request) if request else None,
                "response": response,
            }
        except Exception as e:
            print(f"[GATEWAY] History retrieval failed: {e}", file=sys.stderr)
            return {}

    async def list_pending_dispatches(
        self,
        agent_id: str,
    ) -> list[dict]:
        """List pending dispatches for an agent."""
        if not self.redis_client:
            return []

        try:
            pattern = "dispatch:*:request"
            keys = self.redis_client.keys(pattern)

            pending = []
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    req = json.loads(data)
                    if req.get("target_agent") == agent_id:
                        pending.append(req)

            return pending
        except Exception as e:
            print(f"[GATEWAY] Pending list failed: {e}", file=sys.stderr)
            return []


# ── Module-level singleton ────────────────────────────────────────────────

_gateway: Optional[AgentGateway] = None


def get_agent_gateway() -> AgentGateway:
    """Get or create shared AgentGateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = AgentGateway()
    return _gateway


async def dispatch_to_agent(
    source_agent: str,
    target_agent: str,
    task: str,
    system: str = "",
) -> AsyncIterator[str]:
    """Convenience: dispatch to specific agent."""
    gateway = get_agent_gateway()
    async for chunk in gateway.dispatch_to_agent(source_agent, target_agent, task, system):
        yield chunk


async def parallel_dispatch(
    source_agent: str,
    target_agents: list[str],
    task: str,
) -> dict[str, str]:
    """Convenience: parallel dispatch."""
    gateway = get_agent_gateway()
    return await gateway.parallel_dispatch(source_agent, target_agents, task)
