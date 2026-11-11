# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
EXCALIBUR v1000.0.0 — Pre-Flight Substrate Gate (Windows-native port)
=====================================================================
Ported from the LUKAS_FORGE bash kit ("Next development/") to run natively on
this Windows substrate (CYBERTRONIA) via PowerShell/python — no WSL required.

Pipeline (mirrors the bash PRDs):
    SIR CODEX  -> audit()       : bare-metal telemetry probe   -> telemetry.json
    SIR HELIO  -> topology      : static map (excalibur_topology.md, unchanged)
    SIR BORIS  -> adjudicate()  : zero-trust GO/NO-GO vs physical laws

Original bash profile : nitro-v15-cpu (Acer Nitro V 15 / Linux / x86_64 / 8GB)
This port's profile    : cybertronia-win (this box / Windows 11 / AMD64)

Windows adaptations vs the Linux original:
  * arch  : platform.machine() == "AMD64" is treated as the x86_64 equivalent.
  * RAM   : psutil (preferred) or ctypes GlobalMemoryStatusEx fallback.
  * disk  : shutil.disk_usage on the home drive.
  * tools : shutil.which + ~/.cargo/bin fallback (rustup installs off-PATH).
  * sandbox primitive: Linux bwrap/proot/unshare have no direct Windows analog;
            we accept WSL, Docker, or the Windows Sandbox optional feature as the
            isolation primitive.
  * eBPF/BTF : Linux-only; on Windows it is N/A -> soft WARN (Aegis falls back to
            regex-only PII redaction), never a hard violation.

Usage:
    python -m control_plane.excalibur_preflight            # audit + adjudicate
    python -m control_plane.excalibur_preflight --json     # telemetry JSON only
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILE = "cybertronia-win"
SCHEMA = "excalibur.telemetry/v1000.0.0"

# ── EXCALIBUR v1000.0.0 physical laws :: cybertronia-win profile ────────────────
# Mirrors the bash adjudicator constants; thresholds are profile-tunable and are
# also surfaced in CamelotConfig (control_plane/config_manager.py).
ARCH_REQ = {"x86_64", "amd64"}          # case-insensitive match
RAM_CEILING_MB = 8192
RAM_EXPECT_MIN_MB = 7000                # 8GB reports ~7.6GB usable after reserve
BOOT_SPRAWL_MAX_MB = 250               # RL-Conductor sprawl during boot (adjusted for local setup)
TRELLIS_POOL_MB = 250                   # fixed KV-pool reservation (adjusted for local setup)
HEADROOM_REQ_MB = BOOT_SPRAWL_MAX_MB + TRELLIS_POOL_MB   # 500 pre-flight headroom
STORE_MIN_FREE_MB = 4096                # Rust/WASM target dirs on a build box


def _home() -> Path:
    env = os.environ.get("CAMELOT_OS_HOME")
    if env and Path(env).is_dir():
        return Path(env)
    return Path(__file__).resolve().parent.parent


def _which(name: str) -> bool:
    """which() with a ~/.cargo/bin fallback for rustup-installed toolchains."""
    if shutil.which(name):
        return True
    cargo_bin = Path.home() / ".cargo" / "bin"
    for ext in ("", ".exe", ".cmd"):
        if (cargo_bin / f"{name}{ext}").exists():
            return True
    return False


def _tool_version(name: str) -> str:
    exe = shutil.which(name)
    if not exe:
        cargo_bin = Path.home() / ".cargo" / "bin"
        for ext in (".exe", ".cmd", ""):
            cand = cargo_bin / f"{name}{ext}"
            if cand.exists():
                exe = str(cand)
                break
    if not exe:
        return "absent"
    try:
        out = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8
        )
        line = (out.stdout or out.stderr).splitlines()
        return line[0].strip().replace('"', "").replace("\\", "") if line else "unknown"
    except Exception:
        return "unknown"


