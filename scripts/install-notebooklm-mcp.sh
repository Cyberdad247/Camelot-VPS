#!/usr/bin/env bash
set -euo pipefail

VERSION="0.11.2"
PREFIX="${CAMELOT_NOTEBOOKLM_PREFIX:-/opt/camelot/notebooklm-mcp}"
STATE_DIR="${CAMELOT_NOTEBOOKLM_STATE_DIR:-/var/lib/camelot/notebooklm}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "install-notebooklm-mcp.sh must run as root" >&2
  exit 1
fi

id -u camelot-notebooklm >/dev/null 2>&1 || useradd --system --home-dir "${STATE_DIR}" --shell /usr/sbin/nologin camelot-notebooklm
getent group camelot >/dev/null 2>&1 || groupadd --system camelot
usermod -a -G camelot camelot-notebooklm

install -d -m 0755 "${PREFIX}"
install -d -o camelot-notebooklm -g camelot -m 0700 "${STATE_DIR}"

python3 -m venv "${PREFIX}"
"${PREFIX}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir --upgrade pip
"${PREFIX}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir "notebooklm-mcp-cli==${VERSION}"

installed="$(${PREFIX}/bin/python -c 'from importlib.metadata import version; print(version("notebooklm-mcp-cli"))')"
if [[ "${installed}" != "${VERSION}" ]]; then
  echo "NotebookLM MCP version mismatch: expected ${VERSION}, got ${installed}" >&2
  exit 1
fi

cat <<EOF
Installed notebooklm-mcp-cli ${VERSION} at ${PREFIX}.

Authentication is intentionally separate from service installation.
Run one of the documented bootstrap flows as camelot-notebooklm before enabling notebooklm-mcp.service.
EOF
