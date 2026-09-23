# Off-VPS Copy Design — 3-2-1 for the Tri-Dynamic Cloudbrain Stack

| Field | Value |
|---|---|
| **Status** | PROPOSED — staging design, not installed, not live-tested |
| **Author** | worker OFFSITE (production-hardening swarm) |
| **Forging constraint** | Local only. No network access to 162.35.107.134, no credentials handled, no live testing. Every `__PLACEHOLDER__` in this design is provisioned out-of-band by the owner. |
| **Task mapping** | CB-051 — Automate encrypted backups (evidence for **V-BKP-004**) |
| **Verification touchpoints** | V-BKP-002…V-BKP-004 (CB-051), V-BKP-005…V-BKP-008 (CB-052), V-DEL-005 (backup lifecycle), V-SEC-011 (no secrets in alerts) |
| **Sibling sources** | `cloudbrain/ops/retention/retention-policy.md` (GFS 7/4/12 PROPOSED §2.11; legal hold §1.6; disk watermarks §4); `cloudbrain/docs/runbooks/incident-response-runbook.md` (off-host copies first, V-AUD-004); `cloudbrain/ops/retention/RETENTION_POLICY.md`; blueprint `task.md` / `verification.md` |
| **Companion artifact** | [`cb-offsite-push.sh`](./cb-offsite-push.sh) — bash user-space sketch of the nightly push job (syntax-checked, never executed against the VPS) |

---

## 0. Sandbox constraints this design lives inside

- Debian 13 (trixie), x86_64; user `hermes` (uid/gid 10000); **no sudo**; file ops restricted to `/opt/data`.
- Scripts run as no-agent cron jobs from `/opt/data/scripts/`; outputs land in `/opt/data/cron/output/<job-id>/`.
- Cron jobs have **no outbound DNS/Internet** *except* via Cloudflare DoH (`1.1.1.1`, reachable by IP literal) combined with `curl --resolve <host>:443:<ip>`. This pattern is already proven in production by `cb-ntfy-health.sh`.
- The ~512 KiB cap applies to Hermes `/api/files/upload` and is **irrelevant** here — it does not constrain outbound transfers initiated from cron jobs.
- ~129 GB free under `/opt/data` (figure from the swarm brief; treat as the sizing budget).
- Encrypted backup sets land in `/opt/data/cloudbrain/backups/<UTC-ts>/` (backup worker); encryption keys live in a **separate key file**, never with the payload.
- ntfy.sh alerting already works from cron via the DoH + `--resolve` trick.

---

## 1. The 3-2-1 layout

Three copies of the data, on two media types, one off-site.

| # | Copy | Location / media | Contents | Protects against | Survives full VPS compromise? |
|---|---|---|---|---|---|
| 1 | **Live data** | VPS block storage (`/opt/data`: SurrealDB data dir, Qdrant storage, Redis AOF/RDB, OpenViking files, configs, registry, schemas) | The running system | — (this is the primary, not a backup) | No |
| 2 | **On-VPS encrypted backup sets** | Same VPS disk, separate tree: `/opt/data/cloudbrain/backups/<UTC-ts>/` (SurrealDB export, Qdrant snapshots, Open Notebook data, registry, schemas, configs, audit indexes + audit-log segment digests) | Point-in-time, encrypted at rest, keys in a separate key file | Accidental deletion, corrupt snapshot, bad deploy, operator error | **No** — same host, same credentials. An attacker with the `hermes` user can read and delete these. (Encryption still helps against *partial* compromise — e.g. stolen disk image without the key file.) |
| 3 | **Isolated off-host copy** ⭐ | S3-compatible object storage in a **different provider/account** from the VPS hoster (R2/B2-style generic S3). Ciphertext pushed nightly by the `cb-offsite-push` cron job. | Same encrypted sets as copy 2, plus per-set manifests (chunk hashes, set digest, encryption key **ID** — never key material) | Full VPS compromise, hoster failure, datacenter loss, ransomware on the host | **Yes — by construction** (see §2). This is the V-BKP-004 copy. |

