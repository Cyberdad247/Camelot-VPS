#!/usr/bin/env bash
# ============================================================================
# cb-supervise.sh — user-space service supervisor for the cloudbrain VPS stack
#
# Version: 1.0.0
#
# The `hermes` VPS user has no sudo and no systemd access, so supervision is
# done entirely in user space: this script is invoked from cron every minute
# and reconciles the stack to a healthy state.
#
#   * * * * * /opt/data/cloudbrain/bin/cb-supervise.sh reconcile \
#               >> /opt/data/cloudbrain/logs/supervise-cron.log 2>&1
#
# Design:
#   * Health-gated: a service is only (re)started when its health check
#     fails. Already-healthy services are left alone.
#   * After a start, the script waits up to START_TIMEOUT for the health
#     check to pass; if it never does, the just-started process is stopped
#     again and the failure is logged + alerted.
#   * Crash-loop backoff: restart timestamps are recorded per service; more
#     than MAX_RESTARTS (5) restarts inside RESTART_WINDOW_SEC (600s) refuses
#     further restarts and emits an ALERT line (hook point for ntfy).
#   * Concurrency-safe: a lockfile + flock(1) serialises all mutating runs.
#   * Structured log lines (UTC timestamp, service, event, outcome, detail)
#     go to ${LOG_DIR}/supervise.log.
#   * Dependency order for start-all / reconcile:
#         redis -> qdrant -> surrealdB -> openviking -> mesh broker -> anya
#     (reverse order for stop-all).
#
# Open Notebook is intentionally NOT managed here (paused per ground truth).
# No secrets are embedded anywhere: the SurrealDB env file is referenced by
# path only and sourced in a subshell at runtime on the VPS.
# ============================================================================

set -euo pipefail

CB_SUPERVISE_VERSION="1.0.0"

# ============================================================================
# CONFIG — every path, port and command for the stack lives here.
# All values are overridable from the environment (used by tests).
#
# Lines tagged  "# ASSUMPTION - verify on VPS"  were NOT confirmed in the
# ground-truth inventory. They MUST be checked on the host before trusting
# this supervisor in production.
# ============================================================================

CB_BASE="${CB_BASE:-/opt/data/cloudbrain}"
RUN_DIR="${RUN_DIR:-${CB_BASE}/run}"            # pidfiles, restart state, lock
LOG_DIR="${LOG_DIR:-${CB_BASE}/logs}"           # service logs + supervise.log
STATE_DIR="${STATE_DIR:-${RUN_DIR}}"
LOCK_FILE="${LOCK_FILE:-${RUN_DIR}/cb-supervise.lock}"
SUPERVISE_LOG="${SUPERVISE_LOG:-${LOG_DIR}/supervise.log}"

VENV_PY="${VENV_PY:-${CB_BASE}/venv/bin/python}"  # python for mesh + anya

START_TIMEOUT="${START_TIMEOUT:-60}"           # seconds to wait for healthy after start
STOP_TIMEOUT="${STOP_TIMEOUT:-15}"            # seconds to wait for graceful stop
MAX_RESTARTS="${MAX_RESTARTS:-5}"             # crash-loop guard: max restarts ...
RESTART_WINDOW_SEC="${RESTART_WINDOW_SEC:-600}"  # ... inside this window (10 min)

# --- redis 8.2.1 -------------------------------------------------------------
REDIS_BIN="${REDIS_BIN:-${CB_BASE}/bin/redis-server}"
REDIS_CONF="${REDIS_CONF:-${CB_BASE}/redis.conf}"
REDIS_CLI="${REDIS_CLI:-${CB_BASE}/bin/redis-cli}"  # ASSUMPTION - verify on VPS (falls back to PATH)
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_MATCH="${REDIS_MATCH:-redis-server}"          # pgrep -f fallback pattern

# --- qdrant 1.19.1 ------------------------------------------------------------
QDRANT_BIN="${QDRANT_BIN:-${CB_BASE}/bin/qdrant}"
# ASSUMPTION - verify on VPS: confirm qdrant binds 127.0.0.1:6333 and uses a
# persistent storage path; add flags via QDRANT_ARGS if needed.
QDRANT_ARGS="${QDRANT_ARGS:-}"                       # ASSUMPTION - verify on VPS
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_HEALTH_PATH="${QDRANT_HEALTH_PATH:-/}"
QDRANT_MATCH="${QDRANT_MATCH:-${CB_BASE}/bin/qdrant}"

