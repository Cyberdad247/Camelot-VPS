# SPDX-License-Identifier: MIT

"""Best-effort Living Notebook sync hooks for local Camelot state changes."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
QUEUE_PATH = REPO_ROOT / "03_VAULT" / "runtime_state" / "cloudbrain_sync_queue.jsonl"


def _load_notebooklm_bridge():
    bridge_path = REPO_ROOT / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
    spec = importlib.util.spec_from_file_location("notebooklm_bridge", bridge_path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"Unable to load notebooklm bridge at {bridge_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("notebooklm_bridge", module)
    spec.loader.exec_module(module)
    return module


def _summarize_results(results: dict[str, Any], *, limit: int = 4000) -> str:
    text = str(results)
    if len(text) > limit:
        return text[:limit].rstrip() + " ...[truncated]"
    return text


def _build_summary(event: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Auto-sync trigger: {event.get('event_type', 'unknown')}",
            f"Command: {event.get('command', 'unknown')}",
            "Result summary:",
            _summarize_results(event.get("results", {})),
        ]
    )


def _read_queue() -> list[dict[str, Any]]:
    if not QUEUE_PATH.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in QUEUE_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            events.append(
                {
                    "event_type": "queue_decode_error",
                    "command": "cloudbrain queue status",
                    "results": {"line": line, "error": str(exc)},
                    "queued_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
    return events


def _write_queue(events: list[dict[str, Any]]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        if QUEUE_PATH.exists():
            QUEUE_PATH.unlink()
        return
    text = "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events)
    QUEUE_PATH.write_text(text, encoding="utf-8")


def _enqueue_event(*, event_type: str, command: str, results: dict[str, Any], error: str) -> dict[str, Any]:
    event = {
        "event_type": event_type,
        "command": command,
        "results": results,
        "error": error,
        "queued_utc": datetime.now(timezone.utc).isoformat(),
    }
    events = _read_queue()
    events.append(event)
    _write_queue(events)
    return {"queued": True, "queue_path": str(QUEUE_PATH), "pending": len(events)}


def sync_after_event(
    *,
    event_type: str,
    command: str,
    results: dict[str, Any],
    enabled: bool = True,
) -> dict[str, Any]:
    """Best-effort sync of local state into the short-term living notebook.

    Never raises. Failures are returned to the caller for optional display/logging.
    """
    if not enabled:
        return {"triggered": False, "reason": "disabled"}

    try:
        os.environ.setdefault("CAMELOT_OS_HOME", str(REPO_ROOT))
        bridge = _load_notebooklm_bridge()
        summary = _build_summary({"event_type": event_type, "command": command, "results": results})
        payload = asyncio.run(bridge.async_sync_state(extra_summary=summary))
        return {"triggered": True, "result": payload}
    except Exception as exc:  # pragma: no cover - defensive, environment-dependent
        error = f"{type(exc).__name__}: {exc}"
        queued = _enqueue_event(event_type=event_type, command=command, results=results, error=error)
        return {"triggered": True, "error": error, **queued}


def query_cloud_brain(prompt: str, *, notebook_id: str | None = None) -> str:
    """Query the Cloud Brain for a synthesized answer to *prompt*.

    Resolution chain:
    1. NotebookLM ``synthesize()`` — TTL-cached, canonical ST brain.
    2. Long-term Appwrite memory pull — typed MemoryNode records for the
       agent keywords detected in the prompt.
    3. Local queue inspection — pending sync events as context fallback.

    Never raises. Always returns a non-empty string so Bifrost's
    ``_query_cloudbrain()`` caller remains safe.
    """
    sections: list[str] = []

    # ── 1. NotebookLM synthesis (ST Brain) ───────────────────────────────────
    try:
        bridge = _load_notebooklm_bridge()
        # Use async_synthesize directly to avoid asyncio.run() re-entrance
        # when called from Bifrost's asyncio.to_thread context.
        _kwargs: dict[str, Any] = {}
        if notebook_id:
            _kwargs["notebook_id"] = notebook_id
        try:
            _loop = asyncio.get_running_loop()
        except RuntimeError:
            _loop = None

        if _loop is not None:
            # Already inside a running loop — run the coroutine in a new thread
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=1) as _pool:
                _fut = _pool.submit(
                    lambda: asyncio.run(bridge.async_synthesize(prompt, **_kwargs))
                )
                result: str | None = _fut.result(timeout=90)
        else:
            result = asyncio.run(bridge.async_synthesize(prompt, **_kwargs))

        if result and not str(result).startswith("[Living Notebook synthesis failed"):
            sections.append(f"[Cloud Brain · NotebookLM]\n{result}")
    except Exception as exc:  # pragma: no cover — environment-dependent
        sections.append(f"[Cloud Brain · NotebookLM unavailable: {type(exc).__name__}: {exc}]")


    # ── 2. LT Appwrite memory pull ────────────────────────────────────────────
    try:
        import importlib.util as _ilu
        import sys as _sys
        _cb_path = (
            REPO_ROOT / "01_KERNEL" / "agora" / "cloud_orchestrator_shim"
            / "long_term_cloudbrain.py"
        )
        if _cb_path.exists():
            _spec = _ilu.spec_from_file_location("_lt_cloudbrain", _cb_path)
            if _spec and _spec.loader:
                _lt = _ilu.module_from_spec(_spec)
                _sys.modules.setdefault("_lt_cloudbrain", _lt)
                _spec.loader.exec_module(_lt)  # type: ignore[union-attr]
                # Detect agent keywords in the prompt for targeted recall
                _agents = [
                    a for a in (
                        "boris", "alex", "forge", "mnemo", "sentinel",
                        "ghost", "helio", "merlin", "anya", "lukas", "morgana", "apis",
                    )
                    if a in prompt.lower()
                ]
                _nodes: list[dict[str, Any]] = []
                for _agent in _agents or ["merlin"]:
                    _nodes.extend(_lt.pull_long_term_memory(_agent))
                if _nodes:
                    _excerpts = "\n".join(
                        f"  [{n.get('agent_id', '?')}] {str(n.get('content', ''))[:300]}"
                        for n in _nodes[:6]
                    )
                    sections.append(f"[Cloud Brain · LT Memory ({len(_nodes)} nodes)]\n{_excerpts}")
    except Exception as exc:  # pragma: no cover — environment-dependent
        sections.append(f"[Cloud Brain · LT memory unavailable: {type(exc).__name__}: {exc}]")

    # ── 3. Local queue context (last resort) ──────────────────────────────────
    if not sections:
        try:
            queue = _read_queue()
            if queue:
                recent = queue[-3:]
                lines = "\n".join(
                    f"  [{e.get('queued_utc', '?')}] {e.get('event_type', '?')}: "
                    f"{e.get('command', '?')}"
                    for e in recent
                )
                sections.append(
                    f"[Cloud Brain · Local Queue ({len(queue)} pending)]\n{lines}\n"
                    "(NotebookLM + Appwrite unreachable — showing queued events as context)"
                )
        except Exception:
            pass

    if not sections:
        return (
            "[Cloud Brain] No memory available. "
            "Run `notebooklm login` and set APPWRITE_* env vars to enable full recall."
        )

    return "\n\n".join(sections)


def sync_queue_status() -> dict[str, Any]:
    """Return local Cloud Brain sync queue state."""
    events = _read_queue()
    return {
        "status": "QUEUE_STATUS",
        "queue_path": str(QUEUE_PATH),
        "exists": QUEUE_PATH.exists(),
        "pending": len(events),
        "events": events[-10:],
    }


def flush_sync_queue(*, limit: int | None = None) -> dict[str, Any]:
    """Retry queued sync events and preserve failures for a later flush."""
    events = _read_queue()
    if not events:
        return {"status": "QUEUE_EMPTY", "queue_path": str(QUEUE_PATH), "pending": 0, "flushed": 0, "failed": 0}

    retry_count = len(events) if limit is None or limit <= 0 else min(limit, len(events))
    retry_events = events[:retry_count]
    untouched = events[retry_count:]
    flushed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    try:
        os.environ.setdefault("CAMELOT_OS_HOME", str(REPO_ROOT))
        bridge = _load_notebooklm_bridge()
        for event in retry_events:
            try:
                payload = asyncio.run(bridge.async_sync_state(extra_summary=_build_summary(event)))
                flushed.append({"command": event.get("command"), "result": payload})
            except Exception as exc:  # pragma: no cover - environment-dependent
                event["last_error"] = f"{type(exc).__name__}: {exc}"
                event["last_attempt_utc"] = datetime.now(timezone.utc).isoformat()
                failed.append(event)
    except Exception as exc:  # pragma: no cover - defensive
        for event in retry_events:
            event["last_error"] = f"{type(exc).__name__}: {exc}"
            event["last_attempt_utc"] = datetime.now(timezone.utc).isoformat()
            failed.append(event)

    remaining = failed + untouched
    _write_queue(remaining)
    return {
        "status": "FLUSHED" if not failed else "PARTIAL",
        "queue_path": str(QUEUE_PATH),
        "attempted": retry_count,
        "flushed": len(flushed),
        "failed": len(failed),
        "pending": len(remaining),
        "results": flushed,
        "failures": failed[-5:],
    }
