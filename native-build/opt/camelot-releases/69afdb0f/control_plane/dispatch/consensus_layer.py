# SPDX-License-Identifier: MIT

"""
Consensus Layer — Multi-agent coordination and conflict resolution.

Handles:
  - Consensus-based routing decisions
  - Deconfliction of competing syntheses
  - Voting-based capability selection
  - Fallback routing on agent failure

Usage:
    consensus = ConsensusLayer()
    decision = await consensus.vote_on_routing(prompt, candidate_agents)
    winner = await consensus.consensus_merge(proposals)
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class ConsensusLayer:
    """Multi-agent coordination via consensus."""

    def __init__(self) -> None:
        self.redis_client = None
        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis for voting."""
        try:
            import redis

            self.redis_client = redis.Redis(
                host="localhost", port=6379, decode_responses=True
            )
            self.redis_client.ping()
            print("[CONSENSUS] Redis ready for voting", file=sys.stderr)
        except Exception as e:
            print(f"[CONSENSUS] Redis init failed: {e}", file=sys.stderr)

    async def vote_on_routing(
        self,
        prompt: str,
        candidate_agents: list[str],
        votes_needed: int = 3,
    ) -> Optional[str]:
        """Get consensus vote on which agent should handle dispatch.

        Returns agent_id with majority vote, or None if no consensus.
        """
        if not self.redis_client:
            return candidate_agents[0] if candidate_agents else None

        try:
            # Query each agent for preference
            votes = {}
            for agent_id in candidate_agents:
                vote = await self._get_agent_vote(agent_id, prompt)
                if vote:
                    votes[agent_id] = vote

            if not votes:
                return candidate_agents[0]

            # Tally votes
            vote_counts = Counter(votes.values())
            winner, count = vote_counts.most_common(1)[0]

            if count >= votes_needed:
                return winner

            # No consensus; return most frequent
            return winner
        except Exception as e:
            print(f"[CONSENSUS] Voting failed: {e}", file=sys.stderr)
            return candidate_agents[0] if candidate_agents else None

    async def _get_agent_vote(self, agent_id: str, prompt: str) -> Optional[str]:
        """Get single agent's vote on prompt routing."""
        try:
            # Query agent capability match score
            # (In real implementation, would call agent's scoring endpoint)
            score = await self._compute_match_score(agent_id, prompt)

            if score > 0.7:
                return agent_id
            return None
        except Exception:
            return None

    async def _compute_match_score(self, agent_id: str, prompt: str) -> float:
        """Compute capability match score (simple heuristic)."""
        from control_plane.agent_registry import get_agent

        agent = get_agent(agent_id)
        if not agent:
            return 0.0

        # Score based on capability keywords
        score = 0.5  # Base score
        keywords = prompt.lower().split()

        for cap in agent.capabilities:
            if any(kw in cap for kw in keywords):
                score += 0.1

        return min(1.0, score)

    async def consensus_merge(
        self,
        proposals: dict[str, str],  # {agent_id: proposal_text}
        use_synthesis: bool = True,
    ) -> str:
        """Merge competing proposals via consensus.

        Simple: majority vote on identical text
        Synthesis: ask CloudBrain to merge unique proposals
        """
        if not proposals:
            return ""

        # Count identical proposals
        proposal_counts = Counter(proposals.values())
        most_common, count = proposal_counts.most_common(1)

        # If majority agrees, use that
        if count >= len(proposals) / 2:
            return most_common

        # Otherwise, try synthesis
        if use_synthesis:
            try:
                from control_plane.cloudbrain_sync import query_cloud_brain

                query = f"""
Multiple agents proposed different solutions:

{json.dumps(proposals, indent=2)}

Synthesize the best elements into one coherent proposal.
Focus on: correctness, efficiency, clarity.
"""

                result = await asyncio.to_thread(query_cloud_brain, query)
                return result or most_common
            except Exception:
                pass

        return most_common

    async def select_agent_for_capability(
        self,
        capability: str,
        fallback_agents: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Select best agent for specific capability."""
        from control_plane.agent_registry import get_agent_registry

        registry = get_agent_registry()
        candidates = registry.get_agents_with_capability(capability)

        if not candidates:
            # Fallback
            return fallback_agents[0] if fallback_agents else None

        # Return first available
        for agent in candidates:
            if agent.status == "ready":
                return agent.agent_id

        # All busy; return healthiest
        return candidates[0].agent_id if candidates else None

    async def handle_agent_failure(
        self,
        failed_agent_id: str,
        original_task: dict,
    ) -> Optional[str]:
        """Route task to alternate agent on primary failure."""
        from control_plane.agent_registry import get_agent_registry

        registry = get_agent_registry()

        # Find agents with overlapping capabilities
        failed_agent = registry.get(failed_agent_id)
        if not failed_agent:
            return None

        alternatives = []
        for agent in registry.list_agents():
            if agent.agent_id == failed_agent_id:
                continue
            if agent.status != "ready":
                continue

            # Check capability overlap
            overlap = set(agent.capabilities) & set(failed_agent.capabilities)
            if overlap:
                alternatives.append((agent, len(overlap)))

        if not alternatives:
            return None

        # Return best match
        alternatives.sort(key=lambda x: x[1], reverse=True)
        return alternatives[0][0].agent_id

    async def broadcast_decision(
        self,
        decision_id: str,
        decision: str,
        agents_involved: list[str],
    ) -> None:
        """Broadcast consensus decision to all agents."""
        if not self.redis_client:
            return

        try:
            for agent_id in agents_involved:
                self.redis_client.setex(
                    f"decision:{decision_id}:{agent_id}",
                    3600,  # 1 hour TTL
                    decision,
                )

            # Publish announcement
            self.redis_client.publish("consensus:decision", json.dumps({
                "decision_id": decision_id,
                "decision": decision,
                "agents": agents_involved,
            }))
        except Exception as e:
            print(f"[CONSENSUS] Broadcast failed: {e}", file=sys.stderr)


# ── Module-level singleton ────────────────────────────────────────────────

_consensus: Optional[ConsensusLayer] = None


def get_consensus_layer() -> ConsensusLayer:
    """Get or create shared ConsensusLayer instance."""
    global _consensus
    if _consensus is None:
        _consensus = ConsensusLayer()
    return _consensus


async def vote_on_routing(
    prompt: str,
    candidate_agents: list[str],
) -> Optional[str]:
    """Convenience: vote on routing."""
    consensus = get_consensus_layer()
    return await consensus.vote_on_routing(prompt, candidate_agents)
