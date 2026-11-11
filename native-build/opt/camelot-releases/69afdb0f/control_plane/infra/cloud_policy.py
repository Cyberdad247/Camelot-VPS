# SPDX-License-Identifier: MIT

"""Cloud Timeout, Retry, and Circuit-Breaker Governance for Camelot-OS.

Standardizes HTTP client timeouts, bounded exponential backoff retries,
circuit-breaker failure tracking, and fail-soft fallback thresholds across
all remote Modal, Excalibur, and CloudBrain invocations (Track B6).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine, Optional, Tuple

import httpx
from pydantic import BaseModel


class CloudTimeoutPolicy(BaseModel):
    """Standardized timeout, retry, and circuit-breaker configuration."""

    connect_timeout_s: float = 5.0
    health_read_timeout_s: float = 10.0
    action_read_timeout_s: float = 60.0
    max_retries: int = 2
    backoff_factor: float = 0.5
    retry_status_codes: Tuple[int, ...] = (502, 503, 504)
    circuit_breaker_threshold: int = 3
    circuit_breaker_recovery_s: float = 30.0

    # In-memory runtime circuit state: {service_key: {"failures": int, "last_failure": float}}
    _circuit_state: dict[str, dict[str, Any]] = {}

    def __init__(self, **data: Any):
        super().__init__(**data)
        # Initialize internal dictionary
        object.__setattr__(self, "_circuit_state", {})

    def get_httpx_timeout(self, is_health: bool = False) -> httpx.Timeout:
        """Return standardized httpx.Timeout with fast connect timeout."""
        read_timeout = self.health_read_timeout_s if is_health else self.action_read_timeout_s
        return httpx.Timeout(
            timeout=read_timeout,
            connect=self.connect_timeout_s,
            read=read_timeout,
            write=read_timeout,
        )

    def is_circuit_open(self, service_key: str) -> bool:
        """Check whether the circuit breaker is currently OPEN for a service."""
        state = self._circuit_state.get(service_key)
        if not state:
            return False
        failures = state.get("failures", 0)
        last_failure = state.get("last_failure", 0.0)
        if failures >= self.circuit_breaker_threshold:
            # Check if recovery window has passed (half-open check)
            if time.time() - last_failure >= self.circuit_breaker_recovery_s:
                return False  # Half-open: allow one probe trial
            return True
        return False

    def record_success(self, service_key: str) -> None:
        """Record a successful response, resetting consecutive failure counts."""
        if service_key in self._circuit_state:
            self._circuit_state[service_key] = {"failures": 0, "last_failure": 0.0}

    def record_failure(self, service_key: str) -> None:
        """Record a failure, incrementing consecutive failure count."""
        state = self._circuit_state.setdefault(service_key, {"failures": 0, "last_failure": 0.0})
        state["failures"] = state.get("failures", 0) + 1
        state["last_failure"] = time.time()

    def is_retryable_exception(self, exc: Exception) -> bool:
        """Determine if an exception is eligible for bounded retry."""
        if isinstance(exc, (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            if exc.response is not None and exc.response.status_code in self.retry_status_codes:
                return True
        return False

    def compute_backoff(self, attempt: int) -> float:
        """Compute exponential backoff delay with multiplier."""
        return self.backoff_factor * (2 ** attempt)

    async def execute_http(
        self,
        request_fn: Callable[[], Coroutine[Any, Any, httpx.Response]],
        *,
        service_key: str,
        is_health: bool = False,
    ) -> httpx.Response:
        """Execute an async HTTP call wrapped in timeout, retry, and circuit-breaker logic."""
        if self.is_circuit_open(service_key):
            state = self._circuit_state.get(service_key, {})
            failures = state.get("failures", 0)
            raise RuntimeError(
                f"Circuit breaker OPEN for '{service_key}' ({failures} consecutive failures). "
                f"Fast-failing to preserve local resources until recovery window."
            )

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await request_fn()
                response.raise_for_status()
                self.record_success(service_key)
                return response
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries and self.is_retryable_exception(exc):
                    delay = self.compute_backoff(attempt)
                    await asyncio.sleep(delay)
                    continue
                # Not retryable or max retries exhausted
                self.record_failure(service_key)
                raise last_exc

        assert last_exc is not None
        self.record_failure(service_key)
        raise last_exc

    def get_circuit_summary(self) -> dict[str, Any]:
        """Return diagnostic snapshot of circuit breaker states."""
        now = time.time()
        summary: dict[str, Any] = {}
        for key, state in self._circuit_state.items():
            failures = state.get("failures", 0)
            last_fail = state.get("last_failure", 0.0)
            is_open = failures >= self.circuit_breaker_threshold and (now - last_fail < self.circuit_breaker_recovery_s)
            summary[key] = {
                "consecutive_failures": failures,
                "circuit_open": is_open,
                "last_failure_ago_s": round(now - last_fail, 1) if last_fail > 0 else None,
            }
        return summary
