# Camelot-OS Low-Level Design Document (LLDD)
## VPS Hub / Twin-Brain Fencing / Shadow Brain Continuity

**Document ID:** `CAMELOT-OS-SADD-LLDD-v2.1-20260913-LLDD`  
**Version:** `2.1.0`  
**Date:** `2026-09-13`  
**Status:** `IMPLEMENTATION-GOVERNED | PARTIALLY DEPLOYED | SHADOW-BRAIN DESIGN APPROVED`  
**Scope:** Camelot-OS VPS Hub / Cybertronia and governed node-local continuity services.

---

## 1. Runtime Service Registry

| Service | Runtime | Default Bind | MemoryMax | Primary Responsibility |
|---|---|---:|---:|---|
| `camelot-bifrost` | Go native | loopback / governed mesh | 512 MiB | signed transport admission only |
| `camelot-sentinel` | Rust native | 127.0.0.1:3002 | 256 MiB | policy, lease, revocation |
| `camelot-epoch-fencer` | Rust native | 127.0.0.1:3014 | 128 MiB | Twin-Brain heartbeat, promotion, signed epoch |
| `camelot-vfs-guardian` | Rust native | 127.0.0.1:3003 | 256 MiB | signed VFS preflight |
| `camelot-node-agent` | Rust + Wasmtime | 127.0.0.1:3010 | 448 MiB | bounded no-host-import WASM |
| `camelot-state-service` | Rust + SQLite | 127.0.0.1:3012 | 256 MiB | authoritative snapshot, replay, SSE |
| `camelot-gideon` | Rust native | 127.0.0.1:3011 | 256 MiB | independent evidence verdict |
| `camelot-arthur` | Rust native | 127.0.0.1:3013 | 128 MiB | final resolution |
| `camelot-receipt-service` | Rust + SQLite | 127.0.0.1:3001 | 256 MiB | signed receipt chain |
| `camelot-shadowd` | Rust native | 127.0.0.1:4190 | bounded by systemd | ephemeral Shadow Subspace |
| `camelot-shadow-brain` | Rust native | local only | 384 MiB | local cognition and retrieval |
| `camelot-ukg-sync` | Rust/Go native | local/Bifrost only | 96 MiB | Crown -> node UKG synchronization |
| `camelot-reconciler` | Rust native | local only | 128 MiB | offline journal reconciliation |
| `camelot-forge-crystal` | on-demand CLI | none | on demand | QR/NFC recovery crystal generation/verify |

The last four continuity services are design targets and must not be marked deployed until implementation and CI exist.

---

## 2. Signed Authority Epoch Contract

### 2.1 `authority-epoch/1`

```json
{
  "schemaVersion": "authority-epoch/1",
  "certificateId": "uuid",
  "epoch": 42,
  "activeBrain": "notebooklm",
  "previousBrain": "open-notebook",
  "promotionMode": "PLANNED",
  "promotedAt": "RFC3339",
  "reason": "planned handoff",
  "receiptHeadSequence": 1882,
  "stateDigest": "sha256:...",
  "signerPublicKey": "...",
  "signature": "..."
}
```

### 2.2 Fencer API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | process liveness |
| GET | `/health/ready` | signed-state readiness |
| GET | `/v1/epoch` | current certificate + brain status |
| POST | `/v1/brains/heartbeat` | submit Open-Notebook/NotebookLM heartbeat |
| POST | `/v1/promote` | perform planned/failover promotion |

Promotion is internal only and requires both the normal fencer bearer credential and a separate server-side promotion assertion.

### 2.3 Heartbeat contract

```json
{
  "brainId": "open-notebook",
  "observedEpoch": 42,
  "ready": true,
  "receiptHeadSequence": 1882,
  "stateDigest": "sha256:..."
}
```

Heartbeat freshness defaults to a short bounded window and is policy-configurable.

---

## 3. Dynamic Epoch Consumer Rules

Each authority-sensitive service uses a verified `EpochSource`.

Pseudo-rule:

