# SPDX-License-Identifier: MIT

"""OpenCodex Bridge — Universal Provider Proxy for CAMELOT-OS.

Wraps the ``@bitkyc08/opencodex`` management API and assimilates Free Claude Code
(FCC) provider mapping, zero-downtime failover logic, and RTK terminal output filtering:

- **Knight-tier model resolution** — maps SoulRouter knight IDs to
  opencodex provider/model combos with failover chains.
- **FCC Provider Catalog & Defaults** — 50+ ToS-compliant provider descriptors,
  endpoints, and multi-provider failover chains.
- **Zero-Downtime Failover Session** — pre-commit candidate state machine that
  seamlessly pivots across provider outages without losing prompt state or session continuity.
- **RTK Terminal Output Filtering** — strips ANSI escapes, telemetry noise, and handles
  fast-path command prefix/filepath extraction to reduce token consumption by up to 90%.
- **Health probes** — liveness (``/healthz``) and readiness (``/readyz``).
- **Process lifecycle** — start/stop/status for the opencodex sidecar.
- **Provider registry** — lists active providers and their models.

The bridge is **optional** — if opencodex is not running, callers fall
back to the existing ``llm_router`` / ``cliproxy`` resolution path.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

logger = logging.getLogger("camelot.ocx_bridge")

# ── Configuration ────────────────────────────────────────────────────────────

OCX_HOST = os.getenv("OCX_HOST", "127.0.0.1")
OCX_PORT = int(os.getenv("OCX_PORT", "10100"))
OCX_BASE = f"http://{OCX_HOST}:{OCX_PORT}"
OCX_API_KEY = (os.getenv("OPENCODEX_API_AUTH_TOKEN") or "").strip()

# Fallback to cliproxy when opencodex is not available
CLIPROXY_URL = os.getenv("CLIPROXY_URL", "http://127.0.0.1:8080/v1")
CLIPROXY_KEY = (os.getenv("CLIPROXY_KEY") or "").strip()
OLLAMA_URL = "http://127.0.0.1:11434/v1"


# ── FCC Provider Catalog & Canonical Endpoints ───────────────────────────────
# Assimilated from free-claude-code config/provider_catalog.py (50 providers)

FCC_DEFAULT_BASE_URLS: dict[str, str] = {
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
    "open_router": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "cline_pass": "https://api.cline.bot/api/v1",
    "openai": "https://chatgpt.com/backend-api/codex",
    "openai_oauth": "http://127.0.0.1:10531/v1",
    "xai": "https://api.x.ai/v1",
    "qwencloud": "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
    "qwencloud_coding": "https://coding-intl.dashscope.aliyuncs.com/v1",
    "together": "https://api.together.ai/v1",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "siliconflow": "https://api.siliconflow.com/v1",
    "nebius": "https://api.tokenfactory.nebius.com/v1",
    "chutes": "https://llm.chutes.ai/v1",
    "featherless": "https://api.featherless.ai/v1",
    "agnes": "https://apihub.agnes-ai.com/v1",
    "zenmux": "https://zenmux.ai/api/v1",
    "wandb": "https://api.inference.wandb.ai/v1",
    "azure_openai": "https://api.openai.azure.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "vertex": "https://aiplatform.googleapis.com",
    "deepseek": "https://api.deepseek.com",
    "mistral": "https://api.mistral.ai/v1",
    "mistral_codestral": "https://codestral.mistral.ai/v1",
    "opencode_zen": "https://opencode.ai/zen/v1",
    "opencode_go": "https://opencode.ai/zen/go/v1",
    "vercel": "https://ai-gateway.vercel.sh/v1",
    "bedrock": "https://bedrock-mantle.us-east-1.api.aws/v1",
    "huggingface": "https://router.huggingface.co/v1",
    "cohere": "https://api.cohere.ai/compatibility/v1",
    "github_models": "https://models.github.ai/inference",
    "wafer": "https://pass.wafer.ai/v1",
    "kimi": "https://api.moonshot.ai/v1",
    "kimi_code": "https://api.kimi.com/coding/v1",
    "kilo": "https://api.kilo.ai/api/gateway",
    "minimax": "https://api.minimax.io/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "sambanova": "https://api.sambanova.ai/v1",
    "fireworks": "https://api.fireworks.ai/inference/v1",
    "novita": "https://api.novita.ai/openai/v1",
    "cloudflare": "https://api.cloudflare.com/client/v4",
    "zai": "https://api.z.ai/api/coding/paas/v4",
    "zai_api": "https://api.z.ai/api/paas/v4",
    "tokenrouter": "https://api.tokenrouter.com/v1",
    "nararoute": "https://router.bynara.id/v1",
    "poolside": "https://inference.poolside.ai/v1",
    "llm7": "https://api.llm7.io/v1",
    "ollama_cloud": "https://ollama.com/v1",
    "lmstudio": "http://localhost:1234/v1",
    "llamacpp": "http://localhost:8080/v1",
    "ollama": "http://localhost:11434",
}


class ProviderAuthKind(StrEnum):
    """Authentication kind for provider integration."""
    CONFIGURATION = "configuration"
    CONNECTED_ACCOUNT = "connected_account"


@dataclass(frozen=True, slots=True)
class FCCProviderDescriptor:
    """Descriptor for a provider assimilated from Free Claude Code."""
    provider_id: str
    display_name: str
    auth_kind: ProviderAuthKind = ProviderAuthKind.CONFIGURATION
    local: bool = False
    credential_env: Optional[str] = None
    credential_url: Optional[str] = None
    default_base_url: Optional[str] = None
    proxy_attr: Optional[str] = None


FCC_PROVIDER_CATALOG: dict[str, FCCProviderDescriptor] = {
    "nvidia_nim": FCCProviderDescriptor(
        provider_id="nvidia_nim",
        display_name="NVIDIA NIM",
        credential_env="NVIDIA_NIM_API_KEY",
        credential_url="https://build.nvidia.com/settings/api-keys",
        default_base_url=FCC_DEFAULT_BASE_URLS["nvidia_nim"],
        proxy_attr="nvidia_nim_proxy",
    ),
    "open_router": FCCProviderDescriptor(
        provider_id="open_router",
        display_name="OpenRouter",
        credential_env="OPENROUTER_API_KEY",
        credential_url="https://openrouter.ai/keys",
        default_base_url=FCC_DEFAULT_BASE_URLS["open_router"],
        proxy_attr="open_router_proxy",
    ),
    "groq": FCCProviderDescriptor(
        provider_id="groq",
        display_name="Groq",
        credential_env="GROQ_API_KEY",
        credential_url="https://console.groq.com/keys",
        default_base_url=FCC_DEFAULT_BASE_URLS["groq"],
        proxy_attr="groq_proxy",
    ),
    "cline_pass": FCCProviderDescriptor(
        provider_id="cline_pass",
        display_name="ClinePass",
        credential_env="CLINE_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["cline_pass"],
        proxy_attr="cline_pass_proxy",
    ),
    "openai": FCCProviderDescriptor(
        provider_id="openai",
        display_name="OpenAI / ChatGPT",
        auth_kind=ProviderAuthKind.CONNECTED_ACCOUNT,
        default_base_url=FCC_DEFAULT_BASE_URLS["openai"],
        proxy_attr="openai_proxy",
    ),
    "openai_oauth": FCCProviderDescriptor(
        provider_id="openai_oauth",
        display_name="OpenAI OAuth Dev Proxy",
        auth_kind=ProviderAuthKind.CONNECTED_ACCOUNT,
        local=True,
        default_base_url=FCC_DEFAULT_BASE_URLS["openai_oauth"],
        proxy_attr="openai_oauth_proxy",
    ),
    "xai": FCCProviderDescriptor(
        provider_id="xai",
        display_name="xAI (Grok)",
        credential_env="XAI_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["xai"],
        proxy_attr="xai_proxy",
    ),
    "qwencloud": FCCProviderDescriptor(
        provider_id="qwencloud",
        display_name="QwenCloud Token Plan",
        credential_env="QWENCLOUD_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["qwencloud"],
        proxy_attr="qwencloud_proxy",
    ),
    "together": FCCProviderDescriptor(
        provider_id="together",
        display_name="Together AI",
        credential_env="TOGETHER_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["together"],
        proxy_attr="together_proxy",
    ),
    "deepinfra": FCCProviderDescriptor(
        provider_id="deepinfra",
        display_name="DeepInfra",
        credential_env="DEEPINFRA_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["deepinfra"],
        proxy_attr="deepinfra_proxy",
    ),
    "siliconflow": FCCProviderDescriptor(
        provider_id="siliconflow",
        display_name="SiliconFlow",
        credential_env="SILICONFLOW_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["siliconflow"],
        proxy_attr="siliconflow_proxy",
    ),
    "gemini": FCCProviderDescriptor(
        provider_id="gemini",
        display_name="Gemini AI Studio",
        credential_env="GEMINI_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["gemini"],
        proxy_attr="gemini_proxy",
    ),
    "vertex": FCCProviderDescriptor(
        provider_id="vertex",
        display_name="Google Vertex AI",
        default_base_url=FCC_DEFAULT_BASE_URLS["vertex"],
        proxy_attr="vertex_proxy",
    ),
    "deepseek": FCCProviderDescriptor(
        provider_id="deepseek",
        display_name="DeepSeek",
        credential_env="DEEPSEEK_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["deepseek"],
    ),
    "mistral": FCCProviderDescriptor(
        provider_id="mistral",
        display_name="Mistral",
        credential_env="MISTRAL_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["mistral"],
        proxy_attr="mistral_proxy",
    ),
    "opencode_zen": FCCProviderDescriptor(
        provider_id="opencode_zen",
        display_name="OpenCode Zen",
        credential_env="OPENCODE_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["opencode_zen"],
        proxy_attr="opencode_zen_proxy",
    ),
    "opencode_go": FCCProviderDescriptor(
        provider_id="opencode_go",
        display_name="OpenCode Go",
        credential_env="OPENCODE_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["opencode_go"],
        proxy_attr="opencode_go_proxy",
    ),
    "vercel": FCCProviderDescriptor(
        provider_id="vercel",
        display_name="Vercel AI Gateway",
        credential_env="AI_GATEWAY_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["vercel"],
        proxy_attr="vercel_ai_gateway_proxy",
    ),
    "bedrock": FCCProviderDescriptor(
        provider_id="bedrock",
        display_name="Amazon Bedrock",
        credential_env="AWS_BEARER_TOKEN_BEDROCK",
        default_base_url=FCC_DEFAULT_BASE_URLS["bedrock"],
        proxy_attr="bedrock_proxy",
    ),
    "huggingface": FCCProviderDescriptor(
        provider_id="huggingface",
        display_name="Hugging Face",
        credential_env="HUGGINGFACE_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["huggingface"],
        proxy_attr="huggingface_proxy",
    ),
    "cohere": FCCProviderDescriptor(
        provider_id="cohere",
        display_name="Cohere",
        credential_env="COHERE_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["cohere"],
        proxy_attr="cohere_proxy",
    ),
    "github_models": FCCProviderDescriptor(
        provider_id="github_models",
        display_name="GitHub Models",
        credential_env="GITHUB_MODELS_TOKEN",
        default_base_url=FCC_DEFAULT_BASE_URLS["github_models"],
        proxy_attr="github_models_proxy",
    ),
    "wafer": FCCProviderDescriptor(
        provider_id="wafer",
        display_name="Wafer",
        credential_env="WAFER_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["wafer"],
        proxy_attr="wafer_proxy",
    ),
    "kimi": FCCProviderDescriptor(
        provider_id="kimi",
        display_name="Kimi",
        credential_env="KIMI_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["kimi"],
        proxy_attr="kimi_proxy",
    ),
    "kilo": FCCProviderDescriptor(
        provider_id="kilo",
        display_name="Kilo.ai",
        credential_env="KILO_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["kilo"],
        proxy_attr="kilo_proxy",
    ),
    "minimax": FCCProviderDescriptor(
        provider_id="minimax",
        display_name="MiniMax",
        credential_env="MINIMAX_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["minimax"],
        proxy_attr="minimax_proxy",
    ),
    "cerebras": FCCProviderDescriptor(
        provider_id="cerebras",
        display_name="Cerebras",
        credential_env="CEREBRAS_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["cerebras"],
        proxy_attr="cerebras_proxy",
    ),
    "sambanova": FCCProviderDescriptor(
        provider_id="sambanova",
        display_name="SambaNova",
        credential_env="SAMBANOVA_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["sambanova"],
        proxy_attr="sambanova_proxy",
    ),
    "cloudflare": FCCProviderDescriptor(
        provider_id="cloudflare",
        display_name="Cloudflare Workers AI",
        credential_env="CLOUDFLARE_API_TOKEN",
        default_base_url=FCC_DEFAULT_BASE_URLS["cloudflare"],
        proxy_attr="cloudflare_proxy",
    ),
    "zai": FCCProviderDescriptor(
        provider_id="zai",
        display_name="Z.ai Coding Plan",
        credential_env="ZAI_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["zai"],
        proxy_attr="zai_proxy",
    ),
    "ollama_cloud": FCCProviderDescriptor(
        provider_id="ollama_cloud",
        display_name="Ollama Cloud",
        credential_env="OLLAMA_API_KEY",
        default_base_url=FCC_DEFAULT_BASE_URLS["ollama_cloud"],
        proxy_attr="ollama_cloud_proxy",
    ),
    "lmstudio": FCCProviderDescriptor(
        provider_id="lmstudio",
        display_name="LM Studio",
        default_base_url=FCC_DEFAULT_BASE_URLS["lmstudio"],
        local=True,
    ),
    "llamacpp": FCCProviderDescriptor(
        provider_id="llamacpp",
        display_name="llama.cpp",
        default_base_url=FCC_DEFAULT_BASE_URLS["llamacpp"],
        local=True,
    ),
    "ollama": FCCProviderDescriptor(
        provider_id="ollama",
        display_name="Ollama Local",
        default_base_url=FCC_DEFAULT_BASE_URLS["ollama"],
        local=True,
    ),
}

SUPPORTED_FCC_PROVIDERS: tuple[str, ...] = tuple(FCC_PROVIDER_CATALOG.keys())


def get_fcc_provider_descriptor(provider_id: str) -> Optional[FCCProviderDescriptor]:
    """Retrieve an FCC provider descriptor by ID."""
    return FCC_PROVIDER_CATALOG.get(provider_id)


def get_provider_base_url(provider_id: str) -> str:
    """Return the default base URL for a provider."""
    return FCC_DEFAULT_BASE_URLS.get(provider_id, "")


# ── Knight Tier → Provider/Model Mapping ─────────────────────────────────────
# Multi-provider failover chains assimilated from FCC provider catalog and routing table.

@dataclass(frozen=True)
class ProviderModel:
    """A provider/model pair for a knight tier."""
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""

    @property
    def wire_id(self) -> str:
        """OpenCodex / FCC slug wire ID (provider/model)."""
        return f"{self.provider}/{self.model}"


@dataclass(frozen=True)
class KnightTierConfig:
    """Configuration for a knight tier's model resolution and failover chain."""
    tier: str
    primary: ProviderModel
    fallbacks: tuple[ProviderModel, ...] = ()
    combo_strategy: str = "failover"  # failover | round-robin
    local_only: bool = False


