# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
[S4-04] SIR_OCTAVIAN — Factory Metrics & Telemetry Node
========================================================
Reads: harness_queue.jsonl, switchboard_manifest.json, PROVENANCE_LEDGER.md
Emits: logs/metrics.json  +  optional HTTP endpoint at :8400

Usage:
    python control_plane/sir_octavian.py              # one-shot metrics snapshot
    python control_plane/sir_octavian.py --serve      # serve metrics JSON at :8400
    python control_plane/sir_octavian.py --watch 30   # refresh every 30s
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
QUEUE_PATH    = HOME / "logs" / "harness_queue.jsonl"
MANIFEST_PATH = HOME / "logs" / "switchboard_manifest.json"
LEDGER_PATH   = HOME / "PROVENANCE_LEDGER.md"
METRICS_PATH  = HOME / "logs" / "metrics.json"
METRICS_PORT  = 8400

THROUGHPUT_WINDOW_S = 3600  # tasks per hour window


# ── Collectors ────────────────────────────────────────────────────────────────

def _collect_queue() -> dict:
    if not QUEUE_PATH.exists():
        return {"pending": 0, "total_lines": 0}
    lines = QUEUE_PATH.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    pending = sum(
        1 for ln in lines
        if ln.strip() and '"status"' not in ln  # unprocessed = no status field
    )
    return {"pending": pending, "total_lines": total}


def _collect_terminals() -> dict:
    if not MANIFEST_PATH.exists():
        return {"live": 0, "dark": 0, "total": 0, "terminals": {}}
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"live": 0, "dark": 0, "total": 0, "terminals": {}}
    terminals = manifest.get("terminals", {})
    live = sum(1 for t in terminals.values() if t.get("status") in ("live", "assumed_live"))
    dark = sum(1 for t in terminals.values() if t.get("status") == "dark")
    return {
        "live": live,
        "dark": dark,
        "total": len(terminals),
        "terminals": {k: v.get("status", "unknown") for k, v in terminals.items()},
    }


def _collect_ledger() -> dict:
    if not LEDGER_PATH.exists():
        return {"total_entries": 0, "last_hour": 0, "max_id": 0}
    text = LEDGER_PATH.read_text(encoding="utf-8")
    all_ids = [int(m.group(1)) for m in re.finditer(r"^\| *(\d+) *\|", text, re.MULTILINE)]
    # Rough "last hour" estimate: entries in last THROUGHPUT_WINDOW_S seconds
    # Ledger rows don't carry timestamps in a parseable column, so proxy by
    # assuming entries are appended in temporal order and each sprint takes ~hours
    total = len(all_ids)
    max_id = max(all_ids, default=0)
    return {"total_entries": total, "max_id": max_id}


def _throughput_tasks_per_hour() -> float:
    """Estimate tasks/hr from queue file mtime delta vs line count."""
    if not QUEUE_PATH.exists():
        return 0.0
    stat = QUEUE_PATH.stat()
    age_s = time.time() - stat.st_mtime
    if age_s < 1:
        return 0.0
    lines = QUEUE_PATH.read_text(encoding="utf-8").count("\n")
    return round((lines / age_s) * THROUGHPUT_WINDOW_S, 1)


def collect_metrics() -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    queue    = _collect_queue()
    ledger   = _collect_ledger()
    terminals = _collect_terminals()
    throughput = _throughput_tasks_per_hour()

    return {
        "ts": ts,
        "engine": "SIR_OCTAVIAN",
        "throughput_tasks_per_hr": throughput,
        "queue": queue,
        "terminals": terminals,
        "ledger": ledger,
        "health": "green" if terminals["dark"] == 0 else (
            "yellow" if terminals["live"] > terminals["dark"] else "red"
        ),
    }


def snapshot(print_output: bool = True) -> dict:
    metrics = collect_metrics()
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if print_output:
        _print_metrics(metrics)
    return metrics


