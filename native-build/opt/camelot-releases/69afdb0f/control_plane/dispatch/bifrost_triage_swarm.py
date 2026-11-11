# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Bifrost Triage Swarm — runnable swarm-knight orchestrator for the 5 audit fixes.

Drives the remediation defined in
`docs/reports/bifrost_triage_2026-06-24/{blueprint,tasks,verification}.md`.

Reuses the KineticSwarm role model (control_plane.kinetic_swarm) for assignment, but
dispatches for **real** through the Bifrost dispatcher (control_plane.bifrost.Bifrost) —
bypassing KineticSwarm's simulated `_execute_via_agent` stub.

Apply mode is propose + HITL gate: knights produce unified diffs that are staged to
`03_VAULT/runtime_state/bifrost_triage/<task_id>.diff`. Nothing touches source until the
operator approves with `--apply <task_id>`.

CLI:
    python -m control_plane.bifrost_triage_swarm --plan          # dry-run roster + dependency order
    python -m control_plane.bifrost_triage_swarm --run           # dispatch all, stage diffs, PAUSE
    python -m control_plane.bifrost_triage_swarm --run --task T1  # dispatch one task
    python -m control_plane.bifrost_triage_swarm --apply T1       # apply staged diff + verify
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
TRIAGE_DIR = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "bifrost_triage"
LEDGER_PATH = TRIAGE_DIR / "run_ledger.jsonl"

# Swarm role → dispatchable Bifrost terminal (kinetic_swarm.py role model).
# apis/galahad/lancelot are swarm-only agents with no terminal; mapped to the closest
# dispatchable knight. The executor needs no LLM (it applies patches) → "__local__".
ROLE_TO_TERMINAL: dict[str, str] = {
    "coordinator": "sir_rustclaw",
    "forge":       "sir_forge",
    "architect":   "sir_openclaw",
    "sensor":      "sir_alex",
    "verifier":    "sir_sentinel",
    "executor":    "__local__",
}

AUDIT_CONTEXT = (
    "You are remediating the CAMELOT-OS Bifrost dispatch core "
    "(control_plane/dispatch/bifrost.py). A 2026-06-24 audit found dead dispatch branches, a "
    "docstring promising a non-existent `http` strategy, registry/model drift, a "
    "misleading integration ledger, and an unaudited security surface. Produce a MINIMAL, "
    "surgical change — no broad refactors. OUTPUT A SINGLE UNIFIED DIFF (git apply format) "
    "and nothing else."
)


@dataclass
class TriageTask:
    id: str
    title: str
    role: str                     # swarm role (key of ROLE_TO_TERMINAL)
    files: list[str]
    depends_on: list[str] = field(default_factory=list)
    acceptance: str = ""
    verify_cmd: str = ""          # bash assertion; exit 0 = pass


