// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import {
  EvidenceEnvelopeSchema,
  EffectManifestSchema,
  OperatorTaskSnapshotSchema,
  type EvidenceEnvelope,
  type EffectManifest,
} from './contracts';

describe('operator contracts', () => {
  it('parses a valid evidence envelope (operator-evidence/1)', () => {
    const envelope: EvidenceEnvelope = {
      schemaVersion: 'operator-evidence/1',
      eventId: 'evt_01J...',
      taskId: 'task_01J...',
      correlationId: 'cor_01J...',
      causationId: undefined,
      timestamp: '2026-08-14T13:48:00Z',
      actor: { id: 'sir_gideon', role: 'gideon' },
      kind: 'diff.verified',
      payload: { diffSha256: 'sha256:abc' },
      payloadHash: 'sha256:abc',
      parentHash: undefined,
      integrity: 'verified',
    };
    expect(EvidenceEnvelopeSchema.parse(envelope).schemaVersion).toBe('operator-evidence/1');
  });

  it('rejects an envelope with an unknown actor role', () => {
    const bad = {
      schemaVersion: 'operator-evidence/1',
      eventId: 'evt_1',
      taskId: 'task_1',
      correlationId: 'cor_1',
      timestamp: '2026-08-14T13:48:00Z',
      actor: { id: 'x', role: 'malware' },
      kind: 'diff.verified',
      payload: {},
      payloadHash: 'sha256:x',
      integrity: 'verified',
    };
    expect(() => EvidenceEnvelopeSchema.parse(bad)).toThrow();
  });

  it('parses a valid effect manifest (effect-manifest/1)', () => {
    const manifest: EffectManifest = {
      schemaVersion: 'effect-manifest/1',
      manifestId: 'eff_01J...',
      taskId: 'task_01J...',
      correlationId: 'cor_01J...',
      kind: 'worktree.patch.promote',
      baseRevision: 'git-sha-base',
      candidateRevision: 'git-sha-candidate',
      diffSha256: 'sha256:...',
      allowedPaths: ['apps/pwa/src/components/operator_console/**'],
      requiredEvidence: ['receipt://vfs/no-escape/...'],
      policyClass: 'engineering.write',
      expiresAt: '2026-08-14T14:05:00Z',
      oneTimeNonce: 'opaque-random-value',
      // v1.2 fields per §5.5/§11.1 of the SADD
      effectClass: 'workspace.patch',
      declaredRiskTier: 'T2',
      declarationHash: 'sha256:' + 'a'.repeat(64),
    };
    expect(EffectManifestSchema.parse(manifest).policyClass).toBe('engineering.write');
  });

  it('parses a valid task snapshot (operator-task-snapshot/1)', () => {
    const snapshot = OperatorTaskSnapshotSchema.parse({
      schemaVersion: 'operator-task-snapshot/1',
      taskId: 'task_01J...',
      correlationId: 'cor_01J...',
      generatedAt: '2026-08-14T13:48:00Z',
      integrity: 'verified',
      intent: {},
      approval: {},
      taskGraph: [],
      diffs: [],
      tests: [],
      receipts: [],
    });
    expect(snapshot.integrity).toBe('verified');
  });
});
