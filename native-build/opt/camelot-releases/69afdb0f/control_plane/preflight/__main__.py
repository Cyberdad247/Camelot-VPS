# SPDX-License-Identifier: MIT

"""CLI entry point for control_plane.preflight (slice #1 Task 7).

Subcommands:
  --run         Load vfs/checks/ and execute_catalog end-to-end.
  --test        Self-test: writes a synthetic 8-pass catalog into a
                tmp dir and runs execute_catalog. Used to verify the
                orchestrator health without external dependencies.
  --list        Print catalog (sequence, id, type, hitl_on_fail).
  --graduate    Explicit operator-driven graduation: writes
                _graduated.flag for the configured run_root.

Forbidden escape hatches (per ADR 0006):
  env vars:    CAMELOT_SKIP_PREFLIGHT, CAMELOT_BYPASS_PREFLIGHT
  flags:       --skip-sovereign, --force, --no-preflight, --bypass

For each of the above, the CLI exits with code 2 and writes an
explicit message to stderr explaining the design rationale per
ADR 0006 (drop the sovereign escape hatch).
"""
from __future__ import annotations
import argparse
import os
import sys
import tempfile
from pathlib import Path

from .runner import CatalogError, execute_catalog, load_catalog
from .state import GraduationFlag


FORBIDDEN_ENVS = ("CAMELOT_SKIP_PREFLIGHT", "CAMELOT_BYPASS_PREFLIGHT")
FORBIDDEN_FLAGS = (
    "--skip-sovereign", "--force", "--no-preflight", "--bypass",
)
ESCAPE_HATCH_MSG = (
    "sovereign escape hatch is not supported. Per ADR 0006, the design "
    "deliberately drops CAMELOT_SKIP_PREFLIGHT-style overrides; strict-mode "
    "halts are hard halts. Resolve the underlying check or roll back to "
    "advisor-mode by deleting "
    "03_VAULT/runtime_state/preflight/_graduated.flag"
)


def _enforce_no_escape_hatches(argv: list[str]) -> None:
    """Reject env-vars and flags that would bypass the gate.

    Runs BEFORE argparse so a forbidden flag is rejected even if
    the user only passes --skip-sovereign with no other args.
    """
    for env in FORBIDDEN_ENVS:
        if env in os.environ:
            sys.stderr.write(
                f"[VFS_PREFLIGHT] env var {env!r} rejected: {ESCAPE_HATCH_MSG}\n"
            )
            sys.exit(2)
    for flag in FORBIDDEN_FLAGS:
        if flag in argv:
            sys.stderr.write(
                f"[VFS_PREFLIGHT] flag {flag!r} rejected: {ESCAPE_HATCH_MSG}\n"
            )
            sys.exit(2)


def _fake_anya_triage(raw_intent: str) -> dict:
    """Advisory-only sentinel; the real AnyaGate never gets called here
    so tests can run without the substrate."""
    return {
        "method": "advisory_unavailable",
        "lane": "NORMAL",
        "hitl_tier": "AUTO",
        "shatterpoints_detected": [],
    }


def _resolve_paths() -> tuple[Path, Path, Path]:
    """Resolve repo-root, vfs/checks/, 03_VAULT/runtime_state/."""
    here = Path(__file__).resolve()
    repo_root = here
    while repo_root.parent != repo_root:
        if (repo_root / ".git").exists() or (repo_root / "pyproject.toml").exists():
            break
        repo_root = repo_root.parent
    checks_dir = repo_root / "vfs" / "checks"
    run_root = repo_root / "03_VAULT" / "runtime_state"
    return repo_root, checks_dir, run_root


def cmd_run(args: argparse.Namespace) -> int:
    repo_root, checks_dir, run_root = _resolve_paths()
    if not checks_dir.exists():
        sys.stderr.write(
            f"[VFS_PREFLIGHT] checks dir missing: {checks_dir}\n"
        )
        return 2
    try:
        specs = load_catalog(checks_dir)
    except CatalogError as e:
        sys.stderr.write(f"[VFS_PREFLIGHT] CATALOG INVALID: {e}\n")
        return 1
    grad = GraduationFlag(run_root)
    strict = grad.is_strict()
    try:
        scene_text = (
            (repo_root / "vfs" / "rosters.md").read_text()
            + (repo_root / "docs" / "architecture" / "lattice.yaml").read_text()
        )
    except OSError:
        scene_text = ""
    try:
        manifest = execute_catalog(
            specs=specs,
            run_root=run_root,
            scene_text=scene_text,
            strict_mode=strict,
            anya_triage_fn=_fake_anya_triage,
        )
    except CatalogError as e:
        sys.stderr.write(f"[VFS_PREFLIGHT] CATALOG INVALID: {e}\n")
        return 1
    print(f"[VFS_PREFLIGHT] run_id={manifest.run_id}")
    print(
        f"[VFS_PREFLIGHT] {manifest.checks_passed}/{manifest.checks_total} "
        f"CONFIRMED · {manifest.total_ms}ms · catalog_hash="
        f"{manifest.catalog_hash[:8]}\u2026"
    )
    if manifest.halted_at_check:
        print(
            f"[VFS_PREFLIGHT] REJECTED: {manifest.halted_at_check}; "
            f"halt_decision={manifest.halt_decision}"
        )
    if manifest.halt_decision == "block_boot":
        return 1
    return 0


