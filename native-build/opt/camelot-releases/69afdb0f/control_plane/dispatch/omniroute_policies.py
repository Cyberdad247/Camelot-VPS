# SPDX-License-Identifier: MIT

"""control_plane/omniroute_policies.py — SELECT_OPTIMAL_FRAMEWORK_O1 lane signals.

Implements the Omni-Router Matrix lane-selection policy from the Camelot-OS
v1000 spec items 1a + 1b, enriched with Free Claude Code (FCC) multi-provider
failover matrix and RTK token optimization fast-path signals:

* Item 1a — "Route low-latency, rapid boilerplate scaffolding through
  OmniRoute (:20128) directly to SIR_CODEX."  Lands at ``LANE_OMNI_ROUTE_CODEX``.
* Item 1b — "Route massive reasoning/deep-context tasks through
  CLIProxyAPI (:8080) for heavy Cloud Brain computing."  Lands at
  ``LANE_CLIPROXY_HEAVY_REASONING``.
* Item 1c (FCC Assimilation) — "Route outage-resilient, multi-provider zero-downtime
  requests through FCC failover matrix." Lands at ``LANE_FCC_FAILOVER_MATRIX``.
* Item 1d (RTK Assimilation) — "Route terminal command filtering and fast-path
  intercepts (prefix detection, quota probe mock, filepath extraction) through
  RTK optimization engine." Lands at ``LANE_RTK_FILTERED_FAST_PATH``.

This module is a **lane signal**, NOT a gate.  It composes with — and never
replaces — ``control_plane.soul_oversight.pre_execute`` (Iron Gate v2 three
tier HITL).  The Iron Gate is the only thing that can flip a HUMAN_GATE
class move to ``DENY``.  See ``AGENTS.md`` Iron Gate and the Father's Camelot
Compass for the binding ruling.

Conventions:

* Stdlib only — no pydantic import.  Consumers (factory_lane, runic_router)
  can wrap ``LaneSignal`` if they need a ``BaseModel`` compat layer; the
  underlying dataclass is intentionally minimal so this module can be
  loaded before any heavy deps (Tailscale node identity, pyo3 bindings,
  etc.) without import-order surprises.

* Stateless.  No global module state, no singletons.  ``select_lane`` is
  pure given its text input.

* Permission posture: a lane signal never escalates tier, never promotes
  AUTO → PROMPT → HUMAN_GATE.  Promotion is exclusively the Iron Gate's
  prerogative.

References:

* AGENTS.md Iron Gate ("Audit new third-party dependencies … do not invent
  unavailable skills").
* AGENTS.md Runic Command System (``//FORGE``, ``$//CODEX$``, ``$//STATUS$``,
  and the ``Omega_*`` dispatch lanes — the lane signal module respects
  them all).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

# ── Lane enum ──────────────────────────────────────────────────────────────

LANE_OMNI_ROUTE_CODEX: str = "omni_route_codex"
"""Low-latency, rapid boilerplate scaffold lane.  Selects SIR_CODEX via
OmniRoute :20128."""

LANE_CLIPROXY_HEAVY_REASONING: str = "cliproxy_heavy_reasoning"
"""Deep-context, >1M-context reasoning lane.  Selects the Polyglot Matrix
(typically SIR_BORIS / SIR_HELIOS / MERLIN_OMEGA) via CLIProxyAPI :8080."""

LANE_FCC_FAILOVER_MATRIX: str = "fcc_failover_matrix"
"""Outage-resilient multi-provider failover lane. Selects FCC zero-downtime
provider candidate chains (NVIDIA NIM -> OpenRouter -> Groq -> Gemini -> DeepSeek)."""

LANE_RTK_FILTERED_FAST_PATH: str = "rtk_filtered_fast_path"
"""RTK terminal token optimization & fast-path lane. Selects local terminal
output filtering, quota mock, and prefix/filepath extraction without LLM invocation."""

LANE_ORNITH_UNCENSORED_CODING: str = "ornith_uncensored_coding"
"""Sovereign uncensored agentic coding & reasoning lane. Selects Ornith-1.0-35B-AEON-Ultimate-Uncensored
(qwen3_5_moe 30 GatedDeltaNet + 10 full-attn MoE) via local vLLM / NVFP4+DFlash engine (:8000)."""

LANE_UNCENSORED_LOCAL_OFFLINE: str = "uncensored_local_offline"
"""Uncensored local multiplatform offline runtime lane. Selects on-device GGUF /
OpenAI-compatible REST daemon (:4891) for zero-cloud, air-gapped sovereign inference."""

LANE_XINFERENCE_MULTI_MODEL: str = "xinference_multi_model"
"""Xorbits Inference multi-model cluster & multi-backend engine lane. Selects
xllamacpp/vLLM/SGLang/Transformers distributed worker cluster & OpenAI-compatible REST server (:9997)."""

LANE_OPENAI_OAUTH_PROXY: str = "openai_oauth_proxy"
"""ChatGPT Account-to-API local OAuth proxy lane (:10531). Selects zero-key
OpenAI-compatible dev proxy runtime with token refresh & image generation."""

LANE_MAXIM_BIFROST_GATEWAY: str = "maxim_bifrost_gateway"
"""MaximHQ Bifrost AI Gateway & WebRTC/WSS Router lane (:3001). Selects ultra-low latency
cross-mesh streaming telemetry, semantic caching, and resilient provider routing."""

LANE_DEFAULT: str = "default"
"""No lane preference.  Punts to ``factory_lane``'s default dispatch."""

