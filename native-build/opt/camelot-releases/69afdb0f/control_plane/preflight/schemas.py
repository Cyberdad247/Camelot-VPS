# SPDX-License-Identifier: MIT

"""Dataclasses + YAML parser for preflight catalog and run artifacts.

Per docs/architecture/VFS_PREFLIGHT_DESIGN.md §5.3 (per-check JSON) and §5.4
(run manifest). CONFIRMED-only gate at the catalog-load layer: any other
expected_evidence_class value is rejected pre-execution.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
import hashlib

import yaml


EvidenceClass = Literal["CONFIRMED", "REJECTED"]
CommandType = Literal["python_module", "shell"]
HaltDecision = Literal["continue", "block_boot", "await_hitl"]
HitlTier = Literal["AUTO", "PROMPT", "HUMAN_GATE"]


class CatalogParseError(ValueError):
    """Catalog YAML did not validate against the schema."""


@dataclass(frozen=True)
class CheckSpec:
    sequence: int
    id: str
    display_name: str
    command_type: CommandType
    command: list[str]
    timeout_s: int = 30
    retry: int = 0
    expected_evidence_class: EvidenceClass = "CONFIRMED"
    hitl_on_fail: bool = False
    remediation_hint: Optional[str] = None

    @classmethod
    def from_yaml_text(cls, text: str) -> "CheckSpec":
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise CatalogParseError(f"yaml parse error: {e}") from e
        if not isinstance(raw, dict):
            raise CatalogParseError("check yaml must be a mapping")

        for required in ("sequence", "id", "display_name", "command_type", "command"):
            if required not in raw:
                raise CatalogParseError(
                    f"missing required field '{required}'"
                )

        seq_raw = raw["sequence"]
        # YAML's leading-zero-style sequence values (010, 020, ...)
        # are parsed as strings because PyYAML refuses the octal
        # interpretation (octal digits 0-7 only). The spec mandates
        # stride-10 readability, so accept strings here and coerce.
        if isinstance(seq_raw, bool) or not isinstance(
            seq_raw, (int, str)
        ):
            raise CatalogParseError(
                f"sequence must be a positive int (or numeric string), "
                f"got {seq_raw!r}"
            )
        try:
            seq = int(seq_raw)
        except (TypeError, ValueError) as e:
            raise CatalogParseError(
                f"sequence must be coercible to int, got {seq_raw!r}"
            ) from e
        if seq <= 0:
            raise CatalogParseError(
                f"sequence must be positive, got {seq}"
            )

        cmd_type = raw["command_type"]
        if cmd_type not in ("python_module", "shell"):
            raise CatalogParseError(
                f"command_type must be 'python_module' or 'shell', "
                f"got {cmd_type!r}"
            )

        cmd = raw["command"]
        if not isinstance(cmd, list) or not all(
            isinstance(c, str) for c in cmd
        ):
            raise CatalogParseError(
                "command must be a list of strings"
            )

        ec = raw.get("expected_evidence_class", "CONFIRMED")
        if ec != "CONFIRMED":
            # Per VFS_PREFLIGHT_DESIGN §5.3 the catalog is CONFIRMED-only;
            # any other value is rejected at load (no surprise later).
            raise CatalogParseError(
                "expected_evidence_class must be CONFIRMED "
                "(CONFIRMED-only gate), got " + repr(ec)
            )

        try:
            retry = int(raw.get("retry", 0))
        except (TypeError, ValueError) as e:
            raise CatalogParseError(
                f"retry must be an int, got {raw.get('retry')!r}"
            ) from e
        if retry < 0 or retry > 2:
            raise CatalogParseError(
                f"retry must be 0..2, got {retry}"
            )

        try:
            timeout_s = int(raw.get("timeout_s", 30))
        except (TypeError, ValueError) as e:
            raise CatalogParseError(
                f"timeout_s must be an int, got {raw.get('timeout_s')!r}"
            ) from e
        if timeout_s <= 0:
            raise CatalogParseError(
                f"timeout_s must be positive, got {timeout_s}"
            )

        return cls(
            sequence=seq,
            id=str(raw["id"]),
            display_name=str(raw["display_name"]),
            command_type=cmd_type,
            command=cmd,
            timeout_s=timeout_s,
            retry=retry,
            expected_evidence_class=ec,
            hitl_on_fail=bool(raw.get("hitl_on_fail", False)),
            remediation_hint=raw.get("remediation_hint"),
        )


@dataclass
class CheckResult:
    schema: Literal["camelot.preflight.check/v1"] = "camelot.preflight.check/v1"
    run_id: str = ""
    check_id: str = ""
    display_name: str = ""
    command_observed: list[str] = field(default_factory=list)
    command_raw: str = ""
    exit_code: int = -1
    started_at: str = ""
    duration_ms: int = 0
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""
    evidence_class: EvidenceClass = "REJECTED"
    evidence_assertion: dict = field(default_factory=dict)
    hitl_required: bool = False
    halt_decision: HaltDecision = "continue"
    advisor_finding: bool = False
    rejection_reasons: list[str] = field(default_factory=list)
    remediation_hint: Optional[str] = None
    artifact_path: str = ""

    def to_json_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunManifest:
    schema: Literal["camelot.preflight.run/v1"] = "camelot.preflight.run/v1"
    run_id: str = ""
    started_at: str = ""
    ended_at: str = ""
    total_ms: int = 0
    checks_total: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    checks_skipped: int = 0
    halted_at_check: Optional[str] = None
    halt_decision: HaltDecision = "continue"
    scene_hash: str = ""
    catalog_hash: str = ""
    first_run: bool = True
    graduated_to_strict: bool = False
    checks: list = field(default_factory=list)  # List[CheckResult] (forward ref)

    def to_json_dict(self) -> dict:
        return asdict(self)


def utc_now_iso() -> str:
    """ISO-8601 UTC timestamp with millis and Z suffix."""
    return (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    )


def compute_catalog_hash(checks_root: Path) -> str:
    """SHA-256 of all *.yaml files concatenated in sequence order.

    Used by the runner to stamp the run manifest's catalog_hash field;
    two runs with the same catalog_hash re-emit the same run identity.
    """
    yaml_files = sorted(checks_root.glob("*.yaml"))
    h = hashlib.sha256()
    for f in yaml_files:
        h.update(f.read_bytes())
    return h.hexdigest()
