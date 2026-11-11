# SPDX-License-Identifier: MIT

"""OpenClaw — Dynamic Health Monitor + Auto-Triage Engine
==========================================================
CAMELOT-OS Loop 9: runs every 300s, checks system health, classifies
failures, executes known-safe remediations, and queues HITL escalations.

Public entry point: run_openclaw_triage(probe_cache=None) -> dict
"""
from __future__ import annotations

import json
import socket
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CAMELOT_HOME = Path(__file__).resolve().parent.parent
LOGS_DIR     = CAMELOT_HOME / "logs"
SKILLS_DIR   = CAMELOT_HOME / ".hive" / "skills"
QUEUE_FILE   = LOGS_DIR / "harness_queue.jsonl"
REPORT_FILE  = LOGS_DIR / "openclaw_report.json"

CORE_SKILLS = [
    "rust-kinetic", "security", "swarm-colony", "python-api",
    "nextjs", "reasoning", "voice-media", "bitnet",
]

PORT_CHECKS: list[tuple[str, str, int, bool]] = [
    # (key, host, port, is_critical)
    ("CLIProxy",    "127.0.0.1", 8080, True),
    ("KineticEdge", "127.0.0.1", 3001, True),
    ("Qdrant",      "127.0.0.1", 6333, False),
    ("Saltare",     "127.0.0.1", 8085, False),
    ("Holotable",   "127.0.0.1", 3000, False),
    ("OmniVoice",   "127.0.0.1", 3002, False),
    ("KittenTTS",   "127.0.0.1", 8300, False),
    ("SirOctavian", "127.0.0.1", 8400, False),
    ("Redis",       "127.0.0.1", 6379, False),
]


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    key: str
    ok: bool
    critical: bool
    detail: str = ""


@dataclass
class TriageAction:
    action_type: str    # "queue_task" | "write_alert" | "set_hitl"
    payload: dict = field(default_factory=dict)
    trigger_key: str = ""


# ── Check runner ─────────────────────────────────────────────────────────────

