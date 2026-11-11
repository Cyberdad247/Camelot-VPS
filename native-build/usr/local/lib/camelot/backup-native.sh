#!/bin/bash
# Native-build crown-jewel backup (P0-4, 2026-11-10). Successor to the
# container-era backup.sh (camelot-jewels, last ran 2026-10-31). One encrypted
# tarball in /opt/hermesagent/data/backups for off-box pickup. Keeps last 7.
# Secret VALUES ride inside the encrypted archive only; the staged manifest
# lists them by sha256.
set -eu
OUT_DIR=/opt/hermesagent/data/backups
PASS_FILE=/opt/hermesagent/data/backups/.backup-pass
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
{
  for f in /etc/camelot/mesh.env /opt/hermesagent/data/atom/atom.env \
           /opt/hermesagent/data/cloudbrain/bob/bob.key \
           /opt/hermesagent/data/cloudbrain/bob/tunnel.token \
           /opt/camelot-releases/69afdb0f/03_VAULT/security/warp_gates/keypasses.json; do
    [ -e "$f" ] && sha256sum "$f"
  done
} > "$TMP/SECRETS-SHA256.txt"
tar -czf "$TMP/camelot-native-$STAMP.tar.gz" \
  --exclude='opt/camelot-state/logs' \
  --exclude='opt/hermesagent/data/cloudbrain/bob/cloudflared' \
  --exclude='*.log' --exclude='*/__pycache__' \
  --exclude='root/.hermes/audio_cache' --exclude='root/.hermes/backups' \
  -C / \
  opt/camelot-state \
  opt/camelot-releases/69afdb0f/03_VAULT \
  opt/hermesagent/data/cloudbrain/bob \
  opt/hermesagent/data/atom/atom.env \
  etc/camelot/mesh.env \
  root/.hermes \
  usr/local/lib/camelot \
  etc/systemd/system/camelot-bifrost.service etc/systemd/system/camelot-edge-bus.service \
  etc/systemd/system/camelot-heimdall-bifrost.service etc/systemd/system/camelot-hermes-prime.service \
  etc/systemd/system/camelot-hermes-prime.timer etc/systemd/system/camelot-selfcheck.service \
  etc/systemd/system/camelot-selfcheck-watchdog.service etc/systemd/system/camelot-selfcheck-watchdog.timer \
  etc/systemd/system/camelot-selfcheck-alert.service etc/systemd/system/camelot-watchtower.service \
  etc/systemd/system/camelot-watchtower.timer etc/systemd/system/camelot-native-selfcheck.service \
  etc/systemd/system/camelot-native-selfcheck.timer etc/systemd/system/bob-gateway.service \
  etc/systemd/system/cloudflared-bob.service \
  -C "$TMP" SECRETS-SHA256.txt
openssl enc -aes-256-cbc -salt -pbkdf2 -pass "file:$PASS_FILE" \
  -in "$TMP/camelot-native-$STAMP.tar.gz" \
  -out "$OUT_DIR/camelot-native-$STAMP.tar.gz.enc"
ls -t "$OUT_DIR"/camelot-native-*.enc | tail -n +8 | xargs -r rm -f
echo "backup written: $OUT_DIR/camelot-native-$STAMP.tar.gz.enc ($(du -h "$OUT_DIR/camelot-native-$STAMP.tar.gz.enc" | cut -f1))"
