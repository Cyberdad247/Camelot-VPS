# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""Camelot Sovereign CLI: Pipeline Command Handler (Phase 10).
============================================================
Coordinates operator execution of the Sovereign End-to-End Pipeline:
  - `camelot pipeline run <manifest_file>`
  - `camelot pipeline status`
  - `camelot pipeline verify`
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from control_plane.cli.renderer import _print_json, _stream_print
from control_plane.infra.scarcity_guardian import (
    ScarcityGuardian,
    verify_zero_docker_compliance,
)
from control_plane.pipeline.sovereign_pipeline import (
    PipelineStatus,
    SovereignPipeline,
    TaskProposal,
)
from control_plane.security.authority_vector import AuthorityVector


def _load_manifest(manifest_arg: Optional[str]) -> Dict[str, Any]:
    """Load manifest dictionary from a file path, json string, or default."""
    if not manifest_arg:
        # Default safe read-only manifest
        return {
            "schema_version": "camelot-manifest/1",
            "task_id": f"task_cli_{uuid.uuid4().hex[:10]}",
            "effect_class": "workspace.test",
            "target_paths": ["docs/architecture/pipeline.md"],
            "requires_cleanup": False,
        }

    path = Path(manifest_arg)
    if path.exists() and path.is_file():
        content = path.read_text(encoding="utf-8")
        return json.loads(content)

    # Try parsing string directly as JSON
    try:
        return json.loads(manifest_arg)
    except Exception:
        raise ValueError(f"Manifest argument '{manifest_arg}' is neither an existing file nor valid JSON")


def handle_pipeline_run(args: Any, json_mode: bool = False) -> int:
    """Execute a task proposal through the Sovereign End-to-End Pipeline."""
    try:
        manifest = _load_manifest(getattr(args, "manifest", None))
    except Exception as e:
        if json_mode:
            _print_json({"error": f"Failed to load manifest: {e}", "status": "ERROR"})
        else:
            _stream_print(f"❌ Failed to load manifest: {e}", tone="err")
        return 1

    task_id = manifest.get("task_id") or f"task_{uuid.uuid4().hex[:12]}"
    tenant_id = getattr(args, "tenant", None) or manifest.get("tenant_id") or "tenant_default"
    client_key = getattr(args, "client_key", None) or f"cli_{uuid.uuid4().hex[:8]}"
    intent = getattr(args, "intent", None) or manifest.get("intent") or "Run automated test and verification task"
    effect_class = getattr(args, "effect_class", None) or manifest.get("effect_class") or "workspace.test"
    declared_risk_tier = getattr(args, "risk_tier", None) or manifest.get("risk_tier") or "T1"
    bypass_approvals = getattr(args, "bypass_approvals", False)
    auto_ratify = getattr(args, "auto_ratify", False)

    proposal = TaskProposal(
        task_id=task_id,
        tenant_id=tenant_id,
        correlation_id=f"cor_{uuid.uuid4().hex[:8]}",
        idempotency_key=client_key,
        manifest=manifest,
        authority_vector=AuthorityVector.genesis(),
        intent=intent,
        effect_class=effect_class,
        declared_risk_tier=declared_risk_tier,
        target_paths=manifest.get("target_paths", []),
        write_paths=manifest.get("write_paths", []),
        operator_approved=bypass_approvals,
    )

    pipeline = SovereignPipeline(auto_ratify_high_risk=auto_ratify)
    result = pipeline.execute(proposal)

    output = result.to_dict()

    if json_mode:
        _print_json(output)
    else:
        status_icon = "🟢" if result.status in (PipelineStatus.SUCCESS, PipelineStatus.REPLAYED) else "🔴"
        _stream_print(
            f"{status_icon} Pipeline Execution: {result.status.value} (Stage: {result.current_stage.value})",
            tone="accent" if result.status == PipelineStatus.SUCCESS else "err",
        )
        _stream_print(f"  • Task ID         : {result.task_id}", tone="dim")
        _stream_print(f"  • Tenant ID       : {result.tenant_id}", tone="dim")
        _stream_print(f"  • Idempotency     : {result.idempotency_decision.value}", tone="dim")
        if result.security_decision is not None:
            sec_icon = "✅" if result.security_decision.allowed else "⛔"
            dec_str = getattr(result.security_decision.decision, "value", str(result.security_decision.decision))
            _stream_print(f"  • Security Warden : {sec_icon} {dec_str}", tone="dim")
        if result.gideon_verdict:
            _stream_print(f"  • Gideon Verdict  : {result.gideon_verdict.verdict.upper()} ({len(result.gideon_verdict.gates)} gates verified)", tone="dim")
        if result.arthur_resolution:
            _stream_print(f"  • Arthur Crown    : {result.arthur_resolution.directive_type} (Resolution: {result.arthur_resolution.resolution_id[:16]}...)", tone="dim")
        if result.receipt:
            _stream_print(f"  • Merkle Receipt  : {result.receipt.receipt_id} (Height: {result.receipt.chain_height})", tone="dim")
        if result.error_message:
            _stream_print(f"  • Diagnostic      : {result.error_message}", tone="err")

    return 0 if result.status in (PipelineStatus.SUCCESS, PipelineStatus.REPLAYED) else 1


