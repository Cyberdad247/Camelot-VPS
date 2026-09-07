# System Architecture Document: Camelot-VPS Hub

## 1. Component DAG

```mermaid
graph TD
    Browser[Operator Browser / VNC]
    Bifrost[Bifrost Hub]
    Console[Operator Console HTMX]
    WorldTree[World Tree Service]
    Neo4j[(Neo4j)]
    Qdrant[(Qdrant)]
    Multivoice[Multivoice Bridge]
    Hermes[Hermes Adapter]
    VFS[VFS Guardian]
    Receipts[Receipt Ledger]
    Gideon[Gideon Verifier]
    Ollama[Ollama]
    NCNN[NCNN Inference]

    Browser --> Bifrost
    Bifrost --> Console
    Bifrost --> WorldTree
    WorldTree --> Neo4j
    WorldTree --> Qdrant
    Bifrost --> Multivoice
    Bifrost --> Hermes
    Hermes --> Ollama
    Hermes --> NCNN
    Bifrost --> VFS
    VFS --> Receipts
    VFS --> Gideon
```

## 2. Deployment Topology

- **VPS:** InterServer KVM, Ubuntu 22.04/24.04, 8GB RAM, 2+ vCPU.
- **VNC:** TightVNC :1, UFW allow from IPv6 `2603:6010:fb00:2e52:8831:f263:3cd7:1bfb` only.
- **Services:** systemd units for Bifrost, WorldTree, Multivoice, Hermes, VFS, Receipts, Gideon.
