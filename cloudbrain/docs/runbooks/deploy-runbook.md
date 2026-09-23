# Cloudbrain Hardened-Stack Deploy Runbook

**Scope:** Production deployment of the tri-dynamic cloudbrain hardened stack on the Hermes VPS (single-host phase). **Memory may inform/scope decisions; it never mints authority.** No plaintext secrets, keys, tokens, or credentials appear in this runbook or in any artifact it produces — secret values are only ever handled through the approved secrets mechanism (see Wave 2).

**Source docs:** `../../../../files/cloudbrain-prod-blueprint/task.md` (waves/CB IDs), `../../../../files/cloudbrain-prod-blueprint/verification.md` (V-gate IDs), `../../../../files/cloudbrain-prod-blueprint/blueprint.md` (target state). Entry criteria for this runbook mirror `verification.md` entry criteria; do not skip them.

**Approver roles:** Release Manager (overall), Security Administrator (Waves 2, 8), Platform Administrator (Waves 3, 6), Data Steward (Waves 4, 6), Application Operator (execution), Readiness Reviewer (sign-off).

---

## Phase 0 — Pre-deploy

### 0.1 Open the change record

1. Create or reference the approved change record (standard/normal; emergency changes follow retrospective review per change-control policy).
2. Record: scope, risk class, reviewer, expected artifact digest(s), planned migrations, verification plan, rollback trigger, and outcome field.
3. Assign owners per wave before starting. A wave with no named owner does not start.

### 0.2 Confirm entry criteria (V-REL-001..003 evidence base)

- [ ] Inventory and dependency map are current (CB-001 evidence).
- [ ] Release candidate is immutable and identified by digest (signed bundle, V-SUP-003..005).
- [ ] Staging matches intended production topology and policy (V-ENV-001, V-ENV-002).
- [ ] **Backups exist for every environment to be changed** — pre-hardening backup CB-003 must have backup ID + digest on record (V-BKP-001).
- [ ] Test identities and synthetic data with unique run IDs are prepared.
- [ ] Alert recipients and maintenance windows confirmed; ntfy device delivery tested (V-ALT-004).
- [ ] Rollback and recovery procedures available: previous artifact, config version, migration compatibility, backup reference (V-REL-003 preflight).
- [ ] All decision points in §8 resolved (or formally accepted as exceptions with expiry).

### 0.3 Change freeze (CB-003)

1. Announce the change window and freeze untracked production changes.
2. Export current non-secret configuration; hash artifacts; take the recoverable pre-hardening backup.
3. Record baseline manifest + backup ID + digest in the evidence set.
4. **Entry checkpoint:** Release Manager signs that freeze is in effect before Wave 1 begins.

### 0.4 Baseline health check

1. Re-run the full current-state verification baseline (blueprint: historical checks are evidence, not guarantee).
2. Record: Redis 6379 PONG, Qdrant 6333/6334 API 200, SurrealDB 8000 /health 200, OpenViking 1933 /health 200, Mesh Broker 8002 /health 200, Anya Omega 8003 /health 200 — as *pre-deploy observed state*, not as pass marks.
3. Any service not answering on its loopback port is a Wave 3 task input, not a silent skip.

---

## Wave 1 — Inventory / baseline (CB-001–CB-003)

**What runs:**

1. CB-001: enumerate host, OS, kernel, packages, service versions, listening sockets, process owners, units, cron jobs, firewall rules, storage paths, data sizes, DNS, certificates, external integrations. Compare against service catalog; every observed item owned and documented (V-INV-001); every listener reconciled with approved port matrix incl. public + overlay scans (V-NET-001).
2. CB-002: classify memory content, embeddings, metadata, logs, audit events, notebook projections, credentials, backups; map producers/processors/stores/destinations/administrators. Evidence: approved data-flow diagram, classification matrix, subprocessor list (V-GOV-001, V-SEC-011).
3. CB-004: assign service owner, security owner, data steward, on-call route, vendor contact per component; publish service catalog + RACI + escalation tree (V-GOV-002).

**Expected staging artifacts:** `../../ops/` inventory diff + disposition list; data-flow diagram + classification matrix; service catalog/RACI (docs-track placement; refer to runbook `deploy-runbook.md` only after approval).

**Approver:** Release Manager (CB-001/003/004), Security Administrator (CB-002).

**Evidence captured:** dated inventory, sanitized socket/process reports, dependency map, baseline manifest + backup digest, change-freeze record, classification matrix.

