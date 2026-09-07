import React, { useState, useEffect, useCallback } from 'react';
import { X, Brain, Activity, Database, ArrowRightLeft, Cpu, Network, Zap } from 'lucide-react';

interface TwinBrainsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const TwinBrainsModal: React.FC<TwinBrainsModalProps> = ({ isOpen, onClose }) => {
  const [isPlaying, setIsPlaying] = useState(true);
  const [syncRate, setSyncRate] = useState<number>(3); // hz
  const [contextWindow, setContextWindow] = useState<number>(8); // k tokens
  
  const [telemetry, setTelemetry] = useState({
    activeSynapses: 1420,
    openNotebookTokens: 1250,
    notebookLmTokens: 1250,
    syncLatency: 24,
    embeddingMagnitude: 0.84,
  });

  const [activeTransfers, setActiveTransfers] = useState<{id: number, dir: 'left' | 'right', type: string, prog: number}[]>([]);

  const tickSimulation = useCallback(() => {
    setTelemetry(prev => {
      // Fluctuate tokens slightly based on window size
      const maxTokens = contextWindow * 1000;
      const targetTokens = maxTokens * (0.6 + Math.random() * 0.3);
      
      return {
        activeSynapses: Math.floor(1000 + Math.random() * 800 + (syncRate * 100)),
        openNotebookTokens: Math.floor(prev.openNotebookTokens + (targetTokens - prev.openNotebookTokens) * 0.1),
        notebookLmTokens: Math.floor(prev.notebookLmTokens + (targetTokens - prev.notebookLmTokens) * 0.1),
        syncLatency: Math.max(5, Math.floor(20 - (syncRate * 2) + Math.random() * 10)),
        embeddingMagnitude: 0.7 + Math.random() * 0.25
      };
    });

    setActiveTransfers(prev => {
      const advanced = prev.map(t => ({ ...t, prog: t.prog + (syncRate * 2) })).filter(t => t.prog < 100);
      
      // Spawn new transfers based on sync rate
      if (Math.random() < (syncRate / 10)) {
        advanced.push({
          id: Math.random(),
          dir: Math.random() > 0.5 ? 'left' : 'right',
          type: ['Semantic Vec', 'Context Diff', 'Graph Node', 'Memory Ref'][Math.floor(Math.random() * 4)],
          prog: 0
        });
      }
      return advanced;
    });
  }, [syncRate, contextWindow]);

  useEffect(() => {
    if (!isOpen || !isPlaying) return;
    const interval = setInterval(tickSimulation, 50);
    return () => clearInterval(interval);
  }, [isOpen, isPlaying, tickSimulation]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/80 backdrop-blur-md p-2 sm:p-4">
      <div className="bg-[#050505] border-2 border-purple-500/50 rounded-2xl w-full max-w-5xl overflow-hidden shadow-[0_0_50px_rgba(168,85,247,0.2)] flex flex-col font-mono relative animate-in zoom-in-95 duration-200 max-h-[95vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-purple-900/50 bg-[#0a0512] shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Brain className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-purple-300 font-bold tracking-wider sm:text-base text-sm uppercase">Twin Brains Matrix</h2>
              <p className="text-[10px] sm:text-xs text-purple-500/70 uppercase">Open-Notebook ⟷ NotebookLM Cognitive Synapse</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* Left Column: Controls & Telemetry */}
            <div className="lg:col-span-5 space-y-4">
              
              <div className="p-4 bg-purple-950/10 border border-purple-900/30 rounded-xl space-y-4 shadow-inner">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-purple-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest">Synaptic Telemetry</h3>
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-black p-2 rounded border border-purple-900/50">
                    <div className="text-[9px] text-slate-500">ACTIVE SYNAPSES</div>
                    <div className="text-sm font-bold text-cyan-400">{telemetry.activeSynapses.toLocaleString()}</div>
                  </div>
                  <div className="bg-black p-2 rounded border border-purple-900/50">
                    <div className="text-[9px] text-slate-500">SYNC LATENCY</div>
                    <div className="text-sm font-bold text-emerald-400">{telemetry.syncLatency} ms</div>
                  </div>
                </div>

