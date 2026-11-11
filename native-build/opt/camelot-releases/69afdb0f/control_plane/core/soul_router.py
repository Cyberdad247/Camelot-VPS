# SPDX-License-Identifier: MIT

"""Soul Router — MFOE Routing Matrix for Camelot Foundry Council.

Implements the Soul Equation: S_omega = alpha*V + beta*M + gamma*P + delta*E
Routes intents to the optimal Knight engine based on weighted tensor scoring.
"""

from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import importlib.util
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

from control_plane.taxonomy import KEYWORD_ROUTES, PRIVACY_KEYWORDS

try:
    from importlib import import_module
    hydration = import_module("01_KERNEL.memory.hydration_manager")
    HydrationManager = hydration.HydrationManager
except ImportError:
    HydrationManager = None

# Add KERNEL to path for telemetry
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    _TELEMETRY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "01_KERNEL", "senses", "telemetry_client.py"))
    _TELEMETRY_SPEC = importlib.util.spec_from_file_location("camelot_telemetry_client", _TELEMETRY_PATH)
    _TELEMETRY_MODULE = importlib.util.module_from_spec(_TELEMETRY_SPEC)
    _TELEMETRY_SPEC.loader.exec_module(_TELEMETRY_MODULE)
    RotelClient = _TELEMETRY_MODULE.RotelClient
    KINETIC_TOKEN = _TELEMETRY_MODULE.KINETIC_TOKEN
    logger = RotelClient("soul_router")
except Exception:
    class DummyLogger:
        def info(self, *args, **kwargs): pass
    logger = DummyLogger()
    KINETIC_TOKEN = os.getenv("CAMELOT_KINETIC_TOKEN", "")

SALTARE_URL = os.getenv("SALTARE_URL", "http://127.0.0.1:8080/api/v1/route")
CLIPROXY_URL = os.getenv("CLIPROXY_URL", "http://127.0.0.1:8080/v1")

class EngineWeight(float, Enum):
    """Immutable weight locks per Titanium Law."""
    W_ORCHESTRATION = 0.85
    W_COGNITIVE     = 0.88
    W_CONTEXT       = 0.90
    W_VELOCITY      = 0.75
    W_PRIVACY       = 1.00
    W_SOVEREIGNTY   = 0.80
    W_KINETIC       = 0.70
    W_BRIDGE        = 0.78
    W_MEMORY        = 0.92
    W_LINEAR        = 0.95
    W_WARDEN        = 0.93
    W_FINANCE       = 0.82
    W_BIFROST       = 0.91
    W_VOICE         = 0.86
    # Agents-A1 is a 35B local MoE that targets tool use + multi-step
    # planning. Sits one notch above W_VOICE (0.86, single-modal,
    # conversation-tuned) and one below W_COGNITIVE (0.88, SIR_ALEX's
    # general-purpose orchestration weight) because it is single-purpose
    # (agentic) but a strong default for tool-driven tasks. Calibrate up
    # if future eval data shows it outperforms SIR_ALEX on those tasks.
    W_AGENTIC       = 0.87  # Agentic MoE — Agents-A1 (35B MoE, tool use)

@dataclass(frozen=True)
class KnightEngine:
    knight_id: str
    engine: str
    weight: EngineWeight
    function: str
    privacy_level: float = 0.0

