# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
OrganizeEngine v1.0 — Phase 5 File Organization Engine
=======================================================
Lady M semantic clustering + Lady Alexandria cross-reference updater.
20,000+ files → 7-tier taxonomy. Shadow-branch mandatory per Titanium Law.
Colony re-scan required before any merge.

Iron Gate tiers:
  AUTO:   taxonomy_scan(), propose_moves(dry_run=True), merge_check()
  PROMPT: execute_tier(dry_run=False), create_shadow_branch()
  HUMAN_GATE: merge approval after colony re-scan passes

7-Tier Taxonomy:
  T1 KERNEL   — 01_KERNEL/ core runtime modules
  T2 CONTROL  — control_plane/ orchestration layer
  T3 VAULT    — 03_VAULT/ storage, configs, training, memory
  T4 FORGE    — 02_FORGE/ generators, build tools, scripts
  T5 TESTS    — tests/ all test_*.py files
  T6 DOCS     — docs/ *.md *.rst *.txt documentation
  T7 ARCHIVE  — 99_ARCHIVE/ legacy/deprecated code
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("ORGANIZE_ENGINE")

_CAMELOT_ROOT = Path(__file__).resolve().parent.parent

# ── 7-Tier taxonomy definitions ───────────────────────────────────────────────

TIER_IDS = ["T1_KERNEL", "T2_CONTROL", "T3_VAULT", "T4_FORGE", "T5_TESTS", "T6_DOCS", "T7_ARCHIVE"]

_TIER_PATTERNS: dict[str, dict] = {
    "T1_KERNEL": {
        "label": "KERNEL",
        "canonical_root": "01_KERNEL",
        "include_dirs": ["01_KERNEL"],
        "include_globs": [],
        "exclude_globs": [],
        "description": "Core runtime — knights, iron_gate, DEFENSE_GRID, merlin context",
    },
    "T2_CONTROL": {
        "label": "CONTROL",
        "canonical_root": "control_plane",
        "include_dirs": ["control_plane"],
        "include_globs": [],
        "exclude_globs": ["control_plane/__pycache__"],
        "description": "Orchestration layer — anya_gate, soul_oversight, hermes_bridge",
    },
    "T3_VAULT": {
        "label": "VAULT",
        "canonical_root": "03_VAULT",
        "include_dirs": ["03_VAULT"],
        "include_globs": [],
        "exclude_globs": [],
        "description": "Storage — configs, training, memory, firnflow, runtime_state",
    },
    "T4_FORGE": {
        "label": "FORGE",
        "canonical_root": "02_FORGE",
        "include_dirs": ["02_FORGE", "scripts", "bin"],
        "include_globs": [],
        "exclude_globs": [],
        "description": "Build tools — generators, scripts, protocol forge",
    },
    "T5_TESTS": {
        "label": "TESTS",
        "canonical_root": "tests",
        "include_dirs": ["tests"],
        "include_globs": ["test_*.py", "*_test.py"],
        "exclude_globs": [],
        "description": "Test suite — all pytest test files",
    },
    "T6_DOCS": {
        "label": "DOCS",
        "canonical_root": "docs",
        "include_dirs": ["docs"],
        "include_globs": ["*.md", "*.rst", "*.txt"],
        "exclude_globs": ["PROVENANCE_LEDGER.md", "AGENTS.md"],
        "description": "Documentation — plans, architecture, references",
    },
    "T7_ARCHIVE": {
        "label": "ARCHIVE",
        "canonical_root": "99_ARCHIVE",
        "include_dirs": ["99_ARCHIVE"],
        "include_globs": [],
        "exclude_globs": [],
        "description": "Legacy — deprecated code awaiting permanent removal",
    },
}

# Files/dirs that should NEVER be touched
_IMMUTABLE_PATHS = frozenset({
    "PROVENANCE_LEDGER.md",
    "AGENTS.md",
    ".git",
    ".gitignore",
    "pyproject.toml",
    "colony_report.md",
    "CAMELOT_DefenseGrid_Quarantine",
})

# Extensions treated as documentation
_DOC_EXTENSIONS = frozenset({".md", ".rst", ".txt", ".pdf"})

# Extensions treated as code
_CODE_EXTENSIONS = frozenset({".py", ".rs", ".go", ".ts", ".js", ".toml", ".json", ".yaml", ".yml"})


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class FileEntry:
    path: Path
    tier_id: str
    tier_label: str
    size_bytes: int = 0
    misplaced: bool = False
    canonical_dest: Optional[Path] = None


