# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Production Structured JSONL Logger & Telemetry Sentinel
CAMELOT-OS / Titan-OS vMAX Master Production Substrate
=============================================================================
Enforces Production Hardening Pillar 4:
1. Structured JSON-Lines logging with timestamps, levels, knight IDs, and RSS.
2. RotatingFileHandler with 20 MB size limits and 5 backups to prevent disk bloat.
3. Sir Ghost air-gap credential redaction (token/key/secret scrubbers).
4. Automated Working-Set RSS sampling against the 4,096 MB node ceiling.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

# Patterns that must NEVER leak to disk or cloud
SECRET_PATTERNS = re.compile(r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]+)|(key-[a-zA-Z0-9]{16,})|(secret[_-]?[a-zA-Z0-9]{16,})|(password[:=]\s*[^\s,]+)")


class GhostRedactingJSONFormatter(logging.Formatter):
    """
    Serializes log records into structured JSON-Lines while scrubbing secrets
    and injecting live process telemetry (RSS MB and PID).
    """

    def __init__(self, knight_id: str = "SYSTEM"):
        super().__init__()
        self.knight_id = knight_id
        self._proc = psutil.Process()

    def format(self, record: logging.LogRecord) -> str:
        # 1. Measure live resident memory
        try:
            rss_mb = round(self._proc.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            rss_mb = 0.0

        raw_msg = record.getMessage()
        # 2. Scrub secrets matching Sir Ghost criteria
        clean_msg = SECRET_PATTERNS.sub("[REDACTED_BY_SIR_GHOST]", raw_msg)

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "knight": getattr(record, "knight_id", self.knight_id),
            "logger": record.name,
            "message": clean_msg,
            "pid": os.getpid(),
            "rss_mb": rss_mb,
            "scarcity_ratio": round(rss_mb / 4096.0, 4),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def get_production_logger(
    name: str = "camelot_production",
    knight_id: str = "SIR_HELIOS",
    log_dir: Optional[Path] = None,
    max_bytes: int = 20 * 1024 * 1024,  # 20 MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configures and returns a production-grade rotating JSON-Lines logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on re-invocation
    if logger.handlers:
        return logger

    # Resolve destination directory
    root_dir = log_dir or (Path(__file__).resolve().parents[2] / "logs" / "daemons")
    root_dir.mkdir(parents=True, exist_ok=True)
    log_file = root_dir / f"{name}.jsonl"

    handler = RotatingFileHandler(
        str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(GhostRedactingJSONFormatter(knight_id=knight_id))
    logger.addHandler(handler)

    return logger
