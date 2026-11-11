// SPDX-License-Identifier: MIT

import { randomUUID } from 'node:crypto';
import { EffectManifestSchema, type EffectManifest } from './contracts';

export interface VerifyContext {
  now: () => Date;
  /** Nonces already used for this task — replays must be rejected. */
  seenNonces: Set<string>;
  /** Callback resolving a receipt:// ref to presence. */
  requiredEvidencePresent: (ref: string) => boolean;
  gideonVerdict: 'pass' | 'fail' | 'pending' | 'unavailable';
  vfsEvidenceOk: boolean;
}

export interface VerifyResult {
  approved: boolean;
  reasons: string[];
  manifestId: string;
}

export interface Lease {
  leaseId: string;
  manifestId: string;
  issuedAt: number;
  expiresAt: number;
}

/** In-memory lease registry. Slice #2: native decision service; the PEER
 * Sentinel v2 module path (design §17 Q1) remains an open question and this
 * registry is the placeholder it will replace. */
const leases = new Map<string, Lease>();
const seenNonceRegistry = new Map<string, Set<string>>();

export const SENTINEL_UNAVAILABLE = {
  state: 'APPROVAL_SUSPENDED',
  message: 'Sentinel decision service unavailable; approve/deny disabled.',
  lastVerifiedTimestamp: null,
} as const;

export function verifyManifest(
  manifest: EffectManifest,
  ctx: VerifyContext,
): VerifyResult {
  const reasons: string[] = [];

  const parsed = EffectManifestSchema.safeParse(manifest);
  if (!parsed.success) {
    return { approved: false, reasons: ['manifest_schema_invalid'], manifestId: manifest.manifestId };
  }

  if (new Date(manifest.expiresAt).getTime() <= ctx.now().getTime()) {
    reasons.push('manifest_expired');
  }
  for (const ref of manifest.requiredEvidence) {
    if (!ctx.requiredEvidencePresent(ref)) reasons.push('required_evidence_missing');
  }
  if (ctx.gideonVerdict !== 'pass') reasons.push('gideon_verdict_not_pass');
  if (!ctx.vfsEvidenceOk) reasons.push('vfs_evidence_not_ok');
  if (ctx.seenNonces.has(manifest.oneTimeNonce)) reasons.push('nonce_replayed');

  if (reasons.length === 0) {
    const taskNonces = seenNonceRegistry.get(manifest.taskId) ?? new Set<string>();
    taskNonces.add(manifest.oneTimeNonce);
    seenNonceRegistry.set(manifest.taskId, taskNonces);
  }

  return { approved: reasons.length === 0, reasons, manifestId: manifest.manifestId };
}

export function issueLease(manifestId: string, ttlMs = 5 * 60_000): Lease {
  const now = Date.now();
  const lease: Lease = {
    leaseId: randomUUID(),
    manifestId,
    issuedAt: now,
    expiresAt: now + ttlMs,
  };
  leases.set(lease.leaseId, lease);
  return lease;
}

export function getLease(leaseId: string): Lease | undefined {
  const lease = leases.get(leaseId);
  if (!lease) return undefined;
  if (Date.now() > lease.expiresAt) {
    leases.delete(leaseId);
    return undefined;
  }
  return lease;
}

export function revokeLease(leaseId: string): boolean {
  return leases.delete(leaseId);
}
