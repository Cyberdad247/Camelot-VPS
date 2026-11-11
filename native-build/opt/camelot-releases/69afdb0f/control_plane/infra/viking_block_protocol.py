# SPDX-License-Identifier: MIT

"""CAMELOT_OS/control_plane/viking_block_protocol.py.

PR #6A of NOTES_MNEMOSYNE_WIRING.md (2026-07-14, freebuff).

Implements the `viking://` block-level protocol — the foundation for the
Mnemosyne memory spine. PR #6B (`opennotebook_mem0_service`) and PR #7A
(`notebooklm_mcp_bridge`) will both consume this module.

URI grammar (4 forms):
  1. viking://appwrite.databases.{db_id}/collections.{col_id}/documents.{doc_id}
  2. viking://memory.block/{id}
  3. viking://memory.block/{id}/{sub}             # sub in {type, content}
  4. viking://memory.block/{id}?hmac={hexdigest}

HMAC envelope:
  * HMAC-SHA256 over a canonical JSON serialization of the block payload
    (all fields except `hmac`, sorted keys, no whitespace).
  * Replay-attack mitigation: `verify_block` enforces a default 300-second
    timestamp skew window against `datetime.now(timezone.utc)`. Override via
    the `max_skew_seconds` parameter.
  * Secret loaded from env `VIKING_BLOCK_HMAC_KEY`; never logged raw (mask-only).

Stdlib-only: hashlib, hmac, json, dataclasses, urllib.parse, datetime.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

# ── Constants ──────────────────────────────────────────────────────────────────
VIKING_SCHEME = "viking"
DEFAULT_SECRET_KEY_ENV = "VIKING_BLOCK_HMAC_KEY"
DEFAULT_MAX_SKEW_SECONDS = 300
CANONICAL_PROTOCOL_VERSION = 1


class VikingProtocolError(Exception):
    """Raised on `viking://` protocol or HMAC envelope failures."""


# ── Dataclass ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class VikingBlock:
    """A signed memory block on the Mnemosyne spine.

    `hmac` is the empty string before signing (sign_block returns a new
    instance with the digest populated).
    """

    id: str
    type: str  # e.g. "mnemosyne_block", "opennotebook_note", "mem0_memory"
    content: str
    source_agent: str  # canonical agent name (e.g. "sir_boris", "lady_mnemosyne")
    timestamp: str  # ISO8601 UTC string: "YYYY-MM-DDTHH:MM:SSZ"
    hmac: str = field(default="")


# ── URI parsing ────────────────────────────────────────────────────────────────
def parse_viking_uri(uri: str) -> dict[str, Any] | None:
    """Parse a viking:// URI into its constituent parts.

    Returns a dict with keys:
      * domain  -- "appwrite.databases" OR "memory.block"
      * path_segments -- list[str] (e.g. for appwrite: [db_id, col_id, doc_id])
      * sub_path -- "type" | "content" | None (memory.block sub-discover)
      * query_hmac -- str | None (when ?hmac= present)
      * raw -- the original uri string

    Returns None for malformed input or non-`viking://` scheme.
    """
    if not isinstance(uri, str) or not uri:
        return None
    parsed = urlparse(uri)
    if parsed.scheme != VIKING_SCHEME:
        return None
    # netloc holds "appwrite.databases" or "memory.block"
    domain = parsed.netloc
    if domain not in {"appwrite.databases", "memory.block"}:
        return None
    # path is like "/db_id/collections/col_id/documents/doc_id" or "/{id}"
    raw_path = parsed.path.strip("/")
    segments = [s for s in raw_path.split("/") if s] if raw_path else []
    sub_path: str | None = None
    if domain == "memory.block" and len(segments) == 2:
        # Form 3: viking://memory.block/{id}/{sub}
        if segments[1] in {"type", "content"}:
            sub_path = segments[1]
            segments = [segments[0]]
    query = parse_qs(parsed.query)
    hmac_values = query.get("hmac", [])
    return {
        "domain": domain,
        "path_segments": segments,
        "sub_path": sub_path,
        "query_hmac": hmac_values[0] if hmac_values else None,
        "raw": uri,
    }


# ── HMAC envelope ──────────────────────────────────────────────────────────────
def _resolve_secret(secret: str | None) -> str:
    """Resolve the HMAC secret. If `secret` is None, fall back to env var.

    Raises VikingProtocolError if no secret is configured.
    """
    if secret is not None:
        return secret
    env_secret = os.environ.get(DEFAULT_SECRET_KEY_ENV)
    if env_secret:
        return env_secret
    raise VikingProtocolError(
        f"HMAC secret not configured: pass `secret=` or set ${DEFAULT_SECRET_KEY_ENV} env var"
    )


def _now_iso8601_utc() -> str:
    """Return current UTC time as ISO8601 string with explicit Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_canonical_bytes(block: VikingBlock) -> bytes:
    """Bytes representation used as HMAC input.

    Includes an explicit `_v` field for forward compatibility, sorted JSON keys,
    no whitespace. Excludes the `hmac` field (its being signed, not input).
    """
    payload = {
        "_v": CANONICAL_PROTOCOL_VERSION,
        "id": block.id,
        "type": block.type,
        "content": block.content,
        "source_agent": block.source_agent,
        "timestamp": block.timestamp,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_block(block: VikingBlock, secret: str | None = None) -> VikingBlock:
    """Return a new VikingBlock with the `hmac` field populated."""
    signing_secret = _resolve_secret(secret)
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        to_canonical_bytes(block),
        hashlib.sha256,
    ).hexdigest()
    return VikingBlock(
        id=block.id,
        type=block.type,
        content=block.content,
        source_agent=block.source_agent,
        timestamp=block.timestamp,
        hmac=digest,
    )


