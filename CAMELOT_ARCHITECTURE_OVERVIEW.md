# Camelot-OS v3 Reforge Overview — Sovereign Digital Enterprise Runtime

**Node:** Cybertronia  
**Profile:** Primary VPS, 8 GB  
**Binding baseline:** `CAMELOT-OS-SADD-LLDD-v2.1-20260913` v2.1.0  
**Candidate baseline:** `CAMELOT-OS-SADD-v3.0-20260919` + `CAMELOT-OS-LLDD-v3.0-20260919`  
**Status:** v3 reforge candidate. The branch implements and validates migration steps, but v3 is not binding production truth until explicit promotion gates pass.

## Architectural axiom

> MODEL SELECTS. CAMELOT RESOLVES. CAMELOT AUTHORIZES. CAMELOT RENDERS.

And for the v3 reforge:

> THE MODEL PROPOSES. THE CONTRACT DEFINES MEANING. THE SENTINEL DEFINES PERMISSION. THE LEDGER REMEMBERS TRUTH.

Camelot is evolving from a sovereign control plane with cognitive personas into a **sovereign digital-enterprise operating fabric**. The persona layer is retained as a first-class organizational layer, while authority, execution, verification, receipts, and canonical truth remain machine-governed and explicitly separated from personality.

## Layered architecture

```text
Human / Operator
    |
    v
Persona Enterprise Plane
Anya | Merlin | Synthetos | Heimdall | development Helios | specialists
    |
    v
Cognitive Runtime
Model Router | Context Compiler | Spark | Rune | Pill | Skills
    |
    v
Sovereign Runtime
Sentinel | Epoch Fencer | Bifrost | VFS | Node Agent | Gideon | Arthur | Ledger
    |
    v
Continuity / Knowledge
UKG | Shadow Brain | governed memory | offline journal | recovery crystal
    |
    v
Host / Device Layer
Cybertronia VPS | Linux/systemd | Omarchy profile | future host adapters
```

## Persona enterprise continuity

Personas are not decorative UI. They may preserve:

- identity,
- enterprise mandate,
- communication profile,
- department and relationships,
- governed memory,
- skills and procedures,
- decision history and current objectives.

A persona is **not** the model provider. Anya may be backed by different model engines across time while remaining the same governed enterprise identity.

The v3 identity stack is:

```text
Soul
+ existing persona competence profile
+ Enterprise Role
+ signed Knight Package
= governed persistent Knight identity
```

None of those objects is a lease.

## Authority chain

```text
Human intent
 -> persona interpretation
 -> typed plan / DAG
 -> immutable effect manifest
 -> Sentinel policy
 -> Excalibur approval when required
 -> current capability lease
 -> VFS/resource preflight
 -> bounded execution
 -> Gideon verification
 -> Arthur resolution
 -> signed receipt
 -> authoritative state projection
```

Sentinel remains the sole policy, capability-lease, and revocation authority.

Bifrost remains transport/admission. It does not grant permission.

## Dynamic authority fencing

Twin-Brain authority remains fenced by the signed `authorityEpoch`.

The reforge branch now wires Receipt Service into the same dynamic `EpochSource` mechanism already used by other authority-sensitive services. Every new receipt append resolves the currently verified signed epoch. A stale draft from epoch N is rejected immediately after promotion to N+1 without requiring a Receipt Service restart.

Historical receipts remain evidence and are not reinterpreted against the newest epoch.

## Contract Forge

The companion `CAMELOT_OS` reforge branch introduces additive v3 contracts and conformance gates for:

- Soul,
- Enterprise Role,
- Spark,
- Rune,
- Pill,
- memory candidate,
- active memory,
- Effective Capability Set,
- signed authority epoch,
- signed Knight package.

The v3 signing discipline introduces deterministic canonicalization, SHA-256 digests, domain-separated Ed25519 signatures, issuer identity, scope, lifecycle, and provenance.

Camelot-VPS runtime-local contracts remain grandfathered until explicit compatibility ADRs migrate them. Similar names do not imply wire compatibility.

## Risk and cognition vocabulary

The v3 candidate separates:

- **T0–T4** for effect risk / approval posture.
- **L0–L5** for cognition and offline/continuity ceilings.

The binding v2.1 governance still contains legacy L0–L5 risk language. The branch documents both vocabularies during migration so no silent reinterpretation occurs.

## Context Compiler

The target Context Compiler creates a short-lived Spark from:

```text
Quest
+ Soul
+ persona competence profile
+ Enterprise Role
+ relevant UKG
+ governed memory
+ approved skills
+ recent receipts
+ host/runtime state
+ token budget
= Spark
```

The goal is minimum sufficient context.

The Spark expires and cannot contain reusable authority.

## Knight Registry

