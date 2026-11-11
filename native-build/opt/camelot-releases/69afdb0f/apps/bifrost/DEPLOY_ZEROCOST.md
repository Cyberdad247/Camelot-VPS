# Bifrost — Zero-Cost, No-Docker Deployment

Per the **Zero-Cost Law** and the **Microcubic VM Law**: no paid services, no
containers, no credit card. The gateway runs **natively on your machine**; the
public surface (if any) is provided by free, sovereign tooling.

## 1. Database — local SQLite (replaces Neon)

```bash
cp .env.example .env            # DATABASE_URL="file:./vault.db"
npm install
npx prisma generate
npx prisma migrate dev --name init   # creates apps/bifrost/prisma/vault.db
npm run start                   # gateway on :3001 with a local file DB
```

No account, no managed Postgres, no Docker. `vault.db` is gitignored. For a
heavier local setup, flip `provider` to `postgresql` in `prisma/schema.prisma`
and point `DATABASE_URL` at a native install (`scoop install postgresql`).

## 2. Gateway exposure — Tailscale Funnel (replaces Railway)

The gateway already enforces an HMAC webhook + (optionally) the Tailnet gate.
Expose it publicly over HTTPS for **$0** with Funnel — no server to rent:

```bash
# one-time: tailscale up   (free personal tailnet)
tailscale funnel 3001       # serves https://<machine>.<tailnet>.ts.net → :3001
# revoke with:  tailscale funnel reset
```

Keep `WEBHOOK_SECRET` strong — Funnel makes `/webhook/sms` reachable publicly, so
the HMAC check is the auth boundary. For LAN/Tailnet-only (zero public surface),
use `tailscale serve 3001` instead of `funnel`.

## 3. PWA — Cloudflare Pages / GitHub Pages (replaces Vercel)

Build the PWA and deploy the static output to a free static host:

- **Cloudflare Pages**: connect the repo, build command `npm run build`, output
  the PWA `dist/` — free tier, no card.
- **GitHub Pages**: push the built `dist/` to a `gh-pages` branch (e.g. via a
  GitHub Action) — free for public repos.

Point the PWA's gateway URL at the Funnel hostname from step 2.

## Cost summary

| Concern | Tool | Cost |
|---|---|---|
| Database | SQLite (local file) | $0 |
| Gateway host | your machine | $0 |
| Public HTTPS | Tailscale Funnel | $0 |
| PWA hosting | Cloudflare / GitHub Pages | $0 |
