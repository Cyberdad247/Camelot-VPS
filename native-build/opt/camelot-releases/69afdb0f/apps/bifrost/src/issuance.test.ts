// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { issueSignedAction, TTL_MS, FRESHNESS_TOLERANCE_MS } from './issuance';

const SECRET = 'unit-test-secret';

describe('issueSignedAction (KBA Cartridge HMAC issuance)', () => {
  it('returns a signed bundle with shape { payload, signature, timestamp, expiresAt }', () => {
    const result = issueSignedAction('KBA_SYNC_001', SECRET);
    expect(result.payload).toBe(`KBA_SYNC_001:${result.timestamp}`);
    expect(result.signature).toMatch(/^[a-f0-9]{64}$/);
    expect(result.expiresAt - result.timestamp).toBe(TTL_MS);
  });

  it('produces different signatures for different actionIds', () => {
    const a = issueSignedAction('KBA_AUDIT_001', SECRET);
    const b = issueSignedAction('KBA_AUDIT_002', SECRET);
    expect(a.signature).not.toBe(b.signature);
    expect(a.payload).not.toBe(b.payload);
  });

  it('throws on empty secret (defense-in-depth)', () => {
    expect(() => issueSignedAction('KBA_SYNC_001', '')).toThrow(/WEBHOOK_SECRET/);
  });

  it('expiresAt equals timestamp + TTL_MS exactly; FRESHNESS_TOLERANCE_MS is 5 s', () => {
    const r = issueSignedAction('KBA_SYNC_001', SECRET);
    expect(r.expiresAt - r.timestamp).toBe(TTL_MS);
    expect(FRESHNESS_TOLERANCE_MS).toBe(5_000);
  });
});
