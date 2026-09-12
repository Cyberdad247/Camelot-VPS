import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowDown,
  ArrowUpRight,
  CheckCircle2,
  CircleOff,
  ExternalLink,
  Globe2,
  Lock,
  Mic2,
  Network,
  Radio,
  RefreshCw,
  Route,
  Send,
  ShieldCheck,
  Unlock,
  Waves,
} from 'lucide-react';

type RealmId = 'multivoice' | 'godseye' | 'worldmonitor';
type GateId = 'identity' | 'integrity' | 'intent' | 'payload' | 'access';
type ProbeState = 'idle' | 'probing' | 'online' | 'offline';
type ChapterId = 'threshold' | 'hermes' | 'heimdall' | 'multivoice' | 'godseye' | 'worldmonitor' | 'crossing';

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
  short: string;
  subtitle: string;
  transport: 'bridge' | 'handoff' | 'mcp';
  intent: string;
  icon: React.ReactNode;
  accent: string;
  repo: string;
}> = {
  multivoice: {
    label: 'Multivoice Router',
    short: 'VOICE REALM',
    subtitle: 'Persona voice orchestration • Tailscale / bridge aware',
    transport: 'bridge',
    intent: 'Open a governed persona voice handoff through Bifrost.',
    icon: <Mic2 className="w-7 h-7" />,
    accent: '#22d3ee',
    repo: 'Cyberdad247/Multivoice-router',
  },
  godseye: {
    label: "God's Eye View",
    short: 'SPATIAL REALM',
    subtitle: 'Live geospatial intelligence • photorealistic 3D world surface',
    transport: 'handoff',
    intent: 'Open the spatial-intelligence realm with operator-controlled handoff.',
    icon: <Globe2 className="w-7 h-7" />,
    accent: '#f59e0b',
    repo: 'Cyberdad247/gods-eye-view',
  },
  worldmonitor: {
    label: 'WorldMonitor',
    short: 'INTELLIGENCE REALM',
    subtitle: 'Global intelligence • MCP capability surface',
    transport: 'mcp',
    intent: 'Discover the WorldMonitor MCP capability surface through Heimdall.',
    icon: <Radio className="w-7 h-7" />,
    accent: '#c084fc',
    repo: 'koala73/worldmonitor',
  },
};

const DEFAULT_GATES: Record<GateId, boolean> = {
  identity: true,
  integrity: true,
  intent: true,
  payload: true,
  access: true,
};

const CHAPTERS: Array<{ id: ChapterId; index: string; label: string }> = [
  { id: 'threshold', index: '00', label: 'Bifrost Threshold' },
  { id: 'hermes', index: '01', label: 'Hermes Routing' },
  { id: 'heimdall', index: '02', label: 'Heimdall Gatehouse' },
  { id: 'multivoice', index: '03', label: 'Multivoice Realm' },
  { id: 'godseye', index: '04', label: "God's Eye View" },
  { id: 'worldmonitor', index: '05', label: 'WorldMonitor' },
  { id: 'crossing', index: '06', label: 'Crossing Chamber' },
];

