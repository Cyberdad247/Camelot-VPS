# Camelot-OS VPS Hub — Sovereign Control Plane Architecture

**Node:** Cybertronia  
**Profile:** Primary VPS, 8 GB  
**Binding baseline:** `CAMELOT-OS-SADD-LLDD-vMAX-20260912` v2.0.0  
**Status:** Living architecture. Implementation is converging toward the binding baseline and must not be described as fully production-ready until the release gates pass.

## Architectural axiom

> MODEL SELECTS. CAMELOT RESOLVES. CAMELOT AUTHORIZES. CAMELOT RENDERS.

A model output is a proposal. Network connectivity is transport. UI state is a projection. None of those are authority.

## What the VPS Hub is

The Camelot-OS VPS Hub is the active control, trust, evidence, and coordination plane for the Camelot mesh. It converts authenticated intent into bounded, tenant-scoped work while preserving human authority over consequential effects.

```text
User / Operator
    │
    ▼
Ecoshell / World Tree / Mobile Orb
    │  HTTPS + authenticated session
    ▼
Cybertronia VPS Hub
    ├─ Bifrost      trust + transport admission
    ├─ Sentinel     policy + capability leases + revocation
    ├─ Excalibur    exact-manifest human approval
    ├─ VFS Guardian workspace/path/resource preflight
    ├─ Moon/AgentBus bounded scheduling and dispatch
    ├─ Wasmtime     trusted constrained Pills
    ├─ Firecracker  untrusted evaluation chamber
    ├─ Gideon       independent verification
    ├─ Arthur       final completion/promotion resolution
    ├─ Ledger       append-only signed receipt chain
    ├─ PostgreSQL   relational tenancy truth
    ├─ SQLite-VSS   scoped graph/semantic retrieval
    ├─ MinIO        encrypted evidence/object storage
    └─ Redis        ephemeral cache, locks and idempotency only
    │
    ▼
Twin-Brain standby / future lease-bound edge silos
```

## The outcome contract

```text
Intent
→ typed plan
→ Sentinel policy decision
→ immutable effect manifest
→ Excalibur approval when required
→ manifest-bound capability lease
→ VFS preflight
→ bounded execution
→ Gideon verification
→ Arthur decision
→ Ledger receipt
→ verified workspace projection
```

The UI may show `proposal`, `pending approval`, `running`, or `verification pending`, but it may show an effect as complete only after the authoritative receipt projection is available.

## Authority chain

| Actor | Owns | Explicitly does not own |
|---|---|---|
| Anya | typed intent/task proposals | leases, effects, policy mutation |
| Sentinel | policy, leases, revocation, admission | tool execution or self-approval |
| Excalibur | exact-manifest human approval | manifest mutation or lease issuance |
| Gideon | verification, evidence, tests, safety/quality assessment | promotion or effect execution |
| Arthur | final completion/promotion resolution after gates | bypass of policy, verification or approval |
| Ledger | append-only signed evidence | authorization or history rewriting |

The authorization predicate additionally requires authenticated identity, server-resolved tenant scope, current authority epoch, valid node/workload identity, resource availability, VFS pass, current approval where required, and a healthy receipt chain.

## Bifrost v2 Hub boundary

Production Bifrost is a native Go transport service. It verifies `bifrost/1` signed envelopes, freshness, routing scope, lane, message size, signer trust, and replay/idempotency state before admitting traffic.

**Important:** Bifrost admission never grants effect authority. A successfully admitted envelope still proceeds to Sentinel.

Lane model:

- `P0_CRITICAL` — revocations and approval control events
- `P1_ACTIONABLE` — missions, tasks, tool calls
- `P2_DIGEST` — reports and summaries
- `P3_TELEMETRY` — health and metrics
- `P4_RETRY` — receipt-aware retries
- reserve — heartbeat and system events

Messages target less than 8 KiB. Larger artifacts travel by signed object reference rather than inline payload.

The historical Node Bifrost command-center server is retained only as a development/compatibility surface. It is not the target production authority/transport hot path.

## Runtime classes

| Class | Technology | Trust | Hub use |
|---|---|---|---|
| R0 Control | Rust native | highest | Sentinel, Excalibur, Arthur, Ledger |
| R1 Transport | Go native | high | Bifrost, AgentBus/gateways |
| R2 Trusted Pill | Wasmtime + WASI | constrained | parsers, transforms, validators |
| R3 Untrusted Chamber | Firecracker | isolated | third-party/evaluation candidates |
| R4 Experience | Browser PWA | untrusted client | World Tree, operator surfaces, mobile UI |

Production hot-path dependencies do **not** include Docker, Docker Compose, Kubernetes, Python authority services, Node.js API authority services, or direct browser-to-database access.

## Data authority

