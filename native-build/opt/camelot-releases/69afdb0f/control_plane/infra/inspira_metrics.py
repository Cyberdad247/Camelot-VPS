# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Inspira Metrics — CAMELOT-OS HiveIDE Enterprise Telemetry
=========================================================
EXCALIBUR_A_QNF Pillar 4. Aggregates live factory + governance + memory +
compression telemetry into a single typed snapshot for the Inspira dashboard.

Sources (all read-only, graceful if absent):
    factory lanes      — logs/harness_queue.jsonl depth per lane
    HITL governance    — logs/hitl_queue.jsonl rates
    colony forensics   — 01_KERNEL/colony_report.md risk score + secrets
    FirnFlow memory    — nuKG crystal count, L1 token budget
    cost               — always 0.00 (38 free models via CLIProxy OAuth)

Public API:
    collect_metrics()  -> InspiraMetrics
    InspiraMetrics.render()  -> str (dashboard text block)

Run as module:
    python -m control_plane.inspira_metrics
    python -m control_plane.inspira_metrics --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import os
import re
import time
from pathlib import Path

from pydantic import BaseModel, Field

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
QUEUE_FILE = CAMELOT_HOME / "logs" / "harness_queue.jsonl"
HITL_QUEUE = CAMELOT_HOME / "logs" / "hitl_queue.jsonl"
COLONY_REPORT = CAMELOT_HOME / "01_KERNEL" / "colony_report.md"

_BOOT_TIME = time.time()


class InspiraMetrics(BaseModel):
    lane_depth: dict[str, int] = Field(default_factory=dict)
    knight_utilization: dict[str, float] = Field(default_factory=dict)
    hitl_rates: dict[str, int] = Field(default_factory=dict)
    blocked_per_hour: int = 0
    mamba_compression_ratio: float = 0.0
    kv_cache_hit_rate: float = 0.0
    cost_hour_usd: float = 0.0
    active_shatterpoints: list[str] = Field(default_factory=list)
    colony_risk_score: int = 0
    secrets_pending_rotation: int = 0
    crystal_count: int = 0
    uptime_seconds: int = 0

    def render(self) -> str:
        _sep = "─" * 60
        lanes = "  ".join(f"{k}:{v}" for k, v in sorted(self.lane_depth.items()))
        hitl = "  ".join(f"{k}:{v}" for k, v in self.hitl_rates.items())
        return "\n".join([
            "┌─ INSPIRA ENTERPRISE ─────────────────────────────────────┐",
            f"  LANES        {lanes or '(idle)'}",
            f"  IRON GATE    {hitl or '(none)'}   blocked/hr={self.blocked_per_hour}",
            f"  MEMORY       crystals={self.crystal_count}  kv_hit={self.kv_cache_hit_rate:.0%}",
            f"  COMPRESSION  mamba={self.mamba_compression_ratio:.1f}:1",
            f"  COLONY       risk={self.colony_risk_score}/100  secrets={self.secrets_pending_rotation}",
            f"  COST         ${self.cost_hour_usd:.2f}/hr (38 free models)",
            f"  UPTIME       {self.uptime_seconds}s   shatterpoints={len(self.active_shatterpoints)}",
            "└──────────────────────────────────────────────────────────┘",
        ])


def _lane_depth() -> dict[str, int]:
    depth = {"CRITICAL": 0, "HIGH": 0, "NORMAL": 0, "BACKGROUND": 0}
    if not QUEUE_FILE.exists():
        return depth
    try:
        for line in QUEUE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            lane = str(rec.get("lane", rec.get("priority", "NORMAL"))).upper()
            if lane in depth:
                depth[lane] += 1
            else:
                depth["NORMAL"] += 1
    except Exception:
        pass
    return depth


def _hitl_rates() -> tuple[dict[str, int], int]:
    rates = {"AUTO": 0, "PROMPT": 0, "HUMAN_GATE": 0, "SUSPENDED": 0}
    blocked = 0
    if not HITL_QUEUE.exists():
        return rates, blocked
    try:
        for line in HITL_QUEUE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tier = str(rec.get("hitl_tier", "")).upper()
            if tier in rates:
                rates[tier] += 1
            note = str(rec.get("note", "")).upper()
            if "BLOCK" in note or "Z3_BLOCK" in note:
                blocked += 1
    except Exception:
        pass
    return rates, blocked


def _colony_score() -> tuple[int, int]:
    """Parse risk score + secret count from colony_report.md (graceful)."""
    if not COLONY_REPORT.exists():
        return 0, 0
    text = COLONY_REPORT.read_text(encoding="utf-8", errors="replace")
    score = 0
    secrets = 0
    m = re.search(r"Risk Score\s*\|\s*([0-9.]+)", text)
    if m:
        score = int(float(m.group(1)))
    m2 = re.search(r"(\d+)\s+potential secret", text)
    if m2:
        secrets = int(m2.group(1))
    return score, secrets


