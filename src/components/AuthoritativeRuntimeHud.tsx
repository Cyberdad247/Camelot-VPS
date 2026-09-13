import { useEffect, useMemo, useState } from 'react';
import { Activity, BadgeCheck, CircleAlert, Database, RefreshCw, ShieldCheck } from 'lucide-react';
import { useCamelotRuntime } from '../runtime/CamelotRuntimeContext';
import './authoritative-runtime-hud.css';

export function AuthoritativeRuntimeHud() {
  const runtime = useCamelotRuntime();
  const [commandCenterVisible, setCommandCenterVisible] = useState(false);

  useEffect(() => {
    const update = () => setCommandCenterVisible(Boolean(document.getElementById('camelot-command-center')));
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const task of runtime.snapshot?.tasks ?? []) {
      result[task.state] = (result[task.state] ?? 0) + 1;
    }
    return result;
  }, [runtime.snapshot]);

  const active = (runtime.snapshot?.tasks ?? []).filter((task) =>
    ['POLICY_PENDING', 'APPROVAL_PENDING', 'LEASED', 'VFS_PREFLIGHT', 'QUEUED', 'RUNNING', 'VERIFYING'].includes(task.state),
  ).length;
  const receipted = counts.RECEIPTED ?? 0;
  const failed = (counts.FAILED ?? 0) + (counts.DENIED ?? 0) + (counts.REVOKED ?? 0) + (counts.QUARANTINED ?? 0);
  const lastEvent = runtime.recentEvents.at(-1);

  if (!commandCenterVisible || runtime.connectionState === 'unconfigured') return null;

  return (
    <aside className="authoritative-runtime-hud" aria-label="Authoritative Camelot runtime state">
      <div className="arh-head">
        <div>
          <span className={`arh-pulse state-${runtime.connectionState}`} />
          <strong>AUTHORITATIVE RUNTIME</strong>
        </div>
        <button type="button" onClick={() => void runtime.refresh()} aria-label="Refresh authoritative workspace snapshot">
          <RefreshCw size={12} />
        </button>
      </div>

      <div className="arh-identity">
        <span><Database size={12} /> Workspace</span>
        <b>{runtime.workspaceId.slice(0, 12)}{runtime.workspaceId.length > 12 ? '…' : ''}</b>
      </div>

      <div className="arh-grid">
        <div>
          <ShieldCheck size={13} />
          <small>AUTHORITY EPOCH</small>
          <b>{runtime.snapshot?.authorityEpoch ?? '—'}</b>
        </div>
        <div>
          <Activity size={13} />
          <small>ACTIVE TASKS</small>
          <b>{active}</b>
        </div>
        <div>
          <BadgeCheck size={13} />
          <small>RECEIPTED</small>
          <b>{receipted}</b>
        </div>
        <div className={failed ? 'arh-risk' : ''}>
          <CircleAlert size={13} />
          <small>EXCEPTIONS</small>
          <b>{failed}</b>
        </div>
      </div>

      <div className="arh-stream">
        <span>STATE</span>
        <b>{runtime.connectionState.toUpperCase()}</b>
        <span>SEQ</span>
        <b>{runtime.snapshot?.lastSequence ?? '—'}</b>
      </div>

      {lastEvent ? (
        <div className="arh-last-event">
          <small>LAST VERIFIED EVENT</small>
          <span>{lastEvent.type}</span>
          <code>#{lastEvent.sequence}</code>
        </div>
      ) : (
        <div className="arh-last-event">
          <small>EVENT STREAM</small>
          <span>Waiting for workspace evidence</span>
        </div>
      )}

      {runtime.lastError && <div className="arh-error">{runtime.lastError}</div>}
    </aside>
  );
}
