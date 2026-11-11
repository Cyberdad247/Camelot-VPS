# SPDX-License-Identifier: MIT

"""Probe-runner for catalog check 020 foss_validation_constraints.

Pattern: thin CLI wrapper. --roots takes positional roots; calls
probes.license_header.scan; returns JSON line.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from control_plane.preflight.probes.license_header import scan


def main() -> int:
    args = sys.argv[1:]
    roots: list[Path] = []
    if "--roots" in args:
        idx = args.index("--roots")
        # Roots are space-separated values immediately after --roots,
        # terminated by next flag (anything starting with --).
        for value in args[idx + 1:]:
            if value.startswith("--"):
                break
            roots.append(Path(value))
    flagged = [
        str(p.resolve()) for p in scan(roots)
    ]
    all_ok = len(flagged) == 0
    payload = {
        "all_ok": all_ok,
        "flagged_count": len(flagged),
        "flagged_paths": flagged,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
