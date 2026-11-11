# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
control_plane.sase.briefing — SASE 3.0 BriefingScript & MentorScript
===================================================================
Enforces Axiom 2 of the Tri-Core Omni-Forge:
"Reject vibe coding. All tasks must originate from a frozen BriefingScript
and be validated against the durable MentorScript. Most agent failures
are context failures."
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LERNDATEI_PATH = REPO_ROOT / ".hive" / "skills" / "lukas_lerndatei.md"
LEARNINGS_PATH = REPO_ROOT / "03_VAULT" / "Knights" / "learnings.md"


@dataclass
class BriefingScript:
    """
    Frozen execution contract. No kinetic code modification may proceed
    without an approved and frozen BriefingScript.
    """
    briefing_id: str
    goal: str
    definition_of_done: List[str]
    acceptance_test_commands: List[str]
    allowed_vfs_roots: List[str] = field(default_factory=lambda: ["vfs://worldtree/"])
    max_diff_lines: int = 10
    z3_invariants: List[str] = field(default_factory=list)
    freeze_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def freeze(self) -> str:
        """Compute SHA-256 fingerprint of the core requirements to freeze the scope."""
        payload = {
            "goal": self.goal,
            "definition_of_done": sorted(self.definition_of_done),
            "acceptance_test_commands": self.acceptance_test_commands,
            "allowed_vfs_roots": sorted(self.allowed_vfs_roots),
            "max_diff_lines": self.max_diff_lines,
            "z3_invariants": sorted(self.z3_invariants),
        }
        serialized = json.dumps(payload, sort_keys=True)
        self.freeze_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self.freeze_hash

    def verify_integrity(self, current_hash: str) -> bool:
        """Assert that requirements have not suffered context drift."""
        return self.freeze_hash == current_hash if self.freeze_hash else False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MentorScript:
    """
    Durable persistent memory interface for error corrections and learned axioms.
    Reads and appends to persistent markdown ledgers (Lerndatei / learnings.md).
    """

    @classmethod
    def load_axioms(cls) -> List[str]:
        """Load durable rules and corrections from persistent ledgers."""
        axioms = []
        for path in [LERNDATEI_PATH, LEARNINGS_PATH]:
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        line = line.strip()
                        if line.startswith("- [AXIOM]") or line.startswith("- [RULE]") or line.startswith("- [FIX]"):
                            axioms.append(line)
                except Exception:
                    pass
        return axioms

    @classmethod
    def record_reflexion(cls, task_id: str, error_msg: str, root_cause: str, remediation: str) -> str:
        """
        Record a timestamped 🧠Δ Reflexion log into Lerndatei to prevent regression.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        entry = (
            f"\n### [🧠Δ] Reflexion: {task_id} — {now}\n"
            f"- **Error:** `{error_msg}`\n"
            f"- **Root Cause:** {root_cause}\n"
            f"- **Remediation Invariant:** {remediation}\n"
        )

        # Write to .hive/skills/lukas_lerndatei.md
        LERNDATEI_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LERNDATEI_PATH, "a", encoding="utf-8") as f:
            f.write(entry)

        # Also mirror into 03_VAULT/Knights/learnings.md if it exists
        if LEARNINGS_PATH.parent.exists():
            with open(LEARNINGS_PATH, "a", encoding="utf-8") as f:
                f.write(entry)

        return entry
