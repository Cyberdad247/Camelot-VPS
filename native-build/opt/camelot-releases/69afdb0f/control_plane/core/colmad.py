# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
ColMAD — Collaborative Multi-Agent Debate (Think Tank Omega)
============================================================
EXCALIBUR_A_QNF Phase 4. Before any CRITICAL/HIGH architectural commit, three
adversarial persona vectors stress-test the proposal (v999 NLM). Maps Sir
Boris's Crucible Conductor role into a structured debate.

Personas (Alexandrian Matrix authority vectors):
    stark_scaling   — "Does this scale? What breaks at 10x?"
    greene_strategy — "Who benefits? What is the power/coupling cost?"
    tao_rigor       — "Is the logic sound? No hand-waving, no unbounded loops?"

Consensus: >= 2/3 APPROVE -> APPROVED. Otherwise -> escalate to HUMAN_GATE.

Deterministic heuristic core (testable offline). An optional LLM path can be
supplied via `crucible(..., judge=callable)` for live persona simulation.

Run as module:
    python -m control_plane.colmad --test
    python -m control_plane.colmad "Add a Rust kernel shell"
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PERSONAS = ("stark_scaling", "greene_strategy", "tao_rigor")


@dataclass
class PersonaVote:
    persona: str
    approve: bool
    concern: str


@dataclass
class CrucibleVerdict:
    proposal: str
    votes: list[PersonaVote] = field(default_factory=list)
    approvals: int = 0
    verdict: str = "PENDING"          # APPROVED | HUMAN_GATE
    escalate: bool = False

    def render(self) -> str:
        lines = [f"ColMAD Crucible: {self.proposal[:60]}"]
        for v in self.votes:
            mark = "✓" if v.approve else "✗"
            lines.append(f"  [{mark}] {v.persona:16s} {v.concern}")
        lines.append(f"  => {self.verdict} ({self.approvals}/3 approve)")
        return "\n".join(lines)


# Heuristic risk signals per persona axis.
_SCALE_RISK = re.compile(r"\b(global|all users|every|unbounded|infinite|monolith|sync(hronous)?|blocking)\b", re.I)
_SCALE_GOOD = re.compile(r"\b(async|parallel|cache|shard|stream|lazy|incremental|staged)\b", re.I)

_STRATEGY_RISK = re.compile(r"\b(vendor lock|proprietary|single point|tightly coupled|hard.?code|rewrite everything)\b", re.I)
_STRATEGY_GOOD = re.compile(r"\b(modular|fallback|graceful|open.?source|portable|reversible|additive)\b", re.I)

_RIGOR_RISK = re.compile(r"\b(maybe|probably|somehow|magic|just works|trust me|recursi|loop forever|no test)\b", re.I)
_RIGOR_GOOD = re.compile(r"\b(verified|typed|test|bounded|deterministic|proof|z3|invariant)\b", re.I)


def _vote(persona: str, text: str) -> PersonaVote:
    t = text.lower()
    if persona == "stark_scaling":
        risk = len(_SCALE_RISK.findall(t))
        good = len(_SCALE_GOOD.findall(t))
        approve = good >= risk
        concern = ("scales — async/staged signals present" if approve
                   else "scaling risk: synchronous/unbounded/global coupling")
    elif persona == "greene_strategy":
        risk = len(_STRATEGY_RISK.findall(t))
        good = len(_STRATEGY_GOOD.findall(t))
        approve = good >= risk
        concern = ("sound strategy — modular/reversible" if approve
                   else "strategy risk: lock-in / tight coupling / irreversible")
    else:  # tao_rigor
        risk = len(_RIGOR_RISK.findall(t))
        good = len(_RIGOR_GOOD.findall(t))
        approve = good >= risk
        concern = ("rigorous — verified/typed/bounded" if approve
                   else "rigor risk: hand-waving / unbounded / untested")
    return PersonaVote(persona=persona, approve=approve, concern=concern)


class ColMAD:
    """Three-persona adversarial crucible."""

    def crucible(
        self,
        proposal: str,
        judge: Optional[Callable[[str, str], bool]] = None,
    ) -> CrucibleVerdict:
        """Run the debate. If `judge(persona, proposal)` is supplied it overrides
        the heuristic vote (e.g. a live LLM persona)."""
        verdict = CrucibleVerdict(proposal=proposal)
        for persona in PERSONAS:
            if judge is not None:
                approve = bool(judge(persona, proposal))
                verdict.votes.append(PersonaVote(persona, approve,
                                                 "judge override"))
            else:
                verdict.votes.append(_vote(persona, proposal))
        verdict.approvals = sum(1 for v in verdict.votes if v.approve)
        if verdict.approvals >= 2:
            verdict.verdict = "APPROVED"
            verdict.escalate = False
        else:
            verdict.verdict = "HUMAN_GATE"
            verdict.escalate = True
        return verdict


# ── Self-test ────────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("ColMAD self-test")
    cm = ColMAD()

    # V4.7 well-formed proposal reaches consensus
    good = cm.crucible(
        "Add a modular, async, staged Rust shell with typed, verified, bounded "
        "interfaces and a graceful fallback — fully reversible and tested."
    )
    check("V4.7 sound proposal -> APPROVED", good.verdict == "APPROVED")
    check("V4.7 >= 2/3 approvals", good.approvals >= 2)

    # V4.8 risky proposal escalates
    bad = cm.crucible(
        "Rewrite everything synchronously as a global monolith, hard-code the "
        "vendor lock, it probably just works, no test, trust me."
    )
    check("V4.8 risky proposal -> HUMAN_GATE", bad.verdict == "HUMAN_GATE")
    check("V4.8 escalate flag set", bad.escalate is True)

    # judge override path
    forced = cm.crucible("anything", judge=lambda p, x: False)
    check("judge override forces HUMAN_GATE", forced.verdict == "HUMAN_GATE")
    forced_ok = cm.crucible("anything", judge=lambda p, x: True)
    check("judge override can approve", forced_ok.verdict == "APPROVED")

    # 3 votes always present
    check("always 3 persona votes", len(good.votes) == 3)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — colmad")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    proposal = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or \
        "Add SpacetimeDB as the embedded data layer"
    print(ColMAD().crucible(proposal).render())
