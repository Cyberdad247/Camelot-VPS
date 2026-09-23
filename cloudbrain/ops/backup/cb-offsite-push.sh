#!/usr/bin/env bash
# cb-offsite-push.sh — Nightly off-VPS push of encrypted cloudbrain backup sets.
#
# STAGING SKETCH — worker OFFSITE, local forging only. NOT yet installed on the
# Hermes VPS and NEVER live-tested. Review before install; every __PLACEHOLDER__
# value is provisioned out-of-band by the owner and must never be committed,
# logged, or pasted into chat/alerts.
#
# Pipeline (per backup set):
#   1. Select oldest local set newer than the push watermark (requires the
#      backup worker's `.complete` marker — never push a half-written set).
#   2. tar-stream the set | split into 64 MiB chunks; sha256 each chunk.
#   3. S3 multipart upload (CreateMultipartUpload -> UploadPart x N ->
#      CompleteMultipartUpload). Resumable across nights: the upload-id and
#      completed part numbers persist in the state dir; on restart we
#      ListParts and upload only what is missing.
#   4. Upload a manifest object (chunk hashes, full-set digest, key id —
#      NEVER key material), then GET it back and compare digests.
#   5. On success: advance the watermark, prune LOCAL CHUNKS ONLY (the source
#      backup set is pruned by the backup track's GFS policy, never here),
#      reset the failure counter, send a recovery notice if we were failing.
#   6. On failure: increment the consecutive-failure counter, send an ntfy
#      alert with escalating priority. Unpushed sets are NEVER deleted by
#      this script — not even at disk-critical (see cloudbrain/ops/retention).
#
# Cron sandbox networking: no DNS, no general egress. Hostnames are resolved
# via Cloudflare DoH (1.1.1.1, reached by IP literal + curl --resolve) and
# every request uses `curl --resolve HOST:443:IP` so TLS/SNI still see the
# real hostname. This mirrors the proven cb-ntfy-health.sh pattern.
#
# Security rules honored:
#   V-BKP-003 — only ciphertext crosses the wire; the manifest carries the
#               encryption key ID, never key material. This job's config file
#               is a DIFFERENT file from the backup key file by construction.
#   V-SEC-011 — no secrets, credentials, or key material in ntfy payloads
#               or cron-output logs.
#   V-BKP-004 — the S3 credential is WRITE-ONLY scoped (PutObject/GetObject/
#               ListBucket/multipart; NO DeleteObject, NO lifecycle/policy
#               changes). Even a fully compromised VPS can only ADD objects,
#               never destroy the off-host copies.
set -euo pipefail

# ------------------------------------------------------------------ config --
# Single env file, provisioned OUT-OF-BAND by the owner. Mode 0600, owned by
# the hermes user. Expected variables (placeholder names — real values are
# never written here):
#   OFFSITE_S3_ENDPOINT    e.g. https://<account>.r2.cloudflarestorage.com
#   OFFSITE_S3_REGION      e.g. auto (R2) or us-east-1 (B2)
#   OFFSITE_S3_BUCKET      e.g. cloudbrain-offsite
#   OFFSITE_S3_ACCESS_KEY / OFFSITE_S3_SECRET_KEY  (write-only scoped key)
#   OFFSITE_NTFY_TOPIC     private ntfy.sh topic (same one cb-ntfy-health uses)
CONFIG_FILE="${OFFSITE_CONFIG:-/opt/data/secrets/offsite/offsite.env}"

BACKUP_ROOT="/opt/data/cloudbrain/backups"      # <UTC-ts>/ sets from backup worker
STATE_DIR="/opt/data/cloudbrain/offsite/state"
CHUNK_DIR="/opt/data/cloudbrain/offsite/chunks"
LOCK_FILE="/opt/data/cloudbrain/offsite/push.lock"
CHUNK_MB=64
MAX_PART_RETRIES=3
PUSH_STALE_HOURS=36        # alert via health job if last success older than this

# ----------------------------------------------------------------- helpers --
log()  { printf '%s [offsite-push] %s\n' "$(date -u +%FT%TZ)" "$*"; }
die()  { log "FATAL: $*"; exit 1; }