| Store | Purpose | Not allowed |
|---|---|---|
| PostgreSQL | tenants, memberships, missions, leases, approvals, receipts, metadata | unbounded raw artifacts |
| SQLite-VSS | scoped graph + semantic retrieval | global cross-tenant index |
| MinIO | encrypted evidence, source files, exports | public/unscoped buckets |
| Redis | ephemeral cache, locks, rate limits, idempotency | durable policy truth, receipts, secrets |
| Ledger | signed hash-chain references | mutable outcomes |

Every request, event, object, graph/vector row, lease, approval, receipt and artifact carries tenant, workspace, cartridge, mission, classification, retention and provenance scope. The server derives authority context from authenticated identity; browser-supplied tenant assertions are untrusted.

## VFS Guardian

The execution filesystem for each task is rooted at:

```text
/runtime/camelot/tasks/<task-id>/
  source/      read-only pinned source
  worktree/    lease-approved writes
  tmp/         quota-limited scratch
  evidence/    manifests, reports, artifacts
  socket/      task-local AgentBus endpoint
  logs/        redacted structured events
  lease.json   verified local lease copy
```

Preflight denies path escape, unleased writes, unallowlisted executables, unnamed network routes, missing secret handles, stale/expired/revoked leases, resource excess, or source provenance/classification failure.

The current VFS Guardian still contains Phase-0 mock attestation behavior and is therefore an active convergence item, not a completed production gate.

## Ecosystem integrations

External projects are capabilities beneath Camelot governance, not peers of the authority plane:

- **QtScrcpy** → device-action cartridge under device identity, lease and explicit confirmation.
- **t3code** → compiler cartridge inside an approved worktree.
- **jcode** → AST analysis/execution cartridge under VFS + Wasmtime/Firecracker admission.
- **skillscript** → signed/versioned skill candidate; cannot rewrite binding truth or self-promote.
- **Fonoster** → communications cartridge behind consent, policy, exact manifest and receipts.
- **Multivoice-router** → governed voice/persona handoff through Bifrost.
- **Graphiti / Neo4j / Qdrant** → optional adapter or migration source. The binding P0 Cloudbrain direction is scoped SQLite-VSS.

## Experience plane

World Tree, Battle Mode, Shadow Subspace and future cinematic Hub views are immersive **projections** of system truth. The Experience Plane must always retain:

- accessible semantic 2D state,
- reduced-motion fallback,
- timestamps and evidence references,
- receipt references for completed effects,
- explicit distinction between fixture/simulation and verified runtime state.

The uploaded Scroll-Film approach is appropriate as an Experience Plane technique: continuous spatial storytelling, GPU-friendly transforms, mobile-specific composition, and reduced-motion fallbacks. It does not alter the authority model.

## 8 GB Scarcity Protocol

Cybertronia follows the v2 target budget:

- Core authority group: **1.25 GB**
- PostgreSQL: **1.0 GB**
- SQLite-VSS: **0.75 GB**
- MinIO: **0.50 GB**
- Moon / AgentBus / scheduler / Nanobot control: **0.75 GB**
- Static PWA + observability: **0.50 GB**
- OS + safety reserve: **1.45 GB**
- Burst allowance: **1.0 GB**
- Operational cap: **7.2 GB**

Shedding order is Evaluation Chamber → background Nanobot work → graph indexing → analytics/visual enrichment → external adapters. Preserve Bifrost, Sentinel, Excalibur, Gideon, Arthur, Ledger and PostgreSQL.

## Living architecture files

```text
.agent/governance.yaml                 L0 governance
.agent/north-star/vps-hub.md          L1 Hub intent + non-goals
.agent/blueprint/vps-hub-contracts.md L2 contracts and state rules
.agent/guardrails/vps-hub-security.md L3 security/privacy/runtime rules
.agent/engine/vps-hub-capacity.yaml   L4 operations and capacity
crystal/vps-hub-integration-crystal.json integration projection
contracts/*.schema.json               machine-readable contracts
```

If implementation conflicts with a binding document, the correct behavior is to stop, emit a documentation-mismatch finding, and request a human-reviewed correction. Code does not silently outrank the architecture.

## Current convergence priorities

1. Finish native Bifrost compile/test/replay validation and promote it over the Node compatibility gateway.
2. Replace VFS mock attestations with verified lease, authority-epoch, path and evidence attestations.
3. Build authoritative task snapshot + SSE workspace-event projections.
4. Expand machine-readable schemas and compatibility tests across manifests, leases, receipts and Gideon verdicts.
5. Complete Twin-Brain fencing, authority-epoch promotion and receipt reconciliation.
6. Keep Shadow Subspace under the same Sentinel → Excalibur → Gideon → Arthur → Ledger chain.

**Doctrine:** The Castle loads light. The Cartridge loads on demand. The Knight awakens for a purpose. The Gateway transports trust. Sentinel decides authority. The Ledger remembers truth.
