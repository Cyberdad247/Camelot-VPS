# SPDX-License-Identifier: MIT

"""
HTTP daemon wrapper for DistributedKnowledgeSync.

Replaces the simulated ``_send_replication`` (which faked an ack after an
asyncio.sleep without contacting the peer) with a real HTTP POST to the peer's
``/sync/replicate`` endpoint, which feeds ``handle_replication_from_peer``.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, List

from control_plane.distributed_knowledge_sync import (
    DistributedKnowledgeSync,
    ReplicationAck,
    SyncEvent,
    SyncPhase,
)
from control_plane.observability import traced_op

from .http_daemon import HttpDaemon, call_async, post_json


def _event_to_payload(event: SyncEvent) -> dict:
    return {
        "event_id": event.event_id,
        "key": event.key,
        "value": event.value,
        "source_node": event.source_node,
        "timestamp": event.timestamp,
        "phase": event.phase.value,
    }


def _event_from_payload(body: dict) -> SyncEvent:
    return SyncEvent(
        event_id=body["event_id"],
        key=body["key"],
        value=body["value"],
        source_node=body["source_node"],
        timestamp=float(body["timestamp"]),
        phase=SyncPhase(body.get("phase", SyncPhase.PEER_REPLICATION.value)),
    )


class HttpSyncNode(DistributedKnowledgeSync):
    """DistributedKnowledgeSync that replicates to peers over real HTTP."""

    def __init__(
        self,
        node_id: str,
        peers: List[str],
        peer_addrs: Dict[str, str],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__(node_id, peers)
        self.peer_addrs = peer_addrs
        self._loop = loop

    async def _send_replication(self, peer: str, event: SyncEvent) -> ReplicationAck:
        """Override: actually POST the event to the peer and await its ack."""
        base = self.peer_addrs.get(peer)
        ok = False
        if base:
            url = f"{base}/sync/replicate"
            res = await self._loop.run_in_executor(
                None, post_json, url, {"event": _event_to_payload(event)}
            )
            ok = bool(res) and res.get("ok", False)

        ack = ReplicationAck(
            node_id=peer,
            event_id=event.event_id,
            timestamp=time.time(),
            success=ok,
            error=None if ok else "peer unreachable",
        )
        self.acks.setdefault(event.event_id, []).append(ack)
        if ok:
            event.replicated_to.add(peer)
        return ack


def register_routes(daemon: HttpDaemon, node: HttpSyncNode) -> None:
    def sync_write(body: dict, loop):
        key = body["key"]
        value = body["value"]
        event_id = call_async(loop, node.write_to_l1(key, value))
        return 200, {"event_id": event_id}

    def sync_replicate(body: dict, loop):
        event = _event_from_payload(body["event"])
        ok = call_async(loop, node.handle_replication_from_peer(event, event.source_node))
        return 200, {"ok": bool(ok)}

    def sync_status(body: dict, loop):
        return 200, call_async(loop, node.get_sync_status())

    daemon.route("POST", "/sync/write", traced_op("sync.write")(sync_write))
    daemon.route("POST", "/sync/replicate", traced_op("sync.replicate")(sync_replicate))
    daemon.route("GET", "/sync/status", sync_status)
