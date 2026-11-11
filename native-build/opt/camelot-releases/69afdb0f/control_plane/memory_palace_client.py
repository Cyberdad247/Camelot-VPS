# SPDX-License-Identifier: MIT

"""memory_palace_client.py — Python shim for the Rust memory_palace binary.
Replaces local_store.py call sites with zero-overhead Rust vector ops.
Usage:
    from control_plane.memory_palace_client import MemoryPalace
    mp = MemoryPalace()
    mp.upsert("knight_merlin", [0.1, 0.2, ...])        # store vector
    results = mp.query([0.1, 0.2, ...], top_k=5)        # cosine search
"""
from __future__ import annotations

import json
import logging
import os
import struct
import subprocess
from pathlib import Path
from typing import Any

LOG          = logging.getLogger("memory_palace_client")
CAMELOT_ROOT = Path(__file__).resolve().parent.parent

# Prefer env-override so the Cybertronia supervisor can pin a specific binary.
_DEFAULT_BIN = CAMELOT_ROOT / "04_KINETIC" / "memory_palace" / "target" / "release" / "memory_palace.exe"
BINARY       = Path(os.getenv("CAMELOT_MEMORY_PALACE_BIN", str(_DEFAULT_BIN)))


def _run(args: list[str], stdin_data: bytes | None = None) -> dict[str, Any]:
    """Invoke the Rust binary with JSON command protocol."""
    if not BINARY.exists():
        raise FileNotFoundError(
            f"memory_palace binary not found at {BINARY}. "
            "Run: cargo build --release -p memory_palace"
        )
    result = subprocess.run(
        [str(BINARY)] + args,
        input=stdin_data,
        capture_output=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"memory_palace error: {result.stderr.decode(errors='replace')}")
    return json.loads(result.stdout)


class MemoryPalace:
    """High-level Python facade over the Rust memory_palace binary.

    The binary accepts three sub-commands:
        upsert  <key> <dim>   — reads <dim> f32 floats from stdin as little-endian bytes
        query   <dim> <top_k> — reads query vector from stdin, returns JSON result list
        delete  <key>         — remove a vector by key
    """

    def upsert(self, key: str, vector: list[float]) -> None:
        """Store or update a named float32 vector."""
        dim   = len(vector)
        raw   = struct.pack(f"<{dim}f", *vector)
        resp  = _run(["upsert", key, str(dim)], stdin_data=raw)
        if resp.get("status") != "ok":
            raise RuntimeError(f"upsert failed: {resp}")
        LOG.debug("upsert key=%s dim=%d", key, dim)

    def query(self, vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Cosine similarity search. Returns list of {key, score} dicts."""
        dim  = len(vector)
        raw  = struct.pack(f"<{dim}f", *vector)
        resp = _run(["query", str(dim), str(top_k)], stdin_data=raw)
        return resp.get("results", [])

    def delete(self, key: str) -> None:
        """Remove a vector by key."""
        resp = _run(["delete", key])
        if resp.get("status") != "ok":
            raise RuntimeError(f"delete failed: {resp}")
        LOG.debug("delete key=%s", key)

    # ── Backward-compat shims for legacy local_store.py call sites ────────────
    def store_vector(self, key: str, vector: list[float]) -> None:
        """Alias for upsert — matches legacy local_store.store_vector signature."""
        self.upsert(key, vector)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Alias for query — matches legacy local_store.search signature."""
        return self.query(query_vector, top_k=top_k)


# Module-level singleton — import once, reuse everywhere.
_instance: MemoryPalace | None = None


def get_memory_palace() -> MemoryPalace:
    global _instance
    if _instance is None:
        _instance = MemoryPalace()
    return _instance
