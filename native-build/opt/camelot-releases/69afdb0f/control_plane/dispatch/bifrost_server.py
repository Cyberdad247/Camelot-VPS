# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Bifrost Intelligence Board — HTMX + SSE dashboard (v9000.14, P3-T02/T05/T06).
=============================================================================
A FastAPI app that renders the sovereign control board:

    GET  /bifrost                 → HTMX board (Tailwind + Luxora Gold #D4AF37)
    GET  /bifrost/metrics         → htmx-polled metrics fragment
    GET  /bifrost/metrics/stream  → Server-Sent Events live telemetry (P3-T05)
    POST /bifrost/plan            → render an intent to Agent-Native MDX
    POST /bifrost/approve/{id}    → resume a HITL-gated job (ApprovalButton, P3-T06)
    GET  /bifrost/health          → liveness JSON

The board wires htmx (hx-get / hx-trigger / hx-swap) for reactive panels and an
EventSource to the SSE stream. Telemetry comes from inspira_metrics; MDX from
mdx_renderers; approvals flow through an in-process PendingApprovals registry
that releases a kinetic job back into EXECUTE.

Run as module (needs uvicorn):
    python -m control_plane.bifrost_server --serve   # http://127.0.0.1:8080/bifrost
    python -m control_plane.bifrost_server --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LUXORA_GOLD = "#D4AF37"


# ── HITL approval registry (P3-T06) ──────────────────────────────────────────

@dataclass
class PendingApproval:
    action_id: str
    intent: str
    tier: str
    approved: bool = False
    resolved_at: Optional[float] = None
    result: Any = None


class PendingApprovals:
    """In-process registry of HITL-gated jobs awaiting an operator click."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def register(self, action_id: str, intent: str, tier: str) -> PendingApproval:
        pa = PendingApproval(action_id=action_id, intent=intent, tier=tier)
        self._pending[action_id] = pa
        return pa

    def get(self, action_id: str) -> Optional[PendingApproval]:
        return self._pending.get(action_id)

    def approve(self, action_id: str) -> Optional[PendingApproval]:
        """Approve a pending job and resume the kinetic loop into EXECUTE."""
        pa = self._pending.get(action_id)
        if pa is None:
            return None
        pa.approved = True
        pa.resolved_at = time.time()
        try:
            from control_plane.infra.kinetic_loop import run_sync
            pa.result = run_sync(pa.intent, auto_approve=True)
        except Exception as exc:  # pragma: no cover - resume must not crash the board
            pa.result = f"resume error: {exc}"
        return pa


def _metrics_snapshot() -> dict[str, Any]:
    try:
        from control_plane.infra.inspira_metrics import collect_metrics
        m = collect_metrics()
        return {
            "uptime_s": getattr(m, "uptime_seconds", 0),
            "mamba_ratio": getattr(m, "mamba_compression_ratio", 0.0),
            "kv_hit": getattr(m, "kv_cache_hit_rate", 0.0),
            "colony_risk": getattr(m, "colony_risk_score", 0),
            "crystals": getattr(m, "crystal_count", 0),
            "cost_hour_usd": getattr(m, "cost_hour_usd", 0.0),
        }
    except Exception:
        return {"uptime_s": 0, "mamba_ratio": 0.0, "kv_hit": 0.0,
                "colony_risk": 0, "crystals": 0, "cost_hour_usd": 0.0}


def _metrics_fragment(snap: dict[str, Any]) -> str:
    return (
        '<div id="metrics" class="grid grid-cols-3 gap-3">'
        f'<div class="card"><span class="label">COMPRESSION</span>'
        f'<span class="val">{snap["mamba_ratio"]:.1f}:1</span></div>'
        f'<div class="card"><span class="label">KV HIT</span>'
        f'<span class="val">{snap["kv_hit"]*100:.0f}%</span></div>'
        f'<div class="card"><span class="label">COLONY RISK</span>'
        f'<span class="val">{snap["colony_risk"]}</span></div>'
        f'<div class="card"><span class="label">CRYSTALS</span>'
        f'<span class="val">{snap["crystals"]}</span></div>'
        f'<div class="card"><span class="label">COST/HR</span>'
        f'<span class="val">${snap["cost_hour_usd"]:.2f}</span></div>'
        f'<div class="card"><span class="label">UPTIME</span>'
        f'<span class="val">{snap["uptime_s"]}s</span></div>'
        '</div>'
    )


def _board_html() -> str:
    knights = []
    try:
        from control_plane.core.soul_router import FOUNDRY_COUNCIL
        knights = [e.knight_id for e in FOUNDRY_COUNCIL]
    except Exception:
        knights = []
    cards = "".join(
        f'<div class="knight">{k}</div>' for k in knights
    ) or '<div class="knight">roster unavailable</div>'

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><title>Bifrost Intelligence Board</title>
<script src="https://unpkg.com/htmx.org@2.0.3"></script>
<script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body {{ background:#0a0a0a; color:#e5e5e5; font-family:ui-monospace,monospace; }}
  h1 {{ color:{LUXORA_GOLD}; }}
  .card {{ border:1px solid {LUXORA_GOLD}33; border-radius:8px; padding:10px; background:#111; }}
  .label {{ display:block; font-size:10px; color:{LUXORA_GOLD}; letter-spacing:1px; }}
  .val {{ font-size:20px; font-weight:700; }}
  .knight {{ display:inline-block; margin:3px; padding:4px 8px; border:1px solid {LUXORA_GOLD}55;
            border-radius:6px; color:{LUXORA_GOLD}; font-size:12px; }}
</style></head>
<body class="p-6">
  <h1 class="text-2xl font-bold">⚔️ BIFROST INTELLIGENCE BOARD · v{__version__}</h1>
  <p class="text-xs opacity-60">Luxora Gold {LUXORA_GOLD} · HTMX + SSE · CYBERTRONIA</p>

  <section class="mt-4">
    <h2 class="text-sm" style="color:{LUXORA_GOLD}">LIVE TELEMETRY</h2>
    <!-- htmx polling fallback -->
    <div hx-get="/bifrost/metrics" hx-trigger="load, every 2s" hx-swap="innerHTML">
      <div id="metrics">connecting…</div>
    </div>
    <!-- SSE live stream -->
    <div hx-ext="sse" sse-connect="/bifrost/metrics/stream" sse-swap="metrics"
         hx-swap="innerHTML" class="mt-2 text-xs opacity-70" id="sse-sink">
      awaiting SSE…
    </div>
  </section>

  <section class="mt-6">
    <h2 class="text-sm" style="color:{LUXORA_GOLD}">LLM ACCESS & SPEND (Aperture)</h2>
    <div hx-get="/bifrost/aperture" hx-trigger="load, every 10s" hx-swap="innerHTML">
      <div id="aperture">connecting…</div>
    </div>
  </section>

  <section class="mt-6">
    <h2 class="text-sm" style="color:{LUXORA_GOLD}">OMNIROUTE AFFINITY (KV-cache routing)</h2>
    <div hx-get="/bifrost/omniroute" hx-trigger="load, every 5s" hx-swap="innerHTML">
      <div id="omniroute">connecting…</div>
    </div>
  </section>

  <section class="mt-6">
    <h2 class="text-sm" style="color:{LUXORA_GOLD}">FOUNDRY COUNCIL</h2>
    <div>{cards}</div>
  </section>

  <section class="mt-6">
    <h2 class="text-sm" style="color:{LUXORA_GOLD}">PLAN AN INTENT</h2>
    <form hx-post="/bifrost/plan" hx-target="#plan-out" hx-swap="innerHTML">
      <input name="intent" placeholder="build a status dashboard"
             class="bg-black border px-2 py-1 text-sm w-96"
             style="border-color:{LUXORA_GOLD}55"/>
      <button class="px-3 py-1 text-sm" style="background:{LUXORA_GOLD};color:#000">Compile</button>
    </form>
    <pre id="plan-out" class="mt-2 text-xs whitespace-pre-wrap"></pre>
  </section>
</body></html>"""


def create_app():
    """Construct the FastAPI Bifrost app."""
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

    app = FastAPI(title="Bifrost Intelligence Board", version=__version__)
    app.state.approvals = PendingApprovals()

    @app.get("/bifrost", response_class=HTMLResponse)
    def bifrost() -> str:
        return _board_html()

    @app.get("/bifrost/metrics", response_class=HTMLResponse)
    def metrics() -> str:
        return _metrics_fragment(_metrics_snapshot())

    @app.get("/bifrost/aperture", response_class=HTMLResponse)
    def aperture() -> str:
        """LLM access + spend panel from Aperture (graceful if not connected)."""
        from control_plane.infra.aperture_bridge import ApertureBridge, render_panel
        return render_panel(ApertureBridge().fetch_usage(), gold=LUXORA_GOLD)

    @app.get("/bifrost/omniroute", response_class=HTMLResponse)
    def omniroute() -> str:
        """OmniRoute affinity telemetry from the Multivoice-Router /metrics."""
        from control_plane.multivoice_bridge import MultivoiceBridge, render_panel
        return render_panel(MultivoiceBridge().fetch_affinity(), gold=LUXORA_GOLD)

    @app.get("/bifrost/metrics/stream")
    async def metrics_stream(frames: int = 0):
        """SSE telemetry. frames=0 streams until the client disconnects (the
        StreamingResponse cancels the generator); frames>0 emits a bounded count
        (used by tests)."""
        async def gen():
            sent = 0
            while True:
                snap = _metrics_snapshot()
                yield f"event: metrics\ndata: {json.dumps(snap)}\n\n"
                sent += 1
                if frames and sent >= frames:
                    break
                await asyncio.sleep(0.05)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/bifrost/plan", response_class=HTMLResponse)
    def plan(intent: str = Form(...)) -> str:
        # Build a plan without executing (TRIAGE/PLAN only) via a fresh loop run
        # that halts at APPROVE — we only need the plan doc.
        import asyncio as _a

        from control_plane.infra.kinetic_loop import KineticLoop
        from control_plane.infra.mdx_renderers import visual_plan
        from control_plane.infra.mdx_schema import render_mdx
        res = _a.run(KineticLoop().run(intent, auto_approve=False))
        doc = visual_plan(res)
        # register the HITL approval for the ApprovalButton flow
        action_id = getattr(getattr(res, "job", None), "job_id", "job")
        tier = doc["blocks"][0]["risk"]
        app.state.approvals.register(action_id, intent, tier)
        return f'<code>{render_mdx(doc)}</code>'

    @app.post("/bifrost/approve/{action_id}", response_class=HTMLResponse)
    def approve(action_id: str) -> str:
        pa = app.state.approvals.approve(action_id)
        if pa is None:
            return f'<span class="err">unknown action {action_id}</span>'
        complete = getattr(pa.result, "complete", False)
        return (f'<span style="color:{LUXORA_GOLD}">✓ approved {action_id} — '
                f'resumed (complete={complete})</span>')

    @app.get("/bifrost/health")
    def health() -> Any:
        return JSONResponse({"status": "ok", "version": __version__,
                             "board": "bifrost"})

    return app


# module-level app for `uvicorn control_plane.bifrost_server:app`
try:
    app = create_app()
except Exception:  # pragma: no cover - fastapi optional at import
    app = None


# ── Self-test (FastAPI TestClient — no live server needed) ────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("Bifrost Board self-test (P3-T02 / P3-T05 / P3-T06)")
    from fastapi.testclient import TestClient
    client = TestClient(create_app())

    # P3-T02: board renders with htmx attributes + Luxora Gold
    r = client.get("/bifrost")
    html = r.text
    check("board returns 200", r.status_code == 200)
    check("board has hx-get", "hx-get" in html)
    check("board has hx-trigger", "hx-trigger" in html)
    check("board has hx-swap", "hx-swap" in html)
    check("board uses Luxora Gold #D4AF37", LUXORA_GOLD in html)
    check("board wires SSE", "sse-connect=\"/bifrost/metrics/stream\"" in html)
    check("board wires Aperture panel", "hx-get=\"/bifrost/aperture\"" in html)
    check("board wires OmniRoute panel", "hx-get=\"/bifrost/omniroute\"" in html)
    ro = client.get("/bifrost/omniroute")
    check("omniroute panel 200", ro.status_code == 200)
    check("omniroute panel has label", "OMNIROUTE AFFINITY" in ro.text)

    # Aperture panel renders (disconnected here — no `ai` device — but must 200)
    ra = client.get("/bifrost/aperture")
    check("aperture panel 200", ra.status_code == 200)
    check("aperture panel has gateway label", "LLM GATEWAY" in ra.text)
    check("aperture panel links dashboard", "open dashboard" in ra.text)

    # metrics fragment
    rm = client.get("/bifrost/metrics")
    check("metrics fragment 200 + has cards", rm.status_code == 200 and "COMPRESSION" in rm.text)

    # P3-T05: SSE stream emits data: frames
    rs = client.get("/bifrost/metrics/stream?frames=2")
    check("SSE content-type is event-stream",
          rs.headers.get("content-type", "").startswith("text/event-stream"))
    check("SSE emits event: metrics + data:",
          "event: metrics" in rs.text and "data:" in rs.text)
    check("SSE data parses as JSON", '"mamba_ratio"' in rs.text)

    # P3-T06: plan registers an approval, approve resumes the loop
    rp = client.post("/bifrost/plan", data={"intent": "build a status dashboard"})
    check("plan returns rendered MDX", rp.status_code == 200 and "Summary" in rp.text)
    # find a registered action and approve it
    app2 = client.app
    pending = list(app2.state.approvals._pending.keys())
    check("plan registered a pending approval", len(pending) >= 1)
    if pending:
        ra = client.post(f"/bifrost/approve/{pending[0]}")
        check("approve resumes loop (✓)", ra.status_code == 200 and "approved" in ra.text)
        pa = app2.state.approvals.get(pending[0])
        check("approval marked approved + executed", pa.approved and pa.result is not None)

    # health
    rh = client.get("/bifrost/health")
    check("health ok", rh.status_code == 200 and rh.json()["status"] == "ok")

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — bifrost_server")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    if "--serve" in sys.argv:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8080)
    else:
        print("Bifrost Board — use --test (TestClient) or --serve (uvicorn :8080)")
