// SPDX-License-Identifier: MIT

import { z } from 'zod';

export const ActorRoleSchema = z.enum([
  'operator', 'anya', 'merlin', 'hiveide', 'nano_knight',
  'sentinel', 'gideon', 'boris', 'herald', 'system',
]);
export type ActorRole = z.infer<typeof ActorRoleSchema>;

export const EvidenceIntegritySchema = z.enum([
  'verified', 'pending_anchor', 'unavailable', 'integrity_failed',
]);
export type EvidenceIntegrity = z.infer<typeof EvidenceIntegritySchema>;

/** v1.2 closed effect-class set per §5.5 of the SADD. */
export const EffectClassSchema = z.enum([
  'ro.fetch', 'ro.audit', 'internal.synth', 'workspace.test',
  'workspace.patch', 'promote.worktree.merge', 'promote.deploy',
  'external.publish.draft', 'external.publish.publish', 'external.email.send',
  'payment.invoice.draft', 'payment.invoice.issue', 'payment.capture',
  'payment.refund', 'device.calendar.write', 'device.sms.send',
  'device.call.initiate', 'promote.failover',
]);
export type EffectClass = z.infer<typeof EffectClassSchema>;

/** v1.2 risk tier per §5.5; cannot exceed Sentinel's classification. */
export const RiskTierSchema = z.enum(['T0', 'T1', 'T2', 'T3', 'T4']);
export type RiskTier = z.infer<typeof RiskTierSchema>;

export const ActorSchema = z.object({
  id: z.string().min(1),
  role: ActorRoleSchema,
});
export type Actor = z.infer<typeof ActorSchema>;

export const EvidenceEnvelopeSchema = z.object({
  schemaVersion: z.literal('operator-evidence/1'),
  eventId: z.string().min(1),
  taskId: z.string().min(1),
  correlationId: z.string().min(1),
  causationId: z.string().optional(),
  timestamp: z.string().min(1),
  actor: ActorSchema,
  kind: z.string().min(1),
  payload: z.record(z.string(), z.unknown()),
  payloadHash: z.string().min(1),
  parentHash: z.string().optional(),
  integrity: EvidenceIntegritySchema,
  receiptRef: z.string().optional(),
  ledgerAnchorRef: z.string().optional(),
});
export type EvidenceEnvelope = z.infer<typeof EvidenceEnvelopeSchema>;

export const EffectManifestSchema = z.object({
  schemaVersion: z.literal('effect-manifest/1'),
  manifestId: z.string().min(1),
  taskId: z.string().min(1),
  correlationId: z.string().min(1),
  kind: z.string().min(1),
  baseRevision: z.string().min(1),
  candidateRevision: z.string().min(1),
  diffSha256: z.string().min(1),
  allowedPaths: z.array(z.string()).default([]),
  requiredEvidence: z.array(z.string()).default([]),
  policyClass: z.string().min(1),
  expiresAt: z.string().min(1),
  oneTimeNonce: z.string().min(1),
  // v1.2 fields per §5.5/§11.1 of the SADD
  effectClass: EffectClassSchema,
  declaredRiskTier: RiskTierSchema,
  declarationHash: z.string().regex(/^sha256:[0-9a-fA-F]{64}$/),
});
export type EffectManifest = z.infer<typeof EffectManifestSchema>;

export const HaltDecisionSchema = z.object({
  schemaVersion: z.literal('halt-decision/1'),
  decision: z.enum(['continue', 'block_boot', 'await_hitl']),
  checkId: z.string().optional(),
  rejectionReasons: z.array(z.string()).default([]),
  issuedAt: z.string().min(1),
});
export type HaltDecision = z.infer<typeof HaltDecisionSchema>;

export const DiffEvidenceSchema = z.object({
  baseRevision: z.string().min(1),
  candidateRevision: z.string().min(1),
  diffSha256: z.string().min(1),
  changedPaths: z.array(z.string()).default([]),
  addedLines: z.number().int().nonnegative(),
  removedLines: z.number().int().nonnegative(),
  generatedAt: z.string().min(1),
  gideonVerdict: z.enum(['pass', 'fail', 'pending', 'unavailable']).default('pending'),
  receiptRef: z.string().optional(),
});
export type DiffEvidence = z.infer<typeof DiffEvidenceSchema>;

export const TestRunResultSchema = z.object({
  schemaVersion: z.literal('test-run-result/1'),
  runId: z.string().min(1),
  taskId: z.string().min(1),
  correlationId: z.string().min(1),
  runner: z.literal('boris-gideon-adapter'),
  status: z.enum(['passed', 'failed', 'cancelled', 'timed_out']),
  startedAt: z.string().min(1),
  completedAt: z.string().optional(),
  suites: z.array(z.object({
    name: z.string().min(1),
    status: z.enum(['passed', 'failed', 'skipped']),
    durationMs: z.number().nonnegative(),
    artifactRef: z.string().optional(),
  })).default([]),
  summary: z.object({
    total: z.number().int().nonnegative(),
    passed: z.number().int().nonnegative(),
    failed: z.number().int().nonnegative(),
    skipped: z.number().int().nonnegative(),
  }),
  outputHash: z.string().min(1),
  receiptRef: z.string().optional(),
});
export type TestRunResult = z.infer<typeof TestRunResultSchema>;

export const ReceiptSummarySchema = z.object({
  receiptId: z.string().min(1),
  eventId: z.string().min(1),
  taskId: z.string().min(1),
  correlationId: z.string().min(1),
  kind: z.string().min(1),
  timestamp: z.string().min(1),
  actor: ActorSchema,
  payloadHash: z.string().min(1),
  parentHash: z.string().optional(),
  integrity: EvidenceIntegritySchema,
});
export type ReceiptSummary = z.infer<typeof ReceiptSummarySchema>;

export const OperatorTaskSnapshotSchema = z.object({
  schemaVersion: z.literal('operator-task-snapshot/1'),
  taskId: z.string().min(1),
  correlationId: z.string().min(1),
  generatedAt: z.string().min(1),
  integrity: EvidenceIntegritySchema,
  intent: z.record(z.string(), z.unknown()),
  approval: z.record(z.string(), z.unknown()),
  taskGraph: z.array(z.record(z.string(), z.unknown())).default([]),
  diffs: z.array(DiffEvidenceSchema).default([]),
  tests: z.array(TestRunResultSchema).default([]),
  receipts: z.array(ReceiptSummarySchema).default([]),
});
export type OperatorTaskSnapshot = z.infer<typeof OperatorTaskSnapshotSchema>;
