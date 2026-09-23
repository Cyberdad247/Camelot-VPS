#!/usr/bin/env bash
#
# cb-trim.sh — cloudbrain retention enforcement SKETCH (ops-security track)
#
# Implements retention-policy.md §§2–4. DRY-RUN BY DEFAULT; nothing is
# deleted, trimmed, or rotated unless --apply is passed.
#
#   ./cb-trim.sh                  # dry-run, JSON summary to stdout
#   ./cb-trim.sh --apply          # perform trims / rotations / prunes
#   ./cb-trim.sh --apply --allow-evidence-trim
#                                 # additionally permit quarantine/dead-letter
#                                 # stream trims (requires fresh export watermark)
#   ./cb-trim.sh --apply --allow-log-purge
#                                 # permit purge of >30d rotated audit segments
#                                 # (requires backup-confirmation marker files)
#
# Hard constraints respected: loopback only (127.0.0.1:6379), no credentials,
# no sudo, file ops under /opt/data. Stdlib-ish: bash + redis-cli + coreutils
# (+ gzip). Redis steps are skipped (loudly) if redis-cli is unavailable —
# the sibling stdlib-only apply_retention.py remains the fallback for streams.
#
# Exit codes: 0 ok · 1 hard error · 2 write-protected (disk critical) or
# operator-attention skips occurred (still safe; see JSON "alerts").
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — every threshold PROPOSED per CB-050 (see retention-policy.md)
# ---------------------------------------------------------------------------
DATA_ROOT="${DATA_ROOT:-/opt/data}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
CONSUMER_GROUP="${CONSUMER_GROUP:-mesh-brokers}"

# Stream bounds (adopted from sibling engineering policy; owner to reconcile)
LIVE_MAXLEN="${LIVE_MAXLEN:-5000}";       LIVE_MINID_DAYS="${LIVE_MINID_DAYS:-7}"
RETRY_MAXLEN="${RETRY_MAXLEN:-2000}";     RETRY_MINID_DAYS="${RETRY_MINID_DAYS:-3}"
QUAR_MAXLEN="${QUAR_MAXLEN:-20000}";      QUAR_MINID_DAYS="${QUAR_MINID_DAYS:-30}"
DEAD_MAXLEN="${DEAD_MAXLEN:-20000}";      DEAD_MINID_DAYS="${DEAD_MINID_DAYS:-90}"

# Audit log
ANYA_LOG="${ANYA_LOG:-/opt/data/cloudbrain/data/anya-omega/handoffs.log}"
ANYA_DIR="$(dirname "$ANYA_LOG")"
ROTATE_SIZE_BYTES="${ROTATE_SIZE_BYTES:-52428800}"   # 50 MiB
ROTATE_MAX_AGE_DAYS="${ROTATE_MAX_AGE_DAYS:-1}"
KEEP_ROTATED_DAYS="${KEEP_ROTATED_DAYS:-30}"
WATERMARK="${WATERMARK:-$ANYA_DIR/export.watermark}"
ROTATION_MANIFEST="${ROTATION_MANIFEST:-$ANYA_DIR/rotation-manifest.log}"
BACKUP_CONFIRM_DIR="${BACKUP_CONFIRM_DIR:-$ANYA_DIR/backup-confirm}"

# Cron outputs
CRON_OUT="${CRON_OUT:-/opt/data/cron/output}"
KEEP_CRON_RUNS="${KEEP_CRON_RUNS:-50}"
KEEP_CRON_DAYS="${KEEP_CRON_DAYS:-7}"

# Redis persistence (probe candidates under /opt/data; skip if not found)
REDIS_DATA_CANDIDATES="${REDIS_DATA_CANDIDATES:-/opt/data/redis /opt/data/cloudbrain/redis}"
KEEP_RDB="${KEEP_RDB:-3}"

# Qdrant snapshots (probe candidates; skip if not found)
QDRANT_DATA_CANDIDATES="${QDRANT_DATA_CANDIDATES:-/opt/data/qdrant /opt/data/cloudbrain/qdrant}"
KEEP_QDRANT_SNAPS="${KEEP_QDRANT_SNAPS:-5}"

# Disk watermarks (observability track owns alerting; we define thresholds)
DISK_WARN_PCT="${DISK_WARN_PCT:-75}"
DISK_CRIT_PCT="${DISK_CRIT_PCT:-90}"

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
APPLY=0; ALLOW_EVIDENCE_TRIM=0; ALLOW_LOG_PURGE=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --allow-evidence-trim) ALLOW_EVIDENCE_TRIM=1 ;;
    --allow-log-purge) ALLOW_LOG_PURGE=1 ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "unknown arg: $a" >&2; exit 1 ;;
  esac
