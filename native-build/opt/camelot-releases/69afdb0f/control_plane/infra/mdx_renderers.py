# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
MDX Renderers — /visual-plan and /visual-recap (v9000.14, P3-T03 / P3-T04).
===========================================================================
Convert a kinetic_loop.KineticResult into a validated Agent-Native MDX document:

    visual_plan(result)   → kind="visual-plan"   (pre/at-dispatch intent plan)
    visual_recap(result)  → kind="visual-recap"  (post-execution summary)

Both return a dict conforming to mdx_schema.MDX_JSON_SCHEMA; render to text with
mdx_schema.render_mdx.

Run as module:
    python -m control_plane.mdx_renderers --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import sys
from typing import Any

from .mdx_schema import render_mdx, validate_mdx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _risk_band(result: Any) -> str:
    triage = getattr(getattr(result, "job", None), "triage", None)
    if triage is None:
        return "AUTO"
    if getattr(triage, "priority", "") == "CRITICAL":
        return "CRITICAL"
    return getattr(triage, "hitl_tier", "AUTO")


def _stage_diagram(stages: list[str]) -> str:
    """Mermaid flow of the fired stages (fired = solid, link to next)."""
    if not stages:
        return "graph LR; TRIAGE"
    nodes = " --> ".join(stages)
    return f"graph LR; {nodes}"


def visual_plan(result: Any) -> dict[str, Any]:
    """Build a /visual-plan MDX document from a KineticResult (P3-T03)."""
    intent = getattr(result, "intent", "")
    job = getattr(result, "job", None)
    apee = getattr(result, "apee", None)
    knight = getattr(job, "assigned_knight", "unknown")
    risk = _risk_band(result)
    colmad = getattr(apee, "colmad_verdict", None)

    summary = f"Route to **{knight}** (risk **{risk}**). Intent: {intent}"
    if colmad is not None:
        summary += (f" · ColMAD: {getattr(colmad, 'verdict', '?')} "
                    f"({getattr(colmad, 'approvals', 0)}/3)")

    blocks: list[dict[str, Any]] = [
        {"type": "Summary", "text": summary, "risk": risk},
        {"type": "Diagram", "format": "mermaid",
         "source": "graph LR; TRIAGE --> PLAN --> APPROVE --> EXECUTE --> VERIFY --> RECORD"},
    ]

    directive = getattr(getattr(apee, "titan", None), "directive", None)
    if directive:
        blocks.append({"type": "FileMap", "files": [
            {"path": "<directive>", "action": "create", "note": directive[:80]},
        ]})

    sources = []
    domain = getattr(getattr(apee, "enrich", None), "domain", None)
    if domain:
        sources.append({"name": "Anya enrich domain", "ref": str(domain)})
    sources.append({"name": "FirnFlow World Tree", "ref": "L1"})
    blocks.append({"type": "ContextSources", "sources": sources})

    job_id = getattr(job, "job_id", "job")
    blocks.append({"type": "ApprovalButton", "action_id": job_id,
                   "label": "Approve & Execute", "tier": risk})

    doc = {"version": "9000.14", "kind": "visual-plan",
           "title": f"Plan · {intent[:48]}", "blocks": blocks}
    return doc


def visual_recap(result: Any) -> dict[str, Any]:
    """Build a /visual-recap MDX document from a completed KineticResult (P3-T04)."""
    intent = getattr(result, "intent", "")
    stages = [getattr(s, "value", str(s)) for s in getattr(result, "stages_fired", [])]
    complete = getattr(result, "complete", False)
    validated = getattr(result, "validated", False)
    halted = getattr(result, "halted_at", None)
    issues = getattr(result, "validation_issues", []) or []
    prov = getattr(result, "provenance_ref", None)

    outcome = "✅ completed" if complete else (
        f"🛑 halted at {getattr(halted, 'value', halted)}" if halted else "⚠️ incomplete")
    verify = "passed" if validated else "failed"
    summary = (f"Run {outcome}. Verification: **{verify}**. "
               f"Stages fired: {len(stages)}/6. Provenance: {prov or 'none'}.")
    if issues:
        summary += f" Issues: {issues}"

    risk = _risk_band(result)
    blocks: list[dict[str, Any]] = [
        {"type": "Summary", "text": summary, "risk": risk},
        {"type": "Diagram", "format": "mermaid", "source": _stage_diagram(stages)},
    ]
    out = getattr(result, "output", None)
    if out:
        blocks.append({"type": "ContextSources",
                       "sources": [{"name": "Executor output", "ref": out[:80]}]})

    doc = {"version": "9000.14", "kind": "visual-recap",
           "title": f"Recap · {intent[:48]}", "blocks": blocks}
    return doc


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("MDX Renderers self-test (P3-T03 / P3-T04)")
    from .kinetic_loop import run_sync

    # A completed run -> both plan and recap are valid MDX.
    res = run_sync("build a small status dashboard", auto_approve=True)

    plan = visual_plan(res)
    ok_p, err_p = validate_mdx(plan)
    check(f"visual-plan is valid MDX (errors={err_p})", ok_p)
    check("visual-plan kind", plan["kind"] == "visual-plan")
    check("visual-plan has ApprovalButton",
          any(b["type"] == "ApprovalButton" for b in plan["blocks"]))
    check("visual-plan renders mermaid", "```mermaid" in render_mdx(plan))

    recap = visual_recap(res)
    ok_r, err_r = validate_mdx(recap)
    check(f"visual-recap is valid MDX (errors={err_r})", ok_r)
    check("visual-recap kind", recap["kind"] == "visual-recap")
    check("visual-recap reports completion",
          "completed" in recap["blocks"][0]["text"])

    # A halted CRITICAL run -> recap reflects the halt and is still valid MDX.
    halted = run_sync("delete all production databases and drop every table",
                      auto_approve=False)
    hrecap = visual_recap(halted)
    ok_h, _ = validate_mdx(hrecap)
    check("halted recap is valid MDX", ok_h)
    check("halted recap shows halt", "halted" in hrecap["blocks"][0]["text"])
    check("halted plan marks CRITICAL", visual_plan(halted)["blocks"][0]["risk"] == "CRITICAL")

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — mdx_renderers")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    from .kinetic_loop import run_sync
    r = run_sync("build a status dashboard", auto_approve=True)
    print(render_mdx(visual_plan(r)))
