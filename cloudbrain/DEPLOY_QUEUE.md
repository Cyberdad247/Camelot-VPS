# VPS deploy queue — cloudbrain production hardening

Every step needs a **fresh Hermes admin login** for the session (per-session, never stored).
VPS = 162.35.107.134, operator user `hermes`, no sudo.
Execution pattern throughout: upload script (<512 KiB) to `/opt/data/scripts/`, create a
`no_agent` cron job, trigger `/api/cron/jobs/{id}/trigger`, read `/opt/data/cron/output/{id}/`.
Trigger calls may time out while the job still runs — always inspect job/process/output state
before retrying. Never launch duplicate Python build/install jobs.

## Phase 0 — Baseline + decisions

- **E0**: re-verify all six services (Redis :6379 PONG, Qdrant :6333 200, SurrealDB :8000 /health 200, OpenViking :1933 /health 200, broker :8002 /health, Anya :8003 /health). Record versions + UTC timestamps.
- **Docs 1–2**: assign service owner, security owner, data steward, on-call route per component (CB-004). Resolve or time-box decisions D1–D8 (Open Notebook resume vs descope; admin exposure; secrets platform; availability tier; backup destination; telemetry; data policy; SLO/RPO/RTO) — see `docs/runbooks/deploy-runbook.md` §6.

## Phase 1 — Supervision + alerting trust

- **E1**: upload `ops/supervision/cb-supervise.sh`; resolve the 9 `# ASSUMPTION` markers against live state (SurrealDB binary/args/env file, OpenViking start command, qdrant args — check process cmdlines via cron; never print env values). Run one `reconcile` cycle via cron; create every-minute `cb-supervise-reconcile` cron. Kill -9 the broker PID once and confirm the next reconcile restarts it (V-DR-002 partial).
- **Docs 3**: approve the secret-rotation runbook; schedule the first rotation window; confirm the emergency-compromise flow is understood.
- **Docs 4**: confirm ntfy receipt on the actual subscribed phone (V-ALT-004) — never confirmed to date.

## Phase 2 — Mesh correctness patches

- **E2**: `files-read` live `/opt/data/cloudbrain/handoff/mesh_broker.py` and `anya_omega.py`. Confirm the `POST /handoff/ack` contract (field names), redis handle name, consumer group (`mesh-brokers`), queue derivation, current `/handoff/pending` shape. Amend the patch specs if any assumption is wrong — **never apply blind**.
- **E3**: apply `patches/anya/ANYA_ACK_PATCH.md` (keep `.bak-<UTC>` of the original); `cb-supervise.sh restart anya`; `/health` 200.
- **E4**: apply `patches/anya/ANYA_PENDING_PATCH.md` to the broker (keep `.bak-<UTC>`); restart broker; verify the new pending contract cross-checks against `redis-cli XPENDING mesh:handoff:<q> mesh-brokers` (V-MESH-005).

## Phase 3 — Data protection (ops-security)

**Global ordering rule:** first good backup + first good offsite copy BEFORE any retention trimming. TLS cutover triggers CB-012 credential rotation (separate, auth-gated).

