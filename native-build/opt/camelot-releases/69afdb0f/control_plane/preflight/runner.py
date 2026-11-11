# SPDX-License-Identifier: MIT

"""VFS Preflight runner: load catalog, execute checks, emit evidence.

Slice #1 Task 6: implement the orchestrator (`execute_check` and
`execute_catalog`) end-to-end. Task 3 landed `load_catalog` and
provided NotImplementedError stubs that this commit replaces.

Substrate references verified 2026-08-13:
- VFS_PREFLIGHT_DESIGN.md §5 (per-check JSON, run manifest, idempotency)
- VFS_PREFLIGHT_DESIGN.md §6 (failure matrix, first-run advisor)
- VFS_PREFLIGHT_DESIGN.md §3.3 patched (AnyaGate as advisory only)
- PEER_ARCHITECTURE.md §2 (PEER roles for each entity)
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, List

from .state import GraduationFlag
from .schemas import (
    CheckSpec, CheckResult, RunManifest, utc_now_iso,
)


class CatalogError(ValueError):
    """Catalog load failed. The message bundles per-file error info.

    Also raised by execute_catalog if the spec list is empty or the
    run_root is missing/invalid.
    """


class _SentinelUnavailable(Exception):
    """Internal: signals the substrate is unreachable. Re-raised as
    inline sentinel dict downstream; never propagated to the operator."""


def load_catalog(checks_dir: Path) -> List[CheckSpec]:
    """Read `*.yaml` from checks_dir, parse via CheckSpec, sort by sequence.

    See Task 3 commit eff321fb for behavior. Mirrored here for module
    self-containment; matches CheckSpec's CONFIRMED-only gate at load.
    """
    if not checks_dir.exists():
        raise CatalogError(f"checks directory missing: {checks_dir}")
    if not checks_dir.is_dir():
        raise CatalogError(
            f"checks path is not a directory: {checks_dir}"
        )

    specs: List[CheckSpec] = []
    per_file_errors: List[str] = []
    yaml_files = sorted(checks_dir.glob("*.yaml"))
    for f in yaml_files:
        try:
            specs.append(CheckSpec.from_yaml_text(f.read_text()))
        except Exception as e:  # schemas.CatalogParseError or yaml error
            per_file_errors.append(f"{f.name}: {e}")

    if per_file_errors:
        raise CatalogError("; ".join(per_file_errors))

    seen_seqs: set = set()
    duplicates: List[str] = []
    for s in specs:
        if s.sequence in seen_seqs:
            duplicates.append(
                f"sequence {s.sequence} duplicated (ids: "
                f"{[sp.id for sp in specs if sp.sequence == s.sequence]})"
            )
        seen_seqs.add(s.sequence)

    if duplicates:
        raise CatalogError("; ".join(duplicates))

    specs.sort(key=lambda s: s.sequence)
    return specs


# ============================================================================
# Helpers
# ============================================================================

def _try_parse_json(text: str) -> dict:
    """Tolerantly parse JSON from subprocess stdout.

    Probe-runner CLIs emit a single JSON line. If the body has trailing
    prose or the line is split across multiple, we accept the first
    parseable line.
    """
    if not text:
        return {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def _triage_obj_to_dict(obj) -> dict:
    """Best-effort: convert TriageScore-like object to a dict.

    Paths:
    - dict => returned as-is (after filtering to known keys).
    - Pydantic BaseModel => `.model_dump()` or `dict()`.
    - Anything else => string-coerce.
    The runner is **advisory only** with respect to this dict;
    preflight owns evidence_class (VFS_PREFLIGHT_DESIGN §3.3).
    """
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        out = obj.model_dump()
        if isinstance(out, dict):
            return out
    if hasattr(obj, "dict") and callable(obj.dict):
        out = obj.dict()
        if isinstance(out, dict):
            return out
    return {"method": "triage_returned_unknown", "raw": str(obj)[:256]}


_ADVISORY_UNAVAILABLE: dict = {
    "method": "advisory_unavailable",
    "lane": "NORMAL",
    "hitl_tier": "AUTO",
    "shatterpoints_detected": [],
}


# ============================================================================
# execute_check
# ============================================================================

def execute_check(
    spec: CheckSpec, *, strict_mode: bool, anya_triage_fn: Callable
) -> CheckResult:
    """Run a single check via probes.exec.run.

    Behavior:
    - Parses JSON stdout (probe-runner CLIs emit one JSON line).
    - Computes `evidence_class` (`CONFIRMED` if `parsed["all_ok"]
      and no timeout; `REJECTED` otherwise). Preflight **owns** this
      decision — `anya_triage_fn` is invoked for **advisory** metadata
      only per VFS_PREFLIGHT_DESIGN §3.3 patched 2026-08-13.
    - `rejection_reasons` describes which `all_ok` key was False, plus
      "timeout: Ns exceeded" on timeout.
    - `halt_decision` follows §6.1 failure matrix:
        * CONFIRMED -> continue
        * strict-mode + REJECTED -> block_boot
        * advisor-mode + REJECTED -> continue + advisor_finding=True
        * strict-mode + REJECTED + hitl_on_fail -> block_boot (sentinel
          cannot lift halt; PEER Sentinel/Iron Gate is the only path)
    - `anya_triage_fn` failures fall back to the inline `_ADVISORY_UNAVAILABLE`
      sentinel; preflight does not crash if AnyaGate is unreachable.
    """
    started_at = utc_now_iso()
    res = _run_subprocess(spec)

    payload = _try_parse_json(res.stdout_excerpt)

    rejection_reasons: List[str] = []
    if res.timed_out:
        rejection_reasons.append(f"timeout: {spec.timeout_s}s exceeded")
    else:
        if "all_ok" in payload:
            if not payload["all_ok"]:
                # Aggregate every signal the probe emitted alongside
                # the failed `all_ok`. If the probe only showed
                # `all_ok = false` without any False-valued sibling
                # (e.g. vfs_present_run emits `missing_count`, not a
                # False boolean), we still record a generic reason
                # so the rejection is detectable downstream.
                specific_reasons = 0
                for k, v in payload.items():
                    if k == "all_ok":
                        continue
                    if v is False:
                        rejection_reasons.append(f"{k} = {v!r}")
                        specific_reasons += 1
                    elif isinstance(v, dict):
                        # Flatten nested bool leaves (e.g. ports probe's
                        # {"results": {"8080": false, ...}}) into
                        # operator-readable reasons.
                        for sub, sv in v.items():
                            if sv is False:
                                rejection_reasons.append(f"{k}.{sub} = False")
                                specific_reasons += 1
                if not specific_reasons:
                    rejection_reasons.append("all_ok = False (no False-sibling detail)")
        else:
            # Non-JSON output (e.g. shell check) -> trust exit code.
            if res.exit_code != 0:
                rejection_reasons.append(f"exit_code = {res.exit_code}")

    evidence_class = "CONFIRMED" if not rejection_reasons else "REJECTED"
    halt_decision = "continue"
    advisor_finding = False
    if evidence_class == "REJECTED":
        if strict_mode:
            halt_decision = "block_boot"
        else:
            # advisor-mode (first run, _graduated.flag absent):
            # record the finding but proceed per spec §6.2.
            halt_decision = "continue"
            advisor_finding = True

    # Advisory ANYA invocation; never crashes the gate.
    raw_intent = (
        f"preflight_check {spec.id}: evidence={evidence_class} "
        f"reasons={';'.join(rejection_reasons) or 'none'}"
    )
    try:
        triage_obj = anya_triage_fn(raw_intent)
        evidence_assertion = _triage_obj_to_dict(triage_obj)
    except Exception as e:  # noqa: BLE001
        # Graceful degradation when AnyaGate is unreachable.
        evidence_assertion = dict(_ADVISORY_UNAVAILABLE)
        evidence_assertion["warning"] = f"triage_unreachable: {e!r}"

    hitl_required = bool(spec.hitl_on_fail and evidence_class == "REJECTED")
    if hitl_required and not strict_mode:
        # advisor-mode hits a PROMPT-tier deferral, not a hard halt.
        halt_decision = "continue"
        advisor_finding = True

    return CheckResult(
        run_id="",  # assigned by execute_catalog
        check_id=spec.id,
        display_name=spec.display_name,
        command_observed=list(spec.command),
        command_raw=(
            f"vfs/checks/{spec.sequence:03d}_{spec.id}.yaml"
        ),
        exit_code=res.exit_code,
        started_at=started_at,
        duration_ms=res.duration_ms,
        stdout_excerpt=res.stdout_excerpt,
        stderr_excerpt=res.stderr_excerpt,
        evidence_class=evidence_class,
        evidence_assertion=evidence_assertion,
        hitl_required=hitl_required,
        halt_decision=halt_decision,
        advisor_finding=advisor_finding,
        rejection_reasons=rejection_reasons,
        remediation_hint=spec.remediation_hint,
        artifact_path="",  # assigned by execute_catalog
    )


def _run_subprocess(spec: CheckSpec):
    """Internal: dispatch to probes.exec.run with cross-platform
    safety. Imports locally to keep import-time side effects off the
    runner module's surface.

    A bare `python` command token is rewritten to `sys.executable` so
    probes always run under the SAME interpreter as preflight itself.
    On this host `python` on the Windows CreateProcess search path
    resolves to a uv-managed base interpreter without PyYAML, which
    made check 060 `tool_registry_presence` reject while the shell
    (and the venv) resolved it correctly."""
    from .probes import exec as probe_exec
    command = list(spec.command)
    if command and command[0] in ("python", "python3"):
        command[0] = sys.executable
    return probe_exec.run(command, spec.timeout_s)


# ============================================================================
# execute_catalog
# ============================================================================

def execute_catalog(
    *,
    specs: List[CheckSpec],
    run_root: Path,
    scene_text: str,
    strict_mode: bool,
    anya_triage_fn: Callable,
) -> RunManifest:
    """Run the catalog end-to-end and emit JSON evidence.

    Per VFS_PREFLIGHT_DESIGN §5.2:
    - Sequence iteration (specs must already be sorted).
    - Fail-fast on first strict-mode REJECTED; remaining checks SKIPPED.
    - Advisor-mode REJECTED softens the halt (records advisor_finding).
    - Graduations: `_graduated.flag` written on first all-CONFIRMED run.
    - Atomic JSON writes via tempfile + os.replace for slice
      idempotency.
    - Run manifest records total/passed/failed/skipped + hashes.
    """
    if not specs:
        raise CatalogError("execute_catalog called with empty specs list")
    if not run_root.exists() and not run_root == Path("."):
        # Allow missing run_root; we'll create it.
        pass
    run_root.mkdir(parents=True, exist_ok=True)

    # Per-run timestamp directory: <run_root>/preflight/<UTC>/ per
    # VFS_PREFLIGHT_DESIGN §3.1. The `preflight/` subdir keeps artifacts
    # distinct from other runtime_state consumers AND aligns with
    # GraduationFlag(run_root).path() == <run_root>/preflight/_graduated.flag,
    # so first_run / strict_mode / graduation all read one flag location.
    ts = utc_now_iso_for_id()
    run_dir = run_root / "preflight" / ts
    # Idempotency: a re-run within the same second gets a counter suffix.
    suffix_counter = 0
    while run_dir.exists():
        suffix_counter += 1
        run_dir = run_root / "preflight" / f"{ts}_{suffix_counter:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = utc_now_iso()
    started_mono = time.monotonic()

    catalog_hash = compute_catalog_hash_from_text(
        "\n".join(_spec_text_for_hash(s) for s in specs)
    )
    scene_hash = _short_sha(scene_text)

    run_id = f"preflight-{ts.replace(':', '-').replace('.', '-')}-{scene_hash[:6]}"
    if suffix_counter:
        run_id += f"-{suffix_counter:02d}"

    manifest = RunManifest(
        run_id=run_id,
        started_at=started_at,
        ended_at="",
        total_ms=0,
        checks_total=len(specs),
        checks_passed=0,
        checks_failed=0,
        checks_skipped=0,
        halted_at_check=None,
        halt_decision="continue",
        scene_hash=scene_hash,
        catalog_hash=catalog_hash,
        first_run=True,  # recomputed below
        graduated_to_strict=False,
    )

    halted = False
    all_passed = True
    results: List[CheckResult] = []

    for spec in specs:
        if halted:
            # Skip remaining checks; record SKIPPED entries.
            skip_result = CheckResult(
                run_id=run_id,
                check_id=spec.id,
                display_name=spec.display_name,
                command_observed=list(spec.command),
                command_raw=(
                    f"vfs/checks/{spec.sequence:03d}_{spec.id}.yaml"
                ),
                exit_code=-2,  # sentinel for skipped
                started_at=started_at,
                duration_ms=0,
                stdout_excerpt="",
                stderr_excerpt="",
                evidence_class="CONFIRMED",  # SKIPPED is not a fail
                evidence_assertion={"method": "skipped_prior_halt"},
                hitl_required=False,
                halt_decision="continue",
                advisor_finding=False,
                rejection_reasons=["skipped_prior_halt"],
                remediation_hint=None,
                artifact_path="",
            )
            manifest.checks_skipped += 1
            results.append(skip_result)
            _write_result_artifact(run_dir, skip_result)
            continue

        result = execute_check(
            spec, strict_mode=strict_mode, anya_triage_fn=anya_triage_fn,
        )
        result.run_id = run_id
        result.artifact_path = str(run_dir / f"{spec.id}.json")
        _write_result_artifact(run_dir, result)
        results.append(result)

        if result.evidence_class == "REJECTED":
            manifest.checks_failed += 1
            all_passed = False
            if not result.advisor_finding:  # strict-mode
                manifest.halted_at_check = spec.id
                manifest.halt_decision = "block_boot"
                halted = True
        else:
            manifest.checks_passed += 1

    ended_at = utc_now_iso()
    total_ms = int((time.monotonic() - started_mono) * 1000)
    manifest.ended_at = ended_at
    manifest.total_ms = total_ms
    manifest.first_run = not GraduationFlag(run_root).is_strict()
    manifest.checks = list(results)  # populate per-check evidence for callers

    # Graduation (advisor -> strict transition) on first all-CONFIRMED.
    if (
        all_passed
        and not GraduationFlag(run_root).is_strict()
        and _is_first_run(manifest, scene_text)
    ):
        try:
            GraduationFlag(run_root).graduate()
            manifest.graduated_to_strict = True
        except Exception:
            # Graduation is committed-but-best-effort; never crash.
            manifest.graduated_to_strict = False

    _write_manifest(run_dir, manifest)
    return manifest


def _write_result_artifact(run_dir: Path, result: CheckResult) -> None:
    """Atomic write per-check JSON."""
    target = run_dir / f"{result.check_id}.json"
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=str(run_dir),
        prefix=f".{result.check_id}.",
        suffix=".tmp",
        encoding="utf-8",
    ) as tmp:
        json.dump(result.to_json_dict(), tmp, indent=2, sort_keys=True)
        tmp.write("\n")
    os.replace(tmp.name, target)


def _write_manifest(run_dir: Path, manifest: RunManifest) -> None:
    """Atomic write of run manifest under <run_dir>/_manifest.json."""
    target = run_dir / "_manifest.json"
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=str(run_dir),
        prefix="._manifest.",
        suffix=".tmp",
        encoding="utf-8",
    ) as tmp:
        json.dump(manifest.to_json_dict(), tmp, indent=2, sort_keys=True)
        tmp.write("\n")
    os.replace(tmp.name, target)


def utc_now_iso_for_id() -> str:
    """Time string safe for filename use (no colons).

    ISO-8601 UTC with `:` and `.` replaced by `-`. Cross-version-safe
    (uses datetime.now(UTC) per PEP 615 onwards; `datetime.utcnow()`
    is deprecated in Python 3.12+).
    """
    from datetime import datetime, timezone
    return (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    )


def _spec_text_for_hash(spec: CheckSpec) -> str:
    """Stable textual representation for catalog hashing."""
    return (
        f"{spec.sequence}|{spec.id}|{spec.command_type}|"
        f"{'|'.join(spec.command)}|{spec.timeout_s}|{spec.retry}|"
        f"{spec.expected_evidence_class}|{spec.hitl_on_fail}"
    )


def compute_catalog_hash_from_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short_sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_first_run(manifest: RunManifest, scene_text: str) -> bool:
    """First-run check: helper available for anya_gate-type introspection.

    Per spec §6.2, graduation triggers only on first all-CONFIRMED.
    `manifest.first_run` already reflects `_graduated.flag` presence
    on the run_root at pre-run time. This helper is here for symmetry
    with the runner spec; not currently gated.
    """
    return manifest.first_run
