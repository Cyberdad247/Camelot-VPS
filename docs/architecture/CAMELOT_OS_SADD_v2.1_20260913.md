# Camelot-OS System Architecture Design Document (SADD)
## VPS Hub / Cybertronia Sovereign Architecture

**Document ID:** `CAMELOT-OS-SADD-LLDD-v2.1-20260913-SADD`  
**Version:** `2.1.0`  
**Date:** `2026-09-13`  
**Status:** `LIVING BASELINE | VPS HUB | TWIN-BRAIN FENCING | SHADOW-BRAIN CONTINUITY DEFINED`  
**Authority:** `SOVEREIGN_TRUTH`  
**Supersedes:** v2.0.0 only where this document explicitly changes or extends it.  
**Scope:** Camelot-OS VPS Hub / Cybertronia and its governed edge nodes.

---

## 1. Executive Architecture

Camelot-OS is a sovereign, multi-tenant, capability-governed AI operating fabric. The VPS Hub converts intent into bounded, evidence-backed outcomes across a private mesh while preserving human authority over consequential effects.

Version 2.1 extends the v2.0 baseline with two resilience mechanisms:

1. **Twin-Brain Authority Fencing** - Open-Notebook and NotebookLM participate as the Crown cognitive pair, but only the currently promoted brain may participate in current authority. Promotion increments a signed `authorityEpoch`.
2. **Node-Local Shadow Brain Continuity** - every Camelot node may maintain a dynamic local cognitive replica distilled from the Crown using signed UKG knowledge capsules and an offline recovery crystal. The Shadow Brain preserves cognition during cloud or VPS loss but never creates new sovereign effect authority.

### 1.1 Architectural axiom

```text
DOCUMENTATION IS NOT A RECORD OF THE SYSTEM.
DOCUMENTATION IS THE SYSTEM.

MODEL SELECTS.
CAMELOT RESOLVES.
CAMELOT AUTHORIZES.
CAMELOT RENDERS.
```

### 1.2 Non-negotiable principles

1. A model output is a proposal, never an authorized action.
2. Sentinel is the sole policy, capability-lease, and revocation authority.
3. Bifrost authenticates and transports; connectivity does not grant authority.
4. Tenant and workspace scope are derived server-side; client assertions are untrusted.
5. Consequential effects require immutable scope, current policy, a short-lived lease, VFS preflight, bounded execution, independent verification, Arthur resolution, and a signed receipt.
6. Twin-Brain promotion is fenced by a signed authority epoch. Older epochs remain evidence, not authority.
7. Every node may retain a Shadow Brain for local cognition and continuity.
8. Offline operation may preserve retrieval, reasoning, drafts, local shadow work, and receipt delivery, but it does not create new effect authority.
9. Shadow Brain knowledge is node-scoped, signed, provenance-aware, and rollback-resistant.
10. A QR/Forge recovery crystal is a bootstrap trust and recovery object, not a secret container and not an authority token.
11. Cartridges and Pills are bounded capability packages; Core authority cannot be replaced or bypassed.
12. Learning and synchronization create versioned candidates or knowledge capsules; they cannot mutate runtime policy or self-promote.
13. Native hot-path only: no Docker, Kubernetes runtime dependency, Python authority service, Node.js authority API server, or direct browser-to-database access.
14. Helios remains development-only and must never become a runtime authority or visible production persona.

### 1.3 Outcome contract

```text
Intent
  -> typed plan
  -> Bifrost transport admission
  -> Sentinel policy decision + signed lease
  -> Excalibur approval when required
  -> VFS Guardian signed preflight
  -> bounded executor
  -> Gideon verification
  -> Arthur resolution
  -> Ledger receipt
  -> authoritative workspace event
  -> verified World Tree / Battle / Shadow / Throne projection
```

---

## 2. Deployment Topology

### 2.1 Logical brain topology

```text
                         CAMELOT CROWN
                +---------------------------+
                | Open-Notebook <-> NotebookLM |
                |  Crown Twin-Brain Pair       |
                |  one active per authority    |
                |  epoch                        |
                +-------------+----------------+
                              |
                    signed UKG distillation
                              |
                    Bifrost / mesh sync
                              |
         +--------------------+--------------------+
         |                    |                    |
     VPS NODE             MOBILE NODE          EDGE NODE
   Shadow Brain           Shadow Brain        Shadow Brain
     SB-VPS                 SB-S26              SB-EDGE
```

