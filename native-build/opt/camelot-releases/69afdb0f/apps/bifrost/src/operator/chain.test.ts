// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { canonicalJson, payloadHash, sha256Hex } from './chain';

describe('chain', () => {
  it('canonicalJson is key-sorted and stable regardless of insertion order', () => {
    const a = canonicalJson({ b: 1, a: { y: 2, x: 1 } });
    const b = canonicalJson({ a: { x: 1, y: 2 }, b: 1 });
    expect(a).toBe(b);
  });

  it('payloadHash prefixes with sha256:', () => {
    expect(payloadHash({ hello: 'world' })).toMatch(/^sha256:[0-9a-f]{64}$/);
  });

  it('payloadHash differs when payload changes', () => {
    expect(payloadHash({ a: 1 })).not.toBe(payloadHash({ a: 2 }));
  });

  it('sha256Hex is deterministic', () => {
    expect(sha256Hex('abc')).toBe(sha256Hex('abc'));
    expect(sha256Hex('abc')).toBe('sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  });
});
