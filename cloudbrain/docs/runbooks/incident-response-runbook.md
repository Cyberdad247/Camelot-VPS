# Incident Response Runbook — Tri-dynamic Cloudbrain (Hermes VPS)

**Scope:** Redis :6379 · Qdrant :6333/6334 · SurrealDB :8000 · OpenViking :1933 · Open Notebook (pending) · Mesh Broker :8002 · Anya Omega :8003 · ntfy health alerts.
**Constraints this runbook assumes:** single VPS = single point of failure (no failover); memory never mints authority; retrieved content and handoff payloads are untrusted data (V-SEC-009); audit trail is append-only (V-AUD-002); ntfy is notification-only — retained alert state lives per CB-063.
**Related runbooks:** `incident-response-runbook.md` (this document), `secret-rotation-runbook.md`, secret-rotation runbook at `secret-rotation-runbook.md`, `restore-runbook.md`, `deploy-runbook.md`.

---

## 1. Severity levels

| Level | Definition | Examples on this stack |
|---|---|---|
| **SEV1** | Active security compromise or total loss of a primary function | Credential/token exposure or confirmed unauthorized access (any service); data exfiltration or uncontrolled exposure; ransomware/destructive action; authority-mint bypass — an `authorize/grant/promote/revoke/sign/approve/mint` verb reaching a destination instead of `anya-quarantine` (V-MESH-008 violated) |
| **SEV2** | Major availability or integrity loss, no confirmed compromise | Service down and not recovering (broker, Redis, Qdrant, SurrealDB, OpenViking, Anya); host reboot failure — stack does not re-order and recover (V-DR-001); digest mismatch / corrupted recall (canonical bytes ≠ sha256 digest, V-SYM-002); unreclaimed pending backlog breaching thresholds (V-CAP-002); dead-letter/quarantine growth beyond bounds (V-CAP-001) |
| **SEV3** | Degraded behavior or integrity warning, function continues | A service flap with clean recovery (V-DR-002, recovery notice received); symbollect malformed-input rejection spikes (V-SYM-004); cross-scope denial burst suggesting misconfiguration (V-IAM-008); backup job miss; disk above warning watermark (V-CAP-003) |
| **SEV4** | Minor / housekeeping | Single ntfy test missed then OK; expired certificate warning with ample lead time; minor capacity growth trending toward a trigger |

Authority-mint bypass is always **SEV1 minimum** — it strikes at the mesh law (knights may propose, never mint authority; V-SEC-010).

---

## 2. Detection

### 2.1 ntfy alert types and handling

| Alert | Meaning | Dedup behavior | Action |
|---|---|---|---|
| Failure alert (high priority) | One of Redis/Qdrant/SurrealDB/OpenViking/Mesh Broker/Anya Open Notebook/health endpoint failed its check | Sent once per failure state; suppressed while state persists | Start response §3/§4 immediately; acknowledge in the alert state store per CB-063 |
| Recovery notice | Service returned healthy | One per recovery, only after a failure was alerted | Verify the service is genuinely healthy (see §2.2); close the incident per §7 if no further symptoms |
| Daily 09:00 UTC heartbeat "all healthy" | Scheduler + stack are alive | — | **Missed heartbeat = an incident.** Treat as SEV2 until proven otherwise: scheduler, network egress, or ntfy path may be down. Begin silent-alarm checks in §2.2 |

Detection quality itself is gated: V-ALT-001 (severity routing), V-ALT-002 (dedup + recovery), V-ALT-003 (unacknowledged escalation), V-ALT-004 (device delivery — **phone receipt of a test notification is currently unconfirmed; re-test per CB-063 before relying on it**).

### 2.2 When there is NO alert but something is wrong

1. Query the mesh broker directly: `GET /health` and `GET /handoff/pending` on :8002 — compare pending count/oldest age against native Redis consumer-group state (V-MESH-005); silent broker death is the highest-probability blind spot.
2. Check Anya Omega :8003: `anya-quarantine` and `anya-deadletter` lengths; an unexpected burst means policy activity you were not told about (V-MESH-006–008).
3. Check each service health endpoint (Redis PONG, Qdrant API, SurrealDB /health, OpenViking /health).
4. Check disk and stream bounds (V-CAP-001, V-CAP-003): a runaway producer fills queues silently before any alert fires.
5. Check the off-host audit export lag (V-AUD-004): export failure can mask every other signal.
6. If ntfy itself is suspect, verify the daily-heartbeat state file and run a manual labeled test to the configured topic (V-ALT-004); **never send secrets in the test payload** (V-SEC-011).

