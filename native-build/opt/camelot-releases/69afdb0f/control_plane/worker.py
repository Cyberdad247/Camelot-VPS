# SPDX-License-Identifier: MIT

"""
Harness Queue Worker — reads logs/harness_queue.jsonl and executes tasks.

Execution tiers (in order of precedence):
  SHELL     — //BOOT → awaken.py  |  //SCAN → squires.colony triage
  ANTHROPIC — ANTHROPIC_API_KEY set → Claude claude-sonnet-4-6 (streaming)
  OLLAMA    — Ollama running at :11434 → local model (streaming, no API key needed)
  DRY       — neither available → show task, mark NEEDS_LLM

Knight → Ollama model routing:
  sir_forge, sir_debug     → qwen2.5-coder:3b  (code tasks)
  sir_ghost                → qwen3:1.7b         (lightweight, air-gapped)
  merlin_omega, sir_alex   → qwen3:4b           (reasoning)
  default                  → qwen3:4b
  Override: OLLAMA_MODEL env var

Tracking: logs/worker_done.txt  (one task ID per line, survives restarts)

Usage:
    python -m control_plane.worker              # watch mode — polls every 3s
    python -m control_plane.worker --once       # drain queue once and exit
    python -m control_plane.worker --status     # print queue depth and exit
    python -m control_plane.worker --dry-run    # show tasks, skip LLM calls
    python -m control_plane.worker --auto-approve  # skip HITL prompts
    python -m control_plane.worker --backend ollama   # force Ollama even if Anthropic key set
    python -m control_plane.worker --backend anthropic # force Anthropic
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Set by main() from --backend arg; read by _dispatch
_BACKEND: str = "auto"
# Set by main() from --no-commit flag
_NO_COMMIT: bool = False

# ── Paths ─────────────────────────────────────────────────────────────────────

HOME       = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
QUEUE_FILE = HOME / "logs" / "harness_queue.jsonl"
DONE_FILE  = HOME / "logs" / "worker_done.txt"
LOG_FILE   = HOME / "logs" / "worker.log"
PYTHON     = HOME / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

OLLAMA_HOST    = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
RESPONSES_DIR  = HOME / "logs" / "harness_responses"

# Lazily loaded Redis store — None until first _write_response call
_redis_store = None

def _get_redis_store():
    global _redis_store
    if _redis_store is not None:
        return _redis_store
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "local_store", HOME / "01_KERNEL" / "memory" / "local_store.py"
        )
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        _redis_store = _mod.local_store
    except Exception:
        _redis_store = None
    return _redis_store

# Knight → Ollama model
# Enterprise Factory Fleet (Qwen 2.5 Architecture)
# Set OLLAMA_MODEL env var to override globally, e.g. qwen2.5:7b.
_KNIGHT_OLLAMA_MODEL: dict[str, str] = {
    "sir_forge":    "qwen2.5-coder:7b",
    "sir_debug":    "qwen2.5-coder:7b",
    "sir_boris":    "qwen2.5-coder:7b",
    "merlin_omega": "qwen2.5:7b",
    "sir_alex":     "qwen2.5:3b",
    "lady_apis":    "qwen2.5:3b",
    "sir_sentinel": "qwen2.5:3b",
    "sir_ghost":    "qwen2.5:1.5b",
    "squire_colony":"qwen2.5:0.5b",
}
_DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"

# ── Knight personas for LLM dispatch ──────────────────────────────────────────

_KNIGHT_PERSONAS: dict[str, str] = {
    "anya_omega": (
        "You are ANYA_OMEGA, Knight at the Helm (Alpha First & Omega Last) and Sovereign Gatekeeper for CAMELOT-OS. "
        "Govern cognitive ingress, risk-entropy triage, and multi-agent dispatch across the foundry. "
        "Enforce zero-trust safety gates and ensure all work aligns with King Arthur's directives."
    ),
    "sir_forge": (
        "You are SIR_FORGE, kinetic code executor for CAMELOT-OS. "
        "When given a directive, produce concrete, working code or shell commands. "
        "Format code in fenced blocks with the filename as the language tag "
        "(e.g. ```python:path/to/file.py). Be direct — no preamble."
    ),
    "sir_boris": (
        "You are SIR_BORIS, lead architect and Crucible Conductor for CAMELOT-OS. "
        "Analyse the directive, identify the 3 most important concerns, then output "
        "a structured implementation plan with numbered steps. "
        "Flag any security or privacy risks first."
    ),
    "merlin_omega": (
        "You are MERLIN_OMEGA, System 2 deep reasoner for CAMELOT-OS. "
        "Apply Graph-of-Thought decomposition: break the directive into sub-questions, "
        "answer each, then synthesise. Show your reasoning chain explicitly."
    ),
    "sir_debug": (
        "You are SIR_DEBUG, PIV self-healing engineer for CAMELOT-OS. "
        "Follow the PIV loop: (1) PLAN — identify root cause, (2) IMPLEMENT — "
        "produce the fix, (3) VALIDATE — list tests that confirm the fix. "
        "Maximum 3 iterations. If unresolved after 3, escalate with ESCALATE: prefix."
    ),
    "sir_sentinel": (
        "You are SIR_SENTINEL, security auditor for CAMELOT-OS. "
        "Audit the directive for: secret leakage, injection vectors, OWASP top-10, "
        "dependency risks. Output a risk table: | Risk | Severity | Mitigation |"
    ),
    "lady_apis": (
        "You are LADY_APIS, BASHR research loop for CAMELOT-OS. "
        "Brainstorm → Search context → Hypothesise → Refine. "
        "Produce a compressed UKG-format findings block. Cite sources if known."
    ),
    "sir_alex": (
        "You are SIR_ALEX, task DAG planner for CAMELOT-OS. "
        "Decompose the directive into a numbered task list. "
        "Each task: ID, description, depends_on, estimated_minutes, knight."
    ),
    "sir_ghost": (
        "You are SIR_GHOST, privacy scanner for CAMELOT-OS (air-gapped mode). "
        "Scan the directive for: API keys, tokens, passwords, PII, secrets. "
        "Report each finding with: pattern matched, line context, recommended action."
    ),
}

_DEFAULT_PERSONA = (
    "You are a CAMELOT-OS knight. Execute the following directive precisely. "
    "Be concise and concrete."
)


# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class QueueTask:
    id: str
    knight: str
    directive: str
    priority: int = 2
    submitted: str = ""
    retries: int = 0
    source: str = ""
    type: str = ""
    payload: dict = None

# ── Utilities ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def _load_done() -> set[str]:
    if not DONE_FILE.exists():
        return set()
    return set(DONE_FILE.read_text(encoding="utf-8").splitlines())

def _mark_done(task_id: str) -> None:
    DONE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DONE_FILE, "a", encoding="utf-8") as f:
        f.write(task_id + "\n")

def _read_queue(done: set[str]) -> list[QueueTask]:
    if not QUEUE_FILE.exists():
        return []
    tasks: list[QueueTask] = []
    try:
        lines = QUEUE_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            tid = data.get("id", "")
            if tid and tid not in done:
                tasks.append(QueueTask(
                    id=tid,
                    knight=data.get("knight", "sir_boris"),
                    directive=data.get("directive", ""),
                    priority=int(data.get("priority", 2)),
                    submitted=data.get("submitted", ""),
                    retries=int(data.get("retries", 0)),
                    source=data.get("source", ""),
                    type=data.get("type", ""),
                    payload=data,
                ))
        except Exception:
            pass
    return sorted(tasks, key=lambda t: t.priority)


def _queue_depth() -> tuple[int, int]:
    """Return (total_lines, pending_count)."""
    done = _load_done()
    if not QUEUE_FILE.exists():
        return 0, 0
    try:
        lines = [line for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return 0, 0
    pending = sum(
        1 for line in lines
        if (lambda d: d.get("id", "") not in done)(json.loads(line) if line else {})
    )
    return len(lines), pending


def _hitl_prompt(task: QueueTask) -> bool:
    """Return True if approved."""
    print()
    print("=" * 60)
    print(f"  TASK  : {task.id}")
    print(f"  KNIGHT: {task.knight}")
    print(f"  RUNE  : {task.directive[:80]}")
    if task.submitted:
        print(f"  QUEUED: {task.submitted}")
    print("=" * 60)
    try:
        ans = input("  Execute? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "n"
    return ans in ("y", "yes")


# ── File-apply helpers ────────────────────────────────────────────────────────

def _parse_code_blocks(text: str) -> list[tuple[str, str, str]]:
    """
    Parse fenced code blocks from LLM response.
    Returns list of (language, filename_or_empty, code).
    Filename comes from ```lang:path/to/file.py opener syntax.
    """
    pattern = re.compile(r"```([a-zA-Z0-9_+\-.]*(?::[^\n]*)?)?\n(.*?)```", re.DOTALL)
    results = []
    for m in pattern.finditer(text):
        header = (m.group(1) or "").strip()
        code = m.group(2)
        if ":" in header:
            lang, filename = header.split(":", 1)
            filename = filename.strip()
        else:
            lang = header
            filename = ""
        results.append((lang.strip(), filename, code))
    return results


def _apply_output(task_id: str, response: str, auto_approve: bool) -> list[str]:
    """
    Write code blocks that carry filenames to disk; backup full response regardless.
    Returns list of absolute paths written.
    """
    backup_dir = HOME / "logs"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"forge_output_{task_id}.md"
    backup_path.write_text(response, encoding="utf-8")
    _log(f"[APPLY] Saved response -> {backup_path.name}")

    blocks = _parse_code_blocks(response)
    if not blocks:
        _log("[APPLY] No fenced code blocks in response")
        return []

    named = [(lang, fname, code) for lang, fname, code in blocks if fname]
    if not named:
        _log(f"[APPLY] {len(blocks)} block(s) found — none have filename hints (```lang:path)")
        return []

    written: list[str] = []
    for _lang, filename, code in named:
        target = (HOME / filename).resolve()
        try:
            target.relative_to(HOME)
        except ValueError:
            _log(f"[APPLY] WARN: path escapes CAMELOT_OS root, skipped: {filename}")
            continue

        if target.exists() and not auto_approve:
            print(f"\n  File exists: {target.relative_to(HOME)}")
            try:
                ans = input("  Overwrite? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            if ans not in ("y", "yes"):
                _log(f"[APPLY] Skipped (user declined): {filename}")
                continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        _log(f"[APPLY] Wrote {len(code):,} bytes -> {filename}")
        written.append(str(target))

    return written


# ── Sentinel QA gate ──────────────────────────────────────────────────────────

def _sentinel_gate(written_paths: list[str]) -> tuple[list[str], int]:
    """
    Ghost-scan every written file for CRITICAL secret findings.
    Quarantines blocked files (renames to .sentinel_blocked).
    Returns (clean_paths, blocked_count).
    """
    if not written_paths:
        return written_paths, 0
    try:
        import hashlib as _hashlib
        import sys as _sys
        if str(HOME) not in _sys.path:
            _sys.path.insert(0, str(HOME))
        from squires.ghost import triage as _ghost_triage
        from squires.scan import FileRecord
    except Exception as _e:
        _log(f"[SENTINEL] Ghost scanner unavailable ({_e}) — gate skipped")
        return written_paths, 0

    clean: list[str] = []
    blocked = 0
    for path_str in written_paths:
        path = Path(path_str)
        if not path.exists():
            clean.append(path_str)
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            sha = _hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]
            rec = FileRecord(
                rel=str(path.relative_to(HOME)).replace("\\", "/"),
                ext=path.suffix.lower(),
                lines=text.count("\n") + 1,
                size=path.stat().st_size,
                sha256=sha,
                path=path,
            )
            report = _ghost_triage(iter([rec]))
            critical = [f for f in report.flags if f.severity == "critical"]
        except Exception as _e:
            _log(f"[SENTINEL] Scan error {path.name}: {_e} — allowing")
            clean.append(path_str)
            continue

        if critical:
            _log(f"[SENTINEL] BLOCKED {path.name}: {len(critical)} critical finding(s)")
            for flag in critical:
                _log(f"  [{flag.kind}] line {flag.line}: {flag.detail[:80]}")
            quarantine = path.with_suffix(path.suffix + ".sentinel_blocked")
            try:
                path.rename(quarantine)
                _log(f"[SENTINEL] Quarantined -> {quarantine.name}")
            except Exception:
                path.unlink(missing_ok=True)
            blocked += 1
        else:
            _log(f"[SENTINEL] OK {path.name}")
            clean.append(path_str)

    return clean, blocked


