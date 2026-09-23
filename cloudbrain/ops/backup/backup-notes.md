# cb-backup.sh — backup notes

Companion to `cb-backup.sh` (task CB-051; evidence for V-BKP-002, V-BKP-003).
Forged locally; deploy by copying the script to `/opt/data/scripts/cb-backup.sh`
on the Hermes VPS (well under the ~512 KiB per-file upload limit).

## What the script does

For one run it creates `/opt/data/cloudbrain/backups/cb-<UTC-ts>/` and:

1. **redis** — `BGSAVE` via `redis-cli`, polls `INFO persistence` until
   `rdb_bgsave_in_progress:0` with `rdb_last_bgsave_status:ok` and
   `LASTSAVE >=` the pre-save value (same-second saves are valid: the BGSAVE
   reply is only sent after the fork), then copies `appendonlydir/` +
   `dump.rdb` point-in-time.
2. **qdrant** — discovers collections via `GET /collections` (never hardcoded),
   then per collection: `POST /collections/{name}/snapshots`, downloads the
   snapshot file, and saves `GET /collections/{name}` as `<name>.config.json`
   (the config JSON is the "schemas" record for V-BKP-002).
3. **surrealdb** — `surreal export` to `export.surql`. Credentials are parsed
   (not sourced) at runtime from `/opt/data/cloudbrain/open-notebook.env`;
   the script refuses to run if that file is group/world-readable, probes for
   a `--pass-file` CLI option first, and unsets the password variable
   immediately after the export. `SURREAL_NS`/`SURREAL_DB` are overridable env
   vars with clearly-marked **unconfirmed** defaults (`open_notebook`).
4. **anya** — point-in-time `cp` of `knights.json` + `handoffs.log`
   (the log is append-only, so a copy is a prefix-consistent snapshot).
5. **open-notebook** — copies the data dir if it exists and is non-empty;
   otherwise records `SKIP` (exit stays 0) with the reason in the manifest.
6. **config** — `redis.conf` (if present) plus a generated non-secret
   `inventory.txt`. `*.env` / `*secret*` / `*key*` are excluded by an explicit
   allowlist, never a sweep.

Then: `manifest.json` (per-file sha256, byte sizes, service versions, UTC
start/end, backup ID, per-component status) → tar of the data dirs →
encrypt → **decrypt-verify** (decrypt with the provisioned key, compare
digests; a blob that cannot be decrypted is never kept) → plaintext staging
removed (only `<id>.tar.age`/`.tar.enc` + `manifest.json` remain) →
retention prune (`KEEP_LAST`, default 7 newest sets).

Any component FAIL → no encrypted artifact is produced, the staging dir is
kept for forensics with a partial manifest, one-line `OK/FAIL/SKIP` summaries
print per component, and the exit code is non-zero (a partial backup can
never be marked successful — G3 requirement).

## Scheduling recommendation

Daily, via the existing no_agent cron pattern (same shape as `cb-ntfy-health`):

```
# no_agent cron: daily 03:00 UTC — encrypted cloudbrain backup
0 3 * * * /opt/data/scripts/cb-backup.sh /opt/data/cloudbrain/.backup-key.age
```

Notes for the cron wrapper / deploy step:

- Pass the key file as `$1` (or `CBB_KEY_FILE`). The key path will appear in
  the cron definition — that is expected and fine; the key *value* never does.
- Wire the exit code into the existing ntfy health pipeline: non-zero (or a
  manifest whose `overall != "ok"`, or a newest backup older than ~26h) should
  raise the backup-failure / stale-backup alert required by CB-P1-005.
- The script takes a `flock` on `/opt/data/cloudbrain/backups/.cb-backup.lock`
  so overlapping runs are impossible; a second concurrent run exits 1.
- Off-host copy is **not** in the script (cron has no general outbound
  network). After a successful run, ship `<backup-id>.tar.age|.enc` +
  `manifest.json` off-host by the approved transfer path (CB-051 requires at
  least one isolated off-host copy with *separate key control* — the on-host
  key file does not satisfy that by itself).

## Encryption and key separation (V-BKP-003)

- `age` is preferred when the key file holds an age **identity**
  (`AGE-SECRET-KEY-…`; recipient derived via `age-keygen -y`); otherwise
  `openssl enc -aes-256-cbc -pbkdf2` with the key file as passphrase.
  Force with `CBB_CRYPTO=age|openssl`; default `auto`.