**Wave gate:** V-INV-001, V-NET-001, V-GOV-001, V-GOV-002, V-BKP-001, V-SEC-011 all PASS. Any FAIL → freeze stays; do not advance.

---

## Wave 2 — Exposure closure (CB-010–CB-016)

**What runs (strict order):**

1. CB-010: establish private administrative access — Tailscale (or approved overlay) as operator path; Hermes and operator endpoints restricted to approved identities/devices; break-glass path independently tested (V-NET-002, V-IAM-001).
2. CB-011: remove public plain HTTP — stop direct public HTTP to Hermes dashboard; TLS 1.2+ at hardened reverse proxy (see `../../ops/tls/Caddyfile`, `../../ops/tls/TLS_NOTES.md`); secure cookies, HSTS where applicable, automated renewal (V-NET-003, V-TLS-001, V-WEB-001).
3. CB-012: rotate and revoke Hermes credentials — replace compromised credential, invalidate prior sessions/tokens, remove plaintext from config APIs (incl. `/api/config` exposure), review auth logs for unauthorized use (V-IAM-002, V-SEC-001, V-WEB-002). **Hermes password is handled one-time, never stored.**
4. CB-013: host firewall default-deny — private-overlay admin + approved TLS ingress only; all data services private (V-NET-001, V-NET-004).
5. CB-014: dedicated Unix identities/files per service — redis, qdrant, surrealdb, openviking, open-notebook, mesh-broker, anya-omega, bifrost, monitoring, backup (V-OS-001, V-OS-002).
6. CB-015: secrets into approved manager/orchestrator credentials — unique principals per service+environment; secrets removed from scripts, env dumps, URLs, arguments, repos (V-SEC-002..005; rotation runbook `secret-rotation-runbook.md`).
7. CB-016: per-service auth — Redis, Qdrant, SurrealDB, OpenViking, Open Notebook, broker, Anya auth or equivalent mutually-authenticated proxy; least-privilege permission matrix; positive + negative tests (V-IAM-003..007).

**Approver:** Security Administrator (per-step sign-off; CB-012 requires explicit confirmation that old credential material fails everywhere).

**Evidence captured:** access-policy export + approved-device test + break-glass record; external reachability report + TLS scan + renewal test; rotation event metadata **without values** + revocation proof + sanitized log review; versioned firewall policy + scan results; identity/permissions report + negative cross-service tests; secret inventory by reference + scan results; principal-to-permission matrix + API test outcomes.

**Wave gate:** V-NET-002/003/004, V-TLS-001, V-WEB-001/002, V-IAM-001/002/003..007, V-SEC-001..005, V-OS-001/002 all PASS. **Abort triggers:** any service publicly reachable that must be private; any credential that cannot be proven revoked; secrets found in logs/args/repos.

---

## Wave 3 — Deterministic lifecycle (CB-020–CB-024)

**What runs:**

1. CB-021 first: pin OS packages, Python runtime, application deps, service binaries; checksums + SBOM; remove unsupported/unused runtimes (V-SUP-001, V-SUP-002).
2. **DECISION POINT — Open Notebook:** deploy supported (CB-022 path) or formally descope via approved ADR (see §8). If deploy: supported Python version, pinned lockfile, private binding + auth, write/read path test, restart persistence (V-ONB-001..004). If descope: remove from production architecture, record approved replacement.
3. CB-020: hardened service units (expected artifacts under `../../ops/supervision/`) for every stack service — dependencies, readiness, graceful shutdown, restart backoff, resource limits, writable paths (V-SVC-001..004). Disable overlapping watchdog crons **only after** units verified.
4. CB-023: separate liveness/readiness/dependency health; readiness fails when service cannot safely accept work (V-SVC-005, V-SVC-006).
5. CB-024: approved-window reboot + process-failure injection — ordered startup, bounded recovery, alert/recovery notices (V-DR-001, V-DR-002).

**Approver:** Platform Administrator; Security Administrator for identity/isolation review.

**Evidence captured:** lockfiles, artifact manifest, SBOM, rebuild log; supported-version record or descope ADR; versioned unit files, boot graph, failure-recovery logs; endpoint contract + dependency-failure tests; reboot timeline + process-kill results + alert evidence.