Media types: (a) VPS block storage, (b) cloud object storage. The off-host copy is the **isolated** one.

**Relationship to the audit export (V-AUD-004).** The incident-response runbook already treats off-host copies as "the copy an attacker on the host cannot touch" and checks the off-host *audit export* first during incidents. That export is a fourth, forensic stream — append-only evidence for investigation. It is complementary to, and **not counted as**, the 3-2-1 backup copies: the audit export is for *proving what happened*; copy 3 is for *getting the system back*. Both must exist; neither substitutes for the other.

---

## 2. Threat model — why copy 3 survives full VPS compromise (V-BKP-004)

V-BKP-004's pass criterion: *"Production compromise cannot silently destroy every backup copy; backup access is separately audited."* The verification method is to compromise/disable the production host identity in a controlled scenario and inspect backup accessibility and mutability.

**Assumed attacker:** full `hermes`-user compromise (can read `/opt/data`, all cron scripts, the push credential file, and run jobs), up to and including root on the VPS. The attacker therefore **knows** the offsite push credential and the bucket name.

**What the attacker can do:** read the credential, push garbage objects, stop the cron jobs, delete copies 1 and 2.

**What the attacker cannot do — the five controls:**

1. **Write-only scoped credential.** The S3 key the VPS holds allows only `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, and multipart-session actions on the backup bucket/prefix. It explicitly **denies** `s3:DeleteObject`, `s3:DeleteObjectVersion`, `s3:PutBucketLifecycle*`, `s3:PutBucketPolicy`, `s3:PutObjectLockConfiguration`, and all IAM actions. A leaked credential can only *add* objects — it cannot delete, overwrite-protect-bypass, shorten retention, or mint new credentials. The policy is attached out-of-band by the owner; the VPS never sees the admin credentials.
2. **Object Lock (compliance/governance mode).** Completed backup objects are immutable for the retention window *even against the bucket owner's own root credentials*. Provider note: Backblaze B2 supports S3 Object Lock; Cloudflare R2 does **not** (as of this writing) — if R2 is chosen, immutability rests on control 1 + versioning (control 3) instead. The owner picks the provider with this trade-off in view.
3. **Versioning.** Defense in depth: even a delete (which the push key cannot issue) would only plant a delete marker, not destroy data.
4. **Lifecycle rules are owner-managed, out-of-band.** Retention/expiry rules (§6) are configured with the owner's admin credentials, never from the VPS. The push job tags objects with their GFS tier (`tier=daily|weekly|monthly`); the rules key off those tags.
5. **Separate audit of backup access.** Bucket access logging (or the provider's audit log) ships to a **separate log bucket/prefix the push key cannot write to**. Every access — including the attacker's — is recorded where the attacker cannot tamper with it. This is the "separately audited" half of V-BKP-004.

**Residual risks (stated honestly):**

- **Push starvation.** The attacker can stop future pushes (kill cron, break networking). Copies already offsite remain intact, but RPO starts slipping silently *from the VPS side*. Mitigation: a dead-man's switch on the **offsite side** — the owner configures the bucket/provider (or a tiny external monitor) to alert if no new manifest object appears within 36 h. Until that exists, the VPS-side ntfy health job reports "last successful offsite push age" (see §7). **Open:** dead-man's switch ownership → observability track.
- **Poisoned new objects.** The attacker can push a malicious "backup set." Mitigation: restores are human-gated (CB-052), manifests are digest-chained, and a restore cross-checks the offsite manifest against copy 2 / the backup catalog before touching live data. A poisoned object cannot silently become the restore source.

**What this design does NOT yet prove.** The V-BKP-004 *isolation test report* (controlled compromise simulation: attempt deletes with the push credential, attempt lifecycle edits, verify Object Lock, inspect the separate audit log) is a **live-test artifact** for a later swarm worker. This document supplies the threat-model argument and the test protocol (§8); it is design evidence, not test evidence.

---

## 3. Transfer mechanism inside the cron sandbox

### 3.1 Network path

No DNS resolver, no general egress — but `1.1.1.1` is reachable by IP literal, and `curl --resolve` pins the connection while TLS/SNI still see the real hostname:

```
resolve:  curl --resolve cloudflare-dns.com:443:1.1.1.1 \
              https://cloudflare-dns.com/dns-query?name=<s3-host>&type=A \
              -H 'accept: application/dns-json'        → IPv4
