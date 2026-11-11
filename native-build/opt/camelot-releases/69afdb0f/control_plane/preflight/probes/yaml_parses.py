# SPDX-License-Identifier: MIT

"""YAML parses probe — verifies a YAML file is a valid mapping.

Per VFS_PREFLIGHT_DESIGN.md §4 `lattice_yaml_consistency` (sequence 080).
Surfaced via probes.lattice_run.py in Task 6.
"""
from __future__ import annotations
from pathlib import Path
import yaml


def check(path: Path) -> tuple[bool, str]:
    """Verify `path` parses as a mapping.

    Returns:
        (passed, message):
        - passed is True iff `path` parses and the top-level is a dict.
        - message is "" on success and the YAML/yaml.load error on
          failure (empty string indicates success).
    """
    if not path.exists():
        return False, f"missing: {path}"
    try:
        loaded = yaml.safe_load(path.read_text())
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    if not isinstance(loaded, dict):
        return False, "expected a mapping at top level"
    return True, ""
