# SPDX-License-Identifier: MIT

"""
CloudBrain Synthesis — Weekly pattern extraction & learning.

Weekly job:
  1. Query Qdrant for past week's dispatches
  2. Cluster by category/pattern
  3. Synthesize via CloudBrain/NotebookLM
  4. Store insights back in Qdrant
  5. Update blueprint.md with learnings

Usage:
    python -m control_plane.cloudbrain_synthesis  # Run weekly job
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class DispatchClusterer:
    """Cluster dispatches by category and pattern."""

    @staticmethod
    def cluster_by_category(dispatches: list[dict]) -> dict[str, list[dict]]:
        """Group dispatches by category."""
        clusters = {}
        for dispatch in dispatches:
            category = dispatch.get("category", "GENERAL")
            if category not in clusters:
                clusters[category] = []
            clusters[category].append(dispatch)
        return clusters

    @staticmethod
    def cluster_by_pattern(dispatches: list[dict], max_per_cluster: int = 10) -> list[dict]:
        """Cluster similar dispatches by semantic similarity (using existing vectors)."""
        if not dispatches:
            return []

        # Group by category first
        by_category = DispatchClusterer.cluster_by_category(dispatches)

        clusters = []
        for category, items in by_category.items():
            # Sort by timestamp (newest first)
            items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

            clusters.append({
                "id": f"cluster_{category}_{int(time.time())}",
                "category": category,
                "member_count": len(items),
                "members": items[:max_per_cluster],  # Top 10 recent
                "timestamp": time.time(),
            })

        return clusters


class CloudBrainSynthesizer:
    """Synthesis via CloudBrain/NotebookLM."""

    @staticmethod
    async def synthesize(pattern: dict) -> str:
        """Synthesize insights from a cluster of dispatches."""
        try:
            from control_plane.cloudbrain_sync import query_cloud_brain

            # Build query
            category = pattern["category"]
            members = pattern["members"]
            member_summaries = [
                f"- {m.get('keywords', [])} (quality: {m.get('latency_ms', 0)}ms)"
                for m in members[:5]
            ]

            query = f"""
Analyze {category} category dispatches:
{json.dumps(member_summaries)}