# ── Directive enrichment ──────────────────────────────────────────────────────

# Knights that regularly produce code and should get the filename-hint injection.
_CODE_KNIGHTS = {"sir_forge", "sir_debug", "sir_boris", "sir_alex", "merlin_omega"}

# Simple heuristics to guess a reasonable output path from the directive text.
_LANG_EXTS = {
    "python": "py", "py": "py",
    "rust": "rs", "go": "go",
    "typescript": "ts", "ts": "ts",
    "javascript": "js", "js": "js",
    "bash": "sh", "shell": "sh",
}

def _infer_output_path(directive: str) -> str:
    """
    Guess a plausible output path from the directive text.
    Returns an empty string when nothing can be inferred (caller uses generic hint).
    """
    d = directive.lower()

    # Detect language from common keywords (whole-word match to avoid "ts" in "checks")
    lang_ext = "py"  # default
    for kw, ext in _LANG_EXTS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", d):
            lang_ext = ext
            break

    # Try to find a snake_case or CamelCase identifier that looks like a name
    # e.g. "write a function is_port_open" → "is_port_open"
    #      "build class TokenManager"       → "token_manager"
    name_match = re.search(
        r"\b(?:function|class|module|script|utility|helper|tool)\s+([A-Za-z_][A-Za-z0-9_]*)",
        directive,
        re.IGNORECASE,
    )
    if name_match:
        raw = name_match.group(1)
        # CamelCase → snake_case
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", raw).lower()
        folder = "utils" if lang_ext in ("py", "rs", "go", "ts", "js") else "scripts"
        return f"{folder}/{snake}.{lang_ext}"

    # Fallback: look for a quoted filename
    quoted = re.search(r"""["'`]([A-Za-z0-9_./\\-]+\.[a-z]{1,5})["'`]""", directive)
    if quoted:
        return quoted.group(1).replace("\\", "/")

    return ""


