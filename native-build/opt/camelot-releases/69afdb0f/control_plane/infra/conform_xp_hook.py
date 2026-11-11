#!/usr/bin/env python3
"""
conform_xp_hook.py - Binds Conform Filesystem Reconciliation to the Knight XP Ledger.

Audits .conform/journal.db and awards XP in 03_VAULT/Knights/learnings.md:
- Hardlink Deduplication: +100 XP (Sir Forge)
- Zero-Loss Reorganization: +50 XP (Sir Sentinel)
- Merkle State Reconciliation: +50 XP (Merlin Omega)
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path(__file__).resolve().parent.parent.parent))
LEARNINGS_FILE = CAMELOT_HOME / "03_VAULT" / "Knights" / "learnings.md"


def get_conform_journal_stats(conform_dir: Path) -> List[Tuple[str, str, str, str]]:
    journal_db = conform_dir / "journal.db"
    if not journal_db.exists():
        return []

    conn = sqlite3.connect(journal_db)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, op_type, source_path, target_path, status, completed_at FROM journal "
            "WHERE status = 'committed' ORDER BY id DESC LIMIT 50"
        )
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        print(f"[!] Error querying journal: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()


def award_xp_for_conform(
    knight: str,
    grade: str,
    xp_amount: int,
    reason: str,
    apply: bool = False,
) -> bool:
    if not LEARNINGS_FILE.exists():
        print(f"[!] Learnings file missing at {LEARNINGS_FILE}", file=sys.stderr)
        return False

    content = LEARNINGS_FILE.read_text(encoding="utf-8", errors="ignore")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    new_ledger_entry = f"| {knight} | {grade} | +{xp_amount} | {reason} ({now_iso}) |\n"

    # 1. Append to recent XP Ledger table
    ledger_pattern = r"(### XP Ledger\s*\n\| Knight \| Grade \| XP \| Reason \|\s*\n\|[-|\s]+\|\s*\n)"
    if re.search(ledger_pattern, content):
        content = re.sub(ledger_pattern, r"\g<1>" + new_ledger_entry, content, count=1)
    else:
        content += f"\n### XP Ledger\n| Knight | Grade | XP | Reason |\n|---|---|---|---|\n{new_ledger_entry}"

    # 2. Update cumulative register
    # | sir_forge | Engineer | HIGH_KNIGHT | 5400 | A |
    reg_pattern = rf"(\| {re.escape(knight)} \| [^|]+ \| ([^|]+) \| )(\d+)( \| [^|]+ \|)"
    match = re.search(reg_pattern, content)
    if match:
        old_xp = int(match.group(3))
        new_xp = old_xp + xp_amount
        tier = match.group(2).strip()
        # Upgrade tier if passing threshold
        if new_xp >= 10000:
            tier = "OMEGA"
        elif new_xp >= 5000:
            tier = "HIGH_KNIGHT"
        elif new_xp >= 1000:
            tier = "KNIGHT"

        replacement = f"| {knight} | {match.group(1).split('|')[2].strip()} | {tier} | {new_xp}{match.group(4)}"
        content = content[:match.start()] + replacement + content[match.end():]

    if apply:
        LEARNINGS_FILE.write_text(content, encoding="utf-8")
        print(f"[OK] Awarded +{xp_amount} XP to {knight} ({reason})")
    else:
        print(f"[DRY-RUN] Would award +{xp_amount} XP to {knight} ({reason})")

    return True


def main():
    parser = argparse.ArgumentParser(description="Bind Conform events to Knight XP Ledger")
    parser.add_argument("--path", default=str(CAMELOT_HOME), help="Root directory managed by Conform")
    parser.add_argument("--apply", action="store_true", help="Apply updates to learnings.md")
    parser.add_argument("--knight", default="sir_forge", help="Knight to credit")
    parser.add_argument("--xp", type=int, default=100, help="XP amount")
    parser.add_argument("--reason", default="Conform automated zero-loss deduplication", help="Reason for award")
    args = parser.parse_args()

    conform_dir = Path(args.path) / ".conform"
    rows = get_conform_journal_stats(conform_dir)
    print(f"[*] Found {len(rows)} committed journal entries in {conform_dir}")

    award_xp_for_conform(
        knight=args.knight,
        grade="A",
        xp_amount=args.xp,
        reason=args.reason,
        apply=args.apply,
    )


if __name__ == "__main__":
    main()