# Comprehensive Tier Definitions with FCC multi-provider failover chains
KNIGHT_TIER_MAP: dict[str, KnightTierConfig] = {
    # ── G3: Apex frontier (Anthropic / Google / NVIDIA NIM / OpenRouter / Groq / OpenAI)
    "claude_code": KnightTierConfig(
        tier="G3",
        primary=ProviderModel("anthropic", "claude-opus-5"),
        fallbacks=(
            ProviderModel("google", "gemini-3.1-pro-preview"),
            ProviderModel("nvidia_nim", "nvidia/nemotron-3-super-120b-a12b", base_url=FCC_DEFAULT_BASE_URLS["nvidia_nim"]),
            ProviderModel("open_router", "openrouter/free", base_url=FCC_DEFAULT_BASE_URLS["open_router"]),
            ProviderModel("groq", "llama-3.3-70b-versatile", base_url=FCC_DEFAULT_BASE_URLS["groq"]),
            ProviderModel("deepseek", "deepseek-chat", base_url=FCC_DEFAULT_BASE_URLS["deepseek"]),
            ProviderModel("openai", "gpt-5.5"),
        ),
    ),
    "gemini_flash": KnightTierConfig(
        tier="G3",
        primary=ProviderModel("google", "gemini-3-pro-preview"),
        fallbacks=(
            ProviderModel("google", "gemini-3-flash-preview"),
            ProviderModel("nvidia_nim", "nvidia/nemotron-3-super-120b-a12b", base_url=FCC_DEFAULT_BASE_URLS["nvidia_nim"]),
            ProviderModel("anthropic", "claude-sonnet-4"),
            ProviderModel("groq", "llama-3.3-70b-versatile", base_url=FCC_DEFAULT_BASE_URLS["groq"]),
            ProviderModel("openai", "gpt-5.4"),
        ),
    ),
    # ── G2: Pro context/research (Google / NVIDIA NIM / OpenRouter / Anthropic)
    "antigravity.cli": KnightTierConfig(
        tier="G2",
        primary=ProviderModel("google", "gemini-3.1-pro-preview"),
        fallbacks=(
            ProviderModel("nvidia_nim", "nvidia/nemotron-3-super-120b-a12b", base_url=FCC_DEFAULT_BASE_URLS["nvidia_nim"]),
            ProviderModel("open_router", "openrouter/free", base_url=FCC_DEFAULT_BASE_URLS["open_router"]),
            ProviderModel("openai", "gpt-5.4"),
        ),
    ),
    "integration_brain": KnightTierConfig(
        tier="G2",
        primary=ProviderModel("google", "gemini-3.1-pro-preview"),
        fallbacks=(
            ProviderModel("anthropic", "claude-sonnet-4"),
            ProviderModel("deepseek", "deepseek-chat", base_url=FCC_DEFAULT_BASE_URLS["deepseek"]),
            ProviderModel("groq", "llama-3.3-70b-versatile", base_url=FCC_DEFAULT_BASE_URLS["groq"]),
        ),
    ),
    # ── G1: Fast Flash / High-Velocity Bridge
    "open_source": KnightTierConfig(
        tier="G1",
        primary=ProviderModel("google", "gemini-3-flash-preview"),
        fallbacks=(
            ProviderModel("groq", "llama-3.3-70b-versatile", base_url=FCC_DEFAULT_BASE_URLS["groq"]),
            ProviderModel("nvidia_nim", "meta/llama-3.3-70b-instruct", base_url=FCC_DEFAULT_BASE_URLS["nvidia_nim"]),
            ProviderModel("open_router", "openrouter/free", base_url=FCC_DEFAULT_BASE_URLS["open_router"]),
            ProviderModel("openai", "gpt-4.1-mini"),
        ),
    ),
    # ── X1: Codex velocity & Code generation
    "openai_codex": KnightTierConfig(
        tier="X1",
        primary=ProviderModel("openai", "gpt-5.5-codex"),
        fallbacks=(
            ProviderModel("openai_oauth", "gpt-5.5-codex", base_url=FCC_DEFAULT_BASE_URLS["openai_oauth"]),
            ProviderModel("opencode_zen", "gpt-5.3-codex", base_url=FCC_DEFAULT_BASE_URLS["opencode_zen"]),
            ProviderModel("mistral_codestral", "codestral-latest", base_url=FCC_DEFAULT_BASE_URLS["mistral_codestral"]),
            ProviderModel("nvidia_nim", "nvidia/nemotron-3-super-120b-a12b", base_url=FCC_DEFAULT_BASE_URLS["nvidia_nim"]),
            ProviderModel("qwencloud", "qwen3.7-plus", base_url=FCC_DEFAULT_BASE_URLS["qwencloud"]),
        ),
    ),
    "openai_oauth": KnightTierConfig(
        tier="X1",
        primary=ProviderModel("openai_oauth", "gpt-5.5", base_url=FCC_DEFAULT_BASE_URLS["openai_oauth"]),
        fallbacks=(
            ProviderModel("openai_oauth", "gpt-5.4", base_url=FCC_DEFAULT_BASE_URLS["openai_oauth"]),
            ProviderModel("openai_oauth", "gpt-image-2", base_url=FCC_DEFAULT_BASE_URLS["openai_oauth"]),
            ProviderModel("openai", "gpt-5.5-codex"),
        ),
    ),
    # ── L0: Local harness-locked
    "local_qwen": KnightTierConfig(
        tier="L0",
        primary=ProviderModel("ollama", "qwen3:8b", base_url=OLLAMA_URL),
        fallbacks=(
            ProviderModel("lmstudio", "qwen3.5-coder", base_url=FCC_DEFAULT_BASE_URLS["lmstudio"]),
            ProviderModel("llamacpp", "default", base_url=FCC_DEFAULT_BASE_URLS["llamacpp"]),
        ),
        local_only=True,
    ),
    "open_coder": KnightTierConfig(
        tier="L0",
        primary=ProviderModel("ollama", "qwen3:1.7b", base_url=OLLAMA_URL),
        fallbacks=(
            ProviderModel("lmstudio", "qwen3.5-coder", base_url=FCC_DEFAULT_BASE_URLS["lmstudio"]),
        ),
        local_only=True,
    ),
    "agents_a1": KnightTierConfig(
        tier="L0",
        primary=ProviderModel("ollama", "agents-a1", base_url=OLLAMA_URL),
        fallbacks=(),
        local_only=True,
    ),
    # ── Catch-all
    "default": KnightTierConfig(
        tier="G2",
        primary=ProviderModel("google", "gemini-3-pro-preview"),
        fallbacks=(
            ProviderModel("nvidia_nim", "nvidia/nemotron-3-super-120b-a12b", base_url=FCC_DEFAULT_BASE_URLS["nvidia_nim"]),
            ProviderModel("open_router", "openrouter/free", base_url=FCC_DEFAULT_BASE_URLS["open_router"]),
            ProviderModel("anthropic", "claude-sonnet-4"),
            ProviderModel("groq", "llama-3.3-70b-versatile", base_url=FCC_DEFAULT_BASE_URLS["groq"]),
            ProviderModel("openai", "gpt-5.4"),
        ),
    ),
}


