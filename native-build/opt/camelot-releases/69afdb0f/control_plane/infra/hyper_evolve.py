# SPDX-License-Identifier: MIT

"""Guarded hyper-evolution workflow for the Camelot control plane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger_sync import append_provenance_entry
from .provenance import ProvenanceManager, VerificationRun

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_ROOT = REPO_ROOT / "03_VAULT" / "training" / "configs"
LEARNINGS_PATH = CONFIG_ROOT / "learnings.md"
SKILLS_REGISTRY_PATH = CONFIG_ROOT / "skills.md"
AGENTS_REGISTRY_PATH = CONFIG_ROOT / "agents.md"

TITANIUM_LAWS = (
    "Do not bypass human approval for high-risk or destructive operations.",
    "Do not disable provenance, verification, or audit logging.",
    "Do not weaken security boundaries, secret handling, or credential hygiene.",
    "Do not silently expand permissions or execution scope.",
    "Do not mutate production state without an explicit operator directive.",
)

SHATTERPOINTS = (
    "security regression",
    "ledger drift",
    "unbounded scope expansion",
    "secret leakage",
    "destructive autonomy",
    "verification bypass",
    "context rot",
    "operator confusion",
    "non-reproducible behavior",
    "cost ceiling violation",
)

BLOCKLIST = {
    "bypass hitl": "Violates Titanium Laws by removing human approval.",
    "disable hitl": "Violates Titanium Laws by removing human approval.",
    "skip verification": "Violates Titanium Laws by removing verification.",
    "disable verification": "Violates Titanium Laws by removing verification.",
    "disable ledger": "Violates Titanium Laws by removing provenance logging.",
    "skip ledger": "Violates Titanium Laws by removing provenance logging.",
    "force push": "Encourages destructive git behavior.",
    "rm -rf": "Introduces destructive autonomy.",
    "delete without approval": "Attempts destructive autonomy without consent.",
    "exfiltrate": "Introduces secret leakage risk.",
    "ignore secrets": "Weakens credential hygiene.",
    "disable security": "Creates a security regression.",
    "auto-merge without review": "Expands production mutation scope without review.",
}


@dataclass
class EvolutionPaths:
    learnings: Path
    skills: Path
    agents: Path


def ensure_evolution_files() -> EvolutionPaths:
    """Create evolution registry files on demand with stable headers."""
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)

    if not LEARNINGS_PATH.exists():
        LEARNINGS_PATH.write_text(
            "# Camelot Learnings Log\n\n"
            "This file records execution friction, proposed fixes, and review outcomes.\n",
            encoding="utf-8",
        )

    if not SKILLS_REGISTRY_PATH.exists():
        SKILLS_REGISTRY_PATH.write_text(
            "# Camelot Shared Skills Registry\n\n"
            "Approved evolution rules are appended here after governance review.\n",
            encoding="utf-8",
        )

    if not AGENTS_REGISTRY_PATH.exists():
        AGENTS_REGISTRY_PATH.write_text(
            "# Camelot Agent Registry\n\n"
            "Reserved for curated agent operating rules and role notes.\n",
            encoding="utf-8",
        )

    return EvolutionPaths(
        learnings=LEARNINGS_PATH,
        skills=SKILLS_REGISTRY_PATH,
        agents=AGENTS_REGISTRY_PATH,
    )


def append_learning(
    *,
    agent: str,
    objective: str,
    failures: list[str],
    learning: str,
    proposal: str,
) -> Path:
    """Append a learning record to the shared learnings log."""
    ensure_evolution_files()
    timestamp = datetime.now(timezone.utc).isoformat()
    block = [
        "---",
        f"## {timestamp} :: {agent}",
        f"- Objective: {objective}",
        "- Failures:",
    ]
    block.extend(f"  - {item}" for item in failures)
    block.append(f"- Learning: {learning}")
    block.append(f"- Proposed Mutation: {proposal}")
    LEARNINGS_PATH.open("a", encoding="utf-8").write("\n".join(block) + "\n")
    return LEARNINGS_PATH


def review_mutation(*, proposal: str, learning: str, verification: list[str]) -> dict[str, Any]:
    """Apply a fixed governance review before promoting any mutation."""
    normalized = f"{proposal}\n{learning}".lower()
    failures: list[str] = []

    for needle, reason in BLOCKLIST.items():
        if needle in normalized:
            failures.append(reason)

    if len(proposal.strip()) < 20:
        failures.append("Proposal is too short to be a stable operating rule.")

    if not verification:
        failures.append("At least one verification step is required before promotion.")

    failures = list(dict.fromkeys(failures))
    verdict = "PASS" if not failures else "FAIL"
    return {
        "verdict": verdict,
        "approved": not failures,
        "failures": failures,
        "titanium_laws": list(TITANIUM_LAWS),
        "shatterpoints": list(SHATTERPOINTS),
    }


def promote_mutation(
    *,
    agent: str,
    objective: str,
    learning: str,
    proposal: str,
    verification: list[str],
    scope: list[str],
    actor: str,
    tag: str = "[HYPER_EVOLVE]",
) -> dict[str, Any]:
    """Record a learning, run the review gate, and promote approved rules."""
    paths = ensure_evolution_files()
    review = review_mutation(proposal=proposal, learning=learning, verification=verification)

    if review["approved"]:
        timestamp = datetime.now(timezone.utc).isoformat()
        block = [
            "---",
            f"## {timestamp} :: {agent}",
            f"- Objective: {objective}",
            f"- Learning: {learning}",
            f"- Approved Rule: {proposal}",
            "- Verification:",
        ]
        block.extend(f"  - `{item}`" for item in verification)
        if scope:
            block.append("- Scope:")
            block.extend(f"  - {item}" for item in scope)
        paths.skills.open("a", encoding="utf-8").write("\n".join(block) + "\n")

        ledger = append_provenance_entry(
            title=f"Hyper-Evolve mutation approved for {agent}",
            actor=actor,
            scope=scope or [str(paths.skills.relative_to(REPO_ROOT))],
            verification=verification,
            tag=tag,
        )
    else:
        ledger = append_provenance_entry(
            title=f"Hyper-Evolve mutation rejected for {agent}",
            actor=actor,
            scope=scope or [str(paths.learnings.relative_to(REPO_ROOT))],
            verification=verification or ["review gate"],
            tag=f"{tag}[REZERO]",
        )

    run = VerificationRun(
        run_id=f"evolve_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        operator=actor,
        command=f"evolve {agent}",
        results={
            "objective": objective,
            "learning": learning,
            "proposal": proposal,
            "review": review,
            "ledger": ledger,
        },
        success=review["approved"],
    )
    ProvenanceManager().log_verification(run)

    return {
        "status": "APPROVED" if review["approved"] else "REJECTED",
        "agent": agent,
        "objective": objective,
        "learning_path": str(paths.learnings),
        "skills_registry_path": str(paths.skills),
        "agents_registry_path": str(paths.agents),
        "review": review,
        "ledger": ledger,
    }
