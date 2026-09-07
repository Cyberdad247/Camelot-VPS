import React, { useState, useEffect } from 'react';
import { Activity, Maximize2, Minimize2 } from 'lucide-react';
import { SystemVitals } from '../types';

interface SystemTelemetryProps {
  vitals: SystemVitals;
  onOpenDetails?: () => void;
}

export const SystemTelemetry: React.FC<SystemTelemetryProps> = ({ vitals, onOpenDetails }) => {
  const [history, setHistory] = useState<number[]>([72, 75, 71, 78, 82, 74, 76, 80, 78, 77, 81, 78]);

  useEffect(() => {
    const timer = setInterval(() => {
      setHistory((prev) => {
        const nextVal = Math.min(86, Math.max(68, Math.round(78 + (Math.random() * 6 - 3))));
        return [...prev.slice(1), nextVal];
      });
    }, 1500);

    return () => clearInterval(timer);
  }, []);

  const usedGB = (vitals.usedRamMB / 1024).toFixed(2);
  const totalGB = (vitals.totalRamMB / 1024).toFixed(2);

  // SVG Waveform sparkline path
  const width = 140;
  const height = 48;
  const points = history
    .map((val, idx) => {
      const x = (idx / (history.length - 1)) * width;
      const y = height - ((val - 50) / 50) * height;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div 
      className="hud-panel hud-glint hud-depth-2 rounded-xl p-3 flex flex-col justify-between h-full group font-mono"
      id="bento-system-telemetry"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1.5">
        <div>
          <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
            SYSTEM TELEMETRY
          </h3>
          <span className="text-[9px] text-slate-400 block font-normal">
            8GB RAM // REAL-TIME
          </span>
        </div>
        <div className="flex items-center gap-1 text-slate-500 hover:text-cyan-400 cursor-pointer" onClick={onOpenDetails}>
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Main Row: Memory Allocation Ring + Utilization Sparkline */}
      <div className="grid grid-cols-2 gap-3 my-2 items-center">
        
        {/* Left: Memory Allocation Donut Meter */}
        <div className="flex flex-col items-center text-center">
          <span className="text-[9px] text-slate-400 font-semibold uppercase tracking-wider mb-1">
            MEMORY ALLOCATION
          </span>
          <div className="relative w-18 h-18 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              {/* Background Track */}
              <circle cx="50" cy="50" r="38" fill="transparent" stroke="#0f172a" strokeWidth="10" />
              {/* Active Ring (78%) */}
              <circle
                cx="50"
                cy="50"
                r="38"
                fill="transparent"
                stroke="#facc15"
                strokeWidth="10"
                strokeDasharray="238.7"
                strokeDashoffset="52.5"
                strokeLinecap="round"
                className="drop-shadow-[0_0_8px_rgba(250,204,21,0.6)]"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-base font-bold text-amber-300">78%</span>
            </div>
          </div>
          <div className="mt-1 text-[8px] text-slate-300">
            <span className="text-cyan-300 font-bold">{usedGB} GB USED</span>
            <span className="block text-slate-400">{totalGB} GB TOTAL</span>
          </div>
        </div>

        {/* Right: Utilization Over Time Oscilloscope */}
        <div className="flex flex-col justify-between h-full">
          <span className="text-[9px] text-slate-400 font-semibold uppercase tracking-wider text-right">
            UTILIZATION OVER TIME
          </span>
          
          <div className="relative h-14 w-full bg-[#020612]/90 rounded border border-cyan-950/80 p-1 flex items-center">
            {/* Axis Y scale markers */}
            <div className="absolute left-1 inset-y-1 flex flex-col justify-between text-[7px] text-slate-600 font-mono pointer-events-none">
              <span>100%</span>
              <span>50%</span>
              <span>0%</span>
            </div>

            {/* Live Green Oscilloscope Line */}
            <svg className="w-full h-full pl-5" viewBox={`0 0 ${width} ${height}`}>
              <polyline
                fill="none"
                stroke="#10b981"
                strokeWidth="1.8"
                points={points}
                className="drop-shadow-[0_0_6px_rgba(16,185,129,0.8)]"
              />
            </svg>
          </div>

          <div className="text-right text-[8px] text-slate-500 mt-1 font-mono">
            60 SECONDS
          </div>
        </div>

      </div>
    </div>
  );
};
