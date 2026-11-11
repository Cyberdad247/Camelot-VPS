# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Tracing — no-Docker distributed tracing for CAMELOT-OS.

The original observability design called for Jaeger via jaeger_client (a Docker
service), which the Microcubic VM Law forbids. This module provides the same
OpenTracing-style surface — `tracer.start_active_span(name)` yielding a scope
with `scope.span.set_tag(...)` — backed by:

  • a local JSONL span sink (~/.camelot/traces/<service>.jsonl by default), and
  • an OPTIONAL OTLP/HTTP export when OTEL_EXPORTER_OTLP_ENDPOINT is set
    (best-effort, stdlib urllib — no heavy collector/agent, no Docker).

Stdlib-only. Spans carry trace_id / span_id / parent_id, so parent-child nesting
is preserved across `with` blocks via a contextvar stack. Safe by default:
emission never raises into the caller.

Usage:
    from control_plane.tracing import get_tracer
    tracer = get_tracer("camelot-node-1")
    with tracer.start_active_span("consensus_proposal") as scope:
        scope.span.set_tag("entry_id", entry_id)
        scope.span.set_tag("phase", "commit")
        ...  # operation
"""
from __future__ import annotations

import contextvars
import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

_TRACE_HOME = Path(
    os.environ.get("CAMELOT_TRACE_DIR", str(Path.home() / ".camelot" / "traces"))
)
_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

# Active span stack (per async/thread context) for parent linkage.
_active: contextvars.ContextVar[tuple["Span", ...]] = contextvars.ContextVar(
    "camelot_active_spans", default=()
)


def _now_ms() -> float:
    return time.time() * 1000.0


class Span:
    """A single unit of work. OpenTracing-compatible enough for our call sites."""

    __slots__ = (
        "operation", "service", "trace_id", "span_id", "parent_id",
        "start_ms", "end_ms", "tags", "logs", "_tracer", "_finished",
    )

    def __init__(
        self,
        operation: str,
        service: str,
        tracer: "Tracer",
        trace_id: str,
        parent_id: Optional[str],
    ) -> None:
        self.operation = operation
        self.service = service
        self.trace_id = trace_id
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_id = parent_id
        self.start_ms = _now_ms()
        self.end_ms: Optional[float] = None
        self.tags: dict[str, Any] = {}
        self.logs: list[dict[str, Any]] = []
        self._tracer = tracer
        self._finished = False

    # ── OpenTracing-style surface ──────────────────────────────────────────
    def set_tag(self, key: str, value: Any) -> "Span":
        self.tags[key] = value
        return self

    def log_kv(self, **fields: Any) -> "Span":
        self.logs.append({"ts_ms": _now_ms(), **fields})
        return self

    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.end_ms = _now_ms()
        self._tracer._emit(self)

    def to_dict(self) -> dict[str, Any]:
        dur = None if self.end_ms is None else round(self.end_ms - self.start_ms, 3)
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "service": self.service,
            "operation": self.operation,
            "start_ms": round(self.start_ms, 3),
            "duration_ms": dur,
            "tags": self.tags,
            "logs": self.logs,
        }


class Scope:
    """Thin wrapper exposing `.span`, matching `start_active_span(...) as scope`."""

    __slots__ = ("span",)

    def __init__(self, span: Span) -> None:
        self.span = span


class Tracer:
    """No-Docker tracer: JSONL sink + optional OTLP/HTTP export."""

    def __init__(self, service_name: str) -> None:
        self.service = service_name
        self._lock = threading.Lock()
        self._sink = _TRACE_HOME / f"{service_name.replace('/', '_')}.jsonl"

    # ── Span creation ──────────────────────────────────────────────────────
    def start_span(self, operation: str, child_of: Optional[Span] = None) -> Span:
        parent = child_of or (_active.get()[-1] if _active.get() else None)
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        parent_id = parent.span_id if parent else None
        return Span(operation, self.service, self, trace_id, parent_id)

    @contextmanager
    def start_active_span(self, operation: str) -> Iterator[Scope]:
        span = self.start_span(operation)
        token = _active.set(_active.get() + (span,))
        try:
            yield Scope(span)
        except Exception as exc:  # record error on the span, then re-raise
            span.set_tag("error", True)
            span.log_kv(event="error", message=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            _active.reset(token)
            span.finish()

    # ── Emission (never raises into the caller) ────────────────────────────
    def _emit(self, span: Span) -> None:
        record = span.to_dict()
        try:
            with self._lock:
                self._sink.parent.mkdir(parents=True, exist_ok=True)
                with open(self._sink, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, default=str) + "\n")
        except OSError:
            pass
        if _OTLP_ENDPOINT:
            self._export_otlp(record)

    def _export_otlp(self, record: dict[str, Any]) -> None:
        try:
            import urllib.request

            data = json.dumps(record, default=str).encode("utf-8")
            req = urllib.request.Request(
                _OTLP_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=1.0).close()
        except Exception:
            pass  # export is best-effort; local JSONL remains the source of truth


# ── Module-level default tracer registry ────────────────────────────────────

_DEFAULT_SERVICE = os.environ.get("CAMELOT_SERVICE_NAME", "camelot-os")
_tracers: dict[str, Tracer] = {}
_registry_lock = threading.Lock()


def get_tracer(service_name: Optional[str] = None) -> Tracer:
    """Return a process-wide tracer for `service_name` (cached)."""
    name = service_name or _DEFAULT_SERVICE
    with _registry_lock:
        t = _tracers.get(name)
        if t is None:
            t = Tracer(name)
            _tracers[name] = t
        return t


# Convenience default used by call sites that don't need a named service.
tracer = get_tracer()
