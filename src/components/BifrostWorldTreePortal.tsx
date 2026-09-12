import React, { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  CircleOff,
  ExternalLink,
  Gauge,
  Lock,
  Network,
  Radio,
  RefreshCw,
  Route,
  Send,
  ShieldCheck,
  Sparkles,
  Unlock,
  Volume2,
} from 'lucide-react';

type RealmId = 'multivoice' | 'godseye' | 'worldmonitor';
type GateId = 'identity' | 'integrity' | 'intent' | 'payload' | 'access';
type ProbeState = 'idle' | 'probing' | 'online' | 'offline';

interface ProbeResult {
  reachable?: boolean;
  detail?: string;
  status?: number;
}

interface CrossingResult {
  result?: string;
  detail?: string;
  requiresHandoff?: boolean;
  launchUrl?: string;
  error?: string;
}

const GATEWAY_URL = ((import.meta as any).env?.VITE_BIFROST_URL || 'http://127.0.0.1:4188').replace(/\/$/, '');

const REALMS: Record<RealmId, {
  label: string;
  subtitle: string;
  transport: 'bridge' | 'handoff' | 'mcp';
  intent: string;
  accent: string;
}> = {
  multivoice: {
    label: 'Multivoice Router',
    subtitle: 'Persona voice realm • Tailscale / bridge aware',
    transport: 'bridge',
    intent: 'Open a governed persona voice handoff through Bifrost.',
    accent: 'cyan',
  },
  godseye: {
    label: "God's Eye View",
    subtitle: 'Live geospatial intelligence • 3D world surface',
    transport: 'handoff',
    intent: 'Open the spatial-intelligence realm with operator-controlled handoff.',
    accent: 'amber',
  },
  worldmonitor: {
    label: 'WorldMonitor',
    subtitle: 'Global intelligence • MCP capability surface',
    transport: 'mcp',
    intent: 'Discover the WorldMonitor MCP capability surface through Heimdall.',
    accent: 'purple',
  },
};

const DEFAULT_GATES: Record<GateId, boolean> = {
  identity: true,
  integrity: true,
  intent: true,
  payload: true,
  access: true,
};

