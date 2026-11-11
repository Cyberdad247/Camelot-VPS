# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Bifrost Gateway Bridge — control-plane link to the TS Bifrost gateway (:3001).

The TS gateway (apps/bifrost) is the voice/webhook ingress + Microcubic swarm
runtime. This module is the Python control plane's curl-able handle on it:

  health()             — GET /health
  send_command(text)   — HMAC-signed POST /webhook/sms (inbound command inject)
  tail_swarm_events()  — read recent gateway/swarm events off the Hermes bus
  poll_swarm_events()  — single poll of new events via hardened subscribe path
  subscribe_swarm_events() — stream events via hardened subscribe path

The link is deliberately transport-light: outbound goes over the gateway's
existing HMAC-signed webhook (no new ingress surface), inbound observability
rides the file-based Hermes bus (control_plane/hermes_bridge.py), so there is
no new network daemon and the [[no-docker-microcubic-vm]] law is honored.

CLI:
    python -m control_plane.bifrost_gateway health
    python -m control_plane.bifrost_gateway send "add transaction 5000"
    python -m control_plane.bifrost_gateway events --last 20
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

from control_plane.hermes_bridge import HermesBus

GATEWAY_URL = os.environ.get("BIFROST_GATEWAY_URL", "http://127.0.0.1:3001")
WEBHOOK_SECRET = (os.environ.get("WEBHOOK_SECRET") or "").strip()

# Channel the gateway emits to (must match apps/bifrost/src/hermes.ts SWARM_EVENTS).
SWARM_EVENTS_CHANNEL = "swarm.events"

DEFAULT_TIMEOUT = 5.0


def _gateway_base() -> str:
    return GATEWAY_URL.strip().rstrip("/")


# ── Outbound: health + command injection ───────────────────────────────────

def health(timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """GET /health. Returns the parsed body plus an `ok` flag (never raises)."""
    url = f"{_gateway_base()}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return {"ok": resp.status == 200, "status_code": resp.status, **parsed}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "error": exc.reason}
    except Exception as exc:  # connection refused, timeout, bad JSON, etc.
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _sign(raw: str, secret: str) -> str:
    """HMAC-SHA256 hex digest, matching apps/bifrost/src/security.ts."""
    return hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def send_command(message: str, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Inject a command into the gateway via its HMAC-signed /webhook/sms route."""
    secret = WEBHOOK_SECRET.strip()
    if not secret:
        return {"ok": False, "error": "WEBHOOK_SECRET not set in environment"}

    # The signature must cover the exact bytes the server reads as rawBody.
    raw = json.dumps({"message": message})
    signature = _sign(raw, secret)

    req = urllib.request.Request(
        f"{_gateway_base()}/webhook/sms",
        data=raw.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": signature,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return {"ok": resp.status == 200, "status_code": resp.status, "body": parsed}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "error": exc.reason}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ── Inbound: observe gateway/swarm events off the Hermes bus ────────────────

def tail_swarm_events(last_n: int = 20, bus: HermesBus | None = None) -> list[dict]:
    """Read the most recent gateway/swarm events from the Hermes bus (history)."""
    return (bus or HermesBus()).read_channel(SWARM_EVENTS_CHANNEL, last_n=last_n)


def poll_swarm_events(bus: HermesBus | None = None) -> list[dict]:
    """Single poll of NEW swarm events via the hardened subscribe path.

    Uses HermesBus.subscribe(run_forever=False), whose byte-offset cursor is
    immune to corrupt lines, torn final writes, and file truncation — valid
    messages are never skipped. One poll re-reads the channel from the start
    (at-least-once per invocation); callers needing strict incrementality
    should hold a long-lived subscriber via subscribe_swarm_events().
    """
    events: list[dict] = []
    (bus or HermesBus()).subscribe(
        SWARM_EVENTS_CHANNEL, events.append, run_forever=False
    )
    return events


def subscribe_swarm_events(
    callback: Callable[[dict], None],
    poll_interval: float = 5.0,
    run_forever: bool = True,
    bus: HermesBus | None = None,
) -> None:
    """Stream swarm events through the hardened subscribe path.

    Thin wrapper over HermesBus.subscribe for the swarm.events channel;
    see hermes_bridge.subscribe for the corruption-immunity contract.
    """
    (bus or HermesBus()).subscribe(
        SWARM_EVENTS_CHANNEL, callback, poll_interval=poll_interval, run_forever=run_forever
    )


# ── CLI ─────────────────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Bifrost gateway control-plane bridge")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("health", help="GET /health")

    send_p = sub.add_parser("send", help="Inject an HMAC-signed command")
    send_p.add_argument("message", help="Command text, e.g. 'add transaction 5000'")

    events_p = sub.add_parser("events", help="Tail swarm/gateway events from Hermes")
    events_p.add_argument("--last", type=int, default=20)
    events_p.add_argument(
        "--poll",
        action="store_true",
        help="Use the hardened single-poll subscribe path instead of history read",
    )

    args = parser.parse_args(argv)

    if args.cmd == "health":
        print(json.dumps(health(), indent=2))
    elif args.cmd == "send":
        print(json.dumps(send_command(args.message), indent=2))
    elif args.cmd == "events":
        if args.poll:
            for ev in poll_swarm_events():
                print(json.dumps(ev))
        else:
            for ev in tail_swarm_events(args.last):
                print(json.dumps(ev))
    else:
        parser.print_help()


if __name__ == "__main__":
    _main()
