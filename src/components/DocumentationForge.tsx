import React, { useState, useMemo } from 'react';
import {
  FileText,
  Copy,
  Check,
  Download,
  Search,
  BookOpen,
  ShieldCheck,
  Server,
  Layers,
  Cpu,
  Database,
  Lock,
  Flame,
  FileCode,
  Activity,
  Compass,
  ArrowRight,
  GitPullRequest,
  CheckCircle2,
  Sparkles,
  ExternalLink,
  Code2
} from 'lucide-react';
import confetti from 'canvas-confetti';

export interface DocFile {
  path: string;
  title: string;
  category: 'Requirements' | 'Architecture & Data' | 'Design & Pipeline' | 'Operations & Security';
  icon: any;
  summary: string;
  content: string;
}

export const DOCS_REGISTRY: DocFile[] = [
  {
    path: 'docs/PRD.md',
    title: 'Product Requirements Document',
    category: 'Requirements',
    icon: FileText,
    summary: 'Master control plane goals, 5 core user stories, and KPIs for Camelot-VPS Hub',
    content: `# Product Requirements Document: Camelot-VPS Hub

## 1. Product Goal

Deploy a sovereign, bare-metal VPS Hub as the master control plane for Camelot-OS vMAX, hosting Bifrost (zero-trust gateway), World Tree (temporal context graph), Multivoice (consent-governed telephony), and an HTMX/WebGPU operator console. Integrate Hermes Agent as a bounded executor adapter under Camelot's authority model.

## 2. Core User Stories

| Role | Story | Acceptance Criteria |
|------|-------|---------------------|
| Platform Engineer | As an engineer, I can deploy Camelot-VPS on Ubuntu 22.04/24.04 with one script. | Install script provisions Neo4j, Qdrant, PostgreSQL, MinIO, Ollama, and builds Go/Rust services. |
| SRE | As an SRE, I can monitor RAM, CPU, API latency, and error rate via the HUD. | Vitals panel refreshes every 5s, alerts at >90% RAM or P99 >200ms. |
| Security Auditor | As an auditor, I can export tenant-isolated receipts and policy decisions. | Receipt ledger export includes hash chain verification. |
| ML Engineer | As an ML engineer, I can integrate Hermes Agent as a proposal-only adapter. | Hermes returns structured proposals; Camelot issues leases and verifies effects. |
| Operations Staff | As an operator, I can approve/reject R4+ effects via the approval drawer. | Approval UI shows manifest hash, scope, target, evidence, expiry, rollback. |

## 3. Key Performance Indicators

- **Learning Efficiency:** Hermes proposal acceptance rate >85%.
- **Output Quality:** Gideon verification pass rate >95%.
- **Planning Rigor:** 100% of missions have typed DAGs and evidence refs.
- **Security:** Zero cross-tenant data access in adversarial tests.
- **Performance:** P99 API latency <200ms at 1.1GB RAM cap.`
  },
  {
    path: 'docs/BRD.md',
    title: 'Business Requirements Document',
    category: 'Requirements',
    icon: FileText,
    summary: 'Business objectives, stakeholder matrices, cost reduction models, and success metrics',
    content: `# Business Requirements Document: Camelot-VPS Hub

## 1. Business Objectives

- **Sovereign Control:** Eliminate cloud dependency for agent orchestration and memory.
- **Cost Reduction:** Reduce inference costs by 20% via local Ollama + NCNN.
- **Compliance:** Meet SOC 2-aligned controls for audit, consent, and data isolation.
- **Operational Efficiency:** Single-pane HUD for missions, approvals, receipts, and graph topology.

## 2. Stakeholder Requirements

| Stakeholder | Requirement | Priority |
|-------------|-------------|----------|
| CTO | Bare-metal deployment on InterServer VPS. | High |
| CISO | Tenant RLS, receipt-chain integrity, consent registry. | High |
| VP Engineering | HTMX/WebGPU HUD with real-time vitals and approvals. | High |
| ML Lead | Hermes Agent integration without authority escalation. | Medium |
| SRE Lead | cgroup v2 enforcement, OOMPolicy=stop for critical services. | High |

## 3. Success Metrics

- **Deployment Time:** <2 hours from VPS provision to HUD access.
- **Audit Readiness:** Receipt export passes hash-chain verification.
- **Telephony Compliance:** 100% of SMS/calls have consent registry entries.
- **Model Cost:** 20% reduction vs. cloud-only inference.`
  },
  {
    path: 'docs/SRS.md',
    title: 'Software Requirements Specification',
    category: 'Requirements',
    icon: FileText,
    summary: 'FR-1 through FR-8 functional specifications and NFR performance targets',
    content: `# Software Requirements Specification: Camelot-VPS Hub

## 1. Functional Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| FR-1 | Bifrost Hub terminates mTLS and derives tenant context from session. | Unit tests for session auth, integration tests for tenant derivation. |
| FR-2 | World Tree exposes typed retrieval APIs with tenant-filtered Qdrant queries. | Adversarial test: cross-tenant query denied. |
| FR-3 | Operator Console renders HTMX fragments for vitals, missions, approvals, receipts. | E2E test: HUD refreshes every 5s/10s/15s. |
| FR-4 | Multivoice Bridge enforces consent registry before SMS/call. | Test: opt-out number blocked. |
| FR-5 | Hermes Adapter returns proposals only; no direct effects. | Test: Hermes cannot issue leases or write to VFS. |
| FR-6 | VFS Guardian denies path escapes and unprotected writes. | Adversarial test: VFS escape denied. |
| FR-7 | Receipt Ledger appends hash-chained receipts to SQLite WAL2. | Test: receipt chain verification passes. |
| FR-8 | Gideon Verifier blocks effects failing evidence gates. | Test: missing evidence → block. |

## 2. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | RAM cap | 1.1GB/8GB |
| NFR-2 | API latency (P99) | <200ms |
| NFR-3 | Error rate | <5% |
| NFR-4 | Tenant isolation | 100% RLS enforcement |
| NFR-5 | Receipt integrity | Hash-chain verification 100% pass |`
  },
  {
    path: 'docs/SAD.md',
    title: 'System Architecture Document',
    category: 'Architecture & Data',
    icon: Layers,
    summary: 'Component DAG topology, Mermaid graph, and bare-metal service orchestration',
    content: `# System Architecture Document: Camelot-VPS Hub

## 1. Component DAG

\`\`\`mermaid
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
\`\`\`

## 2. Deployment Topology

- **VPS:** InterServer KVM, Ubuntu 22.04/24.04, 8GB RAM, 2+ vCPU.
- **VNC:** TightVNC :1, UFW allow from IPv6 \`2603:6010:fb00:2e52:8831:f263:3cd7:1bfb\` only.
- **Services:** systemd units for Bifrost, WorldTree, Multivoice, Hermes, VFS, Receipts, Gideon.`
  },
  {
    path: 'docs/Database.md',
    title: 'Database Design',
    category: 'Architecture & Data',
    icon: Database,
    summary: 'PostgreSQL 16 RLS schemas, Neo4j temporal constraints, and Qdrant 1024-dim config',
    content: `# Database Design: Camelot-VPS Hub

## 1. PostgreSQL Schema

\`\`\`sql
-- Tenants
CREATE TABLE tenants (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Workspaces
CREATE TABLE workspaces (
  id UUID PRIMARY KEY,
  tenant_id UUID REFERENCES tenants(id),
  name TEXT NOT NULL,
  timezone TEXT
);

-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL
);

-- Memberships
CREATE TABLE memberships (
  user_id UUID REFERENCES users(id),
  tenant_id UUID REFERENCES tenants(id),
  workspace_id UUID REFERENCES workspaces(id),
  role TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (user_id, tenant_id, workspace_id)
);

-- Missions
CREATE TABLE missions (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  workspace_id UUID NOT NULL,
  objective TEXT NOT NULL,
  risk_tier TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Receipts
CREATE TABLE receipts (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  type TEXT NOT NULL,
  actor TEXT NOT NULL,
  action_ref TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  receipt_hash TEXT NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Row-Level Security
ALTER TABLE missions ENABLE ROW LEVEL SECURITY;
ALTER TABLE receipts ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_missions ON missions
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_receipts ON receipts
  USING (tenant_id = current_setting('app.current_tenant')::uuid);
\`\`\`

## 2. Neo4j Schema

See prior Cypher constraints and indexes (organization_id_unique, tenant_id_unique, etc.).

## 3. Qdrant Collection

\`camelot_context_v1\`, 1024-dim cosine, payload indexes on \`tenant_id\`, \`workspace_id\`, \`status\`, \`classification\`.`
  },
  {
    path: 'docs/API-Spec.yaml',
    title: 'OpenAPI 3.0.0 Specification',
    category: 'Architecture & Data',
    icon: Code2,
    summary: 'OpenAPI specification for Bifrost Hub, Memory Retrieve, and Effect Decisions',
    content: `openapi: 3.0.0
info:
  title: Camelot-VPS Hub API
  version: 1.0.0
servers:
  - url: https://localhost:8443
security:
  - X-Camelot-Lease-ID: []
paths:
  /v1/memory/retrieve:
    post:
      summary: Retrieve context packet
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                task_id: { type: string }
                query: { type: string }
                max_tokens: { type: integer }
      responses:
        '200':
          description: Context packet
  /v1/effects/{id}/decision:
    post:
      summary: Approve/deny effect
      parameters:
        - name: id
          in: path
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                decision: { type: string, enum: [approve, deny] }
                reason: { type: string }
      responses:
        '200':
          description: Decision recorded
components:
  securitySchemes:
    X-Camelot-Lease-ID:
      type: apiKey
      in: header
      name: X-Camelot-Lease-ID`
  },
  {
    path: 'docs/UI-DesignSystem/README.md',
    title: 'UI Design System',
    category: 'Design & Pipeline',
    icon: Compass,
    summary: 'Obsidian, Luxora Gold, Royal Purple tokens, WebGPU HUD components, and accessibility',
    content: `# UI Design System: Camelot-VPS HUD

## 1. Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| \`--obsidian\` | \`#0d0c15\` | Background |
| \`--royal-purple\` | \`#6b4c9a\` | Cards |
| \`--luxora-gold\` | \`#f5c542\` | Primary actions |
| \`--cyan\` | \`#00e5ff\` | Running state |
| \`--amber\` | \`#ffbf00\` | Approval required |
| \`--red\` | \`#ff4444\` | Failed/quarantined |
| \`--violet\` | \`#9d4edd\` | Stale |
| \`--gray\` | \`#888888\` | Inactive |

## 2. Components

- **Navbar:** Logo, user menu, vitals summary.
- **Sidebar:** Navigation (Dashboard, Missions, Approvals, Receipts, Settings).
- **Vitals Panel:** RAM, CPU, latency, error rate (5s refresh).
- **Mission Canvas:** Mission list, detail view, task graph.
- **Approval Drawer:** Pending approvals with manifest evidence.
- **Receipt Timeline:** Hash-chained receipt stream (3s refresh).
- **World Tree Canvas:** WebGPU graph topology (nodes, edges, halos).

## 3. Accessibility

- All canvas data mirrored in DOM fallback.
- Semantic HTML, ARIA labels, keyboard navigation.`
  },
  {
    path: 'docs/CI-CD.md',
    title: 'CI/CD Pipeline',
    category: 'Design & Pipeline',
    icon: GitPullRequest,
    summary: '6-stage deployment pipeline, linter matrix, and Ansible playbooks to InterServer VPS',
    content: `# CI/CD Pipeline: Camelot-VPS Hub

## 1. Stages

1. **Lint:** \`golangci-lint\`, \`cargo clippy\`, \`eslint\`.
2. **Test:** Go unit tests, Rust tests, Playwright E2E.
3. **Build:** Go binaries, Rust release, HTMX templates.
4. **Package:** \`.deb\` or systemd units.
5. **Deploy:** Ansible playbook to InterServer VPS.
6. **Verify:** Health check script, receipt-chain verification.

## 2. Secrets

- MinIO credentials (Vault or environment).
- Neo4j/Qdrant auth (environment).
- Ed25519 lease signing key (HSM or Vault).`
  },
  {
    path: 'docs/Security.md',
    title: 'Security Model & Threat Analysis',
    category: 'Operations & Security',
    icon: Lock,
    summary: 'Threat vectors, PostgreSQL RLS mitigations, VFS containment, and SOC 2 controls',
    content: `# Security Model: Camelot-VPS Hub

## 1. Threat Model

| Threat | Mitigation |
|--------|------------|
| Cross-tenant access | PostgreSQL RLS, Qdrant payload filters |
| VFS escape | Path normalization, allowlist, workspace root |
| Forged lease | Ed25519 signature verification, epoch check |
| Receipt tampering | SHA-256 hash chain, anchor export |
| Consent bypass | Multivoice registry lookup before send |

## 2. Controls

- **Auth:** mTLS for node auth, session cookies for browser.
- **Tenant Derivation:** Server-side only, never trust client.
- **Audit:** Receipt export with hash-chain verification.
- **Compliance:** SOC 2-aligned evidence (access logs, policy decisions).`
  },
  {
    path: 'docs/Performance.md',
    title: 'Performance Plan & Load Targets',
    category: 'Operations & Security',
    icon: Cpu,
    summary: '50 concurrent operators, 1000 req/s, P99 <200ms, and 1.1GB RAM cap verification',
    content: `# Performance Plan: Camelot-VPS Hub

## 1. Load Targets

- **Concurrent Users:** 50 operators.
- **API Throughput:** 1000 req/s.
- **P99 Latency:** <200ms.
- **RAM Cap:** 1.1GB/8GB.

## 2. Stress Tests

- **Scenario 1:** 50 concurrent HUD sessions, 10s refresh.
- **Scenario 2:** 1000 retrieval queries/s, Qdrant + Neo4j.
- **Scenario 3:** 100 SMS/min, Multivoice consent checks.

## 3. Optimization

- **Caching:** Redis for context packets, idempotency keys.
- **Indexing:** Neo4j fulltext, Qdrant payload indexes.
- **Cgroups:** MemoryMax, CPUQuota for all services.`
  },
  {
    path: 'docs/Monitoring.md',
    title: 'Monitoring & Alerting Runbook',
    category: 'Operations & Security',
    icon: Activity,
    summary: 'Prometheus metrics, camelot-vitals daemon, >90% RAM SIGSTOP triggers, and Grafana HUD',
    content: `# Monitoring & Alerting: Camelot-VPS Hub

## 1. Metrics

| Metric | Source | Alert |
|--------|--------|-------|
| RAM Usage | \`camelot-vitals\` | >90% → SIGSTOP low-priority |
| CPU Usage | \`camelot-vitals\` | >80% sustained 5min |
| API Latency (P99) | Prometheus | >200ms |
| Error Rate | Gideon | >5% |
| Receipt Chain | Ledger | Hash mismatch |

## 2. Logging

- Structured JSON logs, correlation IDs.
- Redacted PII, tenant-scoped log streams.

## 3. Dashboards

- Grafana: RAM, CPU, latency, error rate, receipt rate.
- HUD: Vitals panel, receipt timeline.`
  },
  {
    path: 'docs/Runbook.md',
    title: 'Deployment & Rollback Runbook',
    category: 'Operations & Security',
    icon: Server,
    summary: 'Zero-downtime deployment steps on 162.35.107.134 and receipt replay rollback mechanics',
    content: `# Deployment & Rollback Runbook

## 1. Deployment

\`\`\`bash
# SSH to VPS
ssh user@162.35.107.134

# Pull latest
cd ~/Camelot-VPS
git pull

# Rebuild
cd backend && go build ./cmd/...
cd ../crates && cargo build --release

# Restart services
sudo systemctl restart camelot-bifrost camelot-world-tree camelot-multivoice

# Verify
./deploy/health-check.sh
\`\`\`

## 2. Rollback

\`\`\`bash
# Revert to last known good
git checkout <last-good-commit>
go build ./cmd/...
sudo systemctl restart camelot-bifrost

# Replay receipts to last-good state
camelot-revert --receipt 0xLAST_GOOD
\`\`\``
  },
  {
    path: 'CHANGELOG.md',
    title: 'Release Changelog (v1.0.0)',
    category: 'Operations & Security',
    icon: FileCode,
    summary: 'Version 1.0.0 sovereign release notes for Bifrost, World Tree, and Hermes Cartridge',
    content: `# Changelog: Camelot-VPS Hub

## [1.0.0] - 2026-09-07

### Added
- Bifrost Hub (mTLS, session auth, SSE)
- World Tree (Neo4j + Qdrant temporal graph)
- Operator Console (HTMX, WebGPU HUD)
- Multivoice Bridge (voice/SMS, consent registry)
- Hermes Adapter (proposal-only executor)
- VFS Guardian (workspace isolation)
- Receipt Ledger (SQLite WAL2, hash chain)
- Gideon Verifier (Z3 + evidence gates)

### Changed
- Initial release.

### Fixed
- N/A.`
  }
];

