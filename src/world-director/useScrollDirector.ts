import { RefObject, useCallback, useEffect, useMemo, useState } from 'react';
import type { BattleChapterId, BattleWorldScene, WorldCameraPose } from './battleWorld';

export type WorldQualityTier = 'high' | 'medium' | 'scarcity';

export interface WorldDirectorSnapshot {
  activeScene: BattleWorldScene;
  activeIndex: number;
  globalProgress: number;
  localProgress: number;
  camera: WorldCameraPose;
  qualityTier: WorldQualityTier;
  reducedMotion: boolean;
}

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const smooth = (value: number) => {
  const x = clamp(value);
  return x * x * (3 - 2 * x);
};

// Same useful shape as scroll-world's dwell mapping, independently implemented.
const lingerEase = (value: number, linger: number) => {
  const x = clamp(value);
  const l = clamp(linger);
  const c = x - 0.5;
  return (1 - l) * x + l * (4 * c * c * c + 0.5);
};

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

const mixCamera = (a: WorldCameraPose, b: WorldCameraPose, t: number): WorldCameraPose => ({
  x: lerp(a.x, b.x, t),
  y: lerp(a.y, b.y, t),
  scale: lerp(a.scale, b.scale, t),
  rotateX: lerp(a.rotateX, b.rotateX, t),
  rotateY: lerp(a.rotateY, b.rotateY, t),
  brightness: lerp(a.brightness, b.brightness, t),
  saturation: lerp(a.saturation, b.saturation, t),
  blur: lerp(a.blur, b.blur, t),
});

function detectQualityTier(): WorldQualityTier {
  if (typeof window === 'undefined') return 'medium';
  const navigatorWithMemory = navigator as Navigator & { deviceMemory?: number };
  const memory = navigatorWithMemory.deviceMemory ?? 8;
  const mobile = window.matchMedia('(hover: none) and (pointer: coarse)').matches || window.innerWidth <= 860;
  if (mobile || memory <= 4) return 'scarcity';
  if (memory >= 12 && window.innerWidth >= 1200) return 'high';
  return 'medium';
}

export function useScrollDirector(
  rootRef: RefObject<HTMLElement | null>,
  scenes: readonly BattleWorldScene[],
): WorldDirectorSnapshot & {
  scrollToScene: (id: BattleChapterId) => void;
  sceneStyle: (id: BattleChapterId) => React.CSSProperties;
} {
  const fallback = scenes[0];
  const [snapshot, setSnapshot] = useState<WorldDirectorSnapshot>({
    activeScene: fallback,
    activeIndex: 0,
    globalProgress: 0,
    localProgress: 0,
    camera: fallback.camera,
    qualityTier: 'medium',
    reducedMotion: false,
  });

  const sceneMap = useMemo(() => new Map(scenes.map((scene, index) => [scene.id, { scene, index }])), [scenes]);

  const read = useCallback(() => {
    const root = rootRef.current;
    if (!root || scenes.length === 0) return;

    const maxScroll = Math.max(1, root.scrollHeight - root.clientHeight);
    const globalProgress = clamp(root.scrollTop / maxScroll);
    const focusY = root.scrollTop + root.clientHeight * 0.5;

    const elements = scenes
      .map(scene => root.querySelector<HTMLElement>(`[data-world-scene="${scene.id}"]`))
      .filter((value): value is HTMLElement => Boolean(value));

    if (!elements.length) return;

    let activeIndex = elements.length - 1;
    for (let index = 0; index < elements.length; index += 1) {
      const el = elements[index];
      if (focusY < el.offsetTop + el.offsetHeight) {
        activeIndex = index;
        break;
      }
    }

    const scene = scenes[activeIndex] ?? fallback;
    const el = elements[activeIndex];
    const rawLocal = clamp((focusY - el.offsetTop) / Math.max(1, el.offsetHeight));
    const localProgress = lingerEase(rawLocal, scene.linger);

    const nextScene = scenes[Math.min(activeIndex + 1, scenes.length - 1)] ?? scene;
    const transitionStart = 0.72;
    const transitionT = smooth((rawLocal - transitionStart) / (1 - transitionStart));
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const camera = reducedMotion ? scene.camera : mixCamera(scene.camera, nextScene.camera, transitionT);

    setSnapshot({
      activeScene: scene,
      activeIndex,
      globalProgress,
      localProgress,
      camera,
      qualityTier: detectQualityTier(),
      reducedMotion,
    });
  }, [fallback, rootRef, scenes]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    let raf = 0;
    const scheduleRead = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(() => {
        raf = 0;
        read();
      });
    };

    read();
    root.addEventListener('scroll', scheduleRead, { passive: true });
    window.addEventListener('resize', scheduleRead);
    window.addEventListener('orientationchange', scheduleRead);

    const resizeObserver = new ResizeObserver(scheduleRead);
    resizeObserver.observe(root);

    return () => {
      if (raf) cancelAnimationFrame(raf);
      root.removeEventListener('scroll', scheduleRead);
      window.removeEventListener('resize', scheduleRead);
      window.removeEventListener('orientationchange', scheduleRead);
      resizeObserver.disconnect();
    };
  }, [read, rootRef]);

  const scrollToScene = useCallback((id: BattleChapterId) => {
    const root = rootRef.current;
    const scene = sceneMap.get(id)?.scene;
    if (!root || !scene) return;
    const element = root.querySelector<HTMLElement>(`[data-world-scene="${id}"]`);
    if (!element) return;
    root.scrollTo({ top: element.offsetTop, behavior: snapshot.reducedMotion ? 'auto' : 'smooth' });
  }, [rootRef, sceneMap, snapshot.reducedMotion]);

  const sceneStyle = useCallback((id: BattleChapterId): React.CSSProperties => {
    const scene = sceneMap.get(id)?.scene ?? fallback;
    return {
      minHeight: `${Math.max(1, scene.scrollWeight) * 100}svh`,
      ['--scene-accent' as string]: scene.accent,
      ['--scene-linger' as string]: scene.linger,
    } as React.CSSProperties;
  }, [fallback, sceneMap]);

  return { ...snapshot, scrollToScene, sceneStyle };
}
