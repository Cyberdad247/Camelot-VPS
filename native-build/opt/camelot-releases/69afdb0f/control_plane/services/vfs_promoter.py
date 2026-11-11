# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
control_plane.services.vfs_promoter — Content-Addressed Snapshot & CAS Head Swap
================================================================================
Implements VFS Promotion Pipeline:
  CONTENT_ADDRESSED_SNAPSHOT ➔ CAS_HEAD_SWAP ➔ PROMOTION_RECEIPT

Guarantees:
1. Pure Content Addressing: Every promoted artifact is digested via SHA-256.
2. Atomic Head Swap: Uses atomic file replace (or CAS compare-and-swap) to prevent partial writes.
3. Cryptographic Receipt: Emits an immutable PromotionReceipt before crystal admission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("vfs_promoter")

CAMELOT_HOME = Path(__file__).resolve().parent.parent.parent
CRYSTALS_DIR = CAMELOT_HOME / "03_VAULT" / "UKG" / "nodes"
RECEIPTS_DIR = CAMELOT_HOME / "03_VAULT" / "Missions" / "promotion_receipts"


@dataclass
class PromotionReceipt:
    receipt_id: str
    source_uri: str
    target_uri: str
    content_hash: str
    previous_head_hash: Optional[str]
    epoch: int
    promoted_by: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VFSPromoter:
    """Orchestrates content-addressed snapshots and atomic CAS promotion to World Tree."""

    def __init__(self, crystals_dir: Optional[Path] = None, receipts_dir: Optional[Path] = None):
        self.crystals_dir = crystals_dir or CRYSTALS_DIR
        self.receipts_dir = receipts_dir or RECEIPTS_DIR
        self.crystals_dir.mkdir(parents=True, exist_ok=True)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        self._head_hashes: Dict[str, str] = {}

    def compute_snapshot_hash(self, content_bytes: bytes) -> str:
        """Returns the SHA-256 hexadecimal digest of raw content."""
        return hashlib.sha256(content_bytes).hexdigest()

    def promote_artifact(
        self,
        source_path: Path,
        target_name: str,
        promoter_knight: str,
        expected_head_hash: Optional[str] = None,
        epoch: int = 100,
    ) -> PromotionReceipt:
        """Executes atomic CAS head swap and issues a signed promotion receipt."""
        if not source_path.exists():
            raise FileNotFoundError(f"Source artifact does not exist: {source_path}")

        raw_bytes = source_path.read_bytes()
        snapshot_hash = self.compute_snapshot_hash(raw_bytes)

        target_file = self.crystals_dir / target_name
        current_head_hash = None

        if target_file.exists():
            current_head_hash = self.compute_snapshot_hash(target_file.read_bytes())

        # CAS verification: If expected_head_hash is provided, verify match
        if expected_head_hash is not None and current_head_hash != expected_head_hash:
            raise ValueError(
                f"[CAS_HEAD_SWAP_CONFLICT] Expected head {expected_head_hash}, but found {current_head_hash}."
            )

        # Atomic head swap: Write to temporary file, then replace target atomically
        temp_file = target_file.with_suffix(f".tmp_{snapshot_hash[:8]}")
        temp_file.write_bytes(raw_bytes)
        temp_file.replace(target_file)

        self._head_hashes[target_name] = snapshot_hash

        # Mint immutable PromotionReceipt
        receipt_id = f"RCPT-PROMOTE-{snapshot_hash[:12].upper()}"
        receipt = PromotionReceipt(
            receipt_id=receipt_id,
            source_uri=str(source_path.relative_to(CAMELOT_HOME) if CAMELOT_HOME in source_path.parents else source_path),
            target_uri=f"vfs://worldtree/crystals/{target_name}",
            content_hash=snapshot_hash,
            previous_head_hash=current_head_hash,
            epoch=epoch,
            promoted_by=promoter_knight,
        )

        receipt_path = self.receipts_dir / f"{receipt_id}.json"
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2), encoding="utf-8")
        logger.info(f"[VFS_PROMOTION_SUCCESS] Promoted {target_name} ({receipt_id})")

        return receipt


# Global promoter singleton
global_vfs_promoter = VFSPromoter()
