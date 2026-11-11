# SPDX-License-Identifier: MIT

"""Probe-runner for catalog check 070 vfs_scaffold_integrity.

--required takes positional paths.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from control_plane.preflight.probes.file_present import scan


def _parse_required(argv: list[str]) -> list[Path]:
    if "--required" not in argv:
        raise SystemExit(
            "vfs_present_run requires --required <path1 path2 ...>"
        )
    idx = argv.index("--required")
    paths = []
    for value in argv[idx + 1:]:
        if value.startswith("--"):
            break
        paths.append(Path(value))
    return paths


def main() -> int:
    try:
        required = _parse_required(sys.argv[1:])
    except SystemExit as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    found = scan(required)
    found_names = {p.resolve() for p in found}
    missing = [
        str(p) for p in required
        if p.resolve() not in found_names
    ]
    all_ok = len(missing) == 0
    payload = {
        "all_ok": all_ok,
        "missing_count": len(missing),
        "missing_paths": missing,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
