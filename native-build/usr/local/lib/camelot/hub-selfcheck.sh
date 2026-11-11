#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Camelot-OS hub self-check — makes the reality contract run continuously.
#
# WHY THIS EXISTS
#
# Every defect found on this hub had one shape: a WRITTEN claim and a LIVE fact that
# disagreed, with nothing in between to notice. The roster, the CloudBrain UUIDs, the
# tailnet inventory, the unit state, `HERMES_PRIME: ALWAYS_ON_HUB`, the stale tree, and
# nine post-conditions swallowed by `|| true` — one bug, eight times.
#
# The detectors for all of that now exist. They simply did not run anywhere, so the
# contract was only checked when a human remembered to check it. This wires them to an
# alarm.
#
#   run       execute the audit, persist a machine-readable status, exit with its code
#   alert     invoked by systemd OnFailure; emits a DEDUPLICATED alert, exits 0 always
#   watchdog  dead-man's switch: fails when the audit has stopped producing fresh
#             status, so that a monitor which silently stops is itself an alert
#
# WHY THE WATCHDOG EXISTS
#
# A timer that stops does not fail — it simply stops. `systemctl --failed` stays clean,
# `status.json` ages quietly, and the entire monitoring layer reverts to being
# documentation, which is the exact defect this script was written to remove. Nothing
# inside a scheduled check can report its own absence, so the liveness of the monitor
# needs a second, independent trigger. That is the watchdog: one hourly timer that
# checks the age of status.json and fails when it exceeds the limit.
#
# It is also the only path that runs REGARDLESS of the audit's verdict, which makes it
# the only place a recovery can be observed — systemd's OnFailure never fires on
# success, so the recovery branch below would otherwise be unreachable in production.
#
# The audit itself is `scripts/vps_hub_bootstrap.sh --self-check`, which is read-only
# and defines the post-conditions. This script never restates them — duplicating the
# contract is how the contract drifts from itself.
#
# Alert delivery, in order of what is actually available on the hub:
#   * journal          — always (systemd captures stdout/stderr)
#   * local mail       — always (sendmail/postfix are installed and active)
#   * remote mail      — only when CAMELOT_ALERT_EMAIL is set to a real address
#   * webhook          — only when CAMELOT_ALERT_WEBHOOK is set
#
# With nothing configured this still alerts, but it lands in root's mailbox on the hub
# and in the journal. That is a real channel, not a pretend one — and the output says
# which channels were used rather than implying a notification was delivered.

set -uo pipefail   # deliberately no -e: a failing audit is the signal, not a script error

STATE_DIR="${CAMELOT_SELFCHECK_DIR:-/var/lib/camelot/selfcheck}"
AUDIT="${CAMELOT_SELFCHECK_AUDIT:-/usr/local/lib/camelot/vps_hub_bootstrap.sh}"
STATUS="$STATE_DIR/status.json"
LAST_RUN="$STATE_DIR/last-run.txt"
SIGNATURE_FILE="$STATE_DIR/last-alert.signature"
WATCHDOG="$STATE_DIR/watchdog.json"
# Threshold sits at 3x the audit cadence: two consecutive missed cycles must not alert
# (a slow host is not a dead monitor), but a genuinely stopped timer is caught within
# the hour. The cadence itself is owned by camelot-selfcheck.timer, not by this script.
MAX_AGE_MIN="${CAMELOT_SELFCHECK_MAX_AGE_MIN:-45}"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
logger_err() { logger -t camelot-selfcheck -p daemon.err -- "$*" 2>/dev/null || true; }

usage() {
  echo "usage: $0 run|alert|watchdog|test-alert" >&2
  exit 2
}

