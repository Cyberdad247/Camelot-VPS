# Cloudbrain production-hardening implementation pack — MANIFEST

Assembled 2026-09-23 (UTC) from a 3-coordinator swarm. Every artifact was forged
locally: zero VPS access, zero credentials, zero secrets in any file.
`files/` (user-visible docs) and canonical CAMELOT baselines untouched.

Source docs: `files/cloudbrain-prod-blueprint/{blueprint.md,task.md,verification.md}`.

## Canonical locations

| Directory | Track | Contents |
|---|---|---|
| `cloudbrain/ops/ + cloudbrain/patches/ + cloudbrain/tests/` | Engineering | Anya/broker patch specs, supervision manager, broker retention tooling, e2e test suite |
| `cloudbrain/ops/` | Ops/security | Backup automation, off-VPS copy, restore, retention policy, TLS termination |
| `cloudbrain/docs/runbooks/` | Docs/readiness | Deploy, secret-rotation, restore, incident-response runbooks |
| `staging/_archive/pre-split/` (source staging tree only) | — | Superseded pre-split drafts (`backup-restore/`, `runbooks/`, `tls/`). Not part of this tree; do not use. |
| `cloudbrain/MANIFEST.md` | — | This file |
| `cloudbrain/DEPLOY_QUEUE.md` | — | Ordered VPS deploy queue (all phases) |

Each track's `TRACK_FILES.md` maps every artifact to its `task.md` CB-* item and
`verification.md` V-* gate. The deploy queue lives in `DEPLOY_QUEUE.md`.

## Engineering track (`engineering/`)

- `patches/anya/ANYA_ACK_PATCH.md` — 4 surgical edits: idempotent `_broker_ack()` after the `handoffs.log` durability point; bounded 5-retry; loop never crashes on ack failure. Held messages are NOT acked. (CB-040; V-MESH-001/002)
- `patches/anya/ANYA_PENDING_PATCH.md` — `GET /handoff/pending` moves from XLEN to `XPENDING` summary+range on group `mesh-brokers`; new contract documented (breaking change flagged). (CB-041; V-MESH-005)
- `ops/retention/RETENTION_POLICY.md` + `ops/retention/apply_retention.py` — MAXLEN 5k live / 2k retry / 20k evidence; export-before-trim fail-closed; PEL-guarded (never trims unacked); `--dry-run`; JSON report; exit-2 fail-closed. (CB-042, CB-050; V-CAP-001/002, V-LIFE-001)
- `ops/supervision/cb-supervise.sh` + `ops/supervision/SUPERVISION_NOTES.md` — user-space start/stop/restart/status/reconcile; health-gated starts; crash-loop backoff (5/10min → refuse + ALERT); flock-safe; dependency order redis→qdrant→surrealdb→openviking→mesh→anya. 9 `# ASSUMPTION` markers to resolve on VPS. Tested against a local fake-service harness. (CB-020; V-SVC-001..004, V-DR-002 partial)
- `tests/` — 7 stdlib-only scripts + README: redis, qdrant, surrealdB (authenticated, no-secret-leak self-check), mesh (publish→claim→ack→pending-zero), anya (route + `grant`-quarantine negative test), symbollect (28/28 locally), health semantics. Unique run IDs, self-cleanup, JSON summaries.
- `TRACK_FILES.md`, plus `cloudbrain/docs/phase-guides/deploy-steps-engineering.md` (ordered VPS steps E0–E8 with rollback).

Known gaps: patch MUST-VERIFY assumptions (ack contract, pending shape, 9 supervisor markers) require one live read of VPS sources before applying; evidence-trim exporter doesn't exist yet (`apply_retention.py` skips evidence trims by design); V-MESH-002 is a manual procedure; V-SVC-006 liveness/readiness split not testable (single health endpoint per service).

## Docs/readiness track (`docs/`)