# --- surrealdB 2.6.5 -----------------------------------------------------------
# ASSUMPTION - verify on VPS: surreal binary path and start args are unknown.
SURREALDB_BIN="${SURREALDB_BIN:-${CB_BASE}/bin/surrealdb}"                    # ASSUMPTION - verify on VPS
SURREALDB_ARGS="${SURREALDB_ARGS:-start --bind 127.0.0.1:8000 file:${CB_BASE}/data/surrealdb/open_notebook.db}"  # ASSUMPTION - verify on VPS
SURREALDB_ENV_FILE="${SURREALDB_ENV_FILE:-${CB_BASE}/open-notebook.env}"      # mode 600; referenced by path only, never embedded
SURREALDB_PORT="${SURREALDB_PORT:-8000}"
SURREALDB_HEALTH_PATH="${SURREALDB_HEALTH_PATH:-/health}"
SURREALDB_MATCH="${SURREALDB_MATCH:-surrealdb}"

# --- openviking 0.4.21 ----------------------------------------------------------
# ASSUMPTION - verify on VPS: the exact OpenViking start command is unknown.
OPENVKING_START_CMD="${OPENVKING_START_CMD:-${VENV_PY} -m openviking --host 127.0.0.1 --port 1933}"  # ASSUMPTION - verify on VPS
OPENVKING_PORT="${OPENVKING_PORT:-1933}"
OPENVKING_HEALTH_PATH="${OPENVKING_HEALTH_PATH:-/health}"
OPENVKING_MATCH="${OPENVKING_MATCH:-openviking}"

# --- mesh broker ----------------------------------------------------------------
MESH_PY="${MESH_PY:-${VENV_PY}}"
MESH_SCRIPT="${MESH_SCRIPT:-${CB_BASE}/handoff/mesh_broker.py}"
MESH_ARGS="${MESH_ARGS:-}"
MESH_PORT="${MESH_PORT:-8002}"
MESH_HEALTH_PATH="${MESH_HEALTH_PATH:-/health}"
MESH_MATCH="${MESH_MATCH:-mesh_broker.py}"

# --- anya omega -------------------------------------------------------------------
ANYA_PY="${ANYA_PY:-${VENV_PY}}"
ANYA_SCRIPT="${ANYA_SCRIPT:-${CB_BASE}/handoff/anya_omega.py}"
ANYA_ARGS="${ANYA_ARGS:-}"
ANYA_PORT="${ANYA_PORT:-8003}"
ANYA_HEALTH_PATH="${ANYA_HEALTH_PATH:-/health}"
ANYA_MATCH="${ANYA_MATCH:-anya_omega.py}"

# Dependency order for start-all / reconcile (reversed for stop-all).
START_ORDER="redis qdrant surrealdB openviking mesh anya"

# ============================================================================
# helpers
# ============================================================================

ensure_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR" "$STATE_DIR"
}

acquire_lock() {
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "cb-supervise: another instance is running (lock: $LOCK_FILE)" >&2
    exit 1
  fi
}

# log_event <svc> <event> <outcome> [detail]
log_event() {
  local svc="$1" event="$2" outcome="$3" detail="${4:-}"
  mkdir -p "$LOG_DIR"
  printf '%s svc=%s event=%s outcome=%s detail=%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$svc" "$event" "$outcome" "$detail" \
    >> "$SUPERVISE_LOG"
}

# emit_alert <svc> <message...>
# Prints an ALERT line to the supervise log and stderr. Wire the hook point
# below to the existing ntfy publisher for phone alerting.
emit_alert() {
  local svc="$1"
  shift
  local line
  line="$(date -u '+%Y-%m-%dT%H:%M:%SZ') ALERT svc=${svc} msg=$*"
  mkdir -p "$LOG_DIR"
  printf '%s\n' "$line" >> "$SUPERVISE_LOG"
  printf '%s\n' "$line" >&2
  # -- HOOK POINT: phone alerting ------------------------------------------------
  # Example wiring to the existing ntfy health publisher:
  #   : "${NTFY_PUBLISH:=/opt/data/scripts/cb-ntfy-publish.sh}"
  #   [ -x "$NTFY_PUBLISH" ] && printf '%s\n' "$line" | "$NTFY_PUBLISH" "cb-supervisor"
  # -----------------------------------------------------------------------------
}

