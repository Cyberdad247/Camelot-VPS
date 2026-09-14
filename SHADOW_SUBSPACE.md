# Camelot Shadow Subspace

Shadow Subspace is Camelot-OS's bounded agent-workspace architecture for using Puter as a visual Shadow Castle while keeping consequential authority in native Camelot services.

## Prime invariant

> **The Shadow may minimize external footprint, but it is never invisible to the Crown.**

"Footprint-minimized" means: no public inbound listener for the native executor, temporary workspaces, narrow egress, short-lived mission context, and no browser exposure of privileged credentials. It does **not** mean bypassing fraud controls, spoofing identity, evading attribution, or deleting the sovereign audit trail.

## Components

```text
Throne Room / Sir Umbra
        |
        v
ShadowSubspacePortal (React)
        |
        v
Bifrost Shadow Adapter :4188
        |  server-side token only
        v
camelot-shadowd :4190 (Rust, loopback only)
        |
        +-- Shadow VFS /var/lib/camelot/shadow/<session>/workspace
        +-- HITL risk gate R0-R6
        +-- Ed25519-signed hash-chain receipts
        +-- bounded CPU/RAM/TTL contract
        +-- no arbitrary shell endpoint

Puter Shadow Castle :4100
        |
        +-- authenticated camelot-shadow extension
        +-- calls Bifrost only
        +-- never receives shadowd token
```

## Risk rings

| Ring | Intended use | Default behavior |
| --- | --- | --- |
| R0 | passive inspection | policy-bounded |
| R1 | reasoning / planning | policy-bounded |
| R2 | Shadow VFS mutation | policy-bounded + receipt |
| R3 | approved external reads / reversible preparation | policy-bounded + receipt |
| R4 | external write / communication | mandatory HITL |
| R5 | production mutation / credential-bearing effect | mandatory HITL |
| R6 | irreversible or security-critical effect | **fail-closed by default** |

R6 is not enabled merely because a browser or CLI says the operator is sovereign. `camelot-shadowd` refuses R6 sessions/effects unless the server-side `CAMELOT_SHADOW_ALLOW_R6=1` switch is deliberately enabled. Keep it disabled until Camelot has a server-authenticated sovereign-identity path. Even when enabled, an R6 approval must use `sovereign` scope.

`camelot-shadowd` currently authorizes effect manifests after policy/HITL evaluation but deliberately does **not** expose a generic arbitrary command executor. Specific future effect adapters should be implemented one-by-one behind capability schemas.

## Native daemon

Build:

```bash
cargo build --release -p camelot-shadowd
```

Required secret:

```bash
export CAMELOT_SHADOW_TOKEN="$(openssl rand -hex 32)"
```

Run locally:

```bash
CAMELOT_SHADOW_TOKEN="$CAMELOT_SHADOW_TOKEN" \
CAMELOT_SHADOW_ALLOW_R6=0 \
  cargo run -p camelot-shadowd
```

The daemon refuses to start on a non-loopback bind address and refuses startup without a token of at least 24 characters.

## Bifrost

Use the same server-side secret for the Bifrost process:

```bash
export CAMELOT_SHADOW_URL=http://127.0.0.1:4190
export CAMELOT_SHADOW_TOKEN="$CAMELOT_SHADOW_TOKEN"
```

The browser only receives `/api/bifrost/shadow/*`. Bifrost injects the native bearer token server-side.

Exposed governed routes:

- `GET /api/bifrost/shadow/health`
- `GET|POST /api/bifrost/shadow/sessions`
- `GET /api/bifrost/shadow/sessions/:session`
- `POST /api/bifrost/shadow/sessions/:session/effects`
- `POST /api/bifrost/shadow/sessions/:session/effects/:effect/approve`
- `POST /api/bifrost/shadow/sessions/:session/effects/:effect/deny`
- `POST /api/bifrost/shadow/sessions/:session/files/write`
- `GET /api/bifrost/shadow/sessions/:session/files/read?path=...`
- `GET /api/bifrost/shadow/sessions/:session/receipts`
- `POST /api/bifrost/shadow/sessions/:session/seal`

There is no generic `proxy?url=` or arbitrary native route forwarding.

## Capability and egress guardrails

The daemon, not the browser, owns the allowlists. The current native capability ceiling is:

```text
shadow.read
shadow.write
shadow.plan
bifrost.request
```

The only current network egress label accepted by the native daemon is:

```text
bifrost://governed
```

A client cannot invent a new capability or egress destination by adding a string to its session request.

## Shadow VFS

Every summoned session receives a dedicated directory:

```text
/var/lib/camelot/shadow/<session-id>/workspace
```

The daemon rejects absolute paths, `..`, root components, and non-normal path components. Reads and writes are capped at 256 KB per request. Sealing a mission writes its final receipt first and then removes the ephemeral session workspace. Ledger records remain outside the session directory.

This is the first-stage copy-on-write boundary. A future VFS integration can populate the session directory from an approved source snapshot and promote validated diffs back to the canonical VFS only after review.

## HITL receipt chain

Receipts are JSON Lines at:

```text
/var/lib/camelot/shadow/ledger/receipts.jsonl
```

Each receipt includes:

- mission/session ID
- Knight identity
- risk ring
- allow / deny / wait-HITL decision
- resource URI
- payload hash
- parent receipt hash
- receipt hash
- ephemeral daemon public signing key
- Ed25519 signature

The daemon reloads the previous receipt hash at startup so new entries continue the append-only hash chain. It currently generates a fresh signing key at process start, however. Production hardening should move that signing key to a persisted protected credential or hardware-backed signer so signer continuity also survives restarts.

## Puter Shadow Castle

The companion branch in `Cyberdad247/puter` installs an authenticated extension under:

```text
src/backend/extensions/camelot-shadow/
```

Puter's runtime discovers external extensions from its configured extension/mod directories. The adapter calls Bifrost only and exposes a narrow Puter-side API for session creation, effect proposals, human decisions, receipt review, and sealing.

Configure the Puter backend with:

```bash
export CAMELOT_BIFROST_URL=http://127.0.0.1:4188
```

## Sovereign CLI

```bash
npm run camelot -- shadow status
npm run camelot -- shadow list
npm run camelot -- shadow summon sir_codex "Prepare a bounded implementation plan"
npm run camelot -- shadow propose <session> R4 external.write bifrost://approved-realm "Publish approved artifact"
npm run camelot -- shadow approve <session> <effect> once "Approved after review"
npm run camelot -- shadow receipts <session>
npm run camelot -- shadow seal <session>
```

R6 commands intentionally fail while `CAMELOT_SHADOW_ALLOW_R6=0`.

## Production hardening still required

- run `cargo check --workspace` and the frontend TypeScript build in CI
- persist or hardware-bind the receipt signing key
- connect Sentinel-issued capability leases instead of the current session-local capability list
- add Heimdall identity/integrity/intent/payload/access evidence to every R4-R6 approval receipt
- replace browser-declared operator identity with a server-authenticated Camelot operator identity
- integrate canonical VFS snapshot/promote APIs for true source copy-on-write semantics
- add specific effect executors rather than a generic shell
- bind Puter user identity to Camelot operator identity instead of the current authenticated-user fallback
- E2E test summon → R4 proposal → human approval/deny → receipt verification → seal
