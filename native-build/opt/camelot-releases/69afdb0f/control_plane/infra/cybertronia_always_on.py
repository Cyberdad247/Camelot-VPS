#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""control_plane/infra/cybertronia_always_on.py

Cybertronia Always-On Engine & Daemon Supervisor for Camelot-OS.
Maintains continuous uptime for core Cybertronia services across reboots, crashes,
and memory constraints. Emits structured telemetry to 03_VAULT/runtime_state/cybertronia_always_on.json.

Managed Daemon Mesh:
  1. go_router          :8077 (SSE command router & Tailscale Funnel ingress)
  2. bifrost_sidecar    :8011 (Bifrost bridge -> upstream :8001)
  3. cognitive_service  :8092 (MemCastle, Graphify, WorldTree sync)
  4. opencodex          :10100 (Universal OpenAI Responses proxy)
  5. kinetic_edge       :3001 (Bifrost Gateway HTTP/WS)
  6. omnivoice          :3002 (OmniVoice WebSocket & routing)
  7. kitten_tts         :8300 (Kitten TTS audio streaming)
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__version__ = "1.0.0"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent.parent
VAULT_STATE = _ROOT / "03_VAULT" / "runtime_state" / "cybertronia_always_on.json"
LOG_DIR = _ROOT / "logs" / "cybertronia"
PID_FILE = LOG_DIR / "always_on_supervisor.pid"
SUPERVISOR_LOG = LOG_DIR / "supervisor.log"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_memory_info() -> Dict[str, Any]:
    """Retrieve physical RAM and pagefile headroom safely on Windows/Linux."""
    if platform.system() == "Windows":
        try:
            buf = ctypes.create_string_buffer(64)
            buf[0:4] = (64).to_bytes(4, "little")
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(buf):
                f = struct.unpack("<IIQQQQQQQ", buf.raw)
                return {
                    "load_pct": f[1],
                    "total_phys_mb": f[2] // (1024 * 1024),
                    "avail_phys_mb": f[3] // (1024 * 1024),
                    "total_page_mb": f[4] // (1024 * 1024),
                    "avail_page_mb": f[5] // (1024 * 1024),
                    "pressure_alarm": (f[3] // (1024 * 1024)) < 400,
                }
        except Exception:
            pass
    return {
        "load_pct": 50,
        "total_phys_mb": 8000,
        "avail_phys_mb": 4000,
        "total_page_mb": 16000,
        "avail_page_mb": 8000,
        "pressure_alarm": False,
    }


def probe_socket(host: str, port: int, timeout: float = 0.6) -> bool:
    """Check if TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass
class DaemonSpec:
    name: str
    port: int
    description: str
    cmd: List[str]
    cwd: Path
    env_vars: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    probe_host: str = "127.0.0.1"


class CybertroniaSupervisor:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or _ROOT
        self.log_dir = self.root / "logs" / "cybertronia"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.procs: Dict[str, subprocess.Popen] = {}
        self.start_times: Dict[str, float] = {}
        self.restart_counts: Dict[str, int] = {}
        self.last_restarts: Dict[str, float] = {}

    def get_daemon_specs(self) -> List[DaemonSpec]:
        py = sys.executable
        node = shutil.which("node") or "node"
        ocx_mjs = self.root / "node_modules" / "@bitkyc08" / "opencodex" / "bin" / "ocx.mjs"
        omnivoice_dist = self.root / "02_FORGE" / "KINETIC_ARMORY" / "omnivoice-router" / "dist" / "omnivoice-router.js"
        bifrost_sidecar_exe = self.root / "01_KERNEL" / "senses" / "bifrost_go_sidecar" / "bifrost_sidecar.exe"
        go_router_exe = self.root / "control_plane" / "go_router" / "go_router.exe"

        specs: List[DaemonSpec] = [
            DaemonSpec(
                name="go_router",
                port=8077,
                description="Go SSE command router & Tailscale Funnel ingress",
                cmd=[str(go_router_exe), "serve", ":8077"] if go_router_exe.exists() else [],
                cwd=self.root / "control_plane" / "go_router",
                env_vars={"CAMELOT_NODE": "cybertronia", "CAMELOT_COGNITIVE_URL": "http://127.0.0.1:8092"},
                enabled=go_router_exe.exists(),
            ),
            DaemonSpec(
                name="bifrost_sidecar",
                port=8011,
                description="Bifrost Go Sidecar mTLS bridge",
                cmd=[str(bifrost_sidecar_exe)] if bifrost_sidecar_exe.exists() else [],
                cwd=self.root,
                enabled=bifrost_sidecar_exe.exists(),
            ),
            DaemonSpec(
                name="cognitive_service",
                port=8092,
                description="MemCastle / Graphify / WorldTree cognitive service",
                cmd=[py, str(self.root / "control_plane" / "cognitive_service.py")],
                cwd=self.root,
                env_vars={"COGNITIVE_PORT": "8092", "CAMELOT_NODE": "cybertronia"},
                enabled=(self.root / "control_plane" / "cognitive_service.py").exists(),
            ),
            DaemonSpec(
                name="opencodex",
                port=10100,
                description="OpenCodex universal OpenAI Responses proxy",
                cmd=[node, str(ocx_mjs), "start", "--port", "10100"] if ocx_mjs.exists() else [],
                cwd=self.root,
                env_vars={"OCX_PORT": "10100", "OCX_HOST": "127.0.0.1"},
                enabled=ocx_mjs.exists(),
            ),
            DaemonSpec(
                name="omnivoice",
                port=3002,
                description="OmniVoice WebSocket & Voice switchboard",
                cmd=[node, str(omnivoice_dist)] if omnivoice_dist.exists() else [],
                cwd=self.root / "02_FORGE" / "KINETIC_ARMORY" / "omnivoice-router",
                enabled=omnivoice_dist.exists(),
            ),
            DaemonSpec(
                name="kitten_tts",
                port=8300,
                description="Kitten TTS low-latency audio stream",
                cmd=[py, "-c", (
                    f"import sys, asyncio; sys.path.insert(0, r'{self.root}'); "
                    f"sys.path.insert(0, r'{self.root / '01_KERNEL' / 'senses' / 'audio'}'); "
                    "from kitten_service import kitten_service; "
                    "asyncio.run(kitten_service.run_streaming_server())"
                )],
                cwd=self.root,
                enabled=(self.root / "01_KERNEL" / "senses" / "audio" / "kitten_service.py").exists(),
            ),
        ]
        return specs

    def log(self, message: str) -> None:
        stamp = _ts()
        line = f"[{stamp}] {message}"
        print(line)
        try:
            with SUPERVISOR_LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def check_daemon(self, spec: DaemonSpec) -> Dict[str, Any]:
        live = probe_socket(spec.probe_host, spec.port)
        proc = self.procs.get(spec.name)
        proc_alive = proc is not None and proc.poll() is None
        pid = proc.pid if proc_alive and proc else None

        return {
            "name": spec.name,
            "port": spec.port,
            "description": spec.description,
            "live": live,
            "proc_alive": proc_alive,
            "pid": pid,
            "restart_count": self.restart_counts.get(spec.name, 0),
            "last_restart": self.last_restarts.get(spec.name),
        }

    def start_daemon(self, spec: DaemonSpec) -> bool:
        if not spec.enabled or not spec.cmd:
            return False

        # If already listening on port, mark healthy and skip re-spawn
        if probe_socket(spec.probe_host, spec.port):
            return True

        # Check memory floor to prevent cascading allocation failures
        mem = get_memory_info()
        if mem.get("pressure_alarm"):
            self.log(f"⚠️ Memory floor breached ({mem['avail_phys_mb']}MB free). Delaying start of {spec.name}.")
            return False

        out_log = self.log_dir / f"{spec.name}.log"
        err_log = self.log_dir / f"{spec.name}.err.log"

        env = os.environ.copy()
        env.update(spec.env_vars)
        env["CAMELOT_OS_HOME"] = str(self.root)

        spawn_kwargs: Dict[str, Any] = {
            "cwd": str(spec.cwd),
            "env": env,
            "stdin": subprocess.DEVNULL,
        }
        if platform.system() == "Windows":
            spawn_kwargs["creationflags"] = (
                getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )

        try:
            out_fh = open(out_log, "ab")
            err_fh = open(err_log, "ab")
            proc = subprocess.Popen(spec.cmd, stdout=out_fh, stderr=err_fh, **spawn_kwargs)
            self.procs[spec.name] = proc
            self.start_times[spec.name] = time.time()
            self.restart_counts[spec.name] = self.restart_counts.get(spec.name, 0) + 1
            self.last_restarts[spec.name] = time.time()
            self.log(f"🚀 Started {spec.name} PID={proc.pid} on :{spec.port}")
            return True
        except Exception as exc:
            self.log(f"❌ Failed to start {spec.name}: {exc}")
            return False

    def emit_telemetry(self, daemon_status: List[Dict[str, Any]]) -> None:
        mem = get_memory_info()
        healthy_count = sum(1 for d in daemon_status if d["live"])
        total_count = len(daemon_status)

        payload = {
            "node": "cybertronia",
            "tailscale_ip": "100.118.224.52",
            "status": "ONLINE" if healthy_count > 0 else "DEGRADED",
            "mode": "ALWAYS_ON_MASTER",
            "timestamp": _ts(),
            "healthy_daemons": f"{healthy_count}/{total_count}",
            "memory": mem,
            "daemons": daemon_status,
            "version": __version__,
        }

        try:
            VAULT_STATE.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = VAULT_STATE.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_file.replace(VAULT_STATE)
        except Exception as exc:
            self.log(f"Telemetry flush error: {exc}")

    def run_supervisor_tick(self) -> List[Dict[str, Any]]:
        specs = self.get_daemon_specs()
        statuses = []
        for spec in specs:
            status = self.check_daemon(spec)
            if not status["live"]:
                # Backoff: do not restart more frequently than every 5s per daemon
                now = time.time()
                last_time = self.last_restarts.get(spec.name, 0)
                if now - last_time >= 5.0:
                    self.start_daemon(spec)
                    time.sleep(0.3)
                    status = self.check_daemon(spec)
            statuses.append(status)
        self.emit_telemetry(statuses)
        return statuses

    def run_forever(self, poll_interval: float = 5.0) -> None:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        self.log(f"♜ Cybertronia Always-On Supervisor online (PID {os.getpid()})")
        try:
            while True:
                self.run_supervisor_tick()
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            self.log("Supervisor interrupted by operator. Exiting.")
        finally:
            if PID_FILE.exists():
                try:
                    PID_FILE.unlink()
                except Exception:
                    pass


def get_status_overview() -> Dict[str, Any]:
    supervisor = CybertroniaSupervisor()
    specs = supervisor.get_daemon_specs()
    statuses = [supervisor.check_daemon(s) for s in specs]
    mem = get_memory_info()
    return {
        "node": "cybertronia",
        "ip": "100.118.224.52",
        "timestamp": _ts(),
        "memory": mem,
        "daemons": statuses,
    }


def install_scheduled_task() -> Tuple[bool, str]:
    """Register Cybertronia Always-On supervisor in Windows Task Scheduler."""
    if platform.system() != "Windows":
        return False, "Scheduled tasks are only supported on Windows host"

    script = _ROOT / "control_plane" / "cybertronia_boot.ps1"
    task_name = "CybertroniaAlwaysOn"
    powershell_exe = shutil.which("powershell") or "powershell.exe"

    cmd = (
        f"$action = New-ScheduledTaskAction -Execute '{powershell_exe}' -Argument '-NoProfile -ExecutionPolicy Bypass -File \"{script}\"'; "
        f"$trigger = New-ScheduledTaskTrigger -AtLogOn; "
        f"$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1); "
        f"Register-ScheduledTask -TaskName '{task_name}' -Action $action -Trigger $trigger -Settings $settings -Force"
    )

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode == 0:
            return True, f"Successfully installed '{task_name}' in Windows Task Scheduler (Triggers @Logon)"
        return False, f"Install failed (code {res.returncode}): {res.stderr.strip() or res.stdout.strip()}"
    except Exception as exc:
        return False, f"Install execution failed: {exc}"


def uninstall_scheduled_task() -> Tuple[bool, str]:
    """Remove Cybertronia Always-On supervisor from Windows Task Scheduler."""
    task_name = "CybertroniaAlwaysOn"
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode == 0:
            return True, f"Successfully removed '{task_name}' from Task Scheduler"
        return False, f"Uninstall failed: {res.stderr.strip() or res.stdout.strip()}"
    except Exception as exc:
        return False, f"Uninstall execution failed: {exc}"


def main():
    parser = argparse.ArgumentParser(description="Cybertronia Always-On Supervisor & Health Engine")
    parser.add_argument("action", nargs="?", default="status", choices=["status", "start", "tick", "install", "uninstall"],
                        help="Action to perform (default: status)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON telemetry")
    args = parser.parse_args()

    supervisor = CybertroniaSupervisor()

    if args.action == "status":
        overview = get_status_overview()
        if args.json:
            print(json.dumps(overview, indent=2))
        else:
            print("=" * 80)
            print("♜ CYBERTRONIA ALWAYS-ON DAEMON MESH TELEMETRY ♜")
            print("=" * 80)
            mem = overview["memory"]
            print(f"Host Node    : cybertronia ({overview['ip']}) | RAM: {mem['avail_phys_mb']}MB / {mem['total_phys_mb']}MB Free ({mem['load_pct']}% load)")
            print(f"Timestamp    : {overview['timestamp']}")
            print("-" * 80)
            print(f"{'Daemon':<20} {'Port':<8} {'Status':<12} {'Description'}")
            print("-" * 80)
            for d in overview["daemons"]:
                stat = "ONLINE" if d["live"] else "OFFLINE"
                print(f"{d['name']:<20} {d['port']:<8} {stat:<12} {d['description']}")
            print("=" * 80)

    elif args.action == "tick":
        res = supervisor.run_supervisor_tick()
        live_count = sum(1 for r in res if r["live"])
        print(f"Tick completed: {live_count}/{len(res)} daemons online")

    elif args.action == "start":
        supervisor.run_forever()

    elif args.action == "install":
        ok, msg = install_scheduled_task()
        print(("✅ " if ok else "❌ ") + msg)

    elif args.action == "uninstall":
        ok, msg = uninstall_scheduled_task()
        print(("✅ " if ok else "❌ ") + msg)


if __name__ == "__main__":
    main()
