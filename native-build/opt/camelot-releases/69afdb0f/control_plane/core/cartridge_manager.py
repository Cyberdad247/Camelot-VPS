# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Cartridge Manager — CAMELOT-OS Scabbard Protocol
=================================================
EXCALIBUR_A_QNF Pillar 4. Activates the hot-swappable cognitive cartridge
system (v700 NLM). Monolithic system prompts are replaced with context
bundles that can be swapped mid-session without a full context reload.

The Scabbard Protocol: on switch, the active cartridge's working state is
saved to FirnFlow L2, and the target cartridge's state is loaded back. This
preserves per-domain context across swaps.

Cartridges (v700 NLM domains):
    ANT     — Vortex Datalink: deep research, web foraging       (Lady Apis)
    BEAVER  — Tectonic Plate: infrastructure, builds, DevOps      (Sir Forge)
    SPIDER  — Silk Weaver: integrations, APIs, MCP                (Sir Link)
    OCTOPUS — Lazarus Pit: debugging, PIV self-healing            (Sir Debug)
    DEFAULT — general-purpose baseline

Public API:
    CartridgeManager.switch(name)      -> CartridgeState
    CartridgeManager.active            -> current cartridge name
    CartridgeManager.describe(name)    -> dict

Run as module:
    python -m control_plane.cartridge_manager --test
    python -m control_plane.cartridge_manager switch ANT
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

CartridgeName = Literal["ANT", "BEAVER", "SPIDER", "EAGLE", "OCTOPUS", "BIO_SWARM", "INVISIONED_AGENCY", "DEFAULT"]

CARTRIDGES: dict[str, dict[str, Any]] = {
    "ANT": {
        "title": "Vortex Datalink",
        "domain": "research / web foraging",
        "lead_knight": "lady_apis",
        "skills": ["bashr-loop", "context-forage", "notebook-sync"],
        "preferred_models": ["gemini-3.1-pro-preview"],
    },
    "BEAVER": {
        "title": "Tectonic Plate",
        "domain": "infrastructure / builds / devops",
        "lead_knight": "sir_forge",
        "skills": ["rust-kinetic", "binary-build", "docker", "ci"],
        "preferred_models": ["gpt-5.4", "gemini-3-pro-preview"],
    },
    "SPIDER": {
        "title": "Silk Weaver",
        "domain": "integrations / apis / mcp",
        "lead_knight": "sir_link",
        "skills": ["mcp", "a2a-bridge", "api-glue"],
        "preferred_models": ["gemini-3-flash-preview"],
    },
    "EAGLE": {
        "title": "Sky Watcher",
        "domain": "high-altitude context audit / speculative sampling / aerial reconnaissance",
        "lead_knight": "lady_apis",
        "skills": ["eagle-sampling", "aerial-audit", "macro-context-foraging"],
        "preferred_models": ["gemini-3.1-pro-preview", "gemini-3.6-flash"],
    },
    "OCTOPUS": {
        "title": "Lazarus Pit",
        "domain": "debugging / piv self-healing",
        "lead_knight": "sir_debug",
        "skills": ["piv-loop", "test-repair", "regression-hunt"],
        "preferred_models": ["gemini-3-flash-preview", "claude-haiku-4-5-20251001"],
    },
    "BIO_SWARM": {
        "title": "Bio-Kinetic Matrix",
        "domain": "biological isolation / cellular swarm / neural pulse",
        "lead_knight": "lady_apis",
        "co_lead": "sir_boris",
        "skills": ["cellular-isolation", "mitosis-scaling", "neural-pulse", "bio-swarm", "hive-orchestration"],
        "preferred_models": ["gemini-3.6-flash", "gpt-5.5-codex"],
    },
    "INVISIONED_AGENCY": {
        "title": "Invisioned Marketing Agency",
        "domain": "brand worldbuilding / autonomous AI systems / GEO search dominance / voice operations",
        "lead_knight": "merlin_omega",
        "co_lead": "anya_omega",
        "skills": ["brand-strategy", "geo-optimization", "kinetic-web", "voice-receptionist", "airgap-security", "living-orbit"],
        "preferred_models": ["gemini-3.1-pro-preview", "claude-haiku-4-5-20251001"],
        "cloudbrain_id": "e6374819-50ce-41cf-b6b3-99924ca6ab90",
    },
    "DEFAULT": {
        "title": "Round Table Baseline",
        "domain": "general",
        "lead_knight": "sir_boris",
        "skills": ["orchestration", "review"],
        "preferred_models": ["gemini-3-pro-preview"],
    },
}


