# SPDX-License-Identifier: MIT

"""
Cognitive MCP — the Graphify/MemCastle/sync cognitive stack as a scoped MCP server.

Exposes ONLY memcastle_search, graphify_ingest, cognitive_sync, cognitive_forage —
not the full Hive (see mcp_conductor.py for that). Every tool is a thin wrapper
around the existing cognitive_service.py pipeline (GF/Graphify, MemCastle, //sync,
forage) — zero duplicated business logic, just JSON-RPC plumbing + a process-local
lock that serializes concurrent tool calls against the shared SQLite-backed vault.

Protocol: JSON-RPC 2.0 over stdio (MCP spec 2024-11-05)

Usage:
    python -m control_plane.cognitive_mcp

Add to ~/.claude/settings.json (or CAMELOT_OS/.claude/settings.json):
    {
      "mcpServers": {
        "cognitive": {
          "command": "python",
          "args": ["-m", "control_plane.cognitive_mcp"],
          "cwd": "C:/Users/vizio/CAMELOT_OS"
        }
      }
    }

Tools exposed:
    memcastle_search   — semantic KNN search over the MemCastle vault
    graphify_ingest    — extract (head, relation, tail) triplets and store them
    cognitive_sync     — bidirectional //sync with the NotebookLM Cloud Brain
    cognitive_forage   — fetch a URL, strip HTML, Graphify-ingest the text
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import threading
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Reuse cognitive_service's pipeline (GF, forage, mcsync, BRIDGE) ─────────────
#
# Mirrors cognitive_service.py's own `_load()` helper rather than a plain package
# import: a fresh `spec_from_file_location` exec gives every fresh re-exec of this
# module (e.g. in tests, via spec_from_file_location against tmp_path env vars) its
# own freshly-initialized cognitive_service instance — no shared SQLite state leaks
# across test runs, same guarantee tests/test_cognitive_service.py relies on. A
# plain `import control_plane.cognitive_service as cs` also works at runtime (it's
# a normal, side-effect-free module import — no HTTP server starts), but it would
# return the *same cached* module on every fresh-load of this file, defeating the
# test isolation pattern. Mirroring `_load()` instead is the option that holds up
# under both: a single long-lived MCP server process, and pytest's tmp_path fixture.

_CP = Path(__file__).resolve().parent
sys.path.insert(0, str(_CP))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _CP / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cs = _load("cognitive_service")  # cs.GF, cs.forage, cs.mcsync, cs.BRIDGE

_LOCK = threading.Lock()  # serializes concurrent MCP tool calls in THIS process

# ── Protocol ──────────────────────────────────────────────────────────────────

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "camelot-cognitive", "version": "1.0.0"}


def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, msg: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}


def _log(msg: str) -> None:
    print(f"[MCP] {msg}", file=sys.stderr, flush=True)


# ── Tool registry ─────────────────────────────────────────────────────────────

def _tools() -> list[dict]:
    return [
        {
            "name": "memcastle_search",
            "description": (
                "Semantic KNN search over the MemCastle vault (Graphify-ingested "
                "triplets and synced cloud syntheses). Read-only."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language search query"},
                    "k": {"type": "integer", "description": "Number of nearest neighbors (default 5)"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "graphify_ingest",
            "description": (
                "Extract (head, relation, tail) triplets from free text via Graphify's "
                "deterministic SVO extractor and store them in the MemCastle vault."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Free text to extract and ingest"},
                    "source": {"type": "string", "description": "Provenance tag (default 'mcp')"},
                },
                "required": ["text"],
            },
        },
        {
            "name": "cognitive_sync",
            "description": (
                "Bidirectional //sync between the MemCastle edge vault and the NotebookLM "
                "Cloud Brain: push a vault snapshot up, pull a fresh synthesis down. Skips "
                "cleanly (status='skipped') if the cloud bridge is unreachable."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Synthesis query for the pull phase "
                                       "(default: a periodic Camelot-OS state-sync prompt)",
                    },
                },
            },
        },
        {
            "name": "cognitive_forage",
            "description": (
                "Fetch a URL, strip HTML to plain text, and Graphify-ingest it into MemCastle. "
                "A real urllib fetch + HTML strip + ingest — no distributed scraper fleet."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch and ingest"},
                },
                "required": ["url"],
            },
        },
    ]


# ── Tool handlers — thin wrappers over cognitive_service.py, zero dup logic ─────

def _tool_memcastle_search(args: dict) -> dict:
    query = args.get("query")
    if not query:
        raise ValueError("memcastle_search requires a non-empty 'query'")
    k = int(args.get("k", 5))
    with _LOCK:
        results = cs.GF.mc.search(query, k=k)
    return {"query": query, "results": results}


def _tool_graphify_ingest(args: dict) -> dict:
    text = args.get("text")
    if not text:
        raise ValueError("graphify_ingest requires non-empty 'text'")
    source = args.get("source", "mcp")
    with _LOCK:
        triplets = cs.GF.ingest(text, source=source)
        total = cs.GF.mc.count()
    return {
        "triplets": [{"head": t.head, "relation": t.relation, "tail": t.tail} for t in triplets],
        "count": len(triplets),
        "vault_total": total,
    }


def _tool_cognitive_sync(args: dict) -> dict:
    query = args.get("query", "Periodic Camelot-OS state sync.")
    with _LOCK:
        result = cs.mcsync.sync(cs.GF.mc, query, bridge=cs.BRIDGE)
    return result


def _tool_cognitive_forage(args: dict) -> dict:
    url = args.get("url")
    if not url:
        raise ValueError("cognitive_forage requires a non-empty 'url'")
    with _LOCK:
        result = cs.forage(cs.GF, url)
    return result


_TOOL_HANDLERS = {
    "memcastle_search": _tool_memcastle_search,
    "graphify_ingest": _tool_graphify_ingest,
    "cognitive_sync": _tool_cognitive_sync,
    "cognitive_forage": _tool_cognitive_forage,
}


async def _call(name: str, args: dict) -> dict:
    return _TOOL_HANDLERS[name](args)


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
        if tool_name not in _TOOL_HANDLERS:
            return _err(id_, -32602, f"Unknown tool: {tool_name}")
        try:
            result = await _call(tool_name, arguments)
            return _ok(id_, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
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

    _log("CAMELOT Cognitive MCP ready (stdio)")

    async for raw in reader:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _log(f"JSON parse error: {exc}")
            _send(_err(None, -32700, f"Parse error: {exc}"))
            continue

        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
            _log(f"Invalid request: {line[:200]}")
            _send(_err(req.get("id") if isinstance(req, dict) else None, -32600, "Invalid Request"))
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
