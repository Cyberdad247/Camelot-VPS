# SPDX-License-Identifier: MIT

"""Subprocess wrapper: bounded timeouts, sized excerpts, cross-platform safe.

Used by the runner (Task 3+). Never raises on non-zero exit; only
reraises FileNotFoundError as a separate code path (the runner
surfaces that as REJECTED with subclass MISSING_TOOL per
VFS_PREFLIGHT_DESIGN.md §5.3).
"""
from __future__ import annotations
import subprocess
import time
from dataclasses import dataclass

EXCERPT_CAP_BYTES = 4096
TRUNCATION_MARKER = "\n…[truncated]\n"


@dataclass
class ExecResult:
    exit_code: int
    stdout_excerpt: str
    stderr_excerpt: str
    duration_ms: int
    timed_out: bool


def _cap(text: str) -> str:
    """Cap `text` (after utf-8 encoding) at EXCERPT_CAP_BYTES bytes.

    Adds a TRUNCATION_MARKER so downstream readers can detect truncation.
    Returns the original text if already within cap.
    """
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= EXCERPT_CAP_BYTES:
        return text
    truncated = encoded[:EXCERPT_CAP_BYTES].decode(
        "utf-8", errors="replace"
    ) + TRUNCATION_MARKER
    return truncated


def run(command: list[str], timeout_s: int) -> ExecResult:
    """Run a subprocess with bounded wall-clock timeout.

    Behavior:
    - Returns ExitResult on success or non-zero exit (does not raise).
    - Sets `timed_out=True` on subprocess.TimeoutExpired.
    - Caps stdout/stderr at 4 KiB each (TRUNCATION_MARKER appended).
    - Measures elapsed wall-clock with time.monotonic().
    - Cross-platform safe (subprocess.run handles SIGTERM on POSIX,
      TerminateProcess on Windows).

    Notes:
    - We intentionally do NOT raise on FileNotFoundError here. The
      runner (Task 6) wraps `run()` and surfaces ENOENT distinctly as
      a REJECTED check with subclass MISSING_TOOL per spec §5.3.
    """
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty list[str]")
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecResult(
            exit_code=-1,
            stdout_excerpt=_cap(exc.stdout or ""),
            stderr_excerpt=_cap(exc.stderr or ""),
            duration_ms=int((time.monotonic() - started) * 1000),
            timed_out=True,
        )
    duration_ms = int((time.monotonic() - started) * 1000)
    return ExecResult(
        exit_code=proc.returncode,
        stdout_excerpt=_cap(proc.stdout or ""),
        stderr_excerpt=_cap(proc.stderr or ""),
        duration_ms=duration_ms,
        timed_out=False,
    )
