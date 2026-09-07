# Software Requirements Specification: Camelot-VPS Hub

## 1. Functional Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| FR-1 | Bifrost Hub terminates mTLS and derives tenant context from session. | Unit tests for session auth, integration tests for tenant derivation. |
| FR-2 | World Tree exposes typed retrieval APIs with tenant-filtered Qdrant queries. | Adversarial test: cross-tenant query denied. |
| FR-3 | Operator Console renders HTMX fragments for vitals, missions, approvals, receipts. | E2E test: HUD refreshes every 5s/10s/15s. |
| FR-4 | Multivoice Bridge enforces consent registry before SMS/call. | Test: opt-out number blocked. |
| FR-5 | Hermes Adapter returns proposals only; no direct effects. | Test: Hermes cannot issue leases or write to VFS. |
| FR-6 | VFS Guardian denies path escapes and unprotected writes. | Adversarial test: VFS escape denied. |
| FR-7 | Receipt Ledger appends hash-chained receipts to SQLite WAL2. | Test: receipt chain verification passes. |
| FR-8 | Gideon Verifier blocks effects failing evidence gates. | Test: missing evidence → block. |

## 2. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | RAM cap | 1.1GB/8GB |
| NFR-2 | API latency (P99) | <200ms |
| NFR-3 | Error rate | <5% |
| NFR-4 | Tenant isolation | 100% RLS enforcement |
| NFR-5 | Receipt integrity | Hash-chain verification 100% pass |