VALID_LANES: frozenset = frozenset(
    {
        LANE_OMNI_ROUTE_CODEX,
        LANE_CLIPROXY_HEAVY_REASONING,
        LANE_FCC_FAILOVER_MATRIX,
        LANE_RTK_FILTERED_FAST_PATH,
        LANE_ORNITH_UNCENSORED_CODING,
        LANE_UNCENSORED_LOCAL_OFFLINE,
        LANE_XINFERENCE_MULTI_MODEL,
        LANE_OPENAI_OAUTH_PROXY,
        LANE_MAXIM_BIFROST_GATEWAY,
        LANE_DEFAULT,
    }
)

# ── Keyword sets ────────────────────────────────────────────────────────────

MAXIM_BIFROST_KEYWORDS: Tuple[str, ...] = (
    "maximhq",
    "maxim_bifrost",
    "bifrost_gateway",
    "bifrost_bridge",
    "bifrost_ai_gateway",
    "port_3001",
    "maxim",
    "adaptive_routing",
    "semantic_caching",
    "webrtc_audio_bridge",
)
"""Keywords that route to ``LANE_MAXIM_BIFROST_GATEWAY``."""

OPENAI_OAUTH_PROXY_KEYWORDS: Tuple[str, ...] = (
    "openai_oauth",
    "openai-oauth",
    "chatgpt_oauth",
    "chatgpt_account",
    "oauth_proxy",
    "port_10531",
    "10531",
    "account_to_api",
    "gpt-image-2",
    "zero_api_key",
)
"""Keywords that route to ``LANE_OPENAI_OAUTH_PROXY``."""

UNCENSORED_LOCAL_OFFLINE_KEYWORDS: Tuple[str, ...] = (
    "uncensored_local_offline",
    "uncensored_multiplatform",
    "local_api_4891",
    "uncensored_local",
    "port_4891",
    "4891",
    "offline_ai",
    "offline_llm",
    "portable_ai",
    "heretic_model",
    "abliterated_local",
    "offline_runtime",
)
"""Keywords that route to ``LANE_UNCENSORED_LOCAL_OFFLINE``."""

XINFERENCE_MULTI_MODEL_KEYWORDS: Tuple[str, ...] = (
    "xinference",
    "xinference_cluster",
    "xllamacpp",
    "vllm",
    "sglang",
    "transformers",
    "distributed_worker",
    "multi_model_cluster",
    "port_9997",
    "9997",
    "model_replica",
)
"""Keywords that route to ``LANE_XINFERENCE_MULTI_MODEL``."""

ORNITH_UNCENSORED_KEYWORDS: Tuple[str, ...] = (
    "ornith",
    "uncensored_code",
    "uncensored_coding",
    "abliterated",
    "aeon_ultimate",
    "qwen3_5_moe",
    "gateddeltanet",
    "dflash",
    "nvfp4_coding",
    "uncensored",
)
"""Keywords that route to ``LANE_ORNITH_UNCENSORED_CODING``."""

RTK_OPTIMIZATION_KEYWORDS: Tuple[str, ...] = (
    "rtk",
    "terminal_filter",
    "fast_prefix",
    "quota_mock",
    "filepath_extract",
    "token_killer",
    "ansi_filter",
    "filter_terminal",
)
"""Keywords that route to ``LANE_RTK_FILTERED_FAST_PATH``."""

FCC_FAILOVER_KEYWORDS: Tuple[str, ...] = (
    "zero-downtime",
    "provider_fallback",
    "failover",
    "fcc",
    "multi-provider",
    "outage_resilient",
    "provider_matrix",
)
"""Keywords that route to ``LANE_FCC_FAILOVER_MATRIX``."""

