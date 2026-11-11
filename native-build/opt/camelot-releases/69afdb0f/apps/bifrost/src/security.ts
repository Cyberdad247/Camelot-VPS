// SPDX-License-Identifier: MIT

import crypto from 'node:crypto';

/**
 * Verify an HMAC-SHA256 hex signature of the raw request body using a shared
 * secret. Uses a constant-time comparison to avoid timing attacks.
 * Returns false on any missing input or length mismatch.
 */
export function verifyWebhookSignature(
  rawBody: string,
  signature: string | undefined,
  secret: string,
): boolean {
  if (!signature || !secret) return false;

  const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
  const sigBuf = Buffer.from(signature);
  const expBuf = Buffer.from(expected);

  if (sigBuf.length !== expBuf.length) return false;
  return crypto.timingSafeEqual(sigBuf, expBuf);
}

export class SignatureError extends Error {
  readonly code: 'INVALID' | 'EXPIRED' | 'MALFORMED';
  constructor(code: 'INVALID' | 'EXPIRED' | 'MALFORMED', message: string) {
    super(message);
    this.code = code;
  }
}

/**
 * Freshness check for a signed action bundle. Validates three things:
 *   1. `timestamp` is well-formed (finite number).
 *   2. `timestamp` is not older than `pastSkewMs` (default 60 s) and not further
 *      in the future than `futureSkewMs` (default 30 s) — symmetric
 *      defense-in-depth against both replay and timestamp-forgery attacks.
 *   3. If `expiresAt` is supplied, `now` may not exceed it by more than 1 s
 *      of additional grace.
 */
export interface FreshnessOptions {
  /** Unix epoch ms when the signature was minted. */
  timestamp: number;
  /** Optional absolute hard expiration set by the issuer. */
  expiresAt?: number;
  /** Override current time (testing). */
  now?: number;
  /** Past-skew window in ms. Default 60_000. */
  pastSkewMs?: number;
  /** Future-skew window in ms. Default 30_000. */
  futureSkewMs?: number;
}

export const DEFAULT_PAST_SKEW_MS = 60_000;
export const DEFAULT_FUTURE_SKEW_MS = 30_000;

export function assertFresh(opts: FreshnessOptions): void {
  const now = opts.now ?? Date.now();
  const pastSkewMs = opts.pastSkewMs ?? DEFAULT_PAST_SKEW_MS;
  const futureSkewMs = opts.futureSkewMs ?? DEFAULT_FUTURE_SKEW_MS;

  if (!Number.isFinite(opts.timestamp)) {
    throw new SignatureError('MALFORMED', 'timestamp must be a finite number');
  }

  const skewMs = now - opts.timestamp;
  if (skewMs > pastSkewMs) {
    throw new SignatureError(
      'EXPIRED',
      `signature too old (age=${skewMs}ms > ${pastSkewMs}ms)`,
    );
  }
  if (skewMs < -futureSkewMs) {
    throw new SignatureError(
      'INVALID',
      `signature timestamp too far in future (skew=${-skewMs}ms > ${futureSkewMs}ms)`,
    );
  }

  if (opts.expiresAt !== undefined) {
    if (!Number.isFinite(opts.expiresAt)) {
      throw new SignatureError('MALFORMED', 'expiresAt must be a finite number');
    }
    if (now > opts.expiresAt + 1000) {
      throw new SignatureError(
        'EXPIRED',
        `signature past hard expiration (now=${now} > expiresAt+1s=${opts.expiresAt + 1000})`,
      );
    }
  }
}

export function verifyActionSignature(args: {
  actionId: string;
  timestamp: number;
  signature: string | undefined;
  expiresAt: number;
  secret: string;
  rawBody?: string;
}): void {
  const { actionId, timestamp, signature, expiresAt, secret } = args;
  const rawBody = args.rawBody ?? `${actionId}:${timestamp}`;
  if (!Number.isFinite(timestamp)) {
    throw new SignatureError('MALFORMED', 'timestamp must be a finite number');
  }
  if (!verifyWebhookSignature(rawBody, signature, secret)) {
    throw new SignatureError('INVALID', 'signature mismatch');
  }
  assertFresh({ timestamp, expiresAt });
}
