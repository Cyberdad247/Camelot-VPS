# SPDX-License-Identifier: MIT
"""Merkle Ledger Receipt Chain Engine — Phase 1B Per-Tenant Integrity Chains.

Implements the SADD+LLDD v1.2 §11.3 per-tenant hash-linked receipt chain.
Every consequential state transition emits a receipt; receipts are hash-linked
into an isolated per-tenant Merkle chain whose head is anchored to the ledger.

Invariants:
    1. Genesis receipt: parent_hash == 'sha256:' + '0'*64 and chain_height == 0.
    2. Monotonicity: chain_height[n] == chain_height[n-1] + 1.
    3. Merkle Chaining: parent_hash[n] == self_hash[n-1].
    4. Self-Hash Purity: SHA-256 over RFC 8785 canonical serialization with self_hash
       and signature stripped.
    5. Authority Dominance: receipt.authority_epoch >= trusted_epoch.
    6. Tenant Isolation: Each tenant has an isolated chain; cross-tenant linking is illegal.
    7. Ledger Anchoring: When chain_height % anchor_interval == 0, receipt is anchor-eligible.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.contracts.canonicalize import sha256_canonical


GENESIS_PARENT_HASH = "sha256:" + "0" * 64
DEFAULT_ANCHOR_INTERVAL = 1000


class ChainVerificationError(Exception):
    """Raised when receipt chain verification or append fails."""
    def __init__(self, message: str, broken_at_height: Optional[int] = None, broken_receipt_id: Optional[str] = None):
        self.broken_at_height = broken_at_height
        self.broken_receipt_id = broken_receipt_id
        super().__init__(message)


class TenantIsolationViolation(Exception):
    """Raised when an operation attempts to breach tenant boundaries."""
    pass


@dataclass
class ReceiptProof:
    signer: str
    signature: str
    hash_algorithm: str = "sha256"
    signature_algorithm: str = "ed25519"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReceiptActor:
    id: str
    role: str
    node_id: str
    trust_band: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Receipt:
    receipt_id: str
    tenant_id: str
    correlation_id: str
    task_id: str
    chain_height: int
    parent_hash: str
    authority_epoch: int
    authority_vector: list[int]
    effect_class: str
    declared_risk_tier: str
    actor: ReceiptActor
    event: str
    proof: ReceiptProof
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "camelot-receipt/2"
    refs: dict[str, Any] = field(default_factory=dict)
    payload_redacted: dict[str, Any] = field(default_factory=dict)
    ledger_anchor_eligible: bool = False
    self_hash: Optional[str] = None

    def compute_self_hash(self) -> str:
        """Compute SHA-256 over RFC 8785 canonical serialization with self_hash and proof.signature stripped."""
        data = self.to_dict()
        data.pop("self_hash", None)
        # Strip proof signature for hash stability per spec
        if "proof" in data and isinstance(data["proof"], dict):
            proof_copy = dict(data["proof"])
            proof_copy.pop("signature", None)
            data["proof"] = proof_copy

        return f"sha256:{sha256_canonical(data)}"

    def seal(self) -> Receipt:
        """Compute and set self_hash, returning self."""
        self.self_hash = self.compute_self_hash()
        return self

    def verify_integrity(self) -> bool:
        """Verify self_hash matches computed hash."""
        if not self.self_hash:
            return False
        return self.compute_self_hash() == self.self_hash

    def to_dict(self) -> dict[str, Any]:
        d = {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "parent_hash": self.parent_hash,
            "chain_height": self.chain_height,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "task_id": self.task_id,
            "authority_epoch": self.authority_epoch,
            "authority_vector": list(self.authority_vector),
            "effect_class": self.effect_class,
            "declared_risk_tier": self.declared_risk_tier,
            "timestamp": self.timestamp,
            "actor": self.actor.to_dict() if isinstance(self.actor, ReceiptActor) else self.actor,
            "event": self.event,
            "proof": self.proof.to_dict() if isinstance(self.proof, ReceiptProof) else self.proof,
            "ledger_anchor_eligible": self.ledger_anchor_eligible,
        }
        if self.refs:
            d["refs"] = self.refs
        if self.payload_redacted:
            d["payload_redacted"] = self.payload_redacted
        if self.self_hash is not None:
            d["self_hash"] = self.self_hash
        return d


@dataclass
class ReceiptChainHead:
    tenant_id: str
    chain_height: int
    head_hash: str
    last_anchor_height: int
    last_anchor_hash: str
    schema_version: str = "camelot-receipt-chain/1"
    anchor_interval: int = DEFAULT_ANCHOR_INTERVAL
    anchor_target: Optional[str] = None
    verified: bool = True
    last_verified_at: Optional[str] = None
    replay_protected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TenantReceiptChain:
    """Manages an isolated per-tenant Merkle receipt chain."""

    def __init__(self, tenant_id: str, anchor_interval: int = DEFAULT_ANCHOR_INTERVAL):
        if not tenant_id.startswith("tenant_"):
            raise ValueError(f"tenant_id must match pattern '^tenant_[A-Za-z0-9_-]+$', got '{tenant_id}'")
        self.tenant_id = tenant_id
        self.anchor_interval = anchor_interval
        self._receipts: list[Receipt] = []
        self._head_hash = GENESIS_PARENT_HASH
        self._last_anchor_height = 0
        self._last_anchor_hash = GENESIS_PARENT_HASH

    @property
    def chain_height(self) -> int:
        return len(self._receipts)

    @property
    def head_hash(self) -> str:
        return self._head_hash

    def get_head(self) -> ReceiptChainHead:
        return ReceiptChainHead(
            tenant_id=self.tenant_id,
            chain_height=self.chain_height,
            head_hash=self._head_hash,
            last_anchor_height=self._last_anchor_height,
            last_anchor_hash=self._last_anchor_hash,
            anchor_interval=self.anchor_interval,
            verified=True,
            last_verified_at=datetime.now(timezone.utc).isoformat(),
        )

    def append(self, receipt: Receipt, trusted_epoch: int = 0) -> Receipt:
        """Append a new receipt to this tenant's chain, validating all invariants."""
        # 1. Tenant boundary enforcement
        if receipt.tenant_id != self.tenant_id:
            raise TenantIsolationViolation(
                f"Cannot append receipt for tenant '{receipt.tenant_id}' to chain for tenant '{self.tenant_id}'"
            )

        # 2. Authority epoch dominance
        if receipt.authority_epoch < trusted_epoch:
            raise ChainVerificationError(
                f"Receipt authority_epoch {receipt.authority_epoch} is below trusted epoch {trusted_epoch}"
            )

        # 3. Authority vector validity
        if len(receipt.authority_vector) != 6:
            raise ChainVerificationError(
                f"Authority vector must be 6-dimensional tuple, got {receipt.authority_vector}"
            )

        expected_height = len(self._receipts)
        # 4. Chain height monotonicity
        if receipt.chain_height != expected_height:
            raise ChainVerificationError(
                f"Invalid chain_height {receipt.chain_height}; expected {expected_height}",
                broken_at_height=receipt.chain_height,
                broken_receipt_id=receipt.receipt_id,
            )

        # 5. Parent hash linking
        if expected_height == 0:
            if receipt.parent_hash != GENESIS_PARENT_HASH:
                raise ChainVerificationError(
                    f"Genesis receipt must have parent_hash '{GENESIS_PARENT_HASH}', got '{receipt.parent_hash}'",
                    broken_at_height=0,
                    broken_receipt_id=receipt.receipt_id,
                )
        else:
            if receipt.parent_hash != self._head_hash:
                raise ChainVerificationError(
                    f"Receipt parent_hash '{receipt.parent_hash}' does not match chain head '{self._head_hash}'",
                    broken_at_height=receipt.chain_height,
                    broken_receipt_id=receipt.receipt_id,
                )

        # 6. Anchor eligibility
        if receipt.chain_height > 0 and receipt.chain_height % self.anchor_interval == 0:
            receipt.ledger_anchor_eligible = True

        # 7. Seal receipt (computes self_hash)
        receipt.seal()

        # 8. Update chain head
        self._head_hash = receipt.self_hash
        if receipt.ledger_anchor_eligible:
            self._last_anchor_height = receipt.chain_height
            self._last_anchor_hash = receipt.self_hash

        self._receipts.append(receipt)
        return receipt

    def verify_chain(self, trusted_epoch: int = 0) -> tuple[bool, str]:
        """Perform full cryptographic audit of the receipt chain."""
        expected_parent = GENESIS_PARENT_HASH
        for idx, r in enumerate(self._receipts):
            if r.tenant_id != self.tenant_id:
                return False, f"Receipt {r.receipt_id} has mismatched tenant_id '{r.tenant_id}'"
            if r.chain_height != idx:
                return False, f"Receipt {r.receipt_id} height mismatch: {r.chain_height} != {idx}"
            if r.parent_hash != expected_parent:
                return False, f"Receipt {r.receipt_id} broken parent_hash link at height {idx}"
            if not r.verify_integrity():
                return False, f"Receipt {r.receipt_id} integrity failed: self_hash tampered"
            if r.authority_epoch < trusted_epoch:
                return False, f"Receipt {r.receipt_id} epoch {r.authority_epoch} < {trusted_epoch}"
            expected_parent = r.self_hash

        return True, "CHAIN_VALID"

    def list_receipts(self, limit: int = 50) -> list[Receipt]:
        return list(self._receipts[-limit:])


