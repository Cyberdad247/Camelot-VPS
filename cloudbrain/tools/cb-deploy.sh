#!/usr/bin/env bash
###############################################################################
# cb-deploy.sh — build a versioned deploy bundle from the cloudbrain/ tree.
#
# Usage:
#   cloudbrain/tools/cb-deploy.sh [version]
#
#   version   optional label for this bundle, e.g. 20260923T024500Z
#             (default: current UTC time in that same format)
#
# What it does:
#   1. Tars the cloudbrain/ tree into
#        cloudbrain/dist/cloudbrain-<version>.tar.gz
#      excluding dist/ itself, any .git/ material, and build noise
#      (__pycache__/, *.pyc).
#   2. Writes cloudbrain/dist/cloudbrain-<version>.sha256 — a sha256 hash of
#      every file inside the bundle (paths relative to the cloudbrain/ root).
#   3. Prints a top-level MANIFEST line (bundle name, sha256, file count,
#      build time) for eyeball verification, and appends it to
#      cloudbrain/dist/MANIFEST.txt.
#   4. Verifies the bundle locally: extracts to a temp dir and runs
#      `sha256sum -c` against the manifest. Aborts if verification fails.
#   5. Prints the operator checklist for uploading to the Hermes VPS via the
#      Hermes Agent HTTP API and staging the deploy.
#
# Safety properties:
#   - set -euo pipefail; fails fast with a clear message on any error.
#   - Resolves the cloudbrain/ tree from its own location, so it works from
#     any working directory.
#   - NEVER touches the network and NEVER contains, requests, or embeds any
#     credential. The operator checklist below shows placeholders only
#     (${HERMES_HOST:?}, read -s prompts) that the operator fills in at
#     deploy time.
#   - Does not commit anything to git.
###############################################################################
set -euo pipefail

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "required tool '$1' not found on PATH"
}

need tar
need sha256sum
need find
need sort
need mktemp
need awk

# ---- Resolve the cloudbrain/ tree from this script's own location -----------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" && pwd)"
CLOUDBRAIN_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

[[ -d "$CLOUDBRAIN_DIR" ]] \
  || die "cloudbrain directory not found (resolved to '$CLOUDBRAIN_DIR')"
[[ "$(basename -- "$CLOUDBRAIN_DIR")" == "cloudbrain" ]] \
  || die "expected to live at cloudbrain/tools/cb-deploy.sh, but resolved tree root is '$CLOUDBRAIN_DIR'"

# ---- Version label -----------------------------------------------------------
VERSION="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]] \
  || die "bad version label '$VERSION' (allowed: letters, digits, . _ -)"

BUNDLE="cloudbrain-${VERSION}.tar.gz"
MANIFEST_NAME="cloudbrain-${VERSION}.sha256"
DIST_DIR="$CLOUDBRAIN_DIR/dist"
mkdir -p -- "$DIST_DIR"

# ---- Collect the file list (relative to the cloudbrain/ root) ----------------
# Excludes: dist/ itself (would recurse into the archive being written),
# any .git/ material, and Python build noise.
REL=()
while IFS= read -r -d '' f; do
  REL+=("${f#"$CLOUDBRAIN_DIR"/}")
done < <(
  find "$CLOUDBRAIN_DIR" -type f \
    ! -path "$CLOUDBRAIN_DIR/dist/*" \
    ! -path "$CLOUDBRAIN_DIR/.git/*" \
    ! -path '*/.git/*' \
    ! -path '*/__pycache__/*' \
    ! -name '*.pyc' \
    -print0 | sort -z
)