def verify_block(
    block: VikingBlock,
    secret: str | None = None,
    max_skew_seconds: int = DEFAULT_MAX_SKEW_SECONDS,
) -> bool:
    """Verify a VikingBlock's HMAC + timestamp freshness.

    Returns True iff:
      1. `block.hmac` is non-empty AND matches `sign_block(...).hmac` for the same payload
      2. `block.timestamp` parses as ISO8601 UTC AND is within `max_skew_seconds`
         of current UTC time (default 300s = 5 min).
    """
    if not block.hmac:
        return False
    expected_digest = hmac.new(
        _resolve_secret(secret).encode("utf-8"),
        to_canonical_bytes(block),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(block.hmac, expected_digest):
        return False
    # Skew check (timestamp is signed so an attacker can't shift it)
    try:
        ts = datetime.strptime(block.timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    skew = abs((now - ts).total_seconds())
    return skew <= max_skew_seconds


# ── Serialization ──────────────────────────────────────────────────────────────
def to_json(block: VikingBlock) -> str:
    """Serialize a VikingBlock to JSON (preserves all fields including hmac)."""
    return json.dumps(asdict(block))


def from_json(serialized: str) -> VikingBlock:
    """Deserialize a JSON string back into a VikingBlock.

    Raises VikingProtocolError on malformed JSON or wrong shape.
    """
    try:
        data = json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise VikingProtocolError(f"invalid JSON: {exc}") from exc
    required = {"id", "type", "content", "source_agent", "timestamp"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise VikingProtocolError(
            f"VikingBlock JSON missing required fields: missing="
            f"{required - set(data) if isinstance(data, dict) else 'NOT_A_DICT'}"
        )
    return VikingBlock(
        id=data["id"],
        type=data["type"],
        content=data["content"],
        source_agent=data["source_agent"],
        timestamp=data["timestamp"],
        hmac=data.get("hmac", ""),
    )


__all__ = [
    "VIKING_SCHEME",
    "DEFAULT_SECRET_KEY_ENV",
    "DEFAULT_MAX_SKEW_SECONDS",
    "VikingProtocolError",
    "VikingBlock",
    "parse_viking_uri",
    "to_canonical_bytes",
    "sign_block",
    "verify_block",
    "to_json",
    "from_json",
    "_now_iso8601_utc",
]
