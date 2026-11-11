# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""Guarded Claw Suite integration manifest.

This module turns the Claw Suite concept into auditable control-plane metadata.
It deliberately does not implement anti-bot bypass, scraping evasion, secret
storage, product publication, checkout creation, or fraud decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ClawKnight:
    knight_id: str
    title: str
    function: str
    replaces: str
    capabilities: tuple[str, ...]
    safety_boundary: str
    evidence_class: str = "planned"


FORBIDDEN_OPENCLAW_PATTERNS = (
    "bypass cloudflare",
    "cloudflare bypass",
    "bypass datadome",
    "datadome bypass",
    "captcha evasion",
    "anti-bot evasion",
    "strip-mine",
    "credential stuffing",
)


CLAW_KNIGHTS: dict[str, ClawKnight] = {
    "sir_openclaw": ClawKnight(
        knight_id="sir_openclaw",
        title="The Compliant Data Harvester",
        function="Public-source trend research with robots/ToS/rate-limit compliance",
        replaces="sq_oracle trend scouting",
        capabilities=("compliant_trend_research", "source_attribution", "rate_limit_respect", "robots_policy"),
        safety_boundary="No anti-bot bypass, credential use, CAPTCHA evasion, or protected-content scraping.",
    ),
    "sir_rustclaw": ClawKnight(
        knight_id="sir_rustclaw",
        title="The Iron Executor",
        function="Memory-safe image pipeline contract for CMYK checks, underbase planning, and asset transcodes",
        replaces="Python OpenCV hot path",
        capabilities=("rust_image_pipeline", "cmyk_contrast_check", "halftone_underbase_plan", "avif_transcode_contract"),
        safety_boundary="Performance claims remain planned until backed by local Rust benchmarks.",
    ),
    "sir_hermes": ClawKnight(
        knight_id="sir_hermes",
        title="The Autonomous Courier",
        function="Shopify Admin publication lane plus Storefront cart/checkout orchestration",
        replaces="ad hoc Shopify scripts",
        capabilities=("shopify_admin", "shopify_storefront", "graphql_orchestration", "webhook_choreography"),
        safety_boundary="Uses secret presence flags only; no token values in manifests, logs, or config.",
        evidence_class="confirmed",
    ),
    "lady_nanobot": ClawKnight(
        knight_id="lady_nanobot",
        title="The Edge Swarm",
        function="Next.js edge component-agent contract for phygital routing and telemetry events",
        replaces="monolithic UI state",
        capabilities=("edge_component_agents", "webgl_mockup_contract", "nfc_route_contract", "telemetry_event_contract"),
        safety_boundary="Telemetry must be consent-aware and avoid fingerprinting without explicit policy approval.",
    ),
    "sir_zeroclaw": ClawKnight(
        knight_id="sir_zeroclaw",
        title="The Zero-Trust Sentry",
        function="Trademark/IP, affiliate-abuse, and checkout-risk guardrail coordinator",
        replaces="basic Sir Galahad checks",
        capabilities=("zero_trust", "ip_trademark_guard", "affiliate_abuse_guard", "checkout_risk_gate"),
        safety_boundary="HUMAN_GATE required for fraud blocks, fingerprinting, and any irreversible commerce action.",
    ),
    "lisa_knight": ClawKnight(
        knight_id="lisa_knight",
        title="The Shopify Digital Assembly Line",
        function="WASM-sandboxed Liquid template forger, GraphQL schema designer, and XP-driven app builder",
        replaces="ad hoc theme and app scripts",
        capabilities=("liquid_forge", "graphql_schema_designer", "theme_harness", "wasm_sandboxed_assembly"),
        safety_boundary="Plan-Only at Level 1/2. Level 3 Sandbox Write gated by XP ladder. Level 4 Production requires Warden HITL gate.",
        evidence_class="confirmed",
    ),
}


def is_forbidden_openclaw_intent(intent: str) -> bool:
    text = (intent or "").lower()
    return any(pattern in text for pattern in FORBIDDEN_OPENCLAW_PATTERNS)


