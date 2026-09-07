import React from 'react';
import { Maximize2 } from 'lucide-react';

interface VikingRefractionsProps {
  onOpenDetails?: () => void;
}

export const VikingRefractions: React.FC<VikingRefractionsProps> = ({ onOpenDetails }) => {
  const streams = [
    { label: 'DATA STREAMS', percent: 85 },
    { label: 'CHARACTER STATES', percent: 68 },
    { label: 'PROMPT SCAFFOLDING', percent: 92 },
    { label: 'AGENT DAG EXECUTION', percent: 74 },
    { label: 'CONTEXT HYDRATION', percent: 88 },
    { label: 'SANDBOX BOUNDARY', percent: 100 }
  ];

  return (
    <div 
      className="hud-panel hud-panel-emerald hud-depth-2 rounded-xl p-3 flex flex-col justify-between h-full group font-mono text-[10px]"
      id="bento-viking-refractions"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1 mb-1">
        <div>
          <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
            VFS REFRACTIONS // OPEN VIKING PROTOCOL
          </h3>
          <span className="text-[9px] text-cyan-400 font-mono block">
            /vfs/refractions/*
          </span>
        </div>
        <div className="flex items-center gap-1 text-slate-500 hover:text-cyan-400 cursor-pointer" onClick={onOpenDetails}>
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Main Row: Stream Progress Bars + Glowing Viking Longship */}
      <div className="grid grid-cols-12 gap-2 items-center my-1">
        
        {/* Left: 6 Data Stream Bars (Span 7) */}
        <div className="col-span-7 space-y-1">
          {streams.map((st, idx) => (
            <div key={idx} className="space-y-0.5">
              <div className="flex items-center justify-between text-[7.5px] text-slate-400 font-semibold uppercase">
                <span>{st.label}</span>
              </div>
              <div className="w-full h-1.5 bg-slate-900 rounded-sm overflow-hidden border border-cyan-950/80">
                <div 
                  className="h-full bg-gradient-to-r from-emerald-500 via-cyan-400 to-emerald-400 rounded-sm shadow-[0_0_6px_rgba(52,211,153,0.5)]"
                  style={{ width: `${st.percent}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Right: Glowing Cyan/Emerald Holographic Viking Drakkar Ship (Span 5) */}
        <div className="col-span-5 flex items-center justify-center">
          <div className="relative w-24 h-24 flex items-center justify-center">
            {/* Ambient ship glow */}
            <div className="absolute inset-0 bg-emerald-500/20 blur-lg rounded-full"></div>

            <svg className="w-full h-full drop-shadow-[0_0_10px_rgba(16,185,129,0.8)]" viewBox="0 0 120 120" fill="none">
              {/* Dragon Prow & Hull */}
              <path 
                d="M15,80 Q60,95 105,80 L100,90 Q60,105 20,90 Z" 
                fill="#064e3b" 
                stroke="#10b981" 
                strokeWidth="2" 
              />
              <path d="M15,80 Q10,65 5,60 Q12,65 18,75" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" />
              <path d="M105,80 Q110,70 115,65 Q110,75 102,78" stroke="#34d399" strokeWidth="2" />

              {/* Shields along gunwale */}
              {[30, 42, 54, 66, 78, 90].map((x, i) => (
                <circle key={i} cx={x} cy={84} r="4" fill="#0284c7" stroke="#38bdf8" strokeWidth="1" />
              ))}

              {/* Mast & Runic Sail */}
              <line x1="60" y1="25" x2="60" y2="80" stroke="#34d399" strokeWidth="2" />
              <line x1="40" y1="30" x2="80" y2="30" stroke="#34d399" strokeWidth="2" />
              <path 
                d="M40,30 Q60,40 80,30 L85,65 Q60,75 35,65 Z" 
                fill="#0f766e" 
                fillOpacity="0.8" 
                stroke="#22d3ee" 
                strokeWidth="1.5" 
              />

              {/* Norse / Celtic Rune Compass on Sail */}
              <circle cx="60" cy="48" r="8" stroke="#facc15" strokeWidth="1" strokeDasharray="2 2" />
              <path d="M60,40 L60,56 M52,48 L68,48 M54,42 L66,54 M54,54 L66,42" stroke="#facc15" strokeWidth="1" />
              
              {/* Oars in water */}
              <line x1="35" y1="88" x2="25" y2="100" stroke="#10b981" strokeWidth="1.2" strokeLinecap="round" />
              <line x1="50" y1="88" x2="40" y2="100" stroke="#10b981" strokeWidth="1.2" strokeLinecap="round" />
              <line x1="65" y1="88" x2="55" y2="100" stroke="#10b981" strokeWidth="1.2" strokeLinecap="round" />
              <line x1="80" y1="88" x2="70" y2="100" stroke="#10b981" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </div>
        </div>

      </div>
    </div>
  );
};