TASK_PLAN: list[TriageTask] = [
    TriageTask(
        id="T1",
        title="Remove dead ollama + hermes dispatch branches",
        role="forge",
        files=["control_plane/dispatch/bifrost.py"],
        depends_on=[],
        acceptance="No `ollama`/`hermes` strategy branch or `_stream_ollama`/`_stream_hermes` "
                   "method remains; docstring lists only live strategies.",
        verify_cmd=(
            "! grep -qE 'strategy == \"(ollama|hermes)\"' control_plane/dispatch/bifrost.py "
            "&& ! grep -qE 'def _stream_(ollama|hermes)\\b' control_plane/dispatch/bifrost.py"
        ),
    ),
    TriageTask(
        id="T3",
        title="Reconcile _TERMINAL_MODEL with the switchboard registry",
        role="forge",
        files=["control_plane/dispatch/bifrost.py"],
        depends_on=["T1"],
        acceptance="Every terminal in switchboard.TERMINAL_REGISTRY is mapped in "
                   "_TERMINAL_MODEL or documented as `# fallback: <id>`.",
        verify_cmd="python -m py_compile control_plane/dispatch/bifrost.py",
    ),
    TriageTask(
        id="T2",
        title="Implement the documented http strategy",
        role="architect",
        files=["control_plane/dispatch/bifrost.py"],
        depends_on=["T3"],
        acceptance="`http` strategy declared in _ENGINE_DISPATCH, handled in stream(), and "
                   "served by _stream_http(); octavian/sonus no longer fall through to cliproxy.",
        verify_cmd=(
            "grep -qE '\"http\"' control_plane/dispatch/bifrost.py "
            "&& grep -qE 'strategy == \"http\"' control_plane/dispatch/bifrost.py "
            "&& grep -qE 'def _stream_http\\b' control_plane/dispatch/bifrost.py"
        ),
    ),
    TriageTask(
        id="T4",
        title="Make bifrost_integration ledger honest",
        role="architect",
        files=["control_plane/dispatch/bifrost_integration.py"],
        depends_on=["T1"],
        acceptance="No `✓ Forged` line emitted by a no-op `_forge_*`; datetime.utcnow() replaced "
                   "with datetime.now(timezone.utc).",
        verify_cmd=(
            "! grep -q '✓ Forged' control_plane/dispatch/bifrost_integration.py "
            "&& ! grep -qE 'datetime\\.utcnow\\(\\)' control_plane/dispatch/bifrost_integration.py"
        ),
    ),
    TriageTask(
        id="T5",
        title="Security pass on the dispatch core (audit-only)",
        role="verifier",
        files=["control_plane/dispatch/bifrost.py"],
        depends_on=[],
        acceptance="Findings appendix V5 in verification.md filled with severity + recommendation "
                   "for CLIPROXY_KEY default, SSRF, prompt injection, and caller auth.",
        verify_cmd="test -f docs/reports/bifrost_triage_2026-06-24/verification.md",
    ),
]


# ── Dependency ordering ─────────────────────────────────────────────────────

def topo_order(plan: list[TriageTask]) -> list[TriageTask]:
    """Kahn's algorithm; stable on declaration order for ties."""
    by_id = {t.id: t for t in plan}
    indeg = {t.id: len([d for d in t.depends_on if d in by_id]) for t in plan}
    ordered: list[TriageTask] = []
    ready = [t for t in plan if indeg[t.id] == 0]
    while ready:
        t = ready.pop(0)
        ordered.append(t)
        for other in plan:
            if t.id in other.depends_on:
                indeg[other.id] -= 1
                if indeg[other.id] == 0 and other not in ordered and other not in ready:
                    ready.append(other)
    if len(ordered) != len(plan):
        raise ValueError("dependency cycle in TASK_PLAN")
    return ordered


# ── Ledger ──────────────────────────────────────────────────────────────────

def _ledger(event: dict) -> None:
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with LEDGER_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


# ── Plan view ───────────────────────────────────────────────────────────────

def print_plan() -> None:
    print("Bifrost Triage Swarm — plan (no dispatch)\n")
    print(f"  {'task':5} {'role':12} {'terminal':14} {'deps':10} title")
    print("  " + "─" * 74)
    for t in topo_order(TASK_PLAN):
        term = ROLE_TO_TERMINAL.get(t.role, "?")
        deps = ",".join(t.depends_on) or "-"
        print(f"  {t.id:5} {t.role:12} {term:14} {deps:10} {t.title}")
    print()
    # roster cross-check against the kinetic swarm role model (best-effort, offline-safe)
    try:
        from control_plane.kinetic_swarm import get_kinetic_swarm
        swarm = get_kinetic_swarm()
        print(f"  KineticSwarm roster: {len(swarm.members)} members "
              f"({', '.join(sorted(swarm.role_assignments))})")
    except Exception as e:  # roster optional — plan still valid without it
        print(f"  (KineticSwarm roster unavailable: {type(e).__name__})")
    print(f"\n  Diffs stage to: {TRIAGE_DIR}")
    print("  Apply mode: propose + HITL gate (use --apply <task_id> after review)")


# ── Knight prompt ───────────────────────────────────────────────────────────

def build_prompt(task: TriageTask) -> str:
    excerpts = []
    for rel in task.files:
        p = CAMELOT_HOME / rel
        if p.exists():
            head = "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[:80])
            excerpts.append(f"--- {rel} (first 80 lines) ---\n{head}")
    body = "\n\n".join(excerpts) if excerpts else "(target files not found locally)"
    return (
        f"{AUDIT_CONTEXT}\n\n"
        f"TASK {task.id}: {task.title}\n"
        f"FILES: {', '.join(task.files)}\n"
        f"ACCEPTANCE: {task.acceptance}\n\n"
        f"Current source:\n{body}\n\n"
        f"Return ONLY a unified diff that satisfies the acceptance criteria."
    )


