// SPDX-License-Identifier: MIT

import crypto from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { verifyWebhookSignature } from '../src/security';

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
