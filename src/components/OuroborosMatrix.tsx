import React, { useState, useEffect } from 'react';
import { Maximize2, Sparkles } from 'lucide-react';

interface OuroborosMatrixProps {
  onOpenDetails?: () => void;
}

export const OuroborosMatrix: React.FC<OuroborosMatrixProps> = ({ onOpenDetails }) => {
  // 5x9 matrix from screenshot
  const initialMatrix = [
    [-1,  1,  1,  1, -1,  0,  1,  1,  1],
    [-1,  0,  0, -1,  1,  0,  0,  0,  1],
    [-3,  0, -1,  1,  0, -1,  0,  0,  1],
    [-1, -1, -2,  0,  0,  0, -1,  0,  0],
    [-1,  1,  1,  0,  0,  0,  1,  1, -1]
  ];

  const [matrix, setMatrix] = useState(initialMatrix);
  const [pulseIndex, setPulseIndex] = useState<{ r: number; c: number } | null>(null);

  // Subtle live matrix state transition pulses
  useEffect(() => {
    const timer = setInterval(() => {
      const r = Math.floor(Math.random() * 5);
      const c = Math.floor(Math.random() * 9);
      setPulseIndex({ r, c });

      setTimeout(() => setPulseIndex(null), 400);
    }, 1800);

    return () => clearInterval(timer);
  }, []);

  return (
    <div 
      className="hud-panel hud-panel-amber hud-glint-amber hud-depth-3 rounded-xl p-3 flex flex-col justify-between h-full group font-mono text-[10px]"
      id="bento-ouroboros-matrix"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1.5 mb-1.5">
        <div>
          <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
            OUROBOROS SSM STATE TRANSITIONS
          </h3>
          <div className="flex items-center gap-1.5 text-[9px]">
            <span className="text-slate-400 uppercase">TERNARY WEIGHT MATRIX</span>
            <span className="text-emerald-400 font-bold">W_ij ∈ {'{-1, 0, 1}'}</span>
          </div>
        </div>
        <div className="flex items-center gap-1 text-slate-500 hover:text-cyan-400 cursor-pointer" onClick={onOpenDetails}>
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Main Section: Matrix Number Grid + Golden Ouroboros Emblem */}
      <div className="grid grid-cols-12 gap-2 items-center my-1">
        
        {/* Left: 5x9 Number Grid (Span 8) */}
        <div className="col-span-8 bg-[#020612]/90 p-1.5 rounded border border-cyan-950/80 flex flex-col justify-between gap-1">
          {matrix.map((row, rIdx) => (
            <div key={rIdx} className="flex items-center justify-between font-mono text-[9px]">
              {row.map((val, cIdx) => {
                const isPulsing = pulseIndex?.r === rIdx && pulseIndex?.c === cIdx;
                return (
                  <span
                    key={cIdx}
                    className={`w-4 text-center transition-all ${
                      isPulsing
                        ? 'text-amber-300 font-bold scale-125'
                        : val > 0
                        ? 'text-cyan-300 font-semibold'
                        : val < 0
                        ? 'text-amber-400 font-medium'
                        : 'text-slate-600'
                    }`}
                  >
                    {val}
                  </span>
                );
              })}
            </div>
          ))}
        </div>

        {/* Right: Golden Ouroboros Circular Emblem (Span 4) */}
        <div className="col-span-4 flex items-center justify-center">
          <div className="relative w-16 h-16 rounded-full border-2 border-amber-400/80 border-dashed animate-rotate-slow flex items-center justify-center shadow-[0_0_20px_rgba(245,158,11,0.5)]">
            <svg className="w-12 h-12" viewBox="0 0 100 100" fill="none">
              <circle cx="50" cy="50" r="38" stroke="#fbbf24" strokeWidth="4" strokeDasharray="18 4" />
              <path d="M78,50 C78,65 65,78 50,78 C35,78 22,65 22,50 C22,35 35,22 50,22 C60,22 70,28 75,36 L70,40" stroke="#f59e0b" strokeWidth="3" />
              <circle cx="70" cy="40" r="3" fill="#ef4444" />
            </svg>
          </div>
        </div>

      </div>

      {/* Footer Metrics */}
      <div className="flex items-center justify-between border-t border-cyan-950/80 pt-1.5 text-[8px] text-slate-400">
        <span>STATE CYCLE: <span className="text-cyan-300 font-bold">1.58 BITS</span></span>
        <span>CONTEXT RECURRENCE: <span className="text-emerald-400 font-bold">STABLE</span></span>
      </div>
    </div>
  );
};
