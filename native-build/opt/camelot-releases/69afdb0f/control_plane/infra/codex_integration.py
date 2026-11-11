# SPDX-License-Identifier: MIT

"""Codex integration state helpers for Camelot-OS."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ACTOR = "ANYA_OMEGA (Gatekeeper / Alpha & Omega Conductor)"
ARTIFACT_RELATIVE_PATH = Path("03_VAULT") / "runtime_state" / "codex_integration_latest.json"


def _artifact_path(home: Path) -> Path:
    return home / ARTIFACT_RELATIVE_PATH


def _repo_version(home: Path) -> str:
    version_path = home / "VERSION"
    if not version_path.exists():
        return "unknown"
    return version_path.read_text(encoding="utf-8", errors="replace").strip() or "unknown"


def _integration_payload(home: Path, *, actor: str, trigger: str) -> dict[str, Any]:
    return {
        "status": "CODEX_INTEGRATED",
        "actor": actor,
        "trigger": trigger,
        "repo_root": str(home),
        "repo_version": _repo_version(home),
        "artifact_path": str(_artifact_path(home)),
        "python": sys.executable,
        "pid": os.getpid(),
        "surfaces": {
            "cli": True,
            "boot": True,
            "ledger": True,
            "cloudbrain": True,
            "dashboard": True,
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_codex_integration(home: Path, *, actor: str = DEFAULT_ACTOR, trigger: str = "integrate") -> dict[str, Any]:
    """Write the latest Codex integration artifact."""
    path = _artifact_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _integration_payload(home, actor=actor, trigger=trigger)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def read_codex_status(home: Path) -> dict[str, Any]:
    """Read the latest Codex integration artifact, or report missing state."""
    path = _artifact_path(home)
    if not path.exists():
        return {
            "status": "CODEX_NOT_INTEGRATED",
            "artifact_path": str(path),
            "surfaces": {"cli": True, "boot": False, "ledger": False, "cloudbrain": False, "dashboard": False},
        }
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return {"status": "CODEX_STATUS_CORRUPT", "artifact_path": str(path), "error": str(exc)}


def boot_codex_integration(home: Path) -> tuple[bool, str]:
    """Boot-matrix probe for Codex integration state."""
    status = read_codex_status(home)
    if status.get("status") == "CODEX_INTEGRATED":
        return True, "Codex integration artifact present"
    return False, f"Codex integration not ready: {status.get('status')}"
