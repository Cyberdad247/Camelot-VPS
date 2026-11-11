# SPDX-License-Identifier: MIT

"""Verify and atomically consume PWA Cockpit approval grants."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from typing import Any

GRANT_CONTEXT = b"camelot-pwa-cockpit/approval-grant/v1:"
GRANT_CONTEXT_V2 = b"camelot-pwa-cockpit/approval-grant/v2:"
GRANT_VERSION = 1
GRANT_VERSION_V2 = 2
MAX_GRANT_LIFETIME_SECONDS = 90
_GRANT_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27}$")
_CONSUMED_DIR = Path(__file__).resolve().parents[1] / "03_VAULT" / "runtime_state" / "cockpit_consumed_grants"


class ApprovalGrantError(ValueError):
    """Raised when an approval grant is absent, invalid, expired, or replayed."""


def _decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc:
        raise ApprovalGrantError("approval grant encoding is invalid") from exc


def _integer(claims: dict[str, Any], name: str) -> int:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApprovalGrantError(f"approval grant {name} is invalid")
    return value


def verify_and_consume(grant: str, command: str, *, now: int | None = None, consumed_dir: Path | None = None) -> dict[str, Any]:
    key = os.environ.get("CAMELOT_COCKPIT_TOKEN", "").strip()
    if len(key) < 16:
        raise ApprovalGrantError("cockpit approval signing key is not configured")

    parts = grant.split(".")
    if len(parts) != 2:
        raise ApprovalGrantError("approval grant structure is invalid")
    payload, supplied_signature = parts
    supplied = _decode(supplied_signature)
    expected_v1 = hmac.new(key.encode("utf-8"), GRANT_CONTEXT + payload.encode("ascii"), hashlib.sha256).digest()
    expected_v2 = hmac.new(key.encode("utf-8"), GRANT_CONTEXT_V2 + payload.encode("ascii"), hashlib.sha256).digest()
    signed_version = 1 if hmac.compare_digest(supplied, expected_v1) else (2 if hmac.compare_digest(supplied, expected_v2) else 0)
    if signed_version == 0:
        raise ApprovalGrantError("approval grant signature is invalid")
    try:
        claims = json.loads(_decode(payload))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovalGrantError("approval grant payload is invalid") from exc
    if not isinstance(claims, dict) or claims.get("version") not in {GRANT_VERSION, GRANT_VERSION_V2}:
        raise ApprovalGrantError("approval grant version is invalid")
    version = claims["version"]
    if version != signed_version:
        raise ApprovalGrantError("approval grant signature is invalid")

    grant_id = claims.get("grantId")
    approval_id = claims.get("approvalId")
    if not isinstance(grant_id, str) or not _GRANT_ID.fullmatch(grant_id):
        raise ApprovalGrantError("approval grant id is invalid")
    if not isinstance(approval_id, str) or not approval_id.startswith("appr-"):
        raise ApprovalGrantError("approval id is invalid")

    issued_at = _integer(claims, "issuedAt")
    expires_at = _integer(claims, "expiresAt")
    current = int(time.time()) if now is None else now
    if issued_at > current + 5 or expires_at <= current:
        raise ApprovalGrantError("approval grant is not currently valid")
    if expires_at - issued_at != MAX_GRANT_LIFETIME_SECONDS:
        raise ApprovalGrantError("approval grant lifetime is invalid")

    command_digest = hashlib.sha256(command.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(str(claims.get("commandDigest", "")), command_digest):
        raise ApprovalGrantError("approval grant does not match the command")

    cartridge_digest = None
    target_root = None
    if version == GRANT_VERSION_V2:
        cartridge_digest = claims.get("cartridgeDigest")
        target_root = claims.get("targetRoot")
        if not isinstance(cartridge_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", cartridge_digest):
            raise ApprovalGrantError("approval grant cartridge digest is invalid")
        if target_root != ".":
            raise ApprovalGrantError("approval grant target root is invalid")

    target_dir = consumed_dir or _CONSUMED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    marker = target_dir / grant_id
    try:
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ApprovalGrantError("approval grant has already been consumed") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"approval_id": approval_id, "consumed_at": current}, handle)
        handle.flush()
        os.fsync(handle.fileno())

    return {
        "version": version,
        "grant_id": grant_id,
        "approval_id": approval_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "command_digest": command_digest,
        "cartridge_digest": cartridge_digest,
        "target_root": target_root,
    }
