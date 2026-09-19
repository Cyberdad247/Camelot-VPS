# Camelot-OS System Architecture Design Document (SADD)
## v3.0 Contract-First Sovereign Digital Enterprise Reforge

**Document ID:** `CAMELOT-OS-SADD-v3.0-20260919`  
**Version:** `3.0.0-REFORGE-CANDIDATE`  
**Date:** `2026-09-19`  
**Status:** `REFORGE CANDIDATE | CONTRACT-FIRST | PERSONA-ENTERPRISE CONTINUITY | AUTHORITY-CLOSURE INTEGRATION`  
**Authority:** `PROPOSED_SOVEREIGN_TRUTH`  
**Supersedes:** v2.1.0 only after explicit human promotion of this document and corresponding governance/contracts migration.  
**Scope:** Camelot-OS / Cybertronia VPS Hub, governed digital enterprise personas, Twin-Brain authority, Shadow continuity, host portability, and universal runtime integration.

---

## 1. Executive Architecture

Camelot-OS v3 is defined as a **sovereign digital-enterprise operating fabric** that enables humans and persistent AI personas to collaborate as a governed organization while separating identity, cognition, authority, execution, memory, evidence, and canonical truth.

The v3 reforge retains the v2.1 constitutional authority model and adds a contract-first foundation so that every durable object crossing a trust boundary has a versioned meaning, deterministic integrity, explicit scope, lifecycle, provenance, and compatibility semantics.

The architecture is intentionally layered:

```text
HUMAN / ORGANIC WORLD
purpose | consent | judgment | values | enterprise intent
        |
        v
PERSONA ENTERPRISE PLANE
Anya | Merlin | Synthetos | Helios | Heimdall | Socrates | departments
        |
        v
COGNITIVE RUNTIME
model router | context compiler | Sparks | Runes | Pills | skills
        |
        v
SOVEREIGN RUNTIME
Sentinel | Epoch Fencer | Bifrost | VFS | Node Agent | Gideon | Arthur | Ledger
        |
        v
CONTINUITY + KNOWLEDGE
UKG | Shadow Brain | governed memory | offline journal | recovery crystal
        |
        v
HOST / DEVICE PLANE
Omarchy | Linux | VPS | WSL | future macOS/Windows adapters | mobile nodes
```

### 1.1 Architectural axiom

```text
DOCUMENTATION IS THE SYSTEM.

MODEL SELECTS.
CAMELOT RESOLVES.
CAMELOT AUTHORIZES.
CAMELOT RENDERS.

THE MODEL PROPOSES.
THE CONTRACT DEFINES MEANING.
THE SENTINEL DEFINES PERMISSION.
THE LEDGER REMEMBERS TRUTH.
```

### 1.2 v3 constitutional invariants

1. A model output is a proposal, never an authorized action.
2. Sentinel remains the sole policy, capability-lease, and revocation authority.
3. Bifrost authenticates, transports, routes, and records governed capability requests, but Bifrost never grants effect authority.
4. Persona identity may persist across model-provider changes. Model identity is not persona identity.
5. A Soul defines persistent identity and constitutional limits; it grants no effect authority.
6. An Enterprise Role defines organizational responsibility and relationships; it grants no effect authority.
7. A Spark is short-lived compiled task context; it never carries reusable authority.
8. A Rune defines procedure; it cannot grant capabilities.
9. A Pill defines possible executable reach and ceilings; Sentinel and a current lease define actual permission.
10. Memory may preserve enterprise history, relationships, preferences, lessons, and procedures. Memory cannot preserve reusable leases, signing keys, remembered permission, or epoch-promotion rights.
11. Consequential effects require current authority, immutable scope, policy, lease, VFS preflight where applicable, bounded execution, independent verification, final resolution, and a signed receipt.
12. Authority epochs fence new authority-bearing actions dynamically. Service restart is not an acceptable fencing mechanism.
13. Older authority epochs remain historical evidence, not current authority.
14. Offline work is provisional evidence until reconciled. Islanded nodes cannot manufacture new sovereign authority.
15. Canonical truth is promoted through verification and resolution. Persona output, Shadow output, UKG, and model memory are not canonical by default.
16. Human operators retain final authority over consequential effect classes under the applicable approval/quorum policy.
17. Native hot-path remains the default. Containers may be used only outside the critical authority path where explicitly approved.
18. Helios remains development-only for engineering orchestration and does not become production effect authority.
19. No Camelot v3 durable object should cross a trust boundary without a versioned contract or an explicitly grandfathered v2 contract.
20. Cognition may be distributed. Authority may not.

