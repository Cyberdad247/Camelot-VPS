#!/usr/bin/env bash
#
# cb-backup.sh — Encrypted backup of the tri-dynamic cloudbrain stack.
#
# Forged for: Hermes VPS (Debian 13, user `hermes`, no sudo, no Docker).
# Runs as a no_agent cron job from /opt/data/scripts/.
#
# What it backs up (see backup-notes.md for the coverage rationale):
#   redis          BGSAVE, then point-in-time copy of appendonlydir + dump.rdb
#   qdrant         per-collection snapshots via REST (collections discovered,
#                  never hardcoded) + per-collection config JSON
#   surrealdb      `surreal export` (.surql), creds sourced from the env file
#   anya           point-in-time copies of knights.json + handoffs.log
#   open-notebook  data dir copy, best-effort (SKIP when the backend never ran)
#   config         non-secret configuration (redis.conf + generated inventory)
#
# Flow: assemble staging dir -> manifest -> tar -> encrypt -> decrypt-verify ->
#       remove plaintext staging -> write final manifest -> prune old sets.
#
# Security rules enforced by this script:
#   * Zero secrets in the script. SurrealDB creds are read at runtime from
#     $SURREAL_ENV_FILE (mode must be owner-only, else we refuse).
#   * The encryption key/passphrase comes ONLY from a key file given as
#     $1 or $CBB_KEY_FILE. It is never defaulted, never copied into the
#     backup tree, and never logged. Refuses to run if the key file lives
#     inside the backup tree or is readable by group/other.
#   * No `set -x` anywhere near credential handling; the password variable is
#     unset immediately after the export.
#   * Any component FAIL -> no encrypted artifact is produced, staging is left
#     for forensics, exit code is non-zero (a partial backup is never marked
#     successful).
#
# Usage:
#   cb-backup.sh /path/to/backup.key
#   CBB_KEY_FILE=/path/to/backup.key cb-backup.sh
#
# Key file formats (auto-detected, or force with CBB_CRYPTO=age|openssl):
#   age      file holds an age IDENTITY (contains "AGE-SECRET-KEY-...").
#            Recipient is derived via `age-keygen -y`. Decrypt-verify works.
#   openssl  file holds a passphrase (single line).
#            Uses `openssl enc -aes-256-cbc -pbkdf2`.
#
# Exit codes: 0 = all components ok/skipped and artifact verified.
#             1 = precondition or component failure (see stderr + summaries).
#
set -euo pipefail

CBB_VERSION="1.0.0"

# --------------------------------------------------------------------------
# Configuration — every path is overridable via environment.
# --------------------------------------------------------------------------
CBB_BASE="${CBB_BASE:-/opt/data/cloudbrain}"
BACKUP_ROOT="${BACKUP_ROOT:-$CBB_BASE/backups}"

REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_CLI="${REDIS_CLI:-$CBB_BASE/bin/redis-cli}"
REDIS_DATA_DIR="${REDIS_DATA_DIR:-$CBB_BASE/data/redis}"
REDIS_CONF="${REDIS_CONF:-$CBB_BASE/redis.conf}"

QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"

SURREAL_URL="${SURREAL_URL:-http://127.0.0.1:8000}"
SURREAL_BIN="${SURREAL_BIN:-$CBB_BASE/bin/surreal}"
SURREAL_ENV_FILE="${SURREAL_ENV_FILE:-$CBB_BASE/open-notebook.env}"
# Variable NAMES inside the env file that hold the DB user/password.
SURREAL_USER_VAR="${SURREAL_USER_VAR:-SURREAL_USER}"
SURREAL_PASS_VAR="${SURREAL_PASS_VAR:-SURREAL_PASS}"
# >>> UNCONFIRMED DEFAULTS: namespace/database names were never confirmed.
# >>> The deploy step MUST export SURREAL_NS / SURREAL_DB with the real values.
if [ -z "${SURREAL_NS+x}" ]; then
    echo "cb-backup: WARN: SURREAL_NS not set; using unconfirmed default 'open_notebook'" >&2
fi
if [ -z "${SURREAL_DB+x}" ]; then
    echo "cb-backup: WARN: SURREAL_DB not set; using unconfirmed default 'open_notebook'" >&2
fi
SURREAL_NS="${SURREAL_NS:-open_notebook}"
SURREAL_DB="${SURREAL_DB:-open_notebook}"

