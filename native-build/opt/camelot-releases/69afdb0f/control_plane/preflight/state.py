# SPDX-License-Identifier: MIT

"""Graduation flag — first-run advisor to strict-mode state.

Per docs/architecture/VFS_PREFLIGHT_DESIGN.md §3.2 and §6.2:
- New boot, no _graduated.flag -> advisor-mode (REJECTED halts nothing).
- After all 8 checks CONFIRMED -> _graduated.flag written atomically.
- Subsequent runs read the flag and tighten to strict-mode (REJECTED halts).

Rollback path: filesystem-level deletion of the flag (this is intentional).
"""
from __future__ import annotations
from pathlib import Path

FLAG_FILENAME = "_graduated.flag"
FLAG_CONTENTS = "vfs-preflight-strict-mode\n"


class GraduationFlag:
    """Tracks whether preflight has graduated from advisor to strict mode."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    def path(self) -> Path:
        return self.root / "preflight" / FLAG_FILENAME

    def is_strict(self) -> bool:
        return self.path().exists()

    def graduate(self) -> None:
        """Promote advisor to strict on first all-CONFIRMED run. Atomic write."""
        target = self.path()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".flag.tmp")
        tmp.write_text(FLAG_CONTENTS)
        try:
            tmp.replace(target)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise

    def revoke(self) -> None:
        """Manual rollback to advisor (intentional operator action)."""
        try:
            self.path().unlink()
        except FileNotFoundError:
            pass