# ==============================================================================
# Sovereign Merkle Root Checkpoint (Arthur Ed25519 Seal)
# ==============================================================================

@dataclass
class CheckpointProof:
    signer: str  # "king-arthur"
    signature: str  # "ed25519:<hex>"
    public_key: str  # hex string
    hash_algorithm: str = "sha256"
    signature_algorithm: str = "ed25519"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SovereignMerkleCheckpoint:
    checkpoint_id: str
    merkle_root: str
    tenant_heads: dict[str, dict[str, Any]]  # tenant_id -> {"chain_height": int, "head_hash": str}
    authority_epoch: int
    proof: CheckpointProof
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "camelot-checkpoint/1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checkpoint_id": self.checkpoint_id,
            "merkle_root": self.merkle_root,
            "tenant_heads": self.tenant_heads,
            "authority_epoch": self.authority_epoch,
            "timestamp": self.timestamp,
            "proof": self.proof.to_dict(),
        }

    def canonical_digest(self) -> str:
        """Compute SHA-256 over RFC 8785 canonical serialization with proof.signature stripped."""
        data = self.to_dict()
        if "proof" in data and isinstance(data["proof"], dict):
            proof_copy = dict(data["proof"])
            proof_copy.pop("signature", None)
            data["proof"] = proof_copy
        return sha256_canonical(data)