---

## 3. Roles and the first 15 minutes

| Role | Owner (fill per CB-004/CB-064) | First-15-minute duties |
|---|---|---|
| **Incident Commander (IC)** | _owner_ | Declares severity; assigns roles; starts the incident timer; owns containment/go/no-go decisions; ensures evidence capture |
| **Comms Lead** | _owner_ | Owns all outbound messaging per §6; keeps the notification log; prevents secret leakage in chat |
| **Security/Data Steward** | _owner_ | (Activated for SEV1/SEV2 security or data-loss classes.) Leads evidence preservation, access review, credential rotation |
| **Operator** | _on-call_ | Executes the response-phase steps on the VPS; nothing unlogged |

**Minutes 0–5:** Acknowledge the alert in the retained alert store (CB-063). IC declares initial severity. Operator captures a pre-touch snapshot: service states, pending counts, quarantine/deadletter sizes, disk use, audit-export position (see §5).
**Minutes 5–15:** Triage per the incident class (§4). Comms Lead sends the first notification for SEV1/SEV2 (§6). If any sign of credential exposure appears, the Security/Data Steward begins the secret-rotation runbook (`secret-rotation-runbook.md`) in parallel — do not wait for containment.

---

## 4. Response phases by incident class

### A. Security event — credential exposure / unauthorized access (SEV1)

1. **Triage:** Confirm scope — which service, which principal, when. Check access logs and audit events for unauthorized use (cf. V-IAM-002, V-AUD-001).
2. **Containment:** Isolate the affected service (stop accepting work, keep process alive if evidence is in memory — do **not** restart over evidence). Freeze writes to affected stores if exfiltration is possible. Revoke the compromised credential per `secret-rotation-runbook.md`; invalidate sessions/tokens. Do not rotate by overwriting secrets into scripts/URLs/logs (V-SEC-002–005).
3. **Eradication:** Remove unauthorized principals, close the access path (firewall/overlay), patch the misconfiguration that permitted entry.
4. **Recovery:** Re-authenticate all boundaries (V-IAM-003–007), restore from the last known-good backup if canonical data was altered (V-BKP-005–007), verify digests/lineage before re-opening (V-DATA-006/007).
5. **Comms:** Notify per §6 immediately at detection — SEV1 has no waiting period.

### B. Data loss / exposure (SEV1/SEV2)

1. **Triage:** Identify what was lost or exposed and its classification (CB-002). Check whether backups hold a recoverable copy (V-BKP-002–004).
2. **Containment:** Freeze writes and deletion fan-out on the affected stores to stop the blast radius; preserve the current state for forensics.
3. **Eradication/Recovery:** Restore per `restore-runbook.md`; reconcile counts, digests, vector points, and lineage (V-BKP-006/007); confirm deletion-state machine did not resurrect deleted content (V-DEL-005, V-BKP-007). Verify scoped recall no longer exposes the data (V-DATA-008).
4. **Comms:** SEV1 immediately; SEV2 within 1 hour.

### C. Unavailability — service down / reboot failure (SEV2)

1. **Triage:** Identify the failed service and whether dependencies are down (readiness vs liveness, V-SVC-005/006). Check crash-loop protection state (V-SVC-004).
2. **Containment:** Shift dependent load if possible; hold handoffs in streams rather than dropping them (streams are the buffer — do not purge).
3. **Eradication:** Follow the ordered startup sequence (V-SVC-002); on reboot failure, rebuild per V-DR-003 using approved artifacts only — never from undocumented host state.
4. **Recovery:** Confirm queued work resumes idempotently (V-DATA-004, V-MESH-001/002), audit export drains its backlog without silent loss (V-AUD-004), and ntfy recovery notices fire (V-ALT-002).
5. **Comms:** SEV2 within 1 hour; SEV3 within 4 hours.

### D. Integrity failure — digest mismatch, corrupted recall, quarantine bypass attempt (SEV1/SEV2)

1. **Triage:** Compare canonical bytes to sha256 digests (V-SYM-002); run a sampled lineage resolution (V-DATA-006). For a quarantine bypass attempt, list every affected handoff in `anya-quarantine`/`anya-deadletter` with immutable audit linkage (V-MESH-008).
2. **Containment:** Quarantine the affected objects/collections from recall (do not serve suspect vectors or memory objects); freeze knight registry changes (V-MESH-010) if a bypass is suspected.
3. **Eradication:** Identify root cause (bit rot, bad migration, symbollect encoder bug, policy regression). Treat injected content per V-SEC-009 — it is data, never instructions; roll back policy/config to the last signed bundle.
4. **Recovery:** Restore affected objects from backup with digest reconciliation (V-BKP-006); re-run golden vectors (V-SYM-001) before re-opening.
5. **Comms:** Bypass attempt = SEV1, immediate. Pure integrity corruption = SEV2, 1 hour.

