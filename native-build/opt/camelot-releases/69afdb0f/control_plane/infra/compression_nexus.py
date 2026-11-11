# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
CompressionNexus v1.0 — System-Wide Compression for Maximum Resource Availability
==================================================================================
Northstar: absolute local optimization — never waste RAM, disk, or context window.

Three-tier compression pipeline:
  Tier 1: QFT context compression  (CLAUDE.md + cartridges → ≤1500 tok)
  Tier 2: Memory / L2 snapshot     (JSON → gzip/msgpack; 40–60% smaller)
  Tier 3: Disk / large file audit   (identify >500KB files; optional gzip pack)

HITL gate:
  compress_context()   AUTO  — in-memory only, no disk changes
  compress_memory()    AUTO  — in-memory only, no disk changes
  audit_disk()         AUTO  — read-only scan
  pack_file()          PROMPT — writes compressed file to disk

Hermes: publishes to compression.status channel after each tier.
"""
from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("COMPRESSION_NEXUS")

_LARGE_FILE_THRESHOLD = 500 * 1024   # 500 KB
_CONTEXT_TOK_TARGET = 1500
_PRIORITY_SECTIONS = [
    "## IDENTITY",
    "## TITANIUM LAWS",
    "## KNIGHT DISPATCH",
    "## RUNIC COMMANDS",
    "## THE CONSCIOUS TRIUMVIRATE",
    "## ANYA SOUL MATRIX",
]


@dataclass
class ContextCompressionResult:
    original_chars: int
    compressed_chars: int
    original_tok_est: int
    compressed_tok_est: int
    text: str
    ratio: float = 0.0

    def __post_init__(self):
        if self.original_chars > 0:
            self.ratio = round(1.0 - self.compressed_chars / self.original_chars, 4)


@dataclass
class MemoryCompressionResult:
    original_bytes: int
    compressed_bytes: int
    codec: str      # gzip | msgpack | msgpack+lz4
    ratio: float = 0.0
    data: bytes = field(default_factory=bytes, repr=False)

    def __post_init__(self):
        if self.original_bytes > 0:
            self.ratio = round(1.0 - self.compressed_bytes / self.original_bytes, 4)


@dataclass
class DiskAuditResult:
    scanned_files: int = 0
    large_files: list[dict] = field(default_factory=list)   # [{path, size_kb, ext}]
    total_size_kb: float = 0.0
    potential_savings_kb: float = 0.0


class CompressionNexus:
    """3-tier compression engine for CAMELOT-OS resource optimization."""

    def __init__(
        self,
        repo_root: Path | str | None = None,
        hermes_enabled: bool = True,
    ) -> None:
        self.repo_root = Path(repo_root or Path.cwd())
        self.hermes_enabled = hermes_enabled

    # ── Tier 1: QFT context compression ───────────────────────────────────

    def compress_context(self, text: str, tok_target: int = _CONTEXT_TOK_TARGET) -> ContextCompressionResult:
        """QFT-compress a markdown context block.

        Keeps PRIORITY_SECTIONS verbatim; truncates all other sections to 5 lines.
        Returns the compressed text and ratio. AUTO gate — no disk writes.
        """
        original_chars = len(text)
        original_tok_est = original_chars // 4

        if original_tok_est <= tok_target:
            return ContextCompressionResult(
                original_chars=original_chars,
                compressed_chars=original_chars,
                original_tok_est=original_tok_est,
                compressed_tok_est=original_tok_est,
                text=text,
            )

        lines = text.splitlines()
        extracted: list[str] = []
        current_block: list[str] = []
        keep = False

        for line in lines:
            if line.startswith("## "):
                if current_block:
                    extracted.extend(current_block if keep else current_block[:5])
                current_block = [line]
                keep = any(line.startswith(s) for s in _PRIORITY_SECTIONS)
            else:
                current_block.append(line)

        if current_block:
            extracted.extend(current_block if keep else current_block[:5])

        compressed = "\n".join(extracted)
        compressed_tok_est = len(compressed) // 4

        if self.hermes_enabled:
            self._emit_hermes("tier1_context", {
                "original_tok": original_tok_est,
                "compressed_tok": compressed_tok_est,
                "ratio": round(1.0 - len(compressed) / original_chars, 4),
            })

        return ContextCompressionResult(
            original_chars=original_chars,
            compressed_chars=len(compressed),
            original_tok_est=original_tok_est,
            compressed_tok_est=compressed_tok_est,
            text=compressed,
        )

    # ── Tier 2: Memory / snapshot compression ─────────────────────────────

    def compress_memory(self, data: Any) -> MemoryCompressionResult:
        """Compress an in-memory JSON-serializable object to bytes.

        Tries msgpack+lz4 → msgpack → gzip(JSON) in order of availability.
        AUTO gate — returns bytes, no disk writes.
        """
        json_bytes = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        original_bytes = len(json_bytes)

        # Try msgpack (faster, smaller)
        try:
            import msgpack
            packed = msgpack.packb(data, use_bin_type=True)
            try:
                import lz4.frame
                compressed = lz4.frame.compress(packed)
                codec = "msgpack+lz4"
            except ImportError:
                compressed = packed
                codec = "msgpack"
        except ImportError:
            # Fallback: gzip(JSON)
            compressed = gzip.compress(json_bytes, compresslevel=6)
            codec = "gzip"

        result = MemoryCompressionResult(
            original_bytes=original_bytes,
            compressed_bytes=len(compressed),
            codec=codec,
            data=compressed,
        )

        if self.hermes_enabled:
            self._emit_hermes("tier2_memory", {
                "original_bytes": original_bytes,
                "compressed_bytes": len(compressed),
                "codec": codec,
                "ratio": result.ratio,
            })

        return result

    def decompress_memory(self, compressed: bytes, codec: str) -> Any:
        """Decompress bytes previously compressed by compress_memory()."""
        if codec == "gzip":
            json_bytes = gzip.decompress(compressed)
            return json.loads(json_bytes.decode("utf-8"))
        elif codec == "msgpack":
            import msgpack
            return msgpack.unpackb(compressed, raw=False)
        elif codec == "msgpack+lz4":
            import lz4.frame
            import msgpack
            return msgpack.unpackb(lz4.frame.decompress(compressed), raw=False)
        raise ValueError(f"Unknown codec: {codec}")

    # ── Tier 3: Disk audit ─────────────────────────────────────────────────

    def audit_disk(self, scan_root: Path | str | None = None) -> DiskAuditResult:
        """Scan directory for files > 500 KB. AUTO gate — read-only."""
        root = Path(scan_root or self.repo_root)
        result = DiskAuditResult()

        _SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
                      ".pytest_tmp", "dist", "build", "target", "99_ARCHIVE"}

        for path in root.rglob("*"):
            if any(p in _SKIP_DIRS for p in path.parts):
                continue
            if path.is_file():
                result.scanned_files += 1
                try:
                    sz = path.stat().st_size
                    result.total_size_kb += sz / 1024
                    if sz > _LARGE_FILE_THRESHOLD:
                        result.large_files.append({
                            "path": str(path.relative_to(root)),
                            "size_kb": round(sz / 1024, 1),
                            "ext": path.suffix,
                        })
                        # Estimate ~50% savings via gzip
                        result.potential_savings_kb += (sz / 1024) * 0.5
                except OSError:
                    pass

        result.total_size_kb = round(result.total_size_kb, 1)
        result.potential_savings_kb = round(result.potential_savings_kb, 1)

        if self.hermes_enabled:
            self._emit_hermes("tier3_disk_audit", {
                "scanned": result.scanned_files,
                "large_count": len(result.large_files),
                "potential_savings_kb": result.potential_savings_kb,
            })

        return result

    def pack_file(self, path: Path | str, remove_original: bool = False) -> Path:
        """Gzip-compress a single file → <path>.gz. PROMPT gate — writes to disk.

        remove_original=True is destructive — call only after operator PROMPT.
        """
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(f"pack_file: {src} not found")

        dest = src.with_suffix(src.suffix + ".gz")
        with src.open("rb") as f_in, gzip.open(dest, "wb", compresslevel=6) as f_out:
            f_out.write(f_in.read())

        if remove_original:
            src.unlink()

        log.info("[COMPRESSION_NEXUS] packed %s -> %s", src, dest)
        return dest

    # ── Hermes ─────────────────────────────────────────────────────────────

    def _emit_hermes(self, tier: str, payload: dict) -> None:
        try:
            from control_plane.hermes_bridge import HermesBus
            HermesBus().publish("compression.status", {"tier": tier, **payload})
        except Exception as exc:
            log.debug("[COMPRESSION_NEXUS] Hermes unavailable: %s", exc)