The Crown Twin-Brain pair is a logical cognitive pair. Physical placement may be co-located or distributed, but promotion semantics are always governed by the signed authority epoch.

### 2.2 Node roles

| Node / Role | Primary Responsibility | Authority Posture | Offline Posture |
|---|---|---|---|
| Cybertronia VPS Hub | Control plane, evidence, data coordination, Bifrost, Sentinel, VFS, verification, receipts | Active authority plane | Local services continue under current verified policy |
| Open-Notebook | Crown cognitive brain | Active or standby according to signed epoch | No independent lease authority |
| NotebookLM | Crown cognitive brain | Active or standby according to signed epoch | No independent lease authority |
| Shadow Brain | Node-local continuity brain on every node | No lease or policy authority | Local reasoning, retrieval, drafts, shadow workspace, journal |
| S26 Mobile Orb | Thin client, presence, consent, voice, QR, local continuity | No policy/lease authority | Shadow Brain + local recovery mode |
| Future Edge Silo | Lease-bound scoped execution | No lateral or policy authority | Shadow Brain + bounded local execution only if explicitly offline-safe |
| Puter Shadow Castle | Ephemeral agent workspace | No host or lease authority | Shadow workspace only |

### 2.3 Authority and knowledge clocks

Camelot now maintains two different monotonic clocks:

| Clock | Meaning | Issuer | Security Effect |
|---|---|---|---|
| `authorityEpoch` | Which Crown brain may participate in current authority | Epoch Fencer | Old leases, VFS evidence, execution requests, verdicts and new receipts are fenced |
| `knowledgeEpoch` | Freshness/version of Shadow Brain knowledge | UKG Sync / Crown knowledge publisher | Detects stale/rollback knowledge and drives node synchronization |

A node may have current authority evidence but stale knowledge, or current knowledge but no authority connectivity. The two states must never be conflated.

---

## 3. Crown Twin-Brain Authority Fencing

### 3.1 Core invariant

> Only the active Twin Brain may participate in current authority. Promotion increments the signed authority epoch. Older epochs remain historical evidence but cannot authorize new consequential effects.

### 3.2 Promotion modes

**Planned promotion** requires:
- current signed epoch,
- fresh source and target heartbeats,
- target readiness,
- target observed current epoch,
- target receipt head at or beyond the active receipt head,
- matching Twin-Brain state digest,
- optimistic `expectedEpoch`,
- optimistic `expectedActiveBrain`,
- server-side promotion assertion.

**Failover promotion** requires:
- active source is stale/unavailable,
- explicit stale-source failover authorization,
- target fresh and ready,
- target observed current epoch,
- target receipt head at or beyond the last promoted receipt floor,
- optimistic epoch/active-brain match.

### 3.3 Epoch propagation

The signed runtime certificate is published atomically and is consumed dynamically by:
- Sentinel,
- VFS Guardian,
- node-agent / Wasmtime admission,
- State Service,
- Gideon,
- Arthur,
- receipt admission,
- future authority-sensitive services.

Services must reread and verify the signed epoch source at the authority decision boundary. Restarting a service is not an acceptable fencing mechanism.

---

## 4. Shadow Brain Continuity Layer

### 4.1 Purpose

The Shadow Brain is the node-local cognitive continuity layer. It allows a node to keep useful context and reasoning capability when the VPS Hub, Crown Twin Brains, or Bifrost are unavailable.

It is a **third cognitive brain**, not a third sovereign authority.

### 4.2 Shadow Brain allowed capabilities

When connected:
- maintain warm local knowledge,
- index node-scoped UKGs,
- answer low-risk local retrieval,
- prepare plans and drafts,
- receive incremental knowledge deltas,
- monitor knowledge age and root digest.

When islanded:
- L0 local UI and read-only rendering,
- L1 local retrieval and reasoning,
- L2 writes only to Shadow VFS / offline journal / draft space,
- local diagnostics,
- mission continuation as a draft,
- provisional signed observations and reconciliation bundles.

By default, the following become `OFFLINE_PENDING` or are denied:
- new external communication,
- canonical VFS promotion,
- deployment,
- financial or irreversible effects,
- creation of new authority,
- policy mutation,
- lease issuance,
- trust-root rotation.