done
MODE="dry-run"; [ "$APPLY" -eq 1 ] && MODE="apply"

# ---------------------------------------------------------------------------
# JSON helpers (no jq dependency)
# ---------------------------------------------------------------------------
jesc() { # JSON-escape a string
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}; s=${s//$'\t'/\\t}; s=${s//$'\r'/\\r}
  printf '"%s"' "$s"
}
ALERTS=()
alert() { ALERTS+=("$1"); }
NEEDS_ATTENTION=0
need_attention() { NEEDS_ATTENTION=1; alert "$1"; }
now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# ---------------------------------------------------------------------------
# 1. Disk high-watermark check — /opt/data
# ---------------------------------------------------------------------------
disk_used_pct=0; disk_state="unknown"
if df --output=pcent,target "$DATA_ROOT" >/dev/null 2>&1; then
  disk_used_pct=$(df --output=pcent "$DATA_ROOT" | tail -1 | tr -dc '0-9')
  disk_state="ok"
  if [ "$disk_used_pct" -ge "$DISK_CRIT_PCT" ]; then
    disk_state="critical"
  elif [ "$disk_used_pct" -ge "$DISK_WARN_PCT" ]; then
    disk_state="warn"
  fi
else
  alert "disk check failed: df could not read $DATA_ROOT"
fi

WRITE_PROTECTED=0
if [ "$disk_state" = "critical" ]; then
  # Emergency write protection: no deletes, no XTRIM, no log truncation.
  WRITE_PROTECTED=1
  need_attention "disk CRITICAL: ${disk_used_pct}% >= ${DISK_CRIT_PCT}% on ${DATA_ROOT} — write-protected mode, report only; pause intake writers, keep consumers draining, never delete durable stores"
elif [ "$disk_state" = "warn" ]; then
  alert "disk WARN: ${disk_used_pct}% >= ${DISK_WARN_PCT}% on ${DATA_ROOT} — recommend cb-trim.sh --apply, ephemeral-first order"
fi

# ---------------------------------------------------------------------------
# 2. Redis streams (MAXLEN + MINID, PEL interlock, evidence gating)
# ---------------------------------------------------------------------------
STREAMS_JSON=""; REDIS_NOTE=""; REDIS_OK=0
rcli() { redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --raw "$@"; }

if ! command -v redis-cli >/dev/null 2>&1; then
  REDIS_NOTE="redis-cli not available — Redis steps skipped; use sibling apply_retention.py (stdlib-only)"
  alert "redis-cli missing: stream trims skipped this pass"
elif ! rcli PING >/dev/null 2>&1; then
  REDIS_NOTE="Redis at ${REDIS_HOST}:${REDIS_PORT} not reachable — Redis steps skipped"
  alert "Redis unreachable at ${REDIS_HOST}:${REDIS_PORT}: stream trims skipped"
