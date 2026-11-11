# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Cribo Bundle Validator
======================
Enforces pre-push dead-code elimination and context compression before
deploying or syncing assets to the VPS Camelot Hub.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


class CriboBundleValidator:
    def __init__(self, cribo_bin: str = "cribo"):
        self.cribo_bin = cribo_bin

    def bundle_and_validate(self, entry_point: Path, output_path: Path) -> dict[str, Any]:
        if not entry_point.exists():
            return {"success": False, "error": f"Entry point {entry_point} not found"}

        bin_path = shutil.which(self.cribo_bin)
        cmd = [bin_path or self.cribo_bin, "--entry", str(entry_point), "--output", str(output_path)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15.0,
            )
            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": f"Cribo bundling failed (code {proc.returncode}): {proc.stderr or proc.stdout}",
                }

            if not output_path.exists():
                return {"success": False, "error": f"Output bundle {output_path} was not created"}

            size_bytes = output_path.stat().st_size
            savings_match = re.search(r"Savings:\s*(\d+)%", proc.stdout)
            savings_pct = int(savings_match.group(1)) if savings_match else 0

            return {
                "success": True,
                "bundle_path": str(output_path),
                "bundle_bytes": size_bytes,
                "savings_pct": savings_pct,
                "stdout": proc.stdout.strip(),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
