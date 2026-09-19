# Camelot-OS Low-Level Design Document (LLDD)
## v3.0 Contract-First Digital Enterprise Runtime

**Document ID:** `CAMELOT-OS-LLDD-v3.0-20260919`  
**Version:** `3.0.0-REFORGE-CANDIDATE`  
**Date:** `2026-09-19`  
**Status:** `IMPLEMENTATION-GOVERNED | CROSS-REPO REFORGE | PARTIAL RUNTIME INTEGRATION`  
**Authority:** `PROPOSED_SOVEREIGN_TRUTH`  
**Scope:** Camelot-VPS runtime, CAMELOT_OS contracts, persona-enterprise continuity, authority fencing, bounded execution, memory/skill lifecycle, and host portability.

---

## 1. Design Baseline

This LLDD extends the v2.1 runtime design without silently replacing implemented contracts.

Current source-of-truth split:

| Repository | Responsibility |
|---|---|
| `Cyberdad247/Camelot-VPS` | live/native runtime implementations, systemd units, authority services, receipt/state/executor path |
| `Cyberdad247/CAMELOT_OS` | contract catalog, architecture package, conformance harness, additive v3 contract reforge |

v3 remains a candidate until the two repositories converge on compatible promoted contracts and the governance baseline is explicitly updated.

---

## 2. Runtime Service Registry

| Component | Runtime | Current / Target Responsibility | v3 change |
|---|---|---|---|
| Bifrost | Go native | authenticated transport/admission | typed capability fabric, still non-authority |
| Sentinel | Rust native | policy, lease, revocation | compile Effective Capability Set |
| Epoch Fencer | Rust native | signed Twin-Brain epoch | remains authority clock issuer |
| Receipt Service | Rust + SQLite | signed receipt chain | consume dynamic signed epoch at append boundary |
| VFS Guardian | Rust native | path/resource preflight | consume effective capabilities and exact effect binding |
| Node Agent | Rust + Wasmtime | bounded execution | consume effective capabilities, not persona ceilings |
| State Service | Rust + SQLite | authoritative projection/replay/SSE | project only receipted/resolved outcomes |
| Gideon | Rust native | independent evidence verdict | verify memory/skill candidates in addition to effects |
| Arthur | Rust native | final resolution | resolve effect, memory, skill activation outcomes |
| Context Compiler | target Rust native | compile Spark | new v3 service/module |
| Knight Registry | target Rust native | signed Knight/Soul admission | new v3 service/module |
| Skill Registry | target Rust native | signed procedural packages | new v3 service/module |
| Shadow Brain | target native | offline cognition/continuity | remains non-authority |
| UKG Sync | target native | signed knowledge sync | remains separate from authority |
| Host Adapter | target native/plugin | OS-specific capabilities | new v3 portability layer |
| Assimilation Engine | target native | desired-state convergence | new v3 convergence layer |

---

## 3. Contract Layers

### 3.1 Grandfathered runtime contracts

Camelot-VPS currently uses runtime-local contracts such as:

- `authority-epoch/1`,
- `receipt/2`,
- current lease/effect manifest structures,
- VFS attestation contracts,
- Gideon/Arthur runtime contracts.

These remain valid until an explicit compatibility ADR migrates them.

### 3.2 Additive v3 Contract Forge families

The draft `CAMELOT_OS` reforge adds:

```text
camelot-soul/1
camelot-enterprise-role/1
camelot-spark/1
camelot-rune/1
camelot-pill/1
camelot-memory-candidate/1
camelot-memory-object/1
camelot-effective-capability-set/1
camelot-authority-epoch/1
camelot-knight-package/1
```

The v3 runtime must not assume that same-name v2/VPS and v3/CAMELOT_OS contracts are wire-compatible merely because they describe similar concepts. Compatibility must be explicit.

---

## 4. Canonical Signed Object Processing

For additive v3 objects:

```text
parse
 -> schema family/version
 -> canonicalize signing projection
 -> SHA-256 digest
 -> signature domain
 -> Ed25519 verify
 -> trusted issuer/key
 -> tenant/workspace scope
 -> not-before/expiry
 -> lifecycle
 -> revocation view
 -> contract-specific semantic checks
 -> admit/reject
```

Canonical profile identifier:

`camelot-c14n-json/1`

Signature input:

```text
UTF8(signature_domain)
|| 0x00
|| raw_sha256_digest
```

A valid signature proves provenance and integrity only.

---

## 5. Persona Identity Objects

### 5.1 Soul

`camelot-soul/1` fields conceptually include:

```text
object_id
tenant_id
workspace_id
issuer_id
validity window
lifecycle
canonical_name
persona_class
purpose
enterprise_mandate[]
worldview[]
communication_profile
constitutional_limits[]
authority_semantics = identity-not-authority
integrity
```

