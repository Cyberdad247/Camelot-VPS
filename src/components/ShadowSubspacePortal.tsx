import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  Clock3,
  Cpu,
  Eye,
  FileCode2,
  Fingerprint,
  LockKeyhole,
  MoonStar,
  Network,
  OctagonX,
  Play,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import './shadow-subspace.css';

type RiskRing = 'R0' | 'R1' | 'R2' | 'R3' | 'R4' | 'R5' | 'R6';
type ShadowHealth = {
  status: string;
  service: string;
  sessions: number;
  policy: string;
  publicInbound: boolean;
  signer: string;
};

type ShadowEffect = {
  effect_id: string;
  intent: string;
  effect: string;
  target: string;
  risk: RiskRing;
  requested_capabilities: string[];
  status: 'proposed' | 'pending_approval' | 'authorized' | 'denied';
  requires_hitl: boolean;
  manifest_hash: string;
  created_at: string;
};

type ShadowSession = {
  session_id: string;
  mission: string;
  knight_id: string;
  delegate_id?: string | null;
  state: string;
  risk_ceiling: RiskRing;
  capabilities: string[];
  bounds: { memory_mb: number; cpu_quota_percent: number; ttl_seconds: number };
  workspace: { mode: string; root_uri: string; public_inbound: boolean; allowed_egress: string[] };
  created_at: string;
  expires_at: string;
  effects: ShadowEffect[];
  receipt_count: number;
  last_receipt_hash?: string | null;
};

type ShadowReceipt = {
  receipt_id: string;
  timestamp: string;
  action: string;
  risk: RiskRing;
  decision: string;
  resource: string;
  receipt_hash: string;
  parent_hash?: string | null;
  signer_public_key: string;
  signature: string;
};

const BIFROST_URL = ((import.meta as any).env?.VITE_BIFROST_URL || 'http://127.0.0.1:4188').replace(/\/$/, '');
const PUTER_URL = ((import.meta as any).env?.VITE_PUTER_SHADOW_URL || 'http://127.0.0.1:4100').replace(/\/$/, '');
const RISKS: RiskRing[] = ['R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6'];

