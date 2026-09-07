import React, { useState } from 'react';
import { 
  RAW_BOOTSTRAP_PROMPT,
  BOOTSTRAP_PHASES,
  CAMELOT_SERVICES,
  SOVEREIGN_LAWS,
  INITIAL_VITALS,
  SAMPLE_AGENTS,
  INITIAL_LEDGER_RECEIPTS
} from './data/bootstrapData';
import { 
  BootstrapPhase, 
  CamelotService, 
  SovereignLaw, 
  SystemVitals, 
  AgentMission, 
  LedgerReceipt, 
  TerminalLog 
} from './types';
import { Header } from './components/Header';
import { MasterWorldTreeDeck } from './components/MasterWorldTreeDeck';
import { BentoGridOverview } from './components/BentoGridOverview';
import { BootstrapTerminal } from './components/BootstrapTerminal';
import { VKGHud } from './components/VKGHud';
import { MissionArena } from './components/MissionArena';
import { SovereignLaws } from './components/SovereignLaws';
import { ScarcityProtocol } from './components/ScarcityProtocol';
import { MasterBootstrapScript } from './components/MasterBootstrapScript';
import { OperatorConsoleHtmx } from './components/OperatorConsoleHtmx';
import { VpsHubInitiationConsole } from './components/VpsHubInitiationConsole';
import { DocumentationForge } from './components/DocumentationForge';
import { Layers, Maximize2, Plus, Minus, TreeDeciduous, Terminal, Server, Flame, Lock, Cpu, FileCode, ShieldCheck, HardDrive, BookOpen } from 'lucide-react';

const INITIAL_LOGS: TerminalLog[] = [
  { id: '1', timestamp: '12:00:01', level: 'sovereign', message: 'WORLD_TREE_BOOTSTRAP... OK' },
  { id: '2', timestamp: '12:00:01', level: 'success', message: 'MEMCASTLE_LINK (/vfs/mempalace/*)... OK (0.18ms)' },
  { id: '3', timestamp: '12:00:01', level: 'z3', message: 'OUROBOROS_SSM (1.58-bit ternary W_ij)... OK' },
  { id: '4', timestamp: '12:00:02', level: 'info', message: 'TWIN_BRAINS_SYNC (Open-Notebook <-> NotebookLM)... OK' },
  { id: '5', timestamp: '12:00:02', level: 'success', message: 'VFS_REFRACTIONS (/vfs/refractions/*)... OK (DMA 12μs)' },
  { id: '6', timestamp: '12:00:02', level: 'info', message: 'GRAPHIFY_ENGINE (3D Spatial Network L1-L7)... OK' },
  { id: '7', timestamp: '12:00:03', level: 'sovereign', message: 'SYSTEM ONLINE // AXIS MUNDI CONVERGED' }
];

