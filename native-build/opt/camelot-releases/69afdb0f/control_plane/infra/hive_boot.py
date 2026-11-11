# SPDX-License-Identifier: MIT

"""
Hive Boot — Single-command launcher for the CAMELOT-OS Universal Bridge.

Starts in the correct order:
  1. CLIProxyAPI   (:8080)  — web model normalization (Claude/Gemini/Codex/Kimi)
  2. OmniRoute     (:20128) — cost-tier smart router (optional, continues if absent)
  3. MCP Conductor (stdio)  — exposes all terminals as MCP tools [background]
  4. Hive TUI               — live multi-stream display

Usage:
    python -m control_plane.hive_boot              # full stack + TUI
    python -m control_plane.hive_boot --no-tui     # services only (headless)
    python -m control_plane.hive_boot --status     # probe and report health
    python -m control_plane.hive_boot --mcp-only   # MCP conductor in foreground

The MCP conductor config (for Claude Code) is printed at startup.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
CLIPROXY_EXE = CAMELOT_HOME.parent / "CLIProxyAPI" / "cli-proxy-api.exe"
CLIPROXY_CFG = CAMELOT_HOME.parent / "CLIProxyAPI" / "config.yaml"

OMNIROUTE_BIN = Path.home() / ".omniroute" / "omniroute.exe"

PYTHON = sys.executable

_procs: list[subprocess.Popen] = []


def _banner() -> None:
    print("""
╔══════════════════════════════════════════════════════╗
║          CAMELOT-OS  HIVE  BOOT  SEQUENCE            ║
║          Universal Bridge — 13 Terminals             ║
╚══════════════════════════════════════════════════════╝
""", flush=True)


def _print_mcp_config() -> None:
    config = {
        "mcpServers": {
            "hive": {
                "command": PYTHON,
                "args": ["-m", "control_plane.mcp_conductor"],
                "cwd": str(CAMELOT_HOME),
            }
        }
    }
    print("\n[MCP] Add to ~/.claude/settings.json:")
    print(json.dumps(config, indent=2))
    print()


def _start_cliproxy() -> subprocess.Popen | None:
    if not CLIPROXY_EXE.exists():
        print(f"[BOOT] CLIProxyAPI not found at {CLIPROXY_EXE} — skipping", flush=True)
        return None
    if _is_port_open(8080):
        print("[BOOT] CLIProxyAPI already running on :8080", flush=True)
        return None
    print("[BOOT] Starting CLIProxyAPI on :8080...", flush=True)
    try:
        proc = subprocess.Popen(
            [str(CLIPROXY_EXE), "--config", str(CLIPROXY_CFG)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(CLIPROXY_EXE.parent),
        )
        _procs.append(proc)
        time.sleep(1.5)
        if _is_port_open(8080):
            print("[BOOT] CLIProxyAPI up on :8080", flush=True)
        else:
            print("[BOOT] CLIProxyAPI may still be starting...", flush=True)
        return proc
    except Exception as e:
        print(f"[BOOT] Failed to start CLIProxyAPI: {e}", flush=True)
        return None


def _start_omniroute() -> subprocess.Popen | None:
    if not OMNIROUTE_BIN.exists():
        print("[BOOT] OmniRoute binary not found — skipping", flush=True)
        return None
    if _is_port_open(20128):
        print("[BOOT] OmniRoute already running on :20128", flush=True)
        return None
    print("[BOOT] Starting OmniRoute on :20128...", flush=True)
    try:
        proc = subprocess.Popen(
            [str(OMNIROUTE_BIN)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _procs.append(proc)
        time.sleep(1.0)
        print(f"[BOOT] OmniRoute {'up' if _is_port_open(20128) else 'starting'} on :20128", flush=True)
        return proc
    except Exception as e:
        print(f"[BOOT] Failed to start OmniRoute: {e}", flush=True)
        return None


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


async def _status_report() -> None:
    print("[STATUS] Probing all terminals...\n", flush=True)
    try:
        from control_plane.bifrost import Bifrost
        rows = await Bifrost().status()
        print(f"{'TERMINAL':20s} {'ENGINE':20s} {'STATUS':12s} {'LATENCY':>8s}  COST")
        print("-" * 72)
        for r in rows:
            indicator = "●" if r["status"] in ("live", "assumed_live") else "○"
            print(
                f"{indicator} {r['id']:19s} {r['engine']:20s} {r['status']:12s}"
                f" {r['latency_ms']:6.0f}ms  {r['cost_tier']}"
            )
    except Exception as e:
        print(f"[STATUS] Error: {e}", flush=True)


def _launch_tui() -> None:
    print("[BOOT] Launching Hive Stream TUI...", flush=True)
    os.chdir(str(CAMELOT_HOME))
    # Import and run directly in-process (Textual manages its own event loop)
    try:
        from control_plane.hive_stream_tui import main
        main()
    except ImportError as e:
        print(f"[BOOT] TUI import error: {e}", flush=True)
        print("[BOOT] Run: uv add textual", flush=True)


def _shutdown(signum, frame) -> None:
    print("\n[BOOT] Shutdown signal — stopping services...", flush=True)
    for proc in _procs:
        try:
            proc.terminate()
        except Exception:
            pass
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="CAMELOT-OS Hive Boot")
    parser.add_argument("--no-tui",    action="store_true", help="Start services without TUI")
    parser.add_argument("--status",    action="store_true", help="Show terminal health and exit")
    parser.add_argument("--mcp-only",  action="store_true", help="Run MCP conductor in foreground")
    args = parser.parse_args()

    if args.status:
        os.chdir(str(CAMELOT_HOME))
        asyncio.run(_status_report())
        return

    _banner()

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    os.chdir(str(CAMELOT_HOME))

    if args.mcp_only:
        # Run MCP conductor directly (stdio — for IDE integration testing)
        print("[BOOT] MCP Conductor mode — connect your IDE client now", flush=True)
        import control_plane.mcp_conductor as conductor
        asyncio.run(conductor._serve_stdio())
        return

    # Start infrastructure
    _start_cliproxy()
    _start_omniroute()

    _print_mcp_config()

    if args.no_tui:
        print("[BOOT] Services running. Press Ctrl+C to stop.", flush=True)
        try:
            while True:
                time.sleep(5)
                for proc in _procs:
                    if proc.poll() is not None:
                        print(f"[BOOT] Process {proc.pid} exited", flush=True)
        except KeyboardInterrupt:
            _shutdown(None, None)
    else:
        # Launch TUI (blocks until quit)
        _launch_tui()
        _shutdown(None, None)


if __name__ == "__main__":
    main()
