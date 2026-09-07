import React from 'react';
import { Maximize2 } from 'lucide-react';

interface IpcMemorySlabsProps {
  onOpenDetails?: () => void;
}

export const IpcMemorySlabs: React.FC<IpcMemorySlabsProps> = ({ onOpenDetails }) => {
  // 4 rows x 8 cols = 32 slab bins
  const slabBins = Array.from({ length: 32 }, (_, i) => {
    return i < 12 ? '#facc15' : i < 26 ? '#22d3ee' : '#34d399';
  });

  return (
    <div 
      className="hud-panel hud-glint hud-depth-1 rounded-xl p-3 flex flex-col justify-between h-full group font-mono text-[10px]"
      id="bento-ipc-slabs"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1 mb-1">
        <div>
          <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
            IPC & MEMORY SLAB SYNC
          </h3>
          <span className="text-[9px] text-slate-400 block uppercase">
            SUB-MILLISECOND LATENCY
          </span>
        </div>
        <div className="flex items-center gap-1 text-slate-500 hover:text-cyan-400 cursor-pointer" onClick={onOpenDetails}>
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Main Grid: Latency & Throughput | Slab Matrix | 100% Ring Gauge */}
      <div className="grid grid-cols-12 gap-2 items-center my-1">
        
        {/* Col 1: Latency & Throughput (Span 4) */}
        <div className="col-span-4 space-y-2">
          <div>
            <span className="text-[8px] text-slate-400 uppercase block">LATENCY</span>
            <span className="text-xs font-bold text-cyan-300">0.23 ms</span>
          </div>
          <div>
            <span className="text-[8px] text-slate-400 uppercase block">THROUGHPUT</span>
            <span className="text-xs font-bold text-emerald-400">2.4 GB/s</span>
          </div>
        </div>

        {/* Col 2: Memory Slab Bins Grid (Span 4) */}
        <div className="col-span-4 flex flex-col items-center">
          <span className="text-[8px] text-slate-400 uppercase block mb-1">
            MEMORY SLAB BINS
          </span>
          <div className="grid grid-cols-8 gap-1 p-1 bg-[#020612]/90 rounded border border-cyan-950/80">
            {slabBins.map((color, idx) => (
              <div 
                key={idx}
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  backgroundColor: color,
                  boxShadow: `0 0 4px ${color}`
                }}
              />
            ))}
          </div>
        </div>

        {/* Col 3: Sync Status & 100% Circular Ring (Span 4) */}
        <div className="col-span-4 flex flex-col items-center text-center">
          <span className="text-[7.5px] text-slate-400 uppercase font-semibold">
            SYNC STATUS
          </span>
          <span className="text-[8px] text-emerald-400 font-bold uppercase mb-0.5">
            OPTIMAL
          </span>
          
          <div className="relative w-12 h-12 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 50 50">
              <circle cx="25" cy="25" r="20" fill="transparent" stroke="#0f172a" strokeWidth="5" />
              <circle
                cx="25"
                cy="25"
                r="20"
                fill="transparent"
                stroke="#10b981"
                strokeWidth="5"
                strokeDasharray="125.6"
                strokeDashoffset="0"
                strokeLinecap="round"
                className="drop-shadow-[0_0_6px_rgba(16,185,129,0.8)]"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-[10px] font-bold text-white">100%</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