---

## 2. System Identity and Boundary

Camelot-OS is not defined as a conventional Linux distribution. It is a layered combination of:

- a **sovereign execution fabric** for policy, authority, verification, receipts, and canonical state;
- a **digital-enterprise runtime** for persistent personas, roles, collaboration, memory, and workflows;
- a **cognitive runtime** for replaceable LLMs and bounded reasoning procedures;
- a **portable host layer** that adapts Camelot to existing operating systems.

The operating system beneath Camelot owns drivers, process primitives, networking, storage primitives, and hardware access. Camelot owns governed identity, capability, evidence, enterprise continuity, and action semantics.

### 2.1 Universal host rule

```text
Operating System
      |
      v
Camelot Host Adapter
      |
      v
Camelot Runtime
```

Omarchy may become a first-class Camelot-native workstation profile, but Camelot must not require Omarchy to function.

---

## 3. Persona-Based Digital Enterprise

### 3.1 Purpose

The persona layer is a priority architectural feature, not ornamental UI. Camelot models the emerging digital enterprise as a collaboration between humans and persistent digital organizational entities.

Each persona may carry:

- stable identity,
- enterprise mandate,
- communication profile,
- department membership,
- collaboration relationships,
- escalation relationships,
- governed long-term memory,
- skill profile,
- current objectives,
- provenance-aware decision history.

The persona is deliberately separated from the model engine.

```text
Anya
  + Soul
  + Enterprise Role
  + Memory
  + Skills
  + Relationships
  + Decision History
        |
        +--> Claude
        +--> Gemini
        +--> local model
        +--> future provider
```

The provider may change without destroying persona continuity.

### 3.2 Digital Enterprise Graph

Camelot should maintain an explicit organizational graph containing responsibility, collaboration, delegation targets, escalation paths, shared-context scope, and department membership.

Example:

```text
Anya          executive intent / synthesis
 |
 +-- Merlin        architecture / decomposition
 |
 +-- Synthetos     source-isolated synthesis
 |
 +-- Heimdall      observation / watchtower
 |
 +-- Helios        development-only engineering worker
 |
 +-- specialist departments and cartridges
```

This graph defines organizational behavior. It is not authority.

---

## 4. Contract-First Foundation

### 4.1 Contract Forge

The v3 contract foundation currently exists in the `CAMELOT_OS` reforge branch as an additive extension of the existing contract catalog. The draft catalog contains 36 schemas and a green Contract Forge / Authority Closure CI gate.

Key v3 contract families include:

| Concept | Contract |
|---|---|
| Persistent persona identity | `camelot-soul/1` |
| Enterprise role | `camelot-enterprise-role/1` |
| Existing competence profile | `camelot-persona/1` |
| Short-lived task context | `camelot-spark/1` |
| Reasoning procedure | `camelot-rune/1` |
| Bounded executable package | `camelot-pill/1` |
| Provisional memory | `camelot-memory-candidate/1` |
| Active governed memory | `camelot-memory-object/1` |
| Sentinel-compiled authority projection | `camelot-effective-capability-set/1` |
| Signed current authority certificate | `camelot-authority-epoch/1` |
| Immutable Knight identity package | `camelot-knight-package/1` |

### 4.2 Signed-object discipline

Additive v3 signed contracts use deterministic canonicalization, SHA-256 content digests, Ed25519 signatures, explicit signature domains, issuer identity, tenant/workspace scope, validity windows, lifecycle state, and provenance references.

Cryptographic validity means only that a trusted issuer signed an object. It never implies effect authority.

---

## 5. Authority Architecture

### 5.1 Authority chain

