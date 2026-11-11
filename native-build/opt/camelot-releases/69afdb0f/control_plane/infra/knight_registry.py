# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — Knight Character Sheet Registry & Arch-Librarian Interconnect
r"""
Full Character Sheet Registry assisting Arch-Librarian Lady Mnemosyne with:
  1. Summoning Knights by exact Spark ID and Knight ID.
  2. Interconnecting Knight brains to their designated CloudBrain Notebook,
     VFS Path, MemPalace Wing, Open Viking Architecture Node, and Open-Notebook local tissue.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SHEETS_PATH = _REPO_ROOT / "03_VAULT" / "training" / "configs" / "knight_character_sheets.json"


@dataclass
class KnightCharacterSheet:
    knight_id: str
    spark_id: str
    name: str
    title: str
    layer: str
    role: str
    summoning_rune: str
    cloudbrain_uuid: str
    vfs_path: str
    mempalace_wing: str
    open_viking_node: str
    primary_engine: str = "Gemini 3.8 Flash"
    skill_tier: str = "S3 Contextual"
    ocean_vector: Dict[str, float] = field(default_factory=dict)
    domain_tags: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    cron_schedule: Optional[str] = None
    interconnect_status: str = "TETHERED_TO_WORLDTREE"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KnightCharacterSheet:
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ArchLibrarianRegistry:
    """Arch-Librarian registry used by Lady Mnemosyne to summon Knights and interconnect their brains."""

    def __init__(self, sheets_file: Optional[Path] = None):
        self.sheets_file = sheets_file or _SHEETS_PATH
        self.worldtree_home_id = "a0a4bfb9-e847-4c38-be39-7aee398f0795"
        self._sheets: Dict[str, KnightCharacterSheet] = {}
        self._load_sheets()

    def _load_sheets(self) -> None:
        if not self.sheets_file.exists():
            logging.error(f"[LIBRARIAN] Character sheet registry missing at {self.sheets_file}")
            return

        try:
            raw = json.loads(self.sheets_file.read_text(encoding="utf-8"))
            self.worldtree_home_id = raw.get("worldtree_home_uuid", self.worldtree_home_id)
            knights_data = raw.get("knights", {})
            for k_id, data in knights_data.items():
                self._sheets[k_id.upper()] = KnightCharacterSheet.from_dict(data)
        except Exception as exc:
            logging.error(f"[LIBRARIAN] Failed loading knight character sheets: {exc}")

    def summon_knight(self, knight_id: str) -> Optional[KnightCharacterSheet]:
        """Summons a Knight by ID and returns their full character sheet."""
        key = knight_id.upper()
        sheet = self._sheets.get(key)
        if sheet:
            logging.info(f"[LIBRARIAN] Summoned Knight '{sheet.name}' (Spark ID: {sheet.spark_id})")
        else:
            logging.warning(f"[LIBRARIAN] Knight ID '{knight_id}' not found in registry.")
        return sheet

    def interconnect_brain(self, knight_id: str) -> Dict[str, Any]:
        """Interconnects a Knight's brain to World Tree, CloudBrain, VFS, MemPalace, and Open Viking."""
        sheet = self.summon_knight(knight_id)
        if not sheet:
            return {
                "knight_id": knight_id.upper(),
                "status": "UNMAPPED_FALLBACK",
                "worldtree_home": self.worldtree_home_id,
                "cloudbrain_uuid": self.worldtree_home_id,
                "vfs_path": f"vfs://worldtree/knights/{knight_id.lower()}/tether.json",
                "mempalace_wing": f"WING_WORLDTREE_{knight_id.upper()}",
                "open_viking_node": f"open_viking://worldtree/{knight_id.lower()}",
            }

        return {
            "knight_id": sheet.knight_id,
            "spark_id": sheet.spark_id,
            "name": sheet.name,
            "title": sheet.title,
            "summoning_rune": sheet.summoning_rune,
            "worldtree_home": self.worldtree_home_id,
            "cloudbrain_uuid": sheet.cloudbrain_uuid,
            "vfs_path": sheet.vfs_path,
            "mempalace_wing": sheet.mempalace_wing,
            "open_viking_node": sheet.open_viking_node,
            "primary_engine": sheet.primary_engine,
            "ocean_vector": sheet.ocean_vector,
            "brain_interconnected": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def list_all_sheets(self) -> Dict[str, Dict[str, Any]]:
        """Lists all registered Knight Character Sheets."""
        return {k_id: sheet.to_dict() for k_id, sheet in self._sheets.items()}


# Global Singleton for Arch-Librarian access
LIBRARIAN_REGISTRY = ArchLibrarianRegistry()


if __name__ == "__main__":
    print("=== ARCH-LIBRARIAN KNIGHT CHARACTER SHEET REGISTRY ===")
    all_sheets = LIBRARIAN_REGISTRY.list_all_sheets()
    print(f"Total Registered Character Sheets: {len(all_sheets)}")
    for k_id, sheet in list(all_sheets.items())[:3]:
        print(f"\n--- {sheet['name']} ({sheet['spark_id']}) ---")
        print(f"  Rune       : {sheet['summoning_rune']}")
        print(f"  CloudBrain : {sheet['cloudbrain_uuid']}")
        print(f"  VFS Path   : {sheet['vfs_path']}")
        print(f"  MemPalace  : {sheet['mempalace_wing']}")
        print(f"  OpenViking : {sheet['open_viking_node']}")
