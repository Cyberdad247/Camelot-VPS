# TLS Termination Notes — Hermes Dashboard/API (CB-011)

Companion config: [`Caddyfile`](./Caddyfile).
Control mapping (per `task.md`): **CB-011 → V-NET-003, V-TLS-001, V-WEB-001**.
Firewall/port-policy work is **CB-013** — see [`firewall-notes.md`](./firewall-notes.md).

> All hostnames, IPs (beyond the known `162.35.107.134` and loopback), and
> credentials below are **placeholders**. Nothing was run against the live
> VPS for this note — local forging only, no network, no credentials.

## 0. Ground truth (launch-blocker #1)

- The Hermes dashboard/API is **plain HTTP on the public Internet**.
- Data-plane services are correctly loopback-only and must stay that way:
  Redis `127.0.0.1:6379`, Qdrant `127.0.0.1:6333/6334`,
  SurrealDB `127.0.0.1:8000`, OpenViking `127.0.0.1:1933`,
  mesh broker `127.0.0.1:8002`, Anya Omega `127.0.0.1:8003`.
- Operator user is `hermes` (uid 10000): **no sudo, no root** → cannot bind
  ports < 1024, cannot touch iptables/nftables, file ops restricted to
  `/opt/data`. Cron jobs have no outbound DNS except Cloudflare DoH +
  `curl --resolve`.
- **Open owner decision:** (A) Tailscale-only administration vs
  (B) public TLS ingress via reverse proxy. This note presents both and
  recommends A. Do not implement B unilaterally.

## 1. User-space Caddy install + run procedure (option B path)

Everything below runs as `hermes`, no privileges required.

### 1.1 Fetch the binary (no outbound DNS in cron — but interactive shells work)

The known-good trick on this host is Cloudflare DoH + `curl --resolve`
(the same pattern already used for ntfy). From an **interactive shell**
(normal DNS is fine there):

```bash
# Placeholders: replace with the real Caddy v2 release asset URL.
mkdir -p /opt/data/cloudbrain/bin
cd /opt/data/cloudbrain/bin
curl -L -o caddy.tar.gz \
  "https://github.com/caddyserver/caddy/releases/download/v2.10.0/caddy_2.10.0_linux_amd64.tar.gz"
tar xzf caddy.tar.gz caddy && rm caddy.tar.gz
chmod +x caddy
./caddy version   # sanity check
```

> **DNS-01 caveat:** stock Caddy builds do NOT include DNS-provider
> modules. If you need the DNS-01 challenge (you do, for option B — see
> §1.3), you need a custom build with your provider's module. The
> standard route is `xcaddy build --with github.com/caddy-dns/<provider>`
> (e.g. `caddy-dns/cloudflare`). That build step happens on a machine
> with Go — build it locally and copy the binary up, or run `xcaddy`
> on the VPS if Go is available. Do NOT put provider API tokens in the
> Caddyfile; pass them via environment (`CLOUDFLARE_API_TOKEN=…`) from a
> root-readable-only file or the process environment, never in a
> world-readable config.

### 1.2 Layout

| Path | Purpose |
|---|---|
| `/opt/data/cloudbrain/bin/caddy` | static binary |
| `/opt/data/cloudbrain/caddy/Caddyfile` | this repo's `Caddyfile`, with TODOs filled in |
| `/opt/data/cloudbrain/caddy/data/` | ACME state (account keys, cert cache) — back up |
| `/opt/data/cloudbrain/caddy/logs/` | sanitized access logs (see Caddyfile) |

```bash
mkdir -p /opt/data/cloudbrain/caddy/logs
cp /path/to/this/Caddyfile /opt/data/cloudbrain/caddy/Caddyfile
# Edit TODOs: <public-hostname>, <acme-email>, <hermes-port>.
# Validate before starting:
/opt/data/cloudbrain/bin/caddy validate --config /opt/data/cloudbrain/caddy/Caddyfile --adapter caddyfile
```

### 1.3 Why DNS-01 is the only viable ACME path here

- **HTTP-01** requires answering on port **80** → impossible for the
  unprivileged `hermes` user.
- **TLS-ALPN-01** requires port **443** → same blocker.
- **DNS-01** requires only outbound HTTPS to your DNS provider's API to
  publish `_acme-challenge` TXT records → works fine in user space.
  Trade-off: needs a custom Caddy build with the provider module and a
  scoped API token (DNS-edit only) for the zone.

### 1.4 Run (unprivileged, port 8443)

```bash
# Foreground first, to watch for config errors:
/opt/data/cloudbrain/bin/caddy run --config /opt/data/cloudbrain/caddy/Caddyfile --adapter caddyfile
# Then detach (or hand to the supervisor pattern — see below):
/opt/data/cloudbrain/bin/caddy start --config /opt/data/cloudbrain/caddy/Caddyfile --adapter caddyfile
```