```text
Intent / Quest
    |
    v
Persona interpretation
    |
    v
Typed plan / DAG / Effect Manifest
    |
    v
Sentinel policy decision
    |
    +--> Excalibur approval if required
    |
    v
Capability Lease
    |
    v
VFS / resource preflight
    |
    v
Bounded executor
    |
    v
Gideon verification
    |
    v
Arthur resolution
    |
    v
Receipt Ledger
    |
    v
Canonical State Projection
```

### 5.2 Effective Capability Set

The v3 design introduces a Sentinel-compiled `EffectiveCapabilitySet` as an execution-time projection derived from applicable policy and ceilings.

Its purpose is to simplify executor admission. It does not become a second policy engine.

```text
effective capability set =
intersection(
  policy,
  persona/knight package,
  Spark,
  Pill,
  Cartridge,
  effect manifest,
  current lease
)
```

No layer may widen another.

### 5.3 Effect risk and cognition terminology

v3 distinguishes two concepts:

- `T0..T4`: effect risk / approval / quorum classification in the Contract Forge direction.
- `L0..L5`: cognition, offline, or bounded-effect ceiling used by persona continuity and island-mode rules.

The current `.agent/governance.yaml` still uses `L0..L5` as risk tiers. That is a documented migration conflict and must be explicitly resolved before v3 is promoted as binding governance.

---

## 6. Twin-Brain Authority Fencing

The v2.1 Twin-Brain model remains intact.

Open-Notebook and NotebookLM may participate as Crown cognitive brains, but only the active promoted brain participates in current authority-bearing flows. Promotion increments the signed authority epoch.

All authority-sensitive services must read and verify the signed current epoch at the decision boundary.

Current VPS implementation already uses a dynamic `EpochSource` in multiple services including Sentinel and Node Agent. The current Receipt Service on `main` still initializes with a static `CAMELOT_AUTHORITY_EPOCH` and is the identified runtime handoff seam.

v3 requires:

```text
receipt.authorityEpoch == currently verified signed authority epoch
```

for every newly admitted receipt.

Historical receipts remain valid evidence after promotion.

---

## 7. Quest and Workflow Architecture

Prompt-only workflow compliance is insufficient.

v3 turns Quest/GOSO-style workflows into explicit state machines or DAGs whose transitions require evidence.

Reference lifecycle:

```text
QUEST_CREATED
  -> SURVEY
  -> ARCHITECT
  -> PROPOSE_EFFECTS
  -> POLICY_CHECK
  -> APPROVAL_REQUIRED?
  -> LEASED
  -> PREFLIGHT
  -> EXECUTING
  -> VERIFYING
  -> RESOLVING
  -> RECEIPTED
  -> PROMOTED
  -> PROJECTED
```

A persona cannot mark a task complete merely by reporting success. Completion requires the contractually defined evidence chain.

---

## 8. Context, Memory, and Knowledge

### 8.1 Context Compiler

The v3 target replaces a generic memory-broker concept with a **Context Compiler**.

The Context Compiler produces a Spark from:

```text
Quest
+ Soul
+ Persona competence profile
+ Enterprise Role
+ relevant UKG
+ governed memory
+ approved skills
+ recent receipts
+ host state
+ token budget
= Spark
```

The goal is minimum sufficient context, not maximal memory exposure.

### 8.2 Memory classes

Camelot distinguishes:

- session context,
- persona scratch memory,
- enterprise long-term memory,
- procedural skill memory,
- signed UKG knowledge,
- canonical runtime state,
- authority.

Authority is not memory.

### 8.3 Governed memory activation

```text
memory candidate
  -> Gideon verdict
  -> Arthur resolution
  -> activation receipt
  -> active memory
```

A persona may propose memory. It cannot self-activate canonical memory.

---

## 9. Skills, Runes, Pills, and Cartridges

### 9.1 Rune

A Rune is a versioned reasoning procedure. It grants no capabilities.

### 9.2 Pill

A Pill is a bounded executable capability package. It defines possible tool reach and resource limits. It remains subordinate to policy and a lease.

### 9.3 Skill

Skills follow a governed lifecycle:

```text
experience
 -> candidate skill
 -> static validation
 -> sandbox evaluation
 -> Gideon review
 -> Arthur resolution
 -> attestation
 -> registry promotion
```

### 9.4 Cartridge

