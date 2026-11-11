# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Sovereign Preview Drone — local deploy before Swarm pin (v9000.14, P5-T06).
===========================================================================
Pillar 9 (Sovereign Hosting): an artifact is *previewed locally* — deployed to a
disposable sandbox and health-checked — BEFORE it is pinned to the Swarm
(P5-T03). A failing local preview blocks the pin, so only healthy artifacts ever
reach the distributed store.

Pipeline:  deploy(artifact) → health_check → [pass] → swarm pin → bzz addr
                                          → [fail] → blocked (no pin)

Uses crucible_runner for isolated execution and swarm_pin for pinning.

Run as module:
    python -m control_plane.preview_drone --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class PreviewResult:
    healthy: bool
    health_detail: str
    pinned: bool = False
    bzz_addr: Optional[str] = None
    blocked_reason: Optional[str] = None


class PreviewDrone:
    """Local-first deploy gate in front of Swarm distribution."""

    def __init__(self, swarm_root: Optional[Path] = None, timeout_sec: float = 15.0):
        self.swarm_root = swarm_root
        self.timeout_sec = timeout_sec

    def deploy_and_pin(self, artifact_source: str, *,
                       health_expect: str = "PREVIEW_OK") -> PreviewResult:
        """Deploy a Python artifact to an isolated sandbox, health-check it, and
        pin to Swarm only if healthy. A healthy artifact prints `health_expect`.
        """
        from .crucible_runner import CrucibleRunner

        run = CrucibleRunner(timeout_sec=self.timeout_sec).run_python(artifact_source)
        healthy = run.passed and health_expect in (run.stdout or "")
        detail = (f"exit={run.returncode} timeout={run.timed_out} "
                  f"stdout={run.stdout.strip()[:60]!r}")

        if not healthy:
            return PreviewResult(healthy=False, health_detail=detail,
                                 blocked_reason="local preview health check failed — pin blocked")

        # Healthy -> pin the artifact to the Swarm.
        from .swarm_pin import SwarmPinner
        pinner = SwarmPinner(root=self.swarm_root)
        addr = pinner.pin(artifact_source.encode("utf-8"))
        return PreviewResult(healthy=True, health_detail=detail, pinned=True, bzz_addr=addr)


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("PreviewDrone self-test (P5-T06)")
    drone = PreviewDrone()

    # Healthy artifact -> local deploy passes -> pinned to swarm.
    healthy_src = "print('PREVIEW_OK')\n"
    ok = drone.deploy_and_pin(healthy_src)
    check("healthy artifact passes local preview", ok.healthy)
    check("healthy artifact pinned to swarm", ok.pinned and ok.bzz_addr)
    check("bzz addr is 64-hex", ok.bzz_addr and len(ok.bzz_addr) == 64)

    # Unhealthy artifact -> preview fails -> pin BLOCKED (sovereign gate).
    broken_src = "raise SystemExit(1)\n"
    bad = drone.deploy_and_pin(broken_src)
    check("broken artifact fails preview", not bad.healthy)
    check("broken artifact NOT pinned (blocked)", not bad.pinned and bad.bzz_addr is None)
    check("block reason reported", bool(bad.blocked_reason))

    # Wrong health signal (runs fine but no PREVIEW_OK) -> also blocked.
    silent_src = "print('hello')\n"
    silent = drone.deploy_and_pin(silent_src)
    check("missing health signal blocks pin", not silent.healthy and not silent.pinned)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — preview_drone")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print("PreviewDrone — use --test to run the local-deploy-before-pin self-test.")
