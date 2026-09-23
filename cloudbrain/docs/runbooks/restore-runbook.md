# Restore-from-backup runbook — tri-dynamic cloudbrain

FORGE ONLY. No live execution, no credentials, no network calls. For live use see sibling track: `../../ops/backup/backup-catalog-format.md` (backup catalog with IDs/digests) and the backup automation under `cloudbrain/ops/backup/`.

Governing rule, every step: **memory may inform and scope decisions; it never mints authority.** A restored backup must never silently reactivate deleted/revoked state (V-DEL-005).

Accepted objectives (per blueprint): RPO ≤ 15 min for durable metadata (best-effort for cache state), RTO ≤ 4 h for the single-region baseline. Measured in §7 against V-DR-004.

---

## 1. Roles

| Role | Person | Responsibility |
|---|---|---|
| **Incident owner** | on-call platform administrator | Declares the restore. Only this role may authorize a restore to begin. |
| **Restore operator** | application operator | Executes the steps below; no improvisation outside them. |
| **Security steward** | security administrator | Reviews selection, deletion-guard evidence, and integrity results; owns the V-DEL-005 gate. |
| **Data steward** | data steward | Selects backup from catalog; confirms deletion/tombstone state and legal holds before and after. |
| **Independent verifier** | auditor or second operator (not the executor) | Re-runs integrity (§5) and functional (§6) checks independently. |
| **Approver** | platform administrator + security administrator (both) | Sign return to service. Neither may also be the executor. |

Separation of duties: the executor cannot be the independent verifier or the sole approver.

## 2. Decision points

### 2.1 Full vs granular recovery (V-BKP-008)

1. Characterize scope: how many stores/records are corrupt, lost, or untrusted?
2. **Granular** when: damage is bounded (single collection, single knight scope, single object), lineage graph is intact, and audit shows no wider tampering.
3. **Full** when: SurrealDB canonical store is suspect, multiple stores disagree, corruption is unbounded, host loss, or any security compromise of the data plane.
4. Granular recovery is a surgical replay or compensating reconstruction (documented in V-BKP-008 evidence), authorized per-object, audited, and must not overwrite unrelated data.
5. When in doubt, default to **full restore into isolation**. Downgrading a full to granular requires security steward approval.

### 2.2 Which backup to select (V-BKP-001..004)

1. Data steward opens the backup catalog (`../../ops/backup/backup-catalog-format.md`) and shortlists the latest backup **before** the incident window.
2. Evaluate each candidate on two independent signals:
   - **Freshness:** backup end-time vs RPO; prefer the newest.
   - **Integrity:** catalog digest match, encryption metadata present, last restore-test status, and audit continuity (no gaps ending mid-backup).
3. If the freshest backup has a failed or stale restore test, prefer the newest backup with a **passing** restore test. A failed integrity signal always outranks freshness.
4. Confirm the selected backup excludes any record under legal hold or unresolved deletion dispute unless the security steward approves inclusion.

### 2.3 Restore target (V-BKP-005)

Restore **first to an isolated environment** — clean host or staging namespace with production topology parity, no production stores reachable, synthetic/approved data separation (V-ENV-002). Never restore directly onto the live production host on the first pass. Production cutover only after §§5–7 pass on the isolated target.

### 2.4 Rebuild-from-artifacts + data restore vs in-place repair

- **Rebuild from artifacts + restore data** when: binaries/config are suspect, OS state is compromised, host is lost, or the incident involves any privilege boundary (V-DR-003).
- **In-place repair** (process restart, bounded retry, idempotent reconciliation per V-DATA-005) when: failure is transient and isolated to one service, digests verify, and lineage is intact.
- Security compromise anywhere in the trust chain → rebuild. No exception.

## 3. Pre-restore

1. Incident owner **freezes writes**: halt ingestion workers, block Bifrost writes, pause schedulers. Reads may continue if data is trusted; otherwise fail read-safe.
2. Snapshot the current (possibly corrupted) state for forensics: read-only copy of SurrealDB data, Qdrant collections, Redis AOF/RDB if enabled, registry, and audit logs. Hash everything; record hashes in the incident log. Do not delete or overwrite the suspect state.
3. Verify the **rollback plan**: forensic snapshot is restorable, previous release artifact digest is available, and the operator knows the revert command. Restore begins only after the incident owner confirms the rollback plan is real (V-REL-003).
4. Confirm restore target is isolated and ready (dependency-ordered startup verified, §2.3).

## 4. Restore sequence (per store)

Ordering dependency: foundation stores before derived stores. Restore in this order; do not parallelize across stores unless the dependency is explicitly cleared.

