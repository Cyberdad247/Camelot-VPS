import React, { useState, useEffect, useRef } from 'react';
import { 
  Crown, 
  Brain, 
  Zap, 
  Layers, 
  Eye, 
  Maximize2,
  Sparkles,
  Compass,
  ArrowRight,
  Info,
  Activity,
  ShieldAlert
} from 'lucide-react';

interface WorldTreeVisualProps {
  onOpenMemcastle: () => void;
  onOpenTwinBrains: () => void;
  onOpenOuroboros: () => void;
  onOpenViking: () => void;
  onOpenGraphify?: () => void;
}

export const WorldTreeVisual: React.FC<WorldTreeVisualProps> = ({
  onOpenMemcastle,
  onOpenTwinBrains,
  onOpenOuroboros,
  onOpenViking,
  onOpenGraphify
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [activeZone, setActiveZone] = useState<string | null>(null);
  const [shipOffset, setShipOffset] = useState(0);
  const [energyPulse, setEnergyPulse] = useState(0);
  const [selectedHotspot, setSelectedHotspot] = useState<string | null>(null);

  // Background animated particle dust & river streams
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 800);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 750);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener('resize', handleResize);

    // Bioluminescent floating spores / particles
    const particles = Array.from({ length: 95 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.55,
      vy: (Math.random() - 0.5) * 0.55 - 0.25,
      size: Math.random() * 2.6 + 0.8,
      color: ['#22d3ee', '#fbbf24', '#34d399', '#c084fc', '#38bdf8', '#a855f7', '#f472b6'][Math.floor(Math.random() * 7)],
      alpha: Math.random() * 0.75 + 0.25
    }));

    let tick = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      tick += 0.025;

      // Draw subtle ambient radial glow behind tree
      const radialGrad = ctx.createRadialGradient(
        width / 2, height * 0.45, 30,
        width / 2, height * 0.45, width * 0.6
      );
      radialGrad.addColorStop(0, 'rgba(30, 58, 138, 0.4)');
      radialGrad.addColorStop(0.3, 'rgba(15, 23, 42, 0.35)');
      radialGrad.addColorStop(0.7, 'rgba(8, 14, 28, 0.2)');
      radialGrad.addColorStop(1, 'rgba(3, 7, 18, 0)');
      ctx.fillStyle = radialGrad;
      ctx.fillRect(0, 0, width, height);

      // Flowing conduit light packets from Left/Right Brains into center trunk
      const leftBrainX = width * 0.2;
      const rightBrainX = width * 0.8;
      const brainY = height * 0.5;
      const trunkX = width * 0.5;
      const trunkY = height * 0.55;

      // Left beam
      ctx.beginPath();
      ctx.moveTo(leftBrainX, brainY);
      ctx.quadraticCurveTo(width * 0.35, height * 0.6, trunkX, trunkY);
      ctx.strokeStyle = 'rgba(192, 132, 252, 0.25)';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Left moving photon
      const lpT = (tick * 0.8) % 1;
      const lx = (1 - lpT) * (1 - lpT) * leftBrainX + 2 * (1 - lpT) * lpT * (width * 0.35) + lpT * lpT * trunkX;
      const ly = (1 - lpT) * (1 - lpT) * brainY + 2 * (1 - lpT) * lpT * (height * 0.6) + lpT * lpT * trunkY;
      ctx.beginPath();
      ctx.arc(lx, ly, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#c084fc';
      ctx.shadowBlur = 12;
      ctx.shadowColor = '#c084fc';
      ctx.fill();
      ctx.shadowBlur = 0;

      // Right beam
      ctx.beginPath();
      ctx.moveTo(rightBrainX, brainY);
      ctx.quadraticCurveTo(width * 0.65, height * 0.6, trunkX, trunkY);
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Right moving photon
      const rpT = (tick * 0.8 + 0.5) % 1;
      const rx = (1 - rpT) * (1 - rpT) * rightBrainX + 2 * (1 - rpT) * rpT * (width * 0.65) + rpT * rpT * trunkX;
      const ry = (1 - rpT) * (1 - rpT) * brainY + 2 * (1 - rpT) * rpT * (height * 0.6) + rpT * rpT * trunkY;
      ctx.beginPath();
      ctx.arc(rx, ry, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#38bdf8';
      ctx.shadowBlur = 12;
      ctx.shadowColor = '#38bdf8';
      ctx.fill();
      ctx.shadowBlur = 0;

      // Vertical trunk energy conduit (Roots -> Ouroboros -> Memcastle)
      ctx.beginPath();
      ctx.moveTo(trunkX, height * 0.85);
      ctx.lineTo(trunkX, height * 0.15);
      ctx.strokeStyle = 'rgba(251, 191, 36, 0.15)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Rising sap energy pulses up the sacred trunk
      for (let i = 0; i < 3; i++) {
        const pulseT = (tick * 0.35 + i * 0.33) % 1;
        const py = height * 0.82 - pulseT * (height * 0.65);
        ctx.beginPath();
        ctx.arc(trunkX + Math.sin(pulseT * 8) * 3, py, 2.5 + Math.sin(tick * 2) * 0.8, 0, Math.PI * 2);
        ctx.fillStyle = i === 1 ? '#34d399' : '#fbbf24';
        ctx.shadowBlur = 14;
        ctx.shadowColor = i === 1 ? '#34d399' : '#fbbf24';
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // Draw floating cosmic particles
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.alpha * (0.6 + 0.4 * Math.sin(tick + p.x));
        ctx.shadowBlur = 8;
        ctx.shadowColor = p.color;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1.0;
      });

      animId = requestAnimationFrame(render);
    };

    render();

    // Smooth Ship & Energy animation tick
    const shipInterval = setInterval(() => {
      setShipOffset((s) => (s + 0.4) % 100);
      setEnergyPulse((p) => (p + 1) % 100);
    }, 40);

    return () => {
      cancelAnimationFrame(animId);
      clearInterval(shipInterval);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <div 
      className="relative w-full h-full min-h-[720px] flex flex-col items-center justify-between p-3 select-none overflow-hidden rounded-2xl border border-cyan-500/25 bg-[#030712]/95 backdrop-blur-2xl shadow-[0_0_50px_rgba(0,0,0,0.9),inset_0_0_35px_rgba(6,182,212,0.05)] font-mono"
      id="world-tree-arena"
    >
      {/* Dynamic Animated Canvas Backdrop */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none z-0" />

      {/* Floating Interactive Mode Overlay HUD */}
      <div className="absolute top-2 right-2 z-30 flex items-center gap-1.5 bg-slate-950/80 px-2 py-1 rounded-lg border border-cyan-900/60 text-[9px] text-cyan-300">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
        <span>HOLO_ENGINE: ACTIVE</span>
      </div>

      {/* ================= 1. APEX: REDIS MEMCASTLE ================= */}
      <div 
        onClick={onOpenMemcastle}
        onMouseEnter={() => setActiveZone('memcastle')}
        onMouseLeave={() => setActiveZone(null)}
        className="relative z-20 flex flex-col items-center cursor-pointer group transition-all duration-300 transform hover:scale-105"
        id="btn-inspect-memcastle-apex"
      >
        {/* Luminous Castle Title Badge */}
        <div className="text-center mb-1">
          <h2 className="text-sm font-bold tracking-widest text-cyan-300 font-sans uppercase drop-shadow-[0_0_12px_rgba(34,211,238,0.8)]">
            REDIS MEMCASTLE
          </h2>
          <span className="text-[11px] font-mono text-cyan-400/90 font-medium tracking-wide">
            /vfs/mempalace/*
          </span>
        </div>

        {/* Illuminated Gothic Castle Citadel Graphic (SVG) */}
        <div className="relative w-72 sm:w-84 h-36 flex items-center justify-center">
          {/* Ambient Glow */}
          <div className="absolute -inset-4 bg-gradient-to-t from-cyan-500/30 via-purple-600/30 to-blue-500/20 blur-xl opacity-80 group-hover:opacity-100 transition-opacity"></div>

          <svg className="w-full h-full drop-shadow-[0_0_20px_rgba(168,85,247,0.7)]" viewBox="0 0 320 160" fill="none">
            <defs>
              <linearGradient id="spireGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="50%" stopColor="#818cf8" />
                <stop offset="100%" stopColor="#c084fc" />
              </linearGradient>
              <linearGradient id="wallGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#1e1b4b" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#0f172a" stopOpacity="0.95" />
              </linearGradient>
              <filter id="neonCastleGlow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2.5" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Castle Base Structure */}
            <path d="M40,140 L280,140 L260,100 L60,100 Z" fill="url(#wallGrad)" stroke="#38bdf8" strokeWidth="1.5" />
            <path d="M60,100 L260,100 L240,65 L80,65 Z" fill="url(#wallGrad)" stroke="#818cf8" strokeWidth="1.5" />
            
            {/* Center Grand Cathedral Spire */}
            <path d="M160,10 L145,55 L175,55 Z" fill="url(#spireGrad)" stroke="#c084fc" strokeWidth="1.5" filter="url(#neonCastleGlow)" />
            <rect x="148" y="55" width="24" height="45" fill="#1e1b4b" stroke="#38bdf8" strokeWidth="1.5" />
            <path d="M160,65 L160,85" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" />
            <circle cx="160" cy="8" r="3.5" fill="#facc15" filter="url(#neonCastleGlow)" />

            {/* Flanking Main Spires */}
            <path d="M120,30 L110,65 L130,65 Z" fill="url(#spireGrad)" stroke="#38bdf8" strokeWidth="1.2" />
            <rect x="112" y="65" width="16" height="35" fill="#1e1b4b" stroke="#818cf8" strokeWidth="1.2" />
            <circle cx="120" cy="28" r="2.5" fill="#38bdf8" />

            <path d="M200,30 L190,65 L210,65 Z" fill="url(#spireGrad)" stroke="#38bdf8" strokeWidth="1.2" />
            <rect x="192" y="65" width="16" height="35" fill="#1e1b4b" stroke="#818cf8" strokeWidth="1.2" />
            <circle cx="200" cy="28" r="2.5" fill="#38bdf8" />

            {/* Outer Tower Spires */}
            <path d="M85,45 L78,75 L92,75 Z" fill="url(#spireGrad)" stroke="#818cf8" strokeWidth="1" />
            <rect x="80" y="75" width="10" height="25" fill="#0f172a" stroke="#818cf8" strokeWidth="1" />
            <circle cx="85" cy="43" r="2" fill="#c084fc" />

            <path d="M235,45 L228,75 L242,75 Z" fill="url(#spireGrad)" stroke="#818cf8" strokeWidth="1" />
            <rect x="230" y="75" width="10" height="25" fill="#0f172a" stroke="#818cf8" strokeWidth="1" />
            <circle cx="235" cy="43" r="2" fill="#c084fc" />

            {/* Far Wing Spires */}
            <path d="M55,60 L50,85 L60,85 Z" fill="url(#spireGrad)" stroke="#38bdf8" strokeWidth="1" />
            <path d="M265,60 L260,85 L270,85 Z" fill="url(#spireGrad)" stroke="#38bdf8" strokeWidth="1" />

            {/* Arched Crystal Windows */}
            {[-60, -30, 0, 30, 60].map((offset, i) => (
              <g key={i}>
                <path 
                  d={`M${160 + offset - 6},115 A6,6 0 0,1 ${160 + offset + 6},115 L${160 + offset + 6},130 L${160 + offset - 6},130 Z`} 
                  fill="#0369a1" 
                  stroke="#38bdf8" 
                  strokeWidth="1" 
                />
                <circle cx={160 + offset} cy={120} r="1.5" fill="#facc15" />
              </g>
            ))}

            {/* Radiant Starlight & Energy Beams */}
            <line x1="160" y1="140" x2="160" y2="160" stroke="#38bdf8" strokeWidth="2" strokeDasharray="3 2" />
          </svg>
        </div>

        {/* Hotspot tooltip on hover */}
        {activeZone === 'memcastle' && (
          <div className="absolute top-full mt-1 px-3 py-1.5 rounded-lg bg-slate-950/90 border border-cyan-400 text-cyan-200 text-[10px] shadow-[0_0_15px_rgba(34,211,238,0.5)] z-40 animate-fade-in">
            <span>Citadel: In-Memory VFS // Click to inspect memory palaces</span>
          </div>
        )}
      </div>

      {/* ================= 2. CENTER SECTION: WORLD TREE, TWIN BRAINS & OUROBOROS ================= */}
      <div className="relative z-10 w-full flex items-center justify-between px-2 sm:px-4 my-auto">
        
        {/* ---------- LEFT BRAIN: OPEN-NOTEBOOK (DEEP REASONING ENGINE) ---------- */}
        <div 
          onClick={onOpenTwinBrains}
          onMouseEnter={() => setActiveZone('open-notebook')}
          onMouseLeave={() => setActiveZone(null)}
          className="flex flex-col items-center cursor-pointer group transition-all duration-300 transform hover:-translate-x-1 hover:scale-105"
          id="btn-inspect-open-notebook"
        >
          {/* Label Header */}
          <div className="text-center mb-1">
            <h3 className="text-xs font-bold tracking-wider text-purple-200 font-sans uppercase">
              OPEN-NOTEBOOK
            </h3>
            <span className="text-[9px] font-mono text-purple-300 block font-medium">
              lfnovo/open-notebook
            </span>
            <span className="text-[8px] px-1.5 py-0.2 rounded bg-purple-950/90 text-cyan-300 border border-purple-800">
              PORT 8502 // ACTIVE
            </span>
          </div>

          {/* Glowing Neural Brain Sphere & Axon Mesh */}
          <div className="relative w-32 sm:w-38 h-32 sm:h-38 rounded-full bg-gradient-to-tr from-purple-950/80 via-[#260f3d]/70 to-[#4c1d95]/40 border-2 border-purple-400/80 p-2 flex items-center justify-center shadow-[0_0_35px_rgba(192,132,252,0.45)] backdrop-blur-md">
            {/* Animated Synaptic Rings */}
            <div className="absolute inset-0 rounded-full border border-purple-300/30 animate-ping opacity-25 pointer-events-none"></div>

            {/* Neural Brain SVG Network */}
            <svg className="w-full h-full" viewBox="0 0 100 100" fill="none">
              {/* Dual Hemispheres */}
              <path 
                d="M48,20 C30,20 18,32 18,50 C18,68 30,80 48,80 C48,65 44,50 48,20 Z" 
                fill="#3b0764" 
                stroke="#c084fc" 
                strokeWidth="1.5" 
              />
              <path 
                d="M52,20 C70,20 82,32 82,50 C82,68 70,80 52,80 C52,65 56,50 52,20 Z" 
                fill="#3b0764" 
                stroke="#c084fc" 
                strokeWidth="1.5" 
              />
              
              {/* Synaptic Nodes */}
              <circle cx="34" cy="36" r="3" fill="#facc15" className="animate-pulse" />
              <circle cx="28" cy="52" r="2.5" fill="#38bdf8" />
              <circle cx="38" cy="65" r="3" fill="#34d399" />
              <circle cx="66" cy="36" r="3" fill="#facc15" className="animate-pulse" />
              <circle cx="72" cy="52" r="2.5" fill="#38bdf8" />
              <circle cx="62" cy="65" r="3" fill="#34d399" />
              <circle cx="50" cy="48" r="4" fill="#fbbf24" />

              {/* Connecting Neural Axons */}
              <line x1="34" y1="36" x2="50" y2="48" stroke="#c084fc" strokeWidth="1.2" />
              <line x1="28" y1="52" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
              <line x1="38" y1="65" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
              <line x1="66" y1="36" x2="50" y2="48" stroke="#c084fc" strokeWidth="1.2" />
              <line x1="72" y1="52" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
              <line x1="62" y1="65" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
            </svg>
          </div>

          {/* Fiber Optic Cables leading to Tree Roots */}
          <div className="w-16 h-8 flex flex-col items-center">
            <div className="w-0.5 h-6 bg-gradient-to-b from-purple-400 to-emerald-400 shadow-[0_0_8px_#c084fc]"></div>
          </div>
        </div>

        {/* ---------- CENTER: YGGDRASIL TRUNK & GOLDEN OUROBOROS SSM ---------- */}
        <div className="relative flex-1 flex flex-col items-center max-w-lg mx-2">
          
          {/* Canopy Leaves & Bioluminescent Foliage (SVG) */}
          <div className="relative w-full h-72 sm:h-84 flex items-center justify-center">
            <svg className="w-full h-full" viewBox="0 0 300 240" fill="none">
              <defs>
                <linearGradient id="goldTrunkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#78350f" />
                  <stop offset="50%" stopColor="#b45309" />
                  <stop offset="100%" stopColor="#d97706" />
                </linearGradient>
                <linearGradient id="snakeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#f59e0b" />
                  <stop offset="30%" stopColor="#fde047" />
                  <stop offset="70%" stopColor="#fbbf24" />
                  <stop offset="100%" stopColor="#d97706" />
                </linearGradient>
                <filter id="goldGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Spreading Cyber Canopy Branches */}
              <path d="M150,110 Q90,70 40,50 Q70,30 110,40 Q150,20 190,40 Q230,30 260,50 Q210,70 150,110 Z" fill="#065f46" fillOpacity="0.3" stroke="#34d399" strokeWidth="1.5" />
              <path d="M150,110 Q100,50 60,20 Q110,25 150,30 Q190,25 240,20 Q200,50 150,110 Z" fill="#047857" fillOpacity="0.25" stroke="#22d3ee" strokeWidth="1.2" />
              
              {/* Canopy Synapse Nodes */}
              {[
                { x: 45, y: 48, c: '#34d399' },
                { x: 75, y: 32, c: '#22d3ee' },
                { x: 115, y: 25, c: '#fbbf24' },
                { x: 150, y: 15, c: '#38bdf8' },
                { x: 185, y: 25, c: '#fbbf24' },
                { x: 225, y: 32, c: '#22d3ee' },
                { x: 255, y: 48, c: '#34d399' },
                { x: 100, y: 65, c: '#c084fc' },
                { x: 200, y: 65, c: '#c084fc' }
              ].map((pt, i) => (
                <circle key={i} cx={pt.x} cy={pt.y} r="3" fill={pt.c} filter="url(#goldGlow)" />
              ))}

              {/* Main Ancient Tree Trunk */}
              <path 
                d="M130,220 C132,160 138,130 144,100 L156,100 C162,130 168,160 170,220 Z" 
                fill="url(#goldTrunkGrad)" 
                stroke="#f59e0b" 
                strokeWidth="2" 
              />

              {/* Golden Coiled Ouroboros Serpent 3D Spirals */}
              {/* Coil 1 (Upper) */}
              <path 
                d="M125,120 C140,110 160,110 175,122 C185,130 175,138 150,136 C130,134 120,128 125,120 Z" 
                fill="url(#snakeGrad)" 
                stroke="#fde047" 
                strokeWidth="1.5"
                filter="url(#goldGlow)" 
              />
              {/* Coil 2 (Middle) */}
              <path 
                d="M120,150 C140,138 165,138 180,152 C190,162 178,170 150,168 C125,166 112,160 120,150 Z" 
                fill="url(#snakeGrad)" 
                stroke="#fde047" 
                strokeWidth="1.5"
                filter="url(#goldGlow)" 
              />
              {/* Coil 3 (Lower) */}
              <path 
                d="M115,182 C140,168 170,168 185,185 C195,195 180,205 150,202 C120,200 108,192 115,182 Z" 
                fill="url(#snakeGrad)" 
                stroke="#fde047" 
                strokeWidth="1.5"
                filter="url(#goldGlow)" 
              />

              {/* Serpent Crown & Head */}
              <path d="M175,115 C185,110 190,115 185,125 C178,128 170,122 175,115 Z" fill="#fde047" stroke="#b45309" strokeWidth="1.5" />
              <circle cx="182" cy="118" r="1.5" fill="#ef4444" />
            </svg>

            {/* Inscribed Mathematical Formulas on Trunk */}
            <div 
              onClick={onOpenOuroboros}
              className="absolute inset-0 flex flex-col items-center justify-center cursor-pointer group"
              id="btn-inspect-ouroboros-trunk"
            >
              <div className="px-3 py-1 rounded bg-slate-950/80 border border-amber-400/80 text-center shadow-[0_0_15px_rgba(245,158,11,0.5)] backdrop-blur-sm group-hover:scale-105 transition-transform">
                <span className="text-xs font-mono font-bold text-amber-300 tracking-wider">
                  W_ij ∈ {'{-1, 0, 1}'}
                </span>
                <span className="block text-[8px] font-mono text-amber-400 font-semibold uppercase">
                  O(1) STATE LOOP // OUROBOROS SSM
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* ---------- RIGHT BRAIN: NOTEBOOKLM (LOGICAL SYNCHRONIZER) ---------- */}
        <div 
          onClick={onOpenTwinBrains}
          onMouseEnter={() => setActiveZone('notebooklm')}
          onMouseLeave={() => setActiveZone(null)}
          className="flex flex-col items-center cursor-pointer group transition-all duration-300 transform hover:translate-x-1 hover:scale-105"
          id="btn-inspect-notebooklm"
        >
          {/* Label Header */}
          <div className="text-center mb-1">
            <h3 className="text-xs font-bold tracking-wider text-purple-200 font-sans uppercase">
              NOTEBOOKLM
            </h3>
            <span className="text-[9px] font-mono text-purple-300/80 font-medium">
              LOGICAL SYNCHRONIZER
            </span>
          </div>

          {/* Glowing Neural Brain Sphere */}
          <div className="relative w-32 sm:w-38 h-32 sm:h-38 rounded-full bg-gradient-to-tl from-purple-950/80 via-[#260f3d]/70 to-[#0e7490]/40 border-2 border-purple-400/80 p-2 flex items-center justify-center shadow-[0_0_35px_rgba(192,132,252,0.45)] backdrop-blur-md">
            {/* Animated Synaptic Rings */}
            <div className="absolute inset-0 rounded-full border border-cyan-300/30 animate-ping opacity-25 pointer-events-none"></div>

            {/* Neural Brain SVG Network */}
            <svg className="w-full h-full" viewBox="0 0 100 100" fill="none">
              {/* Dual Hemispheres */}
              <path 
                d="M48,20 C30,20 18,32 18,50 C18,68 30,80 48,80 C48,65 44,50 48,20 Z" 
                fill="#3b0764" 
                stroke="#c084fc" 
                strokeWidth="1.5" 
              />
              <path 
                d="M52,20 C70,20 82,32 82,50 C82,68 70,80 52,80 C52,65 56,50 52,20 Z" 
                fill="#3b0764" 
                stroke="#c084fc" 
                strokeWidth="1.5" 
              />
              
              {/* Synaptic Nodes */}
              <circle cx="34" cy="36" r="3" fill="#38bdf8" className="animate-pulse" />
              <circle cx="28" cy="52" r="2.5" fill="#fbbf24" />
              <circle cx="38" cy="65" r="3" fill="#34d399" />
              <circle cx="66" cy="36" r="3" fill="#38bdf8" className="animate-pulse" />
              <circle cx="72" cy="52" r="2.5" fill="#fbbf24" />
              <circle cx="62" cy="65" r="3" fill="#34d399" />
              <circle cx="50" cy="48" r="4" fill="#38bdf8" />

              {/* Connecting Neural Axons */}
              <line x1="34" y1="36" x2="50" y2="48" stroke="#c084fc" strokeWidth="1.2" />
              <line x1="28" y1="52" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
              <line x1="38" y1="65" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
              <line x1="66" y1="36" x2="50" y2="48" stroke="#c084fc" strokeWidth="1.2" />
              <line x1="72" y1="52" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
              <line x1="62" y1="65" x2="50" y2="48" stroke="#c084fc" strokeWidth="1" />
            </svg>
          </div>

          {/* Fiber Optic Cables */}
          <div className="w-16 h-8 flex flex-col items-center">
            <div className="w-0.5 h-6 bg-gradient-to-b from-purple-400 to-emerald-400 shadow-[0_0_8px_#c084fc]"></div>
          </div>
        </div>

      </div>

      {/* ================= 3. BASE: EMERALD DATA RIVERS & VIKING LONGSHIPS ================= */}
      <div 
        onClick={onOpenViking}
        onMouseEnter={() => setActiveZone('viking-rivers')}
        onMouseLeave={() => setActiveZone(null)}
        className="relative z-10 w-full max-w-3xl flex flex-col items-center cursor-pointer group"
        id="btn-inspect-emerald-rivers"
      >
        {/* Radial Concentric Cyber Runic Floor Rings & River Paths */}
        <div className="relative w-full h-24 flex items-center justify-center">
          <svg className="w-full h-full" viewBox="0 0 600 100" fill="none">
            <defs>
              <linearGradient id="riverGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#047857" />
                <stop offset="30%" stopColor="#10b981" />
                <stop offset="50%" stopColor="#22d3ee" />
                <stop offset="70%" stopColor="#10b981" />
                <stop offset="100%" stopColor="#047857" />
              </linearGradient>
            </defs>

            {/* Concentric Cybernetic Ground Rings */}
            <ellipse cx="300" cy="50" rx="280" ry="40" stroke="#064e3b" strokeWidth="2" strokeDasharray="6 4" />
            <ellipse cx="300" cy="50" rx="200" ry="28" stroke="#047857" strokeWidth="1.5" />
            <ellipse cx="300" cy="50" rx="120" ry="18" stroke="#10b981" strokeWidth="1.5" />

            {/* Radial River Channels radiating from Tree Roots */}
            <path d="M300,10 C260,35 150,60 50,75" stroke="url(#riverGrad)" strokeWidth="4" strokeLinecap="round" />
            <path d="M300,10 C280,40 220,65 160,85" stroke="url(#riverGrad)" strokeWidth="3" />
            <path d="M300,10 C300,45 300,70 300,90" stroke="url(#riverGrad)" strokeWidth="4" />
            <path d="M300,10 C320,40 380,65 440,85" stroke="url(#riverGrad)" strokeWidth="3" />
            <path d="M300,10 C340,35 450,60 550,75" stroke="url(#riverGrad)" strokeWidth="4" strokeLinecap="round" />

            {/* Moving Viking Ships on Data Rivers */}
            {/* Left Viking Ship 1 */}
            <g transform={`translate(${140 + Math.sin(shipOffset * 0.1) * 8}, ${55 + Math.cos(shipOffset * 0.1) * 3}) scale(0.65)`}>
              <path d="M0,15 Q25,25 50,15 L45,22 Q25,28 5,22 Z" fill="#78350f" stroke="#fbbf24" strokeWidth="1.5" />
              <path d="M25,0 L25,18 M15,5 L35,5 L25,15 Z" fill="#0284c7" stroke="#38bdf8" strokeWidth="1" />
              <circle cx="15" cy="18" r="2.5" fill="#f59e0b" />
              <circle cx="25" cy="19" r="2.5" fill="#22d3ee" />
              <circle cx="35" cy="18" r="2.5" fill="#f59e0b" />
            </g>

            {/* Right Viking Ship 2 */}
            <g transform={`translate(${420 - Math.sin(shipOffset * 0.1) * 8}, ${55 + Math.sin(shipOffset * 0.1) * 3}) scale(0.65)`}>
              <path d="M0,15 Q25,25 50,15 L45,22 Q25,28 5,22 Z" fill="#78350f" stroke="#fbbf24" strokeWidth="1.5" />
              <path d="M25,0 L25,18 M15,5 L35,5 L25,15 Z" fill="#0284c7" stroke="#38bdf8" strokeWidth="1" />
              <circle cx="15" cy="18" r="2.5" fill="#22d3ee" />
              <circle cx="25" cy="19" r="2.5" fill="#f59e0b" />
              <circle cx="35" cy="18" r="2.5" fill="#22d3ee" />
            </g>
          </svg>
        </div>
      </div>

      {/* ================= 4. CENTER BOTTOM: vKG_HUD INSIGNIA ================= */}
      <div className="relative z-20 flex flex-col items-center text-center mt-1 pb-1">
        <div className="flex items-center gap-1.5 mb-0.5">
          <div className="w-4 h-4 rounded-sm bg-cyan-950 border border-cyan-400 flex items-center justify-center shadow-[0_0_8px_#22d3ee]">
            <Layers className="w-2.5 h-2.5 text-cyan-300" />
          </div>
          <h4 className="text-xs font-bold font-mono tracking-widest text-cyan-300 uppercase">
            vKG_HUD
          </h4>
        </div>
        <h3 className="text-xs sm:text-sm font-bold tracking-wider text-white font-sans uppercase drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]">
          THE SOVEREIGN WORLD TREE CONTROL CENTER
        </h3>
        <p className="text-[9px] font-mono text-cyan-400/80 tracking-wide">
          WHERE MYTHIC ARCHITECTURE MEETS ENGINEERED INTELLIGENCE
        </p>
      </div>

    </div>
  );
};
