# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from control_plane.versioning import get_dynamic_version


def load_manifest(storage_state_path: Path, notebook_count: int, source_count: int) -> dict[str, Any]:
    version = get_dynamic_version()
    return {
        "storage_state_path": str(storage_state_path),
        "camelot_version": version.label,
        "camelot_version_source": version.source,
        "notebook_count": notebook_count,
        "source_count": source_count,
    }


def write_manifest(
    manifest_path: Path,
    storage_state_path: Path,
    notebook_count: int,
    source_count: int,
) -> Path:
    payload = load_manifest(storage_state_path, notebook_count, source_count)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest_path