**Wave gate:** V-SUP-001/002, V-ONB-001..004 (or approved ADR), V-SVC-001..006, V-DR-001/002 all PASS. **Abort triggers:** reboot requires manual startup; crash-looping service; Open Notebook neither healthy nor descoped.

---

## Wave 4 — Data contracts (CB-030–CB-035)

**What runs:**

1. CB-030: publish versioned schemas — memory-candidate, memory-object, handoff envelope, audit event, deletion operation, error response; compatibility + deprecation policy; schema registry (V-DATA-001..003).
2. CB-031: idempotent write coordination — stable event IDs, idempotency keys, duplicate/interruption tests (V-DATA-004/005).
3. CB-032: provenance + lineage — source digest, policy version, model version, actor, timestamps, object versions, destination pointers; orphan scan (V-DATA-006/007).
4. CB-033: scoped retrieval + cache binding — tenant/user/knight/purpose/classification/time filters; cache keys bound to policy, object, embedding-model versions (V-IAM-008, V-DATA-008/009).
5. CB-034: deletion fan-out — tombstone, Redis invalidation, Qdrant removal, SurrealDB lifecycle, Open Notebook removal, NotebookLM projection handling; re-ingestion block (V-DEL-001..005).
6. CB-035: NotebookLM receive-only adapter — one-way minimized projection; blocked reverse-write test (V-DATA-010, V-SEC-010).

**Approver:** Data Steward (CB-030/032/034/035), Security Administrator (CB-033).

**Evidence captured:** schema registry + valid/invalid examples + compatibility matrix; duplicate/interruption test results; lineage queries + orphan scan; retrieval policy tests + isolation report; deletion state machine + per-store receipts; adapter policy + blocked-write tests.

**Wave gate:** V-DATA-001..010, V-DEL-001..005, V-IAM-008, V-SEC-010/011 all PASS. **Abort triggers:** cross-scope read possible; stale cache servable; deleted content re-ingestible.

---

## Wave 5 — Handoff integrity (CB-040–CB-044)

**What runs:**

1. CB-040: broker ack semantics — ack only after durable handling; visibility timeout, bounded retry, retry count, poison handling, admin replay. Expected: apply Anya patches in `../../patches/anya/ANYA_ACK_PATCH.md` (V-MESH-001..004).
2. CB-041: real consumer-group pending state — `/handoff/pending` reports pending count, oldest age, owner, delivery attempts, reconciled with native Redis group state. Expected: `../../patches/anya/ANYA_PENDING_PATCH.md` (V-MESH-005).
3. CB-042: bound streams/logs/dead letters — capacity + retention for live/retry/quarantine/dead-letter/idempotency/audit; audit export before trim; growth + old-pending alerts. Expected: `../../ops/retention/apply_retention.py` + `../../ops/retention/RETENTION_POLICY.md` (V-CAP-001..003).
4. CB-043: Anya policy hardening — authenticated knight registration/routing, versioned policy, integrity-protected registry, capability/type/expiry/replay/destination rules, authority verbs fail-closed (V-MESH-006..010).
5. CB-044: Symbollect v1 frozen — golden vectors, round-trip property tests, canonical stability, fuzzing, size/depth limits, version negotiation (V-SYM-001..004).

**Approver:** Platform Administrator; Security Administrator for CB-043 (adversarial tests).

**Evidence captured:** state diagram + interruption/replay tests; pending-state API contract + side-by-side group report; retention config + fill/trim results; policy bundle + adversarial results + registry-change audit; golden vectors + fuzz report + compat policy.

**Wave gate:** V-MESH-001..010, V-CAP-001..003, V-SYM-001..004 all PASS. **Abort triggers:** unacked message acknowledged early; authority verb reaches a destination; unbounded stream growth.

---

## Wave 6 — Backup / recovery proof (CB-050–CB-053)

**What runs:**

1. CB-050: persistence + retention policy — Redis durability decision (disposable vs durable), retention for vectors/records/notebooks/logs/audits/dead letters/backups, legal-hold behavior (V-LIFE-001/002).
2. CB-051: automated encrypted backups — SurrealDB, Qdrant, Open Notebook, registry, schemas, config, audit indexes; ≥1 isolated off-host copy with separate key control. Expected: `../../ops/backup/` job records + catalog (V-BKP-002..004).
3. CB-052: full + granular restore into isolated environment — counts, digests, lineage, vector retrieval, notebook content, policy; sampled object restore; end-to-end flows against restored environment (V-BKP-005..008). Expected: `restore-runbook.md` exercised by a non-author operator (V-GOV-003).
4. CB-053: DR exercise — simulate host loss, rebuild from approved artifacts, restore, safe endpoint change, measured RPO/RTO (V-DR-003/004).