A Soul change yields a new content digest and invalidates any Knight package bound to the old digest.

### 5.2 Enterprise Role

Defines:

```text
persona_id
soul_ref
department
responsibilities[]
delegates_to[]
collaborates_with[]
escalation_targets[]
shared_context_scopes[]
authority_semantics = organization-not-authority
```

### 5.3 Existing persona competence profile

The existing `camelot-persona/1` contract remains the competence/profile layer during migration.

The Knight loader composes:

```text
Soul
+ camelot-persona/1
+ Enterprise Role
+ Knight Package
```

rather than replacing the existing persona contract.

---

## 6. Knight Package Admission

### 6.1 Package binding

`camelot-knight-package/1` binds:

- persona id/class,
- signed Soul digest,
- persona profile digest,
- enterprise role digest,
- allowed Runes,
- allowed Pills,
- allowed effect classes,
- maximum risk tier,
- maximum cognition ceiling,
- mandatory prohibited capabilities.

### 6.2 Loader admission

Reference loader order:

```text
verify package signature/lifecycle
verify Soul signature/lifecycle
verify Enterprise Role signature/lifecycle
validate existing persona schema
verify tenant/workspace equality
check package/component revocation
verify Soul reference + digest
verify persona digest
verify role reference + digest
verify persona id consistency
verify persona class consistency
verify role -> Soul binding
verify mandatory authority prohibitions
verify package ceiling <= policy ceiling
return LoadedKnight
```

The loaded Knight is a governed identity descriptor. It is not a lease.

### 6.3 Initial production target

Sir Synthetos is the preferred first Knight profile:

```text
persona_id: sir_synthetos
class: research_synthesist
initial cognition ceiling: L1
effect posture: read/internal synthesis
allowed:
  ukg.retrieve
  source.read
  source.parse
  citation.extract
  draft.write.shadow
forbidden:
  policy mutation
  lease issuance
  epoch promotion
  canonical memory activation
  unrestricted network
  direct canonical/main write
  device effects
  external publish
```

---

## 7. Dynamic Authority Epoch Admission

### 7.1 Existing runtime

Camelot-VPS already provides `EpochSource` with:

- dynamic certificate file path,
- pinned Ed25519 public key,
- signed certificate verification,
- static bootstrap fallback,
- `current_epoch()` reread semantics.

Sentinel and Node Agent already use this mechanism.

### 7.2 Receipt Service current state

On current `main`, Receipt Service initializes its `LedgerStore` with a static authority epoch loaded from `CAMELOT_AUTHORITY_EPOCH`.

```text
startup env
 -> static u64
 -> LedgerStore.authority_epoch
 -> validate_draft(draft, static_epoch)
```

This is the v3 authority-closure gap.

### 7.3 Target receipt path

```text
POST /receipts
 -> read current signed epoch certificate
 -> verify pinned epoch signer
 -> obtain current epoch N
 -> validate receipt draft authorityEpoch == N
 -> open ledger transaction
 -> read current sequence/head
 -> construct unsigned receipt
 -> sign receipt
 -> verify receipt integrity
 -> insert receipt
 -> atomically advance head
 -> commit
```

Promotion from N to N+1 must cause an N receipt draft to fail on the next append without restarting Receipt Service.

### 7.4 Historical chain rule

Receipt chain verification does not require every historical receipt to equal the current epoch.

Historical receipts retain the epoch under which they were legitimately issued.

---

## 8. Effective Capability Set

### 8.1 Compilation

Sentinel target function:

```text
compile_effective_capabilities(
  policy,
  loaded_knight,
  spark,
  pill,
  cartridge,
  effect_manifest,
  capability_lease
) -> EffectiveCapabilitySet
```

Semantics are intersection/attenuation only.

### 8.2 Executor use

Node Agent should eventually accept:

```text
effect manifest digest
current lease
effective capability set
VFS attestation
artifact bytes/reference
```

and verify that all hashes, scopes, epochs, resources, and capabilities match.

Node Agent must not interpret Soul, Enterprise Role, or persona memory directly.

---

## 9. Context Compiler and Spark Builder

### 9.1 Inputs

```text
Quest
LoadedKnight
Soul
EnterpriseRole
governed memory
UKG
approved skills
recent receipts
host/runtime state
model token budget
```

### 9.2 Output

A signed/validated Spark containing:

- persona id,
- Soul reference,
- quest/task references,
- context source references,
- trust classification,
- token budget,
- allowed Rune references,
- allowed Pill references,
- cognition ceiling,
- expiry.

### 9.3 Trust classes

v3 draft classes:

