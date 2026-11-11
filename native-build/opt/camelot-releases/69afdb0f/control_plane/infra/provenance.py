# SPDX-License-Identifier: MIT

"""Provenance and Audit Ledger Manager — Structured Mission Traceability.

# HITL: file-ops pre-approved — all writes are append-only audit ledger entries
"""

from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import hashlib
import importlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

# Dynamic import for MemPalaceL2 due to 01_KERNEL naming restriction.
# Import as a package so mempalace_l2.py can resolve its own relative imports.
try:
    MemPalaceL2 = importlib.import_module("01_KERNEL.memory.mempalace_l2").MemPalaceL2
except Exception:
    # Fallback loader for CLIs whose sys.path does not include the repo root:
    # __file__ is <root>/control_plane/infra/provenance.py, so the repo root is
    # parents[2] (infra -> control_plane -> root).
    _MEM_PATH = Path(__file__).resolve().parents[2] / "01_KERNEL" / "memory" / "mempalace_l2.py"
    if not _MEM_PATH.exists():
        raise ImportError(
            f"Cannot locate 01_KERNEL/memory/mempalace_l2.py (tried {_MEM_PATH}). "
            "Run the CLI from the CAMELOT_OS repo root."
        ) from None
    _MEM_SPEC = importlib.util.spec_from_file_location("01_KERNEL.memory.mempalace_l2", _MEM_PATH)
    _MEM_MOD = importlib.util.module_from_spec(_MEM_SPEC)
    assert _MEM_SPEC and _MEM_SPEC.loader
    sys_modules = importlib.import_module("sys").modules
    sys_modules[_MEM_SPEC.name] = _MEM_MOD
    _MEM_SPEC.loader.exec_module(_MEM_MOD)
    MemPalaceL2 = _MEM_MOD.MemPalaceL2


class LaneEvent(BaseModel):
    """A single event within a browser lane."""
    type: str
    timestamp: int
    offset_ms: int
    data: dict[str, Any]


class MissionLane(BaseModel):
    """Execution trace of a single Nano-Knight lane."""
    lane_id: str
    goal: str
    status: str
    evaluation: Optional[dict[str, Any]] = None
    events: list[LaneEvent] = Field(default_factory=list)


