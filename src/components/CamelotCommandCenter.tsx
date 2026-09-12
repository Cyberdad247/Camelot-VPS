import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Brain,
  Castle,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  Crown,
  Database,
  FileText,
  FolderOpen,
  Gauge,
  Globe2,
  Home,
  LockKeyhole,
  Mic,
  Network,
  Radio,
  RefreshCw,
  Route,
  Search,
  Send,
  Shield,
  ShieldCheck,
  Swords,
  Terminal,
  TreeDeciduous,
  Volume2,
  Zap,
} from 'lucide-react';
import type { SystemVitals, TerminalLog } from '../types';
import './camelot-command-center.css';

type Zone = 'tree' | 'vfs' | 'brains' | 'throne' | 'battle';
type DefenseId = 'memcastle' | 'firewall' | 'context' | 'inference' | 'sandbox' | 'tracking' | 'counter';
type BridgeState = 'idle' | 'probing' | 'online' | 'offline';

type CouncilMessage = {
  id: number;
  speaker: string;
  text: string;
  kind: 'operator' | 'knight' | 'system';
};

type Knight = {
  id: string;
  name: string;
  short: string;
  title: string;
  role: string;
  color: string;
  icon: string;
  voiceLine: string;
};

interface CamelotCommandCenterProps {
  vitals: SystemVitals;
  logs: TerminalLog[];
  onExecuteCommand: (command: string) => void;
  onNavigateTab: (tab: string) => void;
}

const BIFROST_URL = ((import.meta as any).env?.VITE_BIFROST_URL || 'http://127.0.0.1:4188').replace(/\/$/, '');

const KNIGHTS: Knight[] = [
  { id: 'lady_mnemosyne', name: 'Lady Mnemosyne', short: 'Mnemosyne', title: 'Memory Keeper', role: 'Memory', color: '#38bdf8', icon: '💎', voiceLine: 'Memory is a bridge, not a vault. What shall we recall?' },
  { id: 'sir_codex', name: 'Sir Codex', short: 'Codex', title: 'Compiler', role: 'Implementation', color: '#d4af37', icon: '⚡', voiceLine: 'Deterministic logic stands ready. Give me the machine you want built.' },
  { id: 'sir_loren', name: 'Sir Loren', short: 'Loren', title: 'Researcher', role: 'Research', color: '#a855f7', icon: '📜', voiceLine: 'The corpus is open. Name the truth you want traced.' },
  { id: 'sir_aegis', name: 'Sir Aegis', short: 'Aegis', title: 'Guardian', role: 'Security', color: '#10b981', icon: '🛡️', voiceLine: 'The sovereign boundary is watched. State the threat.' },
  { id: 'sir_calculus', name: 'Sir Calculus', short: 'Calculus', title: 'Analyst', role: 'Validation', color: '#ec4899', icon: '📐', voiceLine: 'State the invariant. I will test what must remain true.' },
  { id: 'sir_lumen', name: 'Sir Lumen', short: 'Lumen', title: 'Visionary', role: 'Spatial UI', color: '#06b6d4', icon: '✨', voiceLine: 'Form and light are ready. Tell me what the operator should feel and understand.' },
  { id: 'sir_pragmata', name: 'Sir Pragmata', short: 'Pragmata', title: 'Executor', role: 'Deployment', color: '#84cc16', icon: '⚙️', voiceLine: 'The plan is only real when it ships. Name the target.' },
  { id: 'sir_harmonia', name: 'Sir Harmonia', short: 'Harmonia', title: 'Alignment', role: 'Alignment', color: '#6366f1', icon: '⚖️', voiceLine: 'Power and safety share the same table. What must we balance?' },
  { id: 'sir_nexus', name: 'Sir Nexus', short: 'Nexus', title: 'Connector', role: 'Routing', color: '#14b8a6', icon: '🌐', voiceLine: 'All paths are visible. Tell me what must connect.' },
  { id: 'sir_prompt', name: 'Sir Prompt', short: 'Prompt', title: 'Orchestrator', role: 'Orchestration', color: '#f59e0b', icon: '🎼', voiceLine: 'Declare the intention. I will turn it into an ordered path.' },
];

