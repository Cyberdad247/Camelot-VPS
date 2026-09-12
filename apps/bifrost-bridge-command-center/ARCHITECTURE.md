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

## Boundary rules

### Hermes
Hermes can construct a route and select an adapter, but cannot override a Heimdall gate. A requested transport is treated as intent, not authority.

### Heimdall
Every crossing is fail-closed. The current UI exposes the five conceptual gates and the gateway enforces the harder network boundary with a server-side destination allowlist.

### Gateway
`server.mjs` is intentionally small. It is not a service mesh and it is not a generic reverse proxy. Each remote realm gets a narrow adapter. Adding a new realm requires a source change.

### Realm ownership
The Bifrost console orchestrates the other products; it does not absorb their rendering engines or source trees. This keeps the repositories independently deployable and makes provenance/licensing boundaries visible.