FOUNDRY_COUNCIL: tuple[KnightEngine, ...] = (
    KnightEngine("sir_boris", "claude_code", EngineWeight.W_ORCHESTRATION, "Architecture & Lead", privacy_level=0.3),
    KnightEngine("sir_alex", "claude_code", EngineWeight.W_COGNITIVE, "Cognitive Orchestration", privacy_level=0.3),
    KnightEngine("sir_helio", "antigravity.cli", EngineWeight.W_CONTEXT, "1M+ Context Mapping", privacy_level=0.2),
    KnightEngine("sir_codex", "openai_codex", EngineWeight.W_VELOCITY, "High-Velocity Code", privacy_level=0.2),
    KnightEngine("sir_forge", "open_coder", EngineWeight.W_KINETIC, "Local Code Gen", privacy_level=0.7),
    KnightEngine("sir_sonus", "vox_anima", EngineWeight.W_VOICE, "Voice & Resonance", privacy_level=0.3),
    KnightEngine("sir_link", "antigravity.cli", EngineWeight.W_BRIDGE, "Cross-UI Handoff", privacy_level=0.2),
    KnightEngine("sir_ghost", "local_qwen", EngineWeight.W_PRIVACY, "Zero-Trust Execution", privacy_level=1.0),
    KnightEngine("sir_liberte", "open_source", EngineWeight.W_SOVEREIGNTY, "Anti-Vendor Sovereign", privacy_level=0.5),
    KnightEngine("sir_mnemo", "integration_brain", EngineWeight.W_MEMORY, "Memory Routing", privacy_level=0.4),
    KnightEngine("sir_ouroboros", "ouroboros_ssm", EngineWeight.W_LINEAR, "Linear Reasoning", privacy_level=0.1),
    KnightEngine("sir_sentinel", "gemini_flash", EngineWeight.W_WARDEN, "Security Warden", privacy_level=0.8),
    KnightEngine("sir_valerian", "gemini_flash", EngineWeight.W_FINANCE, "Financial/ROI", privacy_level=0.4),
    KnightEngine("sir_heimdall", "pydantic_ai", EngineWeight.W_BIFROST, "Bifrost Guardian", privacy_level=0.9),
    KnightEngine("sir_openclaw", "openclaw", EngineWeight.W_CONTEXT, "Compliant Trend Harvester", privacy_level=0.6),
    KnightEngine("sir_rustclaw", "rustclaw", EngineWeight.W_KINETIC, "Rust Image Pipeline Executor", privacy_level=0.5),
    # Commander of the Hermes automation fabric across all registered knights —
    # see control_plane/infra/hermes_commander_fabric.py, which declares
    # COMMANDER_KNIGHT="sir_hermes" / COMMANDER_ROLE="COMMANDER_KNIGHT". The
    # courier duties below are still real; they are the engine's other half.
    KnightEngine("sir_hermes", "hermes_cli", EngineWeight.W_BRIDGE, "Hermes Commander — all-knight automation coordination; Shopify GraphQL/Webhook Courier", privacy_level=0.6),
    KnightEngine("lady_nanobot", "next_edge", EngineWeight.W_VELOCITY, "Edge Component Swarm", privacy_level=0.6),
    KnightEngine("sir_zeroclaw", "local_qwen", EngineWeight.W_PRIVACY, "Zero-Trust Commerce Sentry", privacy_level=1.0),
    # Agents-A1 — 35B MoE agentic LLM, served locally via vLLM or SGLang
    # with an OpenAI-compatible API. Local-first (privacy_level=0.9), so
    # it never leaks prompts to a third-party cloud.
    KnightEngine("sir_agentis", "agents_a1", EngineWeight.W_AGENTIC, "Agentic MoE Orchestrator", privacy_level=0.9),
)

_ENGINE_MAP = {e.knight_id: e for e in FOUNDRY_COUNCIL}

@dataclass
class IntentTensor:
    velocity: float = 0.5
    magnitude: float = 0.5
    privacy: float = 0.0
    environment: float = 0.0
    def __post_init__(self):
        for attr in ("velocity", "magnitude", "privacy", "environment"):
            if not 0.0 <= getattr(self, attr) <= 1.0: raise ValueError(f"{attr} invalid")

_ALPHA, _BETA, _GAMMA, _DELTA = 0.20, 0.35, 0.30, 0.15
def soul_equation(t: IntentTensor) -> float:
    return (_ALPHA*t.velocity + _BETA*t.magnitude + _GAMMA*t.privacy + _DELTA*t.environment)


@dataclass
class RouteDecision:
    knight_id: str
    engine: str
    weight: float
    score: float
    tensor: IntentTensor
    reason: str
    privacy_override: bool = False