A Cartridge is a versioned enterprise capability composition that may package personas, Runes, Pills, skills, workflows, memory schemas, UI surfaces, and evaluation suites.

A Cartridge cannot replace Sentinel or widen Core authority.

---

## 10. Bifrost Capability Fabric

Bifrost remains transport and admission, not policy authority.

v3 evolves Bifrost toward a typed capability fabric in which calls carry stable action types, identity, quest/task scope, effect hash, lease reference, epoch, idempotency key, payload digest, expiry, and provenance.

External protocols such as MCP are adapters beneath this boundary.

**MCP is not an authority boundary.** A successful MCP request does not imply Camelot effect permission.

---

## 11. Model and Cognitive ABI

Camelot personas and cognitive roles must not be tied to one provider.

The Model/Cognitive ABI should expose:

- requested cognitive role,
- model capability requirements,
- context window requirement,
- privacy classification,
- latency/cost preference,
- fallback policy,
- structured output schema,
- tool visibility,
- provenance metadata.

Models may be routed among Claude, Gemini, Hermes-style agents, local models, and future providers. The model never owns canonical state or sovereign authority.

---

## 12. Shadow Brain and Offline Continuity

The v2.1 Shadow Brain doctrine remains.

A Shadow Brain preserves cognition and local enterprise continuity, not sovereign authority.

Allowed island-mode work includes local retrieval, reasoning, drafts, local Shadow VFS work, diagnostics, provisional journal records, and candidate knowledge.

Canonical promotion, external communication, deployment, payment, irreversible actions, policy mutation, lease issuance, and trust-root rotation remain denied or `OFFLINE_PENDING` unless an explicitly scoped offline-safe lease exists.

Rejoin remains evidence-first:

```text
offline journal
 -> integrity validation
 -> conflict analysis
 -> Gideon
 -> Arthur
 -> receipt
 -> canonical merge or quarantine
```

---

## 13. Host ABI and //ASSIMILATION

### 13.1 Host ABI

Camelot v3 introduces an architecture-defined Host ABI to keep the sovereign core OS-independent and the edge OS-aware.

Initial target capabilities include:

- host identity and capability inventory,
- service start/stop/status,
- workspace creation and snapshot,
- sandbox spawn/cancel,
- scoped filesystem access,
- leased network access,
- notification,
- rollback prepare/apply.

Initial adapters should prioritize generic Linux/systemd, Arch/Omarchy, headless VPS, then expand.

### 13.2 //ASSIMILATION

`//ASSIMILATION` becomes a safe host discovery and convergence protocol:

```text
DISCOVER
 -> ATTEST
 -> CLASSIFY HOST
 -> INVENTORY CAPABILITIES
 -> SELECT SIGNED ADAPTER
 -> LOAD DESIRED STATE
 -> DIFF
 -> DRY RUN
 -> POLICY / APPROVAL
 -> LEASE
 -> APPLY
 -> VERIFY
 -> RECEIPT
 -> REGISTER NODE
```

Discovery alone grants no authority.

Running the same desired-state plan again should be idempotent.

### 13.3 Omarchy

Omarchy is treated as a host profile, not Camelot's sovereign foundation.

Potential integration surfaces include:

- systemd service integration,
- signed package integration,
- Hyprland/Quickshell persona/command-center UI,
- local notifications,
- agent skill discovery adapters.

The Omarchy UI may render Camelot state and submit intent. It must not hold Sentinel signing keys, epoch-promotion authority, or direct canonical-write authority.

---

## 14. Multi-Device Kingdom

Camelot's distributed topology should route by capability rather than hard-coded machine name.

Example:

```text
Quest requires:
  gpu.inference
  source.retrieve
  voice.speak

Bifrost capability routing:
  workstation -> gpu.inference
  VPS         -> source.retrieve
  mobile      -> voice.speak
```

Sentinel still controls whether the capability may be exercised.

A node advertises capability. It does not advertise permission.

---

## 15. Security Architecture

Primary v3 threat classes include:

