# Firewall & Port Policy Notes — Host Hardening (CB-013)

Companion: [`tls-notes.md`](./tls-notes.md) (CB-011) and [`Caddyfile`](./Caddyfile).
Control mapping (per `task.md`): **CB-013 → V-NET-001, V-NET-004**.

> Honest-scope statement up front: as the unprivileged `hermes` user
> (uid 10000, no sudo, no root) you **cannot** manage the host packet
> filter. There is no user-space workaround for iptables/nftables.
> Everything in §1 is therefore a **provider/host-root handoff** —
> exact rules to request, not commands you can run. Everything in §2 is
> what *can* be enforced without root, and it is already mostly in place.

## 0. Ground truth

- Debian 13 (trixie), x86_64; operator `hermes` uid/gid 10000; **no sudo**.
- File ops restricted to `/opt/data`; cannot bind ports < 1024.
- Cron jobs have no outbound DNS (Cloudflare DoH + `curl --resolve` works).
- Hermes dashboard/API: plain HTTP on the public interface (**launch-blocker
  #1**, fixed by CB-011 / tls-notes.md — this note assumes that cutover).
- Data-plane services are correctly loopback-bound today:
  Redis `127.0.0.1:6379`, Qdrant `127.0.0.1:6333/6334`,
  SurrealDB `127.0.0.1:8000`, OpenViking `127.0.0.1:1933`,
  mesh broker `127.0.0.1:8002`, Anya Omega `127.0.0.1:8003`.
- **No firewall commands are fabricated in this document.** Do not invent
  `iptables`/`nft` invocations as `hermes` — they will fail with
  `Operation not permitted`, and pretending otherwise is a finding, not a fix.

## 1. Provider/host-root handoff — exact rules to request (V-NET-004)

Send this verbatim to whoever holds host root (or the VPS provider's
firewall panel, if it offers one). Two variants; pick per the owner's
TLS decision (tls-notes.md §2).

### Variant A — Tailscale-only administration (RECOMMENDED)

Default-deny inbound; the ONLY inbound allowances are loopback (host-local),
established return traffic, and the tailnet interface. **No public allow
rules at all.**

```nftables
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;

        # Loopback is always free (V-NET-001: services talk to each other here).
        iifname "lo" accept

        # Return traffic for outbound connections we initiated
        # (package updates, DoH, ntfy, ACME/DNS-API, Tailscale control).
        ct state established,related accept
        ct state invalid drop

        # Tailscale interface: admin TLS + SSH from tailnet identities only.
        # (Finer-grained: restrict further with Tailscale ACLs, not here.)
        iifname "tailscale0" tcp dport { 443, 22 } accept

        # Everything else inbound is denied by the default-drop policy:
        # NO public 80/443, NO plaintext Hermes port, NO data-service ports.
    }
    chain forward { type filter hook forward priority 0; policy drop; }
    chain output  { type filter hook output priority 0; policy accept; }
}
```

### Variant B — public TLS ingress on :8443 (only if owner chooses option B)

Same as Variant A, plus exactly one public exception:

```nftables
        # Option-B ONLY: public HTTPS on the unprivileged Caddy port.
        tcp dport 8443 accept
```

Everything else stays denied. Explicitly still denied: public 80/443
(unusable by the unprivileged Caddy anyway), the old plaintext Hermes
port, and all data-service ports.

### Notes for host root / provider

- **Persist the ruleset** (`nft list ruleset > /etc/nftables.conf` or the
  distro equivalent, enabled at boot) — an unpersisted ruleset evaporates
  on reboot and silently re-opens the host.
- Keep **outbound 443/tcp open** (default-accept output above): cron jobs
  need Cloudflare DoH, ntfy, and (option B) DNS-provider API + ACME.
- If the provider offers a cloud firewall panel, implement the same
  policy there — defense in depth, and it protects the host even if the
  on-box ruleset is flushed.
- After applying, verify **from outside** (V-NET-004 evidence): port-scan
  the public IP and confirm only the intended ports answer
  (Variant A: none; Variant B: 8443 only).

## 2. What CAN be enforced without root

### 2.1 Loopback-only bindings (already in place — keep them)

Every data service binds `127.0.0.1` only. This is the single most
important no-root control: even with no host firewall at all, a
loopback-bound service is unreachable from the network. Guard it as a
standing invariant (V-NET-001).

**`ss -tlnp` verification checklist** (run on the VPS as `hermes`):

```bash
ss -tlnp
```

Expected result — every line's Local Address must be `127.0.0.1:<port>`
(or `::1` for IPv6 loopback). **Any sensitive service showing
`0.0.0.0:<port>` or `:::<port>` is a P0 finding**: rebind it to
loopback immediately and alert via ntfy.

| Service | Expected listener | Public? |
|---|---|---|
| Redis | `127.0.0.1:6379` | **never** |
| Qdrant REST | `127.0.0.1:6333` | **never** |
| Qdrant gRPC | `127.0.0.1:6334` | **never** |
| SurrealDB | `127.0.0.1:8000` | **never** |
| OpenViking | `127.0.0.1:1933` | **never** |
| Mesh broker | `127.0.0.1:8002` | **never** |
| Anya Omega | `127.0.0.1:8003` | **never** |
| Open Notebook backend (when up) | `127.0.0.1:<port>` | **never** |
| Hermes dashboard/API | `127.0.0.1:<hermes-port>` | **never directly** — reached via Caddy (loopback/tailnet) or `tailscale serve` |
| Caddy (Variant 1/3) | `127.0.0.1:8443` or `<tailnet-ip>:8443` | loopback/tailnet only |
| Caddy (Variant 2, option B only) | `0.0.0.0:8443` | **yes — the single deliberate exception** |

Shortcut check for drift (suitable for the ntfy health cron):

```bash
# Fail (and alert) if any LISTEN socket is on a non-loopback address
# other than the approved option-B exception.
ss -tlnH | awk '$4 !~ /^(127\.0\.0\.1|\[::1\]):/ {print}'
```

Tune the allowlist in the real script: under option A the output must be
empty; under option B it must contain only `0.0.0.0:8443`.

### 2.2 Hermes-level access controls (no root needed)

- Bind Hermes itself to `127.0.0.1:<hermes-port>`; the dashboard/API is
  then reachable only through the reverse proxy or tailnet.
- Restrict Hermes' `/api/pairing` and `/auth/native/*` surfaces per the
  gateway sync-readiness posture (approved devices only).
- The `/api/config` plaintext-password exposure stays remediated
  (tracked under CB-012) — verify it is not re-exposed after cutover.

### 2.3 Tailscale ACLs (control-plane firewall, no host root needed)

Under option A, tailnet ACLs in the admin console are the effective
firewall: allow only tagged admin devices → the VPS on the serve port,
deny everything else. Enforced by the coordination server; the host
packet filter is not involved.

### 2.4 Caddy-layer (L7) filtering

The `Caddyfile`'s `@scanners` matcher, 10 MB request-body cap, and
header hardening apply at Layer 7 with zero privileges. Not a
replacement for a packet filter, but it shrinks the reachable app
surface under option B.

### 2.5 Drift detection via the existing ntfy health checks

Extend `cb-ntfy-health` (or the cert-watch sibling) with the §2.1
`ss -tln` check: **any new non-loopback listener on a sensitive port =
immediate high-priority ntfy alert**. This is the no-root substitute
for firewall change-detection.

## 3. Control mapping (CB-013 → V-NET-001, V-NET-004)

| Control | Satisfied by |
|---|---|
| V-NET-001 | Approved port matrix above; loopback bindings verified via `ss -tlnp`; drift alert in ntfy health checks |
| V-NET-004 | Provider/host-root firewall handoff (§1, exact nftables ruleset for both TLS options); external scan evidence post-apply |
| CB-011 (adjacent) | TLS termination removes the plaintext admin surface — see tls-notes.md |

## 4. Constraints honored

- No fabricated firewall commands: nothing here is runnable as `hermes`
  against the host packet filter, and it does not pretend to be.
- No live VPS access used; no credentials handled.
- Placeholders only; real values stay on the VPS / in the provider panel.
- Staged under `cloudbrain/ops/tls/`; nothing else touched.