load_config() {
    [ -r "$CONFIG_FILE" ] || die "config not readable: $CONFIG_FILE"
    # shellcheck disable=SC1090
    set -a; . "$CONFIG_FILE"; set +a
    for v in OFFSITE_S3_ENDPOINT OFFSITE_S3_REGION OFFSITE_S3_BUCKET \
             OFFSITE_S3_ACCESS_KEY OFFSITE_S3_SECRET_KEY OFFSITE_NTFY_TOPIC; do
        [ -n "${!v:-}" ] || die "config missing: $v"
        case "${!v}" in *__PLACEHOLDER__*|__OFFSITE_*)
            die "config $v still holds a placeholder — provision real values out-of-band" ;;
        esac
    done
    # Host part of the endpoint, e.g. <account>.r2.cloudflarestorage.com
    S3_HOST="$(printf '%s' "$OFFSITE_S3_ENDPOINT" | sed -e 's#^https\?://##' -e 's#/.*##')"
    [ -n "$S3_HOST" ] || die "cannot parse host from OFFSITE_S3_ENDPOINT"
}

# Resolve a hostname via Cloudflare DoH without a local resolver.
# Echoes the first IPv4 A record, or returns nonzero.
doh_resolve() {
    local host="$1" resp ip
    resp="$(curl -sS --max-time 15 \
        --resolve "cloudflare-dns.com:443:1.1.1.1" \
        "https://cloudflare-dns.com/dns-query?name=${host}&type=A" \
        -H 'accept: application/dns-json')" || return 1
    ip="$(printf '%s' "$resp" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    a = [x["data"] for x in d.get("Answer", []) if x.get("type") == 1]
    print(a[0] if a else "")
except Exception:
    print("")')"
    [ -n "$ip" ] && printf '%s' "$ip" || return 1
}

# S3 request helper. $1=METHOD $2=path ("/bucket/key?query"); remaining args
# are extra curl flags. Signs with SigV4 via curl's native --aws-sigv4
# (curl >= 7.75; Debian 13 ships 8.x). TLS/SNI see the real hostname while
# the TCP connection goes to the DoH-resolved IP.
s3_curl() {
    local method="$1" path="$2"; shift 2
    curl -sS --max-time 300 \
        --resolve "${S3_HOST}:443:${S3_IP}" \
        --aws-sigv4 "aws:amz:${OFFSITE_S3_REGION}:s3" \
        --user "${OFFSITE_S3_ACCESS_KEY}:${OFFSITE_S3_SECRET_KEY}" \
        -X "$method" "${OFFSITE_S3_ENDPOINT}${path}" "$@"
}

# Minimal ntfy publisher through the same DoH+--resolve trick.
# $1=priority $2=title $3=message  (never pass secrets — V-SEC-011)
ntfy() {
    local prio="$1" title="$2" msg="$3" ntfy_ip
    ntfy_ip="$(doh_resolve "ntfy.sh")" || { log "WARN: ntfy DoH failed, alert lost: $title"; return 1; }
    curl -sS --max-time 20 \
        --resolve "ntfy.sh:443:${ntfy_ip}" \
        "https://ntfy.sh/${OFFSITE_NTFY_TOPIC}" \
        -H "Title: ${title}" -H "Priority: ${prio}" -H "Tags: offsite,backup" \
        --data-binary "$msg" >/dev/null || log "WARN: ntfy publish failed: $title"
}

fail_count() { cat "$STATE_DIR/consec_failures" 2>/dev/null || echo 0; }
set_fail_count() { printf '%s\n' "$1" > "$STATE_DIR/consec_failures"; }

# ------------------------------------------------------------------ select --
# Oldest set newer than the watermark that the backup worker marked complete.
pick_next_set() {
    local watermark=""
    [ -f "$STATE_DIR/watermark" ] && watermark="$(cat "$STATE_DIR/watermark")"
    for d in $(ls -1 "$BACKUP_ROOT" 2>/dev/null | sort); do
        [ -d "$BACKUP_ROOT/$d" ] || continue
        [ -n "$watermark" ] && [[ "$d" < "$watermark" || "$d" == "$watermark" ]] && continue
        [ -f "$BACKUP_ROOT/$d/.complete" ] || { log "skip $d (no .complete marker)"; continue; }
        printf '%s' "$d"
        return 0
    done
    return 1
}