const ARCHITECTURE = [
  ['L7', 'SOVEREIGN INTELLIGENCE', 'Strategy • Vision • Self'],
  ['L6', 'THRONE ROOM', 'MemCastle • Knight Council'],
  ['L5', 'TWIN BRAINS', 'Open-Notebook • NotebookLM'],
  ['L4', 'INTELLIGENCE LAYER', 'RAG • Agents • Reasoning'],
  ['L3', 'DATA & KNOWLEDGE', 'Vector DB • Graph • Context'],
  ['L2', 'VFS ROOTS', 'Files • Code • Media • Artifacts'],
  ['L1', 'INFRASTRUCTURE', 'Compute • Storage • Network'],
  ['L0', 'PHYSICAL LAYER', 'Hardware • Cloud • Edge'],
] as const;

const GATES = [
  ['API GATE', 12],
  ['WEB GATE', 18],
  ['VFS GATE', 6],
  ['AGENT GATE', 14],
  ['MEMORY GATE', 11],
  ['EXTERNAL GATE', 22],
] as const;

const DEFENSE_LABELS: Record<DefenseId, string> = {
  memcastle: 'MEMCASTLE SHIELD',
  firewall: 'AI FIREWALL',
  context: 'CONTEXT FILTER',
  inference: 'INFERENCE GUARD',
  sandbox: 'DATA SANDBOX',
  tracking: 'ADVERSARY TRACKING',
  counter: 'AUTO COUNTERMEASURE',
};

const zoneLabel: Record<Zone, string> = {
  tree: 'Full Tree',
  vfs: 'VFS Roots',
  brains: 'Twin Brains',
  throne: 'Throne Room',
  battle: 'Battle Mode',
};

