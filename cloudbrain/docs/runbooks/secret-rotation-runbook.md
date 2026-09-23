# Secret Rotation Runbook — Tri-dynamic Cloudbrain

**Scope:** Four credential classes — Hermes admin password, SurrealDB credential(s), Redis AUTH password, Qdrant API key.
**Applies to:** Single-VPS phase and all environments. Sibling runbooks live in this directory (`cloudbrain/docs/runbooks/`); patch specs and ops tooling live under `cloudbrain/patches/` and `cloudbrain/ops/`. This document covers credential handling only.
**Hard rule:** No secret value — real or example — appears in shell history, process arguments, cron definitions/outputs, logs, chat transcripts, screenshots, or error messages. Values are generated on-VPS and consumed via a protected channel only.

---

## 1. Preparation

### 1.1 Roles

| Role | Responsibility |
|---|---|
| **Rotation lead** | Owns the maintenance window, sequencing, go/no-go decisions, and evidence record. |
| **Security administrator** | Generates and validates credential values on-VPS; reviews auth logs; declares compromise or clean state. |
| **Platform operator** | Executes service-side changes per this runbook under rotation lead direction. |
| **Auditor / witness** | Observes and attests the rotation metadata record; verifies no value leaked. |

The same person must not be rotation lead and sole witness. Emergency rotation (Section 6) may compress roles; it may never skip the witness attestation.

### 1.2 Maintenance window and comms

1. Schedule a maintenance window; notify operators and alert recipients per the escalation matrix. Declare whether the window is **planned** (dual-credential overlap, no downtime) or **emergency** (Section 6).
2. Confirm a rollback path for each credential class before touching any secret: previous-value restore, prior config digest, and a named operator who can execute it.
3. Open a change record with scope, risk, reviewers, and per-credential verification steps; link evidence to it.

### 1.3 New-value generation rules (all classes)

1. Generate the new value **on-VPS only**, in a context the value never leaves in cleartext:
   - Generate inside the service configuration flow or the secrets manager enrollment flow — never on a local command line.
   - Never paste a value into chat, a ticket, a script argument, or a cron job definition.
   - Never echo a value to a file, terminal, log, or cron output. Redirect or suppress output for any command that could render it.
2. The security administrator verifies value quality (length, entropy, uniqueness) by inspecting **attributes** (character count, character-class count) — never by reading the value itself aloud or in writing.
3. Transport of the value happens through exactly one protected path:
   - Written directly into the approved secret manager or service credential store by the generator process; or
   - Entered by the security administrator through an interactive, non-echoing prompt at the time of use, with immediate consumption.
4. Where a value must pass through an operator action (e.g., Hermes password change form), it is set by the security administrator personally, not relayed secondhand.

---

## 2. Rotation order and overlap semantics

**Order (fixed unless the change record justifies otherwise):**

1. Hermes admin password
2. SurrealDB credential(s)
3. Redis AUTH password
4. Qdrant API key

**Rationale:** Hermes is the operator control plane — its compromise blocks everything else. SurrealDB is the canonical durable record — consumers depend on it next. Redis and Qdrant are the data-path stores; rotating them after SurrealDB keeps memory-object lineage intact while transport resumes.

**Overlap semantics:**

- **Dual-credential window** is required for any credential consumed by more than one process or during a reload: the new value is deployed alongside the old, consumers cut over, then the old value is revoked and verified dead (V-SEC-005).
- Redis `requirepass` supports atomic reconfiguration; SurrealDB principal updates can stage a second principal before deleting the first; Qdrant key rotation stages the new key before the old is removed. Where a service cannot hold two valid credentials at once, the change record must declare a **hard cutover**: stop consumers, rotate, restart consumers, verify — within the window, with the rollback path pre-tested.
- No rotation is declared complete while any component still authenticates with the old value.

---

## 3. Per-credential procedures

### 3.1 Hermes admin password

**Preconditions:** private admin access path available; maintenance window open; security administrator present.

