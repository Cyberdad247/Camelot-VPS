# SPDX-License-Identifier: MIT

"""Probe-runner for catalog check 030 northstar_brief_currency.

Pattern: thin CLI wrapper. --path, --max-age-days; returns JSON.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from control_plane.preflight.probes.file_age import check


def _parse_args(argv: list[str]) -> tuple[Path, int]:
    path_str = None
    max_age = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--path":
            path_str = argv[i + 1]
            i += 2
        elif a == "--max-age-days":
            max_age = int(argv[i + 1])
            i += 2
        else:
            i += 1
    if path_str is None or max_age is None:
        raise SystemExit(
            "file_age_run requires --path <path> --max-age-days <int>"
        )
    return Path(path_str), max_age


def main() -> int:
    try:
        path, max_age = _parse_args(sys.argv[1:])
    except SystemExit as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    passed, age_days = check(path, max_age)
    all_ok = passed
    payload = {
        "all_ok": all_ok,
        "path": str(path),
        "age_days": age_days,
        "max_age_days": max_age,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