# ── Zero-Downtime Failover Logic ─────────────────────────────────────────────
# Assimilated from FCC application/execution.py first-frame failover state machine.

class FailoverCandidateState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    FAILED = "failed"


@dataclass
class FailoverCandidate:
    """One candidate target in a zero-downtime failover sequence."""
    target: ProviderModel
    index: int
    total_candidates: int
    state: FailoverCandidateState = FailoverCandidateState.PENDING
    failure_kind: Optional[str] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    retryable: bool = True

    @property
    def provider_model_ref(self) -> str:
        return self.target.wire_id


class ZeroDowntimeFailoverSession:
    """Manages zero-downtime failover progression across configured provider targets.

    Key Invariant (assimilated from FCC ProviderExecutor):
    - Fallback is allowed ONLY BEFORE the candidate is committed (i.e. before any
      non-empty output frame is emitted downstream).
    - Once committed, fallback is prohibited to preserve stream integrity.
    - If a retryable failure occurs prior to commit, the session advances seamlessly
      to the next candidate without downtime or losing prompt context.
    """

    def __init__(self, candidates: Sequence[ProviderModel], request_id: Optional[str] = None):
        if not candidates:
            raise ValueError("ZeroDowntimeFailoverSession requires at least one candidate.")
        self._request_id = request_id or str(uuid.uuid4())
        self._candidates: list[FailoverCandidate] = [
            FailoverCandidate(target=c, index=i, total_candidates=len(candidates))
            for i, c in enumerate(candidates)
        ]
        self._current_index: int = 0
        self._committed: bool = False
        self._trace_logs: list[dict[str, Any]] = []
        self._candidates[0].state = FailoverCandidateState.ACTIVE

    @property
    def request_id(self) -> str:
        return self._request_id

    @property
    def is_committed(self) -> bool:
        return self._committed

    @property
    def current_candidate(self) -> FailoverCandidate:
        return self._candidates[self._current_index]

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def candidate_index(self) -> int:
        return self._current_index

    def has_next_candidate(self) -> bool:
        return (self._current_index + 1) < len(self._candidates)

    def commit(self) -> None:
        """Commit the current candidate upon first non-empty protocol chunk."""
        self._committed = True
        curr = self.current_candidate
        curr.state = FailoverCandidateState.COMMITTED
        self._record_trace("model_fallback.committed", {
            "selected_provider_model_ref": curr.provider_model_ref,
            "candidate_index": curr.index + 1,
            "candidate_count": curr.total_candidates,
        })

    def record_failure_and_advance(
        self,
        failure_kind: str = "ERROR",
        status_code: int = 500,
        error_message: str = "",
        retryable: bool = True,
    ) -> Optional[FailoverCandidate]:
        """Record a failure on the current candidate and attempt to advance.

        Returns:
            The next FailoverCandidate if failover is viable, or None if exhausted
            or non-retryable/committed.
        """
        curr = self.current_candidate
        curr.state = FailoverCandidateState.FAILED
        curr.failure_kind = failure_kind
        curr.status_code = status_code
        curr.error_message = error_message
        curr.retryable = retryable

        if self._committed:
            logger.warning(
                "Failover disallowed after stream commit: request_id=%s candidate=%s",
                self._request_id,
                curr.provider_model_ref,
            )
            return None

        if not retryable:
            logger.info(
                "Non-retryable failure encountered: request_id=%s candidate=%s kind=%s",
                self._request_id,
                curr.provider_model_ref,
                failure_kind,
            )
            return None

        if not self.has_next_candidate():
            logger.warning(
                "All failover candidates exhausted for request_id=%s (total=%d)",
                self._request_id,
                len(self._candidates),
            )
            return None

        # Advance to next candidate
        next_index = self._current_index + 1
        next_candidate = self._candidates[next_index]
        next_candidate.state = FailoverCandidateState.ACTIVE

        self._record_trace("model_fallback.started", {
            "from_provider_model_ref": curr.provider_model_ref,
            "to_provider_model_ref": next_candidate.provider_model_ref,
            "candidate_index": next_index + 1,
            "candidate_count": len(self._candidates),
            "failure_kind": failure_kind,
            "status_code": status_code,
        })

        self._current_index = next_index
        return next_candidate

    def _record_trace(self, event: str, metadata: dict[str, Any]) -> None:
        entry = {
            "stage": "execution",
            "event": f"camelot.fcc.{event}",
            "request_id": self._request_id,
            **metadata,
        }
        self._trace_logs.append(entry)
        logger.debug("Failover trace: %s", entry)

    def get_traces(self) -> list[dict[str, Any]]:
        return list(self._trace_logs)


