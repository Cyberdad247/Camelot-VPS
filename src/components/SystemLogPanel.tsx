import React, { useState, useRef, useEffect } from 'react';
import { Terminal, Maximize2, Send } from 'lucide-react';
import { TerminalLog } from '../types';

interface SystemLogPanelProps {
  logs: TerminalLog[];
  onExecuteCommand: (cmd: string) => void;
}

export const SystemLogPanel: React.FC<SystemLogPanelProps> = ({ logs, onExecuteCommand }) => {
  const [inputVal, setInputVal] = useState('');
  const logEndRef = useRef<HTMLDivElement | null>(null);

  // Exact 7 log events from reference image
  const defaultLogDisplay = [
    { time: '12:00:01', text: 'WORLD_TREE_BOOTSTRAP... OK', color: 'text-cyan-300' },
    { time: '12:00:01', text: 'MEMCASTLE_LINK... OK', color: 'text-emerald-300' },
    { time: '12:00:01', text: 'OUROBOROS_SSM... OK', color: 'text-amber-300' },
    { time: '12:00:02', text: 'TWIN_BRAINS_SYNC... OK', color: 'text-purple-300' },
    { time: '12:00:02', text: 'VFS_REFRACTIONS... OK', color: 'text-emerald-300' },
    { time: '12:00:02', text: 'GRAPHIFY_ENGINE... OK', color: 'text-cyan-300' },
    { time: '12:00:03', text: 'SYSTEM ONLINE', color: 'text-cyan-400 font-bold' }
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    onExecuteCommand(inputVal.trim());
    setInputVal('');
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div 
      className="hud-panel hud-glint hud-depth-1 rounded-xl p-3 flex flex-col justify-between h-full group font-mono text-[10px]"
      id="bento-system-log"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1.5 mb-1.5">
        <div className="flex items-center gap-1.5">
          <Terminal className="w-3.5 h-3.5 text-cyan-400" />
          <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
            SYSTEM LOG
          </h3>
        </div>
        <div className="flex items-center gap-1 text-slate-500 hover:text-cyan-400 cursor-pointer">
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Log Feed */}
      <div className="bg-[#020612]/90 rounded p-2 border border-cyan-950/80 space-y-1 h-32 overflow-y-auto">
        {/* Render base 7 lines */}
        {defaultLogDisplay.map((item, idx) => (
          <div key={`def-${idx}`} className="flex items-center gap-1.5 leading-tight">
            <span className="text-slate-500 text-[9px]">[{item.time}]</span>
            <span className={`text-[9px] ${item.color}`}>{item.text}</span>
          </div>
        ))}

        {/* Dynamic real-time execution logs if any added */}
        {logs.slice(7).map((log) => (
          <div key={log.id} className="flex items-center gap-1.5 leading-tight">
            <span className="text-slate-500 text-[9px]">[{log.timestamp}]</span>
            <span className={`text-[9px] ${
              log.level === 'success' ? 'text-emerald-300 font-semibold' :
              log.level === 'command' ? 'text-amber-300' :
              log.level === 'sovereign' ? 'text-cyan-300 font-bold' :
              log.level === 'z3' ? 'text-purple-300' :
              'text-slate-300'
            }`}>
              {log.message}
            </span>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>

      {/* Interactive Command Input */}
      <form onSubmit={handleSubmit} className="mt-2 flex items-center gap-1.5">
        <span className="text-cyan-400 font-bold text-[10px]">&gt;</span>
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Execute sovereign command..."
          className="flex-1 bg-slate-950/80 border border-cyan-900/60 rounded px-2 py-1 text-[9px] text-cyan-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-400"
        />
        <button type="submit" className="p-1 rounded bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-500/30">
          <Send className="w-2.5 h-2.5" />
        </button>
      </form>
    </div>
  );
};
