import React, { useState, useEffect, useRef } from 'react';
import { 
  TreeDeciduous, 
  HardDrive, 
  BookOpen, 
  Crown, 
  ShieldCheck, 
  Sparkles, 
  Terminal, 
  Layers, 
  Sliders, 
  Cpu, 
  Database, 
  Network, 
  Lock, 
  Unlock, 
  Eye, 
  Folder, 
  FileText, 
  ChevronRight, 
  ChevronDown, 
  Play, 
  RefreshCw, 
  ArrowDown, 
  ArrowUp, 
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Radio,
  SlidersHorizontal,
  Anchor,
  Compass,
  Zap,
  Volume2,
  VolumeX
} from 'lucide-react';
import { audioEngine } from '../utils/audioEngine';

interface SovereignScrollingProps {
  onNavigateTab?: (tab: string) => void;
  onExecuteCommand?: (cmd: string) => void;
}

// Knights & Mages of the Kingdom
interface MageKnight {
  id: string;
  name: string;
  title: string;
  engine: string;
  sge: string;
  vram: string;
  quote: string;
  directives: string[];
  color: string;
  icon: string;
}

const COUNCIL_MAGES: MageKnight[] = [
  {
    id: 'lady_mnemosyne',
    name: 'Lady Mnemosyne',
    title: 'The Memory Keeper',
    engine: 'Redis MemCastle & Vector Nodes',
    sge: '99.8%',
    vram: '320 MB',
    quote: 'All things remembered. All things connected. Memory is a bridge, not a vault.',
    directives: ['Recall', 'Synthesize', 'Contextualize', 'Protect'],
    color: '#38BDF8',
    icon: '💎'
  },
  {
    id: 'sir_codex',
    name: 'Sir Codex',
    title: 'The Compiler',
    engine: 'OpenAI-Codex / WASM32 Zero-Copy',
    sge: '99.4%',
    vram: '280 MB',
    quote: 'Deterministic logic without allocation is the purest form of digital prayer.',
    directives: ['Compile', 'Optimize', 'Verify Bytecode', 'Enforce Bounds'],
    color: '#D4AF37',
    icon: '⚡'
  },
  {
    id: 'sir_loren',
    name: 'Sir Loren',
    title: 'The Researcher',
    engine: 'Deep Research Agent // Multi-Corpus',
    sge: '98.9%',
    vram: '410 MB',
    quote: 'Truth hides in the high-dimensional manifolds of cross-repository synthesis.',
    directives: ['Index', 'Correlate', 'Synthesize', 'Filter'],
    color: '#A855F7',
    icon: '📜'
  },
  {
    id: 'sir_prompt',
    name: 'Sir Prompt',
    title: 'The Orchestrator',
    engine: 'DAG Dispatcher & Task Sequencer',
    sge: '99.7%',
    vram: '190 MB',
    quote: 'Intention declared becomes topological order materialized.',
    directives: ['Sequence', 'Dispatch', 'Observe', 'Converge'],
    color: '#F59E0B',
    icon: '🎼'
  },
  {
    id: 'sir_aegis',
    name: 'Sir Aegis',
    title: 'The Guardian',
    engine: 'AgentArmor PDG Sentry & Zero-Trust',
    sge: '100%',
    vram: '150 MB',
    quote: 'None shall compromise the sovereign boundaries of the kingdom.',
    directives: ['Shield', 'Attest', 'Isolate', 'Neutralize'],
    color: '#10B981',
    icon: '🛡️'
  },
  {
    id: 'sir_calculus',
    name: 'Sir Calculus',
    title: 'The Analyst',
    engine: 'Z3 SMT Invariant Theorem Prover',
    sge: '99.9%',
    vram: '220 MB',
    quote: 'If an invariant cannot be proved mathematically, it does not exist.',
    directives: ['Prove', 'Constrain', 'Formulate', 'Certify'],
    color: '#EC4899',
    icon: '📐'
  },
  {
    id: 'sir_lumen',
    name: 'Sir Lumen',
    title: 'The Visionary',
    engine: 'Kinetic 3D Frame Scroll Matrix',
    sge: '99.1%',
    vram: '360 MB',
    quote: 'Form and light are the visual syntax of Sovereign Intelligence.',
    directives: ['Illuminate', 'Project', 'Refract', 'Harmonize'],
    color: '#06B6D4',
    icon: '✨'
  },
  {
    id: 'sir_pragmata',
    name: 'Sir Pragmata',
    title: 'The Executor',
    engine: 'Termux ARM64 / Bare-Metal Actuator',
    sge: '99.5%',
    vram: '180 MB',
    quote: 'Abstract models without bare-metal execution are mere ghosts.',
    directives: ['Actuate', 'Bind', 'Deploy', 'Monitor'],
    color: '#84CC16',
    icon: '⚙️'
  },
  {
    id: 'sir_harmonia',
    name: 'Sir Harmonia',
    title: 'The Alignment',
    engine: 'Constitutional Invariant Verifier',
    sge: '99.6%',
    vram: '210 MB',
    quote: 'Safety and power are not rivals, but twin pillars of the realm.',
    directives: ['Align', 'Balance', 'Sanitize', 'Validate'],
    color: '#6366F1',
    icon: '⚖️'
  },
  {
    id: 'sir_nexus',
    name: 'Sir Nexus',
    title: 'The Connector',
    engine: 'VFS Data Bus & Memory Slab Ring',
    sge: '99.8%',
    vram: '300 MB',
    quote: 'Latency is friction; zero-copy slabs are frictionless eternity.',
    directives: ['Bridge', 'Route', 'Buffer', 'Synchronize'],
    color: '#14B8A6',
    icon: '🌐'
  }
];

// Architecture Layers L0-L7
const ARCH_LAYERS = [
  { id: 'L7', name: 'APPLICATION LAYER', desc: 'Agent Interfaces • IDE • Chat • Canvas', color: '#F59E0B' },
  { id: 'L6', name: 'AGENT ORCHESTRATION', desc: 'Multi-Agent Runtime • Tool Use • Planning', color: '#EC4899' },
  { id: 'L5', name: 'MEMORY & KNOWLEDGE', desc: 'Redis • Vector DB • Mem Castle', color: '#A855F7' },
  { id: 'L4', name: 'REASONING LAYER', desc: 'LLM Core • Inference • RAG', color: '#EF4444' },
  { id: 'L3', name: 'TOOL EXECUTION', desc: 'Sandbox • MCP • System Tools', color: '#EAB308' },
  { id: 'L2', name: 'SECURITY & ISOLATION', desc: 'AgentArmor • Policy • Heimdall', color: '#3B82F6' },
  { id: 'L1', name: 'SYSTEM KERNEL', desc: 'OS • Containers • Hypervisor', color: '#F43F5E' },
  { id: 'L0', name: 'PHYSICAL HARDWARE', desc: 'CPU • GPU • Storage • Network', color: '#64748B' }
];

