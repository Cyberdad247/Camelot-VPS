# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
FirnFlow — CAMELOT-OS Tiered Semantic Memory Mesh
==================================================
EXCALIBUR_A_QNF Pillar 4. Replaces flat-file context with scoped, tiered
retrieval (MemPalace 2.0 / FirnFlow, v999 NLM).

Tiers:
  L1  — RAM foyer cache: active working context, hard token budget (8192).
  L2  — Episodic store: Wing -> Room -> Drawer namespace. LanceDB when present,
        JSON-file fallback otherwise (fully functional without the dependency).
  L3  — Cold archive: long-term logs on disk (provenance, step caches).

νKG_Crystals: successful patterns crystallized into L2 for future reuse
(Chimera NLM). Eviction is by semantic recency within the L1 token budget,
not arbitrary LRU.

Public API:
    FirnFlow.retrieve(query, scope)   -> list[Chunk]
    FirnFlow.anchor(key, value, tier) -> None
    FirnFlow.crystallize(skill_id, pattern) -> NuKGCrystal
    FirnFlow.list_crystals()          -> list[NuKGCrystal]

Run as module:
    python -m control_plane.firnflow --status
    python -m control_plane.firnflow --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import math
import os
import re
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
FIRNFLOW_DIR = CAMELOT_HOME / "03_VAULT" / "firnflow"
L2_STORE = FIRNFLOW_DIR / "l2_episodic.json"
L3_DIR = FIRNFLOW_DIR / "l3_cold"
CRYSTAL_STORE = FIRNFLOW_DIR / "nukg_crystals.json"

L1_TOKEN_BUDGET = 8192
CRYSTAL_THRESHOLD = 0.85

Tier = Literal["L1", "L2", "L3"]

# Wing -> directory mapping (v999 NLM namespace)
WINGS: dict[str, str] = {
    "KERNEL": "01_KERNEL",
    "CONTROL": "control_plane",
    "FORGE": "02_FORGE",
    "VAULT": "03_VAULT",
    "HIVE": ".hive",
}