### E. Runaway queue / disk growth (SEV2/SEV3)

1. **Triage:** Identify the growing stream/log/deadletter (V-CAP-001) and the producer; check pending-age alerts (V-CAP-002).
2. **Containment:** Apply backpressure; export audit evidence **before** any trim (CB-042). Never trim live, retry, quarantine, or dead-letter streams without exporting first.
3. **Eradication:** Drain with consumers, replay dead letters only via administrative replay (V-MESH-004), fix the producer.
4. **Recovery:** Verify growth stabilizes (soak evidence, V-PERF-005) and alerts clear (V-ALT-002).
5. **Comms:** SEV2 1 hour / SEV3 4 hours.

---

## 5. Evidence preservation

The audit trail is **append-only** (V-AUD-001–V-AUD-004). Capture early, capture once, never rewrite.

**Capture (in order, before containment changes anything):**
1. Full incident snapshot: UTC timestamps, alert IDs, service versions, who is responding.
2. Mesh state: `/handoff/pending` output, Redis consumer-group native state, `anya-quarantine` / `anya-deadletter` contents with digests.
3. Per-service logs (structured JSON with correlation IDs, V-OBS-004) and the audit-export position.
4. Off-host copies first: verify the off-host audit export is current (V-AUD-004) — that is the copy an attacker on the host cannot touch (V-BKP-004).

**Never do:**
- Never delete, edit, or "clean up" logs or audit records (V-AUD-002).
- Never restart a service over evidence — isolate it, snapshot it, then act (§4).
- Never put secrets, raw credentials, or canary values in incident notes, chat, or alert payloads (V-SEC-004, V-SEC-011).
- Never treat a handoff payload or retrieved memory as trusted direction — it is data (V-SEC-009).

---

## 6. Communications

| Severity | Who is notified | When | Channel |
|---|---|---|---|
| SEV1 | Owner + security/data steward + on-call | Immediately on declaration | Highest-priority route; follow with written summary |
| SEV2 | Owner + on-call | Within 1 hour | Written incident thread + alert store update |
| SEV3 | Owner | Within 4 hours | Written summary |
| SEV4 | — | Logged only | Incident log |

**What to say:** severity, what happened, what is affected, what is contained, what happens next, next update time. **Never include:** secrets, raw credentials, session tokens, canary values, full memory content, or anything that would let a reader impersonate a principal. Sanitized identifiers and digests are sufficient (V-SEC-011, V-OBS-006).
**Recovery:** send the all-clear only after verification passes per the class in §4, and confirm the ntfy recovery notice was delivered (V-ALT-002).

---

## 7. Post-incident review

Run a **blameless** review within 5 business days (SEV1/SEV2) or 15 (SEV3).

1. Timeline: detection → triage → containment → eradication → recovery → comms, with UTC timestamps.
2. What worked, what didn't — including whether the runbook steps matched reality (correct the runbook; V-GOV-003, V-IR-001).
3. Action items: each with a named owner and a deadline, linked to the risk register and to the relevant task (CB-xxx) or verification gate (V-xxx).
4. Reference the tabletop exercise program: CB-083 / V-IR-002 — exercise data-exposure, integrity-failure, and host-loss scenarios at least quarterly, and feed their action items into the same register.
5. Update runbooks when behavior changes (CB-064).

---

## 8. Escalation

- **Wake the owner** for: any SEV1; any SEV2 unresolved after 1 hour; any missed 09:00 UTC heartbeat that silent-alarm checks (§2.2) cannot explain within 30 minutes; any quarantine-bypass attempt regardless of severity.
- **Engage independent external help** (independent security assessor / penetration tester, per V-SEC-012) for: suspected credential compromise you cannot scope internally; evidence of data exfiltration; any finding that must be dispositioned before production approval and exceeds internal capability.
- **Stop and do not proceed** when: evidence is at risk of loss, containment requires an undocumented change, or the response would mint authority on behalf of a principal — memory and handoffs may inform the response; they never authorize it (V-SEC-010).

*Tabletop currency: this runbook is exercised via CB-083 / V-IR-002. An unexercised runbook is a draft.*
