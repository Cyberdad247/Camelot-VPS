import React, { useState, useEffect, useCallback } from 'react';
import { X, Server, Activity, Database, Key, HardDrive, RefreshCw, Layers } from 'lucide-react';

interface MemcastleModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MemcastleModal: React.FC<MemcastleModalProps> = ({ isOpen, onClose }) => {
  const [isPlaying, setIsPlaying] = useState(true);
  const [cachePressure, setCachePressure] = useState<number>(50); // percentage
  
  const [metrics, setMetrics] = useState({
    hits: 142050,
    misses: 2304,
    memoryUsed: 124.5,
    evictions: 12
  });

  const [activeKeys, setActiveKeys] = useState<{key: string, ttl: number, type: string}[]>([
    { key: 'session:auth:9A4F', ttl: 3400, type: 'STRING' },
    { key: 'agent:state:codex', ttl: 120, type: 'HASH' },
    { key: 'cache:vfs:tree_nodes', ttl: 84500, type: 'SET' },
    { key: 'model:weights:buffer', ttl: 5, type: 'BINARY' },
  ]);

  const simulateTraffic = useCallback(() => {
    setMetrics(prev => {
      // Calculate hits/misses based on pressure
      const trafficVolume = Math.floor(Math.random() * (cachePressure * 2));
      const missRatio = cachePressure > 80 ? 0.15 : 0.02;
      
      const newMisses = Math.floor(trafficVolume * missRatio);
      const newHits = trafficVolume - newMisses;
      
      const newMem = prev.memoryUsed + (newMisses * 0.1) - (cachePressure > 90 ? 2.5 : 0.05);
      const clampedMem = Math.max(50, Math.min(newMem, 256));
      
      const evictions = clampedMem >= 250 ? prev.evictions + Math.floor(Math.random() * 5) : prev.evictions;

      return {
        hits: prev.hits + newHits,
        misses: prev.misses + newMisses,
        memoryUsed: clampedMem,
        evictions
      };
    });

    // Cycle TTLs
    setActiveKeys(prev => {
      const next = prev.map(k => ({ ...k, ttl: Math.max(0, k.ttl - 1) })).filter(k => k.ttl > 0);
      if (next.length < 4 && Math.random() > 0.5) {
        next.push({
          key: `dyn:key:${Math.floor(Math.random() * 10000).toString(16)}`,
          ttl: Math.floor(Math.random() * 60) + 10,
          type: ['STRING', 'HASH', 'LIST'][Math.floor(Math.random() * 3)]
        });
      }
      return next;
    });
  }, [cachePressure]);

  useEffect(() => {
    if (!isOpen || !isPlaying) return;
    const interval = setInterval(simulateTraffic, 100);
    return () => clearInterval(interval);
  }, [isOpen, isPlaying, simulateTraffic]);

  if (!isOpen) return null;

  const hitRatio = metrics.hits / (metrics.hits + metrics.misses) * 100;

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/80 backdrop-blur-md p-2 sm:p-4">
      <div className="bg-[#050505] border-2 border-[#D4AF37]/50 rounded-2xl w-full max-w-5xl overflow-hidden shadow-[0_0_50px_rgba(212,175,55,0.2)] flex flex-col font-mono relative animate-in zoom-in-95 duration-200 max-h-[95vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#D4AF37]/30 bg-[#0a0800] shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#D4AF37]/20 rounded-lg">
              <Server className="w-5 h-5 text-[#D4AF37]" />
            </div>
            <div>
              <h2 className="text-[#D4AF37] font-bold tracking-wider sm:text-base text-sm uppercase">Apex Memcastle</h2>
              <p className="text-[10px] sm:text-xs text-[#D4AF37]/70 uppercase">In-Memory Redis-Compatible KV Datastore</p>
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
              
