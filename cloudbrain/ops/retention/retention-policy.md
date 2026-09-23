# Cloudbrain Retention Policy (Ops-Security Track)

**Status:** PROPOSED — requires owner approval before production rollout (CB-050 exit condition).
Every threshold in this document is marked **PROPOSED** and is not in force until approved.
**Scope:** Hermes VPS (`/opt/data`), Redis 8.2.1 streams, Anya Omega audit log,
cron outputs, Redis RDB/AOF, Qdrant snapshots, backup sets.
**Task mapping:** CB-050 (V-LIFE-001, V-LIFE-002), CB-042 (V-CAP-001, V-CAP-002, V-CAP-003).
**Enforcement sketch:** `cb-trim.sh` (same directory; dry-run by default).

---

## 0. Relationship to the engineering sibling policy

The engineering track's `cloudbrain/ops/retention/RETENTION_POLICY.md`
(and its `apply_retention.py`) defines per-class Redis stream bounds:
live `MAXLEN` 5,000 · retry 2,000 · evidence (quarantine/dead-letter) 20,000,
with export-before-trim and PEL guards. **This policy adopts those bounds as the
working proposal.** They refine the coarser "~10,000/stream" starting figure in
the original task brief; the owner must reconcile the two at CB-050 approval —
until then, the sibling's per-class bounds govern.

This document covers what the sibling does **not**: time-based (MINID) trims,
idempotency/cache TTLs, the Anya audit log, cron outputs, RDB/AOF, Qdrant
snapshots, backup sets, disk high-watermark behavior, and the write-protection
interlock. It does not change stream `MAXLEN` bounds or the exporter contract.

---

## 1. Global rules (apply to every data class)

1. **Export durable audit evidence BEFORE trimming transport streams.**
   Quarantine/dead-letter entries must be appended to the durable audit store
   (and the export watermark refreshed) before any trim touches those streams.
   Live/retry streams are transport, not evidence, and may be trimmed without
   export — provided rule 2 holds.
2. **Safety interlock: never trim unacked consumer-group entries.**
   Before any `XTRIM`, read `XPENDING <stream> mesh-brokers`. The effective
   trim bound is `max(configured MAXLEN, pending count)`. If `pending ≥
   configured MAXLEN`, skip the trim for this pass and flag the stream for
   operator attention. Acknowledgment is the only release — retention is not a
   substitute for acking. (Known debt: Anya's ingress loop does not yet ack
   broker messages — owned by the sibling engineering track; this policy
   *respects* it by refusing to trim pending entries rather than "fixing" it.)
3. **Never delete the active/live instance of a durable store as a
   space-recovery measure.** The current RDB, the active AOF set, the
   open `handoffs.log`, the newest Qdrant snapshot, and the latest backup set
   are never trim targets — not even at critical disk watermarks.
4. **Trims are fail-closed.** A skipped trim (no watermark, PEL guard, legal
   hold, missing tooling) keeps the data and reports the skip. Skips are
   louder than trims: they appear in the JSON report's `alerts` array.
5. **Retention runs are audited.** Every enforcement run emits a JSON summary
   (what was inspected, trimmed, skipped, and why). Retain run reports with
   the cron-output class below.
6. **Legal hold** (CB-050): a placed legal hold freezes all trimming of the
   held data class(es) — the exporter stops advancing the watermark for held
   evidence streams, and file-based classes skip purge. Holds are recorded with
   owner, scope, date, and reason; only the owner lifts them.

---

## 2. Retention schedule

All thresholds **PROPOSED** — owner approval required (CB-050).

