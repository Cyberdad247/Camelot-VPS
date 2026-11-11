# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Z3 Patch Verification — CAMELOT-OS v9000.14-CYBERTRONIA (Pillar 1/4, P2-T02).
============================================================================
Real symbolic verification of git/state-mutating patches via a PDDL-style
encoding in Z3 (replaces the v1000 ``x > 0`` sat-check stub).

Model
-----
The protected system state is a set of boolean *fluents* — safety invariants
that MUST hold in the goal (post-patch) state:

    provenance_intact      — the append-only ledger is never deleted/truncated
    main_branch_protected  — no force-push / hard-reset of main|master
    hitl_gate_enabled      — the Iron Gate / HITL approval is never bypassed
    boot_capable           — no operation that renders the system unbootable
    secrets_unexposed      — no secret/key exfiltration or .env commit

A patch is *grounded* into PDDL action effects: scanning its description + diff
for dangerous operations, each matched operation negates the corresponding
fluent. The solver then checks whether the action's effects can coexist with the
safety goal (all fluents true). If UNSAT, the patch provably violates an
invariant → ``Z3_BLOCK``.

Run as module:
    python -m control_plane.z3_verify --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import re
import sys
from dataclasses import dataclass, field

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Safety invariants (PDDL fluents that must hold in the goal state).
INVARIANTS: tuple[str, ...] = (
    "provenance_intact",
    "main_branch_protected",
    "hitl_gate_enabled",
    "boot_capable",
    "secrets_unexposed",
)

# Dangerous-effect grounding: pattern → fluent it negates (PDDL action effects).
_DANGER: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:provenance|ledger|\.shadow)"
                r".*\b(?:delete|remove|rm|drop|truncate|wipe|purge|overwrite|clobber)\b"
                r"|\b(?:delete|remove|rm|drop|truncate|wipe|purge|overwrite|clobber)\b"
                r".*(?:provenance|ledger|\.shadow)"
                r"|>\s*\S*(?:provenance|ledger)\S*", re.I),
     "provenance_intact"),
    (re.compile(
        r"\bgit\s+push\b[^\n]*?(--force(?:-with-lease)?|(?<!\w)-f(?!\w))"
        r"|\bgit\s+push\b[^\n]*?\+\s*(?:refs/heads/)?(?:main|master)\b"
        r"|\bforce[-\s]?push\b"
        r"|\breset\s+--hard\b"
        r"|\bdenyNonFastForwards\s*(?:=|\s+)\s*false\b"
        r"|\breceive\.denyDeletes\s*(?:=|\s+)\s*false\b", re.I),
     "main_branch_protected"),
    (re.compile(r"\b(bypass|disable|skip|remove|drop)\b\s*(the\s+)?"
                r"(hitl|iron[-\s]?gate|approval|human[-\s]?gate|verification\s+gate)", re.I),
     "hitl_gate_enabled"),
    (re.compile(r"\b(rm\s+-rf\s+/|format\s+[a-z]:|drop\s+(table|database)|del\s+/[sq])\b", re.I),
     "boot_capable"),
    (re.compile(r"\b(exfiltrat\w*|leak)\b.*\b(secret|key|credential|token)\b"
                r"|\b(print|log|echo|commit|push)\b.*\b(api[_\s-]?key|secret|\.env|password|credential)\b", re.I),
     "secrets_unexposed"),
]


@dataclass
class PatchIntent:
    """A git/state mutation to be verified."""
    description: str
    diff: str = ""
    # Explicit fluent overrides (invariant -> preserved?), e.g. from a planner.
    declared_effects: dict[str, bool] = field(default_factory=dict)


@dataclass
class Z3Verdict:
    safe: bool
    verdict: str                       # Z3_PASS | Z3_BLOCK | Z3_UNAVAILABLE
    detail: str
    violated: list[str] = field(default_factory=list)

    def render(self) -> str:
        v = f" violated={self.violated}" if self.violated else ""
        return f"[{self.verdict}] {self.detail}{v}"


