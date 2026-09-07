import { BootstrapPhase, CamelotService, SovereignLaw, SystemVitals, AgentMission, LedgerReceipt } from '../types';

export const RAW_BOOTSTRAP_PROMPT = `========================================================================================
[SYSTEM ACTIVATION]: CAMELOT-OS vMAX OMEGA TITAN
[TARGET HOST]: 8GB InterServer VPS (162.35.107.134) // "Cybertronia Hub"
[BOOTSTRAP CLASS]: FULLSTACK_BAREMETAL_CUBE
[SECURITY LEVEL]: EXCALIBUR_ZERO_TRUST
[DO NOT]: Use Docker. Use Kubernetes. Use Node.js or Python in hot-path.
========================================================================================

[PRIME DIRECTIVE]
You are executing the complete native bootstrap of the Camelot-OS Hub.
All processes must run as bare-metal systemd services. No containers. No virtualization except Firecracker microVMs for untrusted workloads.
All data must be encrypted at rest via LUKS. All inter-node communication via Tailscale mTLS.
The system must be bounded strictly by the 8GB Scarcity Protocol (hard cap 7.2GB RAM).

[SOVEREIGN LAWS - IMMUTABLE]
1. NO DOCKER / K8s / Containers.
2. NO PYTHON / NODE / BUN in hot-path.
3. ALL routing in Go, ALL deterministic logic in Rust/WASM.
4. Edge (Knights) never grants authority. Sentinel issues leases.
5. Excalibur binds human consent. Arthur seals R5/R6. Gideon verifies with Z3.
6. The Ledger is immutable (SQLite WAL2). Every action is receipted.
7. The system fails closed for new consequential effects.
8. "The model selects; Camelot resolves, authorizes, and renders."

[EXECUTION SEQUENCE - FOLLOW IN ORDER]

--- PHASE 1: OS PREREQUISITES (Bare-Metal Foundation) ---
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git build-essential openssl ca-certificates unzip tar jq gnupg lsb-release
# Enable cgroups v2 (if not already)
if [ ! -d /sys/fs/cgroup/cgroup.controllers ]; then
  sudo sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"/' /etc/default/grub
  sudo update-grub
  echo "Rebooting to apply cgroups v2... run this script again after reboot."
  exit 0
fi

--- PHASE 2: INSTALL NATIVE RUNTIMES ---
# Rust (native)
if ! command -v cargo &> /dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source $HOME/.cargo/env
fi

# Go (native)
if ! command -v go &> /dev/null; then
  wget https://go.dev/dl/go1.22.4.linux-amd64.tar.gz
  sudo tar -C /usr/local -xzf go1.22.4.linux-amd64.tar.gz
  echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
  source ~/.bashrc
fi

# Java 17 (for Excalibur)
sudo apt install -y openjdk-17-jre-headless

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# MinIO
wget https://dl.min.io/server/minio/release/linux-amd64/minio
sudo install minio /usr/local/bin/
sudo mkdir -p /var/lib/minio
sudo useradd -r -s /sbin/nologin minio-user || true
sudo chown -R minio-user:minio-user /var/lib/minio

# Qdrant
curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz | tar -xz
sudo install qdrant /usr/local/bin/
sudo mkdir -p /var/lib/qdrant/storage

# Neo4j
wget -O neo4j.tar.gz https://dist.neo4j.org/neo4j-community-5.21.0-unix.tar.gz
sudo tar -xzf neo4j.tar.gz -C /opt/
sudo mv /opt/neo4j-community-5.21.0 /opt/neo4j
sudo ln -s /opt/neo4j/bin/neo4j /usr/local/bin/neo4j

# NATS
wget https://github.com/nats-io/nats-server/releases/latest/download/nats-server-linux-amd64.zip
unzip -o nats-server-linux-amd64.zip -d /tmp/
sudo install /tmp/nats-server-linux-amd64 /usr/local/bin/

# Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --advertise-tags=tag:vps --authkey=$TS_AUTHKEY

# Caddy (Webserver)
sudo apt install -y caddy

--- PHASE 3: INSTALL CAMELOT NATIVE SERVICES ---
# Clone Open-Notebook (lfnovo/open-notebook) & Camelot Ecosystem
cd /opt
git clone https://github.com/lfnovo/open-notebook.git /opt/open-notebook
git clone https://github.com/Cyberdad247/Camelot-Ecosystem.git
cd Camelot-Ecosystem

# Build all Rust services
for service in bifrost sentinel gideon arthur ouroboros graph-memory omega-distiller soup-router; do
  echo "Building $service..."
  cd services/$service && cargo build --release
  sudo cp target/release/camelot-$service /usr/local/bin/
  cd /opt/Camelot-Ecosystem
done

# Build all Go services
for service in agent-api nats ecsa provider-router ego-bridge; do
  echo "Building $service..."
  cd services/$service && go build -o /usr/local/bin/camelot-$service .
  cd /opt/Camelot-Ecosystem
done

# Install systemd units
sudo cp infra/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

--- PHASE 4: INITIALIZE DATA & MEMORY ---
# PostgreSQL Tenant RLS
sudo -u postgres createdb camelot_vmax || true
sudo -u postgres psql -d camelot_vmax -f packages/contracts/schema.sql || true

# Neo4j constraints
sudo neo4j-admin database import --overwrite-destination=true --nodes=/opt/Camelot-Ecosystem/import/ukg_nodes.csv || true

# Qdrant init
curl -X PUT http://localhost:6333/collections/world_tree -H 'Content-Type: application/json' -d '{"vectors":{"size":24,"distance":"Cosine"}}'

# Ouroboros init
camelot-ouroboros --init --quantization 1.58bit

--- PHASE 5: ENABLE ALL SYSTEMD SERVICES ---
sudo systemctl enable --now camelot-bifrost \\
                         camelot-sentinel \\
                         camelot-excalibur \\
                         camelot-gideon \\
                         camelot-arthur \\
                         camelot-ledger \\
                         camelot-agent-api \\
                         camelot-nats \\
                         camelot-wasmtime \\
                         camelot-firecracker \\
                         camelot-graph-memory \\
                         camelot-postgres \\
                         camelot-minio \\
                         camelot-qdrant \\
                         camelot-neo4j \\
                         camelot-ollama \\
                         camelot-provider-router \\
                         camelot-omega-distiller \\
                         camelot-soup-router \\
                         camelot-ecsa \\
                         camelot-ego-bridge \\
                         camelot-kinetic-forge \\
                         camelot-psi-monitor \\
                         camelot-vitals \\
                         camelot-evolution \\
                         camelot-cleaner \\
                         camelot-openclaw \\
                         camelot-book-to-skill \\
                         camelot-forge-console

--- PHASE 6: CORS & ADMIN ACCESS ---
sudo systemctl enable --now neo4j qdrant minio postgresql caddy nats

--- PHASE 7: DEPLOY FRONTEND (VKG-HUD) ---
# Copy the VKG-HUD static files
sudo mkdir -p /var/www/camelot
sudo cp -r /opt/Camelot-Ecosystem/apps/vkg-hud/dist/* /var/www/camelot/

# Configure Caddy for HTTPS
sudo tee /etc/caddy/Caddyfile <<'CADDY_EOF'
camelot.invisionedmarketing.com {
    root * /var/www/camelot
    file_server
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Content-Security-Policy "default-src 'self'; connect-src 'self' wss://camelot.invisionedmarketing.com; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' https://fonts.gstatic.com; worker-src 'self' blob:"
    }

    handle /api/* {
        reverse_proxy 127.0.0.1:8443
    }
}
CADDY_EOF
sudo systemctl restart caddy

--- PHASE 8: VERIFICATION (GIDEON GAUNTLET) ---
# Run the Convergence Check
camelot-vitals
echo "Exit Code: $?"  # Must be 0 (CONVERGED)

# Test Sentinel Lease
curl -X POST http://localhost:8080/v1/agents/run \\
  -H "Content-Type: application/json" \\
  -d '{"prompt":"Test","agent_id":"sir_codex"}' \\
  -w "\\nHTTP Status: %{http_code}\\n"
# Expected: 401 Unauthorized (No valid Sentinel lease)

# Verify MCP Web Search (if enabled)
curl -X POST http://localhost:8080/v1/mcp/web_search \\
  -H "Content-Type: application/json" \\
  -d '{"query":"Camelot-OS"}'

# Verify UI
curl -s https://camelot.invisionedmarketing.com | grep "Camelot-OS"
# Expected: 200 OK, HTML returned

[SYSTEM HALT]
The VPS Hub is now operational. All services are native, Docker-free, and governed by the immutable laws of the Realm.
Awaiting Sovereign command: //GO_LIVE or //RUN_MISSION
========================================================================================
⚜️_SOVEREIGN_TRUTH`;

