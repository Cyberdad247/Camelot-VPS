# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Obsidian Pillars — 11-Pillar enforcement layer (v9000.14, Pillar mesh, P2-T03).
==============================================================================
Each of the 11 Pillars of the Obsidian Forge is a validator over a
``PillarContext`` carrying the signals produced by the Kinetic Execution Loop
and supporting subsystems. ``ObsidianPillars.enforce(ctx)`` returns a verdict per
pillar; ``all_compliant`` is the gate signal.

The 11 Pillars:
    1  Spec-Driven Genesis        — every intent is triaged + planned before exec
    2  Contextual Hydration       — World Tree context is hydrated (firnflow)
    3  Immutable Provenance       — an append-only ledger ref was recorded
    4  Adversarial Crucible       — CRITICAL intents face the ColMAD debate
    5  Zero-Trust Access          — the actor holds an authorized role
    6  Kinetic Resilience         — the assigned knight has a typed fallback
    7  Semantic Storage           — context compression ratio is healthy
    8  Sentinel Shield            — no secrets exposed in the artifact
    9  Sovereign Hosting          — no hard external-only dependency
    10 Continuous Kinetic Deploy  — the six-stage loop completed in order
    11 Omni-Observability         — a live metrics snapshot is available

Run as module:
    python -m control_plane.obsidian_pillars --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import sys
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class Pillar(IntEnum):
    SPEC_DRIVEN_GENESIS = 1
    CONTEXTUAL_HYDRATION = 2
    IMMUTABLE_PROVENANCE = 3
    ADVERSARIAL_CRUCIBLE = 4
    ZERO_TRUST_ACCESS = 5
    KINETIC_RESILIENCE = 6
    SEMANTIC_STORAGE = 7
    SENTINEL_SHIELD = 8
    SOVEREIGN_HOSTING = 9
    CONTINUOUS_KINETIC_DEPLOY = 10
    OMNI_OBSERVABILITY = 11


@dataclass
class PillarContext:
    """Signals a kinetic run exposes for pillar enforcement. Fields default to a
    compliant baseline so tests can flip one signal to exercise a negative case.
    """
    stages_fired: list[str] = field(default_factory=lambda: [
        "TRIAGE", "PLAN", "APPROVE", "EXECUTE", "VERIFY", "RECORD"])
    is_critical: bool = False
    colmad_ran: bool = False
    context_hydrated: bool = True
    provenance_ref: Optional[str] = "rec-0001"
    actor_role: Optional[str] = "operator"
    knight_has_fallback: bool = True
    compression_ratio: float = 4.0          # N:1
    secrets_exposed: int = 0
    external_only_dependency: bool = False
    metrics_available: bool = True
    authorized_roles: tuple[str, ...] = ("operator", "architect", "sentinel")


@dataclass
class PillarVerdict:
    pillar: Pillar
    compliant: bool
    detail: str


# ── individual pillar validators ─────────────────────────────────────────────

def _p1(ctx: PillarContext) -> PillarVerdict:
    ok = "TRIAGE" in ctx.stages_fired and "PLAN" in ctx.stages_fired
    return PillarVerdict(Pillar.SPEC_DRIVEN_GENESIS, ok,
                         "intent triaged + planned" if ok else "no spec/plan before action")


def _p2(ctx: PillarContext) -> PillarVerdict:
    return PillarVerdict(Pillar.CONTEXTUAL_HYDRATION, ctx.context_hydrated,
                         "World Tree hydrated" if ctx.context_hydrated else "context not hydrated")


def _p3(ctx: PillarContext) -> PillarVerdict:
    ok = bool(ctx.provenance_ref)
    return PillarVerdict(Pillar.IMMUTABLE_PROVENANCE, ok,
                         f"ledger ref {ctx.provenance_ref}" if ok else "no provenance recorded")


def _p4(ctx: PillarContext) -> PillarVerdict:
    # Compliant unless a CRITICAL intent skipped the crucible.
    ok = (not ctx.is_critical) or ctx.colmad_ran
    return PillarVerdict(Pillar.ADVERSARIAL_CRUCIBLE, ok,
                         "crucible satisfied" if ok else "CRITICAL intent skipped ColMAD")


def _p5(ctx: PillarContext) -> PillarVerdict:
    ok = ctx.actor_role in ctx.authorized_roles
    return PillarVerdict(Pillar.ZERO_TRUST_ACCESS, ok,
                         f"role {ctx.actor_role} authorized" if ok else f"role {ctx.actor_role} denied")


def _p6(ctx: PillarContext) -> PillarVerdict:
    return PillarVerdict(Pillar.KINETIC_RESILIENCE, ctx.knight_has_fallback,
                         "typed fallback present" if ctx.knight_has_fallback else "no fallback engine")


def _p7(ctx: PillarContext) -> PillarVerdict:
    ok = ctx.compression_ratio >= 1.5
    return PillarVerdict(Pillar.SEMANTIC_STORAGE, ok,
                         f"compression {ctx.compression_ratio:.1f}:1" if ok else "compression too low")


def _p8(ctx: PillarContext) -> PillarVerdict:
    ok = ctx.secrets_exposed == 0
    return PillarVerdict(Pillar.SENTINEL_SHIELD, ok,
                         "no secrets exposed" if ok else f"{ctx.secrets_exposed} secret(s) exposed")


def _p9(ctx: PillarContext) -> PillarVerdict:
    ok = not ctx.external_only_dependency
    return PillarVerdict(Pillar.SOVEREIGN_HOSTING, ok,
                         "sovereign/local-first" if ok else "hard external-only dependency")