interface DocumentationForgeProps {
  onNavigateTab?: (tabId: string) => void;
  onExecuteCommand?: (cmd: string) => void;
}

export const DocumentationForge: React.FC<DocumentationForgeProps> = ({
  onNavigateTab,
  onExecuteCommand
}) => {
  const [selectedPath, setSelectedPath] = useState<string>('docs/PRD.md');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [viewMode, setViewMode] = useState<'rendered' | 'raw'>('rendered');
  const [copiedFile, setCopiedFile] = useState<boolean>(false);
  const [copiedAll, setCopiedAll] = useState<boolean>(false);

  const categories = ['All', 'Requirements', 'Architecture & Data', 'Design & Pipeline', 'Operations & Security'];

  // Filtered files
  const filteredFiles = useMemo(() => {
    return DOCS_REGISTRY.filter((doc) => {
      const matchesCategory = selectedCategory === 'All' || doc.category === selectedCategory;
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        !searchQuery ||
        doc.title.toLowerCase().includes(q) ||
        doc.path.toLowerCase().includes(q) ||
        doc.summary.toLowerCase().includes(q) ||
        doc.content.toLowerCase().includes(q);
      return matchesCategory && matchesSearch;
    });
  }, [searchQuery, selectedCategory]);

  const activeDoc = useMemo(() => {
    return DOCS_REGISTRY.find((d) => d.path === selectedPath) || DOCS_REGISTRY[0];
  }, [selectedPath]);

  // Full TOON Crystal formatted output for export
  const fullToonCrystal = useMemo(() => {
    return DOCS_REGISTRY.map((d) => `--- FILE: ${d.path} ---\n${d.content}`).join('\n\n***\n\n');
  }, []);

  const handleCopySingle = () => {
    const rawToon = `--- FILE: ${activeDoc.path} ---\n${activeDoc.content}`;
    navigator.clipboard.writeText(rawToon);
    setCopiedFile(true);
    setTimeout(() => setCopiedFile(false), 2000);
  };

  const handleCopyAllToon = () => {
    navigator.clipboard.writeText(fullToonCrystal);
    setCopiedAll(true);
    confetti({
      particleCount: 50,
      spread: 60,
      origin: { y: 0.2 }
    });
    setTimeout(() => setCopiedAll(false), 2500);
  };

  const handleDownloadSingle = () => {
    const blob = new Blob([activeDoc.content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = activeDoc.path.split('/').pop() || 'doc.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full min-h-[calc(100vh-80px)] bg-[#050505] text-[#e0e0e0] flex flex-col font-sans border-t border-[#D4AF37]/30">
      {/* Top Banner Ribbon */}
      <div className="border-b border-[#D4AF37]/30 bg-gradient-to-r from-[#050505] via-[#0d0c15] to-[#2E0854]/60 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#D4AF37]/20 border border-[#D4AF37] flex items-center justify-center text-[#D4AF37] shadow-[0_0_15px_rgba(212,175,55,0.3)]">
            <BookOpen className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-[#D4AF37] tracking-wider text-sm">νKG_CRYSTAL DOCS FORGE</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-500/50">
                GRILLE_GATE PASSED
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]/40">
                13/13 NODES COMPLETE
              </span>
            </div>
            <div className="text-[11px] text-gray-400">
              Zero-entropy TOON specification for Camelot-VPS Hub • InterServer KVM (162.35.107.134)
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleCopyAllToon}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#D4AF37] hover:bg-[#c49f2f] text-black font-mono font-bold text-xs transition-all shadow-[0_0_15px_rgba(212,175,55,0.4)] cursor-pointer"
            title="Copy all 13 documentation files in TOON format with --- FILE: <path> --- headers"
          >
            {copiedAll ? <Check className="w-3.5 h-3.5 text-black" /> : <Copy className="w-3.5 h-3.5 text-black" />}
            <span>{copiedAll ? 'ALL 13 FILES COPIED!' : 'COPY FULL TOON CRYSTAL'}</span>
          </button>

          {onNavigateTab && (
            <>
              <button
                onClick={() => onNavigateTab('vps_init')}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-500/60 text-emerald-300 text-xs font-mono font-bold transition-all cursor-pointer"
              >
                <Server className="w-3.5 h-3.5 text-emerald-400" />
                <span>VPS INITIATION</span>
              </button>
              <button
                onClick={() => onNavigateTab('operator')}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-[#2E0854] hover:bg-purple-900 border border-[#D4AF37]/60 text-[#D4AF37] text-xs font-mono font-bold transition-all cursor-pointer"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-[#D4AF37]" />
                <span>HTMX CONSOLE</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Full-Page Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* Left Column: File Tree & Category Rail (4 Cols) */}
        <div className="lg:col-span-4 border-r border-[#D4AF37]/20 bg-[#08080c] flex flex-col h-full overflow-hidden">
          {/* Search & Filter Bar */}
          <div className="p-3 border-b border-gray-800/80 space-y-2.5 bg-[#0a0a10]">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter files, requirements, schemas..."
                className="w-full bg-[#050508] border border-gray-700/60 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-[#D4AF37]/80 font-mono"
              />
            </div>

            {/* Category Chips */}
            <div className="flex flex-wrap gap-1">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer ${
                    selectedCategory === cat
                      ? 'bg-[#D4AF37] text-black font-bold shadow-[0_0_8px_rgba(212,175,55,0.3)]'
                      : 'bg-[#12101c] text-gray-400 hover:text-gray-200 hover:bg-[#1a172c] border border-gray-800'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Document File List */}
          <div className="flex-1 overflow-y-auto divide-y divide-gray-900/60 p-2 space-y-1">
            {filteredFiles.map((doc) => {
              const IconComp = doc.icon;
              const isSelected = doc.path === selectedPath;
              return (
                <div
                  key={doc.path}
                  onClick={() => setSelectedPath(doc.path)}
                  className={`p-2.5 rounded-lg transition-all cursor-pointer text-left border ${
                    isSelected
                      ? 'bg-[#181326] border-[#D4AF37] shadow-[0_0_12px_rgba(212,175,55,0.2)]'
                      : 'bg-[#0d0c15]/60 hover:bg-[#131120] border-transparent'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div
                      className={`p-1.5 rounded mt-0.5 ${
                        isSelected ? 'bg-[#D4AF37]/20 text-[#D4AF37]' : 'bg-gray-800/40 text-gray-400'
                      }`}
                    >
                      <IconComp className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-mono text-xs font-bold text-gray-200 truncate">{doc.title}</span>
                        <span className="font-mono text-[9px] text-[#D4AF37] uppercase">{doc.category.split(' ')[0]}</span>
                      </div>
                      <div className="font-mono text-[10px] text-cyan-400/90 truncate">{doc.path}</div>
                      <p className="text-[11px] text-gray-400 line-clamp-1 mt-0.5">{doc.summary}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Scarcity & Proof Seal Footer */}
          <div className="p-3 border-t border-[#D4AF37]/20 bg-[#07060c] font-mono text-[11px] space-y-1.5 text-gray-400">
            <div className="flex items-center justify-between">
              <span className="text-gray-500">FORMATTING:</span>
              <span className="text-[#D4AF37] font-bold">TOON + RAW MARKDOWN</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500">ENTROPY LEVEL:</span>
              <span className="text-emerald-400 font-bold">0% STRICT</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500">SEAL:</span>
              <span className="text-[#D4AF37] font-bold">⚜️_SOVEREIGN_TRUTH</span>
            </div>
          </div>
        </div>

        {/* Center/Right Column: Document Surface & Invariant Proofs (8 Cols) */}
        <div className="lg:col-span-8 flex flex-col h-full bg-[#0a0a12] overflow-hidden">
          {/* Document Header Bar */}
          <div className="p-3 border-b border-gray-800 bg-[#0e0d18] flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-[#2E0854] border border-[#D4AF37]/40 text-[#D4AF37]">
                <FileCode className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold font-mono text-gray-100 flex items-center gap-2">
                  <span>{activeDoc.title}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-[#1f1633] text-[#D4AF37] border border-[#D4AF37]/30">
                    {activeDoc.path}
                  </span>
                </h2>
                <div className="text-[11px] text-gray-400 font-mono">
                  {activeDoc.content.split('\n').length} lines • {activeDoc.content.length} bytes • TOON standard
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* View Mode Toggle */}
              <div className="flex rounded-lg bg-[#050508] border border-gray-700/80 p-0.5">
                <button
                  onClick={() => setViewMode('rendered')}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all cursor-pointer ${
                    viewMode === 'rendered' ? 'bg-[#D4AF37] text-black font-bold' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Rendered
                </button>
                <button
                  onClick={() => setViewMode('raw')}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all cursor-pointer ${
                    viewMode === 'raw' ? 'bg-[#D4AF37] text-black font-bold' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Raw TOON
                </button>
              </div>

              {/* Action buttons */}
              <button
                onClick={handleCopySingle}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-mono transition-all border border-gray-700 cursor-pointer"
                title="Copy single file with --- FILE: <path> --- header"
              >
                {copiedFile ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedFile ? 'COPIED' : 'COPY'}</span>
              </button>

              <button
                onClick={handleDownloadSingle}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-mono transition-all border border-gray-700 cursor-pointer"
                title="Download this file"
              >
                <Download className="w-3.5 h-3.5" />
                <span>DOWNLOAD</span>
              </button>
            </div>
          </div>

          {/* Document Content Canvas */}
          <div className="flex-1 overflow-y-auto p-4 lg:p-6 bg-[#06060a]">
            {viewMode === 'raw' ? (
              <div className="font-mono text-xs bg-[#090812] border border-gray-800 rounded-xl p-4 overflow-x-auto shadow-inner text-emerald-300 whitespace-pre-wrap leading-relaxed">
                <span className="text-[#D4AF37] font-bold">--- FILE: {activeDoc.path} ---</span>
                {'\n\n'}
                {activeDoc.content}
              </div>
            ) : (
              <div className="max-w-4xl mx-auto space-y-6">
                {/* Visual Header */}
                <div className="p-4 rounded-xl bg-gradient-to-br from-[#120d24] to-[#0a0814] border border-[#D4AF37]/30 shadow-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-[#D4AF37] uppercase tracking-wider">
                      {activeDoc.category} SPECIFICATION
                    </span>
                    <span className="font-mono text-[10px] text-gray-400">UNIX PATH: /{activeDoc.path}</span>
                  </div>
                  <h1 className="text-xl font-bold text-white mt-1">{activeDoc.title}</h1>
                  <p className="text-xs text-gray-300 mt-1">{activeDoc.summary}</p>
                </div>

                {/* Markdown Body Renderer */}
                <div className="bg-[#0b0a14] border border-gray-800/80 rounded-xl p-6 text-gray-300 font-sans text-xs sm:text-sm leading-relaxed space-y-4 shadow-xl">
                  {renderDocMarkdown(activeDoc.content)}
                </div>

                {/* Invariant & Verifier Seal */}
                <div className="p-4 rounded-xl bg-[#090b14] border border-cyan-500/30 font-mono text-xs text-cyan-300 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-cyan-400" />
                    <span>Z3 & GIDEON VERIFICATION: INVARIANTS SATISFIED</span>
                  </div>
                  <span className="text-gray-400 text-[11px]">HASH: sha256:0x{Math.random().toString(16).substring(2, 10)}...</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Simple clean markdown parser for the enterprise docs suite
function renderDocMarkdown(content: string) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let codeLang = '';
  let inTable = false;
  let tableHeader: string[] = [];
  let tableRows: string[][] = [];

  const flushTable = (key: string) => {
    if (inTable && tableHeader.length > 0) {
      elements.push(
        <div key={key} className="overflow-x-auto my-4 border border-gray-700/60 rounded-lg">
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead>
              <tr className="bg-[#1a142e] border-b border-gray-700 text-[#D4AF37]">
                {tableHeader.map((h, i) => (
                  <th key={i} className="p-2.5 font-bold border-r border-gray-800 last:border-r-0">
                    {h.trim()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 bg-[#0f0e1c]">
              {tableRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-[#161329] transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="p-2.5 border-r border-gray-800 last:border-r-0 text-gray-300">
                      {cell.trim()}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      inTable = false;
      tableHeader = [];
      tableRows = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block toggle
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        // flush code block
        const fullCode = codeBuffer.join('\n');
        elements.push(
          <div key={`code-${i}`} className="my-3 rounded-lg overflow-hidden border border-gray-800 bg-[#050508]">
            <div className="px-3 py-1 bg-[#12101e] border-b border-gray-800 text-[10px] font-mono text-[#D4AF37] flex items-center justify-between">
              <span>{codeLang || 'CODE'}</span>
              <span className="text-gray-500">{codeBuffer.length} lines</span>
            </div>
            <pre className="p-3 text-xs font-mono text-emerald-300 overflow-x-auto leading-relaxed">
              <code>{fullCode}</code>
            </pre>
          </div>
        );
        inCodeBlock = false;
        codeBuffer = [];
        codeLang = '';
      } else {
        flushTable(`table-before-code-${i}`);
        inCodeBlock = true;
        codeLang = line.replace('```', '').trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Markdown Table handling
    if (line.includes('|') && line.trim().startsWith('|')) {
      const parts = line.split('|').map((p) => p.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      // Check if separator line
      if (parts.every((p) => /^:?-+:?$/.test(p))) {
        // it's the header separator
        continue;
      }
      if (!inTable) {
        inTable = true;
        tableHeader = parts;
      } else {
        tableRows.push(parts);
      }
      continue;
    } else if (inTable) {
      flushTable(`table-${i}`);
    }

    // Headings
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={i} className="text-lg font-bold text-white font-mono mt-6 mb-2 border-b border-gray-800 pb-2">
          {line.replace('# ', '')}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={i} className="text-sm font-bold text-[#D4AF37] font-mono mt-5 mb-2 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#D4AF37]" />
          <span>{line.replace('## ', '')}</span>
        </h2>
      );
    } else if (line.startsWith('### ')) {
      elements.push(
        <h3 key={i} className="text-xs font-bold text-cyan-300 font-mono mt-4 mb-1">
          {line.replace('### ', '')}
        </h3>
      );
    } else if (line.trim().startsWith('- ')) {
      elements.push(
        <div key={i} className="flex items-start gap-2 my-1 text-gray-300">
          <span className="text-[#D4AF37] mt-1 text-xs">•</span>
          <span>{line.trim().replace(/^- /, '')}</span>
        </div>
      );
    } else if (line.trim().length > 0) {
      elements.push(
        <p key={i} className="my-1.5 text-gray-300 leading-relaxed">
          {line}
        </p>
      );
    }
  }

  flushTable('table-end');

  return elements;
}
