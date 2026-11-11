# SPDX-License-Identifier: MIT

"""Camelot-OS Configuration Manager — Persisted Operator Profiles."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


class OperatorProfile(BaseModel):
    """Operator policy for browser swarms and cloud services."""
    compute_tier: str = "hybrid"
    browser_isolation: str = "agency"
    residential_proxy: bool = True
    stealth: bool = True
    ephemeral_sessions: bool = True
    privacy_threshold: float = 0.0


class SubstrateProfile(BaseModel):
    """EXCALIBUR v1000.0.0 substrate (hardware) profile + physical-law thresholds.

    Adjudicated at boot by control_plane/excalibur_preflight.py. Ported from the
    LUKAS_FORGE bash kit; the bash 'nitro-v15-cpu' Linux target and the native
    Windows 'cybertronia-win' target share the same physical laws.
    """
    arch_req: list[str] = Field(default_factory=lambda: ["x86_64", "amd64"])
    ram_ceiling_mb: int = 8192
    ram_expect_min_mb: int = 7000
    boot_sprawl_max_mb: int = 1200      # RL-Conductor sprawl during boot
    trellis_pool_mb: int = 512          # fixed KV-pool reservation
    headroom_req_mb: int = 1712         # boot_sprawl_max + trellis_pool
    store_min_free_mb: int = 4096       # Rust/WASM target dirs
    sandbox_primitives: list[str] = Field(default_factory=lambda: ["wsl", "docker", "windows-sandbox"])
    ebpf_required: bool = False         # soft on Windows (regex-only PII fallback)
    os_family: str = "windows"


class CamelotConfig(BaseModel):
    """Canonical Camelot-OS configuration."""
    cloudbrain_url: Optional[str] = None
    living_notebook_url: Optional[str] = None
    research_agency_url: Optional[str] = None
    research_agency_health_url: Optional[str] = None
    northstar_url: Optional[str] = None
    northstar_health_url: Optional[str] = None
    blueprint_url: Optional[str] = None
    blueprint_health_url: Optional[str] = None
    precise_mode_url: Optional[str] = None
    precise_mode_health_url: Optional[str] = None
    excalibur_bridge_url: Optional[str] = None
    excalibur_health_url: Optional[str] = None
    warp_repo_workflows_path: str = ".warp/workflows"
    warp_local_workflows_path: str = "C:/Users/vizio/AppData/Roaming/warp/Warp/data/workflows"
    active_profile: str = "default"
    profiles: dict[str, OperatorProfile] = Field(default_factory=lambda: {"default": OperatorProfile()})
    # EXCALIBUR substrate (hardware) profiles — adjudicated at boot pre-flight.
    active_substrate: str = "cybertronia-win"
    substrate_profiles: dict[str, SubstrateProfile] = Field(
        default_factory=lambda: {
            # Native Windows host (this box).
            "cybertronia-win": SubstrateProfile(),
            # Linux deployment target (Acer Nitro V 15) — kept as a spec for the
            # original LUKAS_FORGE bash kit.
            "nitro-v15-cpu": SubstrateProfile(
                sandbox_primitives=["bwrap", "proot", "unshare"],
                ebpf_required=False,
                os_family="linux",
            ),
        }
    )


class ConfigManager:
    """Loads and persists Camelot-OS configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path:
            self.config_path = config_path
        else:
            # Default to project root or home directory
            project_root = Path(__file__).parent.parent
            self.config_path = project_root / ".camelot-config.yaml"
            if not self.config_path.exists():
                self.config_path = Path.home() / ".camelot-config.yaml"

        self.config = self._load()

    def _load(self) -> CamelotConfig:
        if not self.config_path.exists():
            return CamelotConfig()

        if self.config_path.suffix in {".yaml", ".yml"} and yaml is None:
            return CamelotConfig()

        try:
            with open(self.config_path, "r") as f:
                if self.config_path.suffix in {".yaml", ".yml"}:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
                return CamelotConfig.model_validate(data or {})
        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            return CamelotConfig()

    def save(self):
        """Persist current configuration to disk."""
        try:
            with open(self.config_path, "w") as f:
                data = self.config.model_dump(exclude_none=True)
                if self.config_path.suffix in {".yaml", ".yml"}:
                    if yaml is None:
                        raise RuntimeError("PyYAML not installed")
                    yaml.safe_dump(data, f, default_flow_style=False)
                else:
                    json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save config to {self.config_path}: {e}")

    def get_profile(self, name: Optional[str] = None) -> OperatorProfile:
        """Retrieve a specific profile or the active one."""
        profile_name = name or self.config.active_profile
        return self.config.profiles.get(profile_name, OperatorProfile())

    def update_profile(self, name: str, profile: OperatorProfile):
        """Update or create a profile."""
        self.config.profiles[name] = profile
        self.save()

    def get_substrate_profile(self, name: Optional[str] = None) -> SubstrateProfile:
        """Retrieve an EXCALIBUR substrate profile or the active one."""
        profile_name = name or self.config.active_substrate
        return self.config.substrate_profiles.get(profile_name, SubstrateProfile())

    def update_substrate_profile(self, name: str, profile: SubstrateProfile):
        """Update or create an EXCALIBUR substrate profile."""
        self.config.substrate_profiles[name] = profile
        self.save()

    def cloud_endpoint_map(self) -> dict[str, str]:
        """Return the effective cloud endpoint map after config hydration rules."""
        keys = [
            "CAMELOT_CLOUDBRAIN_URL",
            "CAMELOT_LIVING_NOTEBOOK_URL",
            "CAMELOT_RESEARCH_AGENCY_URL",
            "CAMELOT_RESEARCH_AGENCY_HEALTH_URL",
            "CAMELOT_NORTHSTAR_URL",
            "CAMELOT_NORTHSTAR_HEALTH_URL",
            "CAMELOT_BLUEPRINT_URL",
            "CAMELOT_BLUEPRINT_HEALTH_URL",
            "CAMELOT_PRECISE_MODE_URL",
            "CAMELOT_PRECISE_MODE_HEALTH_URL",
            "CAMELOT_EXCALIBUR_BRIDGE_URL",
            "CAMELOT_EXCALIBUR_HEALTH_URL",
        ]
        defaults = self._collect_runtime_defaults()
        return {key: defaults.get(key, "") for key in keys}

    def set_cloud_endpoint(self, env_var: str, value: Optional[str]) -> dict[str, str]:
        """Persist a cloud endpoint override into the canonical config file."""
        attr_map = {
            "CAMELOT_CLOUDBRAIN_URL": "cloudbrain_url",
            "CAMELOT_LIVING_NOTEBOOK_URL": "living_notebook_url",
            "CAMELOT_RESEARCH_AGENCY_URL": "research_agency_url",
            "CAMELOT_RESEARCH_AGENCY_HEALTH_URL": "research_agency_health_url",
            "CAMELOT_NORTHSTAR_URL": "northstar_url",
            "CAMELOT_NORTHSTAR_HEALTH_URL": "northstar_health_url",
            "CAMELOT_BLUEPRINT_URL": "blueprint_url",
            "CAMELOT_BLUEPRINT_HEALTH_URL": "blueprint_health_url",
            "CAMELOT_PRECISE_MODE_URL": "precise_mode_url",
            "CAMELOT_PRECISE_MODE_HEALTH_URL": "precise_mode_health_url",
            "CAMELOT_EXCALIBUR_BRIDGE_URL": "excalibur_bridge_url",
            "CAMELOT_EXCALIBUR_HEALTH_URL": "excalibur_health_url",
        }
        attr_name = attr_map.get(env_var)
        if not attr_name:
            raise ValueError(f"Unsupported cloud endpoint key: {env_var}")
        normalized = self._normalize_env_value(value)
        setattr(self.config, attr_name, normalized or None)
        self.save()
        return {
            "env_var": env_var,
            "value": normalized,
            "config_path": str(self.config_path),
        }

    def hydrate_runtime_environment(self) -> dict[str, str]:
        """Populate runtime env vars from repo config without overriding explicit env."""
        env_updates: dict[str, str] = {}
        for key, value in self._collect_runtime_defaults().items():
            if value and not os.getenv(key):
                os.environ[key] = value
                env_updates[key] = value
        return env_updates

    def _collect_runtime_defaults(self) -> dict[str, str]:
        defaults: dict[str, str] = {}
        defaults.update(self._load_repo_env_defaults())
        defaults.update(self._load_tier_runtime_defaults())

        config_defaults = {
            "CAMELOT_CLOUDBRAIN_URL": self._normalize_env_value(self.config.cloudbrain_url),
            "CAMELOT_LIVING_NOTEBOOK_URL": self._normalize_env_value(self.config.living_notebook_url),
            "CAMELOT_RESEARCH_AGENCY_URL": self._normalize_env_value(self.config.research_agency_url),
            "CAMELOT_RESEARCH_AGENCY_HEALTH_URL": self._normalize_env_value(self.config.research_agency_health_url),
            "CAMELOT_NORTHSTAR_URL": self._normalize_env_value(self.config.northstar_url),
            "CAMELOT_NORTHSTAR_HEALTH_URL": self._normalize_env_value(self.config.northstar_health_url),
            "CAMELOT_BLUEPRINT_URL": self._normalize_env_value(self.config.blueprint_url),
            "CAMELOT_BLUEPRINT_HEALTH_URL": self._normalize_env_value(self.config.blueprint_health_url),
            "CAMELOT_PRECISE_MODE_URL": self._normalize_env_value(self.config.precise_mode_url),
            "CAMELOT_PRECISE_MODE_HEALTH_URL": self._normalize_env_value(self.config.precise_mode_health_url),
            "CAMELOT_EXCALIBUR_BRIDGE_URL": self._normalize_env_value(self.config.excalibur_bridge_url),
            "CAMELOT_EXCALIBUR_HEALTH_URL": self._normalize_env_value(self.config.excalibur_health_url),
        }
        for key, value in config_defaults.items():
            if value:
                defaults[key] = value
        return defaults

    @staticmethod
    def _normalize_env_value(value: Optional[str]) -> str:
        normalized = str(value or "").strip()
        if normalized.lower() in {"", "none", "null"}:
            return ""
        return normalized

    def _load_repo_env_defaults(self) -> dict[str, str]:
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env"
        if not env_path.exists():
            return {}

        values: dict[str, str] = {}
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    values[key] = value
        except Exception:
            return {}
        return values

    def _load_tier_runtime_defaults(self) -> dict[str, str]:
        if yaml is None:
            return {}

        project_root = Path(__file__).parent.parent
        tiers_path = project_root / "01_KERNEL" / "config_shim" / "tiers.yaml"
        if not tiers_path.exists():
            return {}

        try:
            data = yaml.safe_load(tiers_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

        cloud = ((data.get("tiers") or {}).get("cloud") or {})
        endpoints = cloud.get("endpoints") or {}
        modal_app = str(cloud.get("modal_app") or "").strip()
        health_url = str(endpoints.get("health") or "").strip()
        defaults: dict[str, str] = {}

        prefix = self._derive_modal_endpoint_prefix(
            health_url=health_url,
            brain_url="",
            modal_app=modal_app,
        )
        if not prefix:
            return defaults

        defaults.update(
            {
                "CAMELOT_RESEARCH_AGENCY_URL": f"{prefix}-research-agency.modal.run",
                "CAMELOT_RESEARCH_AGENCY_HEALTH_URL": f"{prefix}-research-agency-health-endpoint.modal.run",
                "CAMELOT_NORTHSTAR_URL": f"{prefix}-northstar-war-room.modal.run",
                "CAMELOT_NORTHSTAR_HEALTH_URL": f"{prefix}-northstar-health-endpoint.modal.run",
                "CAMELOT_BLUEPRINT_URL": f"{prefix}-development-blueprint.modal.run",
                "CAMELOT_BLUEPRINT_HEALTH_URL": f"{prefix}-development-blueprint-health-endpoint.modal.run",
                "CAMELOT_PRECISE_MODE_URL": f"{prefix}-precise-mode.modal.run",
                "CAMELOT_PRECISE_MODE_HEALTH_URL": f"{prefix}-precise-mode-health-endpoint.modal.run",
            }
        )
        return defaults

    @staticmethod
    def _derive_modal_endpoint_prefix(
        *,
        health_url: str,
        brain_url: str,
        modal_app: str,
    ) -> str:
        for candidate in (health_url, brain_url):
            prefix = ConfigManager._prefix_from_modal_url(candidate)
            if prefix:
                return prefix
        if modal_app:
            return f"https://cyberdad247--{modal_app}"
        return ""

    @staticmethod
    def _prefix_from_modal_url(url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
        except Exception:
            return ""
        host = parsed.netloc.strip()
        if not host.endswith(".modal.run"):
            return ""
        host_without_suffix = host[: -len(".modal.run")]
        for suffix in (
            "-health",
            "-morgana-brain",
            "-research-agency-health-endpoint",
            "-research-agency",
            "-northstar-health-endpoint",
            "-northstar-war-room",
            "-development-blueprint-health-endpoint",
            "-development-blueprint",
            "-precise-mode-health-endpoint",
            "-precise-mode",
        ):
            if host_without_suffix.endswith(suffix):
                host_without_suffix = host_without_suffix[: -len(suffix)]
                break
        if not host_without_suffix:
            return ""
        return f"{parsed.scheme or 'https'}://{host_without_suffix}"
