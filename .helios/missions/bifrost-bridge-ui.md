# Sir Helios Mission — Bifrost Bridge Command Interface

## Development role
Sir Helios remains development-only. He orchestrates the engineering work but is not rendered in the product UI.

## Product owners inside the interface
- **Sir Hermes** — routing, dispatch, service discovery, message transformation, deep-link and tool handoff orchestration.
- **Sir Heimdall** — Bifrost gatekeeper: identity, integrity, intent, payload, access, audit, quarantine, and approval controls.

## Bridge realms
1. **Camelot-VPS** — sovereign host and command plane.
2. **Cyberdad247/Multivoice-router** — persona voice routing plus existing Bridge Proxy and Tailscale discovery APIs.
3. **Cyberdad247/gods-eye-view** — real-time geospatial/spatial-intelligence surface, live tracked entities, shareable view state and voice-driven globe operations.
4. **koala73/worldmonitor** — real-time global intelligence and OSINT via documented MCP/OpenAPI developer surfaces.

## Canonical transport contracts
- Multivoice health: `/api/health`
- Multivoice bridge relay: `/api/bridge/query`
- Multivoice bridge status: `/api/bridge/status/:ip`
- Multivoice Tailscale discovery: `/api/tailscale/devices`
- WorldMonitor MCP: `https://worldmonitor.app/mcp`
- God's Eye View: treat as a separately deployed spatial UI and handoff/deep-link target; do not duplicate or silently rewrite its renderer.

## UX objective
Create a visible Bifrost command interface where Hermes manages routes and Heimdall manages trust gates. The screen must make the bridge topology understandable at a glance, distinguish live/unknown/degraded states, show source→gate→destination flow, and avoid pretending mock telemetry is live.

## Safety and provenance
- No API keys in client code.
- No arbitrary open proxy behavior from the browser.
- Route mutation and remote execution require an explicit operator action.
- Clearly label simulated or unprobed status.
- Do not copy WorldMonitor source code into Camelot. Integrate via its published MCP/OpenAPI surface to preserve license boundaries.
