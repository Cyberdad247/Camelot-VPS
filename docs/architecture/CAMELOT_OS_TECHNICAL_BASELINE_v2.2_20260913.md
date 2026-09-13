# Camelot-OS Technical Baseline v2.2
## Full-Thread Consolidated Architecture Control Document

**Version:** `2.2.0`  
**Date:** `2026-09-13`  
**Status:** `LIVING BASELINE | FULL-THREAD AUDITED | IMPLEMENTATION-GOVERNED`  
**Scope:** Camelot-OS VPS Hub / Cybertronia, Experience, Cognitive, Authority, Execution, Connectivity and Continuity planes  
**Authority:** `SOVEREIGN_TRUTH`  
**Merge policy:** This document does not authorize merging any draft implementation PR.

This file is the v2.2 architecture control/index document. It should be read together with the v2.1 SADD/LLDD retained in this branch and `CAMELOT_OS_FULL_THREAD_TECHNICAL_AUDIT_v2.2_20260913.md`. Where v2.2 explicitly reconciles an earlier architectural conflict, v2.2 controls.

## 1. Five-Plane Architecture

| Plane | Canonical responsibility |
|---|---|
| Experience | World Tree, Command Center, Throne Room, Battle Mode, Shadow Castle, CLI |
| Cognitive | Twin Brains, Knights, cartridges, Paladin research, node-local Shadow Brains |
| Authority | Heimdall, Sentinel, Excalibur, VFS Guardian, Gideon, Arthur, Ledger |
| Execution | Wasmtime, typed effects, Shadow Subspace, isolated workers |
| Connectivity | Bifrost, Tailscale/Headscale, Android/OpenWrt, governed external realms |

```text
MODEL SELECTS.
CAMELOT RESOLVES.
CAMELOT AUTHORIZES.
CAMELOT RENDERS.

CONNECTIVITY != AUTHORITY
MODEL OUTPUT != AUTHORITY
UI STATE != AUTHORITY
```

## 2. World Tree L0-L7 Mapping

| Layer | Meaning |
|---|---|
| L0 Physical | VPS hardware, mobile/edge devices, disk, kernel, cgroups |
| L1 Infrastructure | systemd, mesh, storage, sockets |
| L2 VFS Roots | canonical/shadow VFS, snapshots, diffs |
| L3 Data & Knowledge | State Service, Ledger, UKG, semantic index, evidence |
| L4 Intelligence | Knights, cartridges, bounded model adapters |
| L5 Twin Brains | Open-Notebook + NotebookLM |
| L6 Throne Room | Human/Council interaction, consent, mission formulation |
| L7 Sovereign Intelligence | governed orchestration and verified outcome projection |

## 3. Canonical Authority Chain

```text
Intent / Proposal
      |
   Bifrost
transport admission
      |
   Sentinel
policy + signed lease
      |
   Excalibur
HITL when required
      |
 VFS Guardian
signed preflight
      |
 Bounded Executor
      |
   Gideon
independent verdict
      |
   Arthur
final resolution
      |
   Ledger
signed receipt
      |
 State Service
verified projection
```

Bifrost transports. Sentinel grants capability. Heimdall supplies trust evidence. Excalibur binds human approval. The Experience Plane never manufactures authority or completion.

## 4. Twin-Brain Authority Fencing

Open-Notebook and NotebookLM are the Crown Twin-Brain pair. Only one brain participates in current authority according to the signed `authorityEpoch`.

Planned promotion requires fresh and ready source/target state, current epoch observation, receipt-head convergence, matching state digest, optimistic expected epoch and active-brain values, and a server-side promotion assertion.

Failover requires explicit stale-source authorization plus a fresh/ready target at or beyond the last promoted receipt floor.

Dynamic signed epoch verification is the target at Sentinel, VFS Guardian, node-agent, State Service, Gideon, Arthur and receipt admission. Old epochs remain historical evidence, never current authority.

## 5. Shadow Brain Continuity

Every governed node may host a local Shadow Brain.

Shadow Brain is a third **cognitive** brain, not a third sovereign authority.

```text
CONNECTED -> DEGRADED -> ISLANDED -> REJOINING -> CONNECTED
```

During ISLANDED mode:
- local UI and read-only state continue,
- local retrieval/reasoning continue,
- writes are confined to Shadow VFS/provisional journal,
- consequential effects are queued or denied unless an explicitly offline-safe lease allows them,
- no policy, lease or authority signing key is created locally.

`authorityEpoch` and `knowledgeEpoch` are separate clocks. The first controls current authority participation; the second controls freshness of node-local knowledge.

## 6. UKG and Recovery

`camelot-ukg/2` is the signed node/tenant/workspace-scoped knowledge synchronization unit. It carries a monotonic `knowledgeEpoch`, parent/root digests, provenance, expiry, L0/L1/L2 tiers and publisher signature.

UKG is knowledge evidence, never a capability lease.

Forge Recovery Crystal v2 is the smallest offline trust/knowledge bootstrap. It may carry public trust roots, node identity, last-known epochs, UKG root digest, encrypted bundle reference, discovery hints and a signature. It must never contain reusable private authority credentials.

Offline work is provisional and reconciles through:

