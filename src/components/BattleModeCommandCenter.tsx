import React, { useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, Brain, Castle, ChevronDown, Crosshair, Database,
  Eye, Flame, Gauge, LockKeyhole, Network, Play, Power, Radio, RefreshCw,
  Route, Shield, ShieldAlert, ShieldCheck, Swords, Target, Terminal, Zap,
} from 'lucide-react';
import './battle-mode-command-center.css';

type BattleState = 'nominal' | 'battle' | 'lockdown';
type ThreatType = 'DDoS' | 'Prompt Injection' | 'Data Exfiltration' | 'AI Adversary' | 'Reconnaissance';
type DefenseId = 'memcastle' | 'context' | 'firewall' | 'inference' | 'sandbox' | 'vfs' | 'physical';

interface ThreatRow {
  id: number;
  time: string;
  source: string;
  vector: ThreatType;
  target: string;
  status: 'BLOCKED' | 'NEUTRALIZED' | 'CONTAINED' | 'DEFLECTED' | 'TRACED';
}

const initialThreats: ThreatRow[] = [
  { id: 1, time: '12:03:17', source: '185.199.***', vector: 'DDoS', target: 'VFS_ROOT', status: 'BLOCKED' },
  { id: 2, time: '12:03:21', source: '45.33.***', vector: 'Prompt Injection', target: 'MEMCASTLE', status: 'NEUTRALIZED' },
  { id: 3, time: '12:03:24', source: '103.12.***', vector: 'AI Adversary', target: 'KNOWLEDGE', status: 'CONTAINED' },
  { id: 4, time: '12:03:28', source: '91.65.***', vector: 'Data Exfiltration', target: 'NOTEBOOKLM', status: 'BLOCKED' },
  { id: 5, time: '12:03:31', source: '172.16.***', vector: 'Reconnaissance', target: 'GRAPH_LAYER', status: 'TRACED' },
];

const defenseLabels: Record<DefenseId, string> = {
  memcastle: 'MemCastle Shield', context: 'Context Filter', firewall: 'AI Firewall',
  inference: 'Inference Guard', sandbox: 'Data Sandbox', vfs: 'VFS Perimeter', physical: 'Physical Layer',
};

const countermeasures = [
  ['Threat Isolation', 99], ['Traffic Redirection', 97], ['Prompt Sanitization', 100],
  ['Adversary Tracing', 96], ['Deception Honeypots', 93], ['Signature Updates', 100],
  ['Autonomous Response', 98],
] as const;

const modeCopy: Record<BattleState, { title: string; subtitle: string; color: string }> = {
  nominal: { title: 'NOMINAL', subtitle: 'Sovereign systems observing', color: '#34d399' },
  battle: { title: 'BATTLE MODE', subtitle: 'Threat response fabric engaged', color: '#ff4d5f' },
  lockdown: { title: 'LOCKDOWN', subtitle: 'Maximum containment posture', color: '#f59e0b' },
};

