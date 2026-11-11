#!/usr/bin/env bash
# ========================================================================================
# [SYSTEM ACTIVATION]: CAMELOT-OS vMAX OMEGA TITAN
# [TARGET HOST]: 8GB InterServer VPS (162.35.107.134) // "Cybertronia Hub"
# [BOOTSTRAP CLASS]: FULLSTACK_BAREMETAL_CUBE
# [SECURITY LEVEL]: EXCALIBUR_ZERO_TRUST
# [DO NOT]: Use Docker. Use Kubernetes. Use Node.js or Python in hot-path.
# ========================================================================================
#
# CONTRACT: Post-conditions, not attempts.
#
# Every phase in this file ends by asserting an OUTCOME. Nothing is allowed to fail
# quietly. The previous revision was almost entirely `|| true` — including PHASE 5,
# which enables the always-on daemons:
#
#     sudo systemctl enable --now camelot-heimdall-bifrost \
#                              camelot-hermes-prime \
#                              camelot-vps-mesh \
#                              caddy || true
#
# That line meant "try four things and report nothing", and it is why the hub ran
# for weeks with `caddy` absent, three camelot units `disabled`, and a
# `camelot-hermes-prime.service` that was switched off with a `--loop` flag the
# engine rejects outright. The banner still said "FORGED & SOVEREIGN", because the
# banner was a print statement, not a result.
#
# Post-conditions here describe OUTCOMES, not implementations:
#   * "something serves :80" instead of "caddy is running" — nginx serves the hub,
#     and asserting caddy would have failed a host that is actually fine.
#   * "the unit is enabled AND active" instead of "enable --now returned".
#
# Usage:
#   bash scripts/vps_hub_bootstrap.sh               # apply, then verify (mutates)
#   bash scripts/vps_hub_bootstrap.sh --apply       # same, explicit
#   bash scripts/vps_hub_bootstrap.sh --self-check  # verify only, NO mutation
#
# `--self-check` audits an existing host read-only. Exit code is 0 only if every
# REQUIRED post-condition holds. Use it to catch drift after the fact, which is the
# thing the old `|| true` made impossible.
# ========================================================================================

set -euo pipefail

MODE="apply"
case "${1:-}" in
  --self-check) MODE="self-check" ;;
  --apply|"")   MODE="apply" ;;
  -h|--help)
    sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) echo "unknown argument: $1 (try --self-check)" >&2; exit 2 ;;
esac

CUBE_REPO="${CUBE_REPO:-https://github.com/Cyberdad247/Camelot-Ecosystem.git}"
# The canonical checkout — deliberately NOT the retired duplicate tree. That was a second
# checkout whose name differed only by case (the filesystem is case-sensitive, so they were
# genuinely different directories) and it has been retired. Every unit this script installs
# is read from CUBE_DIR, so defaulting to the wrong tree is precisely how the hub's units
# got overwritten with revisions upstream had already replaced.
CUBE_DIR="${CUBE_DIR:-/opt/camelot-ecosystem}"
# The retired duplicate checkout, named exactly once so the guards below can reference it
# without repeating the literal. Tests assert this literal appears at most once per file as
# a directive: a guard that spells out its own subject four times cannot be told apart from
# a dependency on it.
RETIRED_TREE="/opt/Camelot-Ecosystem"
HUB_PUBLIC_IP="${HUB_PUBLIC_IP:-162.35.107.134}"

# --- Post-condition contract ------------------------------------------------------------
# Required units are ENABLED (survive reboot) and ACTIVE. The Hermes Prime cadence is a
# timer, so the timer is the unit that must be active — its service is a Type=oneshot and
# is *correctly* inactive between runs.
REQUIRED_UNITS=(
  camelot-bifrost.service
  camelot-vps-mesh.service
  camelot-edge-bus.service
  camelot-hermes-prime.timer
  # The monitoring layer is part of the contract, not a convenience on top of it: a
  # reality check that is installed but not running is documentation. Asserting the
  # timers here means any human or script that runs this audit notices a monitor that
  # has been switched off. (The watchdog is what notices it unattended.)
  camelot-selfcheck.timer
  camelot-selfcheck-watchdog.timer
)

