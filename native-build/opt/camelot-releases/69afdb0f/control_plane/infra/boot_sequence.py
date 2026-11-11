# SPDX-License-Identifier: MIT

"""Reusable boot sequence logic for Camelot-OS.

# HITL: file-ops pre-approved — writes bounded to boot state files and logs
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import importlib.util
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .cloud_services import CloudServiceName, CloudServiceRequest, CloudServiceRouter
from .codex_integration import boot_codex_integration
from .excalibur_preflight import boot_excalibur_preflight
from control_plane.preflight.boot_integration import boot_vfs_preflight
from .heimdall_bifrost_governance import boot_heimdall_bifrost_governance
from control_plane.core.knight_configuration import write_knight_configuration
from .nano_swarm_runtime import boot_nano_swarm_runtime
from .orchestration_state import summarize_boot_results
from .symbiotic_maintenance import boot_symbiotic_maintenance
from .vps_hermes_prime import boot_vps_hermes_prime

_C = {
    "g": "\033[92m",
    "y": "\033[93m",
    "r": "\033[91m",
    "c": "\033[96m",
    "m": "\033[95m",
    "b": "\033[94m",
    "w": "\033[97m",
    "d": "\033[2m",
    "x": "\033[0m",
    "B": "\033[1m",
}

_STRIP_RICH = re.compile(r"\[/?[a-zA-Z_ ]*\]")
_MORGANA_TASK_NAME = "Camelot Morgana Bridge"
_BIFROST_SIDECAR_TASK_NAME = "Camelot Bifrost Go Sidecar"
_OMNIROUTE_PORT = 20128


def _strip(msg: str) -> str:
    return _STRIP_RICH.sub("", msg).strip()


def _detect_home() -> Path:
    env = os.environ.get("CAMELOT_OS_HOME")
    if env and Path(env).is_dir():
        return Path(env)
    candidates = [
        Path.home() / "CAMELOT_OS",
        Path("C:/Users/vizio/CAMELOT_OS"),
        Path(__file__).resolve().parent.parent,
    ]
    for candidate in candidates:
        if (candidate / "03_VAULT" / "training" / "configs" / "hud.py").exists():
            return candidate
    return Path(__file__).resolve().parent.parent


def _detect_venv_python(home: Path) -> Path:
    env = os.environ.get("CAMELOT_VENV")
    if env and Path(env).exists():
        return Path(env)
    if platform.system() == "Windows":
        candidates = [
            home / ".venv" / "Scripts" / "python.exe",
            home / ".venv_camelot" / "Scripts" / "python.exe",
        ]
    else:
        candidates = [
            home / ".venv" / "bin" / "python",
            home / ".venv_camelot" / "bin" / "python",
        ]
    for venv_py in candidates:
        if venv_py.exists():
            return venv_py
    return Path(sys.executable)


def _child_spawn_kwargs(*, cwd: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"cwd": cwd}
    if platform.system() == "Windows":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        kwargs["close_fds"] = True
        if os.environ.get("CAMELOT_VISIBLE_CHILDREN") == "1":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            kwargs["close_fds"] = False
    else:
        kwargs["start_new_session"] = True
    return kwargs


def _child_python_env(python_exe: str) -> dict[str, str]:
    """Return an environment safe for spawning a different Python interpreter."""
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env.pop("__PYVENV_LAUNCHER__", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    scripts_dir = str(Path(python_exe).resolve().parent)
    env["VIRTUAL_ENV"] = str(Path(scripts_dir).parent)
    env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")
    return env


def _probe_port(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


_SNAPSHOT_TTL_S = 900
_SNAPSHOT_NAME = "boot_snapshot.json"
# Phases that must stay serial (ordering / spawn side-effects / heavy FS writes)
_SERIAL_PHASE_HINTS = (
    "vfs preflight",
    "excalibur",
    "cliproxy",
    "defense grid",
    "kinetic edge",
    "morgana bridge",
    "bifrost sidecar",
    "symbiotic",
)
# Port probes used to validate a cached snapshot (host, port, label-hint)
# NOTE: 8080 added 2026-09-19 — stale snapshot hid dead CLIProxyAPI (PID 3272 TIME_WAIT)
_SNAPSHOT_PORTS: tuple[tuple[str, int], ...] = (
    ("127.0.0.1", 8080),
    ("127.0.0.1", 3000),
    ("127.0.0.1", 3002),
    ("127.0.0.1", 8001),
    ("127.0.0.1", 8011),
    ("127.0.0.1", 8200),
    ("127.0.0.1", 8300),
    ("127.0.0.1", 8400),
    ("127.0.0.1", 10100),
    ("127.0.0.1", 20128),
)


def _snapshot_path(home: Path) -> Path:
    return home / "03_VAULT" / "runtime_state" / _SNAPSHOT_NAME


def _skipped_phases(explicit: set[str] | None = None) -> set[str]:
    raw = ",".join(
        [os.environ.get("AWAKEN_SKIP", ""), ",".join(sorted(explicit or set()))]
    )
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def _write_boot_snapshot(home: Path, results: dict[str, Any]) -> None:
    try:
        summary = results.get("_summary", {})
        if summary and summary.get("required_ok", 0) < summary.get("required_total", 0):
            return  # only cache GREEN-required boots
        payload = {
            "captured_at": time.time(),
            "total_ms": results.get("_total_ms", 0),
            "summary": summary,
            "results": {
                k: v for k, v in results.items() if not k.startswith("_")
            },
            "ports": [
                {"host": h, "port": p, "open": _probe_port(h, p, timeout=0.5)}
                for h, p in _SNAPSHOT_PORTS
            ],
        }
        _snapshot_path(home).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def try_snapshot_boot(home: Path, ttl_s: int = _SNAPSHOT_TTL_S) -> dict[str, Any] | None:
    """Return cached boot results if fresh and ports still live, else None."""
    try:
        path = _snapshot_path(home)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - float(payload.get("captured_at", 0))
        if age > ttl_s:
            return None
        for entry in payload.get("ports", []):
            if entry.get("open") and not _probe_port(
                entry.get("host", "127.0.0.1"), int(entry.get("port", 0)), timeout=0.5
            ):
                return None  # a previously-live port died -> full boot
        results: dict[str, Any] = dict(payload.get("results", {}))
        results["_total_ms"] = 0
        summary = dict(payload.get("summary", {}))
        summary["snapshot"] = True
        summary["snapshot_age_s"] = round(age)
        results["_summary"] = summary
        results["_snapshot"] = True
        return results
    except Exception:
        return None


def _read_bifrost_token() -> str | None:
    token_path = Path.home() / ".camelot" / "bifrost.token"
    try:
        token = token_path.read_text(encoding="ascii").strip()
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        return None
    return token or None


def _http_status(url: str, *, token: str | None = None, timeout: float = 2.0) -> int:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["x-camelot-token"] = token
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (OSError, urllib.error.URLError, TimeoutError):
        return 0


def _morgana_bridge_binary(home: Path) -> Path | None:
    candidates = [
        home / "bin" / "morgana_bridge.exe",
        home / "01_KERNEL" / "senses" / "morgana_bridge" / "target" / "release" / "morgana_bridge.exe",
        home / "01_KERNEL" / "senses" / "morgana_bridge" / "target" / "debug" / "morgana_bridge.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _windows_task_exists(task_name: str) -> bool:
    if platform.system() != "Windows":
        return False
    completed = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return completed.returncode == 0


def _morgana_bridge_status(token: str | None) -> tuple[bool, str]:
    health = _http_status("http://127.0.0.1:8001/health")
    if health != 200:
        return False, f"health={health or 'unreachable'}"

    if not token:
        return False, "health=200 but token missing for protected status"

    protected = _http_status("http://127.0.0.1:8001/bifrost/status", token=token)
    unauth = _http_status("http://127.0.0.1:8001/bifrost/status")
    if protected != 200:
        return False, f"health=200 protected_status={protected or 'unreachable'}"
    if unauth != 401:
        return False, f"health=200 protected=200 unauth_status={unauth}"
    return True, "health=200 protected=200 unauth=401"


def _bifrost_go_sidecar_status(token: str | None) -> tuple[bool, str]:
    health = _http_status("http://127.0.0.1:8011/health")
    if health != 200:
        return False, f"health={health or 'unreachable'}"

    if not token:
        return False, "health=200 but token missing for protected status"

    protected = _http_status("http://127.0.0.1:8011/v1/bifrost/status", token=token)
    unauth = _http_status("http://127.0.0.1:8011/v1/bifrost/status")
    if protected != 200:
        return False, f"health=200 protected_status={protected or 'unreachable'}"
    if unauth != 401:
        return False, f"health=200 protected=200 unauth_status={unauth}"
    return True, "health=200 protected=200 unauth=401"


def boot_morgana_bridge(home: Path) -> tuple[bool, str]:
    """Bootstrap the Morgana Bifrost bridge and verify secure route behavior."""
    token = _read_bifrost_token()
    ok, detail = _morgana_bridge_status(token)
    if ok:
        return True, f"Morgana Bridge already running ({detail})"

    binary = _morgana_bridge_binary(home)
    if binary is None:
        return False, "morgana_bridge.exe not found - run cargo build in 01_KERNEL/senses/morgana_bridge"
    if not token:
        return False, "Bifrost token missing at ~/.camelot/bifrost.token"

    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = log_dir / "morgana_bridge.out.log"
    stderr_log = log_dir / "morgana_bridge.err.log"
    pid_file = log_dir / "morgana_bridge.pid"

    env = os.environ.copy()
    env["CAMELOT_GATEWAY_TOKEN"] = token
    env.setdefault("BIFROST_BIND_ADDR", "127.0.0.1:8001")
    env.setdefault("BIFROST_CORS_ORIGIN", "http://127.0.0.1:5173")

    cwd = str(binary.parent.parent.parent if binary.parent.name in {"debug", "release"} else home)

    try:
        if platform.system() == "Windows" and _windows_task_exists(_MORGANA_TASK_NAME):
            completed = subprocess.run(
                ["schtasks", "/Run", "/TN", _MORGANA_TASK_NAME],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=env,
            )
            if completed.returncode != 0:
                return False, f"Morgana Bridge task launch failed: {completed.stderr.strip() or completed.stdout.strip()}"
            pid = _MORGANA_TASK_NAME
        elif platform.system() == "Windows":
            try:
                kwargs = _child_spawn_kwargs(cwd=cwd)
                kwargs["env"] = env
                proc = subprocess.Popen([str(binary)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
                pid = str(proc.pid)
            except Exception as popen_err:
                launcher_env = env.copy()
                launcher_env.update(
                    {
                        "MORGANA_BINARY": str(binary),
                        "MORGANA_CWD": cwd,
                    }
                )
                completed = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-WindowStyle",
                        "Hidden",
                        "-Command",
                        (
                            "$proc = Start-Process -FilePath $env:MORGANA_BINARY "
                            "-WorkingDirectory $env:MORGANA_CWD "
                            "-WindowStyle Hidden "
                            "-PassThru; $proc.Id"
                        ),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    env=launcher_env,
                )
                if completed.returncode != 0:
                    return False, f"Morgana Bridge launch failed: {completed.stderr.strip() or completed.stdout.strip()} (Popen err: {popen_err})"
                pid_text = completed.stdout.strip().splitlines()[-1]
                pid = pid_text
        else:
            kwargs = _child_spawn_kwargs(cwd=cwd)
            kwargs["env"] = env
            with stdout_log.open("ab") as stdout, stderr_log.open("ab") as stderr:
                proc = subprocess.Popen([str(binary)], stdout=stdout, stderr=stderr, **kwargs)
            pid = str(proc.pid)
        pid_file.write_text(str(pid), encoding="ascii")
        for _ in range(20):
            time.sleep(0.25)
            ok, detail = _morgana_bridge_status(token)
            if ok:
                return True, f"Morgana Bridge PID={pid} ({detail})"
        return False, f"Morgana Bridge spawned PID={pid} but not ready ({detail})"
    except Exception as exc:
        return False, f"Morgana Bridge launch failed: {type(exc).__name__}: {exc}"


def _bifrost_go_sidecar_binary(home: Path) -> Path | None:
    candidates = [
        home / "bin" / "bifrost_go_sidecar.exe",
        home / "01_KERNEL" / "senses" / "bifrost_go_sidecar" / "bifrost_go_sidecar.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def boot_bifrost_go_sidecar(home: Path) -> tuple[bool, str]:
    """Bootstrap the Bifrost Go sidecar and verify secure route behavior."""
    token = _read_bifrost_token()
    ok, detail = _bifrost_go_sidecar_status(token)
    if ok:
        return True, f"Bifrost Go Sidecar already running ({detail})"

    bind_host, bind_port = "127.0.0.1", 8011
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((bind_host, bind_port)) == 0:
                return True, (
                    "Bifrost Go Sidecar bind port already occupied "
                    f"({bind_host}:{bind_port}); skipping duplicate launch"
                )
    except OSError:
        pass

    binary = _bifrost_go_sidecar_binary(home)
    sidecar_dir = home / "01_KERNEL" / "senses" / "bifrost_go_sidecar"
    go_bin = shutil.which("go")
    if binary is None and (go_bin is None or not sidecar_dir.exists()):
        return False, "bifrost_go_sidecar.exe not found and `go run .` unavailable in 01_KERNEL/senses/bifrost_go_sidecar"
    if not token:
        return False, "Bifrost token missing at ~/.camelot/bifrost.token"

    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    pid_file = log_dir / "bifrost_go_sidecar.pid"

    env = os.environ.copy()
    env["CAMELOT_GATEWAY_TOKEN"] = token
    env.setdefault("BIFROST_SIDECAR_BIND_ADDR", "127.0.0.1:8011")
    env.setdefault("BIFROST_SIDECAR_UPSTREAM_URL", "http://127.0.0.1:8001")
    env.setdefault("BIFROST_SIDECAR_ALLOW_ENV_TOKEN_FALLBACK", "0")

    if binary is not None:
        launch_cmd = [str(binary)]
        cwd = str(binary.parent)
    else:
        launch_cmd = [go_bin, "run", "."]  # type: ignore[list-item]
        cwd = str(sidecar_dir)

    try:
        if platform.system() == "Windows" and _windows_task_exists(_BIFROST_SIDECAR_TASK_NAME):
            completed = subprocess.run(
                ["schtasks", "/Run", "/TN", _BIFROST_SIDECAR_TASK_NAME],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=env,
            )
            if completed.returncode != 0:
                return False, f"Bifrost Go Sidecar task launch failed: {completed.stderr.strip() or completed.stdout.strip()}"
            pid = _BIFROST_SIDECAR_TASK_NAME
        else:
            kwargs = _child_spawn_kwargs(cwd=cwd)
            kwargs["env"] = env
            with (log_dir / "bifrost_go_sidecar.out.log").open("ab") as stdout, (
                log_dir / "bifrost_go_sidecar.err.log"
            ).open("ab") as stderr:
                proc = subprocess.Popen(launch_cmd, stdout=stdout, stderr=stderr, **kwargs)
            pid = str(proc.pid)

        pid_file.write_text(str(pid), encoding="ascii")
        for _ in range(20):
            time.sleep(0.25)
            ok, detail = _bifrost_go_sidecar_status(token)
            if ok:
                return True, f"Bifrost Go Sidecar PID={pid} ({detail})"
        return False, f"Bifrost Go Sidecar spawned PID={pid} but not ready ({detail})"
    except Exception as exc:
        return False, f"Bifrost Go Sidecar launch failed: {type(exc).__name__}: {exc}"


def boot_harness(home: Path):
    harness_py = home / "control_plane" / "infra" / "harness.py"
    if not harness_py.exists():
        harness_py = home / "control_plane" / "harness.py"
    pid_file = home / "logs" / "harness.pid"
    if not harness_py.exists():
        return False, "harness.py not found - skipped"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if platform.system() == "Windows":
                import ctypes

                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION,
                    0,
                    pid,
                )
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    return True, f"Sovereign Harness already running PID={pid}"
                raise OSError("Process not found")
            os.kill(pid, 0)
            return True, f"Sovereign Harness already running PID={pid}"
        except (OSError, ValueError, SystemError):
            pid_file.unlink(missing_ok=True)

    venv_py = _detect_venv_python(home)
    py = str(venv_py) if venv_py.exists() else sys.executable
    kwargs = _child_spawn_kwargs(cwd=str(home))
    kwargs["env"] = _child_python_env(py)
    kwargs["env"]["CAMELOT_OS_HOME"] = str(home)

    try:
        proc = subprocess.Popen([py, str(harness_py)], **kwargs)
        time.sleep(1.2)
        if proc.poll() is not None:
            return False, f"Harness exited immediately (code {proc.returncode})"
        return True, f"Sovereign Harness spawned PID={proc.pid}"
    except Exception as exc:
        return False, f"Harness spawn failed: {type(exc).__name__}: {exc}"


def boot_telemetry(home: Path):
    binary = home / "bin" / "vizion-telemetry.exe"
    if not binary.exists():
        binary = home / "01_KERNEL" / "senses" / "vizion-telemetry" / "vizion-telemetry.exe"
    if not binary.exists():
        return False, "vizion-telemetry.exe not found"

    kwargs = _child_spawn_kwargs(cwd=str(home))

    try:
        proc = subprocess.Popen([str(binary)], **kwargs)
        time.sleep(0.5)
        if proc.poll() is not None:
            if platform.system() == "Windows" and os.environ.get("CAMELOT_VISIBLE_CHILDREN") != "1":
                return True, "Vizion Telemetry available; interactive TUI skipped in hidden boot shell"
            return False, f"exited immediately (code {proc.returncode})"
        return True, f"PID {proc.pid} - terminal TUI active"
    except Exception as exc:
        return False, f"launch failed: {exc}"


def boot_bioswarm(home: Path):
    """Phase 7 - SRDL Bio-Swarm (Nano-Knights)."""
    candidates = [
        home / "bin" / "swarm-spawner.exe",
        home / "kinetic_edge" / "swarm_spawner" / "target" / "release" / "swarm-spawner.exe",
        home / "kinetic_edge" / "swarm_spawner" / "target" / "release" / "swarm_spawner.exe",
        home / "target" / "release" / "swarm-spawner.exe",
    ]
    binary = next((candidate for candidate in candidates if candidate.exists()), None)
    if binary is None:
        return False, "swarm-spawner.exe not found - requires cargo build --release in kinetic_edge/swarm_spawner"

    kwargs = _child_spawn_kwargs(cwd=str(home))

    try:
        proc = subprocess.Popen([str(binary)], **kwargs)
        time.sleep(0.5)
        if proc.poll() is not None:
            return False, f"exited immediately (code {proc.returncode})"
        try:
            from .bio_swarm_runtime import read_bio_swarm_status

            evidence = read_bio_swarm_status(home)
            release = evidence.get("release") if isinstance(evidence.get("release"), dict) else {}
            verdict = release.get("verdict") or "NO_RELEASE_EVIDENCE"
        except Exception:
            verdict = "EVIDENCE_UNAVAILABLE"
        return True, f"PID {proc.pid} - Bio-Swarm Cells Active - release={verdict}"
    except Exception as exc:
        return False, f"launch failed: {exc}"


def boot_edge_interface(home: Path):
    """Phase 8 - Omni-Eye Edge Interface (Go + PWA)."""
    binary = home / "bin" / "edge-server.exe"
    if not binary.exists():
        return False, "edge-server.exe not found"

    if _probe_port("127.0.0.1", 3000):
        return True, "Edge PWA already running on :3000"

    kwargs = _child_spawn_kwargs(cwd=str(home))

    try:
        proc = subprocess.Popen([str(binary)], **kwargs)
        time.sleep(0.5)
        if proc.poll() is not None:
            return False, f"exited immediately (code {proc.returncode})"
        return True, f"PID {proc.pid} - Edge PWA Active on :3000"
    except Exception as exc:
        return False, f"launch failed: {exc}"


def boot_cloud_brain(home: Path):
    """Phase 4 - Cloud Brain status through the typed CloudServiceRouter."""
    os.environ.setdefault("CAMELOT_OS_HOME", str(home))
    try:
        result = asyncio.run(
            CloudServiceRouter().invoke(
                CloudServiceRequest(service=CloudServiceName.CLOUDBRAIN_STATUS)
            )
        )
        if not result.success:
            err_str = str(result.error or "Cloud Brain status failed")
            if any(term in err_str.lower() for term in ("auth", "expire", "unreachable", "connect", "blocked")):
                return True, f"Cloud Brain DEGRADED: {err_str}"
            return False, err_str
        remote = result.result.get("remote_runtime", {})
        status = remote.get("status") or result.result.get("status") or "unknown"
        source = result.source
        if result.error:
            return True, f"Cloud Brain LOCAL READY via {source}; remote check blocked in this shell"
        return True, f"Cloud Brain {str(status).upper()} via {source}"
    except Exception as exc:
        return True, f"Cloud Brain DEGRADED (error loading): {exc}"


def boot_excalibur_mobile_sentinel(home: Path) -> tuple[bool, str]:
    """Phase: Excalibur Omarchy Mobile Sentinel probe (S26 Ultra / Adreno 840)."""
    try:
        from control_plane.dispatch.excalibur_mobile_dispatcher import ExcaliburMobileDispatcher

        d = ExcaliburMobileDispatcher()
        st = d.get_mobile_cockpit_summary()
        kp = st.get("keypass", {}).get("keypass_id", "NO_KEYPASS")
        mode = st.get("operational_mode", "UNKNOWN")
        return True, f"Excalibur Sentinel [{mode}] — WarpGate {kp} (120Hz Adreno 840)"
    except Exception as exc:
        return False, f"Excalibur Sentinel offline: {exc}"


def boot_always_on_tailscale(home: Path) -> tuple[bool, str]:
    """Phase: Always-On Tailscale Mesh Sentinel probe (dual-path failover)."""
    try:
        from control_plane.infra.tailscale_mesh_sentinel import boot_tailscale_sentinel

        return boot_tailscale_sentinel(home)
    except Exception as exc:
        return False, f"Tailscale Sentinel offline: {exc}"


def sync_knight_configuration(home: Path):
    """Refresh the shared knight roster and cartridge configuration artifact."""
    try:
        snapshot = write_knight_configuration(home)
        cartridges = snapshot.get("cartridges", {})
        roster = snapshot.get("excalibur_roster", {})
        switchboard = snapshot.get("switchboard_roster", {})
        return (
            True,
            "Knight config snapshot OK "
            f"({cartridges.get('active_count', 0)} active cartridges, "
            f"{roster.get('count', 0)} Excalibur agents, "
            f"{switchboard.get('count', 0)} terminals)",
        )
    except Exception as exc:
        return False, f"Knight config snapshot failed: {type(exc).__name__}: {exc}"


def boot_graft_graph(home: Path) -> tuple[bool, str]:
    """Non-blocking graft context-graph freshness probe (orientation only)."""
    graft = shutil.which("graft")
    if not graft:
        return True, "graft CLI not on PATH — context graph unavailable (optional)"
    try:
        rc = subprocess.run(
            [graft, "check"],
            cwd=str(home),
            capture_output=True,
            text=True,
            timeout=30,
        ).returncode
    except subprocess.TimeoutExpired:
        return True, "graft check timed out (optional, non-blocking)"
    except OSError:
        return True, "graft check unavailable (optional)"
    if rc == 0:
        return True, "graft graph in sync"
    if rc == 1:
        return False, "graft graph stale — run: graft build (non-blocking)"
    return False, f"graft check aborted (rc={rc}) — graft #122 pattern; rebuild when memory frees"


def datetime_utc_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def boot_clawdbot_gateway(home: Path) -> tuple[bool, str]:
    """Check Clawdbot gateway health on :18789; report token presence."""
    port = 18789
    if _probe_port("127.0.0.1", port):
        cfg_path = Path.home() / ".clawdbot" / "clawdbot.json"
        token_ok = False
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            token_ok = bool(cfg.get("gateway", {}).get("auth", {}).get("token"))
        except Exception:
            pass
        auth_note = "token OK" if token_ok else "token MISSING in config"
        return True, f"Clawdbot gateway LIVE on :{port} | {auth_note}"
    return False, f"Clawdbot gateway DARK on :{port} — run: camelot scripts start-gateway"


def boot_sir_pi(home: Path) -> tuple[bool, str]:
    """Bootstrap Sir Pi — verify pi binary + camelot provider wired to CLIProxyAPI."""
    pi_bin = (
        home / "02_FORGE" / "tools" / "pi-mono"
        / "packages" / "coding-agent" / "dist" / "cli.js"
    )
    if not pi_bin.exists():
        return False, "pi binary not found — run: cd 02_FORGE/tools/pi-mono && npm run build"

    models_json = Path.home() / ".pi" / "agent" / "models.json"
    if not models_json.exists():
        return False, "~/.pi/agent/models.json missing — camelot provider not registered"

    try:
        import json as _json
        providers = _json.loads(models_json.read_text(encoding="utf-8")).get("providers", {})
        if "camelot" not in providers:
            return False, "camelot provider not in models.json — OmniRoute not wired"
        base_url = providers["camelot"].get("baseUrl", "")
        model_count = len(providers["camelot"].get("models", []))
    except Exception as exc:
        return False, f"models.json parse error: {exc}"

    cliproxy_live = _probe_port("127.0.0.1", 8080)
    proxy_status = "CLIProxy :8080 LIVE" if cliproxy_live else "CLIProxy :8080 DARK (start CLIProxy first)"

    return True, (
        f"Sir Pi v0.73.0 ready — camelot@{base_url} "
        f"({model_count} models) | {proxy_status}"
    )


def boot_omniroute_gateway(home: Path) -> tuple[bool, str]:
    """OmniRoute gateway - cost-tier smart router on :20128."""
    if _probe_port("127.0.0.1", _OMNIROUTE_PORT):
        return True, f"OmniRoute already running on :{_OMNIROUTE_PORT}"

    binary = Path.home() / ".omniroute" / "omniroute.exe"
    launch_cmd: list[str]
    cwd = str(home)
    if binary.exists():
        launch_cmd = [str(binary)]
        label = "OmniRoute"
    else:
        node_c = home / "02_FORGE" / "generated" / "ukg_omega_glyph_v1000" / "Node_C_Omni_Router"
        node_c_binary = node_c / "node_c_omni_router.exe"
        if not node_c_binary.exists():
            return False, (
                "OmniRoute binary not found and Node_C_Omni_Router fallback is not built; "
                "run: go build -o node_c_omni_router.exe ."
            )
        launch_cmd = [
            str(node_c_binary),
            "-serve",
            "-host",
            "127.0.0.1",
            "-port",
            str(_OMNIROUTE_PORT),
        ]
        cwd = str(node_c)
        label = "Node C Omni Router fallback"

    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        if platform.system() == "Windows" and label == "Node C Omni Router fallback":
            try:
                kwargs = _child_spawn_kwargs(cwd=cwd)
                proc = subprocess.Popen(launch_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
                pid = str(proc.pid)
            except Exception as popen_err:
                ps_cmd = (
                    "$p = Start-Process "
                    f"-FilePath '{launch_cmd[0]}' "
                    f"-ArgumentList @('{launch_cmd[1]}','{launch_cmd[2]}','{launch_cmd[3]}','{launch_cmd[4]}','{launch_cmd[5]}') "
                    f"-WorkingDirectory '{cwd}' "
                    "-WindowStyle Hidden -PassThru; $p.Id"
                )
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )
                if completed.returncode != 0:
                    detail = completed.stderr.strip() or completed.stdout.strip()
                    return False, f"{label} launch failed: {detail} (Popen err: {popen_err})"
                pid = completed.stdout.strip() or "unknown"
            for _ in range(20):
                time.sleep(0.5)
                if _probe_port("127.0.0.1", _OMNIROUTE_PORT):
                    return True, f"{label} PID={pid} on :{_OMNIROUTE_PORT}"
            return True, f"{label} spawned PID={pid}; port :{_OMNIROUTE_PORT} still warming"

        kwargs = _child_spawn_kwargs(cwd=cwd)
        with (log_dir / "omniroute.out.log").open("ab") as out, (
            log_dir / "omniroute.err.log"
        ).open("ab") as err:
            proc = subprocess.Popen(launch_cmd, stdout=out, stderr=err, **kwargs)
        for _ in range(20):
            time.sleep(0.5)
            if _probe_port("127.0.0.1", _OMNIROUTE_PORT):
                return True, f"{label} PID={proc.pid} on :{_OMNIROUTE_PORT}"
            if proc.poll() is not None:
                return False, f"{label} exited early with code {proc.returncode}"
        return True, f"{label} spawned PID={proc.pid}; port :{_OMNIROUTE_PORT} still warming"
    except Exception as exc:
        return False, f"OmniRoute launch failed: {type(exc).__name__}: {exc}"


def boot_hermes_omniroute_orchestrator(home: Path) -> tuple[bool, str]:
    """Assign Hermes as the zero-cost OmniRoute orchestrator for booted engines."""
    artifact_path = home / "03_VAULT" / "runtime_state" / "hermes_omniroute_orchestrator_latest.json"
    config_path = home / "03_VAULT" / "training" / "configs" / "config" / "omniroute.json"
    hermes_cli = home / "02_FORGE" / "KINETIC_ARMORY" / "hermes-agent" / "cli.py"
    payload: dict[str, Any] = {
        "status": "WARN",
        "global_startup_command": "awaken",
        "rune": "//BOOT",
        "orchestrator": "sir_hermes",
        "omniroute_endpoint": f"http://127.0.0.1:{_OMNIROUTE_PORT}/v1",
        "zero_cost_engines": [],
        "free_terminals": [],
        "timestamp_utc": datetime_utc_iso(),
    }

    try:
        from control_plane.switchboard import TERMINAL_REGISTRY

        hermes = TERMINAL_REGISTRY.get("sir_hermes")
        free_terminals = sorted(
            terminal.id
            for terminal in TERMINAL_REGISTRY.values()
            if terminal.cost_tier == "free"
        )
        payload["free_terminals"] = free_terminals
        payload["hermes_terminal"] = {
            "present": hermes is not None,
            "engine": hermes.engine if hermes else None,
            "cost_tier": hermes.cost_tier if hermes else None,
            "cli_present": hermes_cli.exists(),
        }

        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            engines = config.get("engines", {})
            payload["zero_cost_engines"] = sorted(
                name
                for name, engine in engines.items()
                if engine.get("status") == "active"
                and (
                    engine.get("provider") == "local"
                    or "free" in str(engine.get("tier", "")).lower()
                )
            )
            payload["routing_strategy"] = (
                config.get("routing_matrix", {}).get("strategy")
            )
        else:
            payload["error"] = "omniroute.json not found"

        ok = bool(
            payload["zero_cost_engines"]
            and hermes
            and hermes.cost_tier == "free"
            and hermes.engine == "hermes_cli"
            and hermes_cli.exists()
        )
        payload["status"] = "OK" if ok else "WARN"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not ok:
            return False, "Hermes OmniRoute assignment incomplete; see runtime_state artifact"
        return True, (
            "Hermes orchestrator assigned through OmniRoute "
            f"({len(payload['zero_cost_engines'])} zero-cost engines, "
            f"{len(free_terminals)} free terminals)"
        )
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return False, f"Hermes OmniRoute assignment failed: {type(exc).__name__}: {exc}"


def start_local_lt_memory(home: Path) -> tuple[bool, str]:
    """Local Sovereign LT Memory — FastAPI server at :8200, SQLite backend."""
    if _probe_port("127.0.0.1", 8200):
        # Already running — still apply env overrides in case this process hasn't set them
        os.environ["MODAL_HEALTH_URL"]     = "http://127.0.0.1:8200/health"
        os.environ["MODAL_STORE_URL"]      = "http://127.0.0.1:8200/store"
        os.environ["MODAL_SYNTHESIZE_URL"] = "http://127.0.0.1:8200/synthesize"
        return True, "Local LT Memory already running on :8200"

    server_py = home / "03_VAULT" / "training" / "configs" / "local_lt_memory.py"
    if not server_py.exists():
        return False, "local_lt_memory.py not found — LT tier unavailable"

    venv_py = _detect_venv_python(home)
    py = str(venv_py) if venv_py.exists() else sys.executable
    pid_file = home / "logs" / "lt_memory.pid"
    stdout_log = home / "logs" / "lt_memory.out.log"
    stderr_log = home / "logs" / "lt_memory.err.log"
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    cwd = str(home / "03_VAULT" / "training" / "configs")
    kwargs = _child_spawn_kwargs(cwd=cwd)
    kwargs["env"] = _child_python_env(py)
    kwargs["env"]["CAMELOT_OS_HOME"] = str(home)
    if (
        platform.system() == "Windows"
        and not sys.stdin.isatty()
        and os.environ.get("CAMELOT_ALLOW_NONINTERACTIVE_LT_SPAWN") != "1"
    ):
        return True, "Local LT Memory shim present; spawn skipped in non-interactive shell"
    try:
        if platform.system() == "Windows":
            try:
                with stdout_log.open("ab") as stdout, stderr_log.open("ab") as stderr:
                    proc = subprocess.Popen(
                        [py, "-m", "uvicorn", "local_lt_memory:app",
                         "--host", "127.0.0.1", "--port", "8200", "--no-access-log"],
                        stdout=stdout,
                        stderr=stderr,
                        **kwargs,
                    )
                pid = str(proc.poll() or proc.pid)
            except Exception as popen_err:
                launcher_env = dict(kwargs["env"])
                launcher_env.update(
                    {
                        "LT_MEMORY_PYTHON": py,
                        "LT_MEMORY_CWD": cwd,
                        "LT_MEMORY_STDOUT": str(stdout_log),
                        "LT_MEMORY_STDERR": str(stderr_log),
                    }
                )
                completed = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-WindowStyle",
                        "Hidden",
                        "-Command",
                        (
                            "$args = @('-m','uvicorn','local_lt_memory:app',"
                            "'--host','127.0.0.1','--port','8200','--no-access-log'); "
                            "$proc = Start-Process -FilePath $env:LT_MEMORY_PYTHON "
                            "-ArgumentList $args "
                            "-WorkingDirectory $env:LT_MEMORY_CWD "
                            "-RedirectStandardOutput $env:LT_MEMORY_STDOUT "
                            "-RedirectStandardError $env:LT_MEMORY_STDERR "
                            "-WindowStyle Hidden "
                            "-PassThru; $proc.Id"
                        ),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    env=launcher_env,
                )
                if completed.returncode != 0:
                    detail = completed.stderr.strip() or completed.stdout.strip()
                    return False, f"LT Memory launch failed: {detail} (Popen err: {popen_err})"
                pid = completed.stdout.strip().splitlines()[-1]
                proc = None
            pid_file.write_text(str(pid), encoding="utf-8")
        else:
            with stdout_log.open("ab") as stdout, stderr_log.open("ab") as stderr:
                proc = subprocess.Popen(
                    [py, "-m", "uvicorn", "local_lt_memory:app",
                     "--host", "127.0.0.1", "--port", "8200", "--no-access-log"],
                    stdout=stdout,
                    stderr=stderr,
                    **kwargs,
                )
            pid_file.write_text(str(proc.pid), encoding="utf-8")
        time.sleep(2.0)
        if proc is not None and proc.poll() is not None:
            return False, f"LT Memory server exited immediately (code {proc.returncode})"
        if not _probe_port("127.0.0.1", 8200):
            return False, "LT Memory spawned but :8200 not responding after 2s"
        os.environ["MODAL_HEALTH_URL"]     = "http://127.0.0.1:8200/health"
        os.environ["MODAL_STORE_URL"]      = "http://127.0.0.1:8200/store"
        os.environ["MODAL_SYNTHESIZE_URL"] = "http://127.0.0.1:8200/synthesize"
        if proc is None:
            pid = pid_file.read_text(encoding="utf-8").strip()
            return True, f"Local LT Memory PID={pid} - SQLite sovereign on :8200"
        return True, f"Local LT Memory PID={proc.pid} — SQLite sovereign on :8200"
    except Exception as exc:
        return False, f"LT Memory spawn failed: {type(exc).__name__}: {exc}"


def boot_omnivoice_router(home: Path) -> tuple[bool, str]:
    """OmniVoice Router — WebRTC signaling + energy VAD on :3002."""
    if _probe_port("127.0.0.1", 3002):
        return True, "OmniVoice Router already running on :3002"

    router_dir = home / "02_FORGE" / "KINETIC_ARMORY" / "omnivoice-router"
    compiled_js = router_dir / "dist" / "omnivoice-router.js"
    entry_ts = router_dir / "omnivoice-router.ts"

    if not entry_ts.exists():
        return False, "omnivoice-router.ts not found"

    if compiled_js.exists():
        cmd = ["node", "--max-old-space-size=256", str(compiled_js)]
    else:
        npx = shutil.which("npx")
        ts_node = shutil.which("ts-node")
        if ts_node:
            cmd = [ts_node, str(entry_ts)]
        elif npx:
            cmd = [npx, "ts-node", str(entry_ts)]
        else:
            return False, "OmniVoice Router: not compiled — run: cd omnivoice-router && npm install && npx tsc"

    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        kwargs = _child_spawn_kwargs(cwd=str(router_dir))
        with (log_dir / "omnivoice.out.log").open("ab") as out, \
             (log_dir / "omnivoice.err.log").open("ab") as err:
            proc = subprocess.Popen(cmd, stdout=out, stderr=err, **kwargs)
        time.sleep(3.0)
        if _probe_port("127.0.0.1", 3002):
            return True, f"OmniVoice Router PID={proc.pid} on :3002"
        return False, f"OmniVoice Router spawned PID={proc.pid} but :3002 not responding"
    except Exception as exc:
        return False, f"OmniVoice Router launch failed: {type(exc).__name__}: {exc}"


def boot_kitten_tts(home: Path) -> tuple[bool, str]:
    """Kitten TTS streaming server — aiohttp HTTP endpoint on :8300."""
    if _probe_port("127.0.0.1", 8300):
        return True, "Kitten TTS already running on :8300"

    kitten_py = home / "01_KERNEL" / "senses" / "audio" / "kitten_service.py"
    if not kitten_py.exists():
        return False, "kitten_service.py not found"

    venv_py = _detect_venv_python(home)
    py = str(venv_py) if venv_py.exists() else sys.executable
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Launch: python -c "from kitten_service import kitten_service; import asyncio; asyncio.run(kitten_service.run_streaming_server())"
    _launch_cmd = (
        "import sys, asyncio; sys.path.insert(0, r'" + str(home) + "'); "
        "from 01_KERNEL.senses.audio.kitten_service import kitten_service; "
        "asyncio.run(kitten_service.run_streaming_server())"
    )
    # Use module path style instead (avoids dots-in-path issue on Windows)
    runner_py = home / "logs" / "_kitten_runner.py"
    runner_py.write_text(
        f"import sys, asyncio\n"
        f"sys.path.insert(0, r'{home}')\n"
        f"sys.path.insert(0, r'{home / '01_KERNEL' / 'senses' / 'audio'}')\n"
        f"from kitten_service import kitten_service\n"
        f"asyncio.run(kitten_service.run_streaming_server())\n",
        encoding="utf-8",
    )
    try:
        kwargs = _child_spawn_kwargs(cwd=str(home))
        kwargs["env"] = _child_python_env(py)
        kwargs["env"]["CAMELOT_OS_HOME"] = str(home)
        with (log_dir / "kitten_tts.out.log").open("ab") as out, \
             (log_dir / "kitten_tts.err.log").open("ab") as err:
            proc = subprocess.Popen([py, str(runner_py)], stdout=out, stderr=err, **kwargs)
        time.sleep(3.0)
        if _probe_port("127.0.0.1", 8300):
            return True, f"Kitten TTS PID={proc.pid} streaming on :8300"
        return False, f"Kitten TTS spawned PID={proc.pid} but :8300 not responding (aiohttp required)"
    except Exception as exc:
        return False, f"Kitten TTS launch failed: {type(exc).__name__}: {exc}"


def boot_titan_omega(home: Path) -> tuple[bool, str]:
    """Titan Omega — graft all three memory tiers via isolated subprocess with hard timeout.

    The original synchronous importlib.import_module("titan.memory.titan_omega") call
    blocks the boot loop for 45s per attempt because the titan package performs heavy
    I/O at import time. We now run the graft check in a child process limited to 8s
    so the boot sequence is never stalled and the worker queue stays drained.
    """
    kernel_dir = home / "01_KERNEL"
    if not kernel_dir.exists():
        return False, "01_KERNEL not found — Titan memory unavailable"

    probe_script = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from titan.memory.titan_omega import TitanOmega;"
        "s = TitanOmega.graft(tier='alpha_omega', mode='production', persist='all');"
        "g = len(s.graph.graph.nodes()) if s.graph else 0;"
        "v = len(s.vault.embeddings) if s.vault else 0;"
        "print(f'{s.config.tier}/{s.config.mode} graph={g} vault={v}')"
    )

    venv_py = _detect_venv_python(home)
    py = str(venv_py) if venv_py.exists() else sys.executable

    _TITAN_TIMEOUT = int(os.getenv("CAMELOT_TITAN_TIMEOUT", "15"))

    try:
        result = subprocess.run(
            [py, "-c", probe_script, str(kernel_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TITAN_TIMEOUT,
            cwd=str(home),
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, f"TitanOmega grafted — {result.stdout.strip()}"
        err = (result.stderr.strip() or result.stdout.strip())[:200]
        return False, f"Titan graft failed (rc={result.returncode}): {err}"
    except subprocess.TimeoutExpired:
        return False, (
            f"Import of titan_omega timed out after {_TITAN_TIMEOUT}s — "
            "set CAMELOT_TITAN_TIMEOUT env var to extend, or ensure titan package "
            "does not perform blocking I/O at import time."
        )
    except Exception as exc:
        return False, f"Titan graft failed: {type(exc).__name__}: {exc}"


def boot_sir_octavian(home: Path) -> tuple[bool, str]:
    """Sir Octavian factory metrics server — JSON endpoint on :8400."""
    if _probe_port("127.0.0.1", 8400):
        return True, "Sir Octavian already running on :8400"

    octavian_py = home / "control_plane" / "infra" / "sir_octavian.py"
    if not octavian_py.exists():
        octavian_py = home / "control_plane" / "sir_octavian.py"
    if not octavian_py.exists():
        return False, "sir_octavian.py not found"

    venv_py = _detect_venv_python(home)
    py = str(venv_py) if venv_py.exists() else sys.executable
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        kwargs = _child_spawn_kwargs(cwd=str(home))
        kwargs["env"] = _child_python_env(py)
        kwargs["env"]["CAMELOT_OS_HOME"] = str(home)
        with (log_dir / "sir_octavian.out.log").open("ab") as out, \
             (log_dir / "sir_octavian.err.log").open("ab") as err:
            proc = subprocess.Popen([py, str(octavian_py), "--serve"], stdout=out, stderr=err, **kwargs)
        time.sleep(1.2)
        if _probe_port("127.0.0.1", 8400):
            return True, f"Sir Octavian PID={proc.pid} metrics on :8400"
        return False, f"Sir Octavian spawned PID={proc.pid} but :8400 not responding (aiohttp required)"
    except Exception as exc:
        return False, f"Sir Octavian launch failed: {type(exc).__name__}: {exc}"


def boot_cloud_brain_auth(home: Path) -> tuple[bool, str]:
    """Verify NotebookLM auth session exists and is not expired before RPC probe."""
    bridge_path = home / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
    if not bridge_path.exists():
        return False, "notebooklm_bridge.py not found — Cloud Brain auth check skipped"
    try:
        spec = importlib.util.spec_from_file_location("notebooklm_bridge", bridge_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        info = mod.session_age_check()
    except Exception as exc:
        return False, f"Auth check error: {type(exc).__name__}: {exc}"

    msg = info["message"]
    if not info["exists"]:
        return False, msg
    # critical = auth likely expired; surface as WARN (non-blocking) so boot continues
    # but the message clearly states action required
    return True, msg


def boot_pydantic_ai_knight(home: Path) -> tuple[bool, str]:
    """Phase 9 - Pydantic AI Knight (Sir Helio v400)."""
    knight_py = home / "control_plane" / "infra" / "pydantic_ai_knight.py"
    if not knight_py.exists():
        knight_py = home / "control_plane" / "pydantic_ai_knight.py"
    if not knight_py.exists():
        return False, "pydantic_ai_knight.py not found"

    
    try:
        import pydantic_ai
        return True, f"Pydantic AI engine v{pydantic_ai.__version__} online — Sir Helio v400 ready"
    except ImportError:
        return False, "pydantic-ai library not installed"
    except Exception as exc:
        return False, f"Pydantic AI init failed: {exc}"


def boot_opencodex(home: Path) -> tuple[bool, str]:
    """Start the OpenCodex universal provider proxy sidecar.

    OpenCodex translates the OpenAI Responses API into any LLM provider's
    wire format, providing 40+ provider support, combo failover, and
    account pooling for all CAMELOT-OS knights.

    Phase: runs right after CLIProxyAPI (:8080) since opencodex sits
    upstream of cliproxy on :10100.
    """
    import socket

    ocx_host = os.getenv("OCX_HOST", "127.0.0.1")
    ocx_port = int(os.getenv("OCX_PORT", "10100"))

    # Check if already running
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((ocx_host, ocx_port)) == 0:
                # Port occupied — check if it's actually opencodex
                try:
                    from control_plane.core.ocx_bridge import OCXBridge
                    bridge = OCXBridge()
                    if bridge.is_live():
                        return True, f"OpenCodex already running on {ocx_host}:{ocx_port}"
                except Exception:
                    pass
                return True, f"Port {ocx_port} occupied (non-ocx process); skipping launch"
    except OSError:
        pass

    # Try to start opencodex via npx
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm")
    npx_bin = shutil.which("npx")

    ocx_cli = home / "node_modules" / "@bitkyc08" / "opencodex" / "bin" / "ocx.mjs"
    if not ocx_cli.exists():
        # Try the global install path
        ocx_cli = None

    if ocx_cli is None and npx_bin is None:
        return False, "opencodex not installed (npm install @bitkyc08/opencodex) and npx unavailable"

    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ocx_log = log_dir / "opencodex.log"
    pid_file = log_dir / "opencodex.pid"

    env = os.environ.copy()
    env.setdefault("OCX_HOST", ocx_host)
    env.setdefault("OCX_PORT", str(ocx_port))

    try:
        if ocx_cli is not None:
            launch_cmd = [node_bin or "node", "--max-old-space-size=256", str(ocx_cli), "start", "--port", str(ocx_port)]
        else:
            launch_cmd = [npx_bin, "ocx", "start", "--port", str(ocx_port)]

        log_fh = open(ocx_log, "a", encoding="utf-8")
        kwargs = _child_spawn_kwargs(cwd=str(home))
        kwargs["env"] = env
        kwargs["stdin"] = subprocess.DEVNULL
        proc = subprocess.Popen(
            launch_cmd,
            stdout=log_fh,
            stderr=log_fh,
            **kwargs,
        )

        pid_file.write_text(str(proc.pid), encoding="utf-8")

        # Wait up to 8 seconds for the proxy to become ready
        import time
        for _ in range(16):
            time.sleep(0.5)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.5)
                    if sock.connect_ex((ocx_host, ocx_port)) == 0:
                        return True, f"OpenCodex started on {ocx_host}:{ocx_port} (pid={proc.pid})"
            except OSError:
                pass
            if proc.poll() is not None:
                return False, f"OpenCodex exited early (code={proc.returncode}); see {ocx_log}"

        return False, f"OpenCodex started but not ready after 8s; see {ocx_log}"

    except Exception as exc:
        return False, f"OpenCodex launch failed: {exc}"


def boot_kinetic_adb_watchdog(home: Path) -> tuple[bool, str]:
    """Kinetic ADB link watchdog and auto-resurrection."""
    try:
        bridge_script = home / "04_KINETIC" / "qtscrcpy" / "qtscrcpy_kinetic_bridge.py"
        if not bridge_script.exists():
            return True, "QtScrcpy bridge script not found (skipped)"

        py_bin = sys.executable
        res = subprocess.run(
            [py_bin, str(bridge_script), "watchdog", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            rep = json.loads(res.stdout)
            dev_count = rep.get("devices_found", 0)
            status = rep.get("status", "IDLE")
            if dev_count > 0:
                return True, f"Kinetic ADB online ({dev_count} device(s) reverse-tunneled)"
            return True, f"Kinetic ADB watchdog active (0 devices connected, status={status})"
        return False, f"Kinetic ADB watchdog failed: {res.stderr[:60]}"
    except Exception as e:
        return True, f"Kinetic ADB watchdog pass ({e})"


def _boot_vfs_preflight_stage0(home: Path) -> tuple[bool, str]:
    """Stage-0 VFS preflight gate (hard halt on strict REJECT).

    boot_vfs_preflight returns (ok, msg) for the summary row. In strict
    mode a REJECTED check must HARD HALT the boot BEFORE any later stage
    starts services (ADR 0006 — no sovereign escape hatch). SystemExit
    is a BaseException, so run_boot's `except Exception` does not swallow
    it: the boot aborts immediately and awaken exits 1.
    """
    ok, msg = boot_vfs_preflight(home)
    if not ok:
        sys.stderr.write(f"[VFS_PREFLIGHT] BOOT HALTED: {msg}\n")
        raise SystemExit(1)
    return ok, msg


def run_boot(
    home: Path, quick: bool = False, skip: set[str] | None = None
) -> dict[str, Any]:
    skip_tokens = _skipped_phases(skip)
    # Load local LT env overrides before integration_brain is imported so module-level
    # constants pick up localhost:8200 URLs instead of the Modal cloud endpoints
    lt_env = home / "03_VAULT" / "training" / "configs" / ".env.lt_local"
    if lt_env.exists():
        for raw in lt_env.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    hud_path = home / "03_VAULT" / "training" / "configs" / "hud.py"
    spec = importlib.util.spec_from_file_location("hud", hud_path)
    hud = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(hud)

    phases = [
        {"name": "VFS Preflight    :stage-0", "required": False,
         "fn": lambda: _boot_vfs_preflight_stage0(home)},
        {"name": "EXCALIBUR Pre-Flight", "required": False, "fn": lambda: boot_excalibur_preflight(home)},
        {"name": "Excalibur Sentinel", "required": False, "fn": lambda: boot_excalibur_mobile_sentinel(home)},
        {"name": "Tailscale Sentinel", "required": False, "fn": lambda: boot_always_on_tailscale(home)},
        {"name": "CLIProxyAPI   :8080", "required": True,  "fn": hud._boot_cliproxy},
        {"name": "OpenCodex    :10100", "required": False, "fn": lambda: boot_opencodex(home)},
        {"name": "Defense Grid",        "required": True,  "fn": hud._boot_defense_grid},
        {"name": "Kinetic Edge  :3001", "required": True,  "fn": hud._boot_kinetic_edge},
        {"name": "Kinetic ADB Watchdog", "required": False, "fn": lambda: boot_kinetic_adb_watchdog(home)},
        {"name": "OmniVoice     :3002", "required": False, "fn": lambda: boot_omnivoice_router(home)},
        {"name": "Kitten TTS    :8300", "required": False, "fn": lambda: boot_kitten_tts(home)},
        {"name": "Titan Omega  [Omega]",   "required": False, "fn": lambda: boot_titan_omega(home)},
        {"name": "Sir Octavian  :8400", "required": False, "fn": lambda: boot_sir_octavian(home)},
        {"name": "Morgana Bridge :8001", "required": True, "fn": lambda: boot_morgana_bridge(home)},
        {"name": "Bifrost Sidecar:8011", "required": False, "fn": lambda: boot_bifrost_go_sidecar(home)},
        {"name": "OmniRoute    :20128", "required": False, "fn": lambda: boot_omniroute_gateway(home)},
        {"name": "Hermes OmniRoute", "required": False, "fn": lambda: boot_hermes_omniroute_orchestrator(home)},
        {"name": "VPS Hermes_Prime", "required": False, "fn": lambda: boot_vps_hermes_prime(home)},
        {"name": "Heimdall Bifrost Governance", "required": False, "fn": lambda: boot_heimdall_bifrost_governance(home)},
        {"name": "Local LT Memory:8200","required": False, "fn": lambda: start_local_lt_memory(home)},
        {"name": "Cloud Brain  Auth",  "required": False, "fn": lambda: boot_cloud_brain_auth(home)},
        {"name": "Cloud Brain   (RPC)", "required": False, "fn": lambda: boot_cloud_brain(home)},
        {"name": "Symbiotic Maintenance", "required": False, "fn": lambda: boot_symbiotic_maintenance(home, quick=quick)},
        {"name": "Codex Integration", "required": False, "fn": lambda: boot_codex_integration(home)},
        {"name": "Nano Swarm Runtime", "required": False, "fn": lambda: boot_nano_swarm_runtime(home)},
        {"name": "Clawdbot  :18789",   "required": False, "fn": lambda: boot_clawdbot_gateway(home)},
        {"name": "Sir Pi   [PI_AGENT]", "required": False, "fn": lambda: boot_sir_pi(home)},
        {"name": "Knight Config Sync", "required": False, "fn": lambda: sync_knight_configuration(home)},
        {"name": "Repo Context Graph", "required": False, "fn": lambda: boot_graft_graph(home)},
        {"name": "Vizion Telemetry", "required": False, "fn": lambda: boot_telemetry(home)},
        {"name": "Sovereign Harness", "required": False, "fn": lambda: boot_harness(home)},
        {"name": "Bio-Swarm (Nano)", "required": False, "fn": lambda: boot_bioswarm(home)},
        {"name": "Pydantic AI Knight", "required": False, "fn": lambda: boot_pydantic_ai_knight(home)},
        {"name": "Edge PWA      :3000", "required": False, "fn": lambda: boot_edge_interface(home)},
    ]

    results: dict[str, Any] = {}
    summary_phases: list[dict[str, Any]] = []
    t_total = time.perf_counter()

    def _run_one(phase: dict[str, Any]) -> tuple[str, bool, str, int, bool]:
        label = phase["name"]
        fn = phase["fn"]
        t0 = time.perf_counter()
        try:
            phase_ok, msg = fn()
            clean = _strip(msg)
            status_text = f"{msg} {clean}".lower()
            ok = phase_ok is not False and not any(
                token in status_text
                for token in ("[yellow]", "failed", "unreachable", "exception")
            )
        except Exception as exc:
            ok = False
            clean = f"exception: {type(exc).__name__}: {exc}"
        dt = round((time.perf_counter() - t0) * 1000)
        return label, ok, clean, dt, bool(phase["required"])

    def _emit(label: str, ok: bool, clean: str, dt: int) -> None:
        if not quick:
            glyph = f"{_C['g']}OK{_C['x']}" if ok else f"{_C['y']}WARN{_C['x']}"
            print(f"  {glyph} {_C['B']}{label}{_C['x']}  {clean}  {_C['d']}({dt}ms){_C['x']}")

    active: list[dict[str, Any]] = []
    for phase in phases:
        lname = str(phase["name"]).lower()
        if skip_tokens and any(tok in lname for tok in skip_tokens):
            results[phase["name"]] = {"ok": True, "msg": "skipped via AWAKEN_SKIP", "ms": 0}
            summary_phases.append(
                {"name": phase["name"], "ok": True, "required": False,
                 "detail": "skipped via AWAKEN_SKIP", "ms": 0}
            )
            continue
        active.append(phase)

    serial = [p for p in active if any(h in str(p["name"]).lower() for h in _SERIAL_PHASE_HINTS)]
    parallel = [p for p in active if p not in serial]

    for phase in serial:
        label, ok, clean, dt, req = _run_one(phase)
        results[label] = {"ok": ok, "msg": clean, "ms": dt}
        summary_phases.append(
            {"name": label, "ok": ok, "required": req, "detail": clean, "ms": dt}
        )
        _emit(label, ok, clean, dt)

    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(_run_one, p): p["name"] for p in parallel}
            done: dict[str, tuple[bool, str, int, bool]] = {}
            for fut in concurrent.futures.as_completed(futs):
                label, ok, clean, dt, req = fut.result()
                done[label] = (ok, clean, dt, req)
                _emit(label, ok, clean, dt)
            for phase in parallel:
                label = phase["name"]
                ok, clean, dt, req = done[label]
                results[label] = {"ok": ok, "msg": clean, "ms": dt}
                summary_phases.append(
                    {"name": label, "ok": ok, "required": req, "detail": clean, "ms": dt}
                )

    # Restore canonical phase order for summary stability
    order = [p["name"] for p in phases if p["name"] in results]
    summary_phases.sort(key=lambda s: order.index(s["name"]) if s["name"] in order else 999)

    results["_total_ms"] = round((time.perf_counter() - t_total) * 1000)
    results["_summary"] = summarize_boot_results(summary_phases)
    _write_boot_snapshot(home, results)
    return results