```text
offline journal
 -> Bifrost
 -> VFS/object validation
 -> Gideon
 -> Arthur
 -> Ledger
 -> State Service
 -> canonical merge or quarantine
```

## 7. Shadow Subspace

Shadow Brain and Shadow Subspace are separate.

- **Shadow Brain:** node-local continuity cognition.
- **Shadow Subspace:** ephemeral bounded mission workspace/execution domain.
- **Sir Umbra:** Shadow Subspace Council/interface role.
- **Puter Shadow Castle:** visual workspace surface.
- **camelot-shadowd:** native Shadow Subspace governor.

Shadow Subspace preserves accountability through bounded capabilities, HITL, ephemeral workspaces and signed/hash-chained receipts. It exposes no generic arbitrary shell execution endpoint.

## 8. Mesh Doctrine

Canonical roles:

| Component | Role |
|---|---|
| Tailscale Go | production encrypted data plane |
| Headscale | sovereign mesh identity/control plane |
| Tailscale Android | managed mobile/operator node |
| OpenWrt Tailscale Enabler | subnet/router edge, must be supply-chain hardened |
| tailscale-rs | experimental/sandbox only |

`camelot-meshd` remains the target local facade for Headscale/Tailscale topology, path telemetry and attestation normalization. It is not yet implemented.

> Mesh connectivity conveys reachability, never effect authority.

## 9. Battle Mode / WorldMonitor

WorldMonitor is a governed external visualization/intelligence realm. Current integration is partial.

Target Battle transition:

```text
ARMING
 -> HEIMDALL ATTESTATION
 -> BIFROST OPENS
 -> MESH CONSTELLATION
 -> WORLDMONITOR
```

Battle Mode must render observed evidence for host/cgroup/systemd/mesh/security state. Static declarations must never appear as `VERIFIED`.

## 10. Cognitive Camelot Reconciliation

The Magnum Opus / Cognitive Camelot persona system is retained as the Cognitive Plane.

- TITAN survives as a graph/decoupled memory discipline.
- MIRAS survives as a cognitive quality/reflexion loop.
- Paladin Octem survives as a bounded research/fact-check swarm.
- legacy personas may remain as cartridges/specialists.
- persona identity does not grant runtime authority.
- early Python/Docker/Kubernetes hot-path assumptions are superseded for the VPS Hub authority plane.

Sir Helios remains strictly development-only:

```text
SURVEY -> ARCHITECT -> FORGE -> REVIEW -> VERIFY -> HANDOFF
```

> User sees Camelot. Helios builds Camelot.

## 11. Production Assembly Priorities

### P0
- make every current CI gate mechanically green,
- dynamic epoch enforcement in new receipt admission,
- canonical VFS snapshot/diff/promotion,
- strong Excalibur/HITL identity and exact-manifest binding,
- lease revocation/replay controls,
- durable Bifrost replay/idempotency,
- typed Effect Registry,
- end-to-end governed mission proof,
- backup/restore and migration discipline.

### P1 Continuity
- `camelot-ukg`,
- `camelot-shadow-brain`,
- `camelot-ukg-sync`,
- signed offline journal,
- reconciler,
- Forge Recovery Crystal v2,
- island/rejoin drills.

### P1 Infrastructure Truth
- `camelot-meshd`,
- production Headscale,
- OpenWrt pinned update chain,
- host attestation,
- WorldMonitor Camelot topology/security layer.

### P2 Experience Convergence
- remove remaining simulated local state,
- authoritative Twin-Brain HUD,
- authoritative Shadow Brain HUD,
- evidence-driven Battle Mode transitions.

## 12. CI Truth at Audit Time

Known green surfaces include Experience Plane TypeScript/build, Native Bifrost contracts/build, proposal/projection Go ingress, Shadow browser/CLI build and Shadow Rust check/tests before Clippy.

Known blockers include Rust formatting gates in Twin-Brain/Resolution/Convergence workflows and Shadow Clippy findings for an explicit loop counter, an eight-argument receipt helper and duplicated recovery-state branches.

No branch is production-cleared while those gates remain red.

## 13. Stacked Integration Order

```text
PR #2 Helios
 -> PR #3 Command Center
 -> PR #4 Shadow Subspace
 -> PR #5 VPS Hub Convergence
 -> PR #6 Twin-Brain Fencing
 -> documentation baseline
```

PR #1 remains a reference/prototype lineage unless intentionally harvested.

No automatic merge is authorized.

## 14. Constitutional Invariants

```text
THE WORLD TREE IS THE WORLD.
THE THRONE ROOM IS WHERE THE COUNCIL SPEAKS.
BIFROST GOVERNS CROSSINGS.
SENTINEL GRANTS CAPABILITY.
EXCALIBUR BINDS HUMAN CONSENT.
VFS GUARDIAN BINDS THE RESOURCE.
GIDEON VERIFIES THE RESULT.
ARTHUR RESOLVES THE RESULT.
THE LEDGER REMEMBERS TRUTH.

THE SHADOW MAY PRESERVE COGNITION.
THE SHADOW MAY NOT CREATE A CROWN.

THE ROAD GRANTS PASSAGE.
THE CROWN GRANTS PERMISSION.

USER SEES CAMELOT.
HELIOS BUILDS CAMELOT.
```

**SOVEREIGN_TRUTH**