def _print_metrics(m: dict) -> None:
    t = m["terminals"]
    q = m["queue"]
    ledger = m["ledger"]
    health_icon = {"green": "✅", "yellow": "⚠️", "red": "❌"}.get(m["health"], "?")
    print(f"\n[OCTAVIAN] Factory Metrics  {m['ts']}")
    print(f"  Health      : {health_icon} {m['health'].upper()}")
    print(f"  Throughput  : {m['throughput_tasks_per_hr']} tasks/hr")
    print(f"  Queue       : {q['pending']} pending / {q['total_lines']} total")
    print(f"  Terminals   : {t['live']} live  {t['dark']} dark  {t['total']} total")
    print(f"  Ledger      : {ledger['total_entries']} entries  max_id={ledger['max_id']}")
    if t["dark"] > 0:
        dark_names = [k for k, v in t["terminals"].items() if v == "dark"]
        print(f"  Dark nodes  : {', '.join(dark_names)}")


# ── HTTP server ───────────────────────────────────────────────────────────────

async def _serve(port: int = METRICS_PORT) -> None:
    from aiohttp import web  # type: ignore

    async def handle_metrics(req: web.Request) -> web.Response:
        metrics = collect_metrics()
        METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return web.Response(
            text=json.dumps(metrics, indent=2),
            content_type="application/json",
        )

    app = web.Application()
    app.router.add_get("/metrics", handle_metrics)
    app.router.add_get("/", handle_metrics)  # convenience alias
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[OCTAVIAN] Metrics server ::{port} ONLINE  (GET /metrics)")
    await asyncio.Event().wait()


async def _watch(interval: int) -> None:
    print(f"[OCTAVIAN] Watching — refresh every {interval}s")
    while True:
        snapshot()
        await asyncio.sleep(interval)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(prog="sir_octavian", description="CAMELOT-OS Factory Metrics")
    ap.add_argument("--serve",  action="store_true",  help=f"Serve JSON at :{METRICS_PORT}")
    ap.add_argument("--watch",  type=int, metavar="SEC", help="Refresh interval in seconds")
    ap.add_argument("--port",   type=int, default=METRICS_PORT)
    args = ap.parse_args()

    if args.serve:
        asyncio.run(_serve(args.port))
    elif args.watch:
        asyncio.run(_watch(args.watch))
    else:
        snapshot()


# =============================================================================
# ROUTING ARCHITECTURE EXTENSION  (Sir Alex coordination + Audio Pipeline)
# =============================================================================
"""
Audio Pipeline Router — Cascaded vs Native Audio selection
-----------------------------------------------------------
Cascaded (default, zero-cost):
  User Audio → [STT: faster-whisper] → Text → [LLM: Knight] → Text
             → [TTS: Kokoro/Piper/Silero] → Output Audio

Native Audio (Omni, when available):
  User Audio → [Omni LLM: GPT-4o Realtime / Gemini Live] → Output Audio
  (preserves prosody, inflection, emotion — no text intermediary)

Sir Alex coordinates routing via Triple-QFT:
  Renormalize (strip noise) → Quantize (compress) → Route to optimal engine

Additional engine registry: Groq, Together, Mistral, Ollama multi-model,
OpenRouter, Perplexity — all registered with cost/latency/privacy scores.
"""

from enum import Enum as _Enum  # noqa: E402
from typing import Optional as _Optional  # noqa: E402


class AudioPipeline(_Enum):
    CASCADED     = "cascaded"       # STT → LLM → TTS  (always available)
    NATIVE_AUDIO = "native_audio"   # Omni LLM audio-in → audio-out
    HYBRID       = "hybrid"         # native preferred, cascaded fallback


class CostTier(_Enum):
    FREE   = 0   # zero cost: local models, Ollama, free tiers
    LOW    = 1   # minimal: Groq free tier, Together free tier, Gemini Flash
    MEDIUM = 2   # moderate: Claude Haiku, GPT-4o-mini, Mistral Small
    HIGH   = 3   # premium: Claude Opus, GPT-4o, Gemini Ultra