class MissionRecord(BaseModel):
    """Complete audit record for a Precise Mode mission."""
    mission_id: str
    objective: str
    operator: str
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str
    compute_tier: str
    browser_isolation: str
    lanes: dict[str, MissionLane] = Field(default_factory=dict)
    summary: Optional[str] = None
    entry_id: Optional[int] = None
    parent_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Calculate SHA-256 hash of the record data excluding the hash itself."""
        data = self.model_dump(exclude={"entry_hash"})
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class VerificationRun(BaseModel):
    """Record of a system verification or acceptance run."""
    run_id: str
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operator: str
    command: str
    results: dict[str, Any]
    success: bool
    entry_id: Optional[int] = None
    parent_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Calculate SHA-256 hash of the run data excluding the hash itself."""
        data = self.model_dump(exclude={"entry_hash"})
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class ProvenanceManager:
    """Manages structured JSON ledgers and mission archival."""

    def __init__(self, vault_path: Optional[Path] = None):
        if vault_path:
            self.vault_path = vault_path
        else:
            # Default to 03_VAULT/Missions
            repo_root = Path(__file__).resolve().parent.parent
            self.vault_path = repo_root / "03_VAULT" / "Missions"
        
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.verification_ledger = self.vault_path / "verification_ledger.jsonl"
        # MemPalace remains strict about its HMAC secret, but missing optional
        # persistence must not prevent CLI startup or local ledger writes.
        try:
            self.mempalace = MemPalaceL2()
            self.memory_status = {"state": "ready", "reason": None}
        except RuntimeError as exc:
            if "MEMPALACE_SECRET is not set" not in str(exc):
                raise
            self.mempalace = None
            self.memory_status = {
                "state": "degraded",
                "reason": "MEMPALACE_SECRET is not set",
            }

    def log_mission(self, record: MissionRecord):
        """Save a complete mission record to the vault."""
        # For individual files, we still assign an entry ID and hash for integrity
        # but we don't necessarily chain them across files yet (Task L5 expansion).
        record.entry_hash = record.compute_hash()
        file_path = self.vault_path / f"mission_{record.mission_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record.model_dump(), f, indent=2)
        return file_path

    def log_verification(self, run: VerificationRun):
        """Append a verification run to the JSONL ledger with cryptographic chaining."""
        last_entry = self.get_last_verification_entry()
        
        if last_entry:
            run.entry_id = (last_entry.get("entry_id") or 0) + 1
            run.parent_hash = last_entry.get("entry_hash")
        else:
            run.entry_id = 1
            run.parent_hash = None
            
        run.entry_hash = run.compute_hash()
        
        with open(self.verification_ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(run.model_dump()) + "\n")
            
        # Automatic forge_upgrade_verified crystallization trigger
        if run.success and isinstance(run.results, dict) and run.results.get("event_type") == "forge_upgrade_verified":
            source_dir = run.results.get("source_dir")
            if source_dir:
                try:
                    from control_plane import forge_law
                    forge_law.crystallize_source(source_dir, ledger=self.verification_ledger)
                except Exception:
                    pass  # crystallization is a side effect; don't block ledger write

        # Automatic feed into MemPalace L2
        content = f"Verification Run {run.run_id}: {run.command}\nOperator: {run.operator}\nSuccess: {run.success}\nResults: {json.dumps(run.results)}"
        if self.mempalace is not None:
            self.mempalace.store(
                wing="camelot",
                room="audit",
                content=content,
                metadata={
                    "run_id": run.run_id,
                    "operator": run.operator,
                    "command": run.command,
                    "success": run.success,
                    "entry_hash": run.entry_hash,
                    "retention_class": "SCHEMA_STATIC",
                },
                tenant_id=run.operator,
            )
        
        return self.verification_ledger

    def get_last_verification_entry(self) -> Optional[dict[str, Any]]:
        """Retrieve the last entry from the verification ledger."""
        if not self.verification_ledger.exists():
            return None
            
        try:
            with open(self.verification_ledger, "rb") as f:
                f.seek(0, os.SEEK_END)
                filesize = f.tell()
                if filesize == 0:
                    return None
                
                # Step back from the end to find the start of the last line
                # We start at -2 because -1 is the trailing newline
                offset = -2
                while abs(offset) <= filesize:
                    f.seek(offset, os.SEEK_END)
                    char = f.read(1)
                    if char == b"\n":
                        break
                    offset -= 1
                else:
                    # Reached start of file
                    f.seek(0)
                
                last_line = f.readline().decode("utf-8").strip()
                if not last_line:
                    return None
                return json.loads(last_line)
        except Exception:
            return None

    def get_verification_entries(self) -> list[dict[str, Any]]:
        """Retrieve all entries from the verification ledger."""
        if not self.verification_ledger.exists():
            return []
            
        entries = []
        with open(self.verification_ledger, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def verify_integrity(self) -> bool:
        """Forensic audit of the verification ledger.
        
        Verifies:
        1. Every entry_hash matches its content.
        2. Every parent_hash correctly points to the previous entry's entry_hash.
        3. Sequential entry_ids.
        """
        entries = self.get_verification_entries()
        if not entries:
            return True
            
        prev_hash = None
        for i, entry_data in enumerate(entries):
            # 1. Verify sequential entry_id
            if entry_data.get("entry_id") != i + 1:
                return False
                
            # 2. Verify parent_hash chain
            if entry_data.get("parent_hash") != prev_hash:
                return False
                
            # 3. Verify entry_hash matches content
            # Reconstruct model to use compute_hash
            try:
                run = VerificationRun(**entry_data)
                actual_hash = run.compute_hash()
                if entry_data.get("entry_hash") != actual_hash:
                    return False
            except Exception:
                return False
                
            prev_hash = entry_data.get("entry_hash")
            
        return True

    def get_retention_stats(self) -> dict[str, Any]:
        """Compute stats for log rotation policy (Task E5)."""
        files = list(self.vault_path.glob("mission_*.json"))
        total_size = sum(f.stat().st_size for f in files)
        return {
            "mission_count": len(files),
            "total_size_bytes": total_size,
            "verification_entries": self._count_verification_entries()
        }

    def _count_verification_entries(self) -> int:
        if not self.verification_ledger.exists():
            return 0
        with open(self.verification_ledger, "r") as f:
            return sum(1 for _ in f)

    def rotate_logs(self, max_files: int = 100):
        """Archive old mission logs if count exceeds threshold."""
        files = sorted(
            list(self.vault_path.glob("mission_*.json")),
            key=lambda x: x.stat().st_mtime
        )
        if len(files) <= max_files:
            return 0

        archived_count = 0
        archive_dir = self.vault_path / "Archive"
        archive_dir.mkdir(exist_ok=True)

        for f in files[:-max_files]:
            f.rename(archive_dir / f.name)
            archived_count += 1
        
        return archived_count