```text
TRUSTED_CANONICAL
VERIFIED_EXTERNAL
SIGNED_UKG
USER_SUPPLIED
AGENT_GENERATED
UNTRUSTED_EXTERNAL
QUARANTINED
```

The model receives both content and provenance/trust class.

---

## 10. Memory Activation Pipeline

### 10.1 Candidate state

A memory candidate is provisional and structurally unable to self-activate.

Allowed candidate classes may include:

```text
episodic
semantic
relational
enterprise
procedural-candidate
```

### 10.2 Activation

```text
MemoryCandidate
 -> Gideon verification
 -> Arthur resolution
 -> activation receipt
 -> MemoryObject ACTIVE
```

Active memory must reference:

```text
candidate_digest
gideon_verdict_ref
arthur_resolution_ref
activation_receipt_ref
```

Authority-bearing data is forbidden from memory payloads.

---

## 11. Rune and Pill Runtime

### 11.1 Rune

Rune is procedure metadata.

Example `omega-synthesize`:

```text
SURVEY
 -> ISOLATE SOURCES
 -> EXTRACT CLAIMS
 -> INTERSECTION ANALYSIS
 -> CONFLICT ANALYSIS
 -> SYNTHESIS
 -> PROVENANCE
 -> DRAFT
```

Rune field `grants_capabilities` must remain false.

### 11.2 Pill

Pill declares possible executable reach:

```text
allowed_tools[]
forbidden_tools[]
resource_limits
network_mode
cognition_ceiling
module_digest optional
```

Pill never bypasses lease checks.

---

## 12. Quest State Machine

Suggested v3 persistent states:

```text
QUEST_CREATED
SURVEY
ARCHITECT
PROPOSE_EFFECTS
POLICY_CHECK
AWAITING_APPROVAL
LEASED
PREFLIGHT
EXECUTING
VERIFYING
RESOLVING
RECEIPTED
PROMOTED
PROJECTED
FAILED
QUARANTINED
CANCELLED
```

Transitions should carry required evidence predicates rather than depend on prompt memory.

Example:

```text
EXECUTING -> VERIFYING
requires:
  execution result
  artifact/result digest
  lease reference
  effect manifest reference
  epoch reference
```

---

## 13. Bifrost Action Envelope

Target logical fields:

```text
schema/version
message id
quest id
task id
actor/knight id
tenant/workspace
action type
resource URI
effect manifest hash
lease id
authority epoch
idempotency key
payload digest/reference
parent receipt/provenance
expiry
signature/transport evidence
```

Bifrost validates transport and message admission. Sentinel remains permission authority.

MCP, browser automation, voice routing, GitHub, database, WorldMonitor, and other integrations remain adapters underneath this envelope.

---

## 14. Host ABI

Target interface:

```text
HostIdentity identity()
HostCapabilities capabilities()

service.status(name)
service.start(name)
service.stop(name)

workspace.create(spec)
workspace.snapshot(id)
workspace.destroy(id)

sandbox.spawn(profile)
sandbox.cancel(id)

filesystem.read(scope,path)
filesystem.write_scoped(scope,path,data)

network.open_lease(route, lease)

notify(event)

rollback.prepare(plan)
rollback.apply(plan)
```

Host adapters must translate Camelot actions to OS-specific primitives without defining permission.

---

## 15. //ASSIMILATION Runtime

### 15.1 Phases

```text
DISCOVER
ATTEST
CLASSIFY
INVENTORY
SELECT_ADAPTER
DESIRED_STATE
DIFF
DRY_RUN
POLICY
APPROVAL
LEASE
APPLY
VERIFY
RECEIPT
REGISTER
```

### 15.2 Idempotency

If desired state already matches observed state:

```text
result = NO_OP
receipt = convergence verified
```

No duplicate install is permitted.

### 15.3 Omarchy adapter

Expected adapter decomposition:

```text
host/linux
host/systemd
host/arch
host/omarchy
ui/quickshell
desktop/hyprland
package/pacman
```

The Quickshell/UI component is not a trust boundary.

---

## 16. systemd and Runtime Hardening

The v2.1 hardening posture remains:

- loopback-only privileged services,
- `NoNewPrivileges=true`,
- minimal writable paths,
- protected home/system/kernel interfaces,
- explicit memory/CPU/task ceilings,
- pre-provisioned signing credentials where applicable,
- no browser-visible secrets,
- default-deny network posture for authority services.

Receipt Service target systemd update must add the dynamic epoch certificate path and pinned epoch public key access while keeping its writable filesystem restricted to the receipt ledger.

---

## 17. CI / Conformance Gates

### 17.1 CAMELOT_OS Contract Forge

Current draft reforge gate validates:

