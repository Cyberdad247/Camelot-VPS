# SPDX-License-Identifier: MIT

"""Remote Deployment Contract Specification and Validator for Camelot-OS.

Validates required and optional environment configurations across Modal cloudbrain
endpoints, Appwrite memory spine, and Excalibur mobile/cloud telemetry bridge (Track B4).
Adheres strictly to the Camelot Privacy Rule (keys verified as boolean presence flags only).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class EndpointValidation(BaseModel):
    """Validation record for a single deployment environment variable."""

    env_var: str
    service: str
    category: str
    is_required: bool
    configured: bool
    value_masked: str
    is_valid_url: bool = True
    error: Optional[str] = None


class DeploymentContractReport(BaseModel):
    """Comprehensive remote deployment contract validation verdict."""

    status: str  # "PASS" | "WARN" | "FAIL"
    summary: str
    local_fallback_available: bool = True
    missing_required: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    invalid_urls: list[str] = Field(default_factory=list)
    endpoints: dict[str, EndpointValidation] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def _is_well_formed_url(url: str) -> bool:
    """Check if string is a syntactically valid HTTP/HTTPS URL."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _mask_value(env_var: str, value: Optional[str]) -> str:
    """Mask sensitive tokens while preserving non-secret URLs and identifiers."""
    if not value:
        return "<UNCONFIGURED>"
    val = value.strip()
    # Sensitive tokens: API keys, secrets, passwords -> boolean presence flag
    sensitive_keywords = {"key", "secret", "token", "pass"}
    if any(kw in env_var.lower() for kw in sensitive_keywords):
        return f"<CONFIGURED: {len(val)} chars>"
    # URLs: redact userinfo if present
    try:
        parsed = urlparse(val)
        if parsed.username or parsed.password:
            netloc = parsed.netloc.split("@")[-1]
            return f"{parsed.scheme}://***:***@{netloc}{parsed.path}"
    except Exception:
        pass
    return val


