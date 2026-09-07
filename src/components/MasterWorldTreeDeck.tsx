import React, { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, 
  Volume2, 
  VolumeX, 
  Compass, 
  Maximize2, 
  Minimize2,
  Activity, 
  ShieldCheck, 
  Layers, 
  Terminal, 
  RefreshCw, 
  Zap, 
  Eye, 
  EyeOff,
  Radio, 
  Play, 
  RotateCw,
  Cpu,
  Database,
  Network,
  Minus,
  Plus,
  Lock,
  Unlock,
  Key,
  Flame,
  Binary,
  Anchor,
  HelpCircle,
  Brain,
  Github,
  ExternalLink,
  TreeDeciduous,
  CheckCircle2,
  SlidersHorizontal,
  Move3d,
  Orbit,
  ArrowUpRight,
  ChevronDown,
  ChevronUp,
  Sliders,
  Heart,
  Gauge,
  Server,
  Columns2,
  Pause
} from 'lucide-react';
import { ThreeWorldTreeScene } from './ThreeWorldTreeScene';
import { WorldTreeVisual } from './WorldTreeVisual';
import { audioEngine } from '../utils/audioEngine';
import { MemcastleModal } from './MemcastleModal';
import { TwinBrainsModal } from './TwinBrainsModal';
import { VikingRefractionsModal } from './VikingRefractionsModal';
import { WorldTreeHUD } from './worldtree/WorldTreeHUD';
import { SovereignWorldTreeScrollingExperience } from './SovereignWorldTreeScrollingExperience';
import { Interactive3DShowcase } from './Interactive3DShowcase';
import { FixedThreeUiOverlay } from './FixedThreeUiOverlay';

interface MasterWorldTreeDeckProps {
  vitals?: any;
  onOpenTerminalModal?: () => void;
  onNavigateTab?: (tab: string) => void;
  onExecuteCommand?: (cmd: string) => void;
}

// 4 Distinct World Tree Strata mapped along the scroll journey
interface StratumConfig {
  id: string;
  name: string;
  subTitle: string;
  altitude: string;
  scrollStart: number;
  scrollEnd: number;
  targetScroll: number; // 0 to 1
  icon: string;
  rotX: number;
  rotY: number;
  panYPercent: number;
  zoomScale: number;
  themeColor: string;
  accentBorder: string;
}

const STRATA: StratumConfig[] = [
  {
    id: 'apex',
    name: 'Apex Memcastle & Celestial Spires',
    subTitle: '/vfs/mempalace/* • Zero-Trust Gateways • Port 6379',
    altitude: '+4500m',
    scrollStart: 0.0,
    scrollEnd: 0.28,
    targetScroll: 0.05,
    icon: '⚜️',
    rotX: 13,
    rotY: -8,
    panYPercent: 12,
    zoomScale: 1.08,
    themeColor: '#D4AF37',
    accentBorder: 'rgba(212, 175, 55, 0.6)'
  },
  {
    id: 'brains',
    name: 'Cognitive Canopy & Twin Brains',
    subTitle: 'Open-Notebook (8502) ⟷ NotebookLM Cognitive Sink',
    altitude: '+2800m',
    scrollStart: 0.28,
    scrollEnd: 0.58,
    targetScroll: 0.42,
    icon: '🧠',
    rotX: 17,
    rotY: -13,
    panYPercent: -15,
    zoomScale: 1.15,
    themeColor: '#C084FC',
    accentBorder: 'rgba(192, 132, 252, 0.6)'
  },
  {
    id: 'ouroboros',
    name: 'Axis Trunk & Ouroboros SSM',
    subTitle: '1.58-Bit Ternary Recurrent Loop • W_ij ∈ {-1,0,1}',
    altitude: '+1200m',
    scrollStart: 0.58,
    scrollEnd: 0.82,
    targetScroll: 0.70,
    icon: '⚡',
    rotX: 20,
    rotY: 10,
    panYPercent: -42,
    zoomScale: 1.20,
    themeColor: '#F59E0B',
    accentBorder: 'rgba(245, 158, 11, 0.6)'
  },
  {
    id: 'rivers',
    name: 'Ancient Roots & Emerald Data Rivers',
    subTitle: '/vfs/refractions/* • Viking Drakkar DMA Buffers',
    altitude: '+0000m',
    scrollStart: 0.82,
    scrollEnd: 1.0,
    targetScroll: 0.95,
    icon: '⚓',
    rotX: 11,
    rotY: 4,
    panYPercent: -68,
    zoomScale: 1.12,
    themeColor: '#10B981',
    accentBorder: 'rgba(16, 185, 129, 0.6)'
  }
];

