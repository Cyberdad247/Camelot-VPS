# SPDX-License-Identifier: MIT

"""
Distributed Memory Protocol — Shared memory across agent network.

Implements cross-agent memory synchronization:
  - Redis pub/sub for real-time events
  - Qdrant replication for vector sync
  - CloudBrain consolidation for insights

Agents: Hermes, OpenClaw, NanoBot, ZeroClaw, RustClaw

Usage:
    dm = DistributedMemory()
    await dm.broadcast_event("dispatch_complete", {...})
    await dm.sync_to_peers("knowledge_update")
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class MemoryEvent:
    """Event in distributed memory network."""
    event_type: str  # "dispatch", "learning", "synthesis", "error"
    source_agent: str  # Which agent originated
    target_agents: list[str]  # Broadcast to these agents
    data: dict
    timestamp: float


class DistributedMemory:
    """Shared memory protocol for agent network."""

    def __init__(self) -> None:
        self.redis_client = None
        self.redis_pubsub = None
        self.listeners: dict[str, list[Callable]] = {}
        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis pub/sub for memory events."""
        try:
            import redis

            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            self.redis_client.ping()
            print("[DIST_MEMORY] Connected to Redis pub/sub", file=sys.stderr)
        except Exception as e:
            print(f"[DIST_MEMORY] Redis init failed: {e}", file=sys.stderr)
            self.redis_client = None

    async def broadcast_event(
        self,
        event_type: str,
        source_agent: str,
        data: dict,
        target_agents: Optional[list[str]] = None,
    ) -> None:
        """Broadcast event to network."""
        if not self.redis_client:
            return

        if target_agents is None:
            target_agents = ["hermes", "openclaw", "nanobot", "zeroclaw", "rustclaw"]

        event = MemoryEvent(
            event_type=event_type,
            source_agent=source_agent,
            target_agents=target_agents,
            data=data,
            timestamp=time.time(),
        )

        try:
            # Publish to Redis channel
            message = json.dumps({
                "event_type": event.event_type,
                "source_agent": event.source_agent,
                "target_agents": event.target_agents,
                "data": event.data,
                "timestamp": event.timestamp,
            })

            for target in target_agents:
                self.redis_client.publish(f"agent:{target}:events", message)
                self.redis_client.publish("agent:broadcast", message)
        except Exception as e:
            print(f"[DIST_MEMORY] Broadcast failed: {e}", file=sys.stderr)

    async def subscribe_to_events(
        self,
        agent_id: str,
        callback: Callable,
        event_types: Optional[list[str]] = None,
    ) -> None:
        """Subscribe to events from other agents."""
        if not self.redis_client:
            return

        if event_types is None:
            event_types = ["dispatch", "learning", "synthesis"]

        # Register listener
        key = f"{agent_id}:{len(self.listeners)}"
        self.listeners[key] = [callback] * len(event_types)

        try:
            # Subscribe to agent-specific channel
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(f"agent:{agent_id}:events")

            # Listen for events
            for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        if event_data.get("event_type") in event_types:
                            for listener_cb in self.listeners.get(key, []):
                                await listener_cb(event_data)
                    except Exception as e:
                        print(f"[DIST_MEMORY] Event processing failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[DIST_MEMORY] Subscription failed: {e}", file=sys.stderr)

    async def sync_dispatch_event(
        self,
        dispatch_id: str,
        knight_id: str,
        prompt: str,
        response: str,
        source_agent: str,
    ) -> None:
        """Sync dispatch completion across network."""
        await self.broadcast_event(
            event_type="dispatch",
            source_agent=source_agent,
            data={
                "dispatch_id": dispatch_id,
                "knight_id": knight_id,
                "prompt": prompt[:100],
                "response": response[:200],
                "timestamp": time.time(),
            },
        )

    async def sync_learning_event(
        self,
        knight_id: str,
        quality_score: float,
        category: str,
        source_agent: str,
    ) -> None:
        """Sync learning event (tasks/verification update)."""
        await self.broadcast_event(
            event_type="learning",
            source_agent=source_agent,
            data={
                "knight_id": knight_id,
                "quality_score": quality_score,
                "category": category,
                "timestamp": time.time(),
            },
        )

    async def sync_synthesis_event(
        self,
        category: str,
        synthesis: str,
        source_agent: str,
    ) -> None:
        """Sync weekly synthesis across network."""
        await self.broadcast_event(
            event_type="synthesis",
            source_agent=source_agent,
            data={
                "category": category,
                "synthesis": synthesis[:500],
                "timestamp": time.time(),
            },
        )

    async def get_network_status(self) -> dict:
        """Get status of connected agents."""
        if not self.redis_client:
            return {}

        try:
            status = {}
            agents = ["hermes", "openclaw", "nanobot", "zeroclaw", "rustclaw"]

            for agent_id in agents:
                # Check if agent has recent heartbeat
                heartbeat = self.redis_client.get(f"agent:{agent_id}:heartbeat")
                status[agent_id] = {
                    "online": heartbeat is not None,
                    "last_seen": float(heartbeat) if heartbeat else None,
                }

            return status
        except Exception as e:
            print(f"[DIST_MEMORY] Status check failed: {e}", file=sys.stderr)
            return {}

    async def heartbeat(self, agent_id: str) -> None:
        """Send heartbeat (agent is alive)."""
        if not self.redis_client:
            return

        try:
            self.redis_client.setex(
                f"agent:{agent_id}:heartbeat",
                300,  # 5 min TTL
                time.time(),
            )
        except Exception:
            pass


# ── Module-level singleton ────────────────────────────────────────────────

_dm: Optional[DistributedMemory] = None


def get_distributed_memory() -> DistributedMemory:
    """Get or create shared DistributedMemory instance."""
    global _dm
    if _dm is None:
        _dm = DistributedMemory()
    return _dm
