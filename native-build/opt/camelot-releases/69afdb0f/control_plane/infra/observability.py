# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Observability facade — one place to instrument an operation with both a trace
span and Prometheus metrics, no Docker.

`traced_op(name)` decorates a cluster route handler `fn(body, loop) -> (code, obj)`:
it opens a tracing span (control_plane.tracing), times the call, records a
counter + latency histogram, tags the HTTP status / errors, and re-raises so the
http_daemon still maps failures to 500.

Metrics use new names (camelot_operation_*) that don't collide with
MetricsCollector, and degrade to no-ops if prometheus_client is unavailable.
Exposition is via a native prometheus_client server (start_metrics_server) — no
container, no change to the JSON-only route dispatcher.
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

from control_plane.tracing import get_tracer

try:
    from prometheus_client import Counter, Histogram, start_http_server

    _OP_TOTAL = Counter(
        "camelot_operation_total",
        "CAMELOT-OS instrumented operations",
        ["operation", "status"],
    )
    _OP_LATENCY = Histogram(
        "camelot_operation_duration_seconds",
        "CAMELOT-OS operation latency (seconds)",
        ["operation"],
    )
    _PROM = True
except Exception:  # prometheus_client missing — metrics become no-ops
    _PROM = False


def _record(operation: str, status: str, duration_s: float) -> None:
    if not _PROM:
        return
    try:
        _OP_TOTAL.labels(operation=operation, status=status).inc()
        _OP_LATENCY.labels(operation=operation).observe(duration_s)
    except Exception:
        pass  # metrics are best-effort; never break the operation


Handler = Callable[[dict, Any], tuple]


def traced_op(operation: str) -> Callable[[Handler], Handler]:
    """Wrap a cluster route handler with a trace span + operation metrics."""

    def decorator(fn: Handler) -> Handler:
        @functools.wraps(fn)
        def wrapper(body: dict, loop: Any) -> tuple:
            t0 = time.perf_counter()
            tracer = get_tracer()
            with tracer.start_active_span(operation) as scope:
                try:
                    result = fn(body, loop)
                except Exception:
                    _record(operation, "error", time.perf_counter() - t0)
                    raise  # span context tags error + re-raises; daemon → 500
                # result is (code, obj); reflect the status on span + metric.
                status = "ok"
                try:
                    code = int(result[0])
                    scope.span.set_tag("http.status", code)
                    status = "ok" if code < 400 else "error"
                except Exception:
                    pass
                _record(operation, status, time.perf_counter() - t0)
                return result

        return wrapper

    return decorator


def start_metrics_server(port: int) -> bool:
    """Expose the process metric registry on a native HTTP /metrics server.

    Returns True if started, False if prometheus_client is unavailable or the
    port is already bound. Never raises.
    """
    if not _PROM:
        return False
    try:
        start_http_server(port)
        return True
    except Exception:
        return False


def metrics_exposition() -> tuple[bytes, str]:
    """Return (payload, content_type) for the current registry (for embedding)."""
    if not _PROM:
        return b"", "text/plain"
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return generate_latest(), CONTENT_TYPE_LATEST
