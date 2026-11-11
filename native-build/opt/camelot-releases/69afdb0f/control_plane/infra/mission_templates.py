# SPDX-License-Identifier: MIT

"""Canonical Mission Templates and Objective Scoring (Tracks C4, C5).

Defines reusable, battle-tested mission templates for the 5 canonical Northstar aspects:
1. research: Deep-Dive Domain Investigation & Hypothesis Verification
2. architecture: Zero-Trust System Boundary & Topology Design
3. audit: Forensic Codebase & Security Policy Audit
4. operations: Production Deployment & High-Availability Operations
5. growth: Ecosystem Expansion & Capability Scaling

Also provides standardized objective scoring:
- Confidence Score: (0.0 - 1.0)
- Risk Score: (0.0 - 1.0)
- Completeness Score: (0.0 - 1.0)
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ObjectiveScoring(BaseModel):
    """Standardized objective scoring across Northstar and Development Blueprint."""
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in findings and strategy")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Operational, architectural, and security risk")
    completeness_score: float = Field(..., ge=0.0, le=1.0, description="Completeness of coverage across tracks/phases")
    rationale: dict[str, str] = Field(default_factory=dict, description="Detailed rationale per score")

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_score": round(self.confidence_score, 2),
            "risk_score": round(self.risk_score, 2),
            "completeness_score": round(self.completeness_score, 2),
            "confidence_pct": f"{int(round(self.confidence_score * 100))}%",
            "risk_pct": f"{int(round(self.risk_score * 100))}%",
            "completeness_pct": f"{int(round(self.completeness_score * 100))}%",
            "rationale": self.rationale,
        }


class MissionTemplate(BaseModel):
    """Canonical reusable mission template definition."""
    name: str = Field(..., description="Template identifier: research, architecture, audit, operations, growth")
    title: str = Field(..., description="Human-readable title")
    aspect: str = Field(..., description="Northstar aspect: research, architecture, audit, operations, growth")
    cartridge: str = Field(..., description="Recommended cartridge: ANT, BEAVER, HAWK, SPIDER, COGNITIVE, ORACLE")
    compute_tier: str = Field(..., description="Recommended tier: kinetic, hybrid, apex")
    browser_isolation: str = Field(..., description="Recommended isolation: stealth, team, agency")
    description: str = Field(..., description="Purpose and scope summary")
    default_objective: str = Field(..., description="Default actionable objective statement")
    recommended_knights: list[str] = Field(..., description="Assigned Knights of the Round Table")
    chimera_rounds: list[dict[str, str]] = Field(..., description="Three-phase CHIMERA deliberation plan")
    deliverables: list[str] = Field(..., description="Concrete output artifacts")
    success_criteria: list[str] = Field(..., description="Objective acceptance gates")


CANONICAL_MISSION_TEMPLATES: dict[str, MissionTemplate] = {
    "research": MissionTemplate(
        name="research",
        title="Deep-Dive Domain Investigation & Hypothesis Verification",
        aspect="research",
        cartridge="ANT",
        compute_tier="hybrid",
        browser_isolation="team",
        description="Explores domain sources, discovers clustering overlaps, pressure-tests hypothesis claims, and synthesizes strategic briefs.",
        default_objective="Investigate target domain architecture, map operational requirements, and verify integration constraints.",
        recommended_knights=["lady_apis", "merlin_omega", "sir_boris", "sir_codex"],
        chimera_rounds=[
            {
                "round": "round_1",
                "owner": "Lady Apis",
                "title": "Signal Discovery & Foraging",
                "goal": "Scan primary documentation, verify citations, and extract high-density structural evidence.",
            },
            {
                "round": "round_2",
                "owner": "Merlin / Videneptus",
                "title": "Hypothesis Stress Testing",
                "goal": "Cross-examine contradictory claims against historical benchmarks and architectural invariants.",
            },
            {
                "round": "round_3",
                "owner": "Sir Boris",
                "title": "Synthesis & Deliverable Weaving",
                "goal": "Distill high-signal synthesis into a bounded actionable brief and next-step execution plan.",
            },
        ],
        deliverables=[
            "Clustered Source Synthesis",
            "Contradiction & Evidence Matrix",
            "Strategic Implementation Brief",
        ],
        success_criteria=[
            ">=90% verified source citation coverage",
            "Zero unaddressed contradictory evidence",
            "Concrete phased next steps with resource bounds",
        ],
    ),
    "architecture": MissionTemplate(
        name="architecture",
        title="Zero-Trust System Boundary & Topology Design",
        aspect="architecture",
        cartridge="HAWK",
        compute_tier="hybrid",
        browser_isolation="team",
        description="Designs sovereign component boundaries, interface contracts, resource budgets, and zero-drift fail-soft paths.",
        default_objective="Design sovereign system boundaries, formalize typed schema contracts, and enforce zero-drift isolation.",
        recommended_knights=["merlin_omega", "sir_boris", "sir_codex", "sir_gideon"],
        chimera_rounds=[
            {
                "round": "round_1",
                "owner": "Sir Boris",
                "title": "Topology & Interface Mapping",
                "goal": "Map subsystem components, define unidirectional data flows, and establish isolation boundaries.",
            },
            {
                "round": "round_2",
                "owner": "Merlin_Omega",
                "title": "Invariants & Failure Mode Analysis",
                "goal": "Formalize mathematical proofs, bounded capacity ceilings, and fail-soft degradation trees.",
            },
            {
                "round": "round_3",
                "owner": "Sir Codex",
                "title": "Typed Schema & Contract Locking",
                "goal": "Emit RFC 8785 canonical contracts, generate cross-boundary bindings, and pin cryptographic locks.",
            },
        ],
        deliverables=[
            "Component Topology & Dataflow Map",
            "Typed Schema Contract Specifications",
            "Fail-Soft Recovery & Invariant Matrix",
        ],
        success_criteria=[
            "100% typed interface boundaries with zero unvalidated inputs",
            "Strict compliance with Rule 7 zero-hotpath bare-metal doctrine",
            "Formal rollback and circuit breaker specifications",
        ],
    ),
    "audit": MissionTemplate(
        name="audit",
        title="Forensic Codebase & Security Policy Audit",
        aspect="audit",
        cartridge="COGNITIVE",
        compute_tier="apex",
        browser_isolation="agency",
        description="Performs 13-gate forensic analysis, taint flow tracking, secret exposure defense, and regression immunity checks.",
        default_objective="Perform zero-trust taint analysis, verify iron gates, and check regression immunity.",
        recommended_knights=["sir_sentinel", "sir_gideon", "sir_ghost", "arthur_omega"],
        chimera_rounds=[
            {
                "round": "round_1",
                "owner": "Sir Sentinel",
                "title": "Taint Flow & Perimeter Inspection",
                "goal": "Analyze Program Dependence Graph (PDG), untrusted ingress sanitization, and secret leaks.",
            },
            {
                "round": "round_2",
                "owner": "Sir Gideon",
                "title": "13-Gate Forensic Evaluation",
                "goal": "Independently evaluate diff integrity, test validity, dependency risk, and accessibility baselines.",
            },
            {
                "round": "round_3",
                "owner": "Arthur_Omega",
                "title": "Sovereign Ratification Gate",
                "goal": "Verify Ed25519 cryptographic seals, sign audit verdict, and append to TenantReceiptChain.",
            },
        ],
        deliverables=[
            "13-Gate Forensic Audit Report",
            "Taint Propagation & Secret Containment Log",
            "Remediation Action Plan & Verification Receipts",
        ],
        success_criteria=[
            "Zero unmasked credentials or secret exposure",
            "100% test gate compliance across all security suites",
            "Deterministic cryptographic signature verification",
        ],
    ),
    "operations": MissionTemplate(
        name="operations",
        title="Production Deployment & High-Availability Operations",
        aspect="operations",
        cartridge="SPIDER",
        compute_tier="hybrid",
        browser_isolation="stealth",
        description="Architects zero-downtime deployment choreography, circuit breaker policies, eBPF scarcity controls, and runbooks.",
        default_objective="Establish production release runbooks, configure scarcity daemon thresholds, and verify circuit breakers.",
        recommended_knights=["hermes_prime", "sir_codex", "sir_heimdall", "scarcity_guardian"],
        chimera_rounds=[
            {
                "round": "round_1",
                "owner": "Hermes_Prime",
                "title": "Deployment Choreography & Health Checks",
                "goal": "Define rolling migration sequencing, automated health checks, and Canary verification gates.",
            },
            {
                "round": "round_2",
                "owner": "Scarcity Guardian",
                "title": "Resource Scarcity & PSI Throttling",
                "goal": "Configure 8GB hard cap, Samsung S26 Ultra audio slice, and Linux eBPF PSI hysteresis thresholds.",
            },
            {
                "round": "round_3",
                "owner": "Sir Heimdall",
                "title": "Bifrost Perimeter & Circuit Breakers",
                "goal": "Verify mTLS boundaries, Tailscale mesh connectivity, and remote timeout/circuit breaker thresholds.",
            },
        ],
        deliverables=[
            "Production Deployment & Rollback Runbook",
            "Hardware Scarcity & PSI Throttling Configuration",
            "Bifrost Perimeter Health & Circuit Breaker Limits",
        ],
        success_criteria=[
            "Sub-second failover and degraded dependency fast-fail",
            "Zero Docker footprint (100% bare-metal systemd/WASM/Rust)",
            "All 6 production Iron Gates confirmed green",
        ],
    ),
    "growth": MissionTemplate(
        name="growth",
        title="Ecosystem Expansion & Capability Scaling",
        aspect="growth",
        cartridge="ANT",
        compute_tier="kinetic",
        browser_isolation="team",
        description="Evaluates cross-node mesh capacity, operator velocity, friction points, and multi-tenant scaling patterns.",
        default_objective="Scale multi-node mesh capacity, evaluate developer velocity, and streamline onboarding.",
        recommended_knights=["sir_alex", "knight_strategos", "lady_guinevere", "sir_stitch"],
        chimera_rounds=[
            {
                "round": "round_1",
                "owner": "Sir Alex",
                "title": "DAG Bottleneck & Flow Analysis",
                "goal": "Profile task execution graphs, identify serialization bottlenecks, and measure agent latency.",
            },
            {
                "round": "round_2",
                "owner": "Knight Strategos",
                "title": "Multi-Node Mesh Capacity Planning",
                "goal": "Model workload distribution across Tailscale fleet nodes and evaluate memory headroom scaling.",
            },
            {
                "round": "round_3",
                "owner": "Lady Guinevere",
                "title": "Operator HUD & Interface Resonance",
                "goal": "Refine luxury brutalist UI tokens, ensure sub-100ms HUD updates, and polish telemetry streaming.",
            },
        ],
        deliverables=[
            "Ecosystem Growth & Capacity Forecast",
            "DAG Orchestration Optimization Matrix",
            "Operator Velocity & HUD Enhancement Roadmap",
        ],
        success_criteria=[
            "Identified and prioritized top 3 execution bottlenecks",
            "Quantified memory and latency scaling projections",
            "Zero UI/UX regressions against Tailwind v4 and Luxora Gold standards",
        ],
    ),
}


def list_mission_templates() -> list[MissionTemplate]:
    """Return all 5 canonical mission templates."""
    return list(CANONICAL_MISSION_TEMPLATES.values())


def get_mission_template(name: str) -> MissionTemplate | None:
    """Lookup a canonical mission template by name (case-insensitive)."""
    if not name:
        return None
    return CANONICAL_MISSION_TEMPLATES.get(name.strip().lower())


def resolve_template_parameters(
    template_name: str,
    custom_objective: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve mission parameters by overlaying custom objective and overrides onto template defaults."""
    tmpl = get_mission_template(template_name)
    if not tmpl:
        raise ValueError(
            f"Unknown mission template '{template_name}'. "
            f"Available templates: {', '.join(CANONICAL_MISSION_TEMPLATES.keys())}"
        )

    objective = (custom_objective or "").strip() or tmpl.default_objective
    params: dict[str, Any] = {
        "template": tmpl.name,
        "template_title": tmpl.title,
        "objective": objective,
        "aspect": tmpl.aspect,
        "cartridge": tmpl.cartridge,
        "compute_tier": tmpl.compute_tier,
        "browser_isolation": tmpl.browser_isolation,
        "recommended_knights": tmpl.recommended_knights,
        "chimera_rounds": tmpl.chimera_rounds,
        "deliverables": tmpl.deliverables,
        "success_criteria": tmpl.success_criteria,
    }
    if overrides:
        for k, v in overrides.items():
            if v is not None:
                params[k] = v
    return params


