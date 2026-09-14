import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, Info, ShieldAlert } from 'lucide-react';
import './battle-action-feedback-layer.css';

type FeedbackTone = 'success' | 'info' | 'warning';

interface Feedback {
  id: number;
  title: string;
  detail: string;
  tone: FeedbackTone;
}

interface Props {
  rootId?: string;
}

function describeAction(button: HTMLButtonElement): Omit<Feedback, 'id'> | null {
  const label = (button.textContent || '').replace(/\s+/g, ' ').trim();
  if (!label) return null;

  if (button.closest('.battle-scroll-actions')) {
    if (/nominal/i.test(label)) return { title: 'Nominal state engaged', detail: 'Threat pressure and response posture returned to nominal operating values.', tone: 'success' };
    if (/battle/i.test(label)) return { title: 'Battle Mode engaged', detail: 'Threat response, tactical telemetry, and active defense posture are now prioritized.', tone: 'warning' };
    if (/lockdown/i.test(label)) return { title: 'Lockdown engaged', detail: 'All defense layers armed, shield integrity maximized, and autonomous response enabled.', tone: 'warning' };
  }

  if (button.closest('.threat-selector')) {
    return { title: `Threat filter: ${label}`, detail: 'The Threat Matrix is now scoped to this attack vector.', tone: 'info' };
  }

  if (button.closest('.threat-table')) {
    return { title: 'Target locked', detail: 'The selected threat row was promoted into the active investigation context.', tone: 'warning' };
  }

  if (button.closest('.defense-stack')) {
    const layer = label.replace(/ACTIVE|OFFLINE|L\d+/gi, '').trim();
    return { title: `${layer || 'Defense layer'} updated`, detail: 'Protection readiness has been recalculated from the current seven-layer defense posture.', tone: 'success' };
  }

  if (button.closest('.counter-buttons')) {
    if (/deploy/i.test(label)) return { title: 'Countermeasure swarm deployed', detail: 'Threat pressure reduced, shield integrity reinforced, and response latency improved.', tone: 'success' };
    return { title: 'Autonomous response updated', detail: 'Countermeasure routing now reflects the selected automation posture.', tone: 'info' };
  }

  if (button.closest('.command-line')) {
    return { title: 'Sovereign command submitted', detail: 'The command was written to the active Battle Log and execution context.', tone: 'success' };
  }

  if (button.classList.contains('descend')) {
    return { title: 'Entering Threat Space', detail: 'World Director is moving from overview into active threat investigation.', tone: 'info' };
  }

  return null;
}

export const BattleActionFeedbackLayer: React.FC<Props> = ({ rootId = 'battle-mode-scroll-command-center' }) => {
  const [host, setHost] = useState<HTMLElement | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  useEffect(() => {
    const root = document.getElementById(rootId);
    if (!root) return;

    let clearTimer = 0;
    const syncHost = () => {
      const scene = root.dataset.worldScene || 'overview';
      const section = root.querySelector<HTMLElement>(`[data-battle-chapter="${scene}"]`)
        || root.querySelector<HTMLElement>('[data-battle-chapter]');
      if (section) setHost(section);
    };

    const onClick = (event: Event) => {
      const target = event.target instanceof Element ? event.target.closest('button') : null;
      if (!(target instanceof HTMLButtonElement)) return;
      const description = describeAction(target);
      if (!description) return;
      window.setTimeout(() => {
        const item = { id: Date.now(), ...description };
        setFeedback(item);
        window.clearTimeout(clearTimer);
        clearTimer = window.setTimeout(() => setFeedback(current => current?.id === item.id ? null : current), 3600);
      }, 0);
    };

    syncHost();
    root.addEventListener('click', onClick);
    root.addEventListener('scroll', syncHost, { passive: true });
    const observer = new MutationObserver(syncHost);
    observer.observe(root, { attributes: true, attributeFilter: ['data-world-scene'] });

    return () => {
      window.clearTimeout(clearTimer);
      root.removeEventListener('click', onClick);
      root.removeEventListener('scroll', syncHost);
      observer.disconnect();
    };
  }, [rootId]);

  if (!host || !feedback) return null;
  const Icon = feedback.tone === 'success' ? CheckCircle2 : feedback.tone === 'warning' ? ShieldAlert : Info;

  return createPortal(
    <div className={`battle-action-feedback tone-${feedback.tone}`} role="status" aria-live="polite">
      <Icon size={18} />
      <div>
        <strong>{feedback.title}</strong>
        <span>{feedback.detail}</span>
      </div>
    </div>,
    host,
  );
};

export default BattleActionFeedbackLayer;