# ── Additional Engine Registry ────────────────────────────────────────────────

ENGINE_REGISTRY: list[dict] = [
    # Zero-cost (local / offline)
    {"id": "ollama_llama32",    "type": "llm",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 800,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "http://localhost:11434/v1",  "model": "llama3.2"},
    {"id": "ollama_phi35",      "type": "llm",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 600,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "http://localhost:11434/v1",  "model": "phi3.5"},
    {"id": "ollama_gemma2",     "type": "llm",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 700,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "http://localhost:11434/v1",  "model": "gemma2"},
    {"id": "ollama_qwen25",     "type": "llm",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 650,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "http://localhost:11434/v1",  "model": "qwen2.5"},
    {"id": "ollama_mistral",    "type": "llm",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 750,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "http://localhost:11434/v1",  "model": "mistral"},
    {"id": "silero_tts",        "type": "tts",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 80,   "pipeline": AudioPipeline.CASCADED,     "endpoint": "local",                     "model": "silero_v3_en"},
    {"id": "piper_tts",         "type": "tts",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 100,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "local",                     "model": "piper_onnx"},
    {"id": "kokoro_tts",        "type": "tts",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 150,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "local",                     "model": "kokoro_v019"},
    {"id": "speecht5",          "type": "tts",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 200,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "local",                     "model": "speecht5_tts"},
    {"id": "mms_tts",           "type": "tts",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 180,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "local",                     "model": "mms-tts-eng"},
    {"id": "faster_whisper",    "type": "stt",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 60,   "pipeline": AudioPipeline.CASCADED,     "endpoint": "local",                     "model": "whisper_base"},
    {"id": "wav2vec2",          "type": "stt",  "cost": CostTier.FREE,   "privacy": 1.0, "latency_ms": 120,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "local",                     "model": "wav2vec2_base_960h"},
    # Low cost (API free tiers / generous limits)
    {"id": "groq_llama31_8b",   "type": "llm",  "cost": CostTier.LOW,    "privacy": 0.3, "latency_ms": 80,   "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://api.groq.com/openai/v1", "model": "llama-3.1-8b-instant"},
    {"id": "groq_mixtral",      "type": "llm",  "cost": CostTier.LOW,    "privacy": 0.3, "latency_ms": 120,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://api.groq.com/openai/v1", "model": "mixtral-8x7b-32768"},
    {"id": "together_llama3",   "type": "llm",  "cost": CostTier.LOW,    "privacy": 0.2, "latency_ms": 200,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://api.together.xyz/v1",   "model": "meta-llama/Llama-3.1-70B-Instruct"},
    {"id": "openrouter",        "type": "llm",  "cost": CostTier.LOW,    "privacy": 0.2, "latency_ms": 300,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://openrouter.ai/api/v1",  "model": "auto"},
    {"id": "perplexity_sonar",  "type": "llm",  "cost": CostTier.LOW,    "privacy": 0.2, "latency_ms": 500,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://api.perplexity.ai",     "model": "sonar"},
    # Medium cost
    {"id": "mistral_small",     "type": "llm",  "cost": CostTier.MEDIUM, "privacy": 0.3, "latency_ms": 400,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://api.mistral.ai/v1",     "model": "mistral-small-latest"},
    {"id": "claude_haiku",      "type": "llm",  "cost": CostTier.MEDIUM, "privacy": 0.3, "latency_ms": 350,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://api.anthropic.com",     "model": "claude-haiku-4-5-20251001"},
    {"id": "gpt4o_mini",        "type": "llm",  "cost": CostTier.MEDIUM, "privacy": 0.2, "latency_ms": 300,  "pipeline": AudioPipeline.CASCADED,     "endpoint": "https://api.openai.com/v1",     "model": "gpt-4o-mini"},
    # Native Audio (Omni — audio-in → audio-out, no text intermediary)
    {"id": "gpt4o_realtime",    "type": "omni", "cost": CostTier.HIGH,   "privacy": 0.1, "latency_ms": 200,  "pipeline": AudioPipeline.NATIVE_AUDIO, "endpoint": "wss://api.openai.com/v1/realtime", "model": "gpt-4o-realtime-preview"},
    {"id": "gemini_live",       "type": "omni", "cost": CostTier.HIGH,   "privacy": 0.1, "latency_ms": 250,  "pipeline": AudioPipeline.NATIVE_AUDIO, "endpoint": "wss://generativelanguage.googleapis.com", "model": "gemini-2.0-flash-live"},
]


# ── Route scoring (Sir Alex Triple-QFT coordination) ─────────────────────────

def _score_engine(engine: dict, req: dict) -> float:
    """
    Soul Router score for engine selection.
    S = 0.20*V + 0.35*M + 0.30*P + 0.15*E  (Soul Router equation)

    req keys:
      latency_budget_ms: int      — max acceptable latency
      privacy_floor:     float    — minimum privacy score [0,1]
      cost_ceiling:      CostTier — max cost tier
      pipeline:          AudioPipeline | None — required pipeline type
    """
    latency_budget: int         = req.get("latency_budget_ms", 2000)
    privacy_floor:  float       = req.get("privacy_floor", 0.0)
    cost_ceiling:   CostTier    = req.get("cost_ceiling", CostTier.HIGH)
    req_pipeline:   _Optional[AudioPipeline] = req.get("pipeline")

    # Hard constraints
    if engine["privacy"] < privacy_floor:
        return -1.0
    if engine["cost"].value > cost_ceiling.value:
        return -1.0
    if req_pipeline and engine["pipeline"] != req_pipeline:
        return -1.0

    # Soft scores
    V = max(0.0, 1.0 - engine["latency_ms"] / latency_budget)  # velocity
    M = 1.0                                                       # magnitude (equal for now)
    P = engine["privacy"]                                         # privacy
    E = 1.0 - engine["cost"].value / 4.0                        # environment fit

    return round(0.20 * V + 0.35 * M + 0.30 * P + 0.15 * E, 4)


def route_audio_pipeline(
    engine_type: str = "llm",
    requirements: _Optional[dict] = None,
) -> list[dict]:
    """
    Sir Alex Triple-QFT routing for audio pipeline engine selection.

    Returns ranked list of matching engines (best first).
    engine_type: "llm" | "tts" | "stt" | "omni"
    """
    req = requirements or {}
    candidates = [e for e in ENGINE_REGISTRY if e["type"] == engine_type]
    scored = []
    for eng in candidates:
        score = _score_engine(eng, req)
        if score >= 0:
            scored.append({**eng, "_score": score})
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored


def best_engine(engine_type: str = "llm", requirements: _Optional[dict] = None) -> _Optional[dict]:
    """Return single best engine dict, or None if no candidates pass constraints."""
    ranked = route_audio_pipeline(engine_type, requirements)
    return ranked[0] if ranked else None


def pipeline_summary() -> dict:
    """Return a summary of all registered engines grouped by pipeline type."""
    cascaded = [e["id"] for e in ENGINE_REGISTRY if e["pipeline"] == AudioPipeline.CASCADED]
    native   = [e["id"] for e in ENGINE_REGISTRY if e["pipeline"] == AudioPipeline.NATIVE_AUDIO]
    free     = [e["id"] for e in ENGINE_REGISTRY if e["cost"] == CostTier.FREE]
    return {
        "total_engines":   len(ENGINE_REGISTRY),
        "cascaded_count":  len(cascaded),
        "native_audio":    native,
        "zero_cost":       free,
        "zero_cost_count": len(free),
    }


if __name__ == "__main__":
    main()
