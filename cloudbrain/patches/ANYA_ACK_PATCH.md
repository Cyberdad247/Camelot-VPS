# ANYA_ACK_PATCH — Anya Omega ingress loop: acknowledge claimed broker messages

**Status:** PATCH SPEC — do NOT apply blind. Anya Omega's source (`anya_omega.py`) was not
available locally; every edit below is keyed to an *anchor description* of the ingress loop's
known structure. The applier must locate each anchor in the real file on the VPS and adapt
variable names. All assumptions are listed in §5 and marked **MUST-VERIFY**.

**Scope:** `/opt/data/cloudbrain/handoff/anya_omega.py` ONLY. No broker changes here.
Stdlib only: `urllib.request`, `urllib.error`, `json`, `time`, `logging`, `collections`.

**Target service:** Anya Omega on `127.0.0.1:8003`, kept alive by cron `cb-anya-watch`.

---

## 1. Defect

Anya's background ingress loop claims messages from the broker queue `anya-omega` (via the
mesh broker's claim path, `GET /handoff/next` or equivalent) and routes / quarantines /
dead-letters them — but never calls the broker's `POST /handoff/ack`. Redis consumer-group
pending entries therefore accumulate forever for group `mesh-brokers`, `XPENDING` grows
without bound, and crash-recovery has no trustworthy "done" marker.

## 2. Ordering guarantee (the one rule this patch enforces)

**Ack only AFTER the message is durably handled**, i.e. after all three of:

1. the route / quarantine / dead-letter publish has been issued to the destination broker queue, **and**
2. the decision has been appended to `/opt/data/cloudbrain/data/anya-omega/handoffs.log`, **and**
3. any in-memory registry/state mutation for this message is complete.

Acking before (2) would lose the audit trail on crash. Acking before (1) would lose the
handoff on crash. The ack call site in Edit ACK-3 sits strictly after the durability point.

## 3. Task / verification-gate mapping

| Item | Relevance |
|---|---|
| **CB-040** | Primary: missing ack in Anya ingress loop → unbounded pending accumulation. |
| **CB-041** | Supporting: once acks flow, `GET /handoff/pending` (patched separately in `ANYA_PENDING_PATCH.md`) becomes the observable proof that pending drains. |
| **V-MESH-001** | Pass = after a full claim → route → ack cycle, `XPENDING mesh:handoff:anya-omega mesh-brokers` reports 0 pending. |
| **V-MESH-002** | Pass = `/handoff/pending?queue=anya-omega` `pending_count` matches `XPENDING` count. |
| **V-MESH-005** | Pass = kill consumer mid-processing → pending entry reclaimed/redelivered → redelivery suppressed as duplicate (digest dedupe, Edit ACK-4) → final ack clears pending, exactly-once effect. |

## 4. ASSUMED ack request contract — MUST-VERIFY against `mesh_broker.py` on the VPS

```
POST http://127.0.0.1:8002/handoff/ack
Content-Type: application/json

{"queue": "anya-omega", "id": "1726...-0"}
```

Assumed semantics: the broker maps this to Redis `XACK mesh:handoff:<queue> mesh-brokers <id>`.
Expected success: HTTP 200 with a JSON body (shape unverified). `XACK` on an already-acked or
unknown id is a server-side no-op success — this is what makes the client ack **idempotent
and safe to retry**.

## 5. MUST-VERIFY assumptions (check each against the real `anya_omega.py` / `mesh_broker.py`)

1. **Ack endpoint path and field names.** Assumed `POST /handoff/ack` with JSON fields
   `"queue"` and `"id"`. Verify the real handler: field names may be `msg_id`, `message_id`,
   or require a `consumer` name.
2. **Consumer-group name.** Assumed `mesh-brokers` (from deployment notes). The client does not
   send it, but the operator verifying V-MESH-001 with `XPENDING` needs the true name.
3. **Broker base URL.** Assumed `http://127.0.0.1:8002`. Verify host/port constants already in
   `anya_omega.py` (it already talks to the broker for claims — reuse that constant; do not
   introduce a second one).
4. **Ingress loop claim mechanics.** Assumed the loop claims one message at a time and exposes
   the stream message id as a variable (called `msg_id` below). Locate the real name.
5. **Durability point.** Assumed there is a single point per iteration where the routing
   decision is appended to `handoffs.log`. The ack call must be inserted immediately after it.
6. **Existing imports/logging.** Assumed `logging` is already configured; the patch reuses the
   module logger if one exists, else creates `logging.getLogger("anya-omega")`.
