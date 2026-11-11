# SPDX-License-Identifier: MIT

"""Enterprise ignition and doctor preflight for Camelot-OS."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cockpit import refresh_snapshot
from control_plane.core.knight_configuration import write_knight_configuration
from .ledger_sync import ledger_status, reconcile_ledger_mirrors
from control_plane.dispatch.switchboard import get_board

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
RUNTIME_ARTIFACT = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "enterprise_ignition_latest.json"
REPORT_ARTIFACT = CAMELOT_HOME / "docs" / "reports" / "enterprise_cli_ignition_audit.md"


def _exists(path: Path) -> bool:
    return path.exists()


def _layer(name: str, status: str, evidence: dict[str, Any], actions: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "evidence": evidence,
        "actions": actions or [],
    }


def _status_from_required(checks: dict[str, bool]) -> str:
    if all(checks.values()):
        return "READY"
    if any(checks.values()):
        return "DEGRADED"
    return "MISSING"


def _dashboard_layer(home: Path) -> dict[str, Any]:
    dashboard = home / "02_FORGE" / "PORTAL_CORE" / "Anya_Dashboard"
    package_json = dashboard / "package.json"
    node_modules = dashboard / "node_modules"
    checks = {
        "dashboard_dir": _exists(dashboard),
        "package_json": _exists(package_json),
        "node_modules": _exists(node_modules),
    }
    actions = []
    if not checks["node_modules"]:
        actions.append("cd 02_FORGE/PORTAL_CORE/Anya_Dashboard; npm install")
    actions.append("cd 02_FORGE/PORTAL_CORE/Anya_Dashboard; npm run dev")
    return _layer(
        "ui_dashboard",
        _status_from_required(checks),
        {
            "path": str(dashboard),
            "checks": checks,
            "dev_command": actions[-1],
        },
        actions,
    )


def _chat_layer(home: Path) -> dict[str, Any]:
    session = home / "bin" / "knight_session.py"
    wrapper = home / "bin" / "camelot.py"
    checks = {
        "knight_session": _exists(session),
        "global_wrapper": _exists(wrapper),
    }
    return _layer(
        "chat_interface",
        _status_from_required(checks),
        {
            "checks": checks,
            "command": "camelot chat",
            "fallback": "python bin/knight_session.py",
        },
        ["camelot chat"],
    )


def _bifrost_layer(home: Path) -> dict[str, Any]:
    manifest = get_board().read_manifest()
    terminals = manifest.get("terminals", {}) if isinstance(manifest, dict) else {}
    gateway = terminals.get("bifrost_gateway", {}) if isinstance(terminals, dict) else {}
    bridge = home / "control_plane" / "bifrost_gateway.py"
    checks = {
        "switchboard_manifest": bool(terminals),
        "bifrost_bridge_module": _exists(bridge),
        "gateway_registered": "bifrost_gateway" in terminals,
    }
    status = "READY" if checks["bifrost_bridge_module"] and checks["gateway_registered"] else "DEGRADED"
    return _layer(
        "bifrost_bridge",
        status,
        {
            "checks": checks,
            "gateway_status": gateway.get("status", "unknown"),
            "manifest": str(home / "logs" / "switchboard_manifest.json"),
        },
        ["python -m control_plane.bifrost_gateway health"],
    )


def _cloudbrain_layer(write: bool) -> dict[str, Any]:
    try:
        from .cloudbrain_mnemosyne_audit import run_lady_mnemosyne_cloudbrain_audit

        audit = run_lady_mnemosyne_cloudbrain_audit(write=write)
        status = audit.get("state") or audit.get("status", "UNKNOWN")
        layer_status = "READY" if status == "MNEMOSYNE_READY" else "DEGRADED"
        return _layer(
            "cloudbrain_mnemosyne",
            layer_status,
            {
                "status": status,
                "artifact": audit.get("artifact_path") or audit.get("artifact"),
                "pending_queue": audit.get("queue", {}).get("pending") if isinstance(audit.get("queue"), dict) else None,
            },
            [
                "python -m control_plane.camelot_cli cloudbrain mnemosyne-audit",
                "python -m control_plane.camelot_cli cloudbrain sync",
            ],
        )
    except Exception as exc:
        return _layer(
            "cloudbrain_mnemosyne",
            "DEGRADED",
            {"error": str(exc)},
            ["python -m control_plane.camelot_cli cloudbrain config audit"],
        )


def _local_inference_layer(home: Path) -> dict[str, Any]:
    config = home / "03_VAULT" / "training" / "configs" / "sovereign_models.json"
    ollama = shutil.which("ollama")
    checks = {
        "sovereign_models_config": _exists(config),
        "ollama_on_path": bool(ollama),
    }
    status = "READY" if all(checks.values()) else "DEGRADED"
    return _layer(
        "local_first_inference",
        status,
        {
            "checks": checks,
            "ollama": ollama,
            "config": str(config),
        },
        ["ollama list", "python -m control_plane.camelot_cli status"],
    )


def _ledger_layer(reconcile: bool) -> dict[str, Any]:
    try:
        status = reconcile_ledger_mirrors() if reconcile else ledger_status()
        ok = bool(
            status.get("root_exists")
            or status.get("exists")
            or status.get("success")
            or status.get("status") == "RECONCILED"
        )
        if status.get("mirrors") and status.get("mirrors_aligned") is False:
            ok = False
        return _layer(
            "ledger_provenance",
            "READY" if ok else "DEGRADED",
            status,
            ["python -m control_plane.camelot_cli ledger reconcile"],
        )
    except Exception as exc:
        return _layer(
            "ledger_provenance",
            "DEGRADED",
            {"error": str(exc)},
            ["python -m control_plane.camelot_cli ledger status"],
        )


def run_enterprise_ignition(
    *,
    home: Path | None = None,
    write: bool = True,
    full: bool = False,
    reconcile_ledger: bool = False,
) -> dict[str, Any]:
    """Run the safe enterprise preflight and optionally persist artifacts."""
    home = (home or CAMELOT_HOME).resolve()
    generated = datetime.now(timezone.utc).isoformat()

    knight_config = write_knight_configuration(home) if write else write_knight_configuration(home)
    cockpit_snapshot = refresh_snapshot(trigger="enterprise_ignition") if write else {}

    layers = [
        _chat_layer(home),
        _dashboard_layer(home),
        _bifrost_layer(home),
        _cloudbrain_layer(write=write),
        _local_inference_layer(home),
        _ledger_layer(reconcile=reconcile_ledger),
    ]
    if full:
        layers.append(
            _layer(
                "starship_prompt_shell",
                "READY" if _exists(home / "03_VAULT" / "runtime_state" / "starship" / "camelot-starship.toml") else "DEGRADED",
                {
                    "config": str(home / "03_VAULT" / "runtime_state" / "starship" / "camelot-starship.toml"),
                    "init_script": str(home / "03_VAULT" / "runtime_state" / "starship" / "init_camelot_starship.ps1"),
                },
                ["python -m control_plane.camelot_cli starship assimilate"],
            )
        )

    degraded = [layer for layer in layers if layer["status"] != "READY"]
    status = "ENTERPRISE_READY" if not degraded else "ENTERPRISE_DEGRADED"

    payload: dict[str, Any] = {
        "status": status,
        "generated_utc": generated,
        "repo_root": str(home),
        "artifacts": {
            "runtime": str(RUNTIME_ARTIFACT),
            "report": str(REPORT_ARTIFACT),
            "knight_configuration": knight_config.get("artifact_path"),
            "cockpit_snapshot": cockpit_snapshot.get("artifact_path"),
        },
        "layers": layers,
        "degraded_layers": [layer["name"] for layer in degraded],
        "operator_commands": [
            "camelot ignite",
            "camelot doctor",
            "camelot chat",
            "camelot cockpit refresh --json",
            "python -m control_plane.camelot_cli cloudbrain sync",
        ],
    }

    if write:
        RUNTIME_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        RUNTIME_ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        REPORT_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
        REPORT_ARTIFACT.write_text(render_markdown(payload), encoding="utf-8")

    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Camelot Enterprise CLI Ignition Audit",
        "",
        f"- status: `{payload.get('status')}`",
        f"- generated_utc: `{payload.get('generated_utc')}`",
        f"- repo_root: `{payload.get('repo_root')}`",
        "",
        "## Layer Status",
        "",
        "| Layer | Status | Primary Action |",
        "|---|---:|---|",
    ]
    for layer in payload.get("layers", []):
        actions = layer.get("actions") or [""]
        lines.append(f"| `{layer.get('name')}` | `{layer.get('status')}` | `{actions[0]}` |")

    lines.extend(
        [
            "",
            "## Operator Commands",
            "",
        ]
    )
    for command in payload.get("operator_commands", []):
        lines.append(f"- `{command}`")

    lines.extend(["", "## Degraded Layers", ""])
    degraded = payload.get("degraded_layers") or []
    if degraded:
        lines.extend(f"- `{name}`" for name in degraded)
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"

