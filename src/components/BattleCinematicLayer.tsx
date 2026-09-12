import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { BattleChapterId } from '../world-director/battleWorld';
import {
  BATTLE_CINEMATIC_CONNECTORS,
  BATTLE_MEDIA_BY_ID,
  validateBattleCinematicSeams,
} from '../world-director/cinematicManifest';
import './battle-cinematic-layer.css';

interface BattleCinematicLayerProps {
  rootId?: string;
}

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));

const chapterOrder: BattleChapterId[] = [
  'overview', 'threats', 'telemetry', 'defense', 'brains', 'ouroboros', 'vfs', 'counter', 'command',
];

function isBattleChapter(value: string | undefined): value is BattleChapterId {
  return Boolean(value && chapterOrder.includes(value as BattleChapterId));
}

export const BattleCinematicLayer: React.FC<BattleCinematicLayerProps> = ({
  rootId = 'battle-mode-scroll-command-center',
}) => {
  const [stage, setStage] = useState<HTMLElement | null>(null);
  const [activeId, setActiveId] = useState<BattleChapterId>('overview');
  const [nextId, setNextId] = useState<BattleChapterId>('threats');
  const sceneVideoRef = useRef<HTMLVideoElement>(null);
  const connectorVideoRef = useRef<HTMLVideoElement>(null);
  const mediaEnabled = import.meta.env.VITE_BATTLE_CINEMATIC_MEDIA === '1';
  const seamFailures = useMemo(() => validateBattleCinematicSeams(), []);

  const sceneMedia = BATTLE_MEDIA_BY_ID[activeId];
  const connector = useMemo(
    () => BATTLE_CINEMATIC_CONNECTORS.find(item => item.from === activeId && item.to === nextId),
    [activeId, nextId],
  );

  useEffect(() => {
    const root = document.getElementById(rootId);
    if (!root) return;
    const stageNode = root.querySelector<HTMLElement>('.battle-stage');
    setStage(stageNode);
  }, [rootId]);

  useEffect(() => {
    if (!mediaEnabled || seamFailures.length === 0) return;
    console.error('[CAMELOT:CINEMATIC] Frame seam contract invalid. Falling back to posters.', seamFailures);
  }, [mediaEnabled, seamFailures]);

  const videoAllowed = mediaEnabled && seamFailures.length === 0;

  useEffect(() => {
    const root = document.getElementById(rootId);
    if (!root) return;

    let raf = 0;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const coarse = window.matchMedia('(hover: none) and (pointer: coarse)');

    const read = () => {
      raf = 0;
      const sceneName = root.dataset.worldScene;
      if (!isBattleChapter(sceneName)) return;

      const index = chapterOrder.indexOf(sceneName);
      const following = chapterOrder[Math.min(index + 1, chapterOrder.length - 1)] ?? sceneName;
      setActiveId(previous => previous === sceneName ? previous : sceneName);
      setNextId(previous => previous === following ? previous : following);

      const rawProgress = Number.parseFloat(root.style.getPropertyValue('--scene-progress')) || 0;
      const progress = clamp(rawProgress);
      root.style.setProperty('--cinematic-progress', progress.toFixed(4));
      root.style.setProperty('--cinematic-connector-mix', clamp((progress - 0.72) / 0.28).toFixed(4));

      if (!videoAllowed || reduced.matches) return;

      const mobile = coarse.matches || window.innerWidth <= 860;
      const sceneVideo = sceneVideoRef.current;
      if (sceneVideo?.duration && !sceneVideo.seeking && sceneVideo.dataset.failed !== 'true') {
        const t = clamp(progress, 0, 0.999) * sceneVideo.duration;
        const epsilon = mobile ? 0.03 : 0.012;
        if (Math.abs(sceneVideo.currentTime - t) > epsilon) {
          try { sceneVideo.currentTime = t; } catch { /* decoder not ready yet */ }
        }
      }

      const connectorVideo = connectorVideoRef.current;
      const connectorProgress = clamp((progress - 0.72) / 0.28);
      if (connectorVideo?.duration && connectorProgress > 0 && !connectorVideo.seeking && connectorVideo.dataset.failed !== 'true') {
        const t = clamp(connectorProgress, 0, 0.999) * connectorVideo.duration;
        const epsilon = mobile ? 0.03 : 0.012;
        if (Math.abs(connectorVideo.currentTime - t) > epsilon) {
          try { connectorVideo.currentTime = t; } catch { /* decoder not ready yet */ }
        }
      }
    };

    const scheduleRead = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(read);
    };

    const prime = () => {
      [sceneVideoRef.current, connectorVideoRef.current].forEach(video => {
        if (!video || video.dataset.failed === 'true') return;
        try {
          video.play().then(() => video.pause()).catch(() => undefined);
        } catch { /* gesture/media policy fallback */ }
      });
    };

    read();
    root.addEventListener('scroll', scheduleRead, { passive: true });
    window.addEventListener('resize', scheduleRead);
    window.addEventListener('orientationchange', scheduleRead);
    window.addEventListener('pointerdown', prime, { once: true, passive: true });

    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      root.removeEventListener('scroll', scheduleRead);
      window.removeEventListener('resize', scheduleRead);
      window.removeEventListener('orientationchange', scheduleRead);
      window.removeEventListener('pointerdown', prime);
    };
  }, [connector, rootId, videoAllowed]);

  if (!stage || !sceneMedia) return null;

  const mobile = typeof window !== 'undefined'
    && (window.matchMedia('(hover: none) and (pointer: coarse)').matches || window.innerWidth <= 860);
  const sceneClip = mobile ? (sceneMedia.clipMobile ?? sceneMedia.clip) : sceneMedia.clip;
  const connectorClip = connector
    ? (mobile ? (connector.clipMobile ?? connector.clip) : connector.clip)
    : undefined;

  const markFailed = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    event.currentTarget.dataset.failed = 'true';
  };

  return createPortal(
    <div className="battle-cinematic-layer" data-cinematic-scene={activeId} aria-hidden="true">
      <div
        className="battle-cinematic-poster"
        style={{ backgroundImage: `url(${mobile && sceneMedia.posterMobile ? sceneMedia.posterMobile : sceneMedia.poster})` }}
      />

      {videoAllowed && sceneClip && (
        <video
          key={`scene-${activeId}-${sceneClip}`}
          ref={sceneVideoRef}
          className="battle-cinematic-video battle-cinematic-video--scene"
          src={sceneClip}
          muted
          playsInline
          preload="metadata"
          tabIndex={-1}
          onError={markFailed}
        />
      )}

      {videoAllowed && connectorClip && activeId !== nextId && (
        <video
          key={`connector-${activeId}-${nextId}-${connectorClip}`}
          ref={connectorVideoRef}
          className="battle-cinematic-video battle-cinematic-video--connector"
          src={connectorClip}
          muted
          playsInline
          preload="metadata"
          tabIndex={-1}
          onError={markFailed}
        />
      )}

      <div className="battle-cinematic-vignette" />
      <div className="battle-cinematic-grain" />
    </div>,
    stage,
  );
};

export default BattleCinematicLayer;