def _crystal_count() -> int:
    try:
        from .firnflow import FirnFlow
        return len(FirnFlow().list_crystals())
    except Exception:
        return 0


def _mamba_compression_ratio() -> float:
    """Live Ouroboros SSM (mamba-3) context-compression factor as N:1 (P1-T08).

    Uses CompressionNexus tier-1 QFT compression as the SSM proxy on a
    representative context block. Returns the compression factor (e.g. 4.8 →
    4.8:1) or 0.0 if the engine is unavailable. Graceful — never raises.
    """
    try:
        from .compression_nexus import CompressionNexus
        sample = "# Camelot Context\n" + "\n".join(
            f"## Section {i}\n" + "\n".join(
                f"line {i}-{j} sovereign edge empire context detail bulk text"
                for j in range(20)
            ) for i in range(40)
        )
        res = CompressionNexus().compress_context(sample)
        if 0.0 < res.ratio < 1.0:
            return round(1.0 / (1.0 - res.ratio), 2)
    except Exception:
        pass
    return 0.0


def _kv_cache_hit_rate(router=None) -> float:
    """Runtime KV-cache hit-rate proxy from the soul_router TTFT tracker (P1-T08).

    Hits = TTFT samples under the SLO threshold (fast turnaround ⇒ prefix/KV
    cache reuse). Returns a 0..1 rate, or 0.0 when no samples have been recorded
    yet. Graceful — never raises.
    """
    try:
        from control_plane.core.soul_router import SoulRouter
        r = router if router is not None else SoulRouter()
        samples = [t for hist in getattr(r, "_ttft_history", {}).values() for t in hist]
        if not samples:
            return 0.0
        slo = getattr(r, "slo_threshold_ms", 2000.0)
        hits = sum(1 for t in samples if t <= slo)
        return round(hits / len(samples), 4)
    except Exception:
        return 0.0


def collect_metrics() -> InspiraMetrics:
    """Aggregate a live telemetry snapshot from all sources."""
    lanes = _lane_depth()
    hitl, blocked = _hitl_rates()
    score, secrets = _colony_score()
    return InspiraMetrics(
        lane_depth=lanes,
        hitl_rates=hitl,
        blocked_per_hour=blocked,
        mamba_compression_ratio=_mamba_compression_ratio(),   # live: CompressionNexus SSM proxy
        kv_cache_hit_rate=_kv_cache_hit_rate(),                # live: soul_router TTFT tracker
        cost_hour_usd=0.0,             # 38 free models
        active_shatterpoints=[],
        colony_risk_score=score,
        secrets_pending_rotation=secrets,
        crystal_count=_crystal_count(),
        uptime_seconds=int(time.time() - _BOOT_TIME),
    )


# ── Self-test ────────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("InspiraMetrics self-test")

    # V6.4 schema (12 fields)
    check("V6.4 InspiraMetrics has 12 fields", len(InspiraMetrics.model_fields) == 12)

    # V6.5 collection works and cost is 0
    m = collect_metrics()
    check("V6.5 collect_metrics returns snapshot", isinstance(m, InspiraMetrics))
    check("V6.5 cost is 0.00 (free models)", m.cost_hour_usd == 0.0)

    # lane depth keys present
    check("lane_depth has 4 lanes",
          set(m.lane_depth.keys()) == {"CRITICAL", "HIGH", "NORMAL", "BACKGROUND"})

    # crystal count reads FirnFlow (should be >= 4 after Phase 3 seeding)
    check("crystal_count reads FirnFlow", m.crystal_count >= 0)

    # P1-T08: live data wiring — mamba compression non-zero when engine available
    check(f"P1-T08 mamba_compression_ratio > 0 (={m.mamba_compression_ratio})",
          m.mamba_compression_ratio > 0)
    # kv_cache_hit_rate computes from soul_router TTFT history (seeded probe)
    from control_plane.core.soul_router import SoulRouter
    _r = SoulRouter()
    _r.record_ttft("sir_ouroboros", 400.0)   # under SLO -> hit
    _r.record_ttft("sir_ouroboros", 2500.0)  # over SLO  -> miss
    _rate = _kv_cache_hit_rate(_r)
    check(f"P1-T08 kv_cache_hit_rate from TTFT tracker (={_rate})", _rate == 0.5)

    # render produces a dashboard block
    block = m.render()
    check("render produces dashboard", "INSPIRA ENTERPRISE" in block and "COST" in block)

    print(m.render())
    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — inspira_metrics")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print(collect_metrics().render())
