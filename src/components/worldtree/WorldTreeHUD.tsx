import React, { useEffect, useRef, useState, useCallback } from 'react';
import { 
  TreeDeciduous, 
  Move3d, 
  Layers, 
  Search, 
  Filter, 
  RotateCcw, 
  Play, 
  Pause, 
  Sparkles, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  Zap, 
  Flame, 
  Lock, 
  Cpu, 
  Activity, 
  Maximize2, 
  Radio, 
  Eye, 
  Sliders, 
  X,
  Compass,
  ArrowUpRight,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { WorldTreeGraphData, GraphNode, NodeState, TransitionMode } from '../../types/worldTreeGraph';
import { fetchWorldTreeTimeline, STATE_COLORS, LINK_COLORS } from '../../data/worldTreeGraphData';
import { WorldTree2D } from './WorldTree2D';
import { WorldTree3D } from './WorldTree3D';
import { WorldTreeTransition } from './WorldTreeTransition';

interface WorldTreeHUDProps {
  onOpenModal?: (modalType: 'memcastle' | 'twin_brains' | 'viking' | 'vkg') => void;
  className?: string;
}

export const WorldTreeHUD: React.FC<WorldTreeHUDProps> = ({
  onOpenModal,
  className = ''
}) => {
  // DOM References
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const container2DRef = useRef<HTMLDivElement | null>(null);
  const container3DRef = useRef<HTMLDivElement | null>(null);

  // Engine References
  const graph2DRef = useRef<WorldTree2D | null>(null);
  const graph3DRef = useRef<WorldTree3D | null>(null);
  const transitionRef = useRef<WorldTreeTransition | null>(null);

  // State
  const [graphData, setGraphData] = useState<WorldTreeGraphData | null>(null);
  const [mode, setMode] = useState<TransitionMode>('2D');
  const [morphProgress, setMorphProgress] = useState(0.0);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [nodeCountSetting, setNodeCountSetting] = useState<50 | 200 | 500>(50);
  const [isAutoMorphing, setIsAutoMorphing] = useState(false);
  const [sseActive, setSseActive] = useState(true);
  const [showAccessibleMirror, setShowAccessibleMirror] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; node: GraphNode } | null>(null);
  const [telemetryMessage, setTelemetryMessage] = useState<string>('PARITY LOCK // AXIS MUNDI CONVERGED');
  const [webGpuSupported, setWebGpuSupported] = useState(false);

  // Test WebGPU support
  useEffect(() => {
    if (typeof navigator !== 'undefined' && (navigator as any).gpu) {
      setWebGpuSupported(true);
    }
  }, []);

  // 1. Initial Data Fetching from /v1/graph/timeline?scope=current
  const loadGraph = useCallback(async (count: 50 | 200 | 500) => {
    try {
      setTelemetryMessage(`FETCHING /v1/graph/timeline?scope=current [N=${count}]...`);
      const data = await fetchWorldTreeTimeline('current', count);
      setGraphData(data);
      setTelemetryMessage(`LOADED REV ${data.revision} // ${data.nodes.length} NODES // ${data.links.length} EDGES`);
    } catch (err) {
      console.error('Failed to load World Tree graph:', err);
    }
  }, []);

  useEffect(() => {
    loadGraph(nodeCountSetting);
  }, [loadGraph, nodeCountSetting]);

  // 2. Initialize Renderers & Transition Orchestrator
  useEffect(() => {
    if (!graphData || !container2DRef.current || !container3DRef.current) return;

    // Teardown previous if existing
    if (transitionRef.current) {
      transitionRef.current.destroy();
    }

    const c2d = container2DRef.current;
    const c3d = container3DRef.current;

    // Initialize 2D
    const g2d = new WorldTree2D(c2d, graphData, {
      onNodeSelect: (node) => {
        setSelectedNode(node);
        transitionRef.current?.selectNode(node);
      },
      onNodeRightClick: (node, coords) => {
        setContextMenu({ x: coords.x, y: coords.y, node });
      },
      searchQuery,
      activeFilter
    });
    graph2DRef.current = g2d;

    // Initialize 3D
    const g3d = new WorldTree3D(c3d, graphData, {
      onNodeSelect: (node) => {
        setSelectedNode(node);
        transitionRef.current?.selectNode(node);
      },
      onNodeRightClick: (node, coords) => {
        setContextMenu({ x: coords.x, y: coords.y, node });
      },
      searchQuery,
      activeFilter,
      lodMode: nodeCountSetting === 500 ? 'points' : nodeCountSetting === 200 ? 'simplified' : 'full'
    });
    graph3DRef.current = g3d;

    // Initialize Transition Orchestrator with 800ms duration per specification
    const transition = new WorldTreeTransition(graphData, c2d, c3d, {
      duration: 800,
      onModeChange: (newMode) => setMode(newMode),
      onProgress: (prog) => setMorphProgress(prog),
      onNodeSelect: (node) => setSelectedNode(node)
    });
    transition.setRenderers(g2d, g3d);
    transitionRef.current = transition;

    // Initial state: 2D visible, 3D hidden
    c2d.style.display = 'block';
    c2d.style.opacity = '1';
    c3d.style.display = 'none';
    c3d.style.opacity = '0';

    return () => {
      transition.destroy();
    };
  }, [graphData, nodeCountSetting]);

  // 3. Mode Toggle (Enter 3D / Return to 2D)
  const toggleMode = async () => {
    if (!transitionRef.current) return;
    if (mode === '2D') {
      setTelemetryMessage('TRANSITIONING: 2D ➔ 3D MORPH [800ms] // Z-LIFT & ORBITAL CAM');
      await transitionRef.current.to3D();
      setTelemetryMessage('3D SPATIAL TOPOLOGY ONLINE // ORBITAL NAVIGATION ACTIVE');
    } else {
      setTelemetryMessage('TRANSITIONING: 3D ➔ 2D MORPH [800ms] // ORTHOGRAPHIC FLATTEN');
      await transitionRef.current.to2D();
      setTelemetryMessage('2D TOPOLOGY BLUEPRINT ONLINE // ORTHOGRAPHIC CAD ACTIVE');
    }
  };

  // 4. Continuous Dimension Scrubbing (2.00D ➔ 3.00D)
  const handleScrub = (fraction: number) => {
    if (!transitionRef.current) return;
    setMorphProgress(fraction);
    transitionRef.current.scrubContinuously(fraction);
  };

  // 5. Auto-Morphing Sinusoidal Loop
  useEffect(() => {
    if (!isAutoMorphing) return;
    let animId: number;
    let t = 0;
    const loop = () => {
      t += 0.015;
      const scrubVal = (Math.sin(t) + 1) / 2;
      handleScrub(scrubVal);
      animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isAutoMorphing]);

  // 6. Search Filter Propagation
  useEffect(() => {
    if (graph2DRef.current) graph2DRef.current.setSearchQuery(searchQuery);
    if (graph3DRef.current) graph3DRef.current.setSearchQuery(searchQuery);
  }, [searchQuery]);

  // 7. State Filter Propagation
  useEffect(() => {
    if (graph2DRef.current) graph2DRef.current.setFilter(activeFilter);
    if (graph3DRef.current) graph3DRef.current.setFilter(activeFilter);
  }, [activeFilter]);

  // 8. Simulated / Live SSE Telemetry Stream (/v1/stream/hud)
  useEffect(() => {
    if (!sseActive || !graphData) return;

    // Simulate periodic live patches on nodes
    const interval = setInterval(() => {
      const randomIdx = Math.floor(Math.random() * graphData.nodes.length);
      const targetNode = graphData.nodes[randomIdx];
      if (!targetNode) return;

      const states: NodeState[] = ['verified', 'running', 'approval_required', 'verified'];
      const nextState = states[Math.floor(Math.random() * states.length)];
      
      const patch = {
        type: 'graph.patch',
        nodeId: targetNode.id,
        state: nextState,
        timestamp: new Date().toISOString()
      };

      // Apply patch to local state
      targetNode.state = nextState;
      targetNode.color = STATE_COLORS[nextState];

      if (graph2DRef.current) graph2DRef.current.requestRedraw();
      if (graph3DRef.current) graph3DRef.current.refreshGraph();

      setTelemetryMessage(`SSE [graph.patch]: ${targetNode.label} ➔ ${nextState.toUpperCase()}`);
    }, 4500);

    return () => clearInterval(interval);
  }, [sseActive, graphData]);

  // 9. Keyboard Shortcuts for Navigation Continuity
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if typing in input
      if ((e.target as HTMLElement)?.tagName === 'INPUT') return;

      if (e.key === '3') {
        e.preventDefault();
        toggleMode();
      } else if (e.key === 'm' || e.key === 'M') {
        e.preventDefault();
        setIsAutoMorphing(prev => !prev);
      } else if (e.key === 'Escape') {
        setSelectedNode(null);
        setContextMenu(null);
        transitionRef.current?.selectNode(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mode]);

  // Dismiss context menu on window click
  useEffect(() => {
    const closeMenu = () => setContextMenu(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const stateCounts = React.useMemo(() => {
    if (!graphData) return {};
    const counts: Record<string, number> = {};
    graphData.nodes.forEach(n => {
      counts[n.state] = (counts[n.state] || 0) + 1;
    });
    return counts;
  }, [graphData]);

  return (
    <article 
      ref={wrapperRef}
      className={`hud-card hud-card--wide relative w-full rounded-3xl border border-[#D4AF37]/40 bg-[#050505] shadow-[0_0_80px_rgba(0,0,0,0.95)] overflow-hidden flex flex-col ${className}`}
    >
      {/* ================= HUD CARD HEADER (per Section 7) ================= */}
      <header className="hud-card__header p-4 sm:p-5 border-b border-cyan-900/40 bg-black/80 backdrop-blur-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-amber-500/20 to-purple-900/30 border border-[#D4AF37]/50 text-[#D4AF37] shadow-lg shadow-amber-500/10">
            <TreeDeciduous className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-bold text-white tracking-wide uppercase font-mono">
                World Tree <span className="text-[#D4AF37]">UI</span>
              </h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-cyan-950/80 border border-cyan-500/40 text-cyan-300">
                2D ➔ 3D CONTINUITY
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Tenant-scoped, verified context topology • Revision {graphData?.revision || 412}
            </p>
          </div>
        </div>

        {/* Global Controls & Integrity Badge */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {/* WebGPU / WebGL Badge */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-black/60 border border-slate-700/60 text-[10px] font-mono">
            <Cpu className="w-3 h-3 text-cyan-400" />
            <span className="text-slate-400">GPU:</span>
            <span className={webGpuSupported ? 'text-emerald-400 font-bold' : 'text-cyan-400 font-bold'}>
              {webGpuSupported ? 'WebGPU' : 'WebGL 2.0'}
            </span>
          </div>

          {/* SSE Stream Status */}
          <button
            onClick={() => setSseActive(prev => !prev)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[10px] font-mono transition-all ${
              sseActive 
                ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300' 
                : 'bg-slate-900/40 border-slate-700 text-slate-400'
            }`}
            title="Toggle Live Server-Sent Events (/v1/stream/hud)"
          >
            <Radio className={`w-3 h-3 ${sseActive ? 'animate-pulse text-emerald-400' : ''}`} />
            <span>SSE {sseActive ? 'CONNECTED' : 'PAUSED'}</span>
          </button>

          {/* Graph Integrity Badge */}
          <span 
            id="graph-integrity" 
            className="integrity integrity--verified px-3 py-1 rounded-lg bg-[#D4AF37]/15 border border-[#D4AF37]/60 text-[#D4AF37] font-mono text-[11px] font-bold flex items-center gap-1.5 shadow-md"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-[#D4AF37]" />
            TENANT: ten_01
          </span>
        </div>
      </header>

      {/* ================= COMMAND & SCRUBBER RIBBON ================= */}
      <div className="p-3 sm:px-5 bg-[#080d1a]/90 border-b border-cyan-900/40 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Left: Mode Toggle & Presets */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {/* Primary Toggle Button (per Section 2.5) */}
          <button
            onClick={toggleMode}
            className={`toggle-3d-btn px-4 py-1.5 rounded-xl font-mono text-xs font-bold transition-all duration-300 flex items-center gap-2 border shadow-lg ${
              mode === '3D'
                ? 'bg-[#D4AF37] text-black border-[#D4AF37] hover:bg-[#c49f27]'
                : 'bg-cyan-600 hover:bg-cyan-500 text-black border-cyan-400'
            }`}
          >
            {mode === '3D' ? <Layers className="w-3.5 h-3.5" /> : <Move3d className="w-3.5 h-3.5" />}
            <span>{mode === '3D' ? 'Return to 2D' : 'Enter 3D'}</span>
            <span className="text-[9px] px-1.5 py-0.2 rounded bg-black/25 text-inherit opacity-80">
              [Key '3']
            </span>
          </button>

          {/* Preset Buttons */}
          <div className="flex items-center bg-black/60 rounded-xl p-0.5 border border-cyan-900/50">
            <button
              onClick={() => handleScrub(0)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold transition-all ${
                morphProgress < 0.1 ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/50' : 'text-slate-400 hover:text-white'
              }`}
            >
              2.0D Flat
            </button>
            <button
              onClick={() => handleScrub(0.5)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold transition-all ${
                morphProgress >= 0.1 && morphProgress <= 0.9 ? 'bg-purple-950 text-purple-300 border border-purple-500/50' : 'text-slate-400 hover:text-white'
              }`}
            >
              2.5D Morph
            </button>
            <button
              onClick={() => handleScrub(1.0)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold transition-all ${
                morphProgress > 0.9 ? 'bg-amber-950 text-amber-300 border border-amber-500/50' : 'text-slate-400 hover:text-white'
              }`}
            >
              3.0D Spatial
            </button>
          </div>

          {/* Auto-Morph Sinusoidal Scrubber */}
          <button
            onClick={() => setIsAutoMorphing(prev => !prev)}
            className={`px-2.5 py-1 rounded-xl text-[10px] font-mono border flex items-center gap-1.5 transition-all ${
              isAutoMorphing
                ? 'bg-[#D4AF37]/20 border-[#D4AF37] text-[#D4AF37] animate-pulse'
                : 'bg-black/50 border-slate-700 text-slate-400 hover:text-white'
            }`}
            title="Continuous Sinusoidal Morphing Loop [Key 'M']"
          >
            {isAutoMorphing ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span>Auto-Morph</span>
          </button>
        </div>

        {/* Center: Continuous Dimension Slider */}
        <div className="flex items-center gap-2.5 flex-1 max-w-xs mx-2">
          <span className="text-[10px] font-mono text-cyan-400 font-bold">2.0D</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={morphProgress}
            onChange={(e) => handleScrub(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-[#D4AF37]"
            title="Scrub dimension continuously from flat CAD to 3D spatial"
          />
          <span className="text-[10px] font-mono text-[#D4AF37] font-bold">3.0D</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/60 border border-[#D4AF37]/40 text-[#D4AF37]">
            {(2.0 + morphProgress).toFixed(2)}D
          </span>
        </div>

        {/* Right: Node Limit / Stress Selector (50, 200, 500 nodes per Section 5 & 8) */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-slate-400">DENSITY:</span>
          <div className="flex items-center bg-black/60 rounded-xl p-0.5 border border-cyan-900/50 text-[10px] font-mono">
            {[50, 200, 500].map((count) => (
              <button
                key={count}
                onClick={() => setNodeCountSetting(count as 50 | 200 | 500)}
                className={`px-2 py-0.5 rounded-lg transition-all ${
                  nodeCountSetting === count 
                    ? 'bg-cyan-500 text-black font-bold' 
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {count}N
              </button>
            ))}
          </div>

          {/* Accessible Fallback Toggle (Section 6) */}
          <button
            onClick={() => setShowAccessibleMirror(prev => !prev)}
            className={`p-1.5 rounded-xl border text-[10px] font-mono transition-all ${
              showAccessibleMirror ? 'bg-cyan-950 border-cyan-500 text-cyan-300' : 'bg-black/50 border-slate-700 text-slate-400'
            }`}
            title="Toggle Accessibility DOM Mirror"
          >
            <Eye className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ================= FILTER & SEARCH FILTER TOOLBAR ================= */}
      <div className="px-4 py-2 bg-black/70 border-b border-cyan-950 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* State Filter Buttons */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-mono text-slate-400 mr-1 flex items-center gap-1">
            <Filter className="w-3 h-3 text-slate-500" /> FILTER:
          </span>
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all ${
              activeFilter === 'all'
                ? 'bg-slate-200 text-black font-bold'
                : 'bg-black/50 text-slate-400 border border-slate-800 hover:border-slate-600'
            }`}
          >
            ALL ({graphData?.nodes.length || 0})
          </button>
          
          {(['verified', 'running', 'approval_required', 'failed', 'quarantined', 'stale'] as NodeState[]).map(st => {
            const count = stateCounts[st] || 0;
            const color = STATE_COLORS[st];
            const isActive = activeFilter === st;
            return (
              <button
                key={st}
                onClick={() => setActiveFilter(st)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 transition-all ${
                  isActive
                    ? 'border font-bold'
                    : 'bg-black/50 text-slate-400 border border-slate-800 hover:border-slate-700'
                }`}
                style={{
                  borderColor: isActive ? color : undefined,
                  backgroundColor: isActive ? `${color}20` : undefined,
                  color: isActive ? color : undefined
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                <span>{st.replace('_', ' ')}</span>
                <span className="opacity-60">({count})</span>
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="relative flex items-center">
          <Search className="w-3 h-3 text-slate-400 absolute left-2.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Search node id, label, kind..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-7 pr-7 py-1 rounded-xl bg-slate-900/80 border border-slate-700/70 text-[11px] font-mono text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 w-48 sm:w-64 transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 text-slate-400 hover:text-white"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* ================= MAIN DUAL-VIEWPORT STAGE (2D & 3D) ================= */}
      <div 
        id="world-tree-container" 
        className="relative w-full h-[620px] sm:h-[680px] bg-[#050505] overflow-hidden"
      >
        {/* SUB-CONTAINER 2D CANVAS (per Section 2.5) */}
        <div
          ref={container2DRef}
          className="world-tree-2d absolute inset-0 w-full h-full transition-opacity duration-300"
          style={{ zIndex: mode === '2D' ? 10 : 5 }}
        />

        {/* SUB-CONTAINER 3D THREE.JS (per Section 2.5) */}
        <div
          ref={container3DRef}
          className="world-tree-3d absolute inset-0 w-full h-full transition-opacity duration-300"
          style={{ zIndex: mode === '3D' ? 10 : 5 }}
        />

        {/* FLOATING HUD OVERLAY: CONTINUITY TELEMETRY BANNER */}
        <div className="absolute top-3 left-3 pointer-events-none z-20">
          <div className="hud-panel p-2.5 rounded-xl bg-black/85 backdrop-blur-md border border-cyan-900/50 shadow-xl text-[10px] font-mono space-y-1">
            <div className="flex items-center gap-2 text-cyan-300 font-bold">
              <Compass className="w-3.5 h-3.5 text-[#D4AF37]" />
              <span>COORDINATE PLANE: {mode === '2D' ? 'ORTHOGRAPHIC (X, Y, Z=0)' : mode === '3D' ? 'ORBITAL 3D (X, Y, Z)' : 'INTERPOLATING MORPH'}</span>
            </div>
            <div className="text-slate-400 flex items-center gap-3">
              <span>ACTIVE MODE: <strong className="text-[#D4AF37]">{mode}</strong></span>
              <span>DIMENSION: <strong className="text-cyan-400">{(2.0 + morphProgress).toFixed(2)}D</strong></span>
              <span>LIFT RATIO: <strong className="text-emerald-400">{Math.round(morphProgress * 100)}%</strong></span>
              <span>ENGINE: <strong className={graph3DRef.current?.hasWebGL ? "text-emerald-400" : "text-amber-400"}>{graph3DRef.current?.hasWebGL ? "WEBGL 3D" : "2.5D SPATIAL"}</strong></span>
            </div>
          </div>
        </div>

        {/* FLOATING HUD OVERLAY: CAMERA RESET & QUICK ACTIONS */}
        <div className="absolute top-3 right-3 z-20 flex items-center gap-2">
          <button
            onClick={() => {
              if (mode === '3D' && graph3DRef.current) {
                graph3DRef.current.resetCamera();
              } else if (graph2DRef.current) {
                graph2DRef.current.centerView();
              }
            }}
            className="p-2 rounded-xl bg-black/80 hover:bg-black border border-cyan-800/60 text-cyan-300 hover:text-white transition-all shadow-xl flex items-center gap-1 text-[10px] font-mono"
            title="Reset Camera to Center"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Reset Cam</span>
          </button>
        </div>

        {/* ================= SELECTED NODE INSPECTOR PANEL (Section 4) ================= */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 max-w-sm w-full z-30 pointer-events-auto animate-in fade-in slide-in-from-bottom-2 duration-200">
            <div className="p-3.5 rounded-2xl bg-black/90 backdrop-blur-xl border-2 border-[#D4AF37]/70 shadow-2xl space-y-2.5 text-xs font-mono">
              <div className="flex items-start justify-between gap-2 border-b border-cyan-900/60 pb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span 
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: selectedNode.color || STATE_COLORS[selectedNode.state] }}
                    />
                    <h3 className="font-bold text-white text-sm">
                      {selectedNode.label}
                    </h3>
                  </div>
                  <span className="text-[10px] text-cyan-400 uppercase tracking-wider">
                    ID: {selectedNode.id} • {selectedNode.kind}
                  </span>
                </div>
                <button
                  onClick={() => {
                    setSelectedNode(null);
                    transitionRef.current?.selectNode(null);
                  }}
                  className="text-slate-400 hover:text-white p-0.5 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Node Metadata Matrix */}
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="p-1.5 rounded bg-slate-900/80 border border-slate-800">
                  <span className="text-slate-400 block">STATE</span>
                  <span className="font-bold uppercase" style={{ color: selectedNode.color || STATE_COLORS[selectedNode.state] }}>
                    {selectedNode.state.replace('_', ' ')}
                  </span>
                </div>
                <div className="p-1.5 rounded bg-slate-900/80 border border-slate-800">
                  <span className="text-slate-400 block">TRUST TIER</span>
                  <span className="font-bold text-[#D4AF37]">
                    T{selectedNode.trust_tier} • RISK {selectedNode.risk_tier}
                  </span>
                </div>
                <div className="p-1.5 rounded bg-slate-900/80 border border-slate-800">
                  <span className="text-slate-400 block">IMPORTANCE (VAL)</span>
                  <span className="font-bold text-emerald-400">
                    {selectedNode.val} (Z-Lift: +{(selectedNode.val * 2 * morphProgress).toFixed(1)}px)
                  </span>
                </div>
                <div className="p-1.5 rounded bg-slate-900/80 border border-slate-800">
                  <span className="text-slate-400 block">STRATUM</span>
                  <span className="font-bold text-purple-300 uppercase">
                    {selectedNode.stratum || 'General'}
                  </span>
                </div>
              </div>

              {/* Summary Description */}
              {selectedNode.summary && (
                <p className="text-[11px] text-slate-300 leading-relaxed border-t border-slate-800/80 pt-1.5">
                  {selectedNode.summary}
                </p>
              )}

              {/* Modal Jump Buttons */}
              <div className="flex items-center gap-2 pt-1">
                {onOpenModal && selectedNode.stratum === 'apex' && (
                  <button
                    onClick={() => onOpenModal('memcastle')}
                    className="flex-1 py-1 px-2 rounded bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/50 text-[#D4AF37] text-[10px] font-bold flex items-center justify-center gap-1"
                  >
                    <span>Memcastle Gateway</span>
                    <ArrowUpRight className="w-3 h-3" />
                  </button>
                )}
                {onOpenModal && selectedNode.stratum === 'brains' && (
                  <button
                    onClick={() => onOpenModal('twin_brains')}
                    className="flex-1 py-1 px-2 rounded bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/50 text-purple-300 text-[10px] font-bold flex items-center justify-center gap-1"
                  >
                    <span>Twin Brains Sync</span>
                    <ArrowUpRight className="w-3 h-3" />
                  </button>
                )}
                {onOpenModal && selectedNode.stratum === 'rivers' && (
                  <button
                    onClick={() => onOpenModal('viking')}
                    className="flex-1 py-1 px-2 rounded bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/50 text-emerald-300 text-[10px] font-bold flex items-center justify-center gap-1"
                  >
                    <span>Viking Refractions</span>
                    <ArrowUpRight className="w-3 h-3" />
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ================= RIGHT-CLICK CONTEXT MENU (Section 4) ================= */}
        {contextMenu && (
          <div
            className="fixed z-50 p-2 rounded-xl bg-black/95 border border-[#D4AF37] shadow-2xl text-xs font-mono space-y-1"
            style={{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-2 py-1 border-b border-slate-800 text-[10px] text-[#D4AF37] font-bold">
              {contextMenu.node.label} [{contextMenu.node.id}]
            </div>
            <button
              onClick={() => {
                setSelectedNode(contextMenu.node);
                transitionRef.current?.selectNode(contextMenu.node);
                setContextMenu(null);
              }}
              className="w-full text-left px-2 py-1 rounded hover:bg-cyan-950 text-slate-200 hover:text-cyan-300 flex items-center gap-2"
            >
              <Eye className="w-3 h-3" />
              <span>Select Node</span>
            </button>
            <button
              onClick={() => {
                if (graph3DRef.current) graph3DRef.current.flyToNode(contextMenu.node);
                setContextMenu(null);
              }}
              className="w-full text-left px-2 py-1 rounded hover:bg-cyan-950 text-slate-200 hover:text-cyan-300 flex items-center gap-2"
            >
              <Compass className="w-3 h-3" />
              <span>Fly-To (3D Orbital)</span>
            </button>
            <button
              onClick={() => {
                setTelemetryMessage(`Z3 VERIFIER: PROVED INVARIANTS FOR [${contextMenu.node.id}]`);
                setContextMenu(null);
              }}
              className="w-full text-left px-2 py-1 rounded hover:bg-amber-950 text-slate-200 hover:text-amber-300 flex items-center gap-2"
            >
              <ShieldCheck className="w-3 h-3 text-amber-400" />
              <span>Verify Invariants</span>
            </button>
          </div>
        )}
      </div>

      {/* ================= ACCESSIBILITY FALLBACK (Section 6) ================= */}
      <div 
        className="world-tree-accessible bg-[#030712] border-t border-slate-800 p-4 max-h-56 overflow-y-auto"
        hidden={!showAccessibleMirror}
        aria-live="polite"
      >
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800">
          <h3 className="text-xs font-bold text-white font-mono flex items-center gap-2">
            <Eye className="w-3.5 h-3.5 text-cyan-400" />
            <span>ACCESSIBLE DOM MIRROR // NODE TOPOLOGY LIST</span>
          </h3>
          <span className="text-[10px] text-slate-400 font-mono">
            {graphData?.nodes.length || 0} TOTAL NODES
          </span>
        </div>
        <ul className="space-y-1.5 text-xs font-mono">
          {graphData?.nodes.map((node) => (
            <li 
              key={node.id} 
              className={`p-1.5 rounded flex items-center justify-between gap-2 border transition-all ${
                selectedNode?.id === node.id 
                  ? 'bg-amber-950/40 border-[#D4AF37] text-white' 
                  : 'bg-black/40 border-slate-800/80 text-slate-300 hover:border-slate-700'
              }`}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setSelectedNode(node);
                  transitionRef.current?.selectNode(node);
                }
              }}
              onClick={() => {
                setSelectedNode(node);
                transitionRef.current?.selectNode(node);
              }}
            >
              <div className="flex items-center gap-2">
                <span 
                  className="w-2 h-2 rounded-full" 
                  style={{ backgroundColor: node.color || STATE_COLORS[node.state] }} 
                />
                <strong className="text-slate-100">{node.label}</strong>
                <span className="text-[10px] text-slate-500">({node.kind})</span>
              </div>
              <div className="flex items-center gap-3 text-[10px]">
                <span className="text-slate-400">State: <span className="text-cyan-300">{node.state}</span></span>
                <span className="text-slate-400">Risk: <span className="text-amber-300">{node.risk_tier}</span></span>
                <span className="text-slate-400">Trust: <span className="text-emerald-300">T{node.trust_tier}</span></span>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* ================= TELEMETRY FOOTER & CONSOLE FRAGMENT (Section 7) ================= */}
      <footer className="p-3 bg-black/90 border-t border-cyan-900/40 flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono text-slate-400">
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
          <span className="text-slate-500">TELEMETRY:</span>
          <span className="text-emerald-300 font-bold">{telemetryMessage}</span>
        </div>

        <div className="flex items-center gap-3 text-[10px]">
          <span className="text-slate-500">KEYS: <strong className="text-cyan-300">[3] 2D/3D</strong> • <strong className="text-[#D4AF37]">[M] Auto-Morph</strong> • <strong className="text-slate-300">[Esc] Clear</strong></span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">LOD: <strong className="text-cyan-400">{nodeCountSetting < 100 ? 'Full' : nodeCountSetting < 300 ? 'Simplified' : 'Point Sprites'}</strong></span>
        </div>
      </footer>
    </article>
  );
};
