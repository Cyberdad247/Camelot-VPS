"""Isolated, Tailnet-only signed bus for Android Camelot edge supervisors.

This deliberately does not modify the legacy mesh bridge: that process has
unknown callers and must migrate independently.  The bus accepts only signed
edge envelopes and exposes no browser CORS surface.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from control_plane.dispatch.edge_protocol import EdgeProtocol, ValidationResult, issue_snapshot

LOG = logging.getLogger("CamelotEdgeBus")
EDGE_ENVELOPE_HEADER = "x-camelot-edge-envelope"
EDGE_BUS_PORT = int(os.getenv("CAMELOT_EDGE_BUS_PORT", "8096"))
VPS_TAILSCALE_IP = "100.110.180.18"
_protocol_cache: tuple[str, EdgeProtocol] | None = None


def is_tailnet_bind_host(host: str) -> bool:
    parts = host.split(".")
    return (
        len(parts) == 4
        and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
        and parts[0] == "100"
        and 64 <= int(parts[1]) <= 127
    )


def _protocol_from_environment() -> EdgeProtocol | None:
    global _protocol_cache
    raw_registry = os.getenv("CAMELOT_EDGE_PUBLIC_KEYS_JSON", "")
    registry_file = os.getenv("CAMELOT_EDGE_PUBLIC_KEYS_FILE", "")
    if registry_file:
        try:
            raw_registry = Path(registry_file).read_text(encoding="utf-8")
        except OSError:
            LOG.error("cannot read CAMELOT_EDGE_PUBLIC_KEYS_FILE; refusing edge traffic")
            return None
    if not raw_registry:
        return None
    if _protocol_cache and _protocol_cache[0] == raw_registry:
        return _protocol_cache[1]
    try:
        registry = json.loads(raw_registry)
        protocol = EdgeProtocol(
            {
                str(device_id): base64.b64decode(str(public_key), validate=True)
                for device_id, public_key in registry.items()
            }
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        LOG.error("invalid CAMELOT_EDGE_PUBLIC_KEYS_JSON; refusing edge traffic")
        return None
    _protocol_cache = (raw_registry, protocol)
    return protocol


def edge_request_authorized(headers: dict, *, now: int | None = None) -> ValidationResult:
    encoded = headers.get(EDGE_ENVELOPE_HEADER, "")
    if not encoded:
        return ValidationResult(False, "missing-edge-envelope")
    protocol = _protocol_from_environment()
    if protocol is None:
        return ValidationResult(False, "edge-registry-unavailable")
    try:
        envelope = json.loads(base64.b64decode(encoded, validate=True))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ValidationResult(False, "malformed-edge-envelope")
    return protocol.validate_envelope(envelope, now=int(time.time()) if now is None else now)


class EdgeBusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json({"status": "ready", "listener": "tailnet-only"})
            return
        if self.path != "/v1/edge/snapshot":
            self.send_error(404)
            return
        result = edge_request_authorized(self.headers)
        if not result.ok:
            self._json({"error": result.reason}, 401)
            return
        signer = os.getenv("CAMELOT_EDGE_SNAPSHOT_SIGNING_KEY_B64", "")
        if not signer:
            self._json({"error": "edge-snapshot-signer-unavailable"}, 503)
            return
        try:
            envelope = json.loads(base64.b64decode(self.headers[EDGE_ENVELOPE_HEADER], validate=True))
            snapshot = issue_snapshot(
                device_id=str(envelope["device_id"]),
                now=int(time.time()),
                expires_at=int(time.time()) + 3600,
                signing_key_b64=signer,
            )
        except (KeyError, TypeError, ValueError):
            self._json({"error": "edge-snapshot-issuance-failed"}, 503)
            return
        self._json(snapshot)

    def do_POST(self) -> None:
        if self.path not in {"/v1/edge/receipts", "/v1/edge/outbox"}:
            self.send_error(404)
            return
        result = edge_request_authorized(self.headers)
        self._json({"status": "accepted"} if result.ok else {"error": result.reason}, 200 if result.ok else 401)

    def _json(self, value: dict[str, object], status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def run_server() -> None:
    bind_host = os.getenv("CAMELOT_EDGE_BUS_BIND_HOST", VPS_TAILSCALE_IP)
    if not is_tailnet_bind_host(bind_host):
        raise RuntimeError("CAMELOT_EDGE_BUS_BIND_HOST must be a 100.64.0.0/10 Tailnet address")
    server = HTTPServer((bind_host, EDGE_BUS_PORT), EdgeBusHandler)
    LOG.info("Camelot edge bus listening on %s:%s", bind_host, EDGE_BUS_PORT)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