# ------------------------------------------------------------------ run ---
cmd_run() {
  if [[ ! -x "$AUDIT" && ! -f "$AUDIT" ]]; then
    log "FATAL: audit not found at $AUDIT"
    return 2
  fi

  mkdir -p "$STATE_DIR"

  local out rc
  out="$("$AUDIT" --self-check 2>&1)"
  rc=$?
  printf '%s\n' "$out" > "$LAST_RUN"

  python3 - "$STATUS" "$rc" "$AUDIT" "$LAST_RUN" <<'PY'
import datetime, hashlib, json, pathlib, socket, sys

status_path, rc, audit, last_run = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
text = pathlib.Path(last_run).read_text(encoding="utf-8", errors="replace")

# Parse the audit's own result block rather than re-deriving the contract here.
failures = [l.split("\u274c", 1)[1].strip() for l in text.splitlines() if "\u274c" in l]
warnings = [l.split("\u26a0", 1)[1].strip() for l in text.splitlines() if "\u26a0" in l]

audit_hash = "missing"
ap = pathlib.Path(audit)
if ap.exists():
    audit_hash = hashlib.sha256(ap.read_bytes()).hexdigest()[:16]

payload = {
    "schema": "camelot-os.hub.selfcheck/v1",
    "contract": "vps_hub_bootstrap.sh --self-check",
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "host": socket.gethostname(),
    "ok": rc == 0 and not failures,
    "exit_code": rc,
    "failures": failures,
    "warnings": warnings,
    "failure_count": len(failures),
    "warning_count": len(warnings),
    "audit": audit,
    # Recorded so a DEPLOYED copy that has fallen behind the repository is visible
    # instead of silently auditing an older contract.
    "audit_sha256": audit_hash,
}
pathlib.Path(status_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

print(f"selfcheck: ok={payload['ok']} failures={len(failures)} warnings={len(warnings)} audit_sha={audit_hash}")
for f in failures:
    print(f"  FAIL {f}")
PY

  if (( rc == 0 )); then
    log "hub self-check PASSED (exit 0)"
  else
    log "hub self-check FAILED (exit $rc) — see $STATUS"
  fi
  return "$rc"
}

# -------------------------------------------------------------- deliver ---
# Single delivery path for every alert kind. Two delivery paths drift apart, and the
# channels a notification actually used must be named by the code that used them —
# never implied by a caller that cannot know.
deliver() {
  local subject="$1" body="$2" tag="${3:-alert}" channels=()
  body="$(printf 'CAMELOT HUB SELF-CHECK ALERT\n\n%s' "$body")"

  logger_err "$(printf '%s' "$body" | tr '\n' ' ' | head -c 900)"

  # Mail: always attempted. Default recipient is root (local mailbox); a real address
  # only when explicitly configured, so nothing pretends to leave the box by accident.
  local recipient="${CAMELOT_ALERT_EMAIL:-root}"
  # "submitted", NOT "delivered". sendmail returning 0 means the MTA ACCEPTED the message
  # for delivery; final delivery can fail afterwards with a bounce that lands in root's
  # local mailbox. Reporting the bare address here claimed a delivery that had not
  # happened — the channel had never been exercised, so nobody could tell.
  if printf 'Subject: %s\n\n%s\n' "$subject" "$body" | sendmail "$recipient" 2>/dev/null; then
    channels+=("mail:submitted:${recipient}")
  else
    channels+=("mail:REJECTED(${recipient})")
  fi

  # --- Resend (HTTPS email API) -------------------------------------------------
  # Preferred over local sendmail wherever configured, because direct-to-MX delivery
  # from this host FAILED (Final-Recipient accepted, then Action: failed / Status 5.0.0)
  # and it failed AFTER the MTA accepted the message — so the submission looked like a
  # success while nothing was delivered. An HTTPS API answers on the request, so a
  # rejected send is reported at the moment it happens rather than by a bounce nobody
  # reads. Needs CAMELOT_ALERT_RESEND_KEY; the from-address must be on a domain verified
  # in the provider's dashboard, or delivery is accepted and then filtered.
  if [[ -n "${CAMELOT_ALERT_RESEND_KEY:-}" ]]; then
    local from="${CAMELOT_ALERT_FROM:-onboarding@resend.dev}" payload code
    payload="$(python3 -c 'import json,sys;print(json.dumps({"from":sys.argv[1],"to":[sys.argv[2]],"subject":sys.argv[3],"text":sys.argv[4]}))' \
      "$from" "$recipient" "$subject" "$body" 2>/dev/null)"
    code="$(curl -sS -m 15 -o /dev/null -w '%{http_code}' -X POST https://api.resend.com/emails \
      -H "Authorization: Bearer ${CAMELOT_ALERT_RESEND_KEY}" \
      -H 'Content-Type: application/json' --data "$payload" 2>/dev/null)"
    case "$code" in
      200|201) channels+=("resend:${recipient}") ;;
      *)      channels+=("resend:FAILED(http_${code:-000})") ;;
    esac
  else
    channels+=("resend:unconfigured")
  fi

  if [[ -n "${CAMELOT_ALERT_WEBHOOK:-}" ]]; then
    local hook_code
    # ntfy mode triggers on ntfy.sh URLs or explicitly via CAMELOT_ALERT_NTFY_MODE=1
    # (self-hosted ntfy on a bare tailscale IP carries no 'ntfy' substring).
    if [[ "$CAMELOT_ALERT_WEBHOOK" == *ntfy.sh* || "${CAMELOT_ALERT_NTFY_MODE:-}" == "1" ]]; then
      # ntfy: raw message body with the subject as Title header — the JSON
      # {"text"} envelope is not a payload ntfy displays. Optional bearer
      # token (CAMELOT_ALERT_NTFY_TOKEN) for private topics; a public
      # ntfy.sh topic is readable by anyone who knows its name.
      hook_code="$(curl -sS -m 15 -o /dev/null -w '%{http_code}' \
        -H "Title: ${subject}" \
        ${CAMELOT_ALERT_NTFY_TOKEN:+-H "Authorization: Bearer ${CAMELOT_ALERT_NTFY_TOKEN}"} \
        --data-binary "$body" \
        "$CAMELOT_ALERT_WEBHOOK" 2>/dev/null)"
    else
      hook_code="$(curl -sS -m 15 -o /dev/null -w '%{http_code}' -X POST \
        -H 'Content-Type: application/json' \
        --data "$(python3 -c 'import json,sys;print(json.dumps({"text":open(sys.argv[1]).read()}))' "$STATUS")" \
        "$CAMELOT_ALERT_WEBHOOK" 2>/dev/null)"
    fi
    case "$hook_code" in
      200|201|202) channels+=("webhook:delivered") ;;
      *)           channels+=("webhook:FAILED(http_${hook_code:-000})") ;;
    esac
  else
    channels+=("webhook:unconfigured")
  fi

  log "ALERT emitted ($tag) via ${channels[*]}"
  printf '%s\n' "$body"
}

