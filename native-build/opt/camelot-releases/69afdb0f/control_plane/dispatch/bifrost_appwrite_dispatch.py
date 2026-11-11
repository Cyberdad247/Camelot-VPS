# SPDX-License-Identifier: MIT

"""Bifrost → Appwrite signed-RPC dispatcher.

PR #3 of NOTES_MNEMOSYNE_WIRING.md (2026-07-14, freebuff).

Verifies the canonical Bifrost HMAC envelope
(`bifrost_gateway._sign` ↔ `apps/bifrost/src/security.ts`) against the
shared `WEBHOOK_SECRET`, then forwards intent-to-payload mappings to
`AppwriteClient`. Constant-time signature verification via
`hmac.compare_digest`.

Intent dispatch table:
  - `list_databases`     → AppwriteClient.list_databases      (AUTO tier eligible)
  - `upsert_document`    → AppwriteClient.upsert_document     (HUMAN_GATE; requires
                                                              payload["z3_pass"] == True)

Returns a structured result envelope `{ok, result, error}` so the Bifrost
ingress can route the response back to the calling knight.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from typing import Any

from control_plane.appwrite_client import AppwriteClient


def _sign(raw: str, secret: str) -> str:
    """HMAC-SHA256 hex digest; mirrors `bifrost_gateway._sign` and TS gateway security."""
    return hmac.new(
        secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _verify(raw: str, secret: str, signature: str) -> bool:
    if not secret or not signature:
        return False
    expected = _sign(raw, secret)
    return hmac.compare_digest(expected, str(signature))


def dispatch_to_appwrite(
    intent: str,
    payload: dict[str, Any] | None = None,
    signature: str = "",
) -> dict[str, Any]:
    """Verify Bifrost HMAC envelope, then dispatch to Appwrite.

    Args:
        intent: One of "list_databases" | "upsert_document".
        payload: Sorted-dicts raw JSON object that the signature was computed over.
        signature: HMAC-SHA256 hex digest; verified against `WEBHOOK_SECRET`.

    Returns:
        Structured envelope:
          {"ok": True,  "result": {...}} on success
          {"ok": False, "error": "<reason>"} on failure
    """
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret:
        return {"ok": False, "error": "WEBHOOK_SECRET not configured"}
    payload_dict: dict[str, Any] = payload or {}
    raw = json.dumps(payload_dict, sort_keys=True)
    if not _verify(raw, secret, signature):
        return {"ok": False, "error": "HMAC signature mismatch (Bifrost envelope rejected)"}

    client = AppwriteClient()

    if intent == "list_databases":
        rows = asyncio.run(client.list_databases())
        return {"ok": True, "result": {"databases": rows}}

    if intent == "upsert_document":
        z3_pass = bool(payload_dict.get("z3_pass", False))
        doc_id = str(payload_dict.get("document_id", "")).strip()
        data = payload_dict.get("data")
        if not doc_id:
            return {"ok": False, "error": "document_id required"}
        if not isinstance(data, dict):
            return {"ok": False, "error": "data must be a dict"}
        if not z3_pass:
            return {"ok": False, "error": "HUMAN_GATE: z3_pass=True required"}
        doc = asyncio.run(client.upsert_document(doc_id, data, z3_pass=True))
        return {"ok": True, "result": {"$id": doc.get("$id", doc_id), "data": doc}}

    return {"ok": False, "error": f"unknown intent: {intent!r}"}


__all__ = ["dispatch_to_appwrite", "_sign"]
