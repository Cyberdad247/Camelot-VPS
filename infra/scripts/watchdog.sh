#!/usr/bin/env bash
# Autonomous Triaging & Health Watchdog
# Monitors systemd services and memory slices, taking autonomous remediation actions.

set -euo pipefail

LOG_FILE="/var/log/camelot-watchdog.log"
CRITICAL_SERVICES=("bifrost" "receipt-service")

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

check_services() {
    for svc in "${CRITICAL_SERVICES[@]}"; do
        if ! systemctl is-active --quiet "$svc"; then
            log "WARNING: $svc is down. Attempting autonomous restart..."
            systemctl restart "$svc"
            sleep 2
            if systemctl is-active --quiet "$svc"; then
                log "SUCCESS: $svc recovered autonomously."
            else
                log "CRITICAL: $svc failed to recover."
                # Future: Webhook to Telegram / Admin alerting
            fi
        fi
    done
}

monitor_memory() {
    # Extract memory usage from cgroup slices
    local mem_critical=$(systemctl show camelot-critical.slice -p MemoryCurrent | cut -d= -f2)
    local mem_limit=$(systemctl show camelot-critical.slice -p MemoryHigh | cut -d= -f2)
    
    if [[ "$mem_critical" != "[not set]" && "$mem_limit" != "[not set]" ]]; then
        if (( mem_critical > (mem_limit * 90 / 100) )); then
            log "ALERT: camelot-critical.slice approaching 90% memory capacity. Engaging GC pressure."
            # Trigger aggressive GC or restart non-essential workers if applicable
        fi
    fi
}

log "Running watchdog checks..."
check_services
monitor_memory
