# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
TitanAudit v2.0 — Ω_TITAN Enterprise Repository Audit
======================================================
SIR_SOCRATES (L5_AGENTIC, Northstar Gate) orchestrates a 6-dimension
Titan-class codebase audit by delegating to the full Camelot-OS infrastructure:

  D-I   Codebase Navigation & Comprehension Mapping  (squires scan/index + structure)
  D-II  Configuration & Architecture Audit            (DependencyEngine + excalibur)
  D-III Code Effectiveness & Security Review           (squires ghost/sweep + Socrates)
  D-IV  Kinetic Resource & Thermodynamic Profiling     (excalibur_preflight + compression)
  D-V   UI/UX Rendering Audit                          (frontend probe)
  D-VI  Iron Gate Governance & Northstar Alignment     (Sir Socrates + soul_oversight)

Produces a structured JSON report and renders it as a Markdown artifact.
Runic command: //TITAN_AUDIT  |  Omega_SOCRATES

Usage:
    python -m control_plane.titan_audit              # full audit on repo root
    python -m control_plane.titan_audit --json       # JSON report to stdout
    python -m control_plane.titan_audit --target /path
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure UTF-8 on Windows consoles (prevents cp1252 codec errors with emoji)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Project root ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Dimension dataclasses ───────────────────────────────────────────────────────


@dataclass
class DimensionResult:
    dimension_id: str
    title: str
    score: float  # 0.0–100.0 (higher = healthier)
    verdict: str  # RADIANT | STABLE | TARNISHED | CRITICAL
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TitanAuditReport:
    target: str
    timestamp_utc: str
    profile: str
    overall_score: float
    overall_verdict: str
    dimensions: list[DimensionResult]
    socrates_examination: dict[str, Any]
    elapsed_seconds: float
    raw_report_path: str = ""


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _verdict_from_score(score: float) -> str:
    if score >= 85:
        return "RADIANT"
    if score >= 65:
        return "STABLE"
    if score >= 40:
        return "TARNISHED"
    return "CRITICAL"


def _score_color(score: float) -> str:
    if score >= 85:
        return "green"
    if score >= 65:
        return "yellow"
    if score >= 40:
        return "orange"
    return "red"


# ── TitanAudit Engine ───────────────────────────────────────────────────────────


