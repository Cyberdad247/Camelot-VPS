# SPDX-License-Identifier: MIT

"""
Knight Knowledge Base — Per-knight document management.

# HITL: file-ops pre-approved — writes bounded to per-knight cache files only

Loads blueprint.md, agent.md, tasks.md, verification.md from disk.
Syncs to Redis (L1 cache) and provides context enrichment.

Usage:
    kb = KnightKnowledgeBase()
    blueprint = await kb.load("sir_boris")
    agent_config = await kb.agent("sir_boris")
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import aiofiles
    _AIOFILES = True
except ImportError:
    _AIOFILES = False

try:
    import yaml
    _YAML = True
except ImportError:
    _YAML = False


CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
KNIGHTS_DIR = CAMELOT_HOME / "03_VAULT" / "knights"


@dataclass
class KnightDocument:
    """Represents a knight's document with metadata."""
    knight_id: str
    doc_type: str  # "blueprint" | "agent" | "tasks" | "verification"
    content: str
    loaded_at: float
    hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class KnightKnowledgeBase:
    """Per-knight knowledge base manager with Redis integration."""

    def __init__(self) -> None:
        self._cache: dict[str, KnightDocument] = {}
        self._redis_enabled = False
        try:
            from control_plane.agent_memory import get_memory
            mem = get_memory()
            self._redis_enabled = mem.client is not None
        except Exception:
            pass

    async def _read_file(self, path: Path) -> str:
        """Read file async if aiofiles available, else sync."""
        try:
            if _AIOFILES:
                async with aiofiles.open(path, "r", encoding="utf-8") as f:
                    return await f.read()
            else:
                return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
        except Exception as e:
            print(f"[KB] Error reading {path}: {e}", file=sys.stderr)
            return ""

    def _hash_content(self, content: str) -> str:
        """Simple content hash for change detection."""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()[:8]

    async def load_blueprint(self, knight_id: str) -> str:
        """Load blueprint.md for a knight."""
        path = KNIGHTS_DIR / knight_id / "blueprint.md"
        content = await self._read_file(path)

        doc = KnightDocument(
            knight_id=knight_id,
            doc_type="blueprint",
            content=content,
            loaded_at=time.time(),
            hash=self._hash_content(content),
        )

        self._cache[f"{knight_id}:blueprint"] = doc

        # Store in Redis (L1)
        if self._redis_enabled:
            try:
                import redis
                r = redis.Redis(host="localhost", port=6379, decode_responses=True)
                r.setex(
                    f"knight:{knight_id}:blueprint",
                    86400,  # 24h TTL
                    content,
                )
            except Exception:
                pass

        return content

    async def load_agent(self, knight_id: str) -> dict:
        """Load agent.md for a knight (YAML config)."""
        path = KNIGHTS_DIR / knight_id / "agent.md"
        content = await self._read_file(path)

        doc = KnightDocument(
            knight_id=knight_id,
            doc_type="agent",
            content=content,
            loaded_at=time.time(),
            hash=self._hash_content(content),
        )

        self._cache[f"{knight_id}:agent"] = doc

        # Parse YAML if available
        config = {}
        if _YAML and content:
            try:
                config = yaml.safe_load(content) or {}
            except Exception as e:
                print(f"[KB] YAML parse error for {knight_id}/agent.md: {e}", file=sys.stderr)

        # Store in Redis (L1)
        if self._redis_enabled:
            try:
                import redis
                r = redis.Redis(host="localhost", port=6379, decode_responses=True)
                r.setex(
                    f"knight:{knight_id}:agent",
                    86400,
                    json.dumps(config),
                )
            except Exception:
                pass

        return config

    async def load_tasks(self, knight_id: str) -> dict:
        """Load tasks.md (task queue) for a knight."""
        path = KNIGHTS_DIR / knight_id / "tasks.md"
        content = await self._read_file(path)

        doc = KnightDocument(
            knight_id=knight_id,
            doc_type="tasks",
            content=content,
            loaded_at=time.time(),
            hash=self._hash_content(content),
        )

        self._cache[f"{knight_id}:tasks"] = doc

        # Parse as JSON if available
        tasks = {}
        if content:
            try:
                # Try to extract JSON from markdown code block
                import re
                match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if match:
                    tasks = json.loads(match.group(1))
            except Exception:
                # Fallback: return raw content
                tasks = {"raw": content}

        # Store in Redis (L1)
        if self._redis_enabled:
            try:
                import redis
                r = redis.Redis(host="localhost", port=6379, decode_responses=True)
                r.setex(
                    f"knight:{knight_id}:tasks",
                    86400,
                    json.dumps(tasks),
                )
            except Exception:
                pass

        return tasks

    async def load_verification(self, knight_id: str) -> dict:
        """Load verification.md (test results) for a knight."""
        path = KNIGHTS_DIR / knight_id / "verification.md"
        content = await self._read_file(path)

        doc = KnightDocument(
            knight_id=knight_id,
            doc_type="verification",
            content=content,
            loaded_at=time.time(),
            hash=self._hash_content(content),
        )

        self._cache[f"{knight_id}:verification"] = doc

        # Parse as JSON if available
        results = {}
        if content:
            try:
                import re
                match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if match:
                    results = json.loads(match.group(1))
            except Exception:
                results = {"raw": content}

        # Store in Redis (L1)
        if self._redis_enabled:
            try:
                import redis
                r = redis.Redis(host="localhost", port=6379, decode_responses=True)
                r.setex(
                    f"knight:{knight_id}:verification",
                    86400,
                    json.dumps(results),
                )
            except Exception:
                pass

        return results

    async def load_all(self, knight_id: str) -> dict:
        """Load all documents for a knight."""
        blueprint, agent, tasks, verification = await asyncio.gather(
            self.load_blueprint(knight_id),
            self.load_agent(knight_id),
            self.load_tasks(knight_id),
            self.load_verification(knight_id),
        )

        return {
            "knight_id": knight_id,
            "blueprint": blueprint,
            "agent": agent,
            "tasks": tasks,
            "verification": verification,
            "loaded_at": time.time(),
        }

    async def update_tasks(self, knight_id: str, task_data: dict) -> None:
        """Update tasks.md with new task data."""
        path = KNIGHTS_DIR / knight_id / "tasks.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create markdown with JSON
        content = f"""# {knight_id} Task Queue

```json
{json.dumps(task_data, indent=2)}
```

Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""

        try:
            if _AIOFILES:
                async with aiofiles.open(path, "w", encoding="utf-8") as f:
                    await f.write(content)
            else:
                path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"[KB] Error writing tasks.md for {knight_id}: {e}", file=sys.stderr)

        # Update cache and Redis
        doc = KnightDocument(
            knight_id=knight_id,
            doc_type="tasks",
            content=content,
            loaded_at=time.time(),
            hash=self._hash_content(content),
        )
        self._cache[f"{knight_id}:tasks"] = doc

        if self._redis_enabled:
            try:
                import redis
                r = redis.Redis(host="localhost", port=6379, decode_responses=True)
                r.setex(
                    f"knight:{knight_id}:tasks",
                    86400,
                    json.dumps(task_data),
                )
            except Exception:
                pass

    async def update_verification(self, knight_id: str, result_data: dict) -> None:
        """Update verification.md with test/quality results."""
        path = KNIGHTS_DIR / knight_id / "verification.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create markdown with JSON
        content = f"""# {knight_id} Verification Results