class SoulRouter:
    def __init__(self):
        self._engines = _ENGINE_MAP
        self._routes = KEYWORD_ROUTES
        self._ttft_history: dict[str, list[float]] = {}
        self.slo_threshold_ms = 2000.0

    def get_average_ttft(self, knight_id: str) -> float:
        history = self._ttft_history.get(knight_id, [])
        return sum(history) / len(history) if history else 0.0

    def record_ttft(self, knight_id: str, ttft_ms: float):
        history = self._ttft_history.setdefault(knight_id, [])
        history.append(ttft_ms)
        if len(history) > 10: history.pop(0)

    def _sync_to_cloudbrain(self, knight_id: str, intent: str, reason: str):
        if HydrationManager:
            try:
                connector = import_module("01_KERNEL.memory.cloudbrain_connector")
                if knight_id.upper() not in getattr(connector, "KNIGHT_NOTEBOOKS", {}):
                    return
            except Exception:
                pass
            mgr = HydrationManager(knight_id=knight_id)
            mgr.store_tissue(
                intent=f"soul_route_{knight_id}",
                content=f"Intent: {intent}\nReason: {reason}",
                complexity=5,
                tier="L1"
            )

    def route(self, intent: str, *, velocity: float = 0.5, magnitude: float = 0.5, privacy: float = 0.0, linear_need: float = 0.0, _apee_compiled: bool = False) -> RouteDecision:
        intent_lower = intent.lower()
        slo_escaped = False

        # 1. Privacy Override
        if privacy >= 0.8 or any(kw in intent_lower for kw in PRIVACY_KEYWORDS):
            ghost = self._engines["sir_ghost"]
            tensor = IntentTensor(velocity, magnitude, max(privacy, 0.9), float(ghost.weight))
            self._sync_to_cloudbrain("sir_ghost", intent, "PRIVACY_OVERRIDE")
            return RouteDecision("sir_ghost", ghost.engine, float(ghost.weight), soul_equation(tensor), tensor, "PRIVACY_OVERRIDE", True)

        # 2. Linear Tier
        if linear_need >= 0.8:
            if self.get_average_ttft("sir_ouroboros") > self.slo_threshold_ms:
                slo_escaped = True
            else:
                ouro = self._engines["sir_ouroboros"]
                tensor = IntentTensor(velocity, magnitude, privacy, float(ouro.weight))
                self._sync_to_cloudbrain("sir_ouroboros", intent, "LINEAR_TIER_TRIGGER")
                return RouteDecision("sir_ouroboros", ouro.engine, float(ouro.weight), soul_equation(tensor), tensor, "LINEAR_TIER_TRIGGER")

        # 3. Keyword Match
        matched_knight = None
        for kw, kn in self._routes.items():
            if kw in intent_lower:
                if self.get_average_ttft(kn) > self.slo_threshold_ms:
                    slo_escaped = True; continue
                matched_knight = kn; break

        # 4. Final selection
        if matched_knight:
            engine = self._engines[matched_knight]
            tensor = IntentTensor(velocity, magnitude, privacy, float(engine.weight))
            score = soul_equation(tensor)
            reason = f"KEYWORD_MATCH: {matched_knight}"
        else:
            best_score, best_engine, best_tensor = -1.0, self._engines["sir_boris"], None
            for engine in FOUNDRY_COUNCIL:
                if engine.privacy_level >= 0.8 and privacy < 0.3: continue
                if self.get_average_ttft(engine.knight_id) > self.slo_threshold_ms: continue
                t = IntentTensor(velocity, magnitude, privacy, float(engine.weight))
                s = soul_equation(t)
                if s > best_score: best_score, best_engine, best_tensor = s, engine, t
            matched_knight, engine, tensor, score = best_engine.knight_id, best_engine, best_tensor, best_score
            reason = f"TENSOR_SCORED: {matched_knight}"

        if slo_escaped: reason += " [DUALMAP_ESCAPE]"
        self._sync_to_cloudbrain(matched_knight, intent, reason)
        return RouteDecision(matched_knight, engine.engine, float(engine.weight), score, tensor, reason)

    def resolve_model(self, knight_id: str) -> tuple[str, str, str]:
        """Resolve a knight_id to (model, base_url, api_key) via OpenCodex bridge.

        Falls back to cliproxy/Ollama if opencodex is not running.
        """
        try:
            from control_plane.core.ocx_bridge import resolve_knight_model
            engine = None
            eng = self._engines.get(knight_id)
            if eng:
                engine = eng.engine
            return resolve_knight_model(knight_id, engine)
        except ImportError:
            # Bridge not available — fall back to cliproxy
            return "gemini-2.5-flash", CLIPROXY_URL, (os.getenv("CLIPROXY_KEY") or "").strip()

    def get_engine(self, knight_id: str) -> Optional[KnightEngine]:
        return self._engines.get(knight_id)

    def verify_weight_lock(self) -> bool:
        boris = self._engines.get("sir_boris")
        return boris is not None and float(boris.weight) == 0.85

    def resolve_knight(self, name: str) -> Optional[str]:
        """Resolve a v9000.14 Pantheon name (or legacy spelling) to a canonical
        v1000 knight_id (P2-T04). Case/separator-insensitive. Returns None for an
        unknown name."""
        return resolve_knight(name)


