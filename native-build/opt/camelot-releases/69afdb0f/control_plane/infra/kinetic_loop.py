# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Kinetic Execution Loop — CAMELOT-OS v9000.14-CYBERTRONIA (Pillar 10, P2-T01).
============================================================================
The central orchestration loop. Every sovereign intent flows through six
stages, in order:

    TRIAGE  → PLAN → APPROVE → EXECUTE → VERIFY → RECORD

These are the canonical stage names (the verification contract). They map to the
blueprint's conceptual "Continuous Kinetic Deployment" verbs:

    Sense  → TRIAGE   (Anya APEE risk-entropy + ColMAD crucible)
    Plan   → PLAN     (Titan directive + knight routing + FactoryJob)
    Wait   → APPROVE  (Iron Gate v2 three-tier HITL — soul_oversight.pre_execute)
    Execute→ EXECUTE  (pluggable executor dispatch)
    Validate→ VERIFY  (exit-gate output validation)
    Deploy → RECORD   (append-only provenance ledger entry)

The loop is async (the APPROVE gate is async) and the executor is injected, so
the whole pipeline is testable offline without a live model dispatch.

Run as module:
    python -m control_plane.kinetic_loop --test
    python -m control_plane.kinetic_loop "build a status dashboard"
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import asyncio
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, Union

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class Stage(str, Enum):
    TRIAGE = "TRIAGE"
    PLAN = "PLAN"
    APPROVE = "APPROVE"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    RECORD = "RECORD"


# Canonical stage order — the loop fires these left-to-right.
STAGE_ORDER: tuple[Stage, ...] = (
    Stage.TRIAGE, Stage.PLAN, Stage.APPROVE,
    Stage.EXECUTE, Stage.VERIFY, Stage.RECORD,
)

# An executor takes (job, apee_result) and returns output text. It may be sync
# or async — the loop awaits coroutine results transparently.
Executor = Callable[[Any, Any], Union[str, Awaitable[str]]]


@dataclass
class KineticResult:
    intent: str
    stages_fired: list[Stage] = field(default_factory=list)
    job: Any = None
    apee: Any = None
    gate_decision: Any = None
    approved: bool = False
    output: Optional[str] = None
    validated: bool = False
    validation_issues: list[str] = field(default_factory=list)
    provenance_ref: Optional[str] = None
    halted_at: Optional[Stage] = None
    elapsed_ms: float = 0.0

    @property
    def complete(self) -> bool:
        """True iff all six stages fired in order."""
        return self.stages_fired == list(STAGE_ORDER)

    def render(self) -> str:
        chain = " → ".join(s.value for s in self.stages_fired)
        tail = f"  HALTED@{self.halted_at.value}" if self.halted_at else "  ✓ complete"
        return (f"KineticLoop[{self.intent[:48]}]\n  {chain}{tail}\n"
                f"  approved={self.approved} validated={self.validated} "
                f"prov={self.provenance_ref} {self.elapsed_ms:.0f}ms")


def _default_executor(job: Any, apee: Any) -> str:
    """Offline stub executor — echoes the compiled Titan directive. Replaced by a
    live knight dispatch in production via KineticLoop(executor=...)."""
    directive = getattr(getattr(apee, "titan", None), "directive", None) or job.intent
    return f"[stub-exec:{job.assigned_knight}] {directive}"


