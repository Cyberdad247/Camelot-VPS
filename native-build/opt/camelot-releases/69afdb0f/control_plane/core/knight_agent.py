# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Knight Agent — CAMELOT-OS Typed Knight Contracts
=================================================
EXCALIBUR_A_QNF Pillar 6. Replaces loose knight dispatch with Pydantic-typed
capability contracts (Pydantic AI pattern). Each knight declares its SkillGraph
tier (VIDENEPTUS S1-S5, Merlin NLM), preferred model, OCEAN persona profile
(PersRubrics, Blacklight NLM), and air-gap requirement.

Grounded in the live FOUNDRY_COUNCIL roster (soul_router.py) — capabilities are
derived from the authoritative engine map, not re-invented here.

Crystalline Sleep (v700 NLM): idle knights serialize their working state to
FirnFlow L2 and wake sub-second on demand, honoring the 8GB RAM ceiling.

Public API:
    load_roster()                  -> dict[str, KnightCapability]
    get_capability(knight_id)      -> KnightCapability
    CrystallineSleepManager.sleep / .wake / .is_awake

Run as module:
    python -m control_plane.knight_agent --test
    python -m control_plane.knight_agent --roster
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .factory_lane import UsageLimits

SkillTier = Literal["S1", "S2", "S3", "S4", "S5"]

# VIDENEPTUS SkillGraph tier per knight (Merlin NLM):
#   S1 atomic tools | S2 composite workflows | S3 contextual domain
#   S4 strategic orchestration | S5 quantum meta-logic / self-modification
# Invariant (P1-T03): every knight in soul_router.FOUNDRY_COUNCIL MUST have an
# explicit tier here — no reliance on a silent default. Entries for knights NOT
# in FOUNDRY_COUNCIL (merlin_omega the Grand Orchestrator, lady_apis the
# archivist, sir_debug) are meta-knights: valid tiers, but outside the routable
# council. The _selftest enforces council ⊆ _SKILLGRAPH_TIER.
_SKILLGRAPH_TIER: dict[str, SkillTier] = {
    "sir_ghost": "S1", "sir_debug": "S1",
    "sir_forge": "S2", "sir_codex": "S2", "sir_valerian": "S2",
    "sir_boris": "S3", "sir_sentinel": "S3", "sir_liberte": "S3",
    "sir_sonus": "S3",                       # Voice & Resonance (was missing — P1-T03)
    "sir_alex": "S4", "lady_apis": "S4", "sir_link": "S4", "sir_mnemo": "S4",
    "merlin_omega": "S5", "sir_helio": "S5", "sir_ouroboros": "S5",
    "sir_heimdall": "S4",
    "sir_openclaw": "S3", "sir_rustclaw": "S2", "sir_hermes": "S4",
    "lady_nanobot": "S3", "sir_zeroclaw": "S4",
    # Agents-A1 — agentic MoE orchestrator (S4 strategic orchestration). Was
    # absent, so it silently defaulted to S2 and broke the council⊆tier
    # invariant asserted by _selftest V5.6b.
    "sir_agentis": "S4",
}

# LATTICE_SIGNAL primary model bindings (OMNI_ROUTER_AUDIT). Gemini-primary.
_PRIMARY_MODEL: dict[str, str] = {
    "sir_boris": "gemini-3-pro-preview",
    "sir_alex": "gemini-3-pro-preview",
    "sir_helio": "gemini-3.1-pro-preview",
    "sir_codex": "gpt-5.4",
    "sir_forge": "qwen2.5-coder:3b",
    "sir_link": "gemini-3-flash-preview",
    "sir_ghost": "qwen3:8b",
    "sir_liberte": "gemini-2.5-flash",
    "sir_mnemo": "gemini-3.1-pro-preview",
    "sir_ouroboros": "ouroboros-ssm-local",
    "sir_sentinel": "gemini-3-pro-preview",
    "sir_valerian": "gemini-3-pro-preview",
    "sir_openclaw": "openclaw-local",
    "sir_rustclaw": "rustclaw-local",
    "sir_hermes": "hermes-cli",
    "lady_nanobot": "next-edge",
    "sir_zeroclaw": "qwen3:8b",
    # Local-first (privacy_level=0.9). Without this entry the roster defaulted it
    # to gemini-3-pro-preview — a third-party cloud model — which directly
    # contradicts the "never leaks prompts to a third-party cloud" guarantee on
    # the Agents-A1 engine definition. No _FALLBACK_MODEL entry is intentional: a
    # cloud fallback would reintroduce the same leak.
    "sir_agentis": "agents-a1",
}

