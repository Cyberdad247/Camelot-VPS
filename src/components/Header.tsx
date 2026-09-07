import React, { useState } from 'react';
import { 
  ShieldCheck, 
  Terminal, 
  Cpu, 
  Activity, 
  Copy, 
  Play, 
  Send, 
  CheckCircle2, 
  Server, 
  Layers, 
  Lock, 
  ScrollText,
  FileCode,
  Flame,
  Sparkles,
  TreeDeciduous,
  Radio,
  Minus,
  Plus,
  Crown,
  Eye,
  Key,
  HardDrive,
  BookOpen
} from 'lucide-react';
import { SystemVitals } from '../types';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  vitals: SystemVitals;
  onGoLive: () => void;
  onDispatch: () => void;
  onRunMission: () => void;
  copied: boolean;
  onCopyScript: () => void;
  isTabMinimized?: boolean;
  onToggleTabMinimize?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  vitals,
  onGoLive,
  onDispatch,
  onRunMission,
  copied,
  onCopyScript,
  isTabMinimized = false,
  onToggleTabMinimize
}) => {
  const [compactHeader, setCompactHeader] = useState(false);
  const ramPercent = Math.round((vitals.usedRamMB / vitals.scarcityCapMB) * 100);

  const tabs = [
    { id: 'deck', label: 'World Tree UI (2D ➔ 3D Continuity)', icon: TreeDeciduous },
    { id: 'vps_init', label: 'VPS Hub Initiation (vps3573819)', icon: Server },
    { id: 'docs', label: 'Docs Forge (νKG-Crystal)', icon: BookOpen },
    { id: 'operator', label: 'HTMX Console & WebGPU HUD', icon: ShieldCheck },
    { id: 'bento', label: 'Bento Grid Hub', icon: Layers },
    { id: 'terminal', label: 'Baremetal Terminal', icon: Terminal },
    { id: 'vkg', label: 'VKG-HUD Services', icon: HardDrive },
    { id: 'mission', label: 'Mission Arena', icon: Flame },
    { id: 'laws', label: 'Sovereign Laws & Ledger', icon: Lock },
    { id: 'scarcity', label: '8GB Scarcity Protocol', icon: Cpu },
    { id: 'script', label: 'Master Bootstrap Script', icon: FileCode }
  ];

  return (
    <header className="border-b border-cyan-900/50 bg-[#060a14]/95 backdrop-blur-xl sticky top-0 z-40">
      {/* Top Banner / System Ribbon */}
      {!compactHeader && (
        <div className="px-4 py-1.5 bg-gradient-to-r from-[#050505] via-[#0a1224] to-[#2E0854]/70 border-b border-[#D4AF37]/30 flex flex-wrap items-center justify-between text-xs gap-3 font-mono">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#2E0854]/80 border border-[#D4AF37]/50 text-[#D4AF37] shadow-[0_0_12px_rgba(212,175,55,0.3)]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#D4AF37]" />
              <span className="font-bold text-[10px] uppercase tracking-wider">Ω_EXCALIBUR_V1000 // AEGIS SHIELD</span>
            </div>
            <div className="hidden sm:flex items-center gap-2 text-slate-300 text-[11px]">
              <span className="text-[#D4AF37] font-bold">ANYA_IS_THE_GATE</span>
              <span className="text-slate-600">|</span>
              <span>HOST: <span className="text-cyan-200 font-semibold">{vitals.targetHost}</span></span>
              <span className="text-slate-600">|</span>
              <span className="text-purple-300">BitNet 1.58b Ternary Plane</span>
              <span className="text-slate-600">|</span>
              <span className="text-amber-400">8GB Strict Edge Boundary</span>
            </div>
          </div>

          {/* Quick Directives & Actions */}
          <div className="flex items-center gap-2">
            <button
              id="btn-quick-golive"
              onClick={onGoLive}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs transition-all shadow-[0_0_12px_rgba(245,158,11,0.35)] active:scale-95"
              title="Execute //GO_LIVE deployment"
            >
              <Play className="w-3.5 h-3.5 fill-black" />
              <span>//GO_LIVE</span>
            </button>

            <button
              id="btn-quick-dispatch"
              onClick={onDispatch}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-cyan-300 border border-cyan-500/40 text-xs transition-all active:scale-95"
              title="Dispatch directives to engineering"
            >
              <Send className="w-3.5 h-3.5 text-cyan-400" />
              <span>//DISPATCH</span>
            </button>

            <button
              id="btn-quick-mission"
              onClick={onRunMission}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-purple-950/80 hover:bg-purple-900 text-purple-300 border border-purple-500/40 text-xs transition-all active:scale-95"
              title="Dispatch sovereign knight agent mission"
            >
              <Flame className="w-3.5 h-3.5 text-amber-400" />
              <span>//RUN_MISSION</span>
            </button>

            <button
              id="btn-quick-copy"
              onClick={onCopyScript}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs transition-all"
              title="Copy Raw Master Bootstrap Script"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-300 font-bold">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-slate-400" />
                  <span>Copy Script</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Main Identity & Status Header */}
      <div className="px-4 py-2.5 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        
        {/* Left: Glowing World Tree Logo & Title */}
        <div className="flex items-center gap-3.5">
          <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-[#0c1e38] via-[#091428] to-[#120f26] border-2 border-cyan-400/60 flex items-center justify-center text-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.35)]">
            <TreeDeciduous className="w-5 h-5 text-amber-300 animate-pulse" />
            <div className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping"></div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-heraldic text-lg sm:text-xl font-bold tracking-wider text-white flex items-center gap-2">
                Camelot-OS <span className="text-cyan-400 font-sans font-semibold">World Tree</span>
              </h1>
              <span className="px-2 py-0.5 text-[9px] uppercase font-mono font-bold tracking-wider rounded bg-cyan-950/90 text-cyan-300 border border-cyan-500/40">
                vMAX OMEGA TITAN
              </span>
            </div>
            <p className="text-[10px] text-amber-400 font-mono tracking-widest font-semibold flex items-center gap-2 uppercase">
              <span>THE SOVEREIGN CONTEXT ENGINE</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-400 font-normal">NO DOCKER // NATIVE PROCESSES</span>
            </p>
          </div>
        </div>

        {/* Right: Status & Compact Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Glowing Emerald Box: SYSTEM STATUS: NOMINAL */}
          <div className="px-3 py-1.5 rounded-xl bg-emerald-950/80 border-2 border-emerald-500/60 shadow-[0_0_25px_rgba(16,185,129,0.35)] flex items-center gap-2 font-mono">
            <div className="relative flex items-center justify-center">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span className="absolute w-3.5 h-3.5 rounded-full bg-emerald-400/40 animate-ping"></span>
            </div>
            <div>
              <div className="text-[8px] text-emerald-400 font-bold uppercase tracking-widest leading-none">
                GIDEON GATE CONVERGENCE
              </div>
              <div className="text-[11px] font-bold text-white tracking-wide">
                STATUS: <span className="text-emerald-300">NOMINAL</span>
              </div>
            </div>
          </div>

          {/* Scarcity RAM Pill */}
          <div className="bg-[#050b17] border border-cyan-900/60 rounded-xl px-3 py-1.5 flex items-center gap-2.5 font-mono text-xs">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <div>
              <div className="flex items-center justify-between gap-2 text-[10px]">
                <span className="text-slate-400">8GB RAM</span>
                <span className="font-bold text-cyan-300">{ramPercent}% ({((vitals.usedRamMB) / 1024).toFixed(1)}G)</span>
              </div>
              <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden mt-1">
                <div 
                  className="h-full bg-gradient-to-r from-cyan-400 to-amber-400 rounded-full"
                  style={{ width: `${ramPercent}%` }}
                />
              </div>
            </div>
          </div>

          {/* Toggle Header Ribbons */}
          <button
            onClick={() => setCompactHeader(!compactHeader)}
            className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-cyan-300 transition-all text-[11px]"
            title={compactHeader ? "Expand Header Ribbon" : "Compact Header"}
          >
            {compactHeader ? <Plus className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
          </button>
        </div>

      </div>

      {/* Navigation Tabs */}
      <div className="px-4 flex items-center justify-between overflow-x-auto border-t border-cyan-950/80 bg-[#040812]">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-mono font-medium whitespace-nowrap transition-all border-b-2 ${
                  isActive
                    ? 'border-cyan-400 text-cyan-300 bg-cyan-950/40 shadow-[inset_0_-8px_12px_rgba(34,211,238,0.08)]'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {onToggleTabMinimize && (
          <button
            onClick={onToggleTabMinimize}
            className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono text-slate-400 hover:text-cyan-300 bg-slate-900/70 border border-slate-800 rounded my-1 shrink-0 ml-2"
            title="Minimize active view"
          >
            {isTabMinimized ? <Plus className="w-3 h-3 text-cyan-400" /> : <Minus className="w-3 h-3 text-cyan-400" />}
            <span>{isTabMinimized ? 'RESTORE VIEW' : 'MINIMIZE VIEW'}</span>
          </button>
        )}
      </div>
    </header>
  );
};
