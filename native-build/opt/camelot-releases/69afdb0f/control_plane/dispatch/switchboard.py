# SPDX-License-Identifier: MIT

"""
Switchboard — LLM Flight Control Terminal
CAMELOT Apex OS v400 | Sovereign Terminal Registry

Every LLM engine is a Terminal (gate/runway). Sir Link owns the handshake.
The router NEVER dispatches blind — it queries the Switchboard first.

Lazy probing: health cache TTL=60s. No probe unless cache stale.
Manifest written to logs/switchboard_manifest.json for HUD/harness consumption.

Terminals: sir_boris(claude) | sir_helio(gemini) | sir_ghost(local) |
           sir_codex(openai) | sir_forge(open_coder) | sir_mnemo(integration_brain)
           sir_link(gemini/bridge) | sir_alex(claude/cognitive)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
MANIFEST_PATH = CAMELOT_HOME / "logs" / "switchboard_manifest.json"
MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

HEALTH_TTL_S   = 60.0   # re-probe after 60s
PROBE_TIMEOUT  = 2.0    # max seconds per probe


def _bifrost_health_url(base: str | None = None) -> str:
    gateway = base or os.environ.get("BIFROST_GATEWAY_URL", "http://127.0.0.1:3001")
    return f"{gateway.strip().rstrip('/')}/health"


# ── Terminal definitions ──────────────────────────────────────────────────────

@dataclass
class Terminal:
    id:          str
    engine:      str
    weight:      float
    cost_tier:   str       # "free" | "low" | "medium" | "high"
    capability:  list[str] = field(default_factory=list)
    probe_url:   str       = ""     # empty = local process check
    probe_port:  int       = 0      # 0 = no TCP probe
    status:      str       = "unknown"  # live|dark|degraded|unknown
    latency_ms:  float     = 0.0
    last_probe:  float     = 0.0
    error_count: int       = 0
    notes:       str       = ""


# Master terminal registry — the full switchboard
TERMINAL_REGISTRY: dict[str, Terminal] = {
    "sir_boris": Terminal(
        id="sir_boris", engine="claude_code", weight=0.85,
        cost_tier="medium", capability=["orchestration","architecture","critique","forge"],
        probe_port=8080, notes="Claude Code — CLIProxy gateway",
    ),
    "sir_helio": Terminal(
        id="sir_helio", engine="pydantic_ai", weight=0.95,
        cost_tier="low", capability=["context","research","burst","1m_token","pydantic_ai"],
        probe_port=0, notes="Sir Helio v400 — Pydantic AI Context Lord",
    ),
    "sir_alex": Terminal(
        id="sir_alex", engine="claude_code", weight=0.88,
        cost_tier="medium", capability=["cognitive","reasoning","critical","decision"],
        probe_port=8080, notes="Claude Code — cognitive cartridge orchestration",
    ),
    "sir_link": Terminal(
        id="sir_link", engine="antigravity.cli", weight=0.78,
        cost_tier="low", capability=["bridge","handoff","terminal","ui","switchboard"],
        probe_port=0, notes="Sir Link — handshake coordinator, switchboard ATC",
    ),
    "sir_ghost": Terminal(
        id="sir_ghost", engine="sovereign", weight=1.00,
        cost_tier="free", capability=["privacy","air_gapped","zero_trust"],
        probe_port=0, notes="SIE qwen3:4b — air-gapped sovereign inference",
    ),
    "sir_forge": Terminal(
        id="sir_forge", engine="sovereign", weight=0.70,
        cost_tier="free", capability=["code_gen","scaffold","technical","kinetic"],
        probe_port=0, notes="SIE qwen2.5-coder:3b — sovereign code gen",
    ),
    "sir_codex": Terminal(
        id="sir_codex", engine="openai_codex", weight=0.75,
        cost_tier="free", capability=["velocity","rapid_proto","openai"],
        probe_port=8080, notes="OpenAI Codex via CLIProxyAPI :8080 — free provider pool",
    ),
    "sir_liberte": Terminal(
        id="sir_liberte", engine="open_source", weight=0.80,
        cost_tier="free", capability=["sovereignty","oss","anti_lock"],
        probe_port=0, notes="Open Source — anti-vendor lock-in",
    ),
    "sir_mnemo": Terminal(
        id="sir_mnemo", engine="integration_brain", weight=0.92,
        cost_tier="low", capability=["memory","archive","recall","synthesize","route"],
        probe_port=0, notes="Integration Brain router — ST/LT memory (module probe)",
    ),
    "sir_sentinel": Terminal(
        id="sir_sentinel", engine="claude_code", weight=0.85,
        cost_tier="medium", capability=["security","audit","armor","pdg"],
        probe_port=3001, notes="Security warden — Agent-Armor PDG",
    ),
    "sir_gideon": Terminal(
        id="sir_gideon", engine="local_audit", weight=0.85,
        cost_tier="free", capability=["security","audit","scorpion","gideon","forensic"],
        probe_port=0, notes="Forensic auditor — GIDEON_RISK_MATRIX //SCORPION pass",
    ),
    "sir_octavian": Terminal(
        id="sir_octavian", engine="local_ops", weight=0.82,
        cost_tier="free", capability=["ops","metrics","monitoring","telemetry","status","alerts","factory"],
        probe_port=8400, notes="Ops & metrics sentinel — factory throughput, health dashboard (:8400)",
    ),
    "sir_sonus": Terminal(
        id="sir_sonus", engine="kitten_tts", weight=0.88,
        cost_tier="free", capability=["tts","audio","voice","speak","synthesize","kitten","streaming"],
        probe_port=8300, notes="Kitten TTS streaming node — chunked audio synthesis HTTP :8300",
    ),
    "sir_gravity": Terminal(
        id="sir_gravity", engine="antigravity", weight=0.88,
        cost_tier="free", capability=["code_gen","ide_native","gemini","google","antigravity","kinetic"],
        probe_port=8080, notes="Google Antigravity — Gemini models via CLIProxyAPI antigravity OAuth channel",
    ),
    "sir_kimi": Terminal(
        id="sir_kimi", engine="kimi_cli", weight=0.82,
        cost_tier="free", capability=["long_context","research","chinese","moonshot","kimi","k2"],
        probe_port=8080, notes="Moonshot Kimi K2.5 — 1M context via CLIProxyAPI kimi OAuth channel",
    ),
    "sir_heimdall": Terminal(
        id="sir_heimdall", engine="pydantic_ai", weight=0.99,
        cost_tier="low", capability=["security","mesh","bifrost","zero_trust","network","sentinel"],
        probe_port=0, notes="Sir Heimdall — Bifrost Guardian & Mesh Network Sentinel",
    ),
    "sir_hermes": Terminal(
        id="sir_hermes", engine="hermes_cli", weight=0.78,
        cost_tier="free", capability=[
            "agent","tool_use","nous","openrouter","kinetic","autonomous",
            "shopify_admin","shopify_storefront","graphql_orchestration","webhook_choreography",
            # Commander surface for the Hermes automation fabric. Must stay in
            # sync with COMMANDER_ROLE in control_plane/infra/hermes_commander_fabric.py
            # and with soul_router.FOUNDRY_COUNCIL's sir_hermes function string.
            "commander","hermes_automation","memory_fabric","all_knight_coordination",
        ],
        probe_port=0, notes="Nous Hermes Agent — autonomous tool-calling via subprocess (-q mode); commander of the all-knight automation fabric",
    ),
    "sir_openclaw": Terminal(
        id="sir_openclaw", engine="openclaw", weight=0.90,
        cost_tier="free", capability=[
            "compliant_trend_research","source_attribution","robots_policy","rate_limit_respect",
        ],
        probe_port=0, notes="Claw Suite harvester: compliant public-source research only",
    ),
    "sir_rustclaw": Terminal(
        id="sir_rustclaw", engine="rustclaw", weight=0.86,
        cost_tier="free", capability=[
            "rust_image_pipeline","cmyk_contrast_check","halftone_underbase_plan","avif_transcode_contract",
        ],
        probe_port=0, notes="Claw Suite Rust image pipeline contract",
    ),
    "lady_nanobot": Terminal(
        id="lady_nanobot", engine="next_edge", weight=0.84,
        cost_tier="free", capability=[
            "edge_component_agents","webgl_mockup_contract","nfc_route_contract","telemetry_event_contract",
        ],
        probe_port=0, notes="Claw Suite edge component swarm contract",
    ),
    "sir_zeroclaw": Terminal(
        id="sir_zeroclaw", engine="sovereign", weight=1.00,
        cost_tier="free", capability=[
            "zero_trust","ip_trademark_guard","affiliate_abuse_guard","checkout_risk_gate",
        ],
        probe_port=0, notes="SIE qwen3:4b — zero-trust sentry; HUMAN_GATE for fraud and fingerprint actions",
    ),
    "bifrost_gateway": Terminal(
        id="bifrost_gateway", engine="bifrost_gateway", weight=0.80,
        cost_tier="free", capability=[
            "gateway","websocket","webhook","ingress","swarm","pwa","voice",
        ],
        probe_url=_bifrost_health_url(),
        probe_port=0,
        notes="Bifrost TS gateway — voice/webhook ingress + Microcubic swarm (:3001); bridge via control_plane.bifrost_gateway",
    ),
    # Agents-A1 — 35B MoE agentic LLM, served locally via vLLM or SGLang
    # with an OpenAI-compatible API. Probed via HTTP /health endpoint
    # (vLLM and SGLang both expose this). weight mirrors the
    # soul_router.W_AGENTIC constant; cost_tier=free because it runs
    # on the operator's box with no per-token billing.
    "sir_agentis": Terminal(
        id="sir_agentis", engine="agents_a1", weight=0.87,
        cost_tier="free", capability=[
            "agentic","tool_use","planning","local","openai_compat",
        ],
        probe_url=os.environ.get("AGENTS_A1_BASE", "http://127.0.0.1:8000").rstrip("/") + "/health",
        probe_port=0,
        notes="Agents-A1 35B MoE — local vLLM/SGLang, OpenAI-compat (35B MoE agentic LLM; Cyberdad247/Agents-A1)",
    ),
}


# ── Probing ───────────────────────────────────────────────────────────────────

async def _probe_tcp(port: int, host: str = "127.0.0.1") -> tuple[bool, float]:
    t0 = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=PROBE_TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return True, (time.perf_counter() - t0) * 1000
    except Exception:
        return False, (time.perf_counter() - t0) * 1000


async def _probe_http_health(url: str) -> tuple[bool, float]:
    """HTTP GET health probe (stdlib, off-thread). 200 == live."""
    import urllib.request

    def _get() -> tuple[bool, float]:
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=PROBE_TIMEOUT) as resp:
                return resp.status == 200, (time.perf_counter() - t0) * 1000
        except Exception:
            return False, (time.perf_counter() - t0) * 1000

    return await asyncio.to_thread(_get)


async def _probe_terminal(t: Terminal) -> None:
    """Update terminal status in-place."""
    t.last_probe = time.time()
    if t.engine == "bifrost_gateway" and t.probe_url:
        ok, ms = await _probe_http_health(t.probe_url)
        t.status     = "live" if ok else "dark"
        t.latency_ms = ms
    elif t.engine == "agents_a1" and t.probe_url:
        # Agents-A1 (vLLM/SGLang) exposes a JSON /health endpoint. Probe
        # via HTTP GET and mark dark if it 5xx/times-out.
        ok, ms = await _probe_http_health(t.probe_url)
        t.status     = "live" if ok else "dark"
        t.latency_ms = ms
    elif t.probe_port:
        ok, ms = await _probe_tcp(t.probe_port)
        t.status     = "live" if ok else "dark"
        t.latency_ms = ms
    elif t.engine == "integration_brain":
        # File probe — check if integration_brain.py exists in configs dir
        t0 = time.perf_counter()
        ib_path = CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "integration_brain.py"
        if ib_path.exists():
            t.status     = "assumed_live"   # file present; NotebookLM bridge probed separately
            t.latency_ms = (time.perf_counter() - t0) * 1000
        else:
            t.status     = "dark"
            t.latency_ms = (time.perf_counter() - t0) * 1000
    elif t.engine == "local_audit":
        # Sir Gideon — live if sir_gideon.py present in knights package
        gideon_py = CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "knights" / "sir_gideon.py"
        t.status     = "live" if gideon_py.exists() else "dark"
        t.latency_ms = 0.0
    elif t.engine == "sovereign":
        # Module probe: SIE is live if importable and its Ollama backend responds.
        # Import + backend health() do blocking socket I/O — run off-thread, or a
        # dark Ollama stalls the event loop and times out every concurrent TCP
        # probe in probe_all()'s gather (sir_boris/sir_alex false-dark).
        t0 = time.perf_counter()

        def _sie_status() -> str:
            try:
                from control_plane.sovereign_inference import SIE
                healthy = SIE.health()
                ollama_ok = healthy.get("backends", {}).get("ollama", False)
                return "live" if ollama_ok else "degraded"
            except Exception:
                return "dark"

        t.status     = await asyncio.to_thread(_sie_status)
        t.latency_ms = (time.perf_counter() - t0) * 1000
    elif t.engine in ("antigravity.cli", "openai_codex", "open_source", "antigravity", "kimi_cli", "openclaw", "rustclaw", "next_edge", "pydantic_ai"):
        t.status     = "assumed_live"
        t.latency_ms = 0.0
    elif t.engine == "hermes_cli":
        hermes_cli = (
            CAMELOT_HOME / "02_FORGE" / "KINETIC_ARMORY" / "hermes-agent" / "cli.py"
        )
        t.status     = "live" if hermes_cli.exists() else "dark"
        t.latency_ms = 0.0
    else:
        t.status     = "unknown"
        t.latency_ms = 0.0


# ── Switchboard class ─────────────────────────────────────────────────────────

class Switchboard:
    """Flight Control Terminal for all LLM engines.

    Air Traffic Control (Sir Link) pattern:
      - All traffic declared before routing
      - No dispatch to dark/degraded without fallback
      - Manifest broadcast to HUD on every probe cycle
    """

    def __init__(self):
        self._reg: dict[str, Terminal] = {k: v for k, v in TERMINAL_REGISTRY.items()}

    # ── Probing ───────────────────────────────────────────────────────────────

    async def probe_all(self) -> None:
        await asyncio.gather(*[_probe_terminal(t) for t in self._reg.values()])
        self._write_manifest()

    async def probe_one(self, terminal_id: str) -> Terminal | None:
        t = self._reg.get(terminal_id)
        if t:
            await _probe_terminal(t)
            self._write_manifest()
        return t

    def _needs_probe(self, t: Terminal) -> bool:
        return (time.time() - t.last_probe) > HEALTH_TTL_S

    # ── Routing ───────────────────────────────────────────────────────────────

    async def best_for(self, capabilities: list[str], cost_ceiling: str = "high") -> Terminal | None:
        """Return best live terminal matching capabilities. Lazy-probes stale entries."""
        cost_order = ["free", "low", "medium", "high"]
        ceiling_idx = cost_order.index(cost_ceiling) if cost_ceiling in cost_order else 3

        candidates = [
            t for t in self._reg.values()
            if any(c in t.capability for c in capabilities)
            and cost_order.index(t.cost_tier) <= ceiling_idx
        ]

        # Probe stale candidates lazily
        stale = [t for t in candidates if self._needs_probe(t)]
        if stale:
            await asyncio.gather(*[_probe_terminal(t) for t in stale])
            self._write_manifest()

        live = [t for t in candidates if t.status in ("live", "assumed_live")]
        if not live:
            return None
        return max(live, key=lambda t: t.weight)

    def route_sync(self, knight_id: str) -> Terminal | None:
        """Synchronous cache-only lookup — zero probe cost."""
        t = self._reg.get(knight_id)
        if t and t.status in ("live", "assumed_live", "unknown"):
            return t
        # Find live fallback with highest weight
        live = [x for x in self._reg.values() if x.status in ("live", "assumed_live")]
        return max(live, key=lambda x: x.weight) if live else None

    # ── Manifest ──────────────────────────────────────────────────────────────

    def _write_manifest(self) -> None:
        data = {
            "updated": time.time(),
            "terminals": {k: asdict(v) for k, v in self._reg.items()},
        }
        try:
            MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def read_manifest(self) -> dict:
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def summary(self) -> dict[str, str]:
        return {k: v.status for k, v in self._reg.items()}


# ── Module-level singleton ────────────────────────────────────────────────────

_board = Switchboard()


async def probe_all() -> None:
    await _board.probe_all()

async def best_for(capabilities: list[str], cost_ceiling: str = "high") -> Terminal | None:
    return await _board.best_for(capabilities, cost_ceiling)

def route_sync(knight_id: str) -> Terminal | None:
    return _board.route_sync(knight_id)

def get_manifest() -> dict:
    return _board.read_manifest()

def summary() -> dict[str, str]:
    return _board.summary()

def get_board() -> Switchboard:
    return _board