def _p10(ctx: PillarContext) -> PillarVerdict:
    canonical = ["TRIAGE", "PLAN", "APPROVE", "EXECUTE", "VERIFY", "RECORD"]
    ok = ctx.stages_fired == canonical
    return PillarVerdict(Pillar.CONTINUOUS_KINETIC_DEPLOY, ok,
                         "six-stage loop complete" if ok else "kinetic loop incomplete/out-of-order")


def _p11(ctx: PillarContext) -> PillarVerdict:
    return PillarVerdict(Pillar.OMNI_OBSERVABILITY, ctx.metrics_available,
                         "metrics snapshot available" if ctx.metrics_available else "no observability")


_VALIDATORS: dict[Pillar, Callable[[PillarContext], PillarVerdict]] = {
    Pillar.SPEC_DRIVEN_GENESIS: _p1,
    Pillar.CONTEXTUAL_HYDRATION: _p2,
    Pillar.IMMUTABLE_PROVENANCE: _p3,
    Pillar.ADVERSARIAL_CRUCIBLE: _p4,
    Pillar.ZERO_TRUST_ACCESS: _p5,
    Pillar.KINETIC_RESILIENCE: _p6,
    Pillar.SEMANTIC_STORAGE: _p7,
    Pillar.SENTINEL_SHIELD: _p8,
    Pillar.SOVEREIGN_HOSTING: _p9,
    Pillar.CONTINUOUS_KINETIC_DEPLOY: _p10,
    Pillar.OMNI_OBSERVABILITY: _p11,
}


@dataclass
class PillarReport:
    verdicts: list[PillarVerdict]

    @property
    def all_compliant(self) -> bool:
        return all(v.compliant for v in self.verdicts)

    @property
    def violations(self) -> list[Pillar]:
        return [v.pillar for v in self.verdicts if not v.compliant]

    def render(self) -> str:
        lines = ["Obsidian Pillars enforcement:"]
        for v in self.verdicts:
            mark = "✓" if v.compliant else "✗"
            lines.append(f"  [{mark}] P{int(v.pillar):02d} {v.pillar.name:26s} {v.detail}")
        lines.append(f"  => {'ALL COMPLIANT' if self.all_compliant else f'{len(self.violations)} VIOLATION(S)'}")
        return "\n".join(lines)


class ObsidianPillars:
    """The 11-Pillar enforcement gate."""

    def enforce(self, ctx: PillarContext) -> PillarReport:
        return PillarReport([_VALIDATORS[p](ctx) for p in Pillar])

    def check(self, pillar: Pillar, ctx: PillarContext) -> PillarVerdict:
        return _VALIDATORS[pillar](ctx)

    @staticmethod
    def from_kinetic_result(result: Any) -> PillarContext:
        """Build a PillarContext from a kinetic_loop.KineticResult."""
        apee = getattr(result, "apee", None)
        triage = getattr(getattr(result, "job", None), "triage", None)
        is_critical = getattr(triage, "priority", "") == "CRITICAL"
        return PillarContext(
            stages_fired=[s.value for s in getattr(result, "stages_fired", [])],
            is_critical=is_critical,
            colmad_ran=getattr(apee, "colmad_verdict", None) is not None,
            provenance_ref=getattr(result, "provenance_ref", None),
        )


# ── Self-test (positive + negative per pillar) ────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("ObsidianPillars self-test (P2-T03)")
    op = ObsidianPillars()

    # Positive baseline — all 11 compliant.
    base = PillarContext()
    rep = op.enforce(base)
    check("baseline: 11/11 compliant", rep.all_compliant and len(rep.verdicts) == 11)

    # Negative case per pillar — flip exactly one signal and assert that pillar fails.
    negatives: list[tuple[Pillar, PillarContext]] = [
        (Pillar.SPEC_DRIVEN_GENESIS, PillarContext(stages_fired=["EXECUTE"])),
        (Pillar.CONTEXTUAL_HYDRATION, PillarContext(context_hydrated=False)),
        (Pillar.IMMUTABLE_PROVENANCE, PillarContext(provenance_ref=None)),
        (Pillar.ADVERSARIAL_CRUCIBLE, PillarContext(is_critical=True, colmad_ran=False)),
        (Pillar.ZERO_TRUST_ACCESS, PillarContext(actor_role="anonymous")),
        (Pillar.KINETIC_RESILIENCE, PillarContext(knight_has_fallback=False)),
        (Pillar.SEMANTIC_STORAGE, PillarContext(compression_ratio=1.0)),
        (Pillar.SENTINEL_SHIELD, PillarContext(secrets_exposed=2)),
        (Pillar.SOVEREIGN_HOSTING, PillarContext(external_only_dependency=True)),
        (Pillar.CONTINUOUS_KINETIC_DEPLOY, PillarContext(stages_fired=["TRIAGE", "PLAN"])),
        (Pillar.OMNI_OBSERVABILITY, PillarContext(metrics_available=False)),
    ]
    for pillar, ctx in negatives:
        v = op.check(pillar, ctx)
        check(f"P{int(pillar):02d} {pillar.name} negative -> non-compliant", not v.compliant)

    # And the ADVERSARIAL_CRUCIBLE positive: CRITICAL + colmad_ran is compliant.
    crit_ok = op.check(Pillar.ADVERSARIAL_CRUCIBLE,
                       PillarContext(is_critical=True, colmad_ran=True))
    check("P04 CRITICAL+ColMAD positive -> compliant", crit_ok.compliant)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — obsidian_pillars")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print(ObsidianPillars().enforce(PillarContext()).render())
