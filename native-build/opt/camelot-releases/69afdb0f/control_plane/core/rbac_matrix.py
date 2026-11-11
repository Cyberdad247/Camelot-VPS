# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
RBAC Matrix — A2A Permission Enforcement
=========================================
Shatterpoint SP-01 remediation. Enforces access_matrix.json at Anya gate.

Usage (called from anya_gate._stage_validate):
    from .rbac_matrix import RBACMatrix
    rbac = RBACMatrix()
    ok, issues = rbac.check(knight_id, execution_mode, domain, complexity)
"""

from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_MATRIX_PATH = (
    Path(__file__).parent.parent.parent
    / "03_VAULT" / "training" / "configs" / "config" / "access_matrix.json"
)


@lru_cache(maxsize=1)
def _load_matrix() -> dict:
    if not _MATRIX_PATH.exists():
        return {}
    with _MATRIX_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


class RBACMatrix:
    """Lightweight RBAC enforcer — loaded once, cached."""

    def __init__(self) -> None:
        self._matrix = _load_matrix()
        self._knights: dict = self._matrix.get("knights", {})
        self._deny_rules: list = self._matrix.get("deny_rules", [])

    def _get_knight(self, knight_id: str) -> Optional[dict]:
        key = knight_id.lower().replace("-", "_").replace(" ", "_")
        return self._knights.get(key)

    def check(
        self,
        knight_id: str,
        execution_mode: str,
        domain: str,
        complexity: float = 0.5,
    ) -> tuple[bool, list[str]]:
        """
        Returns (allowed: bool, issues: list[str]).
        Called in _stage_validate before iron_gate decision.
        """
        issues: list[str] = []
        knight = self._get_knight(knight_id)

        if not knight:
            issues.append(f"RBAC: unknown knight '{knight_id}' — no access record, BLOCKED")
            return False, issues

        # Mode check
        allowed_modes = knight.get("allowed_modes", [])
        if execution_mode not in allowed_modes:
            issues.append(
                f"RBAC: {knight_id} mode={execution_mode} not in allowed={allowed_modes}"
            )

        # Domain check — "*" means all domains allowed
        allowed_domains = knight.get("allowed_domains", [])
        if "*" not in allowed_domains and domain not in allowed_domains:
            issues.append(
                f"RBAC: {knight_id} domain={domain} not in allowed={allowed_domains}"
            )

        # Deny rule evaluation
        _tier = knight.get("tier", "KNIGHT")
        _role = knight.get("role", "")
        cost_ceiling = knight.get("cost_ceiling", "low")
        _can_spawn = knight.get("can_spawn_swarm", False)

        for rule in self._deny_rules:
            rid = rule.get("id", "?")
            _action = rule.get("action", "BLOCKED")

            if rid == "DENY-04" and complexity < 0.5 and cost_ceiling == "high":
                issues.append(f"RBAC [{rid}]: cost ceiling violation — reroute to cheaper terminal")

        blocked = any(
            "BLOCKED" in i or "not in allowed" in i for i in issues
        )
        return not blocked, issues

    def is_omega(self, knight_id: str) -> bool:
        knight = self._get_knight(knight_id)
        return knight.get("tier", "") == "OMEGA" if knight else False

    def can_spawn_swarm(self, knight_id: str) -> bool:
        knight = self._get_knight(knight_id)
        return bool(knight.get("can_spawn_swarm", False)) if knight else False

    def max_net_lines(self, knight_id: str) -> int:
        knight = self._get_knight(knight_id)
        return int(knight.get("max_net_lines", 50)) if knight else 50

    def invalidate_cache(self) -> None:
        _load_matrix.cache_clear()
        self._matrix = _load_matrix()
        self._knights = self._matrix.get("knights", {})
        self._deny_rules = self._matrix.get("deny_rules", [])
