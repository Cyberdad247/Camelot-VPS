# Engineering track — VPS deploy steps

Ordered, one-shot runbook for the engineering artifacts. Every step needs a **fresh Hermes admin login** (per-session; never stored). VPS = 162.35.107.134, operator user `hermes`, no sudo.
Execution pattern throughout: upload script (<512 KiB) to `/opt/data/scripts/`, create a `no_agent` cron job, trigger `/api/cron/jobs/{id}/trigger`, read `/opt/data/cron/output/{id}/`. Trigger calls may time out while the job still runs — always inspect job/process/output state before retrying.

## E0 — Preconditions

- Fresh Hermes admin login obtained for this session.
- Baseline re-verified: Redis :6379 PONG, Qdrant :6333 200, SurrealDB :8000 /health 200, OpenViking :1933 /health 200, broker :8002 /health, Anya :8003 /health. Record versions + UTC timestamps.
- Staging artifacts present locally: `cloudbrain/{patches/anya,ops/retention,ops/supervision,tests}/`.

## E1 — Install the supervisor (CB-020)

1. Upload `ops/supervision/cb-supervise.sh` → `/opt/data/scripts/cb-supervise.sh`; `chmod +x`.
2. Read back the 9 `# ASSUMPTION - verify on VPS` markers; resolve each against live state:
   - SurrealDB binary path + start args + env file: `ls /opt/data/cloudbrain/bin/`, check existing process cmdline via cron `ps -o args -C <name>` (never print env values).
   - OpenViking start command: check venv + existing process cmdline.
   - qdrant args, redis-cli path.
3. Edit the CONFIG block in place (via re-upload) until no ASSUMPTION remains unverified.
4. Run one manual cycle via cron job: `/opt/data/scripts/cb-supervise.sh reconcile` → expect `healthy` for all six services, no restarts.
5. Create every-minute cron `cb-supervise-reconcile` running the same command.
6. Verify: `status all` output shows all healthy; kill -9 the broker PID once → next reconcile restarts it → V-DR-002 (partial) evidence.

## E2 — Verify patch assumptions against live sources (CB-040, CB-041)

1. `files-read` `/opt/data/cloudbrain/handoff/mesh_broker.py` and `/opt/data/cloudbrain/handoff/anya_omega.py`.
2. Confirm: `POST /handoff/ack` request contract (field names!), redis client handle name in the broker, consumer group name (`mesh-brokers`), queue-name derivation, current `/handoff/pending` response shape.
3. If any assumption in `ANYA_ACK_PATCH.md` / `ANYA_PENDING_PATCH.md` is wrong, amend the patch spec first — do not apply blind.

## E3 — Apply the Anya ack patch (CB-040)

1. Apply the 4 numbered edits from `patches/anya/ANYA_ACK_PATCH.md` to `/opt/data/cloudbrain/handoff/anya_omega.py` (upload edited file; keep a `.bak-<UTC>` of the original).
2. Restart Anya via the supervisor: `cb-supervise.sh restart anya` → `/health` 200.
3. Verify no duplicate delivery: run `tests/test_mesh.py` + `test_anya.py` (see E5).

## E4 — Apply the pending-endpoint patch (CB-041)

1. Apply `patches/anya/ANYA_PENDING_PATCH.md` to `/opt/data/cloudbrain/handoff/mesh_broker.py` (keep `.bak-<UTC>`).
2. Restart broker via supervisor → `/health` 200.
3. Verify: `GET /handoff/pending` returns the new contract; cross-check `pending_count` against `redis-cli XPENDING mesh:handoff:<q> mesh-brokers` → must agree (V-MESH-005).

## E5 — Run handoff e2e tests (CB-040, CB-041, CB-044)

1. Upload `tests/test_mesh.py`, `test_anya.py`, `test_symbollect.py` → `/opt/data/scripts/`; run each via one-shot cron jobs.
2. Require: zero FAIL lines, exit 0, JSON summaries captured as evidence (gates V-MESH-001/005/006/008, V-SYM-001..004).
3. V-MESH-002 (consumer interruption): run the manual procedure in `tests/README.md` — kill a consumer mid-claim, verify reclaim + idempotent reprocessing.

## E6 — Deploy stream retention (CB-042)

1. Upload `ops/retention/apply_retention.py` → `/opt/data/scripts/`.
2. Dry run first: `python3 apply_retention.py --dry-run` via cron → inspect JSON report; confirm trims are sane and pending entries are preserved.
3. Create scheduled cron (hourly recommended) running the real trim.
4. Verify alert fields in the report cross the 80%/95% thresholds sensibly (V-CAP-001/002).

## E7 — Full e2e suite

1. Upload and run the remaining scripts: `test_redis.py`, `test_qdrant.py`, `test_surrealdb.py`, `test_health_semantics.py` (V-DATA-004/008/009, V-SVC-005/006).
2. `test_surrealdb.py` sources `/opt/data/cloudbrain/open-notebook.env` by path at runtime — verify its output contains no credential values.
3. Collect all JSON summaries + UTC timestamps as the evidence pack for this track.

## E8 — Retire overlapping watchdogs (CB-020)

Only after E1–E7 are green for 24h:
1. Disable `cb-mesh-broker-watch` and `cb-anya-watch` crons (supervisor `reconcile` now covers them).
2. Keep `cb-ntfy-health` (alerting) untouched.
3. Confirm ntfy still reports healthy + a supervised restart produces the expected recovery notice.

## Rollback

- Every edited VPS file keeps a `.bak-<UTC>`; restore = copy back + `cb-supervise.sh restart <svc>`.
- Supervisor/cron changes: delete the cron job, re-enable the old watchdogs.
- Retention: `apply_retention.py` never deletes pending entries; worst case, re-run with `--dry-run` to confirm no-op.
