# SPDX-License-Identifier: MIT

"""
Memory Sync — Cross-agent knowledge pyramid synchronization.

Keeps Qdrant (L2) and CloudBrain (L3) synchronized across agent network:
  - Replicate vectors between agents
  - Merge synthesis insights
  - Cross-agent capability transfer
  - Consensus-based deconfliction

Usage:
    syncer = MemorySyncer()
    await syncer.sync_vector_to_peers(dispatch_id, vector, metadata)
    await syncer.merge_synthesis(category, synthesis_text)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class MemorySyncer:
    """Synchronize knowledge pyramid across agent network."""

    def __init__(self) -> None:
        self.qdrant_client = None
        self.redis_client = None
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize Qdrant and Redis clients."""
        import os
        try:
            from qdrant_client import QdrantClient

            qdrant_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
            qdrant_key = os.environ.get("QDRANT_API_KEY")
            self.qdrant_client = QdrantClient(qdrant_url, api_key=qdrant_key)
            print(f"[SYNC] Connected to Qdrant @ {qdrant_url}", file=sys.stderr)
        except Exception as e:
            print(f"[SYNC] Qdrant init failed: {e}", file=sys.stderr)

        try:
            import redis

            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            print("[SYNC] Connected to Redis", file=sys.stderr)
        except Exception as e:
            print(f"[SYNC] Redis init failed: {e}", file=sys.stderr)

    async def sync_vector_to_peers(
        self,
        dispatch_id: str,
        vector: list[float],
        metadata: dict,
        source_agent: str,
    ) -> None:
        """Sync compressed dispatch vector across agents."""
        if not self.qdrant_client:
            return

        try:
            from qdrant_client.models import PointStruct

            # Store in local Qdrant
            point = PointStruct(
                id=self._hash_id(dispatch_id),
                vector=vector,
                payload={
                    **metadata,
                    "source_agent": source_agent,
                    "synced_at": time.time(),
                },
            )

            self.qdrant_client.upsert(
                collection_name="hive_dispatches",
                points=[point],
            )

            # Broadcast to peers via Redis
            await self._broadcast_vector(dispatch_id, vector, metadata, source_agent)
        except Exception as e:
            print(f"[SYNC] Vector sync failed: {e}", file=sys.stderr)

    async def _broadcast_vector(
        self,
        dispatch_id: str,
        vector: list[float],
        metadata: dict,
        source_agent: str,
    ) -> None:
        """Broadcast vector to all agents via Redis."""
        if not self.redis_client:
            return

        try:
            message = json.dumps({
                "dispatch_id": dispatch_id,
                "vector": vector,
                "metadata": metadata,
                "source_agent": source_agent,
                "timestamp": time.time(),
            })

            # Publish to vector sync channel
            self.redis_client.publish("vector:sync", message)
        except Exception as e:
            print(f"[SYNC] Broadcast failed: {e}", file=sys.stderr)

    async def merge_synthesis(
        self,
        category: str,
        synthesis_text: str,
        source_agent: str,
        other_syntheses: Optional[list[str]] = None,
    ) -> str:
        """Merge synthesis insights from multiple agents."""
        if other_syntheses is None:
            other_syntheses = []

        # Build merged synthesis
        merged = f"Category: {category}\n\n"
        merged += f"Primary synthesis ({source_agent}):\n{synthesis_text}\n\n"

        if other_syntheses:
            merged += "Cross-agent insights:\n"
            for i, synth in enumerate(other_syntheses, 1):
                merged += f"  {i}. {synth}\n"

        # Try to synthesize via CloudBrain
        try:
            from control_plane.cloudbrain_sync import query_cloud_brain

            query = f"""
Consolidate these {category} synthesis insights into one coherent summary:

{merged}

Focus on: unique insights, pattern overlaps, actionable recommendations.
"""

            result = await asyncio.to_thread(query_cloud_brain, query)
            return result or merged
        except Exception:
            return merged

    async def replicate_blueprint_update(
        self,
        knight_id: str,
        blueprint_content: str,
        source_agent: str,
    ) -> None:
        """Replicate blueprint updates across agents."""
        if not self.redis_client:
            return

        try:
            # Store in Redis as blueprint snapshot
            self.redis_client.setex(
                f"blueprint:{knight_id}:synced",
                86400 * 30,  # 30 day retention
                json.dumps({
                    "content": blueprint_content,
                    "source_agent": source_agent,
                    "timestamp": time.time(),
                }),
            )

            # Broadcast to all agents
            self.redis_client.publish("blueprint:update", json.dumps({
                "knight_id": knight_id,
                "source_agent": source_agent,
                "timestamp": time.time(),
            }))
        except Exception as e:
            print(f"[SYNC] Blueprint replication failed: {e}", file=sys.stderr)

    async def get_cross_agent_insights(self, category: str) -> dict:
        """Get aggregated insights across all agents."""
        if not self.redis_client:
            return {}

        try:
            insights = {}
            agents = ["hermes", "openclaw", "nanobot", "zeroclaw", "rustclaw"]

            for agent_id in agents:
                insight_key = f"insight:{agent_id}:{category}"
                data = self.redis_client.get(insight_key)
                if data:
                    insights[agent_id] = json.loads(data)

            return {
                "category": category,
                "agent_insights": insights,
                "aggregated_at": time.time(),
            }
        except Exception as e:
            print(f"[SYNC] Cross-agent insights failed: {e}", file=sys.stderr)
            return {}

    async def consensus_merge(
        self,
        agent_votes: dict[str, str],  # {agent_id: decision}
    ) -> str:
        """Consensus-based merge of competing decisions."""
        if not agent_votes:
            return ""

        # Simple majority vote
        from collections import Counter

        votes = Counter(agent_votes.values())
        consensus = votes.most_common(1)[0][0]

        return consensus

    def _hash_id(self, dispatch_id: str) -> int:
        """Convert dispatch_id to numeric ID for Qdrant."""
        import hashlib

        h = hashlib.md5(dispatch_id.encode()).digest()
        return int.from_bytes(h[:8], byteorder="big")


# ── Module-level singleton ────────────────────────────────────────────────

_syncer: Optional[MemorySyncer] = None


def get_memory_syncer() -> MemorySyncer:
    """Get or create shared MemorySyncer instance."""
    global _syncer
    if _syncer is None:
        _syncer = MemorySyncer()
    return _syncer


async def sync_vector_to_peers(
    dispatch_id: str,
    vector: list[float],
    metadata: dict,
    source_agent: str,
) -> None:
    """Convenience: sync vector to peers."""
    syncer = get_memory_syncer()
    await syncer.sync_vector_to_peers(dispatch_id, vector, metadata, source_agent)


async def merge_synthesis(
    category: str,
    synthesis_text: str,
    source_agent: str,
) -> str:
    """Convenience: merge synthesis."""
    syncer = get_memory_syncer()
    return await syncer.merge_synthesis(category, synthesis_text, source_agent)