ANYA_DIR="${ANYA_DIR:-$CBB_BASE/data/anya-omega}"
ON_DATA_DIR="${ON_DATA_DIR:-$CBB_BASE/data/open-notebook}"

KEEP_LAST="${KEEP_LAST:-7}"          # encrypted sets retained (prune older)
CBB_CRYPTO="${CBB_CRYPTO:-auto}"     # auto | age | openssl
CURL_TIMEOUT="${CURL_TIMEOUT:-30}"   # seconds for ordinary REST calls
TMPDIR="${TMPDIR:-/tmp}"

# Key file: first argument wins, else env var. Never defaulted.
CBB_KEY_FILE="${1:-${CBB_KEY_FILE:-}}"

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
log() { printf 'cb-backup: %s\n' "$*" >&2; }
die() { log "FATAL: $*"; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

# Refuse to proceed if a secret-bearing file is readable by group/other.
# Returns non-zero on problem; the caller decides whether that is fatal.
require_private() { # $1 = path, $2 = label
    if [ ! -f "$1" ]; then log "FATAL: $2 not found: $1"; return 1; fi
    if [ -n "$(find "$1" -maxdepth 0 -perm /077 -print 2>/dev/null)" ]; then
        log "FATAL: $2 is readable by group/other ($(stat -c %a "$1")); chmod 600 $1"
        return 1
    fi
    return 0
}

json_escape() {
    local s="$1"
    s=${s//\\/\\\\}
    s=${s//\"/\\\"}
    s=${s//$'\n'/\\n}
    s=${s//$'\t'/\\t}
    s=${s//$'\r'/\\r}
    printf '%s' "$s"
}

utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# --------------------------------------------------------------------------
# Run state
# --------------------------------------------------------------------------
BACKUP_ID="cb-$(date -u +%Y%m%dT%H%M%SZ)"
STAGE="$BACKUP_ROOT/$BACKUP_ID"
UTC_START="$(utc_now)"
FILES_JSONL="$TMPDIR/cb-backup-files-$BACKUP_ID.jsonl"
PLAIN_TAR="$TMPDIR/cb-backup-$BACKUP_ID.tar"
VERIFY_TMP="$TMPDIR/cb-backup-verify-$BACKUP_ID.tar"
: > "$FILES_JSONL"

cleanup_tmp() { rm -f "$FILES_JSONL" "$PLAIN_TAR" "$VERIFY_TMP"; }
trap cleanup_tmp EXIT

# Per-component results: status in {ok,fail,skip}, bytes, files, version, detail.
declare -A C_STATUS C_BYTES C_FILES C_VERSION C_DETAIL
for _c in redis qdrant surrealdb anya open-notebook config manifest encrypt prune; do
    C_STATUS[$_c]="skip"; C_BYTES[$_c]=0; C_FILES[$_c]=0
    C_VERSION[$_c]="";     C_DETAIL[$_c]=""
done
FAILURES=0

set_comp() { # $1=name $2=status(ok|fail|skip) $3=detail [$4=version]
    # Byte/file counters are accumulated by record_file(); set_comp only stamps
    # status + detail so a partial component still reports what it managed.
    C_STATUS[$1]="$2"; C_DETAIL[$1]="$3"
    [ "${4:-}" = "" ] || C_VERSION[$1]="$4"
    [ "$2" = "fail" ] && FAILURES=$((FAILURES + 1))
    return 0
}

# Record one staged file into the manifest ledger, accumulating per-component
# byte/file counters (runs in the main shell — never inside a pipeline).
record_file() { # $1=component $2=relpath $3=abspath
    local sum size
    sum=$(sha256sum "$3" | awk '{print $1}')
    size=$(stat -c%s "$3")
    printf '{"component":"%s","path":"%s","sha256":"%s","bytes":%s}\n' \
        "$1" "$(json_escape "$2")" "$sum" "$size" >> "$FILES_JSONL"
    C_BYTES[$1]=$(( ${C_BYTES[$1]:-0} + size ))
    C_FILES[$1]=$(( ${C_FILES[$1]:-0} + 1 ))
}

# Record every regular file under a staged dir (relpaths relative to $STAGE).
record_tree() { # $1=component $2=staged-subdir
    local f rel
    while IFS= read -r f; do
        rel=${f#"$STAGE"/}
        record_file "$1" "$rel" "$f"
    done < <(find "$STAGE/$2" -type f | sort)
}

# --------------------------------------------------------------------------
# Component: Redis — BGSAVE, then point-in-time copy of appendonlydir + dump.rdb
# --------------------------------------------------------------------------
backup_redis() {
    local cli="$REDIS_CLI" t0 t1 info tries out bgsave_out
    [ -x "$cli" ] || { C_DETAIL[redis]="redis-cli not executable: $cli"; return 1; }
    t0=$("$cli" -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE 2>/dev/null) \
        || { C_DETAIL[redis]="LASTSAVE failed; is redis up on $REDIS_HOST:$REDIS_PORT?"; return 1; }
    bgsave_out=$("$cli" -h "$REDIS_HOST" -p "$REDIS_PORT" BGSAVE 2>&1) \
        || { C_DETAIL[redis]="BGSAVE command failed: $bgsave_out"; return 1; }
    case "$bgsave_out" in
        *"Background saving started"*|*"already in progress"*) ;;
        *) C_DETAIL[redis]="unexpected BGSAVE reply: $bgsave_out"; return 1 ;;
    esac
    tries=0
    # Completion rule: rdb_bgsave_in_progress returns to 0 AND the last save
    # status is ok AND LASTSAVE is at least t0.  The ">=" (not ">") matters:
    # a tiny DB can save within the same second, and the BGSAVE reply is only
    # sent after the fork, so in_progress:0 observed afterwards means OUR save
    # finished.  rdb_last_bgsave_status guards against a silently failed save.
    while [ "$tries" -lt 60 ]; do
        info=$("$cli" -h "$REDIS_HOST" -p "$REDIS_PORT" INFO persistence 2>/dev/null || true)
        inprog=$(printf '%s\n' "$info" | sed -n 's/^rdb_bgsave_in_progress://p' | tr -d '\r')
        savestat=$(printf '%s\n' "$info" | sed -n 's/^rdb_last_bgsave_status://p' | tr -d '\r')
        t1=$("$cli" -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE 2>/dev/null || echo 0)
        if [ "${inprog:-1}" = "0" ] && [ "${savestat:-err}" = "ok" ] \
           && [ "${t1:-0}" -ge "${t0:-0}" ]; then
            break
        fi
        if [ "${inprog:-1}" = "0" ] && [ "${savestat:-}" = "err" ]; then
            C_DETAIL[redis]="BGSAVE reported status err; check redis logs"
            return 1
        fi
        tries=$((tries + 1)); sleep 3
    done
    if [ "$tries" -ge 60 ]; then C_DETAIL[redis]="BGSAVE did not complete within 180s"; return 1; fi

    out="$STAGE/redis"; mkdir -p "$out"
    local copied=0
    if [ -d "$REDIS_DATA_DIR/appendonlydir" ]; then
        cp -a "$REDIS_DATA_DIR/appendonlydir" "$out/" || { C_DETAIL[redis]="copy of appendonlydir failed"; return 1; }
        copied=1
    fi
    if [ -f "$REDIS_DATA_DIR/dump.rdb" ]; then
        cp -a "$REDIS_DATA_DIR/dump.rdb" "$out/" || { C_DETAIL[redis]="copy of dump.rdb failed"; return 1; }
        copied=1
    fi
    if [ "$copied" -eq 0 ]; then
        C_DETAIL[redis]="neither appendonlydir nor dump.rdb found in $REDIS_DATA_DIR"
        return 1
    fi
    record_tree redis redis
    C_DETAIL[redis]="bgsave complete (lastsave $t0 -> ${t1:-?}), appendonlydir+dump.rdb copied post-save"
    return 0
}

# --------------------------------------------------------------------------
# Component: Qdrant — discover collections, snapshot each via REST, save config
# --------------------------------------------------------------------------
json_names() { # collections list -> one name per line (stdin JSON)
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys
d=json.load(sys.stdin)
for c in d.get("result",{}).get("collections",[]):
    print(c["name"])'
    else
        grep -oP '"name"[[:space:]]*:[[:space:]]*"\K[^"]+'
    fi
}
json_snapshot_name() { # snapshot-create response -> result.name (stdin JSON)
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys
d=json.load(sys.stdin); print(d["result"]["name"])'
    else
        grep -oP -m1 '"name"[[:space:]]*:[[:space:]]*"\K[^"]+'
    fi
}

backup_qdrant() {
    local cols c resp snap qdir
    qdir="$STAGE/qdrant"; mkdir -p "$qdir"
    cols=$(curl -sS --max-time "$CURL_TIMEOUT" "$QDRANT_URL/collections" 2>/dev/null | json_names) \
        || { C_DETAIL[qdrant]="GET /collections failed; is qdrant up at $QDRANT_URL?"; return 1; }
    if [ -z "$cols" ]; then
        C_DETAIL[qdrant]="0 collections discovered; nothing to snapshot"
        return 0
    fi
    local n=0
    while IFS= read -r c; do
        [ -n "$c" ] || continue
        # Per-collection config JSON doubles as the "schemas" record for V-BKP-002.
        curl -sS --max-time "$CURL_TIMEOUT" -o "$qdir/${c}.config.json" \
            "$QDRANT_URL/collections/$c" 2>/dev/null \
            || { C_DETAIL[qdrant]="config fetch failed for collection '$c'"; return 1; }
        resp=$(curl -sS --max-time 120 -X POST "$QDRANT_URL/collections/$c/snapshots" 2>/dev/null) \
            || { C_DETAIL[qdrant]="snapshot create failed for collection '$c'"; return 1; }
        snap=$(printf '%s' "$resp" | json_snapshot_name) \
            || { C_DETAIL[qdrant]="could not parse snapshot name for '$c': $resp"; return 1; }
        [ -n "$snap" ] || { C_DETAIL[qdrant]="empty snapshot name for '$c': $resp"; return 1; }
        curl -sS --max-time 600 -o "$qdir/${c}__${snap}" \
            "$QDRANT_URL/collections/$c/snapshots/$snap" 2>/dev/null \
            || { C_DETAIL[qdrant]="snapshot download failed for '$c' snapshot '$snap'"; return 1; }
        [ -s "$qdir/${c}__${snap}" ] || { C_DETAIL[qdrant]="snapshot file empty for '$c'"; return 1; }
        n=$((n + 1))
    done < <(printf '%s\n' "$cols")
    record_tree qdrant qdrant
    C_DETAIL[qdrant]="$n collection(s) snapshotted via REST + config JSON saved"
    return 0
}

# --------------------------------------------------------------------------
# Component: SurrealDB — `surreal export`, creds from the env file at runtime
# --------------------------------------------------------------------------
env_get() { # $1 = variable name -> prints its value from $SURREAL_ENV_FILE (may be empty)
    local key="$1" line val
    line=$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$SURREAL_ENV_FILE" 2>/dev/null | tail -n 1)
    [ -n "$line" ] || return 0
    val=${line#*=}
    val=$(printf '%s' "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    case "$val" in
        \"*\") val=${val#\"}; val=${val%\"} ;;
        \'*\') val=${val#\'}; val=${val%\'} ;;
    esac
    printf '%s' "$val"
}

backup_surrealdb() {
    local out user pass rc pwf
    require_private "$SURREAL_ENV_FILE" "surreal env file" \
        || { C_DETAIL[surrealdb]="env file missing or too permissive: $SURREAL_ENV_FILE"; return 1; }
    [ -x "$SURREAL_BIN" ] || { C_DETAIL[surrealdb]="surreal binary not executable: $SURREAL_BIN"; return 1; }
    # Env file wins; direct SURREAL_USER/SURREAL_PASS in the environment are a fallback.
    user=$(env_get "$SURREAL_USER_VAR"); [ -n "$user" ] || user="${SURREAL_USER:-}"
    pass=$(env_get "$SURREAL_PASS_VAR"); [ -n "$pass" ] || pass="${SURREAL_PASS:-}"
    if [ -z "$user" ] || [ -z "$pass" ]; then
        C_DETAIL[surrealdb]="credentials not found (looked for $SURREAL_USER_VAR/$SURREAL_PASS_VAR in $SURREAL_ENV_FILE)"
        return 1
    fi
    out="$STAGE/surrealdb"; mkdir -p "$out"
    # Prefer a password-file mechanism when the installed CLI offers one, so the
    # secret never appears in argv (visible via ps). Fall back to --pass with the
    # documented tradeoff: argv is visible only to local host users (hermes/root)
    # for the duration of the export, and the value is never logged by this script.
    if "$SURREAL_BIN" export --help 2>&1 | grep -qE -- '--pass-file|--password-file'; then
        pwf=$(mktemp "$TMPDIR/cb-pw.XXXXXX"); chmod 600 "$pwf"
        printf '%s' "$pass" > "$pwf"
        "$SURREAL_BIN" export --conn "$SURREAL_URL" --user "$user" --pass-file "$pwf" \
            --ns "$SURREAL_NS" --db "$SURREAL_DB" "$out/export.surql" 2>/dev/null
        rc=$?; rm -f "$pwf"
    else
        "$SURREAL_BIN" export --conn "$SURREAL_URL" --user "$user" --pass "$pass" \
            --ns "$SURREAL_NS" --db "$SURREAL_DB" "$out/export.surql" 2>/dev/null
        rc=$?
    fi
    pass=""; unset pass user   # never retain the secret longer than the export
    if [ "$rc" -ne 0 ] || [ ! -s "$out/export.surql" ]; then
        C_DETAIL[surrealdb]="surreal export failed (rc=$rc); check ns/db names and service health"
        return 1
    fi
    record_tree surrealdb surrealdb
    C_DETAIL[surrealdb]="export.surql written for ns=$SURREAL_NS db=$SURREAL_DB"
    return 0
}

# --------------------------------------------------------------------------
# Component: Anya Omega — registry + append-only audit log (point-in-time copy)
# --------------------------------------------------------------------------
backup_anya() {
    local out="$STAGE/anya"
    [ -f "$ANYA_DIR/knights.json" ] || { C_DETAIL[anya]="registry missing: $ANYA_DIR/knights.json"; return 1; }
    [ -f "$ANYA_DIR/handoffs.log" ] || { C_DETAIL[anya]="audit log missing: $ANYA_DIR/handoffs.log"; return 1; }
    mkdir -p "$out"
    cp -a "$ANYA_DIR/knights.json" "$out/" || { C_DETAIL[anya]="copy of knights.json failed"; return 1; }
    # handoffs.log is append-only; cp captures a prefix-consistent snapshot.
    cp -a "$ANYA_DIR/handoffs.log" "$out/" || { C_DETAIL[anya]="copy of handoffs.log failed"; return 1; }
    record_tree anya anya
    C_DETAIL[anya]="point-in-time copies of knights.json + handoffs.log"
    return 0
}

# --------------------------------------------------------------------------
# Component: Open Notebook — best-effort (backend may never have started)
# --------------------------------------------------------------------------
backup_open_notebook() {
    local out="$STAGE/open-notebook"
    if [ ! -d "$ON_DATA_DIR" ] || [ -z "$(ls -A "$ON_DATA_DIR" 2>/dev/null)" ]; then
        C_DETAIL[open-notebook]="data dir absent or empty ($ON_DATA_DIR); backend not started?"
        return 2   # skip, not a failure
    fi
    mkdir -p "$out"
    cp -a "$ON_DATA_DIR/." "$out/" || { C_DETAIL[open-notebook]="copy of $ON_DATA_DIR failed"; return 1; }
    record_tree open-notebook open-notebook
    C_DETAIL[open-notebook]="data dir copied"
    return 0
}

# --------------------------------------------------------------------------
# Component: non-secret configuration
# --------------------------------------------------------------------------
backup_config() {
    local out="$STAGE/config"
    mkdir -p "$out"
    if [ -f "$REDIS_CONF" ]; then
        cp -a "$REDIS_CONF" "$out/redis.conf" || { C_DETAIL[config]="copy of redis.conf failed"; return 1; }
    fi
    # Explicit allowlist: never sweep *.env / *secret* / *key* into the backup.
    {
        printf '# cb-backup non-secret configuration inventory (%s)\n' "$(utc_now)"
        printf 'script_version=%s\n' "$CBB_VERSION"
        printf 'redis_version=%s\n' "${C_VERSION[redis]}"
        printf 'qdrant_version=%s\n' "${C_VERSION[qdrant]}"
        printf 'surrealdb_version=%s\n' "${C_VERSION[surrealdb]}"
        printf 'redis_conf=%s\n' "$REDIS_CONF"
        printf 'redis_data_dir=%s\n' "$REDIS_DATA_DIR"
        printf 'qdrant_url=%s\n' "$QDRANT_URL"
        printf 'surreal_url=%s\n' "$SURREAL_URL"
        printf 'surreal_ns=%s surreal_db=%s\n' "$SURREAL_NS" "$SURREAL_DB"
        printf 'anya_dir=%s\n' "$ANYA_DIR"
    } > "$out/inventory.txt"
    record_tree config config
    C_DETAIL[config]="redis.conf (if present) + generated non-secret inventory; *.env excluded by policy"
    return 0
}

# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------
ENCRYPT_METHOD=""; ENCRYPT_ARTIFACT=""; ENCRYPT_SHA256=""; ENCRYPT_BYTES=0
PLAINTEXT_REMOVED="false"

write_manifest() { # writes $STAGE/manifest.json from ledger + component state
    local utc_end="$1" mf="$STAGE/manifest.json" c files_json comp_json
    files_json=$(awk 'NR>1{printf ",\n"} {printf "    %s", $0} END{printf "\n"}' "$FILES_JSONL")
    comp_json=""
    for c in redis qdrant surrealdb anya open-notebook config; do
        comp_json="${comp_json}$(printf '    "%s": {"status": "%s", "bytes": %s, "files": %s, "version": "%s", "detail": "%s"},\n' \
            "$c" "${C_STATUS[$c]}" "${C_BYTES[$c]}" "${C_FILES[$c]}" \
            "$(json_escape "${C_VERSION[$c]}")" "$(json_escape "${C_DETAIL[$c]}")")"
    done
    {
        printf '{\n'
        printf '  "backup_id": "%s",\n' "$BACKUP_ID"
        printf '  "script": "cb-backup.sh",\n'
        printf '  "script_version": "%s",\n' "$CBB_VERSION"
        printf '  "utc_start": "%s",\n' "$UTC_START"
        printf '  "utc_end": "%s",\n' "$utc_end"
        printf '  "host": "%s",\n' "$(json_escape "$(hostname 2>/dev/null || echo unknown)")"
        printf '  "components": {\n%s' "$comp_json"
        printf '    "_note": "open-notebook may legitimately report skip until its backend has started"\n'
        printf '  },\n'
        printf '  "files": [\n%s  ],\n' "$files_json"
        if [ -n "$ENCRYPT_METHOD" ]; then
            printf '  "encryption": {"method": "%s", "artifact": "%s", "sha256": "%s", "bytes": %s, "decrypt_verified": true},\n' \
                "$ENCRYPT_METHOD" "$(json_escape "$ENCRYPT_ARTIFACT")" "$ENCRYPT_SHA256" "$ENCRYPT_BYTES"
        else
            printf '  "encryption": null,\n'
        fi
        printf '  "plaintext_staging_removed": %s,\n' "$PLAINTEXT_REMOVED"
        printf '  "overall": "%s"\n' "$([ "$FAILURES" -eq 0 ] && echo ok || echo failed)"
        printf '}\n'
    } > "$mf"
    C_BYTES[manifest]=$(stat -c%s "$mf")
    C_FILES[manifest]=1
    set_comp manifest ok "manifest.json written"
}

# --------------------------------------------------------------------------
# Encryption + decrypt-verify
# --------------------------------------------------------------------------
CRYPTO_MODE=""
detect_crypto() {
    case "$CBB_CRYPTO" in
        age)     need_cmd age; need_cmd age-keygen; CRYPTO_MODE="age" ;;
        openssl) need_cmd openssl; CRYPTO_MODE="openssl" ;;
        auto)
            if grep -q "AGE-SECRET-KEY-" "$CBB_KEY_FILE" 2>/dev/null \
               && command -v age >/dev/null 2>&1 && command -v age-keygen >/dev/null 2>&1; then
                CRYPTO_MODE="age"
            elif command -v openssl >/dev/null 2>&1; then
                CRYPTO_MODE="openssl"
            else
                die "neither age nor openssl is available"
            fi
            ;;
        *) die "CBB_CRYPTO must be auto, age, or openssl (got: $CBB_CRYPTO)" ;;
    esac
}

encrypt_set() {
    local dirs=() d blob recipient plain_sum blob_sum
    for d in redis qdrant surrealdb anya open-notebook config; do
        [ -d "$STAGE/$d" ] && dirs+=("$d")
    done
    [ "${#dirs[@]}" -gt 0 ] || { C_DETAIL[encrypt]="no component data staged; refusing to encrypt an empty set"; return 1; }
    tar -C "$STAGE" -cf "$PLAIN_TAR" "${dirs[@]}" \
        || { C_DETAIL[encrypt]="tar assembly failed"; return 1; }
    plain_sum=$(sha256sum "$PLAIN_TAR" | awk '{print $1}')

    case "$CRYPTO_MODE" in
        age)
            recipient=$(age-keygen -y "$CBB_KEY_FILE" 2>/dev/null) \
                || { C_DETAIL[encrypt]="age-keygen could not derive a recipient from the key file"; return 1; }
            blob="$STAGE/$BACKUP_ID.tar.age"
            age -r "$recipient" -o "$blob" "$PLAIN_TAR" \
                || { C_DETAIL[encrypt]="age encryption failed"; return 1; }
            ;;
        openssl)
            blob="$STAGE/$BACKUP_ID.tar.enc"
            openssl enc -aes-256-cbc -pbkdf2 -pass "file:$CBB_KEY_FILE" \
                -in "$PLAIN_TAR" -out "$blob" \
                || { C_DETAIL[encrypt]="openssl encryption failed"; return 1; }
            ;;
    esac

    # Decrypt-verify: prove the blob decrypts with the provisioned key and that
    # the round-trip is bit-identical. A blob we cannot decrypt is worthless.
    case "$CRYPTO_MODE" in
        age)     age -d -i "$CBB_KEY_FILE" -o "$VERIFY_TMP" "$blob" 2>/dev/null ;;
        openssl) openssl enc -d -aes-256-cbc -pbkdf2 -pass "file:$CBB_KEY_FILE" \
                     -in "$blob" -out "$VERIFY_TMP" 2>/dev/null ;;
    esac
    if [ ! -f "$VERIFY_TMP" ]; then
        C_DETAIL[encrypt]="decrypt-verify failed: could not decrypt with the provisioned key file"
        return 1
    fi
    blob_sum=$(sha256sum "$VERIFY_TMP" | awk '{print $1}')
    if [ "$blob_sum" != "$plain_sum" ]; then
        C_DETAIL[encrypt]="decrypt-verify failed: round-trip digest mismatch"
        return 1
    fi
    rm -f "$VERIFY_TMP" "$PLAIN_TAR"

    # Remove plaintext staging: only the encrypted blob + manifest remain.
    for d in "${dirs[@]}"; do rm -rf "$STAGE/$d"; done
    PLAINTEXT_REMOVED="true"

    ENCRYPT_METHOD="$CRYPTO_MODE"
    ENCRYPT_ARTIFACT=$(basename "$blob")
    ENCRYPT_SHA256=$(sha256sum "$blob" | awk '{print $1}')
    ENCRYPT_BYTES=$(stat -c%s "$blob")
    C_BYTES[encrypt]="$ENCRYPT_BYTES"
    C_FILES[encrypt]=1
    C_DETAIL[encrypt]="method=$CRYPTO_MODE artifact=$ENCRYPT_ARTIFACT decrypt-verified"
    return 0
}