# ── Knight Pantheon alias resolution (P2-T04) ────────────────────────────────
# Maps v9000.14-CYBERTRONIA pantheon names to canonical v1000 knight_ids, per the
# blueprint Knight Pantheon Alignment table. Keys are normalized (lowercase,
# separators collapsed to "_") before lookup.
KNIGHT_ALIASES: dict[str, str] = {
    "merlin_omega": "merlin_omega", "merlin": "merlin_omega",
    "anya_omega": "anya", "anya": "anya",
    "sir_helios": "sir_helio",                 # v9000.14 SIR_HELIOS -> sir_helio
    "sir_codex": "sir_codex",
    "lady_alexandria": "lady_apis",            # World Tree Archivist
    "sir_hashimoto": "sir_sentinel",           # Cyber Aegis
    "sir_watchdog": "sir_debug",               # Execution Auditor
    "sir_bard": "sir_sonus",                   # TEN Voice Matrix
}


def _normalize_knight_name(name: str) -> str:
    n = (name or "").strip().lower()
    # Collapse common separators (space, hyphen, the Ω/omega glyph) to underscore.
    n = n.replace("Ω", "_omega").replace("ω", "_omega")
    for sep in (" ", "-", ".", "/"):
        n = n.replace(sep, "_")
    while "__" in n:
        n = n.replace("__", "_")
    return n.strip("_")


def resolve_knight(name: str) -> Optional[str]:
    """Resolve a v9000.14 Pantheon name / legacy spelling to a canonical
    knight_id. Checks the alias table first, then the live FOUNDRY_COUNCIL
    roster. Returns None for an unknown name."""
    norm = _normalize_knight_name(name)
    if norm in KNIGHT_ALIASES:
        return KNIGHT_ALIASES[norm]
    council_ids = {e.knight_id for e in FOUNDRY_COUNCIL}
    if norm in council_ids:
        return norm
    return None


# ---------------------------------------------------------------------------
# Convenience: single-call routing (replaces duplicated _route() helpers)
# ---------------------------------------------------------------------------

def route_intent(
    intent: str,
    *,
    velocity: float | None = None,
    magnitude: float | None = None,
    privacy: float | None = None,
    linear_need: float = 0.0,
) -> RouteDecision:
    """Route an intent through the Soul Equation in one call.

    Estimates velocity/magnitude/privacy from intent keywords when not
    explicitly provided, then delegates to ``SoulRouter.route()``.  This is
    the single canonical entry point that all CLI surfaces should use.
    """
    lower = intent.lower()

    if velocity is None:
        _URGENT = {"urgent", "asap", "immediately", "now", "today", "fast", "quickly"}
        velocity = 0.9 if any(kw in lower for kw in _URGENT) else 0.5

    if magnitude is None:
        _HIGH = {
            "architecture", "refactor", "migrate", "redesign", "multi-agent",
            "microservice", "deploy", "infrastructure", "pipeline", "orchestrat",
            "scaling", "shard", "consensus", "evolution", "v1000",
        }
        _LOW = {"status", "list", "show", "who", "help", "ping", "version"}
        if any(kw in lower for kw in _HIGH):
            magnitude = 0.8
        elif any(kw in lower for kw in _LOW):
            magnitude = 0.2
        else:
            magnitude = 0.4

    if privacy is None:
        privacy = 0.95 if any(kw in lower for kw in PRIVACY_KEYWORDS) else 0.0

    router = SoulRouter()
    return router.route(
        intent,
        velocity=velocity,
        magnitude=magnitude,
        privacy=privacy,
        linear_need=linear_need,
    )


def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("SoulRouter self-test (P2-T04 Pantheon alias resolution)")
    r = SoulRouter()

    # Every v9000.14 Pantheon name resolves.
    pantheon = {
        "MERLIN_Ω": "merlin_omega", "ANYA_Ω": "anya", "SIR_HELIOS": "sir_helio",
        "SIR_CODEX": "sir_codex", "LADY_ALEXANDRIA": "lady_apis",
        "SIR_HASHIMOTO": "sir_sentinel", "SIR_WATCHDOG": "sir_debug",
        "SIR_BARD": "sir_sonus",
    }
    for name, expected in pantheon.items():
        got = r.resolve_knight(name)
        check(f"{name} -> {expected} (got {got})", got == expected)

    # Canonical ids pass through; unknown -> None.
    check("canonical sir_boris passes through", r.resolve_knight("sir_boris") == "sir_boris")
    check("separator-insensitive 'Sir Helios'", r.resolve_knight("Sir Helios") == "sir_helio")
    check("unknown name -> None", r.resolve_knight("sir_nonexistent") is None)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — soul_router")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print("SoulRouter — use --test to run the Pantheon resolution self-test.")
