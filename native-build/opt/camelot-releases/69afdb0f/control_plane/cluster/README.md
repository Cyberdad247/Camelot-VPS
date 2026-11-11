# CAMELOT-OS Cluster Daemon Layer

This package turns the in-process service *algorithms* into real, long-running
HTTP **daemons** so an actual multi-node cluster can form — locally over
loopback for validation, or one-per-machine in production.

## Why this exists

The original `control_plane/distributed_*` modules are excellent algorithm
implementations, but their `__main__` entrypoints run **demos that exit** — they
never bind a port or talk over a network (`_send_message` put messages on a dead
local queue; `_send_replication` faked acks with `asyncio.sleep`). The deploy
scripts' `python3 -m control_plane.<x>` therefore could not produce a live,
`curl`-able cluster. This layer supplies the missing daemon/transport piece.

The originals are **subclassed, never modified** — their demos still pass.

## Layout

| File | Role |
|------|------|
| `http_daemon.py` | stdlib-only HTTP server + asyncio bridge + JSON client (no Flask/Docker) |
| `consensus_daemon.py` | `DistributedConsensus` with HTTP peer transport (`/consensus/*`) |
| `sync_daemon.py` | `DistributedKnowledgeSync` with real replication (`/sync/*`) |
| `agents_daemon.py` | `DistributedAgentRegistry` with cross-node gossip (`/agents/*`) |
| `metrics_daemon.py` | keeps `MetricsCollector` alive + scrapes nodes (`/metrics`) |
| `node_daemon.py` | one process = one node hosting all services + `/health` |
| `launch_local_cluster.py` | spawns a 3-node cluster on loopback and self-validates |

## Quick start (local validation)

```bash
# From repo root. Spawns node_1/2/3 (8443/8444/8445) + metrics (8000),
# runs consensus/sync/agents/metrics checks, prints PASS/FAIL, tears down.
python -m control_plane.cluster.launch_local_cluster

# Leave it running so you can curl it:
python -m control_plane.cluster.launch_local_cluster --keep
curl http://127.0.0.1:8443/health
curl http://127.0.0.1:8443/consensus/status
curl http://127.0.0.1:8000/metrics
```

## Endpoints (per node)

- `GET  /health` — node + service health
- `GET  /consensus/status` · `POST /consensus/propose` · `POST /consensus/message`
- `GET  /sync/status` · `POST /sync/write` · `POST /sync/replicate`
- `GET  /agents/status` · `POST /agents/register` · `POST /agents/gossip`

## Running a real node (production / bare metal)

One process per machine; point each at its peers:

```bash
python -m control_plane.cluster.node_daemon \
    --node-id node_1 --host 0.0.0.0 --port 8443 \
    --peers "node_2=http://192.168.1.11:8443,node_3=http://192.168.1.12:8443" \
    --leader
```

> Note: ports here are the daemon's HTTP port. For a single box (local
> validation) nodes use distinct ports (8443/8444/8445) because Windows loopback
> doesn't alias `127.0.0.x`. On separate machines every node can use `:8443`.

## Known limitations (honest)

- **Leader is static** (`--leader`). Raft-style election in the original is a
  stub; this layer designates the leader rather than electing one.
- **Signatures are placeholder** (SHA-256, not Ed25519) — inherited from the
  algorithm module.
- **L1/L1.5/L2 are in-memory simulations** (no real Redis/Qdrant/CloudBrain);
  this validates the *sync protocol*, not durable storage.
- Designed and tested for loopback validation. Production hardening (TLS between
  nodes, auth on endpoints, persistence) is future work.