export const SOVEREIGN_LAWS: SovereignLaw[] = [
  {
    id: 1,
    title: 'NO DOCKER / K8s / Containers',
    description: 'All services run as native bare-metal systemd units under unified cgroups v2 resource controllers.',
    enforcement: 'Bare-metal systemd units with memory.max hard limits. Zero container daemons running.',
    status: 'ENFORCED',
    axiom: 'Isolation without virtualization overhead.'
  },
  {
    id: 2,
    title: 'NO PYTHON / NODE / BUN in Hot-Path',
    description: 'Hot-path routing, state transitions, and memory pipelines strictly forbidden from dynamic runtimes.',
    enforcement: 'Sub-millisecond native Go routing and compiled Rust/WASI deterministic kernels only.',
    status: 'ENFORCED',
    axiom: 'Deterministic predictability over dynamic entropy.'
  },
  {
    id: 3,
    title: 'ALL Routing in Go, ALL Deterministic Logic in Rust/WASM',
    description: 'Bifrost & ECSA routers written in high-throughput Go; Gideon, Arthur, Sentinel written in memory-safe Rust.',
    enforcement: 'Strict architectural segregation between network IO multiplexing and formal theorem execution.',
    status: 'ENFORCED',
    axiom: 'Go handles concurrency; Rust enforces invariants.'
  },
  {
    id: 4,
    title: 'Edge (Knights) Never Grants Authority — Sentinel Issues Leases',
    description: 'Agents cannot self-authorize. Every dispatch requires an ephemeral cryptographic Sentinel token lease.',
    enforcement: 'Unauthorized API runs yield strict 401 Unauthorized. Time-bounded cryptographically signed leases.',
    status: 'ENFORCED',
    axiom: 'Edge autonomy is zero without sovereign authorization.'
  },
  {
    id: 5,
    title: 'Excalibur Binds Human Consent; Arthur Seals R5/R6; Gideon Verifies with Z3',
    description: 'High-impact mutations require human signature (Excalibur Java). High-risk rings R5/R6 sealed by Arthur. Gideon invokes Z3 formal solver.',
    enforcement: 'Multi-ring cryptographic gating. Mathematical proof required prior to consequential effect release.',
    status: 'ENFORCED',
    axiom: 'Trust is not an assumption; it is a mathematical proof.'
  },
  {
    id: 6,
    title: 'The Ledger is Immutable (SQLite WAL2) — Every Action is Receipted',
    description: 'Write-Ahead-Log mode 2 ledger provides zero-loss auditability. Every agent thought and state mutation produces a signed block receipt.',
    enforcement: 'Cryptographic hash chaining with append-only WAL2 durability.',
    status: 'ENFORCED',
    axiom: 'History cannot be rewritten; reality is monotonically recorded.'
  },
  {
    id: 7,
    title: 'The System Fails Closed for New Consequential Effects',
    description: 'If network, memory cap, or consensus invariants are challenged, all write pipelines lock immediately.',
    enforcement: 'Automatic fail-closed circuit breaker tripped when vitals deviate from convergence.',
    status: 'ENFORCED',
    axiom: 'Safety over availability when integrity is indeterminate.'
  },
  {
    id: 8,
    title: '"The Model Selects; Camelot Resolves, Authorizes, and Renders."',
    description: 'LLM outputs are raw candidate intentions. Camelot-OS resolves context, authorizes via Sentinel/Excalibur, and renders through the VKG.',
    enforcement: 'Full containment of stochastic generative output behind deterministic validation firewalls.',
    status: 'ENFORCED',
    axiom: 'AI proposes; the Sovereign OS disposes.'
  },
  {
    id: 9,
    title: 'Policy Authorizes Effects — Not a Model or UI',
    description: 'Models generate candidates and the UI renders evidence; only Sentinel policy decision and Ed25519 capability leases authorize execution.',
    enforcement: 'Deterministic OPA/Sentinel policy gates and cryptographic lease verification prior to any side effect.',
    status: 'ENFORCED',
    axiom: 'Authority is derived from verified policy, never from probabilistic generation.'
  },
  {
    id: 10,
    title: 'Strict Ingress vs Enforcement Separation: Go Hub ⊕ Rust privileged Core',
    description: 'Go owns network-facing mTLS, session auth, and HTMX fragment rendering; Rust owns VFS, Wasmtime, Z3 verification, and receipt journals.',
    enforcement: 'Unidirectional dependency flow: Bifrost authenticates and transports; it never issues effect authority or makes policy decisions.',
    status: 'ENFORCED',
    axiom: 'Go coordinates IO concurrency; Rust enforces invariants and isolation.'
  }
];