def _self_test_catalog(tmp: Path) -> Path:
    """Write a synthetic 8-pass catalog into tmp/catalog/.

    Each spec invokes a probe-runner that prints {"all_ok": true} on
    stdout. Used by --test to verify orchestrator plumbing without
    touching vfs/checks/.
    """
    cat = tmp / "catalog"
    cat.mkdir(parents=True)
    for i in range(1, 9):
        seq = f"00{i}"
        spec_text = (
            f"sequence: \"{seq}\"\n"
            f"id: self_test_{i}\n"
            f"display_name: Self-Test {i}\n"
            f"command_type: shell\n"
            f"command: [\"python\", \"-c\", "
            f"\"import json,sys; sys.stdout.write(json.dumps({{'all_ok': True}}))\"]\n"
            f"timeout_s: 5\n"
            f"retry: 0\n"
            f"expected_evidence_class: CONFIRMED\n"
            f"hitl_on_fail: false\n"
            f"remediation_hint: null\n"
        )
        (cat / f"0{seq}_self_test_{i}.yaml").write_text(spec_text)
    return cat


def cmd_test(args: argparse.Namespace) -> int:
    """Self-test: synthetic 8-pass catalog -> execute_catalog.

    Uses an isolated tmp run_root so the self-test can never write
    artifacts into the live 03_VAULT/runtime_state tree and can never
    accidentally graduate the real system (the bug that wrote
    _graduated.flag before any real all-CONFIRMED run).
    """
    repo_root, _, _ = _resolve_paths()
    with tempfile.TemporaryDirectory(prefix="preflight_selftest_") as td:
        tmp = Path(td)
        checks_dir = _self_test_catalog(tmp)
        run_root = tmp / "run_root"
        run_root.mkdir(parents=True, exist_ok=True)
        try:
            specs = load_catalog(checks_dir)
        except CatalogError as e:
            sys.stderr.write(f"[VFS_PREFLIGHT] self-test CATALOG INVALID: {e}\n")
            return 1
        manifest = execute_catalog(
            specs=specs,
            run_root=run_root,
            scene_text="self-test",
            strict_mode=GraduationFlag(run_root).is_strict(),
            anya_triage_fn=_fake_anya_triage,
        )
    print(f"[VFS_PREFLIGHT] self-test run_id={manifest.run_id}")
    if manifest.checks_passed == manifest.checks_total:
        print(
            f"[VFS_PREFLIGHT] self-test all checks passing "
            f"({manifest.checks_passed}/{manifest.checks_total})"
        )
        return 0
    sys.stderr.write(
        f"[VFS_PREFLIGHT] self-test failed: "
        f"{manifest.checks_failed} of {manifest.checks_total} failed\n"
    )
    return 1


def cmd_list(args: argparse.Namespace) -> int:
    repo_root, checks_dir, _ = _resolve_paths()
    if not checks_dir.exists():
        sys.stderr.write(
            f"[VFS_PREFLIGHT] checks dir missing: {checks_dir}\n"
        )
        return 2
    try:
        specs = load_catalog(checks_dir)
    except CatalogError as e:
        sys.stderr.write(f"[VFS_PREFLIGHT] CATALOG INVALID: {e}\n")
        return 1
    for s in specs:
        print(
            f"{s.sequence:03d}\t{s.id}\t{s.command_type}\t"
            f"hitl={'true' if s.hitl_on_fail else 'false'}"
        )
    return 0


def cmd_graduate(args: argparse.Namespace) -> int:
    _, _, run_root = _resolve_paths()
    grad = GraduationFlag(run_root)
    if grad.is_strict():
        print(f"[VFS_PREFLIGHT] already strict: {grad.path()}")
        return 0
    grad.graduate()
    print(
        f"[VFS_PREFLIGHT] graduated to strict-mode; "
        f"flag written at {grad.path()}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _enforce_no_escape_hatches(argv)
    ap = argparse.ArgumentParser(
        prog="python -m control_plane.preflight",
        description="VFS Preflight CLI (slice #1 Task 7)",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--run", action="store_true",
        help="Load vfs/checks/ and run execute_catalog."
    )
    g.add_argument(
        "--test", action="store_true",
        help="Run an inline 8-pass synthetic catalog (no real substrate)."
    )
    g.add_argument(
        "--list", action="store_true",
        help="Print vfs/checks/ catalog."
    )
    g.add_argument(
        "--graduate", action="store_true",
        help="Promote advisor -> strict by writing _graduated.flag."
    )
    args = ap.parse_args(argv)
    if args.run:
        return cmd_run(args)
    if args.test:
        return cmd_test(args)
    if args.list:
        return cmd_list(args)
    if args.graduate:
        return cmd_graduate(args)
    return 2  # unreachable given mutually-exclusive group required


if __name__ == "__main__":
    sys.exit(main())
