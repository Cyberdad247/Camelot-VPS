// SPDX-License-Identifier: MIT

import type { OperatorTaskSnapshot } from './contracts';

export const FIXTURES = [
  'operator-console-readonly-audit',
  'operator-console-approval',
  'operator-console-integrity-failure',
  'operator-console-cancellation',
] as const;

export type FixtureName = (typeof FIXTURES)[number];

function base(taskId: string): OperatorTaskSnapshot {
  return {
    schemaVersion: 'operator-task-snapshot/1',
    taskId,
    correlationId: `cor_${taskId}`,
    generatedAt: new Date().toISOString(),
    integrity: 'verified',
    intent: { raw: `Fixture task ${taskId}: governed audit and approval path.` },
    approval: { state: 'APPROVAL_REQUIRED' },
    taskGraph: [
      { nodeId: 'n1', name: 'ant-mapper', status: 'done', worker: 'nano-knight' },
      { nodeId: 'n2', name: 'owl-auditor', status: 'running', worker: 'nano-knight' },
    ],
    diffs: [{
      baseRevision: 'base', candidateRevision: 'cand', diffSha256: 'sha256:abc',
      changedPaths: ['apps/pwa/src/app/console/page.tsx'],
      addedLines: 12, removedLines: 3, generatedAt: new Date().toISOString(),
      gideonVerdict: 'pass',
      receiptRef: 'receipt://vfs/diff/01abc',
    }],
    tests: [{
      schemaVersion: 'test-run-result/1',
      runId: 'run_1', taskId, correlationId: `cor_${taskId}`,
      runner: 'boris-gideon-adapter', status: 'passed',
      startedAt: new Date().toISOString(), completedAt: new Date().toISOString(),
      suites: [{ name: 'operator-console', status: 'passed', durationMs: 1200, artifactRef: 'receipt://boris/test-report/run_1' }],
      summary: { total: 4, passed: 4, failed: 0, skipped: 0 },
      outputHash: 'sha256:test',
      receiptRef: 'receipt://boris/test-run/run_1',
    }],
    receipts: [],
  };
}

export function snapshotFor(taskId: string, fixture: FixtureName): OperatorTaskSnapshot {
  const s = base(taskId);
  switch (fixture) {
    case 'operator-console-readonly-audit':
      s.approval = { state: 'COMPLETED' };
      s.receipts = [{
        receiptId: 'r1', eventId: 'evt_1', taskId, correlationId: `cor_${taskId}`,
        kind: 'task.completed', timestamp: new Date().toISOString(),
        actor: { id: 'herald', role: 'herald' },
        payloadHash: 'sha256:abc', integrity: 'verified',
      }];
      return s;
    case 'operator-console-approval':
      s.approval = { state: 'APPROVAL_REQUIRED' };
      return s;
    case 'operator-console-integrity-failure':
      s.integrity = 'integrity_failed';
      s.receipts = [{
        receiptId: 'r_bad', eventId: 'evt_bad', taskId, correlationId: `cor_${taskId}`,
        kind: 'decision.approved', timestamp: new Date().toISOString(),
        actor: { id: 'sentinel', role: 'sentinel' },
        payloadHash: 'sha256:forged', integrity: 'integrity_failed',
      }];
      return s;
    case 'operator-console-cancellation':
      s.approval = { state: 'CANCELLED' };
      s.receipts = [{
        receiptId: 'r_cancel', eventId: 'evt_cancel', taskId, correlationId: `cor_${taskId}`,
        kind: 'task.cancelled', timestamp: new Date().toISOString(),
        actor: { id: 'herald', role: 'herald' },
        payloadHash: 'sha256:cancel', integrity: 'verified',
      }];
      return s;
  }
}

export function eventsFor(fixture: FixtureName): Array<{ type: string; payload: unknown }> {
  return [
    { type: 'snapshot', payload: snapshotFor('task_fixture', fixture) },
  ];
}