transfer: curl --resolve <s3-host>:443:<ip> \
              --aws-sigv4 "aws:amz:<region>:s3" \
              --user "<key>:<secret>" \
              https://<s3-host>/<bucket>/<key>...
```

SigV4 signing is done natively by curl (`--aws-sigv4`, curl ≥ 7.75; Debian 13 ships 8.x) — no AWS CLI, no SDK, no extra installs in user-space.

### 3.2 Chunking and upload protocol

- The backup set (`/opt/data/cloudbrain/backups/<UTC-ts>/`) is **tar-streamed straight into `split -b 64M`** — no intermediate full-size tar on disk. 64 MiB sits inside the brief's 50–100 MB band, is well above S3's 5 MiB minimum part size, and gives sane retry granularity.
- Each chunk is **sha256-hashed**; hashes go into the set manifest.
- **Primary protocol: S3 multipart upload** (`CreateMultipartUpload` → `UploadPart` × N → `CompleteMultipartUpload`). **Resumable across nights**: the upload-id and completed part numbers persist in the state dir; on restart the job calls `ListParts` and uploads only missing parts. A failed part retries 3× with backoff; the session is deliberately *not* aborted on transient failure so the next night resumes it (orphaned sessions are reaped by the owner's out-of-band `AbortIncompleteMultipartUpload` lifecycle rule).
- **Fallback** (if a chosen backend lacks multipart): client-side chunk PUTs with `Content-Range` per chunk file plus the same manifest. Documented as fallback only; multipart is the default.
- **Auth:** generic S3 SigV4 (R2/B2-style). All credential values are `__PLACEHOLDER__`s in the staged files, provisioned out-of-band into `/opt/data/secrets/offsite/offsite.env` (mode 0600, `hermes`-owned). The sketch refuses to run while any placeholder remains.

### 3.3 The cron job — `cb-offsite-push`

- **Cadence:** nightly (PROPOSED 02:30 UTC — must run *after* the backup worker's window; exact time set once the backup schedule is fixed — open question §10).
- **Concurrency:** `flock` on `/opt/data/cloudbrain/offsite/push.lock`; a second instance exits quietly.
- **Selection:** oldest set newer than the watermark file that carries the backup worker's `.complete` marker (never push a half-written set). On recovery, catch-up is oldest-first, then normal cadence resumes.
- **State** (`/opt/data/cloudbrain/offsite/state/`): `watermark` (last verified set), `consec_failures`, `last_success`, per-set `<set>.upload` (upload-id) and `<set>.etags`.
- **Temp chunks** (`/opt/data/cloudbrain/offsite/chunks/`): pruned on success. The **source backup set is never pruned here** — local GFS pruning belongs to the backup track per the sibling retention policy §2.11.
- **Verify remote manifest:** after `CompleteMultipartUpload`, the job uploads `backups/<set>.manifest.json`, then **GETs it back and compares sha256 digests**, plus a HEAD size sanity check on the object. Watermark advances only on digest match.
- **Failure:** increments the consecutive-failure counter, cleans temp chunks, **retains the source set**, and sends an ntfy alert with escalating priority (night 1–2: `high`; night 3+: `urgent` — "offsite RPO breached"). Recovery after failures sends a `default`-priority recovery notice. Per V-SEC-011, alerts carry set ids, digests, and counts — **never** secrets or key material.
- Full behavior is staged as [`cb-offsite-push.sh`](./cb-offsite-push.sh) (379 lines, `bash -n` clean; header documents every placeholder and security rule).

---

## 4. Alternative path — Tailscale to operator-owned machine/NAS

**Status: option, not dependency.** The admin track owns the Tailscale adoption decision; the S3 design in §3 ships regardless.

If Tailscale is adopted, the preferred transport becomes: VPS joins the tailnet → push to the operator's machine/NAS over WireGuard. Concretely:

- The same `cb-offsite-push` cron job, with the transport layer swapped: `rsync --partial` / `scp`, or better, **restic** to a restic repository on the NAS.
- Advantages: no public object storage and no per-request SigV4; rsync gives byte-level resume for free; restic subsumes chunking, content-defined dedup, and client-side encryption in one tool (its repository format also makes "keys never travel with payloads" trivially auditable).
- What stays the same: watermark/catch-up logic, manifest + digest verification, failure escalation, key separation (§5), GFS retention (§6), and the write-only principle — the NAS-side SSH key would be restricted (e.g. `command="rrsync"` / forced restic-serve, no shell) so a compromised VPS still cannot delete the NAS copies.
- Migration cost is deliberately small: the job's *selection → package → verify → alert* skeleton is transport-agnostic; only the *transfer* step changes.

---

## 5. Key management — backup encryption keys are separately controlled (V-BKP-003)

V-BKP-003's pass criterion: *"Backup content is encrypted; unauthorized restore fails; keys are not stored with the backup payload."*

- **Envelope encryption.** Each backup set is encrypted under a per-set data-encryption key (DEK), wrapped by a key-encryption key (KEK). The offsite push moves **ciphertext only**.
- **The manifest carries the key ID, never key material.** The push job's config file (`offsite.env`) is a *different file* from the backup key file by construction, and the job never reads the key file — only `<set>/.key-id`.
- **Where the offsite key copy lives.** Off the VPS, under operator control — **owner to name the store** (e.g. a dedicated vault entry in the operator's password manager, "cloudbrain DR" envelope). Explicitly **not** in the S3 bucket, not adjacent to any backup object, not in cron outputs. Recommended: Shamir 2-of-3 split of the KEK among independent holdings so no single loss/compromise loses recoverability.
- **Rotation (PROPOSED, owner approves per CB-050):** new DEK per backup set (automatic if the backup worker does envelope encryption); KEK rotation every **90 days**; retired KEKs are retained until every set they wrap has aged out of retention — otherwise old monthlies become unrestorable while still inside the retention window.
- **Keys never travel with payloads** — enforced three ways: architectural (separate files, separate custody), procedural (the runbook forbids co-locating key copies with backup objects), and in the alerting path (V-SEC-011: no key material in ntfy messages, logs, or incident notes).
- **Verification hook for CB-052:** the restore test must include a negative case — attempt a restore of the offsite copy *without* the authorized key path and confirm it fails. That negative test is the V-BKP-003 evidence for the offsite copy.

---

## 6. Retention for offsite copies (CB-050)

**Single source of truth:** the sibling `cloudbrain/ops/retention/retention-policy.md` §2.11 already proposes **GFS daily 7 / weekly 4 / monthly 12** for backup sets (off-host + local). This design **adopts those numbers unchanged** and defines only the *offsite enforcement*. All thresholds remain **PROPOSED** — owner approval per CB-050 is the exit condition.

- **Offsite enforcement:** bucket lifecycle rules, configured **out-of-band by the owner** (the push credential cannot modify lifecycle — V-BKP-004 control 4). Rules key off the `tier=` object tag the push job sets: `daily` objects expire after 7 days unless promoted; `weekly` after 4 weeks; `monthly` after 12 months. Object Lock retention windows are aligned to the tier so immutability and expiry agree.
- **Tier assignment (PROPOSED convention for the backup worker to confirm):** explicit `<set>/.tier` file wins; otherwise Monday sets → `weekly`, 1st-of-month → `monthly`, else `daily`. Set ids are UTC timestamps, so this is deterministic.
- **Legal-hold override.** Extends the sibling policy's hold rule (§1.6) to the offsite copy: a placed hold (recorded with owner, scope, date, reason; **only the owner lifts it**) freezes expiry — affected offsite objects get an extended Object Lock retention / legal-hold flag (applied out-of-band by the owner via `s3:PutObjectLegalHold`; the push key has no such permission), and the corresponding local sets are pinned against GFS pruning. Holds are written to the audit trail. A hold never silently extends *forever*: each hold carries a review date.
- **Deleted-record rule (V-DEL-005 / V-BKP-008).** Backups are immutable point-in-time captures — a record deleted from live data *legitimately* persists in older sets until those sets age out. That is normal and documented, not a violation. The rule bites at **restore time**, and the restore procedure (CB-052) must include a **deleted-record reconciliation step**: diff the backup's deletion log/tombstones against live state as of the backup timestamp, and re-apply as deleted anything deleted after the backup timestamp (or land the restore in a quarantine namespace for review first). **Silent reactivation of deleted content = V-DEL-005 failure.** Granular recovery (V-BKP-008) additionally requires the recovery to be authorized, audited, and non-overwriting of unrelated data — the offsite manifest's per-chunk digests are the accuracy check.

---

## 7. Failure handling — when the push fails 3 nights in a row

### 7.1 Escalation ladder (per-night behavior)

| Night | Script action | ntfy alert |
|---|---|---|
| 1 | Increment `consec_failures` → 1; keep set + chunks-cleaned; state saved for resume | `high` — "offsite push failed (night 1)" with set id |
| 2 | Counter → 2; same retention | `high` — "offsite push failed (night 2)" |
| 3 | Counter → 3; same retention | **`urgent`** — "offsite push failed (3 CONSECUTIVE nights — offsite RPO breached)" |
| 3+ | Counter keeps incrementing; alert repeats nightly at `urgent` | — |
| Recovery | Watermark advances; counter reset; catch-up oldest-first | `default` — "offsite push recovered after N failed night(s)" |

Additionally, the existing ntfy health job gains a staleness check: alert if `last_success` is older than **36 h** (covers the case where the push cron itself is dead, not just failing).

### 7.2 Local retention buffer sizing — the ~129 GB budget

Failed pushes cause *unpushed* sets to accumulate past their normal GFS expiry. The sibling retention policy is explicit: **backup sets are never trim targets, not even at the critical disk watermark** (§1.3, §4.3) — automation must not delete its way out of this. So the buffer is managed by **early warning + human gate**, sized as follows:

- Let **S** = average backup-set size in GB (unknown until the backup worker records real sizes in the catalog — open question §10).
- Normal local retention holds ~7 daily sets ≈ **7S**.
- Free-space budget: **129 GB**. Reserve a 10 GB safety floor. Backlog headroom ≈ **129 − 7S − 10**.
- PROPOSED observability thresholds: **warn when free < 40 GB**, **critical when free < 20 GB**.
- Worked example: if S = 5 GB → normal retention ≈ 35 GB, headroom ≈ 84 GB ≈ **16 nights** of failed pushes before the warn threshold, ~4 more nights to critical. The 3-night `urgent` alert fires *long* before space pressure — the human intervenes while there is still weeks of runway.
- **At critical, automation still deletes nothing.** The critical alert goes to the owner with a runbook excerpt: (1) verify offsite manifests are current; (2) owner explicitly authorizes pruning of the oldest **already-pushed** sets below the GFS floor if needed; (3) **unpushed sets are never pruned** — if they had to be, that would be data loss, and it requires a conscious owner decision recorded in the audit trail, mirroring the sibling policy's human resume gate (§4).

### 7.3 What does NOT happen on failure

- No retry storm: one attempt per night per set (plus in-run part retries); multipart resume means completed parts are never re-uploaded.
- No silent skipping: the watermark only advances on digest-verified success, so a "successful" run that didn't actually push is impossible by construction.
- No credential or key material in any failure artifact (V-SEC-011).

---

## 8. Verification mapping — design evidence vs live-test evidence

| Item | What this design provides (now) | What still needs a live run (later workers) |
|---|---|---|
| **V-BKP-004** off-host isolation | Threat-model argument (§2): write-only scoped credential, Object Lock, versioning, owner-managed lifecycle, separate audit logging; dead-man's switch design | **Isolation test report**: controlled compromise simulation — attempt `DeleteObject`/lifecycle edits with the push credential (must fail), verify Object Lock retention, inspect the separate audit log |
| **V-BKP-003** encryption & key separation | Ciphertext-only transfer; key-ID-only manifests; separate key file; offsite key-custody + rotation design (§5) | Negative restore test without the authorized key path (must fail) — runs under CB-052 against the offsite copy |
| **V-BKP-002** (backup completeness, CB-051) | Manifest schema covers all CB-051 classes (SurrealDB, Qdrant, Open Notebook, registry, schemas, configs, audit indexes) | Scheduled-job records; backup catalog with per-set sizes |
| V-BKP-005…V-BKP-008 (CB-052) | Manifest digests as the accuracy anchor; deleted-record reconciliation procedure (§6) | Full/granular restore drills from the offsite copy, incl. V-DEL-005 no-silent-reactivation check |
| **V-DEL-005** backup lifecycle | Point-in-time semantics + restore-time reconciliation rule (§6); legal-hold override behavior | Trace-a-deleted-record exercise through retained offsite sets |
| CB-050 retention approval | Adopts sibling GFS 7/4/12 as the offsite schedule; tier-tagging convention; hold mechanics | Owner approval of all PROPOSED thresholds |

---

## 9. Assumptions

1. The backup worker produces self-describing, encrypted sets at `/opt/data/cloudbrain/backups/<UTC-ts>/` with a `.complete` marker and a `.key-id` file (tier file `.tier` optional — else the date-derived convention in §6 applies).
2. Average backup-set size **S** is unknown; §7.2's math is parametric until the backup catalog records real sizes.
3. The chosen S3-compatible provider supports SigV4, multipart upload, versioning, and access logging. Object Lock support is preferred (B2 has it; R2 does not) — the design degrades gracefully to scoped-credential + versioning if the owner picks R2.
4. `curl --aws-sigv4` is available (curl ≥ 7.75; Debian 13 ships 8.x) and the DoH + `--resolve` pattern keeps working from cron (proven by `cb-ntfy-health.sh`).
5. Nightly cadence implies an **RPO of ~24 h** for the offsite copy — flagged for owner acceptance in §10.
6. The dead-man's switch for push starvation (§2) is owned by the observability track or the offsite provider's alerting, not by this design.

---

## 10. Open questions (owner / coordinator decisions)

1. **Provider choice:** R2 vs B2 (or other S3-compatible) — trades Object Lock (B2) against ecosystem fit. Owner decides; the design supports either.
2. **Approve all PROPOSED thresholds** — GFS 7/4/12, KEK 90-day rotation, 02:30 UTC push time, warn < 40 GB / critical < 20 GB free (CB-050 exit condition, shared with the sibling retention policy).
3. **RPO acceptance:** is a ~24 h offsite RPO acceptable, or is a more frequent push (e.g. twice daily) required?
4. **Offsite key custody:** name the operator-controlled store for the KEK/DEK copies (and whether Shamir 2-of-3 is wanted). This blocks the V-BKP-003 negative-test evidence.
5. **Tailscale decision** (admin track): if adopted, the transport layer of `cb-offsite-push` is swapped per §4 — confirm before the deployment worker invests in SigV4 hardening.
6. **Backup catalog sizes:** the backup worker must record per-set byte sizes so §7.2's buffer math becomes concrete.
7. **Dead-man's switch ownership:** who/what alerts when *no* manifest appears for 36 h (provider event → owner, or external monitor)?
8. **Legal-hold mechanics:** confirm the out-of-band `PutObjectLegalHold` flow and who besides the owner may *request* a hold.
9. **`.complete` / `.tier` / `.key-id` contract:** backup worker to confirm it will emit these marker files (or propose equivalents).
