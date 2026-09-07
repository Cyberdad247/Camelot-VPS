import React, { useRef, useEffect, useState } from 'react';
import { Network, Maximize2 } from 'lucide-react';

interface GraphifyCanvasProps {
  onExpandModal?: () => void;
}

export const GraphifyCanvas: React.FC<GraphifyCanvasProps> = ({ onExpandModal }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [depthLayer, setDepthLayer] = useState(4);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 280);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 120);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener('resize', handleResize);

    // 3D Nodes
    const nodes = [
      { x: 30, y: 30, color: '#34d399', r: 3 },
      { x: 80, y: 20, color: '#22d3ee', r: 4 },
      { x: 50, y: 65, color: '#38bdf8', r: 3.5 },
      { x: 120, y: 45, color: '#f59e0b', r: 5 }, // Center star node
      { x: 170, y: 25, color: '#c084fc', r: 3.5 },
      { x: 160, y: 70, color: '#818cf8', r: 3 },
      { x: 210, y: 40, color: '#f43f5e', r: 3 },
      { x: 200, y: 80, color: '#fbbf24', r: 2.5 }
    ];

    const edges = [
      [0, 1], [0, 2], [1, 2], [1, 3], [2, 3],
      [3, 4], [3, 5], [4, 5], [4, 6], [5, 7], [6, 7]
    ];

    let t = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      t += 0.02;

      // Draw edges with glowing lines
      edges.forEach(([i, j]) => {
        const n1 = nodes[i];
        const n2 = nodes[j];
        ctx.beginPath();
        ctx.moveTo(n1.x + Math.sin(t + i) * 2, n1.y + Math.cos(t + i) * 2);
        ctx.lineTo(n2.x + Math.sin(t + j) * 2, n2.y + Math.cos(t + j) * 2);
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      });

      // Draw nodes
      nodes.forEach((n, idx) => {
        const ox = n.x + Math.sin(t + idx) * 2;
        const oy = n.y + Math.cos(t + idx) * 2;

        ctx.beginPath();
        ctx.arc(ox, oy, n.r, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.shadowBlur = 8;
        ctx.shadowColor = n.color;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <div 
      className="hud-panel hud-glint hud-depth-3 rounded-xl p-3 flex flex-col justify-between h-full group font-mono text-[10px]"
      id="bento-graphify-canvas"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1 mb-1">
        <div>
          <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
            GRAPHIFY 3D&rarr;2D DEPTH SPATIAL NETWORK
          </h3>
          <span className="text-[9px] text-slate-400 block">
            REAL-TIME TOPOLOGY
          </span>
        </div>
        <div className="flex items-center gap-1 text-slate-500 hover:text-cyan-400 cursor-pointer" onClick={onExpandModal}>
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Main Visual: 3D Topology Canvas + Legend */}
      <div className="grid grid-cols-12 gap-2 items-center">
        {/* Canvas on Left (Span 9) */}
        <div className="col-span-9 relative h-22 bg-[#020612]/90 rounded border border-cyan-950/80 overflow-hidden">
          <canvas ref={canvasRef} className="w-full h-full" />
        </div>

        {/* Legend on Right (Span 3) */}
        <div className="col-span-3 flex flex-col justify-between gap-1 text-[8px] text-slate-400 pl-1">
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span> NODES
          </div>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> EDGES
          </div>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span> DEPTH
          </div>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span> WEIGHT
          </div>
        </div>
      </div>

      {/* Depth Layer Slider */}
      <div className="my-1">
        <div className="flex items-center justify-between text-[8px] text-slate-400 mb-0.5">
          <span>DEPTH LAYER</span>
          <span className="text-cyan-400 font-bold">L{depthLayer}</span>
        </div>
        <input 
          type="range" 
          min="1" 
          max="7" 
          value={depthLayer} 
          onChange={(e) => setDepthLayer(Number(e.target.value))}
          className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400" 
        />
      </div>

      {/* Node Analytics 4-column metric bar */}
      <div className="border-t border-cyan-950/80 pt-1">
        <span className="text-[8px] text-slate-500 block uppercase mb-0.5">NODE ANALYTICS</span>
        <div className="grid grid-cols-4 gap-1 text-center font-mono">
          <div>
            <span className="text-[7px] text-slate-400 block">TOTAL NODES</span>
            <span className="text-[10px] font-bold text-cyan-300">10,428</span>
          </div>
          <div>
            <span className="text-[7px] text-slate-400 block">ACTIVE PATHS</span>
            <span className="text-[10px] font-bold text-cyan-300">1,284</span>
          </div>
          <div>
            <span className="text-[7px] text-slate-400 block">AVG DEGREE</span>
            <span className="text-[10px] font-bold text-cyan-300">2.91</span>
          </div>
          <div>
            <span className="text-[7px] text-slate-400 block">CLUSTER COEFF.</span>
            <span className="text-[10px] font-bold text-cyan-300">0.73</span>
          </div>
        </div>
      </div>
    </div>
  );
};
