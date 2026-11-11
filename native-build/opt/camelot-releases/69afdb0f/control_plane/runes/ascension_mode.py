# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_plane.lady_m import SquireTriage
from control_plane.versioning import get_dynamic_version

SCHEMA = "camelot.ascension-mode/v1"
DEFAULT_RUNTIME_DIR = Path("03_VAULT/runtime_state")
DEFAULT_OUTPUT = DEFAULT_RUNTIME_DIR / "ascension_mode_latest.json"

ASCENSION_ARTIFACTS = (
    "CloudBrain_Link.md",
    "camelot_cloudbrain_v701_manifest.json",
    "knowledge_crystal",
    "squire_index_latest.json",
    "squire_vector_latest.json",
    "nano_swarm_runtime_latest.json",
    "bio_swarm_runtime_latest.json",
    "bio_swarm_release_latest.json",
    "symbiotic_maintenance_latest.json",
    "heimdall_bifrost_governance_latest.json",
    "hermes_omniroute_orchestrator_latest.json",
    "knight_configuration_latest.json",
    "excalibur_telemetry.json",
)


@dataclass(frozen=True)
class ArtifactSignal:
    name: str
    path: str
    exists: bool
    kind: str
    size: int | None
    modified_utc: str | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mtime_utc(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _artifact_signal(root: Path, name: str) -> ArtifactSignal:
    path = root / DEFAULT_RUNTIME_DIR / name
    exists = path.exists()
    return ArtifactSignal(
        name=name,
        path=str(path),
        exists=exists,
        kind="directory" if path.is_dir() else "file" if path.is_file() else "missing",
        size=path.stat().st_size if path.is_file() else None,
        modified_utc=_mtime_utc(path),
    )


def collect_cloudbrain_signals(root: Path) -> list[dict[str, Any]]:
    return [signal.__dict__ for signal in (_artifact_signal(root, name) for name in ASCENSION_ARTIFACTS)]


def score_ascension(*, artifact_count: int, artifact_total: int, risk_score: int, version_source: str) -> dict[str, Any]:
    artifact_score = int((artifact_count / max(artifact_total, 1)) * 45)
    risk_score_component = max(0, 30 - min(risk_score, 100) // 4)
    version_component = 15 if version_source == "git" else 8
    governance_component = 10
    score = min(100, artifact_score + risk_score_component + version_component + governance_component)
    if score >= 80 and risk_score < 50:
        state = "ASCENSION_READY"
    elif score >= 60:
        state = "ASCENSION_STAGING"
    else:
        state = "ASCENSION_BLOCKED"
    return {
        "score": score,
        "state": state,
        "components": {
            "artifacts": artifact_score,
            "risk": risk_score_component,
            "version": version_component,
            "governance": governance_component,
        },
    }


def recommended_actions(payload: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    triage = payload["lady_m"]["triage"]
    missing = [item["name"] for item in payload["cloudbrain"]["artifacts"] if not item["exists"]]
    if triage["risk_score"] >= 50:
        actions.append("Run Sentinel review before enabling execution-bearing ascension workflows.")
    if missing:
        actions.append(f"Refresh missing Cloudbrain artifacts: {', '.join(missing[:5])}.")
    if payload["version"]["source"] != "git":
        actions.append("Restore git-backed dynamic versioning before publication.")
    if not actions:
        actions.append("Keep Ascension mode report-first; promote execution only behind HITL approval.")
    return actions


def build_ascension_report(root: Path, *, scan_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    scan_target = (scan_path or root).resolve()
    version = get_dynamic_version()
    triage = SquireTriage().run(scan_target)
    artifacts = collect_cloudbrain_signals(root)
    present = sum(1 for item in artifacts if item["exists"])
    score = score_ascension(
        artifact_count=present,
        artifact_total=len(artifacts),
        risk_score=triage.risk_score,
        version_source=version.source,
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_utc": _now(),
        "root": str(root),
        "mode": "ASCENSION_ANALYSIS",
        "version": {
            "label": version.label,
            "source": version.source,
            "detail": version.detail,
        },
        "lady_m": {
            "role": "governance_triage",
            "triage": {
                "path": triage.path,
                "risk_score": triage.risk_score,
                "secrets_detected": len(triage.secrets),
                "dead_files": len(triage.dead_files),
                "recommendations": triage.recommendations,
                "report_hash": triage.sha256,
            },
        },
        "cloudbrain": {
            "artifact_total": len(artifacts),
            "artifact_present": present,
            "artifacts": artifacts,
        },
        "score": score,
    }
    payload["recommendations"] = recommended_actions(payload)
    return payload


def write_ascension_report(
    root: Path,
    *,
    scan_path: Path | None = None,
    output: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    root = root.resolve()
    out = output if output.is_absolute() else root / output
    payload = build_ascension_report(root, scan_path=scan_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload | {"output_path": str(out)}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Camelot Ascension mode readiness.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--scan-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = write_ascension_report(args.root, scan_path=args.scan_path, output=args.output)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
