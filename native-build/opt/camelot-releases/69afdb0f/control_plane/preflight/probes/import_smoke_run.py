# SPDX-License-Identifier: MIT

"""Probe-runner for catalog check 060 tool_registry_presence.

--modules takes comma-separated module names.
"""
from __future__ import annotations
import json
import sys

from control_plane.preflight.probes.import_smoke import check


def _parse_modules(argv: list[str]) -> list[str]:
    if "--modules" not in argv:
        raise SystemExit(
            "import_smoke_run requires --modules <comma-separated names>"
        )
    idx = argv.index("--modules")
    raw = argv[idx + 1]
    return [m.strip() for m in raw.split(",") if m.strip()]


def main() -> int:
    try:
        modules = _parse_modules(sys.argv[1:])
    except SystemExit as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    failed = check(modules)
    payload = {
        "all_ok": len(failed) == 0,
        "failed_modules": failed,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
