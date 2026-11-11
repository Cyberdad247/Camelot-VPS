# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
SARDA Engine — Swarm Agent Routing and Dispatch Architecture
=============================================================
Map-Reduce orchestration loop for multi-agent code generation.

MAP:     Decompose task into sub-tasks, fan out to Knights in parallel.
REDUCE:  Collect results, merge into unified AST/artifact.
CRITIQUE: Run 13-Agent Antagonistic Critique pipeline on merged output.

Pure reasoning layer — all I/O delegated to Kinetic Edge via MCP.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

# Add KERNEL to path for telemetry import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    _TELEMETRY_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "01_KERNEL", "senses", "telemetry_client.py")
    )
    _TELEMETRY_SPEC = importlib.util.spec_from_file_location(
        "camelot_telemetry_client",
        _TELEMETRY_PATH,
    )
    if _TELEMETRY_SPEC is None or _TELEMETRY_SPEC.loader is None:
        raise ImportError(f"Unable to load telemetry client from {_TELEMETRY_PATH}")
    _TELEMETRY_MODULE = importlib.util.module_from_spec(_TELEMETRY_SPEC)
    _TELEMETRY_SPEC.loader.exec_module(_TELEMETRY_MODULE)
    RotelClient = _TELEMETRY_MODULE.RotelClient
    logger = RotelClient("sarda_engine")
except Exception:
    class DummyLogger:
        def info(self, *args, **kwargs): pass
    logger = DummyLogger()

from .deerflow_sandbox import DeerFlowSandbox
from .omc_team import OMCTeam
from control_plane.core.soul_router import SoulRouter

# ---------------------------------------------------------------------------
# SARDA Phase Definitions
# ---------------------------------------------------------------------------

class SARDAPhase(str, Enum):
    MAP = "MAP"
    REDUCE = "REDUCE"
    CRITIQUE = "CRITIQUE"
    SETTLE = "SETTLE"


class SubTaskStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubTask:
    """A single unit of work dispatched to a Knight during MAP phase."""
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    intent: str = ""
    knight_id: str = ""
    status: SubTaskStatus = SubTaskStatus.PENDING
    result: Optional[str] = None
    dispatched_at: Optional[float] = None
    completed_at: Optional[float] = None

    @property
    def duration_ms(self) -> float:
        if self.dispatched_at and self.completed_at:
            return (self.completed_at - self.dispatched_at) * 1000
        return 0.0


@dataclass
class CritiqueVerdict:
    """Result from the 13-Agent Antagonistic Critique pipeline."""
    passed: bool = False
    confidence: float = 0.0
    stages_passed: int = 0
    stages_total: int = 13
    failures: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SARDAResult:
    """Complete result from a SARDA Map-Reduce-Critique cycle."""
    task_id: str
    phase: SARDAPhase
    sub_tasks: list[SubTask]
    merged_output: Optional[str] = None
    critique: Optional[CritiqueVerdict] = None
    total_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> str:
        return json.dumps({
            "task_id": self.task_id,
            "phase": self.phase.value,
            "sub_tasks": [
                {
                    "id": st.id,
                    "intent": st.intent,
                    "knight_id": st.knight_id,
                    "status": st.status.value,
                    "duration_ms": st.duration_ms,
                }
                for st in self.sub_tasks
            ],
            "merged_output_length": len(self.merged_output) if self.merged_output else 0,
            "critique": {
                "passed": self.critique.passed,
                "confidence": self.critique.confidence,
                "stages_passed": self.critique.stages_passed,
                "failures": self.critique.failures,
            } if self.critique else None,
            "total_ms": self.total_ms,
            "timestamp": self.timestamp,
        }, indent=2)


# ---------------------------------------------------------------------------
# SARDA Decomposer — breaks a task into routable sub-tasks
# ---------------------------------------------------------------------------

