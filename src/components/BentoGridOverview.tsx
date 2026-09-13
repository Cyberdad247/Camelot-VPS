import React, { lazy, useState } from 'react';
import { 
  ShieldCheck, 
  Cpu, 
  Layers, 
  RotateCcw, 
  CheckCircle2, 
  Activity, 
  Flame, 
  Play, 
  Terminal, 
  Server, 
  Database, 
  Lock, 
  Sparkles,
  ExternalLink,
  Crown,
  Minus,
  Plus,
  Eye,
  EyeOff,
  Key,
  Maximize2,
  Minimize2,
  Radio,
  FileCode,
  Zap,
  Code,
  Brain,
  BookOpen,
  Github
} from 'lucide-react';
import { CamelotService, SystemVitals, BootstrapPhase, SovereignLaw, TerminalLog } from '../types';
import { WorldTreeVisual } from './WorldTreeVisual';
import { GraphifyCanvas } from './GraphifyCanvas';
import { OuroborosMatrix } from './OuroborosMatrix';
import { VikingRefractions } from './VikingRefractions';
import { IpcMemorySlabs } from './IpcMemorySlabs';
import { SystemTelemetry } from './SystemTelemetry';
import { ProcessMatrix } from './ProcessMatrix';
import { SystemLogPanel } from './SystemLogPanel';
import { SystemCommandsPanel } from './SystemCommandsPanel';
const MemcastleModal = lazy(() => import('./MemcastleModal').then(m => ({ default: m.MemcastleModal })));
const TwinBrainsModal = lazy(() => import('./TwinBrainsModal').then(m => ({ default: m.TwinBrainsModal })));
import confetti from 'canvas-confetti';

interface BentoGridOverviewProps {
  vitals: SystemVitals;
  services: CamelotService[];
  phases: BootstrapPhase[];
  laws: SovereignLaw[];
  logs: TerminalLog[];
  onNavigateTab: (tab: string) => void;
  onGoLive: () => void;
  onRunMission: () => void;
  onRestartService: (serviceId: string) => void;
  onRunVitalsCheck: () => void;
  onExecuteCommand: (cmd: string) => void;
  onOpenBootstrapScript: () => void;
}

