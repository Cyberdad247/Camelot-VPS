# SPDX-License-Identifier: MIT

"""Main entry point and command dispatch for the Camelot-OS CLI.

The heavy lifting lives in ``control_plane.cli.handlers`` (one function per
subcommand).  ``main()`` handles the Bifrost gate, free-form directive
routing, arg parsing, and delegates to the handler registry.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from control_plane.cli.directives import (
    _invoke_mode_directive,
    _invoke_swarm_directive,
    _is_bare_swarm_directive,
    _set_active_cartridge,
    _translate_mode_directive,
)
from control_plane.cli.handlers import COMMAND_REGISTRY
from control_plane.cli.parser import _build_parser
from control_plane.cli.renderer import _emit, _stream_print
from control_plane.cli.tasks import _run_task, _stream_task_progress


# ---------------------------------------------------------------------------
# Provenance / sync helpers
# ---------------------------------------------------------------------------

def _log_run(
    results: dict[str, Any],
    success: bool,
    args: Any,
    prov_mgr: Any,
    argv: list[str],
) -> None:
    from control_plane.infra.provenance import VerificationRun
    from control_plane.infra.cloudbrain_sync import sync_after_event

    operator = getattr(args, "profile", "default") or "default"
    run = VerificationRun(
        run_id=f"run_{int(time.time())}",
        operator=operator,
        command=" ".join(argv),
        results=results,
        success=success,
    )
    if prov_mgr is not None:
        prov_mgr.log_verification(run)
    payload = results.get("payload", {}) if isinstance(results, dict) else {}
    service = payload.get("service")
    mutating_command = (
        args.command in {"glyph", "forge-unify", "evolve", "sarda", "team"}
        or (args.command == "ledger" and getattr(args, "ledger_command", "") == "update")
        or (
            args.command == "microcubed"
            and getattr(args, "microcubed_command", "") in {"forge", "execute", "teardown"}
        )
    )
    if (
        success
        and mutating_command
        and service != "notebooklm_sync"
        and "cloudbrain sync" not in run.command.lower()
    ):
        event = sync_after_event(
            event_type="verification_run",
            command=run.command,
            results=results,
        )
        if isinstance(results, dict):
            results.setdefault("cloudbrain_sync", event)


# ---------------------------------------------------------------------------
# Known commands (for argv normalisation)
# ---------------------------------------------------------------------------

KNOWN_COMMANDS = {
    "chat", "route", "triage", "cloudbrain", "orchestrator", "sarda",
    "hermes", "bifrost", "contracts", "ledger", "toon", "glyph", "glyth", "forge-unify", "cockpit",
    "evolve", "team", "codex", "bio-swarm", "nano-swarm", "microcubed",
    "gemini-ext", "scripts", "ctx7", "pipeline", "health", "templates",
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # --- Bifrost gate ---
    try:
        from bin import bifrost
        bifrost.enforce()
    except Exception as e:
        _stream_print(f"BIFROST GATE REFUSED: {e}", tone="err")
        return 77

    # --- Normalise argv ---
    argv = sys.argv[1:]
    for index, part in enumerate(argv):
        if not part.startswith("-"):
            lowered = part.lower()
            if lowered in KNOWN_COMMANDS:
                argv[index] = lowered
            elif lowered == "glyth":
                argv[index] = "glyph"
            break

    # --- Free-form / directive dispatch (no subcommand) ---
    if argv and not argv[0].startswith("-") and argv[0] not in KNOWN_COMMANDS:
        json_mode = False
        prompt_parts = argv
        if "--json" in argv:
            json_mode = True
            prompt_parts = [part for part in argv if part != "--json"]
        prompt_text = " ".join(prompt_parts)
        if _is_bare_swarm_directive(prompt_text):
            output = asyncio.run(_invoke_swarm_directive(json_mode=json_mode))
            _emit(output, json_mode=json_mode, title="SWARM")
            return 0
        mode_directive = _translate_mode_directive(prompt_text)
        if mode_directive:
            cartridge, translated_intent = mode_directive
            if not translated_intent:
                output = _set_active_cartridge(cartridge)
                _emit(output, json_mode=json_mode, title=f"{cartridge} Mode")
                return 0
            if not json_mode:
                _stream_task_progress(translated_intent, objective=translated_intent)
            output = asyncio.run(_invoke_mode_directive(cartridge, translated_intent))
            _emit(output, json_mode=json_mode, title=f"{cartridge} Mode")
            return 0
        if not json_mode:
            _stream_task_progress(prompt_text)
        output = asyncio.run(_run_task(prompt_text))
        _emit(output, json_mode=json_mode, title="Camelot-OS")
        return 0

    # --- Subcommand dispatch ---
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Propagate --non-interactive to the iron gate
    if getattr(args, "non_interactive", False):
        from control_plane.cli.iron_gate import set_non_interactive
        set_non_interactive(True)

    # Load config + provenance managers only for commands that can use them.
    if args.command in {"bifrost", "contracts"}:
        config_mgr = None
        prov_mgr = None
    else:
        import control_plane.camelot_cli as _cli_mod
        config_mgr = _cli_mod.ConfigManager()
        prov_mgr = _cli_mod.ProvenanceManager()

    # Look up handler in registry
    handler = COMMAND_REGISTRY.get(args.command)
    if handler:
        return handler(args, config_mgr, prov_mgr, argv)

    # --- Fallback: enter interactive shell ---
    from control_plane.cli.shell import _interactive_shell
    return _interactive_shell(
        json_mode=args.json,
        non_interactive=getattr(args, "non_interactive", False),
    )
