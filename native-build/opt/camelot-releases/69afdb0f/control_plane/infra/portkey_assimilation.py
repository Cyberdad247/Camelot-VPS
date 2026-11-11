# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

DEFAULT_GATEWAY_URL = "https://api.portkey.ai/v1"
LOCAL_GATEWAY_URL = "http://localhost:8787/v1"


@dataclass(frozen=True)
class PortkeyRuntimeConfig:
    base_url: str
    api_key_env: str = "PORTKEY_API_KEY"
    virtual_key_env: str = "PORTKEY_VIRTUAL_KEY"
    provider: str = "@openai"
    cache_mode: str = "simple"
    retry_attempts: int = 3
    timeout_ms: int = 90_000

    def gateway_config(self) -> dict[str, Any]:
        return {
            "retry": {
                "attempts": self.retry_attempts,
                "on_status_codes": [408, 409, 429, 500, 502, 503, 504],
            },
            "cache": {"mode": self.cache_mode},
            "request_timeout": self.timeout_ms,
            "metadata": {
                "system": "camelot-os",
                "protocol": "universal-critical-thinking",
            },
        }

    def node_client_options(self) -> dict[str, Any]:
        return {
            "apiKey": os.environ.get(self.api_key_env, ""),
            "virtualKey": os.environ.get(self.virtual_key_env, ""),
            "baseURL": self.base_url,
            "config": self.gateway_config(),
        }

    def python_client_options(self) -> dict[str, Any]:
        return {
            "api_key": os.environ.get(self.api_key_env, ""),
            "virtual_key": os.environ.get(self.virtual_key_env, ""),
            "base_url": self.base_url,
            "config": self.gateway_config(),
        }

    def headers_config(self) -> dict[str, Any]:
        return {
            "api_key": os.environ.get(self.api_key_env, ""),
            "provider": self.provider,
            "config": self.gateway_config(),
        }


def load_portkey_runtime_config(*, local_gateway: bool = False) -> PortkeyRuntimeConfig:
    base_url = os.environ.get("PORTKEY_BASE_URL")
    if not base_url:
        base_url = LOCAL_GATEWAY_URL if local_gateway else DEFAULT_GATEWAY_URL
    return PortkeyRuntimeConfig(
        base_url=base_url,
        provider=os.environ.get("PORTKEY_PROVIDER", "@openai"),
        cache_mode=os.environ.get("PORTKEY_CACHE_MODE", "simple"),
        retry_attempts=int(os.environ.get("PORTKEY_RETRY_ATTEMPTS", "3")),
        timeout_ms=int(os.environ.get("PORTKEY_TIMEOUT_MS", "90000")),
    )


def export_runtime_contract(*, local_gateway: bool = False) -> str:
    config = load_portkey_runtime_config(local_gateway=local_gateway)
    return json.dumps(
        {
            "base_url": config.base_url,
            "gateway_config": config.gateway_config(),
            "node_client_options": config.node_client_options(),
            "python_client_options": config.python_client_options(),
            "headers_config": config.headers_config(),
        },
        indent=2,
    )