| # | Data class | What trims when | Mechanism | Notes |
|---|---|---|---|---|
| 2.1 | Redis **live** streams — `mesh:handoff:<knight>`, `anya-omega` | **PROPOSED:** `MAXLEN` 5,000 **and** entries older than 7 days (`MINID`) — the tighter bound wins | `XTRIM` (MAXLEN then MINID) | Per sibling policy. 5,000 ≈ many hours of legitimate backlog; trims bite only on stalled consumers. |
| 2.2 | Redis **retry** streams — `mesh:retry:*` | **PROPOSED:** `MAXLEN` 2,000 **and** entries older than 3 days | `XTRIM` | Bounded redelivery buffer; overflow = systemic failure → dead-letter, not unbounded retry. |
| 2.3 | Redis **quarantine** stream — `anya-quarantine` | **PROPOSED:** `MAXLEN` 20,000 **and** entries older than 30 days — **only after** export to the audit store (fresh watermark < 24 h) **and** explicit `--allow-evidence-trim` | `XTRIM` gated | Policy-violation forensics. Retention never deletes unexported violations to "clean up". |
| 2.4 | Redis **dead-letter** stream — `anya-deadletter` | **PROPOSED:** `MAXLEN` 20,000 **and** entries older than **90 days** — **only after** export (fresh watermark < 24 h) **and** explicit `--allow-evidence-trim` | `XTRIM` gated | Dead letters are audit evidence; 90-day stream floor keeps forensics queryable in Redis while the audit log holds the permanent record. |
| 2.5 | Idempotency / replay-window / cache keys | **PROPOSED:** TTL **48 h**, tied to the replay window | Redis key TTLs (`EXPIRE`/`SET EX`) | V-LIFE-002. Expiry must match policy: no duplicate effects within the replay window. TTLs are the *only* mechanism for this class — never `DEL`-swept. If the replay window changes, TTLs change with it. |
| 2.6 | Anya audit log — `/opt/data/cloudbrain/data/anya-omega/handoffs.log` | **PROPOSED:** rotate at **50 MB** or **daily** (whichever first); keep rotated logs **30 days compressed** (gzip); after 30 days → **export-or-purge**: purge only if the segment is confirmed present in the backup set, otherwise export first; every rotation/purge writes an **audit note** (segment name, sha256, byte count, disposition) to the rotation manifest | logrotate if available, else copy+truncate (`cp` then `: >`) — never move-then-recreate on an actively-appended log | Append-only audit trail; currently unbounded — this is the highest-risk growth item on disk. Compression ~10:1 expected for JSONL. |
| 2.7 | ntfy cron outputs — `/opt/data/cron/output/<job>/` | **PROPOSED:** keep the **last 50 runs per job**, and any run **newer than 7 days** — delete only runs that fail *both* criteria | Directory pruning | Run outputs are the audit trail of retention runs themselves; the dual criterion protects low-frequency jobs. |
| 2.8 | Redis RDB snapshots | **PROPOSED:** keep the **3 most recent** RDB files; never delete the newest (current restore point) | File pruning by mtime | AOF is the primary durability mechanism (AOF enabled); RDB is the compact restore point. |
| 2.9 | Redis AOF | **No retention trim.** The active AOF set is never touched by this policy; `BGREWRITEAOF` is Redis-internal. | — | Manually deleting AOF parts corrupts the manifest. Report size only. |
| 2.10 | Qdrant snapshots | **PROPOSED:** keep the **last 5** snapshots per collection | File pruning by mtime | OpenViking holds no durable data — nothing to retain. |
| 2.11 | Backup sets (off-host + local) | **PROPOSED (GFS):** daily **7**, weekly **4**, monthly **12** | Implemented by the backup track (CB-051), not by `cb-trim.sh` | Retention of backups is the backup track's enforcement; this policy states the schedule so CB-051 configures to it. |

### Sizing rationale (why these numbers)

- **Streams:** per sibling justification — live 5,000 × ~2 KiB ≈ 10 MiB/stream;
  evidence 20,000 ≈ 40 MiB/stream; total well under 256 MiB worst case.
  The 7-day MINID on live streams bounds memory even if `MAXLEN` is raised later;
  the 90-day MINID on dead-letter keeps forensics in Redis for a full quarter
  while the exported audit log is the permanent record.
- **handoffs.log:** at current handoff rates the log is the fastest-growing file
  on the host; 50 MB segments keep individual files greppable and
  restorable; 30 days compressed ≈ one incident-investigation window.
- **Cron outputs:** 50 runs covers the 5-minute ntfy job for ~4 hours plus
  headroom; the 7-day floor protects hourly/daily jobs from being pruned to
  nothing.
- **RDB 3 / Qdrant 5:** two spare restore points behind the current one —
  enough to survive one corrupt snapshot without unbounded accumulation.
- **GFS 7/4/12:** ~4 months of daily granularity, a year of monthly anchors;
  standard, cheap, and sufficient for a single-VPS footprint (~129 GB free).

---

## 3. Ordering rule — export before trim

For every enforcement pass, the order is fixed:

1. **Export** evidence streams (quarantine/dead-letter) to the durable audit
   store; refresh `export.watermark`. (Exporter owned by engineering track;
   until it exists, evidence trims are skipped by design — fail-closed.)
2. **Rotate** the audit log (2.6) so new exports land in the current segment.
3. **Trim** transport streams (2.1, 2.2) with the PEL interlock (§1.2).
4. **Trim** evidence streams (2.3, 2.4) — only with fresh watermark +
   `--allow-evidence-trim`.
5. **Prune** files: cron outputs (2.7), RDB (2.8), Qdrant snapshots (2.10).
6. **Report** JSON; alerts fire on any skip or threshold breach.

Rationale: if a run dies halfway, the durable evidence is already safe; the
worst case is untrimmed (loud) transport, never lost evidence.

---

## 4. Disk high-watermark thresholds — `/opt/data`

Alerting itself belongs to the **observability track** — this section defines
the thresholds and the emergency behavior only.