**Approver:** Platform Administrator + Data Steward; release cannot proceed until CB-052 passes — **backups count only after a clean restore is demonstrated** (blueprint principle 6).

**Evidence captured:** approved retention schedule + configured TTLs; backup catalog + encryption/isolation proof; restore report + reconciled checksums + defect log; DR timeline + gaps/owners + accepted RPO/RTO.

**Wave gate:** V-LIFE-001/002, V-BKP-002..008, V-DR-003/004 all PASS. **Abort triggers:** restore fails; production compromise can silently destroy all backup copies; RPO/RTO not met and not formally accepted.

---

## Wave 7 — Observability (CB-060–CB-064)

**What runs:**

1. CB-060: metrics + dashboards — golden signals, host saturation, write/recall outcomes, queue depth/age, deletion backlog, backup freshness, cert expiry (V-OBS-001..003).
2. CB-061: structured logs + traces — JSON schema, correlation IDs, trace propagation, redaction, centralized storage + retention (V-OBS-004..006).
3. CB-062: audit trail — append-only, integrity-protected, access-controlled, exported off-host; gap/tamper/export-failure alerts (V-AUD-001..004).
4. CB-063: alert routing — retained alert state, severity, dedup, escalation, silencing; ntfy kept for operator notification; test delivery on the actual subscribed device (V-ALT-001..004).
5. CB-064: publish remaining runbooks (deploy, rollback, rotation, service failure, backlog, disk pressure, cert failure, restore, deletion failure, security incident) and time operator exercises (`incident-response-runbook.md`) (V-GOV-003, V-IR-001).

**Approver:** Platform Administrator; Security Administrator (CB-062 audit integrity).

**Evidence captured:** dashboard export + metric catalog; log schema + end-to-end trace + redaction tests; audit chain validation + off-host sample; routing policy + ack'd test alerts + escalation drill; approved runbooks + timed exercise records.

**Wave gate:** V-OBS-001..006, V-AUD-001..004, V-ALT-001..004, V-GOV-003, V-IR-001 all PASS. **Abort triggers:** telemetry leaks prohibited values; audit export silently drops events.

---

## Wave 8 — Release discipline (CB-070–CB-073)

**What runs:**

1. CB-070: CI gates — format, unit, schema, contract, integration, secret, static-analysis, dependency, artifact-integrity per change; protected pipeline (V-CICD-001/002).
2. CB-071: signed release artifacts — immutable artifacts, manifest, SBOM, provenance, checksums, CAMELOT-OS signer-class binding; independent verification (V-SUP-003..005).
3. CB-072: staging parity — topology, policy, schema, versions; synthetic data, separate credentials; drift scan (V-ENV-001/002).
4. CB-073: canary rollout + rollback — same signed artifact (digest chain, V-SUP-005); error/latency/integrity/saturation abort thresholds; automated rollback; migration forward/backward recovery (V-CICD-003..006).

**Approver:** Release Manager + Security Administrator (signer binding).

**Evidence captured:** pipeline records incl. sample failed build; signed release bundle + independent verification; parity report + separation report; canary/rollback run + artifact-digest continuity + migration matrix.

**Wave gate:** V-CICD-001..006, V-SUP-003..005, V-ENV-001/002 all PASS.

### Canary procedure

1. Promote the identical signed artifact (verify digest chain V-SUP-005) to a limited production slice.
2. Run canary smoke tests: synthetic write → recall → handoff → quarantine → delete cycle (Suite B subset).
3. Observe for the agreed window against abort thresholds:

   | Signal | Abort threshold |
   |---|---|
   | Error rate | > agreed p% above baseline over 5 min |
   | p95 recall latency | > 1.5 s sustained (or accepted objective) |
   | p95 handoff acceptance latency | > 250 ms sustained |
   | Integrity failures | any digest/quarantine/ack violation = immediate abort |
   | Saturation | CPU/mem/disk past agreed high-watermark |

4. **Automatic abort:** on threshold breach, rollout stops or rolls back per V-CICD-004 policy; alert fires; no manual override without Security Administrator approval and audit record.
5. On clean observation: complete rollout; record artifact digest, config version, migrations, operator, evidence.