export const SovereignWorldTreeScrollingExperience: React.FC<SovereignScrollingProps> = ({
  onNavigateTab,
  onExecuteCommand
}) => {
  // Navigation & Scroll Tracking
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState<number>(0);
  const [activeSection, setActiveSection] = useState<'full_tree' | 'vfs_roots' | 'twin_brains' | 'throne_room'>('full_tree');
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);

  // Section 1 State: Full Tree (Pictures 1 & 2)
  const [activeTreePicture, setActiveTreePicture] = useState<'pic1_hud' | 'pic2_camelot'>('pic2_camelot');
  const [morphBlend, setMorphBlend] = useState<number>(0.85);

  // Section 2 State: VFS Roots & VPS File Explorer (Pictures 3, 4, 5)
  const [activeVfsPicture, setActiveVfsPicture] = useState<'pic3_reflective' | 'pic4_hud_roots' | 'pic5_zoomed_roots'>('pic4_hud_roots');
  const [selectedVfsPath, setSelectedVfsPath] = useState<string>('/vfs/mempalace/embeddings_768d.bin');
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    '/vfs': true,
    '/vfs/mempalace': true,
    '/vfs/refractions': false,
    '/.agent': false
  });
  const [vfsLog, setVfsLog] = useState<string>('VFS ROOT MOUNT READY: NVMe0n1 7.1 GB/s READ, NVMe1n1 6.8 GB/s WRITE');

  // Section 3 State: Open Notebook & Twin Brains (Picture 6)
  const [privateVsCloudBalance, setPrivateVsCloudBalance] = useState<number>(35); // 0 = 100% private, 100 = 100% cloud
  const [redisEvictionPolicy, setRedisEvictionPolicy] = useState<'LRU' | 'LFU' | 'SOVEREIGN_PINNED'>('SOVEREIGN_PINNED');
  const [redisSlabTtl, setRedisSlabTtl] = useState<number>(3600);
  const [notebookPrompt, setNotebookPrompt] = useState<string>('Synthesize zero-copy invariant between Sir Codex WASM filter and Lady Mnemosyne vector slabs.');
  const [notebookOutput, setNotebookOutput] = useState<string | null>(null);
  const [isSynthesizing, setIsSynthesizing] = useState<boolean>(false);

  // Section 4 State: Throne Room & Council of Mages (Picture 7)
  const [selectedMage, setSelectedMage] = useState<MageKnight>(COUNCIL_MAGES[0]);
  const [throneDecree, setThroneDecree] = useState<string>('');
  const [decreeResponse, setDecreeResponse] = useState<string | null>(null);
  const [gateStatus, setGateStatus] = useState<Record<string, boolean>>({
    identity: true,
    integrity: true,
    intent: true,
    payload: true,
    access: true
  });

  // Track scroll position inside container
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const totalScroll = scrollHeight - clientHeight;
    const progress = totalScroll > 0 ? scrollTop / totalScroll : 0;
    setScrollProgress(progress);

    if (progress < 0.25) {
      setActiveSection('full_tree');
    } else if (progress < 0.58) {
      setActiveSection('vfs_roots');
    } else if (progress < 0.82) {
      setActiveSection('twin_brains');
    } else {
      setActiveSection('throne_room');
    }
  };

  const scrollToSection = (sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
      if (soundEnabled) audioEngine.playCommandExecute();
    }
  };

  const toggleFolder = (folder: string) => {
    setExpandedFolders(prev => ({ ...prev, [folder]: !prev[folder] }));
    if (soundEnabled) audioEngine.playClick();
  };

  const handleSelectFile = (path: string) => {
    setSelectedVfsPath(path);
    setVfsLog(`Hex slab address mapped: 0x7F${(Math.random() * 0xFFFFFF << 0).toString(16).toUpperCase()} • Latency 0.82ms`);
    if (soundEnabled) audioEngine.playClick();
  };

  const handleRunNotebookSynthesis = () => {
    setIsSynthesizing(true);
    if (soundEnabled) audioEngine.playBrainSync();
    setTimeout(() => {
      const privatePct = 100 - privateVsCloudBalance;
      const cloudPct = privateVsCloudBalance;
      setNotebookOutput(
        `[TWIN-BRAIN SYNTHESIS COMPLETED]\n` +
        `• Local Open Core (${privatePct}%): Pinned 48KB zero-copy memory slab via WASI syscall.\n` +
        `• Cloud LM Wrapper (${cloudPct}%): High-order invariant verified with Gemini 3.8 Pro.\n` +
        `• MemCastle Slab: Slot 0x3F2 committed to Redis cache with TTL ${redisSlabTtl}s under ${redisEvictionPolicy}.\n` +
        `• Status: 100% Truthful, Proof Hash: 0x9AF012BC78D24E`
      );
      setIsSynthesizing(false);
      if (soundEnabled) audioEngine.playCommandExecute();
    }, 700);
  };

  const handleIssueDecree = (customDecree?: string) => {
    const decree = customDecree || throneDecree;
    if (!decree.trim()) return;

    if (soundEnabled) audioEngine.playCommandExecute();
    setDecreeResponse(
      `⚜️ HEIMDALL: ROYAL DECREE ACCEPTED & VALIDATED BY AGENTARMOR.\n` +
      `"Decree: '${decree}' has been relayed through Bifrost."\n` +
      `• Sir Prompt has scheduled task across kingdom dag.\n` +
      `• ${selectedMage.name} attests: "${selectedMage.quote}"\n` +
      `• All 10 Knights of the Council are aligned.`
    );
    setThroneDecree('');
    if (onExecuteCommand) {
      onExecuteCommand(`camelot-decree "${decree}"`);
    }
  };

  return (
    <div 
      id="sovereign-worldtree-scroller" 
      ref={containerRef}
      onScroll={handleScroll}
      className="relative w-full h-[calc(100vh-4rem)] overflow-y-auto bg-[#050505] text-slate-100 font-sans selection:bg-[#D4AF37]/30 selection:text-[#D4AF37]"
      style={{ scrollBehavior: 'smooth' }}
    >
      {/* FIXED TOP HUD NAVIGATION BAR */}
      <header className="sticky top-0 z-50 w-full backdrop-blur-xl bg-[#050505]/90 border-b border-[#D4AF37]/30 px-4 py-2.5 shadow-2xl flex flex-wrap items-center justify-between gap-4">
        {/* Brand & Identity */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#2E0854] to-[#050505] border border-[#D4AF37] flex items-center justify-center shadow-lg shadow-[#D4AF37]/20">
            <TreeDeciduous className="w-5 h-5 text-[#D4AF37]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-xs tracking-widest text-[#D4AF37] uppercase">Ω_EXCALIBUR_V1000</span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-[#2E0854] text-purple-200 border border-purple-500/40">
                GCMN_vMAX
              </span>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                ANYA IS THE GATE
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono tracking-tight">
              Aesthetic: Kinetic Obsidian (#050505) ⊕ Luxora Gold (#D4AF37) ⊕ Royal Purple (#2E0854)
            </p>
          </div>
        </div>

        {/* 4 Strata Journey Quick Links */}
        <nav className="flex items-center gap-1 bg-black/60 p-1 rounded-xl border border-white/10 text-xs">
          <button
            id="nav-btn-full-tree"
            onClick={() => scrollToSection('stratum-full-tree')}
            className={`px-3 py-1.5 rounded-lg font-mono flex items-center gap-1.5 transition-all ${
              activeSection === 'full_tree'
                ? 'bg-[#D4AF37] text-black font-bold shadow-md shadow-[#D4AF37]/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <TreeDeciduous className="w-3.5 h-3.5" />
            <span>1-2. Full Tree</span>
          </button>

          <button
            id="nav-btn-vfs-roots"
            onClick={() => scrollToSection('stratum-vfs-roots')}
            className={`px-3 py-1.5 rounded-lg font-mono flex items-center gap-1.5 transition-all ${
              activeSection === 'vfs_roots'
                ? 'bg-emerald-500 text-black font-bold shadow-md shadow-emerald-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>3-5. VFS Roots</span>
          </button>

          <button
            id="nav-btn-twin-brains"
            onClick={() => scrollToSection('stratum-twin-brains')}
            className={`px-3 py-1.5 rounded-lg font-mono flex items-center gap-1.5 transition-all ${
              activeSection === 'twin_brains'
                ? 'bg-purple-500 text-white font-bold shadow-md shadow-purple-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>6. Open Notebook</span>
          </button>

          <button
            id="nav-btn-throne-room"
            onClick={() => scrollToSection('stratum-throne-room')}
            className={`px-3 py-1.5 rounded-lg font-mono flex items-center gap-1.5 transition-all ${
              activeSection === 'throne_room'
                ? 'bg-[#D4AF37] text-black font-bold shadow-md shadow-[#D4AF37]/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <Crown className="w-3.5 h-3.5" />
            <span>7. Throne Room</span>
          </button>
        </nav>

        {/* Telemetry & Audio Toggle */}
        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 font-mono text-[11px] text-slate-300">
            <span className="text-amber-400">RAM: 6.24GB / 8GB</span>
            <span className="text-slate-600">|</span>
            <span className="text-cyan-400">VRAM: &lt;50MB</span>
            <span className="text-slate-600">|</span>
            <span className="text-purple-400">Z3: 44/44 SAT</span>
          </div>

          <button
            id="audio-toggle-btn"
            onClick={() => setSoundEnabled(!soundEnabled)}
            className="p-1.5 rounded-lg border border-white/10 hover:border-[#D4AF37]/50 text-slate-400 hover:text-[#D4AF37] transition-all"
            title={soundEnabled ? 'Mute Royal Audio Engine' : 'Unmute Royal Audio Engine'}
          >
            {soundEnabled ? <Volume2 className="w-4 h-4 text-[#D4AF37]" /> : <VolumeX className="w-4 h-4 text-slate-500" />}
          </button>
        </div>

        {/* Continuous Scroll Progress Strip */}
        <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mt-1">
          <div 
            className="h-full bg-gradient-to-r from-emerald-400 via-purple-500 to-[#D4AF37] transition-all duration-100"
            style={{ width: `${Math.round(scrollProgress * 100)}%` }}
          />
        </div>
      </header>

      {/* =========================================================================
          SECTION 1: PICTURES 1 & 2 - THE FULL WORLD TREE (APEX TO ROOTS OVERVIEW)
         ========================================================================= */}
      <section id="stratum-full-tree" className="relative min-h-screen p-6 max-w-7xl mx-auto flex flex-col justify-between pt-8 pb-16">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-[#D4AF37] font-mono text-xs uppercase tracking-widest">
                <span>PICTURES 1 & 2 // AXIS MUNDI</span>
                <span>•</span>
                <span>ALTITUDE: 0m TO +4500m</span>
              </div>
              <h1 className="text-3xl lg:text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-amber-200 to-[#D4AF37] tracking-tight">
                The Sovereign World Tree Control Center
              </h1>
              <p className="text-sm text-slate-400 max-w-2xl mt-1">
                Where Mythic Architecture Meets Engineered Intelligence. Full tree telemetry with Redis MemCastle crown, Ouroboros SSM ternary trunk, and Viking drakkar root channels.
              </p>
            </div>

            {/* Picture 1 vs Picture 2 Switcher */}
            <div className="flex items-center gap-2 bg-black/80 border border-[#D4AF37]/40 p-1.5 rounded-xl shadow-lg">
              <button
                id="select-pic1-btn"
                onClick={() => { setActiveTreePicture('pic1_hud'); if (soundEnabled) audioEngine.playClick(); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                  activeTreePicture === 'pic1_hud'
                    ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]/50 shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Picture 1: vKG HUD Path-Traced
              </button>
              <button
                id="select-pic2-btn"
                onClick={() => { setActiveTreePicture('pic2_camelot'); if (soundEnabled) audioEngine.playClick(); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                  activeTreePicture === 'pic2_camelot'
                    ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37]/50 shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Picture 2: Camelot-OS World Tree
              </button>
            </div>
          </div>

          {/* Interactive World Tree Canvas Card */}
          <div className="relative w-full rounded-2xl border border-[#D4AF37]/30 bg-gradient-to-b from-[#050505] via-[#10061e] to-[#050505] overflow-hidden shadow-2xl min-h-[540px]">
            {/* Ambient Lighting FX */}
            <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_50%_40%,rgba(212,175,55,0.12),transparent_70%)]" />
            <div className="absolute top-0 right-0 w-96 h-96 bg-purple-900/10 blur-3xl pointer-events-none" />

            {/* Main Visual: Render uploaded Picture 2 or Path-traced Picture 1 */}
            <div className="relative w-full h-[540px] flex items-center justify-center overflow-hidden">
              <img 
                src="/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png"
                alt="Camelot-OS World Tree - The Sovereign Context Engine"
                className="w-full h-full object-contain object-center transition-all duration-700"
                style={{
                  filter: activeTreePicture === 'pic1_hud' 
                    ? 'hue-rotate(25deg) contrast(1.15) saturate(1.2)' 
                    : 'none'
                }}
                onError={(e) => {
                  // Fallback to high-res CDN if local public cache delays
                  (e.currentTarget as HTMLImageElement).src = 'https://i.postimg.cc/Lssx07X3/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png';
                }}
              />

              {/* OVERLAY INTERACTIVE HOTSPOT PINS */}
              {/* Hotspot 1: Crown Redis MemCastle */}
              <button
                id="hotspot-crown"
                onClick={() => scrollToSection('stratum-throne-room')}
                className="absolute top-[10%] left-[50%] -translate-x-1/2 group z-20 flex flex-col items-center"
                title="Redis MemCastle Crown (/vfs/mempalace/*) - Click to Ascend"
              >
                <div className="px-2.5 py-1 rounded-full bg-black/90 border border-cyan-400 text-cyan-300 font-mono text-[10px] tracking-wide shadow-lg group-hover:scale-110 group-hover:bg-cyan-950 transition-all flex items-center gap-1.5">
                  <Crown className="w-3 h-3 text-[#D4AF37]" />
                  <span>REDIS MEMCASTLE (/vfs/mempalace/*)</span>
                </div>
                <div className="w-0.5 h-6 bg-gradient-to-b from-cyan-400 to-transparent" />
              </button>

              {/* Hotspot 2: Left Brain - Open-Notebook */}
              <button
                id="hotspot-left-brain"
                onClick={() => scrollToSection('stratum-twin-brains')}
                className="absolute top-[48%] left-[28%] group z-20 flex flex-col items-center"
                title="Open-Notebook Deep Reasoning Engine"
              >
                <div className="px-2 py-0.5 rounded-full bg-black/90 border border-purple-400 text-purple-300 font-mono text-[10px] shadow-lg group-hover:scale-110 group-hover:bg-purple-950 transition-all flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-purple-400" />
                  <span>OPEN-NOTEBOOK (LOCAL CORE)</span>
                </div>
              </button>

              {/* Hotspot 3: Right Brain - NotebookLM */}
              <button
                id="hotspot-right-brain"
                onClick={() => scrollToSection('stratum-twin-brains')}
                className="absolute top-[48%] right-[28%] group z-20 flex flex-col items-center"
                title="NotebookLM Logical Synchronizer"
              >
                <div className="px-2 py-0.5 rounded-full bg-black/90 border border-cyan-400 text-cyan-300 font-mono text-[10px] shadow-lg group-hover:scale-110 group-hover:bg-cyan-950 transition-all flex items-center gap-1">
                  <Zap className="w-3 h-3 text-cyan-400" />
                  <span>NOTEBOOKLM (CLOUD LM)</span>
                </div>
              </button>

              {/* Hotspot 4: Trunk Ouroboros SSM */}
              <div className="absolute top-[62%] left-[50%] -translate-x-1/2 pointer-events-none text-center">
                <div className="px-3 py-1 rounded bg-black/80 border border-amber-500/40 text-amber-300 font-mono text-[9px] backdrop-blur-md">
                  OUROBOROS SSM TERNARY WEIGHTS: W_ij ∈ &#123;-1, 0, 1&#125;
                </div>
              </div>

              {/* Hotspot 5: Bottom Roots Open Viking VFS */}
              <button
                id="hotspot-roots"
                onClick={() => scrollToSection('stratum-vfs-roots')}
                className="absolute bottom-[6%] left-[50%] -translate-x-1/2 group z-20 flex flex-col items-center"
                title="Open Viking VFS Roots - Click to Descend"
              >
                <div className="w-0.5 h-6 bg-gradient-to-t from-emerald-400 to-transparent" />
                <div className="px-3 py-1 rounded-full bg-black/95 border border-emerald-400 text-emerald-300 font-mono text-[10px] tracking-wide shadow-xl group-hover:scale-110 group-hover:bg-emerald-950 transition-all flex items-center gap-1.5">
                  <Anchor className="w-3 h-3 text-emerald-400" />
                  <span>OPEN VIKING VFS ROOTS (/vfs/refractions/*)</span>
                  <ArrowDown className="w-3 h-3 text-emerald-400 animate-bounce" />
                </div>
              </button>
            </div>

            {/* Dimensional Morph & Telemetry Bottom Strip */}
            <div className="p-4 bg-black/80 border-t border-white/10 flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <span className="text-xs font-mono text-slate-400">2D/3D Morph Blend:</span>
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={Math.round(morphBlend * 100)} 
                  onChange={(e) => setMorphBlend(Number(e.target.value) / 100)}
                  className="w-36 accent-[#D4AF37] cursor-pointer"
                />
                <span className="text-xs font-mono text-[#D4AF37] font-bold">{(morphBlend * 100).toFixed(0)}% 3D</span>
              </div>

              <div className="flex items-center gap-6 font-mono text-xs">
                <span className="text-slate-400">Total Nodes: <strong className="text-white">10,428</strong></span>
                <span className="text-slate-400">Active Paths: <strong className="text-emerald-400">1,284</strong></span>
                <span className="text-slate-400">Avg Degree: <strong className="text-purple-300">2.91</strong></span>
                <button
                  id="descend-to-roots-btn"
                  onClick={() => scrollToSection('stratum-vfs-roots')}
                  className="px-3 py-1 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 hover:bg-emerald-500 hover:text-black transition-all flex items-center gap-1"
                >
                  <span>Explore VFS Roots</span>
                  <ArrowDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 2: PICTURES 3, 4, 5 - BOTTOM HOUSING THE VFS SYSTEM & VPS FILE EXPLORER
         ========================================================================= */}
      <section id="stratum-vfs-roots" className="relative min-h-screen p-6 max-w-7xl mx-auto flex flex-col justify-between pt-12 pb-16 border-t border-emerald-500/20">
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs uppercase tracking-widest">
                <span>PICTURES 3, 4 & 5 // ROOT FOUNDATION</span>
                <span>•</span>
                <span>ALTITUDE: -150m TO 0m</span>
              </div>
              <h2 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-emerald-200 to-emerald-400 tracking-tight">
                Open Viking VFS Roots & VPS File Explorer
              </h2>
              <p className="text-sm text-slate-400 max-w-2xl mt-1">
                Physical Media ⟷ Symbolic Memory ⟷ Sovereign Intelligence. Fiber-optic root conduits routing zero-copy data slabs across Lady Mnemosyne and Lady Alexandria mounts.
              </p>
            </div>

            {/* Pictures 3, 4, 5 Selector */}
            <div className="flex items-center gap-1 bg-black/80 border border-emerald-500/30 p-1.5 rounded-xl text-xs font-mono">
              <button
                id="select-pic3-btn"
                onClick={() => { setActiveVfsPicture('pic3_reflective'); if (soundEnabled) audioEngine.playClick(); }}
                className={`px-2.5 py-1.5 rounded-lg transition-all ${
                  activeVfsPicture === 'pic3_reflective'
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-400/50'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Pic 3: Reflective Table
              </button>
              <button
                id="select-pic4-btn"
                onClick={() => { setActiveVfsPicture('pic4_hud_roots'); if (soundEnabled) audioEngine.playClick(); }}
                className={`px-2.5 py-1.5 rounded-lg transition-all ${
                  activeVfsPicture === 'pic4_hud_roots'
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-400/50'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Pic 4: Open Viking HUD
              </button>
              <button
                id="select-pic5-btn"
                onClick={() => { setActiveVfsPicture('pic5_zoomed_roots'); if (soundEnabled) audioEngine.playClick(); }}
                className={`px-2.5 py-1.5 rounded-lg transition-all ${
                  activeVfsPicture === 'pic5_zoomed_roots'
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-400/50'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Pic 5: Zoomed Optical Fibers
              </button>
            </div>
          </div>

          {/* DUAL PANE: LEFT = VFS ROOTS VISUALIZER & PERSONAS, RIGHT = REAL INTERACTIVE VPS FILE EXPLORER */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Col: Visualizer & Lady Mnemosyne / Alexandria Cards */}
            <div className="lg:col-span-5 space-y-4">
              {/* Visual Display based on Pic 3 / 4 / 5 */}
              <div className="relative rounded-2xl border border-emerald-500/30 bg-black/80 overflow-hidden p-4 shadow-xl">
                <div className="flex items-center justify-between pb-3 border-b border-emerald-500/20 text-xs font-mono">
                  <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                    <Anchor className="w-3.5 h-3.5" />
                    RUNIC CIRCUITRY (SYMBOLIC)
                  </span>
                  <span className="text-slate-400">COMMIT: 1.01ms</span>
                </div>

                <div className="py-4 space-y-3">
                  <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-cyan-950 border border-cyan-500/50 flex items-center justify-center font-bold text-cyan-300">
                      LM
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-cyan-300">LADY MNEMOSYNE</span>
                        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 px-1.5 rounded">ONLINE</span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-mono">/vfs/mempalace/ • 1,024,768 Vector Nodes (12.4 GB)</p>
                      <div className="w-full bg-slate-800 h-1 rounded-full mt-1.5 overflow-hidden">
                        <div className="bg-cyan-400 h-full w-[88%]" />
                      </div>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-amber-950 border border-amber-500/50 flex items-center justify-center font-bold text-amber-300">
                      LA
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-amber-300">LADY ALEXANDRIA</span>
                        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950 px-1.5 rounded">ONLINE</span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-mono">/vfs/refractions/ • 512,944 Persona Templates (8.7 GB)</p>
                      <div className="w-full bg-slate-800 h-1 rounded-full mt-1.5 overflow-hidden">
                        <div className="bg-amber-400 h-full w-[65%]" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Hex Address Stream */}
                <div className="bg-black/90 rounded-xl p-3 border border-white/10 font-mono text-[10px] space-y-1">
                  <div className="text-slate-400 flex justify-between">
                    <span>MEMORY ADDRESS (HEX)</span>
                    <span>MOUNT TARGET</span>
                  </div>
                  <div className="text-cyan-400 flex justify-between">
                    <span>0x7F3A9C00</span>
                    <span>/vfs/mempalace/</span>
                  </div>
                  <div className="text-amber-400 flex justify-between">
                    <span>0x7F3A9D40</span>
                    <span>/vfs/refractions/</span>
                  </div>
                  <div className="text-purple-400 flex justify-between">
                    <span>0x7F3A9E80</span>
                    <span>/.agent/queue</span>
                  </div>
                  <div className="text-emerald-400 flex justify-between">
                    <span>0x7F3AA100</span>
                    <span>/sovereign/ledger</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Col: REAL INTERACTIVE VPS FILE EXPLORER */}
            <div className="lg:col-span-7 rounded-2xl border border-emerald-500/30 bg-black/90 p-5 shadow-2xl flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-white/10">
                  <div className="flex items-center gap-2">
                    <Folder className="w-4 h-4 text-emerald-400" />
                    <span className="font-mono text-xs font-bold text-white tracking-wider">VPS VFS FILE EXPLORER</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-400 border border-emerald-500/30">
                      MOUNT: /vfs
                    </span>
                  </div>
                  <span className="text-xs font-mono text-slate-400">Host: vps3573819 (104.234.50.84)</span>
                </div>

                {/* Directory Navigation Tree */}
                <div className="bg-black/60 rounded-xl border border-white/10 p-3 font-mono text-xs space-y-1 max-h-64 overflow-y-auto">
                  {/* Root */}
                  <div className="flex items-center gap-1.5 text-slate-400">
                    <span className="text-slate-600">/ (root)</span>
                  </div>

                  {/* /vfs folder */}
                  <div className="pl-3 space-y-1">
                    <div 
                      onClick={() => toggleFolder('/vfs')}
                      className="flex items-center gap-1.5 text-emerald-400 cursor-pointer hover:bg-white/5 py-0.5 px-1 rounded"
                    >
                      {expandedFolders['/vfs'] ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      <Folder className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="font-bold">/vfs</span>
                    </div>

                    {expandedFolders['/vfs'] && (
                      <div className="pl-4 space-y-1 border-l border-emerald-500/20 ml-1">
                        {/* /vfs/mempalace */}
                        <div 
                          onClick={() => toggleFolder('/vfs/mempalace')}
                          className="flex items-center gap-1.5 text-cyan-300 cursor-pointer hover:bg-white/5 py-0.5 px-1 rounded"
                        >
                          {expandedFolders['/vfs/mempalace'] ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                          <Folder className="w-3.5 h-3.5 text-cyan-400" />
                          <span>mempalace/ (Lady Mnemosyne)</span>
                        </div>

                        {expandedFolders['/vfs/mempalace'] && (
                          <div className="pl-5 space-y-0.5 border-l border-cyan-500/20 ml-1">
                            <div 
                              onClick={() => handleSelectFile('/vfs/mempalace/embeddings_768d.bin')}
                              className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-all ${
                                selectedVfsPath === '/vfs/mempalace/embeddings_768d.bin'
                                  ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/40'
                                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                              }`}
                            >
                              <FileText className="w-3 h-3 text-cyan-400" />
                              <span>embeddings_768d.bin</span>
                              <span className="ml-auto text-[10px] text-slate-500">8.4 GB</span>
                            </div>

                            <div 
                              onClick={() => handleSelectFile('/vfs/mempalace/episodic_slabs.wal')}
                              className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-all ${
                                selectedVfsPath === '/vfs/mempalace/episodic_slabs.wal'
                                  ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/40'
                                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                              }`}
                            >
                              <FileText className="w-3 h-3 text-cyan-400" />
                              <span>episodic_slabs.wal</span>
                              <span className="ml-auto text-[10px] text-slate-500">2.1 GB</span>
                            </div>

                            <div 
                              onClick={() => handleSelectFile('/vfs/mempalace/mnemosyne_kg.parquet')}
                              className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-all ${
                                selectedVfsPath === '/vfs/mempalace/mnemosyne_kg.parquet'
                                  ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/40'
                                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                              }`}
                            >
                              <FileText className="w-3 h-3 text-cyan-400" />
                              <span>mnemosyne_kg.parquet</span>
                              <span className="ml-auto text-[10px] text-slate-500">1.9 GB</span>
                            </div>
                          </div>
                        )}

                        {/* /vfs/refractions */}
                        <div 
                          onClick={() => toggleFolder('/vfs/refractions')}
                          className="flex items-center gap-1.5 text-amber-300 cursor-pointer hover:bg-white/5 py-0.5 px-1 rounded"
                        >
                          {expandedFolders['/vfs/refractions'] ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                          <Folder className="w-3.5 h-3.5 text-amber-400" />
                          <span>refractions/ (Lady Alexandria)</span>
                        </div>

                        {expandedFolders['/vfs/refractions'] && (
                          <div className="pl-5 space-y-0.5 border-l border-amber-500/20 ml-1">
                            <div 
                              onClick={() => handleSelectFile('/vfs/refractions/sir_codex_profile.json')}
                              className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-all ${
                                selectedVfsPath === '/vfs/refractions/sir_codex_profile.json'
                                  ? 'bg-amber-500/20 text-amber-200 border border-amber-500/40'
                                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                              }`}
                            >
                              <FileText className="w-3 h-3 text-amber-400" />
                              <span>sir_codex_profile.json</span>
                              <span className="ml-auto text-[10px] text-slate-500">24 KB</span>
                            </div>

                            <div 
                              onClick={() => handleSelectFile('/vfs/refractions/heimdall_sentry.wasm')}
                              className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-all ${
                                selectedVfsPath === '/vfs/refractions/heimdall_sentry.wasm'
                                  ? 'bg-amber-500/20 text-amber-200 border border-amber-500/40'
                                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                              }`}
                            >
                              <FileText className="w-3 h-3 text-amber-400" />
                              <span>heimdall_sentry.wasm</span>
                              <span className="ml-auto text-[10px] text-slate-500">48 KB</span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* File Inspector Details */}
                <div className="p-3 rounded-xl bg-black/60 border border-white/10 space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Selected Path:</span>
                    <span className="text-emerald-400 font-bold">{selectedVfsPath}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 font-mono text-[11px] text-slate-300">
                    <div className="p-2 rounded bg-white/5 border border-white/5">
                      <span className="text-slate-500 block text-[9px]">LOCK TYPE</span>
                      <span className="text-cyan-400 font-semibold">SHARED DMA</span>
                    </div>
                    <div className="p-2 rounded bg-white/5 border border-white/5">
                      <span className="text-slate-500 block text-[9px]">SYNCHRONIZATION</span>
                      <span className="text-emerald-400 font-semibold">0.73 ms</span>
                    </div>
                    <div className="p-2 rounded bg-white/5 border border-white/5">
                      <span className="text-slate-500 block text-[9px]">SECURITY</span>
                      <span className="text-purple-300 font-semibold">Z3 PROVED</span>
                    </div>
                  </div>

                  <p className="text-[11px] font-mono text-slate-400">{vfsLog}</p>

                  <div className="flex items-center gap-2 pt-2">
                    <button
                      id="vfs-dma-sync-btn"
                      onClick={() => {
                        setVfsLog(`Initiated zero-copy DMA sync for ${selectedVfsPath}... Complete (0.19ms)`);
                        if (soundEnabled) audioEngine.playCommandExecute();
                      }}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-black font-bold font-mono text-xs transition-all flex items-center gap-1.5"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Trigger DMA Sync</span>
                    </button>
                    <button
                      id="vfs-verify-z3-btn"
                      onClick={() => {
                        setVfsLog(`Z3 Invariant Check: Memory bounds for ${selectedVfsPath} strictly within 8GB ceiling.`);
                        if (soundEnabled) audioEngine.playBrainSync();
                      }}
                      className="px-3 py-1.5 rounded-lg bg-purple-900/50 hover:bg-purple-800 text-purple-200 border border-purple-500/40 font-mono text-xs transition-all"
                    >
                      Verify Z3 Invariants
                    </button>
                  </div>
                </div>
              </div>

              {/* Navigation to Next Stratum */}
              <div className="pt-4 flex justify-end">
                <button
                  id="ascend-to-notebook-btn"
                  onClick={() => scrollToSection('stratum-twin-brains')}
                  className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-mono text-xs font-bold transition-all flex items-center gap-2 shadow-lg shadow-purple-600/30"
                >
                  <span>Transition to Open Notebook Interface</span>
                  <ArrowDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 3: PICTURE 6 - TRANSITIONING TO THE OPEN NOTEBOOK INTERFACE
         ========================================================================= */}
      <section id="stratum-twin-brains" className="relative min-h-screen p-6 max-w-7xl mx-auto flex flex-col justify-between pt-12 pb-16 border-t border-purple-500/20">
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-purple-400 font-mono text-xs uppercase tracking-widest">
                <span>PICTURE 6 // COGNITIVE INTERFACE</span>
                <span>•</span>
                <span>ALTITUDE: +2800m</span>
              </div>
              <h2 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-purple-200 to-cyan-300 tracking-tight">
                Dynamic Twin Brains & Open Notebook Interface
              </h2>
              <p className="text-sm text-slate-400 max-w-2xl mt-1">
                Local Open Core (100% Sovereign Private, Golden Mechanical Gears) ⟷ Cloud LM Wrapper (100% Cloud Scale, Cyan Fiber Synapses). Connected to Memcastle Redis Configurator.
              </p>
            </div>

            <div className="px-3 py-1.5 rounded-xl bg-[#2E0854] border border-purple-500/50 text-xs font-mono text-purple-200">
              PORT 8502 (Open-Notebook) ⟷ PORT 6379 (Redis MemCastle)
            </div>
          </div>

          {/* GRID OF CONTROLS MATCHING PICTURE 6 */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Top/Left Col: Twin Brains Slider & Dials */}
            <div className="lg:col-span-7 rounded-2xl border border-purple-500/30 bg-black/80 p-5 shadow-2xl space-y-6">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <span className="font-mono text-xs font-bold text-white tracking-wider">DYNAMIC TWIN BRAINS ENGINE</span>
                <span className="text-xs font-mono text-purple-300">BALANCE CONTROLLER</span>
              </div>

              {/* Dynamic Brains Visual Comparison */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-500/30 text-center space-y-2">
                  <div className="w-12 h-12 rounded-xl bg-amber-900/40 border border-amber-400/50 mx-auto flex items-center justify-center text-2xl shadow-lg shadow-amber-500/20">
                    ⚙️
                  </div>
                  <h3 className="font-bold text-xs text-amber-300 font-mono uppercase">LOCAL_OPEN_CORE</h3>
                  <p className="text-[11px] text-slate-400">100% Sovereign Private • WASI Offline Runtime • Zero Telemetry Leak</p>
                  <span className="inline-block px-2 py-0.5 rounded font-mono text-[10px] bg-amber-900/60 text-amber-200">
                    {100 - privateVsCloudBalance}% Sovereign Weight
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-cyan-950/30 border border-cyan-500/30 text-center space-y-2">
                  <div className="w-12 h-12 rounded-xl bg-cyan-900/40 border border-cyan-400/50 mx-auto flex items-center justify-center text-2xl shadow-lg shadow-cyan-500/20">
                    🧠
                  </div>
                  <h3 className="font-bold text-xs text-cyan-300 font-mono uppercase">CLOUD_LM_WRAPPER</h3>
                  <p className="text-[11px] text-slate-400">100% Cloud Scale • Gemini 3.8 Pro Reasoning • 1M Token Manifold</p>
                  <span className="inline-block px-2 py-0.5 rounded font-mono text-[10px] bg-cyan-900/60 text-cyan-200">
                    {privateVsCloudBalance}% Cloud Scale
                  </span>
                </div>
              </div>

              {/* Sovereign Private <---> Cloud Scale Interactive Slider */}
              <div className="space-y-2 bg-black/60 p-4 rounded-xl border border-white/10">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-amber-400 font-bold">100% Sovereign Private</span>
                  <span className="text-cyan-400 font-bold">100% Cloud Scale</span>
                </div>
                <input 
                  type="range"
                  min="0"
                  max="100"
                  value={privateVsCloudBalance}
                  onChange={(e) => setPrivateVsCloudBalance(Number(e.target.value))}
                  className="w-full accent-purple-400 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] font-mono text-slate-400">
                  <span>Isolated Hardware Enclave</span>
                  <span>Hybrid Dynamic Route</span>
                  <span>Frontier Hyperscale Sync</span>
                </div>
              </div>

              {/* Interactive Open Notebook Prompt & Synthesis Workspace */}
              <div className="space-y-3 pt-2">
                <span className="font-mono text-xs text-slate-300 font-bold block">OPEN NOTEBOOK SCRATCHPAD:</span>
                <textarea
                  id="notebook-prompt-input"
                  value={notebookPrompt}
                  onChange={(e) => setNotebookPrompt(e.target.value)}
                  rows={2}
                  className="w-full p-3 rounded-xl bg-black/70 border border-purple-500/40 font-mono text-xs text-purple-100 focus:outline-none focus:border-purple-400"
                  placeholder="Enter context, research question, or invariant theorem to synthesize..."
                />
                <button
                  id="notebook-synthesize-btn"
                  onClick={handleRunNotebookSynthesis}
                  disabled={isSynthesizing}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white font-mono text-xs font-bold transition-all flex items-center gap-2 shadow-lg"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{isSynthesizing ? 'Synthesizing with Twin Brains...' : 'Execute Twin-Brain Synthesis'}</span>
                </button>

                {notebookOutput && (
                  <div className="p-3 rounded-xl bg-purple-950/40 border border-purple-500/50 font-mono text-xs text-purple-200 whitespace-pre-line animate-fadeIn">
                    {notebookOutput}
                  </div>
                )}
              </div>
            </div>

            {/* Right Col: Memcastle Redis Configurator (Matching Picture 6) */}
            <div className="lg:col-span-5 rounded-2xl border border-cyan-500/30 bg-black/80 p-5 shadow-2xl space-y-6 flex flex-col justify-between">
              <div className="space-y-5">
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <span className="font-mono text-xs font-bold text-white tracking-wider">MEMCASTLE REDIS CONFIGURATOR</span>
                  <span className="text-xs font-mono text-cyan-400">REDIS_MEM_CASTLE v1</span>
                </div>

                {/* 7.2GB Strict Threshold Gauge */}
                <div className="p-4 rounded-xl bg-cyan-950/30 border border-cyan-500/40 space-y-2">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-cyan-300 font-bold">7.2 GB Threshold Cap</span>
                    <span className="text-emerald-400 font-bold">87% Slab Capacity</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                    <div className="bg-gradient-to-r from-cyan-400 to-purple-500 h-full w-[87%]" />
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono block">Enforces 8GB Scarcity Protocol. Zero heap spills.</span>
                </div>

                {/* Memory Slab Visual Cylinders */}
                <div>
                  <span className="text-xs font-mono text-slate-300 block mb-2">ACTIVE REDIS MEMORY CYLINDERS:</span>
                  <div className="grid grid-cols-4 gap-2">
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((cyl) => (
                      <div key={cyl} className="p-2 rounded-lg bg-cyan-950/40 border border-cyan-500/30 text-center">
                        <div className="h-10 bg-cyan-900/30 rounded border border-cyan-400/40 flex items-end overflow-hidden p-0.5">
                          <div 
                            className="w-full bg-cyan-400 rounded-sm"
                            style={{ height: `${60 + (cyl * 4)}%` }}
                          />
                        </div>
                        <span className="text-[9px] font-mono text-cyan-300 mt-1 block">Slab #{cyl}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Eviction Policy & TTL */}
                <div className="space-y-3 font-mono text-xs">
                  <div>
                    <label className="text-slate-400 block mb-1">CACHE EVICTION POLICY:</label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(['SOVEREIGN_PINNED', 'LRU', 'LFU'] as const).map((pol) => (
                        <button
                          key={pol}
                          onClick={() => { setRedisEvictionPolicy(pol); if (soundEnabled) audioEngine.playClick(); }}
                          className={`py-1.5 px-2 rounded-lg text-[10px] font-bold transition-all ${
                            redisEvictionPolicy === pol
                              ? 'bg-cyan-500 text-black shadow-md'
                              : 'bg-white/5 text-slate-400 hover:text-white'
                          }`}
                        >
                          {pol}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-slate-400 mb-1">
                      <span>SLAB TTL (SECONDS):</span>
                      <span className="text-cyan-300 font-bold">{redisSlabTtl}s</span>
                    </div>
                    <input 
                      type="range"
                      min="60"
                      max="86400"
                      step="300"
                      value={redisSlabTtl}
                      onChange={(e) => setRedisSlabTtl(Number(e.target.value))}
                      className="w-full accent-cyan-400 cursor-pointer"
                    />
                  </div>
                </div>
              </div>

              {/* Navigation to Throne Room */}
              <div className="pt-4 flex justify-end">
                <button
                  id="ascend-to-throne-btn"
                  onClick={() => scrollToSection('stratum-throne-room')}
                  className="px-4 py-2 rounded-xl bg-[#D4AF37] hover:bg-amber-400 text-black font-mono text-xs font-bold transition-all flex items-center gap-2 shadow-lg shadow-[#D4AF37]/30"
                >
                  <span>Ascend to Throne Room & Council of Mages</span>
                  <ArrowDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          SECTION 4: PICTURE 7 - TRANSITION TO THE THRONE ROOM & COUNCIL OF MAGES
         ========================================================================= */}
      <section id="stratum-throne-room" className="relative min-h-screen p-6 max-w-7xl mx-auto flex flex-col justify-between pt-12 pb-20 border-t border-[#D4AF37]/30">
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-[#D4AF37] font-mono text-xs uppercase tracking-widest">
                <span>PICTURE 7 // THE APEX THRONE ROOM</span>
                <span>•</span>
                <span>ALTITUDE: +4500m</span>
              </div>
              <h2 className="text-3xl lg:text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-amber-200 to-[#D4AF37] tracking-tight">
                The Throne Room & Council of Mages
              </h2>
              <p className="text-sm text-slate-400 max-w-2xl mt-1">
                Memcastle Control Console. All 10 Knights of the Kingdom assembled around the Yggdrasil table with Heimdall the Gatekeeper and the Bifrost 3D ➔ 2D Translation Engine.
              </p>
            </div>

            <div className="px-3 py-1.5 rounded-xl bg-[#2E0854] border border-[#D4AF37] text-xs font-mono text-[#D4AF37] flex items-center gap-2 shadow-lg shadow-[#D4AF37]/20">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>GATE STATUS: SECURE (HEIMDALL VERIFIED)</span>
            </div>
          </div>

          {/* MAIN THRONE ROOM GRID */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Col: L0-L7 System Architecture Stack */}
            <div className="lg:col-span-3 rounded-2xl border border-white/10 bg-black/80 p-4 shadow-2xl space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-white/10 text-xs font-mono">
                <span className="font-bold text-[#D4AF37]">SYSTEM ARCHITECTURE</span>
                <span className="text-slate-500">L0 ➔ L7</span>
              </div>
              <p className="text-[10px] font-mono text-slate-400">FROM INTENTION TO EXECUTION</p>

              <div className="space-y-1.5">
                {ARCH_LAYERS.map((layer) => (
                  <div 
                    key={layer.id}
                    className="p-2 rounded-lg bg-white/5 border border-white/5 hover:border-[#D4AF37]/40 transition-all font-mono"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-bold" style={{ color: layer.color }}>{layer.id} {layer.name}</span>
                    </div>
                    <span className="text-[9px] text-slate-400 block truncate">{layer.desc}</span>
                  </div>
                ))}
              </div>

              {/* Gate Checklist */}
              <div className="pt-2 border-t border-white/10 space-y-1 font-mono text-[10px]">
                <span className="text-emerald-400 font-bold block mb-1">HEIMDALL GATE ENCLAVE:</span>
                {Object.entries(gateStatus).map(([k, ok]) => (
                  <div key={k} className="flex justify-between items-center text-slate-300">
                    <span className="capitalize">{k}:</span>
                    <span className="text-emerald-400 font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-2.5 h-2.5" />
                      {k === 'access' ? 'GRANTED' : 'VERIFIED'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Center Col: Interactive Council of Mages Round Table & Heimdall */}
            <div className="lg:col-span-6 rounded-2xl border border-[#D4AF37]/40 bg-gradient-to-b from-[#10061e] via-black to-[#050505] p-5 shadow-2xl space-y-6 flex flex-col justify-between">
              <div className="space-y-4">
                <div className="text-center space-y-1">
                  <span className="font-mono text-xs text-[#D4AF37] uppercase tracking-widest block font-bold">
                    THE COUNCIL OF MAGES
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    KNOWLEDGE • ALIGNMENT • GUARDIANSHIP • MULTI INTELLIGENTIA UNA MENS
                  </span>
                </div>

                {/* 10 Mages Interactive Round Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {COUNCIL_MAGES.map((mage) => {
                    const isSelected = selectedMage.id === mage.id;
                    return (
                      <button
                        key={mage.id}
                        id={`mage-btn-${mage.id}`}
                        onClick={() => {
                          setSelectedMage(mage);
                          if (soundEnabled) audioEngine.playCommandExecute();
                        }}
                        className={`p-2.5 rounded-xl border text-center transition-all flex flex-col items-center gap-1 ${
                          isSelected
                            ? 'bg-[#2E0854] border-[#D4AF37] shadow-lg shadow-[#D4AF37]/30 scale-105'
                            : 'bg-black/60 border-white/10 hover:border-[#D4AF37]/50 text-slate-300'
                        }`}
                      >
                        <span className="text-lg">{mage.icon}</span>
                        <span className="text-[10px] font-mono font-bold block truncate w-full text-white">
                          {mage.name}
                        </span>
                        <span className="text-[8px] font-mono text-slate-400 truncate w-full">
                          {mage.title}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* Bifrost Engine Banner & Heimdall Gatekeeper */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-blue-950/40 via-purple-950/40 to-blue-950/40 border border-blue-500/40 text-center space-y-2">
                  <div className="text-xs font-mono text-cyan-300 font-bold uppercase tracking-wider">
                    BIFROST: 3D ➔ 2D TRANSLATION ENGINE
                  </div>
                  <p className="text-[10px] text-slate-400 font-mono">
                    MULTIDIMENSIONAL DATA • ZERO CONTEXT LEAKAGE
                  </p>
                  <div className="py-2 px-4 rounded-lg bg-black/60 border border-cyan-400/30 inline-block">
                    <span className="text-xs font-mono text-cyan-200 font-bold">
                      HEIMDALL THE GATEKEEPER: "NOTHING UNSEEN SHALL PASS."
                    </span>
                  </div>
                </div>
              </div>

              {/* Royal Decree Command Console */}
              <div className="space-y-3 pt-2">
                <span className="font-mono text-xs text-[#D4AF37] font-bold block">
                  DISPATCH ROYAL DECREE TO ALL KNIGHTS:
                </span>
                <div className="flex gap-2">
                  <input
                    id="royal-decree-input"
                    type="text"
                    value={throneDecree}
                    onChange={(e) => setThroneDecree(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleIssueDecree()}
                    placeholder="Enter decree to command all Knights in the kingdom..."
                    className="flex-1 p-2.5 rounded-xl bg-black/80 border border-[#D4AF37]/40 font-mono text-xs text-white focus:outline-none focus:border-[#D4AF37]"
                  />
                  <button
                    id="issue-decree-btn"
                    onClick={() => handleIssueDecree()}
                    className="px-4 py-2.5 rounded-xl bg-[#D4AF37] hover:bg-amber-400 text-black font-bold font-mono text-xs transition-all shadow-md"
                  >
                    Issue Decree
                  </button>
                </div>

                {/* Preset Directives */}
                <div className="flex flex-wrap gap-1.5">
                  {[
                    'Summon All Knights for Security Audit',
                    'Order Sir Codex to Compile WASI Filters',
                    'Command Heimdall to Seal Bifrost',
                    'Order Lady Mnemosyne to Re-index Vector Nodes'
                  ].map((preset) => (
                    <button
                      key={preset}
                      onClick={() => handleIssueDecree(preset)}
                      className="text-[9px] font-mono px-2 py-1 rounded bg-white/5 hover:bg-[#D4AF37]/20 text-slate-400 hover:text-[#D4AF37] border border-white/5 transition-all"
                    >
                      + {preset}
                    </button>
                  ))}
                </div>

                {decreeResponse && (
                  <div className="p-3 rounded-xl bg-[#2E0854]/60 border border-[#D4AF37]/50 font-mono text-xs text-amber-200 whitespace-pre-line animate-fadeIn">
                    {decreeResponse}
                  </div>
                )}
              </div>
            </div>

            {/* Right Col: Active Summon Card (Lady Mnemosyne / Active Mage) */}
            <div className="lg:col-span-3 rounded-2xl border border-cyan-500/40 bg-black/90 p-5 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <span className="text-xs font-mono text-cyan-400 uppercase font-bold tracking-wider">SUMMON ACTIVE</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-500/40">
                  ONLINE
                </span>
              </div>

              {/* Summon Profile */}
              <div className="space-y-2">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-950 to-purple-950 border border-cyan-400/50 flex items-center justify-center text-3xl mx-auto shadow-xl shadow-cyan-500/20">
                  {selectedMage.icon}
                </div>
                <div className="text-center">
                  <h3 className="font-bold text-sm text-white">{selectedMage.name}</h3>
                  <span className="text-xs font-mono text-cyan-300">{selectedMage.title}</span>
                </div>
              </div>

              {/* Quote */}
              <blockquote className="italic text-xs text-slate-300 border-l-2 border-cyan-400 pl-3 py-1 font-serif bg-cyan-950/20 rounded-r">
                "{selectedMage.quote}"
              </blockquote>

              {/* Metrics */}
              <div className="space-y-2 font-mono text-xs">
                <div>
                  <div className="flex justify-between text-slate-400 text-[11px] mb-1">
                    <span>SGE (Graph Efficiency):</span>
                    <span className="text-cyan-300 font-bold">{selectedMage.sge}</span>
                  </div>
                  <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                    <div className="bg-cyan-400 h-full w-[99%]" />
                  </div>
                </div>

                <div className="flex justify-between text-slate-400 text-[11px]">
                  <span>VRAM (Active Slab):</span>
                  <span className="text-white font-bold">{selectedMage.vram}</span>
                </div>

                <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/30 flex items-center gap-2 text-[10px] text-emerald-300">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>AgentArmor Enforced</span>
                </div>
              </div>

              {/* Core Directives */}
              <div className="pt-2 border-t border-white/10 space-y-1">
                <span className="text-[10px] font-mono text-slate-400 block font-bold">CORE DIRECTIVES:</span>
                <div className="flex flex-wrap gap-1">
                  {selectedMage.directives.map((dir) => (
                    <span 
                      key={dir} 
                      className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/5 border border-white/10 text-slate-300"
                    >
                      {dir}
                    </span>
                  ))}
                </div>
              </div>

              {/* Scroll back to top */}
              <div className="pt-2">
                <button
                  id="scroll-to-top-btn"
                  onClick={() => scrollToSection('stratum-full-tree')}
                  className="w-full py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 font-mono text-xs transition-all flex items-center justify-center gap-1.5"
                >
                  <ArrowUp className="w-3.5 h-3.5" />
                  <span>Back to Apex / Full Tree</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default SovereignWorldTreeScrollingExperience;
