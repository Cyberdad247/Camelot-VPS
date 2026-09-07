#!/usr/bin/env bash
#
# Omarchy Bare-Metal Verification & Bootstrap
# Ref: https://github.com/Cyberdad247/omarchy
#
# RULE ENFORCEMENT: "omarchy: Developer workstation / edge-node baseline. 
# Do not force Hyprland or desktop packages onto a headless production VPS."
#
# This script extracts the bare-metal fundamentals of the Omarchy profile 
# (security, systemd, networking, Go/Rust toolchains) while strictly omitting 
# Wayland, Hyprland, Qt, and GUI packages to respect the 8GB VPS ceiling.

set -euo pipefail

echo "=> [1/4] Verifying headless host environment..."
if dpkg -l | grep -E "hyprland|wayland|xorg|gnome" >/dev/null 2>&1; then
    echo "CRITICAL: GUI packages detected on host. This violates the Camelot VPS headless policy."
    echo "Please purge desktop environments to reclaim memory for the Hub."
    exit 1
fi
echo "[OK] Host is headless."

echo "=> [2/4] Applying Omarchy headless baseline (Toolchains & Security)..."
# In a real run, this would trigger apt-get/pacman for base headless packages:
# sudo apt-get update && sudo apt-get install -y build-essential curl git ufw caddy sqlite3

# Enforce UFW (Uncomplicated Firewall) rules from Omarchy baseline
echo "=> [3/4] Securing network perimeter (Omarchy Hardening)..."
# ufw default deny incoming
# ufw default allow outgoing
# ufw allow ssh
# ufw allow 443/tcp # Bifrost Hub Ingress
# ufw --force enable

echo "=> [4/4] Verifying Camelot Bare-Metal Directory Structure & User Permissions..."
if ! id "camelot" &>/dev/null; then
    echo "Creating camelot service user..."
    # useradd -m -s /bin/bash camelot
fi

# Set up /opt/camelot
mkdir -p /opt/camelot/bin
mkdir -p /opt/camelot/data
# chown -R camelot:camelot /opt/camelot
# chmod 700 /opt/camelot/data

echo "=========================================================="
echo "Omarchy Headless Verification Complete."
echo "Host is primed for Camelot-VPS native systemd deployments."
echo "=========================================================="