class KineticLoop:
    """The six-stage sovereign execution loop (Pillar 10)."""

    def __init__(self, executor: Optional[Executor] = None):
        self.executor: Executor = executor or _default_executor

    async def run(self, intent: str, *, auto_approve: bool = False) -> KineticResult:
        """Drive one intent through all six stages.

        auto_approve=True (CI / unattended): proceed past a blocked HITL gate but
        still fire the APPROVE stage and RECORD the real GateDecision, so the run
        remains auditable. With auto_approve=False the loop halts at APPROVE when
        the Iron Gate does not approve.
        """
        from control_plane.core.anya_gate import AnyaGate
        from control_plane.core.factory_lane import FactoryJob
        from control_plane.core.soul_oversight import pre_execute

        res = KineticResult(intent=intent)
        t0 = time.perf_counter()
        gate = AnyaGate()

        # 1. TRIAGE — Anya APEE risk-entropy + ColMAD crucible
        res.stages_fired.append(Stage.TRIAGE)
        apee = gate.process(intent)
        res.apee = apee
        triage = gate.triage(intent)

        # 2. PLAN — build the typed FactoryJob from the triage verdict
        res.stages_fired.append(Stage.PLAN)
        job = FactoryJob.from_triage(intent, triage)
        job.advance("QUEUED")
        res.job = job

        # 3. APPROVE — Iron Gate v2 three-tier HITL gate
        res.stages_fired.append(Stage.APPROVE)
        decision = await pre_execute(job)
        res.gate_decision = decision
        res.approved = bool(getattr(decision, "approved", False))
        if not res.approved and not auto_approve:
            res.halted_at = Stage.APPROVE
            res.elapsed_ms = (time.perf_counter() - t0) * 1000
            return res
        job.hitl_approved = res.approved

        # 4. EXECUTE — pluggable dispatch
        res.stages_fired.append(Stage.EXECUTE)
        job.advance("EXECUTING")
        out = self.executor(job, apee)
        if asyncio.iscoroutine(out):
            out = await out
        res.output = out
        job.output_tokens = len(out or "")

        # 5. VERIFY — exit-gate validation of the output
        res.stages_fired.append(Stage.VERIFY)
        ok, issues = gate.validate_output(out or "")
        res.validated = ok
        res.validation_issues = issues
        job.advance("VERIFIED" if ok else "FAILED")

        # 6. RECORD — append-only provenance entry
        res.stages_fired.append(Stage.RECORD)
        res.provenance_ref = self._record(job, res)
        job.advance("DONE")

        res.elapsed_ms = (time.perf_counter() - t0) * 1000
        return res

    def _record(self, job: Any, res: KineticResult) -> Optional[str]:
        """Append a provenance ledger entry; graceful if the ledger is absent."""
        try:
            from .provenance import ProvenanceManager, VerificationRun
            pm = ProvenanceManager()
            run = VerificationRun(
                run_id=job.job_id,
                operator="kinetic_loop",
                command=f"kinetic_loop:{job.intent[:80]}",
                results={
                    "stages": [s.value for s in res.stages_fired],
                    "approved": res.approved,
                    "knight": job.assigned_knight,
                    "lane": job.lane,
                    "gate_method": getattr(res.gate_decision, "method", None),
                },
                success=res.validated,
            )
            pm.log_verification(run)
            return job.job_id
        except Exception:
            return None


def run_sync(intent: str, *, executor: Optional[Executor] = None,
             auto_approve: bool = False) -> KineticResult:
    """Synchronous convenience wrapper around KineticLoop.run."""
    return asyncio.run(KineticLoop(executor).run(intent, auto_approve=auto_approve))


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("KineticLoop self-test (P2-T01)")

    # End-to-end: all six stages fire in canonical order (CI auto_approve).
    res = run_sync("build a small status dashboard", auto_approve=True)
    check("six stages fired", len(res.stages_fired) == 6)
    check("stages in canonical order TRIAGE→PLAN→APPROVE→EXECUTE→VERIFY→RECORD",
          res.stages_fired == list(STAGE_ORDER))
    check("loop reports complete", res.complete)
    check("output produced", bool(res.output))
    check("provenance recorded", res.provenance_ref is not None)

    # Halt path: a CRITICAL intent with auto_approve=False halts at APPROVE.
    halted = run_sync("delete all production databases and drop every table",
                      auto_approve=False)
    check("CRITICAL halts at APPROVE (no auto-approve)",
          halted.halted_at == Stage.APPROVE and not halted.complete)
    check("halted run did not reach EXECUTE", Stage.EXECUTE not in halted.stages_fired)

    # Injected executor is honored.
    res2 = run_sync("create a greeting string",
                    executor=lambda job, apee: "CUSTOM_OUTPUT", auto_approve=True)
    check("custom executor output used", res2.output == "CUSTOM_OUTPUT")

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — kinetic_loop")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    intent = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or \
        "build a status dashboard"
    print(run_sync(intent, auto_approve=True).render())