export const BifrostWorldTreePortal: React.FC = () => {
  const [mountTarget, setMountTarget] = useState<HTMLElement | null>(null);
  const [scrollerPresent, setScrollerPresent] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedRealm, setSelectedRealm] = useState<RealmId>('multivoice');
  const [intent, setIntent] = useState(REALMS.multivoice.intent);
  const [payload, setPayload] = useState('');
  const [gates, setGates] = useState<Record<GateId, boolean>>(DEFAULT_GATES);
  const [sealed, setSealed] = useState(false);
  const [probeState, setProbeState] = useState<Record<RealmId, ProbeState>>({
    multivoice: 'idle',
    godseye: 'idle',
    worldmonitor: 'idle',
  });
  const [probeDetail, setProbeDetail] = useState<Record<RealmId, string>>({
    multivoice: 'Not yet probed',
    godseye: 'Not yet probed',
    worldmonitor: 'Not yet probed',
  });
  const [crossingBusy, setCrossingBusy] = useState(false);
  const [crossingResult, setCrossingResult] = useState<CrossingResult | null>(null);
  const [gatewayReachable, setGatewayReachable] = useState<boolean | null>(null);

  useEffect(() => {
    const locate = () => {
      const throne = document.getElementById('stratum-throne-room');
      const scroller = document.getElementById('sovereign-worldtree-scroller');
      setMountTarget(throne);
      setScrollerPresent(Boolean(scroller));
    };

    locate();
    const observer = new MutationObserver(locate);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  const gateOpen = useMemo(
    () => !sealed && Object.values(gates).every(Boolean),
    [gates, sealed],
  );

  const setRealm = (realm: RealmId) => {
    setSelectedRealm(realm);
    setIntent(REALMS[realm].intent);
    setCrossingResult(null);
  };

  const probeRealm = async (realm: RealmId) => {
    setProbeState(prev => ({ ...prev, [realm]: 'probing' }));
    try {
      const response = await fetch(`${GATEWAY_URL}/api/bifrost/probe/${realm}`, {
        headers: { Accept: 'application/json' },
      });
      const data = await response.json() as ProbeResult;
      setGatewayReachable(true);
      setProbeState(prev => ({ ...prev, [realm]: data.reachable ? 'online' : 'offline' }));
      setProbeDetail(prev => ({ ...prev, [realm]: data.detail || 'Probe completed' }));
    } catch (error) {
      setGatewayReachable(false);
      setProbeState(prev => ({ ...prev, [realm]: 'offline' }));
      setProbeDetail(prev => ({
        ...prev,
        [realm]: error instanceof Error ? error.message : 'Bifrost gateway unreachable',
      }));
    }
  };

  const probeAll = async () => {
    await Promise.all((Object.keys(REALMS) as RealmId[]).map(probeRealm));
  };

  const executeCrossing = async () => {
    if (!gateOpen || !intent.trim() || crossingBusy) return;
    setCrossingBusy(true);
    setCrossingResult(null);
    const realm = REALMS[selectedRealm];

    try {
      const response = await fetch(`${GATEWAY_URL}/api/bifrost/crossing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          source: 'camelot',
          destination: selectedRealm,
          transport: realm.transport,
          intent: intent.trim(),
          payload,
        }),
      });
      const data = await response.json() as CrossingResult;
      setGatewayReachable(true);
      setCrossingResult(data);
    } catch (error) {
      setGatewayReachable(false);
      setCrossingResult({
        error: error instanceof Error ? error.message : 'Bifrost gateway unreachable',
      });
    } finally {
      setCrossingBusy(false);
    }
  };

  const openThronePortal = () => {
    setOpen(true);
    document.getElementById('stratum-throne-room')?.scrollIntoView({ behavior: 'smooth' });
    window.setTimeout(() => {
      document.getElementById('bifrost-worldtree-portal')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 450);
  };

  const portal = (
    <div id="bifrost-worldtree-portal" className="mt-8 rounded-3xl border border-cyan-400/30 bg-black/80 shadow-[0_0_80px_rgba(34,211,238,0.08)] overflow-hidden">
      <div className="p-4 sm:p-5 border-b border-cyan-400/20 bg-gradient-to-r from-cyan-950/35 via-[#140a24] to-amber-950/25 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="relative w-12 h-12 rounded-2xl border border-cyan-400/50 bg-black/70 flex items-center justify-center shadow-[0_0_25px_rgba(34,211,238,0.18)]">
            <Network className="w-6 h-6 text-cyan-300" />
            <span className={`absolute -top-1 -right-1 w-3 h-3 rounded-full border-2 border-black ${gateOpen ? 'bg-emerald-400' : 'bg-red-500'}`} />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-mono text-sm sm:text-base font-black tracking-[0.18em] text-white">BIFROST BRIDGE</h3>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono border border-cyan-500/30 bg-cyan-950/60 text-cyan-300">THRONE PORTAL</span>
            </div>
            <p className="text-[11px] sm:text-xs text-slate-400 font-mono mt-1">
              Sir Hermes routes the crossing. Sir Heimdall decides whether anything may pass.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded-lg border font-mono text-[10px] ${gatewayReachable === false ? 'border-red-500/40 bg-red-950/40 text-red-300' : gatewayReachable ? 'border-emerald-500/40 bg-emerald-950/40 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400'}`}>
            GATEWAY {gatewayReachable === false ? 'OFFLINE' : gatewayReachable ? 'REACHABLE' : 'UNPROBED'}
          </span>
          <button
            onClick={() => setOpen(prev => !prev)}
            className="px-3 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-400/30 text-cyan-200 hover:bg-cyan-500/20 font-mono text-[10px] font-bold transition-all"
          >
            {open ? 'Collapse Portal' : 'Open Portal'}
          </button>
        </div>
      </div>

      {open && (
        <div className="p-4 sm:p-5 grid grid-cols-1 xl:grid-cols-12 gap-5 animate-fadeIn">
          <section className="xl:col-span-7 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-cyan-300 font-mono text-[10px] uppercase tracking-[0.2em]">Sir Hermes</div>
                <h4 className="text-white font-bold">Routing Forge</h4>
              </div>
              <button onClick={probeAll} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 font-mono text-[10px]">
                <RefreshCw className="w-3 h-3" /> Probe Realms
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              {(Object.keys(REALMS) as RealmId[]).map(realmId => {
                const realm = REALMS[realmId];
                const active = selectedRealm === realmId;
                const state = probeState[realmId];
                return (
                  <button
                    key={realmId}
                    onClick={() => setRealm(realmId)}
                    className={`text-left p-3 rounded-xl border transition-all ${active ? 'border-cyan-400/60 bg-cyan-950/30 shadow-[0_0_24px_rgba(34,211,238,0.08)]' : 'border-white/10 bg-white/[0.03] hover:border-white/20'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] font-bold text-white">{realm.label}</span>
                      <span className={`w-2 h-2 rounded-full ${state === 'online' ? 'bg-emerald-400' : state === 'offline' ? 'bg-red-400' : state === 'probing' ? 'bg-amber-400 animate-pulse' : 'bg-slate-600'}`} />
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1">{realm.subtitle}</p>
                    <p className="text-[9px] text-slate-600 mt-2 truncate">{probeDetail[realmId]}</p>
                  </button>
                );
              })}
            </div>

            <div className="rounded-xl border border-white/10 bg-black/50 p-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-[10px]">
                <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                  <span className="text-slate-500 block">SOURCE</span>
                  <span className="text-[#D4AF37] font-bold">Camelot-VPS / Throne Room</span>
                </div>
                <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                  <span className="text-slate-500 block">TRANSPORT</span>
                  <span className="text-cyan-300 font-bold uppercase">{REALMS[selectedRealm].transport}</span>
                </div>
              </div>

              <label className="block">
                <span className="font-mono text-[10px] text-slate-400">CROSSING INTENT</span>
                <textarea
                  value={intent}
                  onChange={event => setIntent(event.target.value)}
                  rows={2}
                  className="mt-1.5 w-full rounded-xl border border-cyan-500/25 bg-black/70 px-3 py-2.5 text-xs text-white font-mono focus:outline-none focus:border-cyan-400"
                />
              </label>

              <label className="block">
                <span className="font-mono text-[10px] text-slate-400">OPTIONAL PAYLOAD / CONTEXT</span>
                <textarea
                  value={payload}
                  onChange={event => setPayload(event.target.value.slice(0, 12000))}
                  rows={3}
                  placeholder="Context to carry across the bridge. Maximum 12KB."
                  className="mt-1.5 w-full rounded-xl border border-white/10 bg-black/70 px-3 py-2.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-400"
                />
              </label>

              <button
                onClick={executeCrossing}
                disabled={!gateOpen || !intent.trim() || crossingBusy}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 disabled:from-slate-700 disabled:to-slate-800 disabled:text-slate-500 text-black font-mono text-xs font-black flex items-center justify-center gap-2 transition-all"
              >
                <Send className="w-3.5 h-3.5" />
                {crossingBusy ? 'Crossing Bifrost...' : gateOpen ? 'Authorize Crossing' : 'Blocked by Heimdall'}
              </button>
            </div>

            {crossingResult && (
              <div className={`rounded-xl border p-3 font-mono text-[11px] ${crossingResult.error ? 'border-red-500/40 bg-red-950/30 text-red-200' : 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100'}`}>
                <div className="font-bold flex items-center gap-2">
                  {crossingResult.error ? <CircleOff className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  {crossingResult.error || crossingResult.result || 'Crossing complete'}
                </div>
                {crossingResult.detail && <div className="mt-1 text-slate-300 break-words max-h-28 overflow-auto">{crossingResult.detail}</div>}
                {crossingResult.requiresHandoff && crossingResult.launchUrl && (
                  <button
                    onClick={() => window.open(crossingResult.launchUrl, '_blank', 'noopener,noreferrer')}
                    className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-emerald-400/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
                  >
                    <ExternalLink className="w-3 h-3" /> Open governed handoff
                  </button>
                )}
              </div>
            )}
          </section>

          <section className="xl:col-span-5 rounded-2xl border border-[#D4AF37]/20 bg-[#100a04]/50 p-4 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[#D4AF37] font-mono text-[10px] uppercase tracking-[0.2em]">Sir Heimdall</div>
                <h4 className="text-white font-bold">Gatehouse</h4>
              </div>
              <button
                onClick={() => setSealed(prev => !prev)}
                className={`px-3 py-1.5 rounded-lg border font-mono text-[10px] font-bold flex items-center gap-1.5 ${sealed ? 'border-red-500/40 bg-red-950/40 text-red-300' : 'border-emerald-500/30 bg-emerald-950/30 text-emerald-300'}`}
              >
                {sealed ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
                {sealed ? 'BIFROST SEALED' : 'BIFROST OPEN'}
              </button>
            </div>

            <div className="space-y-2">
              {(Object.keys(gates) as GateId[]).map(gate => {
                const enabled = gates[gate] && !sealed;
                return (
                  <button
                    key={gate}
                    onClick={() => setGates(prev => ({ ...prev, [gate]: !prev[gate] }))}
                    disabled={sealed}
                    className="w-full p-3 rounded-xl border border-white/10 bg-black/40 hover:bg-white/[0.04] disabled:opacity-50 flex items-center justify-between gap-3 text-left transition-all"
                  >
                    <span>
                      <span className="text-[10px] font-mono text-slate-500 block uppercase">{gate} gate</span>
                      <span className="text-xs text-slate-200">{enabled ? 'Verified for crossing' : 'Crossing denied'}</span>
                    </span>
                    <span className={`w-9 h-5 rounded-full p-0.5 transition-all ${enabled ? 'bg-emerald-500' : 'bg-slate-700'}`}>
                      <span className={`block w-4 h-4 bg-white rounded-full transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0'}`} />
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="rounded-xl border border-white/10 bg-black/50 p-3 font-mono text-[10px] space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">POLICY</span>
                <span className="text-[#D4AF37]">ALLOWLISTED / FAIL-CLOSED</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">GATES</span>
                <span className={gateOpen ? 'text-emerald-400' : 'text-red-400'}>{Object.values(gates).filter(Boolean).length}/5 VERIFIED</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">BRIDGE</span>
                <span className={sealed ? 'text-red-400' : 'text-cyan-300'}>{sealed ? 'SEALED BY HEIMDALL' : 'AVAILABLE TO HERMES'}</span>
              </div>
            </div>

            <a
              href={GATEWAY_URL}
              target="_blank"
              rel="noreferrer"
              className="w-full px-3 py-2.5 rounded-xl border border-purple-400/30 bg-purple-500/10 hover:bg-purple-500/20 text-purple-200 font-mono text-[10px] font-bold flex items-center justify-center gap-2 transition-all"
            >
              <ArrowUpRight className="w-3.5 h-3.5" /> Open Full Bifrost Command Center
            </a>
          </section>
        </div>
      )}
    </div>
  );

  return (
    <>
      {scrollerPresent && (
        <button
          onClick={openThronePortal}
          className="fixed right-4 sm:right-6 bottom-16 z-40 px-3 py-2 rounded-2xl border border-cyan-400/30 bg-black/85 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.15)] hover:border-cyan-300/60 transition-all flex items-center gap-2"
          title="Open the Bifrost Bridge portal in the Throne Room"
        >
          <Route className="w-4 h-4 text-cyan-300" />
          <span className="hidden sm:block text-[10px] font-mono font-bold text-cyan-100">BIFROST</span>
          <span className={`w-2 h-2 rounded-full ${gateOpen ? 'bg-emerald-400' : 'bg-red-400'}`} />
        </button>
      )}
      {mountTarget ? createPortal(portal, mountTarget) : null}
    </>
  );
};

export default BifrostWorldTreePortal;
