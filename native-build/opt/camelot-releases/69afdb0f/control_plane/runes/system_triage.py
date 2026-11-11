# SPDX-License-Identifier: MIT

"""Evidence-gated, read-only CAMELOT-OS system triage."""

from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import asyncio
import hashlib
import importlib.util
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Sequence

from control_plane.infra.ledger_sync import compute_entry_hash, ledger_status

CheckStatus = Literal["PASS", "WARN", "FAIL", "UNVERIFIED", "SKIP"]
ClaimClass = Literal["confirmed", "planned", "aspirational", "rejected"]
Verdict = Literal["GREEN", "DEGRADED", "BLOCKED", "UNVERIFIED"]

CANONICAL_NOTEBOOK_ID = "8c656cfa-a189-409e-a72d-07692a47f17e"
REPORT_SCHEMA = "camelot.system-triage/v1"
REPORT_DIR = Path("03_VAULT/runtime_state/system_triage")


@dataclass(slots=True)
class CheckResult:
    name: str
    stage: str
    status: CheckStatus
    required: bool
    classification: ClaimClass
    summary: str
    command: str | None = None
    duration_ms: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TriageOptions:
    mode: Literal["auto", "rapid", "deep"] = "auto"
    force_deep: bool = False
    write_reports: bool = True
    timestamp: str | None = None
    command_timeout_s: int = 900


@dataclass(slots=True)
class TriageContext:
    root: Path
    options: TriageOptions
    initial_tracked_state: dict[str, str]


@dataclass(slots=True)
class TriageResult:
    schema: str
    generated_utc: str
    root: str
    mode: str
    verdict: Verdict
    exit_code: int
    checks: list[CheckResult]
    deep_skipped: bool
    architecture_summary: dict[str, int]
    json_report: Path | None = None
    markdown_report: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["json_report"] = str(self.json_report) if self.json_report else None
        payload["markdown_report"] = str(self.markdown_report) if self.markdown_report else None
        return payload


Check = Callable[[TriageContext], CheckResult]


def aggregate_verdict(checks: Iterable[CheckResult]) -> Verdict:
    items = list(checks)
    if any(
        item.required
        and item.classification == "confirmed"
        and item.status == "FAIL"
        for item in items
    ):
        return "BLOCKED"
    if any(
        item.required
        and item.classification == "confirmed"
        and item.status == "UNVERIFIED"
        for item in items
    ):
        return "UNVERIFIED"
    if any(item.status in {"FAIL", "WARN", "UNVERIFIED"} for item in items):
        return "DEGRADED"
    return "GREEN"


def verdict_exit_code(verdict: Verdict) -> int:
    return {"GREEN": 0, "DEGRADED": 1, "BLOCKED": 2, "UNVERIFIED": 3}[verdict]


def _run(
    context: TriageContext,
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str, int]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd or context.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or context.options.command_timeout_s,
            check=False,
            env=env,
        )
        duration = round((time.perf_counter() - started) * 1000)
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip(), duration
    except subprocess.TimeoutExpired as exc:
        duration = round((time.perf_counter() - started) * 1000)
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return 124, stdout.strip(), f"timeout: {stderr}".strip(), duration
    except OSError as exc:
        duration = round((time.perf_counter() - started) * 1000)
        return 127, "", f"{type(exc).__name__}: {exc}", duration


