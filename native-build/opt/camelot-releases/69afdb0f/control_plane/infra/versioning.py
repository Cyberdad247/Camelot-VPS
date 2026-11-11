# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class VersionInfo:
    label: str
    source: str
    detail: str


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current.parents[1]


def _git_describe(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty", "--long"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    text = result.stdout.strip()
    return text or None


def get_dynamic_version() -> VersionInfo:
    override = os.environ.get("CAMELOT_OS_VERSION")
    if override:
        return VersionInfo(label=override, source="env", detail="CAMELOT_OS_VERSION")

    root = _repo_root()
    git_label = _git_describe(root)
    if git_label:
        return VersionInfo(label=f"dynamic-{git_label}", source="git", detail=str(root))

    fallback = datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M%S")
    return VersionInfo(label=f"dynamic-{fallback}", source="utc", detail="fallback timestamp")


def get_version_string() -> str:
    return get_dynamic_version().label

