# Cloudbrain user-space service supervision — `cb-supervise.sh` v1.0.0

## What this is

A single Bash supervisor (`cb-supervise.sh`, `set -euo pipefail`) that manages the
whole cloudbrain VPS stack from user space, because the `hermes` user has no sudo
and no systemd access. It is invoked from cron every minute in `reconcile` mode and
brings anything unhealthy back up in dependency order:

```
redis → qdrant → surrealdB → openviking → mesh broker → anya omega
```

Open Notebook is intentionally **not** managed (paused per ground truth).

## Files in this directory

- `cb-supervise.sh` — the supervisor. Executable. Versioned (`CB_SUPERVISE_VERSION="1.0.0"`).
- `SUPERVISION_NOTES.md` — this file.

No secrets are stored in either file. The SurrealDB env file
(`/opt/data/cloudbrain/open-notebook.env`, mode 600) is referenced **by path only**
and sourced in a subshell at runtime on the VPS; values never touch the repo, the
logs, or the supervisor's own environment.

## Pre-flight: ASSUMPTIONs to verify on the VPS

These were not in the ground-truth inventory and are marked
`# ASSUMPTION - verify on VPS` in the script's CONFIG section. Check each before
relying on the supervisor in production:

| Item | Current default | What to verify |
|---|---|---|
| `SURREALDB_BIN` / `SURREALDB_ARGS` | `/opt/data/cloudbrain/bin/surrealdb start --bind 127.0.0.1:8000 file:…/open_notebook.db` | Real binary path and start args |
| `OPENVKING_START_CMD` | `${VENV_PY} -m openviking --host 127.0.0.1 --port 1933` | Exact OpenViking start command |
| `QDRANT_ARGS` | (empty) | Confirm qdrant binds 127.0.0.1:6333 and uses a persistent storage path; add flags if needed |
| `REDIS_CLI` | `/opt/data/cloudbrain/bin/redis-cli` | Exact redis-cli path (falls back to `PATH` lookup) |

Also confirm `curl` and `pgrep` exist for the `hermes` user (both are used by the
existing ntfy health script, so they should already be present).

## Install

1. Upload to the VPS, e.g. `/opt/data/cloudbrain/bin/cb-supervise.sh`, and
   `chmod +x` it.
2. Edit the CONFIG `ASSUMPTION` items above.
3. Dry run (read-only, takes no lock on mutating paths):
   `/opt/data/cloudbrain/bin/cb-supervise.sh status`
4. First reconcile (starts anything unhealthy, in dependency order):
   `/opt/data/cloudbrain/bin/cb-supervise.sh reconcile`
5. Add the every-minute cron job:
   ```
   * * * * * /opt/data/cloudbrain/bin/cb-supervise.sh reconcile >> /opt/data/cloudbrain/logs/supervise-cron.log 2>&1
   ```
6. Watch one full cycle (`status`, plus `logs/supervise.log`), then disable the
   old per-service watchdog crons (`cb-mesh-broker-watch`, `cb-anya-watch`) via
   `crontab -e`. Keep their scripts on disk for rollback.
7. Rollback: re-enable the old watchdog cron lines, remove the new cron line.

## Commands

```
cb-supervise.sh start [svc|all]   # start only what is unhealthy (dependency order)
cb-supervise.sh stop [svc|all]    # stop (reverse dependency order)
cb-supervise.sh restart <svc>     # stop then start one service ('all' allowed explicitly)
cb-supervise.sh status [svc|all]  # running/health per service; exit 1 if any unhealthy
cb-supervise.sh reconcile         # start anything unhealthy, in order (the cron entrypoint)
```

## Runtime behavior

- **Health-gated starts.** `start`/`reconcile` never touch a service whose health
  check already passes (redis: `redis-cli PING` → `PONG`; the rest: HTTP 200 on
  their health endpoint). After launching, the supervisor waits up to
  `START_TIMEOUT` (60 s) for the health check; if it never passes, the new process
  is stopped again, the failure is logged, and an `ALERT` line is emitted.
- **Crash-loop backoff.** Restart timestamps live in
  `/opt/data/cloudbrain/run/restarts-<svc>.log`. More than 5 restarts in 10 minutes
  → further restarts are **refused** and an `ALERT` line is emitted (hook point for
  ntfy — see the commented block in `emit_alert`). Counters are pruned to the window,
  so a service recovers automatically once it stays up.
- **Concurrency-safe.** All mutating commands take an exclusive non-blocking
  `flock` on `/opt/data/cloudbrain/run/cb-supervise.lock`; a contended run exits 1
  with a clear message instead of double-starting services. Daemon children
  explicitly close the lock fd so a running service never holds the lock.
