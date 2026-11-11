# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
SirSocrates v1.0 — Northstar Alignment Examiner
================================================
L5 Sovereign Oracle. 5 Socratic alignment questions block any HIGH/CRITICAL
intent from proceeding without examination.

Five pillars examined per intent:
  Q1: Local Sovereignty — does this keep CAMELOT-OS sovereign and local-first?
  Q2: Fingerprint Surface — does this reduce telemetry and fingerprint exposure?
  Q3: Resource Efficiency — does this use fewer CPU/RAM/disk cycles?
  Q4: Iron Gate Integrity — does this preserve HITL governance?
  Q5: Northstar Alignment — does this advance absolute local optimization?

Verdict logging → logs/northstar_verdicts.jsonl
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("SIR_SOCRATES")

_VERDICTS_LOG = Path("logs/northstar_verdicts.jsonl")


@dataclass
class SocraticAnswer:
    question_id: str   # Q1–Q5
    question: str
    aligned: bool
    reasoning: str
    confidence: float  # 0.0–1.0


@dataclass
class SocratesExamination:
    intent: str
    answers: list[SocraticAnswer] = field(default_factory=list)
    overall_aligned: bool = True
    blocking_questions: list[str] = field(default_factory=list)
    verdict: str = "PENDING"   # ALIGNED | PARTIAL | BLOCKED
    examined_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.answers:
            self._compute_verdict()

    def _compute_verdict(self):
        self.blocking_questions = [a.question_id for a in self.answers if not a.aligned]
        if not self.blocking_questions:
            self.verdict = "ALIGNED"
            self.overall_aligned = True
        elif len(self.blocking_questions) <= 1:
            self.verdict = "PARTIAL"
            self.overall_aligned = False
        else:
            self.verdict = "BLOCKED"
            self.overall_aligned = False


# ── Keyword heuristics per question ────────────────────────────────────────

_Q1_CLOUD_KEYWORDS = re.compile(
    r"\b(send to cloud|upload to|aws|azure|gcp|google cloud|anthropic api|openai api"
    r"|external server|third.party|telemetry endpoint|beacon)\b",
    re.I,
)
_Q2_FINGERPRINT_KEYWORDS = re.compile(
    r"\b(track|fingerprint|device id|mac address|uuid|analytics|mixpanel|segment"
    r"|amplitude|datadog|new relic|sentry|rollbar)\b",
    re.I,
)
_Q3_BLOAT_KEYWORDS = re.compile(
    r"\b(install all|import \*|load everything|preload|eager.load"
    r"|duplicate|redundant|unoptimized|no cache)\b",
    re.I,
)
_Q4_BYPASS_KEYWORDS = re.compile(
    r"\b(skip hitl|bypass gate|no approval|auto.approve all|remove iron gate"
    r"|disable oversight|--no-verify|force.push|override safety)\b",
    re.I,
)
_Q5_LOCAL_DRIFT_KEYWORDS = re.compile(
    r"\b(vendor lock|proprietary only|cloud.only|requires internet"
    r"|no offline|subscription.required|saas.only)\b",
    re.I,
)