def validate_deployment_contract() -> DeploymentContractReport:
    """Validate all deployment contracts across Modal, Appwrite, and Excalibur."""
    from control_plane.infra.config_manager import ConfigManager
    ConfigManager().hydrate_runtime_environment()

    # Determine local fallback capability
    local_modal_available = False
    try:
        import importlib.util
        local_modal_available = importlib.util.find_spec("modal") is not None
    except Exception:
        local_modal_available = False

    # Contract specification matrix
    contract_specs: list[dict[str, Any]] = [
        # --- Modal Cloudbrain Actions ---
        {
            "env_var": "CAMELOT_RESEARCH_AGENCY_URL",
            "service": "research_agency",
            "category": "modal_action",
            "is_required": not local_modal_available,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_NORTHSTAR_URL",
            "service": "northstar",
            "category": "modal_action",
            "is_required": not local_modal_available,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_BLUEPRINT_URL",
            "service": "development_blueprint",
            "category": "modal_action",
            "is_required": not local_modal_available,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_PRECISE_MODE_URL",
            "service": "precise_mode",
            "category": "modal_action",
            "is_required": not local_modal_available,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_ELDERGOD_URL",
            "service": "eldergod_forge",
            "category": "modal_action",
            "is_required": False,  # Optional extended capability
            "is_url": True,
        },

        # --- Modal Health Endpoints ---
        {
            "env_var": "CAMELOT_RESEARCH_AGENCY_HEALTH_URL",
            "service": "research_agency_health",
            "category": "modal_health",
            "is_required": False,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_NORTHSTAR_HEALTH_URL",
            "service": "northstar_health",
            "category": "modal_health",
            "is_required": False,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_BLUEPRINT_HEALTH_URL",
            "service": "development_blueprint_health",
            "category": "modal_health",
            "is_required": False,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_PRECISE_MODE_HEALTH_URL",
            "service": "precise_mode_health",
            "category": "modal_health",
            "is_required": False,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_ELDERGOD_HEALTH_URL",
            "service": "eldergod_forge_health",
            "category": "modal_health",
            "is_required": False,
            "is_url": True,
        },

        # --- Appwrite Memory Spine ---
        {
            "env_var": "APPWRITE_ENDPOINT_PUBLIC",
            "service": "appwrite_public_api",
            "category": "appwrite_spine",
            "is_required": False,  # Fallback to local SQLite/Open Notebook
            "is_url": True,
        },
        {
            "env_var": "APPWRITE_PROJECT",
            "service": "appwrite_project_id",
            "category": "appwrite_spine",
            "is_required": False,
            "is_url": False,
        },
        {
            "env_var": "APPWRITE_API_KEY",
            "service": "appwrite_api_key",
            "category": "appwrite_spine",
            "is_required": False,
            "is_url": False,
        },

        # --- Excalibur & Living Notebook ---
        {
            "env_var": "CAMELOT_EXCALIBUR_BRIDGE_URL",
            "service": "excalibur_bridge",
            "category": "excalibur_bridge",
            "is_required": False,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_EXCALIBUR_HEALTH_URL",
            "service": "excalibur_health",
            "category": "excalibur_bridge",
            "is_required": False,
            "is_url": True,
        },
        {
            "env_var": "CAMELOT_LIVING_NOTEBOOK_URL",
            "service": "notebooklm_living_notebook",
            "category": "notebooklm",
            "is_required": False,
            "is_url": True,
        },
    ]

    endpoints: dict[str, EndpointValidation] = {}
    missing_required: list[str] = []
    missing_optional: list[str] = []
    invalid_urls: list[str] = []

    for spec in contract_specs:
        env_name = spec["env_var"]
        raw_value = os.getenv(env_name, "").strip()
        configured = bool(raw_value)
        masked_val = _mask_value(env_name, raw_value)
        is_valid_url = True
        err: Optional[str] = None

        if configured and spec["is_url"]:
            if not _is_well_formed_url(raw_value):
                is_valid_url = False
                err = f"Malformed URL format: '{masked_val}' must have http:// or https:// and a valid host."
                invalid_urls.append(env_name)

        if not configured:
            if spec["is_required"]:
                missing_required.append(env_name)
                err = f"Required deployment contract variable {env_name} is missing."
            else:
                missing_optional.append(env_name)

        endpoints[env_name] = EndpointValidation(
            env_var=env_name,
            service=spec["service"],
            category=spec["category"],
            is_required=spec["is_required"],
            configured=configured,
            value_masked=masked_val,
            is_valid_url=is_valid_url,
            error=err,
        )

    # Check Appwrite cohesion: if endpoint is configured, project and key should also be configured
    appwrite_ep = os.getenv("APPWRITE_ENDPOINT_PUBLIC", "").strip()
    if appwrite_ep:
        for appwrite_req in ("APPWRITE_PROJECT", "APPWRITE_API_KEY"):
            if not os.getenv(appwrite_req, "").strip():
                if appwrite_req not in missing_required:
                    missing_required.append(appwrite_req)
                if appwrite_req in endpoints:
                    endpoints[appwrite_req].error = (
                        f"{appwrite_req} is required when APPWRITE_ENDPOINT_PUBLIC is set."
                    )

    # Calculate overall status
    if invalid_urls or missing_required:
        status = "FAIL" if invalid_urls or not local_modal_available else "WARN"
        summary = (
            f"Deployment contract {status}: {len(invalid_urls)} invalid URLs, "
            f"{len(missing_required)} missing required variables."
        )
    elif missing_optional:
        status = "PASS" if local_modal_available else "WARN"
        summary = (
            f"Deployment contract {status}: All required endpoints valid. "
            f"{len(missing_optional)} optional endpoints unconfigured (local fallback active)."
        )
    else:
        status = "PASS"
        summary = "Deployment contract PASS: All remote endpoints, health URLs, and memory spine verified."

    return DeploymentContractReport(
        status=status,
        summary=summary,
        local_fallback_available=local_modal_available,
        missing_required=missing_required,
        missing_optional=missing_optional,
        invalid_urls=invalid_urls,
        endpoints=endpoints,
    )