Existing leases may only be used offline if the lease explicitly declares an offline-safe capability and offline validity window. Otherwise isolation fails closed.

### 4.3 Continuity states

```text
CONNECTED
   -> DEGRADED
   -> ISLANDED
   -> REJOINING
   -> CONNECTED
```

**CONNECTED:** Crown reachable; Shadow Brain warm and synchronized.  
**DEGRADED:** Crown partially reachable; local retrieval becomes preferred.  
**ISLANDED:** Cloud/VPS unavailable; local cognition active, new effect authority locked.  
**REJOINING:** Local journal and knowledge deltas are reconciled before canonical promotion.

### 4.4 Reconciliation law

A reconnecting node is never trusted merely because it was previously trusted.

```text
Offline Journal
   -> integrity verification
   -> Ouroboros/UKG distillation
   -> VFS conflict analysis
   -> Gideon evidence verification
   -> Arthur resolution
   -> Ledger receipt
   -> canonical merge or quarantine
```

---

## 5. Universal Knowledge Glyph (UKG) Synchronization

### 5.1 UKG role

UKG is the portable, signed knowledge synchronization unit between the Crown and node-local Shadow Brains.

A UKG is knowledge, not authority.

### 5.2 Canonical UKG capsule

```json
{
  "schema": "camelot-ukg/2",
  "nodeId": "camelot-node-03",
  "tenantId": "tenant-...",
  "workspaceId": "workspace-...",
  "authorityEpoch": 42,
  "knowledgeEpoch": 1837,
  "parentDigest": "sha256:...",
  "rootDigest": "sha256:...",
  "generatedAt": "2026-09-13T00:00:00Z",
  "expiresAt": "2026-09-20T00:00:00Z",
  "tiers": {
    "L0": "identity, laws, trust roots, recovery",
    "L1": "node architecture, active services, procedures",
    "L2": "mission-specific context"
  },
  "knowledge": [],
  "relationships": [],
  "procedures": [],
  "nodeCapabilities": [],
  "restrictions": [],
  "signer": "crown-knowledge-publisher",
  "signature": "ed25519:..."
}
```

### 5.3 UKG integrity rules

- Node-specific scope is mandatory.
- Tenant/workspace provenance is mandatory.
- Capsules form a parent-digest chain.
- `knowledgeEpoch` must be monotonic.
- Root digest rollback is rejected unless a signed recovery policy explicitly authorizes rollback.
- Restricted secrets, raw biometrics, private keys, and broad authority tokens are prohibited.
- UKG signer identity is distinct from the authority-epoch signer.
- A node may cache multiple generations but only one verified head is active.

---

## 6. Forge Recovery Crystal / QR Continuity

### 6.1 Purpose

The recovery crystal is the smallest offline seed needed to re-establish trusted Camelot context.

**QR = seed crystal.**  
**Encrypted UKG store = memory.**  
**Local model / Knight runtime = cognition.**

### 6.2 QR payload policy

A recovery crystal may contain:
- node identifier,
- Crown public trust roots,
- Epoch Fencer public key,
- UKG publisher public key,
- last known authority epoch,
- last known knowledge epoch,
- UKG root digest,
- encrypted local bundle reference,
- Bifrost discovery hints,
- schema/version,
- signature.

It must not contain:
- plaintext private keys,
- bearer tokens,
- raw passwords,
- reusable authority assertions,
- biometric templates.

Large bundles use signed chunk manifests and may be transported by multi-QR, NFC, encrypted removable media, or local mesh.

---

## 7. Security Architecture

### 7.1 Threat model additions

| Threat | Mitigation |
|---|---|
| Split-brain Crown | Signed authority epochs, single active brain, optimistic promotion fencing |
| Stale authority after failover | Dynamic signed epoch verification at every authority boundary |
| Stale Shadow knowledge | `knowledgeEpoch`, expiry, health projection |
| UKG rollback attack | parent digest + monotonic knowledge epoch + signed recovery policy |
| Forged UKG capsule | pinned Ed25519 knowledge-publisher key |
| Compromised offline node | local journal treated as untrusted evidence on rejoin |
| QR theft | no private keys/tokens; node binding; encrypted referenced bundle |
| Offline journal tampering | node-signed records + hash chain + reconciliation verification |
| Browser promotion attempt | browser has no promotion credential; promotion is server-side HITL |
| Shadow Brain authority escalation | no Sentinel signing key, no policy authority, no lease issuance capability |

