import React, { useEffect, useRef } from 'react';
import { BattleModeScrollCommandCenter } from './BattleModeScrollCommandCenter';
import { BattleCinematicLayer } from './BattleCinematicLayer';
import { BattleComprehensionLayer } from './BattleComprehensionLayer';
import { BATTLE_WORLD_SCENES } from '../world-director/battleWorld';
import './battle-world-assimilation.css';

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const smooth = (value: number) => {
  const x = clamp(value);
  return x * x * (3 - 2 * x);
};
const lingerEase = (value: number, linger: number) => {
  const x = clamp(value);
  const l = clamp(linger);
  const c = x - 0.5;
  return (1 - l) * x + l * (4 * c * c * c + 0.5);
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function qualityTier(): 'high' | 'medium' | 'scarcity' {
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8;
  const mobile = window.matchMedia('(hover: none) and (pointer: coarse)').matches || window.innerWidth <= 860;
  if (mobile || memory <= 4) return 'scarcity';
  if (memory >= 12 && window.innerWidth >= 1200) return 'high';
  return 'medium';
}

/**
 * Native Camelot assimilation of scroll-world's strongest mechanics:
 * weighted scenes, dwell/linger, continuous camera interpolation, mobile scarcity,
 * reduced-motion fallback, a media layer that can promote from posters to
 * exact-frame scrubbed scene/connector video, and a comprehension layer that
 * explains each subsystem without replacing the live React controls.
 */
export const BattleWorldAssimilation: React.FC = () => {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const root = host.querySelector<HTMLElement>('#battle-mode-scroll-command-center');
    if (!root) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let raf = 0;

    const applySceneWeights = () => {
      BATTLE_WORLD_SCENES.forEach(scene => {
        const section = root.querySelector<HTMLElement>(`[data-battle-chapter="${scene.id}"]`);
        if (!section) return;
        section.dataset.worldScene = scene.id;
        section.style.minHeight = `${Math.max(1, scene.scrollWeight) * 100}svh`;
        section.style.setProperty('--scene-accent', scene.accent);
        section.style.setProperty('--scene-linger', String(scene.linger));
      });
    };

    const read = () => {
      raf = 0;
      const maxScroll = Math.max(1, root.scrollHeight - root.clientHeight);
      const globalProgress = clamp(root.scrollTop / maxScroll);
      const focusY = root.scrollTop + root.clientHeight * 0.5;

      let activeIndex = BATTLE_WORLD_SCENES.length - 1;
      let activeEl: HTMLElement | null = null;

      for (let index = 0; index < BATTLE_WORLD_SCENES.length; index += 1) {
        const scene = BATTLE_WORLD_SCENES[index];
        const el = root.querySelector<HTMLElement>(`[data-battle-chapter="${scene.id}"]`);
        if (!el) continue;
        if (focusY < el.offsetTop + el.offsetHeight) {
          activeIndex = index;
          activeEl = el;
          break;
        }
      }

      const scene = BATTLE_WORLD_SCENES[activeIndex];
      if (!scene) return;
      if (!activeEl) activeEl = root.querySelector<HTMLElement>(`[data-battle-chapter="${scene.id}"]`);
      if (!activeEl) return;

      const rawLocal = clamp((focusY - activeEl.offsetTop) / Math.max(1, activeEl.offsetHeight));
      const local = lingerEase(rawLocal, scene.linger);
      const nextScene = BATTLE_WORLD_SCENES[Math.min(activeIndex + 1, BATTLE_WORLD_SCENES.length - 1)] ?? scene;
      const transition = reduced.matches ? 0 : smooth((rawLocal - 0.72) / 0.28);

      const x = lerp(scene.camera.x, nextScene.camera.x, transition);
      const y = lerp(scene.camera.y, nextScene.camera.y, transition);
      const scale = lerp(scene.camera.scale, nextScene.camera.scale, transition);
      const rotateX = lerp(scene.camera.rotateX, nextScene.camera.rotateX, transition);
      const rotateY = lerp(scene.camera.rotateY, nextScene.camera.rotateY, transition);
      const brightness = lerp(scene.camera.brightness, nextScene.camera.brightness, transition);
      const saturation = lerp(scene.camera.saturation, nextScene.camera.saturation, transition);
      const blur = lerp(scene.camera.blur, nextScene.camera.blur, transition);

      root.dataset.worldDirector = 'active';
      root.dataset.worldQuality = qualityTier();
      root.dataset.worldScene = scene.id;
      root.style.setProperty('--world-progress', globalProgress.toFixed(4));
      root.style.setProperty('--scene-progress', local.toFixed(4));
      root.style.setProperty('--world-x', `${x.toFixed(3)}vw`);
      root.style.setProperty('--world-y', `${y.toFixed(3)}vh`);
      root.style.setProperty('--world-scale', scale.toFixed(4));
      root.style.setProperty('--world-rx', `${rotateX.toFixed(3)}deg`);
      root.style.setProperty('--world-ry', `${rotateY.toFixed(3)}deg`);
      root.style.setProperty('--world-brightness', brightness.toFixed(3));
      root.style.setProperty('--world-saturation', saturation.toFixed(3));
      root.style.setProperty('--world-blur', `${blur.toFixed(2)}px`);
      root.style.setProperty('--world-accent', scene.accent);
    };

    const scheduleRead = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(read);
    };

    applySceneWeights();
    read();
    root.addEventListener('scroll', scheduleRead, { passive: true });
    window.addEventListener('resize', scheduleRead);
    window.addEventListener('orientationchange', scheduleRead);
    reduced.addEventListener('change', scheduleRead);

    const resizeObserver = new ResizeObserver(() => {
      applySceneWeights();
      scheduleRead();
    });
    resizeObserver.observe(root);

    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      root.removeEventListener('scroll', scheduleRead);
      window.removeEventListener('resize', scheduleRead);
      window.removeEventListener('orientationchange', scheduleRead);
      reduced.removeEventListener('change', scheduleRead);
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <div ref={hostRef} className="battle-world-assimilation">
      <BattleModeScrollCommandCenter />
      <BattleCinematicLayer />
      <BattleComprehensionLayer />
    </div>
  );
};

export default BattleWorldAssimilation;