export const BOOTSTRAP_PHASES: BootstrapPhase[] = [
  {
    id: 1,
    title: 'Phase 1: OS Prerequisites (Bare-Metal Foundation)',
    subtitle: 'cgroups v2 unified hierarchy, build toolchains & system baseline',
    commands: [
      'sudo apt update && sudo apt upgrade -y',
      'sudo apt install -y curl wget git build-essential openssl ca-certificates unzip tar jq gnupg lsb-release',
      'cgroup_check: /sys/fs/cgroup/cgroup.controllers [UNIFIED_V2]'
    ],
    description: 'Ensures the 8GB VPS host is fully patched and enables the Linux cgroups v2 controller for strict memory and CPU throttling.',
    status: 'completed',
    estimatedSeconds: 22,
    logs: [
      '[APT] Hit:1 http://archive.ubuntu.com/ubuntu noble InRelease',
      '[APT] Reading package lists... Done',
      '[APT] Building dependency tree... Done',
      '[CGROUPS] Checking /sys/fs/cgroup/cgroup.controllers...',
      '[CGROUPS] Found: cpuset cpu io memory hugetlb pids rdma misc',
      '[CGROUPS-v2] Unified hierarchy ACTIVE. No reboot required.'
    ]
  },
  {
    id: 2,
    title: 'Phase 2: Install Native Runtimes',
    subtitle: 'Rust (cargo 1.80+), Go 1.22.4, OpenJDK 17, PostgreSQL, MinIO, Qdrant, Neo4j, NATS, Tailscale, Caddy',
    commands: [
      'curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y',
      'wget https://go.dev/dl/go1.22.4.linux-amd64.tar.gz && tar -C /usr/local -xzf go1.22.4...',
      'sudo apt install -y openjdk-17-jre-headless postgresql postgresql-contrib caddy',
      'curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant... | install /usr/local/bin/qdrant',
      'wget neo4j-community-5.21.0-unix.tar.gz -> /opt/neo4j',
      'install minio, nats-server, tailscale'
    ],
    description: 'Installs all non-containerized baremetal runtimes into /usr/local/bin and sets up Tailscale encrypted overlay mesh.',
    status: 'completed',
    estimatedSeconds: 45,
    logs: [
      '[RUST] rustc 1.82.0-nightly (e7b003299 2026-07-14) installed to /root/.cargo/bin',
      '[GO] go version go1.22.4 linux/amd64 installed to /usr/local/go',
      '[JAVA] openjdk version "17.0.12" 2026-07-16 (headless) active',
      '[POSTGRES] PostgreSQL 16.3 (Ubuntu 16.3-1.pgdg24.04+1) initialized on port 5432',
      '[MINIO] MinIO RELEASE.2026-06-18 baremetal storage ready at /var/lib/minio',
      '[QDRANT] Qdrant v1.11.0 vector store native binary placed in /usr/local/bin/qdrant',
      '[NEO4J] Neo4j Community 5.21.0 unpacked to /opt/neo4j',
      '[NATS] nats-server v2.10.18 configured with JetStream enabled',
      '[TAILSCALE] Authenticating node 162.35.107.134 with tag:vps mesh encryption... ONLINE',
      '[CADDY] Caddy v2.8.4 web server ready on :80 and :443'
    ]
  },
  {
    id: 3,
    title: 'Phase 3: Install Camelot Native Services',
    subtitle: 'Clone unified repository & compile 9 Rust and 5 Go services with native optimization flags',
    commands: [
      'git clone https://github.com/Cyberdad247/Camelot-Ecosystem.git /opt/Camelot-Ecosystem',
      'cargo build --release for: bifrost, sentinel, gideon, arthur, ouroboros, graph-memory, omega-distiller, soup-router',
      'go build for: agent-api, nats, ecsa, provider-router, ego-bridge',
      'sudo cp infra/systemd/*.service /etc/systemd/system/ && systemctl daemon-reload'
    ],
    description: 'Compiles all core binaries directly on bare-metal hardware with LTO and target-cpu=native optimizations.',
    status: 'completed',
    estimatedSeconds: 65,
    logs: [
      '[GIT] Cloned Camelot-Ecosystem (commit 9f4e21a - "Omega Titan Core")',
      '[RUST-BUILD] Compiling camelot-bifrost v4.2.0 (release mode + LTO)... Done (0.8s)',
      '[RUST-BUILD] Compiling camelot-sentinel v3.1.0 [Lease & Zero-Trust Engine]... Done (1.2s)',
      '[RUST-BUILD] Compiling camelot-gideon v2.8.0 [Z3 Formal Theorem Prover]... Done (2.4s)',
      '[RUST-BUILD] Compiling camelot-arthur v5.0.0 [R5/R6 Ring Seal Engine]... Done (1.1s)',
      '[RUST-BUILD] Compiling camelot-ouroboros v1.5.8 [Quantized 1.58bit Weight Engine]... Done (3.1s)',
      '[RUST-BUILD] Compiling camelot-graph-memory v2.2.0... Done (0.9s)',
      '[RUST-BUILD] Compiling camelot-omega-distiller v1.9.0... Done (1.4s)',
      '[RUST-BUILD] Compiling camelot-soup-router v3.0.0... Done (0.7s)',
      '[GO-BUILD] Compiling camelot-agent-api, camelot-nats, camelot-ecsa, camelot-provider-router, camelot-ego-bridge... Done',
      '[SYSTEMD] Installed 28 unit files to /etc/systemd/system/. Daemon reloaded.'
    ]
  },
  {
    id: 4,
    title: 'Phase 4: Initialize Data & Memory',
    subtitle: 'PostgreSQL Tenant RLS, Neo4j UKG import, Qdrant World Tree 24-dim index, Ouroboros 1.58bit quant',
    commands: [
      'sudo -u postgres createdb camelot_vmax',
      'sudo -u postgres psql -d camelot_vmax -f packages/contracts/schema.sql',
      'sudo neo4j-admin database import --nodes=/opt/Camelot-Ecosystem/import/ukg_nodes.csv',
      'curl -X PUT http://localhost:6333/collections/world_tree -d {"vectors":{"size":24,"distance":"Cosine"}}',
      'camelot-ouroboros --init --quantization 1.58bit'
    ],
    description: 'Seeds relational Row-Level Security, loads the Universal Knowledge Graph (UKG), builds cosine vector indices, and quantizes state matrices.',
    status: 'completed',
    estimatedSeconds: 30,
    logs: [
      '[POSTGRES-RLS] Database `camelot_vmax` initialized. Enforced 14 tenant isolation policies.',
      '[NEO4J-UKG] Imported 48,290 nodes and 184,102 relationships into Unified Knowledge Graph.',
      '[QDRANT] Collection `world_tree` created. Metric: Cosine, Vector Dimension: 24, Segment HNSW active.',
      '[OUROBOROS] State matrix quantization completed at 1.58-bit ternary precision. Memory footprint: 384MB.'
    ]
  },
  {
    id: 5,
    title: 'Phase 5: Enable All Systemd Services',
    subtitle: 'Activate 28 native bare-metal services under strict cgroups v2 memory bounds (7.2GB cap)',
    commands: [
      'sudo systemctl enable --now camelot-bifrost camelot-sentinel camelot-excalibur camelot-gideon...',
      'cgroup enforcement: MemoryMax=7200M total across system slices'
    ],
    description: 'Brings all 28 services online under systemd supervision with automated restarts and OOM killer protection.',
    status: 'completed',
    estimatedSeconds: 15,
    logs: [
      '[SYSTEMD] camelot-bifrost.service: Active (running) PID 2841 [Go Router]',
      '[SYSTEMD] camelot-sentinel.service: Active (running) PID 2842 [Rust Lease Authority]',
      '[SYSTEMD] camelot-excalibur.service: Active (running) PID 2843 [Java 17 Consent Engine]',
      '[SYSTEMD] camelot-gideon.service: Active (running) PID 2844 [Z3 Prover Engine]',
      '[SYSTEMD] camelot-arthur.service: Active (running) PID 2845 [R5/R6 Ring Sealer]',
      '[SYSTEMD] camelot-ledger.service: Active (running) PID 2846 [SQLite WAL2]',
      '[SYSTEMD] 28/28 systemd units ACTIVE. All cgroups v2 limits locked.'
    ]
  },
  {
    id: 6,
    title: 'Phase 6: CORS & Admin Access',
    subtitle: 'Bind and verify ports: Neo4j (7474/7687), Qdrant (6333), MinIO (9000), Postgres (5432), Caddy (80/443), NATS (4222)',
    commands: [
      'sudo systemctl enable --now neo4j qdrant minio postgresql caddy nats'
    ],
    description: 'Binds administrative and broker ports to localhost and Tailscale mesh interface only.',
    status: 'completed',
    estimatedSeconds: 10,
    logs: [
      '[PORT-AUDIT] 127.0.0.1:5432 (Postgres) - LISTENING (Local/RLS)',
      '[PORT-AUDIT] 127.0.0.1:6333 (Qdrant) - LISTENING (HTTP Vector)',
      '[PORT-AUDIT] 127.0.0.1:7474 (Neo4j Bolt/HTTP) - LISTENING',
      '[PORT-AUDIT] 127.0.0.1:9000 (MinIO S3) - LISTENING',
      '[PORT-AUDIT] 127.0.0.1:4222 (NATS Core) - LISTENING',
      '[PORT-AUDIT] 100.x.y.z:8443 (Tailscale mTLS API) - LISTENING'
    ]
  },
  {
    id: 7,
    title: 'Phase 7: Deploy Frontend (VKG-HUD)',
    subtitle: 'Deploy VKG-HUD static bundle to /var/www/camelot & configure Caddy HTTPS reverse proxy',
    commands: [
      'sudo mkdir -p /var/www/camelot',
      'sudo cp -r /opt/Camelot-Ecosystem/apps/vkg-hud/dist/* /var/www/camelot/',
      'sudo tee /etc/caddy/Caddyfile (domain: camelot.invisionedmarketing.com)',
      'sudo systemctl restart caddy'
    ],
    description: 'Deploys the production Visual Knowledge Graph Head-Up Display behind Caddy with automated Let\'s Encrypt TLS and HSTS.',
    status: 'completed',
    estimatedSeconds: 12,
    logs: [
      '[VKG-HUD] Copied static web assets to /var/www/camelot',
      '[CADDY] Loaded Caddyfile for camelot.invisionedmarketing.com',
      '[TLS] Certificate obtained via ACME TLS-ALPN-01 challenge from Let\'s Encrypt',
      '[REVERSE-PROXY] Routing /api/* -> 127.0.0.1:8443 (Sentinel + Bifrost Engine)',
      '[CADDY] Service restarted successfully. HTTP/3 and HTTP/2 active.'
    ]
  },
  {
    id: 8,
    title: 'Phase 8: Verification (Gideon Gauntlet)',
    subtitle: 'Convergence check (camelot-vitals -> Exit 0), Sentinel Lease 401 test, MCP Web Search verify, UI HTTP 200',
    commands: [
      'camelot-vitals -> Exit Code: 0 (CONVERGED)',
      'curl -X POST http://localhost:8080/v1/agents/run (Expected: 401 Unauthorized)',
      'curl -X POST http://localhost:8080/v1/mcp/web_search -d {"query":"Camelot-OS"}',
      'curl -s https://camelot.invisionedmarketing.com | grep "Camelot-OS" (HTTP 200 OK)'
    ],
    description: 'The final zero-trust verification gauntlet confirming that the hub is fully convergent and fails closed against unauthenticated requests.',
    status: 'completed',
    estimatedSeconds: 15,
    logs: [
      '[GIDEON-GAUNTLET] Running camelot-vitals convergence probe...',
      '[GIDEON] Invariant checking: 44 invariants evaluated via Z3 solver. All SAT.',
      '[GIDEON] System Status: CONVERGED (Exit Code: 0)',
      '[SENTINEL-TEST] POST /v1/agents/run without lease token -> HTTP 401 Unauthorized [PASSED: Edge cannot self-authorize]',
      '[MCP-TEST] POST /v1/mcp/web_search query="Camelot-OS" -> 200 OK (3 search nodes resolved)',
      '[UI-TEST] GET https://camelot.invisionedmarketing.com -> HTTP 200 OK ("Camelot-OS vMAX OMEGA TITAN")',
      '[SYSTEM HALT] Baremetal Hub is fully operational. ⚜️_SOVEREIGN_TRUTH'
    ]
  }
];

