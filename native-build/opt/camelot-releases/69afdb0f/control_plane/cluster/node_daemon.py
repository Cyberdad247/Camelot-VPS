# SPDX-License-Identifier: MIT

"""
CAMELOT-OS node daemon — one process hosting all services for a single node.

Runs consensus + knowledge-sync + agent-registry behind a single HTTP server on
one port, with the asyncio event loop in the main thread. Designed so three of
these (on 127.0.0.1:8443/8444/8445) form a real cluster over loopback for local
validation, and the same code runs one-per-machine in production.

Usage:
  python -m control_plane.cluster.node_daemon \
      --node-id node_1 --host 127.0.0.1 --port 8443 \
      --peers "node_2=http://127.0.0.1:8444,node_3=http://127.0.0.1:8445" \
      --leader
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Dict, List, Tuple

from control_plane.observability import start_metrics_server

from .agents_daemon import HttpAgentsNode
from .agents_daemon import register_routes as register_agents
from .consensus_daemon import HttpConsensusNode
from .consensus_daemon import register_routes as register_consensus
from .http_daemon import HttpDaemon
from .sync_daemon import HttpSyncNode
from .sync_daemon import register_routes as register_sync


def parse_peers(spec: str) -> Tuple[List[str], Dict[str, str]]:
    """'node_2=http://h:8444,node_3=http://h:8445' -> (ids, {id: url})."""
    peers: List[str] = []
    addrs: Dict[str, str] = {}
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        node_id, _, url = part.partition("=")
        node_id = node_id.strip()
        url = url.strip().rstrip("/")
        if node_id and url:
            peers.append(node_id)
            addrs[node_id] = url
    return peers, addrs


def build(node_id: str, host: str, port: int, peers_spec: str, is_leader: bool):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    peers, peer_addrs = parse_peers(peers_spec)
    quorum = (len(peers) + 1) // 2 + 1  # majority of cluster (3 -> 2)

    consensus = HttpConsensusNode(node_id, peers, peer_addrs, loop, quorum=quorum, is_leader=is_leader)
    sync = HttpSyncNode(node_id, peers, peer_addrs, loop)
    agents = HttpAgentsNode(node_id, peers, peer_addrs, loop)

    daemon = HttpDaemon(host, port, loop)
    register_consensus(daemon, consensus)
    register_sync(daemon, sync)
    register_agents(daemon, agents)

    started = time.time()

    def health(_body: dict, _loop):
        return 200, {
            "status": "healthy",
            "node_id": node_id,
            "role": consensus.role.value,
            "uptime_seconds": round(time.time() - started, 1),
            "services": {
                "consensus": "up",
                "sync": "up",
                "agents": "up",
            },
            "cluster_size": consensus.cluster_size,
            "quorum": consensus.quorum,
        }

    daemon.route("GET", "/health", health)
    return loop, daemon, consensus, sync, agents


def main() -> None:
    ap = argparse.ArgumentParser(description="CAMELOT-OS node daemon")
    ap.add_argument("--node-id", required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--peers", default="", help="id=url,id=url")
    ap.add_argument("--leader", action="store_true")
    args = ap.parse_args()

    loop, daemon, consensus, sync, agents = build(
        args.node_id, args.host, args.port, args.peers, args.leader
    )

    # Seed two local agents per node so the registry has something to gossip.
    agents.register_local_agent(f"{args.node_id}_forge", args.port + 100, "forge", {"dispatch", "execution"})
    agents.register_local_agent(f"{args.node_id}_coord", args.port + 200, "coordinator", {"routing"})

    daemon.start()
    print(f"[{args.node_id}] listening on http://{args.host}:{args.port} "
          f"(role={consensus.role.value}, peers={list(consensus.peers)})", flush=True)

    # Native Prometheus exposition of this node's operation metrics (no Docker).
    metrics_port = args.port + 300
    if start_metrics_server(metrics_port):
        print(f"[{args.node_id}] /metrics on http://{args.host}:{metrics_port}", flush=True)

    # Exchange Ed25519 public keys with peers, then gossip — both on the loop.
    loop.call_soon(lambda: loop.create_task(consensus.bootstrap_keys()))
    loop.call_soon(lambda: loop.create_task(agents.gossip_loop(interval=2.0)))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        daemon.stop()


if __name__ == "__main__":
    main()