export const BentoGridOverview: React.FC<BentoGridOverviewProps> = ({
  vitals,
  services,
  phases,
  laws,
  logs,
  onNavigateTab,
  onGoLive,
  onRunMission,
  onRestartService,
  onRunVitalsCheck,
  onExecuteCommand,
  onOpenBootstrapScript
}) => {
  const [activeModal, setActiveModal] = useState<'memcastle' | 'brains' | null>(null);
  const [showSecrets, setShowSecrets] = useState(false);
  const [expandedLogs, setExpandedLogs] = useState(false);

  const runningServices = services.filter(s => s.status === 'running').length;
  const memoryPercent = Math.round((vitals.usedRamMB / vitals.scarcityCapMB) * 100);
  const scarce = memoryPercent >= 80;

  const handleCelebrate = () => {
    confetti({ particleCount: 120, spread: 70, origin: { y: 0.6 } });
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        <section className="xl:col-span-7 rounded-2xl border border-slate-800 bg-slate-950/75 p-5 overflow-hidden">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <div className="flex items-center gap-2 text-cyan-300 text-xs uppercase tracking-[0.22em]"><Crown size={14}/> Sovereign Overview</div>
              <h2 className="text-2xl font-semibold text-white mt-2">Camelot-OS World Tree</h2>
              <p className="text-sm text-slate-400 mt-1">A living map of memory, compute, orchestration and guarded execution.</p>
            </div>
            <button onClick={handleCelebrate} className="px-3 py-2 rounded-lg border border-amber-400/30 text-amber-300 text-xs hover:bg-amber-400/10"><Sparkles size={14} className="inline mr-1"/> Pulse</button>
          </div>
          <WorldTreeVisual />
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <button onClick={() => setActiveModal('memcastle')} className="rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-left"><Database size={16}/><b className="block mt-2 text-white">MemCastle</b><span className="text-slate-500">Open memory</span></button>
            <button onClick={() => setActiveModal('brains')} className="rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-left"><Brain size={16}/><b className="block mt-2 text-white">Twin Brains</b><span className="text-slate-500">Inspect cognition</span></button>
            <button onClick={() => onNavigateTab('deck')} className="rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-left"><Layers size={16}/><b className="block mt-2 text-white">World Tree Deck</b><span className="text-slate-500">Enter spatial map</span></button>
            <button onClick={() => onNavigateTab('mission')} className="rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-left"><Play size={16}/><b className="block mt-2 text-white">Mission Arena</b><span className="text-slate-500">Dispatch work</span></button>
          </div>
        </section>

        <section className="xl:col-span-5 grid grid-cols-2 gap-4">
          <Metric icon={<Server size={18}/>} label="Services" value={`${runningServices}/${services.length}`} detail="running" />
          <Metric icon={<Cpu size={18}/>} label="Memory" value={`${memoryPercent}%`} detail={`${vitals.usedRamMB} MB / ${vitals.scarcityCapMB} MB`} warn={scarce}/>
          <Metric icon={<Activity size={18}/>} label="CPU" value={`${vitals.cpuLoad}%`} detail="host load" />
          <Metric icon={<ShieldCheck size={18}/>} label="Laws" value={`${laws.filter(l => l.status === 'enforced').length}`} detail="enforced" />
          <div className="col-span-2 rounded-2xl border border-slate-800 bg-slate-950/75 p-4">
            <div className="flex items-center justify-between"><b className="text-white text-sm">System Actions</b><Zap size={16} className="text-amber-300"/></div>
            <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
              <Action icon={<Activity size={14}/>} label="Vitals" onClick={onRunVitalsCheck}/>
              <Action icon={<RotateCcw size={14}/>} label="Restart degraded" onClick={() => services.filter(s => s.status !== 'running').forEach(s => onRestartService(s.id))}/>
              <Action icon={<Terminal size={14}/>} label="Diagnostics" onClick={() => onExecuteCommand('camelot-diag --all')}/>
              <Action icon={<FileCode size={14}/>} label="Bootstrap" onClick={onOpenBootstrapScript}/>
              <Action icon={<Play size={14}/>} label="Run mission" onClick={onRunMission}/>
              <Action icon={<ExternalLink size={14}/>} label="Operator" onClick={() => onNavigateTab('operator')}/>
            </div>
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <GraphifyCanvas />
        <OuroborosMatrix />
        <VikingRefractions />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <IpcMemorySlabs />
        <SystemTelemetry vitals={vitals} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <ProcessMatrix services={services} onRestartService={onRestartService}/>
        <div className="space-y-5">
          <SystemCommandsPanel onExecuteCommand={onExecuteCommand}/>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/75 p-4">
            <div className="flex items-center justify-between mb-3"><b className="text-white text-sm">Secrets Boundary</b><button onClick={() => setShowSecrets(v => !v)} className="text-xs text-cyan-300">{showSecrets ? <EyeOff size={14}/> : <Eye size={14}/>}</button></div>
            <div className="flex items-center gap-3 text-sm"><Key size={16} className="text-amber-300"/><span className="text-slate-400">Runtime credentials:</span><b className="text-white">{showSecrets ? 'protected by environment boundary' : '••••••••••••'}</b></div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/75 p-4">
        <button onClick={() => setExpandedLogs(v => !v)} className="w-full flex items-center justify-between text-left"><span className="font-semibold text-white flex items-center gap-2"><Radio size={15}/> System Logs</span>{expandedLogs ? <Minimize2 size={15}/> : <Maximize2 size={15}/>}</button>
        {expandedLogs && <div className="mt-4"><SystemLogPanel logs={logs}/></div>}
      </div>

      {activeModal === 'memcastle' && <MemcastleModal onClose={() => setActiveModal(null)} />}
      {activeModal === 'brains' && <TwinBrainsModal onClose={() => setActiveModal(null)} />}
    </div>
  );
};

const Metric: React.FC<{icon: React.ReactNode; label: string; value: string; detail: string; warn?: boolean}> = ({icon, label, value, detail, warn}) => (
  <div className={`rounded-2xl border p-4 ${warn ? 'border-amber-500/30 bg-amber-500/5' : 'border-slate-800 bg-slate-950/75'}`}>
    <div className="text-slate-500">{icon}</div><b className="block text-2xl text-white mt-3">{value}</b><span className="block text-xs uppercase tracking-wider text-slate-400 mt-1">{label}</span><small className="text-slate-600">{detail}</small>
  </div>
);

const Action: React.FC<{icon: React.ReactNode; label: string; onClick: () => void}> = ({icon, label, onClick}) => (
  <button onClick={onClick} className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-slate-300 hover:border-cyan-500/30 hover:text-white flex items-center gap-2">{icon}{label}</button>
);