else
  REDIS_OK=1
  # Discover streams: per-knight live queues, retry buffers, special queues.
  mapfile -t DISCOVERED < <(
    { rcli --scan --pattern 'mesh:handoff:*' 2>/dev/null;
      rcli --scan --pattern 'mesh:retry:*' 2>/dev/null;
      for k in anya-omega anya-quarantine anya-deadletter; do
        [ "$(rcli EXISTS "$k" 2>/dev/null)" = "1" ] && printf '%s\n' "$k"
      done; } | sort -u
  )

  classify() { # echo "<class> <maxlen> <minid_days>"
    case "$1" in
      anya-quarantine) echo "evidence $QUAR_MAXLEN $QUAR_MINID_DAYS" ;;
      anya-deadletter) echo "evidence $DEAD_MAXLEN $DEAD_MINID_DAYS" ;;
      mesh:retry:*)    echo "retry $RETRY_MAXLEN $RETRY_MINID_DAYS" ;;
      *)               echo "live $LIVE_MAXLEN $LIVE_MINID_DAYS" ;;
    esac
  }

  watermark_ok_for() { # $1 = stream; 0 if fresh watermark covers it
    [ -f "$WATERMARK" ] || return 1
    [ $(( $(date +%s) - $(stat -c %Y "$WATERMARK") )) -lt 86400 ] || return 1
    grep -q "\"$1\"" "$WATERMARK" 2>/dev/null
  }

  for s in "${DISCOVERED[@]:-}"; do
    [ -n "$s" ] || continue
    read -r class maxlen minid_days < <(classify "$s")
    len=$(rcli XLEN "$s" 2>/dev/null || echo 0)
    # --- Safety interlock: never trim unacked consumer-group entries ---
    pending_raw=$(rcli XPENDING "$s" "$CONSUMER_GROUP" 2>/dev/null | head -1 || true)
    if ! [[ "$pending_raw" =~ ^[0-9]+$ ]]; then
      entry_note="XPENDING failed (group '${CONSUMER_GROUP}' missing?) — trim SKIPPED fail-closed"
      STREAMS_JSON+="$(printf '{"stream":%s,"class":%s,"len_before":%s,"skipped":true,"note":%s},' \
        "$(jesc "$s")" "$(jesc "$class")" "$len" "$(jesc "$entry_note")")"
      need_attention "stream ${s}: XPENDING unreadable — trim skipped, investigate consumer group"
      continue
    fi
    pending=$pending_raw
    effective_maxlen=$maxlen
    [ "$pending" -gt "$effective_maxlen" ] && effective_maxlen=$pending

    skipped=false; note=""; trimmed_maxlen=0; trimmed_minid=0
    minid_id="$(( $(date -d "$minid_days days ago" +%s) * 1000 ))-0"

    if [ "$WRITE_PROTECTED" -eq 1 ]; then
      skipped=true; note="write-protected (disk critical) — no trim"
    elif [ "$pending" -ge "$maxlen" ]; then
      skipped=true
      note="PEL guard: pending (${pending}) >= MAXLEN (${maxlen}) — trim skipped, operator attention required"
      need_attention "stream ${s}: pending ${pending} >= MAXLEN ${maxlen} — consumer likely stalled (known Anya ack debt)"
    elif [ "$class" = "evidence" ]; then
      if [ "$ALLOW_EVIDENCE_TRIM" -ne 1 ]; then
        skipped=true; note="evidence stream: --allow-evidence-trim not passed — skipped fail-closed"
        alert "evidence trim skipped for ${s}: missing --allow-evidence-trim"
      elif ! watermark_ok_for "$s"; then
        skipped=true; note="evidence stream: no fresh (<24h) export watermark covering ${s} — skipped fail-closed"
        need_attention "stream ${s}: export-before-trim watermark missing/stale — deploy exporter, data preserved"
      fi
    fi

    if [ "$skipped" = false ] && [ "$APPLY" -eq 1 ]; then
      # Ordering: export (done by exporter beforehand) -> MAXLEN -> MINID.
      trimmed_maxlen=$(rcli XTRIM "$s" MAXLEN "~" "$effective_maxlen" 2>/dev/null || echo 0)
      trimmed_minid=$(rcli XTRIM "$s" MINID "$minid_id" 2>/dev/null || echo 0)
      note="trimmed"
    fi

    len_after=$len
    if [ "$skipped" = false ] && [ "$APPLY" -eq 1 ]; then
      len_after=$(rcli XLEN "$s" 2>/dev/null || echo "$len")
    fi
    would_trim=$(( len > effective_maxlen ? len - effective_maxlen : 0 ))
    over_80=false; [ "$len" -ge $(( maxlen * 80 / 100 )) ] && over_80=true
    [ "$over_80" = true ] && alert "stream ${s} at ${len}/${maxlen} (>=80% of MAXLEN)"

    STREAMS_JSON+="$(printf '{"stream":%s,"class":%s,"maxlen_configured":%s,"minid_days":%s,"minid_id":%s,"len_before":%s,"len_after":%s,"would_trim_maxlen_est":%s,"trimmed_maxlen":%s,"trimmed_minid":%s,"pending":%s,"effective_maxlen":%s,"over_80pct":%s,"skipped":%s,"note":%s},' \
      "$(jesc "$s")" "$(jesc "$class")" "$maxlen" "$minid_days" "$(jesc "$minid_id")" \
      "$len" "$len_after" "$would_trim" "$trimmed_maxlen" "$trimmed_minid" \
      "$pending" "$effective_maxlen" "$over_80" "$skipped" "$(jesc "$note")")"
  done
  STREAMS_JSON="[${STREAMS_JSON%,}]"
fi
[ -z "$STREAMS_JSON" ] && STREAMS_JSON="[]"