def _enrich_directive(directive: str, knight: str) -> str:
    """
    Append a compact file-format instruction to directives for code-producing knights.
    The instruction is short enough not to confuse small models.
    """
    if knight.lower() not in _CODE_KNIGHTS:
        return directive

    # Don't double-inject if user already embedded a filename hint
    if "```" in directive and ":" in directive.split("```", 1)[-1].split("\n")[0]:
        return directive

    inferred = _infer_output_path(directive)
    if inferred:
        hint = (
            f"\n\nIMPORTANT: Output all code as a single fenced block with this exact header: "
            f"```{inferred.rsplit('.', 1)[-1]}:{inferred}"
        )
    else:
        hint = (
            "\n\nIMPORTANT: Output all code in a fenced block with a filepath header, "
            "e.g. ```python:utils/my_module.py  Choose a sensible path."
        )
    return directive + hint


# ── PIV Validation ────────────────────────────────────────────────────────────

def _validate_file(path: Path) -> tuple[bool, str]:
    """
    Syntax-check a file using the appropriate language tool.
    Returns (ok, error_message).
    Silently passes (True, "") when the validator is not installed or extension unknown.
    """
    ext = path.suffix.lower()
    try:
        if ext == ".py":
            r = subprocess.run(
                [sys.executable, "-m", "py_compile", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                return False, (r.stderr or r.stdout).strip()

        elif ext == ".rs":
            tmp = Path(tempfile.mkdtemp(prefix="camelot_piv_"))
            try:
                r = subprocess.run(
                    ["rustc", "--edition", "2021", "--crate-type", "lib",
                     str(path), "--out-dir", str(tmp)],
                    capture_output=True, text=True, timeout=90,
                )
                if r.returncode != 0:
                    return False, r.stderr.strip()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        elif ext == ".go":
            r = subprocess.run(
                ["gofmt", "-e", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            err = r.stderr.strip()
            if r.returncode != 0 or err:
                return False, err or r.stdout.strip()

        elif ext in (".js", ".mjs", ".cjs", ".jsx"):
            r = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                return False, (r.stderr or r.stdout).strip()

        elif ext in (".ts", ".tsx"):
            # Try tsc for full TS syntax; fall back to node --check (catches JS-level errors)
            tsc = shutil.which("tsc")
            if tsc:
                r = subprocess.run(
                    [tsc, "--noEmit", "--allowJs", "--strict", "false",
                     "--target", "ES2020", "--module", "commonjs", str(path)],
                    capture_output=True, text=True, timeout=60,
                )
                if r.returncode != 0:
                    return False, (r.stderr or r.stdout).strip()
            else:
                r = subprocess.run(
                    ["node", "--check", str(path)],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    return False, (r.stderr or r.stdout).strip()

        elif ext == ".sh" and sys.platform != "win32":
            r = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return False, r.stderr.strip()

    except FileNotFoundError:
        pass  # validator not installed — skip
    except subprocess.TimeoutExpired:
        _log(f"[PIV] Validator timed out for {path.name} — skipping")
    except Exception as e:
        _log(f"[PIV] Validator error for {path.name}: {e}")

    return True, ""


def _call_llm_raw(task: QueueTask, user_content: str, dry_run: bool) -> str:
    """Call the active LLM backend with custom content (no enrichment). Returns response text."""
    if dry_run:
        return "dry-run"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if _BACKEND in ("anthropic",) or (_BACKEND == "auto" and api_key):
        try:
            import anthropic
            persona = _KNIGHT_PERSONAS.get(task.knight.lower(), _DEFAULT_PERSONA)
            client = anthropic.Anthropic(api_key=api_key)
            collected: list[str] = []
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=persona,
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                for chunk in stream.text_stream:
                    print(chunk, end="", flush=True)
                    collected.append(chunk)
            print()
            return "".join(collected)
        except Exception as e:
            return f"error: {e}"

    if _BACKEND in ("ollama", "auto") and _probe_ollama():
        model = _ollama_model_for(task.knight)
        persona = _KNIGHT_PERSONAS.get(task.knight.lower(), _DEFAULT_PERSONA)
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": persona},
                {"role": "user",   "content": user_content},
            ],
            "stream": True,
        }).encode()
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            collected = []
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        text = chunk.get("message", {}).get("content", "")
                        if text:
                            print(text, end="", flush=True)
                            collected.append(text)
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        pass
            print()
            return "".join(collected)
        except Exception as e:
            return f"error: {e}"

    return "NEEDS_LLM"


def _piv_fix(path: Path, error: str, task: QueueTask, dry_run: bool) -> bool:
    """
    One-shot LLM fix attempt for a validation failure.
    Writes the corrected file only if the fix itself passes validation.
    Returns True if the file was successfully corrected.
    """
    if dry_run:
        _log(f"[PIV] DRY-RUN: would request fix for {path.name}")
        return False

    lang = path.suffix.lstrip(".")
    rel = str(path.relative_to(HOME)).replace("\\", "/")

    try:
        original = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        _log(f"[PIV] Cannot read {path.name} for fix: {e}")
        return False

    fix_prompt = (
        f"The file `{rel}` you wrote has a syntax error:\n\n"
        f"```\n{error[:800]}\n```\n\n"
        f"Original code:\n\n"
        f"```{lang}:{rel}\n{original}\n```\n\n"
        f"Fix the syntax error. Output ONLY the corrected file as a single fenced block "
        f"with this exact header line: ```{lang}:{rel}"
    )

    _log(f"[PIV] Requesting fix for {rel}...")
    print(f"\n{'─' * 60}")
    print(f"  PIV FIX  {path.name}")
    print(f"{'─' * 60}")

    fix_task = QueueTask(
        id=f"{task.id}-piv",
        knight=task.knight,
        directive=fix_prompt,
        priority=task.priority,
    )
    response = _call_llm_raw(fix_task, fix_prompt, dry_run=False)
    if not response or response.startswith(("error:", "NEEDS_LLM", "dry-run")):
        _log(f"[PIV] LLM fix call failed: {response[:80]}")
        return False

    blocks = _parse_code_blocks(response)
    for _lang, fname, code in blocks:
        if not fname:
            continue
        target = (HOME / fname).resolve()
        try:
            target.relative_to(HOME)
        except ValueError:
            continue
        if target != path:
            continue

        # Validate the proposed fix before applying it (preserve original ext for validator)
        tmp = path.parent / f"_piv_tmp_{path.name}"
        try:
            tmp.write_text(code, encoding="utf-8")
            ok, err2 = _validate_file(tmp)
        finally:
            tmp.unlink(missing_ok=True)

        if ok:
            path.write_text(code, encoding="utf-8")
            _log(f"[PIV] Fixed: {rel}")
            return True
        else:
            _log(f"[PIV] Fix still has errors: {err2[:200]}")
            return False

    _log(f"[PIV] No matching code block for {rel} in fix response")
    return False


def _piv_run(written_paths: list[str], task: QueueTask, dry_run: bool, auto_approve: bool) -> str:
    """
    Validate every written file; attempt one LLM fix per failure.
    Returns a compact summary string (empty string if nothing was written).
    """
    if not written_paths:
        return ""

    passed = fixed = unfixed = 0
    for path_str in written_paths:
        path = Path(path_str)
        ok, error = _validate_file(path)
        if ok:
            _log(f"[PIV] OK  {path.name}")
            passed += 1
        else:
            _log(f"[PIV] FAIL {path.name}: {error[:120]}")
            if _piv_fix(path, error, task, dry_run):
                fixed += 1
            else:
                unfixed += 1

    parts = [f"piv {passed}/{len(written_paths)} OK"]
    if fixed:
        parts.append(f"{fixed} fixed")
    if unfixed:
        parts.append(f"{unfixed} unfixed")
    return ", ".join(parts)


# ── Git integration ───────────────────────────────────────────────────────────

def _git_commit(written_paths: list[str], task: QueueTask, piv_summary: str) -> str:
    """
    Stage written files and commit them with a [FORGE] message.
    Only commits when PIV passed (no 'unfixed' in summary) and git is available.
    Returns short SHA string on success, empty string otherwise.
    """
    if _NO_COMMIT or not written_paths:
        return ""
    if "unfixed" in piv_summary:
        _log("[GIT] Skipping commit — PIV has unfixed files")
        return ""

    try:
        # Confirm we're inside a git repo
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(HOME), capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return ""
    except FileNotFoundError:
        return ""  # git not installed

    # Stage only the files the worker wrote (not the entire working tree)
    rel_paths: list[str] = []
    for p in written_paths:
        try:
            rel_paths.append(str(Path(p).relative_to(HOME)))
        except ValueError:
            pass
    if not rel_paths:
        return ""

    subprocess.run(
        ["git", "add", "--"] + rel_paths,
        cwd=str(HOME), capture_output=True, timeout=30,
    )

    msg = f"[FORGE] {task.id}: {task.directive[:70]}"
    r = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(HOME), capture_output=True, text=True, timeout=30,
    )
    if r.returncode == 0:
        sha_r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(HOME), capture_output=True, text=True, timeout=5,
        )
        sha = sha_r.stdout.strip() if sha_r.returncode == 0 else "?"
        _log(f"[GIT] Committed {len(rel_paths)} file(s) -> {sha}")
        return f"git:{sha}"
    elif "nothing to commit" in (r.stdout + r.stderr):
        return ""
    else:
        _log(f"[GIT] Commit failed: {(r.stderr or r.stdout)[:120]}")
        return ""


