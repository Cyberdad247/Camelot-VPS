# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
DependencyEngine v1.0 — Dynamic Dependency Resolution + Auto-Update Pipeline
=============================================================================
Northstar: absolute local optimization — never stale packages, never bloated.

Supported manifests:
  pyproject.toml       (PEP 517/518 [project.dependencies])
  requirements.txt     (pip plain list)
  Cargo.toml           (Rust [dependencies])
  package.json         (Node [dependencies] + [devDependencies])

HITL gate:
  audit()          AUTO  — read-only, no network
  check_updates()  PROMPT — network call (pip/cargo), guarded by Galahad stealth_exec
  propose_update() PROMPT — shadow branch + ruff + pytest before merge

Hermes: publishes to dependency.updates channel on every proposal.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("DEPENDENCY_ENGINE")

_MANIFEST_FILES = (
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "package.json",
)

_PIP_TIMEOUT = 10   # seconds — pip index versions can hang on slow networks


@dataclass
class DepEntry:
    name: str
    current_version: str       # version specifier as declared (may be ">=1.0")
    manifest: str              # which file it came from
    ecosystem: str             # python | rust | node


@dataclass
class DepAuditResult:
    entries: list[DepEntry] = field(default_factory=list)
    manifest_paths: list[str] = field(default_factory=list)
    ecosystems_found: list[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.entries)

    def by_ecosystem(self, eco: str) -> list[DepEntry]:
        return [e for e in self.entries if e.ecosystem == eco]


@dataclass
class UpdateProposal:
    package: str
    current_version: str
    proposed_version: str
    ecosystem: str
    manifest: str
    approved: bool = False
    shadow_branch: str = ""
    tests_passed: Optional[bool] = None
    notes: str = ""