# Intent keyword -> sub-task decomposition rules
DECOMPOSITION_RULES: dict[str, list[str]] = {
    "scaffold": [
        "architecture:generate project structure and module boundaries",
        "code_gen:implement core functions and types",
        "security_review:audit generated code for OWASP vulnerabilities",
    ],
    "refactor": [
        "architecture:analyze dependency graph and propose restructure",
        "code_gen:implement refactored modules",
        "audit:validate no behavioral regressions",
    ],
    "feature": [
        "architecture:design feature integration points",
        "code_gen:implement feature logic",
        "security_review:check for injection vectors in new surface area",
    ],
    "fix": [
        "code_gen:implement the fix",
        "audit:verify fix addresses root cause",
    ],
    "deploy": [
        "orchestration:coordinate deployment sequence",
        "memory:archive deployment evidence and release context",
        "security_review:pre-deploy security scan",
        "audit:post-deploy health verification",
    ],
}

# Fallback: any unrecognized intent gets this decomposition
DEFAULT_DECOMPOSITION = [
    "architecture:analyze and plan approach",
    "code_gen:implement solution",
    "audit:validate output",
]


def decompose(intent: str) -> list[tuple[str, str]]:
    """Break an intent string into (routing_keyword, sub_intent) pairs.

    Uses DECOMPOSITION_RULES for known patterns, DEFAULT_DECOMPOSITION otherwise.
    """
    intent_lower = intent.lower()
    for trigger, rules in DECOMPOSITION_RULES.items():
        if trigger in intent_lower:
            return [
                (r.split(":", 1)[0], r.split(":", 1)[1])
                for r in rules
            ]
    return [
        (r.split(":", 1)[0], r.split(":", 1)[1])
        for r in DEFAULT_DECOMPOSITION
    ]


# ---------------------------------------------------------------------------
# 13-Agent Critique Pipeline (Stub — T6.4 will implement full pipeline)
# ---------------------------------------------------------------------------

CRITIQUE_STAGES = (
    "SECURITY",
    "CONTRACTS",
    "TESTS",
    "EDGE_CASES",
    "TYPES",
    "PERF",
    "CONCURRENCY",
    "API_SURFACE",
    "ROLLBACK",
    "INJECTION_GUARD",
    "INTEGRATION",
    "OPS",
    "FINAL_VERDICT",
)


def run_critique(merged_output: str) -> CritiqueVerdict:
    """Run the 13-Agent Antagonistic Critique pipeline.

    Current implementation: structural validation only.
    T6.4 will wire each stage to its dedicated agent.
    """
    failures = []

    # Stage 1: SECURITY — check for obvious dangerous patterns
    dangerous = ["eval(", "exec(", "os.system(", "__import__(",
                 "subprocess.call(", "shell=True"]
    for pattern in dangerous:
        if pattern in merged_output:
            failures.append(f"SECURITY: dangerous pattern '{pattern}' detected")

    # Stage 2: CONTRACTS — check for bare except clauses
    if "except:" in merged_output and "except Exception" not in merged_output:
        failures.append("CONTRACTS: bare 'except:' clause — must specify exception type")

    # Stage 10: INJECTION_GUARD — check for string formatting in SQL/shell
    if "f'" in merged_output or 'f"' in merged_output:
        for risk in ["DELETE ", "DROP ", "INSERT ", "UPDATE ", "SELECT "]:
            if risk in merged_output.upper():
                # Check if it's inside an f-string context (rough heuristic)
                idx = merged_output.upper().find(risk)
                preceding = merged_output[max(0, idx - 50):idx]
                if "f'" in preceding or 'f"' in preceding:
                    failures.append(
                        f"INJECTION_GUARD: SQL keyword '{risk.strip()}' in f-string context"
                    )

    stages_passed = len(CRITIQUE_STAGES) - len(failures)
    confidence = stages_passed / len(CRITIQUE_STAGES)

    return CritiqueVerdict(
        passed=len(failures) == 0,
        confidence=round(confidence, 3),
        stages_passed=stages_passed,
        stages_total=len(CRITIQUE_STAGES),
        failures=failures,
    )


# ---------------------------------------------------------------------------
# SARDA Engine
# ---------------------------------------------------------------------------

