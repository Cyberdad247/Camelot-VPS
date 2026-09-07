import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal as TerminalIcon, 
  Play, 
  RotateCcw, 
  CheckCircle2, 
  AlertTriangle, 
  ChevronRight, 
  Sparkles, 
  Copy, 
  ShieldAlert, 
  FastForward,
  CornerDownLeft,
  Minus,
  Plus,
  Maximize2,
  Minimize2,
  Key,
  Flame,
  Binary,
  Eye,
  Radio
} from 'lucide-react';
import { BootstrapPhase, TerminalLog } from '../types';
import confetti from 'canvas-confetti';

const AVAILABLE_COMMANDS = [
  'clear',
  'optimize',
  'sync-engines',
  'help',
  'matrix',
  'odin_vision',
  '//GO_LIVE',
  '//DISPATCH',
  '//RUN_MISSION sir_codex',
  '//RUN_MISSION sir_boris',
  '//RUN_MISSION sir_helio',
  'camelot-vitals',
  'cgroup-inspect'
];

interface BootstrapTerminalProps {
  phases: BootstrapPhase[];
  onExecutePhase: (phaseId: number) => void;
  onExecuteAll: () => void;
  onReset: () => void;
  isExecutingAll: boolean;
  activePhaseId: number;
  terminalLogs: TerminalLog[];
  onRunCustomCommand: (cmd: string) => void;
  vpsIp: string;
}