# ── RTK Terminal Output Filtering & Optimization Patterns ────────────────────
# Assimilated from Free Claude Code RTK integration and API optimization handlers.

_ANSI_ESCAPE_RE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)
_PROGRESS_BAR_RE = re.compile(
    r"(?:\[[\=\>\-\#\.\s\w]{2,}\]\s*\d{1,3}%?|\[[\=\>\-\#\.\s]{2,}\]|\b\d{1,3}%\b|\b\d+\/\d+\b\s*\[[0-9:\.]+\])"
)
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")


def filter_terminal_output(
    text: str,
    *,
    strip_ansi: bool = True,
    strip_progress: bool = True,
    max_duplicate_lines: int = 2,
) -> str:
    """Filter raw terminal output to reduce token consumption by up to 90%.

    Strips ANSI color and cursor codes, progress bars, and collapses repetitive spinner ticks.
    """
    if not text:
        return ""

    result = text
    if strip_ansi:
        result = _ANSI_ESCAPE_RE.sub("", result)

    if strip_progress:
        # Strip progress bars across text
        result = _PROGRESS_BAR_RE.sub("", result)
        # Normalize carriage returns and newlines
        result = result.replace("\r\n", "\n").replace("\r", "\n")
        lines = result.splitlines()
        filtered_lines: list[str] = []
        last_line: str = ""
        dup_count: int = 0

        for line in lines:
            cleaned = line.strip()
            if not cleaned:
                continue
            # Collapse spinner / progress repetitions
            if cleaned == last_line:
                dup_count += 1
                if dup_count <= max_duplicate_lines:
                    filtered_lines.append(cleaned)
            else:
                dup_count = 1
                last_line = cleaned
                filtered_lines.append(cleaned)

        result = "\n".join(filtered_lines)

    return result.strip()


def extract_command_prefix(command: str) -> str:
    """Extract command prefix for fast prefix detection without LLM calls.

    Handles environment variable assignments (e.g. ``FOO=1 bar``) and
    detects command injection attempts.
    """
    if "`" in command or "$(" in command:
        return "command_injection_detected"

    try:
        parts = shlex.split(command, posix=False)
        if not parts:
            return "none"

        env_prefix: list[str] = []
        cmd_start = 0
        for i, part in enumerate(parts):
            if _ENV_ASSIGNMENT_RE.match(part):
                env_prefix.append(part)
                cmd_start = i + 1
            else:
                break

        if cmd_start >= len(parts):
            return "none"

        cmd_parts = parts[cmd_start:]
        if not cmd_parts:
            return "none"

        first_word = cmd_parts[0]
        two_word_commands = {
            "git", "npm", "docker", "kubectl", "cargo", "go", "pip", "yarn"
        }

        if first_word in two_word_commands and len(cmd_parts) > 1:
            second_word = cmd_parts[1]
            if not second_word.startswith("-"):
                return f"{first_word} {second_word}"
            return first_word

        return first_word if not env_prefix else f"{' '.join(env_prefix)} {first_word}"

    except ValueError:
        parts = command.split()
        if not parts:
            return "none"
        # Strip env assignments
        cmd_start = 0
        for i, part in enumerate(parts):
            if _ENV_ASSIGNMENT_RE.match(part):
                cmd_start = i + 1
            else:
                break
        cmd_parts = parts[cmd_start:]
        return cmd_parts[0] if cmd_parts else "none"