def build_claw_suite_manifest(objective: str = "shopify headless ai forger") -> dict[str, Any]:
    return {
        "protocol": "CLAW_SUITE_INTEGRATION",
        "objective": objective,
        "ukg_state": {
            "crystal": "I2L_v9.0-CLAW_SUITE",
            "state": "FORGED_GUARDED",
            "backend": "SHOPIFY_HEADLESS",
            "evidence_class": "planned_until_runtime_verified",
        },
        "knights": {kid: asdict(knight) for kid, knight in CLAW_KNIGHTS.items()},
        "safety": {
            "evasion_allowed": False,
            "blocked_capabilities": [
                "anti_bot_evasion",
                "datadome_bypass",
                "cloudflare_bypass",
                "captcha_evasion",
                "protected_content_scraping",
                "secret_value_storage",
                "automatic_fraud_denial_without_human_gate",
            ],
            "openclaw_allowed_sources": [
                "approved_public_api",
                "merchant_owned_data",
                "licensed_dataset",
                "manual_research_export",
                "robots_and_terms_compliant_page_fetch",
            ],
        },
        "shopify_lanes": {
            "admin": {
                "purpose": "product_and_media_publication",
                "api": "Admin GraphQL API",
                "required_scopes": ["write_products"],
                "graphql_entrypoints": [
                    "productCreate",
                    "productVariantsBulkCreate",
                    "productVariantsBulkUpdate",
                    "productVariantAppendMedia",
                ],
                "doc_basis": "Context7 /websites/shopify_dev_api_admin",
            },
            "storefront": {
                "purpose": "cart_and_checkout",
                "api": "Storefront GraphQL API",
                "required_scopes": ["unauthenticated_read_product_listings"],
                "graphql_entrypoints": ["cartCreate", "Cart.checkoutUrl"],
                "doc_basis": "Context7 /websites/shopify_dev_api_storefront",
            },
            "secret_policy": "presence_flags_only_no_values",
        },
        "workflows": [
            {
                "id": "phoenix_creation_cycle",
                "status": "planned_guarded",
                "sequence": ["sir_openclaw", "sir_zeroclaw", "sir_rustclaw", "sir_hermes"],
                "human_gate": ["publish_product", "use_external_source_without_license"],
            },
            {
                "id": "kinetic_edge_presentation",
                "status": "planned_guarded",
                "sequence": ["sir_hermes", "lady_nanobot"],
                "human_gate": ["fingerprinting", "behavioral_personalization_without_consent"],
            },
            {
                "id": "zero_trust_commerce",
                "status": "planned_guarded",
                "sequence": ["lady_nanobot", "sir_zeroclaw", "sir_hermes"],
                "human_gate": ["fraud_block", "affiliate_denial", "checkout_intercept"],
            },
        ],
        "execution": {
            "auto_execute": False,
            "reason": "Manifest only. Runtime actions require scoped implementation plus HITL for commerce/security gates.",
        },
    }


def route_claw_suite(param: str = "", context: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = (param or "").strip()
    if raw.lower().startswith("lisa"):
        task_prompt = raw[4:].strip() or "Build Shopify subscription app"
        try:
            from cartridges.lisa_shopify_app_sandbox.core.cartridge_adapter import LisaCartridgeHost
        except ImportError:
            import importlib.util
            from pathlib import Path
            adapter_path = Path(__file__).resolve().parent.parent.parent / "cartridges" / "lisa-shopify-app-sandbox" / "core" / "cartridge_adapter.py"
            if adapter_path.exists():
                spec = importlib.util.spec_from_file_location("lisa_adapter", adapter_path)
                if spec and spec.loader:
                    import sys
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules["lisa_adapter"] = mod
                    spec.loader.exec_module(mod)
                    LisaCartridgeHost = mod.LisaCartridgeHost
                else:
                    LisaCartridgeHost = None
            else:
                LisaCartridgeHost = None

        if LisaCartridgeHost:
            host = LisaCartridgeHost()
            result = host.process_task(task_prompt, mode="dry-run")
            return {
                "action": "lisa_cartridge_process",
                "suite": "CLAW",
                "knight": "lisa_knight",
                "execution_result": result,
            }

    manifest = build_claw_suite_manifest(param or "shopify headless ai forger")
    return {
        "action": "claw_suite_manifest",
        "suite": "CLAW",
        "requested": param or "",
        "knights": list(CLAW_KNIGHTS),
        "safety": manifest["safety"],
        "shopify_lanes": manifest["shopify_lanes"],
        "execution": manifest["execution"],
    }