export const CAMELOT_SERVICES: CamelotService[] = [
  // Core Orchestration
  {
    id: 'bifrost',
    name: 'Bifrost Router',
    unitName: 'camelot-bifrost.service',
    language: 'Go',
    category: 'core_orchestration',
    allocatedRamMB: 180,
    cgroupLimitMB: 256,
    currentRamMB: 142,
    port: 8443,
    status: 'active',
    description: 'High-speed Go mesh router handling inter-node mTLS packet routing and sub-millisecond edge dispatch.',
    zeroTrustRole: 'Packet Gatekeeper & Ingress Reverse Proxy',
    systemdExec: '/usr/local/bin/camelot-bifrost --listen 127.0.0.1:8443',
    z3Verified: true
  },
  {
    id: 'sentinel',
    name: 'Sentinel Authority',
    unitName: 'camelot-sentinel.service',
    language: 'Rust',
    category: 'core_orchestration',
    allocatedRamMB: 120,
    cgroupLimitMB: 192,
    currentRamMB: 88,
    port: 8080,
    status: 'active',
    description: 'Zero-Trust ephemeral lease token dispenser. Edge Knights can never act without active cryptographically bound lease.',
    zeroTrustRole: 'Sovereign Lease & Token Issuer',
    systemdExec: '/usr/local/bin/camelot-sentinel --lease-ttl 300s',
    z3Verified: true
  },
  {
    id: 'excalibur',
    name: 'Excalibur Consent Engine',
    unitName: 'camelot-excalibur.service',
    language: 'Java',
    category: 'core_orchestration',
    allocatedRamMB: 420,
    cgroupLimitMB: 512,
    currentRamMB: 380,
    port: 8900,
    status: 'active',
    description: 'Java 17 Human Consent and sovereign cryptographic signature validation. Binds human will to agent actions.',
    zeroTrustRole: 'Human-in-the-Loop Sovereign Gate',
    systemdExec: '/usr/bin/java -jar /usr/local/lib/camelot-excalibur.jar',
    z3Verified: true
  },
  {
    id: 'gideon',
    name: 'Gideon Z3 Verifier',
    unitName: 'camelot-gideon.service',
    language: 'Rust',
    category: 'core_orchestration',
    allocatedRamMB: 280,
    cgroupLimitMB: 384,
    currentRamMB: 215,
    port: 8091,
    status: 'converged',
    description: 'Rust formal theorem solver embedding Z3. Proves invariants on agent action plans prior to emission.',
    zeroTrustRole: 'Formal Invariant & Convergence Verifier',
    systemdExec: '/usr/local/bin/camelot-gideon --z3-threads 2',
    z3Verified: true
  },
  {
    id: 'arthur',
    name: 'Arthur Ring Seal',
    unitName: 'camelot-arthur.service',
    language: 'Rust',
    category: 'core_orchestration',
    allocatedRamMB: 140,
    cgroupLimitMB: 200,
    currentRamMB: 98,
    port: 8092,
    status: 'active',
    description: 'Seals ring boundaries R5 (destructive filesystem writes) and R6 (external network calls).',
    zeroTrustRole: 'R5/R6 Execution Ring Seal Authority',
    systemdExec: '/usr/local/bin/camelot-arthur --strict-isolation',
    z3Verified: true
  },
  {
    id: 'ledger',
    name: 'Immutable Ledger',
    unitName: 'camelot-ledger.service',
    language: 'Rust',
    category: 'data_memory',
    allocatedRamMB: 110,
    cgroupLimitMB: 180,
    currentRamMB: 84,
    port: 8093,
    status: 'active',
    description: 'SQLite WAL2 append-only hash-chained ledger. Receipts all system mutations and sovereign commands.',
    zeroTrustRole: 'Monotonic History & Audit Engine',
    systemdExec: '/usr/local/bin/camelot-ledger --db /var/lib/camelot/ledger.db --wal2',
    z3Verified: true
  },
  {
    id: 'agent_api',
    name: 'Agent API',
    unitName: 'camelot-agent-api.service',
    language: 'Go',
    category: 'core_orchestration',
    allocatedRamMB: 160,
    cgroupLimitMB: 240,
    currentRamMB: 128,
    port: 8085,
    status: 'active',
    description: 'High-throughput Go agent dispatching endpoint. Connects Sovereign directives to WASI workers.',
    zeroTrustRole: 'Agent Orchestration Pipeline',
    systemdExec: '/usr/local/bin/camelot-agent-api',
    z3Verified: true
  },

  // Data & Memory
  {
    id: 'postgres',
    name: 'PostgreSQL (Tenant RLS)',
    unitName: 'postgresql.service',
    language: 'Native Bin',
    category: 'data_memory',
    allocatedRamMB: 512,
    cgroupLimitMB: 680,
    currentRamMB: 440,
    port: 5432,
    status: 'active',
    description: 'Baremetal PostgreSQL 16 enforcing strict Row Level Security (RLS) across all multi-tenant contexts.',
    zeroTrustRole: 'Relational Store with Row-Level Isolation',
    systemdExec: '/usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/16/main',
    z3Verified: true
  },
  {
    id: 'neo4j',
    name: 'Neo4j UKG Graph',
    unitName: 'neo4j.service',
    language: 'Java',
    category: 'data_memory',
    allocatedRamMB: 750,
    cgroupLimitMB: 950,
    currentRamMB: 680,
    port: 7474,
    status: 'active',
    description: 'Unified Knowledge Graph (UKG) holding ontology, agent relationships, and semantic entity maps.',
    zeroTrustRole: 'Semantic Topology & Relationship Graph',
    systemdExec: '/opt/neo4j/bin/neo4j console',
    z3Verified: true
  },
  {
    id: 'qdrant',
    name: 'Qdrant Vector Store',
    unitName: 'qdrant.service',
    language: 'Rust',
    category: 'data_memory',
    allocatedRamMB: 380,
    cgroupLimitMB: 500,
    currentRamMB: 310,
    port: 6333,
    status: 'active',
    description: 'High-speed Rust vector database managing 24-dimensional World Tree embeddings with HNSW indexing.',
    zeroTrustRole: 'Dense Semantic Vector Memory',
    systemdExec: '/usr/local/bin/qdrant --config-path /etc/qdrant/config.yaml',
    z3Verified: true
  },
  {
    id: 'minio',
    name: 'MinIO S3 Object Store',
    unitName: 'minio.service',
    language: 'Go',
    category: 'data_memory',
    allocatedRamMB: 220,
    cgroupLimitMB: 300,
    currentRamMB: 175,
    port: 9000,
    status: 'active',
    description: 'Baremetal S3-compatible blob storage for raw artifacts, skill packages, and memory snapshots.',
    zeroTrustRole: 'Immutable Artifact Vault',
    systemdExec: '/usr/local/bin/minio server /var/lib/minio',
    z3Verified: true
  },
  {
    id: 'graph_memory',
    name: 'Graph Memory Daemon',
    unitName: 'camelot-graph-memory.service',
    language: 'Rust',
    category: 'data_memory',
    allocatedRamMB: 160,
    cgroupLimitMB: 220,
    currentRamMB: 120,
    port: 8094,
    status: 'active',
    description: 'Rust service synchronizing real-time episodic agent observations with Neo4j UKG nodes.',
    zeroTrustRole: 'Episodic Memory Synthesizer',
    systemdExec: '/usr/local/bin/camelot-graph-memory --sync-interval 5s',
    z3Verified: true
  },

  // Runtimes & Routing
  {
    id: 'nats',
    name: 'NATS JetStream Broker',
    unitName: 'nats.service',
    language: 'Go',
    category: 'runtimes_routing',
    allocatedRamMB: 140,
    cgroupLimitMB: 200,
    currentRamMB: 96,
    port: 4222,
    status: 'active',
    description: 'Ultra-low latency pub/sub bus coordinating inter-service message flow and event streams.',
    zeroTrustRole: 'Real-time Event Backbone',
    systemdExec: '/usr/local/bin/nats-server -c /etc/nats/nats.conf',
    z3Verified: true
  },
  {
    id: 'wasmtime',
    name: 'Wasmtime WASI Sandbox',
    unitName: 'camelot-wasmtime.service',
    language: 'Rust',
    category: 'runtimes_routing',
    allocatedRamMB: 240,
    cgroupLimitMB: 350,
    currentRamMB: 180,
    status: 'active',
    description: 'WASI runtime executing deterministic agent plugins and skill modules in microsecond memory compartments.',
    zeroTrustRole: 'Isolated Deterministic Execution Pool',
    systemdExec: '/usr/local/bin/camelot-wasmtime --pool-size 16',
    z3Verified: true
  },
  {
    id: 'firecracker',
    name: 'Firecracker MicroVM Mgr',
    unitName: 'camelot-firecracker.service',
    language: 'Rust',
    category: 'runtimes_routing',
    allocatedRamMB: 300,
    cgroupLimitMB: 450,
    currentRamMB: 220,
    status: 'active',
    description: 'KVM-accelerated microVM supervisor for running untrusted guest binaries in sub-5ms boot times.',
    zeroTrustRole: 'Untrusted Workload Jail',
    systemdExec: '/usr/local/bin/camelot-firecracker --jailer-root /srv/jailer',
    z3Verified: true
  },
  {
    id: 'ouroboros',
    name: 'Ouroboros Quant Matrix',
    unitName: 'camelot-ouroboros.service',
    language: 'Rust',
    category: 'intelligence_tools',
    allocatedRamMB: 384,
    cgroupLimitMB: 500,
    currentRamMB: 360,
    port: 8095,
    status: 'active',
    description: '1.58-bit ternary quantized model runtime executing local continuous self-distillation.',
    zeroTrustRole: 'Local Compact Model Accelerator',
    systemdExec: '/usr/local/bin/camelot-ouroboros --quantization 1.58bit',
    z3Verified: true
  },
  {
    id: 'omega_distiller',
    name: 'Omega Distiller',
    unitName: 'camelot-omega-distiller.service',
    language: 'Rust',
    category: 'intelligence_tools',
    allocatedRamMB: 210,
    cgroupLimitMB: 300,
    currentRamMB: 165,
    status: 'active',
    description: 'Distills telemetry and reasoning traces into compact deterministic skills.',
    zeroTrustRole: 'Knowledge Compression Pipeline',
    systemdExec: '/usr/local/bin/camelot-omega-distiller',
    z3Verified: true
  },
  {
    id: 'soup_router',
    name: 'Soup Router',
    unitName: 'camelot-soup-router.service',
    language: 'Rust',
    category: 'runtimes_routing',
    allocatedRamMB: 110,
    cgroupLimitMB: 160,
    currentRamMB: 75,
    port: 8096,
    status: 'active',
    description: 'Multi-model inference load balancer blending and gating frontier models.',
    zeroTrustRole: 'Model Gate & Redundancy Balancer',
    systemdExec: '/usr/local/bin/camelot-soup-router',
    z3Verified: true
  },
  {
    id: 'ecsa',
    name: 'ECSA Consensus Engine',
    unitName: 'camelot-ecsa.service',
    language: 'Go',
    category: 'runtimes_routing',
    allocatedRamMB: 130,
    cgroupLimitMB: 180,
    currentRamMB: 92,
    port: 8097,
    status: 'active',
    description: 'Ephemeral Consensus & State Arbitration engine ensuring multi-knight action coherence.',
    zeroTrustRole: 'State Arbiter & Anti-Fork Engine',
    systemdExec: '/usr/local/bin/camelot-ecsa',
    z3Verified: true
  },
  {
    id: 'ego_bridge',
    name: 'Ego Bridge',
    unitName: 'camelot-ego-bridge.service',
    language: 'Go',
    category: 'runtimes_routing',
    allocatedRamMB: 95,
    cgroupLimitMB: 140,
    currentRamMB: 64,
    status: 'active',
    description: 'Connects external client interfaces and MCP tools to sovereign core bus.',
    zeroTrustRole: 'External MCP Protocol Bridge',
    systemdExec: '/usr/local/bin/camelot-ego-bridge',
    z3Verified: true
  },
  {
    id: 'kinetic_forge',
    name: 'Kinetic Forge',
    unitName: 'camelot-kinetic-forge.service',
    language: 'Rust',
    category: 'intelligence_tools',
    allocatedRamMB: 150,
    cgroupLimitMB: 220,
    currentRamMB: 110,
    status: 'active',
    description: 'WASM tool compiler generating executable primitives dynamically from verified specifications.',
    zeroTrustRole: 'Just-in-Time Tool Generator',
    systemdExec: '/usr/local/bin/camelot-kinetic-forge',
    z3Verified: true
  },
  {
    id: 'psi_monitor',
    name: 'Psi Monitor',
    unitName: 'camelot-psi-monitor.service',
    language: 'Rust',
    category: 'security_mesh',
    allocatedRamMB: 80,
    cgroupLimitMB: 120,
    currentRamMB: 48,
    status: 'active',
    description: 'Linux Pressure Stall Information (PSI) daemon tracking CPU, Memory, and IO pressure against 8GB budget.',
    zeroTrustRole: 'Resource Starvation Guard',
    systemdExec: '/usr/local/bin/camelot-psi-monitor',
    z3Verified: true
  },
  {
    id: 'vitals',
    name: 'Camelot Vitals Probe',
    unitName: 'camelot-vitals.service',
    language: 'Rust',
    category: 'security_mesh',
    allocatedRamMB: 75,
    cgroupLimitMB: 110,
    currentRamMB: 42,
    status: 'converged',
    description: 'System health probe testing 44 convergence invariants; exits with code 0 on absolute harmony.',
    zeroTrustRole: 'Zero-Trust Convergence Audit',
    systemdExec: '/usr/local/bin/camelot-vitals --daemon',
    z3Verified: true
  },
  {
    id: 'evolution',
    name: 'Evolution Engine',
    unitName: 'camelot-evolution.service',
    language: 'Rust',
    category: 'intelligence_tools',
    allocatedRamMB: 125,
    cgroupLimitMB: 180,
    currentRamMB: 82,
    status: 'active',
    description: 'Autonomous architectural refactoring and self-optimizing prompt compiler.',
    zeroTrustRole: 'Autonomous Evolutionary Refactorer',
    systemdExec: '/usr/local/bin/camelot-evolution',
    z3Verified: true
  },
  {
    id: 'cleaner',
    name: 'Sovereign Cleaner',
    unitName: 'camelot-cleaner.service',
    language: 'Go',
    category: 'security_mesh',
    allocatedRamMB: 60,
    cgroupLimitMB: 90,
    currentRamMB: 34,
    status: 'active',
    description: 'Enforces WAL checkpoints, garbage collects stale microVM snapshots, and frees temporary cgroup buffers.',
    zeroTrustRole: 'Zero-Entropy Sanitizer',
    systemdExec: '/usr/local/bin/camelot-cleaner',
    z3Verified: true
  },
  {
    id: 'open_notebook',
    name: 'Open-Notebook (Deep Reasoning)',
    unitName: 'camelot-open-notebook.service',
    language: 'Python',
    category: 'cognitive_intelligence',
    allocatedRamMB: 380,
    cgroupLimitMB: 512,
    currentRamMB: 310,
    port: 8502,
    status: 'active',
    description: 'Open source AI research assistant & multi-source notebook grounding engine (https://github.com/lfnovo/open-notebook.git). Powers Twin Quantum Brain deep research, podcast generation & vector retrieval.',
    zeroTrustRole: 'Source-Grounded Research & Multi-LLM Synthesizer',
    systemdExec: '/opt/open-notebook/venv/bin/python /opt/open-notebook/app.py --port 8502',
    z3Verified: true,
    repoUrl: 'https://github.com/lfnovo/open-notebook.git'
  },
  {
    id: 'caddy',
    name: 'Caddy Webserver & Mesh',
    unitName: 'caddy.service',
    language: 'Go',
    category: 'security_mesh',
    allocatedRamMB: 110,
    cgroupLimitMB: 160,
    currentRamMB: 72,
    port: 443,
    status: 'active',
    description: 'Reverse proxy serving VKG-HUD with automatic HTTPS, HSTS, strict CSP headers, and zstd/gzip compression.',
    zeroTrustRole: 'Encrypted Public Ingress & CSP Enforcement',
    systemdExec: '/usr/bin/caddy run --environ --config /etc/caddy/Caddyfile',
    z3Verified: true
  }
];

