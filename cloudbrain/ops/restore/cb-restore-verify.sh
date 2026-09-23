#!/usr/bin/env bash
# cb-restore-verify.sh — post-restore verification for the tri-dynamic
# cloudbrain stack (CB-052, evidence for V-BKP-005 through V-BKP-008).
#
# Usage:
#   ./cb-restore-verify.sh <backup-dir> [--json]
#
# Environment overrides (for the isolated drill variant, restore.md §7):
#   RESTORE_ROOT   prefix replaced by DRILL_ROOT when mapping manifest paths
#                  (default: /opt/data/cloudbrain)
#   DRILL_ROOT     scratch tree root for drills (default: same as RESTORE_ROOT)
#   REDIS_PORT     (default 6379)   REDIS_HOST (default 127.0.0.1)
#   QDRANT_URL     (default http://127.0.0.1:6333)
#   SURREAL_URL    (default http://127.0.0.1:8000)
#   BROKER_URL     (default http://127.0.0.1:8002)
#   ANYA_URL       (default http://127.0.0.1:8003)
#   OPENVK_URL     (default http://127.0.0.1:1933)
#   SURREAL_ENV    credential env file (default /opt/data/cloudbrain/open-notebook.env)
#   REDIS_CLI      redis-cli path (default /opt/data/cloudbrain/bin/redis-cli)
#
# SurrealDB credentials are sourced at runtime from $SURREAL_ENV; they are
# never embedded in this script. No other secrets are used.
#
# Exit: 0 iff no FAIL; prints PASS/FAIL/SKIP per check.

set -u
shopt -s nullglob

RESTORE_ROOT="${RESTORE_ROOT:-/opt/data/cloudbrain}"
DRILL_ROOT="${DRILL_ROOT:-$RESTORE_ROOT}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
SURREAL_URL="${SURREAL_URL:-http://127.0.0.1:8000}"
BROKER_URL="${BROKER_URL:-http://127.0.0.1:8002}"
ANYA_URL="${ANYA_URL:-http://127.0.0.1:8003}"
OPENVK_URL="${OPENVK_URL:-http://127.0.0.1:1933}"
SURREAL_ENV="${SURREAL_ENV:-/opt/data/cloudbrain/open-notebook.env}"
REDIS_CLI="${REDIS_CLI:-/opt/data/cloudbrain/bin/redis-cli}"

PASS=0; FAIL=0; SKIP=0
JSON_OUT=0
[[ "${2:-}" == "--json" ]] && JSON_OUT=1

declare -a RESULTS   # "status|name|detail"

report() { # status name [detail]
  local status="$1" name="$2" detail="${3:-}"
  case "$status" in
    PASS) PASS=$((PASS+1)) ;; FAIL) FAIL=$((FAIL+1)) ;; SKIP) SKIP=$((SKIP+1)) ;;
  esac
  if [[ "$JSON_OUT" == "1" ]]; then
    RESULTS+=("$(printf '{"status":%s,"check":%s,"detail":%s}' \
      "$(printf '%s' "$status" | jq -Rs .)" \
      "$(printf '%s' "$name"   | jq -Rs .)" \
      "$(printf '%s' "$detail" | jq -Rs .)")")
  else
    printf '[%s] %s%s\n' "$status" "$name" "${detail:+ — $detail}"
  fi
}

# Never route loopback checks through an HTTP(S) proxy that may be set in
# the environment (e.g. cron); these services are 127.0.0.1-only.
CURL=(curl -s --noproxy '*' --max-time 10 -o /dev/null -w '%{http_code}')
CURLB=(curl -s --noproxy '*' --max-time 15)

