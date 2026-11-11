# SPDX-License-Identifier: MIT

"""Probe-runner for catalog check 040 port_readiness_scan.

Pattern: --ports comma-separated list of ints.
"""
from __future__ import annotations
import json
import sys

from control_plane.preflight.probes.ports import scan as probe_ports


def _parse_ports(argv: list[str]) -> list[int]:
    if "--ports" not in argv:
        raise SystemExit("ports_run requires --ports <comma-separated ints>")
    idx = argv.index("--ports")
    raw = argv[idx + 1]
    return [int(p.strip()) for p in raw.split(",") if p.strip()]


def main() -> int:
    try:
        ports = _parse_ports(sys.argv[1:])
    except SystemExit as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"invalid port list: {e}\n")
        return 2
    result = probe_ports(ports, timeout_s=0.2)
    open_count = sum(1 for v in result.values() if v)
    total = len(result)
    payload = {
        "all_ok": open_count == total,
        "open_count": open_count,
        "total": total,
        "results": {str(p): v for p, v in result.items()},
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