@dataclass
class CartridgeState:
    name: str
    title: str
    lead_knight: str
    activated_at: float = field(default_factory=time.time)
    working_context: dict[str, Any] = field(default_factory=dict)


class CartridgeManager:
    """Scabbard Protocol hot-swap with FirnFlow L2 state persistence."""

    def __init__(self, firnflow=None):
        self._active: str = "DEFAULT"
        self._state: CartridgeState = self._fresh_state("DEFAULT")
        # Lazy FirnFlow — graceful if unavailable
        self._ff = firnflow
        if self._ff is None:
            try:
                from control_plane.infra.firnflow import FirnFlow
                self._ff = FirnFlow()
            except Exception:
                self._ff = None

    @staticmethod
    def _fresh_state(name: str) -> CartridgeState:
        spec = CARTRIDGES[name]
        return CartridgeState(name=name, title=spec["title"], lead_knight=spec["lead_knight"])

    @property
    def active(self) -> str:
        return self._active

    def describe(self, name: Optional[str] = None) -> dict[str, Any]:
        name = (name or self._active).upper()
        if name not in CARTRIDGES:
            raise KeyError(f"unknown cartridge: {name}")
        return {"name": name, **CARTRIDGES[name]}

    def _l2_key(self, name: str) -> str:
        return f"cartridge_state::{name}"

    def _save_state(self) -> None:
        if self._ff is not None:
            self._ff.anchor(self._l2_key(self._active),
                            json.dumps(asdict(self._state)), "L2")

    def _load_state(self, name: str) -> CartridgeState:
        if self._ff is not None:
            hits = self._ff.retrieve(self._l2_key(name), "L2")
            for h in hits:
                if h.key == self._l2_key(name):
                    try:
                        data = json.loads(h.value)
                        return CartridgeState(**data)
                    except (json.JSONDecodeError, TypeError):
                        break
        return self._fresh_state(name)

    def switch(self, name: str) -> CartridgeState:
        """Scabbard Protocol: persist current cartridge, load target."""
        name = name.upper()
        if name not in CARTRIDGES:
            raise KeyError(f"unknown cartridge: {name} (valid: {list(CARTRIDGES)})")
        # 1. Save current working state to L2
        self._save_state()
        # 2. Load target state (restored if previously saved, else fresh)
        self._state = self._load_state(name)
        self._active = name
        return self._state

    def update_context(self, **kwargs: Any) -> None:
        """Mutate the active cartridge's working context (persisted on next switch)."""
        self._state.working_context.update(kwargs)


# ── Self-test ────────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("CartridgeManager self-test")
    cm = CartridgeManager()

    # V5.1 ANT switch
    st = cm.switch("ANT")
    check("V5.1 switch ANT activates", cm.active == "ANT" and st.lead_knight == "lady_apis")

    # V5.3 all cartridges valid
    check("V5.3 all cartridges + DEFAULT defined",
          all(c in CARTRIDGES for c in ("ANT", "BEAVER", "SPIDER", "EAGLE", "OCTOPUS", "BIO_SWARM", "DEFAULT")))

    # V5.2 state persistence across swap
    cm.switch("ANT")
    cm.update_context(last_query="notebook sync", forage_depth=3)
    cm.switch("BEAVER")
    check("V5.2 switch to BEAVER changes lead", cm.active == "BEAVER" and cm._state.lead_knight == "sir_forge")
    restored = cm.switch("ANT")
    check("V5.2 ANT state restored after round-trip",
          restored.working_context.get("last_query") == "notebook sync")

    # describe
    d = cm.describe("OCTOPUS")
    check("describe OCTOPUS returns Lazarus Pit", d["title"] == "Lazarus Pit")

    # invalid cartridge
    try:
        cm.switch("NONEXISTENT")
        check("invalid cartridge raises", False)
    except KeyError:
        check("invalid cartridge raises KeyError", True)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — cartridge_manager")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    cm = CartridgeManager()
    if len(sys.argv) >= 3 and sys.argv[1] == "switch":
        st = cm.switch(sys.argv[2])
        print(f"Scabbard: {st.name} activated ({st.title}, lead={st.lead_knight})")
    else:
        print("CAMELOT-OS Cognitive Cartridges:")
        for name, spec in CARTRIDGES.items():
            print(f"  {name:8s} {spec['title']:20s} -> {spec['lead_knight']} [{spec['domain']}]")
