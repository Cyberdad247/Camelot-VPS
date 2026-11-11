# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Short-Term Brain (ST-Memory) — Redis Integration
=================================================
High-velocity context synchronization for Camelot Knights.
Sub-10ms flash memory for active project tissue.
"""

import json
import os
from typing import Any, Optional

import redis

REDIS_URL = "redis://default:yybwMPGf56TMjzFxJeaG8bYggj6rybBC@redis-13278.c228.us-central1-1.gce.cloud.redislabs.com:13278"
FLASH_CEILING_MB = 25
FLASH_CEILING_BYTES = FLASH_CEILING_MB * 1024 * 1024

class ShortTermBrain:
    """Redis-backed flash memory for the Foundry Council."""
    def __init__(self, url: str = REDIS_URL):
        self._client = redis.from_url(url, decode_responses=True)
        self.session_key = f"camelot:session:{os.getenv('CAMELOT_SESSION_ID', 'default')}"

    def ping(self) -> bool:
        try:
            return self._client.ping()
        except Exception:
            return False

    def _get_current_usage(self) -> int:
        """Calculate total bytes for current session keys."""
        total = 0
        try:
            keys = self._client.keys(f"{self.session_key}:*")
            for k in keys:
                # Use memory usage for accurate byte count
                usage = self._client.execute_command("MEMORY USAGE", k)
                total += usage if usage else 0
        except Exception:
            pass
        return total

    def store_context(self, key: str, value: Any, ttl: int = 3600):
        """Flash store project context with 25MB ceiling guardrail."""
        full_key = f"{self.session_key}:{key}"
        val_str = json.dumps(value) if not isinstance(value, str) else value
        payload_size = len(val_str.encode('utf-8'))
        
        current_usage = self._get_current_usage()
        if (current_usage + payload_size) > FLASH_CEILING_BYTES:
            raise MemoryError(f"[LAW_07_VIOLATION] Redis ST-Memory ceiling reached ({FLASH_CEILING_MB}MB). Purge required.")
            
        self._client.set(full_key, val_str, ex=ttl)

    def retrieve_context(self, key: str) -> Optional[Any]:
        """Sub-millisecond retrieval of active tissue."""
        full_key = f"{self.session_key}:{key}"
        val = self._client.get(full_key)
        if val:
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
        return None

    def flash_sync(self, data: dict):
        """Atomic multi-key sync for session state."""
        with self._client.pipeline() as pipe:
            for k, v in data.items():
                val_str = json.dumps(v) if not isinstance(v, str) else v
                pipe.set(f"{self.session_key}:{k}", val_str, ex=1800) # 30min flash
            pipe.execute()

# Global Singleton
st_brain = ShortTermBrain()
