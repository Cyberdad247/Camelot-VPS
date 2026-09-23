# Decisions checklist — docs/readiness track (manual / procedural)

Adapted from the staging `deploy-steps-docs.md`. These are the steps for this track that require a human decision, approval, or hands-on exercise. Nothing here runs unattended. Ordered by when each must happen.

## Before Wave 0 closes

1. **Assign owners (CB-004).** Name a service owner, security owner, data steward, and on-call route for every component. No owner may be "the agent" — a human approves each line. Evidence: service catalog + RACI (V-GOV-002).
2. **Resolve or time-box decisions D1–D8** (see `runbooks/deploy-runbook.md` — Decision points, D1–D8): Open Notebook resume vs formal descope; admin exposure (private-overlay only vs approved public TLS); secrets platform; availability tier; backup destination; telemetry platform; data policy; service objectives (SLO/RPO/RTO). Unresolved items become time-bounded exceptions, never silent launch blockers.

## Before Wave 1 closes

3. **Approve the secret-rotation runbook** and schedule the first rotation window. Confirm the emergency-compromise flow is understood by whoever holds the Hermes admin role.
4. **Confirm ntfy phone receipt** on the actual subscribed device (V-ALT-004) — a test notification was published before but receipt was never confirmed. No confirmed receipt = alerting is unverified.

## Before Wave 5 closes

5. **Approve all four runbooks** (deploy, secret rotation, restore, incident response) as the operated versions. Version them; further edits go through change control.

## Before Wave 6 closes

6. **Runbook usability exercise (V-GOV-003 / V-IR-001).** An operator who did NOT author the runbooks executes service-failure, rollback, and restore procedures using only the runbooks. Time each exercise; file defects found; revise and re-test.
7. **Incident tabletop (CB-083 / V-IR-002).** Exercise data exposure, corrupted recall, compromised operator identity, and host loss with technical, security, data, and comms owners present. Every gap gets an owner and deadline.
8. **Access certification (V-IAM-009).** Reconcile all human and service identities; remove orphaned, dormant, shared, or excessive access (or formally accept with expiry).
9. **Restore drill sign-off (V-BKP-005–008).** Witness the isolated restore, review the reconciliation report, and sign the restore-test record.
10. **Production readiness review (CB-084).** Review the traceability matrix (V-REL-001), measured SLO/RPO/RTO vs accepted targets (V-REL-002), and rollback preflight (V-REL-003). Record the verdict with the exact words APPROVED, APPROVED WITH EXCEPTIONS, or REJECTED, plus approvers, exceptions with expiry, and next review date.

## Recurring (after launch)

11. **Monthly (Suite C):** credential-age review, restore sampling, alert-delivery check, access-anomaly review.
12. **Quarterly (Suite D):** full isolated restore, DR exercise, access certification, incident tabletop, retention/deletion audit.
13. **Annually (Suite E):** independent penetration test, threat-model review, SLO/RPO/RTO reassessment, full readiness review.

## Queued deploy steps needing VPS access / auth

- Steps 6, 7, 9 require a live stack: they execute against staging (or production in an approved window) and need a fresh Hermes login per session. Queue them in the deploy order; do not run exercises against production without the change record and rollback plan from `runbooks/deploy-runbook.md`.
- Step 4 (ntfy receipt confirmation) needs the operator's phone in hand.