# ── Auto-ledger ───────────────────────────────────────────────────────────────

def _ledger_entry(task: QueueTask, written: list[str], piv: str, git: str = "") -> None:
    """Record a provenance entry after a successful forge."""
    try:
        from control_plane.ledger_sync import append_provenance_entry

        file_names = [Path(p).name for p in written[:3]]
        files_note = f"{len(written)} file(s): {', '.join(file_names)}"
        if len(written) > 3:
            files_note += f" +{len(written) - 3} more"
        verification = ["worker PIV gate"]
        if piv:
            verification.append(piv)
        if git:
            verification.append(git)
        title = f"[FORGE:{task.id}] {task.directive[:70].rstrip()}"
        append_provenance_entry(
            title=title,
            actor=task.knight.upper(),
            scope=[files_note],
            verification=verification,
            tag="worker_forge",
        )
        _log("[LEDGER] Provenance entry written")
    except Exception as e:
        _log(f"[LEDGER] Write failed: {e}")


def _write_response(task_id: str, text: str, source: str = "") -> None:
    """Write completed task response to file and publish to Redis channel."""
    payload = json.dumps({"id": task_id, "text": text, "source": source, "ts": _now()})
    # File write (fallback polling path)
    try:
        RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
        out = RESPONSES_DIR / f"{task_id}.json"
        out.write_text(payload, encoding="utf-8")
    except Exception as e:
        _log(f"[RESPONSE] File write failed: {e}")
    # Redis pub/sub (low-latency path — no-op if Redis is dark)
    try:
        rs = _get_redis_store()
        if rs is not None:
            rs.publish(task_id, payload)
    except Exception:
        pass  # Redis dark — file fallback is sufficient