```json
{json.dumps(result_data, indent=2)}
```

Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""

        try:
            if _AIOFILES:
                async with aiofiles.open(path, "w", encoding="utf-8") as f:
                    await f.write(content)
            else:
                path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"[KB] Error writing verification.md for {knight_id}: {e}", file=sys.stderr)

        # Update cache and Redis
        doc = KnightDocument(
            knight_id=knight_id,
            doc_type="verification",
            content=content,
            loaded_at=time.time(),
            hash=self._hash_content(content),
        )
        self._cache[f"{knight_id}:verification"] = doc

        if self._redis_enabled:
            try:
                import redis
                r = redis.Redis(host="localhost", port=6379, decode_responses=True)
                r.setex(
                    f"knight:{knight_id}:verification",
                    86400,
                    json.dumps(result_data),
                )
            except Exception:
                pass

    def get_cached(self, knight_id: str, doc_type: str) -> Optional[KnightDocument]:
        """Get cached document without disk I/O."""
        key = f"{knight_id}:{doc_type}"
        return self._cache.get(key)

    async def create_knight_directory(self, knight_id: str) -> Path:
        """Create directory structure for new knight."""
        knight_dir = KNIGHTS_DIR / knight_id
        knight_dir.mkdir(parents=True, exist_ok=True)

        # Create stub files
        (knight_dir / "blueprint.md").write_text(f"# {knight_id} Blueprint\n\n")
        (knight_dir / "agent.md").write_text(f"# {knight_id} Configuration\n\n")
        (knight_dir / "tasks.md").write_text(f"# {knight_id} Tasks\n\n```json\n{{}}\n```\n")
        (knight_dir / "verification.md").write_text(f"# {knight_id} Verification\n\n```json\n{{}}\n```\n")

        return knight_dir


# ── Module-level singleton ────────────────────────────────────────────────

_kb: Optional[KnightKnowledgeBase] = None


def get_knowledgebase() -> KnightKnowledgeBase:
    """Get or create the shared KnightKnowledgeBase instance."""
    global _kb
    if _kb is None:
        _kb = KnightKnowledgeBase()
    return _kb
