# SPDX-License-Identifier: MIT

"""Lady Mnemosyne Chimera harness.

Coordinates Cloudbrain custody, Hermes automation signals, Squire triage, and
Titan phial research expert assignments. This module is report-first: it may
publish Hermes messages when requested, but it does not mutate NotebookLM,
purge files, or execute queued remediation.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_plane.cloudbrain_mnemosyne_audit import run_lady_mnemosyne_cloudbrain_audit
from control_plane.hermes_bridge import HermesBus

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNTIME_DIR = REPO_ROOT / "03_VAULT" / "runtime_state"
PHIAL_ROOT = REPO_ROOT / "01_KERNEL" / "titan" / "phials"
ARTIFACT_PATH = RUNTIME_DIR / "lady_mnemosyne_chimera_latest.json"
REPORT_PATH = REPO_ROOT / "docs" / "reports" / "lady_mnemosyne_chimera_harness.md"

PHIAL_EXPERT_RULES: list[tuple[tuple[str, ...], dict[str, Any]]] = [
    (("tree_sitter", "semantic", "rag"), {
        "research_expert": "MERLIN_OMEGA",
        "supporting_knights": ["SIR_ALEX", "SIR_CODEX"],
        "research_lane": "code_understanding_and_reasoning",
    }),
    (("memory", "decay", "graph", "nano"), {
        "research_expert": "LADY_MNEMOSYNE",
        "supporting_knights": ["LORD_ARCHIVIST", "SIR_SENTINEL"],
        "research_lane": "memory_freshness_and_graph_recall",
    }),
    (("regex", "cleaner", "map"), {
        "research_expert": "SIR_HERMES",
        "supporting_knights": ["SIR_FORGE", "SIR_SENTINEL"],
        "research_lane": "automation_hygiene_and_operational_mapping",
    }),
]

DEFAULT_EXPERT = {
    "research_expert": "LADY_APIS",
    "supporting_knights": ["MERLIN_OMEGA", "SIR_CODEX"],
    "research_lane": "frontier_research_and_source_review",
}


@dataclass(frozen=True)
class PhialAssignment:
    phial: str
    path: str
    research_expert: str
    supporting_knights: list[str]
    research_lane: str
    objective: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "phial": self.phial,
            "path": self.path,
            "research_expert": self.research_expert,
            "supporting_knights": self.supporting_knights,
            "research_lane": self.research_lane,
            "objective": self.objective,
        }


def _load_notebooklm_bridge() -> Any | None:
    bridge_path = REPO_ROOT / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
    if not bridge_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("mnemosyne_chimera_notebooklm_bridge", bridge_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _phial_files(phial_root: Path = PHIAL_ROOT) -> list[Path]:
    if not phial_root.exists():
        return []
    return sorted(
        path for path in phial_root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _expert_for_phial(path: Path) -> dict[str, Any]:
    name = path.stem.lower()
    rel = str(path).lower()
    for keywords, expert in PHIAL_EXPERT_RULES:
        if any(keyword in name or keyword in rel for keyword in keywords):
            return dict(expert)
    return dict(DEFAULT_EXPERT)


def build_phial_assignments(phial_root: Path = PHIAL_ROOT) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    for path in _phial_files(phial_root):
        expert = _expert_for_phial(path)
        rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        objective = (
            f"Keep {path.stem} current with frontier methods for {expert['research_lane']}; "
            "capture risks, benchmark gaps, and upgrade candidates before implementation."
        )
        assignments.append(
            PhialAssignment(
                phial=path.stem,
                path=str(rel),
                research_expert=str(expert["research_expert"]),
                supporting_knights=list(expert["supporting_knights"]),
                research_lane=str(expert["research_lane"]),
                objective=objective,
            ).to_dict()
        )
    return assignments


def run_squire_swarm_triage(scan_path: Path, *, max_files: int = 500) -> dict[str, Any]:
    """Run bounded Squire swarm triage using SCAN/INDEX/GHOST/SWEEP/JUDGE."""
    from squires.ghost import triage as ghost_triage
    from squires.index import build_index
    from squires.judge import judge
    from squires.scan import scan
    from squires.sweep import sweep

    target = scan_path.resolve()
    records = list(scan(target))[:max_files]
    idx = build_index(iter(records))
    ghost_report = ghost_triage(iter(records))
    sweep_report = sweep(iter(records))
    verdict = judge(ghost_report, sweep_report, idx)
    critical = [flag for flag in ghost_report.flags if flag.severity == "critical"]
    return {
        "scan_path": str(target),
        "bounded": True,
        "max_files": max_files,
        "files_scanned": len(records),
        "risk_label": verdict.risk_label,
        "risk_score": round(float(verdict.risk_score), 2),
        "requires_hitl": bool(verdict.requires_hitl),
        "critical_flags": len(critical),
        "ghost_flags": len(ghost_report.flags),
        "sweep_flags": len(sweep_report.flags),
        "secret_samples": [f"{flag.file}:{flag.line}:{flag.kind}" for flag in critical[:5]],
        "recommendations": verdict.recommendations[:10],
    }


async def _living_synthesis(query: str) -> dict[str, Any]:
    bridge = _load_notebooklm_bridge()
    if bridge is None:
        return {"status": "UNAVAILABLE", "error": "notebooklm_bridge.py not found"}
    try:
        text = await bridge.async_synthesize(query, use_cache=False)
    except Exception as exc:  # pragma: no cover - network/session dependent
        return {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
    failed = text is None or str(text).startswith("[Living Notebook synthesis failed")
    return {
        "status": "FAILED" if failed else "COMPLETE",
        "query": query,
        "text": text,
        "source": "NotebookLM living system",
    }


def _publish_hermes(payload: dict[str, Any]) -> dict[str, Any]:
    bus = HermesBus()
    messages = [
        ("mnemosyne.chimera", {
            "source": "LADY_MNEMOSYNE",
            "state": payload["state"],
            "scan_path": payload["squire_triage"]["scan_path"],
            "phial_count": len(payload["phial_research_assignments"]),
        }),
        ("cloudbrain.library", {
            "source": "LADY_MNEMOSYNE",
            "owner": "LADY_MNEMOSYNE",
            "cloudbrain_state": payload["cloudbrain_audit"].get("state"),
            "queue_pending": payload["cloudbrain_audit"].get("queue", {}).get("pending"),
        }),
        ("phial.research", {
            "source": "LADY_MNEMOSYNE",
            "assignments": payload["phial_research_assignments"],
        }),
    ]
    published = []
    for channel, message in messages:
        published.append({"channel": channel, "ok": bus.publish(channel, message)})
    return {"published": published, "hermes_status": bus.status()}


def render_chimera_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Lady Mnemosyne Chimera Harness",
        "",
        f"- Generated UTC: {payload['generated_utc']}",
        f"- State: {payload['state']}",
        f"- Hermes Emitted: {payload['hermes'].get('enabled')}",
        f"- Squire Scan: {payload['squire_triage']['scan_path']}",
        f"- Squire Risk: {payload['squire_triage']['risk_score']}",
        f"- Phial Assignments: {len(payload['phial_research_assignments'])}",
        "",
        "## Cloudbrain",
        f"- Audit State: {payload['cloudbrain_audit'].get('state')}",
        f"- Queue Pending: {payload['cloudbrain_audit'].get('queue', {}).get('pending')}",
        "",
        "## Phial Research Experts",
    ]
    for item in payload["phial_research_assignments"]:
        lines.append(
            f"- {item['phial']} -> {item['research_expert']} "
            f"({item['research_lane']}); support: {', '.join(item['supporting_knights'])}"
        )
    lines.extend(["", "## Guardrail"])
    lines.append("Hermes messages are automation signals only; implementation remains explicit and provenance-gated.")
    lines.append("")
    return "\n".join(lines)


def run_mnemosyne_chimera(
    *,
    scan_path: str | Path = REPO_ROOT,
    max_files: int = 500,
    emit_hermes: bool = False,
    living_query: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    cloudbrain_audit = run_lady_mnemosyne_cloudbrain_audit(write=write)
    squire_triage = run_squire_swarm_triage(Path(scan_path), max_files=max_files)
    phial_assignments = build_phial_assignments()
    findings = []
    if squire_triage["risk_score"] >= 50:
        findings.append({
            "severity": "P1",
            "title": "Squire triage risk requires Sentinel review",
            "detail": f"risk_score={squire_triage['risk_score']}",
        })
    if cloudbrain_audit.get("state") != "MNEMOSYNE_READY":
        findings.append({
            "severity": "P1",
            "title": "Cloudbrain audit is not fully ready",
            "detail": str(cloudbrain_audit.get("state")),
        })
    state = "CHIMERA_READY" if not findings else "CHIMERA_TRIAGE_REQUIRED"
    payload: dict[str, Any] = {
        "schema": "camelot.lady-mnemosyne-chimera/v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "owner": "LADY_MNEMOSYNE",
        "automation_owner": "SIR_HERMES",
        "cloudbrain_audit": cloudbrain_audit,
        "squire_triage": squire_triage,
        "phial_research_assignments": phial_assignments,
        "findings": findings,
        "hermes": {"enabled": emit_hermes, "result": None},
        "living_system": {"enabled": bool(living_query), "result": None},
        "verification": [
            "python -m control_plane.camelot_cli cloudbrain mnemosyne-chimera --json --scan-path control_plane --max-files 500",
            "python -m control_plane.camelot_cli cloudbrain mnemosyne-audit --json",
            "python -m pytest tests/control_plane/test_mnemosyne_chimera.py",
        ],
    }
    if living_query:
        payload["living_system"]["result"] = asyncio.run(_living_synthesis(living_query))
    if emit_hermes:
        payload["hermes"]["result"] = _publish_hermes(payload)
    if write:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        REPORT_PATH.write_text(render_chimera_markdown(payload), encoding="utf-8")
        payload["artifact_path"] = str(ARTIFACT_PATH)
        payload["report_path"] = str(REPORT_PATH)
    return payload


if __name__ == "__main__":
    print(json.dumps(run_mnemosyne_chimera(), indent=2))