- Draft 2020-12 schema validity,
- deterministic canonicalization,
- SHA-256 mutation detection,
- domain-separated Ed25519 verification,
- tenant substitution rejection,
- unknown version rejection,
- expiry/revocation rejection,
- Rune non-authority rule,
- memory activation provenance,
- ceiling attenuation,
- signed authority-epoch reference behavior,
- signed Knight/Soul package admission.

### 17.2 Camelot-VPS runtime gates

Runtime handoff should update:

- `twin-brain-fencing.yml` to include Receipt Service where dynamic epoch semantics are shared;
- `vps-hub-ledger-runtime.yml` to include `camelot-epoch`;
- convergence gate where Knight Registry/Context Compiler are added later.

Required authority drill:

```text
write signed epoch N
append receipt N -> PASS

atomically replace certificate with valid signed N+1
append receipt N -> FAIL
append receipt N+1 -> PASS

no service restart between promotion and rejection
```

---

## 18. Data and Provenance Graph

All durable v3 objects should support `derived_from[]` or equivalent provenance links where appropriate.

Conceptual lineage:

```text
Quest
 -> Spark
 -> Model Output
 -> Effect Manifest
 -> Lease
 -> Execution Evidence
 -> Gideon Verdict
 -> Arthur Resolution
 -> Receipt
 -> Canonical State

Memory:
source evidence
 -> memory candidate
 -> Gideon
 -> Arthur
 -> activation receipt
 -> active memory

Skill:
executions/evidence
 -> candidate skill
 -> tests
 -> Gideon
 -> Arthur
 -> signed skill
```

This DAG is the basis for future Gods-Eye provenance visualization.

---

## 19. Resource Budgets and Circuit Breakers

Each autonomous quest should support limits such as:

```text
max_model_calls
max_tool_calls
max_delegations
max_recursion_depth
max_wall_time
max_tokens
max_external_requests
max_bytes_written
max_cost
```

Breaker conditions should include repeated tool failure, repeated policy denial, unexpected capability requests, context divergence, budget exhaustion, and verification failure.

Breaker state:

```text
RUNNING -> DEGRADED -> PAUSED -> HUMAN_REVIEW
```

---

## 20. Cross-Repo Migration Map

### Stage 1
Keep v2.1 runtime contracts intact. Land v3 architecture documents and compatibility notes.

### Stage 2
Wire dynamic signed epoch source into Receipt Service append admission.

### Stage 3
Promote signed Knight/Soul package loader into a live Knight Registry or Sentinel-adjacent admission module.

### Stage 4
Add Context Compiler and Spark Builder.

### Stage 5
Run Sir Synthetos end to end as the first low-risk persona:

```text
Soul
 -> Persona
 -> Enterprise Role
 -> Knight Package
 -> Spark
 -> Rune
 -> Pill
 -> Evidence
 -> Gideon
 -> Arthur
 -> Receipt
```

### Stage 6
Compile Effective Capability Set inside Sentinel and consume it in Node Agent.

### Stage 7
Add governed memory activation and skill registry.

### Stage 8
Complete Shadow/UKG/rejoin continuity.

### Stage 9
Introduce Host ABI, //ASSIMILATION, and Omarchy profile.

---

## 21. Known Architecture Mismatches to Resolve Before Promotion

1. `.agent/governance.yaml` still names v2.0 as binding baseline.
2. `.agent/governance.yaml` uses `L0..L5` for risk tiers while v3 Contract Forge separates `T0..T4` effect risk from `L0..L5` cognition/offline ceilings.
3. Camelot-VPS and CAMELOT_OS contain different authority-epoch wire shapes. They are conceptually aligned but not yet a single promoted wire contract.
4. Camelot-VPS `receipt/2` and CAMELOT_OS `camelot-receipt/1` are separate families and require an explicit compatibility/migration ADR.
5. The Knight package loader is contract-tested but not yet a live runtime authority consumer.
6. Effective Capability Set exists as a draft contract but is not yet emitted by live Sentinel.
7. Host ABI and //ASSIMILATION remain architecture-defined.

These mismatches are explicit migration work, not hidden implementation assumptions.

---

## 22. Acceptance Definition for v3 Promotion

v3 becomes eligible for promotion only when:

```text
contracts are versioned and cross-repo compatible
dynamic receipt epoch fencing is live
Knight/Soul package admission is live
Synthetos low-risk mission completes through receipt projection
memory cannot self-activate
authority cannot be recovered from memory or persona state
current authority can be rotated without stale effect acceptance
canonical effect loop passes restart/replay drills
offline continuity cannot manufacture authority
Host ABI does not weaken sovereign boundaries
governance.yaml and architecture docs agree on vocabulary
```

**REFORGE_CANDIDATE**
