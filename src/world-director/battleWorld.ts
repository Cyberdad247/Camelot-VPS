export type BattleChapterId =
  | 'overview'
  | 'threats'
  | 'telemetry'
  | 'defense'
  | 'brains'
  | 'ouroboros'
  | 'vfs'
  | 'counter'
  | 'command';

export interface WorldCameraPose {
  x: number;
  y: number;
  scale: number;
  rotateX: number;
  rotateY: number;
  brightness: number;
  saturation: number;
  blur: number;
}

export interface BattleWorldScene {
  id: BattleChapterId;
  index: string;
  label: string;
  scrollWeight: number;
  linger: number;
  accent: string;
  camera: WorldCameraPose;
}

/**
 * Camelot Continuous World Director timeline.
 *
 * Inspired by scroll-world's scene weighting / linger model, but implemented
 * natively for Camelot React state. No injected DOM, CTA layer, or vendor scrub
 * runtime is used here. Each scene remains a real interactive React interface.
 */
export const BATTLE_WORLD_SCENES: readonly BattleWorldScene[] = [
  {
    id: 'overview', index: '00', label: 'Battle State', scrollWeight: 1.25, linger: 0.30,
    accent: '#67e8f9',
    camera: { x: 0, y: 0, scale: 0.96, rotateX: 0, rotateY: 0, brightness: 0.82, saturation: 1.05, blur: 0 },
  },
  {
    id: 'threats', index: '01', label: 'Threat Matrix', scrollWeight: 1.65, linger: 0.48,
    accent: '#ff4d5f',
    camera: { x: 18, y: 1, scale: 1.08, rotateX: 1.5, rotateY: -7, brightness: 0.63, saturation: 1.18, blur: 0 },
  },
  {
    id: 'telemetry', index: '02', label: 'Telemetry', scrollWeight: 1.35, linger: 0.42,
    accent: '#38bdf8',
    camera: { x: -17, y: 4, scale: 1.16, rotateX: 1, rotateY: 6, brightness: 0.72, saturation: 1.10, blur: 0 },
  },
  {
    id: 'defense', index: '03', label: 'Defense Grid', scrollWeight: 1.70, linger: 0.55,
    accent: '#34d399',
    camera: { x: 13, y: 16, scale: 1.34, rotateX: -3, rotateY: -5, brightness: 0.88, saturation: 1.16, blur: 0 },
  },
  {
    id: 'brains', index: '04', label: 'Twin Brains', scrollWeight: 1.90, linger: 0.58,
    accent: '#c084fc',
    camera: { x: 0, y: 4, scale: 1.48, rotateX: 0, rotateY: 0, brightness: 0.92, saturation: 1.22, blur: 0 },
  },
  {
    id: 'ouroboros', index: '05', label: 'Ouroboros', scrollWeight: 2.00, linger: 0.60,
    accent: '#d4af37',
    camera: { x: 0, y: -3, scale: 1.78, rotateX: 5, rotateY: -7, brightness: 0.94, saturation: 1.18, blur: 0 },
  },
  {
    id: 'vfs', index: '06', label: 'VFS Defense', scrollWeight: 1.85, linger: 0.54,
    accent: '#2dd4bf',
    camera: { x: -10, y: -21, scale: 1.56, rotateX: 8, rotateY: 5, brightness: 0.78, saturation: 1.20, blur: 0 },
  },
  {
    id: 'counter', index: '07', label: 'Countermeasures', scrollWeight: 1.55, linger: 0.42,
    accent: '#f97316',
    camera: { x: 16, y: -8, scale: 1.22, rotateX: 2, rotateY: -8, brightness: 0.67, saturation: 1.28, blur: 0 },
  },
  {
    id: 'command', index: '08', label: 'Command Deck', scrollWeight: 2.20, linger: 0.65,
    accent: '#d4af37',
    camera: { x: 0, y: 2, scale: 0.88, rotateX: 0, rotateY: 0, brightness: 0.36, saturation: 0.86, blur: 1.2 },
  },
] as const;

export const BATTLE_WORLD_BY_ID = Object.fromEntries(
  BATTLE_WORLD_SCENES.map(scene => [scene.id, scene]),
) as Record<BattleChapterId, BattleWorldScene>;