# Returns a one-line reason when the WATCHDOG has recorded a staleness verdict that is
# newer than the last audit result, else nothing. Reporting a stopped monitor as
# "post-conditions failed" would send the reader to the wrong file.
_monitor_stale_reason() {
  [[ -f "$WATCHDOG" ]] || return 0
  python3 - "$WATCHDOG" "$STATUS" <<'PY'
import json, pathlib, sys
wd_path, st_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
try:
    wd = json.loads(wd_path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(0)
if not wd.get("stale"):
    sys.exit(0)
try:
    st = json.loads(st_path.read_text(encoding="utf-8"))
except Exception:
    st = {}
# Only the NEWER verdict counts: a stale verdict must not mask a fresh audit, and an
# old staleness record must not mask a fresh watchdog run.
if (wd.get("ts") or "") <= (st.get("ts") or ""):
    sys.exit(0)
print(wd.get("reason") or "monitor stale with no recorded reason")
PY
}

# ---------------------------------------------------------------- alert ---
_json_get() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get(sys.argv[2],''))" "$STATUS" "$1" 2>/dev/null; }

cmd_alert() {
  if [[ ! -f "$STATUS" ]]; then
    log "alert: no status file at $STATUS — nothing to report"
    logger_err "camelot-selfcheck FAILED but produced no status; check the audit can run"
    return 0
  fi

  local failures sig stale_reason
  stale_reason="$(_monitor_stale_reason)"
  if [[ -n "$stale_reason" ]]; then
    failures="MONITOR STALE — $stale_reason"
  else
    failures="$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print('\n'.join(d.get('failures',[])))" "$STATUS" 2>/dev/null)"
  fi
  sig="$(printf '%s' "$failures" | sha256sum | cut -c1-16)"

  # Recovery is deliberately NOT handled here: systemd's OnFailure only fires on
  # failure, so this function can never announce a recovery in production. The watchdog
  # runs unconditionally and owns that notice.

  # --- dedup ------------------------------------------------------------
  # The timer re-runs every 15 minutes. Without this, a persistent failure would send
  # the same alert 96 times a day until someone muted it, which trains people to ignore
  # alerts. Alert on transition, and on a changed failure set; stay quiet while unchanged.
  if [[ -f "$SIGNATURE_FILE" && "$(cat "$SIGNATURE_FILE")" == "$sig" ]]; then
    log "alert: failure set unchanged ($sig) — suppressed"
    return 0
  fi
  printf '%s\n' "$sig" > "$SIGNATURE_FILE"

  # The subject must name the actual condition: a mailbox showing "self-check failed"
  # when the audit in fact stopped running sends triage to the wrong file entirely.
  local subject body
  if [[ -n "$stale_reason" ]]; then
    subject="[Camelot] hub MONITOR STALE on $(hostname)"
  else
    subject="[Camelot] hub self-check failed on $(hostname)"
  fi

  body="$(printf 'host:    %s\ntime:    %s\nfailures:\n%s\n\nfull status: %s' \
    "$(hostname)" "$(date -u +%FT%TZ)" "$(printf '%s\n' "$failures" | sed 's/^/  - /')" "$STATUS")"

  deliver "$subject" "$body" "sig=$sig"
  return 0   # never propagate: the selfcheck unit already carries the failure
}