7. **Timeout behavior.** Assumed a 5 s ack timeout is acceptable on loopback. Verify no
   stricter loop-timing watchdog exists.

## 6. Patch edits

Numbered surgical edits. `--- a/...` / `+++ b/...` headers are shown for orientation; hunks are
given as **anchor + exact code to insert**, since the original file is unavailable.

```
--- a/handoff/anya_omega.py
+++ b/handoff/anya_omega.py
```

### Edit ACK-1 — module state: imports, constants, retry bookkeeping

**Anchor:** near the top of `anya_omega.py`, with the other module-level imports and constants
(beside the existing `BROKER_*` / queue-name constants if present).

**Insert:**

```python
import json
import logging
import urllib.request
import urllib.error
from collections import deque

LOG = logging.getLogger("anya-omega")

# --- ACK-1: broker acknowledgement configuration ---
# MUST-VERIFY §5.3: reuse the module's existing broker base URL constant if one exists.
BROKER_BASE = "http://127.0.0.1:8002"
INGRESS_QUEUE = "anya-omega"          # queue this ingress loop drains
ACK_TIMEOUT_S = 5.0                   # loopback POST budget; never block the loop longer
ACK_MAX_RETRIES = 5                   # bounded retries per message id, then ack-orphan

_ack_attempts: dict = {}              # msg_id -> consecutive failed ack attempts (in-memory)
_acked_recent = deque(maxlen=2000)    # recently acked ids; local idempotency guard
```

**Rationale:** retry state is intentionally in-memory, not durable. If Anya restarts, unacked
pending entries are reclaimed by Redis and redelivered; Edit ACK-4's digest dedupe keeps that
safe. No new files, no new dependencies.

### Edit ACK-2 — helper: `_broker_ack(queue, msg_id)`

**Anchor:** with the other module-level helper functions, above the ingress loop definition.

**Insert:**

```python
def _broker_ack(queue, msg_id):
    """Acknowledge a fully-handled message at the broker.

    POSTs {"queue": queue, "id": msg_id} to /handoff/ack.
    Returns True on HTTP 2xx, False on any failure.
    NEVER raises: every exception is caught and logged, so an ack failure
    can never crash the ingress loop. Safe to retry: broker-side XACK is
    idempotent (acking an already-acked id is a no-op success).
    """
    body = json.dumps({"queue": queue, "id": msg_id}).encode("utf-8")
    req = urllib.request.Request(
        BROKER_BASE + "/handoff/ack",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=ACK_TIMEOUT_S) as resp:
            if 200 <= resp.status < 300:
                return True
            LOG.warning("ack rejected: queue=%s id=%s http=%s",
                        queue, msg_id, resp.status)
            return False
    except Exception as exc:  # timeout, connection refused, broker restarting, ...
        LOG.warning("ack failed: queue=%s id=%s err=%r", queue, msg_id, exc)
        return False
```

### Edit ACK-3 — the ack call site (the core of the patch)

**Anchor:** *inside the ingress loop, immediately after the block that claims a message from
the broker and routes / quarantines / dead-letters it AND appends the decision to
`handoffs.log` — and before the loop advances to the next iteration* (the `continue` or the
bottom of the `while True` body). This placement satisfies the §2 ordering guarantee.

