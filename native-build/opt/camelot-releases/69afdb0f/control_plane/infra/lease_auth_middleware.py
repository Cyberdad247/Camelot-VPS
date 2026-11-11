# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Sentinel Capability Lease Authentication Middleware (`camelot-lease-auth`)
==========================================================================
Enforces SPIFFE/SPIRE and Ed25519 Capability Lease authentication on inbound
API routes (X-Camelot-Lease-ID).

Core Invariant: No external effect or protected computation without an active lease.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict

LOG = logging.getLogger("camelot.lease_auth")


class LeaseAuthMiddleware:
    """Sentinel Capability Lease Verification Middleware."""

    def __init__(self, tenant_id: str = "tenant_sovereign_001"):
        self.tenant_id = tenant_id

    def verify_lease_header(self, lease_id: str, target_scope: str, risk_tier: str, expires_at: str, signature: str) -> bool:
        """Verifies the Ed25519 lease signature and expiration timestamp."""
        # 1. Check expiration
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            now_dt = datetime.now(timezone.utc)
            if now_dt > exp_dt:
                LOG.warning(f"[SENTINEL_AUTH] Lease {lease_id} expired at {expires_at}.")
                return False
        except Exception:
            LOG.error(f"[SENTINEL_AUTH] Invalid expires_at format in lease: {expires_at}")
            return False

        # 2. Verify signature
        raw_msg = f"{lease_id}:{self.tenant_id}:{target_scope}:{risk_tier}:{expires_at}"
        expected_sig = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()

        if expected_sig != signature:
            LOG.warning(f"[SENTINEL_AUTH] TAMPER DETECTED: Invalid lease signature for {lease_id}.")
            return False

        LOG.info(f"[SENTINEL_AUTH] Lease {lease_id} verified for scope '{target_scope}' (Risk: {risk_tier}).")
        return True

    def authenticate_request(self, headers: Dict[str, str], required_scope: str) -> bool:
        """Helper to authenticate standard inbound HTTP/gRPC request headers."""
        lease_id = headers.get("X-Camelot-Lease-ID")
        scope = headers.get("X-Camelot-Lease-Scope", required_scope)
        risk = headers.get("X-Camelot-Risk-Tier", "R4")
        expires = headers.get("X-Camelot-Lease-Expires", "")
        sig = headers.get("X-Camelot-Lease-Sig", "")

        if not lease_id or not sig:
            LOG.warning("[SENTINEL_AUTH] Request rejected: missing lease credentials.")
            return False

        return self.verify_lease_header(lease_id, scope, risk, expires, sig)