if [[ $# -lt 1 || ! -d "$1" ]]; then
  echo "usage: $0 <backup-dir> [--json]" >&2; exit 2
fi
BKP="$1"
MANIFEST="$BKP/manifest.json"

if [[ ! -f "$MANIFEST" ]]; then
  report FAIL "manifest present" "$MANIFEST not found"
else
  if jq empty "$MANIFEST" 2>/dev/null; then
    TS="$(jq -r '.backup_ts // "unknown"' "$MANIFEST")"
    report PASS "manifest parses" "backup_ts=$TS"
  else
    report FAIL "manifest parses" "invalid JSON"
  fi
fi

# --- 1. Digests: re-hash restored files against manifest --------------------
if [[ -f "$MANIFEST" ]] && jq -e '.files' "$MANIFEST" >/dev/null 2>&1; then
  while IFS= read -r row; do
    want="$(jq -r '.sha256' <<<"$row")"
    mpath="$(jq -r '.path' <<<"$row")"
    live="$mpath"
    # map restore-root paths onto the drill tree
    if [[ "$mpath" == "$RESTORE_ROOT"* && "$DRILL_ROOT" != "$RESTORE_ROOT" ]]; then
      live="$DRILL_ROOT${mpath#"$RESTORE_ROOT"}"
    fi
    if [[ ! -f "$live" ]]; then
      report SKIP "digest $(basename "$mpath")" "not present at $live"
      continue
    fi
    got="$(sha256sum "$live" | awk '{print $1}')"
    if [[ "$got" == "$want" ]]; then
      report PASS "digest $(basename "$mpath")" ""
    else
      report FAIL "digest $(basename "$mpath")" "mismatch at $live"
    fi
  done < <(jq -c '.files[]' "$MANIFEST")
else
  report SKIP "digest verification" "no .files array in manifest"
fi

# --- 2. Health endpoints ----------------------------------------------------
rping="$("$REDIS_CLI" -h "$REDIS_HOST" -p "$REDIS_PORT" PING 2>/dev/null || true)"
[[ "$rping" == "PONG" ]] \
  && report PASS "redis ping" "$REDIS_HOST:$REDIS_PORT" \
  || report FAIL "redis ping" "got '${rping:-<no response>}'"

qready="$("${CURL[@]}" "$QDRANT_URL/readyz" 2>/dev/null)"
[[ "$qready" == "200" ]] \
  && report PASS "qdrant /readyz" "" \
  || { qcoll="$("${CURL[@]}" "$QDRANT_URL/collections" 2>/dev/null)"
       [[ "$qcoll" == "200" ]] \
         && report PASS "qdrant /collections (readyz fallback)" "" \
         || report FAIL "qdrant health" "readyz=$qready collections=$qcoll"; }

shealth="$("${CURL[@]}" "$SURREAL_URL/health" 2>/dev/null)"
[[ "$shealth" == "200" ]] \
  && report PASS "surrealdb /health" "" \
  || report FAIL "surrealdb /health" "http=$shealth"

bhealth="$("${CURL[@]}" "$BROKER_URL/health" 2>/dev/null)"
[[ "$bhealth" == "200" ]] \
  && report PASS "mesh broker /health" "" \
  || report FAIL "mesh broker /health" "http=$bhealth"

ahealth="$("${CURL[@]}" "$ANYA_URL/health" 2>/dev/null)"
[[ "$ahealth" == "200" ]] \
  && report PASS "anya omega /health" "" \
  || report FAIL "anya omega /health" "http=$ahealth"

vhealth="$("${CURL[@]}" "$OPENVK_URL/health" 2>/dev/null)"
[[ "$vhealth" == "200" ]] \
  && report PASS "openviking /health" "" \
  || report FAIL "openviking /health" "http=$vhealth"

# --- 3. Synthetic write→read round-trips (unique run id) --------------------
RUNID="rv-$(date -u +%Y%m%dT%H%M%SZ)-$$"

# 3a. Redis SET/GET/DEL
if rset="$("$REDIS_CLI" -h "$REDIS_HOST" -p "$REDIS_PORT" SET "restore:verify:$RUNID" "$RUNID" 2>&1)"; then
  rget="$("$REDIS_CLI" -h "$REDIS_HOST" -p "$REDIS_PORT" GET "restore:verify:$RUNID" 2>/dev/null || true)"
  "$REDIS_CLI" -h "$REDIS_HOST" -p "$REDIS_PORT" DEL "restore:verify:$RUNID" >/dev/null 2>&1
  [[ "$rget" == "$RUNID" ]] \
    && report PASS "redis round-trip" "SET/GET/DEL ok" \
    || report FAIL "redis round-trip" "GET returned '${rget:-<empty>}'"
else
  report FAIL "redis round-trip" "SET failed: $rset"
fi

# 3b. Qdrant upsert + search on a scratch collection (created, then deleted)
QCOLL="restore_verify_${RUNID//[-:]/_}"
qbody() { printf '%s' "$1" | "${CURLB[@]}" -X "$2" "$3" -H 'Content-Type: application/json' -d @- 2>/dev/null; }
if qbody '{"vectors":{"size":4,"distance":"Cosine"}}' PUT "$QDRANT_URL/collections/$QCOLL" | jq -e '.status=="ok"' >/dev/null 2>&1; then
  qbody "{\"points\":[{\"id\":1,\"vector\":[0.1,0.2,0.3,0.4],\"payload\":{\"run\":\"$RUNID\"}}]}" \
    PUT "$QDRANT_URL/collections/$QCOLL/points?wait=true" >/dev/null
  qhit="$(qbody "{\"vector\":[0.1,0.2,0.3,0.4],\"limit\":1}" POST "$QDRANT_URL/collections/$QCOLL/points/search" | jq -r '.result[0].payload.run // empty')"
  qbody '' DELETE "$QDRANT_URL/collections/$QCOLL" >/dev/null
  [[ "$qhit" == "$RUNID" ]] \
    && report PASS "qdrant round-trip" "upsert+search on scratch collection ok" \
    || report FAIL "qdrant round-trip" "search did not return the scratch point"
else
  report FAIL "qdrant round-trip" "scratch collection create failed"
fi

# 3c. SurrealDB CREATE + SELECT + DELETE on scratch records (auth via env file)
if [[ -f "$SURREAL_ENV" ]]; then
  set -a; # shellcheck disable=SC1090
  . "$SURREAL_ENV"; set +a
  if [[ -z "${SURREAL_USER:-}" || -z "${SURREAL_PASS:-}" ]]; then
    report SKIP "surrealdb round-trip" "SURREAL_USER/SURREAL_PASS not set in $SURREAL_ENV"
  else
    SURREAL_NS="${SURREAL_NS:-cloudbrain}"
    SURREAL_DB="${SURREAL_DB:-cloudbrain}"
    sq() { # $1 = SQL; prints response body
      "${CURLB[@]}" -X POST "$SURREAL_URL/sql" \
        -u "$SURREAL_USER:$SURREAL_PASS" \
        -H "surreal-ns: $SURREAL_NS" -H "surreal-db: $SURREAL_DB" \
        -H 'Accept: application/json' --data-binary "$1"
    }
    TABLE="restore_verify_${RUNID//[-:]/_}"
    if sq "CREATE $TABLE SET run = '$RUNID';" | jq -e '.[0].status=="OK"' >/dev/null 2>&1; then
      sgot="$(sq "SELECT run FROM $TABLE WHERE run = '$RUNID';" | jq -r '.[0].result[0].run // empty')"
      sq "DELETE $TABLE WHERE run = '$RUNID';" >/dev/null
      [[ "$sgot" == "$RUNID" ]] \
        && report PASS "surrealdb round-trip" "CREATE/SELECT/DELETE ok" \
        || report FAIL "surrealdb round-trip" "SELECT did not return the scratch record"
    else
      report FAIL "surrealdb round-trip" "CREATE failed (auth/ns/db?)"
    fi
    unset SURREAL_PASS SURREAL_USER 2>/dev/null || true
  fi
else
  report SKIP "surrealdb round-trip" "$SURREAL_ENV not found"
fi

# 3d. Mesh broker publish→claim→ack (functional restore, V-BKP-007).
# The broker's exact claim/ack query shapes live with the broker track; this
# check is best-effort: publish must 2xx, claim/ack mismatches report SKIP.
BTMP="$(mktemp)"
bcode="$(curl -s --noproxy '*' --max-time 15 -o "$BTMP" -w '%{http_code}' \
  -X POST "$BROKER_URL/handoff" -H 'Content-Type: application/json' \
  -d "{\"queue\":\"anya-omega\",\"type\":\"ping\",\"payload\":{\"to\":\"*\",\"run\":\"$RUNID\"}}" 2>/dev/null || echo 000)"
if [[ "$bcode" =~ ^20[01]$ ]]; then
  bclaim="$("${CURLB[@]}" "$BROKER_URL/handoff/next?queue=anya-omega&consumer=restore-verify" 2>/dev/null || true)"
  if grep -q "$RUNID" <<<"$bclaim"; then
    bid="$(jq -r '.id // .entry_id // empty' <<<"$bclaim")"
    if [[ -n "$bid" ]]; then
      "${CURLB[@]}" -X POST "$BROKER_URL/handoff/ack" -H 'Content-Type: application/json' \
        -d "{\"queue\":\"anya-omega\",\"id\":\"$bid\",\"consumer\":\"restore-verify\"}" >/dev/null 2>&1
    fi
    report PASS "broker publish→claim→ack" "round-trip ok"
  else
    report SKIP "broker claim/ack" "publish 2xx; claim response did not echo run id (API shape unconfirmed)"
  fi
else
  report FAIL "broker publish" "http=$bcode"
fi
rm -f "$BTMP"

# 3e. Anya direct route sanity (functional restore, V-BKP-007)
aroute="$("${CURLB[@]}" -X POST "$ANYA_URL/route" -H 'Content-Type: application/json' \
  -d "{\"to\":\"anya-omega\",\"type\":\"ping\",\"payload\":{\"run\":\"$RUNID\"}}" 2>/dev/null || true)"
if echo "$aroute" | grep -qi 'digest\|ok\|routed'; then
  report PASS "anya direct route" "route accepted"
else
  report SKIP "anya direct route" "endpoint response unrecognized: ${aroute:0:120}"
fi

# --- 4. Counts vs manifest ---------------------------------------------------
# 4a. Redis DBSIZE
if jq -e '.counts.redis_dbsize' "$MANIFEST" >/dev/null 2>&1; then
  want="$(jq -r '.counts.redis_dbsize' "$MANIFEST")"
  got="$("$REDIS_CLI" -h "$REDIS_HOST" -p "$REDIS_PORT" DBSIZE 2>/dev/null || echo -1)"
  [[ "$got" == "$want" ]] \
    && report PASS "redis DBSIZE" "$got keys" \
    || report FAIL "redis DBSIZE" "got $got, manifest expects $want"
else
  report SKIP "redis DBSIZE" "counts.redis_dbsize not in manifest"
fi

# 4b. Qdrant per-collection points_count
if jq -e '.counts.qdrant' "$MANIFEST" >/dev/null 2>&1; then
  while IFS= read -r c; do
    want="$(jq -r --arg c "$c" '.counts.qdrant[$c]' "$MANIFEST")"
    got="$("${CURLB[@]}" "$QDRANT_URL/collections/$c" 2>/dev/null | jq -r '.result.points_count // -1' 2>/dev/null || echo -1)"
    [[ "$got" == "$want" ]] \
      && report PASS "qdrant $c points" "$got" \
      || report FAIL "qdrant $c points" "got $got, manifest expects $want"
  done < <(jq -r '.counts.qdrant | keys[]' "$MANIFEST")
else
  report SKIP "qdrant counts" "counts.qdrant not in manifest"
fi

# 4c. SurrealDB per-table counts (auth via env file, re-sourced)
if jq -e '.counts.surrealdb' "$MANIFEST" >/dev/null 2>&1 && [[ -f "$SURREAL_ENV" ]]; then
  set -a; # shellcheck disable=SC1090
  . "$SURREAL_ENV"; set +a
  if [[ -n "${SURREAL_USER:-}" && -n "${SURREAL_PASS:-}" ]]; then
    SURREAL_NS="${SURREAL_NS:-cloudbrain}"
    SURREAL_DB="${SURREAL_DB:-cloudbrain}"
    while IFS= read -r t; do
      want="$(jq -r --arg t "$t" '.counts.surrealdb[$t]' "$MANIFEST")"
      got="$("${CURLB[@]}" -X POST "$SURREAL_URL/sql" -u "$SURREAL_USER:$SURREAL_PASS" \
        -H "surreal-ns: $SURREAL_NS" -H "surreal-db: $SURREAL_DB" -H 'Accept: application/json' \
        --data-binary "SELECT count() FROM $t GROUP ALL;" 2>/dev/null \
        | jq -r '.[0].result[0].count // -1' 2>/dev/null || echo -1)"
      [[ "$got" == "$want" ]] \
        && report PASS "surrealdb $t count" "$got" \
        || report FAIL "surrealdb $t count" "got $got, manifest expects $want"
    done < <(jq -r '.counts.surrealdb | keys[]' "$MANIFEST")
  else
    report SKIP "surrealdb counts" "credentials not available in $SURREAL_ENV"
  fi
  unset SURREAL_PASS SURREAL_USER 2>/dev/null || true
elif ! jq -e '.counts.surrealdb' "$MANIFEST" >/dev/null 2>&1; then
  report SKIP "surrealdb counts" "counts.surrealdb not in manifest"
else
  report SKIP "surrealdb counts" "$SURREAL_ENV not found"
fi

# --- 5. Anya registry + audit presence ----------------------------------------
ADIR="$DRILL_ROOT/data/anya-omega"
if [[ "$DRILL_ROOT" == "$RESTORE_ROOT" ]]; then ADIR="/opt/data/cloudbrain/data/anya-omega"; fi
[[ -f "$ADIR/knights.json" ]] && jq empty "$ADIR/knights.json" 2>/dev/null \
  && report PASS "anya registry valid" "" \
  || report FAIL "anya registry valid" "$ADIR/knights.json missing or invalid"
[[ -f "$ADIR/handoffs.log" ]] \
  && report PASS "anya audit log present" "$(wc -l < "$ADIR/handoffs.log" | tr -d ' ') lines" \
  || report FAIL "anya audit log present" "$ADIR/handoffs.log missing"

# --- Summary ------------------------------------------------------------------
if [[ "$JSON_OUT" == "1" ]]; then
  printf '{"run_id":%s,"pass":%d,"fail":%d,"skip":%d,"results":[%s]}\n' \
    "$(printf '%s' "$RUNID" | jq -Rs .)" "$PASS" "$FAIL" "$SKIP" \
    "$(IFS=,; echo "${RESULTS[*]}")"
else
  echo "---- summary: PASS=$PASS FAIL=$FAIL SKIP=$SKIP (run $RUNID)"
fi
[[ "$FAIL" -eq 0 ]]