# ── Execution tiers ───────────────────────────────────────────────────────────

def _exec_shell(cmd: list[str], label: str) -> str:
    _log(f"[SHELL] {label}")
    try:
        proc = subprocess.run(
            cmd, cwd=str(HOME),
            capture_output=False,  # stream to terminal
            timeout=120,
        )
        return f"exit={proc.returncode}"
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception as e:
        return f"error: {e}"


def _exec_colony(path_arg: str) -> str:
    path = path_arg.strip() or "."
    return _exec_shell(
        [str(PYTHON), "-m", "squires.colony", "triage", path, "--auto-approve"],
        f"squires.colony triage {path}",
    )


def _probe_ollama() -> bool:
    """Return True if Ollama is reachable."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _ollama_model_for(knight: str) -> str:
    override = os.environ.get("OLLAMA_MODEL", "")
    if override:
        return override
    return _KNIGHT_OLLAMA_MODEL.get(knight.lower(), _DEFAULT_OLLAMA_MODEL)


def _exec_ollama(task: QueueTask, dry_run: bool, auto_approve: bool = False) -> str:
    model = _ollama_model_for(task.knight)
    if dry_run:
        _log(f"[DRY-RUN] Would call Ollama {model} for: {task.directive[:60]}")
        return "dry-run"

    persona = _KNIGHT_PERSONAS.get(task.knight.lower(), _DEFAULT_PERSONA)
    enriched = _enrich_directive(task.directive, task.knight)
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user",   "content": enriched},
        ],
        "stream": True,
    }).encode()

    _log(f"[OLLAMA] {task.knight} -> {model} streaming...")
    print()
    print(f"{'─' * 60}")
    print(f"  {task.knight.upper()} [{model}] | {task.directive[:55]}")
    print(f"{'─' * 60}")

    collected = []
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    text = chunk.get("message", {}).get("content", "")
                    if text:
                        print(text, end="", flush=True)
                        collected.append(text)
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print()
        _log(f"[OLLAMA] ERROR: {e}")
        return f"error: {e}"

    print()
    print(f"{'─' * 60}")
    full = "".join(collected)

    if task.directive.upper().startswith("//VOCAL") or task.directive.upper().startswith("UNKNOWN_RUNE: //VOCAL"):
        _log("[VOX] Intercepting cognitive response for TTS synthesis...")
        import urllib.error
        import urllib.request
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8300/synthesize",
                data=json.dumps({"text": full, "knight_id": task.knight}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pcm_data = resp.read()
                
                breq = urllib.request.Request(
                    "http://127.0.0.1:3002/broadcast_audio",
                    data=pcm_data,
                    headers={"Content-Type": "application/octet-stream"},
                    method="POST"
                )
                urllib.request.urlopen(breq, timeout=5)
                _log("[VOX] Audio broadcast successful.")
        except urllib.error.URLError as e:
            _log(f"[VOX] Audio broadcast failed (service offline): {e}")
            _exec_shell([str(PYTHON), "-m", "01_KERNEL.senses.audio.vox_service", "--synthesize", full], "vox_service synthesize fallback")
        except Exception as e:
            _log(f"[VOX] Audio broadcast failed: {e}")

    written = _apply_output(task.id, full, auto_approve)
    written, s_blocked = _sentinel_gate(written)
    piv = _piv_run(written, task, dry_run, auto_approve)
    git = _git_commit(written, task, piv)
    if written:
        _ledger_entry(task, written, piv, git)
    _write_response(task.id, full, task.source)
    parts = [f"ok ({len(full)} chars, model={model})"]
    if written:
        parts.append(f"wrote {len(written)} file(s)")
    if s_blocked:
        parts.append(f"{s_blocked} sentinel-blocked")
    if piv:
        parts.append(piv)
    if git:
        parts.append(git)
    return ", ".join(parts)


def _exec_llm(task: QueueTask, dry_run: bool, backend: str = "auto", auto_approve: bool = False) -> str:
    """Route to Anthropic, Ollama, or dry-run based on availability."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # Forced backend
    if backend == "anthropic":
        if not api_key:
            _log("[LLM] --backend anthropic requested but ANTHROPIC_API_KEY not set")
            return "NEEDS_LLM"
        return _exec_anthropic(task, dry_run, auto_approve)

    if backend == "ollama":
        if not _probe_ollama():
            _log(f"[LLM] --backend ollama requested but Ollama not reachable at {OLLAMA_HOST}")
            return "NEEDS_LLM"
        return _exec_ollama(task, dry_run, auto_approve)

    # Auto: Anthropic first, then Ollama, then dry
    if api_key:
        _log("[LLM] Using Anthropic (API key set)")
        return _exec_anthropic(task, dry_run, auto_approve)

    if _probe_ollama():
        _log(f"[LLM] No Anthropic key — using Ollama at {OLLAMA_HOST}")
        return _exec_ollama(task, dry_run, auto_approve)

    _log("[LLM] No Anthropic key and Ollama not reachable — task marked NEEDS_LLM")
    _log("[LLM] To fix: set ANTHROPIC_API_KEY  OR  start Ollama (ollama serve)")
    return "NEEDS_LLM"