Supervision: there is no systemd user instance guaranteed on this host.
Fold Caddy into the **existing every-minute watchdog-cron pattern**
(`cb-mesh-broker-watch`, `cb-anya-watch`): a `cb-caddy-watch` cron that
`curl -sk https://127.0.0.1:8443/healthz` (or the tailnet URL) and
restarts Caddy if the check fails, with ntfy alert on restart. Keep the
watchdog script under `/opt/data/scripts/` with the others.

### 1.5 Cutover checklist (option B)

1. Caddy validated + running on `:8443` (Variant 2 uncommented in the
   Caddyfile; Variant 1 commented out or kept on loopback only).
2. `curl -sI https://<public-hostname>:8443/` → 200 + HSTS header.
3. Cert expiry sane:
   `echo | openssl s_client -connect <public-hostname>:8443 -servername <public-hostname> 2>/dev/null | openssl x509 -noout -dates`
4. Plaintext Hermes port unreachable from the public Internet
   (provider firewall handoff — firewall-notes.md).
5. **Credential rotation** performed (§5) — sessions/tokens that ever
   crossed plain HTTP are burned.
6. Old plain-HTTP bookmarks/URLs replaced everywhere.

## 2. Why Tailscale-only (option A) is recommended

| Concern | Option A: Tailscale-only | Option B: public TLS on :8443 |
|---|---|---|
| Public attack surface | **None.** Nothing Hermes-related listens on the public interface. | A TLS port is world-reachable; scanners, exploit kits, and 0-days in the proxy/app are now your problem. |
| Privileged ports | None needed (userspace-networking mode). | Works around with :8443, but port 80/443 stay unusable; operators must bookmark a non-standard port. |
| Certificates | Automatic Tailscale-issued certs, auto-renewed, no ACME config. | Let's Encrypt via DNS-01: needs a custom Caddy build + DNS-provider API token (new secret to guard). |
| Client requirement | Tailscale on each admin device (already the architecture recommendation). | Any browser — convenient, but convenience is the threat. |
| Firewall dependency | Tailscale ACLs enforce access (control plane, no host firewall needed). Default-deny inbound can omit ALL public allows. | Requires the provider to open 8443 and you to trust the proxy config is flawless. |
| Break-glass | Independent path retained (console/SSH per CB-010 evidence). | Same, but break-glass over public TLS is weaker. |

**Recommendation: option A.** It eliminates the public surface entirely,
needs no privileged ports, no ACME/DNS-01 machinery, and no provider
firewall exception — which matters because the `hermes` user cannot manage
the host firewall anyway. Option B remains documented (Variant 2 in the
Caddyfile) for the owner to choose deliberately, e.g. if admin devices
cannot run Tailscale.

### What changes if the owner picks public TLS (option B) instead

1. Uncomment **Variant 2** (and the HTTP→HTTPS redirector) in the
   Caddyfile; fill in `<public-hostname>`, `<acme-email>`.
2. Build/obtain a Caddy binary with the DNS-provider module; create a
   **scoped** DNS API token (TXT-record edit on the one zone only).
3. File the **provider firewall request** (firewall-notes.md): allow
   inbound TCP 8443 only; everything else denied.
4. Run the **cutover checklist** (§1.5) and the **credential rotation**
   (§5). Steps 3–4 are launch-blocking: public TLS without them is
   theater.
5. Enable the **renewal monitor** (§4) — Let's Encrypt certs are 90-day.

## 3. Option A detail — Tailscale userspace + serve (preferred)

```bash
# 1. Install the Tailscale client as hermes; userspace networking needs no TUN/root:
tailscaled --tun=userspace-networking --state=/opt/data/cloudbrain/tailscale/state &
tailscale up            # complete login in the admin console
tailscale status        # note the VPS tailnet name, e.g. hermes.example.ts.net
tailscale ip -4         # <tailnet-ip>, e.g. 100.x.y.z — for the Caddyfile bind

# 2a. Simplest: let Tailscale terminate TLS (certs auto-issued + renewed):
tailscale serve --https=443 --bg http://127.0.0.1:<hermes-port>
# 2b. Or: Tailscale → Caddy (this repo's Variant 3) → Hermes, to keep
#     Caddy's header hardening, scanner blocking, size limits, sanitized logs:
tailscale serve --https=443 --bg https://127.0.0.1:8443
```

Then in the **Tailscale admin console ACLs**: allow only tagged admin
devices → the VPS on the serve port; deny everything else. Tailnet ACLs
are enforced by the coordination server — no host firewall needed.

