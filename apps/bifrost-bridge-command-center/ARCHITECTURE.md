# Hermes + Heimdall Bifrost Architecture

```text
                            CAMELOT-VPS
                                │
                         operator intent
                                │
                         ┌──────▼──────┐
                         │ SIR HERMES  │
                         │ route forge │
                         └──────┬──────┘
                                │
                         proposed crossing
                                │
                    ┌───────────▼───────────┐
                    │     SIR HEIMDALL      │
                    │ identity  integrity   │
                    │ intent    payload     │
                    │ access               │
                    └───────────┬───────────┘
                                │ approved
                      ┌─────────┼─────────┐
                      │         │         │
              ┌───────▼───┐ ┌──▼──────┐ ┌▼────────────┐
              │Multivoice │ │God's Eye│ │WorldMonitor │
              │ voice     │ │ spatial │ │ MCP / OSINT │
              └───────────┘ └─────────┘ └─────────────┘
```

## Runtime placement

Bifrost now has two coupled surfaces:

- `apps/bifrost-bridge-command-center/` is the deep operator console and local gateway.
- `src/components/BifrostWorldTreePortal.tsx` is the contextual portal inside Camelot's World Tree experience.

The World Tree portal mounts into `#stratum-throne-room` with a React Portal. It is deliberately **not** a generic top-level dashboard tab. A compact Bifrost beacon appears only while the World Tree scroller exists and moves the operator directly to the Throne Room portal.

The intended spatial flow is:

```text
World Tree -> Throne Room -> Bifrost Portal -> Hermes Route -> Heimdall Gates -> External Realm
```

## Boundary rules

### Hermes
Hermes can construct a route, select an adapter, preserve crossing intent, and prepare an explicit realm handoff, but cannot override a Heimdall gate. A requested transport is treated as intent, not authority.

### Heimdall
Every crossing is fail-closed. Five gates are surfaced to the operator:

1. Identity
2. Integrity
3. Intent
4. Payload
5. Access

The bridge can also be sealed globally. A crossing is enabled only when all five gates are verified and Bifrost is open.

### Sir Helios
Sir Helios remains development-only. Helios may design, review, and evolve Bifrost through the Anti-Gravity engineering harness, but does not appear as a runtime control or persona inside the Bifrost interface.

### Gateway
`server.mjs` is intentionally small. It is not a service mesh and it is not a generic reverse proxy. Each remote realm gets a narrow adapter. Adding a new realm requires a source change.

The gateway additionally enforces an explicit browser-origin allowlist. `BIFROST_ALLOWED_ORIGINS` defaults to the local Camelot Vite origins and must not be replaced with a wildcard in production.

### Realm ownership
The Bifrost console orchestrates the other products; it does not absorb their rendering engines or source trees. This keeps the repositories independently deployable and makes provenance/licensing boundaries visible.

## Integrated realms

### Multivoice Router
Repository: `Cyberdad247/Multivoice-router`

Bifrost treats Multivoice as the persona/voice realm. The gateway verifies reachability and returns an explicit handoff. Remote persona or voice mutation is not proxied blindly from Camelot.

### God's Eye View
Repository: `Cyberdad247/gods-eye-view`

Bifrost treats God's Eye View as the spatial-intelligence realm. Its renderer remains authoritative for live globe state, tracked entities, sensor views, and spatial interaction. Camelot hands the operator into that surface instead of copying the renderer.

### WorldMonitor
Repository: `koala73/worldmonitor`

Bifrost uses WorldMonitor's published MCP boundary. The current adapter permits capability discovery (`tools/list`). Generic tool execution remains blocked until individual tool schemas, authentication, and Heimdall authorization policies are defined.

## Configuration

Camelot root UI:

```env
VITE_BIFROST_URL=http://127.0.0.1:4188
```

Bifrost gateway:

```env
BIFROST_HOST=127.0.0.1
BIFROST_PORT=4188
BIFROST_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
```

`VITE_BIFROST_URL` is a public browser address only. It must never contain credentials.

## Future hardening

Before enabling arbitrary WorldMonitor MCP tool execution or remote Multivoice mutations, add:

- per-tool capability policy
- explicit schema validation
- authenticated Camelot operator identity
- signed crossing receipts
- replay protection / nonce
- request rate limits
- structured audit persistence
- Tailscale identity binding where available