# ------------------------------------------------------------- watchdog ---
cmd_watchdog() {
  mkdir -p "$STATE_DIR"

  local rc=0
  python3 - "$STATUS" "$WATCHDOG" "$MAX_AGE_MIN" <<'PY' || rc=$?
import datetime, json, pathlib, socket, sys

status_path, out_path, max_age = sys.argv[1], sys.argv[2], int(sys.argv[3])
now = datetime.datetime.now(datetime.timezone.utc)
stale, reason, age_minutes, status_ts = False, "", None, None

sp = pathlib.Path(status_path)
if not sp.exists():
    stale = True
    reason = f"no status file at {status_path} — the audit has never produced one"
else:
    try:
        status_ts = json.loads(sp.read_text(encoding="utf-8"))["ts"]
        t = datetime.datetime.fromisoformat(status_ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        age_minutes = (now - t).total_seconds() / 60.0
        if age_minutes > max_age:
            stale = True
            reason = f"last self-check was {age_minutes:.0f} min ago (limit {max_age} min)"
    except Exception as exc:  # unreadable status is itself a monitor fault
        stale = True
        reason = f"status file at {status_path} is unreadable: {exc}"

payload = {
    "schema": "camelot-os.hub.selfcheck.watchdog/v1",
    "ts": now.isoformat(),
    "host": socket.gethostname(),
    "ok": not stale,
    "stale": stale,
    "reason": reason,
    "age_minutes": age_minutes,
    "max_age_minutes": max_age,
    "status_ts": status_ts,
    "status_file": status_path,
}
pathlib.Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

print(
    f"watchdog: fresh={not stale} age_min="
    f"{'n/a' if age_minutes is None else f'{age_minutes:.1f}'} "
    f"limit={max_age} — {reason or 'monitor is live'}"
)
sys.exit(1 if stale else 0)
PY

  if (( rc == 0 )); then
    # The only unconditional path, therefore the only place a recovery is observable.
    if [[ -f "$SIGNATURE_FILE" ]] && [[ "$(_json_get ok)" == "True" ]]; then
      rm -f "$SIGNATURE_FILE"
      deliver "[Camelot] hub self-check RECOVERED on $(hostname)" \
        "The hub self-check is passing again and the monitor is fresh." "recovered"
    fi
    return 0
  fi

  log "watchdog: monitor is STALE — failing so systemd records it"
  return 1
}

# ------------------------------------------------------------ test-alert ---
# Sends a clearly-labelled test through the SAME delivery path a real alert uses, so that
# "can this reach a person?" is answerable by running one command instead of by waiting
# for a post-condition to fail. A delivery path that has never been exercised is an
# assumption, and the failure mode of an untested alert is silence.
cmd_test_alert() {
  local last
  if [[ -f "$STATUS" ]]; then
    last="$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print('audit: ok=%s failures=%s audit_sha=%s' % (d['ok'], d['failure_count'], d['audit_sha256']))" "$STATUS" 2>/dev/null)"
  else
    last="audit: unknown (no status file at $STATUS)"
  fi

  local rc=0
  deliver "[Camelot] TEST alert from $(hostname) - no action required" \
    "$(printf 'Delivery test for camelot-selfcheck-alert.service.\n\nIf you are reading this, the alert channel reaches a person.\nThis is a requested test; it describes nothing that is wrong.\n\nhost:        %s\nsent (UTC):  %s\n%s\n\nTo exercise the real path:  %s alert\n' \
      "$(hostname)" "$(date -u +%FT%TZ)" "$last" "$0")" \
    "test"

  # Submitting is not delivering. Read the MTA's own bounce report and say which happened,
  # because "sendmail exited 0" is exactly the kind of confident-but-unverified claim this
  # whole layer exists to eliminate — and it hid a channel that delivered nothing.
  if [[ -z "${CAMELOT_ALERT_EMAIL:-}" ]]; then
    log "test: CAMELOT_ALERT_EMAIL unset — this reached only the local mailbox on this host"
    return 0
  fi

  local wait="${CAMELOT_ALERT_VERIFY_WAIT:-25}" waited=0 bounce=2
  log "test: watching for a bounce naming ${CAMELOT_ALERT_EMAIL} (up to ${wait}s)"
  while (( waited < wait )); do
    python3 - "${CAMELOT_ALERT_EMAIL}" 2>/dev/null <<'PY'
import mailbox, sys
addr = sys.argv[1].lower()
try:
    box = mailbox.mbox("/var/mail/root")
except Exception:
    sys.exit(2)
for msg in box:
    if "Undelivered" not in (msg.get("Subject") or ""):
        continue
    text = msg.as_string().lower()
    if addr in text and "action: failed" in text:
        sys.exit(0)
for msg in box:
    if addr in (msg.get("To") or "").lower():
        sys.exit(3)
PY
    bounce=$?
    (( bounce == 0 )) && break
    sleep 5; waited=$((waited + 5))
  done

  case "$bounce" in
    0) log "test: DELIVERY FAILED — the MTA bounced mail for ${CAMELOT_ALERT_EMAIL}; see root's mailbox for the diagnostic"; rc=1 ;;
    3) log "test: DELIVERED (at least to this host's mailbox) for ${CAMELOT_ALERT_EMAIL}" ;;
    *) log "test: NO BOUNCE within ${wait}s — the MTA accepted the message. That is not proof of inbox arrival: check the spam folder, and prefer a channel that reports its own errors" ;;
  esac
  return "$rc"
}

case "${1:-}" in
  run)        cmd_run ;;
  alert)      cmd_alert ;;
  watchdog)   cmd_watchdog ;;
  test-alert) cmd_test_alert ;;
  *)          usage ;;
esac
