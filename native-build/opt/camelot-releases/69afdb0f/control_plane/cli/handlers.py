# SPDX-License-Identifier: MIT

"""Command handlers for the Camelot-OS CLI.

Each handler receives (args, config_mgr, prov_mgr, argv) and returns an int
exit code.  The ``COMMAND_REGISTRY`` dict at the bottom maps subcommand names
to their handler functions, keeping ``dispatch.py`` under 400 lines.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_plane.cli.constants import CAMELOT_HOME
from control_plane.cli.renderer import (
    _emit,
    _print_json,
    _progress,
    _stream_print,
)
from control_plane.cli.tasks import (
    _run_sarda,
    _run_task,
    _run_team_self_test,
    _stream_sarda_progress,
    _stream_task_progress,
)


# ---------------------------------------------------------------------------
# Handler type alias
# ---------------------------------------------------------------------------

HandlerFn = Any  # Callable[[argparse.Namespace, ConfigManager, ProvenanceManager, list[str]], int]


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------

def _handle_chat(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    from control_plane.cli.shell import _interactive_shell
    return _interactive_shell(
        json_mode=args.json,
        provider=args.provider,
        llm=args.llm,
        verbose=args.verbose,
        non_interactive=getattr(args, "non_interactive", False),
    )


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------

def _handle_route(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    from control_plane.infra.cli_intercept import CLIIntercept
    intercept = CLIIntercept()
    result = intercept.intercept(" ".join(args.intent))
    if args.json:
        _print_json(
            {
                "knight_id": result.route.knight_id,
                "engine": result.engine_cmd,
                "model": result.model,
                "backend_url": result.backend_url,
                "reason": result.route.reason,
            }
        )
    else:
        _stream_print(intercept.format_route_log(result), tone="info")
    return 0


# ---------------------------------------------------------------------------
# triage
# ---------------------------------------------------------------------------

def _handle_triage(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    import control_plane.camelot_cli as _cli_mod
    TriageOptions = _cli_mod.TriageOptions
    run_system_triage = _cli_mod.run_system_triage
    mode = "rapid" if args.rapid else ("deep" if args.deep else "auto")
    result = run_system_triage(
        CAMELOT_HOME,
        options=TriageOptions(
            mode=mode,
            force_deep=args.force_deep,
            write_reports=not args.no_reports,
            command_timeout_s=max(1, args.timeout),
        ),
    )
    _emit(result.to_dict(), json_mode=args.triage_json or args.json, title="System Triage")
    return result.exit_code


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------

def _handle_orchestrator(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    from control_plane.cli.orchestrator_cmd import _run_orchestrator_cli
    output = _run_orchestrator_cli(
        mode=args.mode,
        root=args.root,
        older_than_days=args.older_than_days,
        large_file_mb=args.large_file_mb,
        intent=args.intent,
        message=args.message,
        kind=args.kind,
        status=args.status,
    )
    _emit(output, json_mode=args.json, title="Orchestrator")
    return 0


# ---------------------------------------------------------------------------
# hermes
# ---------------------------------------------------------------------------

def _handle_hermes(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    from control_plane.infra.vps_hermes_prime import summarize_vps_hermes_prime

    output = summarize_vps_hermes_prime(
        root=CAMELOT_HOME,
        probe_live=getattr(args, "probe_live", False),
    )
    _emit(output, json_mode=args.json, title="VPS Hermes_Prime")
    return 0 if output.get("status") in {"CONFIGURED", "ONLINE", "DEGRADED"} else 2


def _handle_bifrost(args: Any, config_mgr: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.cli.bifrost_cmd import handle_bifrost

    return handle_bifrost(args, config_mgr, prov_mgr, argv)


def _handle_contracts(args: Any, config_mgr: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.cli.contracts_cmd import handle_contracts

    return handle_contracts(args, config_mgr, prov_mgr, argv)


# ---------------------------------------------------------------------------
# ledger
# ---------------------------------------------------------------------------

def _handle_ledger(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.infra.ledger_sync import (
        append_provenance_entry,
        ledger_status,
        reconcile_ledger_mirrors,
        sync_to_kernel,
    )
    from control_plane.infra.cloudbrain_sync import sync_after_event
    from control_plane.cli.dispatch import _log_run

    if args.ledger_command == "status":
        output = ledger_status()
    elif args.ledger_command == "audit":
        if not args.json:
            _stream_print("Initiating forensic SHA-256 integrity check...", tone="accent")
        is_valid = prov_mgr.verify_integrity()
        output = {
            "status": "SECURE" if is_valid else "TAMPERED",
            "integrity_check": "PASS" if is_valid else "FAIL",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "entries_scanned": len(prov_mgr.get_verification_entries()),
            "ledger_path": str(prov_mgr.verification_ledger),
        }
    elif args.ledger_command == "reconcile":
        output = reconcile_ledger_mirrors()
    elif args.ledger_command == "update":
        output = append_provenance_entry(
            title=args.title,
            actor=args.actor,
            scope=list(args.scope),
            verification=list(args.verification),
            tag=args.tag,
        )
        output["cloudbrain_sync"] = sync_after_event(
            event_type="ledger_update",
            command=f"ledger update {args.title}",
            results=output,
        )
    else:
        if not args.json:
            _progress("sync", "sending ledger sync intent to local kernel", tone="info")
        output = asyncio.run(sync_to_kernel(args.intent))
    _log_run(output, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(output, json_mode=args.json, title="Ledger")
    return 0


# ---------------------------------------------------------------------------
# toon
# ---------------------------------------------------------------------------

def _handle_toon(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.cli.toon_manifest import default_manifest_paths, write_compiled_manifest, write_scarcity_core_artifacts
    from control_plane.cli.dispatch import _log_run

    if args.toon_command == "sample":
        output = write_scarcity_core_artifacts(CAMELOT_HOME)
    else:
        manifest_paths = [Path(path) for path in args.paths] if args.paths else default_manifest_paths(CAMELOT_HOME)
        output = write_compiled_manifest(
            manifest_paths,
            root=CAMELOT_HOME,
            output_path=Path(args.output),
        )
    _log_run({"payload": output}, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(output, json_mode=args.json, title="TOON")
    return 0 if output.get("status") in {"COMPILED", "WROTE"} else 1


# ---------------------------------------------------------------------------
# glyph
# ---------------------------------------------------------------------------

def _handle_glyph(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.infra.ledger_sync import append_provenance_entry

    try:
        from control_plane.runes.glyph_registry import (
            list_glyphs, load_stack, expand_atom, audit_atom, execute_atom,
        )
    except ImportError:
        list_glyphs = load_stack = expand_atom = audit_atom = execute_atom = None
        _stream_print("glyph_registry module unavailable", tone="err")

    if args.glyph_command == "list":
        output = list_glyphs() if list_glyphs else {"status": "UNAVAILABLE", "error": "glyph_registry module not found"}
    elif args.glyph_command in {"load", "activate"}:
        output = load_stack(args.stack) if load_stack is not None else {"status": "UNAVAILABLE", "error": "glyph_registry module not found"}
        if output.get("status") == "LOADED":
            output["ledger"] = append_provenance_entry(
                title=f"Glyph stack activated: {args.stack}",
                actor="SIR_BORIS (Codex / GPT-5)",
                scope=[
                    "03_VAULT/UKG/THREAD_AUDIT_MAX.toon",
                    "03_VAULT/UKG/glyphs/thread_audit_max.registry.json",
                    ".camelot/active_glyph_stack.json",
                ],
                verification=[f"camelot glyph {args.glyph_command} {args.stack}", "camelot glyph audit"],
                tag="[Omega_GLYPH]",
            )
    elif args.glyph_command == "expand":
        output = expand_atom(args.atom_id) if expand_atom is not None else {"status": "UNAVAILABLE", "error": "glyph_registry module not found"}
    elif args.glyph_command == "audit":
        output = audit_atom(args.atom_id) if audit_atom is not None else {"status": "UNAVAILABLE", "error": "glyph_registry module not found"}
        if output.get("status") == "AUDITED":
            target = args.atom_id or "all"
            output["ledger"] = append_provenance_entry(
                title=f"Glyph audit: {target}",
                actor="SIR_BORIS (Codex / GPT-5)",
                scope=["03_VAULT/UKG/THREAD_AUDIT_MAX.toon", "control_plane/glyph_registry.py"],
                verification=[f"camelot glyph audit {target}".strip()],
                tag="[Omega_GLYPH_AUDIT]",
            )
    else:
        output = execute_atom(args.atom_id, approved=args.approve) if execute_atom is not None else {"status": "UNAVAILABLE", "error": "glyph_registry module not found"}
        if output.get("status") in {"STAGED", "GUARD_REQUIRED"}:
            output["ledger"] = append_provenance_entry(
                title=f"Glyph execute staged: {args.atom_id}",
                actor="SIR_BORIS (Codex / GPT-5)",
                scope=["control_plane/glyph_registry.py", "03_VAULT/UKG/THREAD_AUDIT_MAX.toon"],
                verification=[
                    f"camelot glyph expand {args.atom_id}",
                    f"camelot glyph execute {args.atom_id}{' --approve' if args.approve else ''}",
                ],
                tag="[Omega_GLYPH_EXECUTE]",
            )
        elif output.get("status") == "MOUNTED":
            output["ledger"] = append_provenance_entry(
                title=f"Glyph execute mounted: {args.atom_id}",
                actor="SIR_BORIS (Codex / GPT-5)",
                scope=[
                    "control_plane/glyph_registry.py",
                    "03_VAULT/UKG/THREAD_AUDIT_MAX.toon",
                    "03_VAULT/runtime_state/openviking_context_mount_latest.json",
                    "03_VAULT/UKG/nodes/OpenViking_Context_Mount_UKG.json",
                ],
                verification=[
                    f"camelot glyph expand {args.atom_id}",
                    f"camelot glyph execute {args.atom_id} --approve",
                    "camelot glyph audit 05",
                ],
                tag="[Omega_GLYPH_MOUNT]",
            )
    _emit(output, json_mode=args.json, title="Glyph")
    return 0 if output.get("status") not in {"NOT_FOUND", "MISSING_ARTIFACT"} else 1


# ---------------------------------------------------------------------------
# forge-unify
# ---------------------------------------------------------------------------

def _handle_forge_unify(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.infra.ledger_sync import append_provenance_entry

    try:
        from control_plane.runes.forge_unify import (
            activate_forge_unify, forge_unify_status, select_topology, sentinel_forensic_check,
        )
    except ImportError:
        activate_forge_unify = forge_unify_status = select_topology = sentinel_forensic_check = None
        _stream_print("forge_unify module unavailable", tone="err")

    if args.forge_unify_command == "activate":
        output = activate_forge_unify() if activate_forge_unify else {"status": "UNAVAILABLE", "error": "forge_unify module not found"}
        output["ledger"] = append_provenance_entry(
            title="Forge Unify v400.2 activated",
            actor="SIR_CODEX (Lead Engineer) with Sir Alex and Sir Link",
            scope=[
                "control_plane/forge_unify.py", "control_plane/camelot_cli.py",
                ".hive/context/manifest.json", ".hive/context/routing/tar_router_contract.json",
                ".hive/context/research/paladin_octem_personas.json",
                "03_VAULT/runtime_state/forge_unify_status.json",
            ],
            verification=[
                "camelot --json forge-unify activate", "camelot --json forge-unify status",
                "camelot --json forge-unify route refactor cross dependency upgrade",
                "camelot --json forge-unify forensic-check",
            ],
            tag="[Omega_FORGE_UNIFY]",
        )
    elif args.forge_unify_command == "status":
        output = forge_unify_status() if forge_unify_status is not None else {"status": "UNAVAILABLE", "error": "forge_unify module not found"} if forge_unify_status is not None else {"status": "UNAVAILABLE"}
    elif args.forge_unify_command == "route":
        output = select_topology(" ".join(args.intent)) if select_topology is not None else {"status": "UNAVAILABLE", "error": "forge_unify module not found"} if select_topology is not None else {"status": "UNAVAILABLE"}
    else:
        output = sentinel_forensic_check(refresh_baseline=args.refresh_baseline) if sentinel_forensic_check is not None else {"status": "UNAVAILABLE", "error": "forge_unify module not found"} if sentinel_forensic_check is not None else {"status": "UNAVAILABLE"}
        if output.get("status") in {"TRIGGERED", "BASELINE_CREATED"}:
            output["ledger"] = append_provenance_entry(
                title=f"Sentinel forensic check: {output.get('status')}",
                actor="SIR_CODEX (Lead Engineer) with Sir Sentinel",
                scope=["control_plane/forge_unify.py", "03_VAULT/runtime_state/sentinel_forensic_report_latest.json"],
                verification=["camelot --json forge-unify forensic-check"],
                tag="[Omega_SENTINEL_FORENSIC]",
            )
    _emit(output, json_mode=args.json, title="Forge Unify")
    return 0 if output.get("status") not in {"NOT_ACTIVE"} else 1


# ---------------------------------------------------------------------------
# cloudbrain  (largest — delegates sub-commands to private helpers)
# ---------------------------------------------------------------------------

def _cloudbrain_progress(args: Any) -> None:
    """Emit per-sub-command progress messages for cloudbrain."""
    c = args.cloudbrain_command
    if c == "status":
        _stream_task_progress("cloudbrain status")
    elif c == "config":
        _stream_task_progress("cloudbrain config")
    elif c == "sync":
        _stream_task_progress("cloud brain sync")
    elif c == "queue":
        _stream_task_progress("cloud brain sync queue")
    elif c == "research-health":
        _stream_task_progress("research health")
    elif c == "northstar-health":
        _stream_task_progress("northstar health")
    elif c == "blueprint-health":
        _stream_task_progress("development blueprint health")
    elif c == "precise-health":
        _stream_task_progress("precise mode health")
    elif c == "memory":
        _stream_task_progress("memory recall", constraints=[f"privacy={args.privacy}"])
    elif c == "northstar":
        _stream_task_progress("northstar war room objective", objective=args.objective,
                              constraints=[f"privacy={args.privacy}", f"compute_tier={args.tier}", f"aspect={args.aspect}"])
    elif c == "blueprint":
        _stream_task_progress("development blueprint objective", objective=args.objective,
                              constraints=[f"compute_tier={args.tier}", f"budget_mode={args.budget_mode}"])
    elif c == "eldergod-health":
        _stream_task_progress("elderGod forge health")
    elif c == "health":
        _stream_task_progress("unified health rollup")
    elif c == "eldergod":
        _stream_task_progress("elderGod forge objective", objective=args.objective,
                              constraints=[f"compute_tier={args.tier}"])
    elif c == "precise":
        _stream_task_progress("precise mode objective", objective=args.objective,
                              constraints=[f"compute_tier={args.tier}", f"browser_isolation={args.browser_isolation}"])
    elif c == "research":
        constraints = [f"privacy={args.privacy}", f"compute_tier={args.tier}"]
        if args.allow_remote_sensitive:
            constraints.append("allow_remote_sensitive")
        _stream_task_progress("research investigate objective", objective=args.objective, constraints=constraints)


def _handle_cloudbrain(args: Any, config_mgr: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.cli.notebooklm import _cmd_camelot_notebooklm_login
    from control_plane.cli.dispatch import _log_run
    import control_plane.camelot_cli as _cli_mod

    if args.cloudbrain_command == "notebooklm":
        return _cmd_camelot_notebooklm_login(args)

    if not args.json:
        _cloudbrain_progress(args)

    c = args.cloudbrain_command
    if c == "status":
        output = asyncio.run(_run_task("cloudbrain status"))
    elif c == "config":
        output = _cloudbrain_config(args, config_mgr)
    elif c == "sync":
        extra: dict[str, Any] = {}
        if args.notebook_id:
            extra["notebook_id"] = args.notebook_id
        if args.note_title:
            extra["note_title"] = args.note_title
        if args.summary:
            extra["extra_summary"] = args.summary
        output = asyncio.run(_run_task("cloud brain sync", extra_parameters=extra))
    elif c == "queue":
        from control_plane.infra.cloudbrain_sync import flush_sync_queue
        if args.cloud_queue_command == "status":
            output = _cli_mod.sync_queue_status()
        else:
            output = flush_sync_queue(limit=args.limit or None)
    elif c == "research-health":
        output = asyncio.run(_run_task("research health"))
    elif c == "northstar-health":
        output = asyncio.run(_run_task("northstar health"))
    elif c == "blueprint-health":
        output = asyncio.run(_run_task("development blueprint health"))
    elif c == "precise-health":
        output = asyncio.run(_run_task("precise mode health"))
    elif c == "memory":
        output = asyncio.run(_run_task("memory recall", agent_id=args.agent_id,
                                       constraints=[f"privacy={args.privacy}"]))
    elif c == "northstar":
        if getattr(args, "list_templates", False):
            from control_plane.infra.mission_templates import list_mission_templates
            payload = {"status": "SUCCESS", "templates": [t.model_dump() for t in list_mission_templates()]}
            _log_run(payload, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
            _emit(payload, json_mode=args.json, title="Northstar Mission Templates")
            return 0

        tmpl_name = getattr(args, "template", None)
        objective = args.objective
        aspect = args.aspect
        cartridge = args.cartridge
        tier = args.tier
        isolation = args.browser_isolation

        if tmpl_name:
            from control_plane.infra.mission_templates import resolve_template_parameters
            tmpl_params = resolve_template_parameters(tmpl_name, custom_objective=args.objective)
            if not objective:
                objective = tmpl_params["objective"]
            if aspect == "research" and tmpl_params.get("aspect"):
                aspect = tmpl_params["aspect"]
            if cartridge == "COGNITIVE" and tmpl_params.get("cartridge"):
                cartridge = tmpl_params["cartridge"]
            if tier == "apex" and tmpl_params.get("compute_tier"):
                tier = tmpl_params["compute_tier"]
            if isolation == "team" and tmpl_params.get("browser_isolation"):
                isolation = tmpl_params["browser_isolation"]

        objective = objective or "northstar war room objective"
        constraints = [f"privacy={args.privacy}", f"compute_tier={tier}", f"aspect={aspect}"]
        extra_params = {
            "aspect": aspect,
            "compute_tier": tier,
            "cartridge": cartridge,
            "browser_isolation": isolation,
            "multilogin_enabled": not args.disable_multilogin,
        }
        if tmpl_name:
            extra_params["template"] = tmpl_name

        output = asyncio.run(_run_task("northstar war room objective", agent_id=args.agent_id,
                                       objective=objective, constraints=constraints,
                                       extra_parameters=extra_params))
    elif c == "blueprint":
        if getattr(args, "list_templates", False):
            from control_plane.infra.mission_templates import list_mission_templates
            payload = {"status": "SUCCESS", "templates": [t.model_dump() for t in list_mission_templates()]}
            _log_run(payload, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
            _emit(payload, json_mode=args.json, title="Blueprint Mission Templates")
            return 0

        tmpl_name = getattr(args, "template", None)
        objective = args.objective
        if tmpl_name:
            from control_plane.infra.mission_templates import resolve_template_parameters
            tmpl_params = resolve_template_parameters(tmpl_name, custom_objective=args.objective)
            if not objective:
                objective = tmpl_params["objective"]

        objective = objective or "development blueprint objective"
        constraints = [f"compute_tier={args.tier}", f"budget_mode={args.budget_mode}"]
        extra_params = {
            "compute_tier": args.tier,
            "budget_mode": args.budget_mode,
            "team_size": args.team_size,
            "horizon_days": args.horizon_days,
            "prioritize_local_first": True,
            "multilogin_enabled": not args.disable_multilogin,
        }
        if tmpl_name:
            extra_params["template"] = tmpl_name

        output = asyncio.run(_run_task("development blueprint objective", objective=objective,
                                       constraints=constraints,
                                       extra_parameters=extra_params))
    elif c == "eldergod-health":
        output = asyncio.run(_run_task("elderGod forge health"))
    elif c == "health":
        return _handle_health(args, config_mgr, prov_mgr, argv)
    elif c == "eldergod":
        output = asyncio.run(_run_task("elderGod forge objective", objective=args.objective,
                                       constraints=[f"compute_tier={args.tier}"],
                                       extra_parameters={"compute_tier": args.tier}))
    elif c == "precise":
        profile = config_mgr.get_profile(args.profile)
        tier = args.tier or profile.compute_tier
        isolation = args.browser_isolation or profile.browser_isolation
        output = asyncio.run(_run_task("precise mode objective", objective=args.objective,
                                       constraints=[f"compute_tier={tier}", f"browser_isolation={isolation}"],
                                       extra_parameters={"compute_tier": tier, "browser_isolation": isolation,
                                                         "residential_proxy_enabled": args.enable_residential_proxy or profile.residential_proxy,
                                                         "stealth_enabled": args.enable_stealth or profile.stealth,
                                                         "ephemeral_sessions": args.ephemeral_sessions or profile.ephemeral_sessions,
                                                         "operator_count": args.operator_count, "memory_gb": args.memory_gb}))
    else:  # research (default)
        constraints = [f"privacy={args.privacy}", f"compute_tier={args.tier}"]
        if args.allow_remote_sensitive:
            constraints.append("allow_remote_sensitive")
        output = asyncio.run(_run_task("research investigate objective", agent_id=args.agent_id,
                                       objective=args.objective, constraints=constraints))
    _log_run(output, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(output, json_mode=args.json, title="Cloudbrain")
    return 0


def _cloudbrain_config(args: Any, config_mgr: Any) -> dict[str, Any]:
    """Dispatch cloudbrain config sub-commands."""
    from control_plane.cli.cloudbrain import (
        _audit_cloudbrain_configuration,
        _diagnose_cloud_endpoints,
        _discover_modal_endpoints,
    )
    cc = args.cloud_config_command
    if cc == "show":
        return {"status": "CONFIG_READY", "config_path": str(config_mgr.config_path),
                "endpoints": config_mgr.cloud_endpoint_map()}
    elif cc == "diagnose":
        return _diagnose_cloud_endpoints(config_mgr)
    elif cc == "audit":
        return _audit_cloudbrain_configuration(config_mgr)
    elif cc == "set":
        return {"status": "CONFIG_UPDATED", **config_mgr.set_cloud_endpoint(args.env_var, args.value)}
    elif cc == "clear":
        return {"status": "CONFIG_CLEARED", **config_mgr.set_cloud_endpoint(args.env_var, None)}
    elif cc == "discover":
        return _discover_modal_endpoints(config_mgr=config_mgr, app_name=args.app_name,
                                         environment_name=args.environment, write=args.write)
    else:
        example_path = Path(args.path)
        example_content = (
            "# Camelot-OS cloud endpoint overrides\n"
            "# Copy to .camelot-config.yaml and replace placeholders with real production URLs.\n"
            'cloudbrain_url: "https://replace-me.modal.run"\n'
            'living_notebook_url: "https://notebooklm.google.com/notebook/replace-me"\n'
            'research_agency_url: "https://replace-me.modal.run"\n'
            'research_agency_health_url: "https://replace-me.modal.run"\n'
            'northstar_url: "https://replace-me.modal.run"\n'
            'northstar_health_url: "https://replace-me.modal.run"\n'
            'blueprint_url: "https://replace-me.modal.run"\n'
            'blueprint_health_url: "https://replace-me.modal.run"\n'
            'precise_mode_url: "https://replace-me.modal.run"\n'
            'precise_mode_health_url: "https://replace-me.modal.run"\n'
            'excalibur_bridge_url: "https://replace-me.modal.run"\n'
            'excalibur_health_url: "https://replace-me.modal.run"\n'
        )
        example_path.write_text(example_content, encoding="utf-8")
        return {"status": "CONFIG_TEMPLATE_WRITTEN", "path": str(example_path)}


# ---------------------------------------------------------------------------
# sarda
# ---------------------------------------------------------------------------

def _handle_sarda(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.cli.dispatch import _log_run

    if not args.json:
        _stream_sarda_progress(args.intent, execute=args.execute, context=args.context, privacy=args.privacy)
    output = asyncio.run(_run_sarda(args.intent, execute=args.execute, context=args.context,
                                    privacy=args.privacy, timeout=args.timeout))
    _log_run(output, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(output, json_mode=args.json, title="SARDA")
    return 0


# ---------------------------------------------------------------------------
# team
# ---------------------------------------------------------------------------

def _handle_team(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.cli.dispatch import _log_run

    if args.team_command == "roster":
        from control_plane.core.knight_configuration import write_knight_configuration
        output = write_knight_configuration(CAMELOT_HOME)
        _emit(output, json_mode=args.json, title="Knight Configuration")
        return 0

    if args.team_command == "self-test":
        if args.runtime:
            os.environ["CAMELOT_HARNESS_RUNTIME"] = args.runtime
        if not args.json:
            _progress("analyze", f"team self-test target={args.target} runtime={os.getenv('CAMELOT_HARNESS_RUNTIME', 'auto')}", tone="info")
        output = _run_team_self_test(worker_id=args.target, prompt=args.prompt, timeout=args.timeout)
        _log_run(output, success=output.get("status") == "PASSED", args=args, prov_mgr=prov_mgr, argv=argv)
        _emit(output, json_mode=args.json, title="Team Self-Test")
        if args.require_pass and output.get("status") != "PASSED":
            return 1
        return 0
    return 0


# ---------------------------------------------------------------------------
# cockpit
# ---------------------------------------------------------------------------

def _handle_cockpit(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    import control_plane.camelot_cli as _cli_mod
    from control_plane.infra.cockpit import cockpit_exec, prompt_payload

    cockpit_json_mode = args.json or getattr(args, "cockpit_json", False)
    if args.cockpit_command == "prompt":
        output = prompt_payload()
        if output.get("stale"):
            output = _cli_mod.refresh_snapshot(trigger="prompt")
    elif args.cockpit_command == "refresh":
        output = _cli_mod.refresh_snapshot(trigger="manual")
    elif args.cockpit_command == "exec":
        output = cockpit_exec(" ".join(args.input))
    else:
        if cockpit_json_mode:
            output = {"status": "HANDOFF", "target": "knight-session",
                      "command": [sys.executable, str(CAMELOT_HOME / "bin" / "knight_session.py")]}
        else:
            from bin.knight_session import main as knight_session_main
            knight_session_main()
            return 0
    _emit(output, json_mode=cockpit_json_mode, title="Cockpit")
    return 0 if output.get("status") != "QUEUE_WARN" else 2


# ---------------------------------------------------------------------------
# codex
# ---------------------------------------------------------------------------

def _handle_codex(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.infra.codex_integration import read_codex_status, write_codex_integration
    from control_plane.infra.ledger_sync import append_provenance_entry
    from control_plane.infra.cloudbrain_sync import sync_after_event
    from control_plane.cli.dispatch import _log_run

    if args.codex_command == "status":
        output = read_codex_status(CAMELOT_HOME)
    else:
        output = write_codex_integration(CAMELOT_HOME, actor=args.actor, trigger=args.codex_command)
        ledger = append_provenance_entry(
            title="Codex integrated with Camelot-OS", actor=args.actor,
            scope=["control_plane/codex_integration.py", "control_plane/camelot_cli.py",
                   "control_plane/boot_sequence.py", "02_FORGE/apps/omni-eye-dashboard",
                   "03_VAULT/runtime_state/codex_integration_latest.json"],
            verification=["camelot codex status", "camelot codex integrate",
                          "awaken --quick surfaces Codex Integration"],
            tag="[Omega_CODEX]",
        )
        sync_event = sync_after_event(event_type="codex_integration", command=f"codex {args.codex_command}", results=output)
        output["ledger"] = ledger
        output["cloudbrain_sync"] = sync_event
    _log_run(output, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(output, json_mode=args.json, title="Codex Integration")
    return 0


# ---------------------------------------------------------------------------
# shadow
# ---------------------------------------------------------------------------

def _handle_shadow(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    import importlib.util as _shadow_ilu
    _shadow_spec = _shadow_ilu.spec_from_file_location(
        "shadow_pipeline",
        CAMELOT_HOME / "01_KERNEL/iron_gate/DEFENSE_GRID/shadow_veil/shadow_pipeline.py",
    )
    _shadow_mod = _shadow_ilu.module_from_spec(_shadow_spec)
    sys.modules["shadow_pipeline"] = _shadow_mod
    _shadow_spec.loader.exec_module(_shadow_mod)
    sv = _shadow_mod.ShadowVeil(repo_root=CAMELOT_HOME, hermes_enabled=False)
    if getattr(args, "scan", False):
        st = sv.scan_once()
    else:
        st = sv.status()
    output = {
        "shadow_veil": {
            "heimdall_ok": st.heimdall_ok, "nemesis_ok": st.nemesis_ok, "hermes_ok": st.hermes_ok,
            "vector_count": st.vector_count, "critical_count": st.critical_count,
            "threats_detected": st.threats_detected, "auto_responses": st.auto_responses,
            "hitl_pending": st.hitl_pending, "last_scan_at": st.last_scan_at,
            "last_threat_at": st.last_threat_at, "active": st.active,
        }
    }
    _emit(output, json_mode=args.json, title="Shadow Veil Status")
    return 0


# ---------------------------------------------------------------------------
# bio-swarm
# ---------------------------------------------------------------------------

def _handle_bio_swarm(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    from control_plane.infra.bio_swarm_runtime import (
        preflight_bio_swarm, run_bio_swarm_once, write_bio_swarm_runtime_status,
    )

    bio_json_mode = args.json or getattr(args, "json_output", False)
    if args.bio_swarm_action == "status":
        output = write_bio_swarm_runtime_status()
        success = output.get("status") in {"READY", "READY_NO_STATE"}
    elif args.bio_swarm_action == "preflight":
        output = preflight_bio_swarm()
        success = output.get("status") == "PREFLIGHT_PASS"
    else:
        output = run_bio_swarm_once(queue_path=args.queue, state_path=args.state,
                                    fixture=args.fixture, timeout=args.timeout)
        success = output.get("verdict") == "PASS"
    _emit(output, json_mode=bio_json_mode, title="Bio-Swarm Runtime")
    return 0 if success else 2


# ---------------------------------------------------------------------------
# nano-swarm
# ---------------------------------------------------------------------------

def _handle_nano_swarm(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    from control_plane.infra.nano_swarm_runtime import (
        supervise_nodes as supervise_nano_swarm_nodes,
        write_runtime_status as write_nano_swarm_runtime_status,
    )

    if args.nano_swarm_command == "status":
        output = write_nano_swarm_runtime_status()
        success = bool(output.get("runtime_ready"))
    else:
        output = supervise_nano_swarm_nodes(args.supervise_action, node_name=args.node)
        success = output.get("status") != "SUPERVISOR_ERROR"
    _emit(output, json_mode=args.json, title="Nano Swarm Runtime")
    return 0 if success else 2


# ---------------------------------------------------------------------------
# microcubed
# ---------------------------------------------------------------------------

def _handle_microcubed(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.infra.microcubed import (
        MicrocubedRequest, execute_house, forge_house, inspect_house, plan_house, teardown_house,
    )
    from control_plane.infra.microcubed import status as microcubed_status
    from control_plane.infra.ledger_sync import append_provenance_entry
    from control_plane.cli.dispatch import _log_run

    if args.microcubed_command == "status":
        output = microcubed_status()
        _emit(output, json_mode=args.json, title="Microcubed")
        return 0

    if args.microcubed_command in {"plan", "forge"}:
        request = MicrocubedRequest(
            objective=args.objective, knight=args.knight, tenant=args.tenant,
            house=args.house, timeout_seconds=args.timeout, max_write_mb=args.max_write_mb,
            queue=getattr(args, "queue", False),
        )
        output = plan_house(request) if args.microcubed_command == "plan" else forge_house(request)
        if args.microcubed_command == "forge":
            output["ledger"] = append_provenance_entry(
                title="Microcubed SmolVM house forged", actor="SIR_CODEX + LUKAS_OMEGA",
                scope=["control_plane/microcubed.py", "control_plane/camelot_cli.py",
                       "03_VAULT/runtime_state/microcubed"],
                verification=["camelot microcubed status",
                              "python -m json.tool 03_VAULT/runtime_state/microcubed/microcubed_latest.json"],
                tag="[Omega_KINETIC][MICROCUBED]",
            )
        _log_run(output, success=output.get("status") in {"PLANNED", "READY"}, args=args, prov_mgr=prov_mgr, argv=argv)
        _emit(output, json_mode=args.json, title="Microcubed")
        return 0

    if args.microcubed_command == "inspect":
        output = inspect_house(args.house_id)
        _emit(output, json_mode=args.json, title="Microcubed")
        return 0

    if args.microcubed_command == "execute":
        command_args = list(args.command_args or [])
        if command_args and command_args[0] == "--":
            command_args = command_args[1:]
        if not command_args:
            raise SystemExit("microcubed execute requires a command after --")
        output = execute_house(args.house_id, command_args, timeout_seconds=args.timeout)
        _log_run(output, success=output.get("status") == "COMPLETE", args=args, prov_mgr=prov_mgr, argv=argv)
        _emit(output, json_mode=args.json, title="Microcubed")
        return 0 if output.get("status") == "COMPLETE" else 2

    output = teardown_house(args.house_id, archive=not args.no_archive)
    _log_run(output, success=output.get("status") in {"TORN_DOWN", "MISSING"}, args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(output, json_mode=args.json, title="Microcubed")
    return 0


# ---------------------------------------------------------------------------
# gemini-ext
# ---------------------------------------------------------------------------

def _handle_gemini_ext(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    from control_plane.infra.gemini_extension_registry import (
        inspect_gemini_extension, list_gemini_extensions, summarize_gemini_extensions,
    )

    if args.gemini_ext_command == "status":
        output = summarize_gemini_extensions()
    elif args.gemini_ext_command == "list":
        output = list_gemini_extensions()
    else:
        output = inspect_gemini_extension(args.name)
    _emit(output, json_mode=args.json, title="Gemini Extensions")
    return 0 if output.get("status") != "NOT_FOUND" else 1


# ---------------------------------------------------------------------------
# evolve
# ---------------------------------------------------------------------------

def _handle_evolve(args: Any, _cm: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.infra.hyper_evolve import append_learning, promote_mutation
    from control_plane.cli.dispatch import _log_run

    if not args.json:
        _stream_task_progress("hyper evolve", objective=args.objective,
                              constraints=[f"agent={args.agent}", f"verification_steps={len(args.verification)}"])
    append_learning(agent=args.agent, objective=args.objective, failures=list(args.failures),
                    learning=args.learning, proposal=args.proposal)
    output = promote_mutation(agent=args.agent, objective=args.objective, learning=args.learning,
                              proposal=args.proposal, verification=list(args.verification),
                              scope=list(args.scope), actor=args.actor)
    _log_run(output, success=output.get("status") == "APPROVED", args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(output, json_mode=args.json, title="Hyper Evolve")
    return 0


# ---------------------------------------------------------------------------
# scripts
# ---------------------------------------------------------------------------

def _handle_scripts(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    script_map = {
        "voice-test": ["python", str(CAMELOT_HOME / "scripts" / "voice" / "voice_test_orchestrator.py")],
        "notebook-access": ["python", str(CAMELOT_HOME / "scripts" / "notebooklm" / "access_v999.py")],
        "notebook-check": ["python", str(CAMELOT_HOME / "scripts" / "notebooklm" / "check_notebook.py")],
        "notebook-query": ["python", str(CAMELOT_HOME / "scripts" / "notebooklm" / "query_notebook.py")],
        "forge-omnicrystal": ["python", str(CAMELOT_HOME / "02_FORGE" / "forge_omnicrystal.py")],
        "start-gateway": ["powershell", "-ExecutionPolicy", "Bypass", "-File",
                          str(CAMELOT_HOME / "05_INFRASTRUCTURE" / "gateways" / "start_clawdbot_gateway.ps1")],
        "stop-gateway": ["powershell", "-ExecutionPolicy", "Bypass", "-File",
                         str(CAMELOT_HOME / "05_INFRASTRUCTURE" / "gateways" / "stop_clawdbot_gateway.ps1")],
    }
    cmd = script_map.get(args.scripts_command)
    if cmd:
        if not args.json:
            _stream_print(f"Running integrated script: {args.scripts_command}...", tone="info")
        subprocess.run(cmd)
    return 0


# ---------------------------------------------------------------------------
# ctx7
# ---------------------------------------------------------------------------

def _handle_ctx7(args: Any, _cm: Any, _pm: Any, _argv: list[str]) -> int:
    if args.setup:
        _stream_print(f"Executing ctx7 automated setup for: {args.report}", tone="accent")
    else:
        _stream_print(f"Analyzing Context 7 report: {args.report}", tone="info")
    return 0


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------

def _handle_pipeline(args: Any, config_mgr: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.cli.pipeline_cmd import handle_pipeline
    return handle_pipeline(args, config_mgr, prov_mgr, argv)


# ---------------------------------------------------------------------------
# health (Track B5)
# ---------------------------------------------------------------------------

def _handle_health(args: Any, config_mgr: Any, prov_mgr: Any, argv: list[str]) -> int:
    """Handle the 'camelot health' command (Track B5)."""
    from control_plane.infra.cloud_services import CloudServiceRequest, CloudServiceName, CloudServiceRouter

    router = CloudServiceRouter()
    probe_remote = getattr(args, "probe_remote", True)

    if not getattr(args, "json", False):
        _stream_print("Probing Camelot ecosystem health rollup...", tone="info")

    result = asyncio.run(router.invoke(CloudServiceRequest(
        service=CloudServiceName.HEALTH_ROLLUP,
        payload={"probe_remote": probe_remote},
    )))

    if getattr(args, "json", False):
        _print_json(result.model_dump())
        return 0 if result.success else 1

    data = result.result
    overall = data.get("overall_status", "UNKNOWN")
    score_pct = data.get("score_pct", 0.0)
    healthy_count = data.get("healthy_count", 0)
    total_count = data.get("total_count", 0)
    fallback_count = data.get("fallback_count", 0)
    subsystems = data.get("subsystems", {})
    contract = data.get("deployment_contract", {})
    cb = data.get("circuit_breaker", {})

    tone = "accent" if overall == "HEALTHY" else ("warn" if overall == "DEGRADED" else "err")
    _stream_print("==================================================================", tone="accent")
    _stream_print(f"CAMELOT-OS UNIFIED HEALTH ROLLUP  [{overall}]  {score_pct}% READY", tone=tone)
    _stream_print(f"   Healthy: {healthy_count}/{total_count} subsystems | Active Fallbacks: {fallback_count}", tone="info")
    _stream_print("==================================================================", tone="accent")

    _stream_print(f"{'Subsystem':<20} {'Status':<10} {'Source':<15} {'Details'}", tone="info")
    _stream_print("-" * 66, tone="dim")
    for name, sub in subsystems.items():
        status = sub.get("status", "UNKNOWN")
        source = sub.get("source", "unknown")
        summary = str(sub.get("summary") or sub.get("error") or "OK")[:30]
        s_tone = "accent" if status == "ONLINE" else ("warn" if status == "FALLBACK" else "err")
        _stream_print(f"{name:<20} {status:<10} {source:<15} {summary}", tone=s_tone)

    _stream_print("-" * 66, tone="dim")
    contract_status = contract.get("status", "UNKNOWN")
    c_tone = "accent" if contract_status == "PASS" else ("warn" if contract_status == "WARN" else "err")
    _stream_print(f"Deployment Contract: [{contract_status}] {contract.get('summary', '')}", tone=c_tone)

    if getattr(args, "verbose", False):
        _stream_print("\nCircuit Breaker Status:", tone="info")
        if cb:
            for k, v in cb.items():
                is_open = v.get("circuit_open", False)
                cb_tone = "err" if is_open else "info"
                _stream_print(f"  - {k}: {'OPEN' if is_open else 'CLOSED'} (failures={v.get('consecutive_failures', 0)})", tone=cb_tone)
        else:
            _stream_print("  - All circuits CLOSED (0 failures)", tone="accent")

    return 0 if result.success else 1


def _handle_templates(args: Any, _config_mgr: Any, prov_mgr: Any, argv: list[str]) -> int:
    from control_plane.infra.mission_templates import (
        list_mission_templates,
        get_mission_template,
    )
    from control_plane.cli.dispatch import _log_run

    name = getattr(args, "name", None)
    if name:
        tmpl = get_mission_template(name)
        if not tmpl:
            _stream_print(f"Error: Unknown template '{name}'", tone="err")
            return 1
        payload = {"status": "SUCCESS", "template": tmpl.model_dump()}
    else:
        payload = {
            "status": "SUCCESS",
            "templates": [t.model_dump() for t in list_mission_templates()],
        }

    _log_run(payload, success=True, args=args, prov_mgr=prov_mgr, argv=argv)
    _emit(payload, json_mode=args.json, title="Canonical Mission Templates (Track C4)")
    return 0


# ===========================================================================
# COMMAND REGISTRY
# ===========================================================================

COMMAND_REGISTRY: dict[str, HandlerFn] = {
    "chat": _handle_chat,
    "route": _handle_route,
    "triage": _handle_triage,
    "orchestrator": _handle_orchestrator,
    "hermes": _handle_hermes,
    "bifrost": _handle_bifrost,
    "contracts": _handle_contracts,
    "ledger": _handle_ledger,
    "toon": _handle_toon,
    "glyph": _handle_glyph,
    "forge-unify": _handle_forge_unify,
    "cloudbrain": _handle_cloudbrain,
    "sarda": _handle_sarda,
    "team": _handle_team,
    "cockpit": _handle_cockpit,
    "codex": _handle_codex,
    "shadow": _handle_shadow,
    "bio-swarm": _handle_bio_swarm,
    "nano-swarm": _handle_nano_swarm,
    "microcubed": _handle_microcubed,
    "gemini-ext": _handle_gemini_ext,
    "evolve": _handle_evolve,
    "scripts": _handle_scripts,
    "ctx7": _handle_ctx7,
    "pipeline": _handle_pipeline,
    "health": _handle_health,
    "templates": _handle_templates,
}
