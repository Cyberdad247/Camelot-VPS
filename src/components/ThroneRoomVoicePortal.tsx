import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ThroneRoomKnightCouncil, ThroneKnight } from './ThroneRoomKnightCouncil';

const COUNCIL: ThroneKnight[] = [
  { id:'lady_mnemosyne', name:'Lady Mnemosyne', title:'The Memory Keeper', engine:'Redis MemCastle & Vector Nodes', sge:'99.8%', vram:'320 MB', quote:'All things remembered. All things connected. Memory is a bridge, not a vault.', directives:['Recall','Synthesize','Contextualize','Protect'], color:'#38BDF8', icon:'💎' },
  { id:'sir_codex', name:'Sir Codex', title:'The Compiler', engine:'Codex / WASM32 Zero-Copy', sge:'99.4%', vram:'280 MB', quote:'Deterministic logic without allocation is the purest form of digital prayer.', directives:['Compile','Optimize','Verify','Enforce Bounds'], color:'#D4AF37', icon:'⚡' },
  { id:'sir_loren', name:'Sir Loren', title:'The Researcher', engine:'Deep Research Agent // Multi-Corpus', sge:'98.9%', vram:'410 MB', quote:'Truth hides in the high-dimensional manifolds of cross-repository synthesis.', directives:['Index','Correlate','Synthesize','Filter'], color:'#A855F7', icon:'📜' },
  { id:'sir_prompt', name:'Sir Prompt', title:'The Orchestrator', engine:'DAG Dispatcher & Task Sequencer', sge:'99.7%', vram:'190 MB', quote:'Intention declared becomes topological order materialized.', directives:['Sequence','Dispatch','Observe','Converge'], color:'#F59E0B', icon:'🎼' },
  { id:'sir_aegis', name:'Sir Aegis', title:'The Guardian', engine:'AgentArmor PDG Sentry & Zero-Trust', sge:'100%', vram:'150 MB', quote:'None shall compromise the sovereign boundaries of the kingdom.', directives:['Shield','Attest','Isolate','Neutralize'], color:'#10B981', icon:'🛡️' },
  { id:'sir_calculus', name:'Sir Calculus', title:'The Analyst', engine:'Z3 SMT Invariant Theorem Prover', sge:'99.9%', vram:'220 MB', quote:'If an invariant cannot be proved mathematically, it does not exist.', directives:['Prove','Constrain','Formulate','Certify'], color:'#EC4899', icon:'📐' },
  { id:'sir_lumen', name:'Sir Lumen', title:'The Visionary', engine:'Kinetic 3D Frame Scroll Matrix', sge:'99.1%', vram:'360 MB', quote:'Form and light are the visual syntax of Sovereign Intelligence.', directives:['Illuminate','Project','Refract','Harmonize'], color:'#06B6D4', icon:'✨' },
  { id:'sir_pragmata', name:'Sir Pragmata', title:'The Executor', engine:'Termux ARM64 / Bare-Metal Actuator', sge:'99.5%', vram:'180 MB', quote:'Abstract models without bare-metal execution are mere ghosts.', directives:['Actuate','Bind','Deploy','Monitor'], color:'#84CC16', icon:'⚙️' },
  { id:'sir_harmonia', name:'Sir Harmonia', title:'The Alignment', engine:'Constitutional Invariant Verifier', sge:'99.6%', vram:'210 MB', quote:'Safety and power are not rivals, but twin pillars of the realm.', directives:['Align','Balance','Sanitize','Validate'], color:'#6366F1', icon:'⚖️' },
  { id:'sir_nexus', name:'Sir Nexus', title:'The Connector', engine:'VFS Data Bus & Memory Slab Ring', sge:'99.8%', vram:'300 MB', quote:'Latency is friction; zero-copy slabs are frictionless eternity.', directives:['Bridge','Route','Buffer','Synchronize'], color:'#14B8A6', icon:'🌐' },
  { id:'sir_umbra', name:'Sir Umbra', title:'The Shadow CPU', engine:'Puter Shadow Castle / camelot-shadowd', sge:'HITL', vram:'512 MB cap', quote:'The shadow may work beyond the torchlight, but every consequential step remains visible to the Crown.', directives:['Summon','Isolate','Draft','Request Approval'], color:'#8B5CF6', icon:'◐' },
];

export const ThroneRoomVoicePortal: React.FC = () => {
  const [host, setHost] = useState<HTMLElement | null>(null);
  const [selected, setSelected] = useState<ThroneKnight>(COUNCIL[0]);
  const [message, setMessage] = useState('');
  const [response, setResponse] = useState<string | null>(null);

  useEffect(() => {
    let observer: MutationObserver | null = null;
    const bind = () => {
      const throne = document.getElementById('stratum-throne-room');
      if (!throne) return false;
      let mount = throne.querySelector<HTMLElement>('#throne-room-voice-council-mount');
      if (!mount) {
        mount = document.createElement('div');
        mount.id = 'throne-room-voice-council-mount';
        mount.className = 'mt-8 lg:col-span-12';
        const roomBody = throne.querySelector<HTMLElement>('.grid.grid-cols-1.lg\\:grid-cols-12');
        (roomBody ?? throne).appendChild(mount);
      }
      setHost(mount);
      return true;
    };
    if (!bind()) {
      observer = new MutationObserver(() => {
        if (bind()) observer?.disconnect();
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
    return () => observer?.disconnect();
  }, []);

  const send = (text = message) => {
    const clean = text.trim();
    if (!clean) return;
    if (selected.id === 'sir_umbra') {
      setResponse(
        `◐ UMBRA: Shadow mission intent received.\n` +
        `Mission: “${clean}”\n` +
        `A bounded Shadow Subspace workspace will open through Bifrost. R4–R6 effects remain frozen until human approval.`
      );
    } else {
      setResponse(
        `⚜ HEIMDALL: Intent accepted for ${selected.name}.\n` +
        `${selected.name}: “${selected.quote}”\n` +
        `Received: “${clean}”\n` +
        `Routing note: conversational UI is active; remote synthesized Knight reasoning remains behind the governed Multivoice/Bifrost boundary.`
      );
    }
    setMessage('');
    window.dispatchEvent(new CustomEvent('camelot:throne-message', { detail: { knightId: selected.id, message: clean } }));
  };

  if (!host) return null;
  return createPortal(
    <ThroneRoomKnightCouncil
      knights={COUNCIL}
      selectedKnight={selected}
      onSelectKnight={setSelected}
      decree={message}
      onDecreeChange={setMessage}
      response={response}
      onSend={send}
      soundEnabled
    />,
    host,
  );
};

export default ThroneRoomVoicePortal;