_FALLBACK_MODEL: dict[str, str] = {
    "sir_boris": "claude-opus-4-6",
    "sir_alex": "claude-sonnet-4-6",
    "sir_helio": "gemini-3-pro-preview",
    "sir_codex": "gpt-5.3-codex-spark",
    "sir_link": "gemini-2.5-flash",
    "sir_sentinel": "claude-sonnet-4-6",
    "sir_mnemo": "claude-sonnet-4-6",
    "sir_openclaw": "sir_helio",
    "sir_rustclaw": "sir_forge",
    "sir_hermes": "sir_link",
    "lady_nanobot": "sir_codex",
    "sir_zeroclaw": "sir_ghost",
}

# OCEAN PersRubrics (Blacklight NLM): Big-5 numerical persona stabilizers (0-1).
# Tuned per knight role — high Conscientiousness for security, high Openness for research.
_OCEAN: dict[str, dict[str, float]] = {
    "sir_boris":    {"O": 0.80, "C": 0.90, "E": 0.60, "A": 0.55, "N": 0.20},
    "sir_alex":     {"O": 0.85, "C": 0.80, "E": 0.50, "A": 0.60, "N": 0.25},
    "sir_sentinel": {"O": 0.45, "C": 0.95, "E": 0.40, "A": 0.35, "N": 0.30},
    "sir_ghost":    {"O": 0.40, "C": 0.95, "E": 0.20, "A": 0.30, "N": 0.15},
    "lady_apis":    {"O": 0.95, "C": 0.70, "E": 0.65, "A": 0.70, "N": 0.20},
    "merlin_omega": {"O": 0.95, "C": 0.85, "E": 0.45, "A": 0.60, "N": 0.15},
    "sir_openclaw": {"O": 0.85, "C": 0.85, "E": 0.35, "A": 0.45, "N": 0.20},
    "sir_rustclaw": {"O": 0.65, "C": 0.95, "E": 0.25, "A": 0.35, "N": 0.15},
    "sir_hermes":   {"O": 0.70, "C": 0.90, "E": 0.45, "A": 0.55, "N": 0.20},
    "lady_nanobot": {"O": 0.90, "C": 0.75, "E": 0.60, "A": 0.60, "N": 0.20},
    "sir_zeroclaw": {"O": 0.50, "C": 0.98, "E": 0.25, "A": 0.25, "N": 0.20},
}
_OCEAN_DEFAULT = {"O": 0.60, "C": 0.75, "E": 0.50, "A": 0.55, "N": 0.25}


class KnightCapability(BaseModel):
    """Typed capability contract for one knight."""
    knight_id: str
    function: str
    skillgraph_tier: SkillTier
    engine: str
    primary_model: str
    fallback_model: Optional[str] = None
    privacy_level: float = Field(ge=0.0, le=1.0)
    requires_air_gap: bool = False
    ocean_profile: dict[str, float] = Field(default_factory=dict)
    usage_limits: UsageLimits = Field(default_factory=UsageLimits)


def load_roster() -> dict[str, KnightCapability]:
    """Build typed capabilities from the live FOUNDRY_COUNCIL roster."""
    from .soul_router import FOUNDRY_COUNCIL

    roster: dict[str, KnightCapability] = {}
    for e in FOUNDRY_COUNCIL:
        kid = e.knight_id
        roster[kid] = KnightCapability(
            knight_id=kid,
            function=e.function,
            skillgraph_tier=_SKILLGRAPH_TIER.get(kid, "S2"),
            engine=e.engine,
            primary_model=_PRIMARY_MODEL.get(kid, "gemini-3-pro-preview"),
            fallback_model=_FALLBACK_MODEL.get(kid),
            privacy_level=e.privacy_level,
            requires_air_gap=(e.privacy_level >= 1.0),
            ocean_profile=_OCEAN.get(kid, dict(_OCEAN_DEFAULT)),
        )
    return roster


