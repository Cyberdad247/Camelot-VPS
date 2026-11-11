# SPDX-License-Identifier: MIT
"""Sovereign Authority Vector Evaluator (Camelot-OS SADD §6.3, §10.3, §11.2).

Formalizes the 6-dimensional authority vector:
A_epoch = <E_leadership, R_policy, R_revocation, R_registry, R_identity, R_contract>

Replaces scalar integer epochs with multidimensional distributed state invalidation
across VPS Hub KVM563, Excalibur S26 Ultra, and local workstation nodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import hashlib
import json


@dataclass(frozen=True)
class AuthorityVector:
    """Multidimensional Sovereign Authority Vector."""
    e_leadership: int
    r_policy: int
    r_revocation: int
    r_registry: int
    r_identity: int
    r_contract: int

    def __post_init__(self):
        for field_name, val in [
            ("e_leadership", self.e_leadership),
            ("r_policy", self.r_policy),
            ("r_revocation", self.r_revocation),
            ("r_registry", self.r_registry),
            ("r_identity", self.r_identity),
            ("r_contract", self.r_contract),
        ]:
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"{field_name} must be a non-negative integer, got {val!r}")

    def to_tuple(self) -> tuple[int, int, int, int, int, int]:
        return (
            self.e_leadership,
            self.r_policy,
            self.r_revocation,
            self.r_registry,
            self.r_identity,
            self.r_contract,
        )

    def to_list(self) -> list[int]:
        return list(self.to_tuple())

    @classmethod
    def from_sequence(cls, seq: Sequence[int]) -> AuthorityVector:
        if len(seq) != 6:
            raise ValueError(f"AuthorityVector requires exactly 6 dimensions, got {len(seq)}")
        return cls(
            e_leadership=int(seq[0]),
            r_policy=int(seq[1]),
            r_revocation=int(seq[2]),
            r_registry=int(seq[3]),
            r_identity=int(seq[4]),
            r_contract=int(seq[5]),
        )

    @classmethod
    def genesis(cls) -> AuthorityVector:
        """Genesis state vector: <1, 1, 0, 1, 1, 1>."""
        return cls(
            e_leadership=1,
            r_policy=1,
            r_revocation=0,
            r_registry=1,
            r_identity=1,
            r_contract=1,
        )

    def dominates(self, other: AuthorityVector) -> bool:
        """Monotonic dominance check: self >= other across all dimensions."""
        s = self.to_tuple()
        o = other.to_tuple()
        return all(a >= b for a, b in zip(s, o))

    def validate_lease(self, lease_vector: AuthorityVector) -> tuple[bool, str]:
        """Validate if a capability lease with lease_vector is authorized under self (host).

        Rules:
        1. Fencing: lease leadership cannot exceed host leadership.
        2. Revocation: if host revocation > lease revocation, lease is revoked.
        3. Contract Lock: contract revision must match host exactly.
        4. Policy: lease policy cannot exceed host policy.
        """
        if self.r_revocation > lease_vector.r_revocation:
            return False, f"REVOKED: host revocation revision {self.r_revocation} > lease {lease_vector.r_revocation}"
        if lease_vector.r_contract != self.r_contract:
            return False, f"CONTRACT_DRIFT: lease contract {lease_vector.r_contract} != host {self.r_contract}"
        if lease_vector.e_leadership < self.e_leadership:
            return False, f"STALE_LEADERSHIP: lease leadership {lease_vector.e_leadership} < host {self.e_leadership}"
        if lease_vector.r_policy < self.r_policy:
            return False, f"STALE_POLICY: lease policy {lease_vector.r_policy} < host {self.r_policy}"
        return True, "OK"

    def bump_leadership(self) -> AuthorityVector:
        return AuthorityVector(
            e_leadership=self.e_leadership + 1,
            r_policy=self.r_policy,
            r_revocation=self.r_revocation,
            r_registry=self.r_registry,
            r_identity=self.r_identity,
            r_contract=self.r_contract,
        )

    def bump_policy(self) -> AuthorityVector:
        return AuthorityVector(
            e_leadership=self.e_leadership,
            r_policy=self.r_policy + 1,
            r_revocation=self.r_revocation,
            r_registry=self.r_registry,
            r_identity=self.r_identity,
            r_contract=self.r_contract,
        )

    def bump_revocation(self) -> AuthorityVector:
        return AuthorityVector(
            e_leadership=self.e_leadership,
            r_policy=self.r_policy,
            r_revocation=self.r_revocation + 1,
            r_registry=self.r_registry,
            r_identity=self.r_identity,
            r_contract=self.r_contract,
        )

    def bump_registry(self) -> AuthorityVector:
        return AuthorityVector(
            e_leadership=self.e_leadership,
            r_policy=self.r_policy,
            r_revocation=self.r_revocation,
            r_registry=self.r_registry + 1,
            r_identity=self.r_identity,
            r_contract=self.r_contract,
        )

    def bump_identity(self) -> AuthorityVector:
        return AuthorityVector(
            e_leadership=self.e_leadership,
            r_policy=self.r_policy,
            r_revocation=self.r_revocation,
            r_registry=self.r_registry,
            r_identity=self.r_identity + 1,
            r_contract=self.r_contract,
        )

    def bump_contract(self) -> AuthorityVector:
        return AuthorityVector(
            e_leadership=self.e_leadership,
            r_policy=self.r_policy,
            r_revocation=self.r_revocation,
            r_registry=self.r_registry,
            r_identity=self.r_identity,
            r_contract=self.r_contract + 1,
        )

    def canonical_digest(self) -> str:
        """Deterministic SHA-256 hash of the vector tuple."""
        raw = json.dumps(self.to_list(), separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
