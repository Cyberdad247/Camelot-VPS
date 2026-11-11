// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { verdictFor } from './gideon';
import type { DiffEvidence, TestRunResult } from './contracts';

function makeDiff(overrides: Partial<DiffEvidence> = {}): DiffEvidence {
  return {
    baseRevision: 'base',
    candidateRevision: 'cand',
    diffSha256: 'sha256:abc',
    changedPaths: ['apps/pwa/src/app/console/page.tsx'],
    addedLines: 12,
    removedLines: 3,
    generatedAt: '2026-08-14T13:48:00Z',
    gideonVerdict: 'pending',
    ...overrides,
  };
}

function makeTest(status: TestRunResult['status']): TestRunResult {
  return {
    schemaVersion: 'test-run-result/1',
    runId: 'run_1',
    taskId: 'task_1',
    correlationId: 'cor_1',
    runner: 'boris-gideon-adapter',
    status,
    startedAt: '2026-08-14T13:40:00Z',
    completedAt: '2026-08-14T13:42:00Z',
    suites: [],
    summary: { total: 0, passed: 0, failed: 0, skipped: 0 },
    outputHash: 'sha256:test',
  };
}

describe('gideon verdict provider', () => {
  it('passes when the diff hash is self-consistent and tests pass', () => {
    expect(verdictFor(makeDiff(), [makeTest('passed')])).toBe('pass');
  });

  it('fails when any test run failed', () => {
    expect(verdictFor(makeDiff(), [makeTest('passed'), makeTest('failed')])).toBe('fail');
  });

  it('is unavailable when the adapter is unreachable', () => {
    expect(verdictFor(makeDiff(), [makeTest('passed')], { unavailable: true })).toBe('unavailable');
  });

  it('stays pending while tests are still running', () => {
    expect(verdictFor(makeDiff(), [makeTest('passed'), makeTest('cancelled')])).toBe('pending');
  });
});
