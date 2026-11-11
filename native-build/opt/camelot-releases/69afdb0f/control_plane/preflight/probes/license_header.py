# SPDX-License-Identifier: MIT

"""FOSS license marker probe — flags files without a recognized SPDX header.

Per VFS_PREFLIGHT_DESIGN.md §4 `foss_validation_constraints` (sequence 020).
Surfaced via probes.license_header_run.py in Task 6.

Submodule / nested-repo boundaries are detected two ways:
  1. A `.git` entry inside a child directory (initialized gitlink marker
     or a full nested clone), and
  2. The git index itself (`git ls-files -s`, mode 160000) — required
     because this repo carries 29 *unmapped* gitlinks whose worktrees
     were checked out without a `.git` marker.
Each repository owns its own licensing; foreign trees are never scanned.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess

SPDX_PATTERNS = [
    re.compile(r"\bSPDX-License-Identifier:\s*([A-Za-z0-9\-\.\+]+)"),
    re.compile(r"Copyright\s+\(c\)\s+\d{4}"),
]
SKIP_EXTS = {
    ".md", ".txt", ".json", ".lock", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".gitignore", ".gitattributes",
    ".exe", ".dll", ".pyd", ".so", ".dylib", ".bin", ".dat",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".ttf", ".pyc", ".pkl", ".db", ".sqlite", ".sqlite3", ".pdf",
    ".zip", ".gz", ".tar", ".7z", ".whl", ".icns", ".cur",
    ".nkg",   # Camelot knowledge-graph data — no comment convention
    ".jsonl", # line-delimited JSON data — a header line would corrupt it
    ".mod",   # Go module manifests (dependency graphs, like package-lock)
    ".sum",   # Go checksum manifests
    ".jsonld", ".toon",   # JSON-LD / Camelot data artifacts
    ".conf", ".hujson",   # config data
    ".tpl",                 # source templates (rendered elsewhere)
    ".crusade", ".mlo", ".mermaid",  # workflow/diagram/data docs
    ".bak", ".old",        # archives
    ".zon", ".nix", ".typed", ".tsbuildinfo",  # build/type metadata & package manifests
}
# Dotfiles/config files have no extension in Path.suffix — match by name.
SKIP_NAMES = {
    ".gitignore", ".gitattributes", ".gitkeep", ".python-version",
    ".npmrc", ".prettierignore", ".dockerignore", ".editorconfig",
    ".eslintrc", ".eslintignore", ".flake8", ".pylintrc", ".hgignore",
    "LICENSE", "LICENSE.md", "COPYING", "NOTICE",
    ".gitmodules",
    "00-RELEASENOTES", ".workspace-root", "VERSION",
}
# Directories that are never authored FOSS code: VCS metadata,
# vendored/submodule trees, generated output, and build artifacts.
SKIP_DIRS = {
    "node_modules", "dist", "build", "target",
    "__pycache__", ".venv", ".pytest_cache", ".turbo", ".next",
    "generated", "vendor", "third_party", ".cargo", ".ruff_cache",
}
# Safety valve: stop collecting after this many flags.
MAX_FLAGGED = 5000


def _looks_binary(head: bytes) -> bool:
    """NUL-byte sniff on the first 4 KiB — binary files must never be
    'licensed' by prepending text (would corrupt them)."""
    return b"\x00" in head


def _repo_root(roots: list[Path]) -> Path | None:
    """Walk up from the first existing scan root to the git worktree root."""
    for root in roots:
        cur = root.resolve()
        for _ in range(10):
            if (cur / ".git").exists():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
    return None


def _gitlink_dirs(repo_root: Path | None) -> set[str]:
    """Repo-relative posix paths of gitlinks (git index mode 160000)."""
    if repo_root is None:
        return set()
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-s"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except Exception:  # noqa: BLE001 — git absent: fall back to .git-marker only
        return set()
    links: set[str] = set()
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "160000":
            links.add(parts[3].replace("\\", "/"))
    return links


def scan(roots: list[Path]) -> list[Path]:
    """Return source files (non-skipped ext) missing a recognized marker.

    Empty list means OK. Skipped extensions include documentation,
    config, lock, and binary files; skipped dirs include vendored,
    generated, build, and gitlink/submodule trees (each repo licenses
    itself). Collection stops at MAX_FLAGGED so a pathological tree
    cannot hang the boot gate.
    """
    flagged: list[Path] = []
    repo_root = _repo_root(roots)
    gitlinks = _gitlink_dirs(repo_root)
    for root in roots:
        if not root.exists():
            continue
        root = root.resolve()  # absolute so relative_to(repo_root) works
        for dirpath, dirnames, filenames in os.walk(root):
            keep: list[str] = []
            for d in dirnames:
                if d in SKIP_DIRS:
                    continue
                if (Path(dirpath) / d / ".git").exists():
                    continue  # initialized gitlink / nested repo boundary
                if gitlinks and repo_root is not None:
                    try:
                        rel = Path(dirpath).relative_to(repo_root).as_posix()
                    except ValueError:
                        rel = ""
                    child = f"{rel}/{d}" if rel and rel != "." else d
                    if child in gitlinks:
                        continue  # unmapped gitlink without .git marker
                keep.append(d)
            dirnames[:] = keep
            for fname in filenames:
                fp = Path(dirpath) / fname
                if fname in SKIP_NAMES:
                    continue
                # Env files: .env, .env.production, cybertronia.node.env …
                if fname == ".env" or fname.startswith(".env.") or fname.endswith(".env"):
                    continue
                if fp.suffix.lower() in SKIP_EXTS:
                    continue
                try:
                    head_bytes = fp.read_bytes()[:4096]
                except OSError:
                    continue
                if _looks_binary(head_bytes):
                    continue
                head = head_bytes.decode("utf-8", errors="ignore")
                if any(rx.search(head) for rx in SPDX_PATTERNS):
                    continue
                flagged.append(fp)
                if len(flagged) >= MAX_FLAGGED:
                    return flagged
    return flagged
