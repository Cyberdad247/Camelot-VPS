# SPDX-License-Identifier: MIT

"""Cloud endpoint diagnosis, audit, and Modal discovery."""

from __future__ import annotations

import importlib
import importlib.util
import json
from typing import Any

from control_plane.cli.constants import CAMELOT_HOME, MODAL_DISCOVERY_MAP


def _diagnose_cloud_endpoints(config_mgr: Any) -> dict[str, Any]:
    effective = config_mgr.cloud_endpoint_map()
    persisted = {
        "CAMELOT_CLOUDBRAIN_URL": config_mgr._normalize_env_value(config_mgr.config.cloudbrain_url),
        "CAMELOT_LIVING_NOTEBOOK_URL": config_mgr._normalize_env_value(config_mgr.config.living_notebook_url),
        "CAMELOT_RESEARCH_AGENCY_URL": config_mgr._normalize_env_value(config_mgr.config.research_agency_url),
        "CAMELOT_RESEARCH_AGENCY_HEALTH_URL": config_mgr._normalize_env_value(config_mgr.config.research_agency_health_url),
        "CAMELOT_NORTHSTAR_URL": config_mgr._normalize_env_value(config_mgr.config.northstar_url),
        "CAMELOT_NORTHSTAR_HEALTH_URL": config_mgr._normalize_env_value(config_mgr.config.northstar_health_url),
        "CAMELOT_BLUEPRINT_URL": config_mgr._normalize_env_value(config_mgr.config.blueprint_url),
        "CAMELOT_BLUEPRINT_HEALTH_URL": config_mgr._normalize_env_value(config_mgr.config.blueprint_health_url),
        "CAMELOT_PRECISE_MODE_URL": config_mgr._normalize_env_value(config_mgr.config.precise_mode_url),
        "CAMELOT_PRECISE_MODE_HEALTH_URL": config_mgr._normalize_env_value(config_mgr.config.precise_mode_health_url),
    }
    findings: list[str] = []
    if not importlib.util.find_spec("modal"):
        findings.append("Modal SDK is not installed in the current Python environment.")
    for key, value in persisted.items():
        if value:
            findings.append(f"{key} is pinned in .camelot-config.yaml and overrides inferred defaults.")
    if not any(persisted.values()):
        findings.append("No explicit cloud endpoint overrides are pinned; runtime is using inferred defaults.")
    if persisted.get("CAMELOT_CLOUDBRAIN_URL", "").startswith("https://notebooklm.google.com/notebook/"):
        findings.append(
            "CAMELOT_CLOUDBRAIN_URL currently points at a NotebookLM notebook URL. "
            "That should move to CAMELOT_LIVING_NOTEBOOK_URL; long-term cloudbrain should be excalibur-brain."
        )
    findings.append("Modal dashboard URLs are not callable service endpoints; control plane needs *.modal.run URLs.")
    findings.append("Best-practice alternative: discover deployed function URLs via modal.Function.from_name(...).get_web_url().")
    return {
        "status": "CONFIG_DIAGNOSIS",
        "config_path": str(config_mgr.config_path),
        "effective_endpoints": effective,
        "persisted_overrides": persisted,
        "findings": findings,
    }


def _audit_cloudbrain_configuration(config_mgr: Any) -> dict[str, Any]:
    from control_plane.infra.ledger_sync import ledger_status

    ledger = ledger_status()
    warp_artifact = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "warp_workflow_sync_latest.json"
    warp_sync: dict[str, Any] = {"exists": warp_artifact.exists(), "path": str(warp_artifact)}
    if warp_artifact.exists():
        try:
            warp_sync.update(json.loads(warp_artifact.read_text(encoding="utf-8")))
        except Exception as exc:
            warp_sync["error"] = f"{type(exc).__name__}: {exc}"

    notebook_id = ""
    notebook_title = ""
    try:
        bridge_path = CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
        spec = importlib.util.spec_from_file_location("notebooklm_bridge_audit", bridge_path)
        bridge = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(bridge)
        notebook_id = getattr(bridge, "CANONICAL_NOTEBOOK_ID", "")
        notebook_title = getattr(bridge, "CANONICAL_NOTEBOOK_TITLE", "")
    except Exception:
        pass

    return {
        "status": "AUDIT_READY",
        "config_path": str(config_mgr.config_path),
        "notebook": {
            "id": notebook_id,
            "title": notebook_title,
            "url": config_mgr.config.living_notebook_url,
        },
        "excalibur": {
            "bridge_url": config_mgr.config.excalibur_bridge_url,
            "health_url": config_mgr.config.excalibur_health_url,
        },
        "warp": {
            "repo_workflows_path": config_mgr.config.warp_repo_workflows_path,
            "local_workflows_path": config_mgr.config.warp_local_workflows_path,
            "latest_sync": warp_sync,
        },
        "ledger": {
            "root_hash": ledger.get("root_hash"),
            "mirrors_aligned": ledger.get("mirrors_aligned"),
            "mirrors": ledger.get("mirrors", []),
        },
        "endpoint_diagnostics": _diagnose_cloud_endpoints(config_mgr),
    }


def _discover_modal_endpoints(
    *,
    config_mgr: Any,
    app_name: str,
    environment_name: str,
    write: bool,
) -> dict[str, Any]:
    modal_spec = importlib.util.find_spec("modal")
    if modal_spec is None:
        return {
            "status": "DISCOVERY_UNAVAILABLE",
            "reason": "Modal SDK not installed in current Python environment",
            "app_name": app_name,
            "discovered": {},
        }

    try:
        modal = importlib.import_module("modal")
    except Exception as exc:
        return {
            "status": "DISCOVERY_FAILED",
            "reason": f"Failed to import modal: {exc}",
            "app_name": app_name,
            "discovered": {},
        }

    discovered: dict[str, str] = {}
    errors: dict[str, str] = {}
    for env_var, function_name in MODAL_DISCOVERY_MAP.items():
        try:
            remote_function = modal.Function.from_name(
                app_name,
                function_name,
                environment_name=environment_name,
            )
            url = remote_function.get_web_url()
            if url:
                discovered[env_var] = url.rstrip("/")
        except Exception as exc:
            errors[env_var] = str(exc)

    if write:
        for env_var, url in discovered.items():
            config_mgr.set_cloud_endpoint(env_var, url)

    status = "DISCOVERY_COMPLETE" if discovered else "DISCOVERY_FAILED"
    return {
        "status": status,
        "app_name": app_name,
        "environment_name": environment_name,
        "discovered": discovered,
        "errors": errors,
        "config_path": str(config_mgr.config_path),
        "wrote_config": write and bool(discovered),
    }