def _probe_port(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run_checks(probe_cache: dict | None = None) -> list[CheckResult]:
    results: list[CheckResult] = []

    # Port probes — use cache from harness watchdog when available
    for key, host, port, is_critical in PORT_CHECKS:
        if probe_cache is not None and key in probe_cache:
            ok = probe_cache[key]
        else:
            ok = _probe_port(host, port)
        results.append(CheckResult(key=key, ok=ok, critical=is_critical,
                                   detail=f":{port}"))

    # Harness PID
    pid_ok = (LOGS_DIR / "harness.pid").exists()
    results.append(CheckResult("harness_pid", pid_ok, critical=True,
                               detail=str(LOGS_DIR / "harness.pid")))

    # Core skill files
    for sk in CORE_SKILLS:
        ok = (SKILLS_DIR / f"{sk}.md").exists()
        results.append(CheckResult(f"skill:{sk}", ok, critical=False,
                                   detail=f".hive/skills/{sk}.md"))

    # RBAC matrix
    rbac_ok = (CAMELOT_HOME / "control_plane" / "rbac_matrix.py").exists()
    results.append(CheckResult("rbac_matrix", rbac_ok, critical=True,
                               detail="control_plane/rbac_matrix.py"))

    # access_matrix.json
    am_ok = (CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "config" / "access_matrix.json").exists()
    results.append(CheckResult("access_matrix", am_ok, critical=True,
                               detail="03_VAULT/training/configs/config/access_matrix.json"))

    # GIDEON risk score from cached report
    gideon_ok, gideon_detail = _check_gideon()
    results.append(CheckResult("scorpion_gate", gideon_ok, critical=True,
                               detail=gideon_detail))

    # Switchboard terminal count
    sw_ok, sw_detail = _check_switchboard()
    results.append(CheckResult("switchboard", sw_ok, critical=False,
                               detail=sw_detail))

    # Ollama model count
    ollama_ok, ollama_detail = _check_ollama()
    results.append(CheckResult("ollama_models", ollama_ok, critical=False,
                               detail=ollama_detail))

    # Skill gaps via GEP (fast — just filesystem check, no log scan)
    gap_ok, gap_detail = _check_skill_gaps()
    results.append(CheckResult("skill_gaps", gap_ok, critical=False,
                               detail=gap_detail))

    # Watchdog restart I/O error detector
    wd_ok, wd_detail = _check_watchdog_errors()
    results.append(CheckResult("watchdog_io_errors", wd_ok, critical=False,
                               detail=wd_detail))

    return results


def _check_gideon() -> tuple[bool, str]:
    report_path = LOGS_DIR / "gideon_report.json"
    if not report_path.exists():
        return True, "no report yet (first run)"
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        score = data.get("gideon_risk_score", 0)
        passed = data.get("passed", True)
        return passed, f"GIDEON_RISK_SCORE={score}"
    except Exception as e:
        return True, f"parse error: {e}"


def _check_switchboard() -> tuple[bool, str]:
    manifest = LOGS_DIR / "switchboard_manifest.json"
    if not manifest.exists():
        return False, "switchboard_manifest.json missing"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        terminals = data.get("terminals", {})
        live = sum(1 for v in terminals.values() if v.get("status") in ("live", "assumed_live"))
        total = len(terminals)
        dark = total - live
        ok = live >= 8
        return ok, f"{live}/{total} live ({dark} dark)"
    except Exception as e:
        return False, str(e)[:60]


def _check_ollama() -> tuple[bool, str]:
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        count = len(payload.get("models", []))
        return count >= 4, f"{count} models"
    except (urllib.error.URLError, OSError, TimeoutError):
        return False, "ollama not reachable"
    except Exception as e:
        return False, str(e)[:60]


def _check_skill_gaps() -> tuple[bool, str]:
    if not SKILLS_DIR.exists():
        return False, "skills dir missing"
    existing = {f.stem for f in SKILLS_DIR.glob("*.md")}
    gaps = [sk for sk in CORE_SKILLS if sk not in existing]
    return len(gaps) == 0, f"gaps={gaps}" if gaps else "no gaps"


def _check_watchdog_errors() -> tuple[bool, str]:
    log_path = LOGS_DIR / "harness.log"
    if not log_path.exists():
        return True, "no harness.log"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
        io_errors = [line for line in lines if "I/O operation on closed file" in line]
        if len(io_errors) >= 5:
            return False, f"{len(io_errors)} I/O closed-file errors in last 200 lines"
        return True, f"{len(io_errors)} I/O errors (below threshold)"
    except Exception as e:
        return True, str(e)[:60]


# ── Classifier ───────────────────────────────────────────────────────────────

def _classify(results: list[CheckResult]) -> tuple[list[CheckResult], list[CheckResult], list[CheckResult]]:
    critical = [r for r in results if not r.ok and r.critical]
    warn     = [r for r in results if not r.ok and not r.critical]
    ok       = [r for r in results if r.ok]
    return critical, warn, ok


# ── Triage playbook ──────────────────────────────────────────────────────────

def _triage(critical: list[CheckResult], warn: list[CheckResult]) -> list[TriageAction]:
    actions: list[TriageAction] = []

    def _queue(knight: str, directive: str, key: str) -> TriageAction:
        return TriageAction(
            action_type="queue_task",
            payload={"id": f"openclaw-{uuid.uuid4().hex[:8]}", "knight": knight,
                     "directive": directive, "priority": 1},
            trigger_key=key,
        )

    for r in critical + warn:
        k = r.key

        if k == "CLIProxy":
            actions.append(_queue("sir_boris", "//BOOT CLIProxy", k))
        elif k == "KineticEdge":
            actions.append(_queue("sir_forge", "//BOOT KineticEdge", k))
        elif k == "harness_pid":
            actions.append(TriageAction("write_alert", {
                "file": str(LOGS_DIR / "openclaw_recovery.md"),
                "content": f"# OpenClaw Recovery Alert\n**{datetime.now(timezone.utc).isoformat()}**\n\n"
                           f"Harness PID file missing — sovereign daemon may be down.\n"
                           f"Run: `python control_plane/harness.py`\n",
            }, trigger_key=k))
        elif k in ("rbac_matrix", "access_matrix"):
            actions.append(_queue("sir_sentinel", f"//SCAN {k}", k))
            actions.append(TriageAction("set_hitl", {"reason": f"{k} check failed"}, trigger_key=k))
        elif k == "scorpion_gate":
            actions.append(TriageAction("write_alert", {
                "file": str(LOGS_DIR / "openclaw_hitl_required.md"),
                "content": f"# Iron Gate HITL Required\n**{datetime.now(timezone.utc).isoformat()}**\n\n"
                           f"SCORPION gate failed: {r.detail}\n"
                           f"Review logs/gideon_report.json and apply remediation.\n",
            }, trigger_key=k))
            actions.append(TriageAction("set_hitl", {"reason": f"SCORPION: {r.detail}"}, trigger_key=k))
        elif k == "skill_gaps":
            actions.append(_queue("lord_archivist", "run_gep_scan", k))
        elif k == "ollama_models":
            actions.append(TriageAction("write_alert", {
                "file": str(LOGS_DIR / "openclaw_ollama_alert.md"),
                "content": f"# Ollama Models Alert\n**{datetime.now(timezone.utc).isoformat()}**\n\n"
                           f"Fewer than 4 models loaded ({r.detail}).\n"
                           f"Run: `ollama pull gemma3` and `ollama pull qwen3`\n",
            }, trigger_key=k))
        elif k == "switchboard":
            actions.append(_queue("sir_link", "//STATUS switchboard", k))
        elif k == "watchdog_io_errors":
            actions.append(TriageAction("write_alert", {
                "file": str(LOGS_DIR / "openclaw_watchdog_diag.md"),
                "content": f"# Watchdog I/O Diagnostic\n**{datetime.now(timezone.utc).isoformat()}**\n\n"
                           f"Detail: {r.detail}\n"
                           f"Root cause: harness subprocess stdout/stderr handles closed after Popen.\n"
                           f"Fix: restart harness to get fresh file handles.\n",
            }, trigger_key=k))

    return actions


# ── Action executor ──────────────────────────────────────────────────────────

def _execute_safe_actions(actions: list[TriageAction]) -> tuple[int, bool, list[str]]:
    healed = 0
    needs_escalation = False
    taken: list[str] = []

    for act in actions:
        try:
            if act.action_type == "queue_task":
                QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(QUEUE_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(act.payload) + "\n")
                healed += 1
                taken.append(f"queued:{act.payload['knight']}:{act.payload['directive'][:40]}")

            elif act.action_type == "write_alert":
                alert_path = Path(act.payload["file"])
                alert_path.parent.mkdir(parents=True, exist_ok=True)
                alert_path.write_text(act.payload["content"], encoding="utf-8")
                healed += 1
                taken.append(f"alert:{alert_path.name}")

            elif act.action_type == "set_hitl":
                needs_escalation = True
                taken.append(f"hitl:{act.payload.get('reason','')[:60]}")

        except Exception as e:
            taken.append(f"ERROR:{act.action_type}:{e}")

    return healed, needs_escalation, taken


# ── Report writer ─────────────────────────────────────────────────────────────

def _write_report(report: dict) -> None:
    try:
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── Public entry point ────────────────────────────────────────────────────────

def run_openclaw_triage(probe_cache: dict | None = None) -> dict:
    """Execute one full check + triage cycle. Safe to call from harness loop."""
    t0 = time.perf_counter()
    ts = datetime.now(timezone.utc).isoformat()

    all_checks = _run_checks(probe_cache)
    critical, warn, ok_checks = _classify(all_checks)

    if critical:
        status = "CRITICAL"
    elif warn:
        status = "DEGRADED"
    else:
        status = "ALL_GREEN"

    actions = _triage(critical, warn)
    healed, hitl_required, taken = _execute_safe_actions(actions)

    report = {
        "timestamp": ts,
        "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        "status": status,
        "checks_ok": len(ok_checks),
        "checks_warn": len(warn),
        "checks_critical": len(critical),
        "checks_total": len(all_checks),
        "auto_healed": healed,
        "hitl_required": hitl_required,
        "critical_items": [r.key for r in critical],
        "warn_items": [r.key for r in warn],
        "actions_taken": taken,
    }
    _write_report(report)
    return report


if __name__ == "__main__":
    sys.path.insert(0, str(CAMELOT_HOME))
    result = run_openclaw_triage()
    print(json.dumps(result, indent=2))
