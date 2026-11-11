# go_router — durable public deploy (option B)

The dashboard's live SSE features (knight banner, 3D avatar, MDX plan overlay)
need go_router reachable at a **stable public HTTPS URL**. The Cloudflare quick
tunnel is only an ephemeral demo (random URL, dies with the local process). This
makes it durable.

go_router's SSE hub is **in-memory and single-process**, so it must run as one
long-lived container — not on per-request serverless (a `/plan` POST to one
instance would never reach `/events` subscribers on another). Fly.io fits.

## Deploy (requires your Fly account — needs interactive auth)

```bash
cd control_plane/go_router
fly auth login                       # opens browser; one-time
fly launch --no-deploy --copy-config # reads fly.toml; pick/confirm app name + region
fly deploy                           # builds Dockerfile, runs one persistent machine
fly status                           # confirm the machine is running
```

This yields a stable URL like `https://camelot-go-router.fly.dev`.
Verify: `curl https://camelot-go-router.fly.dev/healthz`.

## Point the deployed dashboard at it

```bash
cd ../../02_FORGE/PORTAL_CORE/Anya_Dashboard
vercel env rm VITE_GO_ROUTER_URL production --yes
printf 'https://camelot-go-router.fly.dev' | vercel env add VITE_GO_ROUTER_URL production
vercel deploy --prod --yes
```

Now https://v0-project-crusade.vercel.app stays connected without your local
machine running. Fire plans/runes against the stable URL:

```bash
curl "https://camelot-go-router.fly.dev/plan?title=Deploy&content=%23%20Plan"
curl "https://camelot-go-router.fly.dev/rune?rune=ENGINEER&task=x"
```

## Notes
- CORS is permissive (`Access-Control-Allow-Origin: *`) so any origin can stream.
- Address binding precedence: explicit arg > `$PORT` (Fly injects it) > `:8077`.
- Other hosts work too (Railway/Render auto-detect the Dockerfile and inject
  `$PORT`); only the `vercel env` URL changes.
