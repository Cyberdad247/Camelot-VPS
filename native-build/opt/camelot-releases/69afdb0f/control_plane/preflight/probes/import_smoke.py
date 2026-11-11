# SPDX-License-Identifier: MIT

"""Importable modules check — ensures required Python imports succeed.

Per VFS_PREFLIGHT_DESIGN.md §4 `tool_registry_presence` (sequence 060).
Surfaced via probes.import_smoke_run.py in Task 6.
"""
from __future__ import annotations
import importlib


def check(modules: list[str]) -> list[str]:
    """Return the list of modules that failed to import.

    Empty list means OK.
    """
    failed: list[str] = []
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception:  # noqa: BLE001 — any failure is a missing tool
            failed.append(m)
    return failed