pidfile_for() { printf '%s/%s.pid' "$RUN_DIR" "$1"; }

match_for() {
  case "$1" in
    redis)      printf '%s' "$REDIS_MATCH" ;;
    qdrant)     printf '%s' "$QDRANT_MATCH" ;;
    surrealdB)  printf '%s' "$SURREALDB_MATCH" ;;
    openviking) printf '%s' "$OPENVKING_MATCH" ;;
    mesh)       printf '%s' "$MESH_MATCH" ;;
    anya)       printf '%s' "$ANYA_MATCH" ;;
  esac
}

# ancestor_pids — PIDs on the chain above this supervisor (pure procfs, no ps
# dependency). Used so pgrep -f never mistakes a wrapper/parent process whose
# own command line happens to contain a service match pattern for the service.
ancestor_pids() {
  local pid="$$" ppid out=""
  while [ -r "/proc/$pid/status" ]; do
    ppid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null || true)"
    [ -n "$ppid" ] && [ "$ppid" != "0" ] || break
    out="${out}${out:+ }$ppid"
    [ "$ppid" = "1" ] && break
    pid="$ppid"
  done
  printf '%s' "$out"
}

# find_pids <svc> — pids whose command line matches the service pattern,
# excluding this supervisor and everything above it in the process tree.
find_pids() {
  local svc="$1" pat pid out="" ancestors
  pat="$(match_for "$svc")"
  [ -n "$pat" ] || return 0
  ancestors=" $$ $(ancestor_pids) "
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    case "$ancestors" in
      *" $pid "*) continue ;;
    esac
    out="${out}${out:+ }${pid}"
  done < <(pgrep -f "$pat" 2>/dev/null || true)
  printf '%s' "$out"
}

# pid_alive_for <pid> <svc> — true if pid is alive and looks like the service
# (guards against stale pidfiles whose PIDs were recycled).
pid_alive_for() {
  local pid="$1" svc="$2" pat cmdline
  kill -0 "$pid" 2>/dev/null || return 1
  [ -r "/proc/$pid/cmdline" ] || return 0  # no procfs: trust kill -0
  pat="$(match_for "$svc")"
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$cmdline" in
    *"$pat"*) return 0 ;;
    *) return 1 ;;
  esac
}

# pids_of <svc> — pidfile pid (validated) plus pgrep fallback, deduplicated.
pids_of() {
  local svc="$1" pf pid out="" p2
  pf="$(pidfile_for "$svc")"
  if [ -f "$pf" ]; then
    pid="$(tr -d '[:space:]' < "$pf" 2>/dev/null || true)"
    if [ -n "$pid" ] && pid_alive_for "$pid" "$svc"; then
      out="$pid"
    fi
  fi
  for p2 in $(find_pids "$svc"); do
    case " $out " in
      *" $p2 "*) ;;
      *) out="${out}${out:+ }$p2" ;;
    esac
  done
  printf '%s' "$out"
}

# ============================================================================
# health checks
# ============================================================================

http_healthy() {
  local port="$1" path="${2:-/}" code
  code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${port}${path}" 2>/dev/null || true)"
  [ "$code" = "200" ]
}

redis_healthy() {
  local cli="$REDIS_CLI" pong
  if [ ! -x "$cli" ]; then
    cli="$(command -v redis-cli 2>/dev/null || true)"  # PATH fallback
  fi
  [ -n "$cli" ] || return 1
  pong="$("$cli" -h 127.0.0.1 -p "$REDIS_PORT" PING 2>/dev/null || true)"
  [ "$pong" = "PONG" ]
}

