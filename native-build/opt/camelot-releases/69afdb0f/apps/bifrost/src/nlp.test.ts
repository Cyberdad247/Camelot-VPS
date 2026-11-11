// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { parseCommand } from './nlp';

describe('parseCommand (Task 2.3 NLP)', () => {
  it('parses "add transaction" with amount, stripping $ and commas', () => {
    expect(parseCommand('add transaction 15000')).toEqual({
      action: 'add_transaction',
      amount: 15000,
    });
    expect(parseCommand('Add Transaction $15,000')).toEqual({
      action: 'add_transaction',
      amount: 15000,
    });
  });

  it('parses "remind <who>"', () => {
    expect(parseCommand('remind Andre')).toEqual({ action: 'remind', who: 'andre' });
  });

  it('parses "order <item>"', () => {
    expect(parseCommand('order espresso')).toEqual({ action: 'order', item: 'espresso' });
  });

  it('falls back to unknown for unrecognized input', () => {
    expect(parseCommand('do a backflip')).toEqual({ action: 'unknown', raw: 'do a backflip' });
  });

  // KBA Cartridge — server.ts emits `kba KBA_<DOMAIN>_<discriminator>` after
  // a verified /api/bifrost/hitl dispatch. parseCommand lifts the domain out.
  it('parses a canonical KBA_SYNC utterance', () => {
    expect(parseCommand('kba KBA_SYNC_001')).toEqual({
      action: 'kba',
      domain: 'sync',
      raw: 'kba KBA_SYNC_001',
    });
  });

  it('parses a KBA_REROUTE utterance with a non-numeric discriminator', () => {
    expect(parseCommand('kba KBA_REROUTE_X7')).toEqual({
      action: 'kba',
      domain: 'reroute',
      raw: 'kba KBA_REROUTE_X7',
    });
  });

  it('falls back to unknown when the `kba` prefix is missing', () => {
    expect(parseCommand('KBA_FORGE_X1')).toEqual({ action: 'unknown', raw: 'KBA_FORGE_X1' });
  });

  it('falls back to unknown for an invalid KBA domain', () => {
    expect(parseCommand('kba kba_unknown_001').action).toBe('unknown');
  });
});