export const INITIAL_VITALS: SystemVitals = {
  targetHost: '162.35.107.134',
  hostAlias: 'Cybertronia Hub',
  os: 'Ubuntu 24.04.1 LTS (Noble Numbat)',
  kernel: 'Linux 6.8.0-40-generic x86_64',
  cgroups: 'cgroups v2 (Unified Hierarchy)',
  totalRamMB: 8192,
  scarcityCapMB: 7372, // 7.2 GB
  kernelReserveMB: 820,
  usedRamMB: 4892,
  tailscaleStatus: 'CONNECTED',
  tailscaleIp: '100.112.44.89',
  tailscaleTag: 'tag:vps',
  gideonConvergence: 'CONVERGED',
  caddyStatus: 'ONLINE',
  caddyDomain: 'camelot.invisionedmarketing.com',
  sentinelLeaseCount: 14,
  wal2LedgerTxCount: 849,
  uptimeSeconds: 14820
};

export const SAMPLE_AGENTS: {
  id: AgentMission['agentId'];
  name: string;
  title: string;
  specialty: string;
  defaultPrompt: string;
}[] = [
  {
    id: 'sir_codex',
    name: 'Sir Codex',
    title: 'Knight of Deterministic Logic & WASI Synthesizer',
    specialty: 'Rust/WASM baremetal code synthesis, memory optimization, formal invariant checking',
    defaultPrompt: 'Synthesize a high-throughput WASI memory filter adhering to the 8GB Scarcity Protocol.'
  },
  {
    id: 'sir_galahad',
    name: 'Sir Galahad',
    title: 'Knight of the Pure Invariant (Z3 Theorem Prover)',
    specialty: 'Z3 formal mathematical logic, state transition safety proofs, anti-hallucination firewalls',
    defaultPrompt: 'Verify state transition safety invariants for the proposed Neo4j UKG relationship mutation.'
  },
  {
    id: 'sir_lancelot',
    name: 'Sir Lancelot',
    title: 'Knight Champion of the Kinetic Ring (R5/R6 Dispatch)',
    specialty: 'High-speed I/O execution, Firecracker microVM orchestration, external network negotiation',
    defaultPrompt: 'Dispatch untrusted external webhook payload into an isolated Firecracker microVM containerless jail.'
  },
  {
    id: 'lady_guinevere',
    name: 'Lady Guinevere',
    title: 'Keeper of the Universal Knowledge Graph (UKG)',
    specialty: 'Neo4j UKG entity ontology, multi-tenant RLS schema arbitration, semantic graph synthesis',
    defaultPrompt: 'Query the 48,290 nodes in the UKG to locate the nearest episodic memory path for sovereign identity.'
  },
  {
    id: 'merlin',
    name: 'Merlin the Enchanter',
    title: 'Archmage of Ouroboros (1.58-bit Quantization)',
    specialty: '1.58-bit ternary matrix self-distillation, continuous model alignment, entropy reduction',
    defaultPrompt: 'Trigger continuous self-distillation cycle across active telemetry traces into Ouroboros 1.58-bit matrix.'
  },
  {
    id: 'sir_percival',
    name: 'Sir Percival',
    title: 'Knight of the Sacred Ledger (SQLite WAL2)',
    specialty: 'Append-only monotonic audit blocks, cryptographic hash chaining, Arthur R5/R6 seal generation',
    defaultPrompt: 'Audit recent 100 WAL2 ledger transactions and compute cryptographic Merkle root.'
  }
];

