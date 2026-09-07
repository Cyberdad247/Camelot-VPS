import React, { useState } from 'react';
import { SentinelPolicyEngine, ILease, ITaskExecutionRequest } from './SentinelPolicyEngine';
import { 
  Flame, 
  ShieldCheck, 
  Lock, 
  KeyRound, 
  Sparkles, 
  CheckCircle2, 
  AlertOctagon, 
  Cpu, 
  ScrollText, 
  CornerDownRight, 
  Play,
  RotateCcw,
  Minus,
  Plus,
  Crown,
  Key,
  Zap,
  Layers
} from 'lucide-react';
import { SAMPLE_AGENTS } from '../data/bootstrapData';
import { AgentMission, LedgerReceipt, SystemVitals } from '../types';
import confetti from 'canvas-confetti';

interface MissionArenaProps {
  onDispatchMission?: (mission: AgentMission) => void;
  missions?: AgentMission[];
  receipts?: LedgerReceipt[];
  vitals?: SystemVitals;
}

export const MissionArena: React.FC<MissionArenaProps> = ({
  onDispatchMission,
  missions = [],
  receipts = [],
  vitals
}) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>('sir_codex');
  const [customPrompt, setCustomPrompt] = useState<string>(SAMPLE_AGENTS[0]?.defaultPrompt || '');
  const [requireValidLease, setRequireValidLease] = useState<boolean>(true);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);

  // Minimization states
  const [minimizedAgents, setMinimizedAgents] = useState(false);
  const [showSentinel, setShowSentinel] = useState(false);
  const [activeLeases, setActiveLeases] = useState<ILease[]>([
    {
      leaseId: 'LEASE_SENTINEL_0x1a2b3c',
      agentId: 'sir_codex',
      expiresAt: Date.now() + 1000 * 60 * 60, // Valid for 1 hour
      allowedEffects: ['read_file', 'write_file', 'execute_wasm']
    }
  ]);
  const [currentRequest, setCurrentRequest] = useState<ITaskExecutionRequest | null>(null);
  const [minimizedReceipts, setMinimizedReceipts] = useState(false);

  // Hidden Aspect: Protocol Ragnarok // Secret 9th Knight: Arthur Pendragon
  const [ragnarokActive, setRagnarokActive] = useState(false);
  const [legendarySealActive, setLegendarySealActive] = useState(false);

  const selectedAgent = SAMPLE_AGENTS.find((a) => a.id === selectedAgentId) || SAMPLE_AGENTS[0];

  const handleAgentSelect = (agentId: string) => {
    setSelectedAgentId(agentId);
    const agent = SAMPLE_AGENTS.find((a) => a.id === agentId);
    if (agent) {
      setCustomPrompt(agent.defaultPrompt);
    }
  };

  const handleRun = () => {
    if (!customPrompt.trim()) return;
    
    // Create execution request
    const request: ITaskExecutionRequest = {
      taskId: `TASK-${Math.floor(Math.random() * 90000)}`,
      agentId: selectedAgent.id,
      requestedEffect: 'execute_wasm', // hardcoded effect for demo
      missionPrompt: customPrompt
    };
    
    setCurrentRequest(request);
    setShowSentinel(true);
  };

  const handleAuthorize = () => {
    setShowSentinel(false);
    setIsDispatching(true);

    const newMission: AgentMission = {
      id: `MSN-${Math.floor(1000 + Math.random() * 9000)}`,
      agentId: selectedAgent.id,
      agentName: selectedAgent.name,
      agentTitle: selectedAgent.title,
      prompt: customPrompt,
      leaseId: requireValidLease ? `LEASE_SENTINEL_0x${Math.floor(Math.random() * 0xffffff).toString(16)}` : 'INVALID_LEASE_0x0000',
      leaseGranted: true,
      status: 'receipted',
      wal2ReceiptHash: `0x${Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('')}`,
      executionMs: Number((4 + Math.random() * 12).toFixed(1)),
      resultOutput: `Execution complete under WASI sandbox. Memory bounded strictly to 64MB. Invariants proved SAT.`,
      z3ProofStatus: 'PROVED'
    };

    setTimeout(() => {
      onDispatchMission?.(newMission);
      setIsDispatching(false);
      setCustomPrompt('');
      confetti({ particleCount: 25, spread: 60, origin: { y: 0.7 } });
    }, 1200);
  };

  const handleReject = (reason: string) => {
    setShowSentinel(false);
    
    const failedMission: AgentMission = {
      id: `MSN-${Math.floor(1000 + Math.random() * 9000)}`,
      agentId: selectedAgent.id,
      agentName: selectedAgent.name,
      agentTitle: selectedAgent.title,
      prompt: customPrompt,
      leaseId: 'INVALID_LEASE_0x0000',
      leaseGranted: false,
      status: 'rejected',
      wal2ReceiptHash: `0x${Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('')}`,
      executionMs: 0,
      resultOutput: `EXECUTION BLOCKED: ${reason}`,
      z3ProofStatus: 'UNSAT'
    };
    
    onDispatchMission?.(failedMission);
    setCustomPrompt('');
  };

  const toggleRagnarok = () => {
    setRagnarokActive(!ragnarokActive);
    if (!ragnarokActive) {
      confetti({ particleCount: 50, spread: 90, origin: { y: 0.5 } });
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-2 sm:p-4 space-y-4 font-mono">
      {showSentinel && currentRequest && (
        <SentinelPolicyEngine
          request={currentRequest}
          activeLeases={requireValidLease ? activeLeases : []}
          onAuthorize={handleAuthorize}
          onReject={handleReject}
        />
      )}
      
      {/* Top Banner */}
      <div className="bg-[#0e131f] border border-amber-950/80 rounded-xl p-4 sm:p-5 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Flame className="w-5 h-5 text-amber-400" />
              <h2 className="font-heraldic text-lg font-bold text-amber-200 tracking-wider">
                AGENT MISSION DISPATCH ARENA — //RUN_MISSION
              </h2>
            </div>
            <p className="text-xs text-slate-400 font-terminal mt-1">
              Execute sovereign knight tasks with cryptographic Sentinel token leases, WASI runtime sandboxing, and monotonic SQLite WAL2 ledger receipting.
            </p>
          </div>

          {/* HIDDEN ASPECT: Protocol Ragnarok Trigger */}
          <button
            onClick={toggleRagnarok}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs font-bold transition-all ${
              ragnarokActive
                ? 'bg-amber-950 border-amber-400 text-amber-200 shadow-[0_0_15px_rgba(245,158,11,0.5)] animate-pulse'
                : 'bg-slate-900 border-amber-900/60 text-amber-400/80 hover:text-amber-300'
            }`}
          >
            <Crown className="w-3.5 h-3.5 text-amber-400" />
            <span>{ragnarokActive ? 'PROTOCOL RAGNAROK ACTIVE' : '[CLASSIFIED: PROTOCOL RAGNAROK]'}</span>
          </button>
        </div>
      </div>

      {/* HIDDEN ASPECT: PROTOCOL RAGNAROK (ARTHUR PENDRAGON // CORE SOVEREIGN) */}
      {ragnarokActive && (
        <div className="bg-amber-950/30 border-2 border-amber-500/60 rounded-xl p-4 shadow-2xl space-y-3 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-amber-500/40 pb-2">
            <div className="flex items-center gap-2">
              <Crown className="w-5 h-5 text-amber-400 animate-pulse" />
              <div>
                <h3 className="text-sm font-bold text-amber-200 tracking-wider">
                  CLASSIFIED 9TH KNIGHT: ARTHUR PENDRAGON // THE CORE SOVEREIGN
                </h3>
                <span className="text-[10px] text-amber-300/80">
                  SUPREME AUTHORITY WITH ZERO-BOUND LEASE INVARIANTS & HARDWARE REGISTERS
                </span>
              </div>
            </div>
            <button
              onClick={() => setRagnarokActive(false)}
              className="text-xs text-amber-300 hover:text-white underline"
            >
              Dismiss Ragnarok
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3 bg-black/80 border border-amber-500/40 rounded-lg space-y-1.5">
              <span className="text-amber-400 font-bold">SUPREME SOVEREIGN LEASE</span>
              <p className="text-[11px] text-slate-300">
                Grants unrestricted DMA bus arbitration across all 28 baremetal services with zero queue wait.
              </p>
              <button
                onClick={() => {
                  setCustomPrompt('ARTHUR_PENDRAGON: Flush all stale ASTs, sync WAL2 checkpoint, and prove constitutional convergence.');
                  setSelectedAgentId('sir_codex');
                  setLegendarySealActive(true);
                  confetti({ particleCount: 30, spread: 70, origin: { y: 0.6 } });
                }}
                className="w-full mt-2 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black font-bold text-[10px]"
              >
                Load Supreme Directive
              </button>
            </div>

            <div className="md:col-span-2 p-3 bg-black/80 border border-amber-500/40 rounded-lg space-y-1">
              <span className="text-amber-400 font-bold">RAGNAROK PROOF STATUS</span>
              <div className="p-2 rounded bg-slate-950 border border-slate-800 text-[10px] text-emerald-300 font-mono">
                {legendarySealActive ? (
                  <>
                    <div>✓ EXCALIBUR CONVERGENCE: ENGAGED</div>
                    <div>✓ 44/44 CONSTITUTIONAL THEOREMS VERIFIED SATISFIED</div>
                    <div>✓ WAL2 CHECKPOINT HEIGHT #9999 CONVERGED</div>
                  </>
                ) : (
                  <div>Awaiting Supreme Directive Execution...</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Arena 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Left Column: Agent Selector & Prompt Formulation */}
        <div className="lg:col-span-6 space-y-4">
          
          {/* Agent Selection Card (Collapsible) */}
          <div className="bg-[#0e131f] border border-cyan-950/80 rounded-xl p-4 shadow-lg space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                <span>SELECT SOVEREIGN AGENT</span>
              </h3>
              <button
                onClick={() => setMinimizedAgents(!minimizedAgents)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedAgents ? "Expand agents" : "Minimize agents"}
              >
                {minimizedAgents ? <Plus className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
              </button>
            </div>

            {!minimizedAgents ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {SAMPLE_AGENTS.map((agent) => {
                  const isSelected = selectedAgentId === agent.id;
                  return (
                    <button
                      key={agent.id}
                      onClick={() => handleAgentSelect(agent.id)}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        isSelected
                          ? 'bg-amber-950/40 border-amber-400 text-amber-200 shadow-[0_0_10px_rgba(245,158,11,0.2)]'
                          : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <div className="font-bold text-xs">{agent.name}</div>
                      <div className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">{agent.title}</div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="text-[11px] text-amber-300 font-bold p-2 bg-slate-900/60 rounded">
                Active: {selectedAgent.name} ({selectedAgent.title})
              </div>
            )}
          </div>

          {/* Prompt Dispatch Box */}
          <div className="bg-[#0e131f] border border-cyan-950/80 rounded-xl p-4 shadow-lg space-y-3">
            <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
              <KeyRound className="w-4 h-4 text-amber-400" />
              <span>DIRECTIVE PROMPT & SENTINEL LEASE</span>
            </h3>

            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              rows={3}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs font-mono text-cyan-200 focus:outline-none focus:border-cyan-500 placeholder:text-slate-600"
              placeholder="Formulate mission directive for the agent..."
            />

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={requireValidLease}
                  onChange={(e) => setRequireValidLease(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-amber-500 focus:ring-0"
                />
                <span>Enforce Valid Sentinel Lease (Zero-Trust)</span>
              </label>

              <button
                onClick={handleRun}
                disabled={isDispatching}
                className="flex items-center gap-2 px-4 py-2 rounded bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs transition-all shadow-[0_0_15px_rgba(245,158,11,0.35)] active:scale-95 disabled:opacity-50"
              >
                {isDispatching ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin"></span>
                    <span>DISPATCHING...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-black" />
                    <span>DISPATCH MISSION</span>
                  </>
                )}
              </button>
            </div>
          </div>

        </div>

        {/* Right Column: Ledger Receipts & Recent Dispatches */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-[#0e131f] border border-cyan-950/80 rounded-xl p-4 shadow-lg space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
                <ScrollText className="w-4 h-4 text-emerald-400" />
                <span>MONOTONIC WAL2 LEDGER RECEIPTS ({missions.length})</span>
              </h3>
              <button
                onClick={() => setMinimizedReceipts(!minimizedReceipts)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
                title={minimizedReceipts ? "Expand receipts" : "Minimize receipts"}
              >
                {minimizedReceipts ? <Plus className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
              </button>
            </div>

            {!minimizedReceipts ? (
              <div className="space-y-2.5 max-h-[500px] overflow-y-auto custom-scrollbar">
                {missions.map((m) => (
                  <div
                    key={m.id}
                    className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-amber-300">{m.agentName}</span>
                      <span className="text-[10px] text-emerald-400 px-1.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/30">
                        {m.z3ProofStatus} ({m.executionMs}ms)
                      </span>
                    </div>
                    <p className="text-slate-300 text-[11px]">{m.prompt}</p>
                    <div className="p-2 rounded bg-slate-900 border border-slate-800/80 text-[10px] text-cyan-200">
                      {m.resultOutput}
                    </div>
                    <div className="text-[9px] font-mono text-slate-500 truncate">
                      WAL2 Receipt: {m.wal2ReceiptHash}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[11px] text-slate-400 p-2 bg-slate-900/60 rounded flex justify-between">
                <span>Receipts Log Minimized</span>
                <span className="text-emerald-400 font-bold">{missions.length} PROVED ENTRIES</span>
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
};
