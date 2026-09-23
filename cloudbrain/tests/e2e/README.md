# Cloudbrain E2E verification — `cloudbrain/tests/e2e`

Part of the CAMELOT_OS cloudbrain/ production-hardening pack. Adapted from the
local staging pack; the staging source of record remains
`cloudbrain/tests/e2e/`.

Local-only verification scripts for the Hermes VPS cloudbrain stack. They do
nothing from here: each script is uploaded to the VPS and executed there via
the no-agent cron pattern (loopback only — cron has no DNS). Every script is
**stdlib-only** (no pip), uses **synthetic records with unique run IDs**, and
**cleans up after itself**.

VPS run: upload each script to `/opt/data/scripts/`, execute via a no-agent
cron job, read results at `/opt/data/cron/output/{id}/`.

## Script inventory

| Script | Verifies | Gates covered |
|---|---|---|
| `test_redis.py` | Redis flash memory: PING, SET/GET round trip, TTL expiry, persistence presence (`CONFIG GET save` / `LASTSAVE` / `BGSAVE` capability) | V-DATA-004 |
| `test_qdrant.py` | Two synthetic scope collections with identical vectors; filtered search + cross-scope isolation; collections deleted afterwards | V-DATA-008 |
| `test_surrealdb.py` | Authenticated CREATE / SELECT / DELETE of a synthetic record; credentials sourced from the env file by path, values never printed (self-check FAILs on any leak) | V-DATA-009 |
| `test_mesh.py` | Broker publish → claim via `/handoff/next` → ack → pending-set accuracy; consumer-interruption reclamation is a manual step (SKIP) | V-MESH-001, V-MESH-005, V-MESH-002 |
| `test_anya.py` | Ephemeral knight registration + capability reflection; routed proposal arrives with Symbollect wire + sha256 digest (digest recomputed and verified); `grant`-type message quarantined, never delivered | V-CAP-002, V-MESH-008, V-MESH-006 |
| `test_symbollect.py` | 5 frozen golden packets (wire / canonical / digest / decode); canonical stability under key shuffling; round-trip property on generated values; malformed-input + reserved-key-collision rejection | V-SYM-001, V-SYM-002, V-SYM-003, V-SYM-004 |
| `test_health_semantics.py` | Per-service liveness vs readiness probing; documents the honest gap that every service exposes a single health endpoint | V-SVC-005, V-SVC-006 |

## Gate ID glossary

| Gate | Meaning |
|---|---|
| V-MESH-001 | Mesh broker HTTP round trip: publish → claim → ack completes for a synthetic message |
| V-MESH-002 | Consumer-interruption reclamation: a claimed-but-unacked message is reclaimable via the `mesh-brokers` consumer group (manual procedure below; script emits SKIP) |
| V-MESH-005 | Pending-set accuracy: a claimed message appears in pending; after ack it disappears |
| V-MESH-006 | Authority-minting quarantine: `authorize`/`grant`/`promote`/`revoke`/`sign`/`approve`/`mint` types are quarantined by Anya Omega, never routed |
| V-MESH-008 | Digest-attached delivery: routed handoffs arrive with Symbollect wire + sha256 digest; the digest verifies against the canonical form |
| V-SYM-001 | Golden vectors: `encode`/`canonical`/`digest` outputs frozen for 5 representative packets (incl. the documented example) |
| V-SYM-002 | Canonical stability: key-order shuffling yields identical canonical form and digest |
| V-SYM-003 | Round-trip property: `encode`→`decode`→`encode` is stable over a generated corpus |
| V-SYM-004 | Malformed-input rejection: malformed packets raise; literal keys colliding with reserved dictionary codes are refused by `encode` |
| V-DATA-004 | Redis flash memory: SET/GET round trip, TTL expiry, persistence presence |
| V-DATA-008 | Qdrant cross-scope isolation: two synthetic scopes; filtered search never leaks across scopes |
| V-DATA-009 | SurrealDB authenticated lifecycle: create/query/delete of a synthetic record with credentials sourced from the env file (redacted) |
| V-SVC-005 | Liveness: each service's process responds |
| V-SVC-006 | Readiness: each service can serve its real workload (best-effort probes; WARN + gap note where only a single health endpoint exists) |
| V-CAP-002 | Capability registry: an ephemeral knight registers with declared capabilities; the registry reflects them |

## Deploying via the cron pattern

For each script (replace `<name>`):

1. **Upload** `<name>.py` to `/opt/data/scripts/e2e/<name>.py` on the VPS
   (each file < 512 KiB; the cron environment runs Python 3.13 stdlib only).
2. **Create a no-agent cron job** whose command is
   `python3 /opt/data/scripts/e2e/<name>.py`. Allow a ≥120s timeout:
   `test_redis.py` sleeps 3s for TTL expiry; `test_mesh.py`/`test_anya.py`
   poll up to ~15s for deliveries.
3. **Trigger** it: `python3 bin/hermes-api.py cron-trigger <job_id>`
   (list jobs with `bin/hermes-api.py cron-list`).
4. **Read** the output at `/opt/data/cron/output/<job_id>/`.
5. **Delete the cron job** afterwards unless you want it as a recurring gate.

Suggested run order: `test_health_semantics.py` → `test_redis.py` →
`test_qdrant.py` → `test_surrealdb.py` → `test_mesh.py` → `test_anya.py` →
`test_symbollect.py` (order-independent; all are self-contained).