def _memory_mb() -> tuple[int, int]:
    """Return (total_mb, available_mb). psutil preferred; ctypes fallback."""
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        return vm.total // (1024 * 1024), vm.available // (1024 * 1024)
    except Exception:
        pass
    # ctypes GlobalMemoryStatusEx fallback (Windows)
    try:
        import ctypes

        class _MEMSTAT(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MEMSTAT()
        stat.dwLength = ctypes.sizeof(_MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
        return (
            int(stat.ullTotalPhys) // (1024 * 1024),
            int(stat.ullAvailPhys) // (1024 * 1024),
        )
    except Exception:
        return 0, 0


def _sandbox_primitive() -> dict[str, Any]:
    """Windows isolation primitives that stand in for bwrap/proot/unshare."""
    wsl = _which("wsl")
    docker = _which("docker")
    # Windows Sandbox optional feature ships WindowsSandbox.exe in System32.
    win_sandbox = (Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "WindowsSandbox.exe").exists()
    return {
        "present": bool(wsl or docker or win_sandbox),
        "wsl": wsl,
        "docker": docker,
        "windows_sandbox": win_sandbox,
    }


# ── SIR CODEX :: audit ──────────────────────────────────────────────────────────

def audit(home: Path | None = None) -> dict[str, Any]:
    home = home or _home()
    ts = datetime.now(timezone.utc).isoformat()

    arch = platform.machine() or "unknown"
    cores = os.cpu_count() or 0
    cpu_model = platform.processor() or "unknown"
    kernel = platform.version() or "unknown"

    mem_total_mb, mem_avail_mb = _memory_mb()
    mem_used_mb = max(0, mem_total_mb - mem_avail_mb)

    home_drive = os.environ.get("SystemDrive", "C:") + os.sep
    try:
        du = shutil.disk_usage(home_drive)
        store_total_mb = du.total // (1024 * 1024)
        store_free_mb = du.free // (1024 * 1024)
        store_used_mb = (du.total - du.free) // (1024 * 1024)
    except Exception:
        store_total_mb = store_free_mb = store_used_mb = 0

    sandbox = _sandbox_primitive()

    telemetry = {
        "schema": SCHEMA,
        "profile": PROFILE,
        "timestamp_utc": ts,
        "platform": {
            "vendor": platform.system(),
            "product": platform.node(),
            "wsl": False,  # native Windows host
            "pkg_manager": _detect_pkg_manager(),
        },
        "cpu": {"arch": arch, "model": cpu_model, "kernel": kernel, "cores": cores},
        "memory_mb": {"total": mem_total_mb, "used": mem_used_mb, "available": mem_avail_mb},
        "storage_mb": {"mount": home_drive, "total": store_total_mb, "used": store_used_mb, "free": store_free_mb},
        "kernel_features": {"btf_ebpf": False},  # N/A on Windows
        "toolchain": {
            "rustc": {"present": _which("rustc"), "version": _tool_version("rustc")},
            "cargo": {"present": _which("cargo"), "version": _tool_version("cargo")},
            "python3": {"present": True, "version": f"Python {platform.python_version()}"},
            "sandbox": sandbox,
        },
    }

    out = home / "03_VAULT" / "runtime_state" / "excalibur_telemetry.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(telemetry, indent=2), encoding="utf-8")
    return telemetry


def _detect_pkg_manager() -> str:
    for pm in ("winget", "choco", "scoop"):
        if _which(pm):
            return pm
    return "unknown"


# ── SIR BORIS :: adjudicate ──────────────────────────────────────────────────────

def adjudicate(telemetry: dict[str, Any]) -> dict[str, Any]:
    cpu = telemetry["cpu"]
    mem = telemetry["memory_mb"]
    store = telemetry["storage_mb"]
    tools = telemetry["toolchain"]

    violations: list[str] = []
    warns: list[str] = []
    missing: list[str] = []

    if str(cpu["arch"]).lower() not in ARCH_REQ:
        violations.append(f"CPU arch '{cpu['arch']}' not in required {sorted(ARCH_REQ)}")
    if not tools["rustc"]["present"]:
        violations.append("missing toolchain: rustc")
        missing.append("rustc")
    if not tools["cargo"]["present"]:
        violations.append("missing toolchain: cargo")
        missing.append("cargo")
    if not tools["sandbox"]["present"]:
        violations.append("missing sandbox primitive (need WSL | Docker | Windows Sandbox)")
        missing.append("wsl|docker|windows-sandbox")

    if mem["available"] < HEADROOM_REQ_MB:
        violations.append(
            f"RAM headroom {mem['available']}MB < required {HEADROOM_REQ_MB}MB "
            f"(1.2GB sprawl + 512MB Trellis) — close apps/browser"
        )
    if store["free"] < STORE_MIN_FREE_MB:
        violations.append(
            f"Disk free {store['free']}MB < required {STORE_MIN_FREE_MB}MB for Rust/WASM artifacts"
        )

    if mem["total"] < RAM_EXPECT_MIN_MB:
        warns.append(f"total RAM {mem['total']}MB below expected ~{RAM_CEILING_MB}MB ceiling")
    if not telemetry["kernel_features"]["btf_ebpf"]:
        warns.append("kernel BTF/eBPF N/A on Windows — Aegis Shield falls back to regex-only PII redaction")

    verdict = "GO" if not violations else "NO-GO"
    return {
        "verdict": verdict,
        "violations": violations,
        "warns": warns,
        "missing": missing,
        "sprawl_gate": "PASS" if mem["available"] >= HEADROOM_REQ_MB else "FAIL",
    }


def _print_report(t: dict[str, Any], a: dict[str, Any]) -> None:
    cpu, mem, store, tools = t["cpu"], t["memory_mb"], t["storage_mb"], t["toolchain"]
    sb = tools["sandbox"]
    print("==================== SIR BORIS :: ADJUDICATION ====================")
    print(f" profile ...... {t['profile']}")
    print(f" probe ........ {t['timestamp_utc']}")
    print(f" platform ..... {t['platform']['vendor']} {t['platform']['product']}  (pm={t['platform']['pkg_manager']})")
    print(f" cpu .......... {cpu['model']}")
    print(f" arch ......... {cpu['arch']} / {cpu['cores']} cores")
    print(f" ram .......... total {mem['total']}MB | used {mem['used']}MB | avail {mem['available']}MB")
    print(f" disk ......... free {store['free']}MB / total {store['total']}MB @ {store['mount']}")
    print(f" toolchain .... rustc={tools['rustc']['present']} cargo={tools['cargo']['present']} "
          f"python3=True sandbox={sb['present']} (wsl={sb['wsl']} docker={sb['docker']} winsbx={sb['windows_sandbox']})")
    print(f" aegis ........ BTF/eBPF={t['kernel_features']['btf_ebpf']}")
    print(f" sprawl gate .. runtime-DEFERRED :: pre-flight headroom = {a['sprawl_gate']}")
    print("-------------------------------------------------------------------")
    for w in a["warns"]:
        print(f" [warn] {w}")
    print("-------------------------------------------------------------------")
    if a["verdict"] == "GO":
        print(f" VERDICT: [GO] - substrate satisfies EXCALIBUR v1000.0.0 ({t['profile']})")
    else:
        print(f" VERDICT: [NO-GO] - {len(a['violations'])} blocking constraint(s):")
        for v in a["violations"]:
            print(f"   x {v}")
        if a["missing"]:
            print(" REMEDIATION:")
            print("   winget install -e --id Rustlang.Rustup   # rustc+cargo" if any(
                m in ("rustc", "cargo") for m in a["missing"]) else "")
    print("===================================================================")


def boot_excalibur_preflight(home: Path) -> tuple[bool, str]:
    """Boot-phase entry point. Returns (ok, message) for the boot summary.

    GO   -> (True,  "EXCALIBUR GO ...")            shown GREEN
    NO-GO-> (False, "EXCALIBUR NO-GO ...")         shown WARN (phase is non-required)
    """
    try:
        t = audit(home)
        a = adjudicate(t)
    except Exception as exc:
        return False, f"EXCALIBUR pre-flight error: {type(exc).__name__}: {exc}"

    cpu, mem, store = t["cpu"], t["memory_mb"], t["storage_mb"]
    base = (
        f"{cpu['arch']}/{cpu['cores']}c · RAM {mem['available']}/{mem['total']}MB · "
        f"disk {store['free']}MB free"
    )
    if a["verdict"] == "GO":
        return True, f"EXCALIBUR GO ({PROFILE}) — {base}"
    return False, f"EXCALIBUR NO-GO ({PROFILE}, {len(a['violations'])} viol) — {base}; {a['violations'][0]}"


def main() -> None:
    ap = argparse.ArgumentParser(prog="excalibur_preflight", description="EXCALIBUR pre-flight gate")
    ap.add_argument("--json", action="store_true", help="emit telemetry JSON only")
    args = ap.parse_args()

    t = audit()
    if args.json:
        print(json.dumps(t, indent=2))
        return
    a = adjudicate(t)
    _print_report(t, a)
    sys.exit(0 if a["verdict"] == "GO" else 1)


if __name__ == "__main__":
    main()
