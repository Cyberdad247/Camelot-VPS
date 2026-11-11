// SPDX-License-Identifier: MIT

import crypto from 'node:crypto';
import { describe, expect, it } from 'vitest';
import {
  DEFAULT_FUTURE_SKEW_MS,
  DEFAULT_PAST_SKEW_MS,
  SignatureError,
  assertFresh,
  verifyActionSignature,
  verifyWebhookSignature,
} from './security';

const SECRET = 'test-secret';
const body = JSON.stringify({ message: 'add transaction 100' });
const sign = (b: string, secret = SECRET) =>
  crypto.createHmac('sha256', secret).update(b).digest('hex');

describe('verifyWebhookSignature (Task 2.4 ingress security)', () => {
  it('accepts a valid signature', () => {
    expect(verifyWebhookSignature(body, sign(body), SECRET)).toBe(true);
  });

  it('rejects a tampered body', () => {
    expect(verifyWebhookSignature(`${body} `, sign(body), SECRET)).toBe(false);
  });

  it('rejects a signature made with the wrong secret', () => {
    expect(verifyWebhookSignature(body, sign(body, 'wrong'), SECRET)).toBe(false);
  });

  it('rejects missing signature or secret', () => {
    expect(verifyWebhookSignature(body, undefined, SECRET)).toBe(false);
    expect(verifyWebhookSignature(body, sign(body), '')).toBe(false);
  });
});

// ── KBA Cartridge additions ──

describe('assertFresh (KBA freshness gate — symmetric past/future skew defense)', () => {
  const NOW = 1_700_000_000_000;

  it('exposes the documented default skew windows', () => {
    expect(DEFAULT_PAST_SKEW_MS).toBe(60_000);
    expect(DEFAULT_FUTURE_SKEW_MS).toBe(30_000);
  });

  it('passes when timestamp equals now and no expiresAt given', () => {
    expect(() => assertFresh({ timestamp: NOW, now: NOW })).not.toThrow();
  });

  it('passes within the past-skew window', () => {
    expect(() =>
      assertFresh({ timestamp: NOW - DEFAULT_PAST_SKEW_MS + 1000, now: NOW }),
    ).not.toThrow();
  });

  it('passes within the future-skew window', () => {
    expect(() =>
      assertFresh({ timestamp: NOW + DEFAULT_FUTURE_SKEW_MS - 1000, now: NOW }),
    ).not.toThrow();
  });

  it('rejects when timestamp is past the past-skew window', () => {
    expect(() =>
      assertFresh({ timestamp: NOW - DEFAULT_PAST_SKEW_MS - 1000, now: NOW }),
    ).toThrow(SignatureError);
  });

  it('rejects when timestamp is further in the future than the future-skew window', () => {
    expect(() =>
      assertFresh({ timestamp: NOW + DEFAULT_FUTURE_SKEW_MS + 1000, now: NOW }),
    ).toThrow(SignatureError);
  });

  it('rejects when expiresAt is past by more than the 1s hard-expiry grace', () => {
    expect(() =>
      assertFresh({
        timestamp: NOW,
        now: NOW,
        expiresAt: NOW - 60_000,
      }),
    ).toThrow(SignatureError);
  });

  it('accepts when expiresAt is within the 1s hard-expiry grace', () => {
    expect(() =>
      assertFresh({
        timestamp: NOW,
        now: NOW,
        expiresAt: NOW - 500,
      }),
    ).not.toThrow();
  });

  it('rejects non-finite timestamp with MALFORMED', () => {
    expect(() => assertFresh({ timestamp: Number.NaN, now: NOW })).toThrow(SignatureError);
  });

  it('rejects non-finite expiresAt with MALFORMED', () => {
    expect(() =>
      assertFresh({ timestamp: NOW, now: NOW, expiresAt: Number.POSITIVE_INFINITY }),
    ).toThrow(SignatureError);
  });

  it('respects caller-supplied skew overrides', () => {
    expect(() =>
      assertFresh({
        timestamp: NOW - 10_000,
        now: NOW,
        pastSkewMs: 5_000,
      }),
    ).toThrow(SignatureError);
  });
});

describe('verifyActionSignature (KBA bundle validator)', () => {
  const SECRET = 'unit-secret';
  const actionId = 'KBA_SYNC_001';
  const timestamp = Date.now();
  const expiresAt = timestamp + 5 * 60_000;
  const signBundle = (aid: string, ts: number, secret: string) =>
    crypto.createHmac('sha256', secret).update(`${aid}:${ts}`).digest('hex');

  it('accepts a valid signed bundle', () => {
    expect(() =>
      verifyActionSignature({
        actionId,
        timestamp,
        signature: signBundle(actionId, timestamp, SECRET),
        expiresAt,
        secret: SECRET,
      }),
    ).not.toThrow();
  });

  it('rejects when signature is invalid', () => {
    expect(() =>
      verifyActionSignature({
        actionId,
        timestamp,
        signature: 'x'.repeat(64),
        expiresAt,
        secret: SECRET,
      }),
    ).toThrow(SignatureError);
  });

  it('rejects when timestamp claims to be from the future beyond the skew window', () => {
    expect(() =>
      verifyActionSignature({
        actionId,
        timestamp: Date.now() + 5 * 60_000,
        signature: signBundle(actionId, Date.now() + 5 * 60_000, SECRET),
        expiresAt: Date.now() + 10 * 60_000,
        secret: SECRET,
      }),
    ).toThrow(SignatureError);
  });

  it('rejects when expiresAt is past hard expiration', () => {
    expect(() =>
      verifyActionSignature({
        actionId,
        timestamp: Date.now() - 10 * 60_000,
        signature: signBundle(actionId, Date.now() - 10 * 60_000, SECRET),
        expiresAt: Date.now() - 60_000,
        secret: SECRET,
      }),
    ).toThrow(SignatureError);
  });
});
