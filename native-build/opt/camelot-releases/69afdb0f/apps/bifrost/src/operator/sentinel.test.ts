// SPDX-License-Identifier: MIT

import { describe, expect, it, vi } from 'vitest';
import {
  getLease,
  issueLease,
  revokeLease,
  verifyManifest,
  type VerifyContext,
} from './sentinel';
import type { EffectManifest } from './contracts';

function makeManifest(overrides: Partial<EffectManifest> = {}): EffectManifest {
  return {
    schemaVersion: 'effect-manifest/1',
    manifestId: 'eff_01J',
    taskId: 'task_01J',
    correlationId: 'cor_01J',
    kind: 'worktree.patch.promote',
    baseRevision: 'base',
    candidateRevision: 'cand',
    diffSha256: 'sha256:abc',
    allowedPaths: ['apps/pwa/src/**'],
    requiredEvidence: ['receipt://vfs/no-escape/1'],
    policyClass: 'engineering.write',
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    oneTimeNonce: 'nonce-1',
    // v1.2 fields per §5.5/§11.1 of the SADD
    effectClass: 'workspace.patch',
    declaredRiskTier: 'T2',
    declarationHash: 'sha256:' + 'a'.repeat(64),
    ...overrides,
  };
}

function makeCtx(overrides: Partial<VerifyContext> = {}): VerifyContext {
  return {
    now: () => new Date(),
    seenNonces: new Set<string>(),
    requiredEvidencePresent: (ref: string) => ref.startsWith('receipt://'),
    gideonVerdict: 'pass',
    vfsEvidenceOk: true,
    ...overrides,
  };
}

describe('sentinel decision service', () => {
  it('approves a valid, unexpired manifest with all evidence present', () => {
    const r = verifyManifest(makeManifest(), makeCtx());
    expect(r.approved).toBe(true);
    expect(r.reasons).toEqual([]);
  });

  it('rejects an expired manifest', () => {
    const ctx = makeCtx({ now: () => new Date('2026-08-14T15:00:00Z') });
    const r = verifyManifest(
      makeManifest({ expiresAt: '2026-08-14T14:00:00Z' }),
      ctx,
    );
    expect(r.approved).toBe(false);
    expect(r.reasons).toContain('manifest_expired');
  });

  it('rejects when required evidence is missing', () => {
    const r = verifyManifest(makeManifest(), makeCtx({
      requiredEvidencePresent: () => false,
    }));
    expect(r.approved).toBe(false);
    expect(r.reasons).toContain('required_evidence_missing');
  });

  it('rejects when Gideon verdict is fail or unavailable', () => {
    for (const verdict of ['fail', 'unavailable'] as const) {
      const r = verifyManifest(makeManifest(), makeCtx({ gideonVerdict: verdict }));
      expect(r.approved).toBe(false);
      expect(r.reasons).toContain('gideon_verdict_not_pass');
    }
  });

  it('rejects when VFS evidence is not ok', () => {
    const r = verifyManifest(makeManifest(), makeCtx({ vfsEvidenceOk: false }));
    expect(r.approved).toBe(false);
    expect(r.reasons).toContain('vfs_evidence_not_ok');
  });

  it('rejects a replayed one-time nonce', () => {
    const seen = new Set<string>(['nonce-1']);
    const r = verifyManifest(makeManifest(), makeCtx({ seenNonces: seen }));
    expect(r.approved).toBe(false);
    expect(r.reasons).toContain('nonce_replayed');
  });

  it('issues a lease that verifies once and can be revoked', () => {
    vi.useFakeTimers();
    try {
      const lease = issueLease('eff_01J', 5_000);
      expect(getLease(lease.leaseId)?.manifestId).toBe('eff_01J');
      expect(revokeLease(lease.leaseId)).toBe(true);
      expect(getLease(lease.leaseId)).toBeUndefined();
      expect(revokeLease(lease.leaseId)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });
});