- **Stale-pidfile tolerant.** Pidfiles are validated against `/proc/<pid>/cmdline`;
  recycled PIDs are rejected. A `pgrep -f` fallback (excluding the supervisor's own
  process tree) still finds processes started outside the supervisor, e.g. by the
  old watchdogs during migration.
- **Graceful stop.** `SIGTERM`, wait up to `STOP_TIMEOUT` (15 s), then `SIGKILL`;
  pidfile removed either way.
- **Structured logging.** Every action appends to
  `/opt/data/cloudbrain/logs/supervise.log`:
  `2026-09-22T22:31:19Z svc=mesh event=start outcome=ok detail=healthy within 60s`
  (`event` ∈ start/stop/restart/reconcile/status, `outcome` ∈ ok/skipped/attempt/
  failed/refused/killed/warning). `ALERT` lines go to the same log plus stderr.

## Replacing the existing watchdog crons

`cb-mesh-broker-watch` and `cb-anya-watch` each restarted one service on a fixed
schedule with no health gating, no backoff, and no ordering. `reconcile` subsumes
both: it covers all six services, only starts what is actually unhealthy, respects
dependency order, and refuses crash loops instead of respawning them forever.
Disable the old crons only after one clean `reconcile` cycle has been observed;
the ntfy health-check cron (`cb-ntfy-health`) stays as-is — it is monitoring, not
supervision, and the supervisor's `ALERT` hook is meant to feed into it.

## What it does NOT cover — residual risks

- **No systemd, no privileges.** There are no cgroup resource limits, no
  sandboxing, no socket activation, and no true OS-level boot ordering. Cron is
  effectively the init system: if cron itself stops, nothing recovers. After a host
  reboot, recovery happens on the first cron tick (up to ~60 s plus service start
  times), not at boot.
- **Shallow health checks.** `PONG` / HTTP 200 is liveness, not the
  liveness-vs-readiness split CB-023 calls for. A wedged-but-listening service can
  read as healthy.
- **No log rotation.** `supervise.log` and per-service logs grow unboundedly;
  add a monthly `truncate -s` / user-space logrotate cron entry.
- **Backoff state is local.** Clearing `/opt/data/cloudbrain/run/` resets restart
  counters (fail-open toward restarting — acceptable, but be aware).
- **ASSUMPTION items** (above) must be verified; wrong start commands fail closed
  (launcher error + ALERT) but the service stays down until fixed.

## Verification mapping

- **CB-020 (interim, user-space).** This script is the CB-020 interim step: one
  versioned supervisor replaces the watchdog crons with defined dependencies,
  readiness-gated starts, graceful shutdown, and restart backoff. Full systemd
  hardening remains a privileged follow-up.
- **V-SVC-001 (unit integrity) — partial.** Versioned script, pinned paths in one
  CONFIG section, explicit `ASSUMPTION` markers, `bash -n` clean, exercised by a
  local test harness. Unit-file semantics don't apply in user space.
- **V-SVC-002 (ordered startup) — covered.** `START_ORDER` enforced by
  `start all` and `reconcile`; each service is health-gated before the next starts.
- **V-SVC-003 (graceful shutdown) — covered.** `stop` sends `SIGTERM`, waits
  `STOP_TIMEOUT`, escalates to `SIGKILL`, cleans the pidfile; both paths are logged.
- **V-SVC-004 (crash-loop protection) — covered.** 5 restarts / 10 min → refuse +
  `ALERT` identifying the service.
- **V-DR-002 (process failure recovery) — partial.** Per-process kill recovery is
  handled by minute-cadence `reconcile` (verified: `kill -9` → restarted healthy on
  next run). Dependency-failure injection and the host-reboot proof remain for the
  CB-024 exercise.

## Testing performed

`bash -n` plus a local harness (fake `redis-cli`, stub HTTP servers on loopback,
env-overridable CONFIG — fakes lived in `/tmp`, nothing extra written to the
workspace). Verified: start/stop/restart/status/reconcile, health-gate no-op on
already-healthy services, dependency order, `kill -9` recovery, failed-start
teardown with `ALERT`, crash-loop refusal on the 6th restart inside 10 minutes
with a distinct `ALERT`, `flock` contention (second run exits 1), stale-pidfile
rejection, graceful `SIGTERM` stop and `SIGKILL` fallback, `restart` argument
validation. Two real bugs were found and fixed during testing: daemon children
inheriting the supervisor's lock fd (lock never released), and `pgrep -f`
matching ancestor wrapper processes (false "running").

Not yet done: execution against the real VPS binaries — the `ASSUMPTION` items and
the SurrealDB env-file sourcing path need one live `reconcile` cycle on the host.

## When Open Notebook unpauses

Add a service block to CONFIG, a `start_open_notebook` launcher, a
`open_notebook)` arm in `service_healthy`/`match_for`, and insert it into
`START_ORDER` (likely after surrealdB, before openviking — confirm dependency then).
