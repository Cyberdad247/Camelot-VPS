# SPDX-License-Identifier: MIT

"""
MCP Conductor — CAMELOT-OS Universal Bridge as an MCP Server.

Exposes every registered terminal as an MCP tool over stdio transport.
IDE clients (Claude Code, VS Code MCP extension, Cursor, etc.) connect
via stdio and can call any agent in the CAMELOT-OS Hive.

Protocol: JSON-RPC 2.0 over stdio (MCP spec 2024-11-05)

Usage:
    python -m control_plane.mcp_conductor

Add to ~/.claude/settings.json (or CAMELOT_OS/.claude/settings.json):
    {
      "mcpServers": {
        "hive": {
          "command": "python",
          "args": ["-m", "control_plane.mcp_conductor"],
          "cwd": "C:/Users/vizio/CAMELOT_OS"
        }
      }
    }

Tools exposed:
    route_to_agent   — intent-routed dispatch (auto-selects best terminal)
    ask_sir_boris    — Claude Sonnet direct
    ask_sir_alex     — Claude Opus direct
    ask_sir_helio    — Gemini Flash 2.5 (1M context) direct
    ask_sir_link     — Gemini Pro 2.5 direct
    ask_sir_ghost    — Local Qwen air-gapped direct
    ask_sir_forge    — Qwen Coder local direct
    ask_sir_codex    — OpenAI Codex direct
    ask_sir_mnemo    — Cloud Brain (NotebookLM) direct
    ask_sir_gideon   — GIDEON forensic auditor direct
    ask_sir_sentinel — Claude Haiku security direct
    hive_status      — health of all terminals
    hive_parallel    — send same prompt to N terminals concurrently
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Protocol ──────────────────────────────────────────────────────────────────

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "camelot-hive", "version": "1.1.0"}

TERMINAL_CATALOGUE: dict[str, str] = {
    "sir_boris":    "Claude Sonnet — primary orchestration, architecture, code review",
    "sir_alex":     "Claude Opus — deep reasoning, critical thinking, decision analysis",
    "sir_helio":    "Gemini Flash 2.5 — 1M+ context research and mapping",
    "sir_link":     "Gemini Pro 2.5 — A2A bridge coordination, handshake",
    "sir_ghost":    "Local Qwen (air-gapped) — private, zero-trust, offline",
    "sir_forge":    "Qwen Coder local — kinetic code generation, scaffolding",
    "sir_codex":    "OpenAI Codex — rapid prototyping, velocity coding",
    "sir_mnemo":    "Integration Brain — NotebookLM Cloud Brain memory synthesis",
    "sir_sentinel": "Claude Haiku — security audit, PDG armor review",
    "sir_gideon":   "GIDEON Forensic Auditor — SCORPION risk matrix",
    "sir_octavian": "Ops Sentinel — factory metrics, health dashboard",
    "sir_gravity":  "Google Antigravity — Gemini 2.5 Pro via Antigravity OAuth (IDE-native Google AI)",
    "sir_kimi":     "Moonshot Kimi K2 — 1M+ context via Kimi OAuth (free pool, Chinese/English)",
    "sir_hermes":   "Nous Hermes Agent — autonomous tool-calling agent via subprocess (kinetic)",
}


def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, msg: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}


def _log(msg: str) -> None:
    print(f"[MCP] {msg}", file=sys.stderr, flush=True)


# ── Tool registry ─────────────────────────────────────────────────────────────

def _tools() -> list[dict]:
    tools: list[dict] = [
        {
            "name": "route_to_agent",
            "description": (
                "Route a prompt to the optimal CAMELOT terminal using intent-aware dispatch. "
                "Classifies intent (FORGE/CODE/RESEARCH/MEMORY/OPS/SECURITY/VOICE/GENERAL) "
                "and selects the best available terminal automatically."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Task or question to route"},
                    "system": {"type": "string", "description": "Optional system context"},
                },
                "required": ["prompt"],
            },
        },
        {
            "name": "hive_status",
            "description": "Return health status of all registered CAMELOT terminals.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "hive_parallel",
            "description": (
                "Send the same prompt to multiple terminals concurrently and collect all responses. "
                "Useful for cross-model synthesis or A/B evaluation."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "terminal_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"List of terminal IDs. Valid: {list(TERMINAL_CATALOGUE)}",
                    },
                    "prompt": {"type": "string", "description": "Prompt to send to all terminals"},
                    "system": {"type": "string", "description": "Optional system context"},
                },
                "required": ["terminal_ids", "prompt"],
            },
        },
        {
            "name": "audit_colony",
            "description": (
                "Run the GIDEON forensic colony audit (GHOST scan) on a path and "
                "return the secrets/TODO/risk summary. EXCALIBUR_A_QNF Phase 5."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to audit (default: 01_KERNEL)"},
                },
            },
        },
    ]

    # Per-terminal direct ask tools
    for tid, desc in TERMINAL_CATALOGUE.items():
        tools.append({
            "name": f"ask_{tid}",
            "description": f"Direct dispatch to {tid}: {desc}",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt":     {"type": "string"},
                    "system":     {"type": "string"},
                    "max_tokens": {"type": "integer", "description": "Default: 2048"},
                },
                "required": ["prompt"],
            },
        })

    return tools


# ── Tool handlers ─────────────────────────────────────────────────────────────

async def _call(name: str, args: dict) -> str:
    from control_plane.bifrost import Bifrost
    bf = Bifrost()

    if name == "route_to_agent":
        parts: list[str] = []
        async for _tid, chunk in bf.route_and_stream(args["prompt"], args.get("system", "")):
            parts.append(chunk)
        return "".join(parts)

    elif name == "hive_status":
        rows = await bf.status()
        lines = ["TERMINAL            ENGINE               STATUS       LATENCY  COST"]
        for r in rows:
            lines.append(
                f"{r['id']:20s} {r['engine']:20s} {r['status']:12s}"
                f" {r['latency_ms']:6.0f}ms  {r['cost_tier']}"
            )
        return "\n".join(lines)

    elif name == "hive_parallel":
        tids   = args.get("terminal_ids", [])
        prompt = args["prompt"]
        system = args.get("system", "")
        buffers: dict[str, list[str]] = {tid: [] for tid in tids}
        async for tid, chunk in bf.parallel_stream(tids, prompt, system):
            buffers.setdefault(tid, []).append(chunk)
        sections: list[str] = []
        for tid in tids:
            text = "".join(buffers.get(tid, []))
            sections.append(f"=== {tid} ===\n{text}")
        return "\n\n".join(sections)

    elif name in ("ask_sir_mnemo", "ask_sir_gideon", "audit_colony"):
        # EXCALIBUR_A_QNF Phase 5: dedicated implementations (not Bifrost passthrough)
        if name == "ask_sir_mnemo":
            return await _ask_mnemo(args.get("prompt", ""), args.get("notebook_id"))
        # sir_gideon / audit_colony both run the forensic colony audit
        return await _audit_colony(args.get("path", "01_KERNEL"))

    elif name.startswith("ask_"):
        tid = name[4:]
        parts: list[str] = []
        async for chunk in bf.stream(
            tid,
            args["prompt"],
            args.get("system", ""),
            int(args.get("max_tokens", 2048)),
        ):
            parts.append(chunk)
        return "".join(parts)

    else:
        return f"[MCP] Unknown tool: {name}"


# ── sir_mnemo: NotebookLM Cloud Brain (Phase 5, Task 5.4) ───────────────────────

async def _ask_mnemo(prompt: str, notebook_id: str | None = None) -> str:
    """Query the NotebookLM Cloud Brain directly. Auth from ~/.notebooklm."""
    try:
        from notebooklm import NotebookLMClient
    except ImportError:
        return "[sir_mnemo] notebooklm-py not installed in this environment."
    if not prompt.strip():
        return "[sir_mnemo] empty prompt."
    # Default to the living notebook alias if none specified
    nb = notebook_id or "a9cf586e-1971-4959-bb97-cdcd37257ebb"
    try:
        client = await NotebookLMClient.from_storage()
        async with client:
            result = await client.chat.ask(nb, prompt)
            return result.answer or "[sir_mnemo] empty response."
    except Exception as exc:
        return f"[sir_mnemo] Cloud Brain error: {exc} (run 'notebooklm login' to refresh)"


# ── sir_gideon: forensic colony audit (Phase 5, Task 5.3) ───────────────────────

async def _audit_colony(path: str = "01_KERNEL") -> str:
    """Run the GHOST forensic audit and return a structured summary."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "squires.colony", "ghost", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    text = out.decode("utf-8", errors="replace")
    # Extract the summary line
    summary = next((ln for ln in text.splitlines() if ln.strip().startswith("Summary:")),
                   "Summary: (not found)")
    return f"[sir_gideon] GHOST audit of {path}\n{summary}"


