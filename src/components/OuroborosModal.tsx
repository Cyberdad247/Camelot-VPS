import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { X, Zap, Activity, RefreshCw, Play, Pause, SkipForward, Sliders, HardDrive, Cpu } from 'lucide-react';
import { IOuroborosState, ITernaryVector, TernaryWeight } from '../types/ternary';

interface OuroborosModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const OuroborosModal: React.FC<OuroborosModalProps> = ({ isOpen, onClose }) => {
  const [isPlaying, setIsPlaying] = useState(true);
  const [sparsityTarget, setSparsityTarget] = useState<number>(0.6); // 60% zeros by default
  const [vectorSize, setVectorSize] = useState<number>(64);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(400);

  const [ouroborosState, setOuroborosState] = useState<IOuroborosState>({
    loopId: 'SSM-1.58b-0x9A4F',
    currentStep: 0,
    maxIterations: 1024,
    triggerCondition: 'gradient_threshold > 0.05',
    haltCondition: 'loss < 1e-4',
    fallbackAction: 'TRAP',
    activeVector: {
      id: 'vec_001',
      weights: Array(64).fill(0),
      magnitude: 0
    }
  });

  // Calculate Memory Metrics
  const metrics = useMemo(() => {
    const W = vectorSize;
    const activeW = ouroborosState.activeVector.weights.filter(w => w !== 0).length;
    const sparsity = W === 0 ? 0 : ((W - activeW) / W) * 100;
    
    // 1.58 bits per weight vs 16 bits (FP16)
    const ternaryBits = W * 1.58;
    const ternaryBytes = Math.ceil(ternaryBits / 8);
    const fp16Bytes = W * 2;
    const compressionRatio = fp16Bytes / (ternaryBytes || 1);

    return { activeW, sparsity, ternaryBytes, fp16Bytes, compressionRatio };
  }, [ouroborosState.activeVector.weights, vectorSize]);

  const stepState = useCallback(() => {
    setOuroborosState(prev => {
      // Ensure weights array matches vectorSize
      const currentWeights = prev.activeVector.weights.length === vectorSize 
        ? prev.activeVector.weights 
        : Array(vectorSize).fill(0);

      const newWeights = currentWeights.map(() => {
        const rand = Math.random();
        if (rand < sparsityTarget) return 0 as TernaryWeight;
        // Split remaining probability between -1 and +1
        return Math.random() > 0.5 ? 1 as TernaryWeight : -1 as TernaryWeight;
      });
      
      const magnitude = newWeights.reduce((acc, val) => acc + Math.abs(val), 0);
      
      return {
        ...prev,
        currentStep: prev.currentStep + 1,
        activeVector: {
          ...prev.activeVector,
          weights: newWeights,
          magnitude
        }
      };
    });
  }, [sparsityTarget, vectorSize]);

  useEffect(() => {
    if (!isOpen || !isPlaying) return;
    const interval = setInterval(stepState, playbackSpeed);
    return () => clearInterval(interval);
  }, [isOpen, isPlaying, stepState, playbackSpeed]);

  // Adjust vector when size changes
  useEffect(() => {
    setOuroborosState(prev => ({
      ...prev,
      activeVector: {
        ...prev.activeVector,
        weights: Array(vectorSize).fill(0),
        magnitude: 0
      }
    }));
  }, [vectorSize]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/80 backdrop-blur-md p-2 sm:p-4">
      <div className="bg-[#050505] border-2 border-amber-500/50 rounded-2xl w-full max-w-5xl overflow-hidden shadow-[0_0_50px_rgba(245,158,11,0.2)] flex flex-col font-mono relative animate-in zoom-in-95 duration-200 max-h-[95vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-amber-900/50 bg-[#0a0500] shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <Zap className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h2 className="text-amber-300 font-bold tracking-wider sm:text-base text-sm">OUROBOROS TERNARY INTEGRATION</h2>
              <p className="text-[10px] sm:text-xs text-amber-500/70 uppercase">Comprehensive 1.58-Bit Quantization Control</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* Left Column: Controls & Metrics */}
            <div className="lg:col-span-5 space-y-6">
              
              {/* Telemetry & Metrics */}
              <div className="p-4 bg-black border border-slate-800 rounded-xl space-y-4 shadow-inner">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest">Real-Time Telemetry</h3>
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-900/50 p-2 rounded border border-slate-800/80">
                    <div className="text-[9px] text-slate-500">ITERATION</div>
                    <div className="text-sm font-bold text-cyan-400">{ouroborosState.currentStep}</div>
                  </div>
                  <div className="bg-slate-900/50 p-2 rounded border border-slate-800/80">
                    <div className="text-[9px] text-slate-500">SPARSITY</div>
                    <div className="text-sm font-bold text-purple-400">{metrics.sparsity.toFixed(1)}%</div>
                  </div>
                  <div className="bg-slate-900/50 p-2 rounded border border-slate-800/80">
                    <div className="text-[9px] text-slate-500">MAGNITUDE</div>
                    <div className="text-sm font-bold text-amber-400">{ouroborosState.activeVector.magnitude}</div>
                  </div>
                  <div className="bg-slate-900/50 p-2 rounded border border-slate-800/80">
                    <div className="text-[9px] text-slate-500">ACTIVE PARAMETERS</div>
                    <div className="text-sm font-bold text-emerald-400">{metrics.activeW} / {vectorSize}</div>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="text-slate-500 flex items-center gap-1"><Cpu className="w-3 h-3"/> FP16 Footprint:</span>
                    <span className="text-red-400 font-bold">{metrics.fp16Bytes} Bytes</span>
                  </div>
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="text-slate-500 flex items-center gap-1"><HardDrive className="w-3 h-3"/> Ternary Footprint:</span>
                    <span className="text-emerald-400 font-bold">{metrics.ternaryBytes} Bytes</span>
                  </div>
                  <div className="flex justify-between items-center text-[10px] bg-emerald-950/30 p-1.5 rounded">
                    <span className="text-emerald-500">Compression Ratio:</span>
                    <span className="text-emerald-300 font-bold">{metrics.compressionRatio.toFixed(2)}x</span>
                  </div>
                </div>
              </div>

