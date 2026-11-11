// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { parseCommand } from '../src/nlp';
import { BASELINE_VALUATION, type SovereignState, applyCommand } from '../src/state';

const freshState = (): SovereignState => ({
  portfolioValuation: BASELINE_VALUATION,
  transactionsCount: 0,
  lastCommand: null,
  updatedAt: new Date(0).toISOString(),
  swarm: { active: false, tasks: 0, completed: 0 },
});

describe('applyCommand (Task D · voice action → state)', () => {
  it('moves valuation from $14.2M to $14,215,000 on "add transaction 15000"', () => {
    const s = freshState();
    applyCommand(parseCommand('add transaction 15000'), s);
    expect(s.portfolioValuation).toBe(14_215_000);
    expect(s.transactionsCount).toBe(1);
    expect(s.lastCommand).toBe('add_transaction');
  });

  it('does not change valuation for non-financial commands', () => {
    const s = freshState();
    applyCommand(parseCommand('remind Andre'), s);
    expect(s.portfolioValuation).toBe(BASELINE_VALUATION);
    expect(s.lastCommand).toBe('remind');
  });
});
