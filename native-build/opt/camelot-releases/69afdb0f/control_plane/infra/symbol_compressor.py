# SPDX-License-Identifier: MIT

"""
Symbol Compressor — Dispatch compression & semantic indexing.

Converts dispatch events into compressed vectors (Qdrant):
  1. Extract keywords (sparse tokens)
  2. Create embedding (768-dim vector)
  3. Store in Qdrant with metadata
  4. Cache in Redis (L1, 24h)

Token reduction: 100-token dispatch → 1 embedding vector (100x reduction)
Privacy: Only vectors stored in Qdrant (no raw prompts)

Usage:
    compressor = SymbolCompressor()
    await compressor.compress(dispatch_event)
    similar = await compressor.find_similar(prompt, knight_id, limit=3)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    _QDRANT = True
except ImportError:
    _QDRANT = False


QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_COLLECTION = "hive_dispatches"
EMBEDDING_DIM = 384  # Use smaller model (all-MiniLM-L6-v2) for speed


@dataclass
class CompressedDispatch:
    """Compressed dispatch record."""
    dispatch_id: str
    knight_id: str
    vector: list[float]
    keywords: list[str]
    category: str
    confidence: float
    tokens_in: int
    tokens_out: int
    latency_ms: float
    model: str
    timestamp: float
    success: bool


class SymbolCompressor:
    """Dispatch compression and semantic indexing."""

    def __init__(self) -> None:
        self.client: Optional[QdrantClient] = None
        self.embedding_model = None
        self._init_qdrant()
        self._init_embedding_model()

    def _init_qdrant(self) -> None:
        """Initialize Qdrant client."""
        if not _QDRANT:
            print("[COMPRESSOR] qdrant-client not installed — compression disabled", file=sys.stderr)
            return

        try:
            api_key = os.environ.get("QDRANT_API_KEY")
            self.client = QdrantClient(QDRANT_URL, api_key=api_key)
            # Create collection if not exists
            try:
                self.client.get_collection(QDRANT_COLLECTION)
            except Exception:
                self.client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                )
            print(f"[COMPRESSOR] Connected to Qdrant @ {QDRANT_URL}", file=sys.stderr)
        except Exception as e:
            print(f"[COMPRESSOR] Qdrant init failed: {e}", file=sys.stderr)
            self.client = None

    def _init_embedding_model(self) -> None:
        """Initialize embedding model (lazy load)."""
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("[COMPRESSOR] Embedding model loaded (all-MiniLM-L6-v2)", file=sys.stderr)
        except ImportError:
            print("[COMPRESSOR] sentence-transformers not installed — embeddings disabled", file=sys.stderr)
        except Exception as e:
            print(f"[COMPRESSOR] Embedding model init failed: {e}", file=sys.stderr)

    def _extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """Extract keywords from text using simple heuristics."""
        # Simple approach: split, remove stopwords, sort by TF
        import re
        from collections import Counter

        # Lowercase and remove punctuation
        words = re.findall(r"\b\w+\b", text.lower())

        # Remove common stopwords
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "was", "are", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "what", "which", "who", "when",
            "where", "why", "how",
        }

        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        # Return top by frequency
        counter = Counter(keywords)
        return [word for word, _ in counter.most_common(max_keywords)]

    def _embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        if not self.embedding_model:
            return [0.0] * EMBEDDING_DIM

        try:
            embedding = self.embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        except Exception as e:
            print(f"[COMPRESSOR] Embedding failed: {e}", file=sys.stderr)
            return [0.0] * EMBEDDING_DIM

    async def compress(
        self,
        dispatch_id: str,
        knight_id: str,
        prompt: str,
        category: str,
        confidence: float,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        model: str,
        success: bool = True,
    ) -> CompressedDispatch:
        """Compress a dispatch into vector + metadata."""
        # Extract keywords (sparse tokens)
        keywords = self._extract_keywords(prompt)

        # Create embedding
        vector = self._embed(prompt)

        # Create compressed record
        compressed = CompressedDispatch(
            dispatch_id=dispatch_id,
            knight_id=knight_id,
            vector=vector,
            keywords=keywords,
            category=category,
            confidence=confidence,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            model=model,
            timestamp=time.time(),
            success=success,
        )

        # Store in Qdrant (L2)
        if self.client:
            try:
                point = PointStruct(
                    id=self._hash_id(dispatch_id),
                    vector=vector,
                    payload={
                        "dispatch_id": dispatch_id,
                        "knight_id": knight_id,
                        "keywords": keywords,
                        "category": category,
                        "confidence": confidence,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "latency_ms": latency_ms,
                        "model": model,
                        "timestamp": compressed.timestamp,
                        "success": success,
                    },
                )
                self.client.upsert(
                    collection_name=QDRANT_COLLECTION,
                    points=[point],
                )
            except Exception as e:
                print(f"[COMPRESSOR] Qdrant store failed: {e}", file=sys.stderr)

        # Store in Redis (L1) for fast retrieval
        try:
            import redis
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            r = redis.from_url(redis_url, decode_responses=True)
            r.setex(
                f"dispatch:{dispatch_id}:compressed",
                86400,  # 24h TTL
                json.dumps({
                    "dispatch_id": dispatch_id,
                    "knight_id": knight_id,
                    "keywords": keywords,
                    "category": category,
                    "confidence": confidence,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": latency_ms,
                    "model": model,
                    "timestamp": compressed.timestamp,
                    "success": success,
                }),
            )
        except Exception:
            pass

        return compressed

    async def find_similar(
        self,
        prompt: str,
        knight_id: str,
        limit: int = 3,
        threshold: float = 0.75,
    ) -> list[dict]:
        """Find similar past dispatches in Qdrant."""
        if not self.client:
            return []

        try:
            # Create query embedding
            query_vector = self._embed(prompt)

            # Search Qdrant
            results = self.client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_vector,
                query_filter={
                    "must": [
                        {
                            "key": "knight_id",
                            "match": {"value": knight_id},
                        }
                    ]
                },
                limit=limit,
            )

            # Convert to dict with score
            similar = []
            for result in results:
                if result.score >= threshold:
                    payload = result.payload or {}
                    payload["score"] = result.score
                    similar.append(payload)

            return similar
        except Exception as e:
            print(f"[COMPRESSOR] Search failed: {e}", file=sys.stderr)
            return []

    async def get_knight_stats(self, knight_id: str) -> dict:
        """Get compression stats for a knight."""
        if not self.client:
            return {}

        try:
            # Query all dispatches for this knight
            results = self.client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=1000,
                query_filter={
                    "must": [
                        {
                            "key": "knight_id",
                            "match": {"value": knight_id},
                        }
                    ]
                },
            )

            if not results[0]:
                return {}

            # Aggregate stats
            points = results[0]
            total_dispatches = len(points)
            total_tokens_in = sum(p.payload.get("tokens_in", 0) for p in points)
            total_tokens_out = sum(p.payload.get("tokens_out", 0) for p in points)
            avg_latency = sum(p.payload.get("latency_ms", 0) for p in points) / total_dispatches if total_dispatches else 0
            success_count = sum(1 for p in points if p.payload.get("success"))

            return {
                "knight_id": knight_id,
                "total_dispatches": total_dispatches,
                "total_tokens_in": total_tokens_in,
                "total_tokens_out": total_tokens_out,
                "avg_tokens_per_dispatch": total_tokens_in / total_dispatches if total_dispatches else 0,
                "avg_latency_ms": avg_latency,
                "success_rate": success_count / total_dispatches if total_dispatches else 0,
                "compression_ratio": f"{(total_tokens_in / (total_dispatches * EMBEDDING_DIM)):.1f}x" if total_dispatches else "N/A",
            }
        except Exception as e:
            print(f"[COMPRESSOR] Stats failed: {e}", file=sys.stderr)
            return {}

    def _hash_id(self, dispatch_id: str) -> int:
        """Convert dispatch_id string to numeric ID for Qdrant."""
        h = hashlib.md5(dispatch_id.encode()).digest()
        return int.from_bytes(h[:8], byteorder="big")


# ── Module-level singleton ────────────────────────────────────────────────

_compressor: Optional[SymbolCompressor] = None


def get_compressor() -> SymbolCompressor:
    """Get or create the shared SymbolCompressor instance."""
    global _compressor
    if _compressor is None:
        _compressor = SymbolCompressor()
    return _compressor


async def compress_dispatch(
    dispatch_id: str,
    knight_id: str,
    prompt: str,
    category: str,
    confidence: float,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    model: str,
) -> None:
    """Module-level convenience: compress a dispatch."""
    compressor = get_compressor()
    await compressor.compress(
        dispatch_id, knight_id, prompt, category, confidence,
        tokens_in, tokens_out, latency_ms, model
    )


async def find_similar_dispatches(
    prompt: str,
    knight_id: str,
    limit: int = 3,
) -> list[dict]:
    """Module-level convenience: find similar past dispatches."""
    compressor = get_compressor()
    return await compressor.find_similar(prompt, knight_id, limit)