async function shadowRequest(path: string, init: RequestInit = {}) {
  const response = await fetch(`${BIFROST_URL}/api/bifrost/shadow${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(init.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error || `Shadow request failed (${response.status})`);
  return body;
}

export const ShadowSubspacePortal: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState<ShadowHealth | null>(null);
  const [sessions, setSessions] = useState<ShadowSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [receipts, setReceipts] = useState<ShadowReceipt[]>([]);
  const [mission, setMission] = useState('');
  const [delegate, setDelegate] = useState('sir_umbra');
  const [riskCeiling, setRiskCeiling] = useState<RiskRing>('R5');
  const [effectRisk, setEffectRisk] = useState<RiskRing>('R4');
  const [effectType, setEffectType] = useState('external.write');
  const [effectTarget, setEffectTarget] = useState('bifrost://approved-realm');
  const [effectIntent, setEffectIntent] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const active = useMemo(() => sessions.find(session => session.session_id === activeId) || null, [sessions, activeId]);
  const pending = useMemo(() => active?.effects.filter(effect => effect.status === 'pending_approval') || [], [active]);

  const refresh = useCallback(async () => {
    try {
      const [nextHealth, nextSessions] = await Promise.all([
        shadowRequest('/health'),
        shadowRequest('/sessions'),
      ]);
      setHealth(nextHealth);
      setSessions(nextSessions);
      setError(null);
      if (!activeId && nextSessions[0]) setActiveId(nextSessions[0].session_id);
    } catch (nextError) {
      setHealth(null);
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }, [activeId]);

  const refreshReceipts = useCallback(async (sessionId: string) => {
    try {
      setReceipts(await shadowRequest(`/sessions/${sessionId}/receipts`));
    } catch {
      setReceipts([]);
    }
  }, []);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  useEffect(() => {
    if (activeId && open) void refreshReceipts(activeId);
  }, [activeId, open, refreshReceipts]);

  useEffect(() => {
    const openShadow = (event: Event) => {
      const detail = (event as CustomEvent).detail || {};
      setOpen(true);
      if (typeof detail.mission === 'string') setMission(detail.mission);
      if (typeof detail.knightId === 'string') setDelegate(detail.knightId);
    };
    const throneMessage = (event: Event) => {
      const detail = (event as CustomEvent).detail || {};
      if (detail.knightId !== 'sir_umbra') return;
      setOpen(true);
      setDelegate('sir_umbra');
      if (typeof detail.message === 'string') setMission(detail.message);
    };
    const keyboard = (event: KeyboardEvent) => {
      if (event.altKey && event.key.toLowerCase() === 'u') {
        event.preventDefault();
        setOpen(value => !value);
      }
    };
    window.addEventListener('camelot:shadow-open', openShadow as EventListener);
    window.addEventListener('camelot:throne-message', throneMessage as EventListener);
    window.addEventListener('keydown', keyboard);
    return () => {
      window.removeEventListener('camelot:shadow-open', openShadow as EventListener);
      window.removeEventListener('camelot:throne-message', throneMessage as EventListener);
      window.removeEventListener('keydown', keyboard);
    };
  }, []);

  const summon = async () => {
    const cleanMission = mission.trim();
    if (!cleanMission) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const session: ShadowSession = await shadowRequest('/sessions', {
        method: 'POST',
        body: JSON.stringify({
          mission: cleanMission,
          knight_id: 'sir_umbra',
          delegate_id: delegate === 'sir_umbra' ? null : delegate,
          ttl_seconds: 1800,
          risk_ceiling: riskCeiling,
          memory_mb: 512,
          cpu_quota_percent: 25,
          capabilities: ['shadow.read', 'shadow.write', 'shadow.plan', 'bifrost.request'],
          allowed_egress: ['bifrost://governed'],
        }),
      });
      setSessions(previous => [session, ...previous.filter(item => item.session_id !== session.session_id)]);
      setActiveId(session.session_id);
      setMission('');
      setNotice(`Shadow ${session.session_id.slice(0, 8)} summoned under Sir Umbra.`);
      await refreshReceipts(session.session_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally { setBusy(false); }
  };

  const proposeEffect = async () => {
    if (!active || !effectIntent.trim()) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const effect: ShadowEffect = await shadowRequest(`/sessions/${active.session_id}/effects`, {
        method: 'POST',
        body: JSON.stringify({
          intent: effectIntent.trim(),
          effect: effectType,
          target: effectTarget,
          risk: effectRisk,
          requested_capabilities: effectType.startsWith('external') ? ['bifrost.request'] : [],
        }),
      });
      setNotice(effect.requires_hitl ? `${effect.risk} effect is frozen at the human gate.` : `${effect.risk} effect authorized by policy.`);
      setEffectIntent('');
      await refresh();
      await refreshReceipts(active.session_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally { setBusy(false); }
  };

  const decide = async (effect: ShadowEffect, decision: 'approve' | 'deny') => {
    if (!active) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await shadowRequest(`/sessions/${active.session_id}/effects/${effect.effect_id}/${decision}`, {
        method: 'POST',
        body: JSON.stringify(decision === 'approve'
          ? { operator: 'sovereign', scope: effect.risk === 'R6' ? 'sovereign' : 'once', note: 'Approved from Camelot Shadow Subspace UI.' }
          : { operator: 'sovereign', note: 'Denied from Camelot Shadow Subspace UI.' }),
      });
      setNotice(`${effect.risk} effect ${decision === 'approve' ? 'approved once' : 'denied'} and receipted.`);
      await refresh();
      await refreshReceipts(active.session_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally { setBusy(false); }
  };

  const seal = async () => {
    if (!active) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await shadowRequest(`/sessions/${active.session_id}/seal`, { method: 'POST', body: '{}' });
      setNotice('Shadow sealed. Ephemeral workspace removed; signed receipts retained.');
      await refresh();
      await refreshReceipts(active.session_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally { setBusy(false); }
  };

  return (
    <>
      <button className="shadow-launcher" onClick={() => setOpen(true)} title="Open Shadow Subspace (Alt+U)">
        <MoonStar size={18}/><span>UMBRA</span><i className={health?.status === 'ok' ? 'online' : ''}/>
      </button>

      {open && <section className="shadow-shell" role="dialog" aria-modal="true" aria-label="Camelot Shadow Subspace">
        <div className="shadow-backdrop" onClick={() => setOpen(false)}/>
        <div className="shadow-workspace">
          <header className="shadow-header">
            <div><MoonStar size={24}/><span><strong>SIR UMBRA // SHADOW SUBSPACE</strong><small>Puter Shadow Castle × Native Knight CPU × HITL Ledger</small></span></div>
            <div className="shadow-header-state"><i className={health?.status === 'ok' ? 'online' : ''}/>{health?.status === 'ok' ? 'NATIVE CPU ONLINE' : 'BIFROST / SHADOWD UNVERIFIED'}</div>
            <button onClick={() => setOpen(false)} aria-label="Close Shadow Subspace"><X size={20}/></button>
          </header>

          <div className="shadow-grid">
            <aside className="shadow-left">
              <article className="shadow-card shadow-identity">
                <div className="shadow-card-title"><Fingerprint size={15}/>Shadow Identity</div>
                <div className="shadow-umbra-glyph"><MoonStar size={38}/></div>
                <strong>SIR UMBRA</strong><small>Native Shadow CPU</small>
                <div className="shadow-truth"><ShieldCheck size={14}/><span>Externally footprint-minimized.<b>Internally attributable.</b></span></div>
              </article>

              <article className="shadow-card">
                <div className="shadow-card-title"><Sparkles size={15}/>Summon Mission</div>
                <textarea value={mission} onChange={event => setMission(event.target.value)} placeholder="What should the Shadow Knight investigate, draft, or prepare?"/>
                <label>Delegate Knight<input value={delegate} onChange={event => setDelegate(event.target.value)} placeholder="sir_codex"/></label>
                <label>Risk ceiling<select value={riskCeiling} onChange={event => setRiskCeiling(event.target.value as RiskRing)}>{RISKS.slice(0, 6).map(risk => <option key={risk}>{risk}</option>)}</select></label>
                <button className="shadow-primary" disabled={busy || !mission.trim()} onClick={summon}><Play size={14}/>Summon Shadow</button>
              </article>

              <article className="shadow-card shadow-guardrails">
                <div className="shadow-card-title"><LockKeyhole size={15}/>Guardrail Contract</div>
                <span><i/>R0–R3 policy bounded</span>
                <span><i/>R4–R6 human gate</span>
                <span><i/>R6 sovereign scope</span>
                <span><i/>No public inbound</span>
                <span><i/>No arbitrary shell API</span>
                <span><i/>Signed receipt chain</span>
              </article>
            </aside>

            <main className="shadow-center">
              <div className="shadow-stage-heading"><span><Cpu size={17}/>ACTIVE SHADOWS</span><button onClick={() => void refresh()}><RefreshCw size={13}/>Refresh</button></div>
              <div className="shadow-session-strip">
                {sessions.length === 0 && <button className="empty" onClick={() => setMission('Prepare a bounded implementation plan in Shadow Subspace.')}>No active shadows. Summon one.</button>}
                {sessions.map(session => <button key={session.session_id} className={activeId === session.session_id ? 'active' : ''} onClick={() => setActiveId(session.session_id)}>
                  <i/><span><b>{session.delegate_id || session.knight_id}</b><small>{session.session_id.slice(0, 8)} · {session.state}</small></span><em>{session.risk_ceiling}</em>
                </button>)}
              </div>

              {active ? <>
                <article className="shadow-card shadow-mission-card">
                  <div className="shadow-mission-top"><div><span>MISSION</span><h2>{active.mission}</h2></div><b>{active.state.toUpperCase()}</b></div>
                  <div className="shadow-metrics">
                    <span><Cpu size={13}/><b>{active.bounds.cpu_quota_percent}%</b><small>CPU QUOTA</small></span>
                    <span><Activity size={13}/><b>{active.bounds.memory_mb} MB</b><small>RAM CEILING</small></span>
                    <span><Clock3 size={13}/><b>{Math.max(0, Math.ceil((new Date(active.expires_at).getTime() - Date.now()) / 60000))}m</b><small>TTL</small></span>
                    <span><ScrollText size={13}/><b>{active.receipt_count}</b><small>RECEIPTS</small></span>
                  </div>
                  <div className="shadow-capabilities">{active.capabilities.map(capability => <span key={capability}>{capability}</span>)}</div>
                  <div className="shadow-boundary"><Network size={14}/><span><b>{active.workspace.root_uri}</b><small>{active.workspace.mode} · public inbound {active.workspace.public_inbound ? 'ON' : 'OFF'} · egress {active.workspace.allowed_egress.join(', ') || 'none'}</small></span></div>
                </article>

                <article className="shadow-card shadow-effect-card">
                  <div className="shadow-card-title"><ShieldCheck size={15}/>Effect Manifest</div>
                  <div className="shadow-effect-fields">
                    <label>Risk<select value={effectRisk} onChange={event => setEffectRisk(event.target.value as RiskRing)}>{RISKS.map(risk => <option key={risk}>{risk}</option>)}</select></label>
                    <label>Effect<select value={effectType} onChange={event => setEffectType(event.target.value)}><option>external.write</option><option>external.read</option><option>production.mutate</option><option>shadow.plan</option></select></label>
                    <label>Target<input value={effectTarget} onChange={event => setEffectTarget(event.target.value)}/></label>
                  </div>
                  <textarea value={effectIntent} onChange={event => setEffectIntent(event.target.value)} placeholder="Describe the exact requested effect. The model proposes; Camelot authorizes."/>
                  <button className="shadow-primary" disabled={busy || !effectIntent.trim()} onClick={proposeEffect}><ShieldCheck size={14}/>Submit to Guardrails</button>
                </article>

                <article className="shadow-card shadow-effects-list">
                  <div className="shadow-card-title"><Eye size={15}/>Mission Effects <small>{pending.length} awaiting human</small></div>
                  {active.effects.length === 0 && <div className="shadow-empty-line">No external effects requested. Shadow work remains isolated.</div>}
                  {[...active.effects].reverse().map(effect => <div className={`shadow-effect effect-${effect.status}`} key={effect.effect_id}>
                    <b>{effect.risk}</b><span><strong>{effect.effect}</strong><small>{effect.target}</small><em>{effect.intent}</em></span><i>{effect.status.replace('_', ' ')}</i>
                    {effect.status === 'pending_approval' && <div className="shadow-hitl"><button disabled={busy} onClick={() => void decide(effect, 'deny')}><OctagonX size={13}/>Deny</button><button disabled={busy} onClick={() => void decide(effect, 'approve')}><CheckCircle2 size={13}/>Approve {effect.risk === 'R6' ? 'Sovereign' : 'Once'}</button></div>}
                  </div>)}
                </article>
              </> : <div className="shadow-no-session"><MoonStar size={42}/><h2>Shadow Subspace dormant</h2><p>Summon a bounded mission from the Throne Room or this console.</p></div>}
            </main>

            <aside className="shadow-right">
              <article className="shadow-card shadow-ledger">
                <div className="shadow-card-title"><ScrollText size={15}/>HITL Ledger <small>APPEND ONLY</small></div>
                <div className="shadow-receipts">
                  {receipts.length === 0 && <div className="shadow-empty-line">No receipts loaded.</div>}
                  {[...receipts].reverse().slice(0, 12).map(receipt => <div key={receipt.receipt_id}><i className={receipt.decision.includes('DENY') ? 'deny' : 'allow'}/><span><b>{receipt.action}</b><small>{receipt.risk} · {receipt.decision}</small><em>{receipt.receipt_hash.slice(0, 24)}…</em></span></div>)}
                </div>
              </article>

              <article className="shadow-card">
                <div className="shadow-card-title"><FileCode2 size={15}/>Shadow Castle</div>
                <p>Puter is the visual workspace. Native authority stays in Camelot.</p>
                <button onClick={() => window.open(PUTER_URL, '_blank', 'noopener,noreferrer')}><MoonStar size={13}/>Open Puter Workspace</button>
                <small className="shadow-adapter-note">Adapter path is governed through Bifrost. No Shadow daemon token is sent to the browser.</small>
              </article>

              {active && <article className="shadow-card shadow-danger-zone">
                <div className="shadow-card-title"><Trash2 size={15}/>Seal Shadow</div>
                <p>Verification receipt is written first. The ephemeral workspace is then removed.</p>
                <button disabled={busy || active.state === 'sealed'} onClick={seal}><Trash2 size={13}/>{active.state === 'sealed' ? 'SEALED' : 'Seal & Purge Workspace'}</button>
              </article>}

              {(notice || error) && <article className={`shadow-card shadow-message ${error ? 'error' : 'notice'}`}><b>{error ? 'GUARDRAIL' : 'RECEIPT'}</b><p>{error || notice}</p></article>}
            </aside>
          </div>
        </div>
      </section>}
    </>
  );
};

export default ShadowSubspacePortal;
