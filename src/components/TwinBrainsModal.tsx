import React, { useState, useEffect } from 'react';
import { 
  X, 
  Brain, 
  ExternalLink, 
  Github, 
  ShieldCheck,
  Activity
} from 'lucide-react';
import confetti from 'canvas-confetti';

interface TwinBrainsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const TwinBrainsModal: React.FC<TwinBrainsModalProps> = ({ isOpen, onClose }) => {
  const [imageLoaded, setImageLoaded] = useState(false);

  useEffect(() => {
    if (isOpen) {
      confetti({ particleCount: 40, spread: 70, origin: { y: 0.8 }, colors: ['#a855f7', '#06b6d4', '#eab308'] });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-6 bg-black/90 backdrop-blur-xl animate-fadeIn">
      <div className="relative w-full max-w-6xl h-[95vh] rounded-2xl bg-[#030712] border-2 border-cyan-500/30 shadow-[0_0_80px_rgba(34,211,238,0.2)] flex flex-col overflow-hidden">
        
        {/* ================= MODAL HEADER ================= */}
        <div className="flex-none p-4 border-b border-cyan-500/20 bg-gradient-to-r from-[#0a1128] via-[#050914] to-[#030712]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-purple-950/90 to-cyan-950/80 border border-purple-400/50 shadow-[0_0_20px_rgba(192,132,252,0.4)]">
                <Brain className="w-7 h-7 text-purple-300 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[10px] text-purple-400 font-bold uppercase tracking-widest">
                    SOVEREIGN COGNITIVE PIPELINE
                  </span>
                  <a 
                    href="https://github.com/lfnovo/open-notebook.git"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 px-2 py-0.5 text-[9px] bg-purple-500/20 hover:bg-purple-500/30 text-purple-200 rounded border border-purple-400/50 transition-all font-bold"
                  >
                    <Github className="w-3 h-3" />
                    <span>lfnovo/open-notebook</span>
                    <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                  <span className="px-2 py-0.5 text-[9px] bg-cyan-950/60 text-cyan-300 rounded border border-cyan-800">
                    PORT 8502 // LIVE
                  </span>
                </div>
                <h2 className="text-xl sm:text-2xl font-bold text-white font-heraldic tracking-wide flex items-center gap-2">
                  TWIN QUANTUM BRAINS
                  <span className="text-sm font-terminal text-cyan-400 font-normal opacity-80">[SYS_ACTIVE]</span>
                </h2>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/30 border border-emerald-900/50 text-emerald-400 text-xs font-mono">
                <Activity className="w-4 h-4" />
                <span>ALL SYSTEMS OPTIMAL</span>
              </div>
              <button
                onClick={onClose}
                className="p-2.5 rounded-xl bg-slate-900 hover:bg-rose-950 text-slate-400 hover:text-rose-200 border border-slate-800 hover:border-rose-900/50 transition-all"
                title="Close Dashboard"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>

        {/* ================= HIGH-RES UI DASHBOARD IMAGE ================= */}
        <div className="flex-1 relative bg-[#02040a] flex items-center justify-center p-4 sm:p-6 overflow-hidden">
          {/* Background Ambient Glow */}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.08)_0%,transparent_60%)] pointer-events-none" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(192,132,252,0.05)_0%,transparent_70%)] pointer-events-none translate-x-[20%]" />

          {/* Image Container */}
          <div className="relative w-full h-full max-h-full rounded-xl overflow-hidden border-2 border-cyan-900/40 shadow-[0_0_60px_rgba(34,211,238,0.15)] group">
            {!imageLoaded && (
              <div className="absolute inset-0 flex items-center justify-center text-cyan-500/50 flex-col gap-3">
                <Brain className="w-12 h-12 animate-bounce" />
                <span className="font-mono text-sm tracking-widest animate-pulse">ESTABLISHING NEURAL LINK...</span>
              </div>
            )}
            
            <img
              src="https://i.postimg.cc/kG4W01Nv/wan2-5-preview-a-Hyperrealistic-3D-Un-(1).png"
              alt="Dynamic Twin Brains & Memcastle VFS Dashboard"
              className={`w-full h-full object-contain bg-black transition-opacity duration-1000 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
              onLoad={() => setImageLoaded(true)}
            />

            {/* CRT Scanline Overlay Effect */}
            <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%] opacity-20 mix-blend-overlay" />
            
            {/* Holographic scanning bar */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-30 animate-scan pointer-events-none" />
          </div>
        </div>

        {/* ================= MODAL FOOTER ================= */}
        <div className="flex-none p-4 border-t border-cyan-500/20 bg-[#030712] flex items-center justify-between text-xs">
          <div className="flex items-center gap-3 text-slate-400 font-mono text-[11px]">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span>Cryptographic VFS Signature: <span className="text-emerald-400 font-bold">VERIFIED_Z3_SAT</span></span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700">8GB Scarcity Protocol Active</span>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="https://github.com/lfnovo/open-notebook.git"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-purple-300 border border-purple-900/50 font-bold transition-all"
            >
              <Github className="w-4 h-4" />
              <span>lfnovo/open-notebook</span>
            </a>

            <button
              onClick={onClose}
              className="px-6 py-2 rounded-lg bg-gradient-to-r from-cyan-900 to-purple-900 hover:from-cyan-800 hover:to-purple-800 text-cyan-100 border border-cyan-500/50 font-bold tracking-wider transition-all shadow-[0_0_15px_rgba(34,211,238,0.2)]"
            >
              DISENGAGE LINK
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