export const BattleModeCommandCenter: React.FC = () => {
  const [mode, setMode] = useState<BattleState>('battle');
  const [selectedThreat, setSelectedThreat] = useState<ThreatType>('Prompt Injection');
  const [threatCount, setThreatCount] = useState(247);
  const [shieldIntegrity, setShieldIntegrity] = useState(99.7);
  const [responseLatency, setResponseLatency] = useState(12);
  const [autoResponse, setAutoResponse] = useState(true);
  const [defenses, setDefenses] = useState<Record<DefenseId, boolean>>({
    memcastle: true, context: true, firewall: true, inference: true, sandbox: true, vfs: true, physical: true,
  });
  const [logs, setLogs] = useState([
    'SHIELD ABSORBED MASS ATTACK WAVE',
    'NODE BREACH ATTEMPT CONTAINED',
    'MALICIOUS PROMPT QUARANTINED',
    'THREAT ACTOR TRACED (TIER-1)',
    'COUNTERMEASURE SWARM DEPLOYED',
    'SYSTEMS STABLE',
  ]);
  const [command, setCommand] = useState('');
  const [pulse, setPulse] = useState(0);

  const activeDefenses = Object.values(defenses).filter(Boolean).length;
  const readiness = Math.round((activeDefenses / 7) * 92);
  const activeMode = modeCopy[mode];

  const filteredThreats = useMemo(
    () => initialThreats.filter(row => row.vector === selectedThreat || selectedThreat === 'Prompt Injection'),
    [selectedThreat],
  );

  const appendLog = (entry: string) => {
    setLogs(prev => [`${new Date().toLocaleTimeString([], { hour12: false })}  ${entry}`, ...prev].slice(0, 8));
  };

  const engageBattleMode = () => {
    setMode('battle');
    setThreatCount(value => Math.max(value, 247));
    setPulse(value => value + 1);
    appendLog('BATTLE MODE ENGAGED // RESPONSE FABRIC ONLINE');
  };

  const enterLockdown = () => {
    setMode('lockdown');
    setAutoResponse(true);
    setShieldIntegrity(100);
    setResponseLatency(8);
    setDefenses({ memcastle: true, context: true, firewall: true, inference: true, sandbox: true, vfs: true, physical: true });
    setPulse(value => value + 1);
    appendLog('HEIMDALL LOCKDOWN // ALL DEFENSE LAYERS SEALED');
  };

  const standDown = () => {
    setMode('nominal');
    setThreatCount(18);
    setResponseLatency(22);
    appendLog('BATTLE MODE STANDING DOWN // OBSERVATION POSTURE');
  };

  const toggleDefense = (id: DefenseId) => {
    setDefenses(prev => ({ ...prev, [id]: !prev[id] }));
    appendLog(`${defenseLabels[id].toUpperCase()} ${defenses[id] ? 'DISARMED' : 'ARMED'}`);
  };

  const deployCountermeasures = () => {
    setThreatCount(value => Math.max(0, value - 64));
    setShieldIntegrity(value => Math.min(100, value + 0.2));
    setResponseLatency(value => Math.max(6, value - 2));
    setPulse(value => value + 1);
    appendLog('COUNTERMEASURE SWARM DEPLOYED // 1,284 ROUTES/MIN');
  };

  const executeCommand = () => {
    if (!command.trim()) return;
    appendLog(`COMMAND EXECUTED // ${command.trim().toUpperCase()}`);
    setCommand('');
    setPulse(value => value + 1);
  };

  return (
    <section id="battle-mode-command-center" className={`battle-shell battle-shell--${mode}`}>
      <div className="battle-scanline" />
      <header className="battle-topbar">
        <div className="battle-brand">
          <div className="battle-tree-mark">♜</div>
          <div>
            <strong>Camelot-OS World Tree</strong>
            <span>THE SOVEREIGN CONTEXT ENGINE</span>
          </div>
        </div>
        <div className="battle-mode-badge" style={{ '--mode-color': activeMode.color } as React.CSSProperties}>
          <span>SYSTEM STATUS</span>
          <strong>{activeMode.title}</strong>
        </div>
        <div className="battle-top-actions">
          <button onClick={standDown}><Power size={14} /> Nominal</button>
          <button className="danger" onClick={engageBattleMode}><Swords size={14} /> Battle</button>
          <button className="amber" onClick={enterLockdown}><LockKeyhole size={14} /> Lockdown</button>
        </div>
      </header>

      <div className="battle-grid">
        <aside className="battle-column battle-column--left">
          <article className="battle-panel threat-panel">
            <div className="battle-panel-title"><Target size={16} /><span>THREAT MATRIX</span><b>REAL-TIME GLOBAL ATTACK SURFACE</b></div>
            <div className="threat-map" aria-label="Live threat map">
              <div className="map-grid" />
              {[12, 28, 42, 61, 76, 88].map((left, index) => <i key={left} style={{ left: `${left}%`, top: `${22 + (index % 3) * 24}%` }} />)}
              <svg viewBox="0 0 100 45" preserveAspectRatio="none" aria-hidden="true"><path d="M8,32 C24,4 48,5 62,25 S88,30 96,9"/><path d="M4,10 C28,42 55,35 78,7"/></svg>
            </div>
            <div className="threat-total"><div><span>ACTIVE THREATS</span><strong>{threatCount}</strong></div><div className="severity"><span>CRITICAL <b>23</b></span><span>HIGH <b>68</b></span><span>MEDIUM <b>112</b></span><span>LOW <b>44</b></span></div></div>
            <div className="threat-filters">
              {(['DDoS', 'Prompt Injection', 'Data Exfiltration', 'AI Adversary', 'Reconnaissance'] as ThreatType[]).map(type => (
                <button key={type} className={selectedThreat === type ? 'active' : ''} onClick={() => setSelectedThreat(type)}>{type}</button>
              ))}
            </div>
          </article>

          <article className="battle-panel telemetry-panel">
            <div className="battle-panel-title"><Activity size={16}/><span>TACTICAL TELEMETRY</span><b>SYSTEM PERFORMANCE UNDER ATTACK</b></div>
            <div className="gauge-row">
              {[['DEFENSE READINESS', `${readiness}%`], ['THREATS / MIN', `${threatCount}K`], ['SHIELD INTEGRITY', `${shieldIntegrity.toFixed(1)}%`], ['RESPONSE LATENCY', `${responseLatency}ms`]].map(([label, value]) => (
                <div className="mini-gauge" key={label}><strong>{value}</strong><span>{label}</span></div>
              ))}
            </div>
            <div className="spark-row"><div className="spark red"/><div className="spark cyan"/><div className="spark green"/></div>
          </article>

          <article className="battle-panel vector-panel">
            <div className="battle-panel-title"><Crosshair size={16}/><span>ATTACK VECTOR ANALYSIS</span><b>TRACE / CONTAIN / DEFLECT</b></div>
            <div className="battle-table">
              <div className="battle-tr battle-th"><span>TIME</span><span>SOURCE</span><span>VECTOR</span><span>TARGET</span><span>STATUS</span></div>
              {(filteredThreats.length ? filteredThreats : initialThreats).map(row => (
                <button key={row.id} className="battle-tr" onClick={() => { setSelectedThreat(row.vector); appendLog(`TARGET LOCK // ${row.source} ${row.vector}`); }}>
                  <span>{row.time}</span><span>{row.source}</span><span>{row.vector}</span><span>{row.target}</span><strong>{row.status}</strong>
                </button>
              ))}
            </div>
          </article>
        </aside>

        <main className="battle-core">
          <div className="battle-core-status">
            <Castle size={18}/><span>Redis MemCastle</span><b>{mode === 'nominal' ? 'OBSERVING' : 'FORTIFIED // ACTIVE DEFENSE'}</b>
          </div>
          <div className={`battle-worldtree ${pulse ? 'battle-worldtree--pulse' : ''}`} key={pulse}>
            <img src="/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png" alt="Camelot-OS World Tree" />
            <div className="battle-shield-dome" />
            <div className="battle-target-ring ring-a"/><div className="battle-target-ring ring-b"/><div className="battle-target-ring ring-c"/>
            <div className="battle-attack-lines">{Array.from({ length: 9 }).map((_, i) => <i key={i} style={{ '--i': i } as React.CSSProperties}/>)}</div>
            <div className="battle-brain-label brain-left"><Brain size={14}/><span>OPEN-NOTEBOOK</span><b>COMBAT ANALYSIS</b></div>
            <div className="battle-brain-label brain-right"><Brain size={14}/><span>NOTEBOOKLM</span><b>STRATEGIC SYNCHRONIZER</b></div>
            <div className="battle-ouroboros"><Zap size={14}/><span>O(1) STATE LOOP</span><strong>OUROBOROS SSM</strong><small>DETECT ⟡ REASON ⟡ DEFEND ⟡ EVOLVE</small></div>
            <div className="battle-vfs-label"><Database size={14}/><span>VFS // OPEN VIKING PROTOCOL</span><b>REAL-TIME DATA DEFENSE FABRIC</b></div>
          </div>
          <div className="battle-core-footer">
            <div><span>vKG_HUD</span><strong>THE SOVEREIGN WORLD TREE CONTROL CENTER</strong><small>MYTHIC ARCHITECTURE // ENGINEERED INTELLIGENCE // BATTLE READY</small></div>
          </div>
        </main>

        <aside className="battle-column battle-column--right">
          <article className="battle-panel battle-alert-panel">
            <div><AlertTriangle size={24}/><span>SYSTEM ALERT</span></div>
            <strong>{activeMode.title}</strong>
            <p>{activeMode.subtitle.toUpperCase()}</p>
            <ul><li>DETECT</li><li>DEFEND</li><li>COUNTER</li><li>PRESERVE</li></ul>
          </article>

          <article className="battle-panel defense-panel">
            <div className="battle-panel-title"><ShieldCheck size={16}/><span>DEFENSE GRID</span><b>ACTIVE PROTECTION LAYERS</b></div>
            <div className="defense-orb"><Shield size={34}/><i/><i/><i/></div>
            <div className="defense-list">
              {(Object.keys(defenseLabels) as DefenseId[]).map(id => (
                <button key={id} className={defenses[id] ? 'active' : ''} onClick={() => toggleDefense(id)}>
                  <span>{defenseLabels[id]}</span><strong>{defenses[id] ? 'ACTIVE' : 'OFFLINE'}</strong>
                </button>
              ))}
            </div>
          </article>

          <article className="battle-panel counter-panel">
            <div className="battle-panel-title"><Route size={16}/><span>COUNTERMEASURE ROUTING</span><b>{autoResponse ? 'AUTO-RESPONSE // LIVE' : 'MANUAL CONTROL'}</b></div>
            {countermeasures.map(([label, pct]) => <div className="counter-row" key={label}><span>{label}</span><i><b style={{ width: `${autoResponse ? pct : Math.max(20, pct - 40)}%` }}/></i><strong>{autoResponse ? pct : Math.max(20, pct - 40)}%</strong></div>)}
            <div className="counter-actions"><button onClick={() => setAutoResponse(v => !v)}><Radio size={13}/>{autoResponse ? 'Disable Auto' : 'Enable Auto'}</button><button className="deploy" onClick={deployCountermeasures}><Flame size={13}/>Deploy Swarm</button></div>
          </article>

          <article className="battle-panel battle-log-panel">
            <div className="battle-panel-title"><Terminal size={16}/><span>ACTIVE BATTLE LOG</span><b>● LIVE</b></div>
            <div className="battle-log">{logs.map((log, index) => <div key={`${log}-${index}`}><span>{index === 0 ? 'NOW' : `-${index}s`}</span><p>{log}</p><b>+</b></div>)}</div>
            <div className="battle-command"><input value={command} onChange={e => setCommand(e.target.value)} onKeyDown={e => e.key === 'Enter' && executeCommand()} placeholder="Enter sovereign command..."/><button onClick={executeCommand}><Play size={13}/></button></div>
          </article>
        </aside>
      </div>

      <footer className="battle-bottom-strip">
        <div><ShieldAlert size={14}/><span>HEIMDALL</span><strong>{activeDefenses}/7 DEFENSE LAYERS</strong></div>
        <div><Eye size={14}/><span>ANYA GATE</span><strong>WATCHING</strong></div>
        <div><Network size={14}/><span>BIFROST</span><strong>ROUTES GOVERNED</strong></div>
        <div><RefreshCw size={14}/><span>OUROBOROS</span><strong>STATE RECURRENT</strong></div>
        <div><Gauge size={14}/><span>SCARCITY</span><strong>8GB BOUNDARY</strong></div>
      </footer>
    </section>
  );
};

export default BattleModeCommandCenter;