### Rollback procedure

1. **Preflight (before every deploy):** confirm previous artifact + config version on hand, data compatibility with previous release, operator access, latest backup reference, tested rollback steps (V-REL-003).
2. On abort decision: stop rollout, restore previous artifact + configuration (V-CICD-005), verify synthetic flows pass.
3. For migration rollback: follow the tested forward/backward or roll-forward path (V-CICD-006); backup taken immediately before destructive migrations is the recovery point.
4. Record: rollback timeline, cause, evidence, and whether rollback itself passed verification.

### Abort thresholds (global, any wave)

Stop the deploy if any of these appear: public plain-HTTP admin or public database exposure; compromised/shared credential still active; secrets in logs/source/APIs/URLs/args; missing auth or cross-tenant isolation on a data path; Open Notebook required but not healthy/supported and not descoped; unacked-message accumulation or unbounded stream/log growth; failure of write/recall/quarantine/deletion/backup/restore paths; reboot recovery failure; no off-host integrity-protected audit; no tested rollback/DR path; unresolved critical/high finding without time-bounded acceptance; unowned production service. (These are the task.md launch blockers; any one blocks.)

---

## Wave 9 — Readiness proof (CB-080–CB-084)

**What runs:**

1. CB-080: capacity baselines — storage growth, embedding throughput, recall latency, projection throughput, queue capacity, host saturation; 30/90/365-day forecast (V-PERF-001/002).
2. CB-081: load/soak/overload — expected peak, 2× peak, sustained soak, burst, slow dependencies, disk pressure (V-PERF-003..007).
3. CB-082: security testing — config review, vuln assessment, authz tests, fuzzing, dep scans, **independent penetration test** against staging + approved production scope (V-SEC-006..012).
4. CB-083: access review + incident tabletop — identity/privilege/session/key reconciliation; data-exposure, integrity-failure, outage scenarios (V-IAM-009, V-IR-002).
5. CB-084: production readiness review — evidence reconciliation, residual risks, SLO/RPO/RTO acceptance, operations, rollback readiness (V-REL-001..003).

**Approver:** Readiness Reviewer + all role approvers (owner sign-off on V-PERF-002 forecast and V-REL-002 objectives).

**Evidence captured:** baseline + forecast report; load profiles + latency/error graphs + remediation list; pen-test report + retest + risk acceptances; signed access certification + tabletop record; signed readiness decision + exception register.

**Wave gate:** all V-PERF, V-SEC-006..012, V-IAM-009, V-IR-002, V-REL-001..003 PASS or formally accepted.

---

## Post-deploy

### Suite B verification (every release candidate)

1. Run the full Suite B battery: all contract + integration tests; synthetic write, recall, handoff, quarantine, deletion paths; staging parity (V-ENV-001); vulnerability scan (V-SEC-006); backup freshness (V-BKP-002/003 check); canary smoke tests (V-CICD-003).
2. Reconcile P0/P1 tasks → verification IDs → evidence: traceability matrix (V-REL-001).
3. Review measured availability, latency, capacity, RPO, RTO, security, cost vs accepted targets (V-REL-002).
4. Confirm rollback readiness preflight is current (V-REL-003).

### Smoke tests (immediately after deploy)

- Health: Redis PONG, Qdrant API 200, SurrealDB /health 200, OpenViking /health 200, broker 8002 /health, Anya 8003 /health, Open Notebook (if in scope) ready via approved route only.
- Paths: one synthetic memory-candidate → promotion → scoped recall; one handoff publish → claim → ack; one authority-verb message → quarantine confirmed.
- Negative: one unauthenticated API attempt per data service must fail; one cross-scope recall attempt must return nothing.
- Alerts: force one warning + recovery; confirm ntfy delivery on subscribed device (V-ALT-004); confirm recovery notice.

### Sign-off and release verdict

1. Readiness Reviewer records: verdict, release digest, environment, date, approvers, exceptions, next review date in the signed evidence manifest.
2. Use exactly one verdict:
   - **APPROVED** — every mandatory gate passes; no launch blocker remains.
   - **APPROVED WITH EXCEPTIONS** — no critical blocker remains; each exception has owner, compensating control, expiry, remediation date.
   - **REJECTED** — a launch blocker or mandatory test failed, was blocked, or was not run. (Remediation plan + re-verification required before any re-attempt.)
