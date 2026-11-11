# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
[S4-01] Intent Router — dynamic knight hot-swap via semantic intent classification.

Replaces pure weight-based routing in switchboard.py with intent-aware dispatch:
  1. classify_intent(text) → IntentCategory  (keyword heuristic, <1ms, no LLM)
  2. route_by_intent(text, board) → Terminal  (probes live terminals in priority order)

Maps each intent category to an ordered list of preferred terminal IDs. The first
live terminal in the list wins; falls back to switchboard.best_for() if all preferred
terminals are dark.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from control_plane.taxonomy import INTENT_KEYWORDS, INTENT_TERMINAL_MAP, IntentCategory

try:
    from importlib import import_module
    hydration = import_module("01_KERNEL.memory.hydration_manager")
    HydrationManager = hydration.HydrationManager
except ImportError:
    HydrationManager = None

if TYPE_CHECKING:
    from control_plane.switchboard import Switchboard, Terminal


def classify_intent(text: str) -> tuple[IntentCategory, float]:
    """Classify intent from text using keyword heuristic.

    Returns (IntentCategory, confidence) where confidence is 0.0–1.0.
    Scoring: 0.9 for exact phrase match, 0.7 for word boundary match,
    0.5 for substring match. Ties broken by category priority order.
    """
    lower = text.lower()
    scores: dict[IntentCategory, float] = {}

    for category, keywords in INTENT_KEYWORDS.items():
        best = 0.0
        for kw in keywords:
            if kw in lower:
                if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                    # Multi-word phrases get a specificity bonus to win ties
                    score = 0.9 + 0.02 * (len(kw.split()) - 1)
                else:
                    score = 0.5
                if score > best:
                    best = score
        if best > 0:
            scores[category] = best

    if not scores:
        return IntentCategory.GENERAL, 0.3

    best_cat = max(scores, key=lambda c: scores[c])
    return best_cat, scores[best_cat]


async def route_by_intent(
    text: str,
    board: "Switchboard",
) -> tuple[Optional["Terminal"], IntentCategory, float]:
    """Route a user utterance to the best live terminal.

    Returns (terminal, category, confidence).
    Terminal is None only if no live terminals exist at all.
    """
    category, confidence = classify_intent(text)
    preferred_ids = INTENT_TERMINAL_MAP.get(category, INTENT_TERMINAL_MAP[IntentCategory.GENERAL])

    # Try preferred terminals in order
    selected_terminal = None
    for tid in preferred_ids:
        t = await board.probe_one(tid)
        if t and t.status in ("live", "assumed_live"):
            selected_terminal = t
            break

    # Fallback: capability-based best_for
    if not selected_terminal:
        capability_map = {
            IntentCategory.FORGE:    ["forge", "orchestration"],
            IntentCategory.CODE:     ["code_gen", "velocity"],
            IntentCategory.RESEARCH: ["research", "context"],
            IntentCategory.MEMORY:   ["memory", "recall"],
            IntentCategory.OPS:      ["ops", "monitoring"],
            IntentCategory.SECURITY:     ["security", "audit"],
            IntentCategory.VOICE:        ["bridge", "audio"],
            IntentCategory.NATIVE_AUDIO: ["bridge", "context"],
            IntentCategory.GENERAL:      ["orchestration", "cognitive"],
        }
        selected_terminal = await board.best_for(capability_map.get(category, ["orchestration"]))
        confidence *= 0.5  # reduced confidence on fallback

    # LATTICE_RADIANT Sync: Store routed intent context
    if selected_terminal and HydrationManager:
        mgr = HydrationManager(knight_id=selected_terminal.id)
        mgr.store_tissue(intent=f"routed_intent_{category.value}", content=text, complexity=5, tier="L1")

    return selected_terminal, category, confidence


def explain_routing(text: str) -> dict:
    """Debug helper — show classification result without probing."""
    category, confidence = classify_intent(text)
    return {
        "text": text[:80],
        "category": category.value,
        "confidence": round(confidence, 2),
        "preferred_terminals": INTENT_TERMINAL_MAP.get(category, []),
    }
