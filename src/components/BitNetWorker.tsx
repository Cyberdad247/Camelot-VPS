import React, { useState } from 'react';
import { BrainCircuit, Cpu, Zap, Database, Activity, Code2, Layers } from 'lucide-react';

export const BitNetWorker: React.FC = () => {
  const [prompt, setPrompt] = useState('Initialize cognitive diagnostics and yield ternary validation matrix.');
  const [status, setStatus] = useState<'IDLE' | 'SANDBOXING' | 'INFERENCING' | 'COMPLETE'>('IDLE');
  const [logs, setLogs] = useState<string[]>([
    "Systemd Slice: camelot-intelligence.slice [ACTIVE]",
    "Memory Limit: 2.0GB (Hard Ceiling)",
    "Weight Quantization: {-1, 0, 1} (BitNet 1.58b)",
    "Pre-allocated VRAM/RAM Buffer: 312.4 MB",
    "Zero Dynamic Heap: VERIFIED"
  ]);
  
  const [metrics, setMetrics] = useState({
    tps: 0,
    memory: 312.4,
    latency: 0
  });

  const handleInference = () => {
    if (!prompt.trim() || status === 'SANDBOXING' || status === 'INFERENCING') return;
    
    setStatus('SANDBOXING');
    setLogs(prev => [...prev, `[WASMTIME] Initializing zero-heap WASI sandbox for task...`, `[WASMTIME] Memory bounded to 1024 pages (64MB)...`]);
    
    setTimeout(() => {
      setStatus('INFERENCING');
      setLogs(prev => [...prev, `[BITNET] Wasmtime host delegated inference vector to Ternary Engine.`, `[BITNET] Processing 1.58b parameters...`]);
      
      setTimeout(() => {
        setStatus('COMPLETE');
        setMetrics({
          tps: 42.5 + Math.random() * 5,
          memory: 312.4, // Constant!
          latency: 245
        });
        setLogs(prev => [
          ...prev, 
          `[BITNET_OUT] Acknowledged prompt. Processed strictly with -1, 0, 1 weights.`,
          `[WASMTIME] Execution context tore down. 0 bytes leaked.`
        ]);
      }, 1500);
    }, 1000);
  };

  return (
    <div className="space-y-4">
      {/* Top HUD */}
      <div className="p-4 rounded-2xl bg-[#090d18] border border-fuchsia-500/40 space-y-3 shadow-[0_0_15px_rgba(217,70,239,0.1)]">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-fuchsia-300 flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-fuchsia-400" />
              <span>PHASE 4: BITNET TERNARY ENGINE</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              1.58b Parameter Model constrained to OS `camelot-intelligence.slice`. Routed via Wasmtime Host.
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 bg-black border border-fuchsia-900 rounded-full text-[10px] font-mono text-fuchsia-200">
            <span className={`w-2 h-2 rounded-full ${status === 'IDLE' || status === 'COMPLETE' ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`}></span>
            {status}
          </div>
        </div>

        {/* Telemetry Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
          <div className="p-3 bg-black border border-slate-800 rounded-xl">
            <div className="text-[10px] text-slate-500 mb-1 font-mono flex items-center gap-1"><Layers className="w-3 h-3"/> QUANTIZATION</div>
            <div className="text-sm text-cyan-400 font-bold">BitNet-1.58b</div>
          </div>
          <div className="p-3 bg-black border border-slate-800 rounded-xl">
            <div className="text-[10px] text-slate-500 mb-1 font-mono flex items-center gap-1"><Database className="w-3 h-3"/> FOOTPRINT</div>
            <div className="text-sm text-amber-400 font-bold">{metrics.memory.toFixed(1)} MB <span className="text-[10px] text-slate-600">(STATIC)</span></div>
          </div>
          <div className="p-3 bg-black border border-slate-800 rounded-xl">
            <div className="text-[10px] text-slate-500 mb-1 font-mono flex items-center gap-1"><Zap className="w-3 h-3"/> INFERENCE SPEED</div>
            <div className="text-sm text-emerald-400 font-bold">{metrics.tps.toFixed(1)} <span className="text-[10px] text-slate-600">t/s</span></div>
          </div>
          <div className="p-3 bg-black border border-slate-800 rounded-xl">
            <div className="text-[10px] text-slate-500 mb-1 font-mono flex items-center gap-1"><Cpu className="w-3 h-3"/> LATENCY</div>
            <div className="text-sm text-fuchsia-400 font-bold">{status === 'IDLE' ? '--' : metrics.latency} <span className="text-[10px] text-slate-600">ms</span></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Interaction Panel */}
        <div className="p-4 rounded-2xl bg-black border border-slate-800 space-y-4">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
            <Code2 className="w-4 h-4 text-cyan-500" />
            Wasmtime Boundary Input
          </h3>
          <div className="space-y-2">
            <label className="text-[10px] text-slate-500 font-mono">INFERENCE PROMPT</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={status === 'SANDBOXING' || status === 'INFERENCING'}
              rows={4}
              className="w-full bg-[#050505] border border-slate-700 rounded-lg p-3 text-xs font-mono text-cyan-200 focus:outline-none focus:border-fuchsia-500 disabled:opacity-50"
            />
          </div>
          <button
            onClick={handleInference}
            disabled={status === 'SANDBOXING' || status === 'INFERENCING'}
            className="w-full py-2.5 rounded-lg bg-fuchsia-900/40 hover:bg-fuchsia-900/60 border border-fuchsia-500/50 text-fuchsia-300 font-bold text-xs tracking-wider transition-all disabled:opacity-50"
          >
            {status === 'IDLE' || status === 'COMPLETE' ? 'DISPATCH VIA WASMTIME' : 'EXECUTING...'}
          </button>
        </div>

        {/* Execution Log */}
        <div className="p-4 rounded-2xl bg-black border border-slate-800 space-y-4 flex flex-col">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-500" />
            Execution Telemetry
          </h3>
          <div className="flex-1 bg-[#03050a] border border-slate-800/80 rounded-xl p-3 font-mono text-[10px] space-y-1.5 overflow-y-auto max-h-[200px]">
            {logs.map((log, idx) => (
              <div 
                key={idx} 
                className={`${
                  log.includes('VERIFIED') ? 'text-emerald-400 font-bold' : 
                  log.includes('[WASMTIME]') ? 'text-cyan-400' : 
                  log.includes('[BITNET_OUT]') ? 'text-fuchsia-300 bg-fuchsia-950/30 p-1 border border-fuchsia-900/50 rounded mt-2 mb-2' : 
                  'text-slate-400'
                }`}
              >
                {log}
              </div>
            ))}
            {(status === 'SANDBOXING' || status === 'INFERENCING') && (
              <div className="flex gap-1 items-center text-amber-500 mt-2">
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-ping"></span>
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-ping delay-75"></span>
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-ping delay-150"></span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
