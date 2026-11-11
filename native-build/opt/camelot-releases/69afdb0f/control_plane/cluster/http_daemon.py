# SPDX-License-Identifier: MIT

"""
Minimal stdlib HTTP daemon framework for CAMELOT-OS cluster services.

No Flask / FastAPI / Docker — just http.server + urllib, to honour the
low-resource, no-Docker philosophy. Each node runs ONE ThreadingHTTPServer in a
background thread while the asyncio event loop runs in the main thread; HTTP
handlers bridge into the loop via run_coroutine_threadsafe.

Handlers are plain callables ``fn(body: dict, loop) -> (status_code, obj)``.
"""

from __future__ import annotations

import asyncio
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional, Tuple

Handler = Callable[[dict, asyncio.AbstractEventLoop], Tuple[int, Any]]


class Router:
    """Maps (method, path) -> handler."""

    def __init__(self) -> None:
        self.routes: Dict[Tuple[str, str], Handler] = {}

    def add(self, method: str, path: str, fn: Handler) -> None:
        self.routes[(method.upper(), path)] = fn


def _make_handler(router: Router, loop: asyncio.AbstractEventLoop):
    class _H(BaseHTTPRequestHandler):
        # Silence default stderr request logging.
        def log_message(self, *_args) -> None:  # noqa: D401
            return

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except (ValueError, TypeError):
                return {}

        def _respond(self, code: int, obj: Any) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _dispatch(self, method: str) -> None:
            path = self.path.split("?", 1)[0]
            fn = router.routes.get((method, path))
            if fn is None:
                self._respond(404, {"error": "not found", "path": path})
                return
            try:
                body = self._read_body() if method == "POST" else {}
                code, obj = fn(body, loop)
                self._respond(code, obj)
            except Exception as exc:  # noqa: BLE001 - surface daemon-side errors
                self._respond(500, {"error": str(exc), "type": type(exc).__name__})

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

    return _H


class HttpDaemon:
    """A ThreadingHTTPServer bound to host:port, served from a daemon thread."""

    def __init__(self, host: str, port: int, loop: asyncio.AbstractEventLoop) -> None:
        self.host = host
        self.port = port
        self.loop = loop
        self.router = Router()
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def route(self, method: str, path: str, fn: Handler) -> None:
        self.router.add(method, path, fn)

    def start(self) -> None:
        handler_cls = _make_handler(self.router, self.loop)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler_cls)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name=f"http:{self.port}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()


# ── async / HTTP bridge helpers ────────────────────────────────────────────


def call_async(loop: asyncio.AbstractEventLoop, coro, timeout: float = 10.0):
    """Run a coroutine on the loop (from an HTTP handler thread) and get result."""
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=timeout)


def fire_async(loop: asyncio.AbstractEventLoop, coro) -> None:
    """Schedule a coroutine on the loop without waiting (fire-and-forget)."""
    asyncio.run_coroutine_threadsafe(coro, loop)


def post_json(
    url: str, obj: dict, timeout: float = 3.0, retries: int = 0, backoff: float = 0.1
) -> Optional[dict]:
    """Blocking JSON POST. Returns parsed dict, or None on failure after retries.

    ``retries`` extra attempts are made on failure — important for consensus,
    whose BFT correctness depends on every protocol message being delivered.
    """
    import time as _time

    data = json.dumps(obj).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except Exception:  # noqa: BLE001 - peer may be transiently unavailable
            if attempt < retries:
                _time.sleep(backoff * (attempt + 1))
    return None


def get_json(url: str, timeout: float = 3.0) -> Tuple[Optional[int], Optional[dict]]:
    """Blocking JSON GET. Returns (status_code, parsed) or (None, None) on failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:  # noqa: BLE001
        return None, None
