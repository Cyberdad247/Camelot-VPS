# SPDX-License-Identifier: MIT

"""Orchestrator CLI wrapper — delegates to Go runner or Python fallback."""

from __future__ import annotations

from typing import Any


def _run_orchestrator_cli(
    *,
    mode: str,
    root: str = ".",
    older_than_days: int = 60,
    large_file_mb: float = 50.0,
    intent: str = "refactor the backend control plane",
    message: str = "Camelot orchestration event",
    kind: str = "startup",
    status: str = "green",
) -> dict[str, Any]:
    from control_plane.infra.orchestration_state import (
        build_notification_bundle,
        build_orchestration_snapshot,
        go_autonomous_workflow_report,
        route_persona,
        run_orchestrator_cli,
        summarize_boot_results,
        triage_files,
        validate_autonomous_knight_workflows,
    )

    payload = run_orchestrator_cli(
        mode,
        root=root,
        older_than_days=older_than_days,
        large_file_mb=large_file_mb,
        intent=intent,
        message=message,
        kind=kind,
        status=status,
    )
    if payload is not None:
        payload.setdefault("source", "go")
        return payload

    fallback = {
        "mode": mode,
        "source": "python",
    }
    if mode in {"status", "awaken", "conversation"}:
        fallback.update(
            build_orchestration_snapshot(
                root=root,
                older_than_days=older_than_days,
                large_file_mb=large_file_mb,
                intent=intent,
                message=message,
                kind=kind,
                status=status,
            )
        )
    if mode == "knights":
        fallback["autonomous"] = go_autonomous_workflow_report() or validate_autonomous_knight_workflows()
    elif mode == "persona":
        fallback["persona"] = route_persona(intent)
    elif mode == "notify":
        fallback["notification"] = build_notification_bundle(
            {
                "kind": kind,
                "status": status,
                "summary": message,
            }
        )
    elif mode == "triage":
        fallback["triage"] = triage_files(root, older_than_days=older_than_days, large_file_mb=large_file_mb)
    elif mode == "status":
        fallback["triage_summary"] = triage_files(
            root,
            older_than_days=older_than_days,
            large_file_mb=large_file_mb,
        )["summary"]
        fallback["persona"] = route_persona(intent)
        fallback["autonomous"] = go_autonomous_workflow_report() or validate_autonomous_knight_workflows()
    elif mode == "awaken":
        fallback["boot_summary"] = summarize_boot_results(
            [
                {"name": "CLIProxyAPI", "ok": True, "required": True},
                {"name": "Defense Grid", "ok": True, "required": True},
                {"name": "Kinetic Edge", "ok": True, "required": True},
                {"name": "VPS Hermes_Prime", "ok": True, "required": False},
                {"name": "Bifrost Gateway :3001", "ok": True, "required": False},
                {"name": "Cloud Brain", "ok": True, "required": True},
            ]
        )
        fallback["persona"] = route_persona("shape the dashboard interface")
        fallback["autonomous"] = go_autonomous_workflow_report() or validate_autonomous_knight_workflows()
    else:
        fallback["boot_summary"] = summarize_boot_results(
            [
                {"name": "CLIProxyAPI", "ok": True, "required": True},
                {"name": "Defense Grid", "ok": True, "required": True},
                {"name": "Kinetic Edge", "ok": True, "required": True},
                {"name": "VPS Hermes_Prime", "ok": True, "required": False},
                {"name": "Bifrost Gateway :3001", "ok": True, "required": False},
                {"name": "Cloud Brain", "ok": True, "required": True},
            ]
        )
    return fallback