1. Security administrator generates the new password on-VPS per Section 1.3.
2. Through the authenticated admin UI/session, set the new password.
3. **Invalidate all prior sessions and tokens:** revoke every existing session, clear any issued tokens, and confirm the active session inventory shows only the new session (V-IAM-002).
4. Confirm the **old password fails everywhere**: login attempts with the old credential on every admin surface (UI, API, any alternate admin route). Each attempt must fail and be audited without the value appearing in the audit record (V-IAM-002).
5. **Review auth logs** for the compromised period: enumerate logins from unexpected sources, failed-login anomalies, and any session the old credential held. Escalate to Section 6 if unauthorized use is found.
6. **Fix `/api/config` plaintext exposure:** query `/api/config` (unauthenticated and with a low-privilege session) and verify no password, token, private key, or reusable secret material appears in the response, in error bodies, or in support/diagnostic outputs (V-SEC-001, V-WEB-002).
7. Re-run Section 1.3 negative checks (process list, history, logs) for this rotation before closing the window.

### 3.2 SurrealDB credential(s)

**Preconditions:** current credential verified working; dual-principal support confirmed or hard-cutover path approved.

1. Security administrator generates the new root/app credential on-VPS per Section 1.3.
2. Create the new principal (or stage the new root credential) **before** removing the old: enroll it in the credential store and apply least-privilege scope per the principal matrix (V-IAM-005).
3. Cut over consumers to the new credential one by one; verify each reports healthy with its scoped identity.
4. **Verify least-privilege principals still work:** each app principal performs its allowed operations and is denied administrative operations, schema changes, and unrelated-tenant access (V-IAM-005).
5. Remove the old principal/credential.
6. Confirm the **old credential fails**: connection attempts with the old credential must be rejected and audited without value exposure.
7. Reconcile the principal inventory: every listed principal has an owner, scope, and last-use; orphaned or dormant principals are removed or documented (V-IAM-009).

### 3.3 Redis AUTH password

**Preconditions:** all consumers identified (Mesh Broker, Anya Omega, workers, watchdogs); consumer config update path tested.

1. Security administrator generates the new password on-VPS per Section 1.3.
2. Apply the new `requirepass` atomically via Redis configuration (no process restart with the value in an argument; no config file committed to source). Confirm the server requires authentication for new connections.
3. During the dual-credential window, update each consumer's stored credential and restart/reload consumers so they authenticate with the new value.
4. **Verify unauthenticated commands fail:** an unauthenticated connection attempting any command (including read-only) is rejected (V-IAM-003).
5. **Verify wrong-identity commands fail:** a connection authenticating as the wrong identity (or with a stale/wrong credential) is rejected, and per-principal permission limits hold (read-only identity cannot write; writers cannot run prohibited administrative commands) (V-IAM-003).
6. Disable or revoke the old password once every consumer has cut over; confirm zero consumers still authenticate with it (check auth-failure logs, not values).
7. Verify stream consumers, consumer groups, and watchdog cron jobs are healthy post-cutover; ntfy health check reports no authentication failures.

### 3.4 Qdrant API key

**Preconditions:** collection access matrix known; scoped identities per consumer confirmed.

1. Security administrator generates the new API key on-VPS per Section 1.3.
2. Stage the new key in the Qdrant configuration alongside the old key (dual-key window); verify the new key is accepted.
3. Cut over each consumer (embedding workers, recall path, admin tools) to the new key.
4. **Verify scoped access per identity (V-IAM-004):** with each service identity, test health, collection read, point write, collection delete, and cross-tenant/cross-scope filters. Only approved operations and scoped collections succeed; cross-scope access fails and produces audit events.
5. Remove the old key; confirm requests presenting the old key fail and are audited.
6. Verify vector retrieval for a synthetic scoped query still returns correct results post-rotation.

---

## 4. Post-rotation verification

Execute for **every** credential class after rotation, in order:

1. **Old material fails:** attempt authentication with the retired value through every surface it once used. All attempts must fail (V-IAM-002, V-IAM-005, V-IAM-003, V-IAM-004). Record outcomes, never values.
2. **New material works:** each legitimate consumer authenticates and performs its scoped operations; end-to-end synthetic write/recall/handoff passes.
3. **Negative secrecy checks (V-SEC-003, V-SEC-004):**
   - Inspect the process list, unit status outputs, environment exposure, and shell history as an unprivileged account: no credential value present.
   - Search logs, traces, metrics, alerts, and cron outputs for the new value: zero hits expected.
   - **Canary technique (V-SEC-004):** during rotation, the security administrator exercises success and failure paths using a one-time canary marker value in a non-sensitive test slot (a value that is *not* a real credential). Afterward, search all telemetry for the canary. Absence of the canary in logs proves the logging path is clean; the real value is never searched by content and never recorded.
