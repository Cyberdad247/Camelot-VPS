# Bifrost Bridge Command Center

Visible operator UI for **Sir Hermes** and **Sir Heimdall**. Sir Helios remains development-only and is not rendered here.

## Roles

- **Sir Hermes** owns routing, dispatch, transport selection, realm handoff, and crossing intent.
- **Sir Heimdall** owns the five crossing gates: identity, integrity, intent, payload, and access. The bridge fails closed when any gate is blocked or when the bridge is sealed.

## Integrated realms

### Camelot-VPS
The sovereign origin and command plane.

### Multivoice-router
Repository: `https://github.com/Cyberdad247/Multivoice-router`

The current Multivoice server already exposes:
- `GET /api/health`
- `POST /api/bridge/query`
- `GET /api/bridge/status/:ip`
- `GET /api/tailscale/devices`
- persona/RAG/voice APIs

The Bifrost gateway deliberately does **not** expose Multivoice's generic bridge proxy to the browser. It health-checks the configured Multivoice deployment and hands the operator into that surface for explicit voice/persona actions.

### God's Eye View
Repository: `https://github.com/Cyberdad247/gods-eye-view`

Treated as the spatial-intelligence realm. It remains a separately deployed renderer with its own 3D globe, live tracked entities, voice controls, and shareable view state. Bifrost probes it and performs an explicit UI handoff instead of copying or embedding its renderer.

### WorldMonitor
Repository: `https://github.com/koala73/worldmonitor`

Uses the documented MCP transport at:

`https://worldmonitor.app/mcp`

The current implementation performs a safe `tools/list` capability discovery when an MCP crossing is requested. Tool execution is intentionally not generic because each tool has its own schema and may require authorization.

## Run

```bash
cd apps/bifrost-bridge-command-center
npm run check
npm run dev
```

Open:

`http://127.0.0.1:4188`

Optional configuration:

```bash
BIFROST_PORT=4188
BIFROST_HOST=127.0.0.1
MULTIVOICE_BASE_URL=https://obsidian-spire-hud.vercel.app
GODS_EYE_BASE_URL=https://maptheworld.ai
WORLDMONITOR_BASE_URL=https://worldmonitor.app
```

## Security model

The gateway is an allowlisted adapter, **not an open proxy**.

- Remote targets are defined server-side.
- The browser cannot submit arbitrary hosts or URLs.
- Request bodies are capped.
- Secrets are never stored in the UI.
- Remote mutation is not performed by a status probe.
- UI handoffs require an explicit operator confirmation.
- WorldMonitor integration uses its public developer surface rather than copying source into Camelot.

## Current implementation boundary

This is a working command-center app and orchestration gateway, but it is not yet mounted as a tab inside the root Camelot React shell. Keeping it isolated makes the bridge testable before it is grafted into the primary World Tree UI.