@dataclass
class MovePlan:
    src: Path
    dest: Path
    tier_id: str
    reason: str
    dry_run: bool = True


@dataclass
class TierResult:
    tier_id: str
    files_scanned: int
    files_misplaced: int
    moves_planned: int
    moves_executed: int
    dry_run: bool
    errors: list[str] = field(default_factory=list)
    scanned_at: float = field(default_factory=time.time)


@dataclass
class TaxonomyScanResult:
    tiers: dict[str, list[FileEntry]] = field(default_factory=dict)
    total_files: int = 0
    misplaced_files: int = 0
    uncategorized: list[Path] = field(default_factory=list)
    scanned_at: float = field(default_factory=time.time)

    @property
    def by_tier(self) -> dict[str, int]:
        return {tid: len(entries) for tid, entries in self.tiers.items()}


@dataclass
class MergeCheckResult:
    approved: bool
    risk_score: float
    risk_label: str
    risk_delta: float
    colony_critical: bool
    message: str
    checked_at: float = field(default_factory=time.time)


@dataclass
class CrossRefUpdate:
    file_path: Path
    old_import: str
    new_import: str
    applied: bool = False
    dry_run: bool = True


# ── OrganizeEngine ────────────────────────────────────────────────────────────

class OrganizeEngine:
    """Lady M semantic clustering + Lady Alexandria cross-reference updater.

    All operations default to dry_run=True. The only live operations are
    execute_tier(dry_run=False) and create_shadow_branch(), both PROMPT gate.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        dry_run: bool = True,
        hermes_enabled: bool = True,
    ) -> None:
        self._root = Path(repo_root) if repo_root else _CAMELOT_ROOT
        self._dry_run = dry_run
        self._hermes_enabled = hermes_enabled
        self._baseline_risk: float = -1.0

    # ── Tier 1: Taxonomy scan (AUTO) ─────────────────────────────────────────

    def taxonomy_scan(self, max_files: int = 50_000) -> TaxonomyScanResult:
        """Classify all repo files into 7 tiers. Read-only — AUTO gate."""
        result = TaxonomyScanResult()
        for tid in TIER_IDS:
            result.tiers[tid] = []

        count = 0
        for fpath in self._root.rglob("*"):
            if count >= max_files:
                break
            if not fpath.is_file():
                continue
            # Skip immutable
            rel = fpath.relative_to(self._root)
            if any(part in _IMMUTABLE_PATHS for part in rel.parts):
                continue
            # Skip hidden dirs
            if any(part.startswith(".") for part in rel.parts):
                continue

            tier_id = self._classify(rel)
            entry = FileEntry(
                path=fpath,
                tier_id=tier_id,
                tier_label=_TIER_PATTERNS[tier_id]["label"],
                size_bytes=self._safe_size(fpath),
                misplaced=self._is_misplaced(rel, tier_id),
            )
            if entry.misplaced:
                entry.canonical_dest = self._canonical_dest(rel, tier_id)
                result.misplaced_files += 1

            result.tiers[tier_id].append(entry)
            result.total_files += 1
            count += 1

        log.info(
            "[ORGANIZE] taxonomy_scan: %d files — %d misplaced — tiers: %s",
            result.total_files,
            result.misplaced_files,
            result.by_tier,
        )
        self._emit_hermes("organize.progress", {
            "stage": "taxonomy_scan",
            "total_files": result.total_files,
            "misplaced": result.misplaced_files,
            "by_tier": result.by_tier,
        })
        return result

    # ── Tier 2: Propose moves (AUTO, dry_run only output) ────────────────────

    def propose_moves(self, tier_id: str, dry_run: bool = True) -> list[MovePlan]:
        """Return (src, dest) move plans for misplaced files in tier. AUTO gate."""
        scan = self.taxonomy_scan()
        entries = scan.tiers.get(tier_id, [])
        plans: list[MovePlan] = []

        for entry in entries:
            if not entry.misplaced or entry.canonical_dest is None:
                continue
            plans.append(MovePlan(
                src=entry.path,
                dest=entry.canonical_dest,
                tier_id=tier_id,
                reason=f"File classified as {tier_id} but located outside canonical root",
                dry_run=dry_run,
            ))

        log.info("[ORGANIZE] propose_moves(%s): %d moves planned (dry_run=%s)", tier_id, len(plans), dry_run)
        return plans

    # ── Tier 3: Execute tier (PROMPT gate) ───────────────────────────────────

    def execute_tier(self, tier_id: str, dry_run: bool = True) -> TierResult:
        """Execute moves for one tier. PROMPT gate. dry_run=False moves files.

        Shadow branch must exist before calling with dry_run=False.
        Colony re-scan (merge_check) must pass before merging branch.
        """
        if tier_id not in _TIER_PATTERNS:
            raise ValueError(f"Unknown tier_id: {tier_id}")

        plans = self.propose_moves(tier_id, dry_run=dry_run)
        result = TierResult(
            tier_id=tier_id,
            files_scanned=0,
            files_misplaced=len(plans),
            moves_planned=len(plans),
            moves_executed=0,
            dry_run=dry_run,
        )

        for plan in plans:
            if dry_run:
                log.info("[ORGANIZE] DRY_RUN move: %s → %s", plan.src, plan.dest)
                result.moves_executed += 1
            else:
                try:
                    plan.dest.parent.mkdir(parents=True, exist_ok=True)
                    plan.src.rename(plan.dest)
                    log.info("[ORGANIZE] MOVED: %s → %s", plan.src, plan.dest)
                    result.moves_executed += 1
                except OSError as exc:
                    err = f"Move failed {plan.src}: {exc}"
                    log.error("[ORGANIZE] %s", err)
                    result.errors.append(err)

        self._emit_hermes("organize.progress", {
            "stage": "execute_tier",
            "tier_id": tier_id,
            "moves_executed": result.moves_executed,
            "dry_run": dry_run,
            "errors": len(result.errors),
        })
        return result

    # ── Colony re-scan (AUTO — mandatory before merge) ───────────────────────

    def merge_check(self) -> MergeCheckResult:
        """Colony re-scan. Returns MergeCheckResult with approved flag.

        Per Titanium Law: shadow branch + colony re-scan before merge.
        approved=True only when risk_label not CRITICAL.
        """
        try:
            import importlib.util as _ilu
            import sys
            spec = _ilu.spec_from_file_location(
                "org_colony_nexus",
                self._root / "01_KERNEL/iron_gate/DEFENSE_GRID/colony_nexus.py",
            )
            mod = _ilu.module_from_spec(spec)
            sys.modules["org_colony_nexus"] = mod
            spec.loader.exec_module(mod)
            state = mod.ColonyNexus(
                report_path=self._root / "colony_report.md",
                hermes_enabled=False,
            ).scan()

            delta = state.risk_score - self._baseline_risk if self._baseline_risk >= 0 else 0.0
            if self._baseline_risk < 0:
                self._baseline_risk = state.risk_score

            approved = not state.is_critical
            message = (
                "MERGE BLOCKED — colony risk is CRITICAL (797+ secrets detected). "
                "Rotate secrets first: camelot keys set <KEY_NAME>."
                if state.is_critical else
                f"Merge approved — colony risk {state.risk_label} ({state.risk_score:.1f}/100)"
            )
            result = MergeCheckResult(
                approved=approved,
                risk_score=state.risk_score,
                risk_label=state.risk_label,
                risk_delta=delta,
                colony_critical=state.is_critical,
                message=message,
            )
        except Exception as exc:
            log.warning("[ORGANIZE] colony re-scan failed: %s", exc)
            result = MergeCheckResult(
                approved=False,
                risk_score=-1.0,
                risk_label="UNKNOWN",
                risk_delta=0.0,
                colony_critical=True,
                message=f"Colony scan failed: {exc} — merge blocked by default",
            )

        log.info("[ORGANIZE] merge_check: approved=%s risk=%s", result.approved, result.risk_label)
        self._emit_hermes("organize.progress", {
            "stage": "merge_check",
            "approved": result.approved,
            "risk_label": result.risk_label,
            "risk_score": result.risk_score,
        })
        return result

    # ── Shadow branch (PROMPT gate) ───────────────────────────────────────────

    def create_shadow_branch(self, tier_n: int, galahad_exec: bool = True) -> str:
        """Create git shadow branch organize/tier-N. PROMPT gate.

        Uses Sir Galahad stealth_exec if galahad_exec=True.
        Returns branch name created.
        """
        branch = f"organize/tier-{tier_n}"
        try:
            if galahad_exec:
                import importlib.util as _ilu
                import sys
                spec = _ilu.spec_from_file_location(
                    "org_galahad",
                    self._root / "01_KERNEL/iron_gate/DEFENSE_GRID/knights/galahad.py",
                )
                mod = _ilu.module_from_spec(spec)
                sys.modules["org_galahad"] = mod
                spec.loader.exec_module(mod)
                g = mod.SirGalahad()
                result = g.stealth_exec(["git", "checkout", "-b", branch], cwd=str(self._root))
                if result.returncode != 0:
                    log.warning("[ORGANIZE] git branch failed: %s", result.stderr)
            else:
                import subprocess
                subprocess.run(
                    ["git", "checkout", "-b", branch],
                    cwd=str(self._root),
                    capture_output=True,
                )
            log.info("[ORGANIZE] shadow branch created: %s", branch)
        except Exception as exc:
            log.warning("[ORGANIZE] create_shadow_branch failed: %s", exc)
        return branch

    # ── Lady Alexandria: cross-reference updater ──────────────────────────────

    def update_cross_references(
        self, old_path: Path, new_path: Path, dry_run: bool = True
    ) -> list[CrossRefUpdate]:
        """Scan Python files for imports referencing old_path, propose updates.

        Lady Alexandria: fixes broken import paths after file moves.
        dry_run=True reports only; dry_run=False patches in-place.
        """
        old_module = self._path_to_module(old_path)
        new_module = self._path_to_module(new_path)
        updates: list[CrossRefUpdate] = []

        if not old_module:
            return updates

        for py_file in self._root.rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
                if old_module in text:
                    new_text = text.replace(old_module, new_module)
                    upd = CrossRefUpdate(
                        file_path=py_file,
                        old_import=old_module,
                        new_import=new_module,
                        dry_run=dry_run,
                    )
                    if not dry_run:
                        py_file.write_text(new_text, encoding="utf-8")
                        upd.applied = True
                    updates.append(upd)
            except Exception:
                pass

        log.info(
            "[ORGANIZE] update_cross_references: %d files to patch (dry_run=%s)",
            len(updates), dry_run,
        )
        return updates

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _classify(self, rel: Path) -> str:
        parts = rel.parts
        if not parts:
            return "T6_DOCS"

        root_dir = parts[0]

        if root_dir == "01_KERNEL" or root_dir.startswith("01_"):
            return "T1_KERNEL"
        if root_dir == "control_plane":
            return "T2_CONTROL"
        if root_dir in ("03_VAULT", "03_VAULT"):
            return "T3_VAULT"
        if root_dir in ("02_FORGE", "scripts", "bin"):
            return "T4_FORGE"
        if root_dir == "tests" or rel.name.startswith("test_") or rel.name.endswith("_test.py"):
            return "T5_TESTS"
        if root_dir == "docs" or rel.suffix in _DOC_EXTENSIONS:
            return "T6_DOCS"
        if root_dir == "99_ARCHIVE" or root_dir.startswith("99_"):
            return "T7_ARCHIVE"

        # Fallback: classify by extension
        if rel.suffix in _CODE_EXTENSIONS:
            return "T2_CONTROL"
        if rel.suffix in _DOC_EXTENSIONS:
            return "T6_DOCS"

        return "T6_DOCS"

    def _is_misplaced(self, rel: Path, tier_id: str) -> bool:
        """A file is misplaced if its canonical root doesn't match its actual location."""
        canonical_root = _TIER_PATTERNS[tier_id]["canonical_root"]
        if not rel.parts:
            return False
        return rel.parts[0] != canonical_root

    def _canonical_dest(self, rel: Path, tier_id: str) -> Path:
        """Compute canonical destination path for a misplaced file."""
        canonical_root = _TIER_PATTERNS[tier_id]["canonical_root"]
        # Keep relative path but move under canonical root
        return self._root / canonical_root / rel.name

    def _path_to_module(self, path: Path) -> str:
        """Convert a file path to a Python dotted module string."""
        try:
            rel = path.relative_to(self._root)
            parts = list(rel.with_suffix("").parts)
            return ".".join(parts)
        except ValueError:
            return ""

    @staticmethod
    def _safe_size(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def _emit_hermes(self, channel: str, payload: dict) -> None:
        if not self._hermes_enabled:
            return
        try:
            from control_plane.hermes_bridge import HermesBus
            HermesBus().publish(channel, {"source": "ORGANIZE_ENGINE", **payload})
        except Exception as exc:
            log.debug("[ORGANIZE] hermes emit failed: %s", exc)
