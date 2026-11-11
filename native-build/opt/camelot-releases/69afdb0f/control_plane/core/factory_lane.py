# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Factory Lane — CAMELOT-OS Digital Factory Control Plane
========================================================
EXCALIBUR_A_QNF Pillar 2. Typed FactoryJob pipeline replacing loose
dataclass dispatch. Every intent becomes a Pydantic-validated job flowing
through 4 priority lanes with stage-gate telemetry.

Schema-first (Pydantic AI pattern): deps_type/output_type discipline,
UsageLimits to cap runaway loops, ToolReturn to separate LLM context from
application logic, FileStatePersistence to suspend/resume HUMAN_GATE jobs.

Public API:
    FactoryJob          — the typed unit of work
    TriageScore         — Anya APEE v7.0 self-triage output (imported by anya_gate)
    ToolReturn          — separates return_value / content / metadata
    UsageLimits         — request/token/tool-call caps
    FileStatePersistence — suspend/resume HUMAN_GATE jobs
    LANE_PRIORITY       — lane → priority int mapping

Run as module for self-test:
    python -m control_plane.factory_lane --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

# ── Paths ──────────────────────────────────────────────────────────────────────

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
CHECKPOINT_DIR = CAMELOT_HOME / "logs" / "factory_checkpoints"
HITL_QUEUE = CAMELOT_HOME / "logs" / "hitl_queue.jsonl"

# ── Lane configuration ──────────────────────────────────────────────────────────

Lane = Literal["CRITICAL", "HIGH", "NORMAL", "BACKGROUND"]
HitlTier = Literal["AUTO", "PROMPT", "HUMAN_GATE"]
Stage = Literal["QUEUED", "DISPATCHED", "EXECUTING", "PIV_LOOP", "DONE", "FAILED"]
Cartridge = Literal["ANT", "BEAVER", "SPIDER", "OCTOPUS", "HIVE_IDE_SWARM", "DEFAULT"]

LANE_PRIORITY: dict[str, int] = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "BACKGROUND": 3}
LANE_WORKERS: dict[str, int] = {"CRITICAL": 1, "HIGH": 2, "NORMAL": 4, "BACKGROUND": 2}
LANE_TIMEOUT_SEC: dict[str, int] = {"CRITICAL": 30, "HIGH": 120, "NORMAL": 300, "BACKGROUND": 900}


# ── Schemas ────────────────────────────────────────────────────────────────────

class TriageScore(BaseModel):
    """Anya APEE v7.0 self-triage output (Pillar 1).

    Produced by anya_gate._stage_triage(). Drives lane assignment and HITL tier.
    risk_entropy replaces binary complexity flags with a continuous 0-1 score
    (Ouroboros Adaptive Governance, v999 NLM).
    """
    auto_dispatchable: bool
    priority: Lane
    hitl_tier: HitlTier
    risk_entropy: float = Field(ge=0.0, le=1.0)
    risk_reason: str
    assigned_knight: str
    estimated_tokens: int = Field(ge=0)
    cost_ceiling_usd: float = Field(ge=0.0, default=0.0)
    shatterpoints_detected: list[str] = Field(default_factory=list)
    requires_z3_verification: bool = False
    cartridge_hint: Cartridge = "DEFAULT"

    @classmethod
    def auto(cls, knight: str = "sir_boris", reason: str = "low risk") -> "TriageScore":
        """Convenience constructor for a clean AUTO-lane job."""
        return cls(
            auto_dispatchable=True,
            priority="NORMAL",
            hitl_tier="AUTO",
            risk_entropy=0.05,
            risk_reason=reason,
            assigned_knight=knight,
            estimated_tokens=2048,
        )


class ToolReturn(BaseModel):
    """Separates what the application needs from what the LLM sees (Pydantic AI).

    return_value: structured result for application logic (never tokenized)
    content:      the slice that re-enters the LLM context (kept minimal)
    metadata:     local logging only — zero token cost
    """
    return_value: Any = None
    content: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageLimits(BaseModel):
    """Hard caps to prevent runaway recursive tool-calling and cost blowouts."""
    request_limit: int = Field(default=10, ge=1)
    total_tokens_limit: int = Field(default=100_000, ge=1)
    tool_calls_limit: int = Field(default=50, ge=1)

    def exceeded(self, requests: int, tokens: int, tool_calls: int) -> Optional[str]:
        """Return the name of the first exceeded limit, else None."""
        if requests > self.request_limit:
            return f"request_limit ({requests} > {self.request_limit})"
        if tokens > self.total_tokens_limit:
            return f"total_tokens_limit ({tokens} > {self.total_tokens_limit})"
        if tool_calls > self.tool_calls_limit:
            return f"tool_calls_limit ({tool_calls} > {self.tool_calls_limit})"
        return None


