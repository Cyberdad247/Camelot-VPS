# SPDX-License-Identifier: MIT

"""control_plane.preflight.boot_integration — boot-phase wrapper (slice #1 Task 8).

This module threads VFS preflight into the existing Camelot-OS boot
sequence as the FIRST phase — stratifying BEFORE the existing
EXCALIBUR pre-flight (control_plane.infra.excalibur_preflight).

Surface contract (matching EXCALIBUR's boot_excalibur_preflight):
    boot_vfs_preflight(home: Path) -> tuple[bool, str]
        - Returns (True,  msg) on GO            (msg shown GREEN)
        - Returns (False, msg) on REJECT/halt    (msg shown WARN/RED)

The caller (control_plane.infra.boot_sequence.run_boot) treats the
first phase (VFS preflight) as non-required in the day-0 cycle, then
promotes to required=True after sovereign graduation.

Adviser-mode graduation
-----------------------
- Day-0 (no `_graduated.flag`): REJECT becomes a non-blocking
  advisor_finding → boot proceeds, operator summary surfaces every
  finding immediately.
- Post-graduation (`_graduated.flag` present): REJECT halts the boot
  (returns False, "VFS_PREFLIGHT REJECT: ..."). Strict mode.

Internally calls execute_catalog(); does no YAML parsing of its own.
Anya triage is fed a harmless stub that returns _ADVISORY_UNAVAILABLE,
so boot_vfs_preflight NEVER crashes when AnyaGate is unreachable
(slice #1 design §3.4 graceful-degradation sentinel).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .runner import (
    _ADVISORY_UNAVAILABLE,
    CatalogError,
    execute_catalog,
    load_catalog,
)
from .state import GraduationFlag


def boot_vfs_preflight(home: Path) -> tuple[bool, str]:
    """Boot-phase VFS preflight entry point.

    Stratifies before EXCALIBUR pre-flight (slice #1 design §10).
    Returns (ok, msg) for the boot summary row, matching the EXCALIBUR
    pre-flight contract.
    """
    # Single state root for BOTH artifacts and the graduation flag.
    # execute_catalog writes per-run dirs at
    # <run_root>/preflight/<UTC>/ and GraduationFlag(run_root).path()
    # resolves to <run_root>/preflight/_graduated.flag — one consistent
    # location, so strict detection, first_run, and graduation all agree
    # (fixes the pre-graduation mismatch where first_run stayed True in
    # strict mode and graduation wrote to a nested, unread path).
    run_root = home / "03_VAULT" / "runtime_state"
    checks_root = home / "vfs" / "checks"
    strict_mode = GraduationFlag(run_root).is_strict()

    try:
        specs = load_catalog(checks_root)
    except (CatalogError, FileNotFoundError, OSError) as exc:
        return False, (
            f"VFS_PREFLIGHT error: {type(exc).__name__}: {exc}"
        )

    if not specs:
        # Empty catalog: nothing to assert ⇒ proceed (informative message).
        return True, (
            f"VFS_PREFLIGHT GO: 0 check(s) catalog_hash=(empty) "
            f"halt=allow_boot strict_mode={strict_mode}"
        )

    scene_text = _scene_for(home)

    try:
        manifest = execute_catalog(
            specs=specs,
            run_root=run_root,
            scene_text=scene_text,
            strict_mode=strict_mode,
            anya_triage_fn=lambda _intent: dict(_ADVISORY_UNAVAILABLE),
        )
    except Exception as exc:  # noqa: BLE001 — boot-phase sentinel
        return False, (
            f"VFS_PREFLIGHT error: {type(exc).__name__}: {exc}"
        )

    halt = (manifest.halt_decision or "").lower() if hasattr(
        manifest, "halt_decision"
    ) else ""
    if halt == "block_boot":
        return _halt_msg(manifest, strict_mode)
    return _go_msg(manifest, strict_mode)


def _halt_msg(manifest: Any, strict_mode: bool) -> tuple[bool, str]:
    summary = _summarize_manifest(manifest)
    return False, (
        f"VFS_PREFLIGHT REJECT: {summary} "
        f"strict_mode={strict_mode}; hard halt per ADR 0006."
    )


def _go_msg(manifest: Any, strict_mode: bool) -> tuple[bool, str]:
    summary = _summarize_manifest(manifest)
    return True, (
        f"VFS_PREFLIGHT GO: {summary} strict_mode={strict_mode}"
    )


def _summarize_manifest(manifest: Any) -> str:
    """Build a one-line, color-friendly summary for the boot row.

    Accepts either a RunManifest attribute object OR a plain dict
    (handy in tests and for code that has already serialized to dict).
    """
    if isinstance(manifest, dict):
        checks = manifest.get("checks", []) or []
        halt = manifest.get("halt_decision", "allow_boot")
        catalog_hash = (manifest.get("catalog_hash", "") or "")[:8]
    else:
        checks = getattr(manifest, "checks", []) or []
        halt = getattr(manifest, "halt_decision", "allow_boot")
        catalog_hash = (getattr(manifest, "catalog_hash", "") or "")[:8]
    return (
        f"{len(checks)} check(s) catalog_hash={catalog_hash} halt={halt}"
    )


def _scene_for(home: Path) -> str:
    """Brief, opaque scene representation for the preflight substrate.

    The catalog checks read this opaque string for hints; it is *not*
    parsed by execute_catalog. Kept tiny + line-oriented for the
    YAML probes to extract.
    """
    return (
        f"home={home}\n"
        f"profile=cybertronia-win\n"
        f"runner=control_plane.preflight.boot_integration\n"
    )