### 7.2 Offline risk posture

| Risk Tier | Offline Default |
|---|---|
| L0 | allow |
| L1 | allow within verified local UKG scope |
| L2 | allow only to Shadow VFS / provisional journal |
| L3 | queue for reconciliation or explicit offline-safe lease |
| L4 | deny / `OFFLINE_PENDING` |
| L5 | deny |

---

## 8. Data Architecture

### 8.1 Authoritative stores

The v2.0 store boundaries remain in force:
- PostgreSQL: relational source of truth,
- SQLite-VSS / scoped semantic store: node/workspace retrieval,
- MinIO: encrypted objects/evidence,
- Redis: ephemeral coordination only,
- Ledger: immutable evidence chain.

### 8.2 Node-local Shadow Brain store

```text
/var/lib/camelot/shadow-brain/
  identity/
    node.json
    crown-trust-roots.json
  epoch/
    authority.json
  ukg/
    head.json
    l0/
    l1/
    l2/
  graph/
    local.sqlite
  journal/
    offline.sqlite
  receipts/
    pending/
  cartridges/
  recovery/
    forge-crystal.json
```

All node-local data remains tenant/workspace scoped and encrypted at rest according to node capability.

---

## 9. Experience Plane Projection

World Tree, Battle Mode, Shadow Subspace, Throne Room and CLI render authoritative state; they do not create authority.

The Twin-Brain surface must show:
- active brain,
- authority epoch,
- both heartbeat ages,
- both observed epochs,
- receipt heads,
- state-digest match,
- promotion mode,
- fence status.

Every node surface must show:
- Shadow Brain state,
- cloud/Crown reachability,
- authority epoch seen,
- knowledge epoch,
- knowledge age,
- UKG root digest,
- offline readiness,
- pending reconciliation count,
- recovery crystal status.

Example:

```text
NODE: VPS-ALPHA
Cloud Link        ONLINE
Crown Brain       NotebookLM
Authority Epoch   42
Shadow Brain      SYNCHRONIZED
Knowledge Epoch   1837
Knowledge Age     00:03:12
UKG Root          sha256:91cf...
Offline Ready     YES
Pending Journal   0
Recovery Crystal  VERIFIED
```

---

## 10. Implementation Status

| Capability | Status |
|---|---|
| Native Bifrost signed transport admission | Implemented in draft VPS Hub convergence work |
| Sentinel signed capability leases | Implemented in draft VPS Hub convergence work |
| VFS signed preflight | Implemented in draft VPS Hub convergence work |
| Governed Wasmtime node-agent | Implemented in draft VPS Hub convergence work |
| State Service snapshots/replay/SSE | Implemented in draft VPS Hub convergence work |
| Gideon evidence gate | Implemented in draft VPS Hub convergence work |
| Arthur resolution gate | Implemented with signed dynamic authority epoch fencing in draft Twin-Brain work |
| Signed Twin-Brain epoch certificate | Implemented in draft Twin-Brain fencing work |
| Epoch Fencer promotion runtime | Implemented in draft Twin-Brain fencing work |
| Dynamic epoch in Sentinel/VFS/node-agent/State/Gideon/Arthur | Implemented in draft Twin-Brain fencing work |
| Dynamic epoch in new receipt admission | In progress |
| Shadow Brain service | Architecture defined; not yet implemented |
| UKG Sync service | Architecture defined; not yet implemented |
| Offline journal/reconciler | Architecture defined; not yet implemented |
| Forge Recovery Crystal v2 | Architecture defined; not yet implemented |
| World Tree Shadow Brain projection | Architecture defined; not yet implemented |

---

## 11. Constitutional Law

> The Crown may disappear without erasing the Kingdom's memory.  
> Every node may retain cognition.  
> Only Camelot policy and authorized humans may create consequential authority.

```text
THE ROAD GRANTS PASSAGE.
THE CROWN GRANTS PERMISSION.
THE SHADOW PRESERVES KNOWLEDGE.
THE LEDGER REMEMBERS TRUTH.
```

**SOVEREIGN_TRUTH**