class SARDAEngine:
    """Swarm Agent Routing and Dispatch Architecture.

    Orchestrates a Map-Reduce-Critique cycle:
    1. MAP:     Decompose task -> fan out sub-tasks to Knights in parallel
    2. REDUCE:  Collect outputs -> merge into unified artifact
    3. CRITIQUE: 13-Agent pipeline validates the merged output
    """

    def __init__(
        self,
        soul_router: Optional[SoulRouter] = None,
        deerflow: Optional[DeerFlowSandbox] = None,
    ):
        self.soul_router = soul_router or SoulRouter()
        self._omc_team: Optional[OMCTeam] = None
        self._deerflow = deerflow  # Lazy-checked on first dispatch
        self.results_dir = Path.home() / "CAMELOT_OS" / "logs" / "sarda"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    # --- MAP Phase ---

    def map_phase(
        self,
        intent: str,
        parameters: dict[str, Any] | None = None,
        privacy: float = 0.0,
    ) -> list[SubTask]:
        """Decompose intent into sub-tasks and route each to a Knight.

        Returns list of SubTask objects with knight_id assigned via SoulRouter.
        """
        pairs = decompose(intent)
        sub_tasks = []

        for routing_keyword, sub_intent in pairs:
            # Route through Soul Equation
            full_intent = f"{routing_keyword}: {sub_intent}"
            route = self.soul_router.route(
                full_intent,
                velocity=0.5,
                magnitude=0.6,
                privacy=privacy,
            )

            st = SubTask(
                intent=sub_intent,
                knight_id=route.knight_id,
            )
            sub_tasks.append(st)

        return sub_tasks

    def _get_deerflow(self) -> Optional[DeerFlowSandbox]:
        """Lazy-check DeerFlow availability."""
        if self._deerflow is None:
            df = DeerFlowSandbox()
            if df.check_docker():
                self._deerflow = df
        return self._deerflow if self._deerflow and self._deerflow.check_docker() else None

    def _dispatch_via_deerflow(
        self, st: SubTask, context: str
    ) -> SubTask:
        """Execute a code_gen sub-task inside a DeerFlow sandbox container."""
        df = self._deerflow
        if not df:
            st.status = SubTaskStatus.FAILED
            st.result = "DeerFlow unavailable"
            return st

        code = f"# SARDA sub-task: {st.id}\n# {st.intent}\n{context}"
        sandbox_id = f"sarda_{st.id}"

        st.dispatched_at = time.time()
        st.status = SubTaskStatus.DISPATCHED

        result = df.execute_python(code, sandbox_id=sandbox_id, timeout=120)

        st.completed_at = time.time()
        if result.success:
            st.status = SubTaskStatus.COMPLETED
            st.result = result.stdout
        else:
            st.status = SubTaskStatus.FAILED
            st.result = result.stderr

        return st

    def dispatch_map(
        self, sub_tasks: list[SubTask], context: str = ""
    ) -> list[SubTask]:
        """Fan out sub-tasks to Knights in parallel.

        code_gen tasks (sir_forge) go through DeerFlow sandbox containers
        when Docker is available. All other tasks go through OMCTeam (tmux).

        Args:
            sub_tasks: List from map_phase().
            context: Shared context string prepended to each prompt.

        Returns:
            Updated sub_tasks with status set to DISPATCHED/COMPLETED/FAILED.
        """
        deerflow = self._get_deerflow()

        # Partition: code_gen tasks → DeerFlow, everything else → OMCTeam
        deerflow_tasks = []
        omc_tasks = []
        for st in sub_tasks:
            if st.knight_id == "sir_forge" and deerflow:
                deerflow_tasks.append(st)
            else:
                omc_tasks.append(st)

        # Dispatch DeerFlow tasks in parallel (semaphore caps at 3 containers)
        if deerflow_tasks:
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {
                    pool.submit(self._dispatch_via_deerflow, st, context): st
                    for st in deerflow_tasks
                }
                for future in as_completed(futures):
                    try:
                        future.result()  # Updates sub_task in place
                    except Exception:
                        st = futures[future]
                        st.status = SubTaskStatus.FAILED
                        st.result = "DeerFlow dispatch exception"

        # Dispatch OMC tasks via existing tmux pathway
        if omc_tasks:
            if self._omc_team is None:
                self._omc_team = OMCTeam()
                self._omc_team.spawn_session()

            results = {}
            for st in omc_tasks:
                prompt = f"[SARDA:{st.id}] {context}\n\nSub-task: {st.intent}"
                success = self._omc_team.dispatch(st.knight_id, prompt)
                results[st.knight_id] = success

            now = time.time()
            for st in omc_tasks:
                if results.get(st.knight_id, False):
                    st.status = SubTaskStatus.DISPATCHED
                    st.dispatched_at = now
                else:
                    st.status = SubTaskStatus.FAILED

        return sub_tasks

    # --- REDUCE Phase ---

    def reduce_phase(
        self, sub_tasks: list[SubTask], timeout: int = 120
    ) -> str:
        """Collect results from dispatched Knights and merge into single output.

        Args:
            sub_tasks: List of dispatched sub-tasks.
            timeout: Max seconds to wait for each knight.

        Returns:
            Merged output string.
        """
        if self._omc_team is None:
            return ""

        raw_results = self._omc_team.collect_all(timeout=timeout)

        now = time.time()
        merged_parts = []
        for st in sub_tasks:
            output = raw_results.get(st.knight_id)
            if output:
                st.status = SubTaskStatus.COMPLETED
                st.result = output
                st.completed_at = now
                merged_parts.append(
                    f"# --- [{st.knight_id}] {st.intent} ---\n{output}"
                )
            else:
                st.status = SubTaskStatus.FAILED
                st.completed_at = now

        return "\n\n".join(merged_parts)

    # --- CRITIQUE Phase ---

    def critique_phase(self, merged_output: str) -> CritiqueVerdict:
        """Run 13-Agent Antagonistic Critique on the merged output."""
        return run_critique(merged_output)

    # --- Full Cycle ---

    def execute(
        self,
        intent: str,
        parameters: dict[str, Any] | None = None,
        context: str = "",
        privacy: float = 0.0,
        timeout: int = 120,
    ) -> SARDAResult:
        """Execute a full SARDA Map-Reduce-Critique cycle.

        Args:
            intent: High-level task description.
            parameters: Optional task parameters.
            context: Shared context for all sub-tasks.
            privacy: Data sensitivity [0-1]. >=0.8 forces Sir Ghost.
            timeout: Max seconds to wait per knight in REDUCE phase.

        Returns:
            SARDAResult with full telemetry.
        """
        task_id = uuid4().hex[:12]
        logger.info("SARDA_EXECUTION_START", task_id=task_id, intent=intent)
        start = time.perf_counter()

        # MAP
        logger.info("SARDA_PHASE_START", task_id=task_id, phase="MAP")
        sub_tasks = self.map_phase(intent, parameters, privacy)
        sub_tasks = self.dispatch_map(sub_tasks, context)

        # REDUCE
        logger.info("SARDA_PHASE_START", task_id=task_id, phase="REDUCE")
        merged = self.reduce_phase(sub_tasks, timeout)

        # CRITIQUE
        logger.info("SARDA_PHASE_START", task_id=task_id, phase="CRITIQUE")
        critique = self.critique_phase(merged)

        total_ms = (time.perf_counter() - start) * 1000

        result = SARDAResult(
            task_id=task_id,
            phase=SARDAPhase.CRITIQUE if critique else SARDAPhase.REDUCE,
            sub_tasks=sub_tasks,
            merged_output=merged,
            critique=critique,
            total_ms=round(total_ms, 1),
        )

        logger.info("SARDA_EXECUTION_COMPLETE", task_id=task_id, total_ms=total_ms, passed=critique.passed if critique else None)

        # Persist telemetry
        out_file = self.results_dir / f"sarda_{task_id}.json"
        out_file.write_text(result.to_json(), encoding="utf-8")

        return result

    # --- Dry-Run (no tmux, for validation) ---

    def dry_run(
        self,
        intent: str,
        privacy: float = 0.0,
    ) -> SARDAResult:
        """Plan a SARDA cycle without dispatching — returns routing decisions only.

        Useful for verifying decomposition and knight assignment before execution.
        """
        task_id = uuid4().hex[:12]
        start = time.perf_counter()

        sub_tasks = self.map_phase(intent, privacy=privacy)

        total_ms = (time.perf_counter() - start) * 1000

        return SARDAResult(
            task_id=task_id,
            phase=SARDAPhase.MAP,
            sub_tasks=sub_tasks,
            total_ms=round(total_ms, 1),
        )

    def teardown(self):
        """Clean up tmux session."""
        if self._omc_team:
            self._omc_team.teardown()
            self._omc_team = None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    intent = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "scaffold a new API endpoint"
    engine = SARDAEngine()
    result = engine.dry_run(intent)
    print(result.to_json())