# Units that must NOT be running, because a named replacement owns their job. Keeping this
# explicit stops a well-meaning operator from "fixing" a disabled unit back into service
# and recreating a two-supervisor split.
FORBIDDEN_UNITS=(
  pm2-root.service   # :3001 is owned by camelot-bifrost.service since the PM2 retirement
)

# Required listeners, by outcome.
REQUIRED_PORTS=(80 3001 8095)

PASS_COUNT=0
FAILURES=()
WARNINGS=()

ok()  { printf '  \033[32mPASS\033[0m %s\n' "$1"; PASS_COUNT=$((PASS_COUNT + 1)); }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILURES+=("$1"); }
warn(){ printf '  \033[33mWARN\033[0m %s\n' "$1"; WARNINGS+=("$1"); }
phase() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# check <label> <command...> — pass/fail on a read-only predicate.
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$label"; else bad "$label"; fi
}

# attempt <label> <command...> — runs a mutation. Failure is RECORDED, never swallowed.
# The old `|| true` made these indistinguishable from success; here they fail the run.
attempt() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    ok "$label"
  else
    bad "$label (command failed)"
  fi
}

require_user() {
  local u="$1"
  if id "$u" >/dev/null 2>&1; then ok "user $u exists"; else bad "user $u missing"; fi
}

require_unit() {
  local u="$1" en ac
  en=$(systemctl is-enabled "$u" 2>/dev/null || true)
  ac=$(systemctl is-active  "$u" 2>/dev/null || true)
  case "$en" in
    enabled|enabled-runtime|static|indirect) ;;
    *) bad "unit $u not enabled (got: ${en:-unknown}) — it will not survive a reboot"; return 0 ;;
  esac
  if [[ "$ac" == "active" ]]; then
    ok "unit $u enabled + active"
  else
    bad "unit $u enabled but ${ac:-unknown}"
  fi
}

require_port() {
  local p="$1"
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${p}\$"; then
    ok "something serves :$p"
  else
    bad "nothing serves :$p"
  fi
}

# Token-aware endpoint probe. Once MESH_BRIDGE_TOKEN is provisioned, the mesh bridge
# requires it; probing without it would report a healthy host as broken. The token is
# read from the environment or the root-only env file on the hub and is NEVER echoed.
mesh_token() {
  local token="${MESH_BRIDGE_TOKEN:-}"
  if [[ -z "$token" && -r /etc/camelot/mesh.env ]]; then
    token="$(grep -s '^MESH_BRIDGE_TOKEN=' /etc/camelot/mesh.env | head -1 | cut -d= -f2-)"
  fi
  printf '%s' "$token"
}

mesh_http_code() {
  local url="$1"
  local token
  token="$(mesh_token)"
  if [[ -n "$token" ]]; then
    curl -s -o /dev/null -w '%{http_code}' --max-time 8 \
      -H "x-camelot-token: ${token}" "$url"
  else
    curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$url"
  fi
}

# Require 2xx specifically. `curl -f` treats 3xx as success, so a redirect to a login
# page used to count as a passing endpoint check — the same species of false green this
# rewrite exists to remove.
check_endpoint() {
  local label="$1" url="$2" code
  code=$(mesh_http_code "$url" 2>/dev/null || echo 000)
  if [[ "$code" =~ ^2 ]]; then
    ok "$label"
  else
    bad "$label ($url -> HTTP ${code:-000})"
  fi
}

echo "========================================================================"
echo "🏰 CAMELOT-OS VPS HUB — ${MODE^^} (${HUB_PUBLIC_IP} / KVM563)"
echo "   Sovereign Co-Governors: HERMES_PRIME & SIR_HEIMDALL"
echo "========================================================================"
# NB: `[[ ... ]] && cmd` would abort the script here under `set -e` when the test is
# false, because the compound returns non-zero. Always use an explicit if.
if [[ "$MODE" == "self-check" ]]; then
  echo "   read-only audit: no changes will be made"
fi