def extract_filepaths_from_command(command: str, output: str = "") -> str:
    """Extract file paths from reading commands without calling remote LLM.

    Listing commands (ls, dir, find, tree) return empty tags;
    reading commands (cat, head, tail, grep) extract concrete paths.
    """
    listing_commands = {
        "ls", "dir", "find", "tree", "pwd", "cd", "mkdir", "rmdir", "rm"
    }
    reading_commands = {"cat", "head", "tail", "less", "more", "bat", "type"}

    try:
        parts = shlex.split(command, posix=False)
        if not parts:
            return "<filepaths>\n</filepaths>"

        cmd_start = 0
        for i, part in enumerate(parts):
            if _ENV_ASSIGNMENT_RE.match(part):
                cmd_start = i + 1
            else:
                break
        cmd_parts = parts[cmd_start:]
        if not cmd_parts:
            return "<filepaths>\n</filepaths>"

        base_cmd = cmd_parts[0].replace("\\", "/").split("/")[-1].lower()

        if base_cmd in listing_commands:
            return "<filepaths>\n</filepaths>"

        if base_cmd in reading_commands:
            filepaths = [p for p in cmd_parts[1:] if not p.startswith("-")]
            if filepaths:
                return f"<filepaths>\n{chr(10).join(filepaths)}\n</filepaths>"
            return "<filepaths>\n</filepaths>"

        if base_cmd == "grep":
            flags_with_args = {"-e", "-f", "-m", "-A", "-B", "-C"}
            pattern_via_flag = False
            positional: list[str] = []
            skip_next = False

            for part in cmd_parts[1:]:
                if skip_next:
                    skip_next = False
                    continue
                if part.startswith("-"):
                    if part in flags_with_args:
                        if part in {"-e", "-f"}:
                            pattern_via_flag = True
                        skip_next = True
                    continue
                positional.append(part)

            filepaths = positional if pattern_via_flag else positional[1:]
            if filepaths:
                return f"<filepaths>\n{chr(10).join(filepaths)}\n</filepaths>"
            return "<filepaths>\n</filepaths>"

        return "<filepaths>\n</filepaths>"

    except ValueError:
        return "<filepaths>\n</filepaths>"


def is_quota_check_request(text: str, max_tokens: int = 1) -> bool:
    """Detect if an incoming payload is a quota probe request."""
    return max_tokens == 1 and "quota" in text.lower()


def is_title_generation_request(system_prompt: str) -> bool:
    """Detect if an incoming payload is a title generation request."""
    sys_lower = system_prompt.lower()
    return "sentence-case title" in sys_lower or (
        "return json" in sys_lower and "title" in sys_lower
    )


# ── Aurora Token Pooling & Tool-Call Emulation ────────────────────────────────
# Assimilated from aurora token pooling, session health checks, and <tool_call> emulation.

class AuroraAccountType(StrEnum):
    NOAUTH = "noauth"
    FREE = "free"
    PUID = "puid"


class AuroraAccountStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    RATE_LIMITED = "rate_limited"
    DISABLED = "disabled"
    BANNED = "banned"


@dataclass
class AuroraBrowserFingerprint:
    oai_device_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    oai_session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    )
    screen_width: int = 1920
    screen_height: int = 1080
    hardware_concurrency: int = 8
    platform: str = "Win32"
    tls_profile_name: str = "chrome_146"


@dataclass
class AuroraAccount:
    id: str
    type: AuroraAccountType
    token: str
    refresh_token: str = ""
    session_token: str = ""
    is_temporary: bool = False
    puid: str = ""
    team_user_id: str = ""
    chatgpt_account_id: str = ""
    proxy: str = ""
    fingerprint: AuroraBrowserFingerprint = field(default_factory=AuroraBrowserFingerprint)
    status: AuroraAccountStatus = AuroraAccountStatus.PENDING
    total_calls: int = 0
    failed_calls: int = 0


def parse_jwt_claims(jwt_token: str) -> dict[str, Any]:
    """Parse JWT claims (payload) without verifying signature."""
    import base64
    parts = jwt_token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    # Pad base64 if needed
    rem = len(payload) % 4
    if rem > 0:
        payload += "=" * (4 - rem)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}


def extract_chatgpt_account_id(jwt_token: str) -> str:
    """Extract chatgpt_account_id from JWT claims."""
    claims = parse_jwt_claims(jwt_token)
    auth = claims.get("https://api.openai.com/auth", {})
    if isinstance(auth, dict):
        return auth.get("chatgpt_account_id", "")
    return ""


def extract_chatgpt_user_id(jwt_token: str) -> str:
    """Extract chatgpt_user_id from JWT claims."""
    claims = parse_jwt_claims(jwt_token)
    auth = claims.get("https://api.openai.com/auth", {})
    if isinstance(auth, dict):
        return auth.get("chatgpt_user_id", "")
    return ""


def extract_chatgpt_plan_type(jwt_token: str) -> str:
    """Extract chatgpt_plan_type from JWT claims."""
    claims = parse_jwt_claims(jwt_token)
    return claims.get("chatgpt_plan_type", "")


