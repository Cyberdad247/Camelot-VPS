export type NodeState = 
  | 'verified' 
  | 'running' 
  | 'approval_required' 
  | 'failed' 
  | 'quarantined' 
  | 'stale';

export type RiskTier = 'R1' | 'R2' | 'R3' | 'R4';

export type NodeKind = 
  | 'mission' 
  | 'task' 
  | 'manifest' 
  | 'verifier' 
  | 'service' 
  | 'memory_palace' 
  | 'drakkar_buffer' 
  | 'ssm_loop';

export type LinkKind = 
  | 'produced' 
  | 'depends_on' 
  | 'verifies' 
  | 'flows_to' 
  | 'synthesizes' 
  | 'quarantines';

export interface GraphNode {
  id: string;
  kind: NodeKind | string;
  label: string;
  state: NodeState;
  risk_tier: RiskTier;
  trust_tier: number; // 0 - 3
  x: number;
  y: number;
  z: number;
  vx?: number;
  vy?: number;
  vz?: number;
  val: number; // Importance value
  color: string;
  stratum?: 'apex' | 'brains' | 'ouroboros' | 'rivers';
  summary?: string;
  metadata?: Record<string, any>;
  // Runtime internal properties
  __initialX?: number;
  __initialY?: number;
}

export interface GraphLink {
  id?: string;
  source: string | GraphNode;
  target: string | GraphNode;
  kind: LinkKind | string;
  color: string;
  curvature: number;
  active?: boolean;
  throughput?: string;
  flow_rate?: number;
}

export interface WorldTreeGraphData {
  scope: {
    tenant_id: string;
    workspace_id: string;
  };
  revision: number;
  nodes: GraphNode[];
  links: GraphLink[];
}

export type TransitionMode = '2D' | 'transitioning' | '3D';