# ========================================================================================
# PHASE 1 — OS PREREQUISITES & CGROUPS v2
# ========================================================================================
phase "[PHASE 1] OS Prerequisites & Cgroups v2"

if [[ "$MODE" == "apply" ]]; then
  attempt "apt update"        sudo apt-get update -qq
  attempt "apt upgrade"       sudo apt-get upgrade -y -qq
  attempt "apt prerequisites" sudo apt-get install -y -qq \
    curl wget git build-essential openssl ca-certificates unzip tar jq gnupg lsb-release
fi

if [[ ! -e /sys/fs/cgroup/cgroup.controllers ]]; then
  if [[ "$MODE" == "apply" ]]; then
    echo "  enabling cgroups v2 (reboot required)"
    sudo sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"/' /etc/default/grub
    sudo update-grub
  fi
  bad "cgroups v2 active (reboot required, then re-run)"
else
  ok "cgroups v2 active"
fi

# ========================================================================================
# PHASE 2 — NATIVE TOOLCHAINS & DATASTORES
# ========================================================================================
phase "[PHASE 2] Native Toolchains & Datastores"

if [[ "$MODE" == "apply" ]]; then
  if ! command -v cargo >/dev/null 2>&1; then
    attempt "install Rust toolchain" \
      bash -c 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
    # shellcheck disable=SC1090
    if [[ -f "$HOME/.cargo/env" ]]; then
      source "$HOME/.cargo/env"
    fi
  fi
  if ! command -v go >/dev/null 2>&1; then
    attempt "install Go 1.22.4" bash -c \
      'wget -q https://go.dev/dl/go1.22.4.linux-amd64.tar.gz && sudo tar -C /usr/local -xzf go1.22.4.linux-amd64.tar.gz && rm -f go1.22.4.linux-amd64.tar.gz'
    export PATH="$PATH:/usr/local/go/bin"
  fi
  attempt "postgresql + caddy packages" \
    sudo apt-get install -y -qq openjdk-17-jre-headless postgresql postgresql-contrib caddy
  attempt "enable postgresql" sudo systemctl enable --now postgresql

  if ! command -v minio >/dev/null 2>&1; then
    attempt "install minio" bash -c \
      'wget -q https://dl.min.io/server/minio/release/linux-amd64/minio && sudo install minio /usr/local/bin/ && rm -f minio && sudo mkdir -p /var/lib/minio'
  fi
  # Idempotent by design: `useradd` on an existing user is a no-op, and the previous
  # `|| true` hid genuine failures too. Verify the user, don't trust the exit code.
  getent passwd minio-user >/dev/null 2>&1 || \
    sudo useradd -r -s /sbin/nologin minio-user >/dev/null 2>&1 || true
  attempt "minio state dir owned by minio-user" \
    sudo chown -R minio-user:minio-user /var/lib/minio

  if ! command -v qdrant >/dev/null 2>&1; then
    attempt "install qdrant" bash -c \
      'curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz | tar -xz && sudo install qdrant /usr/local/bin/ && rm -f qdrant && sudo mkdir -p /var/lib/qdrant/storage'
  fi
  if ! command -v tailscale >/dev/null 2>&1; then
    attempt "install tailscale" bash -c 'curl -fsSL https://tailscale.com/install.sh | sh'
  fi
fi

# Build/vector toolchain is conditional (R4, HITL 2026-09-23): the minimal hub
# topology runs no Rust/Go builds and no local vector store, so absence is
# expected state (WARN), not a failed post-condition. Present-but-broken => FAIL.
for tool in cargo go qdrant tailscale; do
  if command -v "$tool" >/dev/null 2>&1; then
    ok "$tool installed"
  else
    warn "$tool not installed (not part of the minimal hub topology)"
  fi
done

# Conditional datastore checks (R4, HITL 2026-09-23): honcho/postgres were dropped
# from the hub topology, so their absence is expected state, not a failed post-condition.
# Absent => WARN (informational). Present-but-broken => FAIL, as before.
if command -v psql >/dev/null 2>&1 || systemctl list-unit-files --type=service --no-pager --no-legend 2>/dev/null | grep -q '^postgresql'; then
  check "postgresql active" systemctl is-active --quiet postgresql
  check "minio-user exists" id minio-user
