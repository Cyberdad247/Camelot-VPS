# cloudbrain — production-hardening implementation pack

Implementation pack for production-hardening the **tri-dynamic cloudbrain memory
stack** on the Hermes VPS. The stack was already deployed; everything here
hardens it for reliable unattended operation: supervision, backup/restore,
retention, TLS, mesh correctness fixes, alerting, and the runbooks that govern
them. Forged locally — zero secrets in any file.

## Stack being hardened

| Component | Role | Port |
|---|---|---|
| Redis 8.2.1 | Flash memory | :6379 |
| Qdrant 1.19.1 | Context compiler | :6333 / :6334 |
| SurrealDB 2.6.5 | Long-term store | :8000 |
| OpenViking 0.4.21 | Notebook/memory service | :1933 |
| Mesh handoff broker | Knight handoff routing | :8002 |
| Anya Omega | Routing + policy router | :8003 |
| Symbollect v1 | Dictionary-compressed handoff packet codec | — |
| ntfy | Phone alerting (5-min health checks + daily heartbeat) | — |

## How deployment works

- **Target:** VPS `162.35.107.134`, operator user `hermes`, **no sudo**.
- **Auth:** every VPS session requires a **fresh Hermes admin login**; credentials are per-session and never stored.
- **Execution pattern:** upload the script (<512 KiB) to `/opt/data/scripts/`, create a
  `no_agent` cron job, trigger `/api/cron/jobs/{id}/trigger`, read the output at
  `/opt/data/cron/output/{id}/`. Trigger calls may time out while the job still
  runs — inspect job/process/output state before retrying. Never launch duplicate
  Python build/install jobs.
- **Order:** follow [DEPLOY_QUEUE.md](DEPLOY_QUEUE.md) Phase 0 → Phase 6; decisions
  D1–D8 and owner assignments live in
  [docs/DECISIONS_CHECKLIST.md](docs/DECISIONS_CHECKLIST.md).

## Tree layout

```
cloudbrain/
├── README.md                  ← this file
├── MANIFEST.md                ← artifact inventory, canonical locations, known gaps
├── DEPLOY_QUEUE.md            ← ordered VPS deploy queue (all phases)
├── VERSIONS.md                ← version log (sibling coordinator)
├── docs/
│   ├── runbooks/              ← deploy, secret-rotation, restore, incident-response
│   ├── phase-guides/          ← deploy-steps-engineering.md, deploy-steps-ops-security.md
│   └── DECISIONS_CHECKLIST.md ← manual/decision steps (owners, D1–D8, readiness review)
├── ops/                       ← backup, restore, retention, tls, supervision (sibling coordinator)
├── patches/                   ← Anya/broker patch specs (sibling coordinator)
├── tests/                     ← e2e test suite (sibling coordinator)
└── tools/                     ← (planned)
```

The `docs/` tree, this README, `MANIFEST.md`, and `DEPLOY_QUEUE.md` are the
docs-track worker's build. `ops/`, `patches/`, `tests/`, `tools/`, and
`VERSIONS.md` belong to sibling coordinators and are referenced here only as
planned/canonical homes.

## Entry points

- Start with [MANIFEST.md](MANIFEST.md) — what every artifact is, where it lives,
  what it's missing.
- Then [DEPLOY_QUEUE.md](DEPLOY_QUEUE.md) — the ordered, phase-by-phase VPS
  execution order with gates and rollback rules.

Governing rule, everywhere: **memory may inform and scope decisions; it never
mints authority.**
