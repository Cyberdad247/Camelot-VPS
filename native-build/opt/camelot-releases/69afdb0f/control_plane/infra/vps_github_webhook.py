# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Camelot-VPS GitHub Continuous Deployment Webhook Server (`camelot-vps-webhook`)
==============================================================================
Listens on port :9000 (proxied via Caddy at `/webhook/camelot-vps`) for GitHub
`push` events from `https://github.com/Cyberdad247/Camelot-VPS.git`.

When a push event is verified via HMAC SHA-256 (`X-Hub-Signature-256`), this daemon:
1. Pulls latest changes from `camelot-vps/main` into `/opt/camelot-vps` or `apps/camelot-vps-hub`
2. Runs build script (`npm run build` / `bun run build`)
3. Syncs static build output to `/var/www/worldtree`
4. Emits a Sentinel Provenance Receipt
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("camelot.vps_webhook")


@dataclass
class WebhookDeliveryReceipt:
    delivery_id: str
    repository: str
    ref: str
    commit_sha: str
    verified: bool
    build_status: str  # "DEPLOYED" | "FAILED" | "UNAUTHORIZED"
    deployed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CamelotVPSWebhookHandler:
    """Zero-Trust GitHub Webhook Receiver for Camelot-VPS Sync."""

    def __init__(self, secret: Optional[str] = None, state_dir: Optional[Path] = None):
        # Fail closed: no hardcoded fallback. Resolve via explicit arg (tests),
        # GITHUB_WEBHOOK_SECRET env, or the SecretManager store — the edge VPS
        # bus holds the canonical value (see SecretManager / camelot-edge-bus).
        self.secret = secret or os.getenv("GITHUB_WEBHOOK_SECRET", "")
        if not self.secret:
            raise RuntimeError(
                "GITHUB_WEBHOOK_SECRET is not set — refusing to start with an open webhook. "
                "Set the env var or store it via `python -m control_plane.infra.secret_manager set GITHUB_WEBHOOK_SECRET`."
            )
        self.state_dir = state_dir or Path("03_VAULT/runtime_state/webhooks")
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def verify_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Validates HMAC SHA-256 signature from GitHub."""
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        
        expected_sig = "sha256=" + hmac.new(
            self.secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_sig, signature_header)

    def process_github_event(
        self,
        payload_bytes: bytes,
        signature_header: Optional[str],
        event_type: str = "push"
    ) -> WebhookDeliveryReceipt:
        """Processes incoming push event and triggers deployment."""
        delivery_id = f"del_{uuid.uuid4().hex[:8]}"
        
        # 1. Verify HMAC Signature
        if not self.verify_signature(payload_bytes, signature_header):
            LOG.warning(f"[WEBHOOK_DENIED] Invalid HMAC signature for delivery {delivery_id}")
            receipt = WebhookDeliveryReceipt(
                delivery_id=delivery_id,
                repository="unknown",
                ref="unknown",
                commit_sha="unknown",
                verified=False,
                build_status="UNAUTHORIZED"
            )
            self._save_receipt(receipt)
            return receipt

        # 2. Parse Payload
        data = json.loads(payload_bytes.decode("utf-8"))
        repo_name = data.get("repository", {}).get("full_name", "Cyberdad247/Camelot-VPS")
        ref = data.get("ref", "refs/heads/main")
        commit_sha = data.get("after", "unknown")

        # 3. Deployment: verified push -> ACCEPTED receipt; the real pipeline
        # (branch-gated, SHA-verified pull/build/sync) runs in a background
        # thread and FINALIZES this receipt afterwards. Without
        # CAMELOT_DEPLOY_ENABLED=1 the receipt stays ACCEPTED with an explicit
        # note — it never claims a deploy that did not happen.
        LOG.info(
            f"[WEBHOOK_SYNC] Verified push from {repo_name} ({ref} @ {commit_sha[:7]})"
        )

        receipt = WebhookDeliveryReceipt(
            delivery_id=delivery_id,
            repository=repo_name,
            ref=ref,
            commit_sha=commit_sha,
            verified=True,
            build_status="ACCEPTED",
        )

        self._save_receipt(receipt)

        if os.getenv("CAMELOT_DEPLOY_ENABLED", "") == "1":
            from control_plane.infra.webhook_deploy import spawn_deploy

            def _finalize(res) -> None:
                self._update_receipt(
                    receipt.delivery_id,
                    build_status=res.status,
                    deploy_steps=res.steps,
                    deploy_error=res.error,
                )
                LOG.info("[WEBHOOK_DEPLOY] %s -> %s", receipt.delivery_id, res.status)

            spawn_deploy(data, _finalize)
        else:
            self._update_receipt(
                receipt.delivery_id,
                deploy_error="deploy disabled (CAMELOT_DEPLOY_ENABLED not set)",
            )

        return receipt

    def _update_receipt(self, delivery_id: str, **fields) -> None:
        """Merge extra fields into a saved receipt (deploy finalization)."""
        target_file = self.state_dir / f"{delivery_id}.json"
        try:
            record = json.loads(target_file.read_text(encoding="utf-8"))
        except Exception:
            return
        record.update(fields)
        target_file.write_text(json.dumps(record, indent=2), encoding="utf-8")

    def _save_receipt(self, receipt: WebhookDeliveryReceipt) -> None:
        target_file = self.state_dir / f"{receipt.delivery_id}.json"
        target_file.write_text(json.dumps(asdict(receipt), indent=2), encoding="utf-8")