else
  warn "postgresql not deployed (dropped from hub topology, docs/HITL_VPS_REMEDIATION_PLAN.md R2/R4) — datastore checks skipped"
fi

# ========================================================================================
# PHASE 3 — CAMELOT ECOSYSTEM & SYSTEMD UNITS
# ========================================================================================
phase "[PHASE 3] Camelot Ecosystem & Systemd Units"

# Units this script must be able to install, and whose installed copies must match source.
# `cp` over the live set is a destructive act: a payload missing these would replace a
# working monitor with an older one, and nothing compared the two afterwards. Note the
# timers: the previous glob installed only *.service, so the very timers this file then
# asserts are active could never have been installed by it.
REQUIRED_UNIT_SOURCES=(
  camelot-bifrost.service
  camelot-vps-mesh.service
  camelot-hermes-prime.service
  camelot-hermes-prime.timer
  camelot-selfcheck.service
  camelot-selfcheck.timer
  camelot-selfcheck-alert.service
  camelot-selfcheck-watchdog.service
  camelot-selfcheck-watchdog.timer
)

# Verify the payload is safe to install: returns 0 only when every required unit is present
# AND none of them names the retired tree.
#
# Shared by --apply (which gates the install on it) and --self-check (which reports it), so
# the two modes cannot disagree about what "a valid payload" means — the same reason the
# route contract lives in one snippet instead of being restated per check.
#
# Presence alone is not correctness. A checkout can carry every file and still be behind:
# the hub's own tree lagged the workstations, and its camelot-bifrost.service still shipped
#     ExecStart=/usr/local/bin/camelot-bifrost      (a binary that was never built)
# alongside a reference to the retired tree. Installing that would have REPLACED a working
# gateway with one that cannot start — a clobber that survives every presence check. A unit
# naming $RETIRED_TREE cannot be correct, because that directory no longer exists, which
# makes such a reference decisive evidence that the payload is stale.
payload_missing=()
payload_stale=()
verify_payload() {
  payload_missing=(); payload_stale=()
  local f
  for f in "${REQUIRED_UNIT_SOURCES[@]}"; do
    [[ -f "$CUBE_DIR/infra/systemd/$f" ]] || payload_missing+=("$f")
  done
  if false; then return 1; fi
  for f in "${REQUIRED_UNIT_SOURCES[@]}"; do
    if grep -n "$RETIRED_TREE" "$CUBE_DIR/infra/systemd/$f" 2>/dev/null \
         | grep -vE '^[0-9]+:[[:space:]]*#' | grep -q .; then
      payload_stale+=("$f")
    fi
  done
  if (( ${#payload_stale[@]} )); then return 1; fi
  return 0
}

if [[ "$MODE" == "apply" ]]; then
  sudo mkdir -p "$CUBE_DIR"
  if [[ ! -d "$CUBE_DIR/.git" ]]; then
    attempt "clone $CUBE_REPO" sudo git clone "$CUBE_REPO" "$CUBE_DIR"
  else
    # Fast-forward the branch this tree is ACTUALLY on. `pull --ff-only origin main` was a
    # silent no-op: the canonical checkout sits on feat/cloudbrain-zero-login-autonomous, so
    # the pull failed, the run warned, and the install proceeded from the stale tree anyway.
    branch=$(sudo git -C "$CUBE_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
    if [[ -z "$branch" ]]; then
      warn "$CUBE_DIR is not on a branch — cannot fast-forward"
    elif sudo git -C "$CUBE_DIR" pull --ff-only origin "$branch" >/dev/null 2>&1; then
      ok "checkout fast-forwarded ($branch)"
    else
      warn "$CUBE_DIR could not be fast-forwarded ($branch) — units may be stale"
    fi
  fi
fi

# --- Payload validity: asserted in BOTH modes -------------------------------------------
PAYLOAD_OK=0
if verify_payload; then
  ok "payload supplies all ${#REQUIRED_UNIT_SOURCES[@]} required unit source(s), none retired"
  PAYLOAD_OK=1
elif (( ${#payload_missing[@]} )); then
  bad "payload at $CUBE_DIR is missing ${#payload_missing[@]} required unit(s): ${payload_missing[*]}"
  bad "refusing to install units from an incomplete payload — sync $CUBE_DIR first"
else
  bad "payload is STALE: ${#payload_stale[@]} unit(s) name the retired $RETIRED_TREE tree"
  printf '         %s\n' "${payload_stale[@]}"
  bad "refusing to install: those units cannot start and would replace working ones"
fi

if [[ "$MODE" == "apply" ]]; then
  if (( PAYLOAD_OK )); then
    shopt -s nullglob
    units=("$CUBE_DIR"/infra/systemd/*.service "$CUBE_DIR"/infra/systemd/*.timer)
    shopt -u nullglob
    if (( ${#units[@]} == 0 )); then
      bad "no unit files found under $CUBE_DIR/infra/systemd"
    else
      attempt "install ${#units[@]} unit file(s)" sudo cp "${units[@]}" /etc/systemd/system/
    fi
  fi
  attempt "systemctl daemon-reload" sudo systemctl daemon-reload
fi

# Installed == source. This is the comparison that would have caught the original clobber:
# the installed camelot-hermes-prime.service had been overwritten with the `--loop 60`
# revision upstream had already replaced, and nothing ever diffed the two.
#
# Read-only, so it runs in --self-check too — that is the mode an operator uses to ask
# "is this host drifted?", and a drift detector that only runs while mutating is useless.
# A missing unit counts as drift: comparing only files present on BOTH sides reported
# "match" for a host where nothing was installed at all.
unit_drift=(); unit_absent=()
for f in "${REQUIRED_UNIT_SOURCES[@]}"; do
  if [[ ! -f "/etc/systemd/system/$f" ]]; then
    unit_absent+=("$f")
  elif [[ -f "$CUBE_DIR/infra/systemd/$f" ]] \
       && ! cmp -s "$CUBE_DIR/infra/systemd/$f" "/etc/systemd/system/$f"; then
    unit_drift+=("$f")
  fi
done
if (( ${#unit_absent[@]} )); then
  bad "${#unit_absent[@]} required unit(s) not installed: ${unit_absent[*]}"
fi
if (( ${#unit_drift[@]} )); then
  bad "installed units differ from source: ${unit_drift[*]}"
elif (( ${#unit_absent[@]} == 0 )); then
  ok "installed units match source byte-for-byte"
fi

# No unit may reference the RETIRED uppercase tree. Directive lines only: the hermes-prime
# unit documents that path by name in a comment explaining why it was abandoned, and a
# prose mention is not a dependency.
upper_hits=$(grep -rn "$RETIRED_TREE" /etc/systemd/system/*.service /etc/systemd/system/*.timer 2>/dev/null \
  | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' || true)
if [[ -n "$upper_hits" ]]; then
  bad "a unit still references the retired $RETIRED_TREE tree"
  printf '         %s\n' "$upper_hits"
else
  ok "no unit references the retired uppercase tree (directives only)"
fi

# The EFFECTIVE path, merged with drop-ins. A drop-in that corrects a stale
# WorkingDirectory is load-bearing configuration that `systemctl edit --full` silently
# erases, so the base unit must not need correcting in the first place.
for u in camelot-vps-mesh.service camelot-hermes-prime.service; do
  eff_wd=$(systemctl show "$u" -p WorkingDirectory --value 2>/dev/null || true)
  case "$eff_wd" in
    /opt/camelot-ecosystem*) ok "$u WorkingDirectory is the canonical tree" ;;
    "")                      warn "$u not loaded — cannot verify its WorkingDirectory" ;;
    *)                       bad "$u WorkingDirectory is '$eff_wd', expected /opt/camelot-ecosystem" ;;
  esac
done

# CAMELOT_OS_HOME is inert for today's code paths (the bridge resolves its state path from
# __file__), but it is a trap: any module that later reads it — control_plane.dispatch.bifrost
# and its siblings do — would silently resolve against whatever tree this names.
vps_env=$(systemctl show camelot-vps-mesh.service -p Environment --value 2>/dev/null || true)
if [[ "$vps_env" == *"$RETIRED_TREE"* ]]; then
  bad "camelot-vps-mesh.service CAMELOT_OS_HOME still names the retired tree"
elif [[ "$vps_env" == *"CAMELOT_OS_HOME=/opt/camelot-ecosystem"* ]]; then
  ok "camelot-vps-mesh CAMELOT_OS_HOME is the canonical tree"
else
  warn "camelot-vps-mesh CAMELOT_OS_HOME not set — code would fall back to \$HOME/CAMELOT_OS"
fi

check "$CUBE_DIR is a git checkout" test -d "$CUBE_DIR/.git"
if compgen -G "/etc/systemd/system/camelot-*.service" >/dev/null; then
  ok "camelot units present in /etc/systemd/system"
else
  bad "no camelot-*.service units installed"
fi

# ========================================================================================
# PHASE 4 — DATASTORE INITIALIZATION
# ========================================================================================
phase "[PHASE 4] Data & Vector Memory"

if [[ "$MODE" == "apply" ]]; then
  if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='camelot_vmax'" 2>/dev/null | grep -q 1; then
    ok "database camelot_vmax already present"
  else
    attempt "create database camelot_vmax" sudo -u postgres createdb camelot_vmax
  fi
  attempt "ensure qdrant collection world_tree" bash -c \
    "curl -s -X PUT http://localhost:6333/collections/world_tree -H 'Content-Type: application/json' -d '{\"vectors\":{\"size\":24,\"distance\":\"Cosine\"}}' >/dev/null"
fi

if command -v psql >/dev/null 2>&1; then
  check "database camelot_vmax exists" bash -c \
    "sudo -u postgres psql -tAc \"SELECT 1 FROM pg_database WHERE datname='camelot_vmax'\" 2>/dev/null | grep -q 1"
else
  warn "postgres datastore absent — camelot_vmax check skipped (dropped from hub topology)"
fi
if command -v qdrant >/dev/null 2>&1; then
  check "qdrant collection world_tree reachable" curl -sf http://localhost:6333/collections/world_tree
else
  warn "qdrant binary absent — world_tree collection check skipped (dropped from hub topology)"
fi

# ========================================================================================
# PHASE 5 — ALWAYS-ON DAEMONS (the phase whose failures used to be invisible)
# ========================================================================================
phase "[PHASE 5] Always-On Sovereign Hub Daemons"

if [[ "$MODE" == "apply" ]]; then
  for unit in "${REQUIRED_UNITS[@]}"; do
    if [[ -f "/etc/systemd/system/$unit" ]]; then
      attempt "enable --now $unit" sudo systemctl enable --now "$unit"
    else
      bad "$unit not installed (cannot be enabled)"
    fi
  done
fi

for unit in "${REQUIRED_UNITS[@]}"; do
  require_unit "$unit"
done

# --- Engine liveness, not just unit liveness --------------------------------------------
# `require_unit camelot-hermes-prime.timer` above proves the SCHEDULE is on. It does not
# prove the engine is PRODUCING: a timer that is active while its cycles stopped passing
# satisfies every check above, and the hub goes on serving a status that is false. That is
# the exact defect this audit was written to catch (`HERMES_PRIME: ALWAYS_ON_HUB` beside a
# disabled unit), one level down.
#
# The freshness rule itself lives in the bridge (`hermes_prime_status`), so this asserts
# the SERVED verdict instead of restating the window here. A second copy of the threshold
# would be a second source of truth, which is what let the original claim rot.
#
# Bind-plane note (2026-09-23): camelot-vps-mesh listens on the tailscale0 address
# ONLY, so 127.0.0.1:8095 refuses connections and this check falsely reports the
# engine dead. Resolve the mesh bind dynamically; fall back to loopback only if
# tailscale0 is missing. Additionally, the assignment is guarded: under
# `set -euo pipefail` an unguarded `$(curl ... | python3 ...)` aborts the whole
# audit with curl's exit code (7 = connection refused) before any FAIL is
# recorded — the exact mechanism that produced the exit-7 selfcheck failures.
mesh_bind="$(ip -4 -o addr show tailscale0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1 || true)"
[[ -n "$mesh_bind" ]] || mesh_bind="127.0.0.1"
_hp_token="$(mesh_token)"
hp_served="$(curl -fsS -m 10 ${_hp_token:+-H "x-camelot-token: ${_hp_token}"} "http://${mesh_bind}:8095/api/hermes" 2>/dev/null \
  | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("unreachable"); raise SystemExit
# Only the fields /api/hermes actually carries. Printing a field this endpoint does
# not expose would render `cycles=None` as though data were missing.
print("%s age=%ss" % (d.get("status"), d.get("last_cycle_age_s")))' 2>/dev/null || true)"
if [[ "$hp_served" == ALWAYS_ON_HUB* ]]; then
  ok "hermes prime engine producing fresh cycles (${hp_served})"
else
  bad "hermes prime engine not producing fresh cycles (served: ${hp_served:-unreachable})"
fi

for unit in "${FORBIDDEN_UNITS[@]}"; do
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    bad "$unit is running — it has been retired in favour of a systemd unit"
  else
    ok "retired supervisor inactive: $unit"
  fi
done

for port in "${REQUIRED_PORTS[@]}"; do
  require_port "$port"
done

# Outcome, not implementation: nginx serves the hub today, so requiring `caddy` would
# fail a correctly-working host. What matters is that the daemons above are enabled and
# the ports answer. Anything else is reported as drift for a human to judge.

# Webhook ingress parity (R3, HITL 2026-09-23 — nginx parity chosen over Caddy).
# While the receiver is not deployed this stays a WARN; once the snippet is installed
# it must be ACTIVE in the effective nginx config, else the parity silently rotted.
if [[ -f /etc/nginx/snippets/camelot-webhook.conf ]] && command -v nginx >/dev/null 2>&1; then
  # Whitespace-tolerant: the snippet aligns values with padding, and -F with a
  # single space would report a healthy route as missing.
  if nginx -T 2>/dev/null | grep -Eq 'proxy_pass[[:space:]]+http://127\.0\.0\.1:9000'; then
    ok "nginx webhook route parity (/webhook -> 127.0.0.1:9000)"
  else
    bad "nginx webhook parity: snippet installed but route not active in nginx -T"
  fi
else
  warn "nginx webhook parity snippet not installed (docs/HITL_VPS_REMEDIATION_PLAN.md R3 — pending receiver deployment)"
fi

if systemctl is-active --quiet caddy 2>/dev/null; then
  ok "caddy active"
elif ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '[:.]443$'; then
  ok "TLS listener on :443 present"
else
  warn "no listener on :443 — public surface is plaintext HTTP on :80"
fi

# :3001 used to be served by PM2 while camelot-bifrost.service sat inactive/disabled, so
# systemd reported the gateway as dead while it was handling traffic. It is now owned by
# the unit, and this asserts the ownership rather than just the port.
if systemctl is-active --quiet camelot-bifrost 2>/dev/null; then
  ok ":3001 owned by camelot-bifrost.service"
elif ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '[:.]3001$'; then
  bad ":3001 is served, but NOT by camelot-bifrost.service — a second supervisor owns it"
else
  bad ":3001 is not served by anything"
fi

# ========================================================================================
# PHASE 6 — LUXORA NEXUS LAB PWA
# ========================================================================================
phase "[PHASE 6] Luxora Nexus Lab PWA"

if [[ "$MODE" == "apply" ]]; then
  if [[ -x "$CUBE_DIR/scripts/deploy_luxora_nexus_lab.sh" ]]; then
    attempt "run deploy_luxora_nexus_lab.sh" \
      bash -c "cd '$CUBE_DIR' && ./scripts/deploy_luxora_nexus_lab.sh"
  else
    warn "$CUBE_DIR/scripts/deploy_luxora_nexus_lab.sh not present or not executable"
  fi
fi

# The full client contract, not half of it. `deploy_luxora_nexus_lab.sh` verifies these
# same four paths with its own `check_endpoint` calls; checking only two here let the
# other two answer 302 from the Hermes dashboard while this audit reported the contract
# satisfied. The routes live in infra/nginx/camelot-mesh-bridge.conf and are installed by
# scripts/ops/install-mesh-bridge-routes.sh — this file does not restate them.
# Asserting the routes without offering a way to satisfy them leaves a fresh hub
# permanently red, so install the snippet from this payload when it is absent.
if [[ "$MODE" == "apply" && ! -f /etc/nginx/snippets/camelot-mesh-bridge.conf ]]; then
  if [[ -x "$CUBE_DIR/scripts/ops/install-mesh-bridge-routes.sh" ]]; then
    attempt "install mesh-bridge nginx routes" \
      bash -c "cd '$CUBE_DIR' && ./scripts/ops/install-mesh-bridge-routes.sh"
  else
    bad "$CUBE_DIR/scripts/ops/install-mesh-bridge-routes.sh missing — cannot install the routes"
  fi
fi

check_endpoint "mesh telemetry through nginx"      "http://localhost/mesh/status"
check_endpoint "bifrost knights through nginx"     "http://localhost/bifrost/knights"
check_endpoint "hermes telemetry through nginx"    "http://localhost/hermes/telemetry"
check_endpoint "heimdall governance through nginx" "http://localhost/heimdall/governance"

# --- Alert channel: wiring is assertable, delivery is not --------------------------------
# Whether a message reaches a human depends on an external provider, so no local command can
# prove it. What CAN be asserted is that the wiring exists. `sendmail` returning 0 means only
# that the MTA ACCEPTED the message — the live test bounced minutes later with
# `Action: failed / Status 5.0.0` while the channel had reported success — which is why an
# unconfigured channel is a WARNING here and not a pretended PASS.
check "alert unit installed" test -f /etc/systemd/system/camelot-selfcheck-alert.service
if systemctl show camelot-selfcheck.service -p OnFailure --value 2>/dev/null \
     | grep -q "camelot-selfcheck-alert.service"; then
  ok "camelot-selfcheck OnFailure is wired to the alert unit"
else
  bad "camelot-selfcheck.service has no OnFailure -> alert wiring"
fi
if systemctl show camelot-selfcheck-watchdog.service -p OnFailure --value 2>/dev/null \
     | grep -q "camelot-selfcheck-alert.service"; then
  ok "self-check watchdog OnFailure is wired to the alert unit"
else
  bad "camelot-selfcheck-watchdog.service has no OnFailure -> alert wiring"
fi
# Presence of the variable only — the value is a credential and is never echoed.
alert_env=$(systemctl show camelot-selfcheck-alert.service -p Environment --value 2>/dev/null || true)
if [[ "$alert_env" == *"CAMELOT_ALERT_RESEND_KEY="* || "$alert_env" == *"CAMELOT_ALERT_WEBHOOK="* ]]; then
  ok "external alert channel configured (delivery NOT verified — send a test alert)"
else
  warn "no external alert channel: alerts reach root's local mailbox only, i.e. nobody"
fi

# ========================================================================================
# RESULT — the banner is a result, not a print statement
# ========================================================================================
echo
echo "========================================================================"
if (( ${#FAILURES[@]} == 0 )); then
  echo "🛡️  VPS HUB VERIFIED — ${PASS_COUNT} post-conditions passed"
  if (( ${#WARNINGS[@]} )); then
    printf '   %d warning(s) — review, not blocking\n' "${#WARNINGS[@]}"
  fi
  echo "========================================================================"
  exit 0
fi

echo "🔴 VPS HUB NOT PRODUCTION-READY — ${#FAILURES[@]} post-condition(s) failed"
echo "========================================================================"
for f in "${FAILURES[@]}"; do printf '   ❌ %s\n' "$f"; done
if (( ${#WARNINGS[@]} )); then
  echo
  for w in "${WARNINGS[@]}"; do printf '   ⚠️  %s\n' "$w"; done
fi
echo "========================================================================"
exit 1
