import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { X, Anchor, Waves, Terminal, Shield, RefreshCw, Cpu, Activity, Play, Pause, Zap, BarChart2 } from 'lucide-react';

interface VikingRefractionsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface DmaChannel {
  id: string;
  name: string;
  target: string;
  baseThroughput: number; // MB/s
  latency: number; // microseconds
  status: 'SYNCHRONIZED' | 'STREAMING' | 'DMA_LOCK' | 'HYDRATED' | 'STALLED';
  progress: number;
}

export const VikingRefractionsModal: React.FC<VikingRefractionsModalProps> = ({ isOpen, onClose }) => {
  const [selectedChannelId, setSelectedChannelId] = useState<string>('ch_0');
  const [isPlaying, setIsPlaying] = useState(true);
  const [streamStress, setStreamStress] = useState<number>(1.0); // 1.0 = normal, 2.0 = double throughput
  const [channels, setChannels] = useState<DmaChannel[]>([
    { id: 'ch_0', name: 'STREAM_CHANNEL_0', target: '/vfs/refractions/char_states', baseThroughput: 1200, latency: 12, status: 'STREAMING', progress: 45 },
    { id: 'ch_1', name: 'STREAM_CHANNEL_1', target: '/vfs/refractions/prompt_scaffolding', baseThroughput: 840, latency: 18, status: 'STREAMING', progress: 15 },
    { id: 'ch_2', name: 'STREAM_CHANNEL_2', target: '/vfs/refractions/agent_dag', baseThroughput: 2100, latency: 9, status: 'DMA_LOCK', progress: 98 },
    { id: 'ch_3', name: 'STREAM_CHANNEL_3', target: '/vfs/refractions/context_hydration', baseThroughput: 1800, latency: 14, status: 'STREAMING', progress: 62 },
    { id: 'ch_4', name: 'STREAM_CHANNEL_4', target: '/vfs/refractions/sandbox_boundary', baseThroughput: 450, latency: 4, status: 'SYNCHRONIZED', progress: 100 }
  ]);
  const [ringBufferIndex, setRingBufferIndex] = useState(0);

  const selectedChannel = useMemo(() => channels.find(c => c.id === selectedChannelId) || channels[0], [channels, selectedChannelId]);

  const tickSimulation = useCallback(() => {
    setChannels(prev => prev.map(ch => {
      if (ch.status === 'SYNCHRONIZED' || ch.status === 'DMA_LOCK') {
        if (Math.random() > 0.95 && ch.status === 'SYNCHRONIZED') {
          return { ...ch, status: 'STREAMING', progress: 0 };
        }
        return ch;
      }
      
      const speedBump = (ch.baseThroughput / 1000) * streamStress * (Math.random() * 0.5 + 0.5);
      const newProgress = Math.min(100, ch.progress + speedBump);
      
      if (newProgress >= 100) {
        return { ...ch, progress: 100, status: 'SYNCHRONIZED' };
      }
      return { ...ch, progress: newProgress, status: 'STREAMING' };
    }));

    setRingBufferIndex(prev => (prev + 1) % 64);
  }, [streamStress]);

  useEffect(() => {
    if (!isOpen || !isPlaying) return;
    const interval = setInterval(tickSimulation, 100);
    return () => clearInterval(interval);
  }, [isOpen, isPlaying, tickSimulation]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/80 backdrop-blur-md p-2 sm:p-4">
      <div className="bg-[#050505] border-2 border-cyan-500/50 rounded-2xl w-full max-w-5xl overflow-hidden shadow-[0_0_50px_rgba(34,211,238,0.2)] flex flex-col font-mono relative animate-in zoom-in-95 duration-200 max-h-[95vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-cyan-900/50 bg-[#000a12] shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Anchor className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-cyan-300 font-bold tracking-wider sm:text-base text-sm uppercase">Open Viking Refraction Protocol</h2>
              <p className="text-[10px] sm:text-xs text-cyan-500/70 uppercase">Emerald Data Rivers / Zero-Copy DMA Streaming</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* Left Column: Channels & Controls */}
            <div className="lg:col-span-5 space-y-4">
              
              <div className="p-4 bg-cyan-950/10 border border-cyan-900/30 rounded-xl space-y-4">
                <div className="flex items-center justify-between border-b border-cyan-900/50 pb-2">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-500" />
                    <h3 className="text-xs font-bold text-cyan-500 uppercase tracking-widest">Operator Controls</h3>
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={() => setIsPlaying(!isPlaying)}
                      className={`p-1.5 rounded border transition-colors ${isPlaying ? 'bg-amber-950/50 border-amber-500/50 text-amber-400' : 'bg-emerald-950/50 border-emerald-500/50 text-emerald-400'}`}
                      title={isPlaying ? "Halt Streaming" : "Resume Streaming"}
                    >
                      {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    </button>
                    <button 
                      onClick={tickSimulation}
                      disabled={isPlaying}
                      className="p-1.5 rounded bg-slate-900 border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">DMA Ring Stress Multiplier</span>
                    <span className="text-cyan-400 font-bold">{streamStress.toFixed(1)}x</span>
                  </div>
                  <input 
                    type="range" min="0.1" max="5.0" step="0.1"
                    value={streamStress} onChange={(e) => setStreamStress(parseFloat(e.target.value))}
                    className="w-full accent-cyan-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="text-[9px] text-slate-500">Accelerates virtual buffer saturation rates for load testing.</div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-1">
                  <span>ACTIVE VFS CHANNELS</span>
                  <span className="text-emerald-400 font-bold">{channels.filter(c=>c.status==='STREAMING').length} STREAMING</span>
                </div>
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                  {channels.map((ch) => (
                    <div
                      key={ch.id}
                      onClick={() => setSelectedChannelId(ch.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        selectedChannelId === ch.id
                          ? 'bg-cyan-950/40 border-cyan-500/60 shadow-[0_0_15px_rgba(34,211,238,0.15)]'
                          : 'bg-black border-slate-800 hover:border-cyan-900/50'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[11px] font-bold mb-1.5">
                        <span className={selectedChannelId === ch.id ? 'text-cyan-300' : 'text-slate-300'}>{ch.name}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded border border-slate-700 bg-slate-900 text-emerald-400">
                          {((ch.baseThroughput * streamStress) / 1024).toFixed(2)} GB/s
                        </span>
                      </div>
                      <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden mb-1 border border-slate-800">
                        <div
                          className={`h-full rounded-full transition-all duration-100 ${
                            ch.status === 'SYNCHRONIZED' ? 'bg-emerald-400' : ch.status === 'DMA_LOCK' ? 'bg-amber-400' : 'bg-gradient-to-r from-cyan-600 to-cyan-400'
                          }`}
                          style={{ width: `${ch.progress}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[9px]">
                        <span className="text-slate-500 font-mono truncate max-w-[140px]">{ch.target}</span>
                        <span className={ch.status === 'SYNCHRONIZED' ? 'text-emerald-500' : 'text-cyan-500'}>{ch.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column: Visualization & Telemetry */}
            <div className="lg:col-span-7 flex flex-col gap-4">
              
              <div className="bg-black border border-slate-800 rounded-xl p-4 flex flex-col h-64 relative overflow-hidden shadow-inner">
                <div className="flex justify-between items-center z-10 relative mb-4">
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                    <Zap className="w-4 h-4 text-cyan-400" />
                    Zero-Copy DMA Ring Buffer
                  </h3>
                  <div className="text-[10px] text-cyan-500 font-mono px-2 py-1 bg-cyan-950/30 rounded border border-cyan-900/50">
                    PTR_OFFSET: 0x{(ringBufferIndex * 128).toString(16).toUpperCase().padStart(4, '0')}
                  </div>
                </div>

                {/* Animated Ring Visualization */}
                <div className="flex-1 flex items-center justify-center relative z-10">
                  <div className="relative w-48 h-48">
                    {/* Background rings */}
                    <div className="absolute inset-2 rounded-full border border-slate-800" />
                    <div className="absolute inset-6 rounded-full border border-slate-800" />
                    <div className="absolute inset-10 rounded-full border border-slate-800" />
                    
                    {/* Active streaming representation */}
                    {Array.from({ length: 16 }).map((_, i) => {
                      const isActive = (i + ringBufferIndex) % 16 < 4;
                      const angle = (i * 360) / 16;
                      return (
                        <div 
                          key={i}
                          className="absolute inset-0 flex items-start justify-center origin-center transition-all duration-100"
                          style={{ transform: `rotate(${angle}deg)` }}
                        >
                          <div className={`w-2 h-4 rounded-full transition-colors ${
                            !isPlaying ? 'bg-slate-700' :
                            isActive ? 'bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.8)]' : 'bg-slate-800'
                          }`} />
                        </div>
                      )
                    })}
                    
                    {/* Center Core */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className={`w-16 h-16 rounded-full border-2 flex items-center justify-center bg-black transition-colors ${
                        isPlaying ? 'border-cyan-500 shadow-[0_0_20px_rgba(34,211,238,0.3)]' : 'border-slate-700'
                      }`}>
                        <Cpu className={`w-6 h-6 ${isPlaying ? 'text-cyan-400' : 'text-slate-600'}`} />
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Scanline overlay */}
                <div className="absolute inset-0 pointer-events-none opacity-5 bg-[linear-gradient(rgba(255,255,255,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%] z-0"></div>
              </div>

              {/* Inspector Panel */}
              <div className="bg-cyan-950/10 border border-cyan-900/40 rounded-xl p-4 flex-1 flex flex-col">
                <div className="flex items-center justify-between border-b border-cyan-900/50 pb-2 mb-3">
                  <span className="text-xs font-bold text-amber-300 flex items-center gap-2"><BarChart2 className="w-4 h-4"/> Channel Inspector</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded border font-bold ${
                    selectedChannel.status === 'SYNCHRONIZED' ? 'bg-emerald-950/50 text-emerald-400 border-emerald-500/50' :
                    selectedChannel.status === 'DMA_LOCK' ? 'bg-amber-950/50 text-amber-400 border-amber-500/50' :
                    'bg-cyan-950/50 text-cyan-400 border-cyan-500/50'
                  }`}>
                    {selectedChannel.status}
                  </span>
                </div>
                
                <div className="space-y-3 text-xs mb-4">
                  <div className="flex justify-between py-1 border-b border-slate-800/50">
                    <span className="text-slate-400">Target Path:</span>
                    <span className="text-cyan-300 font-mono truncate max-w-[250px]" title={selectedChannel.target}>{selectedChannel.target}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800/50">
                    <span className="text-slate-400">Base Throughput:</span>
                    <span className="text-emerald-300 font-bold">{(selectedChannel.baseThroughput / 1024).toFixed(2)} GB/s</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800/50">
                    <span className="text-slate-400">Active Throughput (Stressed):</span>
                    <span className="text-emerald-400 font-bold flex items-center gap-1">
                      {isPlaying ? ((selectedChannel.baseThroughput * streamStress) / 1024).toFixed(2) : '0.00'} GB/s
                      {streamStress > 1 && <Activity className="w-3 h-3 text-amber-500 animate-pulse"/>}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800/50">
                    <span className="text-slate-400">Ring Latency:</span>
                    <span className="text-amber-300 font-bold">{selectedChannel.latency} μs</span>
                  </div>
                </div>
                
                <div className="mt-auto p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-[10px] text-slate-400 leading-relaxed font-mono">
                  <span className="text-emerald-500 font-bold">VIKING_PROTOCOL:</span> Direct Memory Access (DMA) prevents redundant CPU copies by writing directly to the VFS Ring Buffers. This bypasses kernel space, preserving the 8GB ceiling while driving multi-gigabyte throughputs required by the Camelot cognition pipeline.
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
