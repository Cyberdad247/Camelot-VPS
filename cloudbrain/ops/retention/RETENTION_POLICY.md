# Mesh Handoff Broker — Stream Retention Policy

**Status:** Proposed defaults (staging) — pending approval before production deployment.
**Applies to:** Redis Streams on the Hermes VPS cloudbrain stack — mesh handoff broker (`127.0.0.1:6379`).
**Defect addressed:** No stream retention/trimming policy exists; streams grow unbounded.
**Date:** 2026-09-22

## 1. Rationale

The mesh broker (`/opt/data/cloudbrain/handoff/mesh_broker.py`) and Anya Omega
route handoffs through Redis Streams (`mesh:handoff:<queue>`, `anya-omega`,
`anya-quarantine`, `anya-deadletter`). Streams are append-only by design: without
an explicit retention bound, every handoff, retry, quarantine verdict, and
dead-letter accumulates forever, consuming Redis memory until the node degrades
or fails. This policy sets bounded, auditable retention per stream class so that
growth is predictable while forensic evidence and in-flight work are never
silently lost.

## 2. Scope

**In scope:**

| Stream pattern | Class | Content |
|---|---|---|
| `mesh:handoff:<knight>` | live | Per-knight handoff queues (drained by broker consumers) |
| `anya-omega` | live | Anya Omega ingress queue (drained by the ingress loop) |
| `mesh:retry:*` | retry | Retry buffer for redelivery (if/when introduced) |
| `anya-quarantine` | evidence | Quarantined policy-violating handoffs (authority verbs, unknown knights) |
| `anya-deadletter` | evidence | Dead-lettered / undeliverable handoffs |

**Out of scope (do not trim with this policy):**
- `/opt/data/cloudbrain/data/anya-omega/handoffs.log` — the durable audit trail.
  It is append-only; rotation/archival is owned by the backup task (CB-051), not
  stream retention.
- Redis idempotency keys / replay-window records — TTL-governed under V-LIFE-002.
- Qdrant / SurrealDB / Open Notebook data — covered by the broader retention
  schedule (CB-050).

## 3. Stream classes and bounds (proposed defaults)

| Class | Streams | `MAXLEN` target | Retention character |
|---|---|---|---|
| live | `mesh:handoff:*`, `anya-omega` | **5,000** | Short: keep headroom for consumer lag, trim hot |
| retry | `mesh:retry:*` | **2,000** | Short: bounded redelivery buffer |
| evidence | `anya-quarantine`, `anya-deadletter` | **20,000** | Long: forensic evidence, export-before-trim |

All targets are **proposed defaults** with tuning guidance in §9. The authoritative
values live as constants in `apply_retention.py` (single source of truth); this
document and that script must agree.

## 4. Sizing justification

- **Live (5,000):** The broker's ingress and per-knight consumers drain queues on
  the order of seconds-to-minutes (watchdog crons run every minute). Entries are
  small typed packets (symbollect-compressed, ~hundreds of bytes each). 5,000
  entries therefore represent many hours of legitimate backlog — far beyond the
  expected consumer lag — while bounding worst-case memory to ~5–10 MiB per
  stream. Trims only bite when a consumer has stalled far past normal lag.
- **Retry (2,000):** A bounded redelivery buffer. If retries exceed this, the
  backlog is a systemic failure, not a transient spike; dead-lettering (not
  unbounded retry) is the correct response.
- **Evidence (20,000):** Quarantine verdicts and dead letters are forensic
  evidence (authority-verb attempts, unknown knights, undeliverable handoffs).
  At expected rates this is weeks of evidence retained for audit, while still
  capping memory. Trims require prior export (§5).

**Memory budget sanity check:** 5,000 × ~2 KiB ≈ 10 MiB per live stream;
20,000 × ~2 KiB ≈ 40 MiB per evidence stream. Total across a handful of knight
queues is well under 256 MiB worst case — safe for the VPS Redis footprint.

## 5. Export-before-trim rule (evidence streams)

**Audit evidence must be exported to the durable audit store BEFORE any trim of
quarantine/dead-letter streams.**

