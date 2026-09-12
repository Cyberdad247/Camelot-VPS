import React, { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Eye, HelpCircle, Keyboard, MousePointer2, Sparkles, X } from 'lucide-react';
import type { BattleChapterId } from '../world-director/battleWorld';
import { BATTLE_COMPREHENSION, BATTLE_COMPREHENSION_ORDER } from '../world-director/battleComprehension';
import './battle-comprehension-layer.css';

interface BattleComprehensionLayerProps {
  rootId?: string;
}

type GuideMode = 'guided' | 'expert';

function isChapter(value: string | undefined): value is BattleChapterId {
  return Boolean(value && BATTLE_COMPREHENSION_ORDER.includes(value as BattleChapterId));
}

export const BattleComprehensionLayer: React.FC<BattleComprehensionLayerProps> = ({
  rootId = 'battle-mode-scroll-command-center',
}) => {
  const [activeId, setActiveId] = useState<BattleChapterId>('overview');
  const [mode, setMode] = useState<GuideMode>('guided');
  const [helpOpen, setHelpOpen] = useState(false);
  const [interactionPulse, setInteractionPulse] = useState(0);

  const scene = BATTLE_COMPREHENSION[activeId];
  const index = BATTLE_COMPREHENSION_ORDER.indexOf(activeId);
  const previousId = BATTLE_COMPREHENSION_ORDER[Math.max(0, index - 1)];
  const nextId = BATTLE_COMPREHENSION_ORDER[index === BATTLE_COMPREHENSION_ORDER.length - 1 ? 0 : index + 1];

  useEffect(() => {
    const root = document.getElementById(rootId);
    if (!root) return;

    if (!root.hasAttribute('tabindex')) root.tabIndex = 0;
    root.setAttribute('aria-label', 'Camelot Battle Mode continuous command center');

    let frame = 0;
    const read = () => {
      frame = 0;
      const candidate = root.dataset.worldScene;
      if (isChapter(candidate)) {
        setActiveId(previous => previous === candidate ? previous : candidate);
      }
    };

    const schedule = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(read);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editable = target?.matches('input, textarea, select, [contenteditable="true"]');
      if (editable) return;
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp' && event.key !== 'PageDown' && event.key !== 'PageUp') return;
      event.preventDefault();
      const direction = event.key === 'ArrowDown' || event.key === 'PageDown' ? 1 : -1;
      const current = BATTLE_COMPREHENSION_ORDER.indexOf(activeId);
      const targetIndex = Math.min(BATTLE_COMPREHENSION_ORDER.length - 1, Math.max(0, current + direction));
      const id = BATTLE_COMPREHENSION_ORDER[targetIndex];
      const section = root.querySelector<HTMLElement>(`[data-battle-chapter="${id}"]`);
      section?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    };

    const onClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest('button, input, textarea, select, a')) {
        setInteractionPulse(value => value + 1);
      }
    };

    read();
    root.addEventListener('scroll', schedule, { passive: true });
    root.addEventListener('keydown', onKeyDown);
    root.addEventListener('click', onClick);

    return () => {
      if (frame) cancelAnimationFrame(frame);
      root.removeEventListener('scroll', schedule);
      root.removeEventListener('keydown', onKeyDown);
      root.removeEventListener('click', onClick);
    };
  }, [activeId, rootId]);

  const moveTo = (id: BattleChapterId) => {
    const root = document.getElementById(rootId);
    const target = root?.querySelector<HTMLElement>(`[data-battle-chapter="${id}"]`);
    target?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    root?.focus({ preventScroll: true });
  };

  const progressText = useMemo(() => `${index + 1} of ${BATTLE_COMPREHENSION_ORDER.length}`, [index]);

  return (
    <div className={`battle-comprehension battle-comprehension--${mode}`} data-pulse={interactionPulse}>
      <div className="battle-comprehension-live" aria-live="polite" aria-atomic="true">
        {scene.title}. {scene.purpose}
      </div>

      <div className="battle-context-strip">
        <div className="battle-context-location">
          <span>YOU ARE HERE</span>
          <strong>{scene.title}</strong>
          <small>{progressText}</small>
        </div>
        <div className="battle-context-purpose">
          <span>WHY THIS MATTERS</span>
          <p>{scene.purpose}</p>
        </div>
        <div className="battle-context-actions">
          <button type="button" className={mode === 'guided' ? 'active' : ''} onClick={() => setMode('guided')}><Eye size={14}/> Guided</button>
          <button type="button" className={mode === 'expert' ? 'active' : ''} onClick={() => setMode('expert')}><Sparkles size={14}/> Expert</button>
          <button type="button" aria-expanded={helpOpen} onClick={() => setHelpOpen(value => !value)}><HelpCircle size={14}/> Help</button>
        </div>
      </div>

      {mode === 'guided' && (
        <aside className="battle-guide-card" aria-label="Current section guide">
          <div className="battle-guide-index"><b>{String(index).padStart(2, '0')}</b><span>{scene.title}</span></div>
          <div className="battle-guide-block">
            <span>WHAT YOU CAN DO</span>
            <p>{scene.interaction}</p>
          </div>
          <div className="battle-guide-block outcome">
            <span>WHAT CHANGES</span>
            <p>{scene.outcome}</p>
          </div>
          <div className="battle-guide-navigation">
            <button type="button" onClick={() => moveTo(previousId)} disabled={index === 0}><ArrowUp size={14}/> Previous</button>
            <button type="button" className="primary" onClick={() => moveTo(nextId)}>{scene.primaryVerb}<ArrowDown size={14}/></button>
          </div>
        </aside>
      )}

      {helpOpen && (
        <aside className="battle-help-panel" aria-label="Battle Mode controls">
          <button className="battle-help-close" type="button" aria-label="Close help" onClick={() => setHelpOpen(false)}><X size={16}/></button>
          <h3>How to operate Battle Mode</h3>
          <div><MousePointer2 size={17}/><p><b>Touch or click</b><span>Interactive controls use visible buttons. Changes update tactical state immediately.</span></p></div>
          <div><Keyboard size={17}/><p><b>Keyboard</b><span>Focus the command center, then use ↑ / ↓ or Page Up / Page Down to move one subsystem at a time.</span></p></div>
          <div><Eye size={17}/><p><b>Guided vs Expert</b><span>Guided explains the current subsystem. Expert keeps only the location strip and leaves more room for operations.</span></p></div>
        </aside>
      )}
    </div>
  );
};

export default BattleComprehensionLayer;
