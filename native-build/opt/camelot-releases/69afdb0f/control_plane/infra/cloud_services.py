# SPDX-License-Identifier: MIT

"""Typed routing for Camelot cloudbrain and research services."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from .cloud_policy import CloudTimeoutPolicy
from .config_manager import ConfigManager

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(REPO_ROOT / "01_KERNEL"))



# --- NotebookLM bridge loader (Omega₃) -----------------------------------------
# The bridge lives under 03_VAULT/training/configs/ which is not on sys.path.
# Load it by file-spec on first use, then cache the module handle.

_NOTEBOOKLM_BRIDGE = None


def _load_notebooklm_bridge():
    global _NOTEBOOKLM_BRIDGE
    if _NOTEBOOKLM_BRIDGE is not None:
        return _NOTEBOOKLM_BRIDGE
    home = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS"))
    bridge_path = home / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
    if not bridge_path.is_file():
        raise FileNotFoundError(f"notebooklm_bridge.py not found at {bridge_path}")
    spec = importlib.util.spec_from_file_location("notebooklm_bridge", bridge_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["notebooklm_bridge"] = module
    spec.loader.exec_module(module)
    _NOTEBOOKLM_BRIDGE = module
    return module


# Heavy cloud deps (modal, supabase, long-term cloudbrain) are imported lazily
# inside handler methods so lightweight consumers — e.g. the Omega₃ NotebookLM slice —
# don't pay the import cost or fail on a missing optional dependency.
def _modal_services():
    from agora.cloud_orchestrator_shim import modal_services
    return modal_services


def _long_term_cloudbrain():
    from agora.cloud_orchestrator_shim import long_term_cloudbrain
    return long_term_cloudbrain


def _has_modal_sdk() -> bool:
    return importlib.util.find_spec("modal") is not None


def _missing_remote_service_result(
    *,
    service: "CloudServiceName",
    env_var: str,
) -> "CloudServiceResult":
    return CloudServiceResult(
        service=service,
        success=False,
        error=(
            f"{env_var} is not configured and local Modal execution is unavailable. "
            "This service is cloud-backed; configure the remote endpoint URL for this environment."
        ),
        source="config",
    )


class CloudServiceName(str, Enum):
    CLOUDBRAIN_STATUS = "cloudbrain_status"
    CLOUDBRAIN_MEMORY = "cloudbrain_memory"
    RESEARCH_AGENCY = "research_agency"
    RESEARCH_AGENCY_HEALTH = "research_agency_health"
    NORTHSTAR = "northstar"
    NORTHSTAR_HEALTH = "northstar_health"
    DEVELOPMENT_BLUEPRINT = "development_blueprint"
    DEVELOPMENT_BLUEPRINT_HEALTH = "development_blueprint_health"
    PRECISE_MODE = "precise_mode"
    PRECISE_MODE_HEALTH = "precise_mode_health"
    ELDERGOD_FORGE = "eldergod_forge"
    ELDERGOD_FORGE_HEALTH = "eldergod_forge_health"
    NOTEBOOKLM_HEALTH = "notebooklm_health"
    NOTEBOOKLM_SYNTHESIZE = "notebooklm_synthesize"
    NOTEBOOKLM_SYNC = "notebooklm_sync"
    NOTEBOOKLM_RESEARCH_START = "notebooklm_research_start"
    NOTEBOOKLM_RESEARCH_POLL = "notebooklm_research_poll"
    NOTEBOOKLM_STUDIO_LIST = "notebooklm_studio_list"
    NOTEBOOKLM_STUDIO_GENERATE = "notebooklm_studio_generate"
    NOTEBOOKLM_SOURCES_LIST = "notebooklm_sources_list"
    NOTEBOOKLM_SOURCES_ADD = "notebooklm_sources_add"
    NOTEBOOKLM_SOURCES_DELETE = "notebooklm_sources_delete"
    HEALTH_ROLLUP = "health_rollup"


class CloudServiceRequest(BaseModel):
    service: CloudServiceName
    payload: dict[str, Any] = Field(default_factory=dict)


class CloudServiceResult(BaseModel):
    service: CloudServiceName
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    source: str = "local"


class CloudServiceRouter:
    """Routes typed requests to local or remote cloud services."""

    def __init__(self, policy: Optional[CloudTimeoutPolicy] = None):
        ConfigManager().hydrate_runtime_environment()
        self.policy = policy or CloudTimeoutPolicy()
        self.cloudbrain_url = os.getenv("CAMELOT_CLOUDBRAIN_URL", "").rstrip("/")
        self.living_notebook_url = os.getenv("CAMELOT_LIVING_NOTEBOOK_URL", "").rstrip("/")
        self.research_url = os.getenv("CAMELOT_RESEARCH_AGENCY_URL", "").rstrip("/")
        self.research_health_url = os.getenv("CAMELOT_RESEARCH_AGENCY_HEALTH_URL", "").rstrip("/")
        self.northstar_url = os.getenv("CAMELOT_NORTHSTAR_URL", "").rstrip("/")
        self.northstar_health_url = os.getenv("CAMELOT_NORTHSTAR_HEALTH_URL", "").rstrip("/")
        self.blueprint_url = os.getenv("CAMELOT_BLUEPRINT_URL", "").rstrip("/")
        self.blueprint_health_url = os.getenv("CAMELOT_BLUEPRINT_HEALTH_URL", "").rstrip("/")
        self.precise_mode_url = os.getenv("CAMELOT_PRECISE_MODE_URL", "").rstrip("/")
        self.precise_mode_health_url = os.getenv("CAMELOT_PRECISE_MODE_HEALTH_URL", "").rstrip("/")
        self.eldergod_url = os.getenv("CAMELOT_ELDERGOD_URL", "").rstrip("/")
        self.eldergod_health_url = os.getenv("CAMELOT_ELDERGOD_HEALTH_URL", "").rstrip("/")
        self.excalibur_bridge_url = os.getenv("CAMELOT_EXCALIBUR_BRIDGE_URL", "").rstrip("/")
        self.excalibur_health_url = os.getenv("CAMELOT_EXCALIBUR_HEALTH_URL", "").rstrip("/")

    def _brain_role_manifest(self) -> dict[str, Any]:
        bridge = _load_notebooklm_bridge()
        return {
            "long_term_agentic_brain": {
                "service": "excalibur-brain",
                "role": "primary_remote_agentic_brain",
                "bridge_url": self.excalibur_bridge_url or None,
                "health_url": self.excalibur_health_url or None,
                "local_runtime": "Open Notebook + Appwrite",
            },
            "short_term_working_memory": {
                "service": "NotebookLM",
                "role": "living_notebook",
                "notebook_id": bridge.CANONICAL_NOTEBOOK_ID,
                "notebook_title": bridge.CANONICAL_NOTEBOOK_TITLE,
                "notebook_url": self.living_notebook_url or None,
            },
            "deprecated_config": {
                "cloudbrain_url": self.cloudbrain_url or None,
                "warning": (
                    "CAMELOT_CLOUDBRAIN_URL is deprecated for NotebookLM notebook links. "
                    "Use CAMELOT_LIVING_NOTEBOOK_URL for the living notebook and "
                    "CAMELOT_EXCALIBUR_* for the long-term remote brain."
                ) if self.cloudbrain_url else None,
            },
        }

    async def _invoke_excalibur_bridge(
        self,
        *,
        task: str,
        mode: str,
        service: CloudServiceName,
        payload: dict[str, Any],
    ) -> CloudServiceResult:
        if not self.excalibur_bridge_url:
            return CloudServiceResult(
                service=service,
                success=False,
                error="CAMELOT_EXCALIBUR_BRIDGE_URL is not configured.",
                source="config",
            )

        bridge_payload = {
            "intent": task,
            "task": task,
            "mode": mode,
            "service": service.value,
            "payload": payload,
        }
        try:
            async def _do_post() -> httpx.Response:
                async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=False)) as client:
                    return await client.post(self.excalibur_bridge_url, json=bridge_payload)

            response = await self.policy.execute_http(_do_post, service_key=f"excalibur_bridge:{service.value}", is_health=False)
            result = response.json()
            return CloudServiceResult(
                service=service,
                success=True,
                result={
                    "bridge_service": "excalibur-brain",
                    "bridge_url": self.excalibur_bridge_url,
                    "bridge_response": result,
                },
                source="remote_bridge",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=service,
                success=False,
                error=str(exc),
                source="remote_bridge",
            )

    async def _invoke_excalibur_health(self, service: CloudServiceName) -> CloudServiceResult:
        if not self.excalibur_health_url:
            return CloudServiceResult(
                service=service,
                success=False,
                error="CAMELOT_EXCALIBUR_HEALTH_URL is not configured.",
                source="config",
            )
        try:
            async def _do_get() -> httpx.Response:
                async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=True)) as client:
                    return await client.get(self.excalibur_health_url)

            response = await self.policy.execute_http(_do_get, service_key=f"excalibur_health:{service.value}", is_health=True)
            result = response.json()
            return CloudServiceResult(
                service=service,
                success=True,
                result={
                    "bridge_service": "excalibur-brain",
                    "bridge_health_url": self.excalibur_health_url,
                    **result,
                },
                source="remote_bridge",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=service,
                success=False,
                error=str(exc),
                source="remote_bridge",
            )

    async def invoke(self, request: CloudServiceRequest) -> CloudServiceResult:
        if request.service is CloudServiceName.CLOUDBRAIN_STATUS:
            return await self._cloudbrain_status()
        if request.service is CloudServiceName.CLOUDBRAIN_MEMORY:
            return await self._cloudbrain_memory(request.payload)
        if request.service is CloudServiceName.RESEARCH_AGENCY:
            return await self._research_agency(request.payload)
        if request.service is CloudServiceName.RESEARCH_AGENCY_HEALTH:
            return await self._research_agency_health()
        if request.service is CloudServiceName.NORTHSTAR:
            return await self._northstar(request.payload)
        if request.service is CloudServiceName.NORTHSTAR_HEALTH:
            return await self._northstar_health()
        if request.service is CloudServiceName.DEVELOPMENT_BLUEPRINT:
            return await self._development_blueprint(request.payload)
        if request.service is CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH:
            return await self._development_blueprint_health()
        if request.service is CloudServiceName.PRECISE_MODE:
            return await self._precise_mode(request.payload)
        if request.service is CloudServiceName.PRECISE_MODE_HEALTH:
            return await self._precise_mode_health()
        if request.service is CloudServiceName.ELDERGOD_FORGE:
            return await self._eldergod_forge(request.payload)
        if request.service is CloudServiceName.ELDERGOD_FORGE_HEALTH:
            return await self._eldergod_forge_health()
        if request.service is CloudServiceName.NOTEBOOKLM_HEALTH:
            return await self._notebooklm_health()
        if request.service is CloudServiceName.NOTEBOOKLM_SYNTHESIZE:
            return await self._notebooklm_synthesize(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_SYNC:
            return await self._notebooklm_sync(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_RESEARCH_START:
            return await self._notebooklm_research_start(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_RESEARCH_POLL:
            return await self._notebooklm_research_poll(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_STUDIO_LIST:
            return await self._notebooklm_studio_list(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_STUDIO_GENERATE:
            return await self._notebooklm_studio_generate(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_SOURCES_LIST:
            return await self._notebooklm_sources_list(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_SOURCES_ADD:
            return await self._notebooklm_sources_add(request.payload)
        if request.service is CloudServiceName.NOTEBOOKLM_SOURCES_DELETE:
            return await self._notebooklm_sources_delete(request.payload)
        if request.service is CloudServiceName.HEALTH_ROLLUP:
            probe_remote = bool(request.payload.get("probe_remote", True))
            return await self._health_rollup(probe_remote=probe_remote)
        return CloudServiceResult(
            service=request.service,
            success=False,
            error=f"Unsupported cloud service: {request.service}",
        )

    async def _cloudbrain_status(self) -> CloudServiceResult:
        topology = _long_term_cloudbrain().cloudbrain_status()
        topology["brain_roles"] = self._brain_role_manifest()

        if self.excalibur_health_url:
            remote = await self._invoke_excalibur_health(CloudServiceName.CLOUDBRAIN_STATUS)
            if remote.success:
                remote.result = {
                    "topology": topology,
                    "remote_runtime": remote.result,
                }
                return remote
            return CloudServiceResult(
                service=CloudServiceName.CLOUDBRAIN_STATUS,
                success=True,
                error=remote.error,
                result={
                    "topology": topology,
                    "remote_runtime_error": remote.error,
                },
                source="local",
            )

        return CloudServiceResult(
            service=CloudServiceName.CLOUDBRAIN_STATUS,
            success=True,
            result=topology,
            source="local",
        )

    async def _cloudbrain_memory(self, payload: dict[str, Any]) -> CloudServiceResult:
        agent_id = str(payload.get("agent_id", "merlin"))
        try:
            memories = _long_term_cloudbrain().pull_long_term_memory(agent_id)
            return CloudServiceResult(
                service=CloudServiceName.CLOUDBRAIN_MEMORY,
                success=True,
                result={
                    "agent_id": agent_id,
                    "memory_count": len(memories),
                    "memories": memories,
                    "brain_roles": self._brain_role_manifest(),
                },
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.CLOUDBRAIN_MEMORY,
                success=False,
                error=str(exc),
                source="local",
            )

    async def _research_agency(self, payload: dict[str, Any]) -> CloudServiceResult:
        if self.research_url:
            try:
                async def _do_post() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=False)) as client:
                        return await client.post(self.research_url, json=payload)

                response = await self.policy.execute_http(_do_post, service_key="research_agency", is_health=False)
                return CloudServiceResult(
                    service=CloudServiceName.RESEARCH_AGENCY,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_bridge_url:
                    fallback = await self._invoke_excalibur_bridge(
                        task=f"research investigate objective: {str(payload.get('objective') or '').strip() or 'research investigate objective'}",
                        mode="RESEARCH",
                        service=CloudServiceName.RESEARCH_AGENCY,
                        payload=payload,
                    )
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.RESEARCH_AGENCY,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_bridge_url:
            objective = str(payload.get("objective") or "").strip() or "research investigate objective"
            return await self._invoke_excalibur_bridge(
                task=f"research investigate objective: {objective}",
                mode="RESEARCH",
                service=CloudServiceName.RESEARCH_AGENCY,
                payload=payload,
            )

        # ── Browser Research Agency (Perplexity-killer, zero paid API) ──
        try:
            import sys
            from pathlib import Path as _Path
            _knights_dir = str(
                _Path(os.environ.get("CAMELOT_OS_HOME", _Path.home() / "CAMELOT_OS"))
                / "03_VAULT" / "training" / "configs"
            )
            if _knights_dir not in sys.path:
                sys.path.insert(0, _knights_dir)
            from knights.browser_research_agency import BrowserResearchAgency
            objective = str(payload.get("objective") or "").strip() or "general research"
            tier = str(payload.get("compute_tier") or "hybrid").lower()
            agency = BrowserResearchAgency(tier=tier)
            brief = await agency.run(objective, constraints=payload.get("constraints"))
            return CloudServiceResult(
                service=CloudServiceName.RESEARCH_AGENCY,
                success=True,
                result=brief.to_cloud_result(),
                source="browser_nano_knights",
            )
        except ImportError:
            pass  # browser-use not installed — fall through to Modal stub
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.RESEARCH_AGENCY,
                success=False,
                error=f"BrowserResearchAgency: {exc}",
                source="browser_nano_knights",
            )

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.RESEARCH_AGENCY,
                env_var="CAMELOT_RESEARCH_AGENCY_URL",
            )

        try:
            result = _modal_services().run_research_agency(payload)
            return CloudServiceResult(
                service=CloudServiceName.RESEARCH_AGENCY,
                success=True,
                result=result,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.RESEARCH_AGENCY,
                success=False,
                error=str(exc),
                source="local",
            )

    async def _research_agency_health(self) -> CloudServiceResult:
        if self.research_health_url:
            try:
                async def _do_get() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=True)) as client:
                        return await client.get(self.research_health_url)

                response = await self.policy.execute_http(_do_get, service_key="research_agency_health", is_health=True)
                return CloudServiceResult(
                    service=CloudServiceName.RESEARCH_AGENCY_HEALTH,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_health_url:
                    fallback = await self._invoke_excalibur_health(CloudServiceName.RESEARCH_AGENCY_HEALTH)
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.RESEARCH_AGENCY_HEALTH,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_health_url:
            return await self._invoke_excalibur_health(CloudServiceName.RESEARCH_AGENCY_HEALTH)

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.RESEARCH_AGENCY_HEALTH,
                env_var="CAMELOT_RESEARCH_AGENCY_HEALTH_URL",
            )

        return CloudServiceResult(
            service=CloudServiceName.RESEARCH_AGENCY_HEALTH,
            success=True,
            result=_modal_services().research_agency_health(),
            source="local",
        )

    async def _northstar(self, payload: dict[str, Any]) -> CloudServiceResult:
        if self.northstar_url:
            try:
                async def _do_post() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=False)) as client:
                        return await client.post(self.northstar_url, json=payload)

                response = await self.policy.execute_http(_do_post, service_key="northstar", is_health=False)
                return CloudServiceResult(
                    service=CloudServiceName.NORTHSTAR,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_bridge_url:
                    fallback = await self._invoke_excalibur_bridge(
                        task=f"northstar war room objective: {str(payload.get('objective') or '').strip() or 'northstar war room objective'}",
                        mode="ANALYSIS",
                        service=CloudServiceName.NORTHSTAR,
                        payload=payload,
                    )
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.NORTHSTAR,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_bridge_url:
            objective = str(payload.get("objective") or "").strip() or "northstar war room objective"
            return await self._invoke_excalibur_bridge(
                task=f"northstar war room objective: {objective}",
                mode="ANALYSIS",
                service=CloudServiceName.NORTHSTAR,
                payload=payload,
            )

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.NORTHSTAR,
                env_var="CAMELOT_NORTHSTAR_URL",
            )

        try:
            result = _modal_services().run_northstar(payload)
            return CloudServiceResult(
                service=CloudServiceName.NORTHSTAR,
                success=True,
                result=result,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NORTHSTAR,
                success=False,
                error=str(exc),
                source="local",
            )

    async def _northstar_health(self) -> CloudServiceResult:
        if self.northstar_health_url:
            try:
                async def _do_get() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=True)) as client:
                        return await client.get(self.northstar_health_url)

                response = await self.policy.execute_http(_do_get, service_key="northstar_health", is_health=True)
                return CloudServiceResult(
                    service=CloudServiceName.NORTHSTAR_HEALTH,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_health_url:
                    fallback = await self._invoke_excalibur_health(CloudServiceName.NORTHSTAR_HEALTH)
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.NORTHSTAR_HEALTH,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_health_url:
            return await self._invoke_excalibur_health(CloudServiceName.NORTHSTAR_HEALTH)

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.NORTHSTAR_HEALTH,
                env_var="CAMELOT_NORTHSTAR_HEALTH_URL",
            )

        return CloudServiceResult(
            service=CloudServiceName.NORTHSTAR_HEALTH,
            success=True,
            result=_modal_services().northstar_health(),
            source="local",
        )

    async def _development_blueprint(self, payload: dict[str, Any]) -> CloudServiceResult:
        if self.blueprint_url:
            try:
                async def _do_post() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=False)) as client:
                        return await client.post(self.blueprint_url, json=payload)

                response = await self.policy.execute_http(_do_post, service_key="development_blueprint", is_health=False)
                return CloudServiceResult(
                    service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_bridge_url:
                    fallback = await self._invoke_excalibur_bridge(
                        task=f"development blueprint objective: {str(payload.get('objective') or '').strip() or 'development blueprint objective'}",
                        mode="DEV",
                        service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                        payload=payload,
                    )
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_bridge_url:
            objective = str(payload.get("objective") or "").strip() or "development blueprint objective"
            return await self._invoke_excalibur_bridge(
                task=f"development blueprint objective: {objective}",
                mode="DEV",
                service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                payload=payload,
            )

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                env_var="CAMELOT_BLUEPRINT_URL",
            )

        try:
            result = _modal_services().run_development_blueprint(payload)
            return CloudServiceResult(
                service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                success=True,
                result=result,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                success=False,
                error=str(exc),
                source="local",
            )

    async def _development_blueprint_health(self) -> CloudServiceResult:
        if self.blueprint_health_url:
            try:
                async def _do_get() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=True)) as client:
                        return await client.get(self.blueprint_health_url)

                response = await self.policy.execute_http(_do_get, service_key="development_blueprint_health", is_health=True)
                return CloudServiceResult(
                    service=CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_health_url:
                    fallback = await self._invoke_excalibur_health(CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH)
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_health_url:
            return await self._invoke_excalibur_health(CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH)

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH,
                env_var="CAMELOT_BLUEPRINT_HEALTH_URL",
            )

        return CloudServiceResult(
            service=CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH,
            success=True,
            result=_modal_services().development_blueprint_health(),
            source="local",
        )

    async def _precise_mode(self, payload: dict[str, Any]) -> CloudServiceResult:
        if self.precise_mode_url:
            try:
                async def _do_post() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=False)) as client:
                        return await client.post(self.precise_mode_url, json=payload)

                response = await self.policy.execute_http(_do_post, service_key="precise_mode", is_health=False)
                return CloudServiceResult(
                    service=CloudServiceName.PRECISE_MODE,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_bridge_url:
                    fallback = await self._invoke_excalibur_bridge(
                        task=f"precise mode objective: {str(payload.get('objective') or '').strip() or 'precise mode objective'}",
                        mode="ANALYSIS",
                        service=CloudServiceName.PRECISE_MODE,
                        payload=payload,
                    )
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.PRECISE_MODE,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_bridge_url:
            objective = str(payload.get("objective") or "").strip() or "precise mode objective"
            return await self._invoke_excalibur_bridge(
                task=f"precise mode objective: {objective}",
                mode="ANALYSIS",
                service=CloudServiceName.PRECISE_MODE,
                payload=payload,
            )

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.PRECISE_MODE,
                env_var="CAMELOT_PRECISE_MODE_URL",
            )

        try:
            result = _modal_services().run_precise_mode(payload)
            return CloudServiceResult(
                service=CloudServiceName.PRECISE_MODE,
                success=True,
                result=result,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.PRECISE_MODE,
                success=False,
                error=str(exc),
                source="local",
            )

    async def _precise_mode_health(self) -> CloudServiceResult:
        if self.precise_mode_health_url:
            try:
                async def _do_get() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=True)) as client:
                        return await client.get(self.precise_mode_health_url)

                response = await self.policy.execute_http(_do_get, service_key="precise_mode_health", is_health=True)
                return CloudServiceResult(
                    service=CloudServiceName.PRECISE_MODE_HEALTH,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_health_url:
                    fallback = await self._invoke_excalibur_health(CloudServiceName.PRECISE_MODE_HEALTH)
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.PRECISE_MODE_HEALTH,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_health_url:
            return await self._invoke_excalibur_health(CloudServiceName.PRECISE_MODE_HEALTH)

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.PRECISE_MODE_HEALTH,
                env_var="CAMELOT_PRECISE_MODE_HEALTH_URL",
            )

        return CloudServiceResult(
            service=CloudServiceName.PRECISE_MODE_HEALTH,
            success=True,
            result=_modal_services().precise_mode_health(),
            source="local",
        )

    async def _eldergod_forge(self, payload: dict[str, Any]) -> CloudServiceResult:
        if self.eldergod_url:
            try:
                async def _do_post() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=False)) as client:
                        return await client.post(self.eldergod_url, json=payload)

                response = await self.policy.execute_http(_do_post, service_key="eldergod_forge", is_health=False)
                return CloudServiceResult(
                    service=CloudServiceName.ELDERGOD_FORGE,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_bridge_url:
                    fallback = await self._invoke_excalibur_bridge(
                        task=f"elderGod forge objective: {str(payload.get('objective') or '').strip() or 'elderGod forge objective'}",
                        mode="DEV",
                        service=CloudServiceName.ELDERGOD_FORGE,
                        payload=payload,
                    )
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.ELDERGOD_FORGE,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_bridge_url:
            objective = str(payload.get("objective") or "").strip() or "elderGod forge objective"
            return await self._invoke_excalibur_bridge(
                task=f"elderGod forge objective: {objective}",
                mode="DEV",
                service=CloudServiceName.ELDERGOD_FORGE,
                payload=payload,
            )

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.ELDERGOD_FORGE,
                env_var="CAMELOT_ELDERGOD_URL",
            )

        try:
            result = _modal_services().run_eldergod_forge(payload)
            return CloudServiceResult(
                service=CloudServiceName.ELDERGOD_FORGE,
                success=True,
                result=result,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.ELDERGOD_FORGE,
                success=False,
                error=str(exc),
                source="local",
            )

    async def _eldergod_forge_health(self) -> CloudServiceResult:
        if self.eldergod_health_url:
            try:
                async def _do_get() -> httpx.Response:
                    async with httpx.AsyncClient(timeout=self.policy.get_httpx_timeout(is_health=True)) as client:
                        return await client.get(self.eldergod_health_url)

                response = await self.policy.execute_http(_do_get, service_key="eldergod_forge_health", is_health=True)
                return CloudServiceResult(
                    service=CloudServiceName.ELDERGOD_FORGE_HEALTH,
                    success=True,
                    result=response.json(),
                    source="remote",
                )
            except Exception as exc:
                if self.excalibur_health_url:
                    fallback = await self._invoke_excalibur_health(CloudServiceName.ELDERGOD_FORGE_HEALTH)
                    if fallback.success:
                        fallback.result.setdefault("typed_endpoint_error", str(exc))
                        return fallback
                return CloudServiceResult(
                    service=CloudServiceName.ELDERGOD_FORGE_HEALTH,
                    success=False,
                    error=str(exc),
                    source="remote",
                )

        if self.excalibur_health_url:
            return await self._invoke_excalibur_health(CloudServiceName.ELDERGOD_FORGE_HEALTH)

        if not _has_modal_sdk():
            return _missing_remote_service_result(
                service=CloudServiceName.ELDERGOD_FORGE_HEALTH,
                env_var="CAMELOT_ELDERGOD_HEALTH_URL",
            )

        return CloudServiceResult(
            service=CloudServiceName.ELDERGOD_FORGE_HEALTH,
            success=True,
            result=_modal_services().eldergod_forge_health(),
            source="local",
        )

    async def _health_rollup(self, probe_remote: bool = True) -> CloudServiceResult:
        """Unified health rollup across cloudbrain, research, northstar, blueprint,

        precise-mode, eldergod forge, notebooklm, and deployment contract (Track B5).
        """
        from .deployment_contract import validate_deployment_contract

        contract_report = validate_deployment_contract()

        # Run health probes concurrently
        probes = {
            "cloudbrain": self._cloudbrain_status(),
            "research": self._research_agency_health(),
            "northstar": self._northstar_health(),
            "blueprint": self._development_blueprint_health(),
            "precise_mode": self._precise_mode_health(),
            "eldergod": self._eldergod_forge_health(),
            "notebooklm": self._notebooklm_health(),
        }

        keys = list(probes.keys())
        probe_results = await asyncio.gather(*probes.values(), return_exceptions=True)

        results: dict[str, CloudServiceResult] = {}
        for key, res in zip(keys, probe_results):
            if isinstance(res, Exception):
                results[key] = CloudServiceResult(
                    service=CloudServiceName.HEALTH_ROLLUP,
                    success=False,
                    error=str(res),
                    source="error",
                )
            else:
                results[key] = res

        # Evaluate status per subsystem
        subsystems: dict[str, dict[str, Any]] = {}
        healthy_count = 0
        total_count = len(results)

        core_services = {"cloudbrain", "research", "northstar", "blueprint", "precise_mode"}
        core_failures = 0
        fallback_count = 0

        for key, r in results.items():
            is_healthy = r.success
            source = r.source
            if is_healthy:
                healthy_count += 1
                if source in {"local", "local_fallback", "browser_nano_knights"}:
                    fallback_count += 1
            else:
                if key in core_services:
                    core_failures += 1

            subsystems[key] = {
                "service": r.service.value if hasattr(r, "service") else key,
                "healthy": r.success,
                "status": "ONLINE" if (r.success and source == "remote") else ("FALLBACK" if r.success else "OFFLINE"),
                "source": source,
                "error": r.error,
                "summary": r.result.get("status") or r.result.get("message") or ("OK" if r.success else "FAILED"),
            }

        if core_failures == 0 and contract_report.status == "PASS" and healthy_count == total_count:
            overall_status = "HEALTHY"
        elif core_failures == 0:
            overall_status = "DEGRADED"
        else:
            overall_status = "UNAVAILABLE"

        score_pct = round((healthy_count / total_count) * 100, 1)

        rollup_data = {
            "overall_status": overall_status,
            "score_pct": score_pct,
            "healthy_count": healthy_count,
            "total_count": total_count,
            "fallback_count": fallback_count,
            "subsystems": subsystems,
            "deployment_contract": contract_report.to_dict(),
            "circuit_breaker": self.policy.get_circuit_summary(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return CloudServiceResult(
            service=CloudServiceName.HEALTH_ROLLUP,
            success=(overall_status in {"HEALTHY", "DEGRADED"}),
            result=rollup_data,
            error=None if overall_status in {"HEALTHY", "DEGRADED"} else f"{core_failures} core services unavailable",
            source="rollup",
        )

    # --- NotebookLM Cloud Brain (Omega₃) ---------------------------------------


    async def _notebooklm_health(self) -> CloudServiceResult:
        try:
            bridge = _load_notebooklm_bridge()
            ok, msg, latency_ms = await bridge.async_health_probe()
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_HEALTH,
                success=ok,
                result={"message": msg, "latency_ms": round(latency_ms)},
                error=None if ok else msg,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_HEALTH,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                source="local",
            )

    async def _notebooklm_synthesize(self, payload: dict[str, Any]) -> CloudServiceResult:
        query = str(payload.get("query") or payload.get("question") or "").strip()
        if not query:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SYNTHESIZE,
                success=False,
                error="missing 'query' in payload",
                source="local",
            )
        notebook_id = payload.get("notebook_id")
        use_cache = bool(payload.get("use_cache", True))
        try:
            bridge = _load_notebooklm_bridge()
            kwargs: dict[str, Any] = {"use_cache": use_cache}
            if notebook_id:
                kwargs["notebook_id"] = str(notebook_id)
            text = await bridge.async_synthesize(query, **kwargs)
            ok = text is not None and not str(text).startswith("[Cloud Brain synthesis failed")
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SYNTHESIZE,
                success=ok,
                result={
                    "query": query,
                    "notebook_id": notebook_id or bridge.CANONICAL_NOTEBOOK_ID,
                    "text": text,
                    "cache": bridge.cache_stats(),
                },
                error=None if ok else str(text),
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SYNTHESIZE,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                source="local",
            )

    async def _notebooklm_sync(self, payload: dict[str, Any]) -> CloudServiceResult:
        try:
            bridge = _load_notebooklm_bridge()
            kwargs: dict[str, Any] = {}
            if payload.get("notebook_id"):
                kwargs["notebook_id"] = str(payload["notebook_id"])
            if payload.get("note_title"):
                kwargs["note_title"] = str(payload["note_title"])
            if payload.get("extra_summary"):
                kwargs["extra_summary"] = str(payload["extra_summary"])
            if payload.get("content"):
                kwargs["content"] = str(payload["content"])
            result = await bridge.async_sync_state(**kwargs)
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SYNC,
                success="error" not in result,
                result=result if "error" not in result else {},
                error=result.get("error") if "error" in result else None,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SYNC,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                source="local",
            )

    # --- Omega₃.2 LADY_APIS research ---------------------------------------

    async def _notebooklm_research_start(self, payload: dict[str, Any]) -> CloudServiceResult:
        query = str(payload.get("query") or payload.get("objective") or "").strip()
        if not query:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_RESEARCH_START,
                success=False, error="missing 'query' in payload", source="local",
            )
        try:
            bridge = _load_notebooklm_bridge()
            result = await bridge.async_research_start(
                query,
                notebook_id=str(payload.get("notebook_id") or bridge.CANONICAL_NOTEBOOK_ID),
                source=str(payload.get("source", "web")),
                mode=str(payload.get("mode", "fast")),
            )
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_RESEARCH_START,
                success=True, result=result, source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_RESEARCH_START,
                success=False, error=f"{type(exc).__name__}: {exc}", source="local",
            )

    async def _notebooklm_research_poll(self, payload: dict[str, Any]) -> CloudServiceResult:
        try:
            bridge = _load_notebooklm_bridge()
            result = await bridge.async_research_poll(
                notebook_id=str(payload.get("notebook_id") or bridge.CANONICAL_NOTEBOOK_ID),
            )
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_RESEARCH_POLL,
                success=True, result=result, source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_RESEARCH_POLL,
                success=False, error=f"{type(exc).__name__}: {exc}", source="local",
            )

    # --- Omega₃.3 SIR_SONUS studio ----------------------------------------

    async def _notebooklm_studio_list(self, payload: dict[str, Any]) -> CloudServiceResult:
        try:
            bridge = _load_notebooklm_bridge()
            result = await bridge.async_studio_list(
                artifact_type=str(payload.get("artifact_type", "audio")),
                notebook_id=str(payload.get("notebook_id") or bridge.CANONICAL_NOTEBOOK_ID),
            )
            ok = "error" not in result
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_STUDIO_LIST,
                success=ok,
                result=result if ok else {},
                error=result.get("error") if not ok else None,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_STUDIO_LIST,
                success=False, error=f"{type(exc).__name__}: {exc}", source="local",
            )

    async def _notebooklm_studio_generate(self, payload: dict[str, Any]) -> CloudServiceResult:
        artifact_type = str(payload.get("artifact_type") or "").strip()
        if not artifact_type:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_STUDIO_GENERATE,
                success=False, error="missing 'artifact_type' in payload", source="local",
            )
        try:
            bridge = _load_notebooklm_bridge()
            source_ids = payload.get("source_ids")
            result = await bridge.async_studio_generate(
                artifact_type,
                notebook_id=str(payload.get("notebook_id") or bridge.CANONICAL_NOTEBOOK_ID),
                instructions=payload.get("instructions"),
                source_ids=list(source_ids) if source_ids else None,
            )
            ok = "error" not in result
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_STUDIO_GENERATE,
                success=ok,
                result=result if ok else {},
                error=result.get("error") if not ok else None,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_STUDIO_GENERATE,
                success=False, error=f"{type(exc).__name__}: {exc}", source="local",
            )

    # --- Omega₃.4 MASON sources -------------------------------------------

    async def _notebooklm_sources_list(self, payload: dict[str, Any]) -> CloudServiceResult:
        try:
            bridge = _load_notebooklm_bridge()
            result = await bridge.async_sources_list(
                notebook_id=str(payload.get("notebook_id") or bridge.CANONICAL_NOTEBOOK_ID),
            )
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_LIST,
                success=True, result=result, source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_LIST,
                success=False, error=f"{type(exc).__name__}: {exc}", source="local",
            )

    async def _notebooklm_sources_add(self, payload: dict[str, Any]) -> CloudServiceResult:
        try:
            bridge = _load_notebooklm_bridge()
            result = await bridge.async_sources_add(
                url=payload.get("url"),
                text=payload.get("text"),
                title=payload.get("title"),
                notebook_id=str(payload.get("notebook_id") or bridge.CANONICAL_NOTEBOOK_ID),
                wait=bool(payload.get("wait", False)),
            )
            ok = "error" not in result
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_ADD,
                success=ok,
                result=result if ok else {},
                error=result.get("error") if not ok else None,
                source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_ADD,
                success=False, error=f"{type(exc).__name__}: {exc}", source="local",
            )

    async def _notebooklm_sources_delete(self, payload: dict[str, Any]) -> CloudServiceResult:
        source_id = str(payload.get("source_id") or "").strip()
        if not source_id:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_DELETE,
                success=False, error="missing 'source_id' in payload", source="local",
            )
        try:
            bridge = _load_notebooklm_bridge()
            result = await bridge.async_sources_delete(
                source_id,
                notebook_id=str(payload.get("notebook_id") or bridge.CANONICAL_NOTEBOOK_ID),
            )
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_DELETE,
                success=True, result=result, source="local",
            )
        except Exception as exc:
            return CloudServiceResult(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_DELETE,
                success=False, error=f"{type(exc).__name__}: {exc}", source="local",
            )
