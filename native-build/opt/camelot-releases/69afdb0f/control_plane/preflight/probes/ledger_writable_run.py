# SPDX-License-Identifier: MIT

"""Probe-runner for catalog check 050 provenance_ledger_writable.

Verifies PROVENANCE_LEDGER.md is present and writable. Does NOT modify
the ledger. Honors AGENTS.md rule: the post-write hook owns the file.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if "--path" not in args:
        sys.stderr.write(
            "ledger_writable_run requires --path <ledger-path>\n"
        )
        return 2
    idx = args.index("--path")
    path = Path(args[idx + 1])
    if not path.exists():
        all_ok = False
        payload = {
            "all_ok": all_ok,
            "path": str(path),
            "exists": False,
            "writable": False,
        }
        sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
        return 1
    writable = path.stat().st_mode != 0 and (
        path.parent.stat().st_mode & 0o200
        or path.exists()
    )
    # Probing with os.access; do not write.
    import os
    writable = os.access(path, os.W_OK)
    payload = {
        "all_ok": writable,
        "path": str(path),
        "exists": True,
        "writable": writable,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0 if writable else 1


if __name__ == "__main__":
    sys.exit(main())
