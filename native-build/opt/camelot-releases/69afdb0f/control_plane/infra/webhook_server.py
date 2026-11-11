# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""HTTP server wrapper for the Camelot-VPS GitHub webhook receiver.

Thin, fail-closed stdlib server that fronts
`control_plane.infra.vps_github_webhook.CamelotVPSWebhookHandler`.

Design constraints (do not relax):
- Binds 127.0.0.1 only. nginx is the sole public ingress and proxies
  /webhook/* to this port (see infra/nginx/webhook.conf and
  docs/HITL_VPS_REMEDIATION_PLAN.md R3).
- Refuses to start without GITHUB_WEBHOOK_SECRET (fail closed, per the
  handler's own contract — an open webhook is worse than a dead one).
- Never logs payload bodies or signature values; receipts land in
  03_VAULT/runtime_state/webhooks/ via the handler's own state_dir.

Usage (hub): python3 control_plane/infra/webhook_server.py [--port 9000]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Allow direct execution from a checkout (hub units run from /opt/camelot-ecosystem).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from control_plane.infra.vps_github_webhook import CamelotVPSWebhookHandler  # noqa: E402

LOG = logging.getLogger("camelot.vps_webhook_server")
DEFAULT_PORT = 9000


def build_handler(receiver: CamelotVPSWebhookHandler):
    class WebhookHTTPRequestHandler(BaseHTTPRequestHandler):
        """Routes /webhook/* to the zero-trust handler; /webhook/health for probes."""

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if self.path == "/webhook/health":
                body = json.dumps({"status": "ok"}).encode("utf-8")
                self._respond(200, body)
            else:
                self._respond(404, b'{"error": "not found"}')

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            if not self.path.startswith("/webhook/"):
                self._respond(404, b'{"error": "not found"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._respond(400, b'{"error": "bad content-length"}')
                return
            if length <= 0 or length > 25 * 1024 * 1024:
                self._respond(400, b'{"error": "invalid body size"}')
                return
            payload = self.rfile.read(length)
            signature = self.headers.get("X-Hub-Signature-256")
            event_type = self.headers.get("X-GitHub-Event", "push")
            try:
                receipt = receiver.process_github_event(payload, signature, event_type=event_type)
            except json.JSONDecodeError:
                LOG.warning("malformed JSON body (unverified)")
                self._respond(400, b'{"error": "malformed json"}')
                return
            body = json.dumps(
                {
                    "delivery_id": receipt.delivery_id,
                    "verified": receipt.verified,
                    "build_status": receipt.build_status,
                    "commit_sha": receipt.commit_sha,
                }
            ).encode("utf-8")
            # 401 on unverified: nginx still returns the receipt, GitHub marks
            # the delivery failed, and the receipt file preserves the evidence.
            self._respond(200 if receipt.verified else 401, body)

        def _respond(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:  # journal-friendly, no payloads
            LOG.info("%s - %s", self.address_string(), fmt % args)

    return WebhookHTTPRequestHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Camelot-VPS webhook receiver (:9000, loopback only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1", help="bind address; keep loopback behind nginx")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        receiver = CamelotVPSWebhookHandler()
    except RuntimeError as exc:
        LOG.error("refusing to start: %s", exc)
        return 2

    server = ThreadingHTTPServer((args.host, args.port), build_handler(receiver))
    LOG.info("webhook receiver listening on %s:%s (loopback plane)", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