def compute_tenant_head_leaf(tenant_id: str, chain_height: int, head_hash: str) -> str:
    """Compute deterministic SHA-256 leaf hash for a tenant's head in the Merkle checkpoint."""
    payload = {
        "tenant_id": tenant_id,
        "chain_height": chain_height,
        "head_hash": head_hash,
    }
    return sha256_canonical(payload)


def build_merkle_tree(leaf_hashes: list[str]) -> tuple[str, list[list[str]]]:
    """Build a binary Merkle tree over sorted leaf hashes.

    Returns (merkle_root, tree_levels) where tree_levels[0] is leaves and tree_levels[-1][0] is root.
    """
    if not leaf_hashes:
        return "sha256:" + "0" * 64, []

    current_level = list(leaf_hashes)
    levels = [current_level]

    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            # If odd number of nodes, duplicate the last node
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            combined = hashlib.sha256(f"{left}:{right}".encode("utf-8")).hexdigest()
            next_level.append(combined)
        current_level = next_level
        levels.append(current_level)

    root = f"sha256:{levels[-1][0]}"
    return root, levels


class SovereignMerkleCheckpointGovernor:
    """Aggregates per-tenant append-only Merkle chains into a signed Merkle root checkpoint (Arthur Ed25519 Seal).

    Diagram:
        Tenant A Chain ─── Head A ┐
        Tenant B Chain ─── Head B ├─► Signed Merkle Root Checkpoint (Arthur Ed25519 Seal)
        Tenant C Chain ─── Head C ┘
    """

    # Sovereign test key (deterministic 32-byte seed for King Arthur)
    _ARTHUR_SOVEREIGN_SEED = b"Arthur_Omega_Sovereign_Seed_32B!"

    def __init__(self, chains: Optional[dict[str, TenantReceiptChain]] = None):
        self._chains: dict[str, TenantReceiptChain] = chains or {}

    def register_chain(self, chain: TenantReceiptChain) -> None:
        self._chains[chain.tenant_id] = chain

    def get_chain(self, tenant_id: str) -> Optional[TenantReceiptChain]:
        return self._chains.get(tenant_id)

    @classmethod
    def get_default_arthur_key(cls):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        return ed25519.Ed25519PrivateKey.from_private_bytes(cls._ARTHUR_SOVEREIGN_SEED)

    def compute_merkle_root(self) -> tuple[str, list[str], dict[str, dict[str, Any]]]:
        """Collect sorted tenant heads and compute the binary Merkle root."""
        sorted_tenants = sorted(self._chains.keys())
        tenant_heads: dict[str, dict[str, Any]] = {}
        leaf_hashes: list[str] = []

        for tenant_id in sorted_tenants:
            chain = self._chains[tenant_id]
            head_info = {
                "chain_height": chain.chain_height,
                "head_hash": chain.head_hash,
            }
            tenant_heads[tenant_id] = head_info
            leaf = compute_tenant_head_leaf(tenant_id, chain.chain_height, chain.head_hash)
            leaf_hashes.append(leaf)

        root, _ = build_merkle_tree(leaf_hashes)
        return root, leaf_hashes, tenant_heads

    def create_signed_checkpoint(
        self,
        authority_epoch: int = 1,
        private_key: Optional[Any] = None,
        checkpoint_id: Optional[str] = None,
    ) -> SovereignMerkleCheckpoint:
        """Issue a Signed Merkle Root Checkpoint with the Arthur Ed25519 Seal."""

        key = private_key or self.get_default_arthur_key()
        pub_bytes = key.public_key().public_bytes_raw()
        pub_hex = pub_bytes.hex()

        merkle_root, _, tenant_heads = self.compute_merkle_root()
        cid = checkpoint_id or f"chk_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{merkle_root[7:15]}"

        # Create unsigned checkpoint template
        checkpoint = SovereignMerkleCheckpoint(
            checkpoint_id=cid,
            merkle_root=merkle_root,
            tenant_heads=tenant_heads,
            authority_epoch=authority_epoch,
            proof=CheckpointProof(
                signer="king-arthur",
                signature="",  # will populate after signing
                public_key=pub_hex,
            ),
        )

        # Cryptographic signing with Arthur Ed25519 Seal
        digest = checkpoint.canonical_digest()
        signature_bytes = key.sign(digest.encode("utf-8"))
        signature_hex = f"ed25519:{signature_bytes.hex()}"

        checkpoint.proof.signature = signature_hex
        return checkpoint

    @staticmethod
    def verify_checkpoint(checkpoint: SovereignMerkleCheckpoint) -> tuple[bool, str]:
        """Cryptographically verify the Arthur Ed25519 Seal and Merkle root integrity."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # 1. Recompute Merkle root over tenant heads
        sorted_tenants = sorted(checkpoint.tenant_heads.keys())
        leaf_hashes = []
        for t in sorted_tenants:
            info = checkpoint.tenant_heads[t]
            leaf = compute_tenant_head_leaf(t, info["chain_height"], info["head_hash"])
            leaf_hashes.append(leaf)

        expected_root, _ = build_merkle_tree(leaf_hashes)
        if expected_root != checkpoint.merkle_root:
            return False, f"Merkle root mismatch: expected {expected_root}, got {checkpoint.merkle_root}"

        # 2. Verify Arthur Ed25519 signature
        if not checkpoint.proof.signature.startswith("ed25519:"):
            return False, "Invalid signature format; expected 'ed25519:<hex>'"

        sig_hex = checkpoint.proof.signature.split("ed25519:", 1)[1]
        sig_bytes = bytes.fromhex(sig_hex)
        pub_bytes = bytes.fromhex(checkpoint.proof.public_key)

        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        digest = checkpoint.canonical_digest().encode("utf-8")

        try:
            public_key.verify(sig_bytes, digest)
        except Exception as e:
            return False, f"Ed25519 signature verification failed: {e}"

        return True, "CHECKPOINT_SEAL_VALID"

    def generate_inclusion_proof(self, tenant_id: str) -> tuple[str, list[dict[str, str]]]:
        """Generate a Merkle inclusion proof (audit path) for a specific tenant chain head."""
        sorted_tenants = sorted(self._chains.keys())
        if tenant_id not in self._chains:
            raise KeyError(f"Tenant '{tenant_id}' is not registered in this governor")

        target_idx = sorted_tenants.index(tenant_id)
        leaf_hashes = [
            compute_tenant_head_leaf(t, self._chains[t].chain_height, self._chains[t].head_hash)
            for t in sorted_tenants
        ]

        target_leaf = leaf_hashes[target_idx]
        _, levels = build_merkle_tree(leaf_hashes)

        proof: list[dict[str, str]] = []
        idx = target_idx

        for level in levels[:-1]:
            if idx % 2 == 0:
                # Target is left, sibling is right
                sibling_idx = idx + 1 if idx + 1 < len(level) else idx
                position = "right"
            else:
                # Target is right, sibling is left
                sibling_idx = idx - 1
                position = "left"

            proof.append({
                "position": position,
                "sibling_hash": level[sibling_idx],
            })
            idx = idx // 2

        return target_leaf, proof

    @staticmethod
    def verify_inclusion_proof(leaf_hash: str, proof: list[dict[str, str]], expected_root: str) -> bool:
        """Verify a Merkle audit path connects leaf_hash to expected_root."""
        current = leaf_hash
        for step in proof:
            sibling = step["sibling_hash"]
            if step["position"] == "right":
                current = hashlib.sha256(f"{current}:{sibling}".encode("utf-8")).hexdigest()
            else:
                current = hashlib.sha256(f"{sibling}:{current}".encode("utf-8")).hexdigest()

        return f"sha256:{current}" == expected_root