def get_capability(knight_id: str) -> KnightCapability:
    roster = load_roster()
    if knight_id not in roster:
        raise KeyError(f"unknown knight: {knight_id}")
    return roster[knight_id]


class CrystallineSleepManager:
    """Serialize idle knights to FirnFlow L2; wake sub-second on demand (v700 NLM)."""

    def __init__(self, firnflow=None):
        self._awake: set[str] = set()
        self._ff = firnflow
        if self._ff is None:
            try:
                from control_plane.infra.firnflow import FirnFlow
                self._ff = FirnFlow()
            except Exception:
                self._ff = None

    def _key(self, knight_id: str) -> str:
        return f"knight_sleep::{knight_id}"

    def sleep(self, knight_id: str, working_state: Optional[dict] = None) -> None:
        """Serialize knight state to L2 and mark dormant."""
        if self._ff is not None:
            self._ff.anchor(self._key(knight_id),
                            json.dumps(working_state or {}), "L2")
        self._awake.discard(knight_id)

    def wake(self, knight_id: str) -> dict:
        """Restore knight state from L2 and mark awake. Returns working state."""
        state: dict = {}
        if self._ff is not None:
            for h in self._ff.retrieve(self._key(knight_id), "L2"):
                if h.key == self._key(knight_id):
                    try:
                        state = json.loads(h.value)
                    except json.JSONDecodeError:
                        state = {}
                    break
        self._awake.add(knight_id)
        return state

    def is_awake(self, knight_id: str) -> bool:
        return knight_id in self._awake


# ── Self-test ────────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("KnightAgent self-test")

    roster = load_roster()
    # V5.4 schema
    check("V5.4 roster non-empty", len(roster) >= 10)
    boris = roster.get("sir_boris")
    check("V5.4 KnightCapability has fields",
          boris is not None and boris.primary_model and boris.skillgraph_tier)

    # V5.5 OCEAN PersRubrics
    check("V5.5 sir_boris OCEAN profile has 5 traits",
          set(boris.ocean_profile.keys()) == {"O", "C", "E", "A", "N"})

    # V5.6 every knight has a SkillGraph tier
    check("V5.6 all knights have S1-S5 tier",
          all(k.skillgraph_tier in ("S1", "S2", "S3", "S4", "S5") for k in roster.values()))

    # V5.6b (P1-T03) unified roster: every FOUNDRY_COUNCIL knight has an EXPLICIT
    # tier entry — no silent default. Catches roster/tier drift like sir_sonus.
    from .soul_router import FOUNDRY_COUNCIL
    missing_tier = [e.knight_id for e in FOUNDRY_COUNCIL if e.knight_id not in _SKILLGRAPH_TIER]
    check(f"V5.6b council⊆tier (missing={missing_tier})", not missing_tier)

    # V5.9 air-gap enforcement
    ghost = roster.get("sir_ghost")
    check("V5.9 sir_ghost requires_air_gap", ghost is not None and ghost.requires_air_gap)
    check("V5.9 non-private knight no air-gap", not roster["sir_boris"].requires_air_gap)

    # Crystalline Sleep round-trip
    csm = CrystallineSleepManager()
    csm.wake("sir_helio")
    check("CrystallineSleep wake marks awake", csm.is_awake("sir_helio"))
    csm.sleep("sir_helio", {"last_task": "1M context map", "ctx_tokens": 4200})
    check("CrystallineSleep sleep marks dormant", not csm.is_awake("sir_helio"))
    restored = csm.wake("sir_helio")
    check("CrystallineSleep restores state", restored.get("ctx_tokens") == 4200)

    # invalid knight
    try:
        get_capability("sir_nonexistent")
        check("invalid knight raises", False)
    except KeyError:
        check("invalid knight raises KeyError", True)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — knight_agent")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    roster = load_roster()
    if "--roster" in sys.argv:
        print("CAMELOT-OS Knight Roster (typed capabilities):")
        for kid, cap in sorted(roster.items(), key=lambda kv: kv[1].skillgraph_tier):
            ag = " [AIR-GAP]" if cap.requires_air_gap else ""
            print(f"  {cap.skillgraph_tier} {kid:14s} {cap.primary_model:24s} {cap.function}{ag}")
    else:
        print(f"Loaded {len(roster)} knight capabilities. Use --roster to list, --test to verify.")