SCAFFOLD_KEYWORDS: Tuple[str, ...] = (
    "scaffold",
    "boilerplate",
    "prototype",
    "rapid",
    "velocity",
    "codex",
    "fast_gen",
    "iteration",
)
"""Keywords that route to ``LANE_OMNI_ROUTE_CODEX``.  Aligned with the
SIR_CODEX dispatch keyword list."""

REASONING_KEYWORDS: Tuple[str, ...] = (
    "deep-context",
    "reasoning",
    "cloud_brain",
    "merlin",
    "1m-context",
    "context_window",
)
"""Keywords that route to ``LANE_CLIPROXY_HEAVY_REASONING``.  Aligned with
the deep-context / 1M-token reasoning cluster (SIR_HELIOS, MERLIN_OMEGA,
SIR_BORIS).
"""


# ── LaneSignal: small, frozen, hashable, no pydantic ─────────────────────────


@dataclass(frozen=True)
class LaneSignal:
    """A lane selection recommendation.  NEVER a gate decision.

    Attributes:
        lane:             one of ``VALID_LANES``.
        rationale:        human-readable explanation (cite-friendly).
        matched_keyword:  the keyword that triggered the selection, or
                          empty string for ``LANE_DEFAULT``.
    """

    lane: str
    rationale: str
    matched_keyword: str = ""

    def __post_init__(self) -> None:
        if self.lane not in VALID_LANES:
            _expected = (
                "cliproxy_heavy_reasoning",
                "default",
                "fcc_failover_matrix",
                "maxim_bifrost_gateway",
                "omni_route_codex",
                "openai_oauth_proxy",
                "ornith_uncensored_coding",
                "rtk_filtered_fast_path",
                "uncensored_local_offline",
                "xinference_multi_model",
            )
            raise ValueError(
                f"unknown lane {self.lane!r}; expected one of "
                f"{list(_expected)}"
            )

    @classmethod
    def default(cls) -> "LaneSignal":
        """The default lane signal — no policy triggered."""
        return cls(
            lane=LANE_DEFAULT,
            rationale="no SELECT_OPTIMAL framework_o1 policy triggered",
            matched_keyword="",
        )


# ── Selector ────────────────────────────────────────────────────────────────


def _match_first(text_lower: str, keywords: Tuple[str, ...]) -> Tuple[bool, str]:
    """Return ``(True, kw)`` for the first keyword matched in ``text_lower``,
    else ``(False, "")``.  Iteration order of the keyword tuple is therefore
    the canonical priority order."""
    for kw in keywords:
        if kw in text_lower:
            return True, kw
    return False, ""