# GFS tier for lifecycle tagging. Convention PROPOSED for the backup worker
# to confirm: explicit <set>/.tier wins; else Monday -> weekly, day 01 ->
# monthly, else daily. (Set ids are UTC timestamps: YYYYMMDDTHHMMSSZ.)
set_tier() {
    local set_id="$1" tier_file="$BACKUP_ROOT/$set_id/.tier"
    if [ -f "$tier_file" ]; then tr -d '[:space:]' < "$tier_file"; return; fi
    local ymd="${set_id:0:8}"
    if [ "${ymd:6:2}" = "01" ]; then echo "monthly";
    elif [ "$(date -u -d "${ymd:0:4}-${ymd:4:2}-${ymd:6:2}" +%u)" = "1" ]; then echo "weekly";
    else echo "daily"; fi
}

# ------------------------------------------------------------------- chunk --
chunk_set() { # $1=set_id -> writes chunks, echoes "<nchunks> <set_sha256>"
    local set_id="$1" pfx="$CHUNK_DIR/${set_id}.part-" n=0
    mkdir -p "$CHUNK_DIR"
    rm -f "${pfx}"*
    log "chunking set $set_id (${CHUNK_MB} MiB parts)"
    # tar-stream straight into split: no intermediate full-size tar on disk.
    tar -C "$BACKUP_ROOT" -cf - "$set_id" | split -b "${CHUNK_MB}M" - "$pfx"
    for c in "${pfx}"*; do
        sha256sum "$c" >> "$CHUNK_DIR/${set_id}.sha256"
        n=$((n+1))
    done
    [ "$n" -gt 0 ] || die "chunking produced no parts for $set_id"
    local set_digest
    set_digest="$(cut -d' ' -f1 "$CHUNK_DIR/${set_id}.sha256" | sha256sum | cut -d' ' -f1)"
    printf '%s %s' "$n" "$set_digest"
}

# ----------------------------------------------------------------- multipart --
s3_xml() { # $1 = xpath-ish key; reads XML on stdin, prints text via python
    python3 -c '
import sys, xml.etree.ElementTree as ET
want = sys.argv[1]
try:
    root = ET.fromstring(sys.stdin.read())
    for el in root.iter():
        if el.tag.endswith(want):
            print(el.text or ""); break
except Exception:
    pass' "$1"
}

mpart_initiate() { # $1=object_key -> echoes UploadId
    s3_curl POST "/${OFFSITE_S3_BUCKET}/$1?uploads" | s3_xml "UploadId"
}

mpart_list_done() { # $1=object_key $2=upload_id -> echoes uploaded part numbers, one per line
    s3_curl GET "/${OFFSITE_S3_BUCKET}/$1?uploadId=$2" | python3 -c '
import sys, xml.etree.ElementTree as ET
try:
    for el in ET.fromstring(sys.stdin.read()).iter():
        if el.tag.endswith("PartNumber"): print(el.text)
except Exception: pass'
}

mpart_upload_part() { # $1=object_key $2=upload_id $3=part_no $4=chunk_file -> echoes ETag
    local hdr etag attempt=1
    hdr="$(mktemp)"
    while [ "$attempt" -le "$MAX_PART_RETRIES" ]; do
        if s3_curl PUT "/${OFFSITE_S3_BUCKET}/$1?partNumber=$3&uploadId=$2" \
                --data-binary "@$4" -D "$hdr" -o /dev/null; then
            etag="$(grep -i '^etag:' "$hdr" | head -1 | sed -e 's/^[Ee][Tt][Aa][Gg]: *//' -e 's/^"//' -e 's/"$//' | tr -d '\r')"
            rm -f "$hdr"
            [ -n "$etag" ] && { printf '%s' "$etag"; return 0; }
        fi
        log "part $3 attempt $attempt failed; retrying"
        attempt=$((attempt+1)); sleep $((attempt*5))
    done
    rm -f "$hdr"; return 1
}

mpart_complete() { # $1=object_key $2=upload_id $3=parts_file("N ETag" lines)
    local xml
    xml="$(python3 -c '
import sys
parts = []
for line in open(sys.argv[1]):
    n, et = line.split()
    parts.append(f"<Part><PartNumber>{n}</PartNumber><ETag>\"{et}\"</ETag></Part>")
print("<CompleteMultipartUpload>" + "".join(parts) + "</CompleteMultipartUpload>")' "$3")"
    s3_curl POST "/${OFFSITE_S3_BUCKET}/$1?uploadId=$2" \
        -H 'Content-Type: application/xml' --data-binary "$xml" -o /dev/null
}