# ── Dispatch (real Bifrost) ─────────────────────────────────────────────────

async def dispatch_task(task: TriageTask) -> str:
    terminal = ROLE_TO_TERMINAL.get(task.role, "")
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRIAGE_DIR / f"{task.id}.diff"

    if terminal == "__local__":
        _ledger({"task": task.id, "event": "skipped", "reason": "local executor role"})
        print(f"  [{task.id}] role={task.role} → local (no dispatch)")
        return ""

    from control_plane.bifrost import Bifrost  # lazy: avoids heavy import for --plan

    print(f"  [{task.id}] → {terminal} ({task.role}) dispatching…")
    t0 = time.time()
    chunks: list[str] = []
    try:
        async for chunk in Bifrost().stream(terminal, build_prompt(task)):
            chunks.append(chunk)
    except Exception as e:
        _ledger({"task": task.id, "event": "dispatch_error", "terminal": terminal,
                 "error": f"{type(e).__name__}: {e}"})
        print(f"  [{task.id}] dispatch error: {type(e).__name__}: {e}")
        return ""

    proposal = "".join(chunks)
    out_path.write_text(proposal, encoding="utf-8")
    _ledger({"task": task.id, "event": "proposed", "terminal": terminal,
             "bytes": len(proposal), "latency_ms": round((time.time() - t0) * 1000),
             "diff_path": str(out_path)})
    print(f"  [{task.id}] staged proposal → {out_path} ({len(proposal)} bytes)")
    return proposal


async def run_all(only: str | None = None) -> None:
    plan = topo_order(TASK_PLAN)
    if only:
        plan = [t for t in plan if t.id == only] or plan
    print("Bifrost Triage Swarm — dispatch (propose only)\n")
    for task in plan:
        await dispatch_task(task)
    print("\n  HITL GATE: review staged diffs in")
    print(f"    {TRIAGE_DIR}")
    print("  then apply each with:  python -m control_plane.bifrost_triage_swarm --apply <task_id>")


# ── Apply (post-approval) ───────────────────────────────────────────────────

def apply_task(task_id: str) -> int:
    task = next((t for t in TASK_PLAN if t.id == task_id), None)
    if task is None:
        print(f"unknown task: {task_id}")
        return 2
    diff_path = TRIAGE_DIR / f"{task_id}.diff"
    if not diff_path.exists() or diff_path.stat().st_size == 0:
        print(f"no staged diff for {task_id} at {diff_path} — run --run first")
        return 2

    apply = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(diff_path)],
        cwd=str(CAMELOT_HOME), capture_output=True, text=True,
    )
    if apply.returncode != 0:
        _ledger({"task": task_id, "event": "apply_failed", "stderr": apply.stderr[:500]})
        print(f"  [{task_id}] git apply failed:\n{apply.stderr}")
        return 1
    print(f"  [{task_id}] applied {diff_path.name}")

    verify = subprocess.run(
        ["bash", "-c", task.verify_cmd], cwd=str(CAMELOT_HOME),
        capture_output=True, text=True,
    )
    status = "PASS" if verify.returncode == 0 else "FAIL"
    _ledger({"task": task_id, "event": "verified", "status": status,
             "returncode": verify.returncode})
    print(f"  [{task_id}] verification: {status}")
    if status == "FAIL":
        print(verify.stdout + verify.stderr)
    return 0 if status == "PASS" else 1


# ── CLI ─────────────────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bifrost triage swarm orchestrator")
    ap.add_argument("--plan", action="store_true", help="show roster + dependency order, no dispatch")
    ap.add_argument("--run", action="store_true", help="dispatch tasks, stage diffs, then pause")
    ap.add_argument("--task", help="restrict --run to a single task id (e.g. T1)")
    ap.add_argument("--apply", metavar="TASK_ID", help="apply a staged diff and verify")
    args = ap.parse_args(argv)

    if args.apply:
        return apply_task(args.apply)
    if args.run:
        asyncio.run(run_all(args.task))
        return 0
    # default / --plan
    print_plan()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
