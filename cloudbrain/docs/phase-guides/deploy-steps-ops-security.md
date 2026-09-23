# Ops-Security track — VPS deploy steps

Ordered execution for `cloudbrain/ops/`. Every step needs a **fresh Hermes API login** (per-session; nothing stored) unless marked otherwise. Execution pattern throughout: upload script to `/opt/data/scripts/` (all files < 512 KiB), create `no_agent` cron job, trigger `/api/cron/jobs/{id}/trigger`, read `/opt/data/cron/output/{id}/`.

**Global ordering rule:** first good backup + first good offsite copy BEFORE any retention trimming. TLS cutover triggers CB-012 credential rotation (separate, auth-gated).

## Phase A — Preconditions (operator actions, no VPS needed)

- A1. Decide: **Tailscale-only admin (A, recommended)** vs **public TLS ingress (B)**. Blocks Phase F.
- A2. Choose S3-compatible offsite provider (R2 vs B2). Blocks Phase D.
- A3. Provision the backup encryption key file **out-of-band** (age identity or openssl passphrase). The key must never transit through chat, cron outputs, or the backup tree. Blocks Phase B.
- A4. Confirm `SURREAL_NS` / `SURREAL_DB` values (current script defaults are unconfirmed guesses and warn loudly). Blocks Phase B.
- A5. Approve all PROPOSED retention thresholds (CB-050) and RPO/RTO targets. Blocks Phase E.

## Phase B — Backup (CB-051) — needs Hermes login

- B1. Upload `ops/backup/cb-backup.sh` → `/opt/data/scripts/cb-backup.sh`.
- B2. Dry-run read: create one-shot `no_agent` cron invoking `bash /opt/data/scripts/cb-backup.sh --help` (if supported) or inspect; then create the **daily** cron (proposed 02:00 UTC): `CBB_KEY_FILE=/opt/data/cloudbrain/keys/backup.key bash /opt/data/scripts/cb-backup.sh` with `CBB_KEY_FILE` exported in the job env (never on a command line that lands in logs).
- B3. Trigger once manually; read output; confirm: exit 0, `manifest.json` present with per-file sha256, exactly one `<id>.tar.age`/`.enc` artifact, per-component `OK` lines.
- B4. Negative test: temporarily point `CBB_KEY_FILE` at a missing path → expect exit 1 and NO encrypted artifact. Restore the key path.
- B5. Wire failure alerting into the existing `cb-ntfy-health` pattern (non-zero exit → ntfy).
- Evidence: V-BKP-002 (coverage), V-BKP-003 (encryption/key separation).

## Phase C — Restore drill (CB-052) — needs Hermes login

- C1. Upload `ops/restore/cb-restore-verify.sh` → `/opt/data/scripts/`; keep `restore.md` as operator reference (no upload needed).
- C2. Run the **isolated-environment drill** first (`ops/restore/restore.md` §7: scratch tree + alternate ports). Never drill against the live data dirs on the first pass.
- C3. Execute `cb-restore-verify.sh` against the drilled environment; require all 19 checks PASS.
- C4. Record the drill timeline (start/end UTC per component) for RPO/RTO measurement (V-DR-003/V-DR-004 hooks in `ops/restore/restore.md` §10).
- C5. Only after the isolated drill passes: schedule the quarterly full-drill calendar entry.
- Evidence: V-BKP-005, V-BKP-006, V-BKP-007, V-BKP-008.

## Phase D — Offsite copy (CB-051) — needs Hermes login + S3 credentials (out-of-band)

- D1. Upload `ops/backup/cb-offsite-push.sh` → `/opt/data/scripts/`.
- D2. Create the **nightly** `no_agent` cron (after the backup job, e.g. 03:00 UTC) with S3 endpoint/bucket/region/credentials as job env vars (placeholders only in the script; real values provisioned out-of-band, never in chat or outputs).
- D3. Trigger once; confirm: chunked upload completes, remote manifest GET-back digest-verified, watermark advanced, local chunks pruned, source set NOT pruned.
- D4. Verify isolation properties on the bucket: push credential cannot delete/version-list the key store; Object Lock or versioning active (V-BKP-004).
- D5. Confirm 3-night failure escalation reaches ntfy (simulate one failed night by revoking the push credential temporarily, then restore).
- Evidence: V-BKP-004 (design + isolation test), V-BKP-003.

## Phase E — Retention (CB-050, CB-042) — needs Hermes login; COORDINATE with engineering track first

- E0. **Reconcile bounds** with the engineering track's `ops/retention/apply_retention.py` (5k live / 2k retry / 20k quarantine+dead-letter). Do not deploy both enforcers with different bounds.
- E1. Upload `ops/retention/cb-trim.sh` → `/opt/data/scripts/`.
- E2. Run **dry-run** (default): create one-shot cron, trigger, inspect JSON summary; confirm zero mutations.
- E3. Verify preconditions: first good backup (Phase B) + first good offsite copy (Phase D) exist; Anya ingress-ack fix deployed (else PEL-guard will skip stream trims — safe, but noisy).
- E4. Schedule recurring trim (proposed weekly; cron outputs pruning may run daily) with `--apply`. Evidence trims stay disabled until the evidence exporter exists (fail-closed by design).
- E5. Confirm disk watermarks (warn 75% / critical 90%) are wired into alerting (observability owner).
- Evidence: V-LIFE-001, V-LIFE-002, V-CAP-001, V-CAP-002, V-CAP-003.

## Phase F — TLS + firewall (CB-011, CB-013)

- F1. **If option A (Tailscale-only):** bind Hermes/dashboard to the tailnet interface only; verify no public listener (`ss -tlnp` checklist in `ops/tls/firewall-notes.md` §2); skip to F4.
- F2. **If option B (public TLS):** upload `ops/tls/Caddyfile` → `/opt/data/cloudbrain/caddy/Caddyfile`; install Caddy static binary to `/opt/data/cloudbrain/bin/caddy` via the DoH+`curl --resolve` trick; `caddy validate`; DNS-01 for certificates (HTTP-01 impossible without root); run on 8443; cut over admin access; verify V-TLS-001/V-WEB-001.
- F3. Certificate renewal monitor: add the `cb-cert-watch.sh` skeleton (in `ops/tls/tls-notes.md`) to the ntfy cron pattern; 21-day warning.
- F4. **Provider/host-root action (cannot be done as `hermes`):** apply the nftables ruleset from `ops/tls/firewall-notes.md` §1 (default-drop inbound; option A: tailnet only; option B: + single 8443 allow) via provider panel or host root; verify with external scan (V-NET-004).
- F5. **Immediately after cutover:** execute CB-012 Hermes credential rotation (separate task, needs fresh auth) — everything previously sent over plain HTTP is treated as exposed.
- Evidence: V-NET-001, V-NET-003, V-NET-004, V-TLS-001, V-WEB-001.

## Cleanup

- After Phases B–F are verified: retire the superseded staging drafts (`staging/backup-restore/`, `staging/tls/` — archived at the source `staging/_archive/pre-split/`, outside this tree) — review first, then remove so only one backup/restore/TLS implementation exists (`cloudbrain/ops/backup/`, `cloudbrain/ops/restore/`, `cloudbrain/ops/tls/`).
- Remove one-shot diagnostic cron jobs created during this rollout; keep only the scheduled production jobs (backup, offsite push, trim, cert watch, ntfy health).