- The exporter appends quarantine/dead-letter entries to
  `/opt/data/cloudbrain/data/anya-omega/handoffs.log` (or the durable audit
  store) and writes a watermark file:
  `/opt/data/cloudbrain/data/anya-omega/export.watermark` — JSON of the form
  `{"anya-quarantine": "<last-exported-id>", "anya-deadletter": "<last-exported-id>", "exported_at": "<iso>"}`.
- `apply_retention.py` trims an evidence-class stream **only if**:
  1. the watermark file exists, is fresh (mtime < 24 h), and covers that stream,
     **and**
  2. the operator passes `--allow-evidence-trim` (explicit opt-in per cron run).
- Otherwise the script skips evidence trimming and records the skip in its JSON
  report (`evidence_watermark` + per-stream `note`). Skips are fail-closed: the
  stream keeps growing, loudly, until the exporter is deployed — this is
  preferable to silent evidence loss.
- Legal-hold behavior (CB-050): if a legal hold is placed on a stream's
  evidence, the exporter must stop updating the watermark for that stream and
  the trimmer consequently holds the data indefinitely.

## 6. Deletion / retention interplay

Trims must never silently drop unacknowledged messages required by policy:

1. **PEL protection:** Before any `XTRIM`, the script queries
   `XPENDING <stream> mesh-brokers` and sets the effective trim bound to
   `max(configured MAXLEN, pending count)`. Pending (claimed, unacked) entries
   are the oldest in delivery order, so retaining the last `effective` entries
   preserves every PEL entry. If pending ≥ configured MAXLEN, the stream is
   **not trimmed** this pass and is flagged for operator attention.
2. **No silent loss of required work:** A trim that would discard entries still
   needed by policy (pending handoffs, unexported evidence) is skipped and
   reported, never forced. The report's `alerts` array names the stream and the
   reason.
3. **Fail-closed quarantine:** Policy-violating handoffs (`authorize`, `grant`,
   `promote`, `revoke`, `sign`, `approve`, `mint`) live in `anya-quarantine`
   until exported; retention never deletes them early to "clean up" violations.
4. **Acknowledgment is the only release:** Retention removes *consumed,
   acknowledged, exported* history — it is not a substitute for acking.

## 7. Alert thresholds

Evaluated per stream class (evidence streams: `MAXLEN` = 20,000; live: 5,000).

| Condition | Warning | Critical | Notes |
|---|---|---|---|
| Stream length > % of MAXLEN | **80%** | **95%** | `apply_retention.py` flags >80% in its report `alerts` |
| Oldest pending (PEL) entry age | **> 15 min** | **> 60 min** | Maps to V-CAP-002; report includes `oldest_pending_idle_ms` |
| Dead-letter growth rate | **> 50/min** sustained 5 min | **> 200/min** sustained 5 min | Watch for systemic routing failures |
| Quarantine growth rate | **> 20/min** sustained 5 min | **> 100/min** sustained 5 min | Watch for attack or misconfigured knight |
| Evidence trim skipped (no fresh watermark) | **warn every run** | — | Deploy the exporter (see §12) |

Pending-age and growth-rate alerts are evaluated by the monitoring layer
(ntfy health checks / consumer of the JSON report); the retention script
emits the raw facts (`len_before`, `pending`, `oldest_pending_idle_ms`,
`over_80pct`).

## 8. Enforcement

`apply_retention.py` (same directory) is the enforcement tool:

- **Stdlib-only**, no DNS, only loopback `127.0.0.1:6379` — safe under the
  no-agent cron pattern (upload < 512 KiB to `/opt/data/scripts/`, create a
  no-agent cron job, trigger, read `/opt/data/cron/output/{id}/`).
- **Idempotent:** repeated runs converge; already-bounded streams are no-ops.
- **Discovers** streams via `SCAN MATCH mesh:handoff:*` plus the known special
  streams (`anya-omega`, `anya-quarantine`, `anya-deadletter`); classifies each
  and applies `XTRIM MAXLEN ~ <bound>` with the PEL guard from §6.
- **Reports** JSON to stdout: per-stream
  `{stream, class, maxlen_configured, len_before, len_after, trimmed, pending,
  oldest_pending_idle_ms, effective_maxlen, over_80pct, note}` plus an `alerts`
  array and evidence-watermark status.
- **DRY_RUN:** `apply_retention.py --dry-run` computes everything, trims nothing.