# ---------------------------------------------------------------------------
# 3. Anya audit log rotation (size/time) + 30d compressed retention
# ---------------------------------------------------------------------------
audit_json() {
  if [ ! -f "$ANYA_LOG" ]; then
    printf '{"path":%s,"exists":false,"note":%s}' "$(jesc "$ANYA_LOG")" "$(jesc "log not present — nothing to rotate")"
    return
  fi
  local size mtime_age_days rotated="" purged="" note="no rotation needed"
  size=$(stat -c %s "$ANYA_LOG")
  mtime_age_days=$(( ($(date +%s) - $(stat -c %Y "$ANYA_LOG")) / 86400 ))
  local do_rotate=0
  [ "$size" -ge "$ROTATE_SIZE_BYTES" ] && do_rotate=1
  [ "$mtime_age_days" -ge "$ROTATE_MAX_AGE_DAYS" ] && do_rotate=1

  if [ "$do_rotate" -eq 1 ]; then
    local stamp seg
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    seg="${ANYA_LOG}.${stamp}"
    if [ "$WRITE_PROTECTED" -eq 1 ]; then
      note="rotation due (size=${size}, age=${mtime_age_days}d) but write-protected — deferred"
    elif [ "$APPLY" -eq 1 ]; then
      # Prefer logrotate if available AND a config exists; else copy+truncate.
      if command -v logrotate >/dev/null 2>&1 && [ -f /opt/data/cloudbrain/handoff/logrotate.conf ]; then
        logrotate -f /opt/data/cloudbrain/handoff/logrotate.conf
        note="rotated via logrotate"
      else
        cp -p "$ANYA_LOG" "$seg" && : > "$ANYA_LOG"   # copytruncate-style
        gzip -f "$seg"
        seg="${seg}.gz"
        local sha bytes
        sha=$(sha256sum "$seg" | cut -d' ' -f1); bytes=$(stat -c %s "$seg")
        printf '%s ROTATED segment=%s sha256=%s bytes=%s\n' "$(now_iso)" "$(basename "$seg")" "$sha" "$bytes" >> "$ROTATION_MANIFEST"
        note="rotated via copy+truncate (logrotate unavailable); manifest updated"
      fi
      rotated="$seg"
    else
      note="rotation due (size=${size} >= ${ROTATE_SIZE_BYTES} or age=${mtime_age_days}d >= ${ROTATE_MAX_AGE_DAYS}d) — would rotate in --apply"
    fi
  fi

  # Purge rotated segments older than KEEP_ROTATED_DAYS: export-or-purge.
  local purge_note="no purge candidates"
  if [ "$APPLY" -eq 1 ] && [ "$WRITE_PROTECTED" -eq 0 ]; then
    while IFS= read -r old; do
      [ -n "$old" ] || continue
      local base marker
      base=$(basename "$old"); marker="${BACKUP_CONFIRM_DIR}/${base}.confirmed"
      if [ "$ALLOW_LOG_PURGE" -eq 1 ] && [ -f "$marker" ]; then
        local sha bytes
        sha=$(sha256sum "$old" | cut -d' ' -f1); bytes=$(stat -c %s "$old")
        rm -f "$old"
        printf '%s PURGED segment=%s sha256=%s bytes=%s backup_confirmed=yes\n' "$(now_iso)" "$base" "$sha" "$bytes" >> "$ROTATION_MANIFEST"
        purged="${purged}${base} "
      else
        purge_note="purge candidate ${base} held: needs --allow-log-purge + backup confirmation marker"
        alert "$purge_note"
      fi
    done < <(find "$ANYA_DIR" -maxdepth 1 -name "$(basename "$ANYA_LOG").*.gz" -mtime "+$KEEP_ROTATED_DAYS" 2>/dev/null)
  elif [ "$APPLY" -eq 0 ]; then
    local n
    n=$(find "$ANYA_DIR" -maxdepth 1 -name "$(basename "$ANYA_LOG").*.gz" -mtime "+$KEEP_ROTATED_DAYS" 2>/dev/null | wc -l)
    [ "$n" -gt 0 ] && purge_note="$n segment(s) older than ${KEEP_ROTATED_DAYS}d would be export-or-purged in --apply"
  fi

  printf '{"path":%s,"exists":true,"size_bytes":%s,"age_days":%s,"rotated":%s,"purged":%s,"note":%s}' \
    "$(jesc "$ANYA_LOG")" "$size" "$mtime_age_days" "$(jesc "$rotated")" "$(jesc "$purged")" "$(jesc "$note; $purge_note")"
}
AUDIT_JSON=$(audit_json)