              <div className="p-4 bg-black border border-slate-800 rounded-xl space-y-4 shadow-inner">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-[#D4AF37]" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest">Cache Telemetry</h3>
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-900/50 p-2 rounded border border-slate-800/80">
                    <div className="text-[9px] text-slate-500">CACHE HITS</div>
                    <div className="text-sm font-bold text-emerald-400">{metrics.hits.toLocaleString()}</div>
                  </div>
                  <div className="bg-slate-900/50 p-2 rounded border border-slate-800/80">
                    <div className="text-[9px] text-slate-500">CACHE MISSES</div>
                    <div className="text-sm font-bold text-red-400">{metrics.misses.toLocaleString()}</div>
                  </div>
                  <div className="bg-slate-900/50 p-2 rounded border border-slate-800/80 col-span-2 flex justify-between items-center">
                    <div className="text-[9px] text-slate-500">HIT RATIO</div>
                    <div className="text-sm font-bold text-cyan-400">{hitRatio.toFixed(2)}%</div>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-800 space-y-3">
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-slate-500">Memory Allocation (Max 256MB)</span>
                      <span className="text-amber-400 font-bold">{metrics.memoryUsed.toFixed(1)} MB</span>
                    </div>
                    <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                      <div 
                        className={`h-full transition-all duration-200 ${metrics.memoryUsed > 220 ? 'bg-red-500' : 'bg-[#D4AF37]'}`}
                        style={{ width: `${(metrics.memoryUsed / 256) * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="text-slate-500">LRU Evictions:</span>
                    <span className="text-red-400 font-bold">{metrics.evictions.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Stress Tester Controls */}
              <div className="p-4 bg-[#D4AF37]/10 border border-[#D4AF37]/30 rounded-xl space-y-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-[#D4AF37]" />
                    <h3 className="text-xs font-bold text-[#D4AF37] uppercase tracking-widest">Load Simulator</h3>
                  </div>
                  <button 
                    onClick={() => setIsPlaying(!isPlaying)}
                    className="text-[10px] px-2 py-1 rounded bg-[#D4AF37]/20 text-[#D4AF37] hover:bg-[#D4AF37]/40 border border-[#D4AF37]/50"
                  >
                    {isPlaying ? 'PAUSE TRAFFIC' : 'RESUME TRAFFIC'}
                  </button>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Traffic Pressure</span>
                    <span className="text-amber-400 font-bold">{cachePressure}%</span>
                  </div>
                  <input 
                    type="range" min="10" max="100" step="5"
                    value={cachePressure} onChange={(e) => setCachePressure(parseInt(e.target.value))}
                    className="w-full accent-[#D4AF37] h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="text-[9px] text-slate-500 leading-tight">
                    Higher pressure forces rapid memory allocation and triggers LRU evictions. Simulates heavy agent DAG message passing.
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Visualization */}
            <div className="lg:col-span-7 flex flex-col gap-4">
              
              <div className="bg-black border border-slate-800 rounded-xl p-4 flex flex-col h-56 relative overflow-hidden shadow-inner">
                <div className="flex justify-between items-center z-10 relative mb-4">
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[#D4AF37]" />
                    Memory Space Visualization
                  </h3>
                  <div className="text-[10px] text-emerald-500 font-mono px-2 py-1 bg-emerald-950/30 rounded border border-emerald-900/50">
                    O(1) ACCESS TIME
                  </div>
                </div>

                {/* Animated Block Allocator */}
                <div className="flex-1 grid grid-cols-12 sm:grid-cols-16 gap-1 content-start relative z-10">
                  {Array.from({ length: 128 }).map((_, i) => {
                    const isAllocated = i < (metrics.memoryUsed / 256) * 128;
                    const isHot = isAllocated && Math.random() < (cachePressure / 200);
                    
                    return (
                      <div 
                        key={i}
                        className={`w-full aspect-square rounded-[2px] transition-all duration-300 ${
                          !isAllocated ? 'bg-slate-900/30 border border-slate-800/30' :
                          isHot ? 'bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)] scale-110 z-10' :
                          'bg-[#D4AF37]/60 border border-[#D4AF37]/40'
                        }`}
                      />
                    );
                  })}
                </div>
              </div>

              {/* Live Key Inspector */}
              <div className="bg-[#D4AF37]/5 border border-[#D4AF37]/20 rounded-xl flex-1 flex flex-col overflow-hidden">
                <div className="flex items-center justify-between border-b border-[#D4AF37]/20 p-3 bg-[#D4AF37]/10">
                  <span className="text-xs font-bold text-[#D4AF37] flex items-center gap-2"><Key className="w-4 h-4"/> Active Keys (Sample)</span>
                  {isPlaying && <RefreshCw className="w-3 h-3 text-[#D4AF37] animate-spin" />}
                </div>
                
                <div className="p-3 space-y-2 overflow-y-auto">
                  {activeKeys.length === 0 ? (
                    <div className="text-[10px] text-slate-500 text-center py-4">No active keys. Buffer empty.</div>
                  ) : activeKeys.map((k, i) => (
                    <div key={i} className="flex items-center justify-between p-2 rounded bg-black border border-slate-800/80">
                      <div className="flex items-center gap-2">
                        <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded border ${
                          k.type === 'STRING' ? 'bg-blue-950/50 text-blue-400 border-blue-900' :
                          k.type === 'HASH' ? 'bg-purple-950/50 text-purple-400 border-purple-900' :
                          'bg-amber-950/50 text-amber-400 border-amber-900'
                        }`}>
                          {k.type}
                        </span>
                        <span className="text-xs text-slate-300 font-mono">{k.key}</span>
                      </div>
                      <div className="text-[10px] font-mono">
                        <span className="text-slate-500">TTL: </span>
                        <span className={k.ttl < 10 ? 'text-red-400 font-bold' : 'text-emerald-400'}>{k.ttl}s</span>
                      </div>
                    </div>
                  ))}
                </div>
                
                <div className="p-3 bg-black/40 border-t border-slate-800/50 text-[10px] text-slate-400 leading-relaxed font-mono">
                  <span className="text-[#D4AF37] font-bold">MEMCASTLE_ARCH:</span> Pure in-memory Key-Value store replacing standard Redis to eliminate 
                  external container dependencies. Implements strict LRU eviction to guarantee the process never exceeds its Omarchy-assigned memory slice.
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