4. **Rotation metadata record:** write the rotation event to the audit trail — timestamp (UTC), credential class, operator identities, dual-window start/end, old-value revocation confirmation, verification outcomes, canary search result. **No value, partial value, hash-of-value-in-reversible-form, or screenshot containing a value** (V-SEC-001).
5. **Service health sweep:** Redis PONG, Qdrant API healthy, SurrealDB health endpoint healthy, OpenViking health, broker/Anya Omega routing verified with a synthetic handoff, watchdogs and ntfy checks green.
6. Witness attests the record; rotation lead closes the change record.

---

## 5. Emergency rotation on suspected compromise

Trigger: any indicator of compromise — unauthorized login (cf. the compromised Hermes credential), leaked value, suspicious auth-log entry, or disclosure in chat/log/screenshot.

1. **Contain immediately:** revoke or disable the affected credential class on-VPS. If the Hermes admin password is suspect, kill all sessions first, then rotate; do not wait for a maintenance window.
2. **Session invalidation:** invalidate all sessions, tokens, and issued keys for the affected class; confirm the old material fails everywhere before proceeding (V-IAM-002).
3. **Audit review:** pull authentication and authorization logs for the exposure window; enumerate successful and failed uses of the compromised material; identify source, scope, and actions taken during exposure.
4. **Evidence preservation:** export the relevant audit and log records to the append-only, integrity-protected audit trail and the off-host copy before any remediation overwrites them (V-AUD-001 through V-AUD-004).
5. **Rotate per Section 3**, then execute the full Section 4 verification.
6. **Assess blast radius:** because one compromised credential may imply others (shared host, same generation method), the security administrator decides whether adjacent classes rotate in the same incident. Default to rotating Hermes + all service credentials when the admin plane was exposed.
7. **Post-incident:** record the incident, root cause, containment timeline, evidence IDs, and corrective actions (e.g., remove the leak source, tighten exposure). Link to the incident-response plan; schedule the tabletop follow-up (V-IR-002).

---

## 6. Rotation cadence and credential-age review

1. **Planned rotation cadence:**
   - Hermes admin password: **every 90 days**, plus immediately on personnel change, suspected exposure, or any plain-HTTP credential transmission.
   - SurrealDB credentials: **every 90 days**; app principals **every 180 days** unless the secrets platform supports automatic rotation.
   - Redis AUTH password: **every 180 days**.
   - Qdrant API key: **every 180 days**.
2. **Credential-age review (Suite C, monthly):** reconcile every credential's last-rotation timestamp against the schedule; flag anything past 80% of its interval; produce a signed review (V-IAM-009).
3. **Event-driven rotation** overrides cadence: compromise suspicion, operator departure, exposure in any artifact, or a failed negative-secrecy check.
4. **Exceptions:** any overdue rotation requires a named owner, rationale, compensating control, and expiry — per the gate policy. An exception never waives the secrecy rules.

---

## Verification ID traceability

- V-IAM-002 — Hermes revocation proof; old-password-fails checks (§3.1, §4).
- V-IAM-003 — Redis authorization tests (§3.3, §4).
- V-IAM-004 — Qdrant scoped-access tests (§3.4, §4).
- V-IAM-005 — SurrealDB least-privilege tests (§3.2, §4).
- V-IAM-009 — access certification; credential-age review (§3.2, §6).
- V-SEC-001 — configuration API secrecy; rotation metadata without values (§3.1, §4).
- V-SEC-002 — repository secret scan post-rotation (confirm no value entered source) (§4).
- V-SEC-003 — process/argument/history secrecy (§4).
- V-SEC-004 — log/telemetry secrecy via canary technique (§4).
- V-SEC-005 — rotation workflow without disclosure or uncontrolled downtime (§2, §4).

## Operator pre-flight checklist

- [ ] Change record open; window declared; comms sent; rollback path confirmed.
- [ ] New values generated on-VPS only, never on a command line or in chat.
- [ ] Rotation order: Hermes → SurrealDB → Redis → Qdrant.
- [ ] Dual-credential window active (or hard-cutover approved) per class.
- [ ] Old material fails everywhere; new material works for every consumer.
- [ ] Negative secrecy checks pass (process list, logs, cron outputs, history — zero hits; canary search clean).
- [ ] `/api/config` exposes no secret material (V-SEC-001, V-WEB-002).
- [ ] Auth logs reviewed for unauthorized use.
- [ ] Rotation metadata recorded without values; witness attested.
- [ ] Health sweep green; ntfy checks confirm no auth failures.
