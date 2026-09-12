import React, { FormEvent, KeyboardEvent, useMemo, useRef, useState } from 'react';
import {
  Activity, Brain, Castle, ChevronRight, CircleDot, Crosshair, Database,
  Gauge, Globe2, LockKeyhole, Mic2, Network, Power, Radio, Route, Send, Shield,
  ShieldCheck, Swords, Terminal, Zap,
} from 'lucide-react';
import './sovereign-terminal-command-center.css';

type BattleMode = 'nominal' | 'battle' | 'lockdown';
type SceneId = 'overview' | 'threats' | 'telemetry' | 'defense' | 'brains' | 'ouroboros' | 'vfs' | 'counter' | 'command';
type DefenseId = 'memcastle' | 'context' | 'firewall' | 'inference' | 'sandbox' | 'vfs' | 'physical';
type ThreatFilter = 'ddos' | 'prompt-injection' | 'data-exfiltration' | 'ai-adversary' | 'reconnaissance';
type RealmId = 'multivoice' | 'godseye' | 'worldmonitor';

type TerminalLine = {
  id: number;
  kind: 'command' | 'success' | 'error' | 'info' | 'system';
  text: string;
};

const scenes: { id: SceneId; index: string; label: string; icon: React.ComponentType<{ size?: number }>; purpose: string }[] = [
  { id: 'overview', index: '00', label: 'Battle State', icon: Swords, purpose: 'Overall condition and readiness.' },
  { id: 'threats', index: '01', label: 'Threat Matrix', icon: Crosshair, purpose: 'Attack vectors, targets and filters.' },
  { id: 'telemetry', index: '02', label: 'Telemetry', icon: Gauge, purpose: 'Pressure, latency, shield and readiness.' },
  { id: 'defense', index: '03', label: 'Defense Grid', icon: ShieldCheck, purpose: 'Seven-layer protection controls.' },
  { id: 'brains', index: '04', label: 'Twin Brains', icon: Brain, purpose: 'Combat reasoning and context synchronization.' },
  { id: 'ouroboros', index: '05', label: 'Ouroboros', icon: Zap, purpose: 'Recurrent tactical state and continuity.' },
  { id: 'vfs', index: '06', label: 'VFS Defense', icon: Database, purpose: 'Protected data movement and roots.' },
  { id: 'counter', index: '07', label: 'Countermeasures', icon: Route, purpose: 'Active response and route mitigation.' },
  { id: 'command', index: '08', label: 'Command Deck', icon: Terminal, purpose: 'Operator commands and event history.' },
];

const defenseLabels: Record<DefenseId, string> = {
  memcastle: 'MemCastle Shield', context: 'Context Filter', firewall: 'AI Firewall',
  inference: 'Inference Guard', sandbox: 'Data Sandbox', vfs: 'VFS Perimeter', physical: 'Physical Layer',
};

const threats: { id: ThreatFilter; label: string }[] = [
  { id: 'ddos', label: 'DDoS / Flood' }, { id: 'prompt-injection', label: 'Prompt Injection' },
  { id: 'data-exfiltration', label: 'Data Exfiltration' }, { id: 'ai-adversary', label: 'AI Adversary' },
  { id: 'reconnaissance', label: 'Reconnaissance' },
];

const realms: { id: RealmId; label: string; transport: 'bridge' | 'handoff' | 'mcp'; icon: React.ComponentType<{ size?: number }> }[] = [
  { id: 'multivoice', label: 'Multivoice Router', transport: 'bridge', icon: Mic2 },
  { id: 'godseye', label: "God's Eye View", transport: 'handoff', icon: Globe2 },
  { id: 'worldmonitor', label: 'WorldMonitor', transport: 'mcp', icon: Radio },
];

const initialLines: TerminalLine[] = [
  { id: 1, kind: 'system', text: 'CAMELOT-OS SOVEREIGN TERMINAL // browser operator surface online' },
  { id: 2, kind: 'info', text: 'Type help for commands. Ctrl/Cmd+K focuses the command line.' },
];

const BIFROST_URL = ((import.meta as any).env?.VITE_BIFROST_URL || 'http://127.0.0.1:4188').replace(/\/$/, '');

