"""Signed, replay-protected protocol primitives for the Android edge supervisor."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ALLOWED_ACTIONS = frozenset(
    {
        "health_probe",
        "tailscale_route_check",
        "collect_telemetry",
        "notify",
        "refresh_snapshot",
        "flush_outbox",
    }
)
SIGNED_FIELDS = ("device_id", "action", "payload", "issued_at", "expires_at", "nonce")


def canonical_envelope_bytes(envelope: Mapping[str, object]) -> bytes:
    """Encode exactly the signed request fields in a deterministic order."""
    body = {field: envelope[field] for field in SIGNED_FIELDS}
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str


class EdgeProtocol:
    """In-memory registry and nonce guard; enrollment supplies public keys at runtime."""

    def __init__(self, public_keys: Mapping[str, bytes]):
        self._devices = {device_id: Ed25519PublicKey.from_public_bytes(value) for device_id, value in public_keys.items()}
        self._seen_nonces: set[tuple[str, str]] = set()

    def validate_envelope(self, envelope: Mapping[str, object], *, now: int) -> ValidationResult:
        try:
            device_id = str(envelope["device_id"])
            nonce = str(envelope["nonce"])
            expires_at = int(envelope["expires_at"])
            issued_at = int(envelope["issued_at"])
            action = str(envelope["action"])
        except (KeyError, TypeError, ValueError):
            return ValidationResult(False, "malformed-envelope")
        public_key = self._devices.get(device_id)
        if public_key is None:
            return ValidationResult(False, "unregistered-device")
        if action not in ALLOWED_ACTIONS:
            return ValidationResult(False, "forbidden-action")
        if issued_at > now or expires_at <= now:
            return ValidationResult(False, "expired-envelope")
        if (device_id, nonce) in self._seen_nonces:
            return ValidationResult(False, "replayed-nonce")
        try:
            signature = base64.b64decode(str(envelope["signature"]), validate=True)
            public_key.verify(signature, canonical_envelope_bytes(envelope))
        except (InvalidSignature, KeyError, ValueError):
            return ValidationResult(False, "invalid-signature")
        self._seen_nonces.add((device_id, nonce))
        return ValidationResult(True, "accepted")


def issue_snapshot(*, device_id: str, now: int, expires_at: int, signing_key_b64: str) -> dict[str, object]:
    """Issue a canonical Rust-compatible snapshot using a runtime-only key."""
    raw_key = base64.b64decode(signing_key_b64, validate=True)
    signing_key = Ed25519PrivateKey.from_private_bytes(raw_key)
    snapshot: dict[str, object] = {
        "version": 1,
        "device_id": device_id,
        "issued_at": now,
        "expires_at": expires_at,
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "route": "tailnet_only",
    }
    canonical = json.dumps(snapshot, separators=(",", ":")).encode("utf-8")
    public_key = signing_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "snapshot": snapshot,
        "signature": base64.b64encode(signing_key.sign(canonical)).decode("ascii"),
        "public_key": base64.b64encode(public_key).decode("ascii"),
    }
