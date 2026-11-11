# SPDX-License-Identifier: MIT

"""Reusable preflight probes (per-check execution primitives).

Per the plan these primitives live alongside the runner; each task in
the catalog references at most one of them via command_type=python_module.
"""

from __future__ import annotations

__all__: list[str] = []