```text
certificate = read(epoch.json)
verify signature with pinned Epoch Fencer public key
assert certificate.epoch > 0
currentEpoch = certificate.epoch
compare request/lease/attestation/verdict epoch to currentEpoch
reject or quarantine stale authority
```

No authority service may rely solely on a startup environment integer once dynamic epoch mode is enabled.

---

## 4. Shadow Brain Service Design

### 4.1 Service responsibilities

`camelot-shadow-brain`:
- local UKG retrieval,
- node-scoped semantic search,
- low-risk reasoning,
- continuity status,
- local model routing,
- zero policy/lease issuance.

`camelot-ukg-sync`:
- fetch signed capsule manifest,
- validate signer,
- validate parent/root digest,
- reject rollback,
- atomically promote local UKG head,
- acknowledge knowledge epoch.

`camelot-reconciler`:
- read provisional offline journal,
- bundle hashes/provenance,
- submit via Bifrost,
- receive Gideon/Arthur disposition,
- mark accepted/quarantined/conflicted.

`camelot-forge-crystal`:
- create signed recovery metadata,
- render QR/multi-QR,
- verify scan payload,
- never store reusable authority credentials.

### 4.2 Shadow Brain local API

All endpoints are loopback or Unix-socket only.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | process liveness |
| GET | `/health/ready` | UKG head + local index ready |
| GET | `/v1/continuity` | connected/degraded/islanded/rejoining state |
| POST | `/v1/retrieve` | local UKG retrieval |
| POST | `/v1/plan` | generate local draft/plan only |
| GET | `/v1/ukg/head` | active verified knowledge head |
| GET | `/v1/offline/journal` | local pending journal metadata |

No generic `/execute`, `/shell`, `/promote`, `/lease`, or `/policy/write` endpoint is permitted.

---

## 5. UKG Storage Schema

### 5.1 Local SQLite tables

```sql
CREATE TABLE ukg_heads (
  node_id TEXT PRIMARY KEY,
  knowledge_epoch INTEGER NOT NULL,
  authority_epoch INTEGER NOT NULL,
  root_digest TEXT NOT NULL,
  parent_digest TEXT,
  generated_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  signer_public_key TEXT NOT NULL,
  capsule_json TEXT NOT NULL
);

CREATE TABLE ukg_nodes (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  knowledge_epoch INTEGER NOT NULL,
  tier TEXT NOT NULL,
  predicate TEXT,
  object_json TEXT,
  provenance_hash TEXT NOT NULL,
  classification TEXT NOT NULL
);

CREATE TABLE offline_journal (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE NOT NULL,
  node_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  authority_epoch_seen INTEGER NOT NULL,
  knowledge_epoch_seen INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  provisional INTEGER NOT NULL DEFAULT 1,
  signer_public_key TEXT NOT NULL,
  signature TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reconciliation_state TEXT NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE reconciliation_batches (
  batch_id TEXT PRIMARY KEY,
  first_sequence INTEGER NOT NULL,
  last_sequence INTEGER NOT NULL,
  submitted_at TEXT,
  result TEXT,
  result_receipt_id TEXT,
  conflict_count INTEGER NOT NULL DEFAULT 0
);
```

### 5.2 Filesystem layout

```text
/var/lib/camelot/shadow-brain/
  identity/
  epoch/
  ukg/
  graph/
  journal/
  receipts/pending/
  cartridges/
  recovery/
```

Use atomic rename for new UKG heads. Never mutate the active capsule in place.

---

## 6. UKG Sync Protocol

### 6.1 Crown endpoints