## 9. Tuning guidance

- **Raise** a bound when legitimate, non-stalled backlog repeatedly exceeds it
  (check `pending` and `oldest_pending_idle_ms` first — a high pending count
  with old idle means a stuck consumer, not an undersized bound).
- **Lower** a bound if Redis memory pressure appears (cross-check with the disk/
  memory high-watermark behavior, V-CAP-003).
- **Live queues per knight:** if knight count grows substantially, consider a
  global budget (sum of live streams) rather than only per-stream bounds.
- **Evidence retention vs. audit needs:** 20,000 is sized for weeks at current
  rates; if compliance requires longer, extend via more frequent export (not
  unbounded streams) — export is cheap, Redis memory is not.
- Change the constants in `apply_retention.py` **and** the table in §3 together;
  record the change and the reason in the goal's hidden run notes.

## 10. Traceability mapping

| Item | How this policy satisfies it |
|---|---|
| **CB-042** — Bound streams, logs, and dead letters | Per-class `MAXLEN` bounds (§3); export-before-trim (§5); growth/pending alerts (§7); `apply_retention.py` evidence = "retention configuration; trim and preservation results" |
| **CB-050** — Define persistence and retention policy | Defines what Redis stream data is disposable (live/retry, short) vs durable (evidence, export-first); legal-hold behavior (§5, §6) |
| **V-CAP-001** — Stream limits | Fill live/retry/quarantine/dead-letter beyond thresholds with consumers controlled; growth must remain bounded, no required unprocessed message silently lost (§11.1) |
| **V-CAP-002** — Pending-age alert | Hold a claimed message past 15-min warn / 60-min critical; alerts fire once, escalate, recover on ack (§11.2) |
| **V-LIFE-001** — Retention enforcement | Age-controlled records per class; run retention; eligible records expire, protected/held records remain, actions audited (§11.3) |

**Adjacent gates (not covered here):** V-CAP-003 (disk high-watermark behavior)
belongs to host monitoring, not stream trimming — cross-reference it when sizing
(§9). V-LIFE-002 (cache TTL / replay window) governs TTL-based records, not
stream `MAXLEN` — separate mechanism, separate evidence.

## 11. Verification procedures

### 11.1 V-CAP-001 — fill test
1. In staging, pause consumers for the target stream (hold, do not kill —
   preserve PEL state).
2. Publish entries beyond the configured threshold (e.g. 6,000 into a live
   stream with `MAXLEN` 5,000; 25,000 into a dead-letter stream — the latter
   requires a fresh export watermark + `--allow-evidence-trim`, else expect a
   skip).
3. Run `apply_retention.py` (first `--dry-run`, then live).
4. **Pass:** `len_after` ≤ effective bound; `trimmed` > 0; `pending` entries all
   intact (`XPENDING` count unchanged); no unacked message lost. Record length
   and memory graphs as evidence.

### 11.2 V-CAP-002 — pending-age alert
1. Claim a message (`XREADGROUP`) and hold it unacked past 15 min (warning),
   then 60 min (critical).
2. **Pass:** warning fires once, critical escalates, and the alert recovers after
   `XACK`. Evidence: alert timeline from the monitoring layer.

### 11.3 V-LIFE-001 — retention enforcement
1. Create age-controlled records for each data class (live, retry, evidence).
2. Run retention processing (`apply_retention.py`).
3. **Pass:** eligible records (acked, exported, past bound) expire; protected or
   held records (pending, unexported evidence, legal hold) remain; every action
   appears in the JSON report (the audit of the retention run itself).
   Evidence: before/after inventory.

## 12. Open items / follow-ups

1. **Exporter with watermark** — the export-before-trim rule (§5) needs the
   quarantine/dead-letter exporter that appends to `handoffs.log` and maintains
   `export.watermark`. Until it exists, evidence trims are skipped by design.
2. **Growth-rate alerting** — dead-letter/quarantine growth-rate thresholds (§7)
   need a monitoring-layer implementation (ntfy health checks or a rate
   sampler).
3. **V-CAP-003** — disk high-watermark behavior and backpressure remain with
   host monitoring; keep stream bounds consistent with its thresholds.
4. **Approval** — this document's defaults are proposed; CB-050 requires an
   approved retention schedule before production rollout.
