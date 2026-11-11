# SPDX-License-Identifier: MIT
"""Read-only Bifrost routing and local-model policy inspection."""

from __future__ import annotations

import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from control_plane.cli.constants import CAMELOT_HOME
from control_plane.cli.renderer import _emit
from control_plane.dispatch.bifrost_gateway import health
from control_plane.dispatch.omniroute_policies import (
    LANE_MAXIM_BIFROST_GATEWAY,
    get_fcc_provider_policy,
)

_SECRET_NAME = r"(?:[A-Za-z0-9]+[_-])*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|passwd)"
_SECRET_PATTERN = re.compile(
    rf"(?i)\b({_SECRET_NAME})\s*([=:])\s*([^\s,;]+)"
)
_QUOTED_SECRET_PATTERN = re.compile(
    rf"""(?i)(["']{_SECRET_NAME}["']\s*:\s*["'])([^"']+)(["'])"""
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_MODEL_SIZE_PATTERN = re.compile(r"(?i)(?<![a-z0-9])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])")
_QUANT_PATTERN = re.compile(r"(?i)(q\d|int\d|awq|gptq|gguf|4bit|8bit|4-bit|8-bit)")
_SMALL_MODEL_PATTERN = re.compile(
    r"(?i)(tiny|mini|small|nano|4-bit|8-bit|q4|q8|int4|int8|awq|gptq|gguf|quant|quantized|whisper-base|tts|vad)"
)
_SMALL_MAX_BILLION_PARAMS = 4.0
_APPROVED_BIFROST_HOSTS = frozenset({"100.110.180.18"})
_DEFAULT_MODEL_PATH = CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "sovereign_models.json"
_DEFAULT_REGISTRY_PATH = CAMELOT_HOME / "01_KERNEL" / "memory" / "bifrost_knight_llm_registry.json"
_MAX_WORKER_RAM_MB = 512


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower().rstrip(".")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _safe_bifrost_endpoint(value: object) -> bool:
    try:
        parsed = urlparse(str(value))
        host = parsed.hostname
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    return _is_loopback_host(host) or host in _APPROVED_BIFROST_HOSTS


def _is_explicit_bifrost_hub_entry(
    entry: dict[str, Any],
    route_key: str = "bifrost_route",
    allowed_routes: set[str] | None = None,
) -> bool:
    if entry.get("inference_scope") != "bifrost_hub":
        return False
    route = str(entry.get(route_key, ""))
    endpoint = entry.get("bifrost_endpoint", entry.get("endpoint", ""))
    if not route.startswith("/bifrost/") or not _safe_bifrost_endpoint(endpoint):
        return False
    return allowed_routes is None or route in allowed_routes


def redact_text(value: str) -> str:
    value = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)
    value = _QUOTED_SECRET_PATTERN.sub(r"\1[REDACTED]\3", value)
    return _BEARER_PATTERN.sub("Bearer [REDACTED]", value)


def _model_is_small_or_quantized(tag: str) -> bool:
    normalized = tag.strip()
    sizes = [float(match.group(1)) for match in _MODEL_SIZE_PATTERN.finditer(normalized)]
    if _QUANT_PATTERN.search(normalized):
        return True
    if sizes and max(sizes) > _SMALL_MAX_BILLION_PARAMS:
        return False
    if _SMALL_MODEL_PATTERN.search(normalized):
        return True
    return bool(sizes) and max(sizes) <= _SMALL_MAX_BILLION_PARAMS


def _policy_for_tag(tag: str) -> dict[str, Any]:
    if _model_is_small_or_quantized(tag):
        return {"status": "PASS", "reason": "tiny or quantized model"}
    return {
        "status": "REVIEW",
        "reason": "local model is not proven tiny or quantized",
    }


def _local_policy_for_intent(intent: str) -> dict[str, Any]:
    lowered = intent.lower()
    if any(token in lowered for token in ("vllm", "ollama", "local", "offline", "quantized", "q4", "q8")):
        return {
            "status": "REVIEW",
            "reasons": ["intent requests a local backend; model tag must be validated by bifrost validate"],
        }
    return {
        "status": "PASS",
        "reasons": ["no local model backend requested"],
    }


def _model_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else _DEFAULT_MODEL_PATH


def _registry_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else _DEFAULT_REGISTRY_PATH