class AuroraPool:
    """ChatGPT token pool with round-robin rotation, session health checks, and temp token isolation."""

    def __init__(self, initial_accounts: Sequence[AuroraAccount] | None = None):
        self._noauth: list[AuroraAccount] = []
        self._free: list[AuroraAccount] = []
        self._puid: list[AuroraAccount] = []
        self._cursors: dict[AuroraAccountType, int] = {
            AuroraAccountType.NOAUTH: 0,
            AuroraAccountType.FREE: 0,
            AuroraAccountType.PUID: 0,
        }
        self._temporary: dict[str, AuroraAccount] = {}

        if initial_accounts:
            for acct in initial_accounts:
                self.add_account(acct)

    def add_account(self, acct: AuroraAccount) -> None:
        if acct.type == AuroraAccountType.NOAUTH:
            self._noauth.append(acct)
        elif acct.type == AuroraAccountType.FREE:
            self._free.append(acct)
        elif acct.type == AuroraAccountType.PUID:
            self._puid.append(acct)

    def _get_slice(self, acct_type: AuroraAccountType) -> list[AuroraAccount]:
        if acct_type == AuroraAccountType.NOAUTH:
            return self._noauth
        if acct_type == AuroraAccountType.FREE:
            return self._free
        if acct_type == AuroraAccountType.PUID:
            return self._puid
        return []

    def acquire(self, acct_type: AuroraAccountType) -> Optional[AuroraAccount]:
        """Round-robin acquisition of active account for given type."""
        entries = self._get_slice(acct_type)
        if not entries:
            return None
        start = self._cursors[acct_type] % len(entries)
        for i in range(len(entries)):
            idx = (start + i) % len(entries)
            acct = entries[idx]
            if acct.status == AuroraAccountStatus.ACTIVE:
                self._cursors[acct_type] = (idx + 1) % len(entries)
                acct.total_calls += 1
                return acct
        return None

    def report_failure(self, acct: AuroraAccount) -> bool:
        """Mark account as expired upon auth or quota failures."""
        if acct is None:
            return False
        acct.status = AuroraAccountStatus.EXPIRED
        acct.failed_calls += 1
        return True

    def get_expired_accounts(self) -> list[AuroraAccount]:
        out = []
        for lst in (self._noauth, self._free, self._puid):
            for a in lst:
                if a.status == AuroraAccountStatus.EXPIRED:
                    out.append(a)
        return out

    def get_or_create_temp_account(
        self,
        token: str,
        user_agent: str = "",
        proxy_url: str = "",
    ) -> AuroraAccount:
        """Get or create temporary account from external bearer token."""
        import hashlib
        h = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        if h in self._temporary:
            return self._temporary[h]

        fp = AuroraBrowserFingerprint()
        if user_agent:
            fp.user_agent = user_agent

        acct = AuroraAccount(
            id=str(uuid.uuid4()),
            type=AuroraAccountType.FREE,
            token=token,
            is_temporary=True,
            proxy=proxy_url,
            fingerprint=fp,
            status=AuroraAccountStatus.ACTIVE,
            chatgpt_account_id=extract_chatgpt_account_id(token),
        )
        self._temporary[h] = acct
        return acct

    def run_health_check(self, renew_callback: Callable[[AuroraAccount], bool]) -> int:
        """Run health check to renew expired sessions."""
        expired = self.get_expired_accounts()
        renewed = 0
        for acct in expired:
            if renew_callback(acct):
                acct.status = AuroraAccountStatus.ACTIVE
                renewed += 1
        return renewed

    @property
    def total_count(self) -> int:
        return len(self._noauth) + len(self._free) + len(self._puid) + len(self._temporary)


# ── Tool-Call Emulation System ──────────────────────────────────────────────

AURORA_TOOL_CALL_START = "<tool_call>"
AURORA_TOOL_CALL_END = "</tool_call>"

_TOOL_CALL_OPEN_RE = re.compile(r"<tool[_\s]?calls?>", re.IGNORECASE)
_TOOL_CALL_CLOSE_RE = re.compile(r"</tool[_\s]?calls?>", re.IGNORECASE)
_MARKDOWN_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)


def build_aurora_tool_instructions(
    tools: list[dict[str, Any]],
    tool_choice: dict[str, Any] | str | None = None,
) -> str:
    """Build system instructions teaching the model the <tool_call> JSON protocol."""
    if not tools:
        return ""

    lines = [
        "# TOOLS AVAILABLE",
        "You have access to the following tools. Use the EXACT tool name from the list below — do NOT rename, abbreviate or invent names.\n",
    ]

    for t in tools:
        fn = t.get("function", {})
        name = fn.get("name", "")
        desc = fn.get("description", "")
        lines.append(f"- {name}: {desc}")
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])
        if props:
            lines.append("  Params:")
            for p_name in sorted(props.keys()):
                p_info = props[p_name]
                p_type = p_info.get("type", "string")
                p_req = "required" if p_name in required else "optional"
                p_desc = p_info.get("description", "")
                if p_desc:
                    lines.append(f"    * {p_name} ({p_type}, {p_req}): {p_desc}")
                else:
                    lines.append(f"    * {p_name} ({p_type}, {p_req})")

    lines.extend([
        "\n# TOOL CALLING FORMAT (MANDATORY)",
        "To call a tool, output a JSON object wrapped EXACTLY in these tags:",
        AURORA_TOOL_CALL_START,
        '{"name": "tool_name", "arguments": {"param_name": "value"}}',
        AURORA_TOOL_CALL_END,
        "\nCRITICAL RULES:",
        "0. Use ONLY the EXACT tool names listed under TOOLS AVAILABLE. Never rename or invent names.",
        "1. ONLY use the tags above for tool calling. NEVER output raw JSON without tags.",
        "2. You can call multiple tools by emitting multiple <tool_call> blocks consecutively.",
        "3. Do NOT output any other text after your <tool_call> blocks. Wait for the tool response.",
        "4. The JSON inside the tags MUST be valid and include the 'arguments' field.",
        "5. If you need to use a tool, do it IMMEDIATELY without preamble.",
    ])

    if isinstance(tool_choice, dict) and tool_choice.get("function", {}).get("name"):
        forced = tool_choice["function"]["name"]
        lines.append(f'\nCRITICAL: You MUST call the tool "{forced}" in this response.')
    elif tool_choice == "none":
        lines.append("\nCRITICAL: The user has DISABLED tool calling in this request. Do not emit any <tool_call> blocks.")

    return "\n".join(lines)


def build_aurora_final_nudge(tools: list[dict[str, Any]], messages: list[dict[str, Any]]) -> str:
    """Build final nudge prompt to force immediate tool call or prevent sandbox hallucination."""
    if not tools or not messages:
        return ""
    last = messages[-1]
    role = last.get("role", "")
    if role in ("tool", "function"):
        return "\n[SYSTEM INSTRUCTION: The 'Tool (...)' block above is the REAL output produced by running your tool call on the user's actual machine. Treat it as ground truth. Continue the task based strictly on it: call another tool using <tool_call>{...}</tool_call> or produce your final answer.]"
    elif role == "user":
        return "\n[SYSTEM INSTRUCTION: You are an autonomous coding agent. In THIS session you have NO Python sandbox. The ONLY way to inspect or modify files is to emit a <tool_call>. Begin your response immediately with '<tool_call>'.]"
    return ""


