import React, { useMemo, useState } from 'react';
import {
  ArrowDown,
  ArrowUpRight,
  CheckCircle2,
  CircleOff,
  ExternalLink,
  Eye,
  Gauge,
  Globe2,
  Headphones,
  Lock,
  Network,
  Radio,
  RefreshCw,
  Route,
  Send,
  ShieldCheck,
  Sparkles,
  Unlock,
  Waves,
} from 'lucide-react';

type RealmId = 'multivoice' | 'godseye' | 'worldmonitor';
type GateId = 'identity' | 'integrity' | 'intent' | 'payload' | 'access';
type ProbeState = 'idle' | 'probing' | 'online' | 'offline';

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
  eyebrow: string;
  description: string;
  transport: 'bridge' | 'handoff' | 'mcp';
  intent: string;
  url: string;
  repo: string;
}> = {
  multivoice: {
    label: 'Multivoice Router',
    eyebrow: 'VOICE / PERSONA REALM',
    description: 'Route governed voice identities, persona previews, RAG context and Tailscale-aware bridge handoffs into the living Camelot voice layer.',
    transport: 'bridge',
    intent: 'Open a governed persona voice handoff through Bifrost.',
    url: 'https://obsidian-spire-hud.vercel.app',
    repo: 'Cyberdad247/Multivoice-router',
  },
  godseye: {
    label: "God's Eye View",
    eyebrow: 'SPATIAL INTELLIGENCE REALM',
    description: 'Move from Camelot into a photorealistic live globe with tracked aircraft, ships, satellites, earthquakes, public cameras and voice-driven exploration.',
    transport: 'handoff',
    intent: 'Open the spatial-intelligence realm with operator-controlled handoff.',
    url: 'https://maptheworld.ai',
    repo: 'Cyberdad247/gods-eye-view',
  },
  worldmonitor: {
    label: 'WorldMonitor',
    eyebrow: 'GLOBAL INTELLIGENCE REALM',
    description: 'Cross into the geopolitical, infrastructure and global-event intelligence surface through a narrow MCP capability boundary.',
    transport: 'mcp',
    intent: 'Discover the WorldMonitor MCP capability surface through Heimdall.',
    url: 'https://worldmonitor.app',
    repo: 'koala73/worldmonitor',
  },
};

const CHAPTERS = [
  ['threshold', '00', 'Threshold'],
  ['hermes', '01', 'Hermes'],
  ['heimdall', '02', 'Heimdall'],
  ['multivoice', '03', 'Voices'],
  ['godseye', '04', "God's Eye"],
  ['worldmonitor', '05', 'WorldMonitor'],
  ['crossing', '06', 'Crossing'],
] as const;

const DEFAULT_GATES: Record<GateId, boolean> = {
  identity: true,
  integrity: true,
  intent: true,
  payload: true,
  access: true,
};

