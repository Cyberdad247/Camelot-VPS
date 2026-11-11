# SPDX-License-Identifier: MIT
"""Camelot Sovereign CLI entrypoint and structured control plane bridge.

Integrates with security.warden to enforce Zero-Trust Iron Gate decisions
and provides unified CLI dispatch.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_plane.cli.dispatch import main as main
from control_plane.cli.iron_gate import (
    _check_iron_gate as _check_iron_gate,
    set_non_interactive as set_non_interactive,
)
from control_plane.runes.camelot_cli import *  # noqa: F401, F403
from security.warden import SecurityDecision, warden


def execute_governed_command(
    intent: str,
    *,
    file_count: int = 0,
    size_delta_mb: float = 0.0,
    non_interactive: Optional[bool] = None,
) -> SecurityDecision:
    """Execute governance check against security.warden and return the structured SecurityDecision."""
    decision = warden.verify_permission(
        agent_id="CLI",
        resource_type="kinetic_action",
        action="EXECUTE",
        target=intent,
        trust_level="KERNEL",
    )
    return decision


if __name__ == "__main__":
    raise SystemExit(main())
