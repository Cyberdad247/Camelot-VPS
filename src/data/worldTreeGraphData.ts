import { WorldTreeGraphData, GraphNode, GraphLink, NodeState, RiskTier, NodeKind, LinkKind } from '../types/worldTreeGraph';

export const STATE_COLORS: Record<NodeState, string> = {
  verified: '#f5c542',          // gold
  running: '#00e5ff',           // cyan
  approval_required: '#ffbf00', // amber
  failed: '#ff4444',            // red
  quarantined: '#9d4edd',       // violet
  stale: '#888888'              // gray
};

export const LINK_COLORS: Record<string, string> = {
  produced: '#6b4c9a',
  depends_on: '#38bdf8',
  verifies: '#10b981',
  flows_to: '#eab308',
  synthesizes: '#f43f5e',
  quarantines: '#a855f7'
};

// Base Canonical 50-node World Tree Dataset
export function generateCanonicalGraph(nodeCount: 50 | 200 | 500 = 50): WorldTreeGraphData {
  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];

  // Core anchor missions & infrastructure matching the exact specification:
  // "mission_01", "CRM integration", "approval_required", "R4", trust 0, val 15
  nodes.push(
    {
      id: 'mission_01',
      kind: 'mission',
      label: 'CRM integration',
      state: 'approval_required',
      risk_tier: 'R4',
      trust_tier: 0,
      x: 120,
      y: 80,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 15,
      color: STATE_COLORS.approval_required,
      stratum: 'apex',
      summary: 'Enterprise CRM sync with strict customer PII verification barrier.'
    },
    {
      id: 'task_01',
      kind: 'task',
      label: 'Tenant Auth Validator',
      state: 'verified',
      risk_tier: 'R2',
      trust_tier: 3,
      x: 60,
      y: 40,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 14,
      color: STATE_COLORS.verified,
      stratum: 'apex',
      summary: 'Z3 verified token validation lease via Redis Memcastle 6379.'
    },
    {
      id: 'manifest_01',
      kind: 'manifest',
      label: 'Signed WASM Bundle',
      state: 'running',
      risk_tier: 'R1',
      trust_tier: 2,
      x: 180,
      y: 120,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 12,
      color: STATE_COLORS.running,
      stratum: 'brains',
      summary: 'WASM32 zero-copy memory slab with deterministic execution hash.'
    },
    {
      id: 'verifier_01',
      kind: 'verifier',
      label: 'Z3 Invariant Sentinel',
      state: 'verified',
      risk_tier: 'R1',
      trust_tier: 3,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 18,
      color: STATE_COLORS.verified,
      stratum: 'apex',
      summary: 'Continuous SMT solver verification enforcing Axioms 1-44.'
    },
    {
      id: 'ouroboros_ssm',
      kind: 'ssm_loop',
      label: '1.58b Ternary SSM Loop',
      state: 'running',
      risk_tier: 'R2',
      trust_tier: 3,
      x: -80,
      y: 100,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 20,
      color: STATE_COLORS.running,
      stratum: 'ouroboros',
      summary: 'BitNet recurrent weights in {-1, 0, 1} cycling under 8GB protocol.'
    },
    {
      id: 'viking_dma',
      kind: 'drakkar_buffer',
      label: 'Viking Drakkar Ring Buffer',
      state: 'verified',
      risk_tier: 'R1',
      trust_tier: 3,
      x: 90,
      y: 220,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 16,
      color: STATE_COLORS.verified,
      stratum: 'rivers',
      summary: 'Zero-copy DMA ring refractions from /vfs/refractions/*.'
    },
    {
      id: 'twin_brains_sink',
      kind: 'memory_palace',
      label: 'Twin Quantum Brains Sink',
      state: 'running',
      risk_tier: 'R2',
      trust_tier: 2,
      x: -140,
      y: -60,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 17,
      color: STATE_COLORS.running,
      stratum: 'brains',
      summary: 'Bi-directional notebook sync (Open-Notebook ⟷ NotebookLM).'
    },
    {
      id: 'quarantined_worker',
      kind: 'service',
      label: 'Unverified External Ingress',
      state: 'quarantined',
      risk_tier: 'R4',
      trust_tier: 0,
      x: 220,
      y: -100,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 10,
      color: STATE_COLORS.quarantined,
      stratum: 'apex',
      summary: 'External probe blocked by EXCALIBUR Zero-Trust Aegis Shield.'
    },
    {
      id: 'stale_cache_node',
      kind: 'service',
      label: 'Legacy Redis Epoch Cache',
      state: 'stale',
      risk_tier: 'R2',
      trust_tier: 1,
      x: -190,
      y: 160,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 8,
      color: STATE_COLORS.stale,
      stratum: 'ouroboros',
      summary: 'Expired TTL cache waiting for garbage collection prune.'
    },
    {
      id: 'failed_handshake',
      kind: 'task',
      label: 'BGP Route Peer Invariant',
      state: 'failed',
      risk_tier: 'R3',
      trust_tier: 0,
      x: 160,
      y: -40,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val: 11,
      color: STATE_COLORS.failed,
      stratum: 'apex',
      summary: 'Peer latency exceeded 120ms threshold, circuit breaker open.'
    }
  );

  // Canonical initial links
  links.push(
    { source: 'task_01', target: 'manifest_01', kind: 'produced', color: LINK_COLORS.produced, curvature: 0.0, active: true },
    { source: 'mission_01', target: 'manifest_01', kind: 'depends_on', color: LINK_COLORS.depends_on, curvature: 0.0 },
    { source: 'verifier_01', target: 'task_01', kind: 'verifies', color: LINK_COLORS.verifies, curvature: 0.0, active: true },
    { source: 'verifier_01', target: 'ouroboros_ssm', kind: 'verifies', color: LINK_COLORS.verifies, curvature: 0.0, active: true },
    { source: 'manifest_01', target: 'viking_dma', kind: 'flows_to', color: LINK_COLORS.flows_to, curvature: 0.0, active: true },
    { source: 'ouroboros_ssm', target: 'viking_dma', kind: 'synthesizes', color: LINK_COLORS.synthesizes, curvature: 0.0, active: true },
    { source: 'verifier_01', target: 'quarantined_worker', kind: 'quarantines', color: LINK_COLORS.quarantines, curvature: 0.0 },
    { source: 'twin_brains_sink', target: 'ouroboros_ssm', kind: 'flows_to', color: LINK_COLORS.flows_to, curvature: 0.0, active: true },
    { source: 'verifier_01', target: 'failed_handshake', kind: 'quarantines', color: LINK_COLORS.quarantines, curvature: 0.0 }
  );

  // Generate remaining nodes to reach target count (50, 200, 500)
  const nodeKinds: NodeKind[] = ['mission', 'task', 'manifest', 'verifier', 'service', 'memory_palace', 'drakkar_buffer', 'ssm_loop'];
  const nodeStates: NodeState[] = ['verified', 'verified', 'running', 'approval_required', 'running', 'failed', 'quarantined', 'stale'];
  const strata: ('apex' | 'brains' | 'ouroboros' | 'rivers')[] = ['apex', 'brains', 'ouroboros', 'rivers'];
  const labels = [
    'Telemetry Tap', 'Rust Operator RPC', 'Neo4j Schema Lens', 'BitNet Quantizer', 
    'Anya Gatekeeper', 'Memfd Slab Malloc', 'Z3 Sat Checker', 'HTMX Fragment Stream', 
    'Kernel Ring 0 DMA', 'KVM Hypervisor Bridge', 'Zero-Trust Shield', 'Audit Ledger Receipt',
    'Cognitive Sink Proxy', 'Prometheus Scraper', 'Envoy Sidecar Filter', 'PostgreSQL WAL2 Tap',
    'OpenClaw ARM Driver', 'Drakkar Packet Buffer', 'Ouroboros Weight Matrix', 'WASI Pure Logic'
  ];

  const existingCount = nodes.length;
  for (let i = existingCount; i < nodeCount; i++) {
    const kind = nodeKinds[i % nodeKinds.length];
    const state = nodeStates[(i * 3 + 1) % nodeStates.length];
    const riskTier: RiskTier = (`R${(i % 4) + 1}`) as RiskTier;
    const trustTier = state === 'verified' ? 3 : state === 'running' ? 2 : state === 'approval_required' ? 1 : 0;
    const stratum = strata[i % strata.length];
    
    // Spread in 2D space with organic radial distribution
    const radius = 100 + Math.sqrt(i) * 22;
    const angle = (i * 137.5 * Math.PI) / 180; // Golden angle distribution
    const x = Math.round(Math.cos(angle) * radius);
    const y = Math.round(Math.sin(angle) * radius);

    const val = 5 + (trustTier * 3) + (i % 4);
    const label = `${labels[i % labels.length]} #${i + 1}`;

    nodes.push({
      id: `node_${i + 1}`,
      kind,
      label,
      state,
      risk_tier: riskTier,
      trust_tier: trustTier,
      x,
      y,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      val,
      color: STATE_COLORS[state],
      stratum,
      summary: `Automated topology entity under tenant ten_01 scope. Trust tier T${trustTier}.`
    });
  }

  // Interconnect newly generated nodes
  const linkKinds: LinkKind[] = ['produced', 'depends_on', 'verifies', 'flows_to', 'synthesizes'];
  for (let i = existingCount; i < nodeCount; i++) {
    const targetIdx = Math.max(0, Math.floor(i / 2) + (i % 3) - 1);
    const kind = linkKinds[i % linkKinds.length];
    links.push({
      id: `link_${i}`,
      source: nodes[i].id,
      target: nodes[targetIdx].id,
      kind,
      color: LINK_COLORS[kind] || '#6b4c9a',
      curvature: 0.0,
      active: nodes[i].state === 'running' || nodes[i].state === 'verified'
    });

    // Cross link for interesting graph topology
    if (i % 5 === 0 && i > 3) {
      const crossTarget = (i * 7) % existingCount;
      links.push({
        id: `cross_link_${i}`,
        source: nodes[i].id,
        target: nodes[crossTarget].id,
        kind: 'verifies',
        color: LINK_COLORS.verifies,
        curvature: 0.0,
        active: false
      });
    }
  }

  return {
    scope: {
      tenant_id: 'ten_01',
      workspace_id: 'ws_01'
    },
    revision: 412,
    nodes,
    links
  };
}

// Global fetch proxy helper to satisfy: fetch('/v1/graph/timeline?scope=current')
export async function fetchWorldTreeTimeline(scope = 'current', nodeCount: 50 | 200 | 500 = 50): Promise<WorldTreeGraphData> {
  // Check if real server has this endpoint
  try {
    const res = await fetch(`/v1/graph/timeline?scope=${scope}`);
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.nodes) && data.nodes.length > 0) {
        return data;
      }
    }
  } catch (err) {
    // Network fallback below
  }

  // Guaranteed fallback satisfying the exact prompt schema
  return generateCanonicalGraph(nodeCount);
}