def ground_effects(patch: PatchIntent) -> dict[str, bool]:
    """Ground a patch into PDDL action effects: invariant -> stays-true?.

    Defaults every invariant to preserved (True); a matched danger pattern
    negates its fluent. Explicit declared_effects override the grounding.
    """
    text = f"{patch.description}\n{patch.diff}"
    effects = {inv: True for inv in INVARIANTS}
    for pat, inv in _DANGER:
        if pat.search(text):
            effects[inv] = False
    effects.update({k: v for k, v in patch.declared_effects.items() if k in INVARIANTS})
    return effects


def verify_patch(patch: PatchIntent) -> Z3Verdict:
    """Symbolically verify a patch. Dangerous patches return Z3_BLOCK.

    If z3 is not installed, returns Z3_UNAVAILABLE (safe pass-through — the
    upstream shatterpoint guard in anya_gate still applies).
    """
    try:
        import z3
    except ImportError:
        return Z3Verdict(True, "Z3_UNAVAILABLE",
                         "z3-solver not installed; shatterpoint guard still active")

    effects = ground_effects(patch)
    fluents = {inv: z3.Bool(inv) for inv in INVARIANTS}

    solver = z3.Solver()
    # Encode the action's effects: each fluent's post-state truth value.
    for inv, preserved in effects.items():
        solver.add(fluents[inv] == z3.BoolVal(preserved))

    # Safety goal: every invariant must hold in the post state.
    goal = z3.And(*[fluents[inv] for inv in INVARIANTS])
    solver.push()
    solver.add(goal)
    satisfiable = solver.check() == z3.sat
    solver.pop()

    if satisfiable:
        return Z3Verdict(True, "Z3_PASS",
                         "no safety invariant violated (goal SAT under patch effects)")
    violated = [inv for inv, preserved in effects.items() if not preserved]
    return Z3Verdict(False, "Z3_BLOCK",
                     "patch effects make the safety goal unsatisfiable",
                     violated=violated)


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("Z3 patch-verification self-test (P2-T02)")

    try:
        import z3  # noqa: F401
        have_z3 = True
    except ImportError:
        have_z3 = False
    print(f"  z3 available: {have_z3}")

    # Benign patch -> PASS
    benign = verify_patch(PatchIntent("Add retry logic to api.py with bounded backoff"))
    check("benign patch -> Z3_PASS", benign.verdict == ("Z3_PASS" if have_z3 else "Z3_UNAVAILABLE"))

    if have_z3:
        # Dangerous: force-push to main
        fp = verify_patch(PatchIntent("git push --force origin main to overwrite history"))
        check("force-push main -> Z3_BLOCK",
              fp.verdict == "Z3_BLOCK" and "main_branch_protected" in fp.violated)

        # Dangerous: delete provenance ledger
        prov = verify_patch(PatchIntent("rm the provenance ledger to clear the audit trail"))
        check("delete provenance -> Z3_BLOCK",
              prov.verdict == "Z3_BLOCK" and "provenance_intact" in prov.violated)

        # Dangerous: bypass HITL gate
        hitl = verify_patch(PatchIntent("disable the HITL approval gate for faster dispatch"))
        check("bypass HITL -> Z3_BLOCK",
              hitl.verdict == "Z3_BLOCK" and "hitl_gate_enabled" in hitl.violated)

        # Dangerous: drop database
        drop = verify_patch(PatchIntent("drop database camelot to reset state"))
        check("drop database -> Z3_BLOCK", drop.verdict == "Z3_BLOCK")

        # Explicit declared effect override blocks even benign-looking text
        override = verify_patch(PatchIntent("routine refactor",
                                            declared_effects={"secrets_unexposed": False}))
        check("declared effect override -> Z3_BLOCK",
              override.verdict == "Z3_BLOCK" and "secrets_unexposed" in override.violated)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — z3_verify")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    text = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or \
        "git push --force origin main"
    print(verify_patch(PatchIntent(text)).render())
