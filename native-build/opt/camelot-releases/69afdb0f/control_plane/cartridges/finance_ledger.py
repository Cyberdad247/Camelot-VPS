# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Financial Audit & Ledger Cartridge (`camelot.finance.ledger`)
============================================================
Vertical slice for automated invoice reconciliation, double-entry ledger balancing,
and cryptographically signed financial receipts.

Core Mandate: "Debits must equal credits; all journal entries are sealed with SHA-256."
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger("camelot.finance_ledger")


@dataclass
class JournalEntry:
    entry_id: str
    tenant_id: str
    description: str
    debit_account: str
    debit_amount: float
    credit_account: str
    credit_amount: float
    is_balanced: bool
    entry_hash: str
    status: str  # "RECONCILED" | "UNBALANCED" | "SEALED"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FinanceLedgerCartridge:
    """Sovereign Double-Entry Accounting & Reconciliation Engine."""

    def __init__(self, tenant_id: str = "tenant_sovereign_001"):
        self.tenant_id = tenant_id
        self.state_dir = Path("03_VAULT/runtime_state/finance_ledger")
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def reconcile_transaction(
        self,
        description: str,
        debit_account: str,
        debit_amount: float,
        credit_account: str,
        credit_amount: float
    ) -> JournalEntry:
        """Reconciles debits and credits and computes deterministic journal entry hash."""
        entry_id = f"jrn_{uuid.uuid4().hex[:8]}"
        is_balanced = (round(debit_amount, 2) == round(credit_amount, 2))
        
        raw_msg = f"{entry_id}:{self.tenant_id}:{debit_account}:{debit_amount}:{credit_account}:{credit_amount}:{is_balanced}"
        entry_hash = f"sha256:{hashlib.sha256(raw_msg.encode('utf-8')).hexdigest()}"

        entry = JournalEntry(
            entry_id=entry_id,
            tenant_id=self.tenant_id,
            description=description,
            debit_account=debit_account,
            debit_amount=debit_amount,
            credit_account=credit_account,
            credit_amount=credit_amount,
            is_balanced=is_balanced,
            entry_hash=entry_hash,
            status="SEALED" if is_balanced else "UNBALANCED"
        )

        self._record_entry(entry)
        if not is_balanced:
            LOG.warning(f"[FINANCE_ALERT] Unbalanced journal entry {entry_id}: Debit({debit_amount}) != Credit({credit_amount})")
        else:
            LOG.info(f"[FINANCE_LEDGER] Reconciled and sealed journal entry {entry_id} (${debit_amount})")
        return entry

    def _record_entry(self, entry: JournalEntry) -> None:
        target_file = self.state_dir / f"{entry.entry_id}.json"
        target_file.write_text(json.dumps(asdict(entry), indent=2), encoding="utf-8")
        
        ledger_path = self.state_dir / "general_ledger.jsonl"
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