const INITIAL_MISSIONS: AgentMission[] = [
  {
    id: 'MSN-9021',
    agentId: 'sir_codex',
    agentName: 'Sir Codex',
    agentTitle: 'Knight of Deterministic Logic & WASI Synthesizer',
    prompt: 'Synthesize high-throughput WASI memory filter adhering to 8GB Scarcity Protocol.',
    leaseId: 'LEASE_SENTINEL_0x89f2',
    leaseGranted: true,
    status: 'receipted',
    wal2ReceiptHash: '0x8f74a9b24cd61e3892ab4f012c8e3902',
    executionMs: 14.2,
    resultOutput: 'Compiled 48KB WASM binary. Zero heap allocation detected.',
    z3ProofStatus: 'PROVED'
  },
  {
    id: 'MSN-9022',
    agentId: 'sir_galahad',
    agentName: 'Sir Galahad',
    agentTitle: 'Knight of the Pure Invariant (Z3 Theorem Prover)',
    prompt: 'Verify state transition safety invariants for Neo4j UKG mutation.',
    leaseId: 'LEASE_SENTINEL_0x33b1',
    leaseGranted: true,
    status: 'receipted',
    wal2ReceiptHash: '0x3a4b91f09c2e11894b5e28a99d0124c6',
    executionMs: 8.7,
    resultOutput: 'Z3 SAT: Invariants 1-44 hold with zero counterexamples.',
    z3ProofStatus: 'PROVED'
  }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('deck');
  const [vitals, setVitals] = useState<SystemVitals>(INITIAL_VITALS);
  const [services, setServices] = useState<CamelotService[]>(CAMELOT_SERVICES);
  const [phases, setPhases] = useState<BootstrapPhase[]>(BOOTSTRAP_PHASES);
  const [laws, setLaws] = useState<SovereignLaw[]>(SOVEREIGN_LAWS);
  const [missions, setMissions] = useState<AgentMission[]>(INITIAL_MISSIONS);
  const [receipts, setReceipts] = useState<LedgerReceipt[]>(INITIAL_LEDGER_RECEIPTS);
  const [terminalLogs, setTerminalLogs] = useState<TerminalLog[]>(INITIAL_LOGS);

  const [isExecutingAll, setIsExecutingAll] = useState(false);
  const [activePhaseId, setActivePhaseId] = useState(1);
  const [copiedScript, setCopiedScript] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Global Tab Minimization Dock State
  const [minimizedTabs, setMinimizedTabs] = useState<Record<string, boolean>>({});

  const tabLabels: Record<string, { label: string; icon: any }> = {
    vps_init: { label: 'VPS Hub Initiation (vps3573819)', icon: Server },
    docs: { label: 'Docs Forge (νKG-Crystal)', icon: BookOpen },
    deck: { label: 'World Tree UI (2D ➔ 3D Continuity)', icon: TreeDeciduous },
    operator: { label: 'HTMX Operator Console', icon: ShieldCheck },
    bento: { label: 'Bento Grid Hub', icon: Layers },
    terminal: { label: 'Baremetal Terminal', icon: Terminal },
    vkg: { label: 'VKG-HUD Services', icon: HardDrive },
    mission: { label: 'Mission Arena', icon: Flame },
    laws: { label: 'Sovereign Laws & Ledger', icon: Lock },
    scarcity: { label: '8GB Scarcity Protocol', icon: Cpu },
    script: { label: 'Master Bootstrap Script', icon: FileCode }
  };

  const toggleTabMinimize = (tabId: string = activeTab) => {
    setMinimizedTabs((prev) => ({
      ...prev,
      [tabId]: !prev[tabId]
    }));
    showToast(minimizedTabs[tabId] ? `Restored ${tabLabels[tabId]?.label || tabId}` : `Minimized ${tabLabels[tabId]?.label || tabId}`);
  };

  // Toast Notification auto-dismiss
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((cur) => (cur === msg ? null : cur));
    }, 3500);
  };

  // Copy Master Script
  const handleCopyScript = () => {
    navigator.clipboard.writeText(RAW_BOOTSTRAP_PROMPT);
    setCopiedScript(true);
    showToast('Master Bootstrap Prompt copied to clipboard!');
    setTimeout(() => setCopiedScript(false), 2000);
  };

  // Add Log Entry
  const addLog = (message: string, level: TerminalLog['level'] = 'info', phase?: number) => {
    const now = new Date();
    const timestamp = now.toTimeString().split(' ')[0];
    const newLog: TerminalLog = {
      id: `${Date.now()}-${Math.random()}`,
      timestamp,
      level,
      phase,
      message
    };
    setTerminalLogs((prev) => [...prev, newLog]);
  };

  // Run Custom Terminal Command
  const handleRunCustomCommand = (cmd: string) => {
    addLog(cmd, 'command');

    const lower = cmd.toLowerCase().trim();

    if (lower === 'clear') {
      setTerminalLogs([]);
      return;
    }

    if (lower.startsWith('systemctl status') || lower.startsWith('systemctl restart')) {
      addLog(`[SYSTEMD]: Executing ${cmd}...`, 'info');
      setTimeout(() => {
        addLog(`● ${cmd.split(' ')[2] || 'service'} - Active: active (running) [cgroup: 7.2GB cap]`, 'success');
      }, 300);
      return;
    }

    if (lower.includes('z3') || lower.includes('verify')) {
      addLog(`[Z3 SMT SOLVER]: Checking 44 formal invariants against memory bounds...`, 'z3');
      setTimeout(() => {
        addLog(`[Z3 SMT SOLVER]: SAT: All 44 theorems proved with 0 counterexamples.`, 'success');
      }, 500);
      return;
    }

    if (lower.includes('drop_caches') || lower.includes('optimize')) {
      addLog(`[KERNEL]: Dropping clean pagecaches and reclaiming SLUB slab bins...`, 'info');
      setVitals((prev) => ({ ...prev, usedRamMB: Math.max(4800, prev.usedRamMB - 380) }));
      setTimeout(() => {
        addLog(`[KERNEL]: Reclaimed 380MB RAM. Current utilization: 4.89 GB / 8.00 GB.`, 'success');
        showToast('Memory optimized: 380MB reclaimed');
      }, 400);
      return;
    }

    if (lower.includes('sync-engines') || lower.includes('wal2')) {
      addLog(`[SQLITE WAL2]: Initiating checkpoint on /var/lib/camelot/ledger.db...`, 'sovereign');
      setTimeout(() => {
        addLog(`[SQLITE WAL2]: Checkpoint complete. Block Height: #850. Seal: R5/R6 verified.`, 'success');
        showToast('Ledger & Engines synchronized');
      }, 400);
      return;
    }

    // Default simulation output
    setTimeout(() => {
      addLog(`[KERNEL 6.8.0-40-generic]: ${cmd} executed successfully. exit code: 0`, 'info');
    }, 250);
  };

  // Execute Phase
  const handleExecutePhase = (phaseId: number) => {
    setPhases((prev) =>
      prev.map((p) => (p.id === phaseId ? { ...p, status: 'running' } : p))
    );
    setActivePhaseId(phaseId);
    addLog(`>>> STARTING PHASE ${phaseId}: ${phases.find((p) => p.id === phaseId)?.title}`, 'sovereign', phaseId);

    setTimeout(() => {
      setPhases((prev) =>
        prev.map((p) => (p.id === phaseId ? { ...p, status: 'completed' } : p))
      );
      addLog(`✓ PHASE ${phaseId} COMPLETE: Invariants satisfied.`, 'success', phaseId);
      showToast(`Phase ${phaseId} successfully executed`);
    }, 1500);
  };

  // Execute All Phases Sequentially
  const handleExecuteAll = () => {
    setIsExecutingAll(true);
    addLog(`=======================================================`, 'sovereign');
    addLog(`[SYSTEM ACTIVATION]: INITIATING FULL BAREMETAL BOOTSTRAP`, 'sovereign');
    addLog(`[TARGET]: 8GB InterServer VPS (${vitals.targetHost})`, 'sovereign');
    addLog(`=======================================================`, 'sovereign');

    let current = 1;
    const interval = setInterval(() => {
      if (current <= phases.length) {
        handleExecutePhase(current);
        current++;
      } else {
        clearInterval(interval);
        setIsExecutingAll(false);
        setVitals((prev) => ({ ...prev, gideonConvergence: 'CONVERGED' }));
        addLog(`⚔️ SYSTEM CONVERGED: ALL 8 PHASES ACTIVE & SEALED.`, 'success');
        showToast('All 8 Bootstrap Phases Converged!');
      }
    }, 2000);
  };

  // Reset Bootstrap State
  const handleReset = () => {
    setPhases(BOOTSTRAP_PHASES);
    setActivePhaseId(1);
    setIsExecutingAll(false);
    addLog(`[SYSTEM]: Bootstrap state reset to initial pending state.`, 'warn');
    showToast('Bootstrap sequence reset');
  };

  // Restart Service Action
  const handleRestartService = (serviceId: string) => {
    setServices((prev) =>
      prev.map((s) => (s.id === serviceId ? { ...s, status: 'booting' } : s))
    );
    const svc = services.find((s) => s.id === serviceId);
    addLog(`[SYSTEMD]: Restarting ${svc?.unitName || serviceId}...`, 'info');

    setTimeout(() => {
      setServices((prev) =>
        prev.map((s) => (s.id === serviceId ? { ...s, status: 'active' } : s))
      );
      addLog(`[SYSTEMD]: ${svc?.unitName || serviceId} entered ACTIVE state.`, 'success');
      showToast(`${svc?.name || serviceId} restarted successfully`);
    }, 1200);
  };

  // Sovereign Directives
  const handleGoLive = () => {
    addLog(`//GO_LIVE command executed by Sovereign. Initiating zero-trust traffic cutover...`, 'sovereign');
    showToast('//GO_LIVE executed: Live tailscale routing active');
  };

  const handleDispatch = () => {
    addLog(`//DISPATCH sent to engineering team for VPS 162.35.107.134.`, 'sovereign');
    showToast('//DISPATCH broadcast to engineering nodes');
  };

  const handleRunMission = () => {
    setActiveTab('mission');
    showToast('Navigated to Mission Arena: Dispatch sovereign knight agent');
  };

  const handleDispatchAgentMission = (mission: AgentMission) => {
    setMissions((prev) => [mission, ...prev]);
    addLog(`[SENTINEL]: Granted lease ${mission.leaseId} to ${mission.agentName}.`, 'sovereign');
    addLog(`[Z3 PROVER]: Formally proved safety constraints for mission ${mission.id}.`, 'z3');
    showToast(`Mission dispatched to ${mission.agentName}`);
  };

  const isCurrentTabMinimized = !!minimizedTabs[activeTab];

  return (
    <div className="min-h-screen bg-[#040711] text-slate-200 font-sans flex flex-col selection:bg-cyan-500 selection:text-black scanlines">
      {/* Sovereign Header with System Status & Vitals */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        vitals={vitals}
        onGoLive={handleGoLive}
        onDispatch={handleDispatch}
        onRunMission={handleRunMission}
        copied={copiedScript}
        onCopyScript={handleCopyScript}
        isTabMinimized={isCurrentTabMinimized}
        onToggleTabMinimize={() => toggleTabMinimize(activeTab)}
      />

      {/* Main Content Arena */}
      <main className={`flex-1 w-full ${(activeTab === 'vps_init' || activeTab === 'docs' || activeTab === 'deck' || activeTab === 'operator') ? 'p-0' : 'p-2 sm:p-4'}`}>
        {isCurrentTabMinimized ? (
          <div className="max-w-4xl mx-auto my-12 p-8 bg-[#0a1020]/90 border-2 border-cyan-500/40 rounded-2xl text-center space-y-4 shadow-2xl animate-fadeIn">
            <div className="w-12 h-12 mx-auto rounded-full bg-cyan-500/10 border border-cyan-400 flex items-center justify-center text-cyan-300">
              <Minus className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-white font-heraldic">
              {tabLabels[activeTab]?.label || activeTab} is Currently Minimized
            </h2>
            <p className="text-xs text-slate-400 font-mono">
              The view has been collapsed into the background to prioritize minimal footprint and active 3D DMA streaming.
            </p>
            <button
              onClick={() => toggleTabMinimize(activeTab)}
              className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs font-mono shadow-[0_0_15px_rgba(34,211,238,0.4)] transition-all"
            >
              Restore {tabLabels[activeTab]?.label}
            </button>
          </div>
        ) : (
          <>
            {activeTab === 'vps_init' && (
              <VpsHubInitiationConsole
                onExecuteCommand={handleRunCustomCommand}
                onNavigateTab={setActiveTab}
              />
            )}

            {activeTab === 'docs' && (
              <DocumentationForge
                onNavigateTab={setActiveTab}
                onExecuteCommand={handleRunCustomCommand}
              />
            )}

            {activeTab === 'deck' && (
              <MasterWorldTreeDeck 
                vitals={vitals}
                onNavigateTab={setActiveTab}
                onExecuteCommand={handleRunCustomCommand}
              />
            )}

            {activeTab === 'operator' && (
              <OperatorConsoleHtmx
                onExecuteCommand={handleRunCustomCommand}
                onNavigateTab={setActiveTab}
              />
            )}

            {activeTab === 'bento' && (
              <BentoGridOverview
                vitals={vitals}
                services={services}
                phases={phases}
                laws={laws}
                logs={terminalLogs}
                onNavigateTab={setActiveTab}
                onGoLive={handleGoLive}
                onRunMission={handleRunMission}
                onRestartService={handleRestartService}
                onRunVitalsCheck={() => handleRunCustomCommand('camelot-diag --z3-verify')}
                onExecuteCommand={handleRunCustomCommand}
                onOpenBootstrapScript={() => setActiveTab('script')}
              />
            )}

            {activeTab === 'terminal' && (
              <BootstrapTerminal
                phases={phases}
                onExecutePhase={handleExecutePhase}
                onExecuteAll={handleExecuteAll}
                onReset={handleReset}
                isExecutingAll={isExecutingAll}
                activePhaseId={activePhaseId}
                terminalLogs={terminalLogs}
                onRunCustomCommand={handleRunCustomCommand}
                vpsIp={vitals.targetHost}
              />
            )}

            {activeTab === 'vkg' && (
              <VKGHud
                services={services}
                vitals={vitals}
                onRestartService={handleRestartService}
                onExecuteCommand={handleRunCustomCommand}
                onOpenOperatorConsole={() => setActiveTab('operator')}
                onOpenVpsInitiation={() => setActiveTab('vps_init')}
              />
            )}

            {activeTab === 'mission' && (
              <MissionArena
                missions={missions}
                onDispatchMission={handleDispatchAgentMission}
                receipts={receipts}
                vitals={vitals}
              />
            )}

            {activeTab === 'laws' && (
              <SovereignLaws
                laws={laws}
                receipts={receipts}
                onRunZ3Check={() => handleRunCustomCommand('z3-solver --verify-all-laws')}
              />
            )}

            {activeTab === 'scarcity' && (
              <ScarcityProtocol
                vitals={vitals}
                services={services}
                onOptimize={() => handleRunCustomCommand('optimize-memory')}
              />
            )}

            {activeTab === 'script' && (
              <MasterBootstrapScript
                scriptText={RAW_BOOTSTRAP_PROMPT}
                onCopy={handleCopyScript}
                copied={copiedScript}
              />
            )}
          </>
        )}
      </main>

      {/* Floating Minimized Tabs Dock */}
      {Object.entries(minimizedTabs).some(([_, isMin]) => isMin) && (
        <div className="fixed bottom-12 right-6 z-40 bg-black/90 border border-cyan-500/50 rounded-xl px-3 py-2 flex items-center gap-2 shadow-2xl backdrop-blur-md">
          <span className="text-[10px] font-mono text-cyan-400 font-bold uppercase">Minimized:</span>
          {Object.entries(minimizedTabs).map(([tabKey, isMin]) => {
            if (!isMin) return null;
            const meta = tabLabels[tabKey];
            const Icon = meta?.icon || Layers;
            return (
              <button
                key={tabKey}
                onClick={() => {
                  setActiveTab(tabKey);
                  toggleTabMinimize(tabKey);
                }}
                className="flex items-center gap-1 px-2 py-1 rounded bg-cyan-950/80 border border-cyan-500/40 text-[10px] font-mono text-cyan-300 hover:bg-cyan-900 transition-all"
                title={`Click to restore ${meta?.label}`}
              >
                <Icon className="w-3 h-3 text-cyan-400" />
                <span>{meta?.label.split(' ')[0]}</span>
                <Plus className="w-2.5 h-2.5 text-cyan-400" />
              </button>
            );
          })}
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 px-4 py-2.5 rounded-xl bg-slate-900/95 border-2 border-cyan-400 text-cyan-200 font-mono text-xs shadow-[0_0_25px_rgba(34,211,238,0.4)] flex items-center gap-2.5 animate-bounce">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Bottom Global Status Bar */}
      <footer className="border-t border-cyan-950/80 bg-[#03060e] px-4 py-2 text-[11px] font-mono text-slate-500 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-cyan-400 font-bold">CAMELOT-OS vMAX OMEGA TITAN</span>
          <span>•</span>
          <span>BAREMETAL HUB (162.35.107.134)</span>
          <span>•</span>
          <span className="text-emerald-400">cgroups v2 ACTIVE</span>
        </div>
        <div className="flex items-center gap-4 text-slate-400">
          <span>WASI: STRICT SANDBOX</span>
          <span>•</span>
          <span>Z3 THEOREMS: 44/44 SAT</span>
          <span>•</span>
          <span className="text-amber-400 font-bold">8GB SCARCITY PROTOCOL</span>
        </div>
      </footer>
    </div>
  );
}