# --------------------------------------------------------------------------
# Retention pruning — keep newest KEEP_LAST sets, delete older cb-* dirs
# --------------------------------------------------------------------------
prune_old() {
    local seen=0 retained=0 pruned=0 d
    case "$KEEP_LAST" in ''|*[!0-9]*) KEEP_LAST=7 ;; esac
    [ "$KEEP_LAST" -ge 1 ] || KEEP_LAST=7
    while IFS= read -r d; do
        seen=$((seen + 1))
        if [ "$seen" -gt "$KEEP_LAST" ]; then
            rm -rf "$BACKUP_ROOT/$d"
            pruned=$((pruned + 1))
        else
            retained=$((retained + 1))
        fi
    done < <(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -name 'cb-*' -printf '%f\n' | sort -r)
    C_DETAIL[prune]="retained=$retained pruned=$pruned (keep_last=$KEEP_LAST)"
    return 0
}

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
print_summary() {
    local c st
    for c in redis qdrant surrealdb anya open-notebook config manifest encrypt prune; do
        st="${C_STATUS[$c]}"
        printf '%-13s %s bytes=%s files=%s -- %s\n' \
            "$c:" "$(printf '%s' "$st" | tr 'a-z' 'A-Z')" "${C_BYTES[$c]}" "${C_FILES[$c]}" "${C_DETAIL[$c]}"
    done
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
main() {
    # ---- preconditions (fail fast, before touching anything) ----
    [ -n "$CBB_KEY_FILE" ] || die "no key file given: pass as \$1 or set CBB_KEY_FILE (never defaulted by design)"
    require_private "$CBB_KEY_FILE" "backup key file" || exit 1
    case "$CBB_KEY_FILE" in
        "$BACKUP_ROOT"/*) die "key file must not live inside the backup tree ($BACKUP_ROOT)" ;;
    esac
    detect_crypto
    need_cmd curl; need_cmd tar; need_cmd sha256sum; need_cmd stat; need_cmd find
    mkdir -p "$STAGE" || die "cannot create staging dir $STAGE"

    # single-instance lock (best effort if flock is unavailable)
    if command -v flock >/dev/null 2>&1; then
        exec 9>"$BACKUP_ROOT/.cb-backup.lock"
        flock -n 9 || die "another cb-backup run is in progress"
    fi

    # ---- service versions (best effort; "unknown" never fails the run) ----
    C_VERSION[redis]=$( { "$REDIS_CLI" -h "$REDIS_HOST" -p "$REDIS_PORT" INFO server 2>/dev/null \
        | grep -m1 '^redis_version:' | cut -d: -f2 | tr -d '\r'; } || true )
    [ -n "${C_VERSION[redis]}" ] || C_VERSION[redis]="unknown"
    C_VERSION[qdrant]=$( { curl -sS --max-time "$CURL_TIMEOUT" "$QDRANT_URL/" 2>/dev/null \
        | grep -oP '"version"[[:space:]]*:[[:space:]]*"\K[^"]+' | head -n1; } || true )
    [ -n "${C_VERSION[qdrant]}" ] || C_VERSION[qdrant]="unknown"
    C_VERSION[surrealdb]=$( { curl -sS --max-time "$CURL_TIMEOUT" "$SURREAL_URL/version" 2>/dev/null \
        | tr -d '\r\n '; } || true )
    [ -n "${C_VERSION[surrealdb]}" ] || C_VERSION[surrealdb]="unknown"

    # ---- components (run all; collect results; never mark partial as success) ----
    if backup_redis;         then set_comp redis ok "${C_DETAIL[redis]}" "${C_VERSION[redis]}"
                             else set_comp redis fail "${C_DETAIL[redis]}" "${C_VERSION[redis]}"; fi
    if backup_qdrant;        then set_comp qdrant ok "${C_DETAIL[qdrant]}" "${C_VERSION[qdrant]}"
                             else set_comp qdrant fail "${C_DETAIL[qdrant]}" "${C_VERSION[qdrant]}"; fi
    if backup_surrealdb;     then set_comp surrealdb ok "${C_DETAIL[surrealdb]}" "${C_VERSION[surrealdb]}"
                             else set_comp surrealdb fail "${C_DETAIL[surrealdb]}" "${C_VERSION[surrealdb]}"; fi
    if backup_anya;          then set_comp anya ok "${C_DETAIL[anya]}"
                             else set_comp anya fail "${C_DETAIL[anya]}"; fi
    rc_on=0; backup_open_notebook || rc_on=$?
    if [ "$rc_on" -eq 0 ];    then set_comp open-notebook ok "${C_DETAIL[open-notebook]}"
    elif [ "$rc_on" -eq 2 ];  then set_comp open-notebook skip "${C_DETAIL[open-notebook]}"
                             else set_comp open-notebook fail "${C_DETAIL[open-notebook]}"; fi
    if backup_config;        then set_comp config ok "${C_DETAIL[config]}"
                             else set_comp config fail "${C_DETAIL[config]}"; fi

    if [ "$FAILURES" -gt 0 ]; then
        # Partial backup: write a forensics manifest, do NOT encrypt, exit non-zero.
        write_manifest "$(utc_now)"
        log "FAILURE: $FAILURES component(s) failed; no encrypted artifact produced (staging kept at $STAGE)"
        print_summary
        exit 1
    fi

    if encrypt_set; then
        set_comp encrypt ok "${C_DETAIL[encrypt]}"
    else
        set_comp encrypt fail "${C_DETAIL[encrypt]}"
        write_manifest "$(utc_now)"
        log "FAILURE: encryption failed; plaintext staging kept at $STAGE for forensics"
        print_summary
        exit 1
    fi

    write_manifest "$(utc_now)"
    prune_old && set_comp prune ok "${C_DETAIL[prune]}" \
              || set_comp prune fail "prune step failed (backups are intact)"

    log "SUCCESS: backup $BACKUP_ID -> $STAGE/$ENCRYPT_ARTIFACT"
    print_summary
    [ "$FAILURES" -eq 0 ]
}

main "$@"
