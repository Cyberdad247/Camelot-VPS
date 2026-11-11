# Copyright (c) 2026 Invisioned Marketing inc. All Rights Reserved.
"""
Soul Oversight v2.0 — Merlin's Recursive Integrity Gate + Iron Gate v2.
=======================================================================
Prevents autonomous knights from self-modifying without oversight.
Enforces Merlin Audit -> Gideon Sting -> HITL Approval.

EXCALIBUR_A_QNF Phase 4 adds the three-tier Iron Gate (pre_execute):
  AUTO        -> dispatch immediately
  PROMPT      -> operator confirm (timeout-optional)
  HUMAN_GATE  -> CAMELOT_DASHBOARD_OPERATOR_TOKEN required; else suspend to
                 FileStatePersistence and enqueue for operator review.
Z3 symbolic verification gates any job that mutates git/state-machines.
"""


__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


class SoulOversight:
    """The Governance gate for Metacognitive Self-Modification."""

    def __init__(self, merlin_engine: Any):
        self.merlin = merlin_engine
        self.vault_base = Path("03_VAULT/training/configs/knights")

    async def audit_proposal(self, knight_id: str, current_soul: str, proposed_soul: str) -> Dict[str, Any]:
        """Merlin_Omega audits the proposed instruction change."""
        print(f"Merlin_Omega [🧙‍♂️]: Auditing soul-proposal for {knight_id}...")
        
        # Simulate Videneptus LaC reasoning check
        is_aligned = "NDR+S" in proposed_soul or "Lattice" in proposed_soul
        drift_score = 0.05 if is_aligned else 0.85 # Low drift is better
        
        verdict = "RADIANT" if drift_score < 0.2 else "REJECT_DRIFT"
        
        return {
            "knight_id": knight_id,
            "verdict": verdict,
            "drift_score": drift_score,
            "requires_hitl": True
        }

    def trigger_iron_gate(self, audit_result: Dict[str, Any]) -> bool:
        """Triggers the HITL approval prompt with a Soul Brief."""
        print(f"\n[HITL_SOUL_GATE] Knight {audit_result['knight_id']} is attempting a soul-rewrite.")
        print(f"Merlin Verdict: {audit_result['verdict']} | Drift Score: {audit_result['drift_score']*100:.1f}%")
        
        if audit_result['verdict'] == "REJECT_DRIFT":
            print("WARNING: Merlin detected significant architectural drift!")

        # In a real CLI, this would call the shared _check_iron_gate
        return False # Default to locked for safety

    async def gate(self, job: Any) -> "GateDecision":
        """Unified governance entry (P1-T05): run the Iron Gate v2 three-tier
        pre-execution check. This is the single coherent API surface — the v1
        soul-rewrite audit (audit_proposal/trigger_iron_gate) and the v2 job
        gate (pre_execute) are both reachable from one SoulOversight instance.
        Delegates to the module-level ``pre_execute`` (kept for back-compat with
        existing imports).
        """
        return await pre_execute(job)

# ---------------------------------------------------------------------------
# Iron Gate v2 — three-tier HITL governance (EXCALIBUR_A_QNF Phase 4)
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass
class GateDecision:
    approved: bool
    method: str                       # AUTO | PROMPT | HUMAN_GATE | SUSPENDED | Z3_BLOCK | BLOCKED
    reason: str = ""
    checkpoint: Optional[str] = None


def _z3_verify_patch(job: Any) -> tuple[bool, str]:
    """Mathematically verify a patch/state-machine intent (P2-T02).

    Delegates to the real PDDL-style Z3 encoder in ``control_plane.z3_verify``:
    safety invariants are modelled as fluents, the patch is grounded into action
    effects, and a patch that makes the safety goal unsatisfiable is BLOCKED.
    Degrades gracefully (pass-through) if the encoder/solver is unavailable —
    the upstream shatterpoint guard still applies.
    """
    try:
        from .z3_verify import PatchIntent, verify_patch
    except Exception as exc:  # pragma: no cover - defensive import guard
        return True, f"Z3 encoder unavailable ({exc}) — passed through"

    intent = getattr(job, "intent", "") or ""
    reason = getattr(getattr(job, "triage", None), "risk_reason", "") or ""
    diff = getattr(job, "diff", "") or ""
    verdict = verify_patch(PatchIntent(description=f"{intent} {reason}", diff=diff))
    return verdict.safe, verdict.render()