`SYMBOLLECT_PATH` env var overrides the codec import path
(`/opt/data/cloudbrain/handoff`) in `test_symbollect.py` and `test_anya.py` —
useful for local harness validation only; leave unset on the VPS.

## Output contract

Every script prints human lines, then a machine-readable JSON summary:

```
PASS V-DATA-004 ping
PASS V-DATA-004 set-get-roundtrip
FAIL V-DATA-004 ttl-expiry | pre-expiry visible=False post-expiry get='t' err=''
--- JSON SUMMARY ---
{ "script": "test_redis.py", "run_id": "...", "started_utc": "...",
  "finished_utc": "...", "results": [...], "summary": {...}, "verdict": "PASS" }
```

- Line format: `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>` /
  `SKIP <gate> <check> | <reason>` / `WARN <gate> <check> | <reason>`.
- **Exit 0 iff no FAIL.** WARN and SKIP do not fail the run; they are counted
  separately in `summary` (`pass`/`fail`/`skip`/`warn`).
- Run IDs: UTC timestamp + random hex suffix, e.g.
  `20260923T022530Z-a1b2c3d4`. All synthetic keys, collections, queues,
  knights, and records embed the run ID.

## Cleanup guarantees

| Script | Cleanup |
|---|---|
| `test_redis.py` | `DEL` of both synthetic keys; verified gone |
| `test_qdrant.py` | `DELETE` of both test collections; `GET` must return 404 |
| `test_surrealdb.py` | `DELETE e2e_verify WHERE run_id = <run>`; re-query must be empty |
| `test_mesh.py` | test message is acked; nothing persists in the stream |
| `test_anya.py` | deliveries acked off the knight queue; `DELETE /knights/{knight}` attempted (see limitation) |
| `test_symbollect.py` | pure codec checks; no state touched |
| `test_health_semantics.py` | read-only probes (+ one throwaway redis key, deleted) |

## V-MESH-002 manual procedure (consumer-interruption reclamation)

Automating a consumer kill inside a cron job is unreliable, so this gate is a
documented manual step. `test_mesh.py` emits `SKIP V-MESH-002` with this pointer.

1. Publish a synthetic handoff: `POST 127.0.0.1:8002/handoff`
   `{"queue":"e2e-manual","to":"e2e-sink","from":"manual","type":"proposal","payload":{"tag":"reclaim-test"}}`.
2. Claim it with consumer `manual-A`: `GET /handoff/next?queue=e2e-manual&consumer=manual-A`. Record the entry id.
3. **Kill consumer A without acking** (stop its process / abandon the claim).
4. Verify the entry is pending: `GET /handoff/pending?queue=e2e-manual` shows the entry id.
5. Reclaim with consumer `manual-B` via the `mesh-brokers` consumer group
   (broker-native reclaim, or `XCLAIM mesh:handoff:e2e-manual mesh-brokers manual-B 0 <id>` in redis-cli).
6. Ack with consumer `manual-B`; confirm pending no longer lists the id.
7. PASS if the message was recovered exactly once and delivered to B.

## V-SVC-005 / V-SVC-006 gap note (honest)

Every service currently exposes a **single** health endpoint, so liveness
("the process answers") and readiness ("it can do its real work") cannot be
fully distinguished. `test_health_semantics.py` probes readiness where a
credential-free signal exists (redis SET/GET, qdrant `GET /collections`, mesh
`GET /handoff/pending`, anya's composite `/health`) and emits WARN — not FAIL —
where it cannot (SurrealDB needs auth; OpenViking documents no deeper probe).
A proper split would require `/live` (process up) vs `/ready` per service:
redis writable, qdrant collections reachable, SurrealDB authenticated query
succeeds, broker stream writable, Anya registry loaded and the ingress loop
draining. Until then, treat V-SVC-006 WARNs as known gaps, not regressions.

## Security notes

- **No secrets** in this directory or in any report. SurrealDB credentials are
  read at runtime from `/opt/data/cloudbrain/open-notebook.env` (mode 600) by
  path; key names are matched flexibly (`SURREAL_*`/`DB_*`/generic), values
  live only in memory, and a self-check FAILs the run if any credential value
  appears in the emitted output. Auth failures report status codes only.
- All probes use `127.0.0.1` literals (cron has no DNS). Nothing leaves the VPS.
- Only synthetic records are created, all tagged with the run ID and deleted.

## Known limitations

- **Broker/Anya response schemas** are parsed tolerantly (`id`/`entry_id`/
  `message_id`, envelope nesting variants). If the VPS implementations use
  different field names, the scripts FAIL with a body snippet — update the
  `pick()` candidate lists rather than the gates.
- **Anya's knight registry is durable** (`knights.json`); `DELETE /knights/{name}`
  may be unsupported, in which case cleanup WARNs. Test knight names are unique
  per run, so leftovers never collide.
- **Symbollect canonical sort key**: goldens assume `canonical()` sorts by the
  message's (long) keys at every level, per the doc's `canonical(msg)`
  definition. If the VPS codec sorts by wire codes instead, V-SYM-001 digest
  goldens will flag the deviation for human review; V-SYM-002
  (self-consistency) is unaffected.
- **SurrealDB env key names** are matched heuristically; if the env file uses
  unexpected names the script FAILs `env-credentials-loadable` listing the
  keys it found (names only).
