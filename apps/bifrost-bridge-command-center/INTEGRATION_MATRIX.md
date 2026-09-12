# Bifrost Integration Matrix

| Realm | Hermes responsibility | Heimdall responsibility | Current adapter | Mutation policy |
|---|---|---|---|---|
| Camelot-VPS | originate intents, route internal commands | verify sovereign operator context | local command plane | local only |
| Multivoice-router | voice/persona handoff, bridge/Tailscale route selection | verify realm reachability and crossing intent | health probe + explicit UI handoff | remote mutation stays in Multivoice UI/API until a dedicated scoped contract is added |
| God's Eye View | spatial-intelligence handoff and future serialized-view exchange | validate destination and operator intent | reachability probe + UI handoff | no automatic map mutation yet |
| WorldMonitor | MCP capability discovery and future tool routing | verify tool intent, schema and auth before execution | MCP `tools/list` over `/mcp` | generic tool execution intentionally blocked pending per-tool gate schemas |

## Intended next contracts

1. **WorldMonitor tool registry cache** — cache `tools/list`, display tool schemas in the Hermes routing forge, then let Heimdall approve specific tools rather than generic MCP execution.
2. **God's Eye serialized view envelope** — accept only documented/shareable view-state fields from God's Eye View and store a signed handoff receipt.
3. **Multivoice scoped Bifrost endpoint** — add a dedicated endpoint to Multivoice-router for persona selection / speech requests with an explicit allowlist, instead of reusing its generic bridge proxy.
4. **Camelot receipt sink** — send successful crossing receipts into the sovereign ledger / VFS receipt path once that API contract is exposed.
