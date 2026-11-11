# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Empire Drone Mesh — discovery + registration protocol (v9000.14, P4-T03).
=========================================================================
Drones (edge workers) announce themselves to the mesh and auto-register with the
Omni-Router. The registry tracks liveness via heartbeats, deduplicates by node
id, and evicts stale drones. Transport-agnostic: the same protocol runs over the
tsnet mesh (P4-T01, Linux) or a local loopback for testing.

A registration is a signed-ish announce frame:
    {node_id, role, endpoint, capabilities[], joined_at, last_seen}

Run as module:
    python -m control_plane.empire_drone --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import sys
import time
from dataclasses import dataclass, field
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_TTL_SEC = 30.0


@dataclass
class DroneAnnounce:
    node_id: str
    role: str                       # e.g. "edge", "preview", "wasm", "voice"
    endpoint: str                   # tsnet/loopback address
    capabilities: list[str] = field(default_factory=list)


@dataclass
class DroneRecord:
    node_id: str
    role: str
    endpoint: str
    capabilities: list[str]
    joined_at: float
    last_seen: float

    def is_stale(self, now: float, ttl: float) -> bool:
        return (now - self.last_seen) > ttl


class EmpireMesh:
    """The Omni-Router's view of the drone fleet."""

    def __init__(self, ttl_sec: float = DEFAULT_TTL_SEC):
        self.ttl_sec = ttl_sec
        self._drones: dict[str, DroneRecord] = {}
        self._join_log: list[str] = []

    def register(self, ann: DroneAnnounce, now: Optional[float] = None) -> DroneRecord:
        """Auto-register (or refresh) a drone on mesh join. Idempotent by node_id:
        a re-announce refreshes last_seen without duplicating the record."""
        t = now if now is not None else time.time()
        existing = self._drones.get(ann.node_id)
        if existing is None:
            rec = DroneRecord(ann.node_id, ann.role, ann.endpoint,
                              list(ann.capabilities), joined_at=t, last_seen=t)
            self._drones[ann.node_id] = rec
            self._join_log.append(ann.node_id)
            return rec
        existing.last_seen = t
        existing.endpoint = ann.endpoint
        existing.capabilities = list(ann.capabilities)
        return existing

    def heartbeat(self, node_id: str, now: Optional[float] = None) -> bool:
        rec = self._drones.get(node_id)
        if rec is None:
            return False
        rec.last_seen = now if now is not None else time.time()
        return True

    def reap(self, now: Optional[float] = None) -> list[str]:
        """Evict stale drones (no heartbeat within TTL). Returns evicted ids."""
        t = now if now is not None else time.time()
        stale = [nid for nid, r in self._drones.items() if r.is_stale(t, self.ttl_sec)]
        for nid in stale:
            del self._drones[nid]
        return stale

    def roster(self) -> list[DroneRecord]:
        return list(self._drones.values())

    def find_by_capability(self, capability: str) -> list[DroneRecord]:
        return [r for r in self._drones.values() if capability in r.capabilities]

    def __len__(self) -> int:
        return len(self._drones)


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("EmpireMesh self-test (P4-T03)")
    mesh = EmpireMesh(ttl_sec=10.0)
    t0 = 1000.0

    # New drone auto-registers on join.
    rec = mesh.register(DroneAnnounce("drone-a", "wasm", "100.64.0.2:9000",
                                      ["wasm32-wasi", "edge"]), now=t0)
    check("new drone auto-registers", len(mesh) == 1 and rec.node_id == "drone-a")
    check("roster reflects the join", mesh.roster()[0].node_id == "drone-a")

    # Re-announce is idempotent (no duplicate), refreshes last_seen.
    mesh.register(DroneAnnounce("drone-a", "wasm", "100.64.0.2:9000", ["wasm32-wasi"]),
                  now=t0 + 1)
    check("re-announce does not duplicate", len(mesh) == 1)

    # Second drone joins; capability lookup works.
    mesh.register(DroneAnnounce("drone-b", "voice", "100.64.0.3:9001", ["voice"]), now=t0 + 2)
    check("second drone registered", len(mesh) == 2)
    check("capability lookup finds voice drone",
          [r.node_id for r in mesh.find_by_capability("voice")] == ["drone-b"])

    # Heartbeat keeps a drone alive; missing heartbeat evicts after TTL.
    mesh.heartbeat("drone-a", now=t0 + 9)
    evicted = mesh.reap(now=t0 + 15)   # drone-b last_seen=t0+2 -> stale (>10s); drone-a fresh
    check("stale drone evicted", evicted == ["drone-b"] and len(mesh) == 1)
    check("fresh drone retained", mesh.roster()[0].node_id == "drone-a")

    check("heartbeat on unknown node -> False", mesh.heartbeat("ghost") is False)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — empire_drone")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print("EmpireMesh — use --test to run the discovery/registration self-test.")