The target Knight Registry admits only signed active Knight packages whose bound Soul, persona profile, Enterprise Role, scope, lifecycle, digests, and policy ceilings verify.

Sir Synthetos is the first preferred runtime profile because it proves persona continuity through a read-only/internal synthesis mission before higher-risk effects are introduced.

## Governed memory

Memory is separate from authority.

```text
Memory Candidate
 -> Gideon
 -> Arthur
 -> activation receipt
 -> Active Memory
```

Personas may remember relationships, enterprise history, preferences, lessons, and procedures. They may not remember a lease and treat it as permission.

## Rune, Pill, Skill, Cartridge

- **Rune:** procedure, no authority.
- **Pill:** bounded possible executable reach, no permission by itself.
- **Skill:** governed procedural artifact that must be evaluated and promoted.
- **Cartridge:** versioned enterprise capability composition.

Cartridges/Pills cannot replace Core authority.

## Bifrost capability fabric

Bifrost is evolving toward typed capability routing. Requests should carry quest/task scope, actor identity, action type, resource, effect hash, lease reference, epoch, idempotency key, payload digest/reference, expiry, and provenance.

MCP, GitHub, voice, browser, WorldMonitor, and other external systems are adapters beneath this boundary.

## Host ABI and //ASSIMILATION

Camelot v3 is not a bespoke Linux distribution.

The core remains portable and uses signed host adapters for OS-specific capability.

`//ASSIMILATION` is defined as safe desired-state convergence:

```text
DISCOVER
 -> ATTEST
 -> CLASSIFY
 -> INVENTORY
 -> SELECT SIGNED ADAPTER
 -> DIFF
 -> DRY RUN
 -> POLICY / APPROVAL
 -> LEASE
 -> APPLY
 -> VERIFY
 -> RECEIPT
 -> REGISTER
```

Omarchy is a first-class target host profile, not the sovereign base of Camelot.

## Shadow Brain continuity

Shadow Brain preserves local cognition and knowledge continuity. It is not a third authority.

Offline work remains draft/evidence until rejoin reconciliation through verification, resolution, receipt, and canonical promotion.

## Runtime classes

| Class | Technology | Trust | Hub use |
|---|---|---|---|
| R0 Control | Rust native | highest | Sentinel, Epoch Fencer, Arthur, Receipt/State authority |
| R1 Transport | Go native | high | Bifrost and gateways |
| R2 Trusted Pill | Wasmtime/WASI | constrained | bounded parsers/transforms/validators |
| R3 Untrusted Chamber | Firecracker | isolated | candidate and third-party evaluation |
| R4 Experience | Browser PWA / desktop UI | untrusted projection | World Tree, command center, Omarchy UI |

The production authority hot path still excludes Docker/Kubernetes runtime dependency, Python authority services, Node.js authority APIs, and direct browser-to-database access.

## Current branch truth

Implemented or already present on the current reforge branch:

- Bifrost/Sentinel/VFS/Node Agent/State/Gideon/Arthur baseline,
- signed Twin-Brain epoch runtime,
- dynamic epoch consumers in multiple authority services,
- dynamic signed epoch receipt admission,
- receipt readiness failure when current epoch validation fails,
- Contract Forge and persona-enterprise SADD/LLDD candidate documents.

Still target work:

- live Knight Registry,
- live Context Compiler/Spark Builder,
- Sentinel Effective Capability Set compiler,
- governed memory activation service path,
- skill registry,
- Host ABI,
- //ASSIMILATION runtime,
- Omarchy adapter,
- complete Shadow/UKG/rejoin production loop.

## 8 GB scarcity doctrine

The Castle still loads light.

Shedding order remains non-critical enrichment first. Preserve Bifrost, Sentinel, Epoch Fencer, VFS, Gideon, Arthur, Receipt/State authority, and required storage before optional agents, indexing, visualization enrichment, or model workers.

## Constitutional summary

```text
THE ROAD GRANTS PASSAGE.
THE CROWN GRANTS PERMISSION.
THE SOUL PRESERVES IDENTITY.
THE SPARK DEFINES CONTEXT.
THE RUNE DEFINES PROCEDURE.
THE PILL DEFINES POSSIBLE REACH.
THE LEASE DEFINES CURRENT POWER.
THE SHADOW PRESERVES KNOWLEDGE.
THE VERIFIER DEFINES EVIDENCE.
THE RESOLVER DEFINES OUTCOME.
THE LEDGER REMEMBERS TRUTH.

PERSONA CONTINUITY MAY PERSIST.
MODEL ENGINES MAY CHANGE.
COGNITION MAY BE DISTRIBUTED.
AUTHORITY MAY NOT.
```

**Doctrine:** The Castle loads light. The Cartridge loads on demand. The Knight awakens for a purpose. Bifrost transports governed requests. Sentinel decides authority. The Ledger remembers truth.
