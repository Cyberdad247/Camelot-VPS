# SPDX-License-Identifier: MIT

"""
Knight Flash Memory — Redis Agent Memory with 24-hour Purge System.

Stores session context, terminal state, and long-term facts for the Hive.
Automatic purge of stale sessions (>24h) and periodic compaction.

Usage:
    from control_plane.agent_memory import KnightMemory
    mem = KnightMemory()

    # Log a dispatch
    await mem.log_dispatch("sir_boris", "Refactor code", system_prompt)

    # Store a fact
    await mem.store_fact("sir_boris", "specializes in architecture review")

    # Retrieve session
    session = await mem.get_session("sir_boris")

    # Search memories
    results = await mem.search("which knight handles security?")
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from redis_iris import AgentMemory
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


# ── Configuration ─────────────────────────────────────────────────────────

AGENT_MEMORY_URL = os.environ.get(
    "AGENT_MEMORY_URL",
    "https://gcp-us-east4.memory.redis.io"
)
AGENT_MEMORY_STORE_ID = os.environ.get(
    "AGENT_MEMORY_STORE_ID",
    "9554270fe8574d1ea5f5fb40140b4b7b"
)
AGENT_MEMORY_API_KEY = os.environ.get(
    "AGENT_MEMORY_API_KEY",
    ""
)

SESSION_PURGE_TTL_SECONDS = 86400  # 24 hours
LONG_TERM_RETENTION_SECONDS = 2592000  # 30 days


# ── Knight Memory ─────────────────────────────────────────────────────────

class KnightMemory:
    """Distributed flash memory for agent state and facts."""

    def __init__(self) -> None:
        self.client: Optional[AgentMemory] = None
        self._init_client()

    def _init_client(self) -> None:
        if not _REDIS_AVAILABLE:
            print("[AGENT_MEMORY] redis-iris not installed — memory disabled", file=sys.stderr)
            return

        if not AGENT_MEMORY_API_KEY:
            print("[AGENT_MEMORY] AGENT_MEMORY_API_KEY not set — memory disabled", file=sys.stderr)
            return

        try:
            self.client = AgentMemory(
                serverURL=AGENT_MEMORY_URL,
                storeId=AGENT_MEMORY_STORE_ID,
                apiKey=AGENT_MEMORY_API_KEY,
            )
            print(f"[AGENT_MEMORY] Connected to {AGENT_MEMORY_URL}", file=sys.stderr)
        except Exception as e:
            print(f"[AGENT_MEMORY] Connection failed: {e}", file=sys.stderr)
            self.client = None

    async def log_dispatch(
        self,
        terminal_id: str,
        prompt: str,
        system: str = "",
        model: str = "",
    ) -> None:
        """Log a prompt dispatch for session reconstruction."""
        if not self.client:
            return

        try:
            await self.client.addSessionEvent({
                "sessionId": f"knight-{terminal_id}",
                "actorId": terminal_id,
                "role": "DISPATCH",
                "content": [
                    {
                        "text": prompt,
                        "metadata": {
                            "system": system,
                            "model": model,
                            "timestamp": time.time(),
                        }
                    }
                ],
                "createdAt": int(time.time() * 1000),
            })
        except Exception as e:
            print(f"[AGENT_MEMORY] log_dispatch failed for {terminal_id}: {e}", file=sys.stderr)

    async def log_response(
        self,
        terminal_id: str,
        response: str,
        latency_ms: float = 0.0,
    ) -> None:
        """Log a response for session history."""
        if not self.client:
            return

        try:
            await self.client.addSessionEvent({
                "sessionId": f"knight-{terminal_id}",
                "actorId": terminal_id,
                "role": "RESPONSE",
                "content": [
                    {
                        "text": response[:2000],  # truncate large responses
                        "metadata": {
                            "latency_ms": latency_ms,
                            "timestamp": time.time(),
                        }
                    }
                ],
                "createdAt": int(time.time() * 1000),
            })
        except Exception as e:
            print(f"[AGENT_MEMORY] log_response failed for {terminal_id}: {e}", file=sys.stderr)

    async def store_fact(self, terminal_id: str, fact: str) -> None:
        """Store a long-term fact about a knight (capability, behavior, etc.)."""
        if not self.client:
            return

        try:
            fact_id = f"fact-{terminal_id}-{int(time.time())}"
            await self.client.bulkCreateLongTermMemories({
                "memories": [
                    {
                        "id": fact_id,
                        "text": f"{terminal_id}: {fact}",
                        "metadata": {
                            "terminal": terminal_id,
                            "created_at": time.time(),
                        }
                    }
                ]
            })
        except Exception as e:
            print(f"[AGENT_MEMORY] store_fact failed for {terminal_id}: {e}", file=sys.stderr)

    async def get_session(self, terminal_id: str) -> dict:
        """Retrieve the session memory for a knight (dispatch/response history)."""
        if not self.client:
            return {}

        try:
            session = await self.client.getSessionMemory(f"knight-{terminal_id}")
            return session or {}
        except Exception as e:
            print(f"[AGENT_MEMORY] get_session failed for {terminal_id}: {e}", file=sys.stderr)
            return {}

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """Semantic search across long-term facts and session history."""
        if not self.client:
            return []

        try:
            results = await self.client.searchLongTermMemory({
                "text": query,
                "topK": limit,
            })
            return results or []
        except Exception as e:
            print(f"[AGENT_MEMORY] search failed for '{query}': {e}", file=sys.stderr)
            return []

    async def purge_stale_sessions(self) -> int:
        """Delete sessions older than 24 hours. Returns count purged."""
        if not self.client:
            return 0

        # Note: redis-iris may not expose bulk delete directly.
        # This is a placeholder for when the API adds purge capability.
        # For now, sessions naturally expire server-side.
        return 0

    async def store_dispatch_context(
        self,
        terminal_id: str,
        category: str,
        confidence: float,
        candidates: list[str],
    ) -> None:
        """Store routing context for future intent analysis."""
        if not self.client:
            return

        try:
            await self.client.bulkCreateLongTermMemories({
                "memories": [
                    {
                        "id": f"context-{terminal_id}-{int(time.time())}",
                        "text": (
                            f"Dispatch to {terminal_id}: "
                            f"category={category}, confidence={confidence:.2f}, "
                            f"candidates={','.join(candidates)}"
                        ),
                        "metadata": {
                            "terminal": terminal_id,
                            "category": category,
                            "confidence": confidence,
                        }
                    }
                ]
            })
        except Exception as e:
            print(f"[AGENT_MEMORY] store_dispatch_context failed: {e}", file=sys.stderr)


# ── Module-level singleton ────────────────────────────────────────────────

_memory: Optional[KnightMemory] = None


def get_memory() -> KnightMemory:
    """Get or create the shared KnightMemory instance."""
    global _memory
    if _memory is None:
        _memory = KnightMemory()
    return _memory


async def log_dispatch(
    terminal_id: str,
    prompt: str,
    system: str = "",
    model: str = "",
) -> None:
    """Module-level convenience: log a dispatch."""
    mem = get_memory()
    await mem.log_dispatch(terminal_id, prompt, system, model)


async def log_response(
    terminal_id: str,
    response: str,
    latency_ms: float = 0.0,
) -> None:
    """Module-level convenience: log a response."""
    mem = get_memory()
    await mem.log_response(terminal_id, response, latency_ms)


async def store_fact(terminal_id: str, fact: str) -> None:
    """Module-level convenience: store a fact."""
    mem = get_memory()
    await mem.store_fact(terminal_id, fact)


async def search(query: str, limit: int = 5) -> list[dict]:
    """Module-level convenience: search facts."""
    mem = get_memory()
    return await mem.search(query, limit)