**Insert** (adapt `msg_id` to the loop's real variable name for the claimed stream id):

```python
        # --- ACK-3: acknowledge the claimed message now that it is durably handled.
        # Runs for routed, quarantined, AND dead-lettered messages alike:
        # all three are terminal states, so all three must clear the pending entry.
        if msg_id in _acked_recent:
            acked = True  # already acked this pass; skip duplicate POST (idempotent anyway)
        else:
            acked = _broker_ack(INGRESS_QUEUE, msg_id)

        if acked:
            _acked_recent.append(msg_id)
            _ack_attempts.pop(msg_id, None)
        else:
            n = _ack_attempts.get(msg_id, 0) + 1
            _ack_attempts[msg_id] = n
            LOG.error("ack attempt %d/%d failed for id=%s; will retry next pass",
                      n, ACK_MAX_RETRIES, msg_id)
            if n >= ACK_MAX_RETRIES:
                # Bounded: stop retrying, hand to the operator. The message itself
                # was already durably handled; only the pending bookkeeping is stuck.
                # Operator clears with: XACK mesh:handoff:anya-omega mesh-brokers <id>
                LOG.error("ack-orphan: id=%s handled but unackable after %d tries; "
                          "manual XACK/XPENDING review required", msg_id, n)
                _ack_attempts.pop(msg_id, None)
                _acked_recent.append(msg_id)
```

**Notes for the applier:**
- If the loop has separate branches for routed / quarantined / dead-lettered that each
  `continue` early, the ACK-3 block must be reachable from **all three** — either insert it
  before each `continue`, or refactor the branches to fall through to a single durability
  point and put ACK-3 there (preferred).
- Held messages (unknown types, fail-closed per mesh law) are **not** terminal: do NOT ack
  them here. They stay pending until an operator resolves or reaps them.

### Edit ACK-4 (recommended) — digest dedupe against redelivery

**Anchor:** in the ingress loop, immediately after the claimed message is decoded and its
symbollect digest is computed, before the policy engine runs.

**Insert:**

```python
_seen_digests = deque(maxlen=5000)  # module level, beside _acked_recent (ACK-1)
```

```python
        # --- ACK-4: suppress duplicate effects on redelivery (crash-recovery path).
        # A message claimed but never acked (V-MESH-005) will be redelivered with the
        # same digest. Skip re-routing, but STILL fall through to ACK-3 so the
        # pending entry is finally cleared.
        if digest in _seen_digests:
            LOG.info("duplicate delivery suppressed: digest=%s id=%s", digest, msg_id)
        else:
            _seen_digests.append(digest)
            ...  # existing policy engine: route / quarantine / dead-letter / hold
```

If the loop structure makes fall-through awkward, the alternative is: on duplicate, log,
append the (suppressed) decision to `handoffs.log` with `"duplicate": true`, then jump to
the ACK-3 block. Either way, **the ack must still happen**.

## 7. Failure modes

| Failure | Behavior |
|---|---|
| Broker down / timeout during ack | Logged as warning; retry counter increments; loop continues; retried next pass. |
| Broker returns non-2xx | Logged with status; same retry path as above. |
| Ack succeeds but process crashes before next loop bookkeeping | Harmless: `_acked_recent` is a hint only; broker-side XACK already cleared the entry. |
| Process restarts with unacked messages | Pending entries reclaimed per Redis consumer-group semantics; redelivery deduped by ACK-4; then acked. |
| Retry budget exhausted (`ACK_MAX_RETRIES`) | `ERROR` log + `ack-orphan` marker; operator runs one `XACK`. Loop never blocks. |
| Duplicate ack (double claim, retry after success) | Safe: broker XACK is idempotent; local `_acked_recent` guard avoids the extra POST. |

## 8. Manual test plan (publish → claim → kill → reclaim → ack → pending = 0)

1. **Publish:** `POST /handoff` to the broker with a test handoff addressed to the
   `anya-omega` queue (`payload.to` = a registered test knight). Record the stream id.
2. **Claim:** watch Anya's ingress loop claim it (`GET /ingress/next?consumer=...` depth drops;
   `handoffs.log` gains a routed entry with a digest).
3. **Kill mid-processing:** stop `anya_omega.py` *after* claim but *before* ack — easiest by
   temporarily pointing `BROKER_BASE` at a black hole, or by killing the process between
   iterations while a message is in flight. The pending entry must remain in `XPENDING`.
4. **Verify reclaim + no duplicate effect:** restart Anya (or `XCLAIM` the pending entry with a
   second consumer). The message is redelivered; `handoffs.log` must show the duplicate
   suppressed (`duplicate: true`), and the test knight must receive the route **exactly once**.
5. **Ack:** with the patch live and the broker reachable, the loop's ACK-3 fires.
6. **Verify pending drops to zero:** `XPENDING mesh:handoff:anya-omega mesh-brokers` → `0`;
   `GET /handoff/pending?queue=anya-omega` → `pending_count: 0` (see `ANYA_PENDING_PATCH.md`).
7. **Ack-failure drill:** stop the broker, let one message cycle through ACK-3 retries, confirm
   the loop keeps routing other messages and logs `ack attempt n/5 failed` without crashing;
   restart the broker and confirm the backlog acks drain on subsequent passes.

## 9. Rollback

Revert the four edits. Behavior returns to the current defect (pending accumulation); no data
migration is involved. The `ack-orphan` log lines, if any, remain as plain text for the operator.

## 10. Open questions for the VPS applier

- Exact `POST /handoff/ack` field names and success body (§5.1).
- Whether the broker's ack handler requires the consumer name or derives the group internally.
- Real variable name of the claimed stream id inside the ingress loop (§5.4).