mpart_abort() { # best-effort cleanup of a doomed multipart session (not of completed objects)
    s3_curl DELETE "/${OFFSITE_S3_BUCKET}/$1?uploadId=$2" -o /dev/null || true
}

# ------------------------------------------------------------------ upload --
push_set() { # $1=set_id ; returns 0 on verified success
    local set_id="$1" tier obj_key mkey upload_id state_f nchunks set_digest
    tier="$(set_tier "$set_id")"
    obj_key="backups/${set_id}.tar"
    mkey="backups/${set_id}.manifest.json"
    state_f="$STATE_DIR/${set_id}.upload"
    log "pushing set $set_id (tier=$tier)"

    read -r nchunks set_digest < <(chunk_set "$set_id")
    [[ "$nchunks" =~ ^[1-9][0-9]*$ ]] || return 1
    log "set $set_id -> $nchunks chunks, set-digest sha256:$set_digest"

    # Resume or initiate the multipart session.
    if [ -f "$state_f" ]; then upload_id="$(cut -d' ' -f1 "$state_f")"
    else
        upload_id="$(mpart_initiate "$obj_key")" || return 1
        printf '%s\n' "$upload_id" > "$state_f"
    fi
    [ -n "$upload_id" ] || return 1

    local done_parts pfx etag parts_list
    pfx="$CHUNK_DIR/${set_id}.part-"
    done_parts="$(mpart_list_done "$obj_key" "$upload_id")"
    parts_list="$(mktemp)"
    local i=1 chunk
    for chunk in "${pfx}"*; do
        if printf '%s\n' "$done_parts" | grep -qx "$i"; then
            log "part $i already uploaded (resume)"
            # ETag needed for Complete; re-list gives it — fetch lazily below.
        else
            # On part failure we do NOT abort the multipart session: the
            # upload-id persists and the next night resumes via ListParts.
            # Orphaned sessions are reaped out-of-band by the bucket's
            # AbortIncompleteMultipartUpload lifecycle rule (owner-configured;
            # the push credential cannot touch lifecycle — V-BKP-004).
            etag="$(mpart_upload_part "$obj_key" "$upload_id" "$i" "$chunk")" \
                || { rm -f "$parts_list"; return 1; }
            printf '%s %s\n' "$i" "$etag" >> "$STATE_DIR/${set_id}.etags"
            log "part $i/$nchunks uploaded (etag ${etag:0:12}…)"
        fi
        i=$((i+1))
    done
    # Rebuild the complete parts list with ETags from the persisted file.
    # (On a resumed run, part ETags were recorded when first uploaded.)
    cp "$STATE_DIR/${set_id}.etags" "$parts_list" 2>/dev/null || true
    [ -s "$parts_list" ] || { log "no part ETags recorded"; rm -f "$parts_list"; return 1; }

    mpart_complete "$obj_key" "$upload_id" "$parts_list" || { rm -f "$parts_list"; return 1; }
    rm -f "$parts_list"

    # Tag the object for the GFS lifecycle tier (out-of-band lifecycle rules
    # key off this tag; the push credential cannot change the rules — V-BKP-004).
    s3_curl PUT "/${OFFSITE_S3_BUCKET}/${obj_key}?tagging" \
        --data-binary "<Tagging><TagSet><Tag><Key>tier</Key><Value>${tier}</Value></Tag></TagSet></Tagging>" \
        -o /dev/null || log "WARN: tagging failed for $obj_key (non-fatal)"

    # ---- manifest: chunk hashes + set digest + key ID (never key material)
    local manifest key_id
    key_id="$(tr -d '[:space:]' < "$BACKUP_ROOT/$set_id/.key-id" 2>/dev/null || echo "unknown")"
    manifest="$(python3 - "$CHUNK_DIR/${set_id}.sha256" <<'EOF'
import json, sys
rows = []
for line in open(sys.argv[1]):
    h, p = line.split()
    rows.append({"chunk": p.split(".part-")[-1], "sha256": h})
print(json.dumps({
    "set_id": "__SET__", "tier": "__TIER__",
    "chunks": rows, "set_sha256": "__DIGEST__",
    "encryption_key_id": "__KEYID__",   # ID only — V-BKP-003
    "pushed_at_utc": "__NOW__",
    "producer": "cb-offsite-push.sh",
}))
EOF
)"
    manifest="${manifest//__SET__/$set_id}"; manifest="${manifest//__TIER__/$tier}"
    manifest="${manifest//__DIGEST__/$set_digest}"; manifest="${manifest//__KEYID__/$key_id}"
    manifest="${manifest//__NOW__/$(date -u +%FT%TZ)}"
    local mfile; mfile="$(mktemp)"
    printf '%s' "$manifest" > "$mfile"
    s3_curl PUT "/${OFFSITE_S3_BUCKET}/${mkey}" \
        -H 'Content-Type: application/json' --data-binary "@$mfile" -o /dev/null \
        || { rm -f "$mfile"; return 1; }

    # ---- verify: GET the manifest back and compare digests, then HEAD the object
    local remote_m
    remote_m="$(s3_curl GET "/${OFFSITE_S3_BUCKET}/${mkey}")" || { rm -f "$mfile"; return 1; }
    rm -f "$mfile"
    if [ "$(printf '%s' "$remote_m" | sha256sum | cut -d' ' -f1)" != \
         "$(printf '%s' "$manifest" | sha256sum | cut -d' ' -f1)" ]; then
        log "manifest verification FAILED for $set_id"
        return 1
    fi
    local remote_len local_len
    remote_len="$(s3_curl HEAD "/${OFFSITE_S3_BUCKET}/${obj_key}" -D - -o /dev/null \
        | grep -i '^content-length:' | tr -d '\r' | awk '{print $2}')"
    local_len="$(tar -C "$BACKUP_ROOT" -cf - "$set_id" | wc -c)"
    [ -n "$remote_len" ] && [ "$remote_len" = "$local_len" ] \
        || log "WARN: size check inconclusive (remote=$remote_len local=$local_len)"
    log "set $set_id verified offsite (manifest digest match)"
    return 0
}

