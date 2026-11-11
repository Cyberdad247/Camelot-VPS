# SPDX-License-Identifier: MIT

"""
TriageScore — Dynamic Confidence-Based Decision Making.

NOTE (P1-T04 disambiguation): this is the *confidence scorer* — exported via
`get_triage_scorer()` / `calculate_triage_score()` and consumed by
test_validation.py and test_phase_f.py. It is distinct from
`factory_lane.TriageScore`, the APEE v7.0 risk-entropy dataclass used by
`anya_gate._stage_triage`. Not orphaned: this module has live test consumers and
imports cleanly. Keep the two separate — they answer different questions
(confidence-to-proceed vs. risk-entropy / HITL-tier).

Replaces static thresholds with intelligent confidence scoring:
  < 0.15: HIGH confidence → AUTO mode (no human approval needed)
  0.15-0.55: MEDIUM confidence → Proceed with monitoring
  > 0.55: LOW confidence → Escalate to Sovereign Commander (HITL)

Scores based on:
  - Historical success rate
  - System health status
  - Resource availability
  - Network conditions
  - Temporal patterns
  - Agent capabilities
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class ConfidenceLevel(str, Enum):
    """Confidence level classification."""
    CRITICAL_LOW = "critical_low"  # < 0.15
    MEDIUM_LOW = "medium_low"  # 0.15-0.35
    MEDIUM = "medium"  # 0.35-0.55
    MEDIUM_HIGH = "medium_high"  # 0.55-0.75
    HIGH = "high"  # > 0.75


class TriageAction(str, Enum):
    """Action based on triage score."""
    AUTO_PROCEED = "auto_proceed"  # No approval needed
    PROCEED_MONITORED = "proceed_monitored"  # Monitor closely
    ESCALATE_HITL = "escalate_hitl"  # Request human approval
    DENY = "deny"  # Block operation


@dataclass
class ScoreComponent:
    """Individual score component."""
    name: str
    value: float  # 0.0-1.0
    weight: float  # 0.0-1.0
    reason: str = ""


@dataclass
class TriageScoreResult:
    """Triage scoring result."""
    operation_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    overall_score: float = 0.0  # 0.0-1.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    recommended_action: TriageAction = TriageAction.PROCEED_MONITORED
    components: List[ScoreComponent] = field(default_factory=list)
    reasoning: str = ""
    estimated_risk: str = "medium"  # low, medium, high, critical


class TriageScorer:
    """Dynamic confidence scoring for operations."""

    def __init__(self):
        """Initialize triage scorer."""
        self.history: Dict[str, List[float]] = {}  # operation_id -> scores
        self.success_rates: Dict[str, float] = {}  # operation_type -> success_rate
        self.thresholds = {
            "auto_proceed": 0.15,  # Score below this = auto
            "escalate_hitl": 0.55,  # Score above this = escalate
        }

    async def calculate_triage_score(
        self,
        operation_id: str,
        operation_type: str,
        system_health: Dict[str, float],
        capability_match: float = 1.0,
        resource_availability: float = 1.0,
        network_conditions: float = 1.0,
        temporal_pattern: float = 1.0,
    ) -> TriageScoreResult:
        """Calculate triage score for operation."""
        components: List[ScoreComponent] = []

        # Component 1: Historical success rate
        success_rate = self.success_rates.get(operation_type, 0.9)
        components.append(ScoreComponent(
            name="Historical Success Rate",
            value=success_rate,
            weight=0.25,
            reason=f"{operation_type} has {success_rate*100:.1f}% success rate"
        ))

        # Component 2: System health
        cpu_health = system_health.get("cpu_utilization", 0.5)
        mem_health = system_health.get("memory_utilization", 0.5)
        disk_health = system_health.get("disk_utilization", 0.5)
        health_score = 1.0 - ((cpu_health + mem_health + disk_health) / 3)
        components.append(ScoreComponent(
            name="System Health",
            value=health_score,
            weight=0.25,
            reason=f"CPU:{cpu_health*100:.0f}%, RAM:{mem_health*100:.0f}%, Disk:{disk_health*100:.0f}%"
        ))

        # Component 3: Capability match
        components.append(ScoreComponent(
            name="Capability Match",
            value=capability_match,
            weight=0.20,
            reason=f"Agent {capability_match*100:.0f}% capable for task"
        ))

        # Component 4: Resource availability
        components.append(ScoreComponent(
            name="Resource Availability",
            value=resource_availability,
            weight=0.15,
            reason=f"{resource_availability*100:.0f}% resources available"
        ))

        # Component 5: Network conditions
        components.append(ScoreComponent(
            name="Network Conditions",
            value=network_conditions,
            weight=0.10,
            reason=f"Network: {network_conditions*100:.0f}% optimal"
        ))

        # Component 6: Temporal pattern
        components.append(ScoreComponent(
            name="Temporal Pattern",
            value=temporal_pattern,
            weight=0.05,
            reason=f"Time-of-day factor: {temporal_pattern*100:.0f}%"
        ))

        # Calculate weighted score
        overall_score = sum(c.value * c.weight for c in components)

        # Determine confidence level
        if overall_score < 0.15:
            confidence_level = ConfidenceLevel.CRITICAL_LOW
            action = TriageAction.AUTO_PROCEED
            risk = "low"
        elif overall_score < 0.35:
            confidence_level = ConfidenceLevel.MEDIUM_LOW
            action = TriageAction.PROCEED_MONITORED
            risk = "low"
        elif overall_score < 0.55:
            confidence_level = ConfidenceLevel.MEDIUM
            action = TriageAction.PROCEED_MONITORED
            risk = "medium"
        elif overall_score < 0.75:
            confidence_level = ConfidenceLevel.MEDIUM_HIGH
            action = TriageAction.ESCALATE_HITL
            risk = "high"
        else:
            confidence_level = ConfidenceLevel.HIGH
            action = TriageAction.ESCALATE_HITL
            risk = "critical"

        # Generate reasoning
        reasoning = self._generate_reasoning(overall_score, components, action)

        result = TriageScoreResult(
            operation_id=operation_id,
            overall_score=overall_score,
            confidence_level=confidence_level,
            recommended_action=action,
            components=components,
            reasoning=reasoning,
            estimated_risk=risk,
        )

        # Store in history
        if operation_type not in self.history:
            self.history[operation_type] = []
        self.history[operation_type].append(overall_score)

        return result

    def _generate_reasoning(
        self,
        score: float,
        components: List[ScoreComponent],
        action: TriageAction,
    ) -> str:
        """Generate human-readable reasoning."""
        lines = []

        # Score interpretation
        if score < 0.15:
            lines.append("✓ CRITICAL CONFIDENCE: All systems optimal, auto-proceed recommended")
        elif score < 0.35:
            lines.append("✓ HIGH CONFIDENCE: System in good state, proceed with light monitoring")
        elif score < 0.55:
            lines.append("⚠ MEDIUM CONFIDENCE: Mixed signals detected, proceed with caution")
        elif score < 0.75:
            lines.append("⚠ LOW CONFIDENCE: Risk factors detected, escalate for review")
        else:
            lines.append("✗ CRITICAL RISK: Multiple risk factors, escalation required")

        # Top risk factors
        components_sorted = sorted(components, key=lambda c: c.value)
        if components_sorted:
            lines.append("\nLowest scoring factors:")
            for comp in components_sorted[:3]:
                lines.append(f"  • {comp.name}: {comp.value*100:.0f}% ({comp.reason})")

        # Action recommendation
        lines.append(f"\nRecommended action: {action.value}")

        return "\n".join(lines)

    async def update_success_rate(self, operation_type: str, success: bool) -> None:
        """Update success rate for operation type."""
        if operation_type not in self.success_rates:
            self.success_rates[operation_type] = 0.9

        current_rate = self.success_rates[operation_type]
        alpha = 0.1  # Learning rate

        if success:
            new_rate = current_rate * (1 - alpha) + 1.0 * alpha
        else:
            new_rate = current_rate * (1 - alpha) + 0.0 * alpha

        self.success_rates[operation_type] = new_rate

    def get_triage_statistics(self) -> Dict[str, any]:
        """Get triage scoring statistics."""
        return {
            "operations_scored": sum(len(v) for v in self.history.values()),
            "operation_types": len(self.history),
            "success_rates": self.success_rates,
            "average_scores": {
                op_type: sum(scores) / len(scores) if scores else 0
                for op_type, scores in self.history.items()
            }
        }

    def get_confidence_distribution(self) -> Dict[str, int]:
        """Get distribution of confidence levels."""
        distribution = {level.value: 0 for level in ConfidenceLevel}

        for scores in self.history.values():
            for score in scores:
                if score < 0.15:
                    distribution[ConfidenceLevel.CRITICAL_LOW.value] += 1
                elif score < 0.35:
                    distribution[ConfidenceLevel.MEDIUM_LOW.value] += 1
                elif score < 0.55:
                    distribution[ConfidenceLevel.MEDIUM.value] += 1
                elif score < 0.75:
                    distribution[ConfidenceLevel.MEDIUM_HIGH.value] += 1
                else:
                    distribution[ConfidenceLevel.HIGH.value] += 1

        return distribution


# ── Module-level singleton ────────────────────────────────────────────────

_scorer: Optional[TriageScorer] = None


def get_triage_scorer() -> TriageScorer:
    """Get or create shared TriageScorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = TriageScorer()
    return _scorer


async def calculate_triage_score(
    operation_id: str,
    operation_type: str,
    system_health: Dict[str, float],
    **kwargs
) -> TriageScoreResult:
    """Calculate triage score for operation."""
    scorer = get_triage_scorer()
    return await scorer.calculate_triage_score(
        operation_id=operation_id,
        operation_type=operation_type,
        system_health=system_health,
        **kwargs
    )
