# Cloudbrain Patches — Index

Patches for the Hermes VPS cloudbrain handoff stack. Each patch is a **PATCH SPEC**
written against the VPS files as of 2026-09-22; neither source file was available locally
when the spec was authored, so every edit is keyed to anchor descriptions and carries
**MUST-VERIFY** assumptions that must be confirmed against the live VPS sources before
applying. Do not apply blind.

Full specs: `ANYA_ACK_PATCH.md`, `ANYA_PENDING_PATCH.md`.

## Apply order

1. **E2 — Verify assumptions against live sources.** Confirm every MUST-VERIFY item below
   against the real `/opt/data/cloudbrain/handoff/mesh_broker.py` and
   `/opt/data/cloudbrain/handoff/anya_omega.py` on the VPS. Adapt variable/anchor names to
   what is actually there.
2. **E3 — Apply the ack patch** (`ANYA_ACK_PATCH.md` → `anya_omega.py`).
3. **E4 — Apply the pending patch** (`ANYA_PENDING_PATCH.md` → `mesh_broker.py`).

E3 must precede E4's full verification: the pending endpoint's `pending_count` only moves
once acks flow, so V-MESH-001's pending-drain proof depends on the ack fix being live.

## Rollback

Per patch, before editing on the VPS:

```
cp /opt/data/cloudbrain/handoff/<file>.py /opt/data/cloudbrain/handoff/<file>.py.bak-<UTC>
```

`<UTC>` is a timestamp such as `2026-09-22T180000Z`. To roll back, copy the `.bak-<UTC>`
file back over the live file and restart the service via the supervisor
`cb-supervise.sh` (the same supervisor used by the `cb-mesh-broker-watch` and
`cb-anya-watch` keep-alive crons). Rollback returns the previous defect with no data
migration: pending accumulation resumes (ack patch reverted) or the endpoint reports
XLEN-as-pending again (pending patch reverted). Note in the rollback log that any
dashboards built on `pending_count` will need reverting too.

---

## Patch 1 — ANYA_ACK_PATCH.md

- **Target VPS file:** `/opt/data/cloudbrain/handoff/anya_omega.py`
- **Scope:** Anya Omega service only (`127.0.0.1:8003`); no broker changes.

**Defect:** Anya's background ingress loop claims messages from the broker queue
`anya-omega` and routes / quarantines / dead-letters them, but never calls the broker's
`POST /handoff/ack`. Redis consumer-group pending entries therefore accumulate forever
for group `mesh-brokers`; `XPENDING` grows without bound, and crash-recovery has no
trustworthy "done" marker.

**What it changes (edits ACK-1..ACK-4):**

- **ACK-1** — module state: imports (`urllib.request`, `urllib.error`, `json`, `logging`,
  `collections.deque`), ack configuration (`BROKER_BASE`, `INGRESS_QUEUE`,
  `ACK_TIMEOUT_S = 5.0`, `ACK_MAX_RETRIES = 5`), and in-memory retry bookkeeping
  (`_ack_attempts`, `_acked_recent`). Retry state is intentionally in-memory, not durable.
- **ACK-2** — helper `_broker_ack(queue, msg_id)`: POSTs `{"queue": queue, "id": msg_id}`
  to `/handoff/ack`, returns True on HTTP 2xx, never raises (all exceptions caught and
  logged). Safe to retry: broker-side XACK is idempotent.
- **ACK-3** — the ack call site inside the ingress loop, inserted strictly **after** the
  durability point (route/quarantine/dead-letter publish issued, decision appended to
  `handoffs.log`, in-memory state mutation complete). Runs for routed, quarantined, AND
  dead-lettered messages alike; held messages (unknown types, fail-closed) are NOT acked.
  Failed acks retry with bounded budget; exhaustion logs an `ack-orphan` marker for the
  operator (`XACK mesh:handoff:anya-omega mesh-brokers <id>`).
- **ACK-4 (recommended)** — digest dedupe against redelivery: a `_seen_digests` deque
  suppresses duplicate routing effects when a never-acked message is reclaimed and
  redelivered after a crash, while still falling through to ACK-3 so the pending entry
  is finally cleared (exactly-once effect).

**MUST-VERIFY assumptions** (confirm against live `anya_omega.py` / `mesh_broker.py`):

1. **Ack endpoint path and field names.** Assumed `POST /handoff/ack` with JSON fields
   `"queue"` and `"id"` (`{"queue": "anya-omega", "id": "1726...-0"}`, mapped broker-side
   to `XACK mesh:handoff:<queue> mesh-brokers <id>`). Field names may instead be
   `msg_id`, `message_id`, or require a `consumer` name.
2. **Consumer-group name.** Assumed `mesh-brokers` (from deployment notes). Needed by the
   operator verifying V-MESH-001 with `XPENDING`.
