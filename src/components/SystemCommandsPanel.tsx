import React from 'react';
import { Terminal, Maximize2, Minimize2 } from 'lucide-react';

interface SystemCommandsPanelProps {
  onInitWorldTree: () => void;
  onSyncAllEngines: () => void;
  onFlushContext: () => void;
  onOptimizeMemory: () => void;
  onRunDiagnostics: () => void;
  onOpenBootstrapScript: () => void;
  onOpenSovereignLaws: () => void;
}

export const SystemCommandsPanel: React.FC<SystemCommandsPanelProps> = ({
  onInitWorldTree,
  onSyncAllEngines,
  onFlushContext,
  onOptimizeMemory,
  onRunDiagnostics
}) => {
  const commands = [
    { label: 'INIT_WORLD_TREE', action: onInitWorldTree },
    { label: 'SYNC_ALL_ENGINES', action: onSyncAllEngines },
    { label: 'FLUSH_CONTEXT', action: onFlushContext },
    { label: 'OPTIMIZE_MEMORY', action: onOptimizeMemory },
    { label: 'RUN_DIAGNOSTICS', action: onRunDiagnostics },
    { label: 'SHUTDOWN_GRACEFULLY', action: () => alert('Sovereign graceful shutdown sequence armed.') }
  ];

  return (
    <div 
      className="hud-panel hud-glint hud-depth-2 rounded-xl p-3 flex flex-col justify-between h-full group font-mono text-[10px]"
      id="bento-system-commands"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1.5 mb-1.5">
        <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
          SYSTEM COMMANDS
        </h3>
        <div className="flex items-center gap-1.5 text-slate-500 hover:text-cyan-400 cursor-pointer">
          <Minimize2 className="w-3 h-3" />
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Command List */}
      <div className="space-y-1 my-auto">
        {commands.map((cmd, idx) => (
          <button
            key={idx}
            onClick={cmd.action}
            className="w-full text-left py-1 px-2 rounded hover:bg-cyan-950/40 text-slate-300 hover:text-cyan-200 transition-colors flex items-center gap-1.5 group/btn border border-transparent hover:border-cyan-500/30"
          >
            <span className="text-cyan-400 font-bold group-hover/btn:translate-x-0.5 transition-transform">
              &gt;
            </span>
            <span className="text-[10px] font-mono tracking-wide font-medium">
              {cmd.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};