service_healthy() {
  case "$1" in
    redis)      redis_healthy ;;
    qdrant)     http_healthy "$QDRANT_PORT" "$QDRANT_HEALTH_PATH" ;;
    surrealdB)  http_healthy "$SURREALDB_PORT" "$SURREALDB_HEALTH_PATH" ;;
    openviking) http_healthy "$OPENVKING_PORT" "$OPENVKING_HEALTH_PATH" ;;
    mesh)       http_healthy "$MESH_PORT" "$MESH_HEALTH_PATH" ;;
    anya)       http_healthy "$ANYA_PORT" "$ANYA_HEALTH_PATH" ;;
    *)          return 2 ;;
  esac
}

wait_for_healthy() {
  local svc="$1" timeout="$2" deadline
  deadline=$(( $(date +%s) + timeout ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if service_healthy "$svc"; then return 0; fi
    sleep 2
  done
  service_healthy "$svc"
}

# ============================================================================
# crash-loop backoff state
# ============================================================================

prune_restart_log() {
  local f="${STATE_DIR}/restarts-$1.log" now cutoff
  [ -f "$f" ] || return 0
  now="$(date +%s)"
  cutoff=$(( now - RESTART_WINDOW_SEC ))
  if awk -v c="$cutoff" 'NF && $1+0 >= c' "$f" > "${f}.tmp" 2>/dev/null; then
    mv "${f}.tmp" "$f"
  else
    rm -f "${f}.tmp"
  fi
}

restart_count() {
  local f="${STATE_DIR}/restarts-$1.log"
  if [ -f "$f" ]; then
    wc -l < "$f" | tr -d '[:space:]'
  else
    printf '0'
  fi
}

record_restart() {
  mkdir -p "$STATE_DIR"
  prune_restart_log "$1"
  date +%s >> "${STATE_DIR}/restarts-$1.log"
}

backoff_allows() {
  prune_restart_log "$1"
  [ "$(restart_count "$1")" -lt "$MAX_RESTARTS" ]
}

# ============================================================================
# process lifecycle
# ============================================================================

# launch_daemon <svc> <pidfile> <logfile> <cmd...>
launch_daemon() {
  local svc="$1" pidfile="$2" logfile="$3" pid
  shift 3
  mkdir -p "$(dirname "$logfile")" "$RUN_DIR"
  (
    # The daemon must NOT inherit the supervisor's lock fd: otherwise the
    # lock would stay held as long as any service lives, blocking every
    # later run (including cron reconcile).
    exec 9>&- 2>/dev/null || true
    # shellcheck disable=SC2086
    exec nohup "$@" >>"$logfile" 2>&1 < /dev/null
  ) &
  pid=$!
  disown "$pid" 2>/dev/null || true
  printf '%s\n' "$pid" > "$pidfile"
}

start_redis() {
  if [ ! -x "$REDIS_BIN" ]; then
    log_event "redis" "start" "failed" "not executable: $REDIS_BIN"
    return 1
  fi
  launch_daemon "redis" "$(pidfile_for redis)" "${LOG_DIR}/redis.log" \
    "$REDIS_BIN" "$REDIS_CONF"
}

start_qdrant() {
  if [ ! -x "$QDRANT_BIN" ]; then
    log_event "qdrant" "start" "failed" "not executable: $QDRANT_BIN"
    return 1
  fi
  # shellcheck disable=SC2086
  launch_daemon "qdrant" "$(pidfile_for qdrant)" "${LOG_DIR}/qdrant.log" \
    "$QDRANT_BIN" ${QDRANT_ARGS}
}

start_surrealdB() {
  if [ ! -x "$SURREALDB_BIN" ]; then
    log_event "surrealdB" "start" "failed" "not executable: $SURREALDB_BIN"
    return 1
  fi
  # Source the env file in a subshell so credentials never leak into the
  # supervisor's own environment or logs. Referenced by path only.
  (
    if [ -r "$SURREALDB_ENV_FILE" ]; then
      set -a
      # shellcheck disable=SC1090
      . "$SURREALDB_ENV_FILE"
      set +a
    else
      log_event "surrealdB" "start" "warning" "env file not readable: $SURREALDB_ENV_FILE"
    fi
    # shellcheck disable=SC2086
    launch_daemon "surrealdB" "$(pidfile_for surrealdB)" "${LOG_DIR}/surrealdB.log" \
      "$SURREALDB_BIN" ${SURREALDB_ARGS}
  )
}

start_openviking() {
  # shellcheck disable=SC2086
  launch_daemon "openviking" "$(pidfile_for openviking)" "${LOG_DIR}/openviking.log" \
    ${OPENVKING_START_CMD}
}

start_mesh() {
  if [ ! -x "$MESH_PY" ]; then
    log_event "mesh" "start" "failed" "no python: $MESH_PY"
    return 1
  fi
  if [ ! -f "$MESH_SCRIPT" ]; then
    log_event "mesh" "start" "failed" "missing: $MESH_SCRIPT"
    return 1
  fi
  # shellcheck disable=SC2086
  launch_daemon "mesh" "$(pidfile_for mesh)" "${LOG_DIR}/mesh.log" \
    "$MESH_PY" "$MESH_SCRIPT" ${MESH_ARGS}
}

start_anya() {
  if [ ! -x "$ANYA_PY" ]; then
    log_event "anya" "start" "failed" "no python: $ANYA_PY"
    return 1
  fi
  if [ ! -f "$ANYA_SCRIPT" ]; then
    log_event "anya" "start" "failed" "missing: $ANYA_SCRIPT"
    return 1
  fi
  # shellcheck disable=SC2086
  launch_daemon "anya" "$(pidfile_for anya)" "${LOG_DIR}/anya.log" \
    "$ANYA_PY" "$ANYA_SCRIPT" ${ANYA_ARGS}
}

# stop_service <svc> — best effort, always returns 0.
stop_service() {
  local svc="$1" pids pid remaining still deadline
  pids="$(pids_of "$svc")"
  if [ -z "$pids" ]; then
    rm -f "$(pidfile_for "$svc")"
    log_event "$svc" "stop" "ok" "not running"
    echo "$svc: not running"
    return 0
  fi
  for pid in $pids; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  deadline=$(( $(date +%s) + STOP_TIMEOUT ))
  remaining="$pids"
  while [ -n "$remaining" ] && [ "$(date +%s)" -lt "$deadline" ]; do
    still=""
    for pid in $remaining; do
      if kill -0 "$pid" 2>/dev/null; then still="${still}${still:+ }$pid"; fi
    done
    remaining="$still"
    [ -n "$remaining" ] && sleep 1
  done
  for pid in $remaining; do
    kill -KILL "$pid" 2>/dev/null || true
    log_event "$svc" "stop" "killed" "SIGKILL pid=$pid after ${STOP_TIMEOUT}s"
  done
  rm -f "$(pidfile_for "$svc")"
  log_event "$svc" "stop" "ok" "pids=$pids"
  echo "$svc: stopped"
  return 0
}

stop_service_quiet() {
  stop_service "$1" >/dev/null 2>&1 || true
}

# start_service <svc> — health-gated start with backoff and post-start check.
start_service() {
  local svc="$1" msg
  if service_healthy "$svc"; then
    log_event "$svc" "start" "skipped" "already healthy"
    echo "$svc: already healthy (not restarted)"
    return 0
  fi
  if ! backoff_allows "$svc"; then
    msg="crash-loop: ${MAX_RESTARTS} restarts within $(( RESTART_WINDOW_SEC / 60 )) min; refusing restart"
    log_event "$svc" "start" "refused" "$msg"
    emit_alert "$svc" "$msg"
    echo "$svc: REFUSED ($msg)" >&2
    return 1
  fi
  stop_service_quiet "$svc"   # clear any wedged process so the port is free
  record_restart "$svc"
  log_event "$svc" "start" "attempt" "launching"
  if ! "start_${svc}"; then
    msg="launcher error (see ${LOG_DIR}/${svc}.log)"
    log_event "$svc" "start" "failed" "$msg"
    emit_alert "$svc" "$msg"
    echo "$svc: FAILED ($msg)" >&2
    return 1
  fi
  if wait_for_healthy "$svc" "$START_TIMEOUT"; then
    log_event "$svc" "start" "ok" "healthy within ${START_TIMEOUT}s"
    echo "$svc: started and healthy"
    return 0
  fi
  stop_service_quiet "$svc"   # never became healthy: tear down what we started
  msg="failed to become healthy within ${START_TIMEOUT}s; stopped"
  log_event "$svc" "start" "failed" "$msg"
  emit_alert "$svc" "$msg"
  echo "$svc: FAILED ($msg)" >&2
  return 1
}

# svc_status <svc> — one status line; rc 0 = healthy, 1 = otherwise.
svc_status() {
  local svc="$1" pids state health restarts rc
  pids="$(pids_of "$svc")"
  if [ -n "$pids" ]; then state="running[$pids]"; else state="stopped"; fi
  restarts="$(restart_count "$svc")"
  if service_healthy "$svc"; then
    health="healthy"; rc=0
  else
    health="UNHEALTHY"; rc=1
  fi
  printf '%-10s %-24s %-9s restarts_10m=%s\n' "$svc" "$state" "$health" "$restarts"
  return "$rc"
}

# ============================================================================
# target expansion
# ============================================================================

expand_target() {
  case "${1:-all}" in
    all) printf '%s\n' "$START_ORDER" ;;
    redis|qdrant|surrealdB|openviking|mesh|anya) printf '%s\n' "$1" ;;
    *)
      echo "unknown service: $1 (choose one of: redis qdrant surrealdB openviking mesh anya, or 'all')" >&2
      return 1
      ;;
  esac
}

