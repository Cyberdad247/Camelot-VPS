import type { BattleChapterId } from './battleWorld';

export interface CinematicSceneMedia {
  id: BattleChapterId;
  poster: string;
  posterMobile?: string;
  clip?: string;
  clipMobile?: string;
  /** Exact rendered first frame of this scene dive. */
  startFrameId: string;
  /** Exact rendered final frame of this scene dive. */
  endFrameId: string;
}

export interface CinematicConnectorMedia {
  from: BattleChapterId;
  to: BattleChapterId;
  clip?: string;
  clipMobile?: string;
  /** Must equal the actual rendered terminal frame ID of the source dive. */
  startFrameId: string;
  /** Must equal the actual rendered first frame ID of the destination dive. */
  endFrameId: string;
}

const WORLD_TREE_POSTER = '/1787629062694-01a036fd-ed60-74c1-b1c7-5e5177f9ba69.png';

/**
 * Cinematic asset contract for the Continuous World Director.
 *
 * Video URLs remain optional until final renders are committed. The runtime therefore
 * works today with the poster/camera director and automatically promotes to video
 * scrubbing when clips are present. This keeps live React controls independent from
 * rendered media and preserves the frame-identical seam rule for future connectors.
 */
export const BATTLE_CINEMATIC_SCENES: readonly CinematicSceneMedia[] = [
  { id: 'overview', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/00-overview.mp4', clipMobile: '/cinematic/battle/mobile/00-overview.mp4', startFrameId: 'battle-00-start', endFrameId: 'battle-00-end' },
  { id: 'threats', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/01-threats.mp4', clipMobile: '/cinematic/battle/mobile/01-threats.mp4', startFrameId: 'battle-01-start', endFrameId: 'battle-01-end' },
  { id: 'telemetry', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/02-telemetry.mp4', clipMobile: '/cinematic/battle/mobile/02-telemetry.mp4', startFrameId: 'battle-02-start', endFrameId: 'battle-02-end' },
  { id: 'defense', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/03-defense.mp4', clipMobile: '/cinematic/battle/mobile/03-defense.mp4', startFrameId: 'battle-03-start', endFrameId: 'battle-03-end' },
  { id: 'brains', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/04-brains.mp4', clipMobile: '/cinematic/battle/mobile/04-brains.mp4', startFrameId: 'battle-04-start', endFrameId: 'battle-04-end' },
  { id: 'ouroboros', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/05-ouroboros.mp4', clipMobile: '/cinematic/battle/mobile/05-ouroboros.mp4', startFrameId: 'battle-05-start', endFrameId: 'battle-05-end' },
  { id: 'vfs', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/06-vfs.mp4', clipMobile: '/cinematic/battle/mobile/06-vfs.mp4', startFrameId: 'battle-06-start', endFrameId: 'battle-06-end' },
  { id: 'counter', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/07-counter.mp4', clipMobile: '/cinematic/battle/mobile/07-counter.mp4', startFrameId: 'battle-07-start', endFrameId: 'battle-07-end' },
  { id: 'command', poster: WORLD_TREE_POSTER, clip: '/cinematic/battle/08-command.mp4', clipMobile: '/cinematic/battle/mobile/08-command.mp4', startFrameId: 'battle-08-start', endFrameId: 'battle-08-end' },
] as const;

export const BATTLE_CINEMATIC_CONNECTORS: readonly CinematicConnectorMedia[] = [
  { from: 'overview', to: 'threats', clip: '/cinematic/battle/connectors/00-01.mp4', clipMobile: '/cinematic/battle/mobile/connectors/00-01.mp4', startFrameId: 'battle-00-end', endFrameId: 'battle-01-start' },
  { from: 'threats', to: 'telemetry', clip: '/cinematic/battle/connectors/01-02.mp4', clipMobile: '/cinematic/battle/mobile/connectors/01-02.mp4', startFrameId: 'battle-01-end', endFrameId: 'battle-02-start' },
  { from: 'telemetry', to: 'defense', clip: '/cinematic/battle/connectors/02-03.mp4', clipMobile: '/cinematic/battle/mobile/connectors/02-03.mp4', startFrameId: 'battle-02-end', endFrameId: 'battle-03-start' },
  { from: 'defense', to: 'brains', clip: '/cinematic/battle/connectors/03-04.mp4', clipMobile: '/cinematic/battle/mobile/connectors/03-04.mp4', startFrameId: 'battle-03-end', endFrameId: 'battle-04-start' },
  { from: 'brains', to: 'ouroboros', clip: '/cinematic/battle/connectors/04-05.mp4', clipMobile: '/cinematic/battle/mobile/connectors/04-05.mp4', startFrameId: 'battle-04-end', endFrameId: 'battle-05-start' },
  { from: 'ouroboros', to: 'vfs', clip: '/cinematic/battle/connectors/05-06.mp4', clipMobile: '/cinematic/battle/mobile/connectors/05-06.mp4', startFrameId: 'battle-05-end', endFrameId: 'battle-06-start' },
  { from: 'vfs', to: 'counter', clip: '/cinematic/battle/connectors/06-07.mp4', clipMobile: '/cinematic/battle/mobile/connectors/06-07.mp4', startFrameId: 'battle-06-end', endFrameId: 'battle-07-start' },
  { from: 'counter', to: 'command', clip: '/cinematic/battle/connectors/07-08.mp4', clipMobile: '/cinematic/battle/mobile/connectors/07-08.mp4', startFrameId: 'battle-07-end', endFrameId: 'battle-08-start' },
] as const;

export const BATTLE_MEDIA_BY_ID = Object.fromEntries(
  BATTLE_CINEMATIC_SCENES.map(scene => [scene.id, scene]),
) as Record<BattleChapterId, CinematicSceneMedia>;

/**
 * Static manifest validation. Useful in tests/build tooling before enabling video media.
 * A connector is invalid if its declared seam IDs do not exactly match neighboring
 * rendered scene frame IDs.
 */
export function validateBattleCinematicSeams(): string[] {
  const failures: string[] = [];
  for (const connector of BATTLE_CINEMATIC_CONNECTORS) {
    const source = BATTLE_MEDIA_BY_ID[connector.from];
    const destination = BATTLE_MEDIA_BY_ID[connector.to];
    if (connector.startFrameId !== source.endFrameId) {
      failures.push(`${connector.from}->${connector.to}: connector start ${connector.startFrameId} != source end ${source.endFrameId}`);
    }
    if (connector.endFrameId !== destination.startFrameId) {
      failures.push(`${connector.from}->${connector.to}: connector end ${connector.endFrameId} != destination start ${destination.startFrameId}`);
    }
  }
  return failures;
}
