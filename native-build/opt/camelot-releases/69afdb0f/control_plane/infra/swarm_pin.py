# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Swarm Pinning — content-addressed artifact distribution (v9000.14, P5-T03).
===========================================================================
Ethereum Swarm (BZZ) stores content by hash. This module implements the
content-addressing contract — pin(content) → bzz hash, fetch(hash) → content —
against a pluggable backend. The default backend is a local content-addressed
store (disk), used for offline development and CI; a live Swarm/Bee node can be
dropped in by implementing the same ``pin``/``fetch`` interface.

The address is a BZZ-style hash: keccak-256 if `eth-hash`/`pysha3` is available,
else SHA3-256 (both are 32-byte content addresses). Pinning is idempotent and
fetch verifies the content matches its address (tamper-evident).

Run as module:
    python -m control_plane.swarm_pin --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Protocol

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def bzz_hash(content: bytes) -> str:
    """Compute a BZZ-style 32-byte content address (hex).

    Prefers keccak-256 (Ethereum/Swarm native); falls back to SHA3-256 if a
    keccak implementation is unavailable. Both yield a stable 64-hex address.
    """
    try:
        # eth-hash / pysha3 expose keccak via hashlib.new('keccak_256')
        h = hashlib.new("keccak_256")
        h.update(content)
        return h.hexdigest()
    except (ValueError, TypeError):
        return hashlib.sha3_256(content).hexdigest()


class SwarmBackend(Protocol):
    def put(self, addr: str, content: bytes) -> None: ...
    def get(self, addr: str) -> Optional[bytes]: ...
    def has(self, addr: str) -> bool: ...


class LocalCASBackend:
    """Local content-addressed store (offline/CI default)."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, addr: str) -> Path:
        return self.root / addr[:2] / addr

    def put(self, addr: str, content: bytes) -> None:
        p = self._path(addr)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def get(self, addr: str) -> Optional[bytes]:
        p = self._path(addr)
        return p.read_bytes() if p.exists() else None

    def has(self, addr: str) -> bool:
        return self._path(addr).exists()


class SwarmPinner:
    """Pin and retrieve artifacts by content address."""

    def __init__(self, backend: Optional[SwarmBackend] = None, root: Optional[Path] = None):
        if backend is None:
            backend = LocalCASBackend(root or Path(tempfile.mkdtemp(prefix="swarm_")))
        self.backend = backend

    def pin(self, content: bytes) -> str:
        """Pin content; returns its BZZ address. Idempotent."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        addr = bzz_hash(content)
        if not self.backend.has(addr):
            self.backend.put(addr, content)
        return addr

    def fetch(self, addr: str) -> Optional[bytes]:
        """Retrieve by address; verifies content integrity (tamper-evident)."""
        content = self.backend.get(addr)
        if content is None:
            return None
        if bzz_hash(content) != addr:
            raise ValueError(f"swarm integrity violation: {addr} content hash mismatch")
        return content

    def is_pinned(self, addr: str) -> bool:
        return self.backend.has(addr)


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("SwarmPinner self-test (P5-T03)")
    tmp = Path(tempfile.mkdtemp(prefix="swarm_test_"))
    try:
        pinner = SwarmPinner(root=tmp)
        content = b"CAMELOT-OS v9000.14 WASM pill artifact bytes"

        addr = pinner.pin(content)
        check("pin returns a 64-hex BZZ address", len(addr) == 64 and all(c in "0123456789abcdef" for c in addr))
        check("content is pinned", pinner.is_pinned(addr))

        # Retrieve by hash; content matches.
        got = pinner.fetch(addr)
        check("fetch by hash round-trips content", got == content)

        # Pinning is idempotent (same address).
        addr2 = pinner.pin(content)
        check("pin is idempotent (stable address)", addr2 == addr)

        # Different content -> different address.
        addr3 = pinner.pin(b"different artifact")
        check("distinct content -> distinct address", addr3 != addr)

        # Unknown address -> None.
        check("fetch unknown address -> None", pinner.fetch("00" * 32) is None)

        # Tamper detection: corrupt the stored blob, fetch must raise.
        bad = "ab" * 32
        pinner.backend.put(bad, b"not matching the address")
        try:
            pinner.fetch(bad)
            check("tampered blob raises", False)
        except ValueError:
            check("tampered blob raises integrity error", True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — swarm_pin")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print("SwarmPinner — use --test to run the pin/fetch round-trip self-test.")