def _tracked_state(root: Path) -> dict[str, str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    state: dict[str, str] = {}
    for relative in completed.stdout.splitlines():
        path = root / relative
        if path.is_file():
            state[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            state[relative] = "missing"
    return state


def _repo_fingerprint(context: TriageContext) -> CheckResult:
    code, stdout, stderr, duration = _run(
        context,
        ["git", "status", "--short", "--branch"],
        timeout=30,
    )
    lines = stdout.splitlines()
    dirty_count = max(0, len(lines) - 1)
    return CheckResult(
        name="repository-fingerprint",
        stage="rapid",
        status="PASS" if code == 0 else "UNVERIFIED",
        required=True,
        classification="confirmed",
        summary=f"Git state captured; {dirty_count} changed or untracked entries",
        command="git status --short --branch",
        duration_ms=duration,
        evidence={"output": stdout, "stderr": stderr, "dirty_count": dirty_count},
    )


def _source_of_truth(context: TriageContext) -> CheckResult:
    required = [
        "docs/architecture/SOURCE_OF_TRUTH_MAP.md",
        "entiremap.md",
        "bin/awaken.py",
        "control_plane/boot_sequence.py",
        "control_plane/runic_router.py",
        ".camelot-config.yaml",
    ]
    missing = [path for path in required if not (context.root / path).exists()]
    readme = context.root / "README.md"
    readme_claim = readme.read_text(encoding="utf-8", errors="replace")[:600] if readme.exists() else ""
    bridge_path = context.root / "03_VAULT/training/configs/notebooklm_bridge.py"
    bridge_text = bridge_path.read_text(encoding="utf-8", errors="replace") if bridge_path.exists() else ""
    title = ""
    for line in bridge_text.splitlines():
        if line.startswith("CANONICAL_NOTEBOOK_TITLE"):
            title = line.partition("=")[2].strip().strip('"')
            break
    readme_v2 = "**Version**: 2.0.0" in readme_claim
    drift = readme_v2 or title != "Camelot-OS v.1000"
    status: CheckStatus = "FAIL" if missing else ("WARN" if drift else "PASS")
    return CheckResult(
        name="source-of-truth",
        stage="rapid",
        status=status,
        required=True,
        classification="confirmed",
        summary="Canonical files present" if not drift else "Canonical files present with version/title drift",
        evidence={
            "missing": missing,
            "bridge_notebook_title": title,
            "expected_live_title": "Camelot-OS v.1000",
            "readme_version_2_claim": readme_v2,
        },
        remediation=[
            "Align CANONICAL_NOTEBOOK_TITLE with the live notebook after review.",
            "Classify or remove untracked README production/version claims.",
        ] if drift else [],
    )


def _excalibur_preflight(context: TriageContext) -> CheckResult:
    started = time.perf_counter()
    try:
        from . import excalibur_preflight as preflight

        total, available = preflight._memory_mb()
        sandbox = preflight._sandbox_primitive()
        telemetry = {
            "cpu": {"arch": platform.machine()},
            "memory_mb": {"total": total, "available": available},
            "storage_mb": {
                "free": __import__("shutil").disk_usage(context.root.anchor or "C:\\").free // (1024 * 1024)
            },
            "toolchain": {
                "rustc": {"present": preflight._which("rustc")},
                "cargo": {"present": preflight._which("cargo")},
                "sandbox": sandbox,
            },
            "kernel_features": {"btf_ebpf": False},
        }
        adjudication = preflight.adjudicate(telemetry)
        status: CheckStatus = "PASS" if adjudication["verdict"] == "GO" else "FAIL"
        return CheckResult(
            name="excalibur-preflight",
            stage="rapid",
            status=status,
            required=True,
            classification="confirmed",
            summary=f"EXCALIBUR substrate verdict: {adjudication['verdict']}",
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={"telemetry": telemetry, "adjudication": adjudication},
            remediation=adjudication["violations"],
        )
    except Exception as exc:
        return CheckResult(
            name="excalibur-preflight",
            stage="rapid",
            status="UNVERIFIED",
            required=True,
            classification="confirmed",
            summary=f"Preflight could not run: {type(exc).__name__}",
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={"error": str(exc)},
        )


def _required_boot_contract(context: TriageContext) -> CheckResult:
    path = context.root / "control_plane/boot_sequence.py"
    text = path.read_text(encoding="utf-8", errors="replace")
    anchors = [
        "CLIProxyAPI   :8080",
        "Defense Grid",
        "Kinetic Edge  :3001",
        "Bio-Swarm (Nano)",
        "Morgana Bridge :8001",
        "Cloud Brain   (RPC)",
    ]
    missing = [anchor for anchor in anchors if anchor not in text]
    return CheckResult(
        name="required-boot-contract",
        stage="rapid",
        status="FAIL" if missing else "PASS",
        required=True,
        classification="confirmed",
        summary="Required boot phases are declared" if not missing else "Required boot phases are missing",
        evidence={"required_phases": anchors, "missing": missing},
    )


def _bio_swarm_runtime(context: TriageContext) -> CheckResult:
    from control_plane.infra.bio_swarm_runtime import read_bio_swarm_status

    state = read_bio_swarm_status(context.root)
    release = state.get("release") if isinstance(state.get("release"), dict) else {}
    release_pass = release.get("verdict") == "PASS"
    binary_exists = bool(state.get("binary_exists"))
    if not binary_exists:
        status: CheckStatus = "FAIL"
        summary = "Bio-Swarm spawner binary is missing"
    elif release_pass:
        status = "PASS"
        summary = "Bio-Swarm spawner binary and release evidence are present"
    else:
        status = "WARN"
        summary = "Bio-Swarm spawner is built but lacks passing one-shot release evidence"
    return CheckResult(
        name="bio-swarm-runtime",
        stage="rapid",
        status=status,
        required=True,
        classification="confirmed",
        summary=summary,
        evidence={
            "status": state.get("status"),
            "binary_path": state.get("binary_path"),
            "binary_sha256": state.get("binary_sha256"),
            "state_path": state.get("state_path"),
            "release_path": state.get("release_path"),
            "release_verdict": release.get("verdict"),
        },
        remediation=[
            "Run `cargo build --release -p swarm-spawner`, copy the binary into bin/, then run `camelot bio-swarm once --fixture --json`."
        ] if status != "PASS" else [],
    )


def _targeted_python_tests(context: TriageContext) -> CheckResult:
    tests = [
        "tests/test_architecture_docs.py",
        "tests/test_ledger_governance.py",
        "tests/test_bio_swarm_runtime.py",
    ]
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    code, stdout, stderr, duration = _run(context, command, timeout=300)
    return CheckResult(
        name="targeted-control-plane-tests",
        stage="rapid",
        status="PASS" if code == 0 else "FAIL",
        required=True,
        classification="confirmed",
        summary="Targeted architecture tests passed" if code == 0 else "Targeted architecture tests failed",
        command=" ".join(command),
        duration_ms=duration,
        evidence={"stdout": stdout[-12000:], "stderr": stderr[-4000:], "returncode": code},
        remediation=["Run the failing test nodes individually and repair before deep validation."] if code else [],
    )


def _rust_check(context: TriageContext) -> CheckResult:
    crates = [
        context.root / "01_KERNEL/core/aegis_shield",
        context.root / "01_KERNEL/reasoning/ouroboros_engine",
    ]
    evidence: list[dict[str, Any]] = []
    total_ms = 0
    failed = False
    for crate in crates:
        code, stdout, stderr, duration = _run(
            context,
            ["cargo", "check", "--quiet"],
            cwd=crate,
            timeout=300,
        )
        total_ms += duration
        failed = failed or code != 0
        evidence.append(
            {"crate": str(crate.relative_to(context.root)), "returncode": code, "stdout": stdout, "stderr": stderr}
        )
    return CheckResult(
        name="rust-kernel-compile",
        stage="rapid",
        status="FAIL" if failed else "PASS",
        required=True,
        classification="confirmed",
        summary="Aegis and Ouroboros compile" if not failed else "A Rust kernel failed to compile",
        command="cargo check --quiet",
        duration_ms=total_ms,
        evidence={"crates": evidence},
    )


def _ledger_alignment(_context: TriageContext) -> CheckResult:
    state = ledger_status()
    aligned = bool(state.get("mirrors_aligned"))
    return CheckResult(
        name="provenance-ledger-alignment",
        stage="rapid",
        status="PASS" if aligned else "FAIL",
        required=True,
        classification="confirmed",
        summary="Ledger mirrors aligned" if aligned else "Ledger mirrors are not aligned",
        evidence=state,
        remediation=["Review differences, then run `camelot ledger reconcile` under an approved change window."] if not aligned else [],
    )


def _verification_ledger_integrity(context: TriageContext) -> CheckResult:
    path = context.root / "03_VAULT/Missions/verification_ledger.jsonl"
    if not path.exists():
        return CheckResult(
            name="verification-ledger-integrity",
            stage="rapid",
            status="FAIL",
            required=True,
            classification="confirmed",
            summary="Verification ledger is missing",
            evidence={"path": str(path)},
        )
    previous_hash = None
    count = 0
    error = ""
    try:
        for count, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if not raw.strip():
                count -= 1
                continue
            entry = json.loads(raw)
            if entry.get("entry_id") != count:
                error = f"entry_id mismatch at line {count}"
                break
            if entry.get("parent_hash") != previous_hash:
                error = f"parent_hash mismatch at line {count}"
                break
            expected = entry.get("entry_hash")
            if expected != compute_entry_hash(entry):
                error = f"entry_hash mismatch at line {count}"
                break
            previous_hash = expected
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return CheckResult(
        name="verification-ledger-integrity",
        stage="rapid",
        status="FAIL" if error else "PASS",
        required=True,
        classification="confirmed",
        summary=f"Verification ledger chain valid ({count} entries)" if not error else "Verification ledger chain invalid",
        evidence={"path": str(path), "entries_checked": count, "error": error},
    )


def _cloudbrain_queue(context: TriageContext) -> CheckResult:
    queue = context.root / "03_VAULT/runtime_state/cloudbrain_sync_queue.jsonl"
    if not queue.exists():
        pending = 0
        tail: list[str] = []
    else:
        tail = queue.read_text(encoding="utf-8", errors="replace").splitlines()
        pending = len([line for line in tail if line.strip()])
    return CheckResult(
        name="cloudbrain-sync-queue",
        stage="rapid",
        status="WARN" if pending else "PASS",
        required=False,
        classification="confirmed",
        summary=f"{pending} queued Cloud Brain event(s)",
        evidence={"path": str(queue), "pending": pending, "tail": tail[-5:]},
        remediation=["Inspect with `camelot cloudbrain queue status`; flush only after authentication and review."] if pending else [],
    )


def _load_notebook_bridge(root: Path):
    path = root / "03_VAULT/training/configs/notebooklm_bridge.py"
    spec = importlib.util.spec_from_file_location("camelot_triage_notebook_bridge", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _live_notebook_details(bridge) -> dict[str, Any]:
    client = await bridge._build_client()
    async with client:
        notebooks = await client.notebooks.list()
    def value(item: Any, key: str, default: Any = "") -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)
    selected = next(
        (notebook for notebook in notebooks if str(value(notebook, "id")) == CANONICAL_NOTEBOOK_ID),
        None,
    )
    return {
        "notebook_count": len(notebooks),
        "found": selected is not None,
        "id": str(value(selected, "id")) if selected else "",
        "title": str(value(selected, "title")) if selected else "",
        "source_count": int(value(selected, "source_count", 0) or 0) if selected else 0,
    }


def _notebooklm_live(context: TriageContext) -> CheckResult:
    started = time.perf_counter()
    try:
        bridge = _load_notebook_bridge(context.root)
        details = asyncio.run(_live_notebook_details(bridge))
        drift = details["title"] != bridge.CANONICAL_NOTEBOOK_TITLE
        status: CheckStatus = "FAIL" if not details["found"] else ("WARN" if drift else "PASS")
        return CheckResult(
            name="notebooklm-live",
            stage="rapid",
            status=status,
            required=True,
            classification="confirmed",
            summary=(
                f"NotebookLM reachable: {details['title']} ({details['source_count']} sources)"
                if details["found"]
                else "Canonical NotebookLM notebook not found"
            ),
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={
                **details,
                "configured_title": bridge.CANONICAL_NOTEBOOK_TITLE,
                "title_drift": drift,
            },
            remediation=["Align the local bridge title with the live notebook title after source review."] if drift else [],
        )
    except Exception as exc:
        return CheckResult(
            name="notebooklm-live",
            stage="rapid",
            status="UNVERIFIED",
            required=True,
            classification="confirmed",
            summary=f"NotebookLM live check failed: {type(exc).__name__}",
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={"error": str(exc)},
            remediation=["Run `nlm login`, then rerun `camelot triage --rapid`."],
        )


def _excalibur_cloudbrain(context: TriageContext) -> CheckResult:
    config = context.root / ".camelot-config.yaml"
    text = config.read_text(encoding="utf-8", errors="replace") if config.exists() else ""
    url = ""
    for line in text.splitlines():
        if line.startswith("excalibur_health_url:"):
            url = line.partition(":")[2].strip()
            break
    if not url:
        return CheckResult(
            name="excalibur-cloudbrain-health",
            stage="rapid",
            status="FAIL",
            required=True,
            classification="confirmed",
            summary="Excalibur health URL is not configured",
        )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        alive = response.status == 200 and payload.get("status") == "alive"
        return CheckResult(
            name="excalibur-cloudbrain-health",
            stage="rapid",
            status="PASS" if alive else "FAIL",
            required=True,
            classification="confirmed",
            summary="Long-term Excalibur Cloud Brain is alive" if alive else "Unexpected Cloud Brain health response",
            command=f"GET {url}",
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={"url": url, "http_status": response.status, "payload": payload},
        )
    except Exception as exc:
        return CheckResult(
            name="excalibur-cloudbrain-health",
            stage="rapid",
            status="UNVERIFIED",
            required=True,
            classification="confirmed",
            summary=f"Cloud Brain health check failed: {type(exc).__name__}",
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={"url": url, "error": str(exc)},
        )


def _full_python_suite(context: TriageContext) -> CheckResult:
    command = [sys.executable, "-m", "pytest", "-q"]
    code, stdout, stderr, duration = _run(context, command, timeout=1800)
    return CheckResult(
        name="full-python-suite",
        stage="deep",
        status="PASS" if code == 0 else "FAIL",
        required=True,
        classification="confirmed",
        summary="Full Python suite passed" if code == 0 else "Full Python suite has failures",
        command=" ".join(command),
        duration_ms=duration,
        evidence={"returncode": code, "stdout": stdout[-20000:], "stderr": stderr[-5000:]},
    )


def _dashboard_check(name: str, relative: str, command_name: str = "build") -> Check:
    def check(context: TriageContext) -> CheckResult:
        cwd = context.root / relative
        command = ["cmd", "/c", "npm", "run", command_name]
        code, stdout, stderr, duration = _run(context, command, cwd=cwd, timeout=900)
        return CheckResult(
            name=name,
            stage="deep",
            status="PASS" if code == 0 else "FAIL",
            required=False,
            classification="confirmed",
            summary=f"{name} passed" if code == 0 else f"{name} failed",
            command=" ".join(command),
            duration_ms=duration,
            evidence={"returncode": code, "stdout": stdout[-12000:], "stderr": stderr[-5000:]},
        )
    return check


def _portable_binary_smoke(context: TriageContext) -> CheckResult:
    binary = context.root / "dist/camelot.exe"
    if not binary.exists():
        return CheckResult(
            name="portable-binary-smoke",
            stage="deep",
            status="FAIL",
            required=False,
            classification="confirmed",
            summary="dist/camelot.exe is missing",
            remediation=["Run `python scripts/build_portable.py --test` in an approved build window."],
        )
    evidence: list[dict[str, Any]] = []
    failed = False
    duration = 0
    for arg in ("--version", "--list", "--help"):
        code, stdout, stderr, elapsed = _run(context, [str(binary), arg], timeout=60)
        duration += elapsed
        failed = failed or code != 0
        evidence.append({"argument": arg, "returncode": code, "stdout": stdout[-2000:], "stderr": stderr[-1000:]})
    return CheckResult(
        name="portable-binary-smoke",
        stage="deep",
        status="FAIL" if failed else "PASS",
        required=False,
        classification="confirmed",
        summary="Portable binary smoke checks passed" if not failed else "Portable binary smoke checks failed",
        duration_ms=duration,
        evidence={"binary": str(binary), "size_bytes": binary.stat().st_size, "runs": evidence},
    )


def _cluster_validation(context: TriageContext) -> CheckResult:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, "-m", "control_plane.cluster.launch_local_cluster"]
    code, stdout, stderr, duration = _run(context, command, timeout=180, env=env)
    return CheckResult(
        name="local-cluster-validation",
        stage="deep",
        status="PASS" if code == 0 else "FAIL",
        required=False,
        classification="confirmed",
        summary="Three-node cluster validation passed" if code == 0 else "Cluster validation failed",
        command="PYTHONUTF8=1 python -m control_plane.cluster.launch_local_cluster",
        duration_ms=duration,
        evidence={"returncode": code, "stdout": stdout[-12000:], "stderr": stderr[-5000:]},
    )


def _deep_rust_tests(context: TriageContext) -> CheckResult:
    crate = context.root / "01_KERNEL/reasoning/ouroboros_engine"
    code, stdout, stderr, duration = _run(context, ["cargo", "test", "--quiet"], cwd=crate, timeout=600)
    return CheckResult(
        name="ouroboros-rust-tests",
        stage="deep",
        status="PASS" if code == 0 else "FAIL",
        required=True,
        classification="confirmed",
        summary="Ouroboros Rust tests passed" if code == 0 else "Ouroboros Rust tests failed",
        command="cargo test --quiet",
        duration_ms=duration,
        evidence={"returncode": code, "stdout": stdout[-12000:], "stderr": stderr[-5000:]},
    )


def _tracked_source_guard(context: TriageContext) -> CheckResult:
    final = _tracked_state(context.root)
    exclude_paths = {
        "01_KERNEL/memory/tissue/flash_context.toon",
        "PROVENANCE_LEDGER.md",
    }
    changed = sorted(
        path
        for path in set(context.initial_tracked_state) | set(final)
        if path not in exclude_paths and Path(path).as_posix() not in exclude_paths
        and context.initial_tracked_state.get(path) != final.get(path)
    )
    return CheckResult(
        name="tracked-source-read-only-guard",
        stage="guard",
        status="FAIL" if changed else "PASS",
        required=True,
        classification="confirmed",
        summary="No pre-existing tracked changes were altered" if not changed else "Validation changed tracked files",
        evidence={"changed_during_triage": changed},
    )


def _aspirational_claims(_context: TriageContext) -> CheckResult:
    claims = [
        "Myrddin blind P2P tensor sharding",
        "TEE-backed DOM attestation",
        "DRAM offline recovery",
        "101ms/0.12MiB microVM targets",
    ]
    return CheckResult(
        name="aspirational-v1000-claims",
        stage="rapid",
        status="WARN",
        required=False,
        classification="aspirational",
        summary="Aspirational architecture claims remain non-blocking pending reproducible evidence",
        evidence={"claims": claims},
    )


def _planned_claims(_context: TriageContext) -> CheckResult:
    return CheckResult(
        name="planned-v1000-capabilities",
        stage="rapid",
        status="SKIP",
        required=False,
        classification="planned",
        summary="Planned capabilities are recorded but do not affect runtime readiness",
        evidence={
            "claims": [
                "hardware-backed Aegis enclave",
                "Myrddin CRDT rejoin protocol",
                "deterministic offline DRAM recovery tables",
            ]
        },
    )


def _security_contract(context: TriageContext) -> CheckResult:
    files = {
        "anya_gate": context.root / "control_plane/anya_gate.py",
        "soul_oversight": context.root / "control_plane/soul_oversight.py",
    }
    required_tokens = {
        "anya_gate": ["risk_entropy", "AUTO", "PROMPT", "HUMAN_GATE"],
        "soul_oversight": ["pre_execute", "HUMAN_GATE", "CAMELOT_DASHBOARD_OPERATOR_TOKEN"],
    }
    missing: dict[str, list[str]] = {}
    for name, path in files.items():
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        absent = [token for token in required_tokens[name] if token not in text]
        if absent:
            missing[name] = absent
    return CheckResult(
        name="security-hitl-contract",
        stage="rapid",
        status="FAIL" if missing else "PASS",
        required=True,
        classification="confirmed",
        summary="Adaptive HITL and HUMAN_GATE contracts are present" if not missing else "Security contract is incomplete",
        evidence={"files": {key: str(path) for key, path in files.items()}, "missing_tokens": missing},
    )


def _rejected_legacy_claims(_context: TriageContext) -> CheckResult:
    return CheckResult(
        name="rejected-legacy-architecture",
        stage="rapid",
        status="PASS",
        required=False,
        classification="rejected",
        summary="Legacy v999-only architecture is excluded from release gates",
        evidence={
            "claims": [
                "Needle-26M as the sole canonical router",
                "v999.3 as the live NotebookLM title",
                "narrative production-ready claims without runtime evidence",
            ]
        },
    )


def _focused_deep_tests(name: str, tests: list[str], *, required: bool = True) -> Check:
    def check(context: TriageContext) -> CheckResult:
        command = [sys.executable, "-m", "pytest", "-q", *tests]
        code, stdout, stderr, duration = _run(context, command, timeout=600)
        return CheckResult(
            name=name,
            stage="deep",
            status="PASS" if code == 0 else "FAIL",
            required=required,
            classification="confirmed",
            summary=f"{name} passed" if code == 0 else f"{name} failed",
            command=" ".join(command),
            duration_ms=duration,
            evidence={"returncode": code, "stdout": stdout[-12000:], "stderr": stderr[-5000:]},
        )
    return check


def _required_runtime_ports(_context: TriageContext) -> CheckResult:
    ports = {
        "CLIProxyAPI": 8080,
        "Kinetic Edge": 3001,
        "Morgana Bridge": 8001,
    }
    probes: dict[str, dict[str, Any]] = {}
    for name, port in ports.items():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                probes[name] = {"port": port, "reachable": True}
        except OSError as exc:
            probes[name] = {"port": port, "reachable": False, "error": str(exc)}
    reachable = sum(1 for probe in probes.values() if probe["reachable"])
    return CheckResult(
        name="required-runtime-ports",
        stage="deep",
        status="PASS" if reachable == len(ports) else "FAIL",
        required=True,
        classification="confirmed",
        summary=f"{reachable}/{len(ports)} required local runtime ports reachable",
        evidence={"probes": probes},
        remediation=["Run `python bin/awaken.py --quick`, then repeat deep triage."] if reachable != len(ports) else [],
    )


def _notebook_query_capability(context: TriageContext) -> CheckResult:
    started = time.perf_counter()
    try:
        bridge = _load_notebook_bridge(context.root)
        response = bridge.synthesize(
            "State the canonical Camelot-OS version from the current notebook sources in one sentence.",
            notebook_id=CANONICAL_NOTEBOOK_ID,
            use_cache=False,
        )
        text = str(response or "")
        failed = not text or "synthesis failed" in text.lower()
        return CheckResult(
            name="notebooklm-query-capability",
            stage="deep",
            status="FAIL" if failed else "PASS",
            required=True,
            classification="confirmed",
            summary="NotebookLM synthesis query succeeded" if not failed else "NotebookLM synthesis query failed",
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={"response_excerpt": text[:4000]},
            remediation=["Run `nlm login` and retry the query."] if failed else [],
        )
    except Exception as exc:
        return CheckResult(
            name="notebooklm-query-capability",
            stage="deep",
            status="UNVERIFIED",
            required=True,
            classification="confirmed",
            summary=f"NotebookLM query raised {type(exc).__name__}",
            duration_ms=round((time.perf_counter() - started) * 1000),
            evidence={"error": str(exc)},
        )


def _deployment_lane_inventory(context: TriageContext) -> CheckResult:
    lanes = {
        "portable_cli": ["scripts/build_portable.py", "camelot.spec"],
        "anya_dashboard": ["02_FORGE/PORTAL_CORE/Anya_Dashboard/package.json"],
        "omni_eye_dashboard": ["02_FORGE/apps/omni-eye-dashboard/package.json"],
        "cluster": ["control_plane/cluster/launch_local_cluster.py"],
        "terraform": ["terraform/main.tf"],
        "observability": ["observability/docker-compose.yml"],
        "ci": [".github/workflows"],
    }
    evidence: dict[str, Any] = {}
    missing_required: list[str] = []
    for lane, paths in lanes.items():
        present = [path for path in paths if (context.root / path).exists()]
        evidence[lane] = {"expected": paths, "present": present, "complete": len(present) == len(paths)}
        if lane in {"portable_cli", "anya_dashboard", "cluster", "ci"} and len(present) != len(paths):
            missing_required.append(lane)
    return CheckResult(
        name="deployment-lane-inventory",
        stage="deep",
        status="FAIL" if missing_required else ("WARN" if any(not item["complete"] for item in evidence.values()) else "PASS"),
        required=True,
        classification="confirmed",
        summary="Deployment lane contracts inventoried",
        evidence={"lanes": evidence, "missing_required": missing_required},
    )


def default_rapid_checks() -> list[Check]:
    return [
        _repo_fingerprint,
        _source_of_truth,
        _excalibur_preflight,
        _required_boot_contract,
        _bio_swarm_runtime,
        _targeted_python_tests,
        _rust_check,
        _security_contract,
        _verification_ledger_integrity,
        _ledger_alignment,
        _notebooklm_live,
        _excalibur_cloudbrain,
        _cloudbrain_queue,
        _aspirational_claims,
        _planned_claims,
        _rejected_legacy_claims,
        _tracked_source_guard,
    ]


def default_deep_checks() -> list[Check]:
    return [
        _full_python_suite,
        _deep_rust_tests,
        _focused_deep_tests(
            "memory-tier-validation",
            [
                "tests/test_mempalace_integrity.py",
                "tests/test_mempalace_l2.py",
            ],
        ),
        _required_runtime_ports,
        _notebook_query_capability,
        _dashboard_check(
            "anya-dashboard-verify",
            "02_FORGE/PORTAL_CORE/Anya_Dashboard",
            "verify",
        ),
        _dashboard_check(
            "omni-eye-dashboard-build",
            "02_FORGE/apps/omni-eye-dashboard",
            "build",
        ),
        _portable_binary_smoke,
        _cluster_validation,
        _deployment_lane_inventory,
        _tracked_source_guard,
    ]


def _execute_checks(context: TriageContext, checks: Iterable[Check]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        started = time.perf_counter()
        try:
            result = check(context)
        except Exception as exc:
            result = CheckResult(
                name=getattr(check, "__name__", "unknown-check"),
                stage="rapid",
                status="UNVERIFIED",
                required=True,
                classification="confirmed",
                summary=f"Check raised {type(exc).__name__}",
                evidence={"error": str(exc)},
            )
        if result.duration_ms == 0:
            result.duration_ms = round((time.perf_counter() - started) * 1000)
        results.append(result)
    return results


def _render_markdown(result: TriageResult) -> str:
    lines = [
        "# CAMELOT-OS System Triage",
        "",
        f"- Generated: `{result.generated_utc}`",
        f"- Root: `{result.root}`",
        f"- Mode: `{result.mode}`",
        f"- Verdict: **{result.verdict}**",
        "",
        "| Check | Stage | Required | Evidence class | Status | Summary |",
        "|---|---|---:|---|---|---|",
    ]
    for check in result.checks:
        lines.append(
            f"| {check.name} | {check.stage} | {'yes' if check.required else 'no'} "
            f"| {check.classification} | {check.status} | {check.summary.replace('|', '/')} |"
        )
    remediations = [
        (check.name, remediation)
        for check in result.checks
        for remediation in check.remediation
    ]
    if remediations:
        lines.extend(["", "## Remediation"])
        lines.extend(f"- **{name}:** {remediation}" for name, remediation in remediations)
    lines.extend(
        [
            "",
            "## Evidence Policy",
            "",
            "NotebookLM defines architectural intent. A capability is operational only when "
            "live repository code, commands, tests, endpoints, or artifacts prove it.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_reports(root: Path, result: TriageResult, stamp: str) -> tuple[Path, Path]:
    report_dir = root / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"triage_{stamp}.json"
    markdown_path = report_dir / f"triage_{stamp}.md"
    result.json_report = json_path
    result.markdown_report = markdown_path
    json_path.write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(_render_markdown(result), encoding="utf-8")
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(markdown_path.read_text(encoding="utf-8"), encoding="utf-8")
    return json_path, markdown_path


def run_system_triage(
    root: Path | str,
    *,
    options: TriageOptions | None = None,
    rapid_checks: Iterable[Check] | None = None,
    deep_checks: Iterable[Check] | None = None,
) -> TriageResult:
    root_path = Path(root).resolve()
    opts = options or TriageOptions()
    context = TriageContext(
        root=root_path,
        options=opts,
        initial_tracked_state=_tracked_state(root_path),
    )
    rapid = _execute_checks(context, rapid_checks if rapid_checks is not None else default_rapid_checks())
    rapid_verdict = aggregate_verdict(rapid)
    should_run_deep = opts.mode == "deep" or (
        opts.mode == "auto" and (rapid_verdict != "BLOCKED" or opts.force_deep)
    )
    if opts.mode == "rapid":
        should_run_deep = False
    if opts.force_deep and opts.mode != "rapid":
        should_run_deep = True
    deep = _execute_checks(context, deep_checks if deep_checks is not None else default_deep_checks()) if should_run_deep else []
    checks = [*rapid, *deep]
    verdict = aggregate_verdict(checks)
    generated = datetime.now(timezone.utc).isoformat()
    summary = {
        classification: sum(1 for check in checks if check.classification == classification)
        for classification in ("confirmed", "planned", "aspirational", "rejected")
    }
    result = TriageResult(
        schema=REPORT_SCHEMA,
        generated_utc=generated,
        root=str(root_path),
        mode=opts.mode,
        verdict=verdict,
        exit_code=verdict_exit_code(verdict),
        checks=checks,
        deep_skipped=not should_run_deep and opts.mode != "rapid",
        architecture_summary=summary,
    )
    if opts.write_reports:
        stamp = opts.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        _write_reports(root_path, result, stamp)
    return result
