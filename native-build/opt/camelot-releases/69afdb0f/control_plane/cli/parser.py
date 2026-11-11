# SPDX-License-Identifier: MIT

"""Argparse builder — all subcommand definitions for the Camelot-OS CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from control_plane.cli.constants import CAMELOT_HOME
from control_plane.infra.codex_integration import DEFAULT_ACTOR as CODEX_DEFAULT_ACTOR


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Camelot-OS",
        description="Camelot-OS prompt-first CLI for routing, cloudbrain, and SARDA.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--profile", help="Use a specific operator profile")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable HITL prompts; block risky intents without asking",
    )

    sub = parser.add_subparsers(dest="command")

    chat_parser = sub.add_parser("chat", help="Start interactive mode")
    chat_parser.add_argument("--json", action="store_true", help="Emit JSON output")
    chat_parser.add_argument("--provider", help="Pin provider for session")
    chat_parser.add_argument("--llm", "--model", dest="llm", help="Pin model for session")
    chat_parser.add_argument("--verbose", "-v", action="store_true", help="Show full telemetry routing output")

    route_parser = sub.add_parser("route", help="Show routing decision for an intent")
    route_parser.add_argument("intent", nargs="+")

    triage = sub.add_parser("triage", help="Run evidence-gated read-only system validation")
    triage_mode = triage.add_mutually_exclusive_group()
    triage_mode.add_argument("--rapid", action="store_true", help="Run only the fail-fast validation stage")
    triage_mode.add_argument("--deep", action="store_true", help="Run rapid and deep validation stages")
    triage.add_argument(
        "--force-deep",
        action="store_true",
        help="Run deep checks even when the rapid stage is blocked",
    )
    triage.add_argument("--json", dest="triage_json", action="store_true", help="Emit JSON output")
    triage.add_argument(
        "--no-reports",
        action="store_true",
        help="Do not write JSON and Markdown evidence reports",
    )
    triage.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Default per-command timeout in seconds",
    )

    orchestrator = sub.add_parser("orchestrator", help="Run the Rust orchestration CLI")
    orchestrator.add_argument(
        "--mode",
        choices=("boot", "status", "knights", "triage", "persona", "notify", "awaken", "conversation"),
        default="status",
        help="Rust orchestration mode to run",
    )
    orchestrator.add_argument("--root", default=".", help="Root directory for triage mode")
    orchestrator.add_argument("--older-than-days", type=int, default=60)
    orchestrator.add_argument("--large-file-mb", type=float, default=50.0)
    orchestrator.add_argument("--intent", default="refactor the backend control plane")
    orchestrator.add_argument("--message", default="Camelot orchestration event")
    orchestrator.add_argument("--kind", default="startup")
    orchestrator.add_argument("--status", default="green")
    orchestrator.add_argument("--json", action="store_true", help="Emit JSON output")

    hermes = sub.add_parser("hermes", help="Show VPS Hermes_Prime and Bifrost bridge status")
    hermes.add_argument("--json", action="store_true", help="Emit JSON output")
    hermes.add_argument(
        "--probe-live",
        dest="probe_live",
        action="store_true",
        default=False,
        help="Run read-only TCP probes against VPS bridge ports",
    )
    hermes.add_argument(
        "--no-probe",
        dest="probe_live",
        action="store_false",
        help="Skip live probes and show configured contract only",
    )

    bifrost = sub.add_parser("bifrost", help="Preview Bifrost routing and validate local model policy")
    bifrost_sub = bifrost.add_subparsers(dest="bifrost_command", required=True)
    bifrost_route = bifrost_sub.add_parser("route", help="Preview a route without invoking a model")
    bifrost_route.add_argument("intent", nargs="+")
    bifrost_route.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit JSON output")
    bifrost_status = bifrost_sub.add_parser("status", help="Show configured or probed Bifrost status")
    bifrost_status.add_argument("--probe", action="store_true", help="Run a read-only gateway health probe")
    bifrost_status.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit JSON output")
    bifrost_validate = bifrost_sub.add_parser("validate", help="Validate the local model manifest policy")
    bifrost_validate.add_argument("path", nargs="?", default=None)
    bifrost_validate.add_argument("--registry", default=None, help="Optional Bifrost registry path")
    bifrost_validate.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit JSON output")

    contracts = sub.add_parser("contracts", help="Validate canonical contract schemas")
    contracts_sub = contracts.add_subparsers(dest="contracts_command", required=True)
    contracts_validate = contracts_sub.add_parser("validate", help="Validate the contract schema catalog")
    contracts_validate.add_argument("path", nargs="?", default=None)
    contracts_validate.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit JSON output")

    ledger = sub.add_parser("ledger", help="Update and sync repository-side ledgers")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    ledger_sub.add_parser("status", help="Show repository ledger status")
    ledger_sub.add_parser("audit", help="Run forensic SHA-256 integrity check on the verification ledger")
    ledger_sub.add_parser("reconcile", help="Copy root provenance ledger to all mirror ledgers")
    ledger_sync = ledger_sub.add_parser("sync", help="Sync ledger state to the local kernel")
    ledger_sync.add_argument(
        "--intent",
        default="Sync repository ledger state to UKG_Vault",
        help="Sync intent to send to the local kernel",
    )
    ledger_update = ledger_sub.add_parser("update", help="Append a provenance ledger entry")
    ledger_update.add_argument("--title", required=True)
    ledger_update.add_argument("--actor", default="SIR_BORIS (Codex / GPT-5)")
    ledger_update.add_argument("--tag", default="[Omega_SYNC]")
    ledger_update.add_argument("--scope", action="append", required=True)
    ledger_update.add_argument("--verification", action="append", required=True)

    toon = sub.add_parser("toon", help="Compile Camelot manifests into TOON payloads")
    toon_sub = toon.add_subparsers(dest="toon_command", required=True)
    toon_compile = toon_sub.add_parser("compile", help="Compile JSON/YAML manifests into one redacted TOON artifact")
    toon_compile.add_argument("paths", nargs="*", help="Manifest paths to compile. Defaults to core Camelot manifests.")
    toon_compile.add_argument(
        "--output",
        default=str(CAMELOT_HOME / "03_VAULT" / "runtime_state" / "camelot_compiled.toon"),
        help="TOON output path",
    )
    toon_sub.add_parser("sample", help="Write the proposed 4GB scarcity-core camelot.toon artifact")

    glyph = sub.add_parser("glyph", help="Manage guarded UKG glyph stacks")
    glyph_sub = glyph.add_subparsers(dest="glyph_command", required=True)
    glyph_sub.add_parser("list", help="List registered glyph atoms")
    glyph_load = glyph_sub.add_parser("load", help="Load a glyph stack into the active registry")
    glyph_load.add_argument("stack", nargs="?", default="thread_audit_max")
    glyph_activate = glyph_sub.add_parser("activate", help="Alias for loading a glyph stack into the active registry")
    glyph_activate.add_argument("stack", nargs="?", default="thread_audit_max")
    glyph_expand = glyph_sub.add_parser("expand", help="Expand one glyph atom without side effects")
    glyph_expand.add_argument("atom_id")
    glyph_audit = glyph_sub.add_parser("audit", help="Audit all atoms or one atom")
    glyph_audit.add_argument("atom_id", nargs="?")
    glyph_execute = glyph_sub.add_parser("execute", help="Stage an approved glyph atom execution")
    glyph_execute.add_argument("atom_id")
    glyph_execute.add_argument(
        "--approve",
        action="store_true",
        help="Record an approved staged execution. Does not enable mutation.",
    )

    forge_unify = sub.add_parser("forge-unify", help="Manage the v400.2 Forge Unify runtime contract")
    forge_unify_sub = forge_unify.add_subparsers(dest="forge_unify_command", required=True)
    forge_unify_sub.add_parser("activate", help="Activate FS context, TAR, Octem, and Sentinel hook manifests")
    forge_unify_sub.add_parser("status", help="Show Forge Unify status and run a Sentinel forensic check")
    forge_route = forge_unify_sub.add_parser("route", help="Select a topology for an intent")
    forge_route.add_argument("intent", nargs="+")
    forge_forensic = forge_unify_sub.add_parser("forensic-check", help="Run the Sir Sentinel integrity check")
    forge_forensic.add_argument("--refresh-baseline", action="store_true")

    cloudbrain = sub.add_parser("cloudbrain", help="Invoke cloudbrain services")
    cloud_sub = cloudbrain.add_subparsers(dest="cloudbrain_command", required=True)
    cloud_sub.add_parser("status", help="Show cloudbrain status")
    cloud_config = cloud_sub.add_parser("config", help="Show or persist cloud endpoint configuration")
    cloud_config_sub = cloud_config.add_subparsers(dest="cloud_config_command", required=True)
    cloud_config_sub.add_parser("show", help="Show the effective cloud endpoint map")
    cloud_config_sub.add_parser("diagnose", help="Diagnose endpoint inference and override state")
    cloud_config_sub.add_parser("audit", help="Audit Cloud Brain, Warp, and ledger sync configuration")
    cloud_config_set = cloud_config_sub.add_parser("set", help="Persist a cloud endpoint override")
    cloud_config_set.add_argument(
        "env_var",
        choices=(
            "CAMELOT_CLOUDBRAIN_URL",
            "CAMELOT_LIVING_NOTEBOOK_URL",
            "CAMELOT_RESEARCH_AGENCY_URL",
            "CAMELOT_RESEARCH_AGENCY_HEALTH_URL",
            "CAMELOT_NORTHSTAR_URL",
            "CAMELOT_NORTHSTAR_HEALTH_URL",
            "CAMELOT_BLUEPRINT_URL",
            "CAMELOT_BLUEPRINT_HEALTH_URL",
            "CAMELOT_PRECISE_MODE_URL",
            "CAMELOT_PRECISE_MODE_HEALTH_URL",
            "CAMELOT_EXCALIBUR_BRIDGE_URL",
            "CAMELOT_EXCALIBUR_HEALTH_URL",
        ),
    )
    cloud_config_set.add_argument("value", help="Absolute URL for the endpoint override")
    cloud_config_clear = cloud_config_sub.add_parser("clear", help="Remove a persisted cloud endpoint override")
    cloud_config_clear.add_argument(
        "env_var",
        choices=(
            "CAMELOT_CLOUDBRAIN_URL",
            "CAMELOT_LIVING_NOTEBOOK_URL",
            "CAMELOT_RESEARCH_AGENCY_URL",
            "CAMELOT_RESEARCH_AGENCY_HEALTH_URL",
            "CAMELOT_NORTHSTAR_URL",
            "CAMELOT_NORTHSTAR_HEALTH_URL",
            "CAMELOT_BLUEPRINT_URL",
            "CAMELOT_BLUEPRINT_HEALTH_URL",
            "CAMELOT_PRECISE_MODE_URL",
            "CAMELOT_PRECISE_MODE_HEALTH_URL",
            "CAMELOT_EXCALIBUR_BRIDGE_URL",
            "CAMELOT_EXCALIBUR_HEALTH_URL",
        ),
    )
    cloud_config_discover = cloud_config_sub.add_parser(
        "discover",
        help="Discover deployed Modal web endpoint URLs via Modal SDK",
    )
    cloud_config_discover.add_argument("--app-name", required=True, help="Deployed Modal app name")
    cloud_config_discover.add_argument(
        "--environment",
        default="main",
        help="Modal environment name to query",
    )
    cloud_config_discover.add_argument(
        "--write",
        action="store_true",
        help="Persist discovered URLs into .camelot-config.yaml",
    )
    cloud_config_example = cloud_config_sub.add_parser("write-example", help="Write a cloud config example file")
    cloud_config_example.add_argument(
        "--path",
        default=".camelot-config.yaml.example",
        help="Destination path for the example config file",
    )
    cloud_sync = cloud_sub.add_parser("sync", help="Sync local Camelot state into the canonical Cloud Brain notebook")
    cloud_sync.add_argument("--notebook-id", default="")
    cloud_sync.add_argument("--note-title", default="")
    cloud_sync.add_argument("--summary", default="")
    cloud_queue = cloud_sub.add_parser("queue", help="Inspect or flush queued Cloud Brain sync events")
    cloud_queue_sub = cloud_queue.add_subparsers(dest="cloud_queue_command", required=True)
    cloud_queue_sub.add_parser("status", help="Show queued Cloud Brain sync events")
    cloud_queue_flush = cloud_queue_sub.add_parser("flush", help="Retry queued Cloud Brain sync events")
    cloud_queue_flush.add_argument("--limit", type=int, default=0, help="Maximum events to retry; 0 means all")
    p_res_health = cloud_sub.add_parser("research-health", help="Show research agency health")
    p_res_health.add_argument("--json", action="store_true", help="Emit JSON output")
    p_ns_health = cloud_sub.add_parser("northstar-health", help="Show Northstar war-room health")
    p_ns_health.add_argument("--json", action="store_true", help="Emit JSON output")
    p_bp_health = cloud_sub.add_parser("blueprint-health", help="Show development blueprint health")
    p_bp_health.add_argument("--json", action="store_true", help="Emit JSON output")
    p_pm_health = cloud_sub.add_parser("precise-health", help="Show precise-mode swarm health")
    p_pm_health.add_argument("--json", action="store_true", help="Emit JSON output")
    p_eg_health = cloud_sub.add_parser("eldergod-health", help="Show elderGod forge health")
    p_eg_health.add_argument("--json", action="store_true", help="Emit JSON output")
    cloud_health = cloud_sub.add_parser("health", help="Unified health aggregation rolling up cloudbrain, research, northstar, blueprint, precise-mode, and eldergod readiness")
    cloud_health.add_argument("--json", action="store_true", help="Emit JSON output")
    cloud_health.add_argument("--no-probe-remote", dest="probe_remote", action="store_false", default=True, help="Skip remote network probes")

    cloud_nb = cloud_sub.add_parser("notebooklm", help="Manage NotebookLM auth state (Google sign-in)")
    cloud_nb_sub = cloud_nb.add_subparsers(dest="cloud_nb_command", required=True)
    cloud_nb_login = cloud_nb_sub.add_parser("login", help="Headed interactive Google sign-in to NotebookLM via Playwright Chromium")
    cloud_nb_login.add_argument("--headless", action="store_true", help="Run Chromium without UI (usually blocks Google auth)")
    cloud_nb_login.add_argument("--timeout", type=int, default=300, help="Interactive login timeout in seconds")
    cloud_nb_login.add_argument("--dry-run", action="store_true", help="Skip actually writing storage_state.json")
    cloud_nb_login.add_argument(
        "--state-path",
        default=str(Path.home() / ".notebooklm" / "storage_state.json"),
        help="Target cookie/origin JSON path",
    )

    memory = cloud_sub.add_parser("memory", help="Recall long-term memory")
    memory.add_argument("--agent-id", default="merlin")
    memory.add_argument("--privacy", type=float, default=0.0)

    eldergod = cloud_sub.add_parser("eldergod", help="Invoke the elderGod forge")
    eldergod.add_argument("objective")
    eldergod.add_argument("--tier", choices=("kinetic", "hybrid", "apex"), default="apex")

    research = cloud_sub.add_parser("research", help="Invoke research agency")
    research.add_argument("objective")
    research.add_argument("--agent-id", default="lady_apis")
    research.add_argument("--privacy", type=float, default=0.0)
    research.add_argument("--tier", choices=("kinetic", "hybrid", "apex"), default="hybrid")
    research.add_argument("--allow-remote-sensitive", action="store_true")

    northstar = cloud_sub.add_parser("northstar", help="Run Northstar war-room planning")
    northstar.add_argument("objective", nargs="?", default=None, help="Mission objective or target statement")
    northstar.add_argument(
        "--aspect",
        choices=("research", "architecture", "audit", "operations", "growth"),
        default="research",
    )
    northstar.add_argument("--agent-id", default="northstar")
    northstar.add_argument("--privacy", type=float, default=0.0)
    northstar.add_argument("--tier", choices=("kinetic", "hybrid", "apex"), default="apex")
    northstar.add_argument(
        "--cartridge",
        choices=("ANT", "BEAVER", "HAWK", "SPIDER", "COGNITIVE", "ORACLE"),
        default="COGNITIVE",
    )
    northstar.add_argument(
        "--browser-isolation",
        choices=("stealth", "team", "agency"),
        default="team",
    )
    northstar.add_argument("--disable-multilogin", action="store_true")
    northstar.add_argument(
        "--template",
        choices=("research", "architecture", "audit", "operations", "growth"),
        default=None,
        help="Canonical mission template preset (Tracks C4, C5)",
    )
    northstar.add_argument(
        "--list-templates",
        action="store_true",
        help="List available canonical mission templates",
    )
    northstar.add_argument("--json", action="store_true", help="Emit JSON output")

    blueprint = cloud_sub.add_parser("blueprint", help="Generate efficient development blueprint")
    blueprint.add_argument("objective", nargs="?", default=None, help="Blueprint objective statement")
    blueprint.add_argument("--tier", choices=("kinetic", "hybrid", "apex"), default="kinetic")
    blueprint.add_argument("--budget-mode", choices=("lean", "balanced", "aggressive"), default="lean")
    blueprint.add_argument("--team-size", type=int, default=1)
    blueprint.add_argument("--horizon-days", type=int, default=30)
    blueprint.add_argument("--disable-multilogin", action="store_true")
    blueprint.add_argument(
        "--template",
        choices=("research", "architecture", "audit", "operations", "growth"),
        default=None,
        help="Apply canonical mission template context",
    )
    blueprint.add_argument(
        "--list-templates",
        action="store_true",
        help="List available canonical mission templates",
    )
    blueprint.add_argument("--json", action="store_true", help="Emit JSON output")

    precise = cloud_sub.add_parser("precise", help="Plan precise-mode Nano-Knight browser swarm")
    precise.add_argument("objective")
    precise.add_argument("--tier", choices=("kinetic", "hybrid", "apex"), default=None)
    precise.add_argument("--browser-isolation", choices=("stealth", "team", "agency"), default=None)
    precise.add_argument("--operator-count", type=int, default=1)
    precise.add_argument("--memory-gb", type=int, default=8)
    precise.add_argument("--enable-residential-proxy", action="store_true", help="Enable residential proxy (Direct by default)")
    precise.add_argument("--enable-stealth", action="store_true", help="Enable stealth injection")
    precise.add_argument("--ephemeral-sessions", action="store_true", help="Use ephemeral sessions (Persistent by default)")

    sarda = sub.add_parser("sarda", help="Plan or execute SARDA")
    sarda.add_argument("intent")
    sarda.add_argument("--execute", action="store_true")
    sarda.add_argument("--context", default="")
    sarda.add_argument("--privacy", type=float, default=0.0)
    sarda.add_argument("--timeout", type=int, default=120)

    team = sub.add_parser("team", help="OMC team operations")
    team_sub = team.add_subparsers(dest="team_command", required=True)
    team_sub.add_parser("roster", help="Refresh and show knight cartridges, configuration, and roster")
    team_self_test = team_sub.add_parser("self-test", help="Run harness dispatch self-test")
    team_self_test.add_argument(
        "--target",
        default="harness_codex",
        help="Dispatch target ID (sir_* or harness_* or harness:<name>)",
    )
    team_self_test.add_argument(
        "--prompt",
        default="codex",
        help="Safe probe prompt",
    )
    team_self_test.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Collection timeout in seconds",
    )
    team_self_test.add_argument(
        "--runtime",
        choices=("auto", "go", "rust", "python"),
        default=None,
        help="Override CAMELOT_HARNESS_RUNTIME for this test invocation",
    )
    team_self_test.add_argument(
        "--require-pass",
        action="store_true",
        help="Exit non-zero when self-test fails",
    )

    cockpit = sub.add_parser("cockpit", help="Warp-first truthful shell overlay helpers")
    cockpit_sub = cockpit.add_subparsers(dest="cockpit_command", required=True)
    cockpit_prompt = cockpit_sub.add_parser("prompt", help="Return the cached prompt/header payload")
    cockpit_prompt.add_argument("--json", dest="cockpit_json", action="store_true", help="Emit JSON output")
    cockpit_exec_parser = cockpit_sub.add_parser("exec", help="Route runic input without replacing the shell")
    cockpit_exec_parser.add_argument("input", nargs="+", help="Runic input such as //STATUS or Omega_STATUS")
    cockpit_exec_parser.add_argument("--json", dest="cockpit_json", action="store_true", help="Emit JSON output")
    cockpit_refresh = cockpit_sub.add_parser("refresh", help="Refresh the cached cockpit snapshot")
    cockpit_refresh.add_argument("--json", dest="cockpit_json", action="store_true", help="Emit JSON output")
    cockpit_chat = cockpit_sub.add_parser("chat", help="Escape hatch into knight-session")
    cockpit_chat.add_argument("--json", dest="cockpit_json", action="store_true", help="Emit JSON output")

    codex = sub.add_parser("codex", help="Manage Codex integration with Camelot-OS")
    codex_sub = codex.add_subparsers(dest="codex_command", required=True)
    codex_sub.add_parser("status", help="Show the Codex integration artifact")
    codex_integrate = codex_sub.add_parser("integrate", help="Write artifact, ledger, and Cloud Brain sync hook")
    codex_integrate.add_argument("--actor", default=CODEX_DEFAULT_ACTOR)
    codex_sync = codex_sub.add_parser("sync", help="Refresh Codex artifact and trigger Cloud Brain sync")
    codex_sync.add_argument("--actor", default=CODEX_DEFAULT_ACTOR)

    shadow = sub.add_parser("shadow", help="Shadow Veil — fingerprint-less defense pipeline status")
    shadow_sub = shadow.add_subparsers(dest="shadow_command", required=True)
    shadow_status_p = shadow_sub.add_parser("status", help="Show Shadow Veil pipeline status")
    shadow_status_p.add_argument("--scan", action="store_true", help="Run a live Heimdall scan before reporting")

    nano_swarm = sub.add_parser("nano-swarm", help="Inspect promoted UKG nano-swarm runtime state")
    nano_swarm_sub = nano_swarm.add_subparsers(dest="nano_swarm_command", required=True)
    nano_swarm_sub.add_parser("status", help="Refresh and show promoted nano-swarm runtime status")
    nano_supervise = nano_swarm_sub.add_parser("supervise", help="Manage promoted nano-swarm service processes")
    nano_supervise.add_argument("supervise_action", choices=("status", "start", "stop", "restart"))
    nano_supervise.add_argument("--node", default=None, help="Limit action to one node")

    bio_swarm = sub.add_parser("bio-swarm", help="Inspect and verify the Bio-Swarm Rust spawner")
    bio_swarm_sub = bio_swarm.add_subparsers(dest="bio_swarm_action", required=True)
    bio_status = bio_swarm_sub.add_parser("status", help="Persist and show Bio-Swarm runtime status")
    bio_status.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output")
    bio_preflight = bio_swarm_sub.add_parser("preflight", help="Check Bio-Swarm binary and evidence paths")
    bio_preflight.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output")
    bio_once = bio_swarm_sub.add_parser("once", help="Run one deterministic Bio-Swarm queue pass")
    bio_once.add_argument("--queue", default=None, help="Queue JSONL path")
    bio_once.add_argument("--state", default=None, help="Runtime state JSON path")
    bio_once.add_argument("--fixture", action="store_true", help="Write a deterministic queue fixture before running")
    bio_once.add_argument("--timeout", type=int, default=30, help="Spawner timeout in seconds")
    bio_once.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output")

    microcubed = sub.add_parser("microcubed", help="Manage Microcubed SmolVM knight task houses")
    microcubed_sub = microcubed.add_subparsers(dest="microcubed_command", required=True)
    microcubed_sub.add_parser("status", help="Show Microcubed houses and latest contract")
    micro_plan = microcubed_sub.add_parser("plan", help="Render a Microcubed task-house contract without writing it")
    micro_plan.add_argument("objective")
    micro_plan.add_argument("--knight", default="sir_forge")
    micro_plan.add_argument("--tenant", default=None)
    micro_plan.add_argument("--house", default=None)
    micro_plan.add_argument("--timeout", type=int, default=900)
    micro_plan.add_argument("--max-write-mb", type=int, default=25)
    micro_forge = microcubed_sub.add_parser("forge", help="Forge an isolated Microcubed house for a knight task")
    micro_forge.add_argument("objective")
    micro_forge.add_argument("--knight", default="sir_forge")
    micro_forge.add_argument("--tenant", default=None)
    micro_forge.add_argument("--house", default=None)
    micro_forge.add_argument("--timeout", type=int, default=900)
    micro_forge.add_argument("--max-write-mb", type=int, default=25)
    micro_forge.add_argument("--queue", action="store_true", help="Append a queue directive for the tenant knight")
    micro_inspect = microcubed_sub.add_parser("inspect", help="Inspect a Microcubed house contract, manifest, and latest output")
    micro_inspect.add_argument("house_id")
    micro_execute = microcubed_sub.add_parser(
        "execute",
        help="Run a command inside a Microcubed house workspace after Sentinel preflight",
    )
    micro_execute.add_argument("house_id")
    micro_execute.add_argument("command_args", nargs=argparse.REMAINDER)
    micro_execute.add_argument("--timeout", type=int, default=None)
    micro_teardown = microcubed_sub.add_parser("teardown", help="Archive and remove a Microcubed house")
    micro_teardown.add_argument("house_id")
    micro_teardown.add_argument("--no-archive", action="store_true")

    gemini_ext = sub.add_parser("gemini-ext", help="Inspect Gemini CLI extension adapters")
    gemini_ext_sub = gemini_ext.add_subparsers(dest="gemini_ext_command", required=True)
    gemini_ext_sub.add_parser("status", help="Summarize Gemini extension adapter state")
    gemini_ext_sub.add_parser("list", help="List Gemini extensions and adapter metadata")
    gemini_ext_inspect = gemini_ext_sub.add_parser("inspect", help="Inspect one Gemini extension")
    gemini_ext_inspect.add_argument("name")

    evolve = sub.add_parser("evolve", help="Record learnings and promote guarded swarm mutations")
    evolve.add_argument("--agent", required=True, help="Knight or subsystem proposing the mutation")
    evolve.add_argument("--objective", required=True, help="Objective that produced the learning")
    evolve.add_argument(
        "--failure",
        action="append",
        dest="failures",
        required=True,
        help="Observed failure or friction point. Repeat for multiple entries.",
    )
    evolve.add_argument("--learning", required=True, help="Condensed lesson extracted from the run")
    evolve.add_argument("--proposal", required=True, help="Concrete rule to promote into the shared registry")
    evolve.add_argument(
        "--verification",
        action="append",
        required=True,
        help="Verification step executed before promotion. Repeat for multiple entries.",
    )
    evolve.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Files or modules affected by the proposed mutation.",
    )
    evolve.add_argument(
        "--actor",
        default="SIR_BORIS (Codex / GPT-5)",
        help="Actor recorded in the provenance ledger.",
    )

    scripts = sub.add_parser("scripts", help="Manage and run integrated scripts")
    scripts_sub = scripts.add_subparsers(dest="scripts_command", required=True)
    scripts_sub.add_parser("voice-test", help="Run the voice test orchestrator")
    scripts_sub.add_parser("notebook-access", help="Run access_v700.py script")
    scripts_sub.add_parser("notebook-check", help="Run check_notebook.py script")
    scripts_sub.add_parser("notebook-query", help="Run query_notebook.py script")
    scripts_sub.add_parser("forge-omnicrystal", help="Run forge_omnicrystal.py script")
    scripts_sub.add_parser("start-gateway", help="Run start_clawdbot_gateway.ps1 script")
    scripts_sub.add_parser("stop-gateway", help="Run stop_clawdbot_gateway.ps1 script")

    p_ctx7 = sub.add_parser("ctx7", help="Context 7 Forensic Report Processor")
    p_ctx7.add_argument("report", help="Path to the sentinel forensic report (.json)")
    p_ctx7.add_argument("--setup", action="store_true", help="Execute automated setup based on report")

    pipeline = sub.add_parser("pipeline", help="Sovereign End-to-End Execution Pipeline (Zero-Trust Lifecycle)")
    pipeline_sub = pipeline.add_subparsers(dest="pipeline_command", required=True)

    pipeline_run = pipeline_sub.add_parser("run", help="Submit and execute a task manifest through all 6 stages")
    pipeline_run.add_argument("manifest", nargs="?", default=None, help="Path to manifest JSON file or raw JSON")
    pipeline_run.add_argument("--tenant", default="tenant_default", help="Tenant ID for Merkle chain isolation")
    pipeline_run.add_argument("--client-key", dest="client_key", default=None, help="Idempotency client key")
    pipeline_run.add_argument("--intent", default=None, help="Human-readable task intent")
    pipeline_run.add_argument("--effect-class", dest="effect_class", default=None, help="Canonical effect class")
    pipeline_run.add_argument("--risk-tier", dest="risk_tier", default=None, help="Declared risk tier (T1-T4)")
    pipeline_run.add_argument("--bypass-approvals", action="store_true", help="Mark operator approval for mutating tasks")
    pipeline_run.add_argument("--auto-ratify", action="store_true", help="Auto-ratify T3/T4 high-risk tasks with Arthur Crown")
    pipeline_run.add_argument("--json", action="store_true", help="Emit JSON output")

    pipeline_status = pipeline_sub.add_parser("status", help="Show pipeline governance and scarcity status")
    pipeline_status.add_argument("--json", action="store_true", help="Emit JSON output")

    pipeline_verify = pipeline_sub.add_parser("verify", help="Run automated 6-stage self-diagnostic smoke test")
    pipeline_verify.add_argument("--json", action="store_true", help="Emit JSON output")

    health = sub.add_parser("health", help="Unified production health aggregation rolling up all subsystems (Track B5)")
    health.add_argument("--json", action="store_true", help="Emit structured JSON output")
    health.add_argument("--no-probe-remote", dest="probe_remote", action="store_false", default=True, help="Skip remote network probes and check local/cached status only")
    health.add_argument("--verbose", "-v", action="store_true", help="Include full contract and circuit breaker diagnostics")

    templates_p = sub.add_parser("templates", help="List and inspect canonical mission templates (Track C4)")
    templates_p.add_argument("--json", action="store_true", help="Emit template catalog as JSON")
    templates_p.add_argument(
        "--name",
        choices=("research", "architecture", "audit", "operations", "growth"),
        default=None,
        help="Inspect specific canonical template details",
    )

    return parser
