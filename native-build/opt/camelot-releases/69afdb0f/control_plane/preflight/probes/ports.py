# SPDX-License-Identifier: MIT

"""TCP port probe — short-lived connect attempts on 127.0.0.1.

Per VFS_PREFLIGHT_DESIGN.md §4 check `port_readiness_scan` (sequence 040).
Surfaced via probes.ports_run.py in Task 6.
"""
from __future__ import annotations
import socket
from typing import Iterable


def scan(ports: Iterable[int], timeout_s: float = 0.2) -> dict[int, bool]:
    """Probe `ports` on 127.0.0.1 with bounded connect timeout.

    Returns a `{port: is_open}` mapping. Never raises OSError;
    connection failures produce `is_open=False`.
    """
    out: dict[int, bool] = {}
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout_s)
        try:
            s.connect(("127.0.0.1", p))
            s.close()
            out[p] = True
        except (OSError, socket.timeout):
            try:
                s.close()
            except OSError:
                pass
            out[p] = False
    return out
