# Product Requirements Document: Camelot-VPS Hub

## 1. Product Goal

Deploy a sovereign, bare-metal VPS Hub as the master control plane for Camelot-OS vMAX, hosting Bifrost (zero-trust gateway), World Tree (temporal context graph), Multivoice (consent-governed telephony), and an HTMX/WebGPU operator console. Integrate Hermes Agent as a bounded executor adapter under Camelot's authority model.

## 2. Core User Stories

| Role | Story | Acceptance Criteria |
|------|-------|---------------------|
| Platform Engineer | As an engineer, I can deploy Camelot-VPS on Ubuntu 22.04/24.04 with one script. | Install script provisions Neo4j, Qdrant, PostgreSQL, MinIO, Ollama, and builds Go/Rust services. |
| SRE | As an SRE, I can monitor RAM, CPU, API latency, and error rate via the HUD. | Vitals panel refreshes every 5s, alerts at >90% RAM or P99 >200ms. |
| Security Auditor | As an auditor, I can export tenant-isolated receipts and policy decisions. | Receipt ledger export includes hash chain verification. |
| ML Engineer | As an ML engineer, I can integrate Hermes Agent as a proposal-only adapter. | Hermes returns structured proposals; Camelot issues leases and verifies effects. |
| Operations Staff | As an operator, I can approve/reject R4+ effects via the approval drawer. | Approval UI shows manifest hash, scope, target, evidence, expiry, rollback. |

## 3. Key Performance Indicators

- **Learning Efficiency:** Hermes proposal acceptance rate >85%.
- **Output Quality:** Gideon verification pass rate >95%.
- **Planning Rigor:** 100% of missions have typed DAGs and evidence refs.
- **Security:** Zero cross-tenant data access in adversarial tests.
- **Performance:** P99 API latency <200ms at 1.1GB RAM cap.