const scrollTo = (id: string) => {
  document.getElementById(`bifrost-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const SectionShell: React.FC<{
  id: string;
  children: React.ReactNode;
  className?: string;
}> = ({ id, children, className = '' }) => (
  <section
    id={`bifrost-${id}`}
    className={`relative min-h-[100svh] scroll-mt-20 snap-start overflow-hidden border-t border-white/5 ${className}`}
  >
    {children}
  </section>
);

export const BifrostScrollExperience: React.FC = () => {
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
  const [gatewayReachable, setGatewayReachable] = useState<boolean | null>(null);
  const [crossingBusy, setCrossingBusy] = useState(false);
  const [crossingResult, setCrossingResult] = useState<CrossingResult | null>(null);

  const gateOpen = useMemo(
    () => !sealed && Object.values(gates).every(Boolean),
    [gates, sealed],
  );

  const selectRealm = (realm: RealmId) => {
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
      const data = await response.json();
      setGatewayReachable(true);
      setProbeState(prev => ({ ...prev, [realm]: data.reachable ? 'online' : 'offline' }));
    } catch {
      setGatewayReachable(false);
      setProbeState(prev => ({ ...prev, [realm]: 'offline' }));
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
      const data = await response.json();
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

  const realmStateClass = (realm: RealmId) => {
    const state = probeState[realm];
    if (state === 'online') return 'bg-emerald-400 shadow-[0_0_18px_rgba(52,211,153,.75)]';
    if (state === 'offline') return 'bg-red-400';
    if (state === 'probing') return 'bg-amber-400 animate-pulse';
    return 'bg-slate-600';
  };

  return (
    <div id="bifrost-scroll-experience" className="relative bg-[#050505] text-slate-100 snap-y snap-proximity selection:bg-cyan-400/30">
      <div className="pointer-events-none fixed inset-0 z-[70] hidden xl:block">
        <div className="absolute left-6 top-1/2 -translate-y-1/2 pointer-events-auto rounded-2xl border border-white/10 bg-black/55 backdrop-blur-xl p-2 shadow-2xl">
          {CHAPTERS.map(([id, number, label]) => (
            <button
              key={id}
              onClick={() => scrollTo(id)}
              className="group flex w-full items-center gap-2 rounded-xl px-2 py-2 text-left hover:bg-white/5"
            >
              <span className="font-mono text-[9px] text-[#D4AF37]">{number}</span>
              <span className="h-px w-4 bg-white/20 transition-all group-hover:w-7 group-hover:bg-cyan-400" />
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500 group-hover:text-white">{label}</span>
            </button>
          ))}
        </div>
      </div>

      <SectionShell id="threshold" className="flex items-center justify-center bg-[radial-gradient(circle_at_50%_45%,rgba(34,211,238,.13),transparent_28%),radial-gradient(circle_at_50%_40%,rgba(46,8,84,.4),transparent_58%)]">
        <div className="absolute inset-0 opacity-60 pointer-events-none">
          <div className="absolute left-1/2 top-[12%] h-[76%] w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-cyan-300/70 to-transparent" />
          <div className="absolute left-1/2 top-1/2 h-[42rem] w-[42rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/15 shadow-[0_0_120px_rgba(34,211,238,.08)]" />
          <div className="absolute left-1/2 top-1/2 h-[30rem] w-[30rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-[#D4AF37]/15 rotate-45" />
        </div>

        <div className="relative z-10 mx-auto max-w-6xl px-6 py-24 text-center">
          <div className="mx-auto mb-8 flex h-20 w-20 items-center justify-center rounded-[2rem] border border-cyan-300/40 bg-cyan-950/20 shadow-[0_0_70px_rgba(34,211,238,.18)]">
            <Network className="h-9 w-9 text-cyan-200" />
          </div>
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.42em] text-[#D4AF37]">Camelot-OS / Realm Transit Layer</p>
          <h2 className="mt-5 text-5xl font-black tracking-[-0.05em] text-white sm:text-7xl lg:text-8xl">
            CROSS THE <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-200 via-white to-[#D4AF37]">BIFROST</span>
          </h2>
          <p className="mx-auto mt-6 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
            A scrolling command journey from sovereign intent to governed crossing. Hermes finds the road. Heimdall decides whether the road opens.
          </p>

          <div className="mx-auto mt-10 grid max-w-3xl grid-cols-3 gap-2 rounded-2xl border border-white/10 bg-black/45 p-2 backdrop-blur-xl">
            {(Object.keys(REALMS) as RealmId[]).map(realm => (
              <button
                key={realm}
                onClick={() => { selectRealm(realm); scrollTo(realm); }}
                className="rounded-xl border border-white/5 bg-white/[0.025] px-3 py-4 transition-all hover:border-cyan-400/30 hover:bg-cyan-400/5"
              >
                <span className={`mx-auto mb-2 block h-2 w-2 rounded-full ${realmStateClass(realm)}`} />
                <span className="block font-mono text-[9px] uppercase text-slate-400 sm:text-[10px]">{REALMS[realm].label}</span>
              </button>
            ))}
          </div>

          <button onClick={() => scrollTo('hermes')} className="mt-12 inline-flex flex-col items-center gap-2 text-slate-500 hover:text-cyan-200">
            <span className="font-mono text-[9px] uppercase tracking-[0.28em]">Begin descent</span>
            <ArrowDown className="h-5 w-5 animate-bounce" />
          </button>
        </div>
      </SectionShell>

      <SectionShell id="hermes" className="bg-[linear-gradient(180deg,#050505,#071521_48%,#050505)]">
        <div className="mx-auto grid min-h-[100svh] max-w-7xl items-center gap-12 px-6 py-24 lg:grid-cols-[1.05fr_.95fr]">
          <div>
            <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.28em] text-cyan-300">
              <Route className="h-4 w-4" /> 01 / Sir Hermes
            </div>
            <h3 className="mt-5 text-5xl font-black tracking-[-0.045em] text-white sm:text-6xl">Route the impossible.</h3>
            <p className="mt-5 max-w-xl text-sm leading-7 text-slate-400">
              Hermes translates operator intent into a governed crossing contract. The destination, transport and carried context are visible before Heimdall ever sees the request.
            </p>

            <div className="mt-10 space-y-3">
              {(Object.keys(REALMS) as RealmId[]).map(realm => (
                <button
                  key={realm}
                  onClick={() => selectRealm(realm)}
                  className={`group flex w-full items-center justify-between rounded-2xl border p-4 text-left transition-all ${selectedRealm === realm ? 'border-cyan-300/45 bg-cyan-400/[0.07] shadow-[0_0_40px_rgba(34,211,238,.06)]' : 'border-white/10 bg-black/30 hover:border-white/20'}`}
                >
                  <div>
                    <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-500">{REALMS[realm].eyebrow}</div>
                    <div className="mt-1 font-bold text-white">{REALMS[realm].label}</div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`h-2.5 w-2.5 rounded-full ${realmStateClass(realm)}`} />
                    <ArrowUpRight className="h-4 w-4 text-slate-600 group-hover:text-cyan-300" />
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="relative min-h-[520px] [perspective:1200px]">
            <div className="absolute inset-0 rounded-[3rem] border border-cyan-300/15 bg-cyan-400/[0.025] shadow-[inset_0_0_70px_rgba(34,211,238,.035)] [transform:rotateY(-7deg)_rotateX(3deg)]" />
            <div className="absolute left-[12%] top-[12%] right-[5%] bottom-[8%] rounded-[2.5rem] border border-white/10 bg-black/70 p-6 backdrop-blur-xl [transform:translateZ(45px)]">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.25em] text-cyan-300">Hermes Routing Forge</div>
                  <div className="mt-1 font-bold text-white">{REALMS[selectedRealm].label}</div>
                </div>
                <button onClick={probeAll} className="rounded-xl border border-white/10 bg-white/5 p-2 text-slate-400 hover:text-cyan-200" title="Probe all realms">
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3 font-mono text-[10px]">
                <div className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
                  <span className="text-slate-600">SOURCE</span>
                  <div className="mt-1 text-[#D4AF37]">CAMELOT-VPS</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
                  <span className="text-slate-600">TRANSPORT</span>
                  <div className="mt-1 uppercase text-cyan-300">{REALMS[selectedRealm].transport}</div>
                </div>
              </div>

              <label className="mt-4 block">
                <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-500">Crossing intent</span>
                <textarea value={intent} onChange={e => setIntent(e.target.value)} rows={4} className="mt-2 w-full rounded-2xl border border-cyan-400/20 bg-black/70 p-3 font-mono text-xs text-white outline-none focus:border-cyan-300/60" />
              </label>

              <label className="mt-4 block">
                <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-500">Context payload</span>
                <textarea value={payload} onChange={e => setPayload(e.target.value.slice(0, 12000))} rows={3} placeholder="Optional context carried across Bifrost" className="mt-2 w-full rounded-2xl border border-white/10 bg-black/70 p-3 font-mono text-xs text-slate-300 outline-none focus:border-cyan-300/60" />
              </label>

              <button onClick={() => scrollTo('heimdall')} className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-cyan-300 px-4 py-3 font-mono text-xs font-black text-black hover:bg-cyan-200">
                Present route to Heimdall <ArrowDown className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </SectionShell>

      <SectionShell id="heimdall" className="bg-[radial-gradient(circle_at_50%_50%,rgba(212,175,55,.08),transparent_28%),linear-gradient(180deg,#050505,#110d05_50%,#050505)]">
        <div className="mx-auto flex min-h-[100svh] max-w-7xl flex-col justify-center px-6 py-24">
          <div className="mx-auto max-w-3xl text-center">
            <div className="font-mono text-[10px] uppercase tracking-[0.32em] text-[#D4AF37]">02 / Sir Heimdall</div>
            <h3 className="mt-5 text-5xl font-black tracking-[-0.045em] text-white sm:text-7xl">Nothing unseen shall pass.</h3>
            <p className="mx-auto mt-5 max-w-2xl text-sm leading-7 text-slate-400">Every crossing must survive five gates. Close one and the bridge becomes a wall.</p>
          </div>

          <div className="mx-auto mt-14 grid w-full max-w-5xl gap-3 md:grid-cols-5">
            {(Object.keys(gates) as GateId[]).map((gate, index) => (
              <button
                key={gate}
                onClick={() => setGates(prev => ({ ...prev, [gate]: !prev[gate] }))}
                className={`relative min-h-56 overflow-hidden rounded-[2rem] border p-5 text-left transition-all ${gates[gate] ? 'border-emerald-400/30 bg-emerald-400/[0.045]' : 'border-red-500/40 bg-red-950/25'}`}
              >
                <div className="font-mono text-[9px] text-slate-600">GATE 0{index + 1}</div>
                <div className="mt-10 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-black/60">
                  {gates[gate] ? <Unlock className="h-5 w-5 text-emerald-300" /> : <Lock className="h-5 w-5 text-red-300" />}
                </div>
                <div className="mt-4 font-mono text-xs font-bold uppercase tracking-[0.14em] text-white">{gate}</div>
                <div className={`mt-2 font-mono text-[9px] ${gates[gate] ? 'text-emerald-400' : 'text-red-400'}`}>{gates[gate] ? 'VERIFIED' : 'BLOCKED'}</div>
                <div className={`absolute inset-x-0 bottom-0 h-1 ${gates[gate] ? 'bg-emerald-400' : 'bg-red-500'}`} />
              </button>
            ))}
          </div>

          <div className="mx-auto mt-8 flex flex-wrap items-center justify-center gap-3">
            <button onClick={() => setSealed(v => !v)} className={`rounded-xl border px-4 py-2.5 font-mono text-[10px] font-bold ${sealed ? 'border-red-500/50 bg-red-950/40 text-red-200' : 'border-[#D4AF37]/35 bg-[#D4AF37]/10 text-[#D4AF37]'}`}>
              {sealed ? 'Unseal entire Bifrost' : 'Seal entire Bifrost'}
            </button>
            <button onClick={() => scrollTo(selectedRealm)} disabled={!gateOpen} className="rounded-xl bg-[#D4AF37] px-4 py-2.5 font-mono text-[10px] font-black text-black disabled:bg-slate-800 disabled:text-slate-500">
              {gateOpen ? 'Gates verified · continue' : 'Crossing blocked'}
            </button>
          </div>
        </div>
      </SectionShell>

      <SectionShell id="multivoice" className="bg-[radial-gradient(circle_at_70%_50%,rgba(34,211,238,.14),transparent_35%),linear-gradient(180deg,#050505,#061820,#050505)]">
        <RealmChapter
          number="03"
          realm="multivoice"
          selected={selectedRealm === 'multivoice'}
          icon={<Headphones className="h-8 w-8" />}
          accent="text-cyan-200"
          orb="border-cyan-300/30 shadow-[0_0_100px_rgba(34,211,238,.12)]"
          onSelect={() => { selectRealm('multivoice'); probeRealm('multivoice'); }}
          onContinue={() => scrollTo('godseye')}
        />
      </SectionShell>

      <SectionShell id="godseye" className="bg-[radial-gradient(circle_at_28%_50%,rgba(245,158,11,.12),transparent_35%),linear-gradient(180deg,#050505,#171006,#050505)]">
        <RealmChapter
          number="04"
          realm="godseye"
          selected={selectedRealm === 'godseye'}
          icon={<Eye className="h-8 w-8" />}
          accent="text-amber-200"
          orb="border-amber-300/30 shadow-[0_0_100px_rgba(245,158,11,.12)]"
          onSelect={() => { selectRealm('godseye'); probeRealm('godseye'); }}
          onContinue={() => scrollTo('worldmonitor')}
        />
      </SectionShell>

      <SectionShell id="worldmonitor" className="bg-[radial-gradient(circle_at_70%_48%,rgba(168,85,247,.14),transparent_35%),linear-gradient(180deg,#050505,#13071b,#050505)]">
        <RealmChapter
          number="05"
          realm="worldmonitor"
          selected={selectedRealm === 'worldmonitor'}
          icon={<Globe2 className="h-8 w-8" />}
          accent="text-purple-200"
          orb="border-purple-300/30 shadow-[0_0_100px_rgba(168,85,247,.14)]"
          onSelect={() => { selectRealm('worldmonitor'); probeRealm('worldmonitor'); }}
          onContinue={() => scrollTo('crossing')}
        />
      </SectionShell>

      <SectionShell id="crossing" className="bg-[radial-gradient(circle_at_50%_48%,rgba(34,211,238,.10),transparent_23%),radial-gradient(circle_at_50%_48%,rgba(212,175,55,.07),transparent_45%),#050505]">
        <div className="mx-auto flex min-h-[100svh] max-w-6xl flex-col items-center justify-center px-6 py-24 text-center">
          <div className={`flex h-24 w-24 items-center justify-center rounded-[2rem] border bg-black/60 ${gateOpen ? 'border-emerald-300/40 shadow-[0_0_70px_rgba(52,211,153,.12)]' : 'border-red-400/40 shadow-[0_0_70px_rgba(248,113,113,.1)]'}`}>
            {gateOpen ? <ShieldCheck className="h-10 w-10 text-emerald-300" /> : <CircleOff className="h-10 w-10 text-red-300" />}
          </div>
          <div className="mt-8 font-mono text-[10px] uppercase tracking-[0.32em] text-[#D4AF37]">06 / Crossing Chamber</div>
          <h3 className="mt-5 text-5xl font-black tracking-[-0.045em] text-white sm:text-7xl">The bridge is {gateOpen ? 'open.' : 'sealed.'}</h3>
          <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-400">
            Destination: <span className="text-white">{REALMS[selectedRealm].label}</span>. Transport: <span className="uppercase text-cyan-300">{REALMS[selectedRealm].transport}</span>. Heimdall status: <span className={gateOpen ? 'text-emerald-300' : 'text-red-300'}>{gateOpen ? 'AUTHORIZED' : 'BLOCKED'}</span>.
          </p>

          <div className="mt-10 w-full max-w-3xl rounded-[2rem] border border-white/10 bg-black/55 p-5 text-left backdrop-blur-xl">
            <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-slate-500">Final crossing contract</div>
                <div className="mt-1 font-bold text-white">Camelot → {REALMS[selectedRealm].label}</div>
              </div>
              <span className={`rounded-full px-2.5 py-1 font-mono text-[9px] ${gatewayReachable === true ? 'bg-emerald-950 text-emerald-300' : gatewayReachable === false ? 'bg-red-950 text-red-300' : 'bg-slate-900 text-slate-400'}`}>
                GATEWAY {gatewayReachable === true ? 'REACHABLE' : gatewayReachable === false ? 'OFFLINE' : 'UNPROBED'}
              </span>
            </div>

            <div className="mt-4 font-mono text-xs leading-6 text-slate-300">{intent}</div>
            {payload && <div className="mt-3 max-h-28 overflow-auto rounded-xl border border-white/5 bg-white/[0.025] p-3 font-mono text-[10px] text-slate-500">{payload}</div>}

            <button onClick={executeCrossing} disabled={!gateOpen || !intent.trim() || crossingBusy} className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-cyan-300 via-white to-[#D4AF37] px-4 py-3.5 font-mono text-xs font-black text-black disabled:from-slate-800 disabled:via-slate-800 disabled:to-slate-800 disabled:text-slate-500">
              <Send className="h-4 w-4" /> {crossingBusy ? 'Crossing Bifrost...' : gateOpen ? 'Authorize crossing' : 'Blocked by Heimdall'}
            </button>

            {crossingResult && (
              <div className={`mt-4 rounded-xl border p-4 font-mono text-[10px] ${crossingResult.error ? 'border-red-500/30 bg-red-950/20 text-red-200' : 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100'}`}>
                <div className="font-bold">{crossingResult.error || crossingResult.result || 'Crossing complete'}</div>
                {crossingResult.detail && <div className="mt-2 max-h-32 overflow-auto break-words text-slate-400">{crossingResult.detail}</div>}
                {crossingResult.requiresHandoff && crossingResult.launchUrl && (
                  <button onClick={() => window.open(crossingResult.launchUrl, '_blank', 'noopener,noreferrer')} className="mt-3 inline-flex items-center gap-2 rounded-lg border border-emerald-400/30 px-3 py-2 text-emerald-300 hover:bg-emerald-400/5">
                    Enter {REALMS[selectedRealm].label} <ExternalLink className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>

          <button onClick={() => scrollTo('threshold')} className="mt-10 font-mono text-[9px] uppercase tracking-[0.22em] text-slate-600 hover:text-white">Return to threshold</button>
        </div>
      </SectionShell>
    </div>
  );
};

const RealmChapter: React.FC<{
  number: string;
  realm: RealmId;
  selected: boolean;
  icon: React.ReactNode;
  accent: string;
  orb: string;
  onSelect: () => void;
  onContinue: () => void;
}> = ({ number, realm, selected, icon, accent, orb, onSelect, onContinue }) => {
  const meta = REALMS[realm];
  return (
    <div className="mx-auto grid min-h-[100svh] max-w-7xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
      <div className="order-2 lg:order-1">
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${accent}`}>{number} / {meta.eyebrow}</div>
        <h3 className="mt-5 text-5xl font-black tracking-[-0.045em] text-white sm:text-7xl">{meta.label}</h3>
        <p className="mt-6 max-w-xl text-sm leading-7 text-slate-400">{meta.description}</p>

        <div className="mt-8 flex flex-wrap gap-2 font-mono text-[9px] uppercase tracking-[0.12em]">
          <span className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-slate-400">{meta.repo}</span>
          <span className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-slate-400">{meta.transport}</span>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <button onClick={onSelect} className={`rounded-xl border px-4 py-2.5 font-mono text-[10px] font-bold ${selected ? 'border-cyan-300/40 bg-cyan-300/10 text-cyan-200' : 'border-white/10 bg-white/5 text-slate-300'}`}>
            {selected ? 'Selected route' : 'Route through this realm'}
          </button>
          <button onClick={() => window.open(meta.url, '_blank', 'noopener,noreferrer')} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 font-mono text-[10px] text-slate-300 hover:text-white">
            Inspect realm <ExternalLink className="h-3.5 w-3.5" />
          </button>
          <button onClick={onContinue} className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 font-mono text-[10px] text-slate-500 hover:text-white">
            Continue descent <ArrowDown className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="order-1 flex items-center justify-center lg:order-2">
        <div className={`relative flex h-[360px] w-[360px] items-center justify-center rounded-full border bg-black/30 sm:h-[470px] sm:w-[470px] ${orb}`}>
          <div className="absolute inset-[12%] rounded-full border border-white/10" />
          <div className="absolute inset-[25%] rounded-full border border-white/10 rotate-45" />
          <div className={`relative z-10 flex h-24 w-24 items-center justify-center rounded-[2rem] border border-white/15 bg-black/80 ${accent}`}>{icon}</div>
          <div className="absolute left-1/2 top-1/2 h-[135%] w-px -translate-x-1/2 -translate-y-1/2 rotate-[28deg] bg-gradient-to-b from-transparent via-white/10 to-transparent" />
          <div className="absolute left-1/2 top-1/2 h-px w-[135%] -translate-x-1/2 -translate-y-1/2 -rotate-[18deg] bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        </div>
      </div>
    </div>
  );
};

export default BifrostScrollExperience;
