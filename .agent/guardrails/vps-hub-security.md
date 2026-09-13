# VPS Hub Security Guardrails

## Identity and sessions

- Primary interactive authentication is WebAuthn/passkey based.
- Browser sessions use Secure, HttpOnly, SameSite=Strict cookies backed by server-side revocation state.
- State-changing browser requests require CSRF protection and idempotency keys.
- High-risk operations require fresh policy-defined step-up authentication.
- BioAuth may provide local user-presence evidence, but never replaces cryptographic authentication.
- Raw biometric templates, audio, or image material must not enter general memory, broad logs, Bifrost payloads, or receipt payloads.

## Tenancy

- Tenant/workspace scope is derived server-side from authenticated identity and membership.
- PostgreSQL RLS is a last-line isolation control, not the source of identity context.
- Redis, SQLite-VSS, MinIO, receipts, approvals, leases, workspace events, and object references are tenant scoped.
- Cross-tenant indexes and unscoped object buckets are prohibited.

## Network

Default posture is deny.

- Internet ingress is explicit HTTPS or authenticated overlay only.
- Edge nodes connect to the Hub through authenticated Bifrost sessions.
- Edge-to-edge lateral movement is denied.
- Browser-to-database and cartridge-to-database access are denied.
- Workers may use external network destinations only when the lease names an approved route.
- Bifrost connectivity does not create tool authority.

## Execution classes

- R0 Control: Rust native, highest trust, explicit internal/Bifrost network only.
- R1 Transport: Go native, authenticated mesh transport.
- R2 Trusted Pill: Wasmtime/WASI, deny-by-default capabilities.
- R3 Untrusted Chamber: Firecracker, no network by default, disposable filesystems and synthetic secrets only.
- R4 Experience: browser/PWA, untrusted client.

Candidates may never self-promote, write production policy, issue leases, or access live tenant secrets.

## Consequential effects

- A model may propose but never authorize its own action.
- Excalibur approval binds to the exact immutable effect-manifest digest.
- Any change to target, recipient, capability, content, cost, duration, or endpoint invalidates prior approval.
- Sentinel is the sole issuer/revoker of capability leases.
- Gideon independently verifies required evidence and contracts.
- Arthur resolves final promotion/completion only after required gates pass.
- Ledger appends evidence and does not authorize work.

## VFS

Deny when any of these conditions are present:

- path escapes the workspace root,
- requested write path is absent from lease scope,
- executable is absent from the allowlist,
- network action lacks a named approved route,
- secret handle is not present in the lease,
- lease is expired, revoked, or stale relative to authority epoch,
- workload exceeds RAM/CPU/storage/time/queue budget,
- source provenance, classification, or license checks fail.

## Experience truthfulness

World Tree, Battle Mode, Shadow Subspace, Excalibur, and any future scroll-film surface must visibly distinguish:

1. simulated fixture,
2. proposal,
3. pending approval,
4. leased/running,
5. verification pending,
6. receipted completion,
7. denied/failed/revoked.

Animation, 3D rendering, cinematic footage, and optimistic UI may not imply completion before a verified receipt projection exists.

## Required adversarial fixtures

Production gates include forged operator request, expired manifest, stale authority epoch, forged node receipt, receipt-parent tamper, VFS path escape, prohibited process, unauthorized secret, unauthorized network route, cross-tenant query/cache attempt, prompt-injection document, malformed structured tree, duplicate provider webhook, primary partition, Twin-Brain promotion, and mobile permission denial.
