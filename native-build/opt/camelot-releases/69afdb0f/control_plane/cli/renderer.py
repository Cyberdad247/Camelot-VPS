# SPDX-License-Identifier: MIT

"""ANSI color, stream printing, pretty rendering, and emit utilities."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from colorama import Fore, Style, just_fix_windows_console

from control_plane.cli.constants import STREAM_DELAY

just_fix_windows_console()


# ---------------------------------------------------------------------------
# Color + stream printing
# ---------------------------------------------------------------------------

def _color(text: str, tone: str) -> str:
    palette = {
        "title": Fore.CYAN + Style.BRIGHT,
        "ok": Fore.GREEN + Style.BRIGHT,
        "warn": Fore.YELLOW + Style.BRIGHT,
        "err": Fore.RED + Style.BRIGHT,
        "info": Fore.CYAN,
        "dim": Style.DIM,
        "accent": Fore.MAGENTA + Style.BRIGHT,
        "score": Fore.BLUE + Style.BRIGHT,
    }
    return f"{palette.get(tone, '')}{text}{Style.RESET_ALL}"


def _stream_print(text: str, *, tone: str | None = None, newline: bool = True) -> None:
    rendered = _color(text, tone) if tone else text
    stream_encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    rendered = rendered.encode(stream_encoding, errors="replace").decode(stream_encoding, errors="replace")
    if not sys.stdout.isatty() or STREAM_DELAY <= 0:
        print(rendered, end="\n" if newline else "", flush=True)
        return

    for char in rendered:
        print(char, end="", flush=True)
        if char not in {"\n", "\r"}:
            time.sleep(STREAM_DELAY)
    if newline:
        print("", flush=True)


def _progress(label: str, detail: str, *, tone: str = "dim") -> None:
    _stream_print(f"[{label}] {detail}", tone=tone)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------

def _provider_label(provider: str | None) -> str:
    return provider or "auto"


def _model_label(model: str | None) -> str:
    return model or "default"


def _prompt_text(knight_id: str, provider: str | None, model: str | None) -> str:
    return f"Camelot[{knight_id}|{_provider_label(provider)}/{_model_label(model)}]> "


def _identity_lines(
    knight_id: str,
    provider: str | None,
    model: str | None,
    last_route: dict[str, Any] | None = None,
) -> list[str]:
    lines = [
        f"Knight: {knight_id}",
        f"Provider: {_provider_label(provider)}",
        f"LLM: {_model_label(model)}",
    ]
    if last_route:
        lines.extend(
            [
                f"Last route: {last_route['knight_id']} via {last_route['engine']}",
                f"Last model: {last_route['model']} @ {last_route['backend_url']}",
                f"Reason: {last_route['reason']}",
            ]
        )
    else:
        lines.append("Last route: none yet; run /route <intent> to preview assignment")
    return lines


# ---------------------------------------------------------------------------
# Pretty rendering
# ---------------------------------------------------------------------------

def _pretty_render(payload: Any) -> str:
    if isinstance(payload, dict) and "payload" in payload and isinstance(payload["payload"], dict):
        inner = payload["payload"]
        lines = [
            f"status: {inner.get('status', 'UNKNOWN')}",
            f"task: {inner.get('task', '-')}",
        ]
        if "service" in inner:
            lines.append(f"service: {inner['service']}")
        if "source" in inner:
            lines.append(f"source: {inner['source']}")
        if "execution_target" in inner:
            lines.append(f"execution_target: {inner['execution_target']}")
        if "reason" in inner:
            lines.append(f"reason: {inner['reason']}")
        route = inner.get("route")
        if isinstance(route, dict):
            lines.append(f"route_knight: {route.get('knight_id', '-')}")
            lines.append(f"route_engine: {route.get('engine', '-')}")
            if route.get("reason"):
                lines.append(f"route_reason: {route['reason']}")
        result = inner.get("result")
        if isinstance(result, dict):
            if "message" in result and "latency_ms" in result:
                lines.append(f"message: {result['message']}")
                lines.append(f"latency_ms: {result['latency_ms']}")
            if "note_title" in result:
                lines.append(f"note_title: {result['note_title']}")
            if "note_id" in result:
                lines.append(f"note_id: {result['note_id']}")
            if "action" in result:
                lines.append(f"action: {result['action']}")
            if "content_chars" in result:
                lines.append(f"content_chars: {result['content_chars']}")
            if "generated_utc" in result:
                lines.append(f"generated_utc: {result['generated_utc']}")
            if "brief" in result:
                lines.append("")
                lines.append(str(result["brief"]))
            if "status" in result and "brief" not in result:
                lines.append(f"health: {result['status']}")
            if "supports_browser_isolation" in result and isinstance(result["supports_browser_isolation"], list):
                lines.append(f"browser_isolation: {', '.join(result['supports_browser_isolation'])}")
            if "principles" in result and isinstance(result["principles"], list):
                lines.append("")
                lines.append("principles:")
                lines.extend(f"- {item}" for item in result["principles"][:5])
            if "architecture_stack" in result and isinstance(result["architecture_stack"], list):
                lines.append("stack:")
                lines.extend(f"- {item}" for item in result["architecture_stack"][:5])
            if "execution_phases" in result and isinstance(result["execution_phases"], list):
                lines.append("phases:")
                for phase in result["execution_phases"][:4]:
                    lines.append(
                        f"- {phase.get('phase')}: {phase.get('goal')} ({phase.get('duration_days')}d, {phase.get('cost_profile')})"
                    )
            if "compute_tiers" in result and isinstance(result["compute_tiers"], list):
                lines.append(f"compute_tiers: {', '.join(result['compute_tiers'])}")
            if "aspects" in result and isinstance(result["aspects"], list):
                lines.append(f"aspects: {', '.join(result['aspects'])}")
            if "compute_tier" in result:
                lines.append(f"compute_tier: {result['compute_tier']}")
            if "browser_isolation" in result and not isinstance(result["browser_isolation"], list):
                lines.append(f"browser_isolation: {result['browser_isolation']}")
            if "aspect" in result:
                lines.append(f"aspect: {result['aspect']}")
            if "cartridge" in result:
                lines.append(f"cartridge: {result['cartridge']}")
            if "memory_count" in result:
                lines.append(f"memory_count: {result['memory_count']}")
            if "assigned_knights" in result:
                lines.append(f"knights: {', '.join(result['assigned_knights'])}")
            if "command_surface" in result:
                lines.append(f"command: {result['command_surface']}")
            if "swarm_capacity" in result and isinstance(result["swarm_capacity"], dict):
                lines.append(
                    f"safe_swarm_units: {result['swarm_capacity'].get('safe_swarm_units')}"
                )
                lines.append(
                    f"max_parallel_browser_sessions: {result['swarm_capacity'].get('max_parallel_browser_sessions')}"
                )
            if "nano_knight_llm_map" in result and isinstance(result["nano_knight_llm_map"], list):
                lines.append("nano_knights:")
                for item in result["nano_knight_llm_map"][:4]:
                    lines.append(
                        f"- {item.get('knight_id')}: {item.get('engine')} / {item.get('model')}"
                    )
            if "template" in result and result["template"]:
                lines.append(f"template: {result['template']}")
            if "deliverables" in result and isinstance(result["deliverables"], list):
                lines.append("deliverables:")
                lines.extend(f"- {item}" for item in result["deliverables"][:5])
            if "scoring" in result and isinstance(result["scoring"], dict):
                sc = result["scoring"]
                conf_pct = sc.get("confidence_pct") or f"{int(sc.get('confidence_score', 0) * 100)}%"
                risk_pct = sc.get("risk_pct") or f"{int(sc.get('risk_score', 0) * 100)}%"
                comp_pct = sc.get("completeness_pct") or f"{int(sc.get('completeness_score', 0) * 100)}%"
                lines.append("")
                lines.append("objective_scoring:")
                lines.append(f"  confidence: {conf_pct}")
                lines.append(f"  risk: {risk_pct}")
                lines.append(f"  completeness: {comp_pct}")
                rationale = sc.get("rationale")
                if isinstance(rationale, dict):
                    for k, v in rationale.items():
                        lines.append(f"  - {k}: {v}")
        return "\n".join(lines)

    if isinstance(payload, dict) and "templates" in payload and isinstance(payload["templates"], list):
        lines = [
            "=" * 70,
            "🛡️  CAMELOT-OS CANONICAL MISSION TEMPLATES (TRACK C4) 🛡️",
            "=" * 70,
        ]
        for tmpl in payload["templates"]:
            lines.append(f"\n◈ [{tmpl.get('name', '').upper()}] — {tmpl.get('title', '')}")
            lines.append(f"  Aspect: {tmpl.get('aspect', '')} | Cartridge: {tmpl.get('cartridge', '')} | Tier: {tmpl.get('compute_tier', '')} | Isolation: {tmpl.get('browser_isolation', '')}")
            lines.append(f"  Scope: {tmpl.get('description', '')}")
            lines.append(f"  Default Objective: {tmpl.get('default_objective', '')}")
            if tmpl.get("recommended_knights"):
                lines.append(f"  Knights: {', '.join(tmpl.get('recommended_knights', []))}")
            if tmpl.get("deliverables"):
                lines.append(f"  Deliverables: {', '.join(tmpl.get('deliverables', []))}")
        lines.append("\n" + "=" * 70)
        lines.append("Invoke via: camelot cloudbrain northstar --template <name> [custom objective]")
        lines.append("=" * 70)
        return "\n".join(lines)

    if isinstance(payload, dict) and {"task_id", "phase", "sub_tasks"}.issubset(payload.keys()):
        lines = [
            f"task_id: {payload.get('task_id')}",
            f"phase: {payload.get('phase')}",
            f"sub_tasks: {len(payload.get('sub_tasks', []))}",
        ]
        critique = payload.get("critique")
        if critique:
            lines.append(f"critique_passed: {critique.get('passed')}")
            lines.append(f"critique_confidence: {critique.get('confidence')}")
        return "\n".join(lines)

    return json.dumps(payload, indent=2)


def _emit(payload: Any, *, json_mode: bool = False, title: str | None = None) -> None:
    if json_mode:
        _print_json(payload)
        return

    if title:
        _stream_print(title, tone="title")
    _stream_print(_pretty_render(payload), tone="info")