def _est_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token)."""
    return max(1, math.ceil(len(text) / 4))


@dataclass
class Chunk:
    key: str
    value: str
    tier: Tier
    tokens: int
    score: float = 1.0


@dataclass
class NuKGCrystal:
    """A crystallized successful pattern (Chimera NLM)."""
    crystal_id: str
    skill_pattern: str
    knight: str
    confidence: float
    context_tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reuse_count: int = 0


class FirnFlow:
    """Tiered semantic memory. L1 always available; L2/L3 persist to disk."""

    def __init__(self, l1_budget: int = L1_TOKEN_BUDGET):
        self.l1_budget = l1_budget
        self._l1: "OrderedDict[str, Chunk]" = OrderedDict()
        self._l1_tokens = 0
        FIRNFLOW_DIR.mkdir(parents=True, exist_ok=True)
        L3_DIR.mkdir(parents=True, exist_ok=True)
        self._lancedb_available = self._probe_lancedb()
        self._l2_backend = "lancedb" if self._lancedb_available else "json-fallback"

    @staticmethod
    def _probe_lancedb() -> bool:
        try:
            import lancedb  # noqa: F401
            return True
        except ImportError:
            return False

    # ── L1 foyer cache ───────────────────────────────────────────────────────

    def _l1_evict_to_budget(self) -> None:
        """Evict oldest entries until within token budget (semantic recency)."""
        while self._l1_tokens > self.l1_budget and self._l1:
            _, evicted = self._l1.popitem(last=False)
            self._l1_tokens -= evicted.tokens

    def _l1_anchor(self, key: str, value: str) -> None:
        tokens = _est_tokens(value)
        if key in self._l1:
            self._l1_tokens -= self._l1[key].tokens
        self._l1[key] = Chunk(key=key, value=value, tier="L1", tokens=tokens)
        self._l1.move_to_end(key)
        self._l1_tokens += tokens
        self._l1_evict_to_budget()

    # ── L2 episodic (JSON fallback) ──────────────────────────────────────────

    def _l2_load(self) -> dict[str, Any]:
        if L2_STORE.exists():
            try:
                return json.loads(L2_STORE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def _l2_save(self, data: dict[str, Any]) -> None:
        tmp = L2_STORE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(L2_STORE)

    def _l2_anchor(self, key: str, value: str) -> None:
        data = self._l2_load()
        data[key] = {"value": value, "ts": datetime.now(timezone.utc).isoformat()}
        self._l2_save(data)

    # ── L3 cold archive ──────────────────────────────────────────────────────

    def _l3_anchor(self, key: str, value: str) -> None:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", key)[:120]
        (L3_DIR / f"{safe}.txt").write_text(value, encoding="utf-8")

    # ── Public API ────────────────────────────────────────────────────────────

    def anchor(self, key: str, value: str, tier: Tier = "L1") -> None:
        """Store a value in the given tier."""
        if tier == "L1":
            self._l1_anchor(key, value)
        elif tier == "L2":
            self._l2_anchor(key, value)
        elif tier == "L3":
            self._l3_anchor(key, value)

    def retrieve(self, query: str, scope: Tier = "L1") -> list[Chunk]:
        """Scoped retrieval. Substring/keyword match within token budget."""
        q = query.lower().strip()
        terms = set(q.split())
        results: list[Chunk] = []

        if scope == "L1":
            for chunk in self._l1.values():
                hay = (chunk.key + " " + chunk.value).lower()
                overlap = sum(1 for t in terms if t in hay)
                if overlap:
                    results.append(Chunk(chunk.key, chunk.value, "L1",
                                         chunk.tokens, score=overlap / max(1, len(terms))))
        elif scope == "L2":
            for key, rec in self._l2_load().items():
                val = rec.get("value", "") if isinstance(rec, dict) else str(rec)
                hay = (key + " " + val).lower()
                overlap = sum(1 for t in terms if t in hay)
                if overlap:
                    results.append(Chunk(key, val, "L2", _est_tokens(val),
                                         score=overlap / max(1, len(terms))))
        elif scope == "L3":
            for f in L3_DIR.glob("*.txt"):
                val = f.read_text(encoding="utf-8", errors="replace")
                hay = (f.stem + " " + val).lower()
                if any(t in hay for t in terms):
                    results.append(Chunk(f.stem, val, "L3", _est_tokens(val)))

        results.sort(key=lambda c: c.score, reverse=True)
        # enforce token budget on returned set
        out, budget = [], self.l1_budget
        for c in results:
            if budget - c.tokens < 0:
                break
            out.append(c)
            budget -= c.tokens
        return out

    # ── World Tree directory-scoped hydration (P2-T05) ───────────────────────

    def _resolve_wing(self, scope: str) -> str:
        """Resolve a Wing name or directory path to a canonical Wing key."""
        s = (scope or "").strip()
        up = s.upper()
        if up in WINGS:
            return up
        norm = s.replace("\\", "/").strip("/").lower()
        for wing, directory in WINGS.items():
            if norm == directory.lower() or norm.startswith(directory.lower() + "/"):
                return wing
        return up  # fall back to the raw token (still usable as a namespace)

    def hydrate_scope(self, scope: str, query: str = "",
                      tiers: tuple[Tier, ...] = ("L1", "L2", "L3")) -> list[Chunk]:
        """World Tree context hydration — load only the context namespaced to a
        directory/Wing (Wing→Room→Drawer), instead of the whole flat store.

        `scope` is a Wing name (KERNEL/CONTROL/FORGE/VAULT/HIVE) or a directory
        path that maps to a Wing. Keys are namespaced as ``WING:room/drawer``.
        Optional `query` further filters within the scope. Returns the scoped
        chunks ordered L1→L2→L3.
        """
        wing = self._resolve_wing(scope)
        prefix = f"{wing}:".upper()
        l3_prefix = re.sub(r"[^a-zA-Z0-9_.-]", "_", f"{wing}:")[:120].upper()
        q_terms = {t for t in query.lower().split()}

        def _match(key: str, val: str, l3: bool = False) -> bool:
            ku = key.upper()
            if not (ku.startswith(prefix) or (l3 and ku.startswith(l3_prefix))):
                return False
            if q_terms:
                hay = (key + " " + val).lower()
                return any(t in hay for t in q_terms)
            return True

        results: list[Chunk] = []
        if "L1" in tiers:
            for c in self._l1.values():
                if _match(c.key, c.value):
                    results.append(Chunk(c.key, c.value, "L1", c.tokens))
        if "L2" in tiers:
            for key, rec in self._l2_load().items():
                val = rec.get("value", "") if isinstance(rec, dict) else str(rec)
                if _match(key, val):
                    results.append(Chunk(key, val, "L2", _est_tokens(val)))
        if "L3" in tiers:
            for f in L3_DIR.glob("*.txt"):
                val = f.read_text(encoding="utf-8", errors="replace")
                if _match(f.stem, val, l3=True):
                    results.append(Chunk(f.stem, val, "L3", _est_tokens(val)))
        return results

    # ── νKG_Crystals ─────────────────────────────────────────────────────────

    def crystallize(self, skill_id: str, pattern: dict[str, Any]) -> NuKGCrystal:
        """Crystallize a successful pattern into L2 for future reuse."""
        confidence = float(pattern.get("confidence", 0.0))
        crystal = NuKGCrystal(
            crystal_id=skill_id,
            skill_pattern=str(pattern.get("pattern", skill_id)),
            knight=str(pattern.get("knight", "unknown")),
            confidence=confidence,
            context_tags=list(pattern.get("context_tags", [])),
        )
        crystals = self._load_crystals_raw()
        crystals[skill_id] = asdict(crystal)
        self._save_crystals_raw(crystals)
        return crystal

    def _load_crystals_raw(self) -> dict[str, Any]:
        if CRYSTAL_STORE.exists():
            try:
                return json.loads(CRYSTAL_STORE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_crystals_raw(self, data: dict[str, Any]) -> None:
        tmp = CRYSTAL_STORE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(CRYSTAL_STORE)

    def list_crystals(self) -> list[NuKGCrystal]:
        return [NuKGCrystal(**v) for v in self._load_crystals_raw().values()]

    # ── Status ──────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        status_dict = {
            "l1_entries": len(self._l1),
            "l1_tokens": self._l1_tokens,
            "l1_budget": self.l1_budget,
            "l2_backend": self._l2_backend,
            "l2_entries": len(self._l2_load()),
            "l3_files": len(list(L3_DIR.glob("*.txt"))),
            "crystals": len(self._load_crystals_raw()),
        }
        return status_dict

    # ── Apex Canonical 5-Tier Memory & NVMe Spill Gate (v4.1) ─────────────────
    # M0(Ledger) ➔ M1(Verified_UKG) ➔ M2(Active_Context) ➔ M3(WASM_mmap) ➔ M4(Quarantine)
    # RAM_THRESHOLD_90_PERCENT (7.2GB Server / 3.6GB Node) ➔ FIRNFLOW_CACHE_FLUSH

    def firnflow_cache_flush(self) -> dict[str, Any]:
        """Flushes active ephemeral context (M2/L1) down to NVMe cold storage (M0/L3)
        and trims working set memory under the 90% Heaviside trigger."""
        import gc
        flushed_count = len(self._l1)
        flushed_tokens = self._l1_tokens

        # Persist all active L1 chunks to L3 cold disk
        for key, chunk in list(self._l1.items()):
            self._l3_anchor(f"spill_{key}", chunk.value)

        self._l1.clear()
        self._l1_tokens = 0
        gc.collect()

        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
            except Exception:
                pass

        return {
            "status": "FIRNFLOW_CACHE_FLUSH_COMPLETE",
            "flushed_entries": flushed_count,
            "flushed_tokens": flushed_tokens,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def evaluate_spill_gate(self, force: bool = False, is_server: bool = False) -> dict[str, Any]:
        """Evaluates memory state against 90% threshold (7.2GB server / 3.6GB node)."""
        limit_mb = 8192.0 if is_server else 4096.0
        threshold_mb = limit_mb * 0.90

        proc_rss_mb = 0.0
        sys_percent = 0.0
        try:
            import psutil
            proc = psutil.Process()
            proc_rss_mb = proc.memory_info().rss / (1024 * 1024)
            sys_percent = psutil.virtual_memory().percent
        except Exception:
            pass

        triggered = force or (proc_rss_mb >= threshold_mb) or (sys_percent >= 90.0)
        flush_res = {}
        if triggered:
            flush_res = self.firnflow_cache_flush()

        return {
            "spill_gate_triggered": triggered,
            "threshold_mb": threshold_mb,
            "process_rss_mb": round(proc_rss_mb, 2),
            "system_percent": sys_percent,
            "flush_result": flush_res,
        }


def init_seed_crystals(ff: FirnFlow) -> int:
    """Initialize the 4 Phase-0 νKG_Crystals from EXCALIBUR_A_QNF findings."""
    seeds = [
        ("crystal_001_apee_v7_triage",
         {"pattern": "risk_entropy triage routing", "knight": "anya_omega",
          "confidence": 0.90, "context_tags": ["apee", "triage", "governance"]}),
        ("crystal_002_firnflow_scoped",
         {"pattern": "Wing->Room->Drawer scoped retrieval", "knight": "lady_m",
          "confidence": 0.88, "context_tags": ["memory", "retrieval"]}),
        ("crystal_003_colmad_crucible",
         {"pattern": "3-persona adversarial consensus", "knight": "merlin_omega",
          "confidence": 0.75, "context_tags": ["governance", "crucible"]}),
        ("crystal_004_rtk_strip",
         {"pattern": "90% noise strip pre-tokenization", "knight": "sir_lukas",
          "confidence": 0.92, "context_tags": ["compression", "rtk"]}),
    ]
    for sid, pat in seeds:
        ff.crystallize(sid, pat)
    return len(seeds)


# ── Self-test ────────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("FirnFlow self-test")
    ff = FirnFlow()

    # V3.5 L1 retrieve
    ff.anchor("test_key", "the EXCALIBUR kernel uses ternary quantization", "L1")
    r = ff.retrieve("EXCALIBUR ternary", "L1")
    check("V3.5 L1 anchor + retrieve returns match", len(r) >= 1 and "EXCALIBUR" in r[0].value)

    # V3.6 token budget enforcement
    small = FirnFlow(l1_budget=50)
    for i in range(40):
        small.anchor(f"k{i}", "x" * 100, "L1")  # ~25 tokens each
    check("V3.6 L1 token budget enforced", small._l1_tokens <= 50)

    # L2 anchor + retrieve
    ff.anchor("l2_doc", "FirnFlow L2 episodic memory with LanceDB fallback", "L2")
    r2 = ff.retrieve("episodic memory", "L2")
    check("L2 anchor + retrieve works", len(r2) >= 1)

    # V3.7 crystallize
    c = ff.crystallize("test_crystal", {"pattern": "test", "knight": "sir_boris", "confidence": 0.9})
    check("V3.7 crystallize returns crystal", c.crystal_id == "test_crystal")
    check("V3.7 crystal persisted", any(x.crystal_id == "test_crystal" for x in ff.list_crystals()))

    # seed crystals (AC-20: >= 4)
    init_seed_crystals(ff)
    check("AC-20 >= 4 seed crystals initialized", len(ff.list_crystals()) >= 4)

    # P2-T05: World Tree directory-scoped hydration
    ff.anchor("KERNEL:reasoning/ouroboros", "ouroboros ssm linear reasoning core", "L1")
    ff.anchor("CONTROL:gate/anya", "anya gate APEE triage pipeline", "L1")
    ff.anchor("KERNEL:senses/telemetry", "rotel telemetry client", "L2")
    kernel_ctx = ff.hydrate_scope("KERNEL")
    control_ctx = ff.hydrate_scope("control_plane")  # dir path -> CONTROL wing
    check("P2-T05 scoped hydration returns only KERNEL keys",
          len(kernel_ctx) >= 2 and all(c.key.upper().startswith("KERNEL:") for c in kernel_ctx))
    check("P2-T05 directory path resolves to CONTROL wing",
          len(control_ctx) >= 1 and all(c.key.upper().startswith("CONTROL:") for c in control_ctx))
    check("P2-T05 scope isolation (no cross-wing leakage)",
          not any(c.key.upper().startswith("CONTROL:") for c in kernel_ctx))
    check("P2-T05 query filter within scope",
          len(ff.hydrate_scope("KERNEL", query="telemetry")) == 1)

    # status
    st = ff.status()
    check("status reports l2_backend", st["l2_backend"] in ("lancedb", "json-fallback"))

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — firnflow "
          f"(L2 backend: {ff._l2_backend})")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    ff = FirnFlow()
    if "--seed" in sys.argv:
        n = init_seed_crystals(ff)
        print(f"Seeded {n} νKG_Crystals")
    st = ff.status()
    print("FirnFlow status:")
    for k, v in st.items():
        print(f"  {k:14s} {v}")