export const BootstrapTerminal: React.FC<BootstrapTerminalProps> = ({
  phases,
  onExecutePhase,
  onExecuteAll,
  onReset,
  isExecutingAll,
  activePhaseId,
  terminalLogs,
  onRunCustomCommand,
  vpsIp
}) => {
  const [commandInput, setCommandInput] = useState('');
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Minimization states
  const [minimizedPhases, setMinimizedPhases] = useState(false);
  const [minimizedTerminal, setMinimizedTerminal] = useState(false);
  const [fullscreenTerminal, setFullscreenTerminal] = useState(false);

  // Hidden Aspect: Matrix Rain Canvas & Classified Easter Eggs
  const [matrixActive, setMatrixActive] = useState(false);
  const [odinVisionActive, setOdinVisionActive] = useState(false);
  const matrixCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // Matrix Rain Animation Loop
  useEffect(() => {
    if (!matrixActive) return;
    const canvas = matrixCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.parentElement?.clientWidth || 800;
    canvas.height = canvas.parentElement?.clientHeight || 500;

    const chars = '0123456789ABCDEFYGGDRASILCAMELOTEXCALIBURΩΨ';
    const fontSize = 14;
    const columns = Math.floor(canvas.width / fontSize);
    const drops = Array.from({ length: columns }, () => 1);

    let animationId: number;

    const draw = () => {
      ctx.fillStyle = 'rgba(4, 7, 17, 0.08)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = '#10b981';
      ctx.font = `${fontSize}px monospace`;

      for (let i = 0; i < drops.length; i++) {
        const text = chars.charAt(Math.floor(Math.random() * chars.length));
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);

        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i]++;
      }

      animationId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animationId);
  }, [matrixActive]);

  // Auto-scroll terminal to bottom
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [terminalLogs]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandInput.trim()) return;

    const cmd = commandInput.trim();
    setShowSuggestions(false);
    setCommandHistory((prev) => [...prev, cmd]);
    setHistoryIndex(-1);

    const lower = cmd.toLowerCase();
    if (lower === 'matrix') {
      setMatrixActive(!matrixActive);
      onRunCustomCommand('[EASTER_EGG]: Matrix rain canvas stream toggled.');
    } else if (lower === 'odin_vision' || lower === 'odin') {
      setOdinVisionActive(!odinVisionActive);
      confetti({ particleCount: 30, spread: 70, origin: { y: 0.6 } });
      onRunCustomCommand('[ODIN_VISION]: Runic ASCII Sovereign World Tree manifested.');
    } else {
      onRunCustomCommand(cmd);
    }

    setCommandInput('');
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setCommandInput(value);

    if (value.trim()) {
      const filtered = AVAILABLE_COMMANDS.filter((cmd) =>
        cmd.toLowerCase().startsWith(value.trim().toLowerCase())
      );
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
      setActiveSuggestionIndex(-1);
    } else {
      setShowSuggestions(false);
    }
  };

  const selectSuggestion = (suggestion: string) => {
    setCommandInput(suggestion);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveSuggestionIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
        return;
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveSuggestionIndex((prev) => (prev === suggestions.length - 1 ? 0 : prev + 1));
        return;
      } else if (e.key === 'Tab') {
        e.preventDefault();
        const index = activeSuggestionIndex >= 0 ? activeSuggestionIndex : 0;
        selectSuggestion(suggestions[index]);
        return;
      } else if (e.key === 'Enter') {
        if (activeSuggestionIndex >= 0) {
          e.preventDefault();
          const cmd = suggestions[activeSuggestionIndex];
          
          setCommandHistory((prev) => [...prev, cmd]);
          setHistoryIndex(-1);
          const lower = cmd.toLowerCase();
          if (lower === 'matrix') {
            setMatrixActive(!matrixActive);
            onRunCustomCommand('[EASTER_EGG]: Matrix rain canvas stream toggled.');
          } else if (lower === 'odin_vision' || lower === 'odin') {
            setOdinVisionActive(!odinVisionActive);
            confetti({ particleCount: 30, spread: 70, origin: { y: 0.6 } });
            onRunCustomCommand('[ODIN_VISION]: Runic ASCII Sovereign World Tree manifested.');
          } else {
            onRunCustomCommand(cmd);
          }
          setCommandInput('');
          setShowSuggestions(false);
          return;
        }
      } else if (e.key === 'Escape') {
        setShowSuggestions(false);
        return;
      }
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (commandHistory.length > 0) {
        const newIndex = historyIndex === -1 ? commandHistory.length - 1 : Math.max(0, historyIndex - 1);
        setHistoryIndex(newIndex);
        setCommandInput(commandHistory[newIndex]);
        setShowSuggestions(false);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex !== -1) {
        const newIndex = historyIndex + 1;
        if (newIndex >= commandHistory.length) {
          setHistoryIndex(-1);
          setCommandInput('');
        } else {
          setHistoryIndex(newIndex);
          setCommandInput(commandHistory[newIndex]);
        }
        setShowSuggestions(false);
      }
    }
  };

  const completedPhasesCount = phases.filter((p) => p.status === 'completed').length;
  const progressPercent = Math.round((completedPhasesCount / phases.length) * 100);

  const getLogColor = (level: TerminalLog['level']) => {
    switch (level) {
      case 'error':
        return 'text-rose-400 font-semibold';
      case 'warn':
        return 'text-amber-300';
      case 'success':
        return 'text-emerald-400 font-medium';
      case 'sovereign':
        return 'text-amber-300 font-bold bg-amber-950/40 px-1 py-0.5 rounded border border-amber-500/20';
      case 'command':
        return 'text-sky-300 font-semibold';
      case 'z3':
        return 'text-purple-300 font-mono';
      default:
        return 'text-slate-300';
    }
  };

  return (
    <div className={`p-2 sm:p-4 max-w-7xl mx-auto transition-all ${fullscreenTerminal ? 'fixed inset-0 z-50 bg-[#030712] max-w-none p-4' : 'grid grid-cols-1 lg:grid-cols-12 gap-4'}`}>
      
      {/* Left Column: Phase Progression & Directives */}
      {!fullscreenTerminal && (
        <div className={`${minimizedPhases ? 'lg:col-span-2' : 'lg:col-span-4'} space-y-4 transition-all`}>
          {/* Progress Card */}
          <div className="bg-[#0e131f] border border-amber-950/80 rounded-xl p-4 shadow-lg">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-slate-200 font-heraldic tracking-wide">
                  {!minimizedPhases ? 'BOOTSTRAP CONVERGENCE' : 'CONVERGE'}
                </h2>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono font-bold text-amber-400 px-2 py-0.5 rounded bg-amber-950/80 border border-amber-500/30">
                  {progressPercent}%
                </span>
                <button
                  onClick={() => setMinimizedPhases(!minimizedPhases)}
                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-300"
                  title={minimizedPhases ? "Expand Phase list" : "Minimize Phase list"}
                >
                  {minimizedPhases ? <Plus className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden mb-4 border border-slate-800">
              <div 
                className="h-full bg-gradient-to-r from-amber-600 via-amber-400 to-emerald-400 rounded-full transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-2">
              <button
                id="btn-bootstrap-runall"
                onClick={onExecuteAll}
                disabled={isExecutingAll || progressPercent === 100}
                className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded text-xs font-semibold font-terminal transition-all ${
                  progressPercent === 100 
                    ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-500/40 cursor-default'
                    : 'bg-amber-500 hover:bg-amber-400 text-black shadow-[0_0_15px_rgba(245,158,11,0.25)] active:scale-95'
                }`}
              >
                {isExecutingAll ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin"></span>
                    <span>RUNNING</span>
                  </>
                ) : progressPercent === 100 ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>SEALED</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-black" />
                    <span>EXEC ALL</span>
                  </>
                )}
              </button>

              <button
                id="btn-bootstrap-reset"
                onClick={onReset}
                disabled={isExecutingAll}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs font-medium font-terminal transition-all active:scale-95"
              >
                <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
                <span>RESET</span>
              </button>
            </div>
          </div>

          {/* Phase List (Collapsible) */}
          {!minimizedPhases && (
            <div className="bg-[#0e131f] border border-slate-800/80 rounded-xl p-3 space-y-2 max-h-[580px] overflow-y-auto custom-scrollbar">
              <div className="text-xs font-mono uppercase tracking-wider text-slate-400 px-1 py-1 flex items-center justify-between">
                <span>Execution Phases (1-8)</span>
                <span className="text-[10px] text-amber-400/80">Bare-Metal</span>
              </div>

              {phases.map((phase) => {
                const isCurrent = phase.id === activePhaseId;
                const isCompleted = phase.status === 'completed';
                const isRunning = phase.status === 'running';

                return (
                  <div
                    key={phase.id}
                    id={`phase-card-${phase.id}`}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      isCurrent
                        ? 'bg-amber-950/30 border-amber-500/50 shadow-md'
                        : isCompleted
                        ? 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                        : 'bg-slate-950/40 border-slate-900 opacity-70'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-mono font-bold ${
                          isCompleted 
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : isRunning
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse'
                            : 'bg-slate-800 text-slate-400'
                        }`}>
                          {isCompleted ? '✓' : phase.id}
                        </span>
                        <h3 className="text-xs font-semibold text-slate-200">
                          {phase.title.split(':')[0]}
                        </h3>
                      </div>

                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                        isCompleted 
                          ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-500/30'
                          : isRunning
                          ? 'bg-amber-950/80 text-amber-400 border border-amber-500/30 animate-pulse'
                          : 'bg-slate-900 text-slate-500'
                      }`}>
                        {phase.status.toUpperCase()}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">
                      {phase.subtitle}
                    </p>

                    <div className="mt-2 flex items-center justify-between pt-2 border-t border-slate-800/40">
                      <span className="text-[10px] font-mono text-slate-500">
                        Est: {phase.estimatedSeconds}s
                      </span>
                      <button
                        id={`btn-phase-trigger-${phase.id}`}
                        onClick={() => onExecutePhase(phase.id)}
                        disabled={isExecutingAll || isRunning}
                        className="text-[11px] font-mono font-medium px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-amber-300 border border-amber-500/20 transition-all flex items-center gap-1"
                      >
                        <span>Run Step</span>
                        <ChevronRight className="w-3 h-3 text-amber-400" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Right Column: Interactive Terminal Box */}
      <div className={`${fullscreenTerminal ? 'w-full h-full' : minimizedPhases ? 'lg:col-span-10' : 'lg:col-span-8'} flex flex-col h-[700px] bg-[#070a10] border border-amber-950/80 rounded-xl overflow-hidden shadow-2xl relative transition-all`}>
        
        {/* Terminal Title Bar */}
        <div className="bg-[#0c101a] px-4 py-2.5 border-b border-slate-800 flex items-center justify-between text-xs font-terminal">
          <div className="flex items-center gap-2">
            <div className="flex gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80 inline-block"></span>
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 inline-block"></span>
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block"></span>
            </div>
            <span className="text-slate-400 ml-2 font-mono">root@{vpsIp}:~ (cgroups-v2: native)</span>
          </div>

          <div className="flex items-center gap-3 text-[11px] text-slate-400">
            <span className="text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              STDOUT LIVE
            </span>

            {/* Matrix Rain Toggle (Easter Egg) */}
            <button
              onClick={() => setMatrixActive(!matrixActive)}
              className={`px-2 py-0.5 rounded border text-[10px] font-mono transition-all ${
                matrixActive 
                  ? 'bg-emerald-950 border-emerald-400 text-emerald-300 shadow-[0_0_8px_rgba(16,185,129,0.5)]' 
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-emerald-400'
              }`}
              title="Classified Easter Egg: Toggle Matrix Green Rain Canvas"
            >
              [MATRIX]
            </button>

            {/* Odin World Tree Vision */}
            <button
              onClick={() => {
                setOdinVisionActive(!odinVisionActive);
                confetti({ particleCount: 25, spread: 60, origin: { y: 0.6 } });
              }}
              className={`px-2 py-0.5 rounded border text-[10px] font-mono transition-all ${
                odinVisionActive 
                  ? 'bg-amber-950 border-amber-400 text-amber-300 shadow-[0_0_8px_rgba(245,158,11,0.5)]' 
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-amber-300'
              }`}
              title="Classified Easter Egg: Manifest Odin World Tree Vision"
            >
              [ODIN VISION]
            </button>

            {/* Fullscreen Toggle */}
            <button
              onClick={() => setFullscreenTerminal(!fullscreenTerminal)}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-cyan-300"
              title={fullscreenTerminal ? "Exit Fullscreen" : "Fullscreen Terminal"}
            >
              {fullscreenTerminal ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>

            <button
              onClick={() => onRunCustomCommand('clear')}
              className="hover:text-slate-200 underline decoration-slate-600 transition-colors"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Matrix Canvas Layer (If active) */}
        {matrixActive && (
          <canvas 
            ref={matrixCanvasRef} 
            className="absolute inset-x-0 top-10 bottom-12 pointer-events-none opacity-40 z-10"
          />
        )}

        {/* Terminal Screen / Logs */}
        <div 
          id="terminal-stdout-container"
          className="flex-1 p-4 font-terminal text-xs leading-relaxed overflow-y-auto space-y-1.5 selection:bg-amber-500/30 selection:text-amber-200 bg-[#05080e] relative z-20 custom-scrollbar"
        >
          {/* Odin Vision ASCII Art Overlay */}
          {odinVisionActive && (
            <div className="p-3 bg-black/80 border border-amber-500/40 rounded-lg text-amber-300 font-mono text-[10px] space-y-1 animate-fadeIn">
              <pre className="text-amber-400">
{`                  .---.
                 /     \\
                | () () |   [ODIN'S ALL-SEEING WORLD TREE]
                 \\  _  /    ==============================
                  '---'     Yggdrasil roots drink from Urdarbrunnr.
                 /| | |\\    Direct Memory Access (DMA): 0.12ms
                / | | | \\   Z3 Invariant Proofs: ALL SATISFIED.`}
              </pre>
            </div>
          )}

          <div className="text-slate-500 pb-2 border-b border-slate-900 select-none">
            <pre className="text-[10px] text-amber-500/70 font-mono">
{`   ___   _   __  __ ___ _    ___ _____       ___  ___ 
  / __| /_\\ |  \\/  | __| |  / _ \\_   _|___  / _ \\/ __|
 | (__ / _ \\| |\\/| | _|| |_| (_) || | |___| (_) \\__ \\
  \\___/_/ \\_\\_|  |_|___|____\\___/ |_|      \\___/|___/
  ====================================================
  CAMELOT-OS vMAX OMEGA TITAN // CYBERTRONIA BAREMETAL`}
            </pre>
            <p className="text-[11px] text-slate-400 mt-1">
              Type <span className="text-amber-300 font-semibold">//GO_LIVE</span>, <span className="text-amber-300 font-semibold">matrix</span>, <span className="text-amber-300 font-semibold">odin_vision</span>, <span className="text-amber-300 font-semibold">//RUN_MISSION sir_codex</span>, or <span className="text-amber-300 font-semibold">help</span>.
            </p>
          </div>

          {terminalLogs.map((log) => (
            <div key={log.id} className="flex items-start gap-2 group hover:bg-slate-900/30 py-0.5 rounded px-1">
              <span className="text-slate-600 text-[10px] select-none font-mono shrink-0 pt-0.5">
                {log.timestamp}
              </span>
              {log.phase && (
                <span className="text-[9px] font-mono uppercase px-1 rounded bg-slate-800/80 text-amber-400/90 border border-slate-700 shrink-0">
                  P{log.phase}
                </span>
              )}
              <span className={`break-words ${getLogColor(log.level)}`}>
                {log.message}
              </span>
            </div>
          ))}

          <div ref={terminalEndRef} />
        </div>

        {/* Terminal Interactive Input Box */}
        <form onSubmit={handleSubmit} className="border-t border-slate-800 bg-[#0b0f19] p-2.5 flex items-center gap-2 relative z-30">
          
          {/* Autocomplete Dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute bottom-full left-0 w-64 mb-1 ml-2 bg-[#0c101a] border border-slate-700/80 rounded shadow-[0_0_15px_rgba(0,0,0,0.5)] overflow-hidden z-50">
              {suggestions.map((suggestion, idx) => (
                <div
                  key={suggestion}
                  onClick={() => selectSuggestion(suggestion)}
                  className={`px-3 py-1.5 text-xs font-mono cursor-pointer transition-colors ${
                    idx === activeSuggestionIndex 
                      ? 'bg-amber-500/20 text-amber-300 border-l-2 border-amber-500' 
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200 border-l-2 border-transparent'
                  }`}
                >
                  {suggestion}
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-1.5 text-amber-400 font-terminal text-xs shrink-0 pl-1">
            <span className="text-slate-500">root@cybertronia:~#</span>
          </div>
          <input
            ref={inputRef}
            id="terminal-input-command"
            type="text"
            value={commandInput}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Enter directive (e.g. clear, optimize, sync-engines, matrix)..."
            className="flex-1 bg-transparent text-amber-200 font-terminal text-xs focus:outline-none placeholder:text-slate-600 caret-amber-400"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="submit"
            className="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-mono flex items-center gap-1 transition-all active:scale-95"
          >
            <span>Execute</span>
            <CornerDownLeft className="w-3 h-3 text-amber-400" />
          </button>
        </form>

        {/* Quick Command Toolbar with Hidden Easter Egg Buttons */}
        <div className="px-3 py-1.5 bg-[#080b12] border-t border-slate-900 flex flex-wrap items-center justify-between gap-2 text-[10px] font-terminal text-slate-400 relative z-30">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-600">Quick Commands:</span>
            {[
              '//GO_LIVE',
              '//DISPATCH',
              '//RUN_MISSION sir_codex',
              'camelot-vitals',
              'cgroup-inspect',
              'matrix',
              'odin_vision'
            ].map((cmd) => (
              <button
                key={cmd}
                onClick={() => {
                  if (cmd === 'matrix') setMatrixActive(!matrixActive);
                  else if (cmd === 'odin_vision') setOdinVisionActive(!odinVisionActive);
                  else onRunCustomCommand(cmd);
                }}
                className="px-1.5 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-amber-500/40 transition-colors"
              >
                {cmd}
              </button>
            ))}
          </div>

          <div className="text-[10px] text-amber-400 font-mono flex items-center gap-1">
            <Key className="w-3 h-3 text-amber-400" />
            <span>ROOT_PRIVILEGES_GRANTED</span>
          </div>
        </div>
      </div>
    </div>
  );
};
