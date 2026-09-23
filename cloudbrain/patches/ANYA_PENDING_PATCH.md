# ANYA_PENDING_PATCH — broker `GET /handoff/pending`: report true consumer-group pending state

**Status:** PATCH SPEC — do NOT apply blind. The broker source (`mesh_broker.py`) was not
available locally; edits below are keyed to *anchor descriptions* of the `GET /handoff/pending`
handler's known structure. The applier must locate each anchor in the real file on the VPS and
adapt names. All assumptions are listed in §6 and marked **MUST-VERIFY**.

**Scope:** `/opt/data/cloudbrain/handoff/mesh_broker.py` ONLY — the `GET /handoff/pending`
handler. No Anya changes here. Stdlib only (the broker is stdlib-only; it speaks RESP over a
socket — the patch uses the module's existing Redis command helper).

**Target service:** mesh broker on `127.0.0.1:8002`, kept alive by cron `cb-mesh-broker-watch`.

---

## 1. Defect

`GET /handoff/pending` currently reports `XLEN` (total stream length — every message ever
published, including long-since-acked ones) as if it were the pending count. The real pending
state lives in the consumer group: `XPENDING mesh:handoff:<queue> mesh-brokers`. Consequences:

- After CB-040's ack fix lands, there is no endpoint that can prove pending actually drained.
- Crash-recovery triage ("how many unacked messages are stuck? how old is the oldest? which
  consumer holds them?") is impossible from the API.
- `stream_length` and `pending_count` are different numbers with different meanings; conflating
  them hides both.

## 2. New JSON response contract

```
GET /handoff/pending?queue=<queue>
```

```json
{
  "queue": "anya-omega",
  "stream": "mesh:handoff:anya-omega",
  "group": "mesh-brokers",
  "group_exists": true,
  "pending_count": 3,
  "oldest_entry_id": "1726...-0",
  "oldest_age_seconds": 42.7,
  "oldest_idle_seconds": 12.1,
  "oldest_delivery_attempts": 2,
  "per_consumer": {"anya-ingress": 3},
  "stream_length": 128
}
```

Field semantics:

| Field | Source | Meaning |
|---|---|---|
| `queue` | request param | queue name as requested |
| `stream` | derived | `mesh:handoff:<queue>` |
| `group` | constant | `mesh-brokers` |
| `group_exists` | XPENDING error | `false` if the group was never created (no consumer ever attached) |
| `pending_count` | `XPENDING <stream> <group>` summary → element 0 | messages claimed but not yet acked |
| `oldest_entry_id` | summary → element 1 (min id); `null` when `pending_count` = 0 | lowest pending stream id |
| `oldest_age_seconds` | derived from `oldest_entry_id` timestamp | wall-clock age of the oldest unacked message: `(now_ms - id_ms) / 1000`. Stream ids are `<ms>-<seq>`. |
| `oldest_idle_seconds` | `XPENDING ... - + 1` range → idle ms / 1000 | time since the oldest entry was last *delivered* to a consumer; large idle + attempts ⇒ stuck consumer |
| `oldest_delivery_attempts` | range → delivery count | redelivery count of the oldest entry; >1 ⇒ reclaim/retry loop |
| `per_consumer` | summary → element 3 | `{consumer_name: pending_count}` — shows which consumer holds what |
| `stream_length` | `XLEN <stream>` (kept) | total stream length, now under a truthful name |

### Breaking-change documentation

- **ASSUMED old contract** (MUST-VERIFY §6.4): the handler returned something like
  `{"queue": ..., "pending": <XLEN int>}`. If so, this patch is **breaking** for any client
  reading `.pending`: that field previously meant *stream length*, now the truthful pending
  count lives in `.pending_count` and the old XLEN value moves to `.stream_length`.
- Mitigation: keep the old field name as a deprecated alias for one release if any in-repo
  consumer reads it — i.e. also return `"pending": <same value as pending_count>` with a
  `"deprecated": "use pending_count"` note. **Do NOT alias it to XLEN** — that perpetuates the bug.
- `stream_length` preserves the old XLEN observability under an honest name, so no monitoring
  signal is lost.

## 3. Redis commands used

Summary form (one round trip, always issued):

```
XPENDING mesh:handoff:<queue> mesh-brokers
→ [ <count:int>, <min-id:str|nil>, <max-id:str|nil>, [ [<consumer:str>, <count:str>]... ] ]
```

Detail form (one extra round trip, only when `pending_count > 0`):

```
XPENDING mesh:handoff:<queue> mesh-brokers - + 1
→ [ [ <id:str>, <consumer:str>, <idle-ms:int>, <delivery-count:int> ] ]   # oldest entry only
```

(`-`/`+` with count 1 returns the single lowest-id pending entry. The optional
`IDLE <min-idle-time>` filter is deliberately *not* used here — this endpoint reports state,
it does not reclaim.)

## 4. Task / verification-gate mapping

| Item | Relevance |
|---|---|
| **CB-041** | Primary: replace XLEN-based total with true `XPENDING` consumer-group state. |
| **CB-040** | Supporting: the ack fix in `ANYA_ACK_PATCH.md` is what makes `pending_count` move; this endpoint is how you watch it move. |
| **V-MESH-001** | Pass = after claim → route → ack, `pending_count` goes N → 0 and matches `XPENDING` from `redis-cli`. |
| **V-MESH-002** | Pass = `pending_count`, `per_consumer`, and `oldest_entry_id` exactly match `XPENDING` summary output for the same stream/group; `stream_length` matches `XLEN`. |
| **V-MESH-005** | Pass = with the consumer killed mid-processing, `pending_count` = 1, `oldest_idle_seconds` grows, `oldest_delivery_attempts` increments on reclaim — the stuck message is visible instead of hidden inside a stream-length number. |

## 5. Patch edits

```
--- a/handoff/mesh_broker.py
+++ b/handoff/mesh_broker.py
```

### Edit PEND-1 — replace the pending computation in the `GET /handoff/pending` handler

**Anchor:** inside the `GET /handoff/pending` request handler, the block that derives the queue
name from the query string, calls `XLEN`, and builds the JSON response. Replace the XLEN call
and everything downstream of it up to the response construction.

**Assumptions used** (all MUST-VERIFY §6): the module has a Redis command helper called
`_redis_cmd(*args)` returning parsed RESP replies; the queue param arrives as `queue`;
stream names derive as `f"mesh:handoff:{queue}"`. Adapt names to the real file.

**Insert:**

```python
        # --- PEND-1: true consumer-group pending state via XPENDING (replaces XLEN). ---
        stream = f"mesh:handoff:{queue}"
        group = "mesh-brokers"  # MUST-VERIFY §6.2: consumer-group name constant
        now_ms = int(time.time() * 1000)

        resp = {
            "queue": queue,
            "stream": stream,
            "group": group,
            "group_exists": True,
            "pending_count": 0,
            "oldest_entry_id": None,
            "oldest_age_seconds": None,
            "oldest_idle_seconds": None,
            "oldest_delivery_attempts": None,
            "per_consumer": {},
            "stream_length": 0,
        }

        try:
            summary = _redis_cmd("XPENDING", stream, group)
        except Exception as exc:
            if "NOGROUP" in str(exc):
                # Group never created: nothing can be pending. Still report XLEN
                # so the endpoint stays useful pre-first-consumer.
                resp["group_exists"] = False
                try:
                    resp["stream_length"] = int(_redis_cmd("XLEN", stream) or 0)
                except Exception:
                    resp["stream_length"] = 0
                return _json_response(resp)  # adapt to the handler's real return style
            raise  # genuine Redis failure: let the handler's 500 path deal with it

        # summary == [count, min-id, max-id, [[consumer, count], ...]]
        count = int(summary[0] or 0)
        resp["pending_count"] = count
        resp["per_consumer"] = {c: int(n) for c, n in (summary[3] or [])}

        if count > 0 and summary[1]:
            oldest_id = str(summary[1])
            resp["oldest_entry_id"] = oldest_id
            try:
                id_ms = int(oldest_id.split("-", 1)[0])
                resp["oldest_age_seconds"] = round((now_ms - id_ms) / 1000.0, 1)
            except (ValueError, IndexError):
                resp["oldest_age_seconds"] = None  # non-standard id; don't fabricate

            # --- PEND-2: oldest-entry detail (idle time + delivery attempts). ---
            try:
                detail = _redis_cmd("XPENDING", stream, group, "-", "+", "1")
                if detail:
                    entry = detail[0]  # [id, consumer, idle-ms, delivery-count]
                    resp["oldest_idle_seconds"] = round(int(entry[2]) / 1000.0, 1)
                    resp["oldest_delivery_attempts"] = int(entry[3])
            except Exception as exc:
                LOG.warning("pending detail XPENDING failed: stream=%s err=%r", stream, exc)
                # Non-fatal: summary fields above are still correct.

        try:
            resp["stream_length"] = int(_redis_cmd("XLEN", stream) or 0)
        except Exception as exc:
            LOG.warning("pending XLEN failed: stream=%s err=%r", stream, exc)

        return _json_response(resp)  # adapt to the handler's real return style
```

**Notes for the applier:**
- `_json_response` / `LOG` / `time` / `_redis_cmd` are placeholders for the handler's real
  response builder, logger, and Redis helper — wire them to the actual names.
- The summary-form `XPENDING` reply shape above is the canonical RESP array form; if the
  module's helper returns RESP-parsed Python (list), indexing as shown is correct. If it
  returns raw bytes, decode first.
- `per_consumer` counts arrive as strings in RESP — hence `int(n)`.
- Do NOT add `IDLE` filtering or `XCLAIM` here: this endpoint is read-only observability.

### Edit PEND-2 — (folded into PEND-1 above)

The oldest-entry detail block is marked inline (`# --- PEND-2 ...`). If the applier prefers
two commits, apply the summary half first (gates V-MESH-001/002 pass on it alone), then the
detail half (needed for V-MESH-005's stuck-consumer visibility).

### Edit PEND-3 (optional, compatibility) — deprecated `pending` alias

**Anchor:** immediately before the response is returned in the patched handler.

**Insert only if** an existing consumer reads the old `.pending` field (§6.4):

```python
        # --- PEND-3 (optional compat): old field name, new truthful meaning. ---
        # BREAKING CHANGE documented in §2: "pending" used to carry XLEN (stream length).
        # It now aliases pending_count. Remove after all consumers migrate.
        resp["pending"] = resp["pending_count"]
        resp["_deprecated"] = {"pending": "use pending_count; stream length is stream_length"}
```

Default recommendation: **omit PEND-3** unless a real consumer is found; a clean break is
better than a lying field name.

## 6. MUST-VERIFY assumptions (check each against the real `mesh_broker.py`)

1. **Redis client handle / command helper.** Assumed a module-level `_redis_cmd(*args)`.
   Verify the real name, its reply parsing (decoded str vs bytes), and its exception type
   for `NOGROUP` (assumed message contains `"NOGROUP"`).
2. **Queue-name derivation.** Assumed stream = `f"mesh:handoff:{queue}"` with `queue` from the
   query string. Verify how the handler currently derives the stream name from the request —
   reuse that exact derivation.
3. **Consumer-group name.** Assumed `mesh-brokers`. Confirm against the `XGROUP CREATE` /
   `XREADGROUP` call sites in the broker.
4. **Old response contract.** Assumed `{"queue": ..., "pending": <XLEN>}`. Read the current
   handler to document the real breaking delta before applying.
5. **Handler return style.** Assumed a `_json_response(dict)`-style builder and a 500 path for
   raised exceptions. Match the file's real conventions.
6. **`time` / logging availability.** Assumed importable; the broker is stdlib-only so this
   is safe, but reuse the module's existing imports where present.

## 7. Failure modes

| Failure | Behavior |
|---|---|
| Group does not exist (`NOGROUP`) | `group_exists: false`, `pending_count: 0`, detail fields `null`; `stream_length` still reported. HTTP 200 — this is a valid state, not an error. |
| Redis unreachable | Exception propagates to the handler's existing 500 path (unchanged behavior). |
| `pending_count` = 0 | Detail XPENDING skipped; all `oldest_*` fields `null`. |
| Non-standard stream id | `oldest_age_seconds` = `null` rather than a fabricated number. |
| Detail XPENDING fails | Warning logged; summary fields still returned correctly. |

## 8. Manual test plan (publish → claim → kill → reclaim → ack → pending = 0)

Shared with `ANYA_ACK_PATCH.md` §8; the pending-specific assertions are:

1. **Baseline:** with an idle queue, `GET /handoff/pending?queue=anya-omega` →
   `pending_count: 0`, `oldest_entry_id: null`, `stream_length` = N (total ever published).
2. **Publish + claim, no ack yet:** publish one test message; have a test consumer
   `XREADGROUP` it without acking. Assert `pending_count: 1`,
   `per_consumer: {"<test-consumer>": 1}`, `oldest_delivery_attempts: 1`,
   while `stream_length` = N+1 — the two numbers visibly diverge (this is the bug being fixed:
   pre-patch, the endpoint would have reported N+1 as "pending").
3. **Cross-check (V-MESH-002):** compare against `XPENDING mesh:handoff:anya-omega mesh-brokers`
   from `redis-cli`: count, min-id, and per-consumer map must match exactly.
4. **Kill consumer (V-MESH-005):** kill the test consumer mid-processing; watch
   `oldest_idle_seconds` grow on successive polls; reclaim via `XCLAIM` with a second consumer
   and assert `oldest_delivery_attempts` becomes 2 and `per_consumer` shifts to the new consumer.
5. **Ack:** `POST /handoff/ack {"queue": "anya-omega", "id": "<id>"}` → 200.
6. **Verify zero:** `pending_count: 0`, `oldest_entry_id: null`, `per_consumer: {}` —
   while `stream_length` stays N+1 (acked messages remain in the stream; retention trimming is
   a separate concern, see `cloudbrain/ops/retention/`).
7. **NOGROUP path:** query a queue whose group was never created → `group_exists: false`,
   HTTP 200, no traceback in broker logs.

## 9. Rollback

Revert PEND-1..3. The endpoint returns to XLEN-as-pending; no schema migration involved.
Note in the rollback log that any dashboards built on `pending_count` will need reverting too.

## 10. Open questions for the VPS applier

- Real Redis helper name and reply decoding (§6.1).
- Real old response field names (§6.4) — needed to finalize the breaking-change note.
- Whether any existing consumer (ntfy health script, dashboard, Anya `/health` ingress-depth
  field) reads `GET /handoff/pending` today; if so, PEND-3's alias decision must be made
  before applying.
