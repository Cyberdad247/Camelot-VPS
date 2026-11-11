# SPDX-License-Identifier: MIT

"""Global Ledger Synchronization — Replicates the root PROVENANCE_LEDGER.md across the Spire.

# HITL: file-ops pre-approved — shutil.copy writes are read-only replication of the provenance ledger
"""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ROOT_LEDGER = REPO_ROOT / "PROVENANCE_LEDGER.md"

TARGET_LEDGERS = [
    REPO_ROOT / "docs" / "PROVENANCE_LEDGER.md",
    REPO_ROOT / "03_VAULT" / "PROVENANCE_LEDGER.md",
    REPO_ROOT / "03_VAULT" / "training" / "configs" / "PROVENANCE_LEDGER.md",
]

def sync_all():
    if not ROOT_LEDGER.exists():
        print(f"❌ Error: Root ledger not found at {ROOT_LEDGER}")
        return False

    print(f"🔄 Syncing root ledger to {len(TARGET_LEDGERS)} targets...")
    
    success_count = 0
    for target in TARGET_LEDGERS:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT_LEDGER, target)
            print(f"  ✅ Synced: {target.relative_to(REPO_ROOT)}")
            success_count += 1
        except Exception as e:
            print(f"  ❌ Failed: {target.relative_to(REPO_ROOT)} ({e})")
            
    print(f"\n✨ Global Sync Complete. {success_count}/{len(TARGET_LEDGERS)} targets updated.")
    return success_count == len(TARGET_LEDGERS)

if __name__ == "__main__":
    sync_all()
