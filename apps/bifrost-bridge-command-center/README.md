# Bifrost Bridge Command Center

Visible operator experience for **Sir Hermes** and **Sir Heimdall**. Sir Helios remains development-only and is not rendered here.

## Primary experience: scrolling UI

Bifrost is now designed as a **continuous scrolling journey inside the Camelot World Tree**, not a modal, dashboard tab, or single control panel.

The World Tree sequence continues through seven Bifrost chapters:

1. **Bifrost Threshold** — entry into the bridge layer.
2. **Sir Hermes** — route discovery, realm probes, and transport selection.
3. **Sir Heimdall** — interactive five-gate fail-closed authorization.
4. **Multivoice Router** — voice/persona realm transition.
5. **God's Eye View** — spatial-intelligence realm transition.
6. **WorldMonitor** — global-intelligence / MCP realm transition.
7. **Crossing Chamber** — final governed route authorization and explicit handoff.

Each chapter occupies most of the viewport, participates in scroll tracking, and exposes a persistent desktop chapter navigator. The interface uses depth, orbital motion, sticky context, large typography, and staged realm transitions so scrolling represents movement through Bifrost rather than a sequence of dashboard cards.

## Roles

- **Sir Hermes** owns routing, dispatch, transport selection, realm handoff, and crossing intent.
- **Sir Heimdall** owns the five crossing gates: identity, integrity, intent, payload, and access. The bridge fails closed when any gate is blocked or when the bridge is sealed.

## Integrated realms

### Camelot-VPS
The sovereign origin and command plane.

### Multivoice-router
Repository: `https://github.com/Cyberdad247/Multivoice-router`

The current Multivoice server already exposes health, bridge, Tailscale, persona/RAG, and voice APIs. Bifrost does not expose its generic bridge proxy directly to the browser. It probes the configured deployment and preserves explicit operator control for voice/persona mutations.

### God's Eye View
Repository: `https://github.com/Cyberdad247/gods-eye-view`

Treated as the spatial-intelligence realm. It remains a separately deployed renderer with its own 3D globe, live tracked entities, voice controls, and shareable view state. Bifrost performs an explicit handoff instead of copying or embedding its renderer.

### WorldMonitor
Repository: `https://github.com/koala73/worldmonitor`

Uses the documented MCP transport at `https://worldmonitor.app/mcp`. The current adapter performs a safe `tools/list` capability discovery. Generic tool execution remains disabled until per-tool authorization and schemas are implemented.

## Gateway

```bash
cd apps/bifrost-bridge-command-center
npm run check
npm run dev
```

The gateway listens on `http://127.0.0.1:4188` by default.

For the root Camelot React UI:

```bash
VITE_BIFROST_URL=http://127.0.0.1:4188
```

Allowed local origins are configured with:

```bash
BIFROST_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
```

## Security model

The gateway is an allowlisted adapter, **not an open proxy**.

- Remote targets are defined server-side.
- The browser cannot submit arbitrary hosts or URLs.
- Request bodies are capped.
- Secrets are never stored in the UI.
- Remote mutation is not performed by a status probe.
- UI handoffs require an explicit operator action.
- WorldMonitor integration uses its public developer surface rather than copying source into Camelot.

## Architectural invariant

**Helios develops Camelot. Hermes routes Bifrost. Heimdall guards Bifrost.**