def select_lane(intent_text: str) -> LaneSignal:
    """SELECT_OPTIMAL_FRAMEWORK_O1 selector.  Pure function.  Lane only.

    Args:
        intent_text: the runic / harness / void-edge directive text.  May be
            ``None`` or empty — handled by short-circuiting to default.

    Returns:
        ``LaneSignal`` whose ``lane`` is one of ``VALID_LANES``.  Never raises
        on ordinary input (only on unknown lane strings, which should never
        happen if you construct ``LaneSignal(lane=...)`` correctly).
    """
    if not intent_text:
        return LaneSignal.default()

    needle = intent_text.lower()

    # 0. MaximHQ Bifrost Bridge AI Gateway check (:3001)
    matched, kw = _match_first(needle, MAXIM_BIFROST_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_MAXIM_BIFROST_GATEWAY,
            rationale=(
                f"MaximHQ Bifrost keyword {kw!r} matched -> Maxim Bifrost Gateway (:3001) -> "
                "ultra-low latency cross-mesh AI Gateway, WebRTC/WSS audio bridge & adaptive semantic cache [maximhq/bifrost]"
            ),
            matched_keyword=kw,
        )

    # 1. OpenAI OAuth ChatGPT dev proxy check (:10531)
    matched, kw = _match_first(needle, OPENAI_OAUTH_PROXY_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_OPENAI_OAUTH_PROXY,
            rationale=(
                f"OpenAI OAuth keyword {kw!r} matched -> OpenAI OAuth Dev Proxy (:10531) -> "
                "ChatGPT account-to-API zero-key runtime with token refresh & gpt-image-2 [openai-oauth spec]"
            ),
            matched_keyword=kw,
        )

    # 2. Uncensored local multiplatform offline runtime check (:4891)
    matched, kw = _match_first(needle, UNCENSORED_LOCAL_OFFLINE_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_UNCENSORED_LOCAL_OFFLINE,
            rationale=(
                f"uncensored local offline keyword {kw!r} matched -> Local OpenAI REST Daemon (:4891) -> "
                "on-device GGUF runtime / zero-cloud air-gap multiplatform engine [Uncensored Local AI spec]"
            ),
            matched_keyword=kw,
        )

    # 2. Xinference multi-model cluster & engine backend check (:9997)
    matched, kw = _match_first(needle, XINFERENCE_MULTI_MODEL_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_XINFERENCE_MULTI_MODEL,
            rationale=(
                f"Xinference multi-model keyword {kw!r} matched -> Xinference Cluster Daemon (:9997) -> "
                "xllamacpp/vLLM/SGLang/Transformers distributed worker cluster [Xinference spec]"
            ),
            matched_keyword=kw,
        )

    # 3. Ornith uncensored coding & MoE reasoning check
    matched, kw = _match_first(needle, ORNITH_UNCENSORED_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_ORNITH_UNCENSORED_CODING,
            rationale=(
                f"Ornith uncensored keyword {kw!r} matched -> Local vLLM / NVFP4+DFlash (:8000) -> "
                "Ornith-1.0-35B-AEON-Ultimate-Uncensored (30 GatedDeltaNet + 10 full-attn MoE) [Ornith spec]"
            ),
            matched_keyword=kw,
        )

    # 4. RTK token optimization & fast-path filter check (highest local specificity)
    matched, kw = _match_first(needle, RTK_OPTIMIZATION_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_RTK_FILTERED_FAST_PATH,
            rationale=(
                f"RTK optimization keyword {kw!r} matched -> RTK Terminal Engine -> "
                "local ANSI/progress stripping and fast-path command intercept [FCC RTK spec]"
            ),
            matched_keyword=kw,
        )

    # 5. FCC multi-provider failover matrix check
    matched, kw = _match_first(needle, FCC_FAILOVER_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_FCC_FAILOVER_MATRIX,
            rationale=(
                f"FCC failover keyword {kw!r} matched -> Multi-Provider Matrix -> "
                "zero-downtime pre-commit candidate failover chain [FCC Provider spec]"
            ),
            matched_keyword=kw,
        )

    # 6. Scaffold / rapid boilerplate check
    matched, kw = _match_first(needle, SCAFFOLD_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_OMNI_ROUTE_CODEX,
            rationale=(
                f"scaffold keyword {kw!r} matched -> OmniRoute (:20128) -> "
                "SIR_CODEX (Velocity Forge); fast boilerplate lane [paper ref 1, 2]"
            ),
            matched_keyword=kw,
        )

    # 7. Deep reasoning / cloud brain check
    matched, kw = _match_first(needle, REASONING_KEYWORDS)
    if matched:
        return LaneSignal(
            lane=LANE_CLIPROXY_HEAVY_REASONING,
            rationale=(
                f"deep-context keyword {kw!r} matched -> CLIProxyAPI (:8080) -> "
                "Polyglot Matrix; heavy Cloud Brain lane [paper ref 4]"
            ),
            matched_keyword=kw,
        )

    return LaneSignal.default()


# ── Policy & Failover Chain Helpers ──────────────────────────────────────────

def resolve_fcc_failover_chain(tier_or_intent: str) -> list[str]:
    """Return ordered provider failover ranking for a given tier or intent string."""
    normalized = tier_or_intent.lower()
    if "maxim" in normalized or "bifrost" in normalized:
        return ["maxim_bifrost_gateway", "omniroute_gateway", "google", "groq", "open_router", "anthropic", "openai"]
    if "omniroute" in normalized or "diegosouzapw" in normalized or "caveman" in normalized:
        return ["omniroute_gateway", "google", "groq", "cerebras", "open_router", "anthropic", "openai"]
    if "r1" in normalized or "deepseek" in normalized or "reasoner" in normalized:
        return ["deepseek", "groq", "together", "openai", "google", "anthropic"]
    if "9997" in normalized or "xinference" in normalized or "xllamacpp" in normalized or "sglang" in normalized:
        return ["xinference_cluster_9997", "uncensored_local_4891", "ornith_vllm", "ollama", "openai"]
    if "4891" in normalized or "uncensored_local" in normalized or "offline" in normalized or "portable_ai" in normalized:
        return ["uncensored_local_4891", "ornith_vllm", "ollama", "lmstudio", "llamacpp"]
    if "ornith" in normalized or "uncensored" in normalized or "aeon" in normalized or "abliterated" in normalized:
        return ["ornith_vllm", "nvidia_nim", "open_router", "groq", "openai"]
    if "g3" in normalized or "opus" in normalized or "apex" in normalized:
        return ["anthropic", "google", "nvidia_nim", "open_router", "groq", "deepseek", "openai"]
    if "g1" in normalized or "flash" in normalized or "fast" in normalized:
        return ["google", "groq", "nvidia_nim", "open_router", "openai"]
    if "x1" in normalized or "codex" in normalized or "code" in normalized:
        return ["openai", "opencode_zen", "mistral_codestral", "nvidia_nim", "qwencloud"]
    if "l0" in normalized or "local" in normalized:
        return ["ollama", "lmstudio", "llamacpp"]
    return ["google", "nvidia_nim", "open_router", "anthropic", "groq", "openai"]


