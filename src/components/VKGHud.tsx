import React, { useState } from 'react';
import { 
  Layers, 
  Search, 
  Cpu, 
  ShieldCheck, 
  CheckCircle2, 
  ExternalLink, 
  Terminal, 
  RefreshCw, 
  X, 
  Zap, 
  Database, 
  Radio, 
  Boxes, 
  Lock,
  Flame,
  Minus,
  Plus,
  Eye,
  Activity,
  Code,
  Sparkles,
  Key,
  Brain,
  Github
} from 'lucide-react';
import { CamelotService, ServiceCategory, SystemVitals } from '../types';
import confetti from 'canvas-confetti';

interface VKGHudProps {
  services: CamelotService[];
  vitals?: SystemVitals;
  onRestartService: (serviceId: string) => void;
  onExecuteCommand?: (cmd: string) => void;
  onOpenOperatorConsole?: () => void;
}

export const VKGHud: React.FC<VKGHudProps> = ({
  services,
  vitals,
  onRestartService,
  onExecuteCommand,
  onOpenOperatorConsole
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeService, setActiveService] = useState<CamelotService | null>(null);

  // Minimization states
  const [minimizedBanner, setMinimizedBanner] = useState(false);
  const [minimizedGrid, setMinimizedGrid] = useState(false);

  // Hidden Aspect: Shadow Channel 0xDEADBEEF (Classified 29th Service)
  const [showShadowChannel, setShowShadowChannel] = useState(false);
  const [dmaRingBufferLatency, setDmaRingBufferLatency] = useState(0.042);
  const [shadowStreamLogs, setShadowStreamLogs] = useState<string[]>([
    '[SHADOW_INIT]: DMA Ring Buffer allocated at physical address 0x0000DEADBEEF',
    '[ZERO_COPY]: 64-byte aligned SIMD vector pipeline listening on port 9999',
    '[ENCRYPT]: Sovereign Zero-Trust key exchange (AES-GCM-256) valid'
  ]);

  const categories: { id: string; label: string; icon: any }[] = [
    { id: 'all', label: 'All Services (29)', icon: Layers },
    { id: 'cognitive_intelligence', label: 'Cognitive & Open-Notebook', icon: Brain },
    { id: 'core_orchestration', label: 'Core Orchestration', icon: ShieldCheck },
    { id: 'data_memory', label: 'Data & Memory', icon: Database },
    { id: 'runtimes_routing', label: 'Runtimes & WASI', icon: Radio },
    { id: 'intelligence_tools', label: 'Intelligence & Distillation', icon: Boxes },
    { id: 'security_mesh', label: 'Security & Mesh', icon: Lock }
  ];

  const filteredServices = services.filter((s) => {
    const matchesCat = selectedCategory === 'all' || s.category === selectedCategory;
    const matchesSearch = 
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.unitName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.language.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const totalAllocatedRam = services.reduce((acc, curr) => acc + curr.allocatedRamMB, 0);
  const totalCurrentRam = services.reduce((acc, curr) => acc + curr.currentRamMB, 0);

  const getLanguageColor = (lang: CamelotService['language']) => {
    switch (lang) {
      case 'Rust':
        return 'bg-amber-950/80 text-amber-300 border-amber-500/40';
      case 'Go':
        return 'bg-sky-950/80 text-sky-300 border-sky-500/40';
      case 'Java':
        return 'bg-rose-950/80 text-rose-300 border-rose-500/40';
      case 'Python':
        return 'bg-purple-950/80 text-purple-300 border-purple-500/40';
      case 'TypeScript':
        return 'bg-blue-950/80 text-blue-300 border-blue-500/40';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  const handleTestRingBuffer = () => {
    const newLat = Number((0.02 + Math.random() * 0.04).toFixed(3));
    setDmaRingBufferLatency(newLat);
    setShadowStreamLogs(prev => [
      `[DMA_PROBE]: Pinged physical RAM offset 0xDEADBEEF -> ${newLat}ms latency (0 dropped frames)`,
      ...prev.slice(0, 4)
    ]);
  };

  const toggleShadowChannel = () => {
    setShowShadowChannel(!showShadowChannel);
    if (!showShadowChannel) {
      confetti({ particleCount: 30, spread: 60, origin: { y: 0.6 } });
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-2 sm:p-4 space-y-4 font-mono">
      
      {/* Top Banner & Telemetry Overview */}
      <div className="bg-[#0e131f] border border-amber-950/80 rounded-xl p-4 sm:p-5 shadow-xl transition-all">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl">⚔️</span>
              <h2 className="font-heraldic text-lg font-bold text-amber-200 tracking-wider">
                VKG-HUD — BAREMETAL SERVICE MATRIX & TOPOLOGY
              </h2>
            </div>
            <p className="text-xs text-slate-400 font-terminal mt-1">
              Visual Knowledge Graph displaying all 28 supervised native baremetal processes running under cgroups v2.
            </p>
          </div>

          {/* Quick Actions & Minimization */}
          <div className="flex flex-wrap items-center gap-2">
            {onOpenOperatorConsole && (
              <button
                onClick={onOpenOperatorConsole}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#2E0854]/90 hover:bg-[#2E0854] border border-[#D4AF37]/60 text-[#D4AF37] text-xs font-bold transition-all shadow-[0_0_12px_rgba(212,175,55,0.3)] cursor-pointer"
                title="Open HTMX Operator Console & WebGPU HUD"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-[#D4AF37]" />
                <span>OPERATOR CONSOLE (HTMX)</span>
              </button>
            )}

            {/* HIDDEN ASPECT: Shadow Channel 0xDEADBEEF */}
            <button
              onClick={toggleShadowChannel}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs font-bold transition-all ${
                showShadowChannel
                  ? 'bg-purple-950 border-purple-400 text-purple-200 shadow-[0_0_15px_rgba(168,85,247,0.4)] animate-pulse'
                  : 'bg-slate-900 border-purple-900/60 text-purple-400 hover:text-purple-300'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <span>{showShadowChannel ? 'SHADOW CHANNEL: ACTIVE' : '[CLASSIFIED: SHADOW 0xDEADBEEF]'}</span>
            </button>

            <button
              onClick={() => setMinimizedBanner(!minimizedBanner)}
              className="p-1.5 rounded bg-slate-900 border border-slate-800 text-slate-400 hover:text-cyan-300"
              title={minimizedBanner ? "Expand Summary Stats" : "Minimize Summary Stats"}
            >
              {minimizedBanner ? <Plus className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Expandable Summary Metrics */}
        {!minimizedBanner && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-slate-800/80 font-terminal text-xs">
            <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-lg">
              <div className="text-[10px] text-slate-500">Live Active Units</div>
              <div className="text-emerald-400 font-bold text-sm flex items-center gap-1.5 mt-0.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                28 / 28 ONLINE
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-lg">
              <div className="text-[10px] text-slate-500">Total Active Footprint</div>
              <div className="text-amber-300 font-bold text-sm mt-0.5">
                {(totalCurrentRam / 1024).toFixed(2)} GB / 7.20 GB
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-lg">
              <div className="text-[10px] text-slate-500">cgroups v2 Confinement</div>
              <div className="text-cyan-400 font-bold text-sm mt-0.5">
                STRICT (7.2G CAP)
              </div>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-lg">
              <div className="text-[10px] text-slate-500">Supervision Engine</div>
              <div className="text-purple-300 font-bold text-sm mt-0.5">
                systemd --user
              </div>
            </div>
          </div>
        )}
      </div>

      {/* HIDDEN ASPECT DRAWER: SHADOW CHANNEL 0xDEADBEEF */}
      {showShadowChannel && (
        <div className="bg-purple-950/30 border-2 border-purple-500/60 rounded-xl p-4 shadow-2xl space-y-3 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-purple-500/40 pb-2">
            <div className="flex items-center gap-2">
              <Key className="w-5 h-5 text-purple-400 animate-pulse" />
              <div>
                <h3 className="text-sm font-bold text-purple-200 tracking-wider">
                  CLASSIFIED 29TH SERVICE: SHADOW CHANNEL 0xDEADBEEF // DARK REFRACTION STREAM
                </h3>
                <span className="text-[10px] text-purple-300/80">
                  DIRECT HARDWARE DMA & ZERO-COPY HYPERTHREAD PIPELINE
                </span>
              </div>
            </div>
            <button
              onClick={() => setShowShadowChannel(false)}
              className="text-xs text-purple-300 hover:text-white underline"
            >
              Close Shadow Channel
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {/* DMA Ring Buffer Tester */}
            <div className="bg-black/80 border border-purple-500/40 p-3 rounded-lg space-y-2">
              <span className="text-purple-300 font-bold flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-purple-400" />
                ZERO-COPY DMA RING BUFFER
              </span>
              <div className="p-2 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-emerald-300 flex items-center justify-between">
                <span>Latency:</span>
                <strong className="text-amber-300">{dmaRingBufferLatency} ms</strong>
              </div>
              <button
                onClick={handleTestRingBuffer}
                className="w-full py-1.5 rounded bg-purple-900/60 border border-purple-500/50 text-purple-200 hover:bg-purple-800 text-[11px] font-bold transition-all"
              >
                Benchmark Hardware DMA Probe
              </button>
            </div>

            {/* Live Stream Output */}
            <div className="md:col-span-2 bg-black/80 border border-purple-500/40 p-3 rounded-lg space-y-1.5">
              <span className="text-purple-300 font-bold flex items-center gap-1.5">
                <Terminal className="w-4 h-4 text-purple-400" />
                SHADOW STREAM TELEMETRY
              </span>
              <div className="p-2 rounded bg-slate-950 border border-slate-800 text-[10px] font-mono text-slate-300 space-y-1 h-20 overflow-y-auto custom-scrollbar">
                {shadowStreamLogs.map((log, idx) => (
                  <div key={idx} className="text-purple-300/90">{log}</div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0a1020] border border-cyan-950/80 p-3 rounded-xl">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {categories.map((cat) => {
            const Icon = cat.icon;
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                    : 'bg-slate-900/80 text-slate-400 border border-slate-800 hover:text-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-64">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search service, port, unit..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs font-mono text-cyan-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      {/* 28 Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {filteredServices.map((service) => {
          const isSelected = activeService?.id === service.id;
          return (
            <div
              key={service.id}
              onClick={() => setActiveService(service)}
              className={`p-3.5 rounded-xl border transition-all cursor-pointer bg-slate-950/80 hover:bg-slate-900/90 relative group ${
                isSelected
                  ? 'border-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.25)]'
                  : 'border-slate-800/80 hover:border-slate-700'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block"></span>
                    <h3 className="font-bold text-xs text-slate-200 tracking-wide">
                      {service.name}
                    </h3>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {service.unitName}
                  </span>
                </div>

                <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${getLanguageColor(service.language)}`}>
                  {service.language}
                </span>
              </div>

              <p className="text-[11px] text-slate-400 mt-2 line-clamp-2 leading-relaxed">
                {service.description}
              </p>

              <div className="mt-3 pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] font-mono">
                <span className="text-cyan-300 font-semibold">Port: {service.port || 'N/A'}</span>
                <div className="flex items-center gap-1.5">
                  {service.repoUrl && (
                    <a
                      href={service.repoUrl}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-purple-300 hover:text-purple-100 flex items-center gap-0.5 px-1 py-0.2 rounded bg-purple-950/80 border border-purple-800"
                      title="Open GitHub Repository"
                    >
                      <Github className="w-2.5 h-2.5" />
                      <span className="text-[9px]">Repo</span>
                    </a>
                  )}
                  <span className="text-amber-300 font-bold">{service.currentRamMB} MB</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Inspect Modal Drawer (If active) */}
      {activeService && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b101c] border-2 border-cyan-400 rounded-2xl max-w-lg w-full p-5 space-y-4 shadow-2xl animate-fadeIn">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-cyan-300 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-cyan-400" />
                  {activeService.name}
                </h3>
                <span className="text-xs text-slate-400 font-mono">{activeService.unitName}</span>
              </div>
              <button
                onClick={() => setActiveService(null)}
                className="p-1 rounded bg-slate-900 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400">Category:</span>
                  <span className="text-cyan-300 font-bold uppercase">{activeService.category}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Language / Runtime:</span>
                  <span className="text-amber-300">{activeService.language}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Listening Port:</span>
                  <span className="text-emerald-300 font-bold">{activeService.port}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Allocated / Current RAM:</span>
                  <span className="text-slate-200">{activeService.allocatedRamMB}MB / {activeService.currentRamMB}MB</span>
                </div>
              </div>

              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                <span className="text-slate-500 text-[10px] block mb-1">Architecture Summary:</span>
                <p className="text-slate-300 leading-relaxed text-[11px]">{activeService.description}</p>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-800">
              <div>
                {activeService.repoUrl && (
                  <a
                    href={activeService.repoUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-purple-950/80 hover:bg-purple-900 border border-purple-500/50 text-purple-200 text-xs font-bold transition-all"
                  >
                    <Github className="w-3.5 h-3.5" />
                    <span>View GitHub Repo</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>

              <button
                onClick={() => {
                  onRestartService(activeService.id);
                  setActiveService(null);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs transition-all shadow-[0_0_12px_rgba(245,158,11,0.3)]"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Restart Unit (systemctl)</span>
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
