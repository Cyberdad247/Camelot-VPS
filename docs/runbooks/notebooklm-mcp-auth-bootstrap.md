# NotebookLM MCP Authentication Bootstrap Runbook

## Purpose

Authenticate the isolated `camelot-notebooklm` provider identity without exposing Google session material to Camelot authority services.

The NotebookLM/Gemini Notebook MCP package uses Google browser/session authentication and undocumented provider APIs. Its credentials are therefore treated as **external-provider credentials**, not Camelot authority credentials.

## Prerequisites

1. Install the pinned provider with `scripts/install-notebooklm-mcp.sh`.
2. Confirm `/var/lib/camelot/notebooklm` is owned by `camelot-notebooklm:camelot` and mode `0700`.
3. Keep `notebooklm-mcp.service` stopped during initial login.

## Preferred bootstrap

Run the provider CLI under the dedicated service identity with its isolated HOME:

```bash
sudo -u camelot-notebooklm \
  env HOME=/var/lib/camelot/notebooklm \
  /opt/camelot/notebooklm-mcp/bin/nlm login
```

On a headless VPS, use a reviewed manual-cookie bootstrap file rather than weakening the long-running service sandbox:

```bash
sudo -u camelot-notebooklm \
  env HOME=/var/lib/camelot/notebooklm \
  /opt/camelot/notebooklm-mcp/bin/nlm login --manual --file /secure/temporary/cookies.txt
```

Delete the temporary cookie file immediately after successful import.

## Verify authentication

```bash
sudo -u camelot-notebooklm \
  env HOME=/var/lib/camelot/notebooklm \
  /opt/camelot/notebooklm-mcp/bin/nlm login --check
```

Then start the sidecar and broker:

```bash
systemctl start notebooklm-mcp.service
curl --fail http://127.0.0.1:8484/health
systemctl start cloudbrain-broker.service
curl --fail http://127.0.0.1:3015/health/ready
```

## Refresh policy

The production sidecar sets `NOTEBOOKLM_HEADLESS_REAUTH=0`. It must not launch a browser from inside its hardened runtime sandbox.

When provider authentication expires:

1. Cloudbrain readiness becomes degraded/unavailable.
2. Existing Camelot authority services remain healthy.
3. No retrieval lease is converted into provider evidence until authentication is restored.
4. An operator runs the authentication refresh/bootstrap process outside the provider service.
5. Restart `notebooklm-mcp.service` and verify `/health` before returning Cloudbrain retrieval to service.

## Prohibited handling

Never place NotebookLM cookies, browser profiles, or Google credentials in:

- `VITE_*` variables
- Sentinel configuration
- Bifrost envelopes
- Ledger receipt bodies
- Context Packets
- VFS artifacts visible to ordinary Knights
- application logs
- GitHub Actions secrets for general Camelot builds

The provider profile under `/var/lib/camelot/notebooklm` is account-equivalent credential material and must be protected accordingly.