def calculate_northstar_scoring(
    *,
    compute_tier: str,
    aspect: str,
    memory_count: int,
    browser_isolation: str,
    multilogin_enabled: bool,
    assigned_knights: list[str],
    mission_tracks: list[dict[str, Any]],
) -> ObjectiveScoring:
    """Calculate objective confidence, risk, and completeness scoring for Northstar outputs."""
    # 1. Confidence Score (0.0 to 1.0)
    tier_weights = {"kinetic": 0.72, "hybrid": 0.86, "apex": 0.95}
    base_conf = tier_weights.get(compute_tier.lower(), 0.80)
    if memory_count > 0:
        base_conf += min(memory_count * 0.02, 0.05)
    if browser_isolation.lower() in {"team", "agency"}:
        base_conf += 0.03
    conf = max(0.10, min(1.0, base_conf))

    # 2. Risk Score (0.0 to 1.0)
    tier_risk = {"kinetic": 0.18, "hybrid": 0.32, "apex": 0.48}
    base_risk = tier_risk.get(compute_tier.lower(), 0.30)
    if not multilogin_enabled:
        base_risk += 0.25  # unisolated browser profile increases session contamination risk
    if aspect.lower() == "audit":
        base_risk = max(0.10, base_risk - 0.08)  # audit aspect explicitly hardens security
    risk = max(0.05, min(0.95, base_risk))

    # 3. Completeness Score (0.0 to 1.0)
    base_comp = 0.78
    if len(mission_tracks) >= 3:
        base_comp += 0.08
    if len(assigned_knights) >= 3:
        base_comp += 0.08
    comp = max(0.10, min(1.0, base_comp))

    rationale = {
        "confidence": (
            f"Evaluated at {int(conf*100)}% based on {compute_tier} compute tier, "
            f"{memory_count} long-term memory records, and {browser_isolation} browser isolation."
        ),
        "risk": (
            f"Evaluated at {int(risk*100)}% with multilogin {'enabled' if multilogin_enabled else 'DISABLED'} "
            f"under {aspect} mission posture."
        ),
        "completeness": (
            f"Evaluated at {int(comp*100)}% across {len(mission_tracks)} tracks "
            f"with {len(assigned_knights)} assigned Knights."
        ),
    }

    return ObjectiveScoring(
        confidence_score=conf,
        risk_score=risk,
        completeness_score=comp,
        rationale=rationale,
    )