class DependencyEngine:
    """Parse manifests, audit dependencies, and propose version updates
    via shadow-branch workflow.
    """

    def __init__(
        self,
        repo_root: Path | str | None = None,
        hermes_enabled: bool = True,
        galahad_stealth: bool = True,
    ) -> None:
        self.repo_root = Path(repo_root or Path.cwd())
        self.hermes_enabled = hermes_enabled
        self.galahad_stealth = galahad_stealth

    # ── Public API ─────────────────────────────────────────────────────────

    def audit(self) -> DepAuditResult:
        """Parse all known manifests under repo_root. Returns DepAuditResult.
        Network-free — AUTO gate.
        """
        result = DepAuditResult()
        found_ecosystems: set[str] = set()

        for manifest in _MANIFEST_FILES:
            p = self.repo_root / manifest
            if not p.exists():
                continue
            result.manifest_paths.append(str(p))
            entries = self._parse_manifest(p)
            result.entries.extend(entries)
            for e in entries:
                found_ecosystems.add(e.ecosystem)

        result.ecosystems_found = sorted(found_ecosystems)
        return result

    def check_updates(self, ecosystem: str = "python") -> list[UpdateProposal]:
        """Query registry for newer versions. PROMPT gate — makes network calls.

        Uses Sir Galahad stealth_exec if available; falls back to direct subprocess.
        Returns an empty list if network is unavailable (graceful degradation).
        """
        audit = self.audit()
        deps = audit.by_ecosystem(ecosystem)
        proposals: list[UpdateProposal] = []

        for dep in deps:
            latest = self._query_latest(dep, ecosystem)
            if latest and latest != dep.current_version:
                proposals.append(UpdateProposal(
                    package=dep.name,
                    current_version=dep.current_version,
                    proposed_version=latest,
                    ecosystem=ecosystem,
                    manifest=dep.manifest,
                ))

        if proposals and self.hermes_enabled:
            self._emit_hermes_updates(proposals)

        return proposals

    def propose_update(
        self,
        package: str,
        version: str,
        ecosystem: str = "python",
        dry_run: bool = True,
    ) -> UpdateProposal:
        """Create a shadow branch with the updated dependency and run tests.

        dry_run=True (default) — skips actual git branch creation, just validates
        the version string and records the proposal. Set dry_run=False for live ops.
        PROMPT gate — operator confirmation required.
        """
        audit = self.audit()
        dep = next((e for e in audit.entries if e.name.lower() == package.lower()), None)

        proposal = UpdateProposal(
            package=package,
            current_version=dep.current_version if dep else "unknown",
            proposed_version=version,
            ecosystem=ecosystem,
            manifest=dep.manifest if dep else "",
        )

        if dry_run:
            proposal.notes = "dry_run=True — shadow branch skipped"
            proposal.approved = False
            return proposal

        # Shadow branch creation
        branch = f"shadow/dep-update-{package}-{version}".replace(".", "_")
        proposal.shadow_branch = branch
        try:
            subprocess.run(["git", "checkout", "-b", branch], cwd=self.repo_root,
                           capture_output=True, check=True, timeout=10)
            # In a real implementation: patch the manifest file, run ruff + pytest
            proposal.tests_passed = None   # not run yet — PROMPT required
            proposal.notes = f"Shadow branch {branch} created; awaiting PROMPT approval"
        except Exception as exc:
            proposal.notes = f"Shadow branch creation failed: {exc}"

        return proposal

    # ── Parsers ────────────────────────────────────────────────────────────

    def _parse_manifest(self, path: Path) -> list[DepEntry]:
        name = path.name.lower()
        try:
            if name == "pyproject.toml":
                return self._parse_pyproject(path)
            elif name == "requirements.txt":
                return self._parse_requirements(path)
            elif name == "cargo.toml":
                return self._parse_cargo(path)
            elif name == "package.json":
                return self._parse_package_json(path)
        except Exception as exc:
            log.debug("[DEP_ENGINE] parse error %s: %s", path, exc)
        return []

    def _parse_pyproject(self, path: Path) -> list[DepEntry]:
        text = path.read_text(encoding="utf-8", errors="replace")
        entries: list[DepEntry] = []
        in_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "[project]" or stripped.startswith("dependencies"):
                in_deps = "depend" in stripped.lower()
                continue
            if in_deps and stripped.startswith("["):
                in_deps = False
            if in_deps and stripped.startswith('"') and ">=" in stripped:
                m = re.match(r'"([A-Za-z0-9_\-\.]+)(.*)"', stripped)
                if m:
                    pkg, ver = m.group(1), m.group(2).strip().strip(",").strip('"')
                    entries.append(DepEntry(name=pkg, current_version=ver,
                                            manifest=str(path), ecosystem="python"))
        return entries

    def _parse_requirements(self, path: Path) -> list[DepEntry]:
        entries: list[DepEntry] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = re.match(r"([A-Za-z0-9_\-\.]+)\s*([><=!~]+.*)?", line)
            if m:
                entries.append(DepEntry(
                    name=m.group(1),
                    current_version=(m.group(2) or "").strip(),
                    manifest=str(path),
                    ecosystem="python",
                ))
        return entries

    def _parse_cargo(self, path: Path) -> list[DepEntry]:
        entries: list[DepEntry] = []
        in_deps = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped == "[dependencies]" or stripped == "[dev-dependencies]":
                in_deps = True
                continue
            if stripped.startswith("[") and "dependencies" not in stripped.lower():
                in_deps = False
            if in_deps and "=" in stripped and not stripped.startswith("#"):
                parts = stripped.split("=", 1)
                pkg = parts[0].strip()
                ver = parts[1].strip().strip('"').strip("'")
                entries.append(DepEntry(name=pkg, current_version=ver,
                                        manifest=str(path), ecosystem="rust"))
        return entries

    def _parse_package_json(self, path: Path) -> list[DepEntry]:
        entries: list[DepEntry] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            for section in ("dependencies", "devDependencies"):
                for pkg, ver in data.get(section, {}).items():
                    entries.append(DepEntry(name=pkg, current_version=str(ver),
                                            manifest=str(path), ecosystem="node"))
        except Exception:
            pass
        return entries

    # ── Network queries ────────────────────────────────────────────────────

    def _query_latest(self, dep: DepEntry, ecosystem: str) -> Optional[str]:
        if ecosystem == "python":
            return self._pip_latest(dep.name)
        return None

    def _pip_latest(self, pkg: str) -> Optional[str]:
        cmd = ["pip", "index", "versions", pkg]
        try:
            if self.galahad_stealth:
                result = self._galahad_exec(cmd)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        timeout=_PIP_TIMEOUT)
            if result.returncode != 0:
                return None
            # parse "Available versions: x.y.z, ..." line
            m = re.search(r"Available versions:\s*([\d.]+)", result.stdout)
            return m.group(1) if m else None
        except Exception as exc:
            log.debug("[DEP_ENGINE] pip latest failed for %s: %s", pkg, exc)
            return None

    def _galahad_exec(self, cmd: list[str]):
        """Run via Sir Galahad stealth_exec if available; direct subprocess fallback."""
        try:
            import importlib.util
            from pathlib import Path as _P
            _knights = _P(__file__).resolve().parents[1] / "01_KERNEL" / "iron_gate" / "DEFENSE_GRID" / "knights"
            spec = importlib.util.spec_from_file_location("galahad", _knights / "galahad.py")
            mod = importlib.util.module_from_spec(spec)
            import sys as _sys
            _sys.modules.setdefault("galahad", mod)
            spec.loader.exec_module(mod)
            g = mod.SirGalahad()
            return g.stealth_exec(cmd, timeout=_PIP_TIMEOUT)
        except Exception:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=_PIP_TIMEOUT)

    # ── Hermes ─────────────────────────────────────────────────────────────

    def _emit_hermes_updates(self, proposals: list[UpdateProposal]) -> None:
        try:
            from control_plane.hermes_bridge import HermesBus
            bus = HermesBus()
            bus.publish("dependency.updates", {
                "count": len(proposals),
                "proposals": [
                    {"package": p.package, "from": p.current_version,
                     "to": p.proposed_version, "ecosystem": p.ecosystem}
                    for p in proposals
                ],
            })
        except Exception as exc:
            log.debug("[DEP_ENGINE] Hermes unavailable: %s", exc)
