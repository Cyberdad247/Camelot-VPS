# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Lord Archivist — Agentic Evolver (GEP Scan Daemon)
====================================================
P1-A. Called by SovereignHarness loop 6 every 3600s.

Responsibilities:
  - GEP scan: detect repeated [FAIL] patterns in harness.log → suggest new skills
  - Skill version check: compare .hive/skills/*.md headers vs current v400.1.0
  - XP accounting: Grade A/B/F knights from task outcomes; write to learnings.md
  - Ledger [Omega_EVOLVE] tag mining: extract evolution events for persona refinement
  - Skill gap detection: flag cartridges that have no matching skill bible

Output: appends structured entries to 03_VAULT/Knights/learnings.md
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CAMELOT_HOME  = Path(__file__).parent.parent
SKILLS_DIR    = CAMELOT_HOME / ".hive" / "skills"
KNIGHTS_DIR   = CAMELOT_HOME / "03_VAULT" / "Knights"
LEARNINGS_FILE = KNIGHTS_DIR / "learnings.md"
HARNESS_LOG   = CAMELOT_HOME / "logs" / "harness.log"
LEDGER_FILE   = CAMELOT_HOME / "PROVENANCE_LEDGER.md"
CARTRIDGES_DIR = CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "cartridges"

CURRENT_VERSION = "v400.1.0"

KNOWN_CARTRIDGES = [
    "rust-kinetic", "security", "swarm-colony",
    "python-api", "nextjs", "reasoning", "voice-media",
]

XP_GRADE_A = 100
XP_GRADE_B = 50
XP_GRADE_F = -20


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SkillAuditResult:
    name: str
    path: str
    version_ok: bool
    found_version: str
    issues: list[str] = field(default_factory=list)


@dataclass
class FailPattern:
    knight: str
    error_type: str
    count: int
    sample: str
    suggested_action: str


@dataclass
class XPEntry:
    knight: str
    grade: str    # A / B / F
    xp_delta: int
    reason: str
    ts: str


@dataclass
class ArchivistReport:
    timestamp: str
    skill_audits: list[SkillAuditResult]
    fail_patterns: list[FailPattern]
    xp_entries: list[XPEntry]
    skill_gaps: list[str]
    evolve_events: list[str]
    duration_ms: float


# ---------------------------------------------------------------------------
# GEP Scan functions
# ---------------------------------------------------------------------------

def _scan_skill_versions() -> list[SkillAuditResult]:
    results: list[SkillAuditResult] = []
    if not SKILLS_DIR.exists():
        return results
    for skill_file in SKILLS_DIR.glob("*.md"):
        if skill_file.name == "brain_directory.md":
            continue
        try:
            first_lines = skill_file.read_text(encoding="utf-8", errors="replace")[:500]
        except Exception:
            continue
        version_match = re.search(r"v(\d+\.\d+\.\d+)", first_lines)
        found_ver = f"v{version_match.group(1)}" if version_match else "UNKNOWN"
        ok = found_ver == CURRENT_VERSION
        issues = [] if ok else [f"version mismatch: found={found_ver} expected={CURRENT_VERSION}"]
        results.append(SkillAuditResult(
            name=skill_file.stem,
            path=str(skill_file),
            version_ok=ok,
            found_version=found_ver,
            issues=issues,
        ))
    return results


def _detect_fail_patterns(window_lines: int = 500) -> list[FailPattern]:
    if not HARNESS_LOG.exists():
        return []
    try:
        lines = HARNESS_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-window_lines:]
    except Exception:
        return []

    fail_re = re.compile(r"\[FAIL\]\s+(\S+)\s+(\w+Error|\w+Exception|ERROR):\s*(.*)", re.IGNORECASE)
    counts: dict[tuple[str, str], list[str]] = defaultdict(list)

    for line in lines:
        m = fail_re.search(line)
        if m:
            task_id, err_type, msg = m.group(1), m.group(2), m.group(3)
            counts[(task_id[:20], err_type)].append(msg[:80])

    # Group by error type across all task IDs
    by_type: dict[str, list[str]] = defaultdict(list)
    for (_, etype), msgs in counts.items():
        by_type[etype].extend(msgs)

    patterns: list[FailPattern] = []
    for err_type, msgs in by_type.items():
        if len(msgs) >= 2:  # recurring = pattern
            action = _suggest_action(err_type)
            patterns.append(FailPattern(
                knight="harness",
                error_type=err_type,
                count=len(msgs),
                sample=msgs[0],
                suggested_action=action,
            ))
    return patterns


def _suggest_action(error_type: str) -> str:
    mapping = {
        "ImportError": "Check knight module path — may need skill bible reload",
        "ModuleNotFoundError": "Verify .venv_camelot activation and uv install",
        "TimeoutError": "Probe timeout — service may be dark; escalate to SIR_LINK",
        "ConnectionRefusedError": "Port closed — check BOOT_PROBES; watchdog should restart",
        "JSONDecodeError": "Malformed harness_queue.jsonl entry — validate with SENTINEL",
        "PermissionError": "File lock or missing RBAC — check access_matrix.json",
        "AttributeError": "API shape mismatch — check cartridge version; may need skill update",
    }
    for key, action in mapping.items():
        if key.lower() in error_type.lower():
            return action
    return f"Unknown error pattern '{error_type}' — route to SIR_DEBUG for PIV self-healing"


def _detect_skill_gaps() -> list[str]:
    gaps: list[str] = []
    if not SKILLS_DIR.exists():
        return KNOWN_CARTRIDGES[:]
    existing = {f.stem for f in SKILLS_DIR.glob("*.md")}
    for cartridge in KNOWN_CARTRIDGES:
        if cartridge not in existing:
            gaps.append(cartridge)
    return gaps


def _mine_evolve_events(window_lines: int = 200) -> list[str]:
    events: list[str] = []
    if not LEDGER_FILE.exists():
        return events
    try:
        lines = LEDGER_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-window_lines:]
    except Exception:
        return events
    for line in lines:
        if "[Omega_EVOLVE]" in line or "Omega_EVOLVE" in line:
            events.append(line.strip()[:120])
    return events


def _score_knight_xp() -> list[XPEntry]:
    """Lightweight XP scoring from harness.log DONE/FAIL ratio per knight."""
    if not HARNESS_LOG.exists():
        return []
    try:
        lines = HARNESS_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-1000:]
    except Exception:
        return []

    _done_re = re.compile(r"\[DONE\]\s+\S+\s+.*knight['\"]?\s*[:\=]\s*['\"]?(\w+)", re.IGNORECASE)
    re.compile(r"\[FAIL\]\s+(\S+)\s+")
    dispatch_re = re.compile(r"\[DISPATCH\]\s+(\w+)\s+")

    knight_done: dict[str, int] = defaultdict(int)
    knight_fail: dict[str, int] = defaultdict(int)
    for line in lines:
        dm = dispatch_re.search(line)
        if dm and "[DONE]" in line:
            knight_done[dm.group(1)] += 1
        elif dm and "[FAIL]" in line:
            knight_fail[dm.group(1)] += 1

    entries: list[XPEntry] = []
    ts = datetime.now(timezone.utc).isoformat()
    for knight in set(list(knight_done.keys()) + list(knight_fail.keys())):
        done = knight_done[knight]
        fail = knight_fail[knight]
        total = done + fail
        if total == 0:
            continue
        ratio = done / total
        if ratio >= 0.95:
            grade, xp = "A", XP_GRADE_A
        elif ratio >= 0.7:
            grade, xp = "B", XP_GRADE_B
        else:
            grade, xp = "F", XP_GRADE_F
        entries.append(XPEntry(
            knight=knight, grade=grade, xp_delta=xp,
            reason=f"done={done} fail={fail} ratio={ratio:.0%}",
            ts=ts,
        ))
    return entries


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _append_learnings(report: ArchivistReport) -> None:
    KNIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"\n## Archivist Scan — {report.timestamp} ({report.duration_ms:.0f}ms)\n",
    ]

    # Skill audit
    stale = [s for s in report.skill_audits if not s.version_ok]
    if stale:
        lines.append("### Stale Skills")
        for s in stale:
            lines.append(f"- `{s.name}`: {s.found_version} (expected {CURRENT_VERSION}) — {'; '.join(s.issues)}")
    else:
        lines.append(f"### Skills: {len(report.skill_audits)}/{len(report.skill_audits)} @ {CURRENT_VERSION} OK")

    # Skill gaps
    if report.skill_gaps:
        lines.append("\n### Skill Gaps (FRAGMENTED)")
        for gap in report.skill_gaps:
            lines.append(f"- Missing: `{gap}` — create `.hive/skills/{gap}.md`")

    # Fail patterns
    if report.fail_patterns:
        lines.append("\n### Recurring Failures")
        for p in report.fail_patterns:
            lines.append(f"- `{p.error_type}` x{p.count}: {p.sample[:60]} → ACTION: {p.suggested_action}")

    # XP entries
    if report.xp_entries:
        lines.append("\n### XP Ledger")
        lines.append("| Knight | Grade | XP | Reason |")
        lines.append("|---|---|---|---|")
        for e in report.xp_entries:
            lines.append(f"| {e.knight} | {e.grade} | {e.xp_delta:+d} | {e.reason} |")

    # Evolve events
    if report.evolve_events:
        lines.append("\n### [Omega_EVOLVE] Events")
        for ev in report.evolve_events[-5:]:
            lines.append(f"- {ev}")

    content = "\n".join(lines) + "\n"
    try:
        with open(LEARNINGS_FILE, "a", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"[LORD_ARCHIVIST] learnings write failed: {e}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_gep_scan() -> ArchivistReport:
    """Execute one full GEP scan cycle. Called by harness _archivist_loop."""
    t0 = time.perf_counter()
    ts = datetime.now(timezone.utc).isoformat()

    skill_audits  = _scan_skill_versions()
    fail_patterns = _detect_fail_patterns()
    xp_entries    = _score_knight_xp()
    skill_gaps    = _detect_skill_gaps()
    evolve_events = _mine_evolve_events()

    report = ArchivistReport(
        timestamp=ts,
        skill_audits=skill_audits,
        fail_patterns=fail_patterns,
        xp_entries=xp_entries,
        skill_gaps=skill_gaps,
        evolve_events=evolve_events,
        duration_ms=(time.perf_counter() - t0) * 1000,
    )
    _append_learnings(report)
    return report


if __name__ == "__main__":
    r = run_gep_scan()
    print(f"[LORD_ARCHIVIST] Scan complete in {r.duration_ms:.0f}ms — "
          f"skills={len(r.skill_audits)} gaps={len(r.skill_gaps)} "
          f"patterns={len(r.fail_patterns)} xp_entries={len(r.xp_entries)}")