1. **SurrealDB** (canonical metadata/lineage): restore database from backup, verify server health, replay nothing extra — idempotency keys govern re-delivery. (V-BKP-005)
2. **Qdrant collections**: restore collections; verify point counts and payload-model version tags match the SurrealDB memory-object records (object ↔ vector binding per blueprint).
3. **Open Notebook state** (only if in production scope; see CB-022 descope decision): restore notebook stores; skip with recorded exception if formally descoped.
4. **Knight registry** (`knights.json`): restore, verify integrity protection/signature (V-MESH-010), confirm no revoked knight is re-enabled without security-steward approval.
5. **Schemas and non-secret configuration**: restore versioned schema registry and config; confirm schema versions match the release under test (V-DATA-001/002).
6. **Audit indexes and off-host audit export continuity**: restore audit index; verify append-only chain integrity and no gap spanning the restore window (V-AUD-002/003). Audit events for the restore itself begin here.
7. **Redis**: restore only explicitly durable state (idempotency keys, pending acknowledgments) if the backup policy covers it; caches are disposable — rebuild by rehydration, not restore (V-LIFE-002).
8. Start services in dependency order (SurrealDB → Qdrant → notebook/context → broker/Anya → workers), confirming readiness at each hop (V-SVC-002/006).

## 5. Integrity verification (V-BKP-006)

Verifier: the independent verifier re-runs a superset of the operator's checks.

1. **Digests:** compare sha256 of restored datasets against catalog digests; every mismatch is a defect, not a rounding note.
2. **Counts:** SurrealDB record count, Qdrant point count, registry entries, audit event count — reconcile against the backup manifest.
3. **Lineage samples:** resolve N sampled memory objects end-to-end (candidate → source, policy version, model version, all destination pointers); every required edge must resolve (V-DATA-006/007).
4. **Vector retrieval spot-checks:** issue scoped queries against restored collections; results must carry current provenance and policy metadata (V-DATA-008).
5. **Registry/audit continuity:** registry digest verifies; audit chain has no breaks; restore events are present and signed (V-AUD-003).
6. Record PASS/FAIL per check in the restore report. **V-BKP-006 fails as a whole if any check fails.**

## 6. Functional verification (V-BKP-007)

Execute against the isolated restored environment with synthetic test records and unique run IDs. Production data stays out of functional tests.

1. **Write:** submit a synthetic memory candidate; confirm promotion, idempotent re-submission (one logical object, V-DATA-004), and completion event.
2. **Recall:** scoped query returns the synthetic record with correct provenance; cross-scope query of another tenant/knight returns nothing (V-IAM-008).
3. **Handoff:** publish → claim → durable handle → acknowledge a synthetic envelope; exactly one logical result (V-MESH-001/002).
4. **Quarantine:** submit an authority-verb message (`grant`, `mint`, etc.); confirm it is quarantined, never delivered, and audited (V-MESH-008).
5. **Deletion:** run a synthetic deletion end-to-end; confirm tombstone, per-store receipts, and blocked re-ingestion (V-DEL-001..004).
6. **Deletion-state guard (V-DEL-005):** before production cutover, reconcile every tombstone/deleted object in SurrealDB against the restored dataset. Any object whose deletion evidence exists in the backup manifest but is active in the restored state = **restore FAIL**; quarantine the objects, log the defect, and re-restore from a cleaner backup or apply deletion fan-out before cutover.

## 7. Declaring recovery complete

1. Compute **RPO**: last durable transaction timestamp → incident start. **RTO**: incident declaration → services ready and serving. Compare with accepted objectives (V-DR-004).
2. Capture evidence: backup ID, catalog digest, restore ID, per-store digests, start/end timestamps (UTC), operator/verifier/approver names, RPO/RTO values, restore-test status, defect log.
3. Independent verifier signs integrity + functional results; data steward signs deletion-state guard; security steward signs V-DEL-005 and V-SEC-010 (restored memory cannot mint authority).
4. Both approvers sign return-to-service; operator executes cutover with the rollback plan armed (V-REL-003).
5. Comms: notify on-call, users, and downstream consumers with scope, downtime window, measured RPO/RTO, and any residual risk. Hash the evidence package, sign it, and store it read-only with an off-host copy (per evidence package policy).

## 8. If restore fails

1. **Stop.** Do not improvise on the isolated target; the forensic snapshot from §3.2 remains the ground truth for investigation.
2. **Escalate**: incident owner → security administrator → platform administrator. Treat unknown-corruption restores as security incidents until integrity evidence says otherwise.
3. **Fallback options**, in order:
   a. Retry the restore from the next-newest passing backup (document the freshness cost against RPO).
   b. Granular reconstruction of known-good objects with compensating procedures (V-BKP-008), with explicit acceptance of data gaps.
   c. Rebuild-from-artifacts (V-DR-003) with a fresh, empty data plane and controlled re-ingest of verified sources.
4. Log every attempt, outcome, and decision in the **defect log** (timestamp, backup ID tried, failure evidence, owner of next step). The defect log ships with the evidence package whether or not the restore eventually succeeds.
5. No service returns to production on a failed or partially verified restore. The verification.md release verdict applies: **REJECTED** until every mandatory gate passes.