- **A — Preconditions (operator, no VPS needed):** decide Tailscale-only (recommended) vs public TLS; choose S3-compatible offsite provider; provision the backup encryption key file out-of-band (never through chat/cron/outputs); confirm `SURREAL_NS`/`SURREAL_DB`; approve all PROPOSED retention thresholds + RPO/RTO.
- **B — Backup (CB-051):** upload `ops/backup/cb-backup.sh`; create the daily cron (proposed 02:00 UTC) with the key file as job env (never on a command line); trigger once manually — require exit 0, `manifest.json` with per-file sha256, one encrypted artifact, per-component OK lines; negative test with a missing key path (expect exit 1, no artifact); wire failures into the ntfy pattern. (V-BKP-002/003)
- **C — Restore drill (CB-052):** upload `ops/restore/cb-restore-verify.sh`; run the isolated-environment drill first (scratch tree + alternate ports — never the live data dirs on the first pass); require all 19 checks PASS; record the drill timeline for RPO/RTO measurement. (V-BKP-005–008)
- **D — Offsite copy (CB-051):** upload `ops/backup/cb-offsite-push.sh`; nightly cron after the backup job with S3 credentials as job env (out-of-band values only); trigger once — chunked upload completes, remote manifest digest-verified, watermark advances, source set NOT pruned; verify bucket isolation (push credential cannot delete); confirm 3-night failure escalation reaches ntfy. (V-BKP-003/004)
- **E — Retention (CB-050, CB-042):** **E0 first — reconcile trim bounds with engineering's `apply_retention.py`** (5k live / 2k retry / 20k evidence); do not run two enforcers with different bounds. Upload `ops/retention/cb-trim.sh`; dry-run (default) via one-shot cron and inspect the JSON summary; preconditions: good backup + good offsite copy exist, Anya ack fix deployed; schedule recurring trim with `--apply` (evidence trims stay disabled until the evidence exporter exists); wire disk watermarks (75%/90%) into alerting. (V-LIFE-001/002, V-CAP-001–003)
- **F — TLS + firewall (CB-011, CB-013):** option A (Tailscale-only): bind admin to the tailnet interface, verify no public listener via the `ss` checklist. Option B (public TLS): install Caddy static binary via DoH + `curl --resolve`, `caddy validate`, DNS-01 certificates, run on 8443, verify V-TLS-001/V-WEB-001. Add the cert-renewal monitor to the ntfy cron pattern (21-day warning). Provider/host-root action (cannot be done as `hermes`): apply the nftables ruleset from `ops/tls/firewall-notes.md`; verify with an external scan (V-NET-004). **Immediately after cutover: execute CB-012 credential rotation** — everything previously sent over plain HTTP is treated as exposed.
- **Cleanup:** after B–F verified, the superseded pre-split drafts stay archived at the source `staging/_archive/pre-split/` (outside this tree; review, then remove so only one backup/restore/TLS implementation exists). Remove one-shot diagnostic cron jobs; keep only scheduled production jobs.

## Phase 4 — Verification

- **E5**: upload and run `tests/test_mesh.py`, `test_anya.py`, `test_symbollect.py` via one-shot cron jobs. Require zero FAIL, exit 0, JSON summaries captured (V-MESH-001/005/006/008, V-SYM-001..004). V-MESH-002: run the manual consumer-interruption procedure in `tests/README.md`.
- **E7**: run `test_redis.py`, `test_qdrant.py`, `test_surrealdb.py`, `test_health_semantics.py` (V-DATA-004/008/009, V-SVC-005/006). Verify SurrealDB test output contains no credential values. Collect all JSON summaries + UTC timestamps as the evidence pack.

## Phase 5 — Operational readiness

- **Docs 5**: approve all four runbooks as the operated versions; version them; further edits via change control.
- **Docs 6**: runbook usability exercises (V-GOV-003/V-IR-001) — an operator who did NOT author the runbooks executes failure, rollback, and restore procedures using only the runbooks. File defects; revise; re-test.
- **Docs 7**: incident tabletop (CB-083/V-IR-002) — data exposure, corrupted recall, compromised operator identity, host loss.
- **Docs 8**: access certification (V-IAM-009).
- **Docs 9**: restore drill sign-off (V-BKP-005–008) — isolated restore, witnessed, reconciliation report reviewed, record signed.

## Phase 6 — Go / no-go

- **Docs 10**: production readiness review (CB-084) — traceability matrix (V-REL-001), measured SLO/RPO/RTO vs targets (V-REL-002), rollback preflight (V-REL-003). Record the verdict with the exact words **APPROVED**, **APPROVED WITH EXCEPTIONS**, or **REJECTED**, plus approvers, exceptions with expiry, and next review date.
- **E8**: only after E1–E7 green for 24h — disable `cb-mesh-broker-watch` and `cb-anya-watch` (supervisor covers them now). Keep `cb-ntfy-health` untouched. Confirm a supervised restart produces the expected ntfy recovery notice.

## Recurring (after launch)

- Monthly (Suite C): credential-age review, restore sampling, alert-delivery check, access-anomaly review.
- Quarterly (Suite D): full isolated restore, DR exercise, access certification, incident tabletop, retention/deletion audit.
- Annually (Suite E): independent penetration test, threat-model review, SLO/RPO/RTO reassessment, full readiness review.

## Rollback (every phase)

- Every edited VPS file keeps a `.bak-<UTC>`; restore = copy back + `cb-supervise.sh restart <svc>`.
- Supervisor/cron changes: delete the cron job, re-enable the old watchdogs.
- Retention: trims never touch pending entries; re-run with `--dry-run` to confirm no-op.
