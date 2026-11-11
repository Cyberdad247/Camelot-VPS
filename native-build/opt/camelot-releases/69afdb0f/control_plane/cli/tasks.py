# SPDX-License-Identifier: MIT

"""Task execution and progress streaming for the Camelot-OS CLI."""

from __future__ import annotations

import json
import time
from typing import Any

from control_plane.cli.constants import PROGRESS_DELAY
from control_plane.cli.iron_gate import _check_iron_gate
from control_plane.cli.renderer import _progress, _stream_print

VERBOSE_TELEMETRY = False


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------

async def _run_task(
    intent: str,
    *,
    agent_id: str | None = None,
    constraints: list[str] | None = None,
    objective: str | None = None,
    extra_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from control_plane.core.anya_gate import AnyaCompiler
    from control_plane.main import ControlPlane, TaskPayload
    from control_plane.infra.orchestration_state import route_persona

    # Phase 1: Anya's Ethereal Compilation (Triple-QFT)
    compiler = AnyaCompiler()
    raw_intent = intent
    preserve_cartridge_directive = raw_intent.lstrip().upper().startswith("LOAD:")
    if not preserve_cartridge_directive and compiler.pedagogy(intent):
        if VERBOSE_TELEMETRY:
            _stream_print("Anya [PEDAGOGY]: Intent is ambiguous. Renormalizing...", tone="warn")

    if preserve_cartridge_directive:
        titan_prompt, confidence = raw_intent, 1.0
    else:
        titan_prompt, confidence = compiler.compile(intent)
    if VERBOSE_TELEMETRY:
        _stream_print(f"Anya [COMPILE]: {titan_prompt} | ⚡ Confidence: {confidence*100:.0f}%", tone="dim")

    if confidence < 0.5:
        if VERBOSE_TELEMETRY:
            _stream_print("Anya [PEDAGOGY]: Intent clarity is low. Scaling to 1M token context for verification.", tone="warn")

    # Preserve explicit cartridge directives; otherwise use renormalized intent for routing logic.
    intent = raw_intent if preserve_cartridge_directive else compiler.renormalize(intent)

    # Phase 4: Iron Gate (High-risk check)
    if not _check_iron_gate(intent):
        return {"status": "CANCELLED", "reason": "HITL_GATE refused"}

    cp = ControlPlane()
    parameters: dict[str, Any] = dict(extra_parameters or {})
    if agent_id:
        parameters["agent_id"] = agent_id
    if objective:
        parameters["objective"] = objective
    persona = route_persona(intent)
    parameters["persona"] = persona["persona"]
    parameters["persona_reason"] = persona["reason"]
    if persona["persona"] == "Sir Alex":
        parameters.setdefault("preferred_knight", "sir_alex")
    task = TaskPayload(
        intent=intent,
        parameters=parameters,
        constraints=constraints or [],
    )
    try:
        return (await cp.process_task(task)).model_dump()
    except RuntimeError as exc:
        if "tmux not found" not in str(exc).lower():
            raise
        privacy = 0.0
        for constraint in constraints or []:
            if constraint.startswith("privacy="):
                try:
                    privacy = float(constraint.split("=", 1)[1])
                except ValueError:
                    privacy = 0.0
        plan = cp.sarda_plan(intent, privacy=privacy)
        return {
            "status": "FALLBACK_PLAN",
            "reason": str(exc),
            "task": intent,
            "result": json.loads(plan.to_json()),
        }


async def _run_sarda(
    intent: str,
    *,
    execute: bool,
    context: str = "",
    privacy: float = 0.0,
    timeout: int = 120,
) -> dict[str, Any]:
    from control_plane.main import ControlPlane

    if execute:
        # Phase 4: Iron Gate (High-risk check)
        if not _check_iron_gate(intent):
            return {"status": "CANCELLED", "reason": "HITL_GATE refused"}

    cp = ControlPlane()
    if execute:
        result = cp.sarda_execute(intent, context=context, privacy=privacy, timeout=timeout)
    else:
        result = cp.sarda_plan(intent, privacy=privacy)
    return json.loads(result.to_json())


def _run_team_self_test(
    *,
    worker_id: str,
    prompt: str,
    timeout: int,
) -> dict[str, Any]:
    from control_plane.infra.bio_swarm_runtime import (
        preflight_bio_swarm,
        run_bio_swarm_once,
    )

    if worker_id.lower() in {"bio-swarm", "bioswarm", "swarm-spawner"}:
        preflight = preflight_bio_swarm()
        if preflight.get("status") != "PREFLIGHT_PASS":
            return {
                "status": "FAILED",
                "target": worker_id,
                "runtime": "bio-swarm",
                "preflight": preflight,
            }
        release = run_bio_swarm_once(fixture=True, timeout=timeout)
        return {
            "status": "PASSED" if release.get("verdict") == "PASS" else "FAILED",
            "target": worker_id,
            "runtime": "bio-swarm",
            "preflight": preflight,
            "release": release,
        }

    from control_plane.main import ControlPlane

    cp = ControlPlane()
    return cp.team_self_test(
        worker_id=worker_id,
        prompt=prompt,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Progress streaming
# ---------------------------------------------------------------------------

def _stream_task_progress(
    intent: str,
    *,
    objective: str | None = None,
    constraints: list[str] | None = None,
) -> None:
    lower = intent.lower()
    _progress("analyze", f"intent: {intent}")

    if any(word in lower for word in {"cloudbrain", "notebook", "memory status"}):
        _progress("route", "cloudbrain status path", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("fetch", "loading cloudbrain topology", tone="info")
        return

    if any(word in lower for word in {"memory", "context", "recall"}):
        _progress("route", "long-term memory path", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("fetch", "querying Appwrite-backed memory", tone="info")
        return

    if any(word in lower for word in {"research", "deep dive", "deep-dive", "investigate"}):
        _progress("route", "research agency path", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("scout", f"objective: {objective or intent}", tone="info")
        time.sleep(PROGRESS_DELAY)
        if constraints:
            _progress("guard", f"constraints: {', '.join(constraints)}", tone="warn")
        tier = next((c.split("=", 1)[1] for c in (constraints or []) if c.startswith("compute_tier=")), None)
        if tier:
            _progress("tier", f"compute tier: {tier}", tone="accent")
        _progress("synthesize", "assembling agency brief", tone="info")
        return

    if any(word in lower for word in {"northstar", "war room", "brainstorm"}):
        _progress("route", "northstar war-room path", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("align", f"objective: {objective or intent}", tone="info")
        time.sleep(PROGRESS_DELAY)
        if constraints:
            _progress("guard", f"constraints: {', '.join(constraints)}", tone="warn")
        tier = next((c.split("=", 1)[1] for c in (constraints or []) if c.startswith("compute_tier=")), None)
        if tier:
            _progress("tier", f"compute tier: {tier}", tone="accent")
        aspect = next((c.split("=", 1)[1] for c in (constraints or []) if c.startswith("aspect=")), None)
        if aspect:
            _progress("aspect", f"mission aspect: {aspect}", tone="accent")
        _progress("chimera", "running 3-round audit topology", tone="info")
        return

    if any(word in lower for word in {"blueprint", "resource constrained", "development blueprint"}):
        _progress("route", "development blueprint path", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("scope", f"objective: {objective or intent}", tone="info")
        time.sleep(PROGRESS_DELAY)
        if constraints:
            _progress("guard", f"constraints: {', '.join(constraints)}", tone="warn")
        tier = next((c.split("=", 1)[1] for c in (constraints or []) if c.startswith("compute_tier=")), None)
        if tier:
            _progress("tier", f"default tier: {tier}", tone="accent")
        _progress("shape", "optimizing phased delivery for constrained resources", tone="info")
        return

    if any(word in lower for word in {"precise mode", "nano-knight", "nano knight", "swarm"}):
        _progress("route", "precise-mode swarm path", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("forge", f"objective: {objective or intent}", tone="info")
        time.sleep(PROGRESS_DELAY)
        if constraints:
            _progress("guard", f"constraints: {', '.join(constraints)}", tone="warn")
        tier = next((c.split("=", 1)[1] for c in (constraints or []) if c.startswith("compute_tier=")), None)
        if tier:
            _progress("tier", f"compute tier: {tier}", tone="accent")
        _progress("symmetry", "matching Nano-Knights to omniroute LLM lanes", tone="info")
        _progress("capacity", "computing safe ephemeral swarm capacity", tone="info")
        return

    if any(word in lower for word in {"eldergod", "elder god forge", "eldergod forge"}):
        _progress("route", "elderGod forge path", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("scope", f"objective: {objective or intent}", tone="info")
        time.sleep(PROGRESS_DELAY)
        if constraints:
            _progress("guard", f"constraints: {', '.join(constraints)}", tone="warn")
        tier = next((c.split("=", 1)[1] for c in (constraints or []) if c.startswith("compute_tier=")), None)
        if tier:
            _progress("tier", f"default tier: {tier}", tone="accent")
        _progress("forge", "igniting the elderGod forge", tone="info")
        return

    _progress("route", "control-plane task path", tone="info")
    time.sleep(PROGRESS_DELAY)
    _progress("execute", "delegating to control plane", tone="info")


def _stream_sarda_progress(
    intent: str,
    *,
    execute: bool,
    context: str = "",
    privacy: float = 0.0,
) -> None:
    _progress("analyze", f"sarda intent: {intent}")
    _progress("map", "decomposing into sub-tasks (Merlin)", tone="info")
    time.sleep(PROGRESS_DELAY)

    # Phase 3: Swarm Zoology (Metal Execution)
    _progress("swarm", "deploying 150-token Nano-Knights", tone="accent")
    _progress("formica", "Ants: parallel file rewriting [Δ]", tone="dim")
    _progress("pongid", "Gorillas: API heavy-lifting", tone="dim")
    _progress("castor", "Beavers: WASM/Docker isolation [▩]", tone="dim")
    time.sleep(PROGRESS_DELAY)

    if any(term in intent.lower() for term in {"research", "deep dive", "deep-dive", "investigate"}):
        _progress("research", "augmenting with research agency context", tone="info")
        time.sleep(PROGRESS_DELAY)
    if execute:
        _progress("dispatch", "sending tasks to routed engines", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("reduce", "merging outputs (Lukas)", tone="info")
        time.sleep(PROGRESS_DELAY)
        _progress("critique", "running final validation (Sir Sentinel)", tone="info")
    else:
        _progress("plan", "previewing routes without execution", tone="info")