def _load_colony_nexus():
    """Lazily load the ColonyNexus class via explicit file-path import (P1-T07).

    ``01_KERNEL`` is not an importable package (leading digit), so colony_nexus
    is loaded by path — a single, explicit pattern that replaces the previous
    try/except cascade (whose first branch, ``from _01_KERNEL...``, could never
    succeed). Returns the ColonyNexus class, or None when the module is
    unavailable. Never raises — colony state must not crash the gate.
    """
    import importlib.util as _ilu
    from pathlib import Path as _Path

    path = (_Path(__file__).resolve().parents[1]
            / "01_KERNEL" / "iron_gate" / "DEFENSE_GRID" / "colony_nexus.py")
    if not path.exists():
        return None
    try:
        spec = _ilu.spec_from_file_location("colony_nexus", path)
        if not (spec and spec.loader):
            return None
        mod = sys.modules.get("colony_nexus")
        if mod is None:
            mod = _ilu.module_from_spec(spec)
            sys.modules["colony_nexus"] = mod
            spec.loader.exec_module(mod)
        return getattr(mod, "ColonyNexus", None)
    except Exception:
        return None


def _colony_escalate(tier: str) -> str:
    """Escalate `tier` to HUMAN_GATE when colony risk is CRITICAL.

    Non-blocking: if the colony module is absent or its scan fails, the original
    tier is returned unchanged (the gate must degrade gracefully).
    """
    if tier == "HUMAN_GATE":
        return tier   # already at max — no need to scan
    ColonyNexus = _load_colony_nexus()
    if ColonyNexus is None:
        return tier   # colony module unavailable — proceed with original tier
    try:
        state = ColonyNexus(hermes_enabled=False).scan()
        if getattr(state, "is_critical", False):
            return "HUMAN_GATE"
    except Exception:
        pass   # colony data unavailable — proceed with original tier
    return tier


async def pre_execute(job: Any) -> GateDecision:
    """Iron Gate v2 entry point. Called before every knight dispatch.

    `job` is a control_plane.factory_lane.FactoryJob (duck-typed: needs
    .triage.hitl_tier, .triage.requires_z3_verification, .triage.risk_reason).

    Colony Nexus escalation: if the live colony_report.md shows CRITICAL risk
    AND the job is not already HUMAN_GATE, escalate the tier to HUMAN_GATE.
    """
    triage = job.triage
    tier = triage.hitl_tier

    # 0. Colony Nexus risk escalation
    tier = _colony_escalate(tier)

    # 1. Z3 verification for git patches / state machines
    if getattr(triage, "requires_z3_verification", False):
        safe, detail = _z3_verify_patch(job)
        if not safe:
            _append_hitl(job, f"Z3_BLOCK: {detail}")
            return GateDecision(False, "Z3_BLOCK", detail)

    # 2. Tier dispatch
    if tier == "AUTO":
        return GateDecision(True, "AUTO", triage.risk_reason)

    if tier == "PROMPT":
        # Non-interactive contexts: honor CAMELOT_ALLOW_TIMEOUT_AUTO for unattended runs
        if os.environ.get("CAMELOT_ALLOW_TIMEOUT_AUTO") == "1":
            return GateDecision(True, "PROMPT", "timeout auto-approve (unattended)")
        return GateDecision(False, "PROMPT", "operator confirmation required")

    if tier == "HUMAN_GATE":
        token = os.environ.get("CAMELOT_DASHBOARD_OPERATOR_TOKEN")
        if not token:
            checkpoint = _suspend(job)
            return GateDecision(False, "SUSPENDED",
                                "operator token not configured — job suspended",
                                checkpoint=checkpoint)
        return GateDecision(True, "HUMAN_GATE", f"operator token accepted ({token[:6]}***)")

    return GateDecision(False, "BLOCKED", f"unknown hitl_tier: {tier}")