| Level | Threshold (PROPOSED) | Behavior |
|---|---|---|
| **Warn** | **≥ 75%** used | Emit alert fact (`disk_warn`) in the trim report for the observability layer to forward. `cb-trim.sh --apply` is encouraged; trimming order is ephemeral-first: cron outputs → old snapshots → log rotation → stream trims. No writer changes. |
| **Critical** | **≥ 90%** used | **Emergency write protection** (below). `cb-trim.sh` enters write-protected mode: no deletes, no `XTRIM`, no log truncation — report only. |

### Emergency write-protection behavior (critical, ≥ 90%)

1. **Stop writers at the edge:** pause ingestion — the mesh broker's HTTP
   intake (`POST /handoff`) and Anya Omega's ingress claim loop stop accepting
   *new* work (watchdog crons may hold the processes, but intake is gated).
2. **Keep draining:** consumers continue to `XACK` and drain queues — acking
   and draining *reduce* pressure and must not be stopped. `XACK` writes no
   stream entries.
3. **Protect durable stores:** under no circumstance delete the active RDB,
   any AOF part, the open `handoffs.log`, the newest Qdrant snapshot, or any
   backup set as a space-recovery measure. Recovery space comes only from
   already-exported evidence and ephemeral classes (§2).
4. **Human gate:** writes resume only after usage drops below 75% **and**
   explicit owner/operator review. The 90% event and the resume decision are
   both recorded as audit notes.
5. **Redis memory pressure note:** if Redis itself nears its memory limit
   before disk does, the same protection applies in memory terms — stop
   producers, keep consumers, never evict durable keys to make room
   (eviction policy must exclude audit/registry keyspaces).

### V-CAP-003 verification

Simulate warn/critical thresholds in staging (e.g. against a loopback
filesystem or quota): alerts fire early, rotation and backpressure operate,
durable stores avoid uncontrolled corruption. Evidence: disk, service, and
alert traces.

---

## 5. Enforcement

- `cb-trim.sh` (this directory) implements §§2–4 as a **sketch**: dry-run by
  default, `--apply` performs changes, `--allow-evidence-trim` gates evidence
  stream trims, `--json` (default) emits the machine-readable summary.
- It **defers** to the sibling `apply_retention.py` for fine-grained stream
  `MAXLEN` enforcement where both exist; the two must agree on bounds (§0).
- Cron cadence **PROPOSED:** run `cb-trim.sh` (dry-run) hourly for reporting,
  and `--apply` daily at a quiet hour. Evidence trims remain separately gated.
- Destructive and failover behavior is proven in **staging first**
  (per execution rules), then in a scheduled production change window.

---

## 6. Traceability

| Item | Satisfied by |
|---|---|
| CB-042 — Bound streams, logs, and dead letters | §§2.1–2.4 stream bounds + MINID; §3 export-before-trim; §4 growth/disk alerts; `cb-trim.sh` evidence = "retention configuration; trim and preservation results" |
| CB-050 — Define persistence and retention policy | Full schedule §2 (Redis disposable vs durable, vectors/records/logs/audits/dead letters/backups); legal-hold rule §1.6; all thresholds marked PROPOSED for approval |
| V-CAP-001 — Stream limits | §§2.1–2.4; fill test per sibling §11.1 |
| V-CAP-002 — Pending-age alert | PEL interlock §1.2 preserves pending entries; 15-min warn / 60-min critical per sibling §7 (observability track wires the alerts) |
| V-CAP-003 — Disk high-watermark behavior | §4 thresholds + emergency write protection; staging simulation required |
| V-LIFE-001 — Retention enforcement | §2 per-class eligibility; §5 enforcement; before/after inventory as evidence |
| V-LIFE-002 — Cache TTL and replay window | §2.5 TTL=48 h tied to replay window; key-lifecycle trace as evidence |

---

## 7. Open items / owner decisions

1. **Reconcile stream bounds:** brief sketched ~10,000/stream; engineering
   sibling refined to 5,000 live / 2,000 retry / 20,000 evidence. Approve one
   set at CB-050.
2. **Approve every PROPOSED threshold** in §2 and §4 (CB-050 exit condition).
3. **Quarantine/dead-letter exporter** (with watermark) must exist before any
   evidence trim is permitted — currently evidence trims are skipped by design.
4. **AOF growth:** AOF is append-only between rewrites; confirm
   `auto-aof-rewrite-percentage`/`min-size` keep it bounded, or add an AOF
   size alert to the observability track.
5. **Backup track (CB-051)** must implement the GFS 7/4/12 schedule (§2.11)
   and the export-or-purge confirmation for audit-log segments (§2.6).
6. **Observability track** owns: wiring `disk_warn`/critical alerts, PEL-age
   alerts (15/60 min), stream growth-rate alerts, and the human resume gate
   after a critical disk event.