def _validate_bifrost_registry(path: str | Path | None = None) -> dict[str, Any]:
    target = _registry_path(path)
    errors: list[str] = []
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "status": "FAIL",
            "read_only": True,
            "root": str(target),
            "errors": [f"unable to load Bifrost registry: {type(exc).__name__}"],
            "violations": [],
            "hub_routes": [],
        }

    bridge = document.get("bifrost_bridge", {})
    hub_routes: set[str] = set()
    if not isinstance(bridge, dict):
        errors.append("bifrost_bridge must be an object")
        bridge = {}
    endpoint = bridge.get("ws_endpoint")
    if endpoint:
        parsed = urlparse(str(endpoint))
        if parsed.scheme != "ws" or parsed.hostname not in _APPROVED_BIFROST_HOSTS:
            errors.append("Bifrost WebSocket endpoint is not the approved VPS hub")
    else:
        errors.append("Bifrost WebSocket endpoint is missing")
    if bridge.get("mTLS") is not True:
        errors.append("Bifrost bridge must require mTLS")
    fallback_proxy = bridge.get("fallback_proxy")
    if fallback_proxy:
        fallback_host = urlparse(str(fallback_proxy)).hostname
        if fallback_host not in {"127.0.0.1", "localhost", "::1"}:
            errors.append("Bifrost fallback proxy must remain loopback-only")

    allocations = document.get("knight_pill_allocations", [])
    if not isinstance(allocations, list):
        errors.append("knight_pill_allocations must be an array")
        allocations = []
    for allocation in allocations:
        if not isinstance(allocation, dict):
            errors.append("allocation entry must be an object")
            continue
        worker_ram = allocation.get("worker_ram_mb")
        if isinstance(worker_ram, (int, float)) and worker_ram > _MAX_WORKER_RAM_MB:
            errors.append(f"{allocation.get('knight_id', 'unknown')}: worker allocation exceeds 512 MB")
        route = str(allocation.get("bifrost_route", ""))
        if not route.startswith("/bifrost/"):
            errors.append(f"{allocation.get('knight_id', 'unknown')}: allocation is not bound to a Bifrost route")
        if allocation.get("inference_scope") == "bifrost_hub":
            if not _is_explicit_bifrost_hub_entry(allocation):
                errors.append(f"{allocation.get('knight_id', 'unknown')}: hub-scoped allocation needs a Bifrost route and safe endpoint")
            else:
                hub_routes.add(route)
        else:
            model = str(allocation.get("assigned_tiny_llm", ""))
            if model and not _model_is_small_or_quantized(model):
                errors.append(f"{allocation.get('knight_id', 'unknown')}: assigned model is not proven tiny or quantized")

    return {
        "status": "FAIL" if errors else "PASS",
        "read_only": True,
        "root": str(target),
        "errors": errors,
        "violations": errors,
        "hub_routes": sorted(hub_routes),
    }


def validate_routing_config(
    path: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Inspect the model manifest and classify local entries by size/quantization."""
    target = _model_path(path)
    errors: list[str] = []
    violations: list[dict[str, str]] = []
    models: dict[str, Any] = {}

    try:
        document = json.loads(target.read_text(encoding="utf-8"))
        models = document.get("models", {})
        if not isinstance(models, dict):
            raise ValueError("models must be an object")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"unable to load model manifest: {type(exc).__name__}")
        models = {}

    registry = _validate_bifrost_registry(registry_path)
    hub_routes = set(registry.get("hub_routes", []))

    for name, entry in models.items():
        if not isinstance(entry, dict):
            errors.append(f"{name}: model entry must be an object")
            continue
        backend = str(entry.get("backend", ""))
        tag = str(entry.get("tag", ""))
        if backend in {"ollama", "vllm", "transformers", "llamacpp"}:
            if entry.get("inference_scope") == "bifrost_hub":
                if not _is_explicit_bifrost_hub_entry(entry, allowed_routes=hub_routes):
                    violations.append({
                        "model": name,
                        "backend": backend,
                        "tag": tag,
                        "reason": "hub-scoped model needs a Bifrost route and safe endpoint",
                    })
            else:
                policy = _policy_for_tag(tag)
                if policy["status"] != "PASS":
                    violations.append({"model": name, "backend": backend, "tag": tag, "reason": policy["reason"]})

    local_policy = {
        "status": "FAIL" if violations else "PASS",
        "checked_models": sorted(models),
        "violations": violations,
    }
    return {
        "status": "FAIL" if errors or violations or registry["status"] == "FAIL" else "PASS",
        "read_only": True,
        "root": str(target),
        "errors": errors,
        "local_policy": local_policy,
        "bifrost_registry": registry,
    }


def build_route_preview(intent: str) -> dict[str, Any]:
    """Return a deterministic policy preview without invoking a model or network."""
    redacted_intent = redact_text(intent)
    policy = get_fcc_provider_policy(intent)
    local_policy = _local_policy_for_intent(intent)
    bifrost_first = policy["lane"] == LANE_MAXIM_BIFROST_GATEWAY
    return {
        "status": "OK",
        "read_only": True,
        "execution": "not_invoked",
        "intent_redacted": redacted_intent,
        "lane": policy["lane"],
        "matched_keyword": policy["matched_keyword"],
        "rationale": policy["rationale"],
        "provider_chain": policy["failover_chain"],
        "primary_provider": policy["primary_provider"],
        "bifrost_first": bifrost_first,
        "local_policy": local_policy,
    }


def build_status(probe: bool = False) -> dict[str, Any]:
    if not probe:
        return {
            "status": "CONFIGURED",
            "read_only": True,
            "probe_performed": False,
            "gateway_url_configured": bool(os.environ.get("BIFROST_GATEWAY_URL", "")),
            "execution": "not_invoked",
        }
    result = health()
    return {
        "status": "ONLINE" if result.get("ok") else "UNAVAILABLE",
        "read_only": True,
        "probe_performed": True,
        "execution": "not_invoked",
        "gateway": {
            "ok": bool(result.get("ok")),
            "status_code": result.get("status_code"),
            "error": result.get("error"),
        },
    }


def handle_bifrost(args: Any, _config_mgr: Any, _prov_mgr: Any, _argv: list[str]) -> int:
    command = getattr(args, "bifrost_command", None)
    if command == "route":
        result = build_route_preview(" ".join(getattr(args, "intent", [])))
    elif command == "status":
        result = build_status(probe=bool(getattr(args, "probe", False)))
    elif command == "validate":
        result = validate_routing_config(
            getattr(args, "path", None),
            registry_path=getattr(args, "registry", None),
        )
    else:
        result = {
            "status": "ERROR",
            "read_only": True,
            "error": "unknown bifrost command",
        }

    _emit(result, json_mode=getattr(args, "json", False), title="Bifrost Routing")
    return 0 if result.get("status") in {"OK", "CONFIGURED", "ONLINE", "PASS"} else 1
