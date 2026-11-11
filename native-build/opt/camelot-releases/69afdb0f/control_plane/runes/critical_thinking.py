# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Evidence:
    claim: str
    source: str
    confidence: float = 0.5
    note: str = ""


@dataclass
class CriticalThinkingFrame:
    objective: str
    facts: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def add_fact(self, fact: str) -> None:
        text = fact.strip()
        if text:
            self.facts.append(text)

    def add_assumption(self, assumption: str) -> None:
        text = assumption.strip()
        if text:
            self.assumptions.append(text)

    def add_risk(self, risk: str) -> None:
        text = risk.strip()
        if text:
            self.risks.append(text)

    def add_decision(self, decision: str) -> None:
        text = decision.strip()
        if text:
            self.decisions.append(text)

    def add_next_action(self, action: str) -> None:
        text = action.strip()
        if text:
            self.next_actions.append(text)


def assimilate_evidence(evidence: Iterable[Evidence]) -> list[str]:
    """Reduce evidence into a ranked list of critical-thinking observations.

    This is the universal skill-layer analog of Portkey's gateway behavior:
    keep the best-supported claims, retain fallback signals, and make the
    confidence boundary explicit.
    """

    ordered = sorted(evidence, key=lambda item: item.confidence, reverse=True)
    summaries: list[str] = []
    for item in ordered:
        confidence_label = "high" if item.confidence >= 0.8 else "medium" if item.confidence >= 0.5 else "low"
        note = f" ({item.note})" if item.note else ""
        summaries.append(f"[{confidence_label}] {item.claim} <- {item.source}{note}")
    return summaries


def build_thinking_frame(
    objective: str,
    *,
    evidence: Iterable[Evidence] | None = None,
    constraints: Iterable[str] | None = None,
) -> CriticalThinkingFrame:
    frame = CriticalThinkingFrame(objective=objective.strip())
    for item in evidence or []:
        frame.add_fact(f"{item.claim} [{item.source}]")
        if item.confidence < 0.5:
            frame.add_assumption(f"Low-confidence claim to verify: {item.claim}")
    for constraint in constraints or []:
        frame.add_risk(constraint)
    return frame


def qualify_frame(frame: CriticalThinkingFrame) -> list[str]:
    """Apply the PAUL-style plan/apply/unify loop to a thinking frame."""

    checks: list[str] = []
    if not frame.objective:
        checks.append("BLOCKED: objective is missing")
    if not frame.facts:
        checks.append("NEEDS_CONTEXT: no verified facts collected")
    if not frame.next_actions and not frame.decisions:
        checks.append("NEEDS_CONTEXT: no decision or next action recorded")
    if not checks:
        checks.append("DONE: frame is qualified")
    return checks


def universal_knight_protocol(
    objective: str,
    *,
    evidence: Iterable[Evidence] | None = None,
    constraints: Iterable[str] | None = None,
) -> CriticalThinkingFrame:
    """Create the shared critical-thinking frame for all Camelot knights."""

    frame = build_thinking_frame(objective, evidence=evidence, constraints=constraints)
    summaries = assimilate_evidence(evidence or [])
    for summary in summaries:
        frame.add_fact(summary)
    qualification = qualify_frame(frame)
    for item in qualification:
        frame.add_decision(item)
    if qualification and qualification[0].startswith("DONE"):
        frame.add_next_action("Proceed with verified implementation")
    else:
        frame.add_next_action("Collect missing context before execution")
    return frame

