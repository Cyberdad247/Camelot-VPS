import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

export type TaskState =
  | 'PROPOSED'
  | 'POLICY_PENDING'
  | 'APPROVAL_PENDING'
  | 'LEASED'
  | 'VFS_PREFLIGHT'
  | 'QUEUED'
  | 'RUNNING'
  | 'VERIFYING'
  | 'RESOLVED'
  | 'RECEIPTED'
  | 'DENIED'
  | 'FAILED'
  | 'REVOKED'
  | 'QUARANTINED';

export interface RuntimeTaskSnapshot {
  missionId: string;
  taskId: string;
  state: TaskState;
  authorityEpoch: number;
  updatedAt: string;
  lastEventId: string;
  lastSequence: number;
  receiptId?: string | null;
}

export interface RuntimeWorkspaceSnapshot {
  tenantId: string;
  workspaceId: string;
  authorityEpoch: number;
  generatedAt: string;
  lastSequence: number;
  tasks: RuntimeTaskSnapshot[];
}

export interface RuntimeWorkspaceEvent {
  schemaVersion: 'workspace-event/1';
  id: string;
  type: string;
  occurredAt: string;
  tenantId: string;
  workspaceId: string;
  cartridgeId: string;
  missionId: string;
  traceId: string;
  sequence: number;
  classification: 'public' | 'internal' | 'confidential' | 'restricted';
  visibility: 'user' | 'operator' | 'audit';
  payload: unknown;
  provenance: {
    source: string;
    nodeId?: string;
    policyDecisionId?: string;
    capabilityLeaseId?: string;
    receiptId?: string;
  };
  integrity: {
    payloadHash: string;
    signerPublicKey?: string;
    signature?: string;
  };
}

export type RuntimeConnectionState = 'unconfigured' | 'connecting' | 'live' | 'degraded';

interface CamelotRuntimeValue {
  connectionState: RuntimeConnectionState;
  tenantId: string;
  workspaceId: string;
  snapshot: RuntimeWorkspaceSnapshot | null;
  recentEvents: RuntimeWorkspaceEvent[];
  lastError: string | null;
  refresh: () => Promise<void>;
}

const CamelotRuntimeContext = createContext<CamelotRuntimeValue | null>(null);

const env = (import.meta as any).env ?? {};
const apiBase = String(env.VITE_WORLD_TREE_API_URL || 'http://127.0.0.1:3006').replace(/\/$/, '');
const configuredTenantId = String(env.VITE_CAMELOT_TENANT_ID || '').trim();
const configuredWorkspaceId = String(env.VITE_CAMELOT_WORKSPACE_ID || '').trim();

export function CamelotRuntimeProvider({children}: PropsWithChildren) {
  const [connectionState, setConnectionState] = useState<RuntimeConnectionState>(
    configuredTenantId && configuredWorkspaceId ? 'connecting' : 'unconfigured',
  );
  const [snapshot, setSnapshot] = useState<RuntimeWorkspaceSnapshot | null>(null);
  const [recentEvents, setRecentEvents] = useState<RuntimeWorkspaceEvent[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    if (!configuredTenantId || !configuredWorkspaceId) return;
    const query = new URLSearchParams({tenantId: configuredTenantId});
    const response = await fetch(
      `${apiBase}/api/workspaces/${encodeURIComponent(configuredWorkspaceId)}/snapshot?${query}`,
      {headers: {'Accept': 'application/json'}},
    );
    if (!response.ok) {
      throw new Error(`workspace snapshot request failed (${response.status})`);
    }
    const next = (await response.json()) as RuntimeWorkspaceSnapshot;
    setSnapshot(next);
  }, []);

  useEffect(() => {
    if (!configuredTenantId || !configuredWorkspaceId) {
      setConnectionState('unconfigured');
      return undefined;
    }

    let disposed = false;
    setConnectionState('connecting');
    setLastError(null);

    const connect = async () => {
      try {
        await refresh();
        if (disposed) return;
        const query = new URLSearchParams({tenantId: configuredTenantId});
        const streamUrl = `${apiBase}/api/workspaces/${encodeURIComponent(configuredWorkspaceId)}/stream?${query}`;
        const source = new EventSource(streamUrl);
        sourceRef.current = source;
        source.onopen = () => {
          if (!disposed) {
            setConnectionState('live');
            setLastError(null);
          }
        };
        source.addEventListener('workspace-event', (rawEvent) => {
          if (disposed) return;
          try {
            const event = JSON.parse((rawEvent as MessageEvent).data) as RuntimeWorkspaceEvent;
            setRecentEvents((current) => [...current.slice(-99), event]);
            void refresh().catch((error: unknown) => {
              setConnectionState('degraded');
              setLastError(error instanceof Error ? error.message : String(error));
            });
          } catch (error) {
            setConnectionState('degraded');
            setLastError(error instanceof Error ? error.message : String(error));
          }
        });
        source.addEventListener('replay-required', () => {
          void refresh();
        });
        source.onerror = () => {
          if (!disposed) {
            setConnectionState('degraded');
            setLastError('authoritative workspace event stream disconnected');
          }
        };
      } catch (error) {
        if (!disposed) {
          setConnectionState('degraded');
          setLastError(error instanceof Error ? error.message : String(error));
        }
      }
    };

    void connect();
    return () => {
      disposed = true;
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [refresh]);

  const value = useMemo<CamelotRuntimeValue>(
    () => ({
      connectionState,
      tenantId: configuredTenantId,
      workspaceId: configuredWorkspaceId,
      snapshot,
      recentEvents,
      lastError,
      refresh,
    }),
    [connectionState, snapshot, recentEvents, lastError, refresh],
  );

  return <CamelotRuntimeContext.Provider value={value}>{children}</CamelotRuntimeContext.Provider>;
}

export function useCamelotRuntime(): CamelotRuntimeValue {
  const context = useContext(CamelotRuntimeContext);
  if (!context) {
    throw new Error('useCamelotRuntime must be used inside CamelotRuntimeProvider');
  }
  return context;
}