export const SovereignTerminalCommandCenter: React.FC = () => {
  const [mode, setMode] = useState<BattleMode>('battle');
  const [scene, setScene] = useState<SceneId>('command');
  const [threatFilter, setThreatFilter] = useState<ThreatFilter>('prompt-injection');
  const [threatCount, setThreatCount] = useState(247);
  const [shield, setShield] = useState(99.7);
  const [latency, setLatency] = useState(12);
  const [autoResponse, setAutoResponse] = useState(true);
  const [defenses, setDefenses] = useState<Record<DefenseId, boolean>>({
    memcastle: true, context: true, firewall: true, inference: true, sandbox: true, vfs: true, physical: true,
  });
  const [realm, setRealm] = useState<RealmId>('multivoice');
  const [realmState, setRealmState] = useState<Record<RealmId, 'idle' | 'probing' | 'online' | 'offline'>>({
    multivoice: 'idle', godseye: 'idle', worldmonitor: 'idle',
  });
  const [intent, setIntent] = useState('Open a governed operator handoff through Bifrost.');
  const [lines, setLines] = useState<TerminalLine[]>(initialLines);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<'terminal' | 'operations' | 'bifrost'>('terminal');
  const inputRef = useRef<HTMLInputElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const nextLineId = useRef(3);

  const activeDefenses = Object.values(defenses).filter(Boolean).length;
  const readiness = Math.round((activeDefenses / Object.keys(defenses).length) * 100);
  const selectedScene = scenes.find(item => item.id === scene) ?? scenes[0];
  const selectedRealm = realms.find(item => item.id === realm) ?? realms[0];

  const pushLine = (kind: TerminalLine['kind'], text: string) => {
    setLines(prev => [...prev.slice(-79), { id: nextLineId.current++, kind, text }]);
    requestAnimationFrame(() => terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight, behavior: 'smooth' }));
  };

  const applyMode = (next: BattleMode) => {
    setMode(next);
    if (next === 'nominal') { setThreatCount(18); setLatency(22); }
    if (next === 'battle') { setThreatCount(value => Math.max(247, value)); setLatency(12); }
    if (next === 'lockdown') {
      setThreatCount(value => Math.max(247, value)); setShield(100); setLatency(8); setAutoResponse(true);
      setDefenses({ memcastle: true, context: true, firewall: true, inference: true, sandbox: true, vfs: true, physical: true });
    }
    pushLine('success', `${next.toUpperCase()} state engaged`);
  };

  const toggleDefense = (id: DefenseId) => {
    setDefenses(prev => {
      const next = !prev[id];
      pushLine(next ? 'success' : 'error', `${defenseLabels[id]} ${next ? 'ARMED' : 'DISARMED'}`);
      return { ...prev, [id]: next };
    });
  };

  const deployCountermeasures = () => {
    setThreatCount(value => Math.max(0, value - 64));
    setShield(value => Math.min(100, value + 0.2));
    setLatency(value => Math.max(6, value - 2));
    pushLine('success', 'COUNTERMEASURE SWARM DEPLOYED // threat pressure reduced');
  };

  const probeRealm = async (target: RealmId) => {
    setRealmState(prev => ({ ...prev, [target]: 'probing' }));
    pushLine('info', `Bifrost probing ${target}...`);
    try {
      const response = await fetch(`${BIFROST_URL}/api/bifrost/probe/${target}`);
      const body = await response.json();
      const online = Boolean(body?.reachable);
      setRealmState(prev => ({ ...prev, [target]: online ? 'online' : 'offline' }));
      pushLine(online ? 'success' : 'error', `${target.toUpperCase()} // ${body?.detail || (online ? 'reachable' : 'unreachable')}`);
    } catch (error) {
      setRealmState(prev => ({ ...prev, [target]: 'offline' }));
      pushLine('error', `${target.toUpperCase()} probe failed // ${error instanceof Error ? error.message : 'unknown error'}`);
    }
  };

  const executeCrossing = async (targetId: RealmId = realm) => {
    const targetRealm = realms.find(item => item.id === targetId) ?? selectedRealm;
    setBusy(true);
    pushLine('info', `Crossing request // ${targetRealm.label} via ${targetRealm.transport}`);
    try {
      const response = await fetch(`${BIFROST_URL}/api/bifrost/crossing`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'camelot', destination: targetRealm.id, transport: targetRealm.transport, intent, payload: '' }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error || `HTTP ${response.status}`);
      pushLine('success', `${body?.result || 'ROUTE VALIDATED'}${body?.detail ? ` // ${body.detail}` : ''}`);
    } catch (error) {
      pushLine('error', `Bifrost crossing failed // ${error instanceof Error ? error.message : 'unknown error'}`);
    } finally { setBusy(false); }
  };

  const printHelp = () => {
    ['status','mode nominal|battle|lockdown','scene list | scene go <id|00..08> | scene explain','threat list | threat filter <type>','defense list | defense arm|disarm|toggle <id> | defense all on|off','auto on|off','counter deploy','bifrost status | bifrost probe <realm> | bifrost cross <realm>','clear'].forEach(text => pushLine('info', text));
  };

  const runCommand = async (raw: string) => {
    const command = raw.trim();
    if (!command) return;
    pushLine('command', `❯ ${command}`);
    setHistory(prev => [command, ...prev.filter(item => item !== command)].slice(0, 50));
    setHistoryIndex(-1);
    const parts = command.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g)?.map(token => token.replace(/^['"]|['"]$/g, '')) ?? [];
    const [root = '', sub = '', ...rest] = parts;
    try {
      switch (root.toLowerCase()) {
        case 'help': printHelp(); break;
        case 'clear': setLines([]); break;
        case 'status': pushLine('info', `MODE ${mode.toUpperCase()} // SCENE ${selectedScene.index} ${selectedScene.label} // THREATS ${threatCount} // DEFENSE ${readiness}% // SHIELD ${shield.toFixed(1)}% // LATENCY ${latency}ms`); break;
        case 'mode': {
          const next = sub.toLowerCase() as BattleMode;
          if (!['nominal', 'battle', 'lockdown'].includes(next)) throw new Error('mode requires nominal, battle, or lockdown');
          applyMode(next); break;
        }
        case 'scene': {
          if (sub === 'list') { scenes.forEach(item => pushLine('info', `${item.index} ${item.label} (${item.id})`)); break; }
          if (sub === 'explain') { pushLine('info', `${selectedScene.index} ${selectedScene.label} // ${selectedScene.purpose}`); break; }
          if (sub === 'go') {
            const target = rest[0]?.toLowerCase(); const found = scenes.find(item => item.id === target || item.index === target);
            if (!found) throw new Error(`unknown scene: ${target || '(missing)'}`);
            setScene(found.id); pushLine('success', `Context moved to ${found.index} ${found.label}`); break;
          }
          throw new Error('scene supports list, go, or explain');
        }
        case 'threat': {
          if (sub === 'list') { threats.forEach(item => pushLine('info', `${item.id}${item.id === threatFilter ? ' *' : ''}`)); break; }
          if (sub === 'filter') {
            const target = rest.join('-').toLowerCase() as ThreatFilter;
            if (!threats.some(item => item.id === target)) throw new Error(`unknown threat filter: ${target || '(missing)'}`);
            setThreatFilter(target); pushLine('success', `Threat filter applied // ${target}`); break;
          }
          throw new Error('threat supports list or filter');
        }
        case 'defense': {
          if (sub === 'list') { (Object.keys(defenseLabels) as DefenseId[]).forEach(id => pushLine(defenses[id] ? 'success' : 'error', `${id} // ${defenseLabels[id]} // ${defenses[id] ? 'ACTIVE' : 'OFFLINE'}`)); break; }
          if (sub === 'all') {
            const enabled = rest[0] === 'on'; if (!['on', 'off'].includes(rest[0])) throw new Error('defense all requires on or off');
            setDefenses({ memcastle: enabled, context: enabled, firewall: enabled, inference: enabled, sandbox: enabled, vfs: enabled, physical: enabled });
            pushLine(enabled ? 'success' : 'error', `All defenses ${enabled ? 'ARMED' : 'DISARMED'}`); break;
          }
          if (['arm', 'disarm', 'toggle'].includes(sub)) {
            const id = rest[0] as DefenseId; if (!defenseLabels[id]) throw new Error(`unknown defense: ${id || '(missing)'}`);
            setDefenses(prev => { const enabled = sub === 'toggle' ? !prev[id] : sub === 'arm'; pushLine(enabled ? 'success' : 'error', `${defenseLabels[id]} ${enabled ? 'ARMED' : 'DISARMED'}`); return { ...prev, [id]: enabled }; });
            break;
          }
          throw new Error('defense supports list, all, arm, disarm, or toggle');
        }
        case 'auto': if (!['on', 'off'].includes(sub)) throw new Error('auto requires on or off'); else { setAutoResponse(sub === 'on'); pushLine('success', `Autonomous response ${sub === 'on' ? 'ENABLED' : 'DISABLED'}`); } break;
        case 'counter': if (sub !== 'deploy') throw new Error('counter currently supports deploy'); else deployCountermeasures(); break;
        case 'bifrost': {
          if (sub === 'status') { const response = await fetch(`${BIFROST_URL}/api/bifrost/config`); const body = await response.json(); pushLine(response.ok ? 'success' : 'error', JSON.stringify(body)); break; }
          if (sub === 'probe') { const target = rest[0] as RealmId; if (!realms.some(item => item.id === target)) throw new Error('realm must be multivoice, godseye, or worldmonitor'); await probeRealm(target); break; }
          if (sub === 'cross') { const target = rest[0] as RealmId; if (!realms.some(item => item.id === target)) throw new Error('realm must be multivoice, godseye, or worldmonitor'); setRealm(target); await executeCrossing(target); break; }
          throw new Error('bifrost supports status, probe, or cross');
        }
        default: throw new Error(`unknown command: ${root}. Type help.`);
      }
    } catch (error) { pushLine('error', error instanceof Error ? error.message : 'Command failed'); }
  };

  const submit = (event: FormEvent) => { event.preventDefault(); const value = input; setInput(''); void runCommand(value); };
  const keyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowUp') { event.preventDefault(); const next = Math.min(history.length - 1, historyIndex + 1); if (next >= 0) { setHistoryIndex(next); setInput(history[next] ?? ''); } }
    if (event.key === 'ArrowDown') { event.preventDefault(); const next = Math.max(-1, historyIndex - 1); setHistoryIndex(next); setInput(next === -1 ? '' : history[next] ?? ''); }
  };
  const quickCommands = useMemo(() => ['status', 'mode lockdown', 'scene list', 'defense list', 'counter deploy', 'bifrost status'], []);

  return <section className="sovereign-terminal" id="sovereign-terminal-command-center" onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); inputRef.current?.focus(); } }}>
    <header className="st-topbar">
      <div className="st-brand"><div className="st-crest">♜</div><div><span>SOVEREIGN TERMINAL</span><strong>Camelot-OS Operator Command Center</strong></div></div>
      <div className="st-mode-switch" aria-label="Battle state"><button className={mode === 'nominal' ? 'active nominal' : ''} onClick={() => applyMode('nominal')}><Power size={14}/>Nominal</button><button className={mode === 'battle' ? 'active battle' : ''} onClick={() => applyMode('battle')}><Swords size={14}/>Battle</button><button className={mode === 'lockdown' ? 'active lockdown' : ''} onClick={() => applyMode('lockdown')}><LockKeyhole size={14}/>Lockdown</button></div>
      <div className="st-runtime"><i className="online"/><span>Browser UI</span><b>{readiness}% DEFENSE</b></div>
    </header>
    <div className="st-mobile-tabs" role="tablist">{(['terminal', 'operations', 'bifrost'] as const).map(tab => <button key={tab} className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)}>{tab}</button>)}</div>
    <div className="st-workspace">
      <aside className={`st-left ${activeTab === 'operations' ? 'mobile-active' : ''}`}><div className="st-panel-heading"><Network size={14}/><span>WORLD DIRECTOR</span><b>{selectedScene.index}/08</b></div><div className="st-scenes">{scenes.map(item => { const Icon = item.icon; return <button key={item.id} className={scene === item.id ? 'active' : ''} onClick={() => { setScene(item.id); pushLine('info', `Scene selected // ${item.index} ${item.label}`); }}><span className="st-scene-index">{item.index}</span><Icon size={14}/><span><strong>{item.label}</strong><small>{item.purpose}</small></span><ChevronRight size={13}/></button>; })}</div><div className="st-mini-status"><div><span>Threats</span><b>{threatCount}</b></div><div><span>Shield</span><b>{shield.toFixed(1)}%</b></div><div><span>Latency</span><b>{latency}ms</b></div><div><span>Auto</span><b>{autoResponse ? 'ON' : 'OFF'}</b></div></div></aside>
      <main className={`st-center ${activeTab === 'terminal' ? 'mobile-active' : ''}`}><div className="st-terminal-toolbar"><div><Terminal size={15}/><strong>camelot@world-tree</strong><span>~/sovereign</span></div><button onClick={() => setLines([])}>CLEAR</button></div><div className="st-terminal-output" ref={terminalRef} role="log" aria-live="polite">{lines.map(line => <div key={line.id} className={`st-line ${line.kind}`}><span className="st-prompt-mark">{line.kind === 'command' ? '›' : line.kind === 'success' ? '✓' : line.kind === 'error' ? '!' : '·'}</span><pre>{line.text}</pre></div>)}</div><div className="st-quick-commands">{quickCommands.map(command => <button key={command} onClick={() => void runCommand(command)}>{command}</button>)}</div><form className="st-command-line" onSubmit={submit}><span>camelot ❯</span><input ref={inputRef} value={input} onChange={event => setInput(event.target.value)} onKeyDown={keyDown} placeholder="Enter sovereign command..." autoComplete="off" spellCheck={false}/><button type="submit" aria-label="Execute command"><Send size={15}/></button></form><div className="st-command-hint">↑↓ history · Ctrl/Cmd+K focus · type <b>help</b> for command map</div></main>
      <aside className={`st-right ${activeTab === 'bifrost' ? 'mobile-active' : ''}`}>
        <section className="st-card"><div className="st-panel-heading"><Shield size={14}/><span>DEFENSE GRID</span><b>{activeDefenses}/7</b></div><div className="st-defense-list">{(Object.keys(defenseLabels) as DefenseId[]).map(id => <button key={id} className={defenses[id] ? 'active' : ''} onClick={() => toggleDefense(id)}><i/><span>{defenseLabels[id]}</span><b>{defenses[id] ? 'ARMED' : 'OFF'}</b></button>)}</div></section>
        <section className="st-card"><div className="st-panel-heading"><Crosshair size={14}/><span>THREAT FILTER</span><b>{threatCount}</b></div><div className="st-threat-grid">{threats.map(item => <button key={item.id} className={threatFilter === item.id ? 'active' : ''} onClick={() => { setThreatFilter(item.id); pushLine('success', `Threat filter applied // ${item.label}`); }}>{item.label}</button>)}</div><button className="st-deploy" onClick={deployCountermeasures}><Activity size={14}/>DEPLOY COUNTERMEASURES</button></section>
        <section className="st-card st-bifrost-card"><div className="st-panel-heading"><Route size={14}/><span>BIFROST</span><b>GOVERNED</b></div><div className="st-realm-tabs">{realms.map(item => { const Icon = item.icon; return <button key={item.id} className={realm === item.id ? 'active' : ''} onClick={() => setRealm(item.id)}><Icon size={13}/><span>{item.label}</span><i className={realmState[item.id]}/></button>; })}</div><label className="st-intent"><span>Crossing intent</span><textarea value={intent} onChange={event => setIntent(event.target.value)} rows={3}/></label><div className="st-bifrost-actions"><button onClick={() => void probeRealm(realm)} disabled={busy}><CircleDot size={13}/>Probe</button><button className="primary" onClick={() => void executeCrossing(realm)} disabled={busy}><Route size={13}/>{busy ? 'Crossing...' : 'Authorize Crossing'}</button></div></section>
      </aside>
    </div>
    <footer className="st-footer"><span><Castle size={12}/>MemCastle <b>{defenses.memcastle ? 'FORTIFIED' : 'OPEN'}</b></span><span><Brain size={12}/>Twin Brains <b>SYNC</b></span><span><Zap size={12}/>Ouroboros <b>RECURRENT</b></span><span><Database size={12}/>VFS <b>{defenses.vfs ? 'GUARDED' : 'OPEN'}</b></span><span><Radio size={12}/>Bifrost <b>{selectedRealm.transport.toUpperCase()}</b></span></footer>
  </section>;
};

export default SovereignTerminalCommandCenter;
