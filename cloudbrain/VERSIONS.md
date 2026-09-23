# Cloudbrain Component Versions

As of **2026-09-22**. Versions verified live on the Hermes VPS on that date.

## Data / memory plane

| Component | Version | Endpoint |
|---|---|---|
| Redis | 8.2.1 | 127.0.0.1:6379 |
| Qdrant | 1.19.1 | 127.0.0.1:6333 / 127.0.0.1:6334 |
| SurrealDB | 2.6.5 | 127.0.0.1:8000 |
| OpenViking | 0.4.21 | 127.0.0.1:1933 |

## Handoff / mesh plane

| Component | Version / file | Endpoint |
|---|---|---|
| Hermes Agent | v0.20.5 | gateway |
| Mesh broker | `/opt/data/cloudbrain/handoff/mesh_broker.py` (stdlib-only) | 127.0.0.1:8002 |
| Anya Omega | `/opt/data/cloudbrain/handoff/anya_omega.py` | 127.0.0.1:8003 |

Symbollect v1 (`/opt/data/cloudbrain/handoff/symbollect.py`, stdlib-only) is the packet
language used by Anya Omega for token-reduced typed handoff messages.

## Patch-spec currency note

The patch specs in `patches/` (`ANYA_ACK_PATCH.md`, `ANYA_PENDING_PATCH.md`) were written
against the VPS files as they stood on **2026-09-22** — the sources were not available
locally, so all edits are keyed to anchor descriptions with MUST-VERIFY assumptions. Before
applying either patch, re-confirm every MUST-VERIFY assumption in `patches/PATCHES.md`
against the live VPS sources; the files may have changed since the specs were authored.