3. **Broker base URL.** Assumed `http://127.0.0.1:8002`. Reuse the module's existing
   broker base-URL constant if one exists; do not introduce a second one.
4. **Ingress loop claim mechanics.** Assumed the loop claims one message at a time and
   exposes the stream message id as a variable (called `msg_id` in the spec).
5. **Durability point.** Assumed there is a single point per iteration where the routing
   decision is appended to `handoffs.log`; the ACK-3 call must be inserted immediately
   after it, reachable from all three terminal branches (routed / quarantined /
   dead-lettered).
6. **Existing imports/logging.** Assumed `logging` is already configured; the patch reuses
   the module logger if one exists, else creates `logging.getLogger("anya-omega")`.
7. **Timeout behavior.** Assumed a 5 s ack timeout is acceptable on loopback; verify no
   stricter loop-timing watchdog exists.

**Gates:** CB-040 (primary), CB-041, V-MESH-001 (XPENDING → 0 after full claim→route→ack
cycle), V-MESH-002, V-MESH-005 (kill mid-processing → redelivery suppressed as duplicate
→ final ack clears pending).

---

## Patch 2 — ANYA_PENDING_PATCH.md

- **Target VPS file:** `/opt/data/cloudbrain/handoff/mesh_broker.py`
- **Scope:** the `GET /handoff/pending` handler only; no Anya changes.

**Defect:** `GET /handoff/pending` currently reports `XLEN` (total stream length — every
message ever published, including long-since-acked ones) as if it were the pending count.
The real pending state lives in the consumer group (`XPENDING mesh:handoff:<queue>
mesh-brokers`). After the ack fix lands there would be no endpoint proving pending
drained, and crash-recovery triage (how many unacked messages are stuck, how old, which
consumer holds them) is impossible from the API.

**What it changes (edits PEND-1..PEND-3):**

- **PEND-1** — replaces the XLEN-based pending computation with true consumer-group
  state: summary-form `XPENDING <stream> <group>` (one round trip), parsed into a new
  JSON contract: `queue`, `stream`, `group` (`mesh-brokers`), `group_exists`
  (`false` on NOGROUP — valid state, HTTP 200), `pending_count`, `oldest_entry_id`,
  `oldest_age_seconds` (derived from the stream-id timestamp), `oldest_idle_seconds`
  and `oldest_delivery_attempts` (detail-form `XPENDING <stream> <group> - + 1`, only
  when `pending_count > 0`; oldest entry only), `per_consumer` map, and `stream_length`
  (`XLEN`, kept under a truthful name). The endpoint is read-only observability: no
  `IDLE` filtering, no `XCLAIM`.
- **PEND-2** — the oldest-entry detail block (idle time + delivery attempts); folded into
  PEND-1 inline, splittable into a second commit if preferred.
- **PEND-3 (optional, default: omit)** — deprecated `pending` alias mapping the old field
  name to the new truthful `pending_count` with a deprecation note; apply only if a real
  consumer still reads `.pending`.

**Breaking change:** the old contract is ASSUMED to be `{"queue": ..., "pending": <XLEN
int>}` (must-verify §6.4). If so, this patch is breaking for any client reading
`.pending`: that field previously meant stream length. Default recommendation is a clean
break (omit PEND-3); do NOT alias `pending` to XLEN — that perpetuates the bug.

**MUST-VERIFY assumptions** (confirm against live `mesh_broker.py`):

1. **Redis helper.** Assumed a module-level `_redis_cmd(*args)` returning parsed RESP
   replies. Verify the real name, reply parsing (decoded str vs bytes), and the
   exception type/message for NOGROUP (assumed message contains `"NOGROUP"`).
2. **Queue-name derivation.** Assumed stream = `f"mesh:handoff:{queue}"` with `queue`
   from the query string. Reuse the handler's exact existing derivation.
3. **Consumer-group name.** Assumed `mesh-brokers`. Confirm against the `XGROUP CREATE`
   / `XREADGROUP` call sites in the broker.
4. **Old response contract.** Assumed `{"queue": ..., "pending": <XLEN>}`. Read the
   current handler to document the real breaking delta before applying.
5. **Handler return style.** Assumed a `_json_response(dict)`-style builder and a 500
   path for raised exceptions. Match the file's real conventions.
6. **`time` / logging availability.** Assumed importable (stdlib-only broker, safe); reuse
   the module's existing imports where present.

**Gates:** CB-041 (primary), CB-040, V-MESH-001 (`pending_count` N → 0 matching
`XPENDING`), V-MESH-002 (counts match `redis-cli` exactly; `stream_length` matches
`XLEN`), V-MESH-005 (stuck consumer visible via growing `oldest_idle_seconds` and
incrementing `oldest_delivery_attempts`).