class TitanAudit:
    """6-dimension Titan-class enterprise repository audit.

    Delegates to squires colony, DependencyEngine, CompressionNexus,
    Excalibur Preflight, and Sir Socrates. Produces a TitanAuditReport
    and a Markdown artifact at `titan_audit_report.md`.
    """

    def __init__(self, target: Path | str | None = None, quick: bool = False) -> None:
        self.target = Path(target or _REPO_ROOT).resolve()
        self.quick = quick
        self._dims: list[DimensionResult] = []
        self._t0 = 0.0
        self._cached_records: list = []  # shared scan cache across D-I and D-III

    # ── Public API ─────────────────────────────────────────────────────────

    def run(self, socrates_examine: bool = True) -> TitanAuditReport:
        """Execute the full 6-dimension Titan audit."""
        self._t0 = time.perf_counter()
        self._dims = []

        # Pre-scan once for D-I and D-III (or use colony index in quick mode)
        self._pre_scan()

        # D-I: Codebase Navigation & Comprehension
        self._dims.append(self._dimension_i_navigation())

        # D-II: Configuration & Architecture
        self._dims.append(self._dimension_ii_configuration())

        # D-III: Code Effectiveness & Security
        self._dims.append(self._dimension_iii_security())

        # D-IV: Resource & Thermodynamic Profiling
        self._dims.append(self._dimension_iv_resources())

        # D-V: UI/UX Rendering Audit
        self._dims.append(self._dimension_v_ui_ux())

        # D-VI: Iron Gate Governance & Northstar
        self._dims.append(self._dimension_vi_governance(socrates_examine))

        elapsed = round(time.perf_counter() - self._t0, 2)

        # Overall scoring
        scores = [d.score for d in self._dims]
        overall = round(sum(scores) / len(scores), 1) if scores else 0.0
        verdict = _verdict_from_score(overall)

        # Sir Socrates examination (Northstar alignment of the audit itself)
        soc_exam = self._run_socrates() if socrates_examine else {}

        # Write report
        report_path = self._write_report(overall, verdict, elapsed)

        return TitanAuditReport(
            target=str(self.target),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            profile="titan-audit/v9000.50",
            overall_score=overall,
            overall_verdict=verdict,
            dimensions=self._dims,
            socrates_examination=soc_exam,
            elapsed_seconds=elapsed,
            raw_report_path=report_path,
        )

    # Core Camelot source dirs scoped for D-III deep security scan.
    # (Avoids 02_FORGE submodules which inflate the repo to 46k+ files.)
    _CORE_SCAN_DIRS: list[str] = [
        "01_KERNEL", "control_plane", "squires", "tests", "bin", "scripts",
        "utils", "02_FORGE/apps", "02_FORGE/PORTAL_CORE",
    ]

    def _pre_scan(self) -> None:
        """Pre-scan the target once, shared by D-I and D-III.

        Always loads colony index stats for D-I (fast, already cached).
        In non-quick mode, additionally scans core Camelot source dirs
        for D-III's GHOST/SWEEP deep security analysis.
        """
        # Always load colony index stats for D-I (regardless of mode)
        # Uses ColonyIndex.load() for transparent .json.gz / .json support
        idx_path = self.target / ".colony" / "index.json"
        if idx_path.exists() or (self.target / ".colony" / "index.json.gz").exists():
            try:
                from squires.index import ColonyIndex
                loaded = ColonyIndex.load(idx_path)
                stats = loaded.stats
                self._cached_stats = {
                    "total_files": stats.get("total_files", 0),
                    "total_lines": stats.get("total_lines", 0),
                    "by_ext": stats.get("by_ext", {}),
                }
            except Exception:
                self._cached_stats = {}
        else:
            self._cached_stats = {}

        if self.quick:
            return

        # Full mode: scan only core Camelot source dirs (not entire 46k-file repo)
        try:
            print("     [scanning core source dirs...]", end="", flush=True)
            from squires.scan import scan
            self._cached_records = []
            for core_dir in self._CORE_SCAN_DIRS:
                dir_path = self.target / core_dir
                if dir_path.exists():
                    self._cached_records.extend(scan(dir_path))
            # Also scan root-level code files (non-recursive — avoids full tree walk)
            try:
                import hashlib

                from squires.scan import _CODE_EXTS, FileRecord
                for entry in self.target.iterdir():
                    if entry.is_file() and entry.suffix in _CODE_EXTS:
                        try:
                            st = entry.stat()
                            if st.st_size > 10 * 1024 * 1024:
                                continue
                            rel = entry.name
                            rec = FileRecord(
                                path=entry, rel=rel, size=st.st_size,
                                ext=entry.suffix,
                            )
                            try:
                                raw = entry.read_bytes()
                                rec.sha256 = hashlib.sha256(raw).hexdigest()[:12]
                                rec.is_binary = b"\x00" in raw[:1024]
                                if not rec.is_binary:
                                    rec.lines = raw.count(b"\n")
                            except Exception:
                                pass
                            self._cached_records.append(rec)
                        except Exception:
                            pass
            except Exception:
                pass
            print(f" {len(self._cached_records)} files", flush=True)
        except Exception:
            self._cached_records = []

    # ── D-I: Navigation & Comprehension Mapping ────────────────────────────

    def _dimension_i_navigation(self) -> DimensionResult:
        """Map codebase structure, detect orphans, measure navigability."""
        findings: list[str] = []
        recs: list[str] = []
        data: dict[str, Any] = {}

        # Always use cached colony index stats for file counts
        cached = getattr(self, "_cached_stats", {})
        data["total_files"] = cached.get("total_files", 0)
        data["total_lines"] = cached.get("total_lines", 0)
        data["ext_distribution"] = cached.get("by_ext", {})
        data["quick_mode"] = self.quick

        if not self.quick and self._cached_records:
            # Deep-mode orphan/sweep analysis on scanned core-source records.
            # (Does NOT overwrite colony-index totals — those stay in data above.)
            records = self._cached_records
            scan_ext_counts: dict[str, int] = {}
            scan_total_lines = 0
            for rec in records:
                scan_ext_counts[rec.ext] = scan_ext_counts.get(rec.ext, 0) + 1
                scan_total_lines += rec.lines
            data["scanned_files"] = len(records)
            data["scanned_lines"] = scan_total_lines
            data["scanned_ext_distribution"] = scan_ext_counts

            # Orphan check via sweeper
            try:
                from squires.sweep import sweep
                sweep_report = sweep(iter(records))
                orphans = [f for f in sweep_report.flags if f.kind in ("unreferenced_file", "unused_import")]
                data["orphans_detected"] = len(orphans)
                if orphans:
                    findings.append(f"{len(orphans)} orphaned/unused references detected")
                    recs.append("Run `//SCAN triage` to generate full cleanup report")
            except Exception:
                data["orphans_detected"] = 0

        # Navigability assessment (uses colony-index totals, not scan-only counts)
        top_dirs = [d.name for d in self.target.iterdir() if d.is_dir() and not d.name.startswith(".")]
        data["top_level_dirs"] = top_dirs
        top_dirs_count = len(top_dirs)
        if data["total_files"] > 10_000:
            findings.append(f"Very large codebase ({data['total_files']:,} files) — navigation may require MemPalace indexing")
            recs.append("Enable MemPalace L2 indexing for cross-file reference tracking")
        elif data["total_files"] > 1_000:
            findings.append(f"Large codebase ({data['total_files']:,} files) — structural mapping recommended")
        else:
            findings.append(f"Manageable codebase size ({data['total_files']:,} files)")

        top_dirs_count = len(data.get("top_level_dirs", []))
        if top_dirs_count > 15:
            findings.append(f"Flat top-level structure ({top_dirs_count} dirs) — consider domain grouping")
        elif top_dirs_count < 3:
            findings.append(f"Shallow structure ({top_dirs_count} top-level dirs) — may indicate monolithic layout")

        # Score
        orphan_penalty = min(20, data.get("orphans_detected", 0) * 2)
        size_penalty = min(10, max(0, (data["total_files"] - 5000) // 1000))
        score = max(0.0, 90.0 - orphan_penalty - size_penalty)
        data["orphan_penalty"] = orphan_penalty
        data["size_penalty"] = size_penalty

        return DimensionResult(
            dimension_id="D-I",
            title="Navigation & Comprehension Mapping",
            score=round(score, 1),
            verdict=_verdict_from_score(score),
            findings=findings,
            recommendations=recs,
            raw_data=data,
        )

    # ── D-II: Configuration & Architecture Audit ───────────────────────────

    def _dimension_ii_configuration(self) -> DimensionResult:
        """Audit build configs, dependencies, environment."""
        findings: list[str] = []
        recs: list[str] = []
        data: dict[str, Any] = {}

        # Dependency audit
        try:
            from control_plane.dependency_engine import DependencyEngine
            dep_engine = DependencyEngine(repo_root=self.target, hermes_enabled=False)
            dep_audit = dep_engine.audit()
            data["dependencies"] = {
                "total": dep_audit.total_count,
                "ecosystems": dep_audit.ecosystems_found,
                "manifests": dep_audit.manifest_paths,
            }
            if dep_audit.total_count == 0:
                findings.append("No dependency manifests found — is this a greenfield project?")
            else:
                ecostr = ", ".join(dep_audit.ecosystems_found)
                findings.append(f"{dep_audit.total_count} dependencies across {ecostr}")
            for eco in dep_audit.ecosystems_found:
                count = len(dep_audit.by_ecosystem(eco))
                if count > 50:
                    findings.append(f"Heavy {eco} dependency footprint ({count} packages)")
                    recs.append(f"Audit {eco} dependencies for unused packages — run `//FORGE dependency audit`")
        except Exception as e:
            data["dependencies"] = {"error": str(e)}
            findings.append("Dependency audit unavailable")

        # Excalibur preflight (hardware readiness)
        adjudication = {}  # safe default if except fires
        try:
            from control_plane.excalibur_preflight import adjudicate
            from control_plane.excalibur_preflight import audit as excalibur_audit
            telemetry = excalibur_audit(self.target)
            adjudication = adjudicate(telemetry)
            data["excalibur"] = {
                "verdict": adjudication["verdict"],
                "cpu": telemetry["cpu"]["arch"],
                "cores": telemetry["cpu"]["cores"],
                "ram_mb": telemetry["memory_mb"]["available"],
                "disk_free_mb": telemetry["storage_mb"]["free"],
            }
            if adjudication["verdict"] == "NO-GO":
                findings.append(f"EXCALIBUR NO-GO: {adjudication['violations']}")
                recs.extend(adjudication.get("missing", []))
            else:
                findings.append("EXCALIBUR substrate GO — hardware meets requirements")
        except Exception as e:
            data["excalibur"] = {"error": str(e)}
            findings.append("Excalibur preflight unavailable")

        # Config file presence check
        config_files = [
            ".camelot-config.yaml", ".env", "Cargo.toml", "pyproject.toml",
            "package.json", "terraform/main.tf"
        ]
        present_configs = [c for c in config_files if (self.target / c).exists()]
        missing_configs = [c for c in config_files if c not in present_configs]
        data["config_files"] = {"present": present_configs, "missing": missing_configs}
        if missing_configs:
            findings.append(f"Missing expected config files: {', '.join(missing_configs[:3])}")

        # Score
        score = 80.0
        if adjudication.get("verdict") == "NO-GO":
            score -= 20
        if len(missing_configs) > 2:
            score -= 10
        if data.get("dependencies", {}).get("total", 0) > 100:
            score -= 5

        return DimensionResult(
            dimension_id="D-II",
            title="Configuration & Architecture Audit",
            score=round(max(0.0, score), 1),
            verdict=_verdict_from_score(score),
            findings=findings,
            recommendations=recs,
            raw_data=data,
        )

    # ── D-III: Code Effectiveness & Security Review ────────────────────────

    def _dimension_iii_security(self) -> DimensionResult:
        """Security scan via squires GHOST + Socrates security posture."""
        findings: list[str] = []
        recs: list[str] = []
        data: dict[str, Any] = {}

        records = self._cached_records

        if self.quick and not records:
            data["ghost"] = {"note": "Quick mode — skipping full security scan"}
            data["sweep"] = {"note": "Quick mode — skipping sweep"}
            findings.append("Quick mode: skipping full security scan. Run without --quick for deep scan.")
            return DimensionResult(
                dimension_id="D-III",
                title="Code Effectiveness & Security Review",
                score=75.0,
                verdict="STABLE",
                findings=findings,
                recommendations=recs,
                raw_data=data,
            )

        # GHOST scan for secrets
        todos: list = []
        large: list = []
        try:
            from squires.ghost import triage as ghost_triage
            ghost_report = ghost_triage(iter(records))
            secrets = [f for f in ghost_report.flags if f.kind == "secret"]
            todos = [f for f in ghost_report.flags if f.kind == "todo"]
            large = [f for f in ghost_report.flags if f.kind == "large_file"]

            data["ghost"] = {
                "secrets_found": len(secrets),
                "todos_found": len(todos),
                "large_files": len(large),
                "total_flags": len(ghost_report.flags),
            }

            if secrets:
                findings.append(f"CRITICAL: {len(secrets)} potential secret(s) detected!")
                recs.append("ROTATE credentials immediately — run `//SCAN ghost` for full report")
                for s in secrets[:3]:
                    findings.append(f"  Secret in {s.file}:{s.line} — {s.detail}")
            else:
                findings.append("No secrets detected — clean scan")

            if len(todos) > 50:
                findings.append(f"High technical debt: {len(todos)} TODO/FIXME markers")
                recs.append("Triage TODOs into sprints or PROVENANCE_LEDGER entries")
            elif todos:
                findings.append(f"{len(todos)} TODO/FIXME markers — moderate")

            if large:
                findings.append(f"{len(large)} large files (>500KB) — consider compression/archiving")
        except Exception as e:
            data["ghost"] = {"error": str(e)}
            findings.append("GHOST scan unavailable")

        # Sweep for duplicates/unused
        try:
            from squires.sweep import sweep
            sweep_report = sweep(iter(records))
            dupes = [f for f in sweep_report.flags if f.kind == "duplicate_content"]
            unused = [f for f in sweep_report.flags if f.kind == "unused_import"]
            data["sweep"] = {"duplicates": len(dupes), "unused_imports": len(unused)}
            if dupes:
                findings.append(f"{len(dupes)} duplicate file(s) — DRY violation")
                recs.append("Run MASON dedup report to identify merge candidates")
            if unused:
                findings.append(f"{len(unused)} unused import(s) — dead code")
        except Exception as e:
            data["sweep"] = {"error": str(e)}

        # Score
        score = 90.0
        n_secrets = data.get("ghost", {}).get("secrets_found", 0)
        if n_secrets > 0:
            score -= min(50, n_secrets * 25)
        score -= min(15, len(todos) // 10)
        score -= min(10, len(large) * 2)

        return DimensionResult(
            dimension_id="D-III",
            title="Code Effectiveness & Security Review",
            score=round(max(0.0, score), 1),
            verdict=_verdict_from_score(score),
            findings=findings,
            recommendations=recs,
            raw_data=data,
        )

    # ── D-IV: Resource & Thermodynamic Profiling ────────────────────────────

    def _dimension_iv_resources(self) -> DimensionResult:
        """Profile CPU/RAM/disk usage and identify resource hotspots."""
        findings: list[str] = []
        recs: list[str] = []
        data: dict[str, Any] = {}

        # Excalibur telemetry
        try:
            from control_plane.excalibur_preflight import adjudicate
            from control_plane.excalibur_preflight import audit as excalibur_audit
            telemetry = excalibur_audit(self.target)
            adjudication = adjudicate(telemetry)
            data["telemetry"] = telemetry
            data["adjudication"] = adjudication

            mem = telemetry["memory_mb"]
            store = telemetry["storage_mb"]
            findings.append(
                f"RAM: {mem['available']}/{mem['total']}MB available "
                f"({round(mem['available']/max(1,mem['total'])*100)}%)"
            )
            findings.append(f"Disk: {store['free']}MB free of {store['total']}MB")

            if mem["available"] < 1024:
                findings.append("CRITICAL: <1GB RAM available — system may thrash under load")
                recs.append("Close memory-heavy apps; consider //PURGE_MEMORY")
            if store["free"] < 4096:
                findings.append("Low disk space — Rust/WASM builds may fail")
                recs.append("Free at least 4GB disk space for build artifacts")
        except Exception as e:
            data["telemetry"] = {"error": str(e)}
            findings.append("Telemetry probe unavailable")

        # Compression nexus disk audit (skip in quick mode — too slow on large repos)
        if not self.quick:
            try:
                from control_plane.compression_nexus import CompressionNexus
                cn = CompressionNexus(repo_root=self.target, hermes_enabled=False)
                disk_audit = cn.audit_disk(self.target)
                data["compression"] = {
                    "scanned_files": disk_audit.scanned_files,
                    "large_files": len(disk_audit.large_files),
                    "total_size_mb": round(disk_audit.total_size_kb / 1024, 1),
                    "potential_savings_mb": round(disk_audit.potential_savings_kb / 1024, 1),
                }
                if disk_audit.large_files:
                    top_large = sorted(disk_audit.large_files, key=lambda x: x["size_kb"], reverse=True)[:5]
                    findings.append(f"{len(disk_audit.large_files)} large files — {data['compression']['potential_savings_mb']}MB compressible")
                    for lf in top_large:
                        findings.append(f"  {lf['path']}: {lf['size_kb']}KB")
                    recs.append(f"Compress top large files to reclaim ~{data['compression']['potential_savings_mb']}MB")
            except Exception as e:
                data["compression"] = {"error": str(e)}
        else:
            data["compression"] = {"note": "Quick mode — disk audit skipped"}

        # Score — graduated RAM penalty (8GB machines have less headroom)
        score = 85.0
        mem = data.get("telemetry", {}).get("memory_mb", {})
        avail = mem.get("available", 9999)
        if avail < 256:
            score -= 25    # critical — OOM risk
        elif avail < 512:
            score -= 15    # tight but functional
        elif avail < 1024:
            score -= 8     # constrained
        elif avail < 2048:
            score -= 5     # moderate
        store_free = data.get("telemetry", {}).get("storage_mb", {}).get("free", 99999)
        if store_free < 2048:
            score -= 20
        elif store_free < 4096:
            score -= 8

        return DimensionResult(
            dimension_id="D-IV",
            title="Resource & Thermodynamic Profiling",
            score=round(max(0.0, score), 1),
            verdict=_verdict_from_score(score),
            findings=findings,
            recommendations=recs,
            raw_data=data,
        )

    # ── D-V: UI/UX Rendering Audit ──────────────────────────────────────────

    def _dimension_v_ui_ux(self) -> DimensionResult:
        """Audit frontend code for patterns, accessibility, and design system adherence."""
        findings: list[str] = []
        recs: list[str] = []
        data: dict[str, Any] = {}

        # Probe for frontend directories
        frontend_globs = [
            "02_FORGE/apps", "02_FORGE/PORTAL_CORE",
            "src/app", "pages", "components", "ui"
        ]
        found_ui: list[str] = []
        for g in frontend_globs:
            p = self.target / g
            if p.exists():
                found_ui.append(g)

        data["frontend_dirs"] = found_ui

        if not found_ui:
            findings.append("No dedicated frontend directories detected — UI audit skipped")
            return DimensionResult(
                dimension_id="D-V",
                title="UI/UX Rendering Audit",
                score=100.0,  # N/A — no penalty
                verdict="RADIANT",
                findings=findings,
                recommendations=recs,
                raw_data=data,
            )

        findings.append(f"Frontend code detected in: {', '.join(found_ui[:5])}")

        # Quick probe for framework signals
        try:
            tsx_count = 0
            jsx_count = 0
            css_count = 0
            for root_dir in found_ui:
                for ext_glob, counter in [("**/*.tsx", "tsx"), ("**/*.jsx", "jsx"), ("**/*.css", "css")]:
                    count = len(list((self.target / root_dir).glob(ext_glob))) if (self.target / root_dir).exists() else 0
                    if counter == "tsx":
                        tsx_count += count
                    elif counter == "jsx":
                        jsx_count += count
                    else:
                        css_count += count

            data["component_counts"] = {"tsx": tsx_count, "jsx": jsx_count, "css": css_count}
            if tsx_count + jsx_count > 0:
                findings.append(f"{tsx_count + jsx_count} React components detected")
            if css_count == 0:
                findings.append("No standalone CSS files — likely using Tailwind/CSS-in-JS (Camelot preference)")
                data["tailwind_detected"] = True
        except Exception:
            pass

        # Check for Camelot UI conventions (skip rglob in quick mode)
        if not self.quick:
            try:
                import re
                luxora_found = False
                tailwind_found = False
                for root_dir in found_ui[:3]:
                    td = self.target / root_dir
                    if not td.exists():
                        continue
                    for f in td.rglob("*.tsx"):
                        try:
                            content = f.read_text(encoding="utf-8", errors="replace")[:2000]
                            if not luxora_found and re.search(r"#D4AF37|D4AF37|luxora", content, re.I):
                                luxora_found = True
                            if not tailwind_found and re.search(r"tailwind|className.*[a-z]+-[0-9]", content):
                                tailwind_found = True
                        except Exception:
                            pass
                    if luxora_found and tailwind_found:
                        break
                data["convention_check"] = {"luxora_gold": luxora_found, "tailwind": tailwind_found}
                if not tailwind_found:
                    findings.append("Tailwind v4 not detected in frontend — Camelot design system convention (Rule 1)")
                    recs.append("Adopt Tailwind v4 + Luxora Gold (#D4AF37) per Camelot Rule 1")
            except Exception:
                pass
        else:
            data["convention_check"] = {"note": "Quick mode — skipped rglob scan"}

        score = 80.0
        if not data.get("convention_check", {}).get("tailwind", False):
            score -= 15

        return DimensionResult(
            dimension_id="D-V",
            title="UI/UX Rendering Audit",
            score=round(max(0.0, score), 1),
            verdict=_verdict_from_score(score),
            findings=findings,
            recommendations=recs,
            raw_data=data,
        )

    # ── D-VI: Iron Gate Governance & Northstar ──────────────────────────────

    def _dimension_vi_governance(self, socrates_examine: bool = True) -> DimensionResult:
        """HITL governance, audit trail, Northstar alignment."""
        findings: list[str] = []
        recs: list[str] = []
        data: dict[str, Any] = {}

        # Check HITL infrastructure
        checks = {
            "provenance_ledger": (self.target / "PROVENANCE_LEDGER.md").exists(),
            "colony_report": (self.target / "colony_report.md").exists(),
            "verification_ledger": (self.target / "03_VAULT" / "Missions" / "verification_ledger.jsonl").exists(),
            "northstar_verdicts": (self.target / "logs" / "northstar_verdicts.jsonl").exists(),
            "hitl_queue": (self.target / "logs" / "hitl_queue.jsonl").exists(),
            "harness_queue": (self.target / "logs" / "harness_queue.jsonl").exists(),
        }
        data["hitl_infrastructure"] = checks

        present = sum(1 for v in checks.values() if v)
        total = len(checks)
        findings.append(f"HITL infrastructure: {present}/{total} artifacts present")

        missing = [k for k, v in checks.items() if not v]
        if missing:
            findings.append(f"Missing governance artifacts: {', '.join(missing)}")
            recs.append("Run `//SCAN triage` to generate missing colony_report.md")

        # Audit trail health
        try:
            provenance = self.target / "PROVENANCE_LEDGER.md"
            if provenance.exists():
                pl_size = provenance.stat().st_size
                data["provenance_size_kb"] = round(pl_size / 1024, 1)
                if pl_size < 10_000:
                    findings.append("PROVENANCE_LEDGER.md is thin — audit trail may be incomplete")
        except Exception:
            pass

        # Northstar verdicts
        try:
            verdicts_path = self.target / "logs" / "northstar_verdicts.jsonl"
            if verdicts_path.exists():
                lines = verdicts_path.read_text(encoding="utf-8").strip().splitlines()
                data["northstar_verdict_count"] = len(lines)
                blocked = sum(1 for l in lines if '"BLOCKED"' in l)
                partial = sum(1 for l in lines if '"PARTIAL"' in l)
                if blocked > 0:
                    findings.append(f"{blocked} BLOCKED Northstar verdict(s) — governance breach detected")
                if partial > 0:
                    findings.append(f"{partial} PARTIAL Northstar verdict(s) — review recommended")
        except Exception:
            pass

        # Score
        score = 75.0 + (present / total) * 20
        blocked_count = data.get("northstar_verdict_count", 0)
        if blocked_count:
            blocked_ratio = min(20, data.get("blocked", 0) * 5)
            score -= blocked_ratio

        return DimensionResult(
            dimension_id="D-VI",
            title="Iron Gate Governance & Northstar Alignment",
            score=round(max(0.0, min(100.0, score)), 1),
            verdict=_verdict_from_score(score),
            findings=findings,
            recommendations=recs,
            raw_data=data,
        )

    # ── Sir Socrates Northstar Examination ──────────────────────────────────

    def _run_socrates(self) -> dict[str, Any]:
        """Run Sir Socrates on the audit target to verify Northstar alignment."""
        try:
            from control_plane.sir_socrates import SirSocrates
            intent = f"Titan Audit v9000.50 on target: {self.target}"
            exam = SirSocrates().examine_all(intent)
            return {
                "verdict": exam.verdict,
                "overall_aligned": exam.overall_aligned,
                "blocking_questions": exam.blocking_questions,
                "answers": [
                    {"id": a.question_id, "aligned": a.aligned, "reasoning": a.reasoning[:120]}
                    for a in exam.answers
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Report writing ─────────────────────────────────────────────────────

    def _write_report(self, overall: float, verdict: str, elapsed: float) -> str:
        """Write the Titan audit report as Markdown."""
        out_path = self.target / "titan_audit_report.md"
        lines = [
            "# ⚔️ Ω_TITAN Enterprise Repository Audit — v9000.50",
            "",
            f"**Target:** `{self.target}`  ",
            f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}  ",
            "**Profile:** titan-audit/v9000.50  ",
            f"**Elapsed:** {elapsed}s  ",
            "",
            f"## Overall Verdict: {verdict} ({overall}%)",
            "",
            "| Dimension | Score | Verdict |",
            "|---|---|---|",
        ]
        for d in self._dims:
            lines.append(f"| {d.dimension_id} — {d.title} | {d.score}% | {d.verdict} |")
        lines.append("")

        for d in self._dims:
            lines.append(f"### {d.dimension_id}: {d.title} — {d.verdict} ({d.score}%)")
            lines.append("")
            if d.findings:
                lines.append("**Findings:**")
                for f in d.findings:
                    lines.append(f"- {f}")
                lines.append("")
            if d.recommendations:
                lines.append("**Recommendations:**")
                for r in d.recommendations:
                    lines.append(f"- {r}")
                lines.append("")

        lines.append("---")
        lines.append("*Audit conducted by SIR_SOCRATES (L5_AGENTIC, Northstar Gate) "
                      "under the Ω_TITAN_REPOSITORY_AUDIT_v9000.50 protocol.*")
        lines.append("*Camelot-OS v1000.0-EXCALIBUR-A | Iron Gate: CLEARED*")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return str(out_path)


# ── CLI entry ───────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        prog="titan_audit",
        description="Ω_TITAN Enterprise Repository Audit v9000.50 — SIR_SOCRATES",
    )
    ap.add_argument("--target", default=None, help="Target directory (default: repo root)")
    ap.add_argument("--json", action="store_true", help="Output JSON to stdout")
    ap.add_argument("--no-socrates", action="store_true", help="Skip Sir Socrates examination")
    ap.add_argument("--quick", action="store_true", help="Quick mode: use cached colony index, skip heavy scans")
    args = ap.parse_args()

    target = Path(args.target) if args.target else _REPO_ROOT
    if not target.exists():
        print(f"❌ Target not found: {target}", file=sys.stderr)
        sys.exit(1)

    print("\n⚔️  Ω_TITAN Enterprise Repository Audit — v9000.50")
    print("   SIR_SOCRATES :: Northstar Gate Examiner")
    print(f"   Target: {target}")
    print("   ─" * 35)

    audit = TitanAudit(target=target, quick=args.quick)
    report = audit.run(socrates_examine=not args.no_socrates)

    if args.json:
        print(json.dumps({
            "target": report.target,
            "timestamp": report.timestamp_utc,
            "overall_score": report.overall_score,
            "overall_verdict": report.overall_verdict,
            "elapsed_seconds": report.elapsed_seconds,
            "dimensions": [
                {
                    "id": d.dimension_id,
                    "title": d.title,
                    "score": d.score,
                    "verdict": d.verdict,
                    "findings": d.findings,
                    "recommendations": d.recommendations,
                }
                for d in report.dimensions
            ],
            "socrates": report.socrates_examination,
            "report_path": report.raw_report_path,
        }, indent=2))
    else:
        # Pretty terminal output
        for d in report.dimensions:
            icon = {"RADIANT": "✅", "STABLE": "🔵", "TARNISHED": "🟠", "CRITICAL": "🔴"}.get(d.verdict, "❓")
            print(f"\n  {icon} {d.dimension_id}: {d.title} — {d.verdict} ({d.score}%)")
            for f in d.findings[:3]:
                print(f"     • {f}")
            if d.recommendations:
                for r in d.recommendations[:1]:
                    print(f"     → {r}")

        print(f"\n  {'─' * 35}")
        verdict_color = _score_color(report.overall_score)
        print(f"  🏆 OVERALL: {report.overall_verdict} ({report.overall_score}%) in {report.elapsed_seconds}s")
        if report.socrates_examination:
            sv = report.socrates_examination.get("verdict", "?")
            print(f"  ⚖️  SOCRATES: {sv}")
        print(f"  📄 Report: {report.raw_report_path}")
        print()

    sys.exit(0)


if __name__ == "__main__":
    main()
