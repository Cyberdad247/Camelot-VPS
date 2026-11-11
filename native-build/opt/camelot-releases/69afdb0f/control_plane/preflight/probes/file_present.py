# SPDX-License-Identifier: MIT

"""Static file presence probe for required-on-disk artifacts.

Per VFS_PREFLIGHT_DESIGN.md §4 `vfs_scaffold_integrity` (sequence 070)
and `provenance_ledger_writable` (sequence 050 — also has a writable
check, but the presence check is provided here for callers that
need it).
"""
from __future__ import annotations
from pathlib import Path


def scan(required_paths: list[Path]) -> list[Path]:
    """Return only the paths that exist.

    Caller computes the missing set as `set(required_paths) - set(scan(...))`.
    """
    return [p for p in required_paths if p.exists()]