export const INITIAL_LEDGER_RECEIPTS: LedgerReceipt[] = [
  {
    receiptId: 'RC-892401',
    timestamp: '2026-08-27 18:24:12 UTC',
    actor: 'BOOTSTRAP_ORCHESTRATOR',
    action: 'SYSTEM_BOOTSTRAP_INITIALIZE',
    hash: '0x8f74a9b24cd61e3892ab4f012c8e3902',
    signature: 'SIG_EXCALIBUR_ED25519_992a',
    blockHeight: 847,
    r5_r6_seal: true
  },
  {
    receiptId: 'RC-892402',
    timestamp: '2026-08-27 18:25:40 UTC',
    actor: 'CGROUP_CONTROLLER',
    action: 'LOCK_MEMORY_MAX_7200M',
    hash: '0x3a4b91f09c2e11894b5e28a99d0124c6',
    signature: 'SIG_ARTHUR_SEAL_441c',
    blockHeight: 848,
    r5_r6_seal: true
  },
  {
    receiptId: 'RC-892403',
    timestamp: '2026-08-27 18:28:19 UTC',
    actor: 'GIDEON_VERIFIER',
    action: 'PROVE_ALL_44_CONVERGENCE_INVARIANTS',
    hash: '0x7e120da9556ef3802ba94017dfc89012',
    signature: 'SIG_Z3_SAT_PROOF_009f',
    blockHeight: 849,
    r5_r6_seal: true
  }
];
