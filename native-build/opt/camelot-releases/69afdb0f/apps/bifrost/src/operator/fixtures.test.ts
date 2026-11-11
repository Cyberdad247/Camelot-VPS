// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { FIXTURES, snapshotFor } from './fixtures';

describe('operator fixtures', () => {
  it('exposes all four fixture names', () => {
    expect([...FIXTURES].sort()).toEqual([
      'operator-console-approval',
      'operator-console-cancellation',
      'operator-console-integrity-failure',
      'operator-console-readonly-audit',
    ]);
  });

  it('readonly-audit has no approval path and real worker nodes', () => {
    const s = snapshotFor('task_x', 'operator-console-readonly-audit');
    expect(s.taskGraph.some((n) => String(n.name).includes('ant-mapper'))).toBe(true);
    expect(s.taskGraph.some((n) => String(n.name).includes('owl-auditor'))).toBe(true);
    expect(s.approval.state).not.toBe('APPROVAL_REQUIRED');
  });

  it('integrity-failure fixture carries integrity_failed state', () => {
    const s = snapshotFor('task_x', 'operator-console-integrity-failure');
    expect(s.integrity).toBe('integrity_failed');
  });

  it('approval fixture carries one pending immutable manifest', () => {
    const s = snapshotFor('task_x', 'operator-console-approval');
    expect(s.approval.state).toBe('APPROVAL_REQUIRED');
  });
});
