# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — Honcho Self-Hosted Memory Bridge for Hermes
"""
HonchoBridge v1.0 — Self-Hosted L4 Metamemory & Dialectic State Engine
====================================================================
Integrates self-hosted Honcho (Plastic Labs / elkimek self-hosted) with
HERMES_PRIME and the Camelot WorldTree.

Provides cross-session user modeling, observation extraction, metamemory
retrieval, and dialectic context consolidation for Hermes Agent.

Topology:
  - Local Port: http://127.0.0.1:8000
  - Mesh VPS Hub: KVM563 Hermes Node, port 8000 (address from
    ``mesh_topology.HUB_TAILSCALE_IP``; not restated here so it cannot drift)
  - VFS Coordinate: vfs://worldtree/memory/honcho/
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from control_plane.infra.hermes_bridge import HermesBus
from control_plane.infra.mesh_topology import HUB_TAILSCALE_IP

log = logging.getLogger("HONCHO_BRIDGE")

_CAMELOT_ROOT = Path(__file__).resolve().parent.parent.parent
_CACHE_PATH = _CAMELOT_ROOT / "03_VAULT" / "runtime_state" / "honcho_memory_cache.json"

DEFAULT_HONCHO_URL = os.environ.get("HONCHO_BASE_URL", "http://127.0.0.1:8000")
VPS_HONCHO_URL = os.environ.get("HONCHO_VPS_URL", f"http://{HUB_TAILSCALE_IP}:8000")


class HonchoBridge:
    """
    Client and local coordinator for self-hosted Honcho memory engine.
    Fully integrated with Hermes Agent and WorldTree.
    """

    def __init__(self, base_url: Optional[str] = None, bus: Optional[HermesBus] = None):
        self.base_url = (base_url or DEFAULT_HONCHO_URL).rstrip("/")
        self.vps_url = VPS_HONCHO_URL.rstrip("/")
        self.bus = bus or HermesBus()
        self._ensure_cache()

    def _ensure_cache(self) -> None:
        if not _CACHE_PATH.exists():
            _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            initial = {
                "version": "1.0.0",
                "worldtree_root": "a0a4bfb9-e847-4c38-be39-7aee398f0795",
                "hermes_prime_uuid": "28f89cb6-5048-4b5d-9e94-376082d24744",
                "users": {},
                "sessions": {},
                "metamemory": {},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _CACHE_PATH.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def _load_cache(self) -> dict[str, Any]:
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"users": {}, "sessions": {}, "metamemory": {}}

    def _save_cache(self, data: dict[str, Any]) -> None:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        _CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _http_request(self, method: str, endpoint: str, payload: Optional[dict] = None) -> Tuple[bool, Any]:
        """Perform HTTP request to Honcho server with graceful fallback to local cache."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        data_bytes = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "Camelot-Hermes-Honcho/1.0"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                res = json.loads(body) if body else {}
                return True, res
        except Exception as err:
            log.debug("Honcho server not reachable at %s: %s (using resilient local cache)", url, err)
            return False, str(err)

    def check_health(self) -> dict[str, Any]:
        """Check live Honcho server health (local and VPS mesh)."""
        ok, res = self._http_request("GET", "health")
        return {
            "online": ok,
            "target": self.base_url,
            "vps_target": self.vps_url,
            "details": res if ok else "RUNNING_IN_LOCAL_FALLBACK_MODE",
            "vfs_mount": "vfs://worldtree/memory/honcho/",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_or_create_user(self, user_id: str, metadata: Optional[dict] = None) -> dict[str, Any]:
        """Get or create user profile in Honcho and WorldTree cache."""
        meta = metadata or {}
        meta.setdefault("created_by", "HERMES_PRIME")
        meta.setdefault("worldtree_anchor", "KING_ARTHUR_VIZION")

        ok, res = self._http_request("POST", "v1/users/", {"id": user_id, "metadata": meta})
        cache = self._load_cache()
        if user_id not in cache["users"]:
            cache["users"][user_id] = {
                "id": user_id,
                "metadata": meta,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_cache(cache)

        self.bus.publish("honcho.memory", {"event": "user_synced", "user_id": user_id})
        return res if ok else cache["users"][user_id]

    def get_or_create_session(self, session_id: str, user_id: str, metadata: Optional[dict] = None) -> dict[str, Any]:
        """Get or create conversation session in Honcho."""
        meta = metadata or {}
        ok, res = self._http_request(
            "POST", "v1/sessions/", {"id": session_id, "user_id": user_id, "metadata": meta}
        )

        cache = self._load_cache()
        if session_id not in cache["sessions"]:
            cache["sessions"][session_id] = {
                "id": session_id,
                "user_id": user_id,
                "metadata": meta,
                "messages": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_cache(cache)

        self.bus.publish("honcho.memory", {"event": "session_synced", "session_id": session_id, "user_id": user_id})
        return res if ok else cache["sessions"][session_id]

    def add_message(
        self, session_id: str, user_id: str, role: str, content: str, metadata: Optional[dict] = None
    ) -> dict[str, Any]:
        """Ingest conversation message into Honcho for background dialectic derivation."""
        msg_payload = {
            "user_id": user_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ok, res = self._http_request("POST", f"v1/sessions/{session_id}/messages/", msg_payload)

        cache = self._load_cache()
        sess = cache["sessions"].setdefault(
            session_id, {"id": session_id, "user_id": user_id, "messages": []}
        )
        sess["messages"].append(msg_payload)
        self._save_cache(cache)

        self.bus.publish(
            "honcho.memory",
            {
                "event": "message_ingested",
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "tokens": len(content.split()),
            },
        )
        return res if ok else msg_payload

    def query_context(self, session_id: str, query: str, max_tokens: int = 4000) -> dict[str, Any]:
        """Query Honcho memory and dialectic context for active session."""
        ok, res = self._http_request(
            "POST",
            f"v1/sessions/{session_id}/context/",
            {"query": query, "max_tokens": max_tokens},
        )
        if ok:
            return res

        cache = self._load_cache()
        sess = cache["sessions"].get(session_id, {})
        messages = sess.get("messages", [])
        return {
            "session_id": session_id,
            "query": query,
            "retrieved_context": [m["content"] for m in messages[-5:]],
            "mode": "LOCAL_CACHE_RECALL",
            "worldtree_status": "VFS_TETHERED",
        }

    def get_metamemory(self, user_id: str) -> dict[str, Any]:
        """Retrieve consolidated user metamemory / theory-of-mind observations."""
        ok, res = self._http_request("GET", f"v1/users/{user_id}/metamemory/")
        if ok:
            return res

        cache = self._load_cache()
        user_meta = cache.get("metamemory", {}).get(user_id, {
            "user_id": user_id,
            "core_identity": "King Arthur (VaShawn O. Head / Vizion)",
            "role": "Sovereign Operator",
            "invariants": [
                "Rule 7 Hotpath Purity (0% Python/Node in Hotpath)",
                "Father's Camelot Compass (Absolute Truth)",
                "Excalibur Command Center (S26 Ultra)",
                "VPS Hub KVM563 (Hermes Control Plane)",
            ],
            "observations": [
                "Prefers concise, mathematically sound engineering reports.",
                "Enforces strict test-driven development and zero-regression gates.",
                "Directs 39 Knights of the Round Table through ANYA_OMEGA and SIR_KAY.",
            ],
            "source": "WORLDTREE_VFS_ANCHOR",
        })
        return user_meta


# Global singleton
honcho_bridge = HonchoBridge()