              {/* Execution Controls */}
              <div className="p-4 bg-amber-950/10 border border-amber-900/30 rounded-xl space-y-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-amber-500" />
                    <h3 className="text-xs font-bold text-amber-500 uppercase tracking-widest">Operator Controls</h3>
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={() => setIsPlaying(!isPlaying)}
                      className={`p-2 rounded border transition-colors ${isPlaying ? 'bg-red-950/50 border-red-500/50 text-red-400 hover:bg-red-900/50' : 'bg-emerald-950/50 border-emerald-500/50 text-emerald-400 hover:bg-emerald-900/50'}`}
                      title={isPlaying ? "Halt Matrix" : "Engage Matrix"}
                    >
                      {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    </button>
                    <button 
                      onClick={stepState}
                      disabled={isPlaying}
                      className="p-2 rounded bg-slate-900 border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      title="Step Forward (Manual)"
                    >
                      <SkipForward className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="space-y-4">
                  {/* Sparsity Target Slider */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Target Sparsity Bias</span>
                      <span className="text-amber-400 font-bold">{(sparsityTarget * 100).toFixed(0)}% Zeroes</span>
                    </div>
                    <input 
                      type="range" 
                      min="0.1" 
                      max="0.95" 
                      step="0.05"
                      value={sparsityTarget} 
                      onChange={(e) => setSparsityTarget(parseFloat(e.target.value))}
                      className="w-full accent-amber-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                    />
                  </div>

                  {/* Vector Size Selection */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Parameter Vector Size</span>
                      <span className="text-cyan-400 font-bold">{vectorSize} Dims</span>
                    </div>
                    <div className="grid grid-cols-4 gap-2">
                      {[64, 128, 256, 512].map(size => (
                        <button
                          key={size}
                          onClick={() => setVectorSize(size)}
                          className={`py-1.5 rounded text-[10px] font-bold border transition-colors ${vectorSize === size ? 'bg-cyan-950/50 border-cyan-500/50 text-cyan-400' : 'bg-black border-slate-800 text-slate-500 hover:border-slate-600'}`}
                        >
                          {size}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Speed Selection */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Clock Speed</span>
                      <span className="text-purple-400 font-bold">{playbackSpeed}ms</span>
                    </div>
                    <input 
                      type="range" 
                      min="50" 
                      max="1000" 
                      step="50"
                      value={playbackSpeed} 
                      onChange={(e) => setPlaybackSpeed(parseInt(e.target.value))}
                      className="w-full accent-purple-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                      style={{ direction: 'rtl' }} // Reverse so left is slower (higher ms), right is faster (lower ms)
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Ternary Visualization Matrix */}
            <div className="lg:col-span-7 space-y-3 flex flex-col h-full">
              <div className="flex justify-between items-center bg-[#0a0a0a] p-3 border border-slate-800 rounded-t-xl shrink-0">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                  <RefreshCw className={`w-3.5 h-3.5 ${isPlaying ? 'animate-spin text-cyan-400' : 'text-slate-500'}`} />
                  Live Tensor Matrix
                </h3>
                <span className="text-[9px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">INT2 / 1.58b</span>
              </div>
              
              <div className="bg-[#020202] border border-slate-800 border-t-0 rounded-b-xl p-4 flex-1 overflow-y-auto min-h-[300px] max-h-[500px]">
                <div className={`grid gap-1.5 ${
                  vectorSize <= 64 ? 'grid-cols-8' : 
                  vectorSize <= 128 ? 'grid-cols-12 sm:grid-cols-16' : 
                  'grid-cols-16 sm:grid-cols-32'
                }`}>
                  {ouroborosState.activeVector.weights.map((w, idx) => (
                    <div 
                      key={idx}
                      className={`
                        flex items-center justify-center rounded text-[10px] sm:text-xs font-bold border transition-all duration-[50ms] aspect-square
                        ${w === -1 ? 'bg-red-950/40 border-red-500/50 text-red-400 shadow-[0_0_8px_rgba(239,68,68,0.3)] scale-110 z-10' : ''}
                        ${w === 0 ? 'bg-slate-900/30 border-slate-800/50 text-slate-700 opacity-50' : ''}
                        ${w === 1 ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.3)] scale-110 z-10' : ''}
                      `}
                    >
                      {w > 0 ? '+' : ''}{w === 0 && vectorSize > 128 ? '' : w}
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Context Footer */}
              <div className="p-3 bg-slate-900/30 border border-slate-800 rounded-xl text-[10px] text-slate-400 leading-relaxed shrink-0">
                The <strong className="text-amber-400">8GB Scarcity Protocol</strong> mandates strict O(1) state resolution. 
                By quantizing state matrices to <strong className="text-cyan-300">[-1, 0, 1]</strong>, FP16 multiplication is eliminated. 
                Operations compile down to hardware-level <span className="font-bold text-emerald-400">ADD / SUB</span> instructions, 
                yielding extreme performance at near-zero dynamic heap cost.
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};
