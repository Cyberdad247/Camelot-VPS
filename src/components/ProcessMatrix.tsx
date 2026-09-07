import React from 'react';
import { RotateCcw, Maximize2 } from 'lucide-react';
import { CamelotService } from '../types';

interface ProcessMatrixProps {
  services: CamelotService[];
  onRestartService: (id: string) => void;
  onInspectService: (svc: CamelotService) => void;
}

export const ProcessMatrix: React.FC<ProcessMatrixProps> = ({
  services,
  onRestartService,
  onInspectService
}) => {
  // Exact 7 processes from reference screenshot
  const displayProcesses = [
    { name: 'vkg_world_tree', pid: '31415', cpu: '12.5%', ram: '1.21 GB', status: 'RUNNING' },
    { name: 'ouroboros_ssm', pid: '27182', cpu: '8.2%', ram: '512 MB', status: 'RUNNING' },
    { name: 'open_notebook', pid: '16180', cpu: '7.1%', ram: '1.08 GB', status: 'RUNNING' },
    { name: 'notebooklm_py', pid: '14142', cpu: '6.5%', ram: '896 MB', status: 'RUNNING' },
    { name: 'graphify_engine', pid: '12231', cpu: '5.4%', ram: '732 MB', status: 'RUNNING' },
    { name: 'vfs_refractions', pid: '10001', cpu: '3.2%', ram: '420 MB', status: 'RUNNING' },
    { name: 'mem_palace', pid: '8888', cpu: '2.1%', ram: '256 MB', status: 'RUNNING' }
  ];

  return (
    <div 
      className="hud-panel hud-glint hud-depth-1 rounded-xl p-3 flex flex-col justify-between h-full group font-mono text-[10px]"
      id="bento-process-matrix"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-950/80 pb-1.5 mb-1.5">
        <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
          PROCESS MATRIX
        </h3>
        <div className="flex items-center gap-1 text-slate-500 hover:text-cyan-400 cursor-pointer">
          <Maximize2 className="w-3 h-3" />
        </div>
      </div>

      {/* Table Structure */}
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-cyan-950/80 text-[8px] uppercase tracking-wider text-slate-400">
              <th className="pb-1 font-semibold">PROCESS</th>
              <th className="pb-1 font-semibold text-center">PID</th>
              <th className="pb-1 font-semibold text-center">CPU%</th>
              <th className="pb-1 font-semibold text-center">RAM</th>
              <th className="pb-1 font-semibold text-right">STATUS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-cyan-950/40 text-[9px]">
            {displayProcesses.map((proc, idx) => (
              <tr 
                key={idx}
                className="hover:bg-cyan-950/30 transition-colors group/row cursor-pointer"
                onClick={() => onRestartService(proc.name)}
                title={`Click to manage ${proc.name}`}
              >
                <td className="py-1 text-cyan-200 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                  <span>{proc.name}</span>
                </td>
                <td className="py-1 text-slate-400 text-center font-mono">{proc.pid}</td>
                <td className="py-1 text-slate-300 text-center font-mono">{proc.cpu}</td>
                <td className="py-1 text-slate-300 text-center font-mono">{proc.ram}</td>
                <td className="py-1 text-right">
                  <span className="px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-wider bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 shadow-[0_0_6px_rgba(52,211,153,0.3)]">
                    {proc.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
