import type { BattleChapterId } from './battleWorld';

export interface BattleComprehensionScene {
  id: BattleChapterId;
  title: string;
  purpose: string;
  interaction: string;
  outcome: string;
  primaryVerb: string;
}

export const BATTLE_COMPREHENSION: Record<BattleChapterId, BattleComprehensionScene> = {
  overview: {
    id: 'overview',
    title: 'Battle State',
    purpose: 'Choose the operating posture and read the overall health of the World Tree.',
    interaction: 'Switch between Nominal, Battle, and Lockdown. Read threats, readiness, shield integrity, and latency.',
    outcome: 'Sets the global tactical posture before you descend into the system.',
    primaryVerb: 'Enter threat space',
  },
  threats: {
    id: 'threats',
    title: 'Threat Matrix',
    purpose: 'Identify what is attacking Camelot and where the pressure is landing.',
    interaction: 'Select a threat family, inspect the attack table, and lock onto individual vectors.',
    outcome: 'Narrows the operator focus before measuring system pressure.',
    primaryVerb: 'Review telemetry',
  },
  telemetry: {
    id: 'telemetry',
    title: 'Tactical Telemetry',
    purpose: 'Translate active threats into system pressure you can reason about quickly.',
    interaction: 'Read defense readiness, threats per minute, shield integrity, and response latency.',
    outcome: 'Shows whether the defense stack is coping or needs intervention.',
    primaryVerb: 'Inspect defenses',
  },
  defense: {
    id: 'defense',
    title: 'Defense Grid',
    purpose: 'Control the seven protection layers guarding the World Tree.',
    interaction: 'Arm or disarm individual layers and observe readiness change immediately.',
    outcome: 'Defines the protection envelope used by the rest of Battle Mode.',
    primaryVerb: 'Open Twin Brains',
  },
  brains: {
    id: 'brains',
    title: 'Dynamic Twin Brains',
    purpose: 'Understand how Open-Notebook and NotebookLM divide combat reasoning and strategic synchronization.',
    interaction: 'This scene is primarily explanatory: compare each brain role and the synchronization bridge between them.',
    outcome: 'Explains where tactical reasoning and knowledge validation converge.',
    primaryVerb: 'Follow state loop',
  },
  ouroboros: {
    id: 'ouroboros',
    title: 'Ouroboros SSM',
    purpose: 'See how Battle Mode retains and evolves tactical state across the encounter.',
    interaction: 'Read the recurrent state model and its detect → reason → defend → evolve loop.',
    outcome: 'Connects cognition to persistent tactical memory without losing the thread.',
    primaryVerb: 'Descend to VFS',
  },
  vfs: {
    id: 'vfs',
    title: 'VFS Defense Fabric',
    purpose: 'Follow defense packets through Camelot’s filesystem and memory corridors.',
    interaction: 'Inspect protected paths, IPC latency, throughput, and synchronization status.',
    outcome: 'Shows how decisions become low-level defensive movement through the roots.',
    primaryVerb: 'Route countermeasures',
  },
  counter: {
    id: 'counter',
    title: 'Countermeasure Routing',
    purpose: 'Turn defensive intelligence into active response.',
    interaction: 'Toggle autonomous response and deploy the countermeasure swarm.',
    outcome: 'Reduces active pressure and improves shield / latency state in real time.',
    primaryVerb: 'Open command deck',
  },
  command: {
    id: 'command',
    title: 'Command Deck',
    purpose: 'Review the battle timeline and issue direct sovereign commands.',
    interaction: 'Read the live event ledger, type a command, then execute it from the terminal.',
    outcome: 'Closes the loop between observation, decision, action, and audit.',
    primaryVerb: 'Return to battle state',
  },
};

export const BATTLE_COMPREHENSION_ORDER: BattleChapterId[] = [
  'overview', 'threats', 'telemetry', 'defense', 'brains', 'ouroboros', 'vfs', 'counter', 'command',
];