def calculate_blueprint_scoring(
    *,
    compute_tier: str,
    budget_mode: str,
    team_size: int,
    horizon_days: int,
    prioritize_local_first: bool,
    execution_phases: list[dict[str, Any]],
) -> ObjectiveScoring:
    """Calculate objective confidence, risk, and completeness scoring for Development Blueprint outputs."""
    # 1. Confidence Score (0.0 to 1.0)
    tier_conf = {"kinetic": 0.76, "hybrid": 0.88, "apex": 0.96}
    base_conf = tier_conf.get(compute_tier.lower(), 0.82)
    if prioritize_local_first:
        base_conf += 0.04  # sovereign local-first reduces external outage risk
    conf = max(0.10, min(1.0, base_conf))

    # 2. Risk Score (0.0 to 1.0)
    budget_risk = {"lean": 0.16, "balanced": 0.34, "aggressive": 0.62}
    base_risk = budget_risk.get(budget_mode.lower(), 0.28)
    if team_size <= 2:
        base_risk = max(0.08, base_risk - 0.04)  # tight operator loop, minimal coordination overhead
    elif team_size > 8:
        base_risk += 0.14  # distributed coordination friction
    risk = max(0.05, min(0.95, base_risk))

    # 3. Completeness Score (0.0 to 1.0)
    base_comp = 0.80
    if len(execution_phases) >= 3:
        base_comp += 0.08
    if horizon_days <= 30:
        base_comp += 0.06  # tight horizon promotes verifiable milestone boundaries
    comp = max(0.10, min(1.0, base_comp))

    rationale = {
        "confidence": (
            f"Evaluated at {int(conf*100)}% based on {compute_tier} tier planning "
            f"with local-first priority set to {prioritize_local_first}."
        ),
        "risk": (
            f"Evaluated at {int(risk*100)}% under {budget_mode} budget mode "
            f"with a team size of {team_size} operator(s)."
        ),
        "completeness": (
            f"Evaluated at {int(comp*100)}% spanning {len(execution_phases)} delivery phases "
            f"over a {horizon_days}-day execution horizon."
        ),
    }

    return ObjectiveScoring(
        confidence_score=conf,
        risk_score=risk,
        completeness_score=comp,
        rationale=rationale,
    )
