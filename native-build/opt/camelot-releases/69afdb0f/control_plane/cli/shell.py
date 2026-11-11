# SPDX-License-Identifier: MIT

"""Interactive REPL shell for the Camelot-OS CLI."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import sys
from typing import Any

from control_plane.cli.constants import (
    CAMELOT_HOME,
    FULL_HELP_LINES,
    HELP_LINES,
)
from control_plane.cli.directives import (
    _invoke_mode_directive,
    _invoke_swarm_directive,
    _is_bare_swarm_directive,
    _set_active_cartridge,
    _translate_mode_directive,
)
from control_plane.cli.renderer import (
    _color,
    _emit,
    _identity_lines,
    _model_label,
    _print_json,
    _provider_label,
    _prompt_text,
    _stream_print,
)
from control_plane.cli.session_log import (
    log_command_error,
    log_raw_entry,
    reset_session,
)
from control_plane.cli.tasks import (
    _run_sarda,
    _run_task,
    _stream_sarda_progress,
    _stream_task_progress,
)

# Global verbose flag — set by shell(), read by tasks._run_task
VERBOSE_TELEMETRY: bool = False


# ---------------------------------------------------------------------------
# Per-command error boundary helper
# ---------------------------------------------------------------------------

def _run_command(
    name: str,
    fn: Any,
    *,
    json_mode: bool,
    context: dict[str, Any] | None = None,
    user_input: str | None = None,
    **kwargs: Any,
) -> None:
    """Execute a command *fn* inside a per-command error boundary.

    On success the return value is emitted.  On failure the error is printed
    (or emitted as JSON), logged to the session log file, and the REPL
    continues — one broken command never crashes the session.
    """
    try:
        output = fn(**kwargs)
        _emit(output, json_mode=json_mode, title=name)
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        log_command_error(name, exc, context=context, user_input=user_input)
        if json_mode:
            _print_json({"success": False, "command": name, "error": str(exc)})
        else:
            _stream_print(f"[{name}] error: {exc}", tone="err")


def _run_async_command(
    name: str,
    coro_fn: Any,
    *,
    json_mode: bool,
    context: dict[str, Any] | None = None,
    user_input: str | None = None,
    **kwargs: Any,
) -> None:
    """Like ``_run_command`` but the function returns a coroutine."""
    try:
        output = asyncio.run(coro_fn(**kwargs))
        _emit(output, json_mode=json_mode, title=name)
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        log_command_error(name, exc, context=context, user_input=user_input)
        if json_mode:
            _print_json({"success": False, "command": name, "error": str(exc)})
        else:
            _stream_print(f"[{name}] error: {exc}", tone="err")


def _repl_context(
    knight: str,
    provider: str | None,
    llm: str | None,
    json_mode: bool,
    non_interactive: bool,
) -> dict[str, Any]:
    """Build the REPL context dict for session log entries."""
    return {
        "knight": knight,
        "provider": provider,
        "model": llm,
        "json_mode": json_mode,
        "non_interactive": non_interactive,
    }


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------
def _interactive_shell(
    json_mode: bool = False,
    provider: str | None = None,
    llm: str | None = None,
    verbose: bool = False,
    non_interactive: bool = False,
) -> int:
    global VERBOSE_TELEMETRY
    VERBOSE_TELEMETRY = verbose

    banner = [
        "Camelot-OS",
        "Prompt-first interface for routing, cloudbrain, and SARDA workflows.",
        "Use /help or //HELP for the full command surface.",
    ]
    if not json_mode:
        _stream_print(banner[0], tone="title")
        _stream_print(banner[1], tone="dim")
        _stream_print(banner[2], tone="dim")
        if provider or llm:
            _stream_print(f"Pinned: provider={provider or 'auto'} llm={llm or 'default'}", tone="info")
        if non_interactive:
            _stream_print("Non-interactive mode — HITL prompts disabled.", tone="warn")

    current_provider = provider
    current_llm = llm
    current_knight = os.getenv("CAMELOT_ACTIVE_KNIGHT", "sir_codex")
    last_route: dict[str, Any] | None = None

    # Initialize stateful conversation history
    conversation_history = [
        {
            "role": "system",
            "content": "You are the Camelot-OS Knight session conversational partner. Be concise, direct, and help the user execute commands and explore the repository. Format code blocks with language hints.",
        }
    ]

    # Start a fresh session log for post-mortem debugging
    session_id = reset_session()
    log_raw_entry({
        "event": "session_start",
        "context": {
            "knight": current_knight,
            "provider": current_provider,
            "model": current_llm,
            "json_mode": json_mode,
            "non_interactive": non_interactive,
        },
    })
    ctx = _repl_context(current_knight, current_provider, current_llm, json_mode, non_interactive)

    while True:
        # ── Input ──────────────────────────────────────────────────────────
        try:
            raw = input(
                _color(_prompt_text(current_knight, current_provider, current_llm), "accent")
            ).strip()
        except EOFError:
            log_raw_entry({"event": "session_end", "reason": "EOF"})
            return 0
        except KeyboardInterrupt:
            log_raw_entry({"event": "session_end", "reason": "KeyboardInterrupt"})
            print()
            return 0

        if not raw:
            continue

        # ── Meta commands (no error boundary needed) ───────────────────────
        if raw == "/clear":
            conversation_history = [conversation_history[0]]
            if not json_mode:
                _stream_print("Conversation history cleared.", tone="ok")
            continue

        if raw == "/history":
            if not json_mode:
                _stream_print(
                    f"Conversation History: {len(conversation_history) - 1} turns",
                    tone="info",
                )
                for msg in conversation_history[1:]:
                    role = msg["role"].upper()
                    _stream_print(
                        f"[{role}]: {msg['content']}",
                        tone="dim" if role == "SYSTEM" else "normal",
                    )
            else:
                _print_json(conversation_history)
            continue

        if raw in {"/exit", "exit", "quit"}:
            log_raw_entry({"event": "session_end", "reason": "user_exit"})
            return 0

        if raw in {"/help", "//HELP"}:
            if not json_mode:
                for line in HELP_LINES:
                    _stream_print(line, tone="dim")
            continue

        if raw in {"/commands", "commands"}:
            if not json_mode:
                for line in FULL_HELP_LINES:
                    _stream_print(line, tone="dim")
            continue

        if raw in {"/who", "who"}:
            output = {
                "knight_id": current_knight,
                "provider": _provider_label(current_provider),
                "model": _model_label(current_llm),
                "last_route": last_route,
            }
            if json_mode:
                _print_json(output)
            else:
                for line in _identity_lines(
                    current_knight, current_provider, current_llm, last_route
                ):
                    _stream_print(line, tone="info")
            continue

        # ── Quick-set commands (no error boundary needed) ──────────────────
        if raw.startswith("/llm "):
            current_llm = raw[len("/llm ") :].strip()
            _stream_print(f"Pinned LLM: {current_llm}", tone="ok")
            continue

        if raw.startswith("/provider "):
            current_provider = raw[len("/provider ") :].strip()
            if current_provider.lower() in ("auto", "none", ""):
                current_provider = None
            _stream_print(f"Pinned Provider: {current_provider or 'auto'}", tone="ok")
            continue

        # ── Runic / mode directives (error-boundaried) ─────────────────────
        try:
            if _is_bare_swarm_directive(raw):
                output = asyncio.run(_invoke_swarm_directive(json_mode=json_mode))
                _emit(output, json_mode=json_mode, title="SWARM")
                continue

            mode_directive = _translate_mode_directive(raw)
            if mode_directive:
                cartridge, translated_intent = mode_directive
                if not translated_intent:
                    output = _set_active_cartridge(cartridge)
                    _emit(output, json_mode=json_mode, title=f"{cartridge} Mode")
                    continue
                if not json_mode:
                    _stream_task_progress(translated_intent, objective=translated_intent)
                output = asyncio.run(
                    _invoke_mode_directive(cartridge, translated_intent)
                )
                _emit(output, json_mode=json_mode, title=f"{cartridge} Mode")
                continue
        except (RuntimeError, ValueError, OSError) as exc:
            log_command_error("directive", exc, context=ctx, user_input=raw)
            if json_mode:
                _print_json({"success": False, "command": "directive", "error": str(exc)})
            else:
                _stream_print(f"[directive] error: {exc}", tone="err")
            continue

        # ── Chat / GUI escape hatches (error-boundaried) ───────────────────
        if raw == "/chat" or raw.startswith("/chat "):
            try:
                _stream_print("Shifting to Sovereign Chat Interface...", tone="accent")
                chat_path = CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "chat.py"
                if not chat_path.exists():
                    _stream_print(f"error: chat.py not found at {chat_path}", tone="err")
                    continue
                parts = raw.split()
                target_provider = current_provider
                target_llm = current_llm
                if "--provider" in parts:
                    idx = parts.index("--provider")
                    if idx + 1 < len(parts):
                        target_provider = parts[idx + 1]
                if "--llm" in parts:
                    idx = parts.index("--llm")
                    if idx + 1 < len(parts):
                        target_llm = parts[idx + 1]
                elif "--model" in parts:
                    idx = parts.index("--model")
                    if idx + 1 < len(parts):
                        target_llm = parts[idx + 1]
                spec = importlib.util.spec_from_file_location("chat", chat_path)
                chat_mod = importlib.util.module_from_spec(spec)
                sys.path.insert(0, str(chat_path.parent))
                spec.loader.exec_module(chat_mod)
                chat_mod.run_chat(provider=target_provider, model=target_llm)
            except (RuntimeError, ValueError, OSError, ImportError) as exc:
                log_command_error("chat", exc, context=ctx, user_input=raw)
                _stream_print(f"[chat] error: {exc}", tone="err")
            continue

        if raw.startswith("/gui") or raw.upper() == "//GUI":
            try:
                _stream_print("Launching Obsidian Spire Cockpit v2.0...", tone="ok")
                from control_plane.infra.tui_app import SovereignApp
                app = SovereignApp()
                app.run()
            except (RuntimeError, ValueError, OSError, ImportError) as exc:
                log_command_error("gui", exc, context=ctx, user_input=raw)
                _stream_print(f"[gui] error: {exc}", tone="err")
            continue

        # ── Status / boot / sync (error-boundaried) ────────────────────────
        if raw == "/status":
            try:
                if not json_mode:
                    _stream_print("Probing Septem Regna Layer health…", tone="title")
                    try:
                        from control_plane.runes import boot_sequence as _bs
                        _bs.run_boot(CAMELOT_HOME)
                    except ImportError:
                        _stream_print("boot_sequence module unavailable", tone="warn")
                    output = asyncio.run(_run_task("cloudbrain status"))
                    _emit(output, json_mode=json_mode, title="Cloudbrain Internals")
                else:
                    try:
                        from control_plane.runes import boot_sequence as _bs
                        output = _bs.run_boot(CAMELOT_HOME, quick=True)
                    except ImportError:
                        output = {"status": "UNAVAILABLE", "error": "boot_sequence module not found"}
                    _print_json(output)
            except (RuntimeError, ValueError, OSError) as exc:
                log_command_error("status", exc, context=ctx, user_input=raw)
                _stream_print(f"[status] error: {exc}", tone="err")
            continue

        if raw == "/boot":
            try:
                _stream_print("Initiating full 6-phase bootstrap sequence…", tone="warn")
                from control_plane.runes import boot_sequence as _bs
                _bs.run_boot(CAMELOT_HOME)
            except ImportError:
                _stream_print("boot_sequence module unavailable", tone="err")
            except (RuntimeError, ValueError, OSError) as exc:
                log_command_error("boot", exc, context=ctx, user_input=raw)
                _stream_print(f"[boot] error: {exc}", tone="err")
            continue

        if raw == "/sync":
            try:
                _stream_print("Triggering OMEGA SYNC PROTOCOL (UKG + Ledger + Kinetic)…", tone="accent")
                from control_plane.runes import boot_sequence as _bs
                sync_script = CAMELOT_HOME / "01_KERNEL" / "system" / "SYNC_PROTOCOL.py"
                venv_py = _bs._detect_venv_python(CAMELOT_HOME)
                import subprocess
                subprocess.run([str(venv_py), str(sync_script)], cwd=str(CAMELOT_HOME), check=False)
            except ImportError:
                _stream_print("boot_sequence module unavailable for sync", tone="err")
            except (RuntimeError, ValueError, OSError) as exc:
                log_command_error("sync", exc, context=ctx, user_input=raw)
                _stream_print(f"[sync] error: {exc}", tone="err")
            continue

        # ── Log (error-boundaried) ─────────────────────────────────────────
        if raw.startswith("/log"):
            try:
                _stream_print("Reading latest Provenance Ledger entries…", tone="info")
                ledger = CAMELOT_HOME / "PROVENANCE_LEDGER.md"
                if ledger.exists():
                    lines = ledger.read_text(encoding="utf-8").splitlines()
                    for line in lines[-20:]:
                        _stream_print(line, tone="dim")
            except (OSError, UnicodeDecodeError) as exc:
                log_command_error("log", exc, context=ctx, user_input=raw)
                _stream_print(f"[log] error: {exc}", tone="err")
            continue

        # ── Task commands (each with its own error boundary) ───────────────
        if raw == "/research-health":
            _run_async_command(
                "research-health",
                _run_task,
                json_mode=json_mode,
                context=ctx,
                user_input=raw,
                intent="research health",
            )
            continue

        if raw.startswith("/memory "):
            agent_id = raw[len("/memory ") :].strip()

            def _do_memory(agent_id: str = agent_id) -> Any:
                if not json_mode:
                    _stream_task_progress(
                        "memory recall", constraints=["privacy=0.0"]
                    )
                return asyncio.run(
                    _run_task(
                        "memory recall",
                        agent_id=agent_id,
                        constraints=["privacy=0.0"],
                    )
                )

            _run_command(
                f"memory:{agent_id}",
                _do_memory,
                json_mode=json_mode,
                context=ctx,
                user_input=raw,
            )
            continue

        if raw.startswith("/research "):
            objective = raw[len("/research ") :].strip()

            def _do_research(objective: str = objective) -> Any:
                if not json_mode:
                    _stream_task_progress(
                        "research investigate objective",
                        objective=objective,
                        constraints=["privacy=0.0", "compute_tier=hybrid"],
                    )
                return asyncio.run(
                    _run_task(
                        "research investigate objective",
                        agent_id="lady_apis",
                        objective=objective,
                        constraints=["privacy=0.0", "compute_tier=hybrid"],
                    )
                )

            _run_command("research", _do_research, json_mode=json_mode, context=ctx, user_input=raw)
            continue

        if raw.startswith("/northstar "):
            objective = raw[len("/northstar ") :].strip()
            constraints = ["privacy=0.0", "compute_tier=apex", "aspect=research"]

            def _do_northstar(objective: str = objective) -> Any:
                if not json_mode:
                    _stream_task_progress(
                        "northstar war room objective",
                        objective=objective,
                        constraints=constraints,
                    )
                return asyncio.run(
                    _run_task(
                        "northstar war room objective",
                        agent_id="northstar",
                        objective=objective,
                        constraints=constraints,
                        extra_parameters={
                            "aspect": "research",
                            "compute_tier": "apex",
                            "cartridge": "COGNITIVE",
                            "browser_isolation": "team",
                            "multilogin_enabled": True,
                        },
                    )
                )

            _run_command("northstar", _do_northstar, json_mode=json_mode, context=ctx, user_input=raw)
            continue

        if raw.startswith("/blueprint "):
            objective = raw[len("/blueprint ") :].strip()
            constraints = ["compute_tier=kinetic", "budget_mode=lean"]

            def _do_blueprint(objective: str = objective) -> Any:
                if not json_mode:
                    _stream_task_progress(
                        "development blueprint objective",
                        objective=objective,
                        constraints=constraints,
                    )
                return asyncio.run(
                    _run_task(
                        "development blueprint objective",
                        objective=objective,
                        constraints=constraints,
                        extra_parameters={
                            "compute_tier": "kinetic",
                            "budget_mode": "lean",
                            "team_size": 1,
                            "horizon_days": 30,
                            "prioritize_local_first": True,
                            "multilogin_enabled": True,
                        },
                    )
                )

            _run_command("blueprint", _do_blueprint, json_mode=json_mode, context=ctx, user_input=raw)
            continue

        if raw.startswith("/precise "):
            objective = raw[len("/precise ") :].strip()
            constraints = ["compute_tier=hybrid", "browser_isolation=agency"]

            def _do_precise(objective: str = objective) -> Any:
                if not json_mode:
                    _stream_task_progress(
                        "precise mode objective",
                        objective=objective,
                        constraints=constraints,
                    )
                return asyncio.run(
                    _run_task(
                        "precise mode objective",
                        objective=objective,
                        constraints=constraints,
                        extra_parameters={
                            "compute_tier": "hybrid",
                            "browser_isolation": "agency",
                            "residential_proxy_enabled": True,
                            "stealth_enabled": True,
                            "ephemeral_sessions": True,
                            "operator_count": 1,
                            "memory_gb": 8,
                        },
                    )
                )

            _run_command("precise", _do_precise, json_mode=json_mode, context=ctx, user_input=raw)
            continue

        if raw.startswith("/sarda "):
            intent = raw[len("/sarda ") :].strip()

            def _do_sarda(intent: str = intent) -> Any:
                if not json_mode:
                    _stream_sarda_progress(intent, execute=False)
                return asyncio.run(_run_sarda(intent, execute=False))

            _run_command("sarda", _do_sarda, json_mode=json_mode, context=ctx, user_input=raw)
            continue

        if raw == "/ledger-status":
            try:
                from control_plane.infra.ledger_sync import ledger_status
                output = ledger_status()
                _emit(output, json_mode=json_mode, title="Ledger Status")
            except (RuntimeError, ValueError, OSError) as exc:
                log_command_error("ledger-status", exc, context=ctx, user_input=raw)
                _stream_print(f"[ledger-status] error: {exc}", tone="err")
            continue

        # ── Route (error-boundaried) ───────────────────────────────────────
        if raw.startswith("/route "):
            try:
                from control_plane.infra.cli_intercept import CLIIntercept
                intercept = CLIIntercept()
                result = intercept.intercept(raw[len("/route ") :].strip())
                output = {
                    "knight_id": result.route.knight_id,
                    "engine": result.engine_cmd,
                    "model": result.model,
                    "backend_url": result.backend_url,
                    "reason": result.route.reason,
                }
                current_knight = result.route.knight_id
                current_llm = result.model
                last_route = output
                if json_mode:
                    _print_json(output)
                else:
                    _stream_print(intercept.format_route_log(result), tone="info")
            except (RuntimeError, ValueError, OSError) as exc:
                log_command_error("route", exc, context=ctx, user_input=raw)
                if json_mode:
                    _print_json({"success": False, "command": "route", "error": str(exc)})
                else:
                    _stream_print(f"[route] error: {exc}", tone="err")
            continue

        # ── Conversational stateful mode (error-boundaried) ─────────────────
        try:
            conversation_history.append({"role": "user", "content": raw})

            from control_plane.infra.cli_intercept import CLIIntercept
            intercept = CLIIntercept()
            result = intercept.intercept(raw)
            current_knight = result.route.knight_id
            current_llm = result.model
            last_route = {
                "knight_id": result.route.knight_id,
                "engine": result.engine_cmd,
                "model": result.model,
                "backend_url": result.backend_url,
                "reason": result.route.reason,
            }

            chat_dir = CAMELOT_HOME / "03_VAULT" / "training" / "configs"
            if str(chat_dir) not in sys.path:
                sys.path.insert(0, str(chat_dir))

            import llm_router

            if not json_mode:
                if VERBOSE_TELEMETRY:
                    _stream_print(intercept.format_route_log(result), tone="info")
                _stream_print(
                    f"[{result.route.knight_id.upper()}] thinking...", tone="accent"
                )

            target_provider = current_provider or "cliproxy"
            target_llm = current_llm or result.model

            res = llm_router.chat(
                messages=conversation_history,
                provider=target_provider,
                model=target_llm,
            )

            if res.get("error"):
                _stream_print(f"error: {res['error']}", tone="err")
                conversation_history.pop()  # drop user turn on error
            else:
                content = res.get("content", "")
                conversation_history.append({"role": "assistant", "content": content})
                if json_mode:
                    _print_json(res)
                else:
                    _stream_print(content, tone="normal")
        except (RuntimeError, ValueError, OSError, ImportError) as exc:
            # Roll back user turn on any failure
            if (
                conversation_history
                and conversation_history[-1].get("role") == "user"
            ):
                conversation_history.pop()
            log_command_error("chat", exc, context=ctx, user_input=raw)
            if json_mode:
                _print_json({"success": False, "command": "chat", "error": str(exc)})
            else:
                _stream_print(f"[chat] error: {exc}", tone="err")
