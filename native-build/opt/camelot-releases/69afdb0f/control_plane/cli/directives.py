# SPDX-License-Identifier: MIT

"""Mode/cartridge directive translation and invocation."""

from __future__ import annotations

import os
from typing import Any

from control_plane.cli.constants import (
    ACTIVE_CARTRIDGE_PATH,
    BARE_SWARM_DIRECTIVE,
    BARE_SWARM_OBJECTIVE,
    MODE_CARTRIDGE_MAP,
)
from control_plane.cli.renderer import _progress
from control_plane.cli.tasks import _run_sarda, _run_task, _stream_sarda_progress


# ---------------------------------------------------------------------------
# Bare swarm directive
# ---------------------------------------------------------------------------

def _is_bare_swarm_directive(text: str) -> bool:
    return text.strip().upper() == BARE_SWARM_DIRECTIVE


# ---------------------------------------------------------------------------
# Mode / cartridge translation
# ---------------------------------------------------------------------------

def _translate_mode_directive(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped.startswith("//"):
        return None

    command, _, remainder = stripped.partition(" ")
    upper_command = command.upper()
    remainder = remainder.strip()

    if upper_command in {f"//{name}" for name in MODE_CARTRIDGE_MAP}:
        cartridge = upper_command[2:]
        if not remainder:
            return cartridge, ""
        if cartridge == "BRAINSTORM":
            return cartridge, f"LOAD:BRAINSTORM LOAD:CREATIVE LOAD:CRITICAL_THINKING {remainder}"
        if cartridge == "CRITICAL_THINKING":
            return cartridge, f"LOAD:CRITICAL_THINKING LOAD:COGNITIVE {remainder}"
        return cartridge, f"LOAD:{cartridge} {remainder}"

    if upper_command in {"//MODE", "//CARTRIDGE"}:
        if not remainder:
            return None
        mode_name, _, objective = remainder.partition(" ")
        cartridge = mode_name.strip().upper()
        if cartridge not in MODE_CARTRIDGE_MAP:
            return None
        objective = objective.strip() or ""
        if not objective:
            return cartridge, ""
        if cartridge == "BRAINSTORM":
            return cartridge, f"LOAD:BRAINSTORM LOAD:CREATIVE LOAD:CRITICAL_THINKING {objective}"
        if cartridge == "CRITICAL_THINKING":
            return cartridge, f"LOAD:CRITICAL_THINKING LOAD:COGNITIVE {objective}"
        return cartridge, f"LOAD:{cartridge} {objective}"

    return None


def _set_active_cartridge(cartridge: str) -> dict[str, Any]:
    os.makedirs(os.path.dirname(ACTIVE_CARTRIDGE_PATH), exist_ok=True)
    with open(ACTIVE_CARTRIDGE_PATH, "w", encoding="utf-8") as handle:
        handle.write(f"{cartridge}\n")
    return {
        "status": "ACTIVE_CARTRIDGE_SET",
        "cartridge": cartridge,
        "path": ACTIVE_CARTRIDGE_PATH,
    }


# ---------------------------------------------------------------------------
# Swarm invocation
# ---------------------------------------------------------------------------

async def _invoke_swarm_directive(*, json_mode: bool = False) -> dict[str, Any]:
    if not json_mode:
        _stream_sarda_progress(BARE_SWARM_OBJECTIVE, execute=True)
    output = await _run_sarda(BARE_SWARM_OBJECTIVE, execute=True)
    if output.get("status") == "CANCELLED" and output.get("reason") == "HITL_GATE refused":
        if not json_mode:
            _progress("fallback", "iron gate unavailable; reverting to plan mode", tone="warn")
            _stream_sarda_progress(BARE_SWARM_OBJECTIVE, execute=False)
        output = await _run_sarda(BARE_SWARM_OBJECTIVE, execute=False)
        output["fallback_reason"] = "HITL_GATE refused"
    return output


# ---------------------------------------------------------------------------
# Mode directive invocation
# ---------------------------------------------------------------------------

async def _invoke_mode_directive(
    cartridge: str,
    translated_intent: str,
) -> dict[str, Any]:
    def _extract_task_status(output: dict[str, Any]) -> str:
        status = str(output.get("status", "")).upper()
        if status:
            return status
        payload = output.get("payload")
        if isinstance(payload, dict):
            return str(payload.get("status", "")).upper()
        return ""

    async def _run_with_fallback(
        preferred_intent: str,
        *,
        preferred_agent_id: str | None = None,
        preferred_constraints: list[str] | None = None,
        preferred_extra_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output = await _run_task(
            preferred_intent,
            agent_id=preferred_agent_id,
            objective=objective,
            constraints=preferred_constraints,
            extra_parameters=preferred_extra_parameters,
        )
        status = _extract_task_status(output)
        if status not in {"FAILED", "CANCELLED", "ERROR"}:
            return output
        fallback = await _run_task(translated_intent)
        if isinstance(fallback, dict):
            fallback.setdefault("fallback_reason", status or "preferred_mode_failed")
            fallback.setdefault("fallback_from", cartridge)
        return fallback

    objective = translated_intent

    if cartridge == "BRAINSTORM":
        return await _run_with_fallback(
            "northstar war room objective",
            preferred_constraints=["privacy=0.0", "compute_tier=apex", "aspect=growth"],
            preferred_extra_parameters={
                "aspect": "growth",
                "compute_tier": "apex",
                "cartridge": "BRAINSTORM",
                "browser_isolation": "team",
                "multilogin_enabled": True,
            },
        )

    if cartridge == "RESEARCH":
        return await _run_with_fallback(
            "research investigate objective",
            preferred_agent_id="lady_apis",
            preferred_constraints=["privacy=0.0", "compute_tier=hybrid"],
        )

    if cartridge == "LEGAL":
        return await _run_with_fallback(
            "northstar war room objective",
            preferred_constraints=["privacy=0.0", "compute_tier=apex", "aspect=audit"],
            preferred_extra_parameters={
                "aspect": "audit",
                "compute_tier": "apex",
                "cartridge": "LEGAL",
                "browser_isolation": "team",
                "multilogin_enabled": True,
            },
        )

    if cartridge == "MARKETING":
        return await _run_with_fallback(
            "northstar war room objective",
            preferred_constraints=["privacy=0.0", "compute_tier=apex", "aspect=growth"],
            preferred_extra_parameters={
                "aspect": "growth",
                "compute_tier": "apex",
                "cartridge": "MARKETING",
                "browser_isolation": "team",
                "multilogin_enabled": True,
            },
        )

    if cartridge == "COGNITIVE":
        return await _run_with_fallback(
            "northstar war room objective",
            preferred_agent_id="sir_alex",
            preferred_constraints=["privacy=0.0", "compute_tier=apex", "aspect=architecture"],
            preferred_extra_parameters={
                "aspect": "architecture",
                "compute_tier": "apex",
                "cartridge": "COGNITIVE",
                "preferred_knight": "sir_alex",
                "browser_isolation": "team",
                "multilogin_enabled": True,
                "execution_target": "analysis_only",
            },
        )

    if cartridge == "CREATIVE":
        return await _run_with_fallback(
            "northstar war room objective",
            preferred_constraints=["privacy=0.0", "compute_tier=apex", "aspect=growth"],
            preferred_extra_parameters={
                "aspect": "growth",
                "compute_tier": "apex",
                "cartridge": "CREATIVE",
                "browser_isolation": "team",
                "multilogin_enabled": True,
            },
        )

    if cartridge == "CRITICAL_THINKING":
        return await _run_with_fallback(
            "northstar war room objective",
            preferred_agent_id="sir_alex",
            preferred_constraints=["privacy=0.0", "compute_tier=apex", "aspect=architecture"],
            preferred_extra_parameters={
                "aspect": "architecture",
                "compute_tier": "apex",
                "cartridge": "CRITICAL_THINKING",
                "preferred_knight": "sir_alex",
                "browser_isolation": "team",
                "multilogin_enabled": True,
                "execution_target": "analysis_only",
            },
        )

    return await _run_task(translated_intent)