3. Hash and sign the evidence package; store read-only; keep a copy outside the production host (verification.md evidence policy).
4. Close the change record with outcome; lift the change freeze only after sign-off.

---

## Decision points — resolve before proceeding

These must be resolved before the waves named; none may be deferred silently:

| # | Decision | Resolve before | Options | If unresolved |
|---|---|---|---|---|
| D1 | **Open Notebook: supported deploy vs formal descope** | End of Wave 3 | Supported runtime + deps, private + auth, healthy (V-ONB-001..004) · or approved descope ADR with named replacement | CB-022 blocks Wave 3 gate; launch blocker |
| D2 | **Administrative exposure** | Wave 2 | Tailscale-only · or approved public TLS ingress with identity-aware access (V-NET-002/003, V-TLS-001) | Wave 2 cannot close |
| D3 | **Secrets platform** | Wave 2 (CB-015) | Managed secrets service · host-local encrypted store · orchestrator credentials | No per-service auth; Wave 2 gate fails |
| D4 | **Availability tier** | Wave 3 | Accepted single-host risk (documented, time-bounded) · or multi-node target with replicated stores | SLO/RPO/RTO targets (V-REL-002, V-DR-004) cannot be approved |
| D5 | **Backup destination** | Wave 6 (CB-051) | Provider, isolation model, retention, key ownership — with off-host copy + separate key control | V-BKP-004 fails; launch blocker |
| D6 | **Telemetry platform** | Wave 7 | Metrics/logs/traces components + retained alert-state (ntfy remains notification-only) | V-OBS/V-ALT gates cannot pass |
| D7 | **Data policy** | Wave 4 | Classifications, retention periods, legal holds, export/deletion deadlines (Data Steward sign-off) | V-GOV-001, V-LIFE-001/002, V-DEL block |
| D8 | **Service objectives** | Wave 9 (CB-084) | Final availability, latency, RPO, RTO approved by owner (initial proposal in blueprint; measured, not claimed) | V-REL-002 cannot pass |

Any deferred decision becomes an **exception** in the readiness register with owner, compensating control, expiry, and remediation date — and never for a launch blocker.

---

## Quick-reference wave checklist

| Wave | CB range | Gate set (all must PASS) | Approver |
|---|---|---|---|
| 1 Inventory | CB-001–003 | V-INV-001, V-NET-001, V-GOV-001/002, V-BKP-001, V-SEC-011 | Release Mgr / Security Admin |
| 2 Exposure | CB-010–016 | V-NET-002/003/004, V-TLS-001, V-WEB-001/002, V-IAM-001/002/003–007, V-SEC-001–005, V-OS-001/002 | Security Admin |
| 3 Lifecycle | CB-020–024 | V-SUP-001/002, V-ONB-001–004 (or ADR), V-SVC-001–006, V-DR-001/002 | Platform Admin |
| 4 Contracts | CB-030–035 | V-DATA-001–010, V-DEL-001–005, V-IAM-008, V-SEC-010/011 | Data Steward |
| 5 Handoff | CB-040–044 | V-MESH-001–010, V-CAP-001–003, V-SYM-001–004 | Platform Admin |
| 6 Backup/DR | CB-050–053 | V-LIFE-001/002, V-BKP-002–008, V-DR-003/004 | Platform Admin / Data Steward |
| 7 Observability | CB-060–064 | V-OBS-001–006, V-AUD-001–004, V-ALT-001–004, V-GOV-003, V-IR-001 | Platform Admin / Security Admin |
| 8 Release | CB-070–073 | V-CICD-001–006, V-SUP-003–005, V-ENV-001/002 | Release Mgr / Security Admin |
| 9 Readiness | CB-080–084 | V-PERF-001–007, V-SEC-006–012, V-IAM-009, V-IR-002, V-REL-001–003 | Readiness Reviewer + all |

Related staging artifacts (sibling tracks, referenced not duplicated): `../../patches/anya/ANYA_ACK_PATCH.md`, `../../patches/anya/ANYA_PENDING_PATCH.md`, `../../ops/retention/RETENTION_POLICY.md`, `../../ops/retention/apply_retention.py`, `../../ops/supervision/` (service units), `../../ops/tls/Caddyfile`, `../../ops/tls/TLS_NOTES.md`, `../../ops/backup/` (backup job records), `deploy-runbook.md`, `restore-runbook.md`, `secret-rotation-runbook.md`, `incident-response-runbook.md`, `../../tests/` (test assets).