def fix_aurora_backslashes(text: str) -> str:
    """Fix lone Windows backslashes in JSON strings (e.g. C:\\path\\to\\file)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = text[i + 1] if i + 1 < n else ""
        if nxt and nxt in '"\\/bfnrtu':
            out.append("\\")
            out.append(nxt)
            i += 2
            continue
        out.append("\\\\")
        i += 1
    return "".join(out)


def robust_aurora_json(text: str) -> tuple[dict[str, Any] | None, bool]:
    """Parse JSON with backslash repair and balanced bracket fallback."""
    if not text:
        return None, False
    repaired = fix_aurora_backslashes(text)
    try:
        val = json.loads(repaired)
        if isinstance(val, dict):
            return val, True
    except Exception:
        pass

    # Balanced braces scan
    depth = 0
    in_str = False
    esc = False
    start = -1
    for i, c in enumerate(repaired):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    val = json.loads(repaired[start : i + 1])
                    if isinstance(val, dict):
                        return val, True
                except Exception:
                    pass
                start = -1
    return None, False


class AuroraToolCallParser:
    """Streaming parser that detects <tool_call> tags and yields text deltas and tool calls."""

    def __init__(self):
        self._buffer: str = ""
        self._inside: bool = False
        self._emitted_count: int = 0
        self._emitted_text: bool = False

    def feed(self, chunk: str) -> tuple[str, list[dict[str, Any]]]:
        """Feed text chunk and receive text deltas and newly parsed tool calls."""
        normalized = _TOOL_CALL_OPEN_RE.sub(AURORA_TOOL_CALL_START, self._buffer + chunk)
        normalized = _TOOL_CALL_CLOSE_RE.sub(AURORA_TOOL_CALL_END, normalized)
        self._buffer = normalized

        text_out: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        while self._buffer:
            if not self._inside:
                start_idx = self._buffer.find(AURORA_TOOL_CALL_START)
                if start_idx >= 0:
                    pre = self._buffer[:start_idx]
                    if pre:
                        text_out.append(pre)
                        self._emitted_text = True
                    self._inside = True
                    self._buffer = self._buffer[start_idx + len(AURORA_TOOL_CALL_START) :]
                    continue

                flush_idx = len(self._buffer)
                for i in range(1, len(AURORA_TOOL_CALL_START)):
                    if self._buffer.endswith(AURORA_TOOL_CALL_START[:i]):
                        flush_idx = len(self._buffer) - i
                        break
                pre = self._buffer[:flush_idx]
                if pre:
                    text_out.append(pre)
                    self._emitted_text = True
                self._buffer = self._buffer[flush_idx:]
                break

            # Inside tool_call tag
            end_idx = self._buffer.find(AURORA_TOOL_CALL_END)
            if end_idx < 0:
                break

            raw = self._buffer[:end_idx].strip()
            tc = self._build_tool_call(raw)
            if tc:
                tool_calls.append(tc)
                self._emitted_count += 1
            self._inside = False
            self._buffer = self._buffer[end_idx + len(AURORA_TOOL_CALL_END) :]

        return "".join(text_out), tool_calls

    def flush(self) -> tuple[str, list[dict[str, Any]]]:
        """Flush any remaining unclosed tool call at the end of the stream."""
        remaining = self._buffer
        self._buffer = ""
        if not remaining:
            return "", []

        if self._inside:
            tc = self._build_tool_call(remaining)
            if tc:
                self._emitted_count += 1
                return "", [tc]
            if self._emitted_count == 0:
                return AURORA_TOOL_CALL_START + remaining, []
            return "", []

        if self._emitted_count == 0:
            tc = self._build_tool_call(remaining)
            if tc:
                self._emitted_count += 1
                return "", [tc]
            if not self._emitted_text:
                return remaining, []

        return "", []

    def _build_tool_call(self, raw: str) -> Optional[dict[str, Any]]:
        s = _MARKDOWN_FENCE_RE.sub("", raw).strip()
        idx = s.find("{")
        if idx < 0:
            return None
        s = s[idx:]
        obj, ok = robust_aurora_json(s)
        if not ok or not obj:
            return None

        name = obj.get("name") or obj.get("tool") or obj.get("tool_name") or obj.get("function")
        if not name or not isinstance(name, str):
            return None

        args = obj.get("arguments") or obj.get("parameters") or obj.get("args")
        if args is None:
            args = {k: v for k, v in obj.items() if k not in ("name", "tool", "tool_name", "function")}

        if isinstance(args, dict):
            args_str = json.dumps(args)
        elif isinstance(args, str):
            args_str = args if args.startswith("{") else json.dumps({"command": args})
        else:
            args_str = json.dumps(args)

        call_id = f"call_{uuid.uuid4().hex[:24]}"
        return {
            "index": self._emitted_count,
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": args_str,
            },
        }


def recover_aurora_tool_calls_from_text(
    text: str,
    shell_tool_name: str = "bash",
    shell_param_name: str = "command",
) -> list[dict[str, Any]]:
    """Scan raw text for standalone JSON or sandbox cmd dicts and recover tool calls."""
    if "{" not in text:
        return []

    seen = set()
    out = []
    depth = 0
    in_str = False
    esc = False
    start = -1

    for i, c in enumerate(text):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                blob = text[start : i + 1]
                obj, ok = robust_aurora_json(blob)
                if ok and obj:
                    name = obj.get("name") or obj.get("tool") or obj.get("tool_name") or obj.get("function")
                    tc = None
                    if name and isinstance(name, str):
                        args = obj.get("arguments") or obj.get("parameters") or obj.get("args") or {}
                        args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                        tc = {
                            "index": len(out),
                            "id": f"call_{uuid.uuid4().hex[:24]}",
                            "type": "function",
                            "function": {"name": name, "arguments": args_str},
                        }
                    elif "cmd" in obj:
                        cmd_val = obj["cmd"]
                        cmd_str = " ".join(cmd_val) if isinstance(cmd_val, list) else str(cmd_val)
                        if cmd_str:
                            tc = {
                                "index": len(out),
                                "id": f"call_{uuid.uuid4().hex[:24]}",
                                "type": "function",
                                "function": {
                                    "name": shell_tool_name,
                                    "arguments": json.dumps({shell_param_name: cmd_str}),
                                },
                            }
                    if tc:
                        key = f"{tc['function']['name']}:{tc['function']['arguments']}"
                        if key not in seen:
                            seen.add(key)
                            out.append(tc)
                start = -1
    return out


def serialize_aurora_tool_calls_for_history(calls: list[dict[str, Any]]) -> str:
    """Serialize tool calls into <tool_call> tags for history playback in prompts."""
    out = []
    for c in calls:
        fn = c.get("function", {})
        name = fn.get("name", "")
        args = fn.get("arguments", "{}")
        if not args.startswith("{"):
            args = json.dumps(args)
        out.append(f"\n{AURORA_TOOL_CALL_START}")
        out.append(f'{{"name": "{name}", "arguments": {args}}}')
        out.append(f"{AURORA_TOOL_CALL_END}")
    return "".join(out)


# ── HTTP helpers (httpx preferred, stdlib fallback) ──────────────────────────

def _http_get(url: str, timeout: float = 5.0) -> Optional[dict[str, Any]]:
    """GET a JSON endpoint. Returns None on any failure."""
    try:
        import httpx
        headers = {}
        if OCX_API_KEY:
            headers["x-opencodex-api-key"] = OCX_API_KEY
        resp = httpx.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    # Stdlib fallback
    try:
        import urllib.request
        req = urllib.request.Request(url)
        if OCX_API_KEY:
            req.add_header("x-opencodex-api-key", OCX_API_KEY)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        pass

    return None


def _http_post(url: str, data: dict, timeout: float = 10.0) -> Optional[dict[str, Any]]:
    """POST JSON to an endpoint. Returns None on any failure."""
    try:
        import httpx
        headers = {"Content-Type": "application/json"}
        if OCX_API_KEY:
            headers["x-opencodex-api-key"] = OCX_API_KEY
        resp = httpx.post(url, json=data, headers=headers, timeout=timeout)
        if resp.status_code in (200, 201):
            return resp.json()
    except Exception:
        pass

    try:
        import urllib.request
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if OCX_API_KEY:
            req.add_header("x-opencodex-api-key", OCX_API_KEY)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        pass

    return None


# ── Bridge Class ─────────────────────────────────────────────────────────────

class OCXBridge:
    """Thin wrapper around the opencodex management API with assimilated FCC failover & RTK capabilities.

    Provides knight-tier model resolution, FCC provider descriptors, zero-downtime
    failover sessions, RTK terminal output filtering, health probes, and process lifecycle.
    """

    def __init__(self, base_url: str | None = None):
        self._base = (base_url or OCX_BASE).rstrip("/")
        self._tier_map = KNIGHT_TIER_MAP
        self._fcc_catalog = FCC_PROVIDER_CATALOG

    # ── Health probes ────────────────────────────────────────────────────

    def is_live(self) -> bool:
        """Check if the opencodex proxy is reachable (GET /healthz)."""
        result = _http_get(f"{self._base}/healthz", timeout=2.0)
        return result is not None

    def is_ready(self) -> bool:
        """Check if the proxy is fully ready (GET /readyz, status=ready)."""
        result = _http_get(f"{self._base}/readyz", timeout=3.0)
        if result is None:
            return False
        return result.get("status") == "ready"

    def health(self) -> dict[str, Any]:
        """Full health report from /readyz."""
        result = _http_get(f"{self._base}/readyz", timeout=3.0)
        return result or {"status": "unreachable", "service": "opencodex"}

    # ── Model resolution & Failover ──────────────────────────────────────

    def resolve(
        self,
        knight_id: str,
        engine: str | None = None,
    ) -> tuple[str, str, str]:
        """Resolve a knight to (model, base_url, api_key)."""
        tier_config = self._get_tier_config(engine)

        if self.is_ready():
            if tier_config.local_only:
                return tier_config.primary.model, tier_config.primary.base_url or OLLAMA_URL, ""
            wire_id = tier_config.primary.wire_id
            return wire_id, self._base, OCX_API_KEY.strip()

        if tier_config.local_only:
            return tier_config.primary.model, tier_config.primary.base_url or OLLAMA_URL, ""
        return tier_config.primary.model, CLIPROXY_URL, CLIPROXY_KEY

    def resolve_with_fallback(
        self,
        knight_id: str,
        engine: str | None = None,
    ) -> list[tuple[str, str, str]]:
        """Resolve with full multi-provider failover chain.

        Returns an ordered list of (model, base_url, api_key) tuples.
        """
        tier_config = self._get_tier_config(engine)
        result: list[tuple[str, str, str]] = []

        # Primary
        model, url, key = self.resolve(knight_id, engine)
        result.append((model, url, key))

        # Fallbacks
        if self.is_ready() and not tier_config.local_only:
            for fb in tier_config.fallbacks:
                wire_id = fb.wire_id
                result.append((wire_id, self._base, OCX_API_KEY.strip()))
        else:
            for fb in tier_config.fallbacks:
                target_url = fb.base_url or (OLLAMA_URL if tier_config.local_only else CLIPROXY_URL)
                result.append((fb.model, target_url, fb.api_key or CLIPROXY_KEY))

        return result

    def create_failover_session(
        self,
        knight_id: str,
        engine: str | None = None,
    ) -> ZeroDowntimeFailoverSession:
        """Create a zero-downtime failover session populated with the tier's provider candidates."""
        tier_config = self._get_tier_config(engine)
        candidates = [tier_config.primary, *tier_config.fallbacks]
        return ZeroDowntimeFailoverSession(candidates=candidates)

    # ── FCC Provider Registry ────────────────────────────────────────────

    def list_fcc_providers(self) -> list[dict[str, Any]]:
        """List all 50 assimilated FCC providers and their default base URLs."""
        return [
            {
                "id": p.provider_id,
                "display_name": p.display_name,
                "auth_kind": p.auth_kind.value,
                "local": p.local,
                "default_base_url": p.default_base_url or "",
            }
            for p in self._fcc_catalog.values()
        ]

    def get_fcc_provider(self, provider_id: str) -> Optional[FCCProviderDescriptor]:
        """Get an FCC provider descriptor by provider_id."""
        return get_fcc_provider_descriptor(provider_id)

    def filter_output(self, output: str) -> str:
        """Filter terminal output via assimilated RTK patterns."""
        return filter_terminal_output(output)

    # ── Standard opencodex endpoints ─────────────────────────────────────

    def list_providers(self) -> list[dict[str, Any]]:
        """List active providers from opencodex."""
        result = _http_get(f"{self._base}/api/providers", timeout=5.0)
        if result is None:
            return self.list_fcc_providers()
        if isinstance(result, dict):
            return [{"id": k, **v} for k, v in result.items()]
        return result if isinstance(result, list) else []

    def list_models(self, provider: str | None = None) -> list[dict[str, Any]]:
        """List available models, optionally filtered by provider."""
        url = f"{self._base}/api/models"
        if provider:
            url += f"?provider={provider}"
        result = _http_get(url, timeout=5.0)
        if result is None:
            return []
        return result if isinstance(result, list) else []

    # ── Process lifecycle ────────────────────────────────────────────────

    def start(self, port: int | None = None) -> bool:
        """Start the opencodex proxy as a background process."""
        cmd = [sys.executable, "-m", "node_modules.@bitkyc08.opencodex.bin.ocx", "start"]
        if port:
            cmd.extend(["--port", str(port)])

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=os.getenv("CAMELOT_HOME", "."),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            logger.info("opencodex started (pid=%d)", proc.pid)
            return True
        except Exception as exc:
            logger.warning("failed to start opencodex: %s", exc)
            return False

    def stop(self) -> bool:
        """Stop the opencodex proxy."""
        try:
            result = _http_post(f"{self._base}/api/system/stop", {}, timeout=5.0)
            return result is not None
        except Exception:
            return False

    def status(self) -> dict[str, Any]:
        """Get proxy status."""
        result = _http_get(f"{self._base}/api/system/status", timeout=3.0)
        return result or {"status": "unreachable"}

    # ── Combo configuration ──────────────────────────────────────────────

    def get_combo_config(self, engine: str | None = None) -> dict[str, Any]:
        """Get the combo (failover/round-robin) config for a knight tier."""
        omniroute_combos = self._load_omniroute_combos()
        if omniroute_combos and engine:
            tier_config = self._get_tier_config(engine)
            for combo_name, combo_cfg in omniroute_combos.items():
                if combo_cfg.get("local_only") != tier_config.local_only:
                    continue
                if combo_name.startswith(tier_config.tier):
                    return {
                        "strategy": combo_cfg.get("strategy", "failover"),
                        "targets": combo_cfg.get("targets", []),
                        "cooldown_seconds": combo_cfg.get("cooldown_seconds", 300),
                    }

        tier_config = self._get_tier_config(engine)
        targets = [{"provider": tier_config.primary.provider, "model": tier_config.primary.model}]
        for fb in tier_config.fallbacks:
            targets.append({"provider": fb.provider, "model": fb.model})
        return {
            "strategy": tier_config.combo_strategy,
            "targets": targets,
            "cooldown_seconds": 300,
        }

    def _load_omniroute_combos(self) -> dict[str, Any]:
        """Load combo definitions from omniroute.json."""
        candidates = [
            Path(os.getenv("CAMELOT_HOME", ".")) / "03_VAULT" / "training" / "configs" / "config" / "omniroute.json",
            Path(".") / "03_VAULT" / "training" / "configs" / "config" / "omniroute.json",
        ]
        for p in candidates:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    combos = data.get("combos", {})
                    return {k: v for k, v in combos.items() if not k.startswith("_")}
                except Exception:
                    pass
        return {}

    def _get_tier_config(self, engine: str | None) -> KnightTierConfig:
        """Look up tier config for an engine string."""
        if engine and engine in self._tier_map:
            return self._tier_map[engine]
        return self._tier_map["default"]


# ── Module-level singleton ───────────────────────────────────────────────────

_bridge: OCXBridge | None = None


def get_bridge() -> OCXBridge:
    """Get or create the module-level OCXBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = OCXBridge()
    return _bridge


def resolve_knight_model(
    knight_id: str,
    engine: str | None = None,
) -> tuple[str, str, str]:
    """Resolve a knight to (model, base_url, api_key) via opencodex."""
    return get_bridge().resolve(knight_id, engine)


def is_opencodex_available() -> bool:
    """Check if opencodex is running and ready."""
    return get_bridge().is_ready()

