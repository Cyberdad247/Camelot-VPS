# Camelot Cloudbrain → NotebookLM MCP Integration v1

## Status

Experimental provider integration beneath Camelot governance. NotebookLM is an external evidence source and **never** an authority source.

## Source architecture carried forward

The Camelot-OS Cloudbrain design identifies NotebookLM as part of the memory/research plane, governed by Lady Mnemosyne, and emits signed token-budgeted `camelot-context-packet/1` objects for Knight consumption. The VPS integration preserves those semantics while replacing older claims of direct bidirectional authority/synchronization with a governed retrieval boundary.

## Production topology

```text
Knight / Research Mission
        │
        │ request retrieval lease
        ▼
Sentinel
        │ cloudbrain:retrieve
        │ cloudbrain://notebooklm/<workspace>/<notebook>
        ▼
Cloudbrain Broker (Rust)
        │ verifies lease + current signed authority epoch
        │ enforces token/output ceilings
        ▼
NotebookLM MCP sidecar (non-authority)
        │ loopback Streamable HTTP / JSON-RPC
        ▼
Google NotebookLM
        │
        ▼
Provider answer + references
        │
        ▼
Cloudbrain Broker
        ├─ hashes result
        ├─ writes retrieval receipt to Ledger
        ├─ classifies content as L2 evidence
        └─ signs camelot-context-packet/1
```

## Security laws

1. NotebookLM MCP never receives Sentinel, Ledger, VFS, Gideon, Arthur, or epoch signing material.
2. The MCP endpoint must remain loopback-only. `cloudbrain-broker` refuses non-loopback provider URLs.
3. Browser code never receives the Cloudbrain bearer token or NotebookLM authentication state.
4. A query requires a current Sentinel-signed `cloudbrain:retrieve` lease bound to the exact workspace and NotebookLM notebook resource.
5. A stale authority epoch immediately invalidates retrieval leases.
6. NotebookLM output is `external_provider_evidence`, not policy, approval, or executable instruction.
7. A response is not returned as a signed Context Packet until the retrieval action is receipted by the Camelot Ledger.
8. NotebookLM authentication remains inside the isolated provider account directory under `/var/lib/camelot/notebooklm`.

## Provider implementation

The sidecar is designed for the `notebooklm-mcp` Streamable HTTP interface and calls only the configured query tool, default `notebook_query`. No generic MCP tool proxy is exposed through Camelot.

The current community NotebookLM MCP implementations use undocumented/internal NotebookLM APIs and browser-derived authentication. For that reason this adapter remains an **experimental external provider** even when Camelot's broker is production hardened. Enterprise production should pin a reviewed provider version and treat provider upgrades as supply-chain changes.

## Request shape

`POST /v1/cloudbrain/query`

```json
{
  "workspaceId": "<uuid>",
  "missionId": "mission-research-001",
  "taskId": "task-research-001",
  "correlationId": "research-001",
  "notebookId": "<notebooklm-id>",
  "question": "What does the notebook say about the production gate?",
  "maxTokens": 4096,
  "lease": { "...": "Sentinel CapabilityLease" }
}
```

The request is server-to-server and requires `Authorization: Bearer <CAMELOT_CLOUDBRAIN_TOKEN>`.

## Sentinel lease example

```json
{
  "actor_id": "lady-mnemosyne",
  "session_id": "<workspace-uuid>",
  "capabilities": ["cloudbrain:retrieve"],
  "resource_bounds": [
    "cloudbrain://notebooklm/<workspace-uuid>/<notebook-id>"
  ],
  "ttl_seconds": 300
}
```

## Context Packet

The broker emits `camelot-context-packet/1`. NotebookLM answers are always represented as `l2_evidence` with a content-addressed SHA-256 reference. The broker signs the packet with its own Cloudbrain identity; consumers pin the broker public key from `/health/ready` or deployment configuration.

## Deployment

The external sidecar executable is expected at:

```text
/opt/camelot/notebooklm-mcp/bin/notebooklm-mcp
```

Authenticate it out-of-band as the dedicated `camelot-notebooklm` service identity before enabling the unit. The service stores provider authentication only beneath:

```text
/var/lib/camelot/notebooklm
```

Then enable:

```text
notebooklm-mcp.service
cloudbrain-broker.service
```

The sidecar is not in the critical authority slice. If it fails, Cloudbrain retrieval becomes unavailable; Sentinel, Bifrost, Ledger, VFS, and the rest of the Sovereign Court continue operating.