in_target() {
  case " $2 " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

reverse_order() {
  local out="" s
  for s in $START_ORDER; do
    out="$s${out:+ $out}"
  done
  printf '%s\n' "$out"
}

# ============================================================================
# CLI
# ============================================================================

usage() {
  cat <<'EOF'
Usage: cb-supervise.sh <command> [service|all]

Commands:
  start [svc|all]   Start services whose health check fails (dependency order).
  stop [svc|all]    Stop services (reverse dependency order).
  restart <svc>     Stop then start one service (or 'all' explicitly).
  status [svc|all]  Show running/health state per service (exit 1 if any unhealthy).
  reconcile         Start anything unhealthy, in dependency order (for cron).

Services (dependency order): redis qdrant surrealdB openviking mesh anya
Open Notebook is intentionally not managed (paused).

Cron (every minute):
  * * * * * /opt/data/cloudbrain/bin/cb-supervise.sh reconcile >> /opt/data/cloudbrain/logs/supervise-cron.log 2>&1
EOF
}

main() {
  local cmd="${1:-}" target="all" list svc fail=0
  if [ $# -ge 2 ]; then target="$2"; fi
  case "$cmd" in
    start)
      ensure_dirs; acquire_lock
      list="$(expand_target "$target")"
      for svc in $START_ORDER; do
        if in_target "$svc" "$list"; then start_service "$svc" || fail=1; fi
      done
      ;;
    stop)
      ensure_dirs; acquire_lock
      list="$(expand_target "$target")"
      for svc in $(reverse_order); do
        if in_target "$svc" "$list"; then stop_service "$svc" || fail=1; fi
      done
      ;;
    restart)
      if [ $# -lt 2 ]; then
        echo "restart requires a service name (or 'all')" >&2
        usage >&2
        exit 2
      fi
      ensure_dirs; acquire_lock
      if [ "$target" = "all" ]; then
        for svc in $(reverse_order); do stop_service "$svc" || fail=1; done
        for svc in $START_ORDER; do start_service "$svc" || fail=1; done
      else
        expand_target "$target" >/dev/null
        stop_service "$target"
        start_service "$target" || fail=1
      fi
      ;;
    status)
      ensure_dirs
      list="$(expand_target "$target")"
      for svc in $START_ORDER; do
        if in_target "$svc" "$list"; then svc_status "$svc" || fail=1; fi
      done
      ;;
    reconcile)
      ensure_dirs; acquire_lock
      for svc in $START_ORDER; do
        if ! service_healthy "$svc"; then
          log_event "$svc" "reconcile" "unhealthy" "attempting start"
          start_service "$svc" || fail=1
        fi
      done
      ;;
    ""|-h|--help|help)
      usage
      ;;
    *)
      echo "unknown command: $cmd" >&2
      usage >&2
      exit 2
      ;;
  esac
  exit "$fail"
}

main "$@"
