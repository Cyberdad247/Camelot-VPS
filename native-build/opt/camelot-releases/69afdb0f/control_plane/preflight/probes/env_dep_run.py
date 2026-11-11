# SPDX-License-Identifier: MIT

"""Probe-runner for catalog check 010 env_dependency_match.

Pattern: thin CLI wrapper. Args parsed from sys.argv; reads --pipeline/extras;
returns JSON line on stdout with `{"all_ok": bool, ...details}`. Exit 0 iff all_ok.
"""
from __future__ import annotations
import json
import sys
import shutil
import platform

EXPECTED_KEYS = ("python_ok", "rust_cargo_ok", "node_ok", "ollama_ok")


def _probe() -> dict:
    """Probe Python 3.11+, Rust cargo, Node, Ollama presence.

    All checks are read-only probes of executable presence on PATH.
    No external state mutated.
    """
    py_major = sys.version_info.major
    py_minor = sys.version_info.minor
    python_ok = (py_major, py_minor) >= (3, 11)
    rust_cargo_ok = shutil.which("cargo") is not None
    node_ok = shutil.which("node") is not None
    ollama_ok = shutil.which("ollama") is not None
    return {
        "python_ok": python_ok,
        "rust_cargo_ok": rust_cargo_ok,
        "node_ok": node_ok,
        "ollama_ok": ollama_ok,
        "python_version": platform.python_version(),
    }


def main() -> int:
    out = _probe()
    out["all_ok"] = all(out[k] for k in EXPECTED_KEYS)
    sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")
    return 0 if out["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
