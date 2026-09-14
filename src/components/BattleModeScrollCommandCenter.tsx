import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, Brain, Castle, ChevronDown, Crosshair, Database,
  Eye, Flame, Gauge, LockKeyhole, Network, Power, Radio, Route, Shield,
  ShieldCheck, Swords, Target, Terminal, Zap,
} from 'lucide-react';
import './battle-mode-scroll-command-center.css';

type BattleState = 'nominal' | 'battle' | 'lockdown';
type ThreatType = 'DDoS' | 'Prompt Injection' | 'Data Exfiltration' | 'AI Adversary' | 'Reconnaissance';
type DefenseId = 'memcastle' | 'context' | 'firewall' | 'inference' | 'sandbox' | 'vfs' | 'physical';
type ChapterId = 'overview' | 'threats' | 'telemetry' | 'defense' | 'brains' | 'ouroboros' | 'vfs' | 'counter' | 'command';

interface ThreatRow {
  id: number;
  time: string;
  source: string;
  vector: ThreatType;
  target: string;
  status: 'BLOCKED' | 'NEUTRALIZED' | 'CONTAINED' | 'DEFLECTED' | 'TRACED';
}

const threats: ThreatRow[] = [
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

const chapters: { id: ChapterId; index: string; label: string }[] = [
  { id: 'overview', index: '00', label: 'Battle State' },
  { id: 'threats', index: '01', label: 'Threat Matrix' },
  { id: 'telemetry', index: '02', label: 'Telemetry' },
  { id: 'defense', index: '03', label: 'Defense Grid' },
  { id: 'brains', index: '04', label: 'Twin Brains' },
  { id: 'ouroboros', index: '05', label: 'Ouroboros' },
  { id: 'vfs', index: '06', label: 'VFS Defense' },
  { id: 'counter', index: '07', label: 'Countermeasures' },
  { id: 'command', index: '08', label: 'Command Deck' },
];

const countermeasures = [
  ['Threat Isolation', 99], ['Traffic Redirection', 97], ['Prompt Sanitization', 100],
  ['Adversary Tracing', 96], ['Deception Honeypots', 93], ['Signature Updates', 100],
  ['Autonomous Response', 98],
] as const;

export const BattleModeScrollCommandCenter: React.FC = () => {
  const scrollerRef = useRef<HTMLElement>(null);
  const [activeChapter, setActiveChapter] = useState<ChapterId>('overview');
  const [progress, setProgress] = useState(0);
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
    'SHIELD ABSORBED MASS ATTACK WAVE', 'NODE BREACH ATTEMPT CONTAINED',
    'MALICIOUS PROMPT QUARANTINED', 'THREAT ACTOR TRACED (TIER-1)',
    'COUNTERMEASURE SWARM DEPLOYED', 'SYSTEMS STABLE',
  ]);
  const [command, setCommand] = useState('');
  const [pulse, setPulse] = useState(0);

  const activeDefenses = Object.values(defenses).filter(Boolean).length;
  const readiness = Math.round((activeDefenses / 7) * 100);
  const filteredThreats = useMemo(() => threats.filter(row => row.vector === selectedThreat), [selectedThreat]);

  useEffect(() => {
    const root = scrollerRef.current;
    if (!root) return;
    const sections: HTMLElement[] = [...root.querySelectorAll<HTMLElement>('[data-battle-chapter]')];
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActiveChapter((visible.target as HTMLElement).dataset.battleChapter as ChapterId);
    }, { root, threshold: [0.35, 0.55, 0.75] });
    sections.forEach(section => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  const onScroll = () => {
    const root = scrollerRef.current;
    if (!root) return;
    const max = root.scrollHeight - root.clientHeight;
    setProgress(max > 0 ? root.scrollTop / max : 0);
  };

  const appendLog = (entry: string) => setLogs(prev => [`${new Date().toLocaleTimeString([], { hour12: false })}  ${entry}`, ...prev].slice(0, 10));
  const go = (id: ChapterId) => document.getElementById(`battle-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const setBattleState = (next: BattleState) => {
    setMode(next);
    if (next === 'nominal') { setThreatCount(18); setResponseLatency(22); }
    if (next === 'battle') { setThreatCount(v => Math.max(v, 247)); setResponseLatency(12); }
    if (next === 'lockdown') {
      setThreatCount(v => Math.max(v, 247)); setShieldIntegrity(100); setResponseLatency(8); setAutoResponse(true);
      setDefenses({ memcastle: true, context: true, firewall: true, inference: true, sandbox: true, vfs: true, physical: true });
    }
    setPulse(v => v + 1);
    appendLog(`${next.toUpperCase()} STATE ENGAGED`);
  };

  const toggleDefense = (id: DefenseId) => {
    setDefenses(prev => ({ ...prev, [id]: !prev[id] }));
    appendLog(`${defenseLabels[id].toUpperCase()} ${defenses[id] ? 'DISARMED' : 'ARMED'}`);
  };

  const deployCountermeasures = () => {
    setThreatCount(v => Math.max(0, v - 64));
    setShieldIntegrity(v => Math.min(100, v + 0.2));
    setResponseLatency(v => Math.max(6, v - 2));
    setPulse(v => v + 1);
    appendLog('COUNTERMEASURE SWARM DEPLOYED // 1,284 ROUTES/MIN');
  };

  const executeCommand = () => {
    if (!command.trim()) return;
    appendLog(`COMMAND EXECUTED // ${command.trim().toUpperCase()}`);
    setCommand('');
    setPulse(v => v + 1);
  };

  return (
    <section ref={scrollerRef} onScroll={onScroll} id="battle-mode-scroll-command-center" className={`battle-scroll-shell mode-${mode} chapter-${activeChapter}`}>
      <div className="battle-scroll-progress"><i style={{ width: `${progress * 100}%` }} /></div>

      <header className="battle-scroll-topbar">
        <div className="battle-scroll-brand"><span>♜</span><div><strong>Camelot-OS World Tree</strong><small>THE SOVEREIGN CONTEXT ENGINE</small></div></div>
        <div className="battle-scroll-status"><small>SYSTEM STATUS</small><strong>{mode === 'battle' ? 'BATTLE MODE' : mode.toUpperCase()}</strong></div>
        <div className="battle-scroll-actions">
          <button onClick={() => setBattleState('nominal')}><Power size={13}/>Nominal</button>
          <button className="danger" onClick={() => setBattleState('battle')}><Swords size={13}/>Battle</button>
          <button className="amber" onClick={() => setBattleState('lockdown')}><LockKeyhole size={13}/>Lockdown</button>
        </div>
      </header>

      <nav className="battle-scroll-rail" aria-label="Battle Mode sections">
        {chapters.map(chapter => <button key={chapter.id} className={activeChapter === chapter.id ? 'active' : ''} onClick={() => go(chapter.id)}><b>{chapter.index}</b><span>{chapter.label}</span></button>)}
      </nav>

      <div className="battle-stage" aria-hidden="true">
        <div className="battle-stage-aura" />
        <img key={pulse} className="battle-stage-tree battle-stage-tree--pulse" src="/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png" alt="" />
        <div className="battle-stage-shield" />
        <div className="battle-stage-ring ring-one"/><div className="battle-stage-ring ring-two"/><div className="battle-stage-ring ring-three"/>
        <div className="battle-stage-beams">{Array.from({ length: 8 }).map((_, i) => <i key={i} style={{ '--beam-i': i } as React.CSSProperties}/>)}</div>
        <div className="battle-stage-label stage-memcastle"><Castle size={14}/> REDIS MEMCASTLE</div>
        <div className="battle-stage-label stage-open"><Brain size={14}/> OPEN-NOTEBOOK</div>
        <div className="battle-stage-label stage-notebook"><Brain size={14}/> NOTEBOOKLM</div>
        <div className="battle-stage-label stage-ouro"><Zap size={14}/> OUROBOROS SSM</div>
        <div className="battle-stage-label stage-vfs"><Database size={14}/> VFS DEFENSE FABRIC</div>
      </div>

      <div className="battle-scroll-content">
        <section id="battle-overview" data-battle-chapter="overview" className="battle-chapter battle-chapter--hero">
          <div className="battle-chapter-copy centered">
            <span className="kicker">00 / SOVEREIGN COMBAT STATE</span>
            <h1>THE WORLD TREE<br/><em>GOES TO WAR.</em></h1>
            <p>One continuous tactical journey. Scroll through detection, cognition, defense, recurrence, filesystem protection, countermeasures, and final command.</p>
            <div className="hero-metrics"><div><b>{threatCount}</b><span>ACTIVE THREATS</span></div><div><b>{readiness}%</b><span>DEFENSE READY</span></div><div><b>{shieldIntegrity.toFixed(1)}%</b><span>SHIELD</span></div><div><b>{responseLatency}ms</b><span>LATENCY</span></div></div>
            <button className="descend" onClick={() => go('threats')}>ENTER THREAT SPACE <ChevronDown size={16}/></button>
          </div>
        </section>

        <section id="battle-threats" data-battle-chapter="threats" className="battle-chapter align-left">
          <div className="battle-interface threat-interface">
            <div className="interface-heading"><Target/><div><span>01 / THREAT MATRIX</span><h2>See the attack surface.</h2></div></div>
            <div className="threat-globe"><div className="threat-grid"/>{[14,29,43,58,73,88].map((left,i)=><i key={left} style={{left:`${left}%`,top:`${22+(i%3)*25}%`}}/>)}<svg viewBox="0 0 100 50"><path d="M5,37 C25,2 43,8 59,26 S82,35 96,8"/><path d="M4,12 C29,45 56,34 80,5"/></svg></div>
            <div className="threat-selector">{(['DDoS','Prompt Injection','Data Exfiltration','AI Adversary','Reconnaissance'] as ThreatType[]).map(type=><button key={type} className={selectedThreat===type?'active':''} onClick={()=>{setSelectedThreat(type);appendLog(`THREAT FILTER // ${type.toUpperCase()}`)}}>{type}</button>)}</div>
            <div className="threat-table"><div className="tr th"><span>TIME</span><span>SOURCE</span><span>VECTOR</span><span>TARGET</span><span>STATUS</span></div>{(filteredThreats.length?filteredThreats:threats).map(row=><button key={row.id} className="tr" onClick={()=>appendLog(`TARGET LOCK // ${row.source} ${row.vector}`)}><span>{row.time}</span><span>{row.source}</span><span>{row.vector}</span><span>{row.target}</span><b>{row.status}</b></button>)}</div>
          </div>
        </section>

        <section id="battle-telemetry" data-battle-chapter="telemetry" className="battle-chapter align-right">
          <div className="battle-interface telemetry-interface">
            <div className="interface-heading"><Activity/><div><span>02 / TACTICAL TELEMETRY</span><h2>Measure the pressure.</h2></div></div>
            <div className="telemetry-gauges">{[[`${readiness}%`,'DEFENSE READINESS'],[`${threatCount}K`,'THREATS / MIN'],[`${shieldIntegrity.toFixed(1)}%`,'SHIELD INTEGRITY'],[`${responseLatency}ms`,'RESPONSE LATENCY']].map(([v,l])=><div className="telemetry-gauge" key={l}><b>{v}</b><span>{l}</span><i/></div>)}</div>
            <div className="telemetry-chart"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div>
            <div className="telemetry-caption"><Gauge size={15}/> SYSTEM PERFORMANCE UNDER ACTIVE RESPONSE LOAD</div>
          </div>
        </section>

        <section id="battle-defense" data-battle-chapter="defense" className="battle-chapter align-left">
          <div className="battle-interface defense-interface">
            <div className="interface-heading"><ShieldCheck/><div><span>03 / DEFENSE GRID</span><h2>Arm every layer.</h2></div></div>
            <div className="defense-core"><Shield size={56}/><i/><i/><i/></div>
            <div className="defense-stack">{(Object.keys(defenseLabels) as DefenseId[]).map((id,index)=><button key={id} className={defenses[id]?'active':''} onClick={()=>toggleDefense(id)}><span><b>L{7-index}</b>{defenseLabels[id]}</span><strong>{defenses[id]?'ACTIVE':'OFFLINE'}</strong></button>)}</div>
          </div>
        </section>

        <section id="battle-brains" data-battle-chapter="brains" className="battle-chapter battle-chapter--wide">
          <div className="battle-interface twin-interface">
            <div className="interface-heading centered-heading"><Brain/><div><span>04 / DYNAMIC TWIN BRAINS</span><h2>Reason on two fronts.</h2></div></div>
            <div className="twin-grid"><article><Brain size={58}/><span>OPEN-NOTEBOOK</span><h3>COMBAT ANALYSIS</h3><p>Threat reasoning · scenario simulation · countermeasure AI · operational intelligence</p><div className="brain-pulse"/></article><div className="synapse-bridge"><i/><i/><i/></div><article><Brain size={58}/><span>NOTEBOOKLM</span><h3>STRATEGIC SYNCHRONIZER</h3><p>Knowledge defense · context validation · adversary modeling · response orchestration</p><div className="brain-pulse"/></article></div>
          </div>
        </section>

        <section id="battle-ouroboros" data-battle-chapter="ouroboros" className="battle-chapter battle-chapter--center">
          <div className="battle-interface ouro-interface">
            <span className="kicker">05 / O(1) STATE LOOP</span><h2>Detect. Reason.<br/>Defend. Evolve.</h2><div className="ouro-ring"><span>Wᵢⱼ ∈ {'{-1,0,1}'}</span><i/></div><p>Ouroboros retains the tactical state without losing the thread. The loop becomes the nervous system of Battle Mode.</p>
          </div>
        </section>

        <section id="battle-vfs" data-battle-chapter="vfs" className="battle-chapter align-right">
          <div className="battle-interface vfs-interface">
            <div className="interface-heading"><Database/><div><span>06 / VFS // OPEN VIKING PROTOCOL</span><h2>Move defense through the roots.</h2></div></div>
            <div className="vfs-lanes">{['/vfs/mempalace/*','/vfs/refractions/*','/.agent/armor','/vfs/receipts/*'].map((path,index)=><div key={path}><span>⚔</span><i/><b>{path}</b><small>{index%2?'REHYDRATION / SANDBOX':'DEFENSE PACKETS / ZERO-COPY'}</small></div>)}</div>
            <div className="vfs-stats"><span>IPC <b>0.23ms</b></span><span>THROUGHPUT <b>2.4GB/s</b></span><span>SYNC <b>OPTIMAL</b></span></div>
          </div>
        </section>

        <section id="battle-counter" data-battle-chapter="counter" className="battle-chapter align-left">
          <div className="battle-interface counter-interface">
            <div className="interface-heading"><Route/><div><span>07 / COUNTERMEASURE ROUTING</span><h2>Turn defense into motion.</h2></div></div>
            <div className="counter-list">{countermeasures.map(([label,pct])=><div key={label}><span>{label}</span><i><b style={{width:`${autoResponse?pct:Math.max(20,pct-40)}%`}}/></i><strong>{autoResponse?pct:Math.max(20,pct-40)}%</strong></div>)}</div>
            <div className="counter-buttons"><button onClick={()=>setAutoResponse(v=>!v)}><Radio size={14}/>{autoResponse?'DISABLE AUTO':'ENABLE AUTO'}</button><button className="deploy" onClick={deployCountermeasures}><Flame size={14}/>DEPLOY SWARM</button></div>
          </div>
        </section>

        <section id="battle-command" data-battle-chapter="command" className="battle-chapter battle-chapter--command">
          <div className="battle-interface command-interface">
            <div className="interface-heading centered-heading"><Terminal/><div><span>08 / ACTIVE BATTLE LOG</span><h2>Command the kingdom.</h2></div></div>
            <div className="command-log">{logs.map((log,index)=><div key={`${log}-${index}`}><span>{index===0?'NOW':`-${index}s`}</span><p>{log}</p><b>+</b></div>)}</div>
            <div className="command-line"><span>❯</span><input value={command} onChange={e=>setCommand(e.target.value)} onKeyDown={e=>e.key==='Enter'&&executeCommand()} placeholder="Enter sovereign battle command..."/><button onClick={executeCommand}>EXECUTE</button></div>
            <div className="final-status"><div><Eye size={16}/>HEIMDALL <b>{activeDefenses}/7 LAYERS</b></div><div><Network size={16}/>BIFROST <b>GOVERNED</b></div><div><Zap size={16}/>OUROBOROS <b>RECURRENT</b></div><div><Shield size={16}/>WORLD TREE <b>{mode.toUpperCase()}</b></div></div>
          </div>
        </section>
      </div>
    </section>
  );
};

export default BattleModeScrollCommandCenter;