Suggested governed Bifrost targets:

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/ukg/nodes/{nodeId}/head` | get latest eligible UKG head |
| GET | `/v1/ukg/nodes/{nodeId}/delta?after={epoch}` | incremental signed delta |
| POST | `/v1/ukg/nodes/{nodeId}/ack` | acknowledge verified local head |
| POST | `/v1/ukg/reconcile` | submit offline reconciliation bundle |

### 6.2 Admission sequence

```text
receive capsule
 -> validate schema
 -> validate tenant/workspace/node scope
 -> validate signer against pinned Crown UKG key
 -> validate authorityEpoch is not from the future
 -> validate knowledgeEpoch monotonicity
 -> validate parentDigest == current head digest
 -> validate rootDigest
 -> validate expiry
 -> scan classification restrictions
 -> write staging files
 -> transactionally update SQLite index
 -> atomic head promotion
 -> emit local receipt/event
```

Failure at any step leaves the previous verified head active.

---

## 7. Offline Journal Rules

Every offline event is provisional.

Required fields:
- node ID,
- tenant/workspace,
- event ID,
- local sequence,
- authority epoch seen,
- knowledge epoch seen,
- payload hash,
- classification,
- provenance,
- timestamp,
- node signing key,
- signature.

The local journal must never claim a final Ledger receipt.

Allowed state transitions:

```text
PENDING -> SUBMITTED -> ACCEPTED
                    -> CONFLICT
                    -> QUARANTINED
                    -> REJECTED
