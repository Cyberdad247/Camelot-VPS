// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { parseCommand } from './nlp';
import { BASELINE_VALUATION, type SovereignState, applyCommand } from './state';

const freshState = (): SovereignState => ({
  portfolioValuation: BASELINE_VALUATION,
  transactionsCount: 0,
  kbaActionsCount: 0,
  kbaActionsByDomain: {
    sync: 0,
    audit: 0,
    reroute: 0,
    rezero: 0,
    heal: 0,
    nano: 0,
    scan: 0,
    forge: 0,
  },
  lastKbaDomain: null,
  lastCommand: null,
  lastResponse: null,
  lastLane: null,
  lastLatencyMs: null,
  lastRezeroed: false,
  updatedAt: new Date(0).toISOString(),
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

  // ── KBA Cartridge v1001 verb coverage ──

  it('increments global + per-domain counters for KBA_SYNC', () => {
    const s = freshState();
    applyCommand(parseCommand('kba KBA_SYNC_001'), s);
    expect(s.kbaActionsCount).toBe(1);
    expect(s.kbaActionsByDomain.sync).toBe(1);
    expect(s.kbaActionsByDomain.forge).toBe(0);
    expect(s.lastKbaDomain).toBe('sync');
    expect(s.lastCommand).toBe('kba');
    expect(s.portfolioValuation).toBe(BASELINE_VALUATION);
  });

  it('isolates per-domain counters for KBA_FORGE without disturbing other domains', () => {
    const s = freshState();
    applyCommand(parseCommand('kba KBA_FORGE_008'), s);
    expect(s.kbaActionsByDomain.forge).toBe(1);
    expect(s.kbaActionsByDomain.sync).toBe(0);
    expect(s.kbaActionsByDomain.audit).toBe(0);
    expect(s.lastKbaDomain).toBe('forge');
  });
});