Supervision: `tailscaled` must stay up — add it to the watchdog-cron
pattern (`cb-tailscale-watch`) alongside the Caddy/mesh/Anya watchers.

Verification (V-NET-003 / V-TLS-001):
- From an enrolled admin device: `curl -sI https://<vps-tailnet-name>/`
  → 200 over TLS, HSTS present.
- From outside the tailnet: nothing on the public interface
  (connection refused on all previously-public ports).
- `tailscale serve status` shows the HTTPS serve config active.

## 4. Certificate renewal monitoring hook (ntfy pattern)

Caddy auto-renews Let's Encrypt certs and reloads with zero downtime —
**but only while Caddy is running**, and renewal can still fail (DNS API
token revoked, zone moved, rate limits). The existing `cb-ntfy-health`
cron already publishes to a private ntfy topic; extend it (or add a daily
sibling job `cb-cert-watch`) with this check:

```bash
#!/bin/bash
# /opt/data/scripts/cb-cert-watch.sh — daily cert-expiry + renewal check
HOST="<public-hostname>"   # or <vps-tailnet-name> for option A
PORT="8443"
WARN_DAYS=21               # alert while there's still time to fix DNS-01
TOPIC_FILE="/opt/data/scripts/.ntfy-topic"   # same private topic as cb-ntfy-health

expiry=$(echo | openssl s_client -connect "${HOST}:${PORT}" -servername "${HOST}" 2>/dev/null \
         | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
[ -z "$expiry" ] && { echo "CERT CHECK FAILED: no cert presented by ${HOST}:${PORT}"; exit 2; }
exp_epoch=$(date -d "$expiry" +%s); now_epoch=$(date +%s)
days_left=$(( (exp_epoch - now_epoch) / 86400 ))
if [ "$days_left" -lt "$WARN_DAYS" ]; then
  echo "CERT WARNING: ${HOST}:${PORT} expires in ${days_left}d (${expiry})"
  exit 1
fi
echo "CERT OK: ${days_left}d remaining"
```

Cron: daily (e.g. `17 6 * * * /opt/data/scripts/cb-cert-watch.sh`).
Alerting follows the existing pattern: non-zero exit → publish a
high-priority ntfy message to the private topic (same DoH +
`curl --resolve` trick the health script already uses); dedupe via a
state file so a failing renewal doesn't spam every day. For option A
(Tailscale serve) this check is belt-and-braces — Tailscale renews its
own certs — but it still catches "tailscaled died" scenarios.

Also monitor: Caddy's ACME errors appear in its process log
(`journalctl`-less here — redirect `caddy run` output to
`/opt/data/cloudbrain/caddy/logs/caddy.log` in the watchdog start
command and grep it for `acme.*error` in the same daily job).

## 5. Credential-rotation warning (pairs with the Hermes rotation task)

**Anything that previously crossed plain HTTP must be treated as
exposed.** Passive capture on the path is trivially possible; assume
compromise, not possibility.

1. Invalidate **all** existing Hermes web sessions (force logout).
2. Rotate the Hermes admin password. Standing practice remains: **fresh
   password login every session, never stored** (per alignment notes).
3. Rotate any API tokens/keys ever used against the plaintext URL.
4. Verify Hermes sets cookies with `Secure; HttpOnly; SameSite=Lax`
   (or `Strict`) — Caddy cannot add these flags itself.
5. Review auth logs for use inconsistent with the operator's own
   sessions (sanitized review — no credential values in notes).
6. **Do NOT record real credential values** in staging files, logs, or
   memory — placeholders/metadata only.

> The actual rotation needs fresh auth and is **NOT** this task's work —
> it pairs with the separate Hermes credential-rotation task (CB-012).
> This note only defines the trigger (TLS cutover) and the scope.

## 6. Verification summary (CB-011)

| Check | Command | Expect |
|---|---|---|
| TLS up (V-TLS-001) | `curl -sI https://<host>:8443/ \| head -5` | 200, HSTS header |
| HSTS (V-WEB-001) | `curl -skI https://<host>:8443/ \| grep -i strict-transport` | `max-age=31536000…` |
| Plaintext dead publicly (V-NET-003) | `curl -s http://<host>:<old-plaintext-port>/` from outside | refused/timeout |
| Cert expiry | `openssl s_client … \| openssl x509 -noout -dates` | > 21 days |
| Loopback discipline (CB-013/V-NET-001) | `ss -tlnp` (see firewall-notes.md) | no sensitive port on `0.0.0.0`/`::` |

## 7. Constraints honored

- No live VPS access used; no credentials handled.
- Placeholders only for hostnames, IPs, ports, emails, tokens.
- Files staged under `cloudbrain/ops/tls/`; nothing else touched.