- The key file path is never defaulted, never copied into the backup tree
  (the script refuses a key file under `/opt/data/cloudbrain/backups/`), and
  never logged. Both the key file and the SurrealDB env file must be mode 600
  (owner-only) or the run refuses.
- Negative test for the verifier: decrypting the artifact without the key
  file fails (wrong-key / missing-key both fail closed); the script itself
  performs the positive proof on every run (decrypt-verify round-trip).

## Intentionally excluded (V-BKP-002 coverage rationale)

| Excluded | Why |
|---|---|
| Python venvs (`/opt/data/cloudbrain/venv`, OpenViking) | Rebuildable from lockfiles/installers; OpenViking holds no durable data worth snapshotting |
| Service binaries (`bin/`) | Reinstallable artifacts; versions are recorded in the manifest + inventory |
| `*.env`, key/secret material | Must never land in a backup payload; referenced, not copied |
| Runtime logs, NTFY state, cron spool | Covered by the retention policy (CB-050), not by backup; the Anya audit log *is* backed up |
| Redis cache keys beyond persistence | Per the durability model, Redis is cache/stream infra; what matters (streams incl. mesh-broker queues, deadletter/quarantine) is in the AOF/RDB pair |
| Mesh broker / Anya Omega / Symbollect code | Code, not data — versioned elsewhere; broker *state* rides in Redis streams |
| Qdrant raw storage dir | Snapshots via the API are the supported, consistent capture; raw segment copies are not crash-consistent |

## Deploy preconditions

1. `/opt/data/cloudbrain/open-notebook.env` exists, mode 600, exporting
   `SURREAL_USER` / `SURREAL_PASS` (or set `SURREAL_USER_VAR` /
   `SURREAL_PASS_VAR` to the real variable names).
2. `SURREAL_NS` / `SURREAL_DB` exported with the **confirmed** namespace and
   database names (defaults are unconfirmed placeholders; the script warns).
3. Backup key file provisioned **out-of-band**, mode 600, outside the backup
   tree. For `age`: generate with `age-keygen -o /path/to/key` on a trusted
   machine and copy only the identity file; for `openssl`: a single-line
   passphrase file. The off-host copy's key must be held under separate
   access control (V-BKP-003).
4. `age` (+ `age-keygen`) or `openssl` present; `curl`, `tar`, `sha256sum`,
   `python3` (or GNU `grep -P` fallback) present.
5. Services reachable on loopback at their configured URLs/ports.
6. `SURREL_BIN` if `surreal` is not at `/opt/data/cloudbrain/bin/surreal`.

## Restore sketch (full proof is CB-052's job)

1. Copy `<id>.tar.age|.enc` + `manifest.json` to the isolated host.
2. Decrypt: `age -d -i <keyfile> -o set.tar <id>.tar.age`, or
   `openssl enc -d -aes-256-cbc -pbkdf2 -pass file:<keyfile> -in <id>.tar.enc -out set.tar`.
3. `tar -xf set.tar`; verify every file against `manifest.json` sha256.
4. **redis**: stop redis, restore `appendonlydir/` + `dump.rdb` into the data
   dir (same ownership), start.
   **qdrant**: recreate collections, upload snapshots via
   `POST /collections/{name}/snapshots/upload`.
   **surrealdb**: `surreal import --conn … --ns … --db … export.surql`
   (same credential sourcing rules as backup).
   **anya**: copy back `knights.json` / `handoffs.log` with the broker stopped.
   **open-notebook**: restore the data dir before first backend start.

## Assumptions made while forging

- `surreal` lives at `/opt/data/cloudbrain/bin/surreal` (overridable via
  `SURREL_BIN`); its `export` subcommand accepts `--conn/--user/--pass/--ns/--db`.
  `--pass-file` support is probed, not assumed; the argv fallback documents
  its tradeoff (visible to local host users via `ps` during the export).
- `SURREAL_NS`/`SURREL_DB` defaults (`open_notebook`) are guesses — flagged
  loudly at runtime and must be confirmed at deploy.
- Qdrant 1.19 snapshot REST semantics (`POST …/snapshots` → `result.name`;
  `GET …/snapshots/{name}` downloads bytes).
- Collection names are URL-safe (no exotic characters needing encoding).
- Failed-run staging dirs match `cb-*` and therefore count toward `KEEP_LAST`
  retention — deliberate, so forensics survive a few days.
- `open-notebook` `SKIP` (backend never started) does not fail the run; this
  is the documented coverage gap until its backend is live.