export const CamelotCommandCenter: React.FC<CamelotCommandCenterProps> = ({
  vitals,
  logs,
  onExecuteCommand,
  onNavigateTab,
}) => {
  const [zone, setZone] = useState<Zone>('tree');
  const [battleMode, setBattleMode] = useState(false);
  const [threatCount, setThreatCount] = useState(247);
  const [selectedKnight, setSelectedKnight] = useState(2);
  const [orbit, setOrbit] = useState(false);
  const [voiceText, setVoiceText] = useState('');
  const [consoleText, setConsoleText] = useState('');
  const [listening, setListening] = useState(false);
  const [bridgeState, setBridgeState] = useState<BridgeState>('idle');
  const [defenses, setDefenses] = useState<Record<DefenseId, boolean>>({
    memcastle: true,
    firewall: true,
    context: true,
    inference: true,
    sandbox: true,
    tracking: true,
    counter: true,
  });
  const [councilMessages, setCouncilMessages] = useState<CouncilMessage[]>([
    { id: 1, speaker: 'SYSTEM', text: 'Voice Council Chamber online. Select a Knight or address the Council.', kind: 'system' },
    { id: 2, speaker: 'Sir Aegis', text: 'Heimdall gates are green. Sovereign boundary intact.', kind: 'knight' },
    { id: 3, speaker: 'Lady Mnemosyne', text: 'MemCastle context is synchronized and ready.', kind: 'knight' },
  ]);
  const messageId = useRef(4);
  const councilRef = useRef<HTMLDivElement>(null);

  const activeKnight = KNIGHTS[selectedKnight];
  const usedRamGb = (vitals.usedRamMB / 1024).toFixed(2);
  const ramPercent = Math.min(100, Math.round((vitals.usedRamMB / vitals.scarcityCapMB) * 100));
  const defenseIntegrity = Math.round((Object.values(defenses).filter(Boolean).length / Object.keys(defenses).length) * 1000) / 10;

  const recentLogs = useMemo(() => logs.slice(-6).reverse(), [logs]);
  const activityFeed = useMemo(() => {
    const base = logs.slice(-5).reverse().map((log, index) => ({
      id: `${log.id}-${index}`,
      time: log.timestamp,
      text: log.message,
      level: log.level === 'warn' ? 'WARN' : log.level === 'success' ? 'SUCCESS' : 'INFO',
    }));
    return base.length ? base : [
      { id: 'fallback-1', time: '22:41:12', text: 'Threat blocked: malicious prompt', level: 'WARN' },
      { id: 'fallback-2', time: '22:41:03', text: 'NotebookLM sync completed', level: 'INFO' },
    ];
  }, [logs]);

  useEffect(() => {
    if (!orbit) return;
    const timer = window.setInterval(() => setSelectedKnight(value => (value + 1) % KNIGHTS.length), 3600);
    return () => window.clearInterval(timer);
  }, [orbit]);

  useEffect(() => {
    councilRef.current?.scrollTo({ top: councilRef.current.scrollHeight, behavior: 'smooth' });
  }, [councilMessages]);

  const addCouncil = (speaker: string, text: string, kind: CouncilMessage['kind']) => {
    setCouncilMessages(prev => [...prev.slice(-19), { id: messageId.current++, speaker, text, kind }]);
  };

  const selectZone = (next: Zone) => {
    setZone(next);
    if (next === 'battle') setBattleMode(true);
    if (next === 'throne') {
      window.setTimeout(() => document.getElementById('cc-voice-council')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 40);
    }
  };

  const speakKnight = () => {
    if (!('speechSynthesis' in window)) {
      addCouncil('SYSTEM', 'Browser speech synthesis is unavailable on this device.', 'system');
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(`${activeKnight.name}. ${activeKnight.voiceLine}`);
    utterance.rate = 0.88;
    utterance.pitch = 0.92;
    window.speechSynthesis.speak(utterance);
    addCouncil(activeKnight.name, activeKnight.voiceLine, 'knight');
  };

  const beginListening = () => {
    const SpeechRecognitionCtor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      addCouncil('SYSTEM', 'Speech recognition is unavailable. Type your message instead.', 'system');
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    setListening(true);
    recognition.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript || '';
      setVoiceText(transcript);
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    recognition.start();
  };

  const submitCouncilIntent = () => {
    const text = voiceText.trim();
    if (!text) return;
    addCouncil('YOU', text, 'operator');
    addCouncil(activeKnight.name, `Intent received. ${activeKnight.role} context selected. Remote synthesis will route through the governed Multivoice/Bifrost boundary when connected.`, 'knight');
    onExecuteCommand(`council --knight ${activeKnight.id} --intent "${text.replace(/"/g, '\\"')}"`);
    setVoiceText('');
  };

  const submitConsole = () => {
    const command = consoleText.trim();
    if (!command) return;
    onExecuteCommand(command);
    setConsoleText('');
  };

  const probeBifrost = async () => {
    setBridgeState('probing');
    try {
      const response = await fetch(`${BIFROST_URL}/api/bifrost/probe/multivoice`);
      const body = await response.json();
      const online = response.ok && Boolean(body?.reachable);
      setBridgeState(online ? 'online' : 'offline');
      addCouncil('BIFROST', body?.detail || (online ? 'Multivoice bridge reachable.' : 'Multivoice bridge unavailable.'), 'system');
    } catch {
      setBridgeState('offline');
      addCouncil('BIFROST', 'Local Bifrost gateway is not reachable from this browser.', 'system');
    }
  };

  const runQuickAction = (action: string) => {
    switch (action) {
      case 'scan':
        setBattleMode(true);
        setZone('battle');
        setThreatCount(value => Math.max(247, value));
        onExecuteCommand('camelot-diag --scan-threats');
        break;
      case 'sync':
        setZone('brains');
        onExecuteCommand('sync-engines --twin-brains');
        break;
      case 'backup':
        onExecuteCommand('camelot-backup --mempalace --vfs');
        break;
      case 'deploy':
        onNavigateTab('mission');
        break;
      case 'vfs':
        setZone('vfs');
        onNavigateTab('deck');
        break;
      case 'throne':
        selectZone('throne');
        break;
      case 'defense':
        setDefenses(prev => ({ ...prev, memcastle: !prev.memcastle }));
        break;
      case 'report':
        onExecuteCommand('camelot-report --full');
        break;
    }
  };

  const toggleDefense = (id: DefenseId) => {
    setDefenses(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <section className={`camelot-command-center zone-${zone} ${battleMode ? 'battle-active' : ''}`} id="camelot-command-center">
      <header className="cc-topbar">
        <button className="cc-brand" onClick={() => selectZone('tree')} aria-label="Camelot World Tree home">
          <span className="cc-tree-mark"><TreeDeciduous size={25}/></span>
          <span><strong>Camelot-OS <b>World Tree</b></strong><small>THE SOVEREIGN WORLD TREE CONTROL CENTER</small></span>
        </button>

        <nav className="cc-nav" aria-label="World Tree command center sections">
          <button className={zone === 'tree' ? 'active' : ''} onClick={() => selectZone('tree')}><Home size={14}/>Full Tree</button>
          <button className={zone === 'vfs' ? 'active' : ''} onClick={() => selectZone('vfs')}><Database size={14}/>VFS Roots</button>
          <button className={zone === 'brains' ? 'active' : ''} onClick={() => selectZone('brains')}><Brain size={14}/>Twin Brains</button>
          <button className={zone === 'throne' ? 'active throne' : ''} onClick={() => selectZone('throne')}><Castle size={14}/>Throne Room</button>
          <button className={battleMode ? 'active battle' : ''} onClick={() => { setBattleMode(value => !value); setZone('battle'); }}><Swords size={14}/>Battle Mode</button>
        </nav>

        <div className="cc-sovereign-status">
          <span><Crown size={13}/>SOLO CEO MODE</span>
          <b>HUMAN × AI × SOVEREIGN</b>
          <button onClick={() => onNavigateTab('deck')}>WORLD TREE</button>
        </div>
      </header>

      <div className="cc-main-grid">
        <aside className="cc-left-rail">
          <article className="cc-panel cc-architecture">
            <div className="cc-panel-title"><LayersIcon/><span>World Tree Architecture</span><small>L7 → L0</small></div>
            <div className="cc-arch-list">
              {ARCHITECTURE.map(([id, name, desc]) => <button key={id} onClick={() => selectZone(id === 'L6' ? 'throne' : id === 'L5' ? 'brains' : id === 'L2' ? 'vfs' : 'tree')}>
                <b>{id}</b><span><strong>{name}</strong><small>{desc}</small></span><i/>
              </button>)}
            </div>
          </article>

          <article className="cc-panel">
            <div className="cc-panel-title"><ShieldCheck size={14}/><span>Heimdall Gate Status</span><small>ALL GATES OPERATIONAL</small></div>
            <div className="cc-gates">
              <div className="cc-gate-list">
                {GATES.map(([name, latency]) => <div key={name}><Shield size={11}/><span>{name}</span><i/><b>Online</b><small>{latency} ms</small></div>)}
              </div>
              <button className="cc-heimdall" onClick={() => onExecuteCommand('heimdall --verify-all')}><LockKeyhole size={28}/><strong>HEIMDALL</strong><small>WATCHES ALL PATHS</small></button>
            </div>
          </article>

          <article className="cc-panel cc-telemetry">
            <div className="cc-panel-title"><Gauge size={14}/><span>Tactical Telemetry</span><small className="live">● LIVE</small></div>
            <div className="cc-stat-grid">
              <div className="danger"><b>{battleMode ? threatCount : 18}</b><span>THREATS / MIN</span><small>{battleMode ? '▲ +12%' : 'NOMINAL'}</small></div>
              <div><b>{defenseIntegrity}%</b><span>DEFENSE INTEGRITY</span></div>
              <div><b>{battleMode ? 12 : 22}ms</b><span>RESPONSE LATENCY</span></div>
              <div><b>{Math.max(72, 100 - Math.round(ramPercent / 3))}%</b><span>SYSTEM HEALTH</span></div>
            </div>
            <div className="cc-sparkline" aria-hidden="true"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div>
            <div className="cc-threat-types"><span>AI ADVERSARY <b>23</b></span><span>DATA EXFILTRATION <b>18</b></span><span>PROMPT INJECTION <b>12</b></span><span>DDOS / FLOOD <b>8</b></span></div>
          </article>

          <article className="cc-panel cc-console-panel">
            <div className="cc-panel-title"><Terminal size={14}/><span>System Console</span><small>LIVE</small></div>
            <div className="cc-console-log">
              {recentLogs.map(log => <div key={log.id}><span>[{log.timestamp}]</span><b>✓</b><em>{log.message}</em></div>)}
            </div>
            <form onSubmit={event => { event.preventDefault(); submitConsole(); }} className="cc-console-input"><span>root@camelot-os:~$</span><input value={consoleText} onChange={event => setConsoleText(event.target.value)} aria-label="System command"/><button type="submit"><Send size={12}/></button></form>
          </article>
        </aside>

        <main className="cc-world-stage">
          <div className="cc-stage-glow"/>
          <img
            className="cc-tree-image"
            src="/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png"
            alt="Camelot-OS World Tree"
            onError={event => { (event.currentTarget as HTMLImageElement).src = 'https://i.postimg.cc/Lssx07X3/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png'; }}
          />

          <button className="cc-hotspot cc-hotspot-castle" onClick={() => selectZone('throne')}><Castle size={17}/><span><b>Redis MemCastle</b><small>THE THRONE ROOM</small></span></button>
          <button className="cc-speak-callout" onClick={() => selectZone('throne')}><Mic size={15}/><span><b>SPEAK TO THE KNIGHTS</b><small>Your thoughts. Their power.<br/>Memory. Strategy. Action.</small></span></button>
          <button className="cc-hotspot cc-hotspot-left-brain" onClick={() => selectZone('brains')}><Brain size={17}/><span><b>Open-Notebook</b><small>ANALYZE • REASON • EXPLORE</small></span></button>
          <button className="cc-hotspot cc-hotspot-right-brain" onClick={() => selectZone('brains')}><Brain size={17}/><span><b>NotebookLM</b><small>REMEMBER • CONNECT • CREATE</small></span></button>
          <button className="cc-hotspot cc-hotspot-vfs" onClick={() => selectZone('vfs')}><Database size={17}/><span><b>VFS ROOTS</b><small>THE LIVING FILE SYSTEM</small></span></button>

          <div className="cc-zone-caption"><span>{zoneLabel[zone]}</span><b>{zone === 'throne' ? 'Council conversation chamber' : zone === 'brains' ? 'Reasoning and knowledge synthesis' : zone === 'vfs' ? 'Files, memory, and data movement' : zone === 'battle' ? 'Active defense and countermeasure state' : 'Sovereign architecture overview'}</b></div>

          <section className="cc-voice-council" id="cc-voice-council" style={{ ['--knight-accent' as string]: activeKnight.color }}>
            <div className="cc-council-heading"><span className="cc-council-mark"><Crown size={16}/></span><div><strong>Voice Council Chamber</strong><small>SPEAK TO THE KNIGHTS // MULTI-AGENT INTELLIGENCE COUNCIL</small></div><span className="cc-council-live">● LIVE</span></div>
            <div className="cc-council-body">
              <div className="cc-knight-selector">
                <button onClick={() => setSelectedKnight(value => (value - 1 + KNIGHTS.length) % KNIGHTS.length)} aria-label="Previous Knight"><ChevronLeft size={20}/></button>
                <div className="cc-knight-carousel">
                  {[-2, -1, 0, 1, 2].map(offset => {
                    const index = (selectedKnight + offset + KNIGHTS.length) % KNIGHTS.length;
                    const knight = KNIGHTS[index];
                    return <button key={`${knight.id}-${offset}`} className={`cc-knight-card offset-${offset + 2} ${offset === 0 ? 'active' : ''}`} onClick={() => setSelectedKnight(index)}>
                      <span className="cc-helmet"><i>{knight.icon}</i><Shield size={32}/></span>
                      <strong>{knight.short}</strong><small>{knight.role}</small>
                    </button>;
                  })}
                </div>
                <button onClick={() => setSelectedKnight(value => (value + 1) % KNIGHTS.length)} aria-label="Next Knight"><ChevronRight size={20}/></button>
                <div className="cc-council-actions"><button className={orbit ? 'active' : ''} onClick={() => setOrbit(value => !value)}><RefreshCw size={12}/>Orbit</button><button onClick={speakKnight}><Volume2 size={12}/>Preview Voice</button></div>
              </div>

              <div className="cc-transcript" ref={councilRef} aria-live="polite">
                <div className="cc-transcript-title">Live Council Transcript</div>
                {councilMessages.map(message => <div key={message.id} className={message.kind}><b>{message.speaker}:</b><span>{message.text}</span></div>)}
              </div>
            </div>
            <div className="cc-voice-input-row">
              <button className={listening ? 'listening' : ''} onClick={beginListening} aria-label="Speak to the council"><Mic size={22}/></button>
              <div><input value={voiceText} onChange={event => setVoiceText(event.target.value)} onKeyDown={event => event.key === 'Enter' && submitCouncilIntent()} placeholder={`Speak to ${activeKnight.name}...`}/><small>Hold to speak or type your message. Selected: {activeKnight.title}.</small></div>
              <button onClick={submitCouncilIntent} aria-label="Send to selected Knight"><Send size={17}/></button>
            </div>
          </section>
        </main>

        <aside className="cc-right-rail">
          <article className={`cc-panel cc-battle-panel ${battleMode ? 'active' : ''}`}>
            <div className="cc-battle-icon"><Swords size={26}/></div><div><span>SOVEREIGN INTELLIGENCE</span><h2>{battleMode ? 'BATTLE MODE' : 'NOMINAL MODE'}</h2><b>{battleMode ? 'ALL SYSTEMS OPERATIONAL // DEFEND • MONITOR • COUNTER' : 'SYSTEM QUIET // OBSERVE • LEARN • PREPARE'}</b></div>
            <button onClick={() => setBattleMode(value => !value)}>{battleMode ? 'STAND DOWN' : 'ENGAGE'}</button>
          </article>

          <article className="cc-panel cc-bifrost-panel">
            <div className="cc-panel-title"><Route size={14}/><span>Bifrost Bridge</span><small>HERMES · HEIMDALL ORCHESTRATION</small></div>
            <div className="cc-bridge-status"><span>BRIDGE STATUS</span><b className={bridgeState}>{bridgeState === 'online' ? 'ONLINE' : bridgeState === 'probing' ? 'PROBING' : bridgeState === 'offline' ? 'OFFLINE' : 'UNKNOWN'}</b></div>
            <div className="cc-bifrost-map"><Globe2 size={34}/><i/><div><b>BIFROST</b><small>REAL-TIME INTELLIGENCE BRIDGE</small></div><i/><TreeDeciduous size={34}/></div>
            <div className="cc-route-labels"><span>EXTERNAL WORLD<small>APIs • Web • Data</small></span><b>ROUTE • FILTER • ENRICH<br/>PROTECT • SYNC • DELIVER</b><span>WORLD TREE<small>Knowledge • Agents</small></span></div>
            <button className="cc-probe" onClick={probeBifrost}><CircleDot size={12}/>Probe Multivoice Realm</button>
          </article>

          <article className="cc-panel cc-defense-panel">
            <div className="cc-panel-title"><Shield size={14}/><span>Defense State</span><small>SOVEREIGN PROTECTION LAYERS</small></div>
            <div className="cc-defense-core"><ShieldCheck size={34}/></div>
            <div className="cc-defense-list">{(Object.keys(DEFENSE_LABELS) as DefenseId[]).map(id => <button key={id} className={defenses[id] ? 'active' : ''} onClick={() => toggleDefense(id)}><i/><span>{DEFENSE_LABELS[id]}</span><b>{defenses[id] ? 'ACTIVE' : 'OFF'}</b></button>)}</div>
          </article>

          <article className="cc-panel cc-commands-panel">
            <div className="cc-panel-title"><Zap size={14}/><span>System Commands</span><small>QUICK ACTIONS</small></div>
            <div className="cc-command-grid">
              <button onClick={() => runQuickAction('scan')}><Search size={15}/>Scan Threats</button>
              <button onClick={() => runQuickAction('sync')}><Brain size={15}/>Sync Brains</button>
              <button onClick={() => runQuickAction('backup')}><Database size={15}/>Backup Now</button>
              <button onClick={() => runQuickAction('deploy')}><Network size={15}/>Deploy Agent</button>
              <button onClick={() => runQuickAction('vfs')}><FolderOpen size={15}/>Open VFS</button>
              <button onClick={() => runQuickAction('throne')}><Castle size={15}/>Enter Throne</button>
              <button onClick={() => runQuickAction('defense')}><Shield size={15}/>Toggle Defense</button>
              <button onClick={() => runQuickAction('report')}><FileText size={15}/>System Report</button>
            </div>
          </article>

          <article className="cc-panel cc-activity-panel">
            <div className="cc-panel-title"><Activity size={14}/><span>Live Activity Feed</span><small className="live">● LIVE</small></div>
            <div className="cc-activity-list">{activityFeed.map(item => <div key={item.id}><span>{item.time}</span><i className={item.level.toLowerCase()}/><b>{item.text}</b><em>{item.level}</em></div>)}</div>
          </article>
        </aside>
      </div>

      <aside className="cc-section-rail" aria-label="Section position">
        {(['tree', 'brains', 'vfs', 'throne', 'battle'] as Zone[]).map(item => <button key={item} className={zone === item ? 'active' : ''} onClick={() => selectZone(item)}><i/><span>{zoneLabel[item]}</span></button>)}
      </aside>

      <footer className="cc-footer"><span>© Camelot-OS // The Sovereign Context Engine</span><b>KNOWLEDGE ROOTS. STRONGER TOMORROWS.</b><span>RAM {usedRamGb}GB / 8GB // SOLO CEO</span></footer>
    </section>
  );
};

const LayersIcon = () => <Network size={14}/>;

export default CamelotCommandCenter;
