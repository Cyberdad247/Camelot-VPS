# SPDX-License-Identifier: MIT

"""
Knight Self-Enhancer — Post-dispatch learning & knowledge updates.

After each dispatch:
  1. Update tasks.md with completed task
  2. Update verification.md with quality metrics
  3. Store insights in CloudBrain
  4. Index in Qdrant (async)

Usage:
    enhancer = KnightSelfEnhancer()
    await enhancer.post_dispatch(dispatch_event, response, latency_ms)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class DispatchEvent:
    """Dispatch event for post-processing."""
    dispatch_id: str
    knight_id: str
    prompt: str
    system: str
    category: str
    confidence: float
    tokens_in: int
    latency_ms: float
    model: str
    timestamp: float


class QualityAssessor:
    """Assess quality of dispatch response."""

    @staticmethod
    def assess(prompt: str, response: str, latency_ms: float) -> dict:
        """Simple quality heuristics."""
        # Length check: response should be substantive
        length_score = min(1.0, len(response) / 200)  # 200+ tokens is good

        # Latency check: fast responses are good (but not too fast = suspicious)
        if latency_ms < 50:
            latency_score = 0.7  # Too fast, might be cached/incomplete
        elif latency_ms < 500:
            latency_score = 1.0  # Good range
        else:
            latency_score = max(0.5, 1.0 - (latency_ms - 500) / 5000)  # Degrades

        # Error markers
        error_score = 1.0
        error_indicators = [
            "error", "exception", "traceback", "failed", "unable to",
            "i apologize", "i can't", "i don't have access"
        ]
        if any(indicator in response.lower() for indicator in error_indicators):
            error_score = 0.3

        # Coherence: very short or incoherent responses
        coherence_score = 0.9
        if len(response) < 50:
            coherence_score = 0.4

        # Overall
        overall = (length_score * 0.3 + latency_score * 0.3 + error_score * 0.2 + coherence_score * 0.2)
        return {
            "overall": round(overall, 2),
            "length": round(length_score, 2),
            "latency": round(latency_score, 2),
            "errors": round(error_score, 2),
            "coherence": round(coherence_score, 2),
        }


class KnightSelfEnhancer:
    """Post-dispatch learning and knowledge updates."""

    def __init__(self) -> None:
        self.assessor = QualityAssessor()

    async def post_dispatch(
        self,
        dispatch_event: DispatchEvent,
        response: str,
        tokens_out: int,
    ) -> None:
        """Process dispatch after completion."""
        # 1. Assess quality
        quality = self.assessor.assess(
            dispatch_event.prompt,
            response,
            dispatch_event.latency_ms,
        )

        # 2. Update tasks.md (async)
        asyncio.create_task(self._update_tasks(dispatch_event, quality))

        # 3. Update verification.md (async)
        asyncio.create_task(self._update_verification(dispatch_event, quality, tokens_out))

        # 4. Store insights in CloudBrain (async)
        asyncio.create_task(self._store_insights(dispatch_event, response, quality))

        # 5. Index in Qdrant (async)
        asyncio.create_task(self._index_compressed(dispatch_event, tokens_out))

    async def _update_tasks(self, dispatch_event: DispatchEvent, quality: dict) -> None:
        """Update tasks.md with completed task."""
        try:
            from control_plane.knight_knowledgebase import get_knowledgebase

            kb = get_knowledgebase()
            tasks = await kb.load_tasks(dispatch_event.knight_id)

            # Add completed task
            if "completed" not in tasks:
                tasks["completed"] = []

            tasks["completed"].append({
                "dispatch_id": dispatch_event.dispatch_id,
                "prompt": dispatch_event.prompt[:100],
                "category": dispatch_event.category,
                "timestamp": dispatch_event.timestamp,
                "latency_ms": dispatch_event.latency_ms,
                "quality_score": quality["overall"],
            })

            # Keep only last 50 completed tasks
            if len(tasks["completed"]) > 50:
                tasks["completed"] = tasks["completed"][-50:]

            # Write back
            await kb.update_tasks(dispatch_event.knight_id, tasks)
        except Exception as e:
            print(f"[ENHANCER] Failed to update tasks for {dispatch_event.knight_id}: {e}", file=sys.stderr)

    async def _update_verification(
        self,
        dispatch_event: DispatchEvent,
        quality: dict,
        tokens_out: int,
    ) -> None:
        """Update verification.md with quality results."""
        try:
            from control_plane.knight_knowledgebase import get_knowledgebase

            kb = get_knowledgebase()
            verification = await kb.load_verification(dispatch_event.knight_id)

            # Add result
            if "results" not in verification:
                verification["results"] = []

            verification["results"].append({
                "dispatch_id": dispatch_event.dispatch_id,
                "timestamp": dispatch_event.timestamp,
                "category": dispatch_event.category,
                "quality": quality,
                "tokens_in": dispatch_event.tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": dispatch_event.latency_ms,
                "model": dispatch_event.model,
            })

            # Keep only last 100 results
            if len(verification["results"]) > 100:
                verification["results"] = verification["results"][-100:]

            # Update aggregate metrics
            if "aggregate" not in verification:
                verification["aggregate"] = {}

            all_results = verification["results"]
            verification["aggregate"] = {
                "total_dispatches": len(all_results),
                "avg_quality": round(sum(r["quality"]["overall"] for r in all_results) / len(all_results), 2),
                "avg_latency_ms": round(sum(r["latency_ms"] for r in all_results) / len(all_results), 1),
                "success_rate": round(sum(1 for r in all_results if r["quality"]["overall"] >= 0.7) / len(all_results), 2),
                "avg_tokens_out": round(sum(r["tokens_out"] for r in all_results) / len(all_results), 0),
            }

            # Write back
            await kb.update_verification(dispatch_event.knight_id, verification)
        except Exception as e:
            print(f"[ENHANCER] Failed to update verification for {dispatch_event.knight_id}: {e}", file=sys.stderr)

    async def _store_insights(
        self,
        dispatch_event: DispatchEvent,
        response: str,
        quality: dict,
    ) -> None:
        """Store insights in CloudBrain."""
        try:
            from control_plane.cloudbrain_sync import query_cloud_brain

            # Extract key insight
            insight = {
                "type": "dispatch_pattern",
                "knight_id": dispatch_event.knight_id,
                "category": dispatch_event.category,
                "quality_score": quality["overall"],
                "summary": f"Category {dispatch_event.category}: quality {quality['overall']}, latency {dispatch_event.latency_ms}ms",
                "timestamp": dispatch_event.timestamp,
            }

            # Store via CloudBrain (fire-and-forget)
            try:
                await asyncio.to_thread(
                    query_cloud_brain,
                    f"Store insight: {json.dumps(insight)}"
                )
            except Exception:
                pass  # CloudBrain is optional
        except Exception as e:
            print(f"[ENHANCER] Failed to store insights: {e}", file=sys.stderr)

    async def _index_compressed(
        self,
        dispatch_event: DispatchEvent,
        tokens_out: int,
    ) -> None:
        """Index dispatch in Qdrant (symbol compression)."""
        try:
            from control_plane.symbol_compressor import compress_dispatch

            await compress_dispatch(
                dispatch_id=dispatch_event.dispatch_id,
                knight_id=dispatch_event.knight_id,
                prompt=dispatch_event.prompt,
                category=dispatch_event.category,
                confidence=dispatch_event.confidence,
                tokens_in=dispatch_event.tokens_in,
                tokens_out=tokens_out,
                latency_ms=dispatch_event.latency_ms,
                model=dispatch_event.model,
            )
        except Exception as e:
            print(f"[ENHANCER] Failed to compress dispatch: {e}", file=sys.stderr)

    async def get_knight_insights(self, knight_id: str) -> dict:
        """Get self-enhancement insights for a knight."""
        try:
            from control_plane.knight_knowledgebase import get_knowledgebase

            kb = get_knowledgebase()
            verification = await kb.load_verification(knight_id)

            return {
                "knight_id": knight_id,
                "recent_results": verification.get("results", [])[-10:],
                "aggregate": verification.get("aggregate", {}),
            }
        except Exception as e:
            print(f"[ENHANCER] Failed to get insights: {e}", file=sys.stderr)
            return {}


# ── Module-level singleton ────────────────────────────────────────────────

_enhancer: Optional[KnightSelfEnhancer] = None


def get_enhancer() -> KnightSelfEnhancer:
    """Get or create the shared KnightSelfEnhancer instance."""
    global _enhancer
    if _enhancer is None:
        _enhancer = KnightSelfEnhancer()
    return _enhancer


async def post_dispatch(
    dispatch_id: str,
    knight_id: str,
    prompt: str,
    system: str,
    category: str,
    confidence: float,
    tokens_in: int,
    tokens_out: int,
    response: str,
    latency_ms: float,
    model: str,
) -> None:
    """Module-level convenience: process dispatch post-completion."""
    enhancer = get_enhancer()
    event = DispatchEvent(
        dispatch_id=dispatch_id,
        knight_id=knight_id,
        prompt=prompt,
        system=system,
        category=category,
        confidence=confidence,
        tokens_in=tokens_in,
        latency_ms=latency_ms,
        model=model,
        timestamp=time.time(),
    )
    await enhancer.post_dispatch(event, response, tokens_out)