def _exec_anthropic(task: QueueTask, dry_run: bool, auto_approve: bool = False) -> str:
    if dry_run:
        _log(f"[DRY-RUN] Would call Claude for: {task.directive[:60]}")
        return "dry-run"

    try:
        import anthropic
    except ImportError:
        return "anthropic SDK not installed"

    persona = _KNIGHT_PERSONAS.get(task.knight.lower(), _DEFAULT_PERSONA)
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    enriched = _enrich_directive(task.directive, task.knight)

    _log(f"[ANTHROPIC] {task.knight} -> claude-sonnet-4-6 streaming...")
    print()
    print(f"{'─' * 60}")
    print(f"  {task.knight.upper()} [claude-sonnet-4-6] | {task.directive[:50]}")
    print(f"{'─' * 60}")

    collected = []
    try:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=persona,
            messages=[{"role": "user", "content": enriched}],
        ) as stream:
            for chunk in stream.text_stream:
                print(chunk, end="", flush=True)
                collected.append(chunk)
    except Exception as e:
        print()
        _log(f"[ANTHROPIC] ERROR: {e}")
        return f"error: {e}"

    print()
    print(f"{'─' * 60}")
    full = "".join(collected)

    if task.directive.upper().startswith("//VOCAL") or task.directive.upper().startswith("UNKNOWN_RUNE: //VOCAL"):
        _log("[VOX] Intercepting cognitive response for TTS synthesis...")
        import urllib.error
        import urllib.request
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8300/synthesize",
                data=json.dumps({"text": full, "knight_id": task.knight}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pcm_data = resp.read()
                
                breq = urllib.request.Request(
                    "http://127.0.0.1:3002/broadcast_audio",
                    data=pcm_data,
                    headers={"Content-Type": "application/octet-stream"},
                    method="POST"
                )
                urllib.request.urlopen(breq, timeout=5)
                _log("[VOX] Audio broadcast successful.")
        except urllib.error.URLError as e:
            _log(f"[VOX] Audio broadcast failed (service offline): {e}")
            _exec_shell([str(PYTHON), "-m", "01_KERNEL.senses.audio.vox_service", "--synthesize", full], "vox_service synthesize fallback")
        except Exception as e:
            _log(f"[VOX] Audio broadcast failed: {e}")

    written = _apply_output(task.id, full, auto_approve)
    written, s_blocked = _sentinel_gate(written)
    piv = _piv_run(written, task, dry_run, auto_approve)
    git = _git_commit(written, task, piv)
    if written:
        _ledger_entry(task, written, piv, git)
    _write_response(task.id, full, task.source)
    parts = [f"ok ({len(full)} chars)"]
    if written:
        parts.append(f"wrote {len(written)} file(s)")
    if s_blocked:
        parts.append(f"{s_blocked} sentinel-blocked")
    if piv:
        parts.append(piv)
    if git:
        parts.append(git)
    return ", ".join(parts)


def _dispatch(task: QueueTask, dry_run: bool, auto_approve: bool) -> str:
    # ── AUDIO / VAD tier ──────────────────────────────────────────────────────
    if task.type == "interrupt":
        _log("[WORKER] Interruption received — cancelling completion run")
        return "interrupted"

    if task.type == "vad_utterance":
        file_path = task.payload.get("file_path", "")
        if not file_path:
            return "error: missing file_path in vad_utterance"
        audio_path = Path(file_path).resolve()
        audio_root = (HOME / "03_VAULT" / "runtime_state" / "audio").resolve()
        try:
            audio_path.relative_to(audio_root)
        except ValueError:
            return "error: vad_utterance path is outside transient audio custody"
        if audio_path.suffix.lower() != ".wav":
            return "error: vad_utterance requires a WAV file"
        try:
            return _exec_shell(
                [str(PYTHON), "-m", "01_KERNEL.senses.audio.sir_sonus", "--transcribe", str(audio_path)],
                f"sir_sonus transcribe {audio_path}",
            )
        finally:
            audio_path.unlink(missing_ok=True)

    d = task.directive
    # Strip "UNKNOWN_RUNE: " prefix that the router emits for unrecognised runes
    if d.upper().startswith("UNKNOWN_RUNE:"):
        d = d.split(":", 1)[1].strip()
    directive_up = d.upper()

    # ── SHELL tier ────────────────────────────────────────────────────────────
    shell_result: Optional[str] = None

    if directive_up.startswith("//BOOT"):
        if not auto_approve and not _hitl_prompt(task):
            return "skipped"
        shell_result = _exec_shell([str(PYTHON), str(HOME / "bin" / "awaken.py")], "awaken boot")

    elif directive_up.startswith("//SCAN") or "squires.colony" in d.lower():
        if not auto_approve and not _hitl_prompt(task):
            return "skipped"
        parts = d.split(maxsplit=1)
        path_arg = parts[1].strip() if len(parts) > 1 else "."
        shell_result = _exec_colony(path_arg)

    elif directive_up.startswith("//STATUS") or "Omega_STATUS" in d:
        if not auto_approve and not _hitl_prompt(task):
            return "skipped"
        shell_result = _exec_shell(
            [str(PYTHON), "-m", "control_plane.harness", "--status"],
            "harness status",
        )

    elif task.knight.lower() in ("sir_ghost", "ghost") or "Omega_GHOST" in d:
        if not auto_approve and not _hitl_prompt(task):
            return "skipped"
        shell_result = _exec_shell(
            [str(PYTHON), "-m", "squires.colony", "ghost", "."],
            "squires.colony ghost .",
        )

    if shell_result is not None:
        _write_response(task.id, shell_result, task.source)
        return shell_result

    # ── LLM tier (all other runes + Omega_*) ─────────────────────────────────
    if not auto_approve and not _hitl_prompt(task):
        return "skipped"
    return _exec_llm(task, dry_run, backend=_BACKEND, auto_approve=auto_approve)


# ── Worker loops ──────────────────────────────────────────────────────────────

def run_once(dry_run: bool, auto_approve: bool, limit: int = 0) -> int:
    done = _load_done()
    tasks = _read_queue(done)
    if limit > 0:
        tasks = tasks[:limit]
    if not tasks:
        _log("[WORKER] Queue empty — nothing to do")
        return 0

    _log(f"[WORKER] {len(tasks)} pending task(s)" + (f" (limit={limit})" if limit else ""))
    processed = 0
    for task in tasks:
        _log(f"[WORKER] -> {task.id} | {task.knight} | {task.directive[:50]}")
        result = _dispatch(task, dry_run=dry_run, auto_approve=auto_approve)
        _log(f"[WORKER] OK {task.id} result={result}")
        _mark_done(task.id)
        done.add(task.id)
        processed += 1

    _log(f"[WORKER] Done — processed {processed} task(s)")
    return processed


async def _dispatch_async(task: QueueTask, dry_run: bool, auto_approve: bool,
                          sem: asyncio.Semaphore) -> tuple[str, str]:
    """Wrap synchronous _dispatch in a thread pool slot for parallel execution."""
    async with sem:
        result = await asyncio.to_thread(_dispatch, task, dry_run, auto_approve)
        return task.id, result


def run_once_parallel(dry_run: bool, auto_approve: bool,
                      limit: int = 0, concurrency: int = 4) -> int:
    """Drain the queue, dispatching up to `concurrency` tasks simultaneously."""
    done = _load_done()
    tasks = _read_queue(done)
    if limit > 0:
        tasks = tasks[:limit]
    if not tasks:
        _log("[WORKER] Queue empty — nothing to do")
        return 0

    _log(f"[WORKER] {len(tasks)} task(s) — parallel (concurrency={concurrency})")

    async def _gather() -> list[tuple[str, str]]:
        sem = asyncio.Semaphore(concurrency)
        return list(await asyncio.gather(
            *[_dispatch_async(t, dry_run, auto_approve, sem) for t in tasks]
        ))

    results = asyncio.run(_gather())
    processed = 0
    for task_id, result in results:
        _log(f"[WORKER] OK {task_id} result={result}")
        _mark_done(task_id)
        processed += 1

    _log(f"[WORKER] Done — {processed} task(s) parallel")
    return processed


def run_watch(dry_run: bool, auto_approve: bool, poll_s: float = 3.0, limit: int = 0) -> None:
    _log(f"[WORKER] Watching {QUEUE_FILE} (poll={poll_s}s) — Ctrl+C to stop")
    done = _load_done()
    try:
        while True:
            tasks = _read_queue(done)
            if limit > 0:
                tasks = tasks[:limit]
            for task in tasks:
                _log(f"[WORKER] -> {task.id} | {task.knight} | {task.directive[:50]}")
                result = _dispatch(task, dry_run=dry_run, auto_approve=auto_approve)
                _log(f"[WORKER] OK {task.id} result={result}")
                _mark_done(task.id)
                done.add(task.id)
            time.sleep(poll_s)
    except KeyboardInterrupt:
        _log("[WORKER] Stopped by user")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m control_plane.worker",
        description="CAMELOT-OS Harness Queue Worker",
    )
    ap.add_argument("--once",         action="store_true", help="Drain queue once and exit")
    ap.add_argument("--status",       action="store_true", help="Show queue depth and exit")
    ap.add_argument("--dry-run",      action="store_true", help="Show tasks without executing LLM calls")
    ap.add_argument("--auto-approve", action="store_true", help="Skip HITL prompts")
    ap.add_argument("--poll",         type=float, default=3.0, metavar="SEC", help="Watch poll interval (default 3s)")
    ap.add_argument("--limit",        type=int,   default=0,   metavar="N",   help="Max tasks per run (0 = unlimited)")
    ap.add_argument("--archive",      action="store_true", help="Mark all current queue entries as done (clear backlog) and exit")
    ap.add_argument("--backend",      choices=["auto", "anthropic", "ollama"], default="auto",
                    help="LLM backend: auto (Anthropic->Ollama->dry), anthropic, ollama (default: auto)")
    ap.add_argument("--no-commit",    action="store_true", help="Skip git commit after file-apply")
    ap.add_argument("--parallel",     action="store_true", help="Dispatch tasks concurrently via asyncio")
    ap.add_argument("--concurrency",  type=int, default=4, metavar="N",
                    help="Max concurrent tasks when --parallel is set (default 4)")
    args = ap.parse_args()

    global _BACKEND, _NO_COMMIT
    _BACKEND = args.backend
    _NO_COMMIT = args.no_commit

    if args.archive:
        done = _load_done()
        tasks = _read_queue(done)
        archived = 0
        for task in tasks:
            _mark_done(task.id)
            archived += 1
        _log(f"[WORKER] Archived {archived} backlog entries — queue is now clean")
        return

    if args.status:
        total, pending = _queue_depth()
        done_count = len(_load_done())
        print(json.dumps({
            "queue_file": str(QUEUE_FILE),
            "total_entries": total,
            "pending": pending,
            "done": done_count,
        }, indent=2))
        return

    if args.once:
        if args.parallel:
            run_once_parallel(dry_run=args.dry_run, auto_approve=args.auto_approve,
                              limit=args.limit, concurrency=args.concurrency)
        else:
            run_once(dry_run=args.dry_run, auto_approve=args.auto_approve, limit=args.limit)
        return

    run_watch(dry_run=args.dry_run, auto_approve=args.auto_approve, poll_s=args.poll, limit=args.limit)


if __name__ == "__main__":
    main()