| Threat | v3 control |
|---|---|
| Persona remembers old permission | authority prohibited from memory schemas |
| Model-provider compromise | model is proposal engine only |
| Soul mutation | Knight package binds immutable Soul digest |
| Cross-workspace persona substitution | signed tenant/workspace binding |
| Stale Twin-Brain authority | dynamic signed epoch admission |
| Skill self-promotion | candidate -> verify -> resolve -> receipt |
| MCP/tool prompt injection | trust classification + capability gate |
| Host adapter escalation | signed adapter + dry-run + lease + receipt |
| Offline authority manufacture | Shadow has no lease/policy signing ability |
| Capability widening | intersection/attenuation semantics |
| Runaway legal loop | budgets + circuit breakers + lease expiry |
| UI claims completion early | canonical receipt/state projection required |

---

## 16. Implementation Truth as of 2026-09-19

| Capability | Status |
|---|---|
| v2.1 Bifrost / Sentinel / VFS / Node Agent / State / Gideon / Arthur baseline | Present in Camelot-VPS convergence code |
| Dynamic signed epoch source | Implemented in Camelot-VPS and consumed by several authority services |
| Receipt `authorityEpoch` field | Implemented |
| Dynamic signed epoch at live Receipt Service append boundary | Not yet wired on main; identified runtime handoff item |
| Contract Forge additive schemas | Implemented on draft CAMELOT_OS reforge branch |
| Contract Forge CI | Green on draft CAMELOT_OS PR |
| Persona Soul / Enterprise Role / Spark / Rune / Pill schemas | Implemented on draft CAMELOT_OS reforge branch |
| Signed Knight package reference loader | Implemented as reference harness logic in CAMELOT_OS; not yet live Knight Registry |
| Memory candidate / active memory contracts | Implemented in draft contract layer; live memory services not yet built |
| Effective Capability Set contract | Implemented in draft contract layer; live Sentinel compiler not yet built |
| Sir Synthetos reference profile | Defined and contract-tested |
| Host ABI | Architecture defined; not implemented |
| //ASSIMILATION runtime | Architecture defined; not implemented |
| Omarchy adapter/UI | Architecture defined; not implemented |
| Shadow Brain / UKG / Reconciler / Forge Crystal | Architecture defined; not yet complete as live production loop |
| Skill Registry / governed procedural learning | Architecture defined; not yet implemented |

---

## 17. Reforge Migration Sequence

The recommended migration order is:

```text
Contract compatibility
 -> dynamic receipt epoch closure
 -> signed Knight package registry
 -> Context Compiler / Spark builder
 -> Synthetos read-only vertical slice
 -> Effective Capability Set compiler
 -> governed memory activation
 -> canonical VFS promotion closure
 -> skill/cartridge registry
 -> UKG / Shadow continuity
 -> Bifrost capability fabric v2
 -> Host ABI
 -> //ASSIMILATION
 -> Omarchy profile
 -> multi-host Kingdom routing
 -> higher-risk effect expansion
```

No new high-risk autonomous capability should outrun the evidence and authority substrate.

---

## 18. Production Readiness Gates

### Gate A - Contract and Mechanical Green
All schemas, compatibility rules, Rust/Go formatting, check, tests, and Clippy/vet gates are green.

### Gate B - Authority Closure
Receipt admission dynamically verifies signed epoch. Revocation, replay protection, exact effect binding, and trust-root ceremony are proven.

### Gate C - Persona Identity Closure
Signed Soul, persona profile, Enterprise Role, and Knight package are admitted with immutable digest and scope verification.

### Gate D - Canonical Effect Loop
Effect manifest -> policy -> lease -> preflight -> execution -> Gideon -> Arthur -> receipt -> state projection works end to end.

### Gate E - Governed Learning
Memory and skill candidates cannot self-promote. Activation requires verification, resolution, provenance, and receipt.

### Gate F - Continuity
Shadow Brain, UKG synchronization, offline journal, reconciler, and recovery crystal survive disconnect/rejoin drills without manufacturing authority.

### Gate G - Portability
Host ABI and //ASSIMILATION safely converge at least one generic Linux target and one Omarchy profile with rollback.

### Gate H - Release Engineering
Signed artifacts, SBOM, installer, migrations, backup/restore, key rotation, rollback, chaos drills, and monitored resource ceilings pass.

---

## 19. Constitutional Law

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

**REFORGE_CANDIDATE**
