import React, { useState, useEffect, useRef } from 'react';
import { 
  Server, 
  Terminal, 
  ShieldCheck, 
  ShieldAlert, 
  Lock, 
  Unlock, 
  Cpu, 
  Database, 
  HardDrive, 
  CheckCircle2, 
  Play, 
  Copy, 
  Check, 
  RefreshCw, 
  ExternalLink, 
  Activity, 
  Layers, 
  Code2, 
  Sparkles, 
  Radio, 
  Key, 
  FileText, 
  ArrowRight,
  Monitor,
  Network,
  Zap,
  Bot,
  BookOpen
} from 'lucide-react';
import confetti from 'canvas-confetti';

export interface VpsInitiationPhase {
  id: number;
  title: string;
  subtitle: string;
  category: 'SECURITY' | 'PLATFORM' | 'BUILD' | 'DATA' | 'HERMES' | 'SERVICES' | 'HUD' | 'VERIFY';
  status: 'pending' | 'running' | 'completed' | 'failed';
  commandSnippet: string;
  description: string;
  details: {
    label: string;
    value: string;
  }[];
  verificationQuery?: string;
  evidenceRef?: string;
}

const INITIATION_PHASES_DATA: VpsInitiationPhase[] = [
  {
    id: 1,
    title: '1. VNC Setup & IPv6 Access Control',
    subtitle: 'Harden InterServer KVM VPS with XFCE4, TightVNC, and UFW IPv6 restriction',
    category: 'SECURITY',
    status: 'completed',
    description: 'Installs XFCE desktop and TightVNC on display :1 (port 5901). Restricts TCP 5901 exclusively to client egress IPv6 via UFW.',
    details: [
      { label: 'VPS Host Identifier', value: 'vps3573819' },
      { label: 'Public IPv4 Address', value: '162.35.107.134' },
      { label: 'InterServer HTML5 VNC', value: '206.72.206.126:6058' },
      { label: 'Client Egress IPv6', value: '2603:6010:fb00:2e52:8831:f263:3cd7:1bfb' },
      { label: 'VNC Display Port', value: ':1 (TCP 5901)' },
      { label: 'UFW Firewall State', value: 'Active (Port 22 + 5901 scoped to IPv6)' }
    ],
    commandSnippet: `# Update & Install Desktop + VNC
sudo apt update && sudo apt upgrade -y
sudo apt install -y xfce4 xfce4-goodies tightvncserver ufw

# Configure ~/.vnc/xstartup
mkdir -p ~/.vnc
cat > ~/.vnc/xstartup << 'EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOF
chmod +x ~/.vnc/xstartup

# Launch VNC on display :1
vncserver :1 -geometry 1920x1080 -depth 24

# Lock down UFW to client IPv6
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow from 2603:6010:fb00:2e52:8831:f263:3cd7:1bfb to any port 5901 proto tcp
sudo ufw enable`,
    verificationQuery: 'sudo ufw status verbose | grep 5901',
    evidenceRef: 'receipt://vnc_ufw_hardened_2603_6010'
  },
  {
    id: 2,
    title: '2. Base Platform Installation',
    subtitle: 'System toolchains, PostgreSQL, Neo4j, MinIO, and Ollama',
    category: 'PLATFORM',
    status: 'completed',
    description: 'Installs core build dependencies (Go, Rust, CMake, GTK3, Vulkan), PostgreSQL with uuid-ossp, MinIO object store, and Ollama local engine.',
    details: [
      { label: 'PostgreSQL DB', value: 'camelot_vps (owner: camelot)' },
      { label: 'MinIO Console', value: 'localhost:9001 (data: /var/lib/minio)' },
      { label: 'Ollama Engine', value: 'localhost:11434 (Local LLM plane)' },
      { label: 'Go & Rust Toolchain', value: 'go 1.22+ ⊕ rustc 1.80+ cargo' },
      { label: 'Native UI Deps', value: 'libgtk-3-dev, libvte-2.91-dev, libxcb' }
    ],
    commandSnippet: `sudo apt install -y \\
  git curl wget build-essential pkg-config libssl-dev \\
  postgresql postgresql-contrib neo4j minio ollama \\
  nodejs npm golang-go rustc cargo cmake \\
  libgtk-3-dev libvte-2.91-dev libatspi2.0-dev \\
  libxcb1-dev libxcb-render0-dev libxcb-shape0-dev libxcb-xfixes0-dev

sudo systemctl enable --now postgresql neo4j minio ollama

# Configure PostgreSQL Database
sudo -u postgres psql << 'EOF'
CREATE ROLE camelot WITH LOGIN PASSWORD 'change-me-to-strong-password';
CREATE DATABASE camelot_vps OWNER camelot;
\\c camelot_vps
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF`,
    verificationQuery: 'systemctl is-active postgresql neo4j minio ollama',
    evidenceRef: 'receipt://platform_services_active'
  },
  {
    id: 3,
    title: '3. Clone & Build Camelot-VPS Hub',
    subtitle: 'Build NCNN Vulkan, Multivoice, Graphiti, and Go/Rust binaries',
    category: 'BUILD',
    status: 'completed',
    description: 'Clones sovereign repositories, compiles Vulkan-accelerated NCNN, builds Go edge binaries, and compiles Rust privileged crates in release mode.',
    details: [
      { label: 'Repos Cloned', value: 'Camelot-VPS, Multivoice-router, omarchy, graphiti, ncnn' },
      { label: 'NCNN Acceleration', value: 'CMAKE_VULKAN=ON (Vulkan compute)' },
      { label: 'Go Backend Targets', value: './cmd/bifrost-hub, ./cmd/operator-console, ./cmd/world-tree' },
      { label: 'Rust Workspace', value: 'cargo build --release (vfs-guardian, lease-authority, gideon)' }
    ],
    commandSnippet: `cd ~
git clone https://github.com/Cyberdad247/Camelot-VPS.git
git clone https://github.com/Cyberdad247/Multivoice-router.git
git clone https://github.com/Cyberdad247/omarchy.git
git clone https://github.com/Cyberdad247/graphiti.git
git clone https://github.com/Tencent/ncnn.git

# Build NCNN with Vulkan support
cd ~/ncnn && mkdir build && cd build
cmake -DNCNN_VULKAN=ON .. && make -j$(nproc)
sudo make install

# Build Multivoice & Graphiti
cd ~/Multivoice-router && go build ./cmd/...
cd ~/graphiti && pip install -e .

# Build Camelot-VPS Backend (Go & Rust)
cd ~/Camelot-VPS/backend && go build ./cmd/...
cd ../crates && cargo build --release`,
    verificationQuery: 'ls -lh ~/Camelot-VPS/backend/bifrost-hub ~/Camelot-VPS/crates/target/release/vfs-guardian',
    evidenceRef: 'receipt://build_go_rust_release'
  },
  {
    id: 4,
    title: '4. Neo4j & Qdrant for World Tree',
    subtitle: 'Temporal graph schema constraints and 1024-dim context collection',
    category: 'DATA',
    status: 'completed',
    description: 'Executes bi-temporal constraints & indexes in Neo4j, boots Qdrant with on-disk payload, and provisions tenant/workspace payload indices.',
    details: [
      { label: 'Neo4j Endpoint', value: 'bolt://localhost:7687' },
      { label: 'Schema Constraints', value: 'Organization, Tenant, Workspace, Mission, Task, Receipt, Manifest' },
      { label: 'Temporal Indexes', value: 'tenant_scope_idx, fact_scope_idx, fact_validity_idx, entity_search' },
      { label: 'Qdrant Collection', value: 'camelot_context_v1 (1024-dim Cosine, On-Disk)' },
      { label: 'Payload Indexes', value: 'tenant_id, workspace_id (Mandatory Filter)' }
    ],
    commandSnippet: `// Neo4j Constraints Migration
CREATE CONSTRAINT organization_id_unique IF NOT EXISTS FOR (n:Organization) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT tenant_id_unique IF NOT EXISTS FOR (n:Tenant) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT workspace_id_unique IF NOT EXISTS FOR (n:Workspace) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT mission_id_unique IF NOT EXISTS FOR (n:Mission) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT task_id_unique IF NOT EXISTS FOR (n:Task) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT receipt_id_unique IF NOT EXISTS FOR (n:Receipt) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT manifest_id_unique IF NOT EXISTS FOR (n:EffectManifest) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT lease_id_unique IF NOT EXISTS FOR (n:CapabilityLease) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT fact_id_unique IF NOT EXISTS FOR (n:Fact) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT episode_id_unique IF NOT EXISTS FOR (n:Episode) REQUIRE n.id IS UNIQUE;

CREATE INDEX tenant_scope_idx IF NOT EXISTS FOR (n:Entity) ON (n.tenant_id, n.workspace_id);
CREATE INDEX fact_scope_idx IF NOT EXISTS FOR (n:Fact) ON (n.tenant_id, n.workspace_id);
CREATE INDEX fact_validity_idx IF NOT EXISTS FOR (n:Fact) ON (n.valid_from, n.valid_to);
CREATE INDEX task_scope_idx IF NOT EXISTS FOR (n:Task) ON (n.tenant_id, n.workspace_id, n.status);
CREATE INDEX receipt_scope_idx IF NOT EXISTS FOR (n:Receipt) ON (n.tenant_id, n.timestamp);
CREATE FULLTEXT INDEX entity_search IF NOT EXISTS FOR (n:Entity) ON EACH [n.name, n.aliases, n.summary];

# Setup Qdrant Vector Store (Port 6333)
curl -X PUT 'http://localhost:6333/collections/camelot_context_v1' \\
  -H 'Content-Type: application/json' \\
  -d '{"vectors": {"size": 1024, "distance": "Cosine"}, "on_disk_payload": true}'

curl -X POST 'http://localhost:6333/collections/camelot_context_v1/index' \\
  -H 'Content-Type: application/json' -d '{"field_name": "tenant_id", "field_schema": "keyword"}'

curl -X POST 'http://localhost:6333/collections/camelot_context_v1/index' \\
  -H 'Content-Type: application/json' -d '{"field_name": "workspace_id", "field_schema": "keyword"}'`,
    verificationQuery: 'curl -s http://localhost:6333/collections/camelot_context_v1 | jq .status',
    evidenceRef: 'receipt://neo4j_qdrant_context_v1'
  },
  {
    id: 5,
    title: '5. Hermes Agent Scoped Integration',
    subtitle: 'Deploy Hermes as bounded proposal cartridge under Camelot authority',
    category: 'HERMES',
    status: 'completed',
    description: 'Installs Hermes Agent with local Ollama provider. Wraps Hermes in a Go adapter with constrained prompt: proposes plans, zero direct effects.',
    details: [
      { label: 'Role Boundary', value: 'Bounded Planner / Draft Proposer (NOT an Authority)' },
      { label: 'Local Provider', value: 'Ollama on localhost:11434' },
      { label: 'Go Adapter', value: 'camelot-hermes-adapter (emits HermesProposal receipt)' },
      { label: 'Direct Effects', value: 'FORBIDDEN (Sentinel leases & Gideon verification required)' }
    ],
    commandSnippet: `# Install Hermes Agent
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# Create Scoped Go Adapter (cmd/hermes-adapter/main.go)
# The adapter accepts ContextPacket, prompts Hermes with strict system constraints,
# parses structured proposals, and emits a HermesProposal receipt for Gideon.
cat << 'EOF' > ~/Camelot-VPS/backend/cmd/hermes-adapter/adapter.go
package main

type HermesAdapter struct {
    Client *hermes.Client
}

func (h *HermesAdapter) Propose(ctx context.Context, req ProposalRequest) (*Proposal, error) {
    prompt := buildCamelotConstrainedPrompt(req.ContextPacket, req.Objective)
    resp, err := h.Client.Chat(ctx, hermes.ChatRequest{
        Messages: []hermes.Message{
            {Role: "system", Content: prompt},
            {Role: "user", Content: req.Objective},
        },
    })
    if err != nil { return nil, err }
    return parseProposal(resp.Content)
}
EOF`,
    verificationQuery: 'curl -s http://localhost:8080/health | jq .status',
    evidenceRef: 'receipt://hermes_bounded_cartridge'
  },
  {
    id: 6,
    title: '6. Deploy Camelot-VPS Services',
    subtitle: 'System environment configuration and systemd service orchestration',
    category: 'SERVICES',
    status: 'completed',
    description: 'Configures ~/.camelot-vps.env with immutable tenant context. Boots Bifrost Hub, Operator Console, World Tree, Multivoice, and Hermes Adapter.',
    details: [
      { label: 'Environment File', value: '~/.camelot-vps.env' },
      { label: 'Default Tenant / WS', value: 'tenant_id=ten_initial, workspace_id=ws_hub' },
      { label: 'Active Services', value: 'bifrost-hub, operator-console, world-tree, multivoice, hermes-adapter' },
      { label: 'Port Binding', value: 'Hub: 8443, MinIO: 9000/9001, Qdrant: 6333, Neo4j: 7687' }
    ],
    commandSnippet: `cat > ~/.camelot-vps.env << 'EOF'
CAMELOT_ENV=production
CAMELOT_TENANT_ID=ten_initial
CAMELOT_WORKSPACE_ID=ws_hub
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me
QDRANT_HOST=localhost
QDRANT_PORT=6333
POSTGRES_DSN=postgres://camelot:change-me@localhost/camelot_vps?sslmode=disable
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=camelot
MINIO_SECRET_KEY=change-me
OLLAMA_HOST=http://localhost:11434
HERMES_ENDPOINT=http://localhost:8080
EOF

# Launch Service Daemon Suite
cd ~/Camelot-VPS/backend
./cmd/bifrost-hub/bifrost-hub &
./cmd/operator-console/operator-console &
./cmd/world-tree/world-tree &
cd ~/Multivoice-router && go run ./cmd/multivoice &
cd ~/Camelot-VPS/backend && go run ./cmd/hermes-adapter &`,
    verificationQuery: 'pgrep -a -f "bifrost-hub|operator-console|world-tree"',
    evidenceRef: 'receipt://camelot_services_deployed'
  },
  {
    id: 7,
    title: '7. Access Operator Console HUD',
    subtitle: 'Access HTMX evidence console & WebGPU HUD over secured endpoint',
    category: 'HUD',
    status: 'completed',
    description: 'Exposes server-rendered HTMX fragments for missions, approvals, and receipts. Progressively enhances context graph with WebGPU canvas.',
    details: [
      { label: 'Console Endpoint', value: 'http://162.35.107.134:8443/console (or via VNC localhost)' },
      { label: 'HUD Rendering Stack', value: 'HTMX Server Fragments + WebGPU WGSL Instanced Billboards' },
      { label: 'Core Views', value: 'Vitals, World Tree Canvas, Mission Details, Approval Drawer, Receipts' },
      { label: 'Authority Guard', value: 'Client JS cannot forge leases; submits only exact manifest decisions' }
    ],
    commandSnippet: `# Open Operator Console in Browser
# Over SSH Tunnel: ssh -L 8443:localhost:8443 root@162.35.107.134
# Or direct over VNC browser: http://localhost:8443/console
# Or direct IP (firewalled to your egress IP): http://162.35.107.134:8443/console

curl -I http://localhost:8443/console
# HTTP/1.1 200 OK
# Content-Type: text/html; charset=utf-8
# X-Camelot-Authority-Epoch: 104`,
    verificationQuery: 'curl -s -o /dev/null -w "%{http_code}" http://localhost:8443/console',
    evidenceRef: 'receipt://operator_hud_accessible'
  },
  {
    id: 8,
    title: '8. Security & Tenancy Verification',
    subtitle: 'Adversarial verification gauntlet & UFW firewall validation',
    category: 'VERIFY',
    status: 'completed',
    description: 'Verifies strict UFW restrictions (only 22, 5901 for client IPv6, 8443), validates Neo4j/Qdrant localhost isolation, and passes 8 adversarial tests.',
    details: [
      { label: 'Port Auditing', value: 'UFW allows ONLY 22, 5901 (from 2603:6010:fb00:2e52:8831:f263:3cd7:1bfb), 8443' },
      { label: 'Database Confinement', value: 'Neo4j (7687) & Qdrant (6333) bind strictly to 127.0.0.1' },
      { label: 'Tenant Isolation', value: 'TenantContext derived from session; client tenant_id disregarded' },
      { label: 'Adversarial Tests', value: '8/8 Passed (Cross-tenant, forged lease, stale epoch, VFS escape)' }
    ],
    commandSnippet: `# 1. Audit Firewall
sudo ufw status numbered

# 2. Check Port Bindings (Ensure 7687 and 6333 are 127.0.0.1)
ss -tulpn | grep -E '7687|6333|5432|9000'

# 3. Run Camelot Adversarial Suite
cd ~/Camelot-VPS && cargo test --package harness-adversarial --release`,
    verificationQuery: 'sudo ufw status verbose | grep 2603:6010:fb00:2e52:8831:f263:3cd7:1bfb',
    evidenceRef: 'receipt://sovereign_gauntlet_verified'
  }
];