export const MasterWorldTreeDeck: React.FC<MasterWorldTreeDeckProps> = ({
  vitals,
  onOpenTerminalModal,
  onNavigateTab,
  onExecuteCommand
}) => {
  // Continuity Architecture State
  // Continuity Layout: 'showcase' (Gemini 3.8 Flash Interactive 3D Showcase) | 'scroller' (Scrolling Interactive UI of 7 Pictures) | 'hud' (Continuous 2D ➔ 3D HUD) | 'unified' (Morphing Canvas) | 'split' (Dual-Sync) | 'overlay' (Fixed Canvas + Pass-Through UI Overlay)
  const [continuityLayout, setContinuityLayout] = useState<'showcase' | 'scroller' | 'hud' | 'unified' | 'split' | 'overlay'>('showcase');

  // Continuous Dimension Factor: 0.00 (2.0D Flat Blueprint) to 1.00 (3.0D Spatial WebGL)
  const [dimensionBlend, setDimensionBlend] = useState<number>(0.75);

  // Auto-Morph Cinema Loop: continuous sinusoidal breath between 2D and 3D
  const [isAutoMorphing, setIsAutoMorphing] = useState<boolean>(false);

  // Scroll-Driven Morphing: page scroll unfolds the third dimension
  const [isScrollMorphEnabled, setIsScrollMorphEnabled] = useState<boolean>(false);

  // 2D Architectural Blueprint & Elevation Wireframe Overlay
  const [showBlueprintWireframe, setShowBlueprintWireframe] = useState<boolean>(true);

  // WebGL 3D Three.js Engine visibility
  const [enableThreeWebGL, setEnableThreeWebGL] = useState<boolean>(true);

  // Dimension Z-Depth scale multiplier
  const [depthScale, setDepthScale] = useState<number>(85);

  // Auto Kinetic Orbit Camera in 3D CSS space
  const [isKineticOrbiting, setIsKineticOrbiting] = useState<boolean>(false);

  // Sound & Parallax
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [parallaxEnabled, setParallaxEnabled] = useState(true);
  const [energyPulseTrigger, setEnergyPulseTrigger] = useState(0);

  // Active Modals
  const [activeModal, setActiveModal] = useState<'memcastle' | 'twin_brains' | 'viking' | null>(null);

  // Parallax Mouse tilt state
  const [mouseTilt, setMouseTilt] = useState({ x: 0, y: 0 });

  // Cinema Mode
  const [cinemaMode, setCinemaMode] = useState(false);

  // Solfeggio Tuner
  const [secretFrequency, setSecretFrequency] = useState(528);

  // Action Feedback Banner
  const [recentActionMsg, setRecentActionMsg] = useState<string | null>(null);

  // Scroll Progress State [0.00 to 1.00]
  const [scrollProgress, setScrollProgress] = useState<number>(0);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  // =========================================================================
  // WORLD TREE RESPIRATION & MEMORY SYNCHRONIZATION ENGINE
  // Pulse/Breathe cycle synchronizes with system memory usage, slowing down
  // as the system approaches its 8GB capacity limit.
  // =========================================================================
  const [breatheModeActive, setBreatheModeActive] = useState<boolean>(true);
  const [simulatedRamMB, setSimulatedRamMB] = useState<number | null>(null);
  const [showRespirationPanel, setShowRespirationPanel] = useState<boolean>(false);

  const capacityMB = vitals?.scarcityCapMB || 8192; // 8GB Boundary
  const activeUsedRamMB = simulatedRamMB !== null 
    ? simulatedRamMB 
    : (vitals?.usedRamMB ?? 4890);

  const ramRatio = Math.min(Math.max(activeUsedRamMB / capacityMB, 0.08), 0.995);
  const ramPercent = Math.round(ramRatio * 100);

  // Respiration formula:
  // Light memory (~15-25%): 2.2s - 2.8s swift pulse (lively, agile)
  // Nominal memory (~60%): 4.6s - 5.0s steady rhythmic cadence
  // Heavy memory (~85%): 8.0s - 9.0s deep, heavy respiration
  // Critical memory near 8GB limit (~98%): 12.0s - 13.5s massive slow heave
  const breatheDurationSec = 2.0 + Math.pow(ramRatio, 1.85) * 11.0;
  const breatheDurationCss = `${breatheDurationSec.toFixed(2)}s`;
  const breathsPerMinute = Math.round(60 / breatheDurationSec);

  // Glow color & depth shift with 8GB scarcity pressure
  const breatheGlowColor = ramRatio > 0.88 
    ? 'rgba(239, 68, 68, 0.75)' // Emergency red/crimson near 8GB limit
    : ramRatio > 0.72 
      ? 'rgba(245, 158, 11, 0.7)' // Amber heavy pressure
      : ramRatio > 0.45 
        ? 'rgba(212, 175, 55, 0.65)' // Luxora Gold nominal
        : 'rgba(34, 211, 238, 0.65)'; // Cyan agile light

  const breatheScale = (1.025 + ramRatio * 0.035).toFixed(3);
  const breatheZ = Math.round(12 + ramRatio * 18);

  // Sound Engine Sync
  useEffect(() => {
    audioEngine.setEnabled(soundEnabled);
  }, [soundEnabled]);

  // Auto-Morph Sinusoidal Cinema Loop: smoothly glides dimensionBlend between 0.05 and 0.95
  useEffect(() => {
    if (!isAutoMorphing) return;
    let animId: number;
    const cycleDurationMs = 9000; // 9 second breathing oscillation
    const startTime = performance.now();

    const morphLoop = (now: number) => {
      const elapsed = (now - startTime) % cycleDurationMs;
      const t = elapsed / cycleDurationMs;
      // Sinusoidal easing: 0 -> 1 -> 0
      const currentBlend = (Math.sin(t * Math.PI * 2 - Math.PI / 2) + 1) / 2;
      setDimensionBlend(Number(currentBlend.toFixed(3)));
      animId = requestAnimationFrame(morphLoop);
    };

    animId = requestAnimationFrame(morphLoop);
    return () => cancelAnimationFrame(animId);
  }, [isAutoMorphing]);

  // Handle Scroll Progress smoothly using requestAnimationFrame
  useEffect(() => {
    let animationFrameId: number;

    const handleScroll = () => {
      animationFrameId = window.requestAnimationFrame(() => {
        if (!scrollContainerRef.current) return;
        const rect = scrollContainerRef.current.getBoundingClientRect();
        const totalHeight = scrollContainerRef.current.scrollHeight - window.innerHeight;
        
        if (totalHeight <= 0) {
          setScrollProgress(0);
          return;
        }

        // Calculate progress based on scroll position of container relative to viewport
        const currentTop = -rect.top;
        const rawProgress = currentTop / totalHeight;
        const clampedProgress = Math.min(Math.max(rawProgress, 0), 1);
        setScrollProgress(clampedProgress);

        if (isScrollMorphEnabled) {
          // As you descend the tree (0 to 1), dimension blend smoothly unfolds from 0.05 to 1.00
          setDimensionBlend(Number((0.05 + clampedProgress * 0.95).toFixed(3)));
        }
      });
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.cancelAnimationFrame(animationFrameId);
    };
  }, [continuityLayout, isScrollMorphEnabled]);

  // Keyboard shortcut: 'c' for cinema, '3' for 3D toggle, 'b' for breathe toggle, 'm' for auto-morph
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;
      
      if (e.key === 'c' || e.key === 'C') {
        audioEngine.playClick();
        setCinemaMode((prev) => !prev);
      }
      if (e.key === '3') {
        audioEngine.playClick();
        handleToggleDimensionalMode();
      }
      if (e.key === 'm' || e.key === 'M') {
        audioEngine.playClick();
        setIsAutoMorphing((prev) => !prev);
      }
      if (e.key === 'b' || e.key === 'B') {
        audioEngine.playClick();
        setBreatheModeActive((prev) => !prev);
        showFeedback(breatheModeActive ? 'World Tree Breathe: Paused' : 'World Tree Breathe: Synchronized with 8GB RAM');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [dimensionBlend, breatheModeActive, isAutoMorphing]);

  // Parallax tracking
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!parallaxEnabled || dimensionBlend < 0.1 || isKineticOrbiting) return;
    const { clientX, clientY, currentTarget } = e;
    const rect = currentTarget.getBoundingClientRect();
    const xRatio = (clientX - rect.left) / rect.width - 0.5;
    const yRatio = (clientY - rect.top) / rect.height - 0.5;
    setMouseTilt({ x: xRatio * 10, y: -yRatio * 10 });
  };

  const handleMouseLeave = () => {
    if (dimensionBlend < 0.1 || isKineticOrbiting) return;
    setMouseTilt({ x: 0, y: 0 });
  };

  // Toggle Dimensional Mode (2D <-> 3D)
  const handleToggleDimensionalMode = () => {
    audioEngine.playClick();
    setIsAutoMorphing(false);
    setIsScrollMorphEnabled(false);
    if (dimensionBlend < 0.5) {
      setDimensionBlend(1.0);
      setDepthScale(85);
      showFeedback('DIMENSIONAL EXPANSION: 3.0D SPATIAL SCROLL MATRIX ENGAGED');
    } else {
      setDimensionBlend(0.0);
      setDepthScale(0);
      setIsKineticOrbiting(false);
      setMouseTilt({ x: 0, y: 0 });
      showFeedback('ORTHOGRAPHIC LOCK: 2.0D FLAT MATRIX RESTORED');
    }
  };

  // Scroll smoothly to a specific stratum
  const scrollToStratum = (targetProgress: number) => {
    audioEngine.playClick();
    if (!scrollContainerRef.current) return;
    const totalHeight = scrollContainerRef.current.scrollHeight - window.innerHeight;
    const targetScrollY = scrollContainerRef.current.offsetTop + (totalHeight * targetProgress);
    window.scrollTo({
      top: targetScrollY,
      behavior: 'smooth'
    });
  };

  // Trigger Ouroboros State Pulse
  const handleOuroborosTrigger = () => {
    audioEngine.playStatePulse();
    setEnergyPulseTrigger((prev) => prev + 1);
    showFeedback('⚡ OUROBOROS SSM: 1.58-BIT TERNARY STATE LOOP PULSED');
    if (onExecuteCommand) {
      onExecuteCommand('ouroboros --pulse-ssm --ternary-step');
    }
  };

  const showFeedback = (msg: string) => {
    setRecentActionMsg(msg);
    setTimeout(() => {
      setRecentActionMsg((cur) => (cur === msg ? null : cur));
    }, 3200);
  };

  // Determine current active stratum
  const currentStratum = STRATA.find(
    (s) => scrollProgress >= s.scrollStart && scrollProgress <= s.scrollEnd
  ) || STRATA[0];

  // Interpolate camera parameters smoothly across strata
  const getInterpolatedCamera = () => {
    if (dimensionBlend < 0.05) {
      const panY = 10 - scrollProgress * 75;
      return { rotX: 0, rotY: 0, panY, scale: 1.05 };
    }

    let sIndex = 0;
    for (let i = 0; i < STRATA.length - 1; i++) {
      if (scrollProgress >= STRATA[i].scrollStart && scrollProgress <= STRATA[i + 1].scrollStart) {
        sIndex = i;
        break;
      }
      if (i === STRATA.length - 2) sIndex = i;
    }

    const sA = STRATA[sIndex];
    const sB = STRATA[sIndex + 1] || sA;
    const segRange = (sB.scrollStart - sA.scrollStart) || 0.3;
    const t = Math.min(Math.max((scrollProgress - sA.scrollStart) / segRange, 0), 1);

    const rotX = sA.rotX + (sB.rotX - sA.rotX) * t;
    const rotY = sA.rotY + (sB.rotY - sA.rotY) * t;
    const panY = sA.panYPercent + (sB.panYPercent - sA.panYPercent) * t;
    const scale = sA.zoomScale + (sB.zoomScale - sA.zoomScale) * t;

    return { rotX, rotY, panY, scale };
  };

  const camera = getInterpolatedCamera();
  const dFactor = dimensionBlend * (depthScale / 100);

  // Final 3D rotation with optional mouse parallax, continuous with dimensionBlend
  const finalRotX = isKineticOrbiting ? 0 : (camera.rotX * dimensionBlend) + (parallaxEnabled ? mouseTilt.y * dimensionBlend : 0);
  const finalRotY = isKineticOrbiting ? 0 : (camera.rotY * dimensionBlend) + (parallaxEnabled ? mouseTilt.x * dimensionBlend : 0);
  const perspectiveCss = dimensionBlend < 0.03 ? 'none' : `${Math.round(2800 - dimensionBlend * 1600)}px`;
  const blueprintOpacity = showBlueprintWireframe ? Math.max(0.12, 1 - dimensionBlend * 0.45) : 0;

  return (
    <div 
      ref={scrollContainerRef}
      className="relative w-full bg-[#050505] text-slate-100 font-mono select-none overflow-x-hidden min-h-[320vh]"
    >
      {/* ================= FIXED TOP STATUS & CONTROLS BAR ================= */}
      <div className="fixed top-0 inset-x-0 z-40 bg-[#050505]/95 border-b border-[#D4AF37]/30 px-3 sm:px-5 py-2 flex flex-wrap items-center justify-between gap-3 text-xs shadow-2xl backdrop-blur-xl">
        
        {/* Left: Brand Identity & Active Stratum Readout */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] animate-pulse"></span>
            <span className="font-bold text-[#D4AF37] tracking-wider text-sm flex items-center gap-1.5">
              <span>Ω_EXCALIBUR_V1000</span>
              <span className="text-slate-600 text-xs">•</span>
              <span className="text-cyan-300 font-sans font-semibold text-xs">SCROLL 3D WORLD TREE</span>
            </span>
          </div>

          <span className="text-slate-700 hidden md:inline">|</span>

          {/* Active Stratum Indicator */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-black/80 border border-[#D4AF37]/40 text-[11px]">
            <span>{currentStratum.icon}</span>
            <span className="text-[#D4AF37] font-bold uppercase">{currentStratum.name.split('&')[0]}</span>
            <span className="text-slate-500 font-mono text-[10px]">
              [{Math.round(scrollProgress * 100)}%]
            </span>
          </div>

          {/* 2D to 3D Dimension Continuity Control Hub */}
          <div className="flex items-center gap-1.5 bg-black/90 p-1 rounded-xl border border-[#D4AF37]/50 shadow-[0_0_20px_rgba(212,175,55,0.2)]">
            <div className="flex items-center gap-1 px-1.5 py-0.5">
              <Move3d className="w-3.5 h-3.5 text-[#D4AF37]" />
              <span className="text-[10px] font-extrabold text-[#D4AF37] tracking-wider uppercase hidden xl:inline">
                CONTINUITY:
              </span>
              <span className="text-[11px] font-extrabold text-cyan-300 font-mono">
                {(2.0 + dimensionBlend).toFixed(2)}D
              </span>
            </div>

            {/* Discrete Dimension Presets */}
            <div className="flex items-center gap-0.5 bg-slate-950 p-0.5 rounded-lg border border-slate-800">
              <button
                onClick={() => {
                  setIsAutoMorphing(false);
                  setIsScrollMorphEnabled(false);
                  setDimensionBlend(0.0);
                  setDepthScale(0);
                  showFeedback('2.0D BLUEPRINT: Orthographic planar projection active');
                }}
                className={`px-2 py-0.5 rounded text-[9px] font-bold transition-all cursor-pointer ${
                  dimensionBlend < 0.15
                    ? 'bg-gradient-to-r from-cyan-600 to-emerald-600 text-white shadow-[0_0_12px_rgba(34,211,238,0.5)]'
                    : 'text-slate-400 hover:text-cyan-300'
                }`}
                title="2.0D Blueprint: Flat orthographic CAD view without perspective distortion"
              >
                2.0D
              </button>
              <button
                onClick={() => {
                  setIsAutoMorphing(false);
                  setIsScrollMorphEnabled(false);
                  setDimensionBlend(0.5);
                  setDepthScale(55);
                  showFeedback('2.5D ISOMETRIC: Stratum relief extrusion active');
                }}
                className={`px-2 py-0.5 rounded text-[9px] font-bold transition-all cursor-pointer ${
                  dimensionBlend >= 0.35 && dimensionBlend <= 0.65
                    ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-[0_0_12px_rgba(168,85,247,0.5)]'
                    : 'text-slate-400 hover:text-purple-300'
                }`}
                title="2.5D Isometric Relief: Layered depth elevation with subtle parallax"
              >
                2.5D
              </button>
              <button
                onClick={() => {
                  setIsAutoMorphing(false);
                  setIsScrollMorphEnabled(false);
                  setDimensionBlend(1.0);
                  setDepthScale(85);
                  showFeedback('3.0D SPATIAL: Full stereoscopic WebGL volumetric matrix engaged');
                }}
                className={`px-2 py-0.5 rounded text-[9px] font-bold transition-all cursor-pointer ${
                  dimensionBlend > 0.85
                    ? 'bg-gradient-to-r from-[#D4AF37] via-amber-500 to-[#2E0854] text-black font-extrabold shadow-[0_0_15px_rgba(212,175,55,0.6)]'
                    : 'text-slate-400 hover:text-[#D4AF37]'
                }`}
                title="3.0D Spatial: Full stereoscopic perspective chamber with WebGL particles"
              >
                3.0D
              </button>
            </div>

            {/* Continuous Continuity Slider */}
            <div className="flex items-center gap-1.5 w-20 sm:w-28 xl:w-32 px-1">
              <span className="text-[8px] text-slate-500 font-mono">2D</span>
              <input 
                type="range"
                min="0"
                max="100"
                step="1"
                value={Math.round(dimensionBlend * 100)}
                onChange={(e) => {
                  setIsAutoMorphing(false);
                  setIsScrollMorphEnabled(false);
                  setDimensionBlend(Number(e.target.value) / 100);
                }}
                className="w-full h-1.5 accent-[#D4AF37] bg-slate-800 rounded-lg cursor-pointer"
                title="Slide to smoothly morph continuously between 2D Blueprint and 3D Volumetric Mesh"
              />
              <span className="text-[8px] text-slate-500 font-mono">3D</span>
            </div>

            {/* Auto-Morph Cinema Loop */}
            <button
              onClick={() => {
                const next = !isAutoMorphing;
                setIsAutoMorphing(next);
                if (next) {
                  setIsScrollMorphEnabled(false);
                  showFeedback('AUTO-MORPH CINEMA: Continuous 2D ⟷ 3D respiration loop engaged');
                } else {
                  showFeedback('Auto-Morph paused');
                }
              }}
              className={`px-2 py-1 rounded-lg text-[9px] font-extrabold flex items-center gap-1 border transition-all cursor-pointer ${
                isAutoMorphing
                  ? 'bg-gradient-to-r from-purple-600 to-amber-500 text-white border-amber-300 shadow-[0_0_15px_rgba(245,158,11,0.5)] animate-pulse'
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-white'
              }`}
              title="Toggle continuous sinusoidal morph loop between 2D and 3D (Press 'M')"
            >
              <Sparkles className="w-3 h-3 text-amber-300" />
              <span>{isAutoMorphing ? 'AUTO-MORPH' : 'MORPH'}</span>
            </button>

            {/* Scroll Unfurl Toggle */}
            <button
              onClick={() => {
                const next = !isScrollMorphEnabled;
                setIsScrollMorphEnabled(next);
                if (next) {
                  setIsAutoMorphing(false);
                  showFeedback('SCROLL-MORPH: Yggdrasil descent dynamically unfolds 2D into 3D!');
                } else {
                  showFeedback('Scroll-Morph disengaged');
                }
              }}
              className={`hidden md:flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-bold border transition-all cursor-pointer ${
                isScrollMorphEnabled
                  ? 'bg-cyan-950 border-cyan-400 text-cyan-200 shadow-[0_0_12px_rgba(34,211,238,0.4)]'
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
              title="Map vertical scroll position down the tree to dimensional emergence"
            >
              <SlidersHorizontal className="w-3 h-3" />
              <span>{isScrollMorphEnabled ? 'UNFURL ON' : 'UNFURL'}</span>
            </button>
          </div>

          {/* Blueprint Wireframe Grid Toggle */}
          <button
            onClick={() => {
              setShowBlueprintWireframe(!showBlueprintWireframe);
              showFeedback(showBlueprintWireframe ? 'Blueprint wireframe hidden' : 'Blueprint architectural wireframe & elevation datum active');
            }}
            className={`px-2.5 py-1 rounded-xl text-[10px] font-bold flex items-center gap-1 border transition-all cursor-pointer ${
              showBlueprintWireframe
                ? 'bg-emerald-950/80 border-emerald-500 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.3)]'
                : 'bg-slate-900 border-slate-700 text-slate-500 hover:text-slate-300'
            }`}
            title="Toggle 2D Architectural Blueprint Coordinate Grid & Elevation Datum Lines"
          >
            <Layers className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden sm:inline">BLUEPRINT:</span>
            <span>{showBlueprintWireframe ? 'ON' : 'OFF'}</span>
          </button>

          {/* RESPIRATION & MEMORY SYNCHRONIZATION WIDGET */}
          <button
            onClick={() => setShowRespirationPanel(!showRespirationPanel)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl border text-[10px] font-bold transition-all cursor-pointer ${
              breatheModeActive
                ? 'bg-black/90 border-[#D4AF37]/60 text-[#D4AF37] shadow-[0_0_15px_rgba(212,175,55,0.3)]'
                : 'bg-slate-900 border-slate-700 text-slate-500'
            }`}
            title="Inspect & Tune World Tree Respiration (Synchronized with 8GB RAM Confinement)"
          >
            <Activity 
              className={`w-3.5 h-3.5 ${
                ramRatio > 0.88 ? 'text-red-400' : ramRatio > 0.72 ? 'text-amber-400' : 'text-[#D4AF37]'
              }`}
              style={{
                animation: `pulse ${breatheDurationCss} ease-in-out infinite`
              }}
            />
            <span className="hidden xl:inline text-slate-400">PULSE:</span>
            <span className="text-cyan-300 font-mono">{breatheDurationCss}</span>
            <span className="text-slate-500 text-[9px]">({breathsPerMinute} BPM)</span>
            <span className={`text-[8px] px-1 py-0.2 rounded font-mono ${
              ramRatio > 0.88 ? 'bg-red-950 text-red-300 border border-red-500/50' : 
              ramRatio > 0.72 ? 'bg-amber-950 text-amber-300 border border-amber-500/50' : 
              'bg-emerald-950 text-emerald-300 border border-emerald-500/50'
            }`}>
              {ramPercent}% RAM
            </span>
          </button>
        </div>

        {/* Right: Layout Switcher, Orbit, Sound, Cinema, Quick Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Continuity View Layout: Showcase vs Scroller vs HUD vs Unified Morph vs Dual-Sync Split */}
          <div className="flex items-center gap-1 bg-black/90 p-0.5 rounded-xl border border-[#D4AF37]/50 shadow-inner">
            <button
              onClick={() => {
                audioEngine.playClick();
                setContinuityLayout('showcase');
                showFeedback('GEMINI 3.8 FLASH 3D SHOWCASE: Cinematic Model Orbit, Two-Row Marquee & Bento Grid');
              }}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                continuityLayout === 'showcase'
                  ? 'bg-gradient-to-r from-[#D4AF37] via-amber-400 to-[#D4AF37] text-black font-extrabold shadow-[0_0_16px_rgba(212,175,55,0.7)]'
                  : 'text-[#D4AF37] hover:text-white'
              }`}
              title="Interactive 3D Website Showcase (Gemini 3.8 Flash, Two-Row Infinite Marquee, Bento Grid)"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>3D SHOWCASE</span>
            </button>

            <button
              onClick={() => {
                audioEngine.playClick();
                setContinuityLayout('scroller');
                showFeedback('SCROLL MATRIX: Interactive 7-Picture World Tree Strata (Apex to VFS Roots & Throne Room)');
              }}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                continuityLayout === 'scroller'
                  ? 'bg-gradient-to-r from-amber-500/40 to-cyan-500/40 text-white border border-[#D4AF37]/60 shadow-[0_0_12px_rgba(212,175,55,0.4)]'
                  : 'text-slate-400 hover:text-white'
              }`}
              title="Scrolling Interactive UI of 7 Pictures (Full Tree, VFS Roots, Open Notebook, Throne Room)"
            >
              <span>7 PICS SCROLL</span>
            </button>

            <button
              onClick={() => {
                audioEngine.playClick();
                setContinuityLayout('hud');
                showFeedback('WORLD TREE HUD: 2D ➔ 3D Continuous Force Graph Topology HUD');
              }}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                continuityLayout === 'hud'
                  ? 'bg-gradient-to-r from-amber-500/30 to-[#2E0854] text-[#D4AF37] border border-[#D4AF37] shadow-[0_0_12px_rgba(212,175,55,0.4)]'
                  : 'text-slate-400 hover:text-white'
              }`}
              title="Continuous 2D to 3D Force-Directed World Tree HUD"
            >
              <TreeDeciduous className="w-3.5 h-3.5 text-[#D4AF37]" />
              <span>2D ➔ 3D HUD</span>
            </button>

            <button
              onClick={() => {
                audioEngine.playClick();
                setContinuityLayout('unified');
                showFeedback('UNIFIED CONTINUITY: Immersive full-screen 2D ➔ 3D morphing viewport');
              }}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 transition-all cursor-pointer ${
                continuityLayout === 'unified'
                  ? 'bg-[#2E0854] text-[#D4AF37] border border-[#D4AF37] shadow-[0_0_10px_rgba(212,175,55,0.3)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Unified continuous morphing canvas"
            >
              <Move3d className="w-3.5 h-3.5" />
              <span>SCROLL DECK</span>
            </button>

            <button
              onClick={() => {
                audioEngine.playClick();
                setContinuityLayout('split');
                showFeedback('DUAL-SYNC SPLIT: 2D Blueprint & 3D Spatial Chamber side-by-side with quantum synchronization');
              }}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 transition-all cursor-pointer ${
                continuityLayout === 'split'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.4)]'
                  : 'text-slate-400 hover:text-cyan-200'
              }`}
              title="Side-by-side dual inspection: 2D Blueprint Schematic on left, 3D Spatial Chamber on right"
            >
              <Columns2 className="w-3.5 h-3.5" />
              <span>DUAL-SYNC</span>
            </button>

            <button
              onClick={() => {
                audioEngine.playClick();
                setContinuityLayout('overlay');
                showFeedback('3D CANVAS OVERLAY: Fixed Three.js viewport (z-0) with HTML UI Overlay (z-1+)');
              }}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 transition-all cursor-pointer ${
                continuityLayout === 'overlay'
                  ? 'bg-purple-950 text-purple-300 border border-purple-400 shadow-[0_0_10px_rgba(168,85,247,0.5)]'
                  : 'text-slate-400 hover:text-purple-300'
              }`}
              title="Fixed Three.js canvas layer with pointer-events pass-through HTML UI overlay"
            >
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span>3D OVERLAY</span>
            </button>
          </div>

          {/* Kinetic Orbit Toggle */}
          {dimensionBlend > 0.3 && (
            <button
              onClick={() => {
                audioEngine.playClick();
                setIsKineticOrbiting(!isKineticOrbiting);
                showFeedback(isKineticOrbiting ? 'Kinetic Orbit: Paused' : 'Kinetic Orbit: Sweeping camera active');
              }}
              className={`px-2.5 py-1 rounded-lg border text-[10px] font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                isKineticOrbiting
                  ? 'bg-amber-500 text-black border-amber-300 shadow-[0_0_15px_rgba(245,158,11,0.5)] animate-pulse'
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-amber-300'
              }`}
              title="Toggle Automated 3D Kinetic Orbit Camera"
            >
              <Orbit className="w-3.5 h-3.5" />
              <span>{isKineticOrbiting ? 'ORBIT: ON' : 'ORBIT'}</span>
            </button>
          )}

          {/* Open-Notebook Launcher */}
          <button
            onClick={() => {
              audioEngine.playBrainSync();
              setActiveModal('twin_brains');
            }}
            className="px-2.5 py-1 rounded-lg bg-[#2E0854]/90 hover:bg-[#2E0854] border border-purple-500/50 text-purple-200 text-[10px] font-bold flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(192,132,252,0.3)] cursor-pointer"
            title="Launch Open-Notebook & Twin Quantum Brains Studio"
          >
            <Brain className="w-3.5 h-3.5 text-purple-300" />
            <span className="hidden sm:inline">OPEN-NOTEBOOK</span>
          </button>

          {/* Cinema / Clean Mode Toggle */}
          <button
            onClick={() => {
              audioEngine.playClick();
              setCinemaMode(!cinemaMode);
            }}
            className={`px-2.5 py-1 rounded-lg border text-[10px] flex items-center gap-1.5 transition-all cursor-pointer ${
              cinemaMode 
                ? 'bg-purple-950 border-purple-400 text-purple-200 shadow-[0_0_12px_rgba(168,85,247,0.4)]' 
                : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle Clean Cinema View (Hide all overlays - Press 'C')"
          >
            {cinemaMode ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            <span>{cinemaMode ? 'CINEMA' : 'HUD'}</span>
          </button>

          {/* Sound Toggle */}
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`px-2.5 py-1 rounded-lg border text-[10px] flex items-center gap-1.5 transition-all cursor-pointer ${
              soundEnabled 
                ? 'bg-cyan-950/80 border-cyan-500 text-cyan-300' 
                : 'bg-slate-900 border-slate-700 text-slate-500'
            }`}
            title="Toggle Synthesizer Sound Effects"
          >
            {soundEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
            <span>{soundEnabled ? 'AUDIO FX' : 'MUTED'}</span>
          </button>

          {/* Trigger State Pulse */}
          <button
            onClick={handleOuroborosTrigger}
            className="px-3 py-1 rounded-lg bg-emerald-950/90 border border-emerald-500/80 hover:border-emerald-300 text-emerald-200 hover:text-white text-[10px] font-bold flex items-center gap-1.5 active:scale-95 transition-all shadow-[0_0_15px_rgba(16,185,129,0.3)] cursor-pointer"
            title="Fire 1.58-bit Ouroboros SSM State Pulse"
          >
            <Zap className="w-3.5 h-3.5 text-emerald-400" />
            <span>PULSE SSM</span>
          </button>

          {/* Quick link to VPS Hub Initiation & HTMX Operator Console */}
          {onNavigateTab && (
            <>
              <button
                onClick={() => onNavigateTab('vps_init')}
                className="hidden xl:flex px-2.5 py-1 rounded-lg bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-500/60 text-emerald-300 text-[10px] font-bold items-center gap-1 transition-all shadow-[0_0_10px_rgba(16,185,129,0.25)] cursor-pointer"
                title="Navigate to InterServer KVM VPS Hub Initiation Plan (vps3573819)"
              >
                <Server className="w-3 h-3 text-emerald-400" />
                <span>VPS INITIATION</span>
              </button>

              <button
                onClick={() => onNavigateTab('operator')}
                className="hidden xl:flex px-2.5 py-1 rounded-lg bg-[#2E0854] hover:bg-purple-900 border border-[#D4AF37]/60 text-[#D4AF37] text-[10px] font-bold items-center gap-1 transition-all shadow-[0_0_10px_rgba(212,175,55,0.25)] cursor-pointer"
                title="Navigate to Go/Rust Operator Console & WebGPU Topology"
              >
                <ShieldCheck className="w-3 h-3 text-[#D4AF37]" />
                <span>HTMX CONSOLE</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* ================= INTERACTIVE MEMORY RESPIRATION TUNER DRAWER ================= */}
      {showRespirationPanel && (
        <div className="fixed top-12 left-4 sm:left-12 z-50 w-80 sm:w-96 p-4 rounded-2xl bg-[#050505]/95 border-2 border-[#D4AF37] shadow-[0_0_40px_rgba(0,0,0,0.9)] backdrop-blur-2xl text-xs space-y-3 animate-fadeIn font-mono">
          <div className="flex items-center justify-between border-b border-[#D4AF37]/30 pb-2">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#D4AF37] animate-pulse" />
              <span className="font-bold text-[#D4AF37] tracking-wider text-xs">
                TREE RESPIRATION & 8GB RAM SYNC
              </span>
            </div>
            <button
              onClick={() => setShowRespirationPanel(false)}
              className="text-slate-400 hover:text-white text-xs px-1.5 py-0.5 rounded bg-slate-800"
            >
              ✕
            </button>
          </div>

          <div className="space-y-1.5 text-[11px]">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">MEMORY UTILIZATION:</span>
              <span className="text-cyan-300 font-bold font-mono">
                {(activeUsedRamMB / 1024).toFixed(2)} GB / 8.00 GB ({ramPercent}%)
              </span>
            </div>

            {/* Visual RAM Bar */}
            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              <div 
                className={`h-full transition-all duration-300 ${
                  ramRatio > 0.88 ? 'bg-gradient-to-r from-amber-500 to-red-500' :
                  ramRatio > 0.72 ? 'bg-gradient-to-r from-emerald-500 to-amber-500' :
                  'bg-gradient-to-r from-cyan-400 to-emerald-400'
                }`}
                style={{ width: `${ramPercent}%` }}
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-slate-400">BREATHE CYCLE:</span>
              <span className="text-[#D4AF37] font-bold font-mono">
                {breatheDurationCss} / breath ({breathsPerMinute} BPM)
              </span>
            </div>

            <div className="flex items-center justify-between text-[10px]">
              <span className="text-slate-500">PHYSIOLOGICAL STATE:</span>
              <span className={`font-bold ${
                ramRatio > 0.88 ? 'text-red-400' : ramRatio > 0.72 ? 'text-amber-300' : 'text-emerald-400'
              }`}>
                {ramRatio > 0.88 
                  ? 'CRITICAL 8GB CAPACITY SLOWDOWN' 
                  : ramRatio > 0.72 
                    ? 'HEAVY LOAD SLOWING DOWN' 
                    : ramRatio > 0.45 
                      ? 'NOMINAL RESTING RHYTHM' 
                      : 'AGILE / FAST PULSE'}
              </span>
            </div>
          </div>

          {/* Interactive Memory Stress Simulation Slider */}
          <div className="space-y-1.5 pt-2 border-t border-slate-800">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-slate-400">TEST MEMORY CAPACITY LOAD:</span>
              <span className="text-[#D4AF37] font-bold font-mono">
                {(activeUsedRamMB / 1024).toFixed(2)} GB
              </span>
            </div>
            <input 
              type="range"
              min="1024"
              max="8150"
              step="128"
              value={activeUsedRamMB}
              onChange={(e) => {
                setSimulatedRamMB(Number(e.target.value));
              }}
              className="w-full h-1.5 accent-[#D4AF37] bg-slate-800 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[8px] text-slate-500 font-mono">
              <span>1GB (Fast 2.2s)</span>
              <span>4.8GB (Nominal 4.8s)</span>
              <span>8GB Limit (Slow 12.8s)</span>
            </div>
          </div>

          {/* Quick Presets */}
          <div className="grid grid-cols-2 gap-1.5 pt-1">
            <button
              onClick={() => {
                audioEngine.playClick();
                setSimulatedRamMB(1800);
                showFeedback('Memory load set to 1.8GB: Light swift pulse (2.6s)');
              }}
              className="px-2 py-1 rounded bg-black/60 hover:bg-slate-850 border border-cyan-800 text-cyan-300 text-[9px] transition-all cursor-pointer"
            >
              1.8 GB (Fast 2.6s)
            </button>
            <button
              onClick={() => {
                audioEngine.playClick();
                setSimulatedRamMB(4890);
                showFeedback('Memory load set to 4.89GB: Nominal rhythm (4.8s)');
              }}
              className="px-2 py-1 rounded bg-black/60 hover:bg-slate-850 border border-[#D4AF37]/50 text-[#D4AF37] text-[9px] transition-all cursor-pointer"
            >
              4.89 GB (Nominal 4.8s)
            </button>
            <button
              onClick={() => {
                audioEngine.playClick();
                setSimulatedRamMB(7200);
                showFeedback('Memory load set to 7.2GB: Heavy slow breathe (8.4s)');
              }}
              className="px-2 py-1 rounded bg-black/60 hover:bg-slate-850 border border-amber-800 text-amber-300 text-[9px] transition-all cursor-pointer"
            >
              7.2 GB (Heavy 8.4s)
            </button>
            <button
              onClick={() => {
                audioEngine.playClick();
                setSimulatedRamMB(7980);
                showFeedback('Memory load set to 7.98GB: 8GB Capacity Limit (Slowest 12.8s heave)');
              }}
              className="px-2 py-1 rounded bg-black/60 hover:bg-slate-850 border border-red-800 text-red-300 text-[9px] font-bold transition-all cursor-pointer"
            >
              7.98 GB (8GB Max 12.8s)
            </button>
          </div>

          <div className="flex items-center justify-between pt-1 border-t border-slate-800">
            <button
              onClick={() => {
                audioEngine.playClick();
                setSimulatedRamMB(null);
                showFeedback('Reset to live kernel vitals');
              }}
              className="text-[9px] text-slate-400 hover:text-cyan-300 underline cursor-pointer"
            >
              Reset to Live Vitals
            </button>

            <button
              onClick={() => {
                audioEngine.playClick();
                setBreatheModeActive(!breatheModeActive);
              }}
              className={`px-2.5 py-1 rounded-lg text-[9px] font-bold border transition-all cursor-pointer ${
                breatheModeActive
                  ? 'bg-[#D4AF37]/20 border-[#D4AF37] text-[#D4AF37]'
                  : 'bg-slate-900 border-slate-700 text-slate-400'
              }`}
            >
              {breatheModeActive ? 'BREATHE: ON' : 'BREATHE: OFF'}
            </button>
          </div>
        </div>
      )}

      {/* Floating Action Feedback Notification */}
      {recentActionMsg && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-1.5 rounded-xl bg-black/95 border border-[#D4AF37] text-[#D4AF37] text-xs font-mono shadow-[0_0_25px_rgba(212,175,55,0.4)] flex items-center gap-2 animate-bounce">
          <span className="w-2 h-2 rounded-full bg-[#D4AF37] animate-ping"></span>
          <span>{recentActionMsg}</span>
        </div>
      )}

      {/* ================= RIGHT FLOATING STRATUM QUICK-NAV RAIL ================= */}
      <aside 
        aria-label="Stratum Navigation"
        className="fixed right-3 sm:right-6 top-1/2 -translate-y-1/2 z-40 flex flex-col gap-2.5 p-2 bg-black/80 rounded-2xl border border-[#D4AF37]/30 backdrop-blur-xl shadow-2xl"
      >
        <div className="text-[8px] text-slate-500 font-bold text-center uppercase tracking-widest pb-1 border-b border-slate-800">
          STRATA
        </div>
        {STRATA.map((s, idx) => {
          const isActive = currentStratum.id === s.id;
          return (
            <button
              key={s.id}
              onClick={() => scrollToStratum(s.targetScroll)}
              className={`group flex items-center gap-2 px-2.5 py-2 rounded-xl text-left transition-all cursor-pointer ${
                isActive
                  ? 'bg-gradient-to-r from-[#2E0854] to-black border-2 border-[#D4AF37] text-white shadow-[0_0_15px_rgba(212,175,55,0.4)]'
                  : 'hover:bg-slate-900/80 text-slate-400 hover:text-slate-200 border border-transparent'
              }`}
              title={`Glide to ${s.name}`}
            >
              <span className="text-sm">{s.icon}</span>
              <div className="hidden lg:block">
                <div className={`text-[10px] font-bold tracking-wider ${isActive ? 'text-[#D4AF37]' : 'text-slate-300'}`}>
                  S{4 - idx}: {s.name.split(' ')[0]}
                </div>
                <div className="text-[8px] text-slate-500 font-mono">
                  {Math.round(s.scrollStart * 100)}% - {Math.round(s.scrollEnd * 100)}%
                </div>
              </div>
              <div className={`w-1.5 h-1.5 rounded-full ml-auto ${isActive ? 'bg-[#D4AF37] animate-ping' : 'bg-slate-700'}`} />
            </button>
          );
        })}

        {/* Scroll percentage bar */}
        <div className="mt-1 pt-1.5 border-t border-slate-800 flex flex-col items-center">
          <div className="w-1.5 h-14 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
            <div 
              className="w-full bg-gradient-to-b from-[#D4AF37] via-cyan-400 to-[#10B981] rounded-full transition-all duration-150"
              style={{ height: `${scrollProgress * 100}%` }}
            />
          </div>
          <span className="text-[8px] text-[#D4AF37] font-bold mt-1 font-mono">
            {Math.round(scrollProgress * 100)}%
          </span>
        </div>
      </aside>

      {/* ================= CONTINUOUS 2D ➔ 3D WORLD TREE VIEWPORT ================= */}
      {continuityLayout === 'showcase' ? (
        <div className="w-full">
          <Interactive3DShowcase
            vitals={vitals}
            onNavigateTab={onNavigateTab}
            onExecuteCommand={onExecuteCommand}
            onSwitchContinuityView={(view) => setContinuityLayout(view)}
          />
        </div>
      ) : continuityLayout === 'scroller' ? (
        <div className="w-full">
          <SovereignWorldTreeScrollingExperience 
            onNavigateTab={onNavigateTab}
            onExecuteCommand={onExecuteCommand}
          />
        </div>
      ) : continuityLayout === 'overlay' ? (
        <div className="w-full h-screen pt-12">
          <FixedThreeUiOverlay onClose={() => setContinuityLayout('showcase')} />
        </div>
      ) : continuityLayout === 'hud' ? (
        <div className="w-full max-w-[1880px] mx-auto p-2 sm:p-4 pt-16 pb-8">
          <WorldTreeHUD 
            onOpenModal={(m) => setActiveModal(m)}
            onNavigateTab={onNavigateTab}
            onExecuteCommand={onExecuteCommand}
          />
        </div>
      ) : continuityLayout === 'split' ? (
        <div className="w-full max-w-[1780px] mx-auto p-2 sm:p-4 pt-16 space-y-4">
          {/* Dual-Sync Header Ribbon */}
          <div className="hud-panel hud-panel-luxora p-3 rounded-2xl flex flex-wrap items-center justify-between gap-3 text-xs border border-[#D4AF37]/50 shadow-xl">
            <div className="flex items-center gap-2">
              <Columns2 className="w-4 h-4 text-cyan-400" />
              <span className="font-bold text-[#D4AF37] tracking-wider uppercase">
                DUAL-SYNC CONTINUITY WORKSTATION
              </span>
              <span className="text-slate-500 font-mono text-[10px]">
                [PARITY LOCK: 100% • ANYA_GATE SYNCHRONIZED]
              </span>
            </div>

            <div className="flex items-center gap-3 text-[11px] font-mono">
              <span className="text-slate-400">STRATUM:</span>
              <span className="text-cyan-300 font-bold uppercase">{currentStratum.name.split('&')[0]}</span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">DESCENT:</span>
              <span className="text-[#D4AF37] font-bold">{Math.round(scrollProgress * 100)}%</span>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400">ALTITUDE:</span>
              <span className="text-emerald-400 font-bold">{currentStratum.altitude}</span>
            </div>
          </div>

          {/* Dual-Column Synchronization Grid */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-stretch">
            {/* LEFT PANE: 2D Living Blueprint Schematic */}
            <div className="relative rounded-3xl border-2 border-cyan-800/60 overflow-hidden shadow-2xl bg-[#030712] flex flex-col justify-between">
              {/* Top Banner */}
              <div className="p-3 bg-black/80 border-b border-cyan-900/60 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-cyan-300 font-bold tracking-wider text-[11px]">
                    2.0D BLUEPRINT SCHEMATIC // ORTHOGRAPHIC DATUM
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[9px] px-2 py-0.5 rounded bg-cyan-950 border border-cyan-600/50 text-cyan-300 font-mono">
                    SCALE 1:1 • FLAT CAD
                  </span>
                </div>
              </div>

              {/* 2D Vector Visualizer */}
              <div className="p-2 sm:p-4">
                <WorldTreeVisual
                  onOpenMemcastle={() => setActiveModal('memcastle')}
                  onOpenTwinBrains={() => setActiveModal('twin_brains')}
                  onOpenOuroboros={() => setActiveModal('twin_brains')}
                  onOpenViking={() => setActiveModal('viking')}
                  onOpenGraphify={() => onNavigateTab ? onNavigateTab('vkg') : undefined}
                />
              </div>

              {/* Bottom Datum Ruler */}
              <div className="p-2 bg-black/80 border-t border-cyan-900/60 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span>DATUM: WGS-84 AXIS MUNDI</span>
                <span className="text-cyan-400">ACTIVE: {currentStratum.id.toUpperCase()}</span>
                <span>STATUS: NOMINAL</span>
              </div>
            </div>

            {/* RIGHT PANE: 3D Spatial Chamber & WebGL Matrix */}
            <div className="relative rounded-3xl border-2 border-[#D4AF37]/50 overflow-hidden shadow-2xl bg-[#050505] flex flex-col justify-between min-h-[640px]">
              {/* Top Banner */}
              <div className="p-3 bg-black/80 border-b border-[#D4AF37]/40 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <Move3d className="w-3.5 h-3.5 text-[#D4AF37]" />
                  <span className="text-[#D4AF37] font-bold tracking-wider text-[11px]">
                    3.0D SPATIAL CHAMBER // STEREOSCOPIC MATRIX
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[9px] px-2 py-0.5 rounded bg-purple-950 border border-purple-500/50 text-purple-300 font-mono">
                    PERSPECTIVE 1400px • WEBGL ACTIVE
                  </span>
                </div>
              </div>

              {/* 3D Scene Viewport */}
              <div 
                className="relative flex-1 w-full overflow-hidden flex items-center justify-center p-2"
                onMouseMove={handleMouseMove}
                onMouseLeave={handleMouseLeave}
                style={{ perspective: '1400px' }}
              >
                <div 
                  className="relative w-full h-full min-h-[560px] rounded-2xl border border-[#D4AF37]/40 overflow-hidden shadow-2xl transition-transform duration-300 ease-out"
                  style={{
                    transformStyle: 'preserve-3d',
                    transform: `rotateX(${finalRotX}deg) rotateY(${finalRotY}deg) translateZ(15px)`,
                    backgroundColor: '#050505'
                  }}
                >
                  {/* Master Image */}
                  <div 
                    className="absolute inset-0 pointer-events-none transition-transform duration-300 ease-out"
                    style={{
                      transform: `translateY(${camera.panY}%) scale(${camera.scale})`,
                      transformStyle: 'preserve-3d'
                    }}
                  >
                    <img 
                      src="/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).src = 'https://i.postimg.cc/Lssx07X3/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png';
                      }}
                      alt="Camelot-OS Sovereign World Tree"
                      referrerPolicy="no-referrer"
                      className="w-full h-auto min-h-[140%] object-cover object-center pointer-events-none transition-all duration-700 brightness-105 contrast-110 select-none"
                    />
                  </div>

                  {/* WebGL Overlay */}
                  <ThreeWorldTreeScene 
                    energyPulseTrigger={energyPulseTrigger}
                    depthLayer={5}
                    onHotspotClick={(zone) => {
                      if (zone === 'memcastle') setActiveModal('memcastle');
                      if (zone === 'brains') setActiveModal('twin_brains');
                      if (zone === 'viking') setActiveModal('viking');
                    }}
                  />

                  {/* Dynamic Stratum Floating Info */}
                  <div className="absolute bottom-4 inset-x-4 pointer-events-none">
                    <div className="hud-panel hud-panel-luxora p-3 rounded-xl flex items-center justify-between text-xs backdrop-blur-xl border border-[#D4AF37]/50 shadow-xl pointer-events-auto">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{currentStratum.icon}</span>
                        <div>
                          <div className="text-[10px] font-bold text-white uppercase">{currentStratum.name}</div>
                          <div className="text-[9px] text-slate-400">{currentStratum.subTitle}</div>
                        </div>
                      </div>
                      <span className="text-[#D4AF37] font-bold font-mono text-[11px]">{currentStratum.altitude}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom Telemetry Bar */}
              <div className="p-2 bg-black/80 border-t border-[#D4AF37]/40 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span>PITCH: {finalRotX.toFixed(1)}° • YAW: {finalRotY.toFixed(1)}°</span>
                <span className="text-[#D4AF37]">PULSE: {breatheDurationCss}</span>
                <span>DMA REFRACTION: 12μs</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="sticky top-0 h-screen w-full overflow-hidden flex flex-col justify-between pt-12 pb-2">
          
          {/* 3D SCENE STAGE WRAPPER */}
          <div 
            className="relative w-full h-full flex items-center justify-center p-2 sm:p-4 overflow-hidden"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            style={{
              perspective: perspectiveCss,
            }}
          >
            {/* The Physical 3D Tilting Frame */}
            <div 
              className={`relative w-full h-full max-w-[1720px] max-h-[92vh] rounded-3xl border transition-all duration-300 ease-out overflow-hidden shadow-2xl ${
                dimensionBlend > 0.4 
                  ? 'border-[#D4AF37]/50 shadow-[0_0_80px_rgba(0,0,0,0.9)]' 
                  : 'border-cyan-500/50 shadow-[0_0_40px_rgba(0,0,0,0.7)]'
              } ${isKineticOrbiting ? 'animate-kinetic-orbit' : ''}`}
              style={{
                transformStyle: 'preserve-3d',
                transform: dimensionBlend < 0.05
                  ? 'rotateX(0deg) rotateY(0deg) translateZ(0px)'
                  : isKineticOrbiting
                    ? undefined
                    : `rotateX(${finalRotX}deg) rotateY(${finalRotY}deg) translateZ(${20 * dFactor}px)`,
                backgroundColor: '#050505'
              }}
            >
              {/* LAYER -1: DEEP COSMIC NEBULA & MATRIX GRID (translateZ: -60px) */}
              <div 
                className="absolute inset-0 pointer-events-none transition-transform duration-500"
                style={{
                  transform: `translateZ(${-60 * dFactor}px) scale(${1 + 0.08 * dFactor})`,
                  transformStyle: 'preserve-3d',
                  backgroundImage: 'radial-gradient(ellipse at center, rgba(46, 8, 84, 0.4) 0%, rgba(5, 5, 5, 0.95) 75%)'
                }}
              >
                <div 
                  className="absolute inset-0 opacity-15"
                  style={{
                    backgroundImage: 'radial-gradient(rgba(212, 175, 55, 0.4) 1px, transparent 0)',
                    backgroundSize: '36px 36px'
                  }}
                />
              </div>

              {/* Bio-luminescent Respiration Aura (Synchronized with 8GB RAM Confinement) */}
              <div 
                className={`absolute inset-0 pointer-events-none rounded-3xl transition-opacity duration-700 ${breatheModeActive ? 'world-tree-aura-active' : ''}`}
                style={{
                  background: `radial-gradient(ellipse at 50% 50%, ${breatheGlowColor} 0%, rgba(46, 8, 84, 0.25) 55%, transparent 80%)`,
                  '--tree-breathe-duration': breatheDurationCss,
                } as React.CSSProperties}
              />

              {/* LAYER 0: THE MASTER WORLD TREE ARTWORK IMAGE (Smoothly Panned by Scroll & Pulsing with 8GB RAM) */}
              <div 
                className="absolute inset-0 pointer-events-none transition-transform duration-300 ease-out overflow-hidden"
                style={{
                  transform: `translateY(${camera.panY}%) scale(${camera.scale}) translateZ(0px)`,
                  transformStyle: 'preserve-3d'
                }}
              >
                {/* Breathe Animated Image Container */}
                <div 
                  className={`w-full h-full ${breatheModeActive ? 'world-tree-breathe-active' : ''}`}
                  style={{
                    '--tree-breathe-duration': breatheDurationCss,
                    '--tree-breathe-glow': breatheGlowColor,
                    '--tree-breathe-scale': breatheScale,
                    '--tree-breathe-z': `${breatheZ}px`,
                  } as React.CSSProperties}
                >
                  <img 
                    src="/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).src = 'https://i.postimg.cc/Lssx07X3/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png';
                    }}
                    alt="Camelot-OS Sovereign World Tree Full Page Control Center"
                    referrerPolicy="no-referrer"
                    className="w-full h-auto min-h-[140%] object-cover object-center pointer-events-none transition-all duration-700 brightness-105 contrast-110 saturate-125 select-none"
                  />
                </div>

                {/* Ambient Depth Scanlines & Vignettes */}
                <div 
                  className="absolute inset-0 pointer-events-none opacity-10"
                  style={{
                    backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, #22d3ee 3px, #22d3ee 4px)',
                    backgroundSize: '100% 4px'
                  }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#050505]/95 via-transparent to-[#050505]/70 pointer-events-none" />
                <div className="absolute inset-0 bg-gradient-to-r from-[#050505]/80 via-transparent to-[#050505]/80 pointer-events-none" />
              </div>

              {/* LAYER 0.5: 2D ARCHITECTURAL BLUEPRINT & ELEVATION DATUM WIREFRAME OVERLAY */}
              {showBlueprintWireframe && (
                <div 
                  className="absolute inset-0 pointer-events-none z-10 transition-opacity duration-300"
                  style={{ 
                    opacity: blueprintOpacity,
                    transform: `translateZ(${12 * (1 - dimensionBlend)}px)`,
                    transformStyle: 'preserve-3d'
                  }}
                >
                  <svg 
                    className="w-full h-full" 
                    viewBox="0 0 1000 700" 
                    preserveAspectRatio="none"
                  >
                    <defs>
                      {/* Architectural Blueprint Grid Pattern */}
                      <pattern id="cadGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(34, 211, 238, 0.14)" strokeWidth="0.8" />
                        <circle cx="0" cy="0" r="1.2" fill="rgba(34, 211, 238, 0.25)" />
                      </pattern>
                      <pattern id="cadMajorGrid" width="200" height="200" patternUnits="userSpaceOnUse">
                        <rect width="200" height="200" fill="url(#cadGrid)" />
                        <path d="M 200 0 L 0 0 0 200" fill="none" stroke="rgba(212, 175, 55, 0.25)" strokeWidth="1.2" />
                      </pattern>
                    </defs>

                    {/* Cad Grid Background */}
                    <rect width="1000" height="700" fill="url(#cadMajorGrid)" />

                    {/* Central Plumb Line (Axis Mundi Trunk Alignment) */}
                    <line 
                      x1="500" y1="20" x2="500" y2="680" 
                      stroke="rgba(212, 175, 55, 0.6)" 
                      strokeWidth="1.5" 
                      strokeDasharray="6 4"
                    />

                    {/* Stratum Datum Elevation Lines */}
                    {/* S4: Apex Spire */}
                    <g transform="translate(0, 110)">
                      <line x1="80" y1="0" x2="920" y2="0" stroke="rgba(212, 175, 55, 0.55)" strokeWidth="1.2" strokeDasharray="4 2" />
                      <circle cx="500" cy="0" r="5" fill="#D4AF37" />
                      <circle cx="500" cy="0" r="14" fill="none" stroke="#D4AF37" strokeWidth="0.8" strokeDasharray="3 3" />
                      <text x="90" y="-8" fill="#D4AF37" fontSize="10" fontFamily="monospace" fontWeight="bold">
                        DATUM S4 // EL +4500m [APEX MEMCASTLE] // PORT: 6379
                      </text>
                    </g>

                    {/* S3: Twin Quantum Brains */}
                    <g transform="translate(0, 270)">
                      <line x1="80" y1="0" x2="920" y2="0" stroke="rgba(168, 85, 247, 0.55)" strokeWidth="1.2" strokeDasharray="4 2" />
                      <circle cx="500" cy="0" r="5" fill="#c084fc" />
                      <circle cx="500" cy="0" r="14" fill="none" stroke="#c084fc" strokeWidth="0.8" strokeDasharray="3 3" />
                      <text x="90" y="-8" fill="#c084fc" fontSize="10" fontFamily="monospace" fontWeight="bold">
                        DATUM S3 // EL +2800m [TWIN QUANTUM BRAINS] // OPEN-NOTEBOOK
                      </text>
                    </g>

                    {/* S2: Ouroboros Ternary SSM */}
                    <g transform="translate(0, 430)">
                      <line x1="80" y1="0" x2="920" y2="0" stroke="rgba(245, 158, 11, 0.55)" strokeWidth="1.2" strokeDasharray="4 2" />
                      <circle cx="500" cy="0" r="5" fill="#fbbf24" />
                      <circle cx="500" cy="0" r="14" fill="none" stroke="#fbbf24" strokeWidth="0.8" strokeDasharray="3 3" />
                      <text x="90" y="-8" fill="#fbbf24" fontSize="10" fontFamily="monospace" fontWeight="bold">
                        DATUM S2 // EL +1200m [1.58b OUROBOROS SSM] // TERNARY LOOP
                      </text>
                    </g>

                    {/* S1: Viking Drakkar Emerald Basin */}
                    <g transform="translate(0, 590)">
                      <line x1="80" y1="0" x2="920" y2="0" stroke="rgba(16, 185, 129, 0.55)" strokeWidth="1.2" strokeDasharray="4 2" />
                      <circle cx="500" cy="0" r="5" fill="#34d399" />
                      <circle cx="500" cy="0" r="14" fill="none" stroke="#34d399" strokeWidth="0.8" strokeDasharray="3 3" />
                      <text x="90" y="-8" fill="#34d399" fontSize="10" fontFamily="monospace" fontWeight="bold">
                        DATUM S1 // EL +0000m [EMERALD RIVERS // VIKING PROTOCOL] // DMA RING
                      </text>
                    </g>

                    {/* CAD Drawing Title Block (Bottom-Right) */}
                    <g transform="translate(770, 605)">
                      <rect width="210" height="75" fill="rgba(5, 5, 5, 0.9)" stroke="rgba(212, 175, 55, 0.6)" strokeWidth="1.2" rx="4" />
                      <text x="10" y="18" fill="#D4AF37" fontSize="9" fontFamily="monospace" fontWeight="bold">
                        DWG: CAMELOT_WORLD_TREE
                      </text>
                      <text x="10" y="34" fill="#22d3ee" fontSize="8" fontFamily="monospace">
                        CONTINUITY: {(2.0 + dimensionBlend).toFixed(2)}D
                      </text>
                      <text x="10" y="50" fill="#94a3b8" fontSize="8" fontFamily="monospace">
                        PROJECTION: {dimensionBlend < 0.1 ? 'ORTHOGRAPHIC 2D' : dimensionBlend > 0.8 ? 'VOLUMETRIC 3D' : 'ISOMETRIC HYBRID'}
                      </text>
                      <text x="10" y="65" fill="#34d399" fontSize="8" fontFamily="monospace">
                        Z3_SAT: 44/44 PASS
                      </text>
                    </g>
                  </svg>
                </div>
              )}

              {/* Respiratory Expanding Wave Ripple at Core of Axis Mundi */}
              {breatheModeActive && (
                <div 
                  className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 rounded-full border border-[#D4AF37]/35 pointer-events-none tree-ripple-effect"
                  style={{
                    '--tree-breathe-duration': breatheDurationCss,
                    boxShadow: `0 0 35px ${breatheGlowColor}`
                  } as React.CSSProperties}
                />
              )}

              {/* Three.js WebGL Particle Overlay (smoothly blends opacity with dimension factor) */}
              {enableThreeWebGL && (
                <div 
                  className="absolute inset-0 z-15 transition-opacity duration-300"
                  style={{ 
                    opacity: Math.max(0.12, dimensionBlend),
                    pointerEvents: dimensionBlend > 0.25 ? 'auto' : 'none'
                  }}
                >
                  <ThreeWorldTreeScene 
                    energyPulseTrigger={energyPulseTrigger}
                    depthLayer={5}
                    onHotspotClick={(zone) => {
                      if (zone === 'memcastle') setActiveModal('memcastle');
                      if (zone === 'brains') setActiveModal('twin_brains');
                      if (zone === 'viking') setActiveModal('viking');
                    }}
                  />
                </div>
              )}

              {/* LAYER 1: Z-STANCHION LASER CONNECTOR GUIDES */}
              {dimensionBlend > 0.25 && dFactor > 0.15 && !cinemaMode && (
                <div className="absolute inset-0 pointer-events-none z-20" style={{ transformStyle: 'preserve-3d' }}>
                  <div 
                    className="z-stanchion"
                    style={{
                      top: '12%',
                      left: '50%',
                      height: '24px',
                      transform: `translateZ(${60 * dFactor}px) rotateX(90deg)`,
                      borderColor: 'rgba(212, 175, 55, 0.6)'
                    }}
                  />
                  <div 
                    className="z-stanchion"
                    style={{
                      top: '40%',
                      left: '26%',
                      height: '24px',
                      transform: `translateZ(${50 * dFactor}px) rotateX(90deg)`,
                      borderColor: 'rgba(192, 132, 252, 0.6)'
                    }}
                  />
                  <div 
                    className="z-stanchion"
                    style={{
                      top: '55%',
                      left: '50%',
                      height: '28px',
                      transform: `translateZ(${55 * dFactor}px) rotateX(90deg)`,
                      borderColor: 'rgba(245, 158, 11, 0.6)'
                    }}
                  />
                </div>
              )}

              {/* LAYER 2: EMBEDDED DYNAMIC STRATUM CARD (Highlights Active Stratum on Scroll) */}
              {!cinemaMode && (
                <div 
                  className="absolute inset-0 pointer-events-none z-30 flex flex-col justify-between p-4 sm:p-6"
                  style={{
                    transformStyle: 'preserve-3d',
                    transform: `translateZ(${80 * dFactor}px)`,
                    transition: 'transform 300ms ease-out'
                  }}
                >
                  {/* Top Left: Active Stratum Hero Card */}
                  <div 
                    className="max-w-md pointer-events-auto transition-all duration-500"
                    style={{ transformStyle: 'preserve-3d' }}
                  >
                    <div className="hud-panel hud-panel-luxora rounded-2xl p-4 text-xs space-y-2.5 backdrop-blur-xl border-2 border-[#D4AF37]/50 shadow-2xl">
                      <div className="flex items-center justify-between border-b border-[#D4AF37]/30 pb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">{currentStratum.icon}</span>
                          <div>
                            <span className="text-[9px] text-[#D4AF37] font-bold uppercase tracking-widest block">
                              CURRENT STRATUM ELEVATION
                            </span>
                            <h2 className="text-sm font-bold text-white tracking-wide">
                              {currentStratum.name}
                            </h2>
                          </div>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#2E0854] text-[#D4AF37] font-bold border border-[#D4AF37]/40">
                          {Math.round(scrollProgress * 100)}%
                        </span>
                      </div>

                      <p className="text-[11px] text-slate-300 font-mono leading-relaxed">
                        {currentStratum.subTitle}
                      </p>

                      {/* Stratum Specific Deep Action Button */}
                      <div className="flex items-center gap-2 pt-1">
                        {currentStratum.id === 'apex' && (
                          <button
                            onClick={() => {
                              audioEngine.playClick();
                              setActiveModal('memcastle');
                            }}
                            className="flex-1 py-1.5 rounded-xl bg-[#D4AF37] hover:bg-amber-400 text-black font-extrabold text-[10px] flex items-center justify-center gap-1.5 transition-all shadow-[0_0_15px_rgba(212,175,55,0.4)] cursor-pointer"
                          >
                            <span>INSPECT REDIS MEMCASTLE</span>
                            <ArrowUpRight className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {currentStratum.id === 'brains' && (
                          <button
                            onClick={() => {
                              audioEngine.playBrainSync();
                              setActiveModal('twin_brains');
                            }}
                            className="flex-1 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-extrabold text-[10px] flex items-center justify-center gap-1.5 transition-all shadow-[0_0_15px_rgba(192,132,252,0.4)] cursor-pointer"
                          >
                            <Brain className="w-3.5 h-3.5" />
                            <span>LAUNCH OPEN-NOTEBOOK STUDIO</span>
                          </button>
                        )}

                        {currentStratum.id === 'ouroboros' && (
                          <button
                            onClick={handleOuroborosTrigger}
                            className="flex-1 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-extrabold text-[10px] flex items-center justify-center gap-1.5 transition-all shadow-[0_0_15px_rgba(245,158,11,0.4)] cursor-pointer"
                          >
                            <Zap className="w-3.5 h-3.5 fill-black" />
                            <span>PULSE 1.58-BIT TERNARY SSM</span>
                          </button>
                        )}

                        {currentStratum.id === 'rivers' && (
                          <button
                            onClick={() => {
                              audioEngine.playClick();
                              setActiveModal('viking');
                            }}
                            className="flex-1 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-[10px] flex items-center justify-center gap-1.5 transition-all shadow-[0_0_15px_rgba(16,185,129,0.4)] cursor-pointer"
                          >
                            <Anchor className="w-3.5 h-3.5" />
                            <span>INSPECT VIKING PROTOCOL</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Top Right: System Invariants Live Flank + World Tree Respiration Telemetry */}
                  <div 
                    className="self-start hidden md:block max-w-xs pointer-events-auto transition-all space-y-2.5"
                    style={{ transformStyle: 'preserve-3d' }}
                  >
                    {/* Live Respiration Gauge Card */}
                    <div 
                      onClick={() => setShowRespirationPanel(true)}
                      className="hud-panel hud-panel-luxora rounded-2xl p-3 text-[10px] space-y-2 backdrop-blur-xl border border-[#D4AF37]/50 shadow-2xl cursor-pointer hover:border-[#D4AF37] transition-all"
                    >
                      <div className="flex items-center justify-between border-b border-[#D4AF37]/30 pb-1">
                        <div className="flex items-center gap-1.5 text-[#D4AF37] font-bold">
                          <Activity className="w-3.5 h-3.5 animate-pulse text-[#D4AF37]" />
                          <span>TREE RESPIRATION</span>
                        </div>
                        <span className={`text-[8px] px-1.5 py-0.2 rounded font-bold ${
                          ramRatio > 0.88 ? 'bg-red-950 text-red-300' : ramRatio > 0.72 ? 'bg-amber-950 text-amber-300' : 'bg-emerald-950 text-emerald-300'
                        }`}>
                          {breatheDurationCss} / breath
                        </span>
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[9px]">
                          <span className="text-slate-400">8GB CAPACITY CADENCE:</span>
                          <span className="text-cyan-300 font-bold">{breathsPerMinute} BPM</span>
                        </div>
                        <div className="w-full h-1 bg-slate-900 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500 transition-all duration-300"
                            style={{ width: `${ramPercent}%` }}
                          />
                        </div>
                        <div className="text-[8px] text-slate-500 text-right">
                          {ramPercent}% RAM • {ramRatio > 0.88 ? 'Slowest Labored Heave' : ramRatio > 0.72 ? 'Slowing under Load' : 'Nominal Pulse'}
                        </div>
                      </div>
                    </div>

                    {/* Standard Sovereign Invariants */}
                    <div className="hud-panel hud-panel-royal rounded-2xl p-3 text-[10px] space-y-2 backdrop-blur-xl border border-purple-500/40 shadow-2xl">
                      <div className="flex items-center justify-between border-b border-purple-500/30 pb-1">
                        <span className="font-bold text-[#D4AF37]">SOVEREIGN INVARIANTS</span>
                        <span className="text-emerald-400 font-bold">ANYA_GATE</span>
                      </div>
                      <div className="grid grid-cols-2 gap-1 text-[9px]">
                        <div className="p-1 rounded bg-black/70 border border-slate-800">
                          <span className="text-slate-500 block">RAM BOUND:</span>
                          <span className="text-cyan-300 font-bold">8GB STRICT</span>
                        </div>
                        <div className="p-1 rounded bg-black/70 border border-slate-800">
                          <span className="text-slate-500 block">Z3 PROOF:</span>
                          <span className="text-emerald-400 font-bold">44/44 SAT</span>
                        </div>
                        <div className="p-1 rounded bg-black/70 border border-slate-800">
                          <span className="text-slate-500 block">DMA SPEED:</span>
                          <span className="text-amber-300 font-bold">12μs REFRACT</span>
                        </div>
                        <div className="p-1 rounded bg-black/70 border border-slate-800">
                          <span className="text-slate-500 block">WAL2 SEAL:</span>
                          <span className="text-purple-300 font-bold">R5/R6 VERIFIED</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Center Interactive Hotspot Badges (Positioned in 3D Space) */}
                  <div className="relative w-full h-32 flex items-center justify-center pointer-events-none">
                    {/* Hotspot 1: APEX REDIS MEMCASTLE */}
                    {currentStratum.id === 'apex' && (
                      <div 
                        onClick={() => {
                          audioEngine.playClick();
                          setActiveModal('memcastle');
                        }}
                        className="pointer-events-auto cursor-pointer hud-panel hud-panel-luxora px-5 py-2.5 rounded-2xl border-2 border-[#D4AF37] shadow-[0_0_35px_rgba(212,175,55,0.6)] animate-bounce"
                      >
                        <span className="font-extrabold text-[#D4AF37] block text-xs tracking-wider">⚜️ APEX SPIRE: /vfs/mempalace/*</span>
                        <span className="text-[9px] text-amber-200 block">PORT 6379 • 0.18ms LATENCY</span>
                      </div>
                    )}

                    {/* Hotspot 2: TWIN BRAINS */}
                    {currentStratum.id === 'brains' && (
                      <div 
                        onClick={() => {
                          audioEngine.playBrainSync();
                          setActiveModal('twin_brains');
                        }}
                        className="pointer-events-auto cursor-pointer hud-panel hud-panel-royal px-5 py-2.5 rounded-2xl border-2 border-purple-400 shadow-[0_0_35px_rgba(192,132,252,0.6)] animate-pulse"
                      >
                        <span className="font-extrabold text-purple-200 block text-xs tracking-wider">🧠 OPEN-NOTEBOOK ⟷ NOTEBOOKLM</span>
                        <span className="text-[9px] text-cyan-300 block">PORT 8502 • COGNITIVE SYNAPSE</span>
                      </div>
                    )}

                    {/* Hotspot 3: OUROBOROS SSM */}
                    {currentStratum.id === 'ouroboros' && (
                      <div 
                        onClick={handleOuroborosTrigger}
                        className="pointer-events-auto cursor-pointer hud-panel hud-panel-amber px-5 py-2.5 rounded-2xl border-2 border-amber-400 shadow-[0_0_35px_rgba(245,158,11,0.6)] animate-pulse"
                      >
                        <span className="font-extrabold text-amber-300 block text-xs tracking-wider">⚡ 1.58-BIT OUROBOROS SSM</span>
                        <span className="text-[9px] text-slate-200 block">O(1) RECURRENT STATE COMPRESSION</span>
                      </div>
                    )}

                    {/* Hotspot 4: EMERALD DATA RIVERS */}
                    {currentStratum.id === 'rivers' && (
                      <div 
                        onClick={() => {
                          audioEngine.playClick();
                          setActiveModal('viking');
                        }}
                        className="pointer-events-auto cursor-pointer hud-panel hud-panel-emerald px-5 py-2.5 rounded-2xl border-2 border-emerald-400 shadow-[0_0_35px_rgba(52,211,153,0.6)] animate-bounce"
                      >
                        <span className="font-extrabold text-emerald-300 block text-xs tracking-wider">⚓ VIKING DRAKKAR // EMERALD RIVERS</span>
                        <span className="text-[9px] text-cyan-200 block">/vfs/refractions/* • DMA RING BUFFERS</span>
                      </div>
                    )}
                  </div>

                  {/* Bottom Center: Stratum Progress Strip */}
                  <div className="w-full max-w-xl mx-auto pointer-events-auto">
                    <div className="hud-panel hud-panel-luxora px-4 py-2 rounded-2xl flex items-center justify-between gap-3 text-[10px] backdrop-blur-xl border border-[#D4AF37]/50 shadow-xl">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400">CONTINUITY:</span>
                        <span className="text-cyan-300 font-bold font-mono">{(2.0 + dimensionBlend).toFixed(2)}D</span>
                        <span className="text-slate-600">|</span>
                        <span className="text-slate-400">PITCH:</span>
                        <span className="text-[#D4AF37] font-bold font-mono">{finalRotX.toFixed(1)}°</span>
                        <span className="text-slate-600">|</span>
                        <span className="text-slate-400">YAW:</span>
                        <span className="text-cyan-300 font-bold font-mono">{finalRotY.toFixed(1)}°</span>
                        <span className="text-slate-600">|</span>
                        <span className="text-slate-400">PULSE:</span>
                        <span className="text-emerald-400 font-bold font-mono">{breatheDurationCss}</span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-slate-400">SCROLL HINT:</span>
                        <span className="text-white font-bold flex items-center gap-1">
                          <span>Scroll Down to Descend Yggdrasil</span>
                          <ChevronDown className="w-3.5 h-3.5 text-[#D4AF37] animate-bounce" />
                        </span>
                      </div>
                    </div>
                  </div>

                </div>
              )}

            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL OVERLAYS ================= */}
      {activeModal === 'memcastle' && (
        <MemcastleModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === 'twin_brains' && (
        <TwinBrainsModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === 'viking' && (
        <VikingRefractionsModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}
    </div>
  );
};
