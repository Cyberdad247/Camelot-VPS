# SPDX-License-Identifier: MIT

"""Session error logger for the Camelot-OS CLI REPL.

Every per-command error boundary writes a structured JSONL entry to a
session-specific log file under ``data/session_logs/``.  The log is
useful for post-mortem debugging: it captures the command that failed,
the error type and message, a traceback, and the REPL context (active
knight, provider, model) at the time of failure.

Log files are named ``session_YYYYMMDD_HHMMSS_<pid>.jsonl`` and
rotated per REPL invocation.  A new session file is created on the
first error; if the REPL runs without errors no file is written.

**Rotation policy** (applied on each ``log_command_error`` call):

- **Max files**: 50 session logs.  Oldest files are deleted first.
- **Max age**: 30 days.  Files older than this are deleted.
- **Max size**: 10 MiB per file.  If a single file exceeds this, it
  is truncated (last 8 KiB preserved with a marker).

Example entry::

    {
        "ts": "2026-08-21T14:32:01.123456+00:00",
        "session_id": "session_20260821_143200_12345",
        "command": "sarda",
        "error_type": "RuntimeError",
        "error_msg": "backend unavailable",
        "traceback": "Traceback (most recent call last):\\n  ...",
        "context": {
            "knight": "sir_codex",
            "provider": "cliproxy",
            "model": "gemini-3.1-pro",
            "json_mode": false,
            "non_interactive": false
        },
        "user_input": "/sarda deploy to production"
    }
"""

from __future__ import annotations

import itertools
import json
import os
import traceback as _traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_LOG_DIR = Path(os.getenv("CAMELOT_HOME", ".")) / "data" / "session_logs"

# Rotation limits
MAX_LOG_FILES = 50          # Keep at most this many session log files
MAX_LOG_AGE_DAYS = 30       # Delete files older than this
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MiB per file
TRUNCATE_KEEP_BYTES = 8 * 1024           # When truncating, keep last 8 KiB


def _ensure_log_dir() -> Path:
    """Create the log directory if it doesn't exist and return its path."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


# ---------------------------------------------------------------------------
# Rotation helpers
# ---------------------------------------------------------------------------

def _rotate_logs() -> None:
    """Apply count-based, age-based, and size-based rotation.

    Called lazily on each ``log_command_error`` / ``log_raw_entry`` so
    there is no background thread — rotation cost is paid only when a
    log is actually written.
    """
    log_dir = _LOG_DIR
    if not log_dir.exists():
        return

    now = datetime.now(timezone.utc)
    files = sorted(log_dir.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime)

    # 1. Age-based cleanup
    max_age_seconds = MAX_LOG_AGE_DAYS * 86400
    for f in files:
        try:
            age = now.timestamp() - f.stat().st_mtime
            if age > max_age_seconds:
                f.unlink(missing_ok=True)
        except OSError:
            pass

    # 2. Count-based cleanup (refresh list after age cleanup)
    files = sorted(log_dir.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime)
    while len(files) > MAX_LOG_FILES:
        oldest = files.pop(0)
        try:
            oldest.unlink(missing_ok=True)
        except OSError:
            pass

    # 3. Size-based truncation (for the current file only — handled in write)
    if _log_path is not None and _log_path.exists():
        try:
            if _log_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                _truncate_file(_log_path)
        except OSError:
            pass


def _truncate_file(path: Path) -> None:
    """Truncate a log file to its last ``TRUNCATE_KEEP_BYTES`` bytes.

    A marker line is prepended so readers know the file was truncated.
    """
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)  # end
            size = f.tell()
            seek_pos = max(0, size - TRUNCATE_KEEP_BYTES)
            f.seek(seek_pos)
            tail = f.read()
        marker = (
            f'{{"ts":"{datetime.now(timezone.utc).isoformat()}",'
            f'"event":"truncated","original_bytes":{size}}}\n'
        ).encode("utf-8")
        with open(path, "wb") as f:
            f.write(marker)
            f.write(tail)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_session_id: str | None = None
_log_path: Path | None = None
_seq = itertools.count()
_rotation_done: bool = False


def _new_session_id() -> str:
    """Generate a unique session identifier (monotonic counter prevents collisions)."""
    now = datetime.now(timezone.utc)
    return f"session_{now.strftime('%Y%m%d_%H%M%S')}_{next(_seq)}"


def get_session_id() -> str:
    """Return the current session ID, creating one if needed."""
    global _session_id
    if _session_id is None:
        _session_id = _new_session_id()
    return _session_id


def get_log_path() -> Path | None:
    """Return the current session log file path, or None if no errors yet."""
    return _log_path


def reset_session() -> str:
    """Start a new logging session.  Returns the new session ID."""
    global _session_id, _log_path, _rotation_done
    _session_id = _new_session_id()
    _log_path = None
    # Run rotation once per session start
    _rotation_done = False
    return _session_id


# ---------------------------------------------------------------------------
# Core logging
# ---------------------------------------------------------------------------

def _maybe_rotate() -> None:
    """Run rotation once per session (lazy, on first write)."""
    global _rotation_done
    if not _rotation_done:
        _rotation_done = True
        _rotate_logs()


def log_command_error(
    command: str,
    exc: Exception,
    *,
    context: dict[str, Any] | None = None,
    user_input: str | None = None,
) -> Path:
    """Append a structured error entry to the session log file.

    Returns the path to the log file.
    """
    global _log_path

    _maybe_rotate()

    log_dir = _ensure_log_dir()
    if _log_path is None:
        _log_path = log_dir / f"{get_session_id()}.jsonl"

    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": get_session_id(),
        "command": command,
        "error_type": type(exc).__qualname__,
        "error_msg": str(exc),
        "traceback": "".join(_traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }
    if context:
        entry["context"] = context
    if user_input:
        entry["user_input"] = user_input

    with open(_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    return _log_path


def log_raw_entry(entry: dict[str, Any]) -> Path:
    """Append an arbitrary JSONL entry to the session log.

    Useful for emitting non-error events (session start, shutdown, etc.).
    """
    global _log_path

    _maybe_rotate()

    log_dir = _ensure_log_dir()
    if _log_path is None:
        _log_path = log_dir / f"{get_session_id()}.jsonl"

    if "ts" not in entry:
        entry["ts"] = datetime.now(timezone.utc).isoformat()
    if "session_id" not in entry:
        entry["session_id"] = get_session_id()

    with open(_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    return _log_path