                <div className="pt-3 border-t border-purple-900/40 space-y-3">
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-slate-500">Open-Notebook Context Window</span>
                      <span className="text-purple-300 font-bold">{telemetry.openNotebookTokens.toLocaleString()} / {(contextWindow * 1000).toLocaleString()} tks</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden">
                      <div className="h-full bg-cyan-500" style={{ width: `${(telemetry.openNotebookTokens / (contextWindow * 1000)) * 100}%` }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-slate-500">NotebookLM Context Window</span>
                      <span className="text-purple-300 font-bold">{telemetry.notebookLmTokens.toLocaleString()} / {(contextWindow * 1000).toLocaleString()} tks</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500" style={{ width: `${(telemetry.notebookLmTokens / (contextWindow * 1000)) * 100}%` }} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Cortex Controls */}
              <div className="p-4 bg-black border border-slate-800 rounded-xl space-y-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-purple-500" />
                    <h3 className="text-xs font-bold text-purple-400 uppercase tracking-widest">Cortex Controls</h3>
                  </div>
                  <button 
                    onClick={() => setIsPlaying(!isPlaying)}
                    className={`text-[10px] px-2 py-1 rounded border transition-colors ${isPlaying ? 'bg-amber-950/30 text-amber-500 border-amber-900' : 'bg-emerald-950/30 text-emerald-500 border-emerald-900'}`}
                  >
                    {isPlaying ? 'SUSPEND BRIDGE' : 'ENGAGE BRIDGE'}
                  </button>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Synaptic Sync Rate (Hz)</span>
                      <span className="text-purple-400 font-bold">{syncRate} Hz</span>
                    </div>
                    <input 
                      type="range" min="1" max="20" step="1"
                      value={syncRate} onChange={(e) => setSyncRate(parseInt(e.target.value))}
                      className="w-full accent-purple-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Context Window Allocation</span>
                      <span className="text-cyan-400 font-bold">{contextWindow}K Tokens</span>
                    </div>
                    <div className="grid grid-cols-4 gap-2">
                      {[4, 8, 16, 32].map(size => (
                        <button
                          key={size}
                          onClick={() => setContextWindow(size)}
                          className={`py-1.5 rounded text-[10px] font-bold border transition-colors ${contextWindow === size ? 'bg-cyan-950/50 border-cyan-500/50 text-cyan-400' : 'bg-slate-900 border-slate-800 text-slate-500 hover:border-slate-600'}`}
                        >
                          {size}K
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Visualization */}
            <div className="lg:col-span-7 flex flex-col gap-4">
              
              <div className="bg-[#020205] border border-purple-900/40 rounded-xl p-4 flex flex-col h-72 relative overflow-hidden shadow-inner">
                <div className="flex justify-between items-center z-10 relative mb-4">
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                    <Network className="w-4 h-4 text-purple-400" />
                    Bi-Directional Knowledge Graph Bridge
                  </h3>
                  <div className="text-[10px] text-purple-400 font-mono flex items-center gap-1">
                    <Zap className="w-3 h-3"/> MAG: {telemetry.embeddingMagnitude.toFixed(3)}
                  </div>
                </div>

                {/* Cognitive Bridge Visualization */}
                <div className="flex-1 relative flex items-center justify-between px-6 z-10">
                  
                  {/* Left Brain: Open Notebook */}
                  <div className="flex flex-col items-center gap-3 w-1/4">
                    <div className={`w-20 h-20 rounded-full border-2 flex items-center justify-center transition-all duration-300 ${isPlaying ? 'bg-cyan-950/40 border-cyan-400 shadow-[0_0_30px_rgba(34,211,238,0.4)]' : 'bg-slate-900 border-slate-700'}`}>
                      <Database className={`w-8 h-8 ${isPlaying ? 'text-cyan-300' : 'text-slate-600'}`} />
                    </div>
                    <div className="text-center">
                      <div className="text-xs font-bold text-cyan-400">Open-Notebook</div>
                      <div className="text-[9px] text-slate-500">Local Vector DB</div>
                    </div>
                  </div>

                  {/* Bridge */}
                  <div className="flex-1 h-12 relative flex items-center justify-center">
                    <div className="absolute w-full h-[1px] bg-slate-800" />
                    <div className="absolute w-full h-[1px] bg-slate-800 top-2" />
                    <div className="absolute w-full h-[1px] bg-slate-800 bottom-2" />
                    
                    {/* Active Packets */}
                    {activeTransfers.map(t => (
                      <div 
                        key={t.id}
                        className="absolute h-6 flex flex-col items-center justify-center transition-all duration-[50ms]"
                        style={{
                          left: t.dir === 'right' ? `${t.prog}%` : `${100 - t.prog}%`,
                          transform: 'translateX(-50%)'
                        }}
                      >
                        <div className={`text-[8px] font-bold mb-1 px-1 rounded bg-black/80 whitespace-nowrap ${t.dir === 'right' ? 'text-cyan-400' : 'text-emerald-400'}`}>
                          {t.type}
                        </div>
                        <div className={`w-3 h-1.5 rounded-full ${t.dir === 'right' ? 'bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)]' : 'bg-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.8)]'}`} />
                      </div>
                    ))}

                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-black px-3 py-1 rounded-full border border-purple-900/50 flex items-center gap-2">
                      <ArrowRightLeft className={`w-4 h-4 ${isPlaying ? 'text-purple-400 animate-pulse' : 'text-slate-600'}`} />
                    </div>
                  </div>

                  {/* Right Brain: NotebookLM */}
                  <div className="flex flex-col items-center gap-3 w-1/4">
                    <div className={`w-20 h-20 rounded-full border-2 flex items-center justify-center transition-all duration-300 ${isPlaying ? 'bg-emerald-950/40 border-emerald-400 shadow-[0_0_30px_rgba(16,185,129,0.4)]' : 'bg-slate-900 border-slate-700'}`}>
                      <Brain className={`w-8 h-8 ${isPlaying ? 'text-emerald-300' : 'text-slate-600'}`} />
                    </div>
                    <div className="text-center">
                      <div className="text-xs font-bold text-emerald-400">NotebookLM</div>
                      <div className="text-[9px] text-slate-500">Audio/Synthesis Engine</div>
                    </div>
                  </div>

                </div>
                
                {/* Background grid */}
                <div className="absolute inset-0 pointer-events-none opacity-20 bg-[linear-gradient(rgba(168,85,247,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(168,85,247,0.1)_1px,transparent_1px)] bg-[length:20px_20px] z-0" />
              </div>

              {/* Context Footer */}
              <div className="p-3 bg-purple-950/20 border border-purple-900/40 rounded-xl flex-1 flex flex-col justify-end">
                <div className="text-[10px] text-slate-400 leading-relaxed font-mono">
                  <span className="text-purple-400 font-bold">COGNITIVE_SYNC:</span> The Twin Brains matrix continuously bridges the deterministic local graph database (Open-Notebook) with the generative synthesis models (NotebookLM). It streams semantic diffs via Port 8502, ensuring both cognitive engines share an identical understanding of the user's worldview without redundant processing.
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
