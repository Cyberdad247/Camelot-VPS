# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Hermes-Jarvis Voice Ingress — voice → kinetic intent (v9000.14, P5-T05).
========================================================================
Turns a voice command into a Kinetic Execution Loop intent. Audio capture and
ASR are pluggable: this module owns the *ingress contract* — a transcript is
normalized (wake-word stripped, filler removed), classified as a command, and
dispatched into the kinetic loop. A live ASR (Whisper/LiveKit/`vox_anima`) can
feed `ingest_transcript`; tests use deterministic transcripts.

Run as module:
    python -m control_plane.voice_ingress --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import re
import sys
from dataclasses import dataclass
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_WAKE_WORDS = re.compile(
    r"^\s*(hey\s+|ok\s+|okay\s+)?(jarvis|hermes|camelot|anya|merlin)[,:\s]+", re.I)
_FILLERS = re.compile(r"\b(please|could you|can you|i want to|i need to|kindly)\b", re.I)


@dataclass
class VoiceIntent:
    raw_transcript: str
    intent: str
    wake_word: Optional[str]
    is_command: bool


def parse_transcript(transcript: str) -> VoiceIntent:
    """Normalize a transcript into a kinetic intent (wake-word + fillers stripped)."""
    raw = transcript or ""
    m = _WAKE_WORDS.match(raw)
    wake = None
    body = raw
    if m:
        wake = m.group(2).lower()
        body = raw[m.end():]
    body = _FILLERS.sub("", body)
    body = re.sub(r"\s{2,}", " ", body).strip().rstrip(".!?").strip()
    # A command must have an actionable verb; otherwise it's chatter.
    is_command = bool(re.search(
        r"\b(build|create|make|deploy|run|fix|audit|status|sync|research|"
        r"scaffold|generate|refactor|launch|show)\b", body, re.I))
    return VoiceIntent(raw_transcript=raw, intent=body, wake_word=wake, is_command=is_command)


class VoiceIngress:
    """Voice → kinetic loop bridge."""

    def ingest_transcript(self, transcript: str, *, auto_approve: bool = True,
                          dispatch: bool = True) -> dict[str, Any]:
        """Parse a transcript and (optionally) dispatch it into the kinetic loop.

        Returns {voice_intent, dispatched, result}. Non-command chatter is parsed
        but never dispatched.
        """
        vi = parse_transcript(transcript)
        out: dict[str, Any] = {"voice_intent": vi, "dispatched": False, "result": None}
        if not vi.is_command:
            return out
        if dispatch:
            from .kinetic_loop import run_sync
            out["result"] = run_sync(vi.intent, auto_approve=auto_approve)
            out["dispatched"] = True
        return out


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("VoiceIngress self-test (P5-T05)")
    vox = VoiceIngress()

    # Wake-word + command -> clean kinetic intent.
    vi = parse_transcript("Hey Jarvis, please build a status dashboard.")
    check("wake word detected", vi.wake_word == "jarvis")
    check("filler + wake stripped", vi.intent == "build a status dashboard")
    check("classified as command", vi.is_command)

    # Dispatch into the kinetic loop.
    res = vox.ingest_transcript("Camelot, build a small status dashboard", auto_approve=True)
    check("command dispatched to kinetic loop", res["dispatched"])
    check("kinetic result complete", getattr(res["result"], "complete", False))

    # Chatter (no verb) -> parsed but not dispatched.
    chatter = vox.ingest_transcript("Hermes, what a lovely day it is")
    check("chatter not classified as command", not chatter["voice_intent"].is_command)
    check("chatter not dispatched", not chatter["dispatched"])

    # No wake word still parses the body.
    nw = parse_transcript("deploy the edge node")
    check("no-wake-word command parses", nw.is_command and nw.wake_word is None)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — voice_ingress")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    import json
    t = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or "Hey Jarvis, build a dashboard"
    vi = parse_transcript(t)
    print(json.dumps({"intent": vi.intent, "wake": vi.wake_word, "command": vi.is_command}))