# ---------------------------------------------------------------------------
# 4. Cron output pruning — keep last 50 runs per job, and runs < 7 days old
# ---------------------------------------------------------------------------
cron_json() {
  local total_kept=0 total_removed=0 jobs=0 details=""
  if [ ! -d "$CRON_OUT" ]; then
    printf '{"dir":%s,"exists":false,"note":%s}' "$(jesc "$CRON_OUT")" "$(jesc "cron output dir absent — nothing to prune")"
    return
  fi
  for jobdir in "$CRON_OUT"/*/; do
    [ -d "$jobdir" ] || continue
    jobs=$((jobs+1))
    mapfile -t runs < <(find "$jobdir" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null | sort -n | cut -d' ' -f2-)
    local n=${#runs[@]}
    local kept=$n removed=0
    local protected_from=$(( n > KEEP_CRON_RUNS ? n - KEEP_CRON_RUNS : 0 ))
    local i=0
    for r in "${runs[@]}"; do
      if [ "$i" -lt "$protected_from" ]; then
        # Older than the newest KEEP_CRON_RUNS — delete only if also older than KEEP_CRON_DAYS.
        if [ -n "$(find "$r" -maxdepth 0 -mtime "+$KEEP_CRON_DAYS" 2>/dev/null)" ]; then
          if [ "$APPLY" -eq 1 ] && [ "$WRITE_PROTECTED" -eq 0 ]; then rm -rf "$r"; fi
          removed=$((removed+1))
        fi
      fi
      i=$((i+1))
    done
    kept=$((n - removed)); total_kept=$((total_kept+kept)); total_removed=$((total_removed+removed))
    details+="$(printf '{"job":%s,"runs":%s,"kept":%s,"removed":%s},' "$(jesc "$(basename "$jobdir")")" "$n" "$kept" "$removed")"
  done
  printf '{"dir":%s,"jobs":%s,"runs_kept":%s,"runs_removed":%s,"per_job":[%s],"note":%s}' \
    "$(jesc "$CRON_OUT")" "$jobs" "$total_kept" "$total_removed" "${details%,}" \
    "$(jesc "criterion: keep newest ${KEEP_CRON_RUNS} per job AND any run newer than ${KEEP_CRON_DAYS}d")"
}
CRON_JSON=$(cron_json)

# ---------------------------------------------------------------------------
# 5. Redis RDB pruning (keep 3) — AOF is report-only, never touched
# ---------------------------------------------------------------------------
rdb_json() {
  local dir=""
  for c in $REDIS_DATA_CANDIDATES; do [ -d "$c" ] && { dir="$c"; break; }; done
  if [ -z "$dir" ]; then
    printf '{"searched":%s,"note":%s}' "$(jesc "$REDIS_DATA_CANDIDATES")" "$(jesc "no Redis data dir found — RDB pruning skipped")"
    return
  fi
  mapfile -t rdbs < <(find "$dir" -maxdepth 2 -name '*.rdb' -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-)
  local n=${#rdbs[@]} removed=0 removed_list=""
  local i=0
  for r in "${rdbs[@]}"; do
    # Never delete the newest (index 0 = current restore point), keep KEEP_RDB.
    if [ "$i" -ge "$KEEP_RDB" ] && [ "$i" -gt 0 ]; then
      if [ "$APPLY" -eq 1 ] && [ "$WRITE_PROTECTED" -eq 0 ]; then rm -f "$r"; fi
      removed=$((removed+1)); removed_list="${removed_list}$(basename "$r") "
    fi
    i=$((i+1))
  done
  local newest=""; [ "$n" -gt 0 ] && newest=$(basename "${rdbs[0]}")
  printf '{"dir":%s,"found":%s,"keep":%s,"newest_protected":%s,"removed":%s,"removed_list":%s,"note":%s}' \
    "$(jesc "$dir")" "$n" "$KEEP_RDB" "$(jesc "$newest")" "$removed" "$(jesc "$removed_list")" \
    "$(jesc "newest RDB is the restore point and is never deleted")"
}
RDB_JSON=$(rdb_json)

aof_json() {
  local dir=""
  for c in $REDIS_DATA_CANDIDATES; do [ -d "$c" ] && { dir="$c"; break; }; done
  if [ -z "$dir" ]; then
    printf '{"note":%s}' "$(jesc "no Redis data dir found — AOF report skipped")"
    return
  fi
  local count=0 bytes=0
  while IFS= read -r f; do count=$((count+1)); bytes=$((bytes + $(stat -c %s "$f"))); done \
    < <(find "$dir" -maxdepth 3 -name 'appendonly*' 2>/dev/null)
  printf '{"dir":%s,"parts":%s,"bytes":%s,"note":%s}' "$(jesc "$dir")" "$count" "$bytes" \
    "$(jesc "AOF is report-only: never trimmed by retention; BGREWRITEAOF is Redis-internal")"
}
AOF_JSON=$(aof_json)

# ---------------------------------------------------------------------------
# 6. Qdrant snapshots — keep last 5 per collection
# ---------------------------------------------------------------------------
qdrant_json() {
  local dir=""
  for c in $QDRANT_DATA_CANDIDATES; do [ -d "$c" ] && { dir="$c"; break; }; done
  if [ -z "$dir" ]; then
    printf '{"searched":%s,"note":%s}' "$(jesc "$QDRANT_DATA_CANDIDATES")" "$(jesc "no Qdrant data dir found — snapshot pruning skipped")"
    return
  fi
  local details="" total_removed=0
  while IFS= read -r snapdir; do
    [ -n "$snapdir" ] || continue
    # Qdrant layout: <storage>/snapshots/<collection>/*.snapshot.
    # Prune per collection dir; also cover files directly under snapshots/.
    while IFS= read -r colldir; do
      [ -n "$colldir" ] || continue
      mapfile -t snaps < <(find "$colldir" -maxdepth 1 -name '*.snapshot' -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-)
      local n=${#snaps[@]}
      local removed=0 removed_list="" i=0
      for s in "${snaps[@]}"; do
        if [ "$i" -ge "$KEEP_QDRANT_SNAPS" ]; then
          if [ "$APPLY" -eq 1 ] && [ "$WRITE_PROTECTED" -eq 0 ]; then rm -f "$s"; fi
          removed=$((removed+1)); removed_list="${removed_list}$(basename "$s") "
        fi
        i=$((i+1))
      done
      total_removed=$((total_removed+removed))
      details+="$(printf '{"collection_dir":%s,"found":%s,"removed":%s,"removed_list":%s},' \
        "$(jesc "$colldir")" "$n" "$removed" "$(jesc "$removed_list")")"
    done < <({ printf '%s\n' "$snapdir"; find "$snapdir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null; })
  done < <(find "$dir" -type d -name snapshots 2>/dev/null)
  printf '{"dir":%s,"keep_per_collection":%s,"total_removed":%s,"collections":[%s]}' \
    "$(jesc "$dir")" "$KEEP_QDRANT_SNAPS" "$total_removed" "${details%,}"
}
QDRANT_JSON=$(qdrant_json)

# ---------------------------------------------------------------------------
# Final JSON summary
# ---------------------------------------------------------------------------
ALERTS_JSON="["
for a in "${ALERTS[@]:-}"; do ALERTS_JSON+="$(jesc "$a"),"; done
ALERTS_JSON="${ALERTS_JSON%,}]"

cat <<EOF
{"tool":"cb-trim.sh","mode":"$MODE","ts":$(jesc "$(now_iso)"),
"policy":"retention-policy.md (all thresholds PROPOSED, CB-050 approval pending)",
"disk":{"mount":$(jesc "$DATA_ROOT"),"used_pct":$disk_used_pct,"warn_pct":$DISK_WARN_PCT,"critical_pct":$DISK_CRIT_PCT,"state":$(jesc "$disk_state")},
"write_protected":$([ "$WRITE_PROTECTED" -eq 1 ] && echo true || echo false),
"redis":{"reachable":$([ "$REDIS_OK" -eq 1 ] && echo true || echo false),"note":$(jesc "$REDIS_NOTE"),"streams":$STREAMS_JSON},
"audit_log":$AUDIT_JSON,
"cron_outputs":$CRON_JSON,
"redis_rdb":$RDB_JSON,
"redis_aof":$AOF_JSON,
"qdrant_snapshots":$QDRANT_JSON,
"flags":{"allow_evidence_trim":$([ "$ALLOW_EVIDENCE_TRIM" -eq 1 ] && echo true || echo false),"allow_log_purge":$([ "$ALLOW_LOG_PURGE" -eq 1 ] && echo true || echo false)},
"alerts":$ALERTS_JSON,
"needs_operator_attention":$([ "$NEEDS_ATTENTION" -eq 1 ] && echo true || echo false)}
EOF

[ "$NEEDS_ATTENTION" -eq 1 ] || [ "$WRITE_PROTECTED" -eq 1 ] && exit 2
exit 0