((${#REL[@]} > 0)) || die "nothing to bundle under '$CLOUDBRAIN_DIR'"

# ---- Build the tarball -------------------------------------------------------
echo "building bundle: $DIST_DIR/$BUNDLE (${#REL[@]} files)"
tar -czf "$DIST_DIR/$BUNDLE" -C "$CLOUDBRAIN_DIR" -- "${REL[@]}"

# ---- Write the sha256 manifest (one line per bundled file) -------------------
(
  cd -- "$CLOUDBRAIN_DIR" && sha256sum -- "${REL[@]}"
) > "$DIST_DIR/$MANIFEST_NAME"
echo "wrote manifest:  $DIST_DIR/$MANIFEST_NAME"

# ---- Verify: extract to a temp dir and check every hash ----------------------
VERIFY_DIR="$(mktemp -d)"
trap 'rm -rf -- "$VERIFY_DIR"' EXIT
tar -xzf "$DIST_DIR/$BUNDLE" -C "$VERIFY_DIR"
(
  cd -- "$VERIFY_DIR" && sha256sum -c --quiet -- "$DIST_DIR/$MANIFEST_NAME"
) || die "bundle verification FAILED — tarball does not match the manifest"
echo "verify: OK (${#REL[@]} files, sha256 manifest clean)"

# ---- Bundle size guard (VPS upload path caps at ~512 KiB) --------------------
SIZE_BYTES="$(wc -c < "$DIST_DIR/$BUNDLE")"
if ((SIZE_BYTES > 480 * 1024)); then
  printf 'WARN: bundle is %s bytes — over the ~512 KiB VPS upload ceiling; split it before deploying.\n' \
    "$SIZE_BYTES" >&2
else
  echo "size: ${SIZE_BYTES} bytes (under the ~512 KiB upload ceiling)"
fi

# ---- Top-level MANIFEST line -------------------------------------------------
BUNDLE_SHA="$(sha256sum -- "$DIST_DIR/$BUNDLE" | awk '{print $1}')"
BUILT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
MANIFEST_LINE="MANIFEST cloudbrain/dist/${BUNDLE} sha256=${BUNDLE_SHA} files=${#REL[@]} built=${BUILT_UTC}"
printf '%s\n' "$MANIFEST_LINE" >> "$DIST_DIR/MANIFEST.txt"
echo
echo "$MANIFEST_LINE"
echo "(also appended to cloudbrain/dist/MANIFEST.txt)"

# ---- Operator checklist ------------------------------------------------------
echo
echo "=================================================================="
echo " OPERATOR CHECKLIST — deploy cloudbrain ${VERSION} to the Hermes VPS"
echo "=================================================================="
echo
echo "Artifacts ready (copy these two files to your deploy workstation):"
echo "  ${DIST_DIR}/${BUNDLE}"
echo "  ${DIST_DIR}/${MANIFEST_NAME}"
echo "  ${MANIFEST_LINE}"
echo
cat <<'CHECKLIST'
This script never touches the network. Everything below runs on YOUR
workstation at deploy time. Fill in credentials only when prompted —
nothing is stored, and this file contains no secrets.

Target: Hermes Agent VPS (user `hermes`) via its HTTP API.
Conventions: ${HERMES_HOST:?} means "you must have HERMES_HOST set".
The cron-job and upload payload shapes below follow the gateway's
/api/cron/jobs and /api/files endpoints — confirm exact field names
against http://${HERMES_HOST:?}/openapi.json before sending.

------------------------------------------------------------------
0) Set connection variables AT DEPLOY TIME ONLY (never store them):

     read -rp 'Hermes host [162.35.107.134]: ' HERMES_HOST
     HERMES_HOST="${HERMES_HOST:-162.35.107.134}"
     read -rsp 'Hermes admin password (fresh login, never stored): ' HERMES_PASSWORD
     echo

------------------------------------------------------------------
1) Log in and capture the session cookie (12h expiry; re-login on 401):

     COOKIE_JAR="$(mktemp)"
     curl -sS -c "$COOKIE_JAR" -X POST "http://${HERMES_HOST:?}/auth/password-login" \
       -H 'Content-Type: application/json' \
       -d "{\"provider\":\"basic\",\"username\":\"admin\",\"password\":\"${HERMES_PASSWORD:?}\"}"
     unset HERMES_PASSWORD

------------------------------------------------------------------
2) Upload the bundle AND its sha256 manifest to /opt/data/scripts/:

     V="<VERSION>"   # e.g. V=20260923T024500Z — use the version printed above
     curl -sS -b "$COOKIE_JAR" -X POST "http://${HERMES_HOST:?}/api/files/upload" \
       -F "path=/opt/data/scripts/cloudbrain-${V}.tar.gz" \
       -F "file=@cloudbrain/dist/cloudbrain-${V}.tar.gz"
     curl -sS -b "$COOKIE_JAR" -X POST "http://${HERMES_HOST:?}/api/files/upload" \
       -F "path=/opt/data/scripts/cloudbrain-${V}.sha256" \
       -F "file=@cloudbrain/dist/cloudbrain-${V}.sha256"

   Keep each upload under ~512 KiB. If your gateway exposes the upload
   under a different route, use the /openapi.json shape instead — the
   destination paths above are what step 3 expects.

------------------------------------------------------------------
3) Create a no_agent cron job that stages the bundle and verifies it.
   It extracts to /opt/data/cloudbrain/deploy/<version>/ and checks
   every file against the sha256 manifest (same check this script ran
   locally). Save the returned job id as JOB_ID.

     curl -sS -b "$COOKIE_JAR" -X POST "http://${HERMES_HOST:?}/api/cron/jobs" \
       -H 'Content-Type: application/json' \
       -d @- <<'JOB'
     {
       "name": "cb-deploy-<VERSION>",
       "agent": "no_agent",
       "schedule": "<one-shot/manual per /openapi.json; this job is run via /trigger>",
       "command": "set -euo pipefail; V=<VERSION>; S=/opt/data/scripts; D=/opt/data/cloudbrain/deploy/$V; mkdir -p \"$D\"; tar -xzf \"$S/cloudbrain-$V.tar.gz\" -C \"$D\"; (cd \"$D\" && sha256sum -c \"$S/cloudbrain-$V.sha256\") && echo STAGE_OK $V"
     }
     JOB

   Replace <VERSION> with the real version (no angle brackets) before
   sending. Confirm the exact create-job field names against
   http://${HERMES_HOST:?}/openapi.json.

------------------------------------------------------------------
4) Trigger the job now:

     curl -sS -b "$COOKIE_JAR" -X POST \
       "http://${HERMES_HOST:?}/api/cron/jobs/${JOB_ID:?}/trigger"

------------------------------------------------------------------
5) Read the job output and confirm the manifest check passed:

     curl -sS -b "$COOKIE_JAR" \
       "http://${HERMES_HOST:?}/api/files/read?path=/opt/data/cron/output/${JOB_ID:?}/"

   Expect "OK" for every file plus the trailing "STAGE_OK <version>".
   The no_agent runner also drops output under /opt/data/cron/output/<job-id>/.

------------------------------------------------------------------
6) Continue with the deploy phases in cloudbrain/staging/DEPLOY_QUEUE.md,
   using /opt/data/cloudbrain/deploy/<version>/ on the VPS as the source
   tree (patches -> e2e tests -> supervision -> backup -> TLS -> runbook).

------------------------------------------------------------------
7) Clean up the session material on your workstation:

     rm -f "$COOKIE_JAR"; unset HERMES_HOST JOB_ID V

Done. The bundle on the VPS is bit-identical to what this script built
and verified locally — the sha256 manifest is the proof.
CHECKLIST
