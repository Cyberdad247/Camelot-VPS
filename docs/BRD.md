# Business Requirements Document: Camelot-VPS Hub

## 1. Business Objectives

- **Sovereign Control:** Eliminate cloud dependency for agent orchestration and memory.
- **Cost Reduction:** Reduce inference costs by 20% via local Ollama + NCNN.
- **Compliance:** Meet SOC 2-aligned controls for audit, consent, and data isolation.
- **Operational Efficiency:** Single-pane HUD for missions, approvals, receipts, and graph topology.

## 2. Stakeholder Requirements

| Stakeholder | Requirement | Priority |
|-------------|-------------|----------|
| CTO | Bare-metal deployment on InterServer VPS. | High |
| CISO | Tenant RLS, receipt-chain integrity, consent registry. | High |
| VP Engineering | HTMX/WebGPU HUD with real-time vitals and approvals. | High |
| ML Lead | Hermes Agent integration without authority escalation. | Medium |
| SRE Lead | cgroup v2 enforcement, OOMPolicy=stop for critical services. | High |

## 3. Success Metrics

- **Deployment Time:** <2 hours from VPS provision to HUD access.
- **Audit Readiness:** Receipt export passes hash-chain verification.
- **Telephony Compliance:** 100% of SMS/calls have consent registry entries.
- **Model Cost:** 20% reduction vs. cloud-only inference.
