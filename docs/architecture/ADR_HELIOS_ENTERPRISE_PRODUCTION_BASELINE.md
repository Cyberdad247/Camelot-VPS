# ADR: Helios Enterprise Production Hardening Baseline

Status: ACCEPTED FOR DEVELOPMENT
Baseline commit: f83e4397bbb1142995004d2cc9b11b1e1e67d84f
Binding governance: v2.1 SOVEREIGN_TRUTH
Candidate architecture: v3 REFORGE_CANDIDATE
Orchestrator: Sir Helios
Authority posture: DEVELOPMENT-ONLY

## Decision

Enterprise production hardening proceeds as an additive development program from the verified PR #9 runtime baseline.

Sir Helios may orchestrate development branches, code generation, tests, CI analysis, review, and evidence preparation. Helios does not receive production effect authority.

## Constitutional boundaries

- Sentinel remains sole policy / lease / revocation authority.
- Epoch Fencer remains the signed authority-epoch source.
- Bifrost transports capability requests but does not grant permission.
- Persona, Soul, Spark, Rune, Pill, UKG, and memory remain non-authoritative.
- Gideon verifies outcomes.
- Arthur resolves outcomes.
- Receipts preserve accepted truth.
- Human review controls binding-governance and production promotion.
- Cognition may be distributed. Authority may not.

## Current verified baseline

At baseline commit f83e4397bbb1142995004d2cc9b11b1e1e67d84f, the following GitHub Actions workflows are green:

- Persona Enterprise Runtime Gate
- Runtime Authority Handoff Gate
- VPS Hub Ledger Runtime Gate
- Twin-Brain Authority Fencing Gate
- VPS Hub Convergence Gate
- Shadow Production Gate
- Cloudbrain NotebookLM Integration Gate

The Native Bifrost and Experience Plane jobs inside the convergence workflow are also green.

## Compatibility posture

Camelot-VPS runtime contracts remain grandfathered where they differ from CAMELOT_OS v3 Contract Forge contracts.

Same or similar contract names MUST NOT be interpreted as wire-compatible unless a compatibility contract or migration explicitly proves that relationship.

Unknown required semantics fail closed.

## Production-hardening workstreams

Wave 1 branches are isolated by concern:

1. Canonical VFS snapshot / diff / promotion closure.
2. Contract Registry + contracts.lock.
3. Key lifecycle + signer classes.
4. Telemetry envelope + SLO foundation.
5. νKG contract + deterministic parser.

Shared-file hotspots are serialized at integration time.

## Merge posture

No Wave 1 branch merges directly to main.

Each lane must produce:
- implementation
- tests
- compatibility impact
- security impact
- rollback/retreat notes
- CI evidence
- unresolved findings

The integration branch is not production promotion.

## Promotion rule

Parallelize implementation.
Serialize authority.
Converge before promotion.
