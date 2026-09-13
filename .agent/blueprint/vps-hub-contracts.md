# VPS Hub Binding Contracts

These contracts specialize the Camelot-OS v2.0 living baseline for the Cybertronia VPS Hub.

## Authority predicate

An effect may proceed only when all required terms are true: authenticated actor, authorized tenant scope, policy allow, verified immutable manifest, current authority epoch, active manifest-bound lease, valid node and workload identity, VFS preflight pass, available resource budget, required verification pass, current human approval where required, and healthy receipt chain.

Bifrost admission is not an authority grant. Bifrost proves transport and message integrity. Sentinel grants authority.

## Mission state machine

`Draft -> Classified -> Preflight -> LeaseIssued -> Running -> Verifying -> Completed`

Alternative terminal branches are `Denied`, `Failed`, `TimedOut`, or `Cancelled`. Terminal work is then revoked and cleaned. No implementation may represent a mission as completed until a verified receipt projection exists.

## Core contract catalog

| Contract | Purpose | Owner |
|---|---|---|
| actor.schema.json | user, service, workload identity | Identity |
| tenant.schema.json | tenant isolation context | Tenant service |
| task.schema.json | typed mission/task proposal | Anya/Moon |
| effect-manifest.schema.json | immutable consequential action | Excalibur |
| policy-decision.schema.json | allow, deny, or review decision | Sentinel |
| capability-lease.schema.json | short-lived scoped authority | Sentinel |
| evidence-envelope.schema.json | verification evidence reference | Gideon |
| receipt.schema.json | signed hash-chained audit record | Ledger |
| gideon-verdict.schema.json | independent assessment | Gideon |
| device-action.schema.json | manifest-bound device operation | Mobile broker |
| promotion.schema.json | candidate release decision | Arthur |

## Bifrost envelope

The Hub accepts only signed, fresh envelopes with explicit routing scope. Required fields are schema version, event id, type, priority lane, occurrence time, expiry, tenant/workspace/mission routing scope, target, correlation id, idempotency key, payload reference, payload hash, signer identity, and Ed25519 signature.

Priority lanes follow the binding baseline: P0 critical authority events, P1 actionable missions and task calls, P2 digests, P3 telemetry, P4 retries, plus a reserved heartbeat/system lane. Messages should stay below 8 KiB. Larger material is referenced through object storage. State-changing envelopes require idempotency keys and receipt-aware retry semantics.

## Workspace event projection

Every projected event carries event id/type/time, tenant/workspace/cartridge/mission/trace scope, monotonically ordered sequence, classification, visibility, payload, provenance references, payload hash, and optional signature.

The PWA consumes snapshot plus SSE replay of authoritative projections. It must never infer a successful effect from a button click or transport response.

## Receipt chain

Receipt hashes are derived from the previous receipt hash, canonical payload hash, and metadata hash. Receipts are append-only, tenant-scoped, signed, and hash chained. Large artifacts remain external references.

## VFS workspace contract

Each task receives an isolated tree under `/runtime/camelot/tasks/<task-id>/` with read-only `source/`, lease-approved `worktree/`, quota-limited `tmp/`, `evidence/`, task-local `socket/`, redacted `logs/`, and a locally verified `lease.json`.

Preflight denies path escape, unleased writes, unallowlisted executables, unnamed network routes, missing secret handles, expired/revoked/stale leases, resource excess, or invalid source provenance/classification/license.

## Tenant scope

Every request, event, object, cache key, graph/vector row, lease, receipt, approval, and artifact carries tenant, workspace, cartridge, mission, classification, retention, and provenance scope. Client-supplied tenant authority is never trusted; the server resolves it from authenticated identity.
