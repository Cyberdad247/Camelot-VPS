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
  const [isMemcastleOpen, setIsMemcastleOpen] = useState(false);
  const [isTwinBrainsOpen, setIsTwinBrainsOpen] = useState(false);

  // Individual Card Minimization State
  const [minimizedCards, setMinimizedCards] = useState<Record<string, boolean>>({
    telemetry: false,
    process: false,
    ouroboros: false,
    logs: false,
    graphify: false,
    vfs: false,
    slabs: false,
    commands: false,
    centerTree: false
  });

  // Hidden Aspect: Sanctum of Excalibur & Z3 Kernel Theorem Inspector
  const [showSanctum, setShowSanctum] = useState(false);
  const [activeProofEquation, setActiveProofEquation] = useState<string>('∀x. (x ∈ VFS_Nodes → LeaseValid(x) ∧ MemBound(x) ≤ 7.2GB)');
  const [rawMemoryHex, setRawMemoryHex] = useState<string>('0x7FFF8A49B000: 43 41 4D 45 4C 4F 54 5F 4F 53 5F 56 4D 41 58 21');
  const [arthurBypassActive, setArthurBypassActive] = useState(false);

  const toggleCard = (cardKey: string) => {
    setMinimizedCards(prev => ({
      ...prev,
      [cardKey]: !prev[cardKey]
    }));
  };

  const handleToggleAllCards = () => {
    const allMin = Object.values(minimizedCards).every(Boolean);
    const newState = !allMin;
    setMinimizedCards({
      telemetry: newState,
      process: newState,
      ouroboros: newState,
      logs: newState,
      graphify: newState,
      vfs: newState,
      slabs: newState,
      commands: newState,
      centerTree: newState
    });
  };

  const handleInitWorldTree = () => {
    onExecuteCommand('systemctl restart vkg.slice');
  };

  const handleSyncAllEngines = () => {
    onExecuteCommand('sync-engines --all-cores --wal2-checkpoint');
  };

  const handleFlushContext = () => {
    onExecuteCommand('vfs-refractions --flush-stale-ast');
  };

  const handleOptimizeMemory = () => {
    onExecuteCommand('echo 3 > /proc/sys/vm/drop_caches && zramctl --recompress');
  };

  const handleRunDiagnostics = () => {
    onExecuteCommand('camelot-diag --z3-verify --strict');
  };

  const triggerSanctum = () => {
    setShowSanctum(!showSanctum);
    if (!showSanctum) {
      confetti({ particleCount: 35, spread: 60, origin: { y: 0.7 } });
    }
  };

  const countMin = Object.values(minimizedCards).filter(Boolean).length;

  return (
    <div className="w-full max-w-[1720px] mx-auto p-2 sm:p-4 space-y-4 font-mono">
      
      {/* Top Bento Toolbar with Minimization & Hidden Aspect */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#0a1020]/90 border border-cyan-950/80 px-4 py-2 rounded-xl text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
            <span className="font-bold text-cyan-300 tracking-wider uppercase">BENTO GRID ARCHITECTURE</span>
          </div>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400 text-[11px]">8 MODULAR REAL-TIME TELEMETRY PANELS</span>
          {countMin > 0 && (
            <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px]">
              {countMin} / 9 PANELS MINIMIZED
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Twin Brains / Open-Notebook Studio Launcher */}
          <button
            onClick={() => setIsTwinBrainsOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-purple-950/80 hover:bg-purple-900 text-purple-200 border border-purple-500/50 text-[11px] font-bold transition-all shadow-[0_0_12px_rgba(192,132,252,0.3)]"
          >
            <Brain className="w-3.5 h-3.5 text-purple-300" />
            <span>OPEN-NOTEBOOK STUDIO</span>
          </button>

          {/* Direct GitHub Link */}
          <a
            href="https://github.com/lfnovo/open-notebook.git"
            target="_blank"
            rel="noreferrer"
            className="hidden sm:flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700 text-[11px] transition-all"
            title="Open-Notebook GitHub Repository"
          >
            <Github className="w-3 h-3 text-purple-400" />
            <span>lfnovo/open-notebook</span>
            <ExternalLink className="w-2.5 h-2.5 text-slate-400" />
          </a>

          {/* Master Minimize / Expand All Cards */}
          <button
            onClick={handleToggleAllCards}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-900 hover:bg-slate-800 text-cyan-300 border border-cyan-500/30 text-[11px] transition-all"
          >
            {countMin >= 5 ? <Maximize2 className="w-3.5 h-3.5" /> : <Minimize2 className="w-3.5 h-3.5" />}
            <span>{countMin >= 5 ? 'EXPAND ALL PANELS' : 'MINIMIZE ALL PANELS'}</span>
          </button>

          {/* HIDDEN ASPECT: Sanctum of Excalibur & Z3 Kernel SMT Inspector */}
          <button
            onClick={triggerSanctum}
            className={`flex items-center gap-1.5 px-3 py-1 rounded border text-[11px] font-bold transition-all ${
              showSanctum
                ? 'bg-amber-950 border-amber-400 text-amber-200 shadow-[0_0_15px_rgba(245,158,11,0.5)] animate-pulse'
                : 'bg-slate-900 border-amber-900/60 text-amber-400/80 hover:text-amber-300'
            }`}
          >
            <Key className="w-3.5 h-3.5 text-amber-400" />
            <span>{showSanctum ? 'SANCTUM: OPEN' : '[HIDDEN SANCTUM OF EXCALIBUR]'}</span>
          </button>
        </div>
      </div>

      {/* HIDDEN ASPECT DRAWER: SANCTUM OF EXCALIBUR & Z3 THEOREMS */}
      {showSanctum && (
        <div className="bg-amber-950/20 border-2 border-amber-500/60 rounded-xl p-4 shadow-2xl space-y-3 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-amber-500/40 pb-2">
            <div className="flex items-center gap-2">
              <Crown className="w-5 h-5 text-amber-400 animate-pulse" />
              <div>
                <h3 className="text-sm font-bold text-amber-200 tracking-wider">
                  SANCTUM OF EXCALIBUR // Z3 SMT KERNEL THEOREM INSPECTOR
                </h3>
                <span className="text-[10px] text-amber-400/80">
                  CLASSIFIED LEVEL 5: DIRECT REGISTER BYPASS & FORMAL CONSTITUTIONAL PROOFS
                </span>
              </div>
            </div>
            <button
              onClick={() => setShowSanctum(false)}
              className="text-xs text-amber-300 hover:text-white underline"
            >
              Close Sanctum
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {/* Proof Equation Solver */}
            <div className="bg-black/70 border border-amber-500/30 p-3 rounded-lg space-y-2">
              <span className="text-amber-300 font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                ACTIVE Z3 FORMAL INVARIANT
              </span>
              <div className="p-2 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-emerald-300">
                {activeProofEquation}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveProofEquation('∀t. (t ∈ WAL2_Blocks → Hash(t) == Seal_R6)')}
                  className="px-2 py-1 rounded bg-amber-950/60 border border-amber-500/40 text-[10px] text-amber-200 hover:bg-amber-900"
                >
                  WAL2 Proof
                </button>
                <button
                  onClick={() => setActiveProofEquation('∀m. (m ∈ Memory_Slabs → Alignment(m) == 64_Bytes)')}
                  className="px-2 py-1 rounded bg-amber-950/60 border border-amber-500/40 text-[10px] text-amber-200 hover:bg-amber-900"
                >
                  Slab Proof
                </button>
                <button
                  onClick={() => setActiveProofEquation('∀l. (l ∈ Sentinel_Leases → Expire(l) ≤ 30_Seconds)')}
                  className="px-2 py-1 rounded bg-amber-950/60 border border-amber-500/40 text-[10px] text-amber-200 hover:bg-amber-900"
                >
                  Sentinel Proof
                </button>
              </div>
            </div>

            {/* Raw Kernel Hex Memory Dump */}
            <div className="bg-black/70 border border-cyan-500/30 p-3 rounded-lg space-y-2">
              <span className="text-cyan-300 font-bold flex items-center gap-1.5">
                <Code className="w-4 h-4 text-cyan-400" />
                RAW MEMORY REGISTER SLAB (HEX)
              </span>
              <div className="p-2 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-cyan-300 h-16 overflow-y-auto">
                {rawMemoryHex}
                <br />0x7FFF8A49B010: 53 45 4E 54 49 4E 45 4C 5F 4C 45 41 53 45 5F 31
                <br />0x7FFF8A49B020: 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00
              </div>
              <button
                onClick={() => {
                  setRawMemoryHex(`0x7FFF8A49B000: ${Array.from({length: 16}, () => Math.floor(Math.random()*256).toString(16).toUpperCase().padStart(2, '0')).join(' ')}`);
                }}
                className="w-full text-center px-2 py-1 rounded bg-cyan-950/60 border border-cyan-500/40 text-[10px] text-cyan-200 hover:bg-cyan-900"
              >
                Inspect Next Memory Segment
              </button>
            </div>

            {/* Arthur R5/R6 Cryptographic Authorization Override */}
            <div className="bg-black/70 border border-emerald-500/30 p-3 rounded-lg space-y-2">
              <span className="text-emerald-300 font-bold flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-400" />
                ARTHUR R5/R6 ZERO-TRUST SEAL
              </span>
              <p className="text-[10px] text-slate-300">
                Seal Status: <strong className="text-emerald-400">{arthurBypassActive ? 'OVERRIDE PROTOCOL ENGAGED' : 'UNBROKEN & VERIFIED'}</strong>
              </p>
              <button
                onClick={() => {
                  setArthurBypassActive(!arthurBypassActive);
                  onExecuteCommand(arthurBypassActive ? 'seal-invariants --restore' : 'seal-invariants --debug-bypass');
                }}
                className={`w-full text-center px-2.5 py-1.5 rounded text-[10px] font-bold border transition-all ${
                  arthurBypassActive 
                    ? 'bg-rose-950 border-rose-500 text-rose-200' 
                    : 'bg-emerald-950/80 border-emerald-500 text-emerald-200 hover:bg-emerald-900'
                }`}
              >
                {arthurBypassActive ? 'RESTORE CONSTITUTIONAL LOCK' : 'ENGAGE ZERO-TRUST AUDIT BYPASS'}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 3-Column Bento Grid Master Architecture */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start hud-perspective-field">
        
        {/* ================= LEFT HUD COLUMN (Span 3) ================= */}
        <div className="lg:col-span-3 flex flex-col gap-4">
          
          {/* Card 1: System Telemetry (8GB RAM // Real-time) */}
          <div className="relative border border-cyan-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-cyan-950/80 text-[10px]">
              <span className="font-bold text-cyan-400">TELEMETRY</span>
              <button
                onClick={() => toggleCard('telemetry')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.telemetry ? "Expand" : "Minimize"}
              >
                {minimizedCards.telemetry ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.telemetry ? (
              <div className="p-1">
                <SystemTelemetry 
                  vitals={vitals} 
                  onOpenDetails={() => onNavigateTab('scarcity')} 
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>8GB RAM Confinement</span>
                <span className="text-amber-300 font-bold">{Math.round((vitals.usedRamMB / vitals.scarcityCapMB)*100)}%</span>
              </div>
            )}
          </div>

          {/* Card 2: Process Matrix */}
          <div className="relative border border-cyan-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-cyan-950/80 text-[10px]">
              <span className="font-bold text-cyan-400">PROCESS MATRIX (28 UNITS)</span>
              <button
                onClick={() => toggleCard('process')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.process ? "Expand" : "Minimize"}
              >
                {minimizedCards.process ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.process ? (
              <div className="p-1">
                <ProcessMatrix 
                  services={services} 
                  onRestartService={onRestartService}
                  onInspectService={(svc) => onNavigateTab('vkg')}
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>cgroups v2 native</span>
                <span className="text-emerald-400 font-bold">28 ACTIVE</span>
              </div>
            )}
          </div>

          {/* Card 3: Ouroboros SSM State Transitions */}
          <div className="relative border border-amber-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-amber-950/80 text-[10px]">
              <span className="font-bold text-amber-400">OUROBOROS SSM</span>
              <button
                onClick={() => toggleCard('ouroboros')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-300"
                title={minimizedCards.ouroboros ? "Expand" : "Minimize"}
              >
                {minimizedCards.ouroboros ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.ouroboros ? (
              <div className="p-1">
                <OuroborosMatrix 
                  onOpenDetails={() => setIsTwinBrainsOpen(true)}
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>1.58-Bit Ternary</span>
                <span className="text-amber-300 font-bold">O(1) LOOP</span>
              </div>
            )}
          </div>

          {/* Card 4: System Log */}
          <div className="relative border border-cyan-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-cyan-950/80 text-[10px]">
              <span className="font-bold text-cyan-400">SYSTEM LOG</span>
              <button
                onClick={() => toggleCard('logs')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.logs ? "Expand" : "Minimize"}
              >
                {minimizedCards.logs ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.logs ? (
              <div className="p-1">
                <SystemLogPanel 
                  logs={logs} 
                  onExecuteCommand={onExecuteCommand}
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>Live Kernel Events</span>
                <span className="text-cyan-300 font-bold">{logs.length} LOGS</span>
              </div>
            )}
          </div>

        </div>

        {/* ================= CENTER ARENA: THE SOVEREIGN WORLD TREE (Span 6) ================= */}
        <div className="lg:col-span-6 flex flex-col gap-4">
          <div className="relative border border-cyan-900/60 rounded-2xl bg-slate-950/90 overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-4 py-2 bg-slate-900/90 border-b border-cyan-950/80 text-xs">
              <span className="font-bold text-amber-200">THE SOVEREIGN WORLD TREE (AXIS MUNDI)</span>
              <button
                onClick={() => toggleCard('centerTree')}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.centerTree ? "Expand tree visual" : "Minimize tree visual"}
              >
                {minimizedCards.centerTree ? <Plus className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
              </button>
            </div>
            {!minimizedCards.centerTree ? (
              <WorldTreeVisual
                onOpenMemcastle={() => setIsMemcastleOpen(true)}
                onOpenTwinBrains={() => setIsTwinBrainsOpen(true)}
                onOpenOuroboros={() => setIsTwinBrainsOpen(true)}
                onOpenViking={() => onNavigateTab('laws')}
                onOpenGraphify={() => onNavigateTab('vkg')}
              />
            ) : (
              <div className="p-6 text-center text-xs text-slate-400 space-y-2">
                <p>World Tree Visual Minimized for Compact Performance View</p>
                <button
                  onClick={() => toggleCard('centerTree')}
                  className="px-3 py-1 rounded bg-cyan-950 border border-cyan-500 text-cyan-300 text-xs"
                >
                  Restore 2D/3D Architecture
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ================= RIGHT HUD COLUMN (Span 3) ================= */}
        <div className="lg:col-span-3 flex flex-col gap-4">
          
          {/* Card 5: Graphify 3D->2D Depth Spatial Network */}
          <div className="relative border border-cyan-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-cyan-950/80 text-[10px]">
              <span className="font-bold text-cyan-400">GRAPHIFY NETWORK</span>
              <button
                onClick={() => toggleCard('graphify')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.graphify ? "Expand" : "Minimize"}
              >
                {minimizedCards.graphify ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.graphify ? (
              <div className="p-1">
                <GraphifyCanvas 
                  onExpandModal={() => onNavigateTab('vkg')}
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>Spatial Topology</span>
                <span className="text-cyan-300 font-bold">10,428 NODES</span>
              </div>
            )}
          </div>

          {/* Card 6: VFS Refractions // Open Viking Protocol */}
          <div className="relative border border-cyan-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-cyan-950/80 text-[10px]">
              <span className="font-bold text-cyan-400">VFS REFRACTIONS (OPEN VIKING)</span>
              <button
                onClick={() => toggleCard('vfs')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.vfs ? "Expand" : "Minimize"}
              >
                {minimizedCards.vfs ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.vfs ? (
              <div className="p-1">
                <VikingRefractions 
                  onOpenDetails={() => onNavigateTab('laws')}
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>Direct Memory Access</span>
                <span className="text-emerald-400 font-bold">5 STREAMS OK</span>
              </div>
            )}
          </div>

          {/* Card 7: IPC & Memory Slab Sync */}
          <div className="relative border border-cyan-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-cyan-950/80 text-[10px]">
              <span className="font-bold text-cyan-400">IPC & MEMORY SLABS</span>
              <button
                onClick={() => toggleCard('slabs')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.slabs ? "Expand" : "Minimize"}
              >
                {minimizedCards.slabs ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.slabs ? (
              <div className="p-1">
                <IpcMemorySlabs 
                  onOpenDetails={() => setIsMemcastleOpen(true)}
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>32 Slab Bins</span>
                <span className="text-emerald-400 font-bold">0.23ms LATENCY</span>
              </div>
            )}
          </div>

          {/* Card 8: System Commands */}
          <div className="relative border border-cyan-950/80 rounded-xl bg-slate-950/80 overflow-hidden shadow-lg transition-all">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900/90 border-b border-cyan-950/80 text-[10px]">
              <span className="font-bold text-cyan-400">SYSTEM COMMANDS</span>
              <button
                onClick={() => toggleCard('commands')}
                className="p-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedCards.commands ? "Expand" : "Minimize"}
              >
                {minimizedCards.commands ? <Plus className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
              </button>
            </div>
            {!minimizedCards.commands ? (
              <div className="p-1">
                <SystemCommandsPanel
                  onInitWorldTree={handleInitWorldTree}
                  onSyncAllEngines={handleSyncAllEngines}
                  onFlushContext={handleFlushContext}
                  onOptimizeMemory={handleOptimizeMemory}
                  onRunDiagnostics={handleRunDiagnostics}
                  onOpenBootstrapScript={onOpenBootstrapScript}
                  onOpenSovereignLaws={() => onNavigateTab('laws')}
                />
              </div>
            ) : (
              <div className="p-2 text-[10px] text-slate-400 flex items-center justify-between">
                <span>Root / WASI</span>
                <span className="text-cyan-300 font-bold">6 COMMANDS</span>
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Exploration Modals */}
      <MemcastleModal 
        isOpen={isMemcastleOpen} 
        onClose={() => setIsMemcastleOpen(false)} 
      />

      <TwinBrainsModal
        isOpen={isTwinBrainsOpen}
        onClose={() => setIsTwinBrainsOpen(false)}
      />

    </div>
  );
};