def handle_pipeline_status(args: Any, json_mode: bool = False) -> int:
    """Report live scarcity, authority vector, and zero-docker governance state."""
    scarcity = ScarcityGuardian()
    zero_docker = verify_zero_docker_compliance()
    is_compliant = bool(zero_docker.get("zero_docker_verified", False))
    authority = AuthorityVector.genesis()

    host_role = "PRIMARY_ORCHESTRATOR"
    if sys.platform.startswith("linux"):
        host_role = "VPS_HUB"

    used_mb = 1200.0
    try:
        import psutil
        vm = psutil.virtual_memory()
        used_mb = round((vm.total - vm.available) / (1024 * 1024), 1)
    except Exception:
        pass

    profile = scarcity.evaluate_node_pressure(host_role, used_mb)

    status_data = {
        "status": "HEALTHY" if is_compliant and not profile.is_critical else "DEGRADED",
        "governance": {
            "zero_docker_compliant": is_compliant,
            "runtime_substrate": zero_docker.get("runtime_substrate", "BARE_METAL"),
            "authority_vector": {
                "e_leadership": authority.e_leadership,
                "r_policy": authority.r_policy,
                "r_revocation": authority.r_revocation,
                "r_registry": authority.r_registry,
                "r_identity": authority.r_identity,
                "r_contract": authority.r_contract,
            },
        },
        "hardware_scarcity": {
            "platform": sys.platform,
            "host_role": profile.node_type,
            "total_ram_mb": profile.total_ram_mb,
            "hard_cap_mb": profile.hard_cap_mb,
            "current_used_mb": profile.current_used_mb,
            "pressure_percentage": profile.pressure_percentage,
            "is_critical": profile.is_critical,
            "throttled_count": len(scarcity.throttled_pills),
        },
    }

    if json_mode:
        _print_json(status_data)
    else:
        _stream_print("🛡️  Camelot Sovereign Pipeline Control Status", tone="accent")
        _stream_print(f"  • Zero-Docker Footprint : {'🟢 100% BARE-METAL / ZERO-DOCKER' if is_compliant else '🔴 NON-COMPLIANT'}", tone="info")
        _stream_print(f"  • Hardware Scarcity Role: {profile.node_type} (Cap: {profile.hard_cap_mb:.1f} MB)", tone="info")
        _stream_print(f"  • RAM Utilization       : {profile.current_used_mb:.1f} MB / {profile.hard_cap_mb:.1f} MB ({profile.pressure_percentage:.1f}%)", tone="info")
        _stream_print(f"  • Scarcity Status       : {'🟢 NOMINAL' if not profile.is_critical else '🚨 CRITICAL'}", tone="info" if not profile.is_critical else "err")
        _stream_print(f"  • Authority Vector      : {authority.to_tuple()}", tone="dim")

    return 0


def handle_pipeline_verify(args: Any, json_mode: bool = False) -> int:
    """Run an automated self-diagnostic smoke test of the 6-stage lifecycle."""
    if not json_mode:
        _stream_print("🚀 Running Sovereign Pipeline 6-Stage Self-Verification...", tone="accent")

    smoke_id = uuid.uuid4().hex[:10]
    test_manifest = {
        "schema_version": "camelot-manifest/1",
        "task_id": f"task_smoke_{smoke_id}",
        "effect_class": "workspace.test",
        "target_paths": ["docs/architecture/pipeline_smoke.md"],
        "requires_cleanup": False,
    }

    proposal = TaskProposal(
        task_id=test_manifest["task_id"],
        tenant_id="tenant_self_test",
        correlation_id=f"cor_smoke_{smoke_id[:6]}",
        idempotency_key=f"smoke_key_{smoke_id[:6]}",
        manifest=test_manifest,
        authority_vector=AuthorityVector.genesis(),
        intent="Run automated sovereign pipeline self-test",
        effect_class="workspace.test",
        declared_risk_tier="T1",
        target_paths=["docs/architecture/pipeline_smoke.md"],
    )

    pipeline = SovereignPipeline()
    result = pipeline.execute(proposal)

    stages_passed = {
        "stage_1_ingress_idempotency": result.idempotency_decision is not None,
        "stage_2_security_gate": result.security_decision is not None and result.security_decision.allowed,
        "stage_3_bounded_execution": result.execution_envelope is not None and result.execution_envelope.status == "SUCCESS",
        "stage_4_sir_gideon_audit": result.gideon_verdict is not None and result.gideon_verdict.verdict == "pass",
        "stage_5_arthur_merkle_commit": result.receipt is not None and result.receipt.chain_height >= 0,
        "stage_6_telemetry_dispatch": len(result.telemetry_events) > 0,
    }

    all_passed = all(stages_passed.values()) and result.status == PipelineStatus.SUCCESS

    verification_data = {
        "status": "PASS" if all_passed else "FAIL",
        "stages": stages_passed,
        "result": result.to_dict(),
    }

    if json_mode:
        _print_json(verification_data)
    else:
        for stage_name, passed in stages_passed.items():
            icon = "🟢" if passed else "🔴"
            _stream_print(f"  {icon} {stage_name.replace('_', ' ').title()}", tone="info" if passed else "err")

        if all_passed:
            _stream_print("🎉 All 6 Sovereign Pipeline Stages Verified 100% Green!", tone="accent")
        else:
            _stream_print("❌ Verification Failed!", tone="err")

    return 0 if all_passed else 1


def handle_pipeline(args: Any, _cm: Any, _pm: Any, _argv: List[str]) -> int:
    """Master dispatch entry point for `camelot pipeline` subcommand."""
    cmd = getattr(args, "pipeline_command", None)
    json_mode = getattr(args, "json", False)

    if cmd in ("run", "submit"):
        return handle_pipeline_run(args, json_mode=json_mode)
    elif cmd == "status":
        return handle_pipeline_status(args, json_mode=json_mode)
    elif cmd in ("verify", "test"):
        return handle_pipeline_verify(args, json_mode=json_mode)
    else:
        if json_mode:
            _print_json({"error": f"Unknown pipeline subcommand: {cmd}", "status": "ERROR"})
        else:
            _stream_print(f"Unknown pipeline subcommand: {cmd}. Available: run, status, verify", tone="err")
        return 1