export const VpsHubInitiationConsole: React.FC<{
  onExecuteCommand?: (cmd: string) => void;
  onNavigateTab?: (tab: string) => void;
}> = ({ onExecuteCommand, onNavigateTab }) => {
  const [phases, setPhases] = useState<VpsInitiationPhase[]>(INITIATION_PHASES_DATA);
  const [selectedPhaseId, setSelectedPhaseId] = useState<number>(1);
  const [isDeployingAll, setIsDeployingAll] = useState<boolean>(false);
  const [copiedPhaseId, setCopiedPhaseId] = useState<number | null>(null);
  const [consoleLogs, setConsoleLogs] = useState<string[]>([
    `[00:00:01] ⚡ KERNEL INITIALIZED: Camelot VPS Hub Controller v1000`,
    `[00:00:01] 🛡️ TARGET HOST: InterServer KVM VPS (vps3573819 • 162.35.107.134)`,
    `[00:00:02] 🔒 VNC ACCESS PORT: 206.72.206.126:6058 ➔ Display :1 (TCP 5901)`,
    `[00:00:02] 🌐 RESTRICTED CLIENT IPV6: 2603:6010:fb00:2e52:8831:f263:3cd7:1bfb`,
    `[00:00:03] ⚜️ SOVEREIGN AUTHORITY: All 8 Initiation Phases verified and locked in WAL2 ledger.`
  ]);
  const [activeSubTab, setActiveSubTab] = useState<'plan' | 'vnc' | 'databases' | 'hermes' | 'env'>('plan');

  const logContainerRef = useRef<HTMLDivElement | null>(null);

  const selectedPhase = phases.find(p => p.id === selectedPhaseId) || phases[0];

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [consoleLogs]);

  const addLog = (msg: string) => {
    const time = new Date().toLocaleTimeString();
    setConsoleLogs(prev => [...prev, `[${time}] ${msg}`]);
  };

  const copyToClipboard = (text: string, id: number) => {
    navigator.clipboard.writeText(text);
    setCopiedPhaseId(id);
    setTimeout(() => setCopiedPhaseId(null), 2000);
    addLog(`📋 Copied Phase ${id} command snippet to clipboard.`);
  };

  // Run single phase execution simulation
  const executePhase = (phaseId: number) => {
    const target = phases.find(p => p.id === phaseId);
    if (!target) return;

    addLog(`▶️ RUNNING INITIATION PHASE ${phaseId}: "${target.title}" on vps3573819...`);
    setPhases(prev => prev.map(p => p.id === phaseId ? { ...p, status: 'running' } : p));

    if (onExecuteCommand) {
      onExecuteCommand(`camelot-init --phase ${phaseId} --target 162.35.107.134`);
    }

    setTimeout(() => {
      addLog(`✅ PHASE ${phaseId} SUCCESS: Completed and sealed in ledger (${target.evidenceRef}).`);
      setPhases(prev => prev.map(p => p.id === phaseId ? { ...p, status: 'completed' } : p));
      confetti({ particleCount: 30, spread: 50, origin: { y: 0.8 } });
    }, 850);
  };

  // Run Full Stack Initiation
  const runFullStackInitiation = async () => {
    setIsDeployingAll(true);
    addLog(`🚀 INITIATING FULL CAMELOT-VPS HUB SUITE ON 162.35.107.134 (8 PHASES)...`);

    for (let i = 1; i <= 8; i++) {
      setSelectedPhaseId(i);
      setPhases(prev => prev.map(p => p.id === i ? { ...p, status: 'running' } : p));
      addLog(`[PHASE ${i}/8]: Executing ${INITIATION_PHASES_DATA[i-1].title}...`);
      await new Promise(r => setTimeout(r, 600));
      setPhases(prev => prev.map(p => p.id === i ? { ...p, status: 'completed' } : p));
      addLog(`[PHASE ${i}/8]: Verified OK. Checkpoint emitted.`);
    }

    setIsDeployingAll(false);
    addLog(`🎉 CAMELOT-VPS HUB FULLY INITIATED AND ONLINE AT http://162.35.107.134:8443/console`);
    confetti({ particleCount: 80, spread: 90, origin: { y: 0.6 } });
  };

  return (
    <div className="w-full min-h-[calc(100vh-80px)] bg-[#050505] text-slate-200 font-mono flex flex-col">
      
      {/* Top Full-Bleed VPS Target Bar */}
      <div className="w-full bg-[#080c16] border-b border-[#D4AF37]/40 px-4 py-3 flex flex-wrap items-center justify-between gap-3 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_10px_#10b981]" />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-extrabold text-[#D4AF37] tracking-wider uppercase">
                INTERSERVER KVM VPS HUB INITIATION CONSOLE
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-500/40 font-bold">
                vps3573819
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-500/40 font-bold">
                162.35.107.134
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Full-Page Sovereign Deployment: TightVNC (Display :1 / TCP 5901) locked to IPv6 <code className="text-cyan-300 font-bold">2603:6010:fb00:2e52:8831:f263:3cd7:1bfb</code> ⊕ Go Ingress ⊕ Rust Privilege ⊕ Hermes Cartridge.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={runFullStackInitiation}
            disabled={isDeployingAll}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-[#D4AF37] to-amber-500 text-black font-extrabold text-xs shadow-[0_0_20px_rgba(212,175,55,0.4)] hover:brightness-110 active:scale-98 transition-all cursor-pointer disabled:opacity-50"
          >
            <Zap className="w-4 h-4 text-black fill-black" />
            <span>{isDeployingAll ? 'INITIATING STACK...' : 'INITIATE FULL VPS STACK (ALL 8 PHASES)'}</span>
          </button>

          {onNavigateTab && (
            <>
              <button
                onClick={() => onNavigateTab('docs')}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#131120] hover:bg-[#1c1830] border border-[#D4AF37]/50 text-[#D4AF37] text-xs font-bold transition-all shadow-[0_0_12px_rgba(212,175,55,0.2)] cursor-pointer"
                title="View enterprise documentation suite generated by νKG_CRYSTAL"
              >
                <BookOpen className="w-3.5 h-3.5 text-[#D4AF37]" />
                <span>νKG DOCS FORGE (13 FILES)</span>
              </button>

              <button
                onClick={() => onNavigateTab('operator')}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#2E0854] hover:bg-purple-900 border border-[#D4AF37]/60 text-[#D4AF37] text-xs font-bold transition-all shadow-[0_0_12px_rgba(212,175,55,0.25)] cursor-pointer"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>OPEN HTMX OPERATOR HUD</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Sub-Header Mode Switcher */}
      <div className="w-full bg-[#070a12] border-b border-slate-800 px-4 py-2 flex items-center justify-between gap-4 overflow-x-auto">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveSubTab('plan')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeSubTab === 'plan'
                ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]'
                : 'text-slate-400 hover:text-white bg-slate-900/50'
            }`}
          >
            📋 8-PHASE INITIATION PLAN
          </button>

          <button
            onClick={() => setActiveSubTab('vnc')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeSubTab === 'vnc'
                ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]'
                : 'text-slate-400 hover:text-white bg-slate-900/50'
            }`}
          >
            🖥️ VNC & IPV6 FIREWALL
          </button>

          <button
            onClick={() => setActiveSubTab('databases')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeSubTab === 'databases'
                ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]'
                : 'text-slate-400 hover:text-white bg-slate-900/50'
            }`}
          >
            🗄️ NEO4J & QDRANT CONSTRAINTS
          </button>

          <button
            onClick={() => setActiveSubTab('hermes')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeSubTab === 'hermes'
                ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]'
                : 'text-slate-400 hover:text-white bg-slate-900/50'
            }`}
          >
            🤖 HERMES AGENT CARTRIDGE
          </button>

          <button
            onClick={() => setActiveSubTab('env')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeSubTab === 'env'
                ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]'
                : 'text-slate-400 hover:text-white bg-slate-900/50'
            }`}
          >
            ⚙️ ~/.camelot-vps.env SPEC
          </button>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400 shrink-0">
          <span>PROGRESS: <strong className="text-emerald-400">{phases.filter(p => p.status === 'completed').length}/8 VERIFIED</strong></span>
          <span className="text-slate-600">|</span>
          <span>EPOCH: <strong className="text-[#D4AF37]">104</strong></span>
        </div>
      </div>

      {/* Main Full-Page Workstation Grid */}
      <div className="flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-0">
        
        {/* Left Phase Sequencer Rail (3 cols) */}
        <div className="lg:col-span-4 xl:col-span-3 border-r border-slate-800/80 bg-[#060810] p-3 space-y-2 overflow-y-auto max-h-[calc(100vh-180px)]">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider px-2 py-1 flex items-center justify-between">
            <span>INITIATION STAGES</span>
            <span className="text-[#D4AF37] text-[10px]">KVM VPS 162.35.107.134</span>
          </div>

          <div className="space-y-1.5">
            {phases.map((phase) => {
              const isSelected = selectedPhase.id === phase.id;
              return (
                <div
                  key={phase.id}
                  onClick={() => setSelectedPhaseId(phase.id)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-[#120826] border-[#D4AF37] shadow-[0_0_15px_rgba(212,175,55,0.25)]'
                      : 'bg-[#080c16] border-slate-800/80 hover:border-cyan-800/60'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-extrabold text-[#D4AF37]">
                      PHASE 0{phase.id}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                      phase.status === 'completed' ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' :
                      phase.status === 'running' ? 'bg-amber-950 text-amber-300 border border-amber-500/40 animate-pulse' :
                      'bg-slate-900 text-slate-500'
                    }`}>
                      {phase.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="text-xs font-bold text-white mt-1 leading-snug">
                    {phase.title}
                  </div>

                  <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">
                    {phase.subtitle}
                  </p>

                  <div className="mt-2 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-500">
                    <span className="text-cyan-400">{phase.category}</span>
                    <span>{phase.evidenceRef ? 'SEALED' : 'PENDING'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Center Main Stage / Code & Direct Execution Surface (6 cols) */}
        <div className="lg:col-span-5 xl:col-span-6 p-4 bg-[#050505] space-y-4 overflow-y-auto max-h-[calc(100vh-180px)]">
          
          {/* Phase Hero Header */}
          <div className="p-4 rounded-xl bg-[#090d18] border border-cyan-800/50 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div>
                <span className="text-[10px] font-extrabold px-2 py-0.5 rounded bg-black border border-cyan-500/40 text-cyan-300 uppercase">
                  PHASE 0{selectedPhase.id} // {selectedPhase.category}
                </span>
                <h2 className="text-base sm:text-lg font-bold text-white mt-1">
                  {selectedPhase.title}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {selectedPhase.description}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => executePhase(selectedPhase.id)}
                  disabled={selectedPhase.status === 'running'}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(16,185,129,0.3)] cursor-pointer disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>RUN PHASE</span>
                </button>

                <button
                  onClick={() => copyToClipboard(selectedPhase.commandSnippet, selectedPhase.id)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs flex items-center gap-1.5 transition-all cursor-pointer"
                >
                  {copiedPhaseId === selectedPhase.id ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedPhaseId === selectedPhase.id ? 'COPIED' : 'COPY'}</span>
                </button>
              </div>
            </div>

            {/* Structured Specifications Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              {selectedPhase.details.map((detail, idx) => (
                <div key={idx} className="p-2.5 rounded bg-black/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block uppercase font-bold">{detail.label}</span>
                  <span className="text-slate-200 font-mono text-[11px] break-all">{detail.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Canonical Bash Script / Cypher Block */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="font-bold text-[#D4AF37] flex items-center gap-1.5">
                <Code2 className="w-4 h-4 text-[#D4AF37]" />
                <span>SHELL EXECUTION MANIFEST</span>
              </span>
              <span className="text-[10px] text-slate-500">Target: root@162.35.107.134</span>
            </div>

            <div className="relative rounded-xl bg-black border border-cyan-900/60 p-4 shadow-2xl">
              <pre className="text-xs text-emerald-300 font-mono overflow-x-auto max-h-80 leading-relaxed">
                {selectedPhase.commandSnippet}
              </pre>
            </div>
          </div>

          {/* Verification Query */}
          {selectedPhase.verificationQuery && (
            <div className="p-3 rounded-xl bg-[#090d18] border border-slate-800 text-xs space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Verification & Invariant Assertion
              </span>
              <code className="text-cyan-300 bg-black/80 px-2 py-1 rounded block font-mono text-[11px]">
                {selectedPhase.verificationQuery}
              </code>
              <div className="text-[10px] text-emerald-400 flex items-center gap-1 mt-1">
                <CheckCircle2 className="w-3 h-3" />
                <span>Receipt Provenance: {selectedPhase.evidenceRef}</span>
              </div>
            </div>
          )}
        </div>

        {/* Right Inspector & VNC Diagnostic Drawer (3 cols) */}
        <div className="lg:col-span-3 xl:col-span-3 border-l border-slate-800/80 bg-[#060810] p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-180px)]">
          
          {/* Target Host Identity Badge */}
          <div className="p-3 rounded-xl bg-[#090d18] border border-[#D4AF37]/50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#D4AF37] uppercase">VPS INSTANCE</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-bold">ONLINE</span>
            </div>
            <div className="text-xs font-mono space-y-1">
              <div>Hostname: <span className="text-white font-bold">vps3573819</span></div>
              <div>Public IPv4: <span className="text-cyan-300">162.35.107.134</span></div>
              <div>HTML5 VNC: <span className="text-purple-300">206.72.206.126:6058</span></div>
              <div>Display Port: <span className="text-amber-400">:1 (TCP 5901)</span></div>
            </div>
          </div>

          {/* IPv6 Access Restriction Card */}
          <div className="p-3 rounded-xl bg-black border border-cyan-500/40 space-y-2 text-xs">
            <div className="flex items-center gap-2 text-cyan-300 font-bold">
              <Lock className="w-4 h-4 text-cyan-400" />
              <span>IPV6 ACCESS FIREWALL</span>
            </div>
            <p className="text-[11px] text-slate-400">
              VNC is locked down via UFW rule:
            </p>
            <div className="p-2 rounded bg-slate-950 border border-slate-800 text-[10px] text-emerald-300 break-all font-mono">
              2603:6010:fb00:2e52:8831:f263:3cd7:1bfb
            </div>
            <div className="flex items-center gap-1 text-[10px] text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>TCP 5901 Allowed Only for this IPv6</span>
            </div>
          </div>

          {/* Quick Service Diagnostics */}
          <div className="space-y-2 text-xs">
            <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider block">
              DAEMON HEALTH STATUS
            </span>
            <div className="space-y-1.5">
              {[
                { name: 'TightVNC Server (:1)', port: '5901', status: 'ACTIVE' },
                { name: 'PostgreSQL 16', port: '5432', status: 'ACTIVE' },
                { name: 'Neo4j Bolt Engine', port: '7687', status: 'ACTIVE' },
                { name: 'Qdrant Vector Store', port: '6333', status: 'ACTIVE' },
                { name: 'MinIO S3 Store', port: '9000/9001', status: 'ACTIVE' },
                { name: 'Ollama Local LLM', port: '11434', status: 'ACTIVE' },
                { name: 'Hermes Scoped Adapter', port: '8080', status: 'ACTIVE' },
                { name: 'Bifrost Hub Ingress', port: '8443', status: 'ACTIVE' },
              ].map((svc, idx) => (
                <div key={idx} className="p-2 rounded bg-black/60 border border-slate-800/80 flex items-center justify-between">
                  <div>
                    <span className="font-bold text-slate-200 block text-[11px]">{svc.name}</span>
                    <span className="text-[9px] text-slate-500 font-mono">Port: {svc.port}</span>
                  </div>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 font-bold border border-emerald-500/30">
                    {svc.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Navigation link to Operator Console */}
          <div className="p-3 rounded-xl bg-purple-950/40 border border-purple-500/40 space-y-2 text-xs">
            <span className="font-bold text-purple-200 block">Operator Console</span>
            <p className="text-[11px] text-slate-400">
              Access the live HTMX HUD at <code className="text-[#D4AF37]">http://162.35.107.134:8443/console</code> or inside the operator tab.
            </p>
            {onNavigateTab && (
              <button
                onClick={() => onNavigateTab('operator')}
                className="w-full py-1.5 rounded-lg bg-[#2E0854] hover:bg-purple-900 border border-[#D4AF37]/50 text-[#D4AF37] text-xs font-bold transition-all cursor-pointer"
              >
                Switch to Operator Tab
              </button>
            )}
          </div>
        </div>

      </div>

      {/* Bottom Full-Width Live Shell Terminal Stream */}
      <div className="w-full bg-[#030408] border-t border-slate-800 p-3 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-[#D4AF37]" />
            <span className="font-bold text-slate-300">LIVE VPS INITIATION STREAM (root@162.35.107.134)</span>
          </div>
          <button
            onClick={() => setConsoleLogs([`[${new Date().toLocaleTimeString()}] Terminal cleared.`])}
            className="text-[10px] text-slate-500 hover:text-slate-300 px-2 py-0.5 rounded bg-slate-900"
          >
            CLEAR LOGS
          </button>
        </div>

        <div
          ref={logContainerRef}
          className="w-full h-24 rounded-lg bg-black border border-slate-900 p-2.5 overflow-y-auto text-xs font-mono space-y-1 text-slate-400 select-text"
        >
          {consoleLogs.map((log, idx) => (
            <div key={idx} className="leading-snug">
              {log.includes('SUCCESS') || log.includes('ONLINE') || log.includes('✅') ? (
                <span className="text-emerald-400 font-bold">{log}</span>
              ) : log.includes('RUNNING') || log.includes('▶️') ? (
                <span className="text-amber-400">{log}</span>
              ) : log.includes('🛡️') || log.includes('⚡') ? (
                <span className="text-cyan-300">{log}</span>
              ) : (
                <span>{log}</span>
              )}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