# ── MCP dispatch ──────────────────────────────────────────────────────────────

async def _dispatch(req: dict) -> dict | None:
    method = req.get("method", "")
    id_    = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return _ok(id_, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "logging": {}},
            "serverInfo": SERVER_INFO,
        })

    elif method in ("initialized", "notifications/initialized"):
        return None  # notification — no response

    elif method == "ping":
        return _ok(id_, {})

    elif method == "tools/list":
        return _ok(id_, {"tools": _tools()})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            result = await _call(tool_name, arguments)
            return _ok(id_, {
                "content": [{"type": "text", "text": result}],
                "isError": False,
            })
        except Exception as exc:
            _log(f"Tool error [{tool_name}]: {exc}")
            return _ok(id_, {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            })

    elif id_ is not None:
        return _err(id_, -32601, f"Method not found: {method}")

    return None  # unknown notification — ignore


# ── Stdio transport ───────────────────────────────────────────────────────────

async def _serve_stdio() -> None:
    loop = asyncio.get_event_loop()

    reader = asyncio.StreamReader()
    read_proto = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: read_proto, sys.stdin.buffer)

    write_transport, _ = await loop.connect_write_pipe(
        lambda: asyncio.BaseProtocol(), sys.stdout.buffer
    )

    def _send(obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        write_transport.write(line.encode("utf-8"))

    _log("CAMELOT Hive MCP Conductor ready (stdio)")

    async for raw in reader:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _log(f"JSON parse error: {exc}")
            continue

        try:
            resp = await _dispatch(req)
            if resp is not None:
                _send(resp)
        except Exception as exc:
            _log(f"Unhandled dispatch error: {exc}")
            if req.get("id") is not None:
                _send(_err(req["id"], -32603, str(exc)))


if __name__ == "__main__":
    asyncio.run(_serve_stdio())
