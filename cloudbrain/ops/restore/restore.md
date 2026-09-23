# Restore Procedures — Tri-Dynamic Cloudbrain Stack

**Scope:** Redis, Qdrant, SurrealDB, mesh broker (state lives in Redis Streams),
Anya Omega (registry + audit), OpenViking config (if backed up).
Open Notebook backend is not yet running (per cloudbrain runbook) — restore
steps for it are stubbed and marked.

**Hard constraints:** Local forging only — all commands run on the VPS as
`hermes` (no sudo). Service start/stop is the **service supervisor** sibling
track's domain; procedures below say "stop `<service>`" / "start
`<service>`" generically and depend on it. Every restore is destructive:
**snapshot current state first** (pre-restore safety backup) — that safety
backup is the rollback artifact (see §8).

**Backup layout** (produced by the backup worker, assumed contract — confirm
with backup worker before first drill):

```
/opt/data/cloudbrain/backups/<UTC-ts>/
  manifest.json      # unencrypted; sha256 per file, service versions,
                     # counts, qdrant collection configs + snapshot paths
  redis/             # encrypted payloads of /opt/data/cloudbrain/data/redis/*
  qdrant/            # per-collection snapshot files
  surrealdb/         # encrypted .surql export
  anya-omega/        # knights.json, handoffs.log segment
```

Expected `manifest.json` keys: `backup_ts`, `services`, `files[]` (`path`,
`sha256`, `bytes`), `counts` (`redis_dbsize`, `qdrant.{collection}`,
`surrealdb.{table}`), `qdrant_collections` (per-collection vector config +
`snapshot` path). The backup worker's decrypt tool is referenced below as
`cb-bkp-decrypt`; replace with the real tool name when confirmed.

**Manifest verification (CB-052) ↔ V-BKP-005…008 mapping:**
V-BKP-005 full restore → §1–§5 (per-component), §6 (ordered full-stack), §7 (isolated drill);
V-BKP-006 integrity → §9 + `cb-restore-verify.sh`;
V-BKP-007 functional → §9 (script round-trips: Redis/Qdrant/SurrealDB/broker/Anya);
V-BKP-008 granular → §1.4, §2.5, §3.4, §4.3.

---

## 0. Preconditions (all procedures)

1. Freeze: no deploy/rotation/restore in progress; record operator, UTC time,
   reason, backup `<UTC-ts>`.
2. Safety backup: run `cloudbrain/ops/backup/cb-backup.sh` (VPS upload → no_agent
   cron → trigger → output-inspection pattern). Record its backup ts.
3. Validate the restore artifact **before** applying:
   - `manifest.json` parses and `backup_ts` post-dates the last known-good state.
   - Decrypt one payload and spot-check (do not restore a corrupt backup).