- `deploy-runbook.md` — hardened-stack deployment wave by wave, approver/evidence/abort triggers per wave, canary + rollback, post-deploy suites, launch blockers, decisions D1–D8.
- `secret-rotation-runbook.md` — Hermes admin, SurrealDB, Redis AUTH, Qdrant API key; dual-credential overlap; on-VPS generation; secrecy across history/`/proc`/cron/logs/chat; emergency-compromise flow; 90/180-day cadence.
- `restore-runbook.md` — roles with separation of duties, full-vs-granular decisions, per-store restore sequence, integrity + functional verification, V-DEL-005 deletion-state guard as a restore-FAIL gate, RPO/RTO sign-off.
- `incident-response-runbook.md` — SEV1–SEV4 (authority-mint bypass pinned SEV1), ntfy handling + missed-heartbeat rule, 0–15 min roles, stack-specific containment, append-only evidence, comms matrix, blameless PIR.
- `TRACK_FILES.md`, plus `cloudbrain/docs/DECISIONS_CHECKLIST.md` (owners, D1–D8, runbook approval, usability exercises, tabletop, access certification, restore-drill sign-off, readiness review verdict wording, Suite C/D/E cadence).

## Ops/security track (`ops-security/`)

- `ops/backup/cb-backup.sh` + `ops/backup/backup-notes.md` — nightly encrypted backup: Redis BGSAVE + point-in-time copy, Qdrant per-collection snapshots (auto-discovered), SurrealDB export (creds from env file only), Anya registry + audit log; sha256 manifest; age/openssl encryption with out-of-band key; fail-closed. Tested locally with stubbed services incl. failure paths. (CB-051; V-BKP-002/003)
- `ops/restore/restore.md` + `ops/restore/cb-restore-verify.sh` — per-component + ordered full-stack + isolated-drill restore procedures; 19-check verifier (manifest re-hash, health, synthetic round-trips, count reconciliation). Tested against mock harness, all PASS. (CB-052; V-BKP-005–008)
- `ops/backup/offvps-copy.md` + `ops/backup/cb-offsite-push.sh` — 3-2-1 design: isolated S3 copy with write-only push credential + Object Lock + versioning; chunked resumable SigV4 push via DoH + `curl --resolve`; Shamir 2-of-3 key custody proposed; 3-night ntfy escalation; never prunes unpushed sets. (CB-051; V-BKP-004)
- `ops/retention/retention-policy.md` + `ops/retention/cb-trim.sh` — proposed thresholds (5k live / 2k retry / 20k evidence streams, 90d dead-letter, 50 MB/daily log rotation, GFS 7/4/12 backups, disk warn 75% / critical 90%); dry-run default; evidence trims fail-closed; never-trim-unacked interlock. Tested with fixture trees. (CB-050, CB-042; V-LIFE-001/002, V-CAP-001–003)
- `ops/tls/Caddyfile` + `ops/tls/tls-notes.md` + `ops/tls/firewall-notes.md` — 3 Caddy variants (default loopback 127.0.0.1:8443; commented public DNS-01 and tailnet-bind); user-space install/run; Tailscale-only recommended; firewall as provider/host-root handoff (no fabricated commands) + `ss`-based loopback verification matrix. (CB-011, CB-013; V-NET-001/003/004, V-TLS-001, V-WEB-001)
- `TRACK_FILES.md` — artifact → task.md → gate map, supersession + cross-track dependency notes.
- `cloudbrain/docs/phase-guides/deploy-steps-ops-security.md` — ordered VPS phases A–F + cleanup (merged into `DEPLOY_QUEUE.md` Phase 3).

Cross-track dependencies: restore calls the supervisor generically for stop/start; retention trim interlock depends on the Anya ingress-ack fix; trim bounds (5k/2k/20k) must be reconciled with ops/retention/`apply_retention.py` before deploy (Phase 3 E0); evidence trims stay disabled until the evidence exporter exists; disk/PEL-age/cert alert wiring has no owner in this swarm (flagged for CB-060–063). Auth-gated, not forgeable here: CB-012 credential rotation, provider firewall application, S3 provider + credentials, Tailscale decision, approval of all PROPOSED thresholds, RPO/RTO values.

## Pending / not in this pack

1. Owner decisions still required before VPS phases: Tailscale-only vs public TLS (blocks TLS cutover); S3-compatible offsite provider; approval of all PROPOSED retention thresholds (CB-050); RPO/RTO values; offsite key-custody store; `SURREAL_NS`/`SURREAL_DB` confirmation.
2. All VPS execution is queued behind a **fresh Hermes admin login** (per-session, never stored). Nothing here has touched the VPS.
3. Open Notebook remains paused by the user; excluded from supervision scope.
4. SurrealDB authenticated-query + restart-supervision verification still outstanding (needs the same fresh login).
5. Cross-track gaps for whoever takes them: evidence-trim exporter (until it exists, evidence trims stay disabled by design); observability owner for disk/PEL-age/cert alerts (CB-060–063).
