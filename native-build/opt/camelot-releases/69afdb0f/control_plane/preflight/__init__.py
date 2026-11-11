# SPDX-License-Identifier: MIT

"""VFS Preflight vertical slice (slice #1 of 5).

Companion docs:
- docs/architecture/VFS_PREFLIGHT_DESIGN.md
- docs/architecture/PEER_ARCHITECTURE.md
- docs/adr/0006-vfs-preflight-strict-mode.md
- docs/architecture/OPERATOR_CONSOLE_DESIGN.md (slice #2 reads slice #1)

Evidence-class JSON per preflight check; CONFIRMED-only gate;
graceful-degradation to advisory sentinel when AnyaGate / Sentinel /
Gideon substrate is unavailable (PEER_ARCHITECTURE.md §3.3).
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