class FactoryJob(BaseModel):
    """The typed unit of work flowing through the digital factory."""
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    intent: str
    lane: Lane
    triage: TriageScore
    assigned_knight: str
    cartridge: Cartridge = "DEFAULT"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: Stage = "QUEUED"
    hitl_approved: bool = False
    piv_iteration: int = Field(default=0, ge=0)
    usage_limits: UsageLimits = Field(default_factory=UsageLimits)
    provenance_hash: Optional[str] = None
    checkpoint_path: Optional[str] = None
    output: Optional[ToolReturn] = None
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None

    @property
    def priority_int(self) -> int:
        return LANE_PRIORITY[self.lane]

    @property
    def timeout_sec(self) -> int:
        return LANE_TIMEOUT_SEC[self.lane]

    def advance(self, stage: Stage) -> "FactoryJob":
        """Transition to a new pipeline stage (returns self for chaining)."""
        self.stage = stage
        return self

    @classmethod
    def from_triage(cls, intent: str, triage: TriageScore) -> "FactoryJob":
        """Build a job directly from an Anya triage result."""
        return cls(
            intent=intent,
            lane=triage.priority,
            triage=triage,
            assigned_knight=triage.assigned_knight,
            cartridge=triage.cartridge_hint,
        )


# ── FileStatePersistence — suspend / resume HUMAN_GATE jobs ──────────────────────

class FileStatePersistence:
    """Snapshot a FactoryJob to disk so a HUMAN_GATE job can be suspended for
    arbitrary time and resumed deterministically (Pydantic AI FileStatePersistence).
    """

    def __init__(self, checkpoint_dir: Path = CHECKPOINT_DIR):
        self.dir = checkpoint_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, job: FactoryJob) -> str:
        """Serialize job to a checkpoint file. Returns the path."""
        path = self.dir / f"{job.job_id}.json"
        job.checkpoint_path = str(path)
        # atomic write: tmp -> replace
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)
        return str(path)

    def load(self, checkpoint_path: str) -> FactoryJob:
        """Reconstruct a FactoryJob from a checkpoint file."""
        data = Path(checkpoint_path).read_text(encoding="utf-8")
        return FactoryJob.model_validate_json(data)

    def resume(self, checkpoint_path: str, to_stage: Stage = "DISPATCHED") -> FactoryJob:
        """Load and advance a suspended job."""
        job = self.load(checkpoint_path)
        return job.advance(to_stage)

    def delete(self, job: FactoryJob) -> None:
        if job.checkpoint_path and Path(job.checkpoint_path).exists():
            Path(job.checkpoint_path).unlink()


# ── HITL queue helper ────────────────────────────────────────────────────────────

def enqueue_human_gate(job: FactoryJob, checkpoint: str) -> None:
    """Append a HUMAN_GATE suspension to the HITL queue for operator review."""
    HITL_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "job_id": job.job_id,
        "intent": job.intent,
        "lane": job.lane,
        "hitl_tier": job.triage.hitl_tier,
        "risk_reason": job.triage.risk_reason,
        "shatterpoints": job.triage.shatterpoints_detected,
        "checkpoint": checkpoint,
    }
    with HITL_QUEUE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Self-test ────────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        status = "PASS" if cond else "FAIL"
        if not cond:
            failures += 1
        print(f"  [{status}] {name}")

    print("FactoryLane self-test")

    # V3.1 FactoryJob validates
    t = TriageScore.auto(knight="sir_boris")
    job = FactoryJob.from_triage("show ledger status", t)
    check("V3.1 FactoryJob validates from triage", job.stage == "QUEUED")
    check("V3.1 lane mirrors triage priority", job.lane == "NORMAL")
    check("V3.1 priority_int correct", job.priority_int == 2)

    # V3.2 UsageLimits enforced
    ul = UsageLimits(request_limit=2)
    check("V3.2 UsageLimits passes under cap", ul.exceeded(2, 100, 1) is None)
    check("V3.2 UsageLimits trips over cap", ul.exceeded(3, 100, 1) is not None)

    # V3.3/3.4 FileStatePersistence save/load/resume
    fsp = FileStatePersistence()
    crit = TriageScore(
        auto_dispatchable=False, priority="CRITICAL", hitl_tier="HUMAN_GATE",
        risk_entropy=0.9, risk_reason="destructive op", assigned_knight="sir_sentinel",
        estimated_tokens=512, shatterpoints_detected=["destructive_autonomy"],
    )
    cjob = FactoryJob.from_triage("delete all logs", crit)
    path = fsp.save(cjob)
    loaded = fsp.load(path)
    check("V3.3 save/load preserves job_id", loaded.job_id == cjob.job_id)
    check("V3.3 save/load preserves triage", loaded.triage.risk_entropy == 0.9)
    check("V3.3 save/load preserves shatterpoints",
          loaded.triage.shatterpoints_detected == ["destructive_autonomy"])
    resumed = fsp.resume(path)
    check("V3.4 resume advances stage", resumed.stage == "DISPATCHED")
    fsp.delete(cjob)
    check("V3.4 checkpoint cleaned up", not Path(path).exists())

    # ToolReturn separation
    tr = ToolReturn(return_value={"rows": 42}, content="42 rows", metadata={"ms": 12})
    check("ToolReturn separates value/content/metadata",
          tr.return_value["rows"] == 42 and tr.content == "42 rows")

    # HUMAN_GATE enqueue
    cp = fsp.save(cjob)
    enqueue_human_gate(cjob, cp)
    check("HITL queue file written", HITL_QUEUE.exists())
    fsp.delete(cjob)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} "
          f"— factory_lane")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    # default: show lane config
    print("CAMELOT-OS Factory Lanes")
    for lane, prio in sorted(LANE_PRIORITY.items(), key=lambda kv: kv[1]):
        print(f"  [{prio}] {lane:11s} workers={LANE_WORKERS[lane]} "
              f"timeout={LANE_TIMEOUT_SEC[lane]}s")