```

---

## 8. Rejoin/Reconciliation Protocol

```text
1. Re-establish Bifrost trust.
2. Fetch and verify current authority epoch.
3. Fetch and verify current UKG head.
4. Compare local authorityEpochSeen and knowledgeEpochSeen.
5. Freeze new canonical promotion from the reconnecting node.
6. Upload signed journal batch as evidence.
7. Validate VFS/object references.
8. Gideon verifies integrity and policy evidence.
9. Arthur resolves ACCEPT / RETRY / REJECT / QUARANTINE.
10. Ledger records resolution.
11. State Service projects canonical result.
12. Local journal marks terminal state.
13. UKG Sync advances local knowledge head.
```

Conflicts are surfaced to HITL; they are never silently overwritten.

---

## 9. Forge Recovery Crystal v2

### 9.1 Logical payload

```json
{
  "schema": "camelot-forge-crystal/2",
  "nodeId": "node-...",
  "issuedAt": "RFC3339",
  "crownTrust": {
    "epochFencerPublicKey": "...",
    "ukgPublisherPublicKey": "...",
    "bifrostTrustRoot": "..."
  },
  "lastKnownAuthorityEpoch": 42,
  "lastKnownKnowledgeEpoch": 1837,
  "ukgRootDigest": "sha256:...",
  "encryptedBundleRef": "local://recovery/ukg.bundle",
  "discoveryHints": ["tailscale://...", "https://hub/..."],
  "signerPublicKey": "...",
  "signature": "ed25519:..."
}
```

### 9.2 QR constraints

- QR must remain small enough for reliable recovery scanning.
- Large knowledge bundles are referenced, not embedded.
- Multi-QR chunking may be used only with a signed chunk manifest and digest verification.
- Any sensitive bundle reference must resolve to encrypted local media.
- Scanning a crystal never grants effect authority.

---

## 10. Systemd Hardening Targets

Example Shadow Brain unit policy:

```ini
[Service]
User=camelot-shadow-brain
Group=camelot
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
MemoryMax=384M
CPUQuota=40%
TasksMax=96
ReadWritePaths=/var/lib/camelot/shadow-brain
IPAddressDeny=any
IPAddressAllow=localhost
Restart=on-failure
```

If a local model runtime requires executable memory, `MemoryDenyWriteExecute` must be evaluated per process rather than weakened globally.

---

## 11. Resource Budget for 8 GB Nodes

| Group | Target Ceiling | Shedding Rule |
|---|---:|---|
| Critical authority plane | ~1.25 GiB | never shed before lower classes |
| Data / state / receipt services | ~1.5 GiB | reduce caches first |
| Shadow Brain core + local semantic index | 384-768 MiB | keep L0/L1, evict L2 first |
| Local inference | dynamic, up to ~1.5 GiB on capable node | stop model before authority services |
| Experience plane | 256-512 MiB | reduce visuals before cognition |
| Evaluation / Firecracker / optional workers | remaining burst budget | first to stop under pressure |
| Reserved OS / kernel / filesystem | minimum safety margin | protected |

System target remains below the 7.2 GB operational ceiling. The Shadow Brain must degrade its index/model before forcing authority-plane OOM.

---

## 12. Observability

Recommended metrics:

```text
camelot_authority_epoch
camelot_active_brain
camelot_brain_heartbeat_age_seconds{brain=...}
camelot_brain_receipt_head{brain=...}
camelot_twinbrain_digest_match
camelot_shadow_brain_state
camelot_shadow_knowledge_epoch
camelot_shadow_knowledge_age_seconds
camelot_ukg_sync_failures_total
camelot_ukg_rollback_rejections_total
camelot_offline_journal_pending_total
camelot_reconciliation_conflicts_total
camelot_recovery_crystal_verify_failures_total
```

No secret, raw UKG confidential payload, or biometric source data is emitted in metrics.

---

## 13. Test and Drill Matrix

Mandatory tests:

1. Planned Open-Notebook -> NotebookLM promotion.
2. Promotion denied when target heartbeat is stale.
3. Promotion denied when state digests differ.
4. Promotion denied when target receipt head is behind.
5. Failover denied without explicit stale-source permission.
6. Successful failover when source is stale and target meets receipt floor.
7. Stale lease rejected immediately after epoch increment.
8. Stale VFS attestation rejected after epoch increment.
9. Stale Wasmtime request rejected after epoch increment.
10. State Service refuses new event projection under stale epoch.
11. Gideon quarantines stale-epoch evidence.
12. Arthur quarantines stale Gideon verdict after dynamic-epoch conversion.
13. Shadow Brain enters ISLANDED after Crown timeout.
14. Shadow Brain continues L0/L1 retrieval offline.
15. L4/L5 effect request becomes OFFLINE_PENDING/denied.
16. Signed UKG delta advances knowledge epoch.
17. Wrong UKG signer rejected.
18. UKG rollback rejected.
19. Tampered QR crystal rejected.
20. Offline journal tamper rejected on rejoin.
21. Conflicting offline change is quarantined for HITL.
22. Low-memory pressure sheds local inference before authority plane.
23. Recovery from QR + encrypted UKG bundle restores local L0/L1 context.
24. Rejoining node cannot inject authority or rewrite canonical state directly.

---

## 14. CI / Release Gates

A production release must pass:

```text
Rust fmt/check/test/clippy for authority + continuity crates
Go test/vet for Bifrost
JSON schema validation for:
  authority-epoch/1
  camelot-ukg/2
  camelot-forge-crystal/2
  workspace-event
  receipt
  VFS attestation
  Gideon verdict
  Arthur resolution
TypeScript typecheck/build for Experience Plane
offline/rejoin integration drill
Twin-Brain promotion drill
receipt-chain verification
secret scan
SBOM generation
```

---

## 15. Implementation Sequence

1. Complete dynamic epoch conversion in new receipt admission.
2. Finish Twin-Brain fencing CI and promotion drills.
3. Implement `camelot-ukg` crate and schemas.
4. Implement node-local `camelot-shadow-brain`.
5. Implement `camelot-ukg-sync`.
6. Implement signed offline journal.
7. Implement reconciler through Gideon/Arthur/Ledger.
8. Implement Forge Recovery Crystal v2 + QR tooling.
9. Project Twin-Brain + Shadow Brain truth into World Tree.
10. Add end-to-end cloud-loss/rejoin chaos drills.
11. Only then allow explicitly offline-safe L3 capabilities.

---

## 16. Final Runtime Invariant

```text
CONNECTED:
  Crown cognition + local Shadow Brain

ISLANDED:
  local cognition survives
  new sovereign effect authority does not

REJOINING:
  local work is evidence
  not truth until reconciled

PROMOTED:
  new authority epoch wins
  old authority becomes history
```

**SOVEREIGN_TRUTH**