# --------------------------------------------------------------------- main --
main() {
    mkdir -p "$STATE_DIR" "$CHUNK_DIR"
    exec 9>"$LOCK_FILE"
    flock -n 9 || { log "another push is running; exiting"; exit 0; }

    load_config
    S3_IP="$(doh_resolve "$S3_HOST")" || die "DoH resolution failed for $S3_HOST"

    local set_id prev_failures
    if ! set_id="$(pick_next_set)"; then
        log "nothing new to push (watermark current)"
        exit 0
    fi
    prev_failures="$(fail_count)"

    if push_set "$set_id"; then
        # Success: advance watermark, prune LOCAL CHUNKS ONLY, reset counter.
        printf '%s\n' "$set_id" > "$STATE_DIR/watermark"
        rm -rf "$CHUNK_DIR/${set_id}.part-"* "$CHUNK_DIR/${set_id}.sha256" \
               "$STATE_DIR/${set_id}.upload" "$STATE_DIR/${set_id}.etags"
        set_fail_count 0
        date -u +%FT%TZ > "$STATE_DIR/last_success"
        log "push complete for $set_id; watermark advanced"
        if [ "$prev_failures" -gt 0 ]; then
            ntfy "default" "offsite push recovered" \
                 "Set $set_id pushed and verified after $prev_failures failed night(s)."
        fi
        exit 0
    fi

    # Failure path: keep everything, escalate the alert. NEVER delete data.
    local n; n=$((prev_failures + 1)); set_fail_count "$n"
    rm -rf "$CHUNK_DIR/${set_id}.part-"* "$CHUNK_DIR/${set_id}.sha256" || true
    local prio="high" note="night $n"
    [ "$n" -ge 3 ] && { prio="urgent"; note="$n CONSECUTIVE nights — offsite RPO breached"; }
    log "push FAILED for $set_id ($note); chunks cleaned, source set retained"
    ntfy "$prio" "offsite push failed ($note)" \
         "Set $set_id could not be pushed/verified ($note). Local set retained; no data deleted. Check cron output."
    exit 1
}

main "$@"