export const BifrostWorldTreePortal: React.FC = () => {
  const [mountTarget, setMountTarget] = useState<HTMLElement | null>(null);
  const [scrollerPresent, setScrollerPresent] = useState(false);
  const [activeChapter, setActiveChapter] = useState<ChapterId>('threshold');
  const [selectedRealm, setSelectedRealm] = useState<RealmId>('multivoice');
  const [intent, setIntent] = useState(REALMS.multivoice.intent);
  const [payload, setPayload] = useState('');
  const [gates, setGates] = useState<Record<GateId, boolean>>(DEFAULT_GATES);
  const [sealed, setSealed] = useState(false);
  const [probeState, setProbeState] = useState<Record<RealmId, ProbeState>>({ multivoice: 'idle', godseye: 'idle', worldmonitor: 'idle' });
  const [probeDetail, setProbeDetail] = useState<Record<RealmId, string>>({ multivoice: 'Not yet probed', godseye: 'Not yet probed', worldmonitor: 'Not yet probed' });
  const [crossingBusy, setCrossingBusy] = useState(false);
  const [crossingResult, setCrossingResult] = useState<CrossingResult | null>(null);
  const [gatewayReachable, setGatewayReachable] = useState<boolean | null>(null);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

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

  useEffect(() => {
    if (!mountTarget) return;
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible?.target?.id?.startsWith('bifrost-chapter-')) {
        setActiveChapter(visible.target.id.replace('bifrost-chapter-', '') as ChapterId);
      }
    }, { root: document.getElementById('sovereign-worldtree-scroller'), threshold: [0.25, 0.5, 0.72] });

    CHAPTERS.forEach(chapter => {
      const node = sectionRefs.current[chapter.id];
      if (node) observer.observe(node);
    });
    return () => observer.disconnect();
  }, [mountTarget]);

  const gateOpen = useMemo(() => !sealed && Object.values(gates).every(Boolean), [gates, sealed]);

  const setRealm = (realm: RealmId) => {
    setSelectedRealm(realm);
    setIntent(REALMS[realm].intent);
    setCrossingResult(null);
    document.getElementById('bifrost-chapter-crossing')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const probeRealm = async (realm: RealmId) => {
    setProbeState(prev => ({ ...prev, [realm]: 'probing' }));
    try {
      const response = await fetch(`${GATEWAY_URL}/api/bifrost/probe/${realm}`, { headers: { Accept: 'application/json' } });
      const data = await response.json() as ProbeResult;
      setGatewayReachable(true);
      setProbeState(prev => ({ ...prev, [realm]: data.reachable ? 'online' : 'offline' }));
      setProbeDetail(prev => ({ ...prev, [realm]: data.detail || 'Probe completed' }));
    } catch (error) {
      setGatewayReachable(false);
      setProbeState(prev => ({ ...prev, [realm]: 'offline' }));
      setProbeDetail(prev => ({ ...prev, [realm]: error instanceof Error ? error.message : 'Bifrost gateway unreachable' }));
    }
  };

  const probeAll = async () => { await Promise.all((Object.keys(REALMS) as RealmId[]).map(probeRealm)); };

  const executeCrossing = async () => {
    if (!gateOpen || !intent.trim() || crossingBusy) return;
    setCrossingBusy(true);
    setCrossingResult(null);
    const realm = REALMS[selectedRealm];
    try {
      const response = await fetch(`${GATEWAY_URL}/api/bifrost/crossing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ source: 'camelot', destination: selectedRealm, transport: realm.transport, intent: intent.trim(), payload }),
      });
      const data = await response.json() as CrossingResult;
      setGatewayReachable(true);
      setCrossingResult(data);
    } catch (error) {
      setGatewayReachable(false);
      setCrossingResult({ error: error instanceof Error ? error.message : 'Bifrost gateway unreachable' });
    } finally {
      setCrossingBusy(false);
    }
  };

  const scrollToChapter = (id: ChapterId) => document.getElementById(`bifrost-chapter-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  const probeDot = (realm: RealmId) => probeState[realm] === 'online' ? 'bg-emerald-400' : probeState[realm] === 'offline' ? 'bg-red-400' : probeState[realm] === 'probing' ? 'bg-amber-300 animate-pulse' : 'bg-slate-600';

  const realmSection = (realmId: RealmId, chapterId: ChapterId, number: string) => {
    const realm = REALMS[realmId];
    return (
      <section id={`bifrost-chapter-${chapterId}`} ref={node => { sectionRefs.current[chapterId] = node; }} className="relative min-h-[92vh] flex items-center py-20 sm:py-24">
        <div className="grid lg:grid-cols-12 gap-8 items-center w-full">
          <div className="lg:col-span-5 space-y-5">
            <div className="font-mono text-[10px] tracking-[0.3em] uppercase" style={{ color: realm.accent }}>CHAPTER {number} // {realm.short}</div>
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl border flex items-center justify-center bg-black/70" style={{ borderColor: `${realm.accent}66`, color: realm.accent, boxShadow: `0 0 36px ${realm.accent}20` }}>{realm.icon}</div>
              <div><h3 className="text-3xl sm:text-4xl font-black text-white tracking-tight">{realm.label}</h3><p className="text-xs sm:text-sm text-slate-400 mt-1">{realm.subtitle}</p></div>
            </div>
            <p className="text-slate-300 leading-relaxed max-w-xl">Bifrost does not absorb this realm. Hermes preserves the destination boundary and hands control across only after Heimdall verifies the crossing contract.</p>
            <div className="font-mono text-[11px] text-slate-500">SOURCE: {realm.repo}</div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => probeRealm(realmId)} className="px-3 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-xs font-mono text-slate-200 flex items-center gap-2"><RefreshCw className="w-3.5 h-3.5" /> Probe Realm</button>
              <button onClick={() => setRealm(realmId)} className="px-4 py-2 rounded-xl text-black font-black text-xs font-mono flex items-center gap-2" style={{ backgroundColor: realm.accent }}>Route Here <ArrowUpRight className="w-3.5 h-3.5" /></button>
            </div>
          </div>
          <div className="lg:col-span-7">
            <div className="relative min-h-[380px] rounded-[2rem] border border-white/10 bg-black/60 overflow-hidden p-6 sm:p-8">
              <div className="absolute inset-0 opacity-30" style={{ background: `radial-gradient(circle at 70% 35%, ${realm.accent}33, transparent 48%)` }} />
              <div className="absolute inset-y-0 left-1/2 w-px bg-gradient-to-b from-transparent via-white/20 to-transparent" />
              <div className="relative z-10 h-full flex flex-col justify-between gap-10">
                <div className="flex items-center justify-between font-mono text-[10px] text-slate-500"><span>REALM LINK // {realm.transport.toUpperCase()}</span><span className="flex items-center gap-2"><span className={`w-2 h-2 rounded-full ${probeDot(realmId)}`} /> {probeState[realmId].toUpperCase()}</span></div>
                <div className="flex-1 grid place-items-center">
                  <div className="relative w-56 h-56 sm:w-64 sm:h-64 rounded-full border border-white/10 grid place-items-center" style={{ boxShadow: `inset 0 0 60px ${realm.accent}12, 0 0 80px ${realm.accent}10` }}>
                    <div className="absolute inset-5 rounded-full border border-dashed animate-[spin_24s_linear_infinite]" style={{ borderColor: `${realm.accent}55` }} />
                    <div className="absolute inset-10 rounded-full border border-white/10 animate-[spin_14s_linear_infinite_reverse]" />
                    <div className="w-24 h-24 rounded-3xl grid place-items-center bg-black/80 border" style={{ borderColor: `${realm.accent}66`, color: realm.accent }}>{realm.icon}</div>
                  </div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/70 p-3 font-mono text-[10px] text-slate-400 break-words">{probeDetail[realmId]}</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  };

  const portal = (
    <div id="bifrost-worldtree-portal" className="relative mt-12 border-t border-cyan-400/20 bg-[#03060d] overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-50 bg-[radial-gradient(circle_at_50%_15%,rgba(34,211,238,0.12),transparent_34%),radial-gradient(circle_at_75%_62%,rgba(192,132,252,0.10),transparent_30%),radial-gradient(circle_at_25%_82%,rgba(245,158,11,0.08),transparent_28%)]" />
      <aside className="sticky top-3 z-40 hidden xl:block float-left ml-3 mt-6 w-48 rounded-2xl border border-white/10 bg-black/75 backdrop-blur-xl p-2 shadow-2xl">
        <div className="px-2 py-2 font-mono text-[9px] tracking-[0.22em] text-cyan-300">BIFROST SCROLL</div>
        {CHAPTERS.map(chapter => <button key={chapter.id} onClick={() => scrollToChapter(chapter.id)} className={`w-full text-left px-2 py-2 rounded-xl transition-all flex items-center gap-2 ${activeChapter === chapter.id ? 'bg-cyan-500/12 text-white' : 'text-slate-500 hover:text-slate-300'}`}><span className={`text-[9px] font-mono ${activeChapter === chapter.id ? 'text-cyan-300' : 'text-slate-700'}`}>{chapter.index}</span><span className="text-[10px] font-mono truncate">{chapter.label}</span></button>)}
      </aside>

      <div className="relative z-10 max-w-6xl mx-auto px-5 sm:px-8 xl:px-12">
        <section id="bifrost-chapter-threshold" ref={node => { sectionRefs.current.threshold = node; }} className="min-h-[96vh] flex items-center py-20">
          <div className="w-full grid lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-7 space-y-6">
              <div className="font-mono text-[10px] tracking-[0.32em] text-cyan-300">00 // THE BIFROST THRESHOLD</div>
              <h2 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-[-0.04em] text-white leading-[0.95]">Cross realms.<br /><span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-purple-300 to-amber-300">Keep sovereignty.</span></h2>
              <p className="text-base sm:text-lg text-slate-400 max-w-2xl leading-relaxed">A continuous operator journey through Camelot's bridge layer. Hermes chooses the path. Heimdall decides what may cross. The connected systems remain sovereign destinations beyond the gate.</p>
              <div className="flex flex-wrap gap-2 font-mono text-[10px]"><span className="px-3 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-950/20 text-cyan-300">HERMES // ROUTING</span><span className="px-3 py-1.5 rounded-full border border-blue-500/30 bg-blue-950/20 text-blue-300">HEIMDALL // AUTHORITY</span><span className={`px-3 py-1.5 rounded-full border ${gatewayReachable === false ? 'border-red-500/30 text-red-300' : gatewayReachable ? 'border-emerald-500/30 text-emerald-300' : 'border-slate-700 text-slate-500'}`}>GATEWAY // {gatewayReachable === false ? 'OFFLINE' : gatewayReachable ? 'REACHABLE' : 'UNPROBED'}</span></div>
              <button onClick={() => scrollToChapter('hermes')} className="inline-flex items-center gap-2 text-xs font-mono text-cyan-200 hover:text-white transition-colors">Enter Bifrost <ArrowDown className="w-4 h-4 animate-bounce" /></button>
            </div>
            <div className="lg:col-span-5 grid place-items-center"><div className="relative w-72 h-72 sm:w-80 sm:h-80 rounded-full border border-cyan-400/20 grid place-items-center shadow-[0_0_100px_rgba(34,211,238,0.10)]"><div className="absolute inset-4 rounded-full border border-dashed border-purple-400/30 animate-[spin_30s_linear_infinite]" /><div className="absolute inset-12 rounded-full border border-amber-400/20 animate-[spin_18s_linear_infinite_reverse]" /><div className="absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-cyan-300/0 via-cyan-300/80 to-cyan-300/0" /><Network className="w-20 h-20 text-cyan-300" /></div></div>
          </div>
        </section>

        <section id="bifrost-chapter-hermes" ref={node => { sectionRefs.current.hermes = node; }} className="min-h-[96vh] flex items-center py-20">
          <div className="w-full grid lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-5 space-y-5"><div className="font-mono text-[10px] tracking-[0.3em] text-cyan-300">01 // SIR HERMES</div><h3 className="text-4xl sm:text-5xl font-black text-white">Routing is motion with memory.</h3><p className="text-slate-400 leading-relaxed">Hermes does not grant authority. He preserves intent, selects the transport, and presents the proposed crossing to Heimdall.</p><button onClick={probeAll} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-500/10 border border-cyan-400/30 text-cyan-200 font-mono text-xs hover:bg-cyan-500/20"><RefreshCw className="w-3.5 h-3.5" /> Probe All Realms</button></div>
            <div className="lg:col-span-7"><div className="relative rounded-[2rem] border border-cyan-400/20 bg-black/60 p-6 sm:p-8 min-h-[430px] overflow-hidden"><div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(34,211,238,0.10),transparent_55%)]" /><div className="relative z-10 h-full flex flex-col justify-center gap-5"><div className="flex items-center gap-3"><Route className="w-7 h-7 text-cyan-300" /><span className="font-mono text-xs text-cyan-200">CAMELOT-VPS // ROUTE FORGE</span></div>{(Object.keys(REALMS) as RealmId[]).map(realmId => { const realm = REALMS[realmId]; return <button key={realmId} onClick={() => setRealm(realmId)} className="group grid grid-cols-[auto_1fr_auto] gap-4 items-center p-4 rounded-2xl border border-white/10 bg-white/[0.03] hover:border-cyan-400/40 hover:bg-cyan-500/[0.04] transition-all text-left"><div className="w-11 h-11 rounded-xl grid place-items-center border border-white/10" style={{ color: realm.accent }}>{realm.icon}</div><div><div className="text-sm font-bold text-white">{realm.label}</div><div className="text-[10px] text-slate-500 font-mono mt-0.5">{realm.transport.toUpperCase()} // {probeDetail[realmId]}</div></div><span className={`w-2.5 h-2.5 rounded-full ${probeDot(realmId)}`} /></button>; })}</div></div></div>
          </div>
        </section>

        <section id="bifrost-chapter-heimdall" ref={node => { sectionRefs.current.heimdall = node; }} className="min-h-[96vh] flex items-center py-20">
          <div className="w-full grid lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-6 order-2 lg:order-1"><div className="rounded-[2rem] border border-blue-400/20 bg-black/60 p-6 sm:p-8 space-y-3">{(Object.keys(gates) as GateId[]).map((gate, index) => { const isOpen = gates[gate]; return <button key={gate} onClick={() => setGates(prev => ({ ...prev, [gate]: !prev[gate] }))} className={`w-full p-4 rounded-2xl border flex items-center justify-between transition-all ${isOpen ? 'border-emerald-500/25 bg-emerald-950/10' : 'border-red-500/35 bg-red-950/20'}`}><div className="flex items-center gap-3 text-left"><span className="w-8 h-8 rounded-lg bg-black/60 border border-white/10 grid place-items-center font-mono text-[10px] text-slate-500">0{index + 1}</span><div><div className="font-mono text-xs font-bold uppercase text-white">{gate}</div><div className="text-[10px] text-slate-500">Heimdall verification boundary</div></div></div>{isOpen ? <Unlock className="w-4 h-4 text-emerald-400" /> : <Lock className="w-4 h-4 text-red-400" />}</button>; })}<button onClick={() => setSealed(prev => !prev)} className={`w-full mt-3 py-3 rounded-xl font-mono text-xs font-black border transition-all ${sealed ? 'bg-red-500 text-black border-red-400' : 'bg-blue-500/10 text-blue-200 border-blue-400/30'}`}>{sealed ? 'BIFROST SEALED // UNSEAL' : 'SEAL ENTIRE BIFROST'}</button></div></div>
            <div className="lg:col-span-6 order-1 lg:order-2 space-y-5"><div className="font-mono text-[10px] tracking-[0.3em] text-blue-300">02 // SIR HEIMDALL</div><h3 className="text-4xl sm:text-5xl font-black text-white">Nothing crosses because it asked nicely.</h3><p className="text-slate-400 leading-relaxed">Every crossing is fail-closed. Identity, integrity, intent, payload, and access must all remain open. Hermes may propose the road; Heimdall owns the gate.</p><div className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl border font-mono text-[10px] ${gateOpen ? 'border-emerald-500/30 bg-emerald-950/20 text-emerald-300' : 'border-red-500/30 bg-red-950/20 text-red-300'}`}><ShieldCheck className="w-4 h-4" /> {gateOpen ? 'ALL FIVE GATES OPEN' : 'CROSSING BLOCKED'}</div></div>
          </div>
        </section>

        {realmSection('multivoice', 'multivoice', '03')}
        {realmSection('godseye', 'godseye', '04')}
        {realmSection('worldmonitor', 'worldmonitor', '05')}

        <section id="bifrost-chapter-crossing" ref={node => { sectionRefs.current.crossing = node; }} className="min-h-[96vh] flex items-center py-20">
          <div className="w-full grid lg:grid-cols-12 gap-10 items-start">
            <div className="lg:col-span-5 space-y-5 lg:sticky lg:top-24"><div className="font-mono text-[10px] tracking-[0.3em] text-emerald-300">06 // CROSSING CHAMBER</div><h3 className="text-4xl sm:text-5xl font-black text-white">Authorize one crossing.</h3><p className="text-slate-400 leading-relaxed">The journey resolves here. Hermes has a route, Heimdall has a verdict, and the destination remains independently owned.</p><div className="rounded-2xl border border-white/10 bg-black/50 p-4 space-y-2 font-mono text-[10px]"><div className="flex justify-between"><span className="text-slate-500">SOURCE</span><span className="text-[#D4AF37]">CAMELOT-VPS</span></div><div className="flex justify-between"><span className="text-slate-500">DESTINATION</span><span className="text-white">{REALMS[selectedRealm].label}</span></div><div className="flex justify-between"><span className="text-slate-500">TRANSPORT</span><span className="text-cyan-300 uppercase">{REALMS[selectedRealm].transport}</span></div><div className="flex justify-between"><span className="text-slate-500">HEIMDALL</span><span className={gateOpen ? 'text-emerald-300' : 'text-red-300'}>{gateOpen ? 'AUTHORIZED' : 'BLOCKED'}</span></div></div></div>
            <div className="lg:col-span-7 rounded-[2rem] border border-emerald-400/20 bg-black/60 p-6 sm:p-8 space-y-5">
              <div className="grid sm:grid-cols-3 gap-2">{(Object.keys(REALMS) as RealmId[]).map(realmId => <button key={realmId} onClick={() => { setSelectedRealm(realmId); setIntent(REALMS[realmId].intent); }} className={`p-3 rounded-xl border text-left ${selectedRealm === realmId ? 'border-emerald-400/50 bg-emerald-950/20' : 'border-white/10 bg-white/[0.02]'}`}><div className="text-[10px] font-mono text-white font-bold">{REALMS[realmId].label}</div><div className="text-[9px] font-mono text-slate-500 mt-1 uppercase">{REALMS[realmId].transport}</div></button>)}</div>
              <label className="block"><span className="font-mono text-[10px] text-slate-500">CROSSING INTENT</span><textarea value={intent} onChange={event => setIntent(event.target.value)} rows={3} className="mt-2 w-full rounded-xl border border-emerald-500/20 bg-black/70 p-3 text-xs text-white font-mono focus:outline-none focus:border-emerald-400" /></label>
              <label className="block"><span className="font-mono text-[10px] text-slate-500">OPTIONAL PAYLOAD / CONTEXT</span><textarea value={payload} onChange={event => setPayload(event.target.value.slice(0, 12000))} rows={5} placeholder="Maximum 12KB. Carried only through the allowlisted Bifrost adapter." className="mt-2 w-full rounded-xl border border-white/10 bg-black/70 p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-emerald-400" /></label>
              <button onClick={executeCrossing} disabled={!gateOpen || !intent.trim() || crossingBusy} className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-400 via-cyan-400 to-purple-400 disabled:from-slate-700 disabled:to-slate-800 disabled:text-slate-500 text-black font-mono text-xs font-black flex items-center justify-center gap-2"><Send className="w-4 h-4" /> {crossingBusy ? 'CROSSING BIFROST...' : gateOpen ? 'AUTHORIZE CROSSING' : 'BLOCKED BY HEIMDALL'}</button>
              {crossingResult && <div className={`rounded-2xl border p-4 font-mono text-[11px] ${crossingResult.error ? 'border-red-500/40 bg-red-950/20 text-red-200' : 'border-emerald-500/30 bg-emerald-950/15 text-emerald-100'}`}><div className="font-bold flex items-center gap-2">{crossingResult.error ? <CircleOff className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}{crossingResult.error || crossingResult.result || 'Crossing complete'}</div>{crossingResult.detail && <div className="mt-2 text-slate-300 break-words max-h-36 overflow-auto">{crossingResult.detail}</div>}{crossingResult.requiresHandoff && crossingResult.launchUrl && <button onClick={() => window.open(crossingResult.launchUrl, '_blank', 'noopener,noreferrer')} className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-emerald-500/30 bg-emerald-950/20 hover:bg-emerald-950/40 text-emerald-200"><ExternalLink className="w-3.5 h-3.5" /> Continue into {REALMS[selectedRealm].label}</button>}</div>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );

  return <>{mountTarget && createPortal(portal, mountTarget)}{scrollerPresent && <button onClick={() => scrollToChapter('threshold')} className="fixed bottom-16 right-5 z-[60] hidden sm:flex items-center gap-2 px-3 py-2 rounded-full border border-cyan-400/30 bg-black/80 backdrop-blur-xl shadow-[0_0_30px_rgba(34,211,238,0.15)] text-cyan-200 font-mono text-[10px] hover:border-cyan-300 transition-all" title="Scroll to Bifrost Bridge"><Waves className="w-3.5 h-3.5" /> BIFROST <span className={`w-1.5 h-1.5 rounded-full ${gateOpen ? 'bg-emerald-400' : 'bg-red-400'}`} /></button>}</>;
};

export default BifrostWorldTreePortal;