def get_fcc_provider_policy(intent_text: str) -> dict[str, Any]:
    """Return provider policy dictionary based on lane analysis."""
    signal = select_lane(intent_text)
    chain = resolve_fcc_failover_chain(intent_text)
    return {
        "lane": signal.lane,
        "matched_keyword": signal.matched_keyword,
        "rationale": signal.rationale,
        "failover_chain": chain,
        "primary_provider": chain[0] if chain else "google",
        "zero_downtime_enabled": signal.lane in (
            LANE_FCC_FAILOVER_MATRIX,
            LANE_MAXIM_BIFROST_GATEWAY,
            LANE_DEFAULT,
            LANE_OMNI_ROUTE_CODEX,
            LANE_ORNITH_UNCENSORED_CODING,
            LANE_UNCENSORED_LOCAL_OFFLINE,
            LANE_XINFERENCE_MULTI_MODEL,
        ),
    }


# ── Self-test (run via ``python -m control_plane.omniroute_policies --test``) ──


def _run_self_test() -> int:
    """Surface ALL lane categorisations + invariants.

    Returns:
        0 on success, 1 on any failure.
    """
    cases = [
        ("Run ChatGPT account-to-API proxy on port_10531", LANE_OPENAI_OAUTH_PROXY, "port_10531"),
        ("Execute openai-oauth chat completion with zero_api_key", LANE_OPENAI_OAUTH_PROXY, "openai-oauth"),
        ("Deploy model on xinference multi_model_cluster", LANE_XINFERENCE_MULTI_MODEL, "xinference"),
        ("Run distributed inference on port_9997 with xllamacpp engine", LANE_XINFERENCE_MULTI_MODEL, "xllamacpp"),
        ("Run uncensored_local model on port_4891 offline", LANE_UNCENSORED_LOCAL_OFFLINE, "uncensored_local"),
        ("Execute offline_ai prompt via portable_ai heretic_model", LANE_UNCENSORED_LOCAL_OFFLINE, "offline_ai"),
        ("Run deep abliterated coding via ornith engine", LANE_ORNITH_UNCENSORED_CODING, "ornith"),
        ("Execute uncensored_code task with qwen3_5_moe", LANE_ORNITH_UNCENSORED_CODING, "uncensored_code"),
        ("//CODEX scaffold a hello-world Rust project", LANE_OMNI_ROUTE_CODEX, "scaffold"),
        ("MERLIN deep-context reasoning over 1m-context window",
         LANE_CLIPROXY_HEAVY_REASONING, "deep-context"),
        ("Execute with zero-downtime failover across providers",
         LANE_FCC_FAILOVER_MATRIX, "zero-downtime"),
        ("Clean terminal logs with rtk filter_terminal",
         LANE_RTK_FILTERED_FAST_PATH, "rtk"),
        ("//STATUS", LANE_DEFAULT, ""),
        ("", LANE_DEFAULT, ""),
        ("   ", LANE_DEFAULT, ""),
        (
            "iterate a prototype crud stub",
            LANE_OMNI_ROUTE_CODEX,
            "prototype",
        ),
    ]
    failures = 0
    for text, expected_lane, expected_kw in cases:
        sig = select_lane(text)
        ok = sig.lane == expected_lane and sig.matched_keyword == expected_kw
        prefix = "[OK]" if ok else "[FAIL]"
        print(
            f"{prefix} input={text!r:50s} -> lane={sig.lane!r:30s} "
            f"kw={sig.matched_keyword!r:12s} rationale={sig.rationale}"
        )
        if not ok:
            failures += 1

    # Invariant: select_lane is pure
    a = select_lane("//CODEX scaffold")
    b = select_lane("//CODEX scaffold")
    if a != b:
        print(f"[FAIL] select_lane not pure (a={a!r}, b={b!r})")
        failures += 1
    else:
        print("[OK] select_lane is idempotent (a == b on repeat call)")

    if failures == 0:
        print(f"\nomniroute_policies self-test: {len(cases) + 1}/{len(cases) + 1} PASS")
        return 0
    print(f"\nomniroute_policies self-test: {failures} FAIL(s)")
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(_run_self_test())

