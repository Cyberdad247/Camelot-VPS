# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Aperture Bridge — centralized LLM usage + spend for the Bifrost Board (v9000.14).
=================================================================================
Surfaces LLM access/cost telemetry from **Aperture by Tailscale** (a centralized
gateway that fronts upstream providers and attributes every request to a
Tailscale identity) into the Bifrost Intelligence Board (P3-T02/T05).

Aperture exposes its dashboard on the tailnet device named ``ai`` (``http://ai/ui``).
This bridge pulls a usage summary — per-model tokens, cost, and request counts —
so the Bifrost board can show *who is spending what on which models* without each
knight handling provider keys.

Design notes:
- Aperture is in beta; its usage-API path is **configurable** (``APERTURE_USAGE_PATH``)
  so only the parser changes if the contract moves. The default base URL is
  ``http://ai`` (HTTP is fine — the tailnet encrypts via WireGuard).
- **Graceful degradation**: if Aperture/the tailnet is unreachable, ``fetch_usage``
  returns a `connected=False` summary instead of raising — the panel just shows
  "not connected", exactly like the other Bifrost telemetry sources.

Run as module:
    python -m control_plane.aperture_bridge --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import json
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BASE_URL = os.environ.get("APERTURE_URL", "http://ai")
DEFAULT_USAGE_PATH = os.environ.get("APERTURE_USAGE_PATH", "/api/usage")
DASHBOARD_URL = os.environ.get("APERTURE_DASHBOARD_URL", "http://ai/ui")


@dataclass
class ModelUsage:
    model: str                       # provider/model, e.g. "anthropic/claude-opus-4-5"
    tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0


@dataclass
class UsageSummary:
    connected: bool = False
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_requests: int = 0
    session_count: int = 0
    per_model: list[ModelUsage] = field(default_factory=list)
    dashboard_url: str = DASHBOARD_URL
    detail: str = ""

    @property
    def top_model(self) -> Optional[ModelUsage]:
        return max(self.per_model, key=lambda m: m.cost_usd, default=None)


def parse_usage(payload: dict[str, Any]) -> UsageSummary:
    """Normalize an Aperture usage payload into a UsageSummary.

    Tolerant of shape: accepts a top-level ``models``/``usage`` list of
    {model, tokens, cost(_usd), requests} and optional ``sessions`` count.
    Unknown fields are ignored; missing fields default to 0.
    """
    rows = payload.get("models") or payload.get("usage") or []
    per_model: list[ModelUsage] = []
    for r in rows:
        per_model.append(ModelUsage(
            model=str(r.get("model") or r.get("name") or "unknown"),
            tokens=int(r.get("tokens") or r.get("total_tokens") or 0),
            cost_usd=float(r.get("cost_usd") or r.get("cost") or 0.0),
            requests=int(r.get("requests") or r.get("count") or 0),
        ))
    return UsageSummary(
        connected=True,
        total_tokens=sum(m.tokens for m in per_model),
        total_cost_usd=round(sum(m.cost_usd for m in per_model), 4),
        total_requests=sum(m.requests for m in per_model),
        session_count=int(payload.get("sessions") or payload.get("session_count") or 0),
        per_model=sorted(per_model, key=lambda m: m.cost_usd, reverse=True),
        detail="aperture ok",
    )


class ApertureBridge:
    """Pulls usage telemetry from an Aperture instance (graceful)."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL,
                 usage_path: str = DEFAULT_USAGE_PATH, timeout_s: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.usage_path = usage_path
        self.timeout_s = timeout_s

    @property
    def usage_url(self) -> str:
        return f"{self.base_url}{self.usage_path}"

    def fetch_usage(self) -> UsageSummary:
        """Fetch and normalize Aperture usage. Never raises — returns a
        disconnected summary on any error (no tailnet, no ``ai`` device, etc.)."""
        try:
            req = urllib.request.Request(self.usage_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                if r.status != 200:
                    return UsageSummary(connected=False, detail=f"aperture HTTP {r.status}")
                payload = json.loads(r.read().decode("utf-8"))
            return parse_usage(payload)
        except Exception as exc:
            return UsageSummary(connected=False,
                                detail=f"aperture not connected ({type(exc).__name__})")


def render_panel(summary: UsageSummary, gold: str = "#D4AF37") -> str:
    """Render an HTML fragment for the Bifrost board's Aperture panel."""
    if not summary.connected:
        return (
            '<div id="aperture" class="card">'
            f'<span class="label">LLM GATEWAY (Aperture)</span>'
            f'<span class="val">not connected</span>'
            f'<a href="{summary.dashboard_url}" style="color:{gold};font-size:11px">open dashboard →</a>'
            f'<div style="font-size:10px;opacity:.6">{summary.detail}</div>'
            '</div>'
        )
    top = summary.top_model
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;font-size:11px">'
        f'<span>{m.model}</span><span>{m.tokens:,} tok · ${m.cost_usd:.2f}</span></div>'
        for m in summary.per_model[:5]
    )
    return (
        '<div id="aperture" class="card">'
        f'<span class="label">LLM GATEWAY (Aperture)</span>'
        f'<span class="val">${summary.total_cost_usd:.2f}</span>'
        f'<div style="font-size:10px;opacity:.7">{summary.total_tokens:,} tokens · '
        f'{summary.total_requests} reqs · {summary.session_count} sessions</div>'
        + (f'<div style="font-size:10px;color:{gold}">top: {top.model}</div>' if top else '')
        + f'<div style="margin-top:4px">{rows}</div>'
        f'<a href="{summary.dashboard_url}" style="color:{gold};font-size:11px">open dashboard →</a>'
        '</div>'
    )


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("ApertureBridge self-test")

    # parse_usage normalizes a representative payload
    summary = parse_usage({
        "models": [
            {"model": "anthropic/claude-opus-4-5", "tokens": 120000, "cost_usd": 3.60, "requests": 40},
            {"model": "openai/gpt-4.1", "tokens": 50000, "cost": 0.50, "count": 25},
        ],
        "sessions": 7,
    })
    check("connected after parse", summary.connected)
    check("totals aggregated", summary.total_tokens == 170000 and abs(summary.total_cost_usd - 4.10) < 1e-6)
    check("sorted by cost (opus top)", summary.top_model.model == "anthropic/claude-opus-4-5")
    check("session count parsed", summary.session_count == 7)

    # render produces a panel with the gateway label + dashboard link
    panel = render_panel(summary)
    check("panel shows total spend", "$4.10" in panel and "LLM GATEWAY" in panel)
    check("panel links to dashboard", "open dashboard" in panel)

    # graceful degradation: unreachable Aperture -> disconnected summary, no raise
    bad = ApertureBridge(base_url="http://127.0.0.1:1", timeout_s=0.3).fetch_usage()
    check("unreachable -> connected False (no raise)", bad.connected is False)
    check("disconnected panel renders", "not connected" in render_panel(bad))

    # live fetch against a mock Aperture server round-trips
    import http.server
    import socketserver
    import threading
    payload = json.dumps({"models": [{"model": "anthropic/claude-sonnet-4-5",
                                      "tokens": 1000, "cost_usd": 0.03, "requests": 2}],
                          "sessions": 1}).encode()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(payload)
        def log_message(self, *a): pass

    with socketserver.TCPServer(("127.0.0.1", 0), H) as srv:
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
        try:
            live = ApertureBridge(base_url=f"http://127.0.0.1:{port}", usage_path="/api/usage").fetch_usage()
            check("live mock fetch connected", live.connected and live.total_requests == 2)
        finally:
            srv.shutdown()

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — aperture_bridge")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    s = ApertureBridge().fetch_usage()
    print(json.dumps({"connected": s.connected, "total_cost_usd": s.total_cost_usd,
                      "total_tokens": s.total_tokens, "detail": s.detail}, indent=2))
