# SPDX-License-Identifier: MIT

"""
Distance Travel — Cross-agent dispatch orchestrator.

Complete integration of distributed memory, consensus, and gateway.

Enables:
  1. Agent-to-agent task dispatch (distance travel)
  2. Knowledge pyramid sync across network
  3. Consensus-based routing
  4. Automatic fallback on failure
  5. Memory consolidation via synthesis

Usage:
    dt = DistanceTravel()

    # Agent asks another agent for help
    result = await dt.ask_agent("hermes", "openclaw", "Reason about X")

    # Parallel multi-agent dispatch
    results = await dt.ask_agents("hermes", ["openclaw", "nanobot"], "Solve X")

    # Consensus routing to best agent
    agent, result = await dt.ask_best_agent("hermes", "capability:reasoning", "Task")
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import AsyncIterator, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class DistanceTravel:
    """Complete distance-travel orchestrator."""

    def __init__(self) -> None:
        from control_plane.agent_gateway import get_agent_gateway
        from control_plane.consensus_layer import get_consensus_layer
        from control_plane.distributed_memory import get_distributed_memory
        from control_plane.memory_sync import get_memory_syncer

        self.gateway = get_agent_gateway()
        self.consensus = get_consensus_layer()
        self.memory_syncer = get_memory_syncer()
        self.distributed_memory = get_distributed_memory()

    async def ask_agent(
        self,
        source_agent: str,
        target_agent: str,
        task: str,
        system: str = "",
    ) -> AsyncIterator[str]:
        """Ask specific agent for help.

        Maintains knowledge pyramid context across agents.
        """
        dispatch_id = f"{source_agent}->{target_agent}:{int(time.time())}"

        # Broadcast event to network
        await self.distributed_memory.broadcast_event(
            event_type="dispatch",
            source_agent=source_agent,
            data={
                "task": task[:100],
                "target_agent": target_agent,
                "dispatch_id": dispatch_id,
            },
        )

        # Dispatch via gateway
        response_chunks = []
        async for chunk in self.gateway.dispatch_to_agent(
            source_agent, target_agent, task, system
        ):
            response_chunks.append(chunk)
            yield chunk

        # Post-dispatch: sync learning
        response_text = "".join(response_chunks)
        await self._sync_learning_to_network(
            source_agent=source_agent,
            target_agent=target_agent,
            task=task,
            response=response_text,
            dispatch_id=dispatch_id,
        )

    async def ask_agents(
        self,
        source_agent: str,
        target_agents: list[str],
        task: str,
        system: str = "",
    ) -> dict[str, str]:
        """Ask multiple agents in parallel.

        Returns {agent_id: response_text}
        """
        dispatch_id = f"{source_agent}->*:{int(time.time())}"

        # Broadcast multi-agent dispatch
        await self.distributed_memory.broadcast_event(
            event_type="dispatch",
            source_agent=source_agent,
            target_agents=target_agents,
            data={
                "task": task[:100],
                "dispatch_id": dispatch_id,
                "parallel": True,
            },
        )

        # Parallel dispatch
        results = await self.gateway.parallel_dispatch(
            source_agent, target_agents, task, system
        )

        # Sync results to network
        for agent_id, response in results.items():
            await self._sync_learning_to_network(
                source_agent=source_agent,
                target_agent=agent_id,
                task=task,
                response=response,
                dispatch_id=dispatch_id,
            )

        return results

    async def ask_best_agent(
        self,
        source_agent: str,
        capability: str,
        task: str,
        system: str = "",
    ) -> tuple[str, AsyncIterator[str]]:
        """Ask best agent for capability via consensus.

        Returns (selected_agent_id, response_stream)
        """
        from control_plane.agent_registry import get_agent_registry

        registry = get_agent_registry()
        candidates = registry.get_agents_with_capability(capability)

        if not candidates:
            raise ValueError(f"No agents with capability: {capability}")

        # Consensus vote
        candidate_ids = [a.agent_id for a in candidates]
        selected = await self.consensus.vote_on_routing(task, candidate_ids)

        if not selected:
            selected = candidate_ids[0]

        # Dispatch
        response_stream = self.ask_agent(source_agent, selected, task, system)

        return selected, response_stream

    async def _sync_learning_to_network(
        self,
        source_agent: str,
        target_agent: str,
        task: str,
        response: str,
        dispatch_id: str,
    ) -> None:
        """Sync dispatch learning across network."""
        try:
            # Broadcast learning event
            await self.distributed_memory.broadcast_event(
                event_type="learning",
                source_agent=source_agent,
                target_agents=[target_agent],
                data={
                    "dispatch_id": dispatch_id,
                    "task": task[:50],
                    "response_length": len(response),
                    "timestamp": time.time(),
                },
            )

            # Sync to memory (async)
            asyncio.create_task(self._index_dispatch(
                dispatch_id, source_agent, target_agent, task, response
            ))
        except Exception as e:
            print(f"[DISTANCE_TRAVEL] Sync failed: {e}", file=sys.stderr)

    async def _index_dispatch(
        self,
        dispatch_id: str,
        source_agent: str,
        target_agent: str,
        task: str,
        response: str,
    ) -> None:
        """Index dispatch in knowledge pyramid."""
        try:
            from control_plane.symbol_compressor import get_compressor

            compressor = get_compressor()

            # Compress dispatch
            await compressor.compress(
                dispatch_id=dispatch_id,
                knight_id=f"{source_agent}+{target_agent}",
                prompt=task,
                category="DISTANCE_TRAVEL",
                confidence=0.9,
                tokens_in=len(task.split()),
                tokens_out=len(response.split()),
                latency_ms=0,  # Would be populated with actual timing
                model="multi-agent",
            )
        except Exception as e:
            print(f"[DISTANCE_TRAVEL] Indexing failed: {e}", file=sys.stderr)

    async def network_status(self) -> dict:
        """Get status of entire agent network."""
        from control_plane.agent_registry import get_agent_registry

        registry = get_agent_registry()
        dist_mem = self.distributed_memory

        # Get network health
        status = await dist_mem.get_network_status()

        return {
            "agents": registry.summary(),
            "network": status,
            "timestamp": time.time(),
        }

    async def cross_agent_synthesis(
        self,
        category: str,
    ) -> str:
        """Synthesize insights from all agents for a category."""
        # Get insights from each agent
        insights = await self.memory_syncer.get_cross_agent_insights(category)

        if not insights.get("agent_insights"):
            return f"No insights available for {category}"

        # Merge via CloudBrain
        return await self.memory_syncer.merge_synthesis(
            category=category,
            synthesis_text="[Aggregating from network...]",
            source_agent="distance_travel",
            other_syntheses=[
                text for text in insights.get("agent_insights", {}).values()
                if isinstance(text, str)
            ],
        )


# ── Module-level singleton ────────────────────────────────────────────────

_dt: Optional[DistanceTravel] = None


def get_distance_travel() -> DistanceTravel:
    """Get or create shared DistanceTravel instance."""
    global _dt
    if _dt is None:
        _dt = DistanceTravel()
    return _dt


async def ask_agent(
    source_agent: str,
    target_agent: str,
    task: str,
) -> AsyncIterator[str]:
    """Convenience: ask specific agent."""
    dt = get_distance_travel()
    async for chunk in dt.ask_agent(source_agent, target_agent, task):
        yield chunk


async def ask_agents(
    source_agent: str,
    target_agents: list[str],
    task: str,
) -> dict[str, str]:
    """Convenience: ask multiple agents."""
    dt = get_distance_travel()
    return await dt.ask_agents(source_agent, target_agents, task)


async def ask_best_agent(
    source_agent: str,
    capability: str,
    task: str,
) -> tuple[str, str]:
    """Convenience: ask best agent for capability."""
    dt = get_distance_travel()
    selected, stream = await dt.ask_best_agent(source_agent, capability, task)

    # Collect stream into string
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)

    return selected, "".join(chunks)
