# SPDX-License-Identifier: MIT

"""User-facing Camelot-OS CLI — backward-compatible shim.

The implementation has been refactored into the ``control_plane.cli`` package:

  control_plane/cli/
  ├── constants.py   — CAMELOT_HOME, STREAM_DELAY, help text, cartridge map
  ├── renderer.py    — ANSI color, stream_print, pretty_render, emit
  ├── iron_gate.py   — HITL Iron Gate security check
  ├── tasks.py       — _run_task, _run_sarda, _run_team_self_test, progress
  ├── directives.py  — mode/cartridge translation and invocation
  ├── cloudbrain.py  — endpoint diagnosis, audit, Modal discovery
  ├── orchestrator.py — orchestrator CLI wrapper
  ├── notebooklm.py  — NotebookLM login handler
  ├── parser.py      — argparse builder (_build_parser)
  ├── shell.py       — interactive REPL (_interactive_shell)
  └── dispatch.py    — main() entry point and command dispatch

All public symbols are re-exported here so that existing imports like::

  from control_plane.camelot_cli import main, _build_parser, _interactive_shell
  from control_plane import camelot_cli

...continue to work without modification.
"""

from __future__ import annotations

# Re-export every symbol that was previously importable from this module.
# This preserves backward compatibility for tests, bin/camelot.py, and
# any other code that references ``control_plane.camelot_cli.*``.

from control_plane.cli.constants import (  # noqa: F401
    ACTIVE_CARTRIDGE_PATH,
    BARE_SWARM_DIRECTIVE,
    BARE_SWARM_OBJECTIVE,
    CAMELOT_HOME,
    FULL_HELP_LINES,
    HELP_LINES,
    MODE_CARTRIDGE_MAP,
    MODAL_DISCOVERY_MAP,
    PROGRESS_DELAY,
    STREAM_DELAY,
    _detect_home,
)
from control_plane.cli.renderer import (  # noqa: F401
    _color,
    _emit,
    _identity_lines,
    _model_label,
    _pretty_render,
    _print_json,
    _progress,
    _provider_label,
    _prompt_text,
    _stream_print,
)
from control_plane.cli.iron_gate import _check_iron_gate  # noqa: F401
from control_plane.cli.iron_gate import set_non_interactive as set_non_interactive  # noqa: F401
from control_plane.cli.tasks import (  # noqa: F401
    VERBOSE_TELEMETRY,
    _run_sarda,
    _run_task,
    _run_team_self_test,
    _stream_sarda_progress,
    _stream_task_progress,
)
from control_plane.cli.directives import (  # noqa: F401
    _invoke_mode_directive,
    _invoke_swarm_directive,
    _is_bare_swarm_directive,
    _set_active_cartridge,
    _translate_mode_directive,
)
from control_plane.cli.cloudbrain import (  # noqa: F401
    _audit_cloudbrain_configuration,
    _diagnose_cloud_endpoints,
    _discover_modal_endpoints,
)
from control_plane.cli.orchestrator_cmd import _run_orchestrator_cli  # noqa: F401
from control_plane.cli.notebooklm import _cmd_camelot_notebooklm_login  # noqa: F401
from control_plane.cli.parser import _build_parser  # noqa: F401
from control_plane.cli.shell import _interactive_shell  # noqa: F401
from control_plane.cli.session_log import (  # noqa: F401
    get_log_path as get_log_path,
    log_command_error as log_command_error,
    log_raw_entry as log_raw_entry,
    reset_session as reset_session,
)
from control_plane.core.ocx_bridge import (  # noqa: F401
    OCXBridge as OCXBridge,
    get_bridge as get_bridge,
    is_opencodex_available as is_opencodex_available,
    resolve_knight_model as resolve_knight_model,
)
from control_plane.cli.dispatch import main as main  # noqa: F401
from control_plane.runes.system_triage import TriageOptions as TriageOptions  # noqa: F401
from control_plane.runes.system_triage import run_system_triage as run_system_triage  # noqa: F401

# Re-export symbols that tests monkeypatch via ``camelot_cli.<name>``
from control_plane.infra.config_manager import ConfigManager as ConfigManager  # noqa: F401
from control_plane.infra.provenance import ProvenanceManager as ProvenanceManager  # noqa: F401
from control_plane.infra.cockpit import refresh_snapshot as refresh_snapshot  # noqa: F401
from control_plane.infra.cloudbrain_sync import sync_queue_status as sync_queue_status  # noqa: F401

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        import sys
        import traceback
        from control_plane.cli.renderer import _stream_print
        from control_plane.infra.hyper_evolve import append_learning

        error_msg = str(e)
        trace = traceback.format_exc()
        _stream_print(f"\n[🔥] KINETIC_CRITICAL_FAILURE: {error_msg}", tone="warn")
        _stream_print("Transmuting error into Chronicle of Scars...", tone="dim")

        # Log to Chronicle of Scars (L6 Governance)
        try:
            append_learning(
                agent="SIR_BORIS",
                objective="Global CLI Execution",
                failures=[error_msg],
                learning="Caught unhandled exception in main loop.",
                proposal=f"Patch affected path and implement guardrail for: {error_msg}",
            )
            _stream_print("Scar recorded. System will evolve on next //BOOT.", tone="accent")
        except Exception:
            pass

        sys.exit(1)