4. Confirm the stop plan (which services' data is being replaced) and that the
   service supervisor is available.

> **Rollback note:** "Restore is itself destructive — snapshot current state
> first." Every procedure below inherits §8: the pre-restore safety backup is
> the undo. If the wrong backup is restored, re-run these same procedures
> against the safety backup.

---

## 1. Redis (file-level restore)

Data: `/opt/data/cloudbrain/data/redis/` — `appendonlydir/`
(AOF + RDB), `dump.rdb`. Binary `/opt/data/cloudbrain/bin/redis-server`,
CLI `/opt/data/cloudbrain/bin/redis-cli`, port 127.0.0.1:6379.

### Preconditions
- Service stopped via supervisor.
- Decrypted backup payloads available under a scratch dir
  (e.g. `/tmp/restore-<ts>/redis/`); sha256 of each verified against
  `manifest.json` (§9) **before** touching live data.

### Procedure
```bash
BKP=/opt/data/cloudbrain/backups/<UTC-ts>     # the chosen backup
SAFETY=/opt/data/cloudbrain/backups/safety-<ts>  # pre-restore safety backup dir
WORK=/tmp/restore-<ts>/redis
mkdir -p "$WORK"

# 1. Decrypt payloads (tool owned by backup worker)
cb-bkp-decrypt "$BKP/redis/redis.payload.enc" "$WORK/redis.tar"

# 2. Verify manifest digests of decrypted files (see §9 / verify script)
# 3. Archive current (live) data dir — do NOT delete it
mv /opt/data/cloudbrain/data/redis \
   /opt/data/cloudbrain/data/redis.pre-restore-<ts>

# 4. Install backup data and fix ownership/permissions
mkdir -p /opt/data/cloudbrain/data/redis
tar -xf "$WORK/redis.tar" -C /opt/data/cloudbrain/data/redis
chown -R hermes:10000 /opt/data/cloudbrain/data/redis
chmod 700 /opt/data/cloudbrain/data/redis
chmod 600 /opt/data/cloudbrain/data/redis/*.rdb 2>/dev/null || true
ls -la /opt/data/cloudbrain/data/redis /opt/data/cloudbrain/data/redis/appendonlydir

# 5. Start service, wait for readiness
#    (start <redis> via supervisor)
for i in $(seq 1 30); do
  /opt/data/cloudbrain/bin/redis-cli -h 127.0.0.1 -p 6379 PING | grep -q PONG && break
  sleep 2
done
/opt/data/cloudbrain/bin/redis-cli -h 127.0.0.1 -p 6379 LASTSAVE
/opt/data/cloudbrain/bin/redis-cli -h 127.0.0.1 -p 6379 DBSIZE
```

### Expected output
- `PING` → `PONG` within the retry loop.
- `LASTSAVE` returns a Unix timestamp ≤ the backup's `backup_ts` (data is the
  backup's state, not newer).
- `DBSIZE` matches `manifest.json` → `counts.redis_dbsize` (see §9).
- Mesh broker queues are restored with Redis: check stream lengths
  `XLEN mesh:handoff:anya-omega`, `XLEN mesh:handoff:anya-quarantine`,
  `XLEN mesh:handoff:anya-deadletter` vs pre-incident notes.

### Rollback note
Keep `redis.pre-restore-<ts>` until the restore is accepted (verify script
passes). To roll back: stop service, swap the directories back, start.

### 1.4 Granular variant (V-BKP-008 — single key, no full restore)
Stand up a scratch Redis on an alternate port from the backup files, then
migrate only the target key:

```bash
RPORT=6389
mkdir -p /tmp/restore-<ts>/redis-scratch
tar -xf "$WORK/redis.tar" -C /tmp/restore-<ts>/redis-scratch
/opt/data/cloudbrain/bin/redis-server --port $RPORT \
  --dir /tmp/restore-<ts>/redis-scratch --daemonize no \
  --appendonly yes --save '' &
# after PONG on $RPORT, migrate the single authorized key:
K=<key>
VAL=$(/opt/data/cloudbrain/bin/redis-cli -p $RPORT --raw DUMP "$K")
echo -n "$VAL" | /opt/data/cloudbrain/bin/redis-cli -p 6379 -x RESTORE "$K" 0
/opt/data/cloudbrain/bin/redis-cli -p 6379 GET "$K"   # verify
kill %1
```
Requires authorization (recorded, audited) and must not overwrite unrelated
keys — use a fresh scratch key name or confirm the target key is the intended
one. Teardown the scratch server afterwards.

---

## 2. Qdrant (snapshot recover per collection)

Data: `/opt/data/cloudbrain/data/qdrant`. Binary `/opt/data/cloudbrain/bin/qdrant`,
REST 127.0.0.1:6333, gRPC 127.0.0.1:6334.
Recover API: `POST /collections/{name}/snapshots/recover`.
Backup: one snapshot file per collection under `$BKP/qdrant/<collection>/`.

### Preconditions
- Backup snapshot files decrypted and verified against `manifest.json`.
- For **full restore**: Qdrant stopped via supervisor.
- For **granular per-collection restore (V-BKP-008)**: may run live; record
  which collection is being replaced.

### Procedure
```bash
BKP=/opt/data/cloudbrain/backups/<UTC-ts>
QREST=http://127.0.0.1:6333
WORK=/tmp/restore-<ts>/qdrant
mkdir -p "$WORK"
cb-bkp-decrypt "$BKP/qdrant/qdrant.payload.enc" "$WORK/qdrant.tar"
tar -xf "$WORK/qdrant.tar" -C "$WORK"        # -> $WORK/qdrant/<collection>/*.snapshot

# Serve snapshots to Qdrant over loopback (recover fetches by URL)
python3 -m http.server 18911 --bind 127.0.0.1 -d "$WORK/qdrant" &
HTTPSRV=$!

for C in $(ls "$WORK/qdrant"); do
  SNAP=$(ls "$WORK/qdrant/$C"/*.snapshot | head -1)
  FILE=$(basename "$SNAP")
  EXISTS=$(curl -s -o /dev/null -w '%{http_code}' "$QREST/collections/$C")

  if [ "$EXISTS" = "200" ]; then
    echo "collection $C exists - replacing from snapshot"
    curl -s -X DELETE "$QREST/collections/$C" >/dev/null
  else
    echo "collection $C NOT present - creating from manifest config, then recovering"
  fi

  # Create collection from manifest vector config (required when not present)
  CFG=$(jq -r --arg c "$C" '.qdrant_collections[$c] | {vectors}' "$BKP/manifest.json")
  curl -s -X PUT "$QREST/collections/$C" -H 'Content-Type: application/json' -d "$CFG"

  # Recover snapshot
  curl -s -X POST "$QREST/collections/$C/snapshots/recover" \
    -H 'Content-Type: application/json' \
    -d "{\"location\":\"http://127.0.0.1:18911/$C/$FILE\",\"priority\":\"snapshot\"}"
  echo " <- recover $C"
done
kill $HTTPSRV
```

### Expected output
- Per-collection recover response: `{"result":true,"status":"ok","time":...}`.
- `GET /collections/<name>` shows `"points_count"` matching
  `manifest.json` → `counts.qdrant.<collection>`.
- `GET /collections` lists exactly the expected collections.

### Rollback note
Pre-restore safety backup contains the current snapshots; re-run §2 against
it. For granular restore, the single collection is the only thing replaced —
the old snapshot from the safety backup restores it.

### 2.5 Collection-not-present case
Handled above: if the collection is absent (deleted, never created on this
host), create it from the vector config in `manifest.json`
(`qdrant_collections.<name>.vectors` — size, distance, on-disk settings),
then recover the snapshot into the empty collection.

---

## 3. SurrealDB (`surreal import` into a FRESH data file)

Data: `/opt/data/cloudbrain/data/surrealdb/open_notebook.db`. Port
127.0.0.1:8000, `/health` 200. Credentials **only** in
`/opt/data/cloudbrain/open-notebook.env` (mode 600) — sourced at runtime,
never embedded/echoed/logged.

**Never import over a live DB file.** Import builds a fresh file; only after
verification is the fresh file promoted.

### Preconditions
- Service stopped via supervisor.
- Backup `.surql` export decrypted; import tool available
  (`SURREAL_BIN=${SURREAL_BIN:-/opt/data/cloudbrain/bin/surreal}`,
  fallback `command -v surreal` — confirm the path with the supervisor track).

### Procedure
```bash
BKP=/opt/data/cloudbrain/backups/<UTC-ts>
DBDIR=/opt/data/cloudbrain/data/surrealdb
WORK=/tmp/restore-<ts>/surrealdb
mkdir -p "$WORK"
SURREAL_BIN=${SURREAL_BIN:-/opt/data/cloudbrain/bin/surreal}

cb-bkp-decrypt "$BKP/surrealdb/surrealdb.payload.enc" "$WORK/export.surql"
sha256sum -c <(jq -r '.files[] | select(.path|endswith("export.surql")) | "\(.sha256)  '"$WORK"'/export.surql"' "$BKP/manifest.json")

# Archive live DB file — do NOT import over it
mv "$DBDIR/open_notebook.db" "$DBDIR/open_notebook.db.pre-restore-<ts>"

# Import into a FRESH file. Credentials from the env file at runtime only.
set -a; . /opt/data/cloudbrain/open-notebook.env; set +a
"$SURREAL_BIN" import \
  --conn "file://$WORK/open_notebook.db" \
  --user "$SURREAL_USER" --pass "$SURREAL_PASS" \
  --ns "${SURREAL_NS:-cloudbrain}" --db "${SURREAL_DB:-cloudbrain}" \
  "file://$WORK/export.surql"
unset SURREAL_PASS

# Verify record counts on the FRESH file before promoting (start a throwaway
# server on an alternate port, or query via the CLI):
#   SELECT count() FROM <table> GROUP ALL;  # per manifest counts.surrealdb
# Promote only if counts match:
mv "$WORK/open_notebook.db" "$DBDIR/open_notebook.db"
chown hermes:10000 "$DBDIR/open_notebook.db"
chmod 600 "$DBDIR/open_notebook.db"
# (start <surrealdb> via supervisor)
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health
```

### Expected output
- `surreal import` exits 0 with a summary of imported records.
- `/health` → `200`.
- Per-table `SELECT count() …` matches `manifest.json` → `counts.surrealdb.*`.

### Rollback note
`open_notebook.db.pre-restore-<ts>` is the untouched live file; swap it back
if the import fails or counts diverge.

### 3.4 Granular variant (V-BKP-008 — one table / record set)
Export contains multiple tables. Restore only the authorized subset into the
**live** DB (service running) after authorization and audit logging:

```bash
set -a; . /opt/data/cloudbrain/open-notebook.env; set +a
# Extract only the authorized table's statements, load into scratch DB first,
# verify, then apply to live via `surreal import` against the live endpoint
# (or re-run the table's CREATE/INSERT statements with the CLI).
unset SURREAL_PASS
```
Never re-import deleted or revoked records — cross-check against the deletion
log before applying (V-BKP-007).

---

## 4. Anya Omega (registry + audit log)

Registry: `/opt/data/cloudbrain/data/anya-omega/knights.json`.
Audit: `/opt/data/cloudbrain/data/anya-omega/handoffs.log` (append-only;
every routed handoff carries a sha256 digest — the chain).

### Preconditions
- Anya Omega stopped via supervisor.
- Backup decrypted; `knights.json` and `handoffs.log` segment verified against
  `manifest.json`.

### Procedure
```bash
BKP=/opt/data/cloudbrain/backups/<UTC-ts>
ADIR=/opt/data/cloudbrain/data/anya-omega
WORK=/tmp/restore-<ts>/anya
mkdir -p "$WORK"
cb-bkp-decrypt "$BKP/anya-omega/anya.payload.enc" "$WORK/anya.tar"
tar -xf "$WORK/anya.tar" -C "$WORK"

# Registry: archive current, restore backup, fix ownership
cp "$ADIR/knights.json" "$ADIR/knights.json.pre-restore-<ts>"
cp "$WORK/knights.json" "$ADIR/knights.json"
chown hermes:10000 "$ADIR/knights.json"
chmod 600 "$ADIR/knights.json"
jq empty "$ADIR/knights.json"   # must be valid JSON

# Audit log: append-only — do NOT truncate live log. Archive current,
# restore backup as the base, then re-append entries that arrived AFTER
# the backup_ts (dedup by sha256 digest field).
cp "$ADIR/handoffs.log" "$ADIR/handoffs.log.pre-restore-<ts>"
cp "$WORK/handoffs.log" "$ADIR/handoffs.log"
# re-append post-backup entries (operator: filter by timestamp > backup_ts,
# dedup on the digest field) — then validate the chain:
sha256sum -c <(echo "$(jq -r '.files[] | select(.path|endswith("handoffs.log")) | .sha256' "$BKP/manifest.json")  $ADIR/handoffs.log") || echo "log advanced past backup - expected, chain validated separately"
chown hermes:10000 "$ADIR"/knights.json "$ADIR"/handoffs.log
# (start <anya-omega> via supervisor)
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8003/health
```

### Expected output
- `knights.json` valid JSON; Anya `/health` → `200`.
- Quarantine/deadletter queues (`anya-quarantine`, `anya-deadletter`) present
  in the mesh (they live in Redis Streams — restored with Redis).
- Registry entries match the manifest digest.

### Rollback note
`knights.json.pre-restore-<ts>` and `handoffs.log.pre-restore-<ts>` restore
prior state; re-append any entries written after the restore began.

### 4.3 Granular variant (V-BKP-008 — one knight's registry entry)
Restore a single knight record: edit `knights.json` to replace only that
knight's entry from the backup (authorized, audited); do not touch other
entries. Validate JSON and restart Anya.

---

## 5. Mesh broker

The broker is stateless Python (`/opt/data/cloudbrain/handoff/mesh_broker.py`,
127.0.0.1:8002); its queue state is Redis Streams — restored by §1.
The script itself is a deployed artifact; restore = redeploy the approved
artifact version recorded in `manifest.json` → `services.mesh_broker`
(if the script was corrupted), then restart via supervisor.

Watchdog cron `cb-mesh-broker-watch` / `cb-anya-watch` keep processes alive —
confirm they exist after a restore (`crontab -l` as hermes), since a restore
that predates them would lose them.

---

## 6. Full-stack ordered restore sequence

For a **full restore** (V-BKP-005) in dependency order:

| Step | Action | Health gate |
|---|---|---|
| 1 | Freeze + record operator/time/reason/backup ts | — |
| 2 | Safety backup via `backup.sh` | backup dir + manifest created |
| 3 | Validate chosen backup (manifest parse, digest spot-checks) | manifest OK |
| 4 | Stop services: Anya → broker → OpenViking → SurrealDB → Qdrant → Redis | processes gone |
| 5 | Restore **Redis** (§1) | start; PONG; DBSIZE = manifest |
| 6 | Restore **Qdrant** (§2, all collections) | start; `/readyz` 200; points_count = manifest |
| 7 | Restore **SurrealDB** (§3) | start; `/health` 200; counts = manifest |
| 8 | Restore **Anya** registry+audit (§4) | start; `/health` 200 |
| 9 | Broker: redeploy script if needed, start | `/health` 200 on :8002 |
| 10 | OpenViking `/health` on :1933 (restart if it holds config state) | 200 |
| 11 | Run `cb-restore-verify.sh <backup-dir>` (§9) | all PASS |
| 12 | Reconciliation: broker `/handoff/pending` vs pre-incident notes; watchdog crons present; ntfy heartbeat clean | documented |

Dependency: the service supervisor track owns stop/start semantics; this
sequence assumes "stop/start `<service>`" resolves through it.

---

## 7. Isolated-environment restore (V-BKP-005 drill variant)

Restore to a scratch tree + alternate ports, leaving production untouched.
Drill root: `/opt/data/cloudbrain/restore-drill/<UTC-ts>/`.

```bash
DRILL=/opt/data/cloudbrain/restore-drill/<UTC-ts>
mkdir -p "$DRILL"/{redis,qdrant,surrealdb,anya}
```

| Component | Scratch data dir | Alt port | Notes |
|---|---|---|---|
| Redis | `$DRILL/redis` | 6389 | `redis-server --port 6389 --dir $DRILL/redis --appendonly yes --save ''` with restored `appendonlydir/` copied in |
| Qdrant | `$DRILL/qdrant` | REST 6343 / gRPC 6344 | `qdrant --storage-path` equivalent: run with a config file (`config.yaml`) overriding `service.http_port`, `service.grpc_port`, `storage.storage_path`. Then run §2 recover against `http://127.0.0.1:6343` |
| SurrealDB | `$DRILL/surrealdb/open_notebook.db` | 8001 | import backup into fresh file (§3), then `surreal start file://… --bind 127.0.0.1:8001` (creds from env file) |
| Mesh broker | n/a (uses Redis) | 8012 | run `mesh_broker.py` pointed at drill Redis (port 6389) if the script supports env/port override — confirm with supervisor track; otherwise drill broker against its own code on 8012 |
| Anya Omega | `$DRILL/anya` | 8013 | run `anya_omega.py` with registry/audit under `$DRILL/anya` on port 8013 (env override — confirm) |

Then run the verification script with overrides:

```bash
RESTORE_ROOT=/opt/data/cloudbrain \
DRILL_ROOT=$DRILL \
REDIS_PORT=6389 QDRANT_URL=http://127.0.0.1:6343 \
SURREAL_URL=http://127.0.0.1:8001 BROKER_URL=http://127.0.0.1:8012 \
ANYA_URL=http://127.0.0.1:8013 \
./cb-restore-verify.sh <backup-dir>
```

Teardown: kill drill processes, keep `$DRILL` until the drill report is
accepted, then remove. No drill process may bind production ports.

**Assumptions to confirm:** Qdrant config-file port/storage overrides;
mesh broker and Anya port/data-dir configurability (env or flags).

---

## 8. Rollback

The pre-restore safety backup (step 2 of every sequence) is the rollback
artifact. To roll back: stop the affected services, re-run the applicable
§1–§5 procedures **against the safety backup directory**, restart in
dependency order, re-run the verify script, and record the re-restore in the
restore log. Retain `*.pre-restore-<ts>` file archives until the restore is
accepted.

Escalation: any verify-script FAIL that cannot be explained by the backup's
own age → SEV2 with the script output attached; signs of tampering → SEV1,
preserve evidence.

---

## 9. Verification — `cb-restore-verify.sh`

The companion script performs V-BKP-006/V-BKP-007 checks:

1. **Digests:** re-hash every `manifest.json` → `files[]` path
   (mapped through `RESTORE_ROOT`/`DRILL_ROOT` for drills) and compare sha256.
2. **Health:** Redis PING, Qdrant `/readyz` (fallback `/collections`),
   SurrealDB `/health`, broker `/health`, Anya `/health`, OpenViking `/health`.
3. **Round-trips:** Redis SET/GET/DEL with a unique run ID; Qdrant
   upsert+search on scratch collection `restore_verify_<runid>` (created and
   deleted); SurrealDB CREATE+SELECT+DELETE on scratch table with the run ID.
   Also exercises broker publish→claim→ack and Anya direct route on the
   restored environment (V-BKP-007).
4. **Counts:** DBSIZE vs `counts.redis_dbsize`; per-collection
   `points_count` vs `counts.qdrant.*`; per-table counts vs
   `counts.surrealdb.*`.
5. Prints `PASS`/`FAIL`/`SKIP` per check; exits non-zero on any FAIL.
   Secrets: SurrealDB credentials are sourced at runtime from
   `$SURREAL_ENV` (`/opt/data/cloudbrain/open-notebook.env`); never embedded.

Checks absent from the manifest (e.g. a missing count) report SKIP, not FAIL.

---

## 10. Restore-drill checklist (V-DR-003 / V-DR-004)

Run drills against the **isolated environment** (§7) unless the drill plan
explicitly approves touching production. Record every timestamp in UTC.

### Timings to record
- [ ] T_declare — drill/incident declared (RTO clock starts)
- [ ] T_freeze — change freeze recorded
- [ ] T_safety — pre-restore safety backup completed
- [ ] T_backup_validated — manifest parsed, digests verified
- [ ] T_stopped — all services stopped
- [ ] T_redis_done / T_qdrant_done / T_surreal_done / T_anya_done — per-component restore+health
- [ ] T_started — all services restarted, health gates green
- [ ] T_verified — `cb-restore-verify.sh` all PASS
- [ ] T_reconciled — broker pending, audit chain, watchdog crons reconciled
- [ ] T_accepted — operator accepts; drill report filed

### RPO measurement hooks (V-DR-004)
For each component record **last-durable-transaction timestamp** and the
**backup's `backup_ts`**; RPO_actual = T_declare − last-durable-txn (data
potentially lost = everything after the backup's last durable write):
- [ ] Redis: `LASTSAVE` time; `DBSIZE`/key spot-check vs pre-drill notes
- [ ] Qdrant: newest snapshot creation time (snapshot filename) vs last write
- [ ] SurrealDB: export timestamp in manifest vs last write
- [ ] Mesh broker: oldest unacked pending message age (`XPENDING` idle) —
  expected gap documented (backup predates unacked messages)
- [ ] Anya: last `handoffs.log` digest timestamp before/after backup
- [ ] RPO_actual ≤ agreed RPO: ___ (objective value — get from goal owners;
      placeholder until CB-050 retention/RPO decision is approved)

### RTO measurement hooks (V-DR-004)
- [ ] RTO_actual = T_verified − T_declare; RTO_actual ≤ agreed RTO: ___
      (placeholder — get from goal owners)
- [ ] Timestamped calculation attached to the drill report; accepted by ___.

### V-DR-003 host-loss mapping
- [ ] Rebuild used **only** approved artifacts: record binary versions
      (Redis 8.2.1, Qdrant 1.19.1, SurrealDB 2.6.5, broker/Anya script digests)
      and config sources — no undocumented host state.
- [ ] Secrets came only through the approved workflow (env file / supervisor),
      never pasted into commands or logs.
- [ ] Drill environment was a clean scratch tree (§7) or a rebuilt host —
      note which.
- [ ] Gaps found → owners assigned → defect log updated.

### V-BKP-005…008 evidence hooks
- [ ] V-BKP-005: restore timeline (timings above) + manifest reconciliation.
- [ ] V-BKP-006: `cb-restore-verify.sh` output attached; sampled digests and
      aggregate counts match; inconsistencies zero or explained.
- [ ] V-BKP-007: end-to-end results (write/recall/handoff/quarantine/deletion
      flows) attached; no deleted or revoked state revived (spot-check a
      known-deleted key/record absent after restore).
- [ ] V-BKP-008: granular recovery record — object recovered, authorized by,
      audited at, unrelated data untouched.

---

## Open questions / assumptions (resolve before first drill)

1. `manifest.json` schema and the backup decrypt tool name are the backup
   worker's contract — confirm exact keys before scripting against it.
2. `surreal` binary path (assumed `/opt/data/cloudbrain/bin/surreal`) —
   confirm with the supervisor track.
3. Qdrant config-file overrides for storage path + ports (drill variant).
4. Mesh broker / Anya Omega port and data-dir configurability (drill variant).
5. Agreed RPO/RTO values (CB-050 / goal owners).
6. Open Notebook restore steps are stubbed until its backend exists.