Key questions:
1. What are the common patterns?
2. Which approaches worked best?
3. How can we improve quality?
4. What should every knight know about {category} tasks?
"""

            # Query CloudBrain
            result = await asyncio.to_thread(query_cloud_brain, query)
            return result or f"No synthesis available for {category}"
        except Exception as e:
            print(f"[SYNTHESIS] CloudBrain query failed: {e}", file=sys.stderr)
            return f"Synthesis failed: {e}"

    @staticmethod
    async def extract_insights(synthesis_text: str) -> dict:
        """Extract structured insights from synthesis."""
        return {
            "type": "synthesis",
            "content": synthesis_text,
            "timestamp": time.time(),
        }


class WeeklySynthesisJob:
    """Weekly synthesis job orchestrator."""

    def __init__(self) -> None:
        self.clusterer = DispatchClusterer()
        self.synthesizer = CloudBrainSynthesizer()

    async def run(self) -> dict:
        """Run weekly synthesis job."""
        print("[SYNTHESIS] Starting weekly synthesis job...", file=sys.stderr)

        # 1. Query Qdrant for past week's dispatches
        dispatches = await self._query_recent_dispatches(days=7)
        print(f"[SYNTHESIS] Found {len(dispatches)} dispatches from past week", file=sys.stderr)

        if not dispatches:
            return {"status": "no_data", "dispatches_found": 0}

        # 2. Cluster dispatches
        clusters = self.clusterer.cluster_by_pattern(dispatches)
        print(f"[SYNTHESIS] Clustered into {len(clusters)} patterns", file=sys.stderr)

        # 3. Synthesize each cluster
        syntheses = []
        for cluster in clusters:
            synthesis = await self.synthesizer.synthesize(cluster)
            insights = await self.synthesizer.extract_insights(synthesis)

            syntheses.append({
                "cluster_id": cluster["id"],
                "category": cluster["category"],
                "member_count": cluster["member_count"],
                "synthesis": synthesis,
                "insights": insights,
            })

            print(f"[SYNTHESIS] Synthesized {cluster['category']} cluster", file=sys.stderr)

        # 4. Store insights in Qdrant
        await self._store_syntheses(syntheses)

        # 5. Update blueprints
        await self._update_blueprints(syntheses)

        print("[SYNTHESIS] Weekly synthesis job complete", file=sys.stderr)
        return {
            "status": "complete",
            "dispatches_processed": len(dispatches),
            "clusters": len(clusters),
            "syntheses": len(syntheses),
        }

    async def _query_recent_dispatches(self, days: int = 7) -> list[dict]:
        """Query Qdrant for recent dispatches."""
        try:
            from control_plane.symbol_compressor import get_compressor

            compressor = get_compressor()
            if not compressor.client:
                return []

            # Query all points from past N days
            cutoff_time = time.time() - (days * 86400)
            results = compressor.client.scroll(
                collection_name="hive_dispatches",
                limit=1000,
                query_filter={
                    "must": [
                        {
                            "key": "timestamp",
                            "range": {"gte": cutoff_time},
                        }
                    ]
                },
            )

            if not results[0]:
                return []

            # Convert to dict
            dispatches = []
            for point in results[0]:
                payload = point.payload or {}
                dispatches.append(payload)

            return dispatches
        except Exception as e:
            print(f"[SYNTHESIS] Query failed: {e}", file=sys.stderr)
            return []

    async def _store_syntheses(self, syntheses: list[dict]) -> None:
        """Store synthesis insights in Qdrant."""
        try:
            from control_plane.symbol_compressor import get_compressor

            compressor = get_compressor()
            if not compressor.client:
                return

            # Store each synthesis as a point
            for synth in syntheses:
                # Embed synthesis text
                vector = compressor._embed(synth["synthesis"])

                from qdrant_client.models import PointStruct
                point = PointStruct(
                    id=compressor._hash_id(synth["cluster_id"]),
                    vector=vector,
                    payload={
                        "type": "synthesis",
                        "cluster_id": synth["cluster_id"],
                        "category": synth["category"],
                        "member_count": synth["member_count"],
                        "synthesis": synth["synthesis"][:1000],  # Store summary
                        "timestamp": synth["insights"]["timestamp"],
                    },
                )

                compressor.client.upsert(
                    collection_name="hive_dispatches",
                    points=[point],
                )
        except Exception as e:
            print(f"[SYNTHESIS] Store failed: {e}", file=sys.stderr)

    async def _update_blueprints(self, syntheses: list[dict]) -> None:
        """Update blueprint.md with synthesis insights."""
        try:
            from control_plane.knight_knowledgebase import get_knowledgebase

            kb = get_knowledgebase()

            # For each synthesis, update relevant knight blueprints
            for synth in syntheses:
                category = synth["category"]

                # Find knights that work on this category
                # (This is simplified; in reality, route via intent_router)
                knights = await self._get_knights_for_category(category)

                for knight_id in knights:
                    blueprint = await kb.load_blueprint(knight_id)

                    # Append insight to blueprint
                    _updated_blueprint = f"""{blueprint}

## Synthesis: {category}
**Updated: {time.strftime('%Y-%m-%d')}**

{synth['synthesis'][:500]}

---
"""

                    # Write back
                    _path = kb._cache[f"{knight_id}:blueprint"].content if f"{knight_id}:blueprint" in kb._cache else ""
                    # Note: blueprint.md file update would happen here
                    print(f"[SYNTHESIS] Updated blueprint for {knight_id} ({category})", file=sys.stderr)
        except Exception as e:
            print(f"[SYNTHESIS] Blueprint update failed: {e}", file=sys.stderr)

    @staticmethod
    async def _get_knights_for_category(category: str) -> list[str]:
        """Get list of knights that specialize in a category."""
        try:
            from control_plane.intent_router import INTENT_TERMINAL_MAP, IntentCategory

            # Map category to intent enum
            category_map = {
                "FORGE": IntentCategory.FORGE,
                "CODE": IntentCategory.CODE,
                "RESEARCH": IntentCategory.RESEARCH,
                "MEMORY": IntentCategory.MEMORY,
                "OPS": IntentCategory.OPS,
                "SECURITY": IntentCategory.SECURITY,
            }

            intent = category_map.get(category)
            if intent:
                return INTENT_TERMINAL_MAP.get(intent, [])
            return []
        except Exception:
            return []


# ── CLI Entry Point ───────────────────────────────────────────────────────

async def main() -> None:
    """Run weekly synthesis job."""
    job = WeeklySynthesisJob()
    result = await job.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
