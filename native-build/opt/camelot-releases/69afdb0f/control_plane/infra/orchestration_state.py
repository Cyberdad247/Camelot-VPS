# SPDX-License-Identifier: MIT

"""Lightweight orchestration-state helpers used by Camelot CLI and boot."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PERSONA_RULES = [
    ("Anya", ("compile", "route", "clarify", "workflow", "prompt", "system")),
    ("Merlin", ("architecture", "blueprint", "engine", "kernel", "design")),
    ("Sir Alex", ("dashboard", "ui", "frontend", "visual", "interface")),
    ("Sir Lukas", ("edge", "sync", "ledger", "cloudbrain", "cloud brain", "runtime")),
    ("Lady Alexandria", ("docs", "archive", "journal", "dictionary", "knowledge")),
]


def route_persona(intent: str) -> dict[str, str]:
    """Pick the best Camelot persona for a plain-language intent."""
    lowered = intent.lower()
    for persona, keywords in PERSONA_RULES:
        if any(keyword in lowered for keyword in keywords):
            return {"persona": persona, "reason": f"matched {persona} routing keywords"}
    return {"persona": "Merlin", "reason": "default architecture and orchestration route"}


def summarize_boot_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    required = [item for item in results if item.get("required", True)]
    optional = [item for item in results if not item.get("required", True)]
    required_ok = sum(1 for item in required if item.get("ok"))
    optional_ok = sum(1 for item in optional if item.get("ok"))
    return {
        "status": "GREEN" if required_ok == len(required) else "DEGRADED",
        "required_ok": required_ok,
        "required_total": len(required),
        "optional_ok": optional_ok,
        "optional_total": len(optional),
        "results": results,
    }


def triage_files(root: str = ".", *, older_than_days: int = 60, large_file_mb: float = 50.0) -> dict[str, Any]:
    """Return a bounded filesystem triage summary without walking vendor-heavy trees deeply."""
    root_path = Path(root).resolve()
    large_files: list[dict[str, Any]] = []
    scanned = 0
    skipped_dirs = {".git", "node_modules", ".venv", ".venv_camelot", ".pytest_cache", "target", "dist", "build"}
    for current, dirs, files in os.walk(root_path):
        dirs[:] = [name for name in dirs if name not in skipped_dirs]
        for name in files:
            path = Path(current) / name
            try:
                stat = path.stat()
            except OSError:
                continue
            scanned += 1
            size_mb = stat.st_size / (1024 * 1024)
            if size_mb >= large_file_mb:
                large_files.append({"path": str(path), "size_mb": round(size_mb, 2)})
            if scanned >= 5000:
                break
        if scanned >= 5000:
            break
    return {
        "summary": {"root": str(root_path), "scanned_files": scanned, "large_files": len(large_files)},
        "large_files": large_files[:50],
        "limits": {"older_than_days": older_than_days, "large_file_mb": large_file_mb},
    }


def validate_autonomous_knight_workflows() -> dict[str, Any]:
    return {
        "status": "AVAILABLE",
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "workflows": ["ledger", "cloudbrain", "dashboard", "defense-grid"],
    }


def go_autonomous_workflow_report() -> dict[str, Any] | None:
    return None


def build_notification_bundle(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": event.get("status", "green"),
        "kind": event.get("kind", "event"),
        "summary": event.get("summary", ""),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_orchestration_snapshot(
    *,
    root: str = ".",
    older_than_days: int = 60,
    large_file_mb: float = 50.0,
    intent: str = "status",
    message: str = "Camelot orchestration event",
    kind: str = "startup",
    status: str = "green",
) -> dict[str, Any]:
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "notification": build_notification_bundle({"kind": kind, "status": status, "summary": message}),
        "persona": route_persona(intent),
        "triage_summary": triage_files(root, older_than_days=older_than_days, large_file_mb=large_file_mb)["summary"],
    }


def run_orchestrator_cli(
    mode: str,
    *,
    root: str = ".",
    older_than_days: int = 60,
    large_file_mb: float = 50.0,
    intent: str = "status",
    message: str = "Camelot orchestration event",
    kind: str = "startup",
    status: str = "green",
) -> dict[str, Any] | None:
    """Use the compiled Go/Rust orchestrator when present; otherwise let Python fallback run."""
    candidates = [Path(root) / "bin" / "orchestrator.exe", Path(root) / "bin" / "camelot-orchestrator.exe"]
    exe = next((path for path in candidates if path.exists()), None)
    if exe is None:
        return None
    try:
        completed = subprocess.run(
            [str(exe), mode],
            cwd=str(Path(root).resolve()),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return {
            "mode": mode,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"mode": mode, "error": f"{type(exc).__name__}: {exc}"}
