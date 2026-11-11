// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { parseCommand } from '../src/nlp';

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
});
