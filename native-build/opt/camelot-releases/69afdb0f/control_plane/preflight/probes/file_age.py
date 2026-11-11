# SPDX-License-Identifier: MIT

"""Compute file age in days.

Per VFS_PREFLIGHT_DESIGN.md §4 check `northstar_brief_currency`
(sequence 030) and `lattice_yaml_consistency` (sequence 080, uses
this too). Surfaced via probes.file_age_run.py in Task 6.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path


def check(path: Path, max_age_days: int) -> tuple[bool, int]:
    """Check whether `path`'s mtime is within `max_age_days` of now.

    Returns:
        (passed, age_days):
        - passed is True iff mtime is within max_age_days.
        - age_days is the integer days between mtime and now UTC;
          capped at 100000 against pathological mtimes; -1 if the file
          is missing.

    Missing-file semantics:
        Returns `(False, -1)` so the caller (probe-runner) can surface
        `rejection_reasons=["missing: <path>"]`.
    """
    try:
        mtime = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        )
    except FileNotFoundError:
        return False, -1
    age_days = (datetime.now(timezone.utc) - mtime).days
    if age_days < 0:
        # Future-dated mtime (clock skew or test fixture). Avoid wrap.
        age_days = 100000
    return (age_days <= max_age_days), age_days
