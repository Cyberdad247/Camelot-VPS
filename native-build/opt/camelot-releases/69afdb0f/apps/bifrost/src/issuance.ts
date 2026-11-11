// SPDX-License-Identifier: MIT

import crypto from 'node:crypto';

/**
 * Issue a short-lived, server-side HMAC signature for an authorized KBA
 * action. The PWA receives this bundle and re-presents it to
 * `/api/bifrost/hitl` with the same actionId in `x-webhook-action` so the
 * verifier can re-derive the raw body and re-check the HMAC.
 *
 * TTL is 5 minutes by default. Freshness tolerance on the verify side
 * absorbs up to 5 s of clock skew.
 */

export const TTL_MS = 5 * 60_000;
export const FRESHNESS_TOLERANCE_MS = 5_000;

export interface SignedAction {
  /** Canonical raw body: `${actionId}:${timestamp}`. */
  payload: string;
  /** HMAC-SHA256 hex digest of `payload` under `secret`. */
  signature: string;
  /** ms epoch of issuance. */
  timestamp: number;
  /** timestamp + TTL_MS. The verifier rejects bundles past this point. */
  expiresAt: number;
}

export function issueSignedAction(actionId: string, secret: string): SignedAction {
  if (!secret) {
    throw new Error('WEBHOOK_SECRET is undefined; issuance forbidden');
  }
  const timestamp = Date.now();
  const payload = `${actionId}:${timestamp}`;
  const signature = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  return {
    payload,
    signature,
    timestamp,
    expiresAt: timestamp + TTL_MS,
  };
}