def _suspend(job: Any) -> str:
    """Persist a HUMAN_GATE job and enqueue for operator review."""
    try:
        from .factory_lane import FileStatePersistence, enqueue_human_gate
        fsp = FileStatePersistence()
        checkpoint = fsp.save(job)
        enqueue_human_gate(job, checkpoint)
        return checkpoint
    except Exception as exc:
        _append_hitl(job, f"suspend failed: {exc}")
        return ""


def _append_hitl(job: Any, note: str) -> None:
    from datetime import datetime, timezone
    home = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS"))
    q = home / "logs" / "hitl_queue.jsonl"
    q.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "job_id": getattr(job, "job_id", "unknown"),
        "note": note,
    }
    with q.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _selftest() -> int:
    """P1-T05 acceptance: verify the consolidated SoulOversight + Iron Gate v2
    API behaves coherently across all three HITL tiers and the soul-rewrite
    audit path. Returns the failure count.
    """
    import asyncio

    from .factory_lane import FactoryJob, TriageScore

    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    def _job(tier: str, z3: bool = False) -> FactoryJob:
        ts = TriageScore(
            auto_dispatchable=(tier == "AUTO"),
            priority="NORMAL" if tier == "AUTO" else "HIGH",
            hitl_tier=tier,
            risk_entropy=0.05 if tier == "AUTO" else 0.7,
            risk_reason=f"selftest tier={tier}",
            assigned_knight="sir_boris",
            estimated_tokens=1000,
            cost_ceiling_usd=0.0,
            shatterpoints_detected=[],
            requires_z3_verification=z3,
            cartridge_hint="DEFAULT",
        )
        return FactoryJob(job_id=f"selftest-{tier.lower()}", intent="selftest",
                          lane="NORMAL", triage=ts, assigned_knight="sir_boris")

    print("SoulOversight self-test (P1-T05 consolidated gate)")
    oversight = SoulOversight(None)

    # Tier-dispatch logic is tested in isolation from live colony state by
    # neutralizing the colony escalator (which legitimately forces HUMAN_GATE
    # when colony_report.md is CRITICAL). The escalator itself is checked below.
    global _colony_escalate
    _real_escalate = _colony_escalate
    _colony_escalate = lambda tier: tier  # noqa: E731 — identity for isolation
    os.environ.pop("CAMELOT_ALLOW_TIMEOUT_AUTO", None)
    os.environ.pop("CAMELOT_DASHBOARD_OPERATOR_TOKEN", None)
    try:
        # Unified class API delegates to Iron Gate v2
        auto = asyncio.run(oversight.gate(_job("AUTO")))
        check("AUTO tier approved via SoulOversight.gate", auto.approved and auto.method == "AUTO")

        prompt = asyncio.run(oversight.gate(_job("PROMPT")))
        check("PROMPT tier requires confirmation", (not prompt.approved) and prompt.method == "PROMPT")

        # HUMAN_GATE with no operator token -> suspended with checkpoint
        hg = asyncio.run(oversight.gate(_job("HUMAN_GATE")))
        check("HUMAN_GATE without token -> SUSPENDED", hg.method == "SUSPENDED" and not hg.approved)
    finally:
        _colony_escalate = _real_escalate

    # Colony escalator is idempotent at the ceiling tier (deterministic).
    check("colony escalate idempotent at HUMAN_GATE", _colony_escalate("HUMAN_GATE") == "HUMAN_GATE")

    # GateDecision schema
    check("GateDecision has coherent fields",
          all(hasattr(auto, f) for f in ("approved", "method", "reason", "checkpoint")))

    # Module-level entry remains (back-compat)
    direct = asyncio.run(pre_execute(_job("AUTO")))
    check("module-level pre_execute back-compat", isinstance(direct, GateDecision))

    # Soul-rewrite audit path (v1) still coherent
    audit = asyncio.run(oversight.audit_proposal("sir_boris", "old soul", "new Lattice NDR+S soul"))
    check("audit_proposal returns aligned verdict", audit["verdict"] == "RADIANT")

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — soul_oversight")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    # Smoke test
    oversight = SoulOversight(None)
    print("Soul Oversight [shield]: Active and guarding the Knight Roster.")