class SirSocrates:
    """Examines intents against 5 Northstar pillars. Can be used sync or async."""

    def __init__(
        self,
        verdicts_path: Path | str | None = None,
        log_verdicts: bool = True,
    ) -> None:
        self.verdicts_path = Path(verdicts_path or _VERDICTS_LOG)
        self.log_verdicts = log_verdicts

    # ── Public API ─────────────────────────────────────────────────────────

    def examine(self, intent: str, triage_tier: str = "AUTO") -> SocratesExamination:
        """Synchronous examination. Use for integration in AnyaGate.process().

        Only examines HIGH/CRITICAL/HUMAN_GATE tiers — all others pass straight through.
        """
        if triage_tier not in ("PROMPT", "HUMAN_GATE") and "HIGH" not in intent.upper() and "CRITICAL" not in intent.upper():
            return SocratesExamination(
                intent=intent,
                answers=[],
                overall_aligned=True,
                verdict="ALIGNED",
            )

        answers = [
            self._q1_sovereignty(intent),
            self._q2_fingerprint(intent),
            self._q3_efficiency(intent),
            self._q4_iron_gate(intent),
            self._q5_northstar(intent),
        ]

        exam = SocratesExamination(intent=intent, answers=answers)
        exam._compute_verdict()

        if self.log_verdicts:
            self._log_verdict(exam)

        return exam

    def examine_all(self, intent: str) -> SocratesExamination:
        """Always run all 5 questions regardless of tier (for tests / direct calls)."""
        answers = [
            self._q1_sovereignty(intent),
            self._q2_fingerprint(intent),
            self._q3_efficiency(intent),
            self._q4_iron_gate(intent),
            self._q5_northstar(intent),
        ]
        exam = SocratesExamination(intent=intent, answers=answers)
        exam._compute_verdict()
        if self.log_verdicts:
            self._log_verdict(exam)
        return exam

    # ── 5 Socratic Questions ───────────────────────────────────────────────

    def _q1_sovereignty(self, intent: str) -> SocraticAnswer:
        """Q1: Does this keep CAMELOT-OS sovereign and local-first?"""
        breach = bool(_Q1_CLOUD_KEYWORDS.search(intent))
        return SocraticAnswer(
            question_id="Q1",
            question="Does this keep CAMELOT-OS sovereign and local-first?",
            aligned=not breach,
            reasoning=(
                "Intent references cloud/external services — violates local sovereignty"
                if breach else
                "No cloud dependency detected — local sovereignty preserved"
            ),
            confidence=0.85 if breach else 0.90,
        )

    def _q2_fingerprint(self, intent: str) -> SocraticAnswer:
        """Q2: Does this reduce telemetry and fingerprint exposure?"""
        breach = bool(_Q2_FINGERPRINT_KEYWORDS.search(intent))
        return SocraticAnswer(
            question_id="Q2",
            question="Does this reduce telemetry and fingerprint exposure?",
            aligned=not breach,
            reasoning=(
                "Fingerprint/tracking keywords detected — Shadow Veil at risk"
                if breach else
                "No fingerprinting vectors detected — shadow profile safe"
            ),
            confidence=0.88 if breach else 0.92,
        )

    def _q3_efficiency(self, intent: str) -> SocraticAnswer:
        """Q3: Does this use fewer CPU/RAM/disk cycles?"""
        breach = bool(_Q3_BLOAT_KEYWORDS.search(intent))
        return SocraticAnswer(
            question_id="Q3",
            question="Does this use fewer CPU/RAM/disk cycles?",
            aligned=not breach,
            reasoning=(
                "Bloat/redundancy keywords — resource efficiency compromised"
                if breach else
                "No bloat patterns — resource efficiency preserved"
            ),
            confidence=0.80 if breach else 0.85,
        )

    def _q4_iron_gate(self, intent: str) -> SocraticAnswer:
        """Q4: Does this preserve Iron Gate HITL governance?"""
        breach = bool(_Q4_BYPASS_KEYWORDS.search(intent))
        return SocraticAnswer(
            question_id="Q4",
            question="Does this preserve Iron Gate HITL governance?",
            aligned=not breach,
            reasoning=(
                "HITL bypass keywords detected — Iron Gate integrity threatened"
                if breach else
                "No governance bypass detected — Iron Gate integrity preserved"
            ),
            confidence=0.95 if breach else 0.97,
        )

    def _q5_northstar(self, intent: str) -> SocraticAnswer:
        """Q5: Does this advance absolute local optimization (Northstar)?"""
        drift = bool(_Q5_LOCAL_DRIFT_KEYWORDS.search(intent))
        return SocraticAnswer(
            question_id="Q5",
            question="Does this advance absolute local optimization (Northstar)?",
            aligned=not drift,
            reasoning=(
                "Vendor lock/cloud-only patterns detected — Northstar drift risk"
                if drift else
                "Intent aligns with local-first Northstar objective"
            ),
            confidence=0.87 if drift else 0.91,
        )

    # ── Verdict logging ────────────────────────────────────────────────────

    def _log_verdict(self, exam: SocratesExamination) -> None:
        try:
            self.verdicts_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": exam.examined_at,
                "intent_hash": hash(exam.intent) & 0xFFFFFFFF,
                "intent_prefix": exam.intent[:80],
                "verdict": exam.verdict,
                "blocking": exam.blocking_questions,
                "answers": [
                    {"id": a.question_id, "aligned": a.aligned, "confidence": a.confidence}
                    for a in exam.answers
                ],
            }
            with self.verdicts_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            log.debug("[SOCRATES] verdict log failed: %s", exc)
