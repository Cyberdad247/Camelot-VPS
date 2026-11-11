// SPDX-License-Identifier: MIT

import { Router, type Request, type Response } from 'express';
import { z } from 'zod';
import type { EventStore } from './receipts';
import {
  ActorRoleSchema,
  EvidenceIntegritySchema,
  type ActorRole,
  type EffectManifest,
  type EvidenceEnvelope,
  type OperatorTaskSnapshot,
  type DiffEvidence,
  type TestRunResult,
} from './contracts';
import type { VerifyContext, VerifyResult } from './sentinel';
import { verdictFor } from './gideon';
import { FIXTURES, snapshotFor, type FixtureName } from './fixtures';

// Keys are stored lowercase so the case-insensitive match (`k.toLowerCase()`)
// actually hits camelCase keys like `apiKey` (design §8.3 redact_sensitive_fields).
const SENSITIVE_KEYS = new Set(['secret', 'token', 'password', 'apikey', 'authorization']);

export function redactSensitive(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactSensitive);
  if (value !== null && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(record)) {
      if (SENSITIVE_KEYS.has(k.toLowerCase())) {
        out[k] = '[REDACTED]';
      } else {
        out[k] = redactSensitive(v);
      }
    }
    return out;
  }
  return value;
}

const DecisionBodySchema = z.object({
  decision: z.enum(['approve', 'deny']),
  reason: z.string().max(2000).optional(),
}).strict(); // .strict() rejects command/path/raw-diff smuggling (design §9)

const IngestEvidenceBodySchema = z.object({
  kind: z.string().min(1),
  actorId: z.string().min(1).default('boris'),
  actorRole: ActorRoleSchema.default('boris'),
  payload: z.record(z.string(), z.unknown()),
  receiptRef: z.string().optional(),
  integrity: EvidenceIntegritySchema.default('verified'),
});

export interface OperatorBffDeps {
  store: EventStore;
  verifyManifest: (manifest: EffectManifest, ctx: VerifyContext) => VerifyResult;
  issueLease: (manifestId: string, ttlMs?: number) => { leaseId: string };
  now: () => Date;
  requiredEvidencePresent: (ref: string) => boolean;
  gideonVerdict: () => 'pass' | 'fail' | 'pending' | 'unavailable';
  vfsEvidenceOk: () => boolean;
  broadcastWs?: (envelope: EvidenceEnvelope) => void;
}

function authorize(req: Request): boolean {
  const token = req.header('x-operator-token');
  return Boolean(token && process.env.OPERATOR_SESSION_TOKEN && token === process.env.OPERATOR_SESSION_TOKEN);
}

function auth(res: Response): void {
  res.status(401).json({ error: 'UNAUTHORIZED' });
}

/** Deterministic fixture snapshots driven by OPERATOR_FIXTURE_TASK
 * (defaults to the approval fixture). Fall back to the default fixture for
 * unknown task names rather than fabricating new state (design §18). */
function fixtureSnapshot(taskId: string): OperatorTaskSnapshot {
  const fixture = (process.env.OPERATOR_FIXTURE_TASK ?? 'operator-console-approval') as FixtureName;
  if (!FIXTURES.includes(fixture)) return snapshotFor(taskId, 'operator-console-approval');
  return snapshotFor(taskId, fixture);
}

// ── Live Dispatch Pub-Sub Spine ──────────────────────────────────────────
const subscribersByTask = new Map<string, Set<(envelope: EvidenceEnvelope) => void>>();

export function subscribeToTaskEvidence(taskId: string, fn: (envelope: EvidenceEnvelope) => void): () => void {
  let set = subscribersByTask.get(taskId);
  if (!set) {
    set = new Set();
    subscribersByTask.set(taskId, set);
  }
  set.add(fn);
  return () => {
    set?.delete(fn);
    if (set && set.size === 0) {
      subscribersByTask.delete(taskId);
    }
  };
}

export function broadcastTaskEvidence(
  taskId: string,
  envelope: EvidenceEnvelope,
  broadcastWs?: (e: EvidenceEnvelope) => void,
): void {
  const set = subscribersByTask.get(taskId);
  if (set) {
    for (const fn of set) {
      try {
        fn(envelope);
      } catch {
        // Keep other subscribers running despite individual failure
      }
    }
  }
  if (broadcastWs) {
    try {
      broadcastWs(envelope);
    } catch {
      // Ignore external ws broadcast errors
    }
  }
}

export function createOperatorBff(deps: OperatorBffDeps): Router {
  const router = Router();

  router.get('/session', (_req, res) => {
    res.json({ authenticated: Boolean(process.env.OPERATOR_SESSION_TOKEN) });
  });

  router.get('/tasks/:taskId/snapshot', (req, res) => {
    if (!authorize(req)) return auth(res);
    const taskId = req.params.taskId as string;
    const snapshot = redactSensitive(fixtureSnapshot(taskId)) as OperatorTaskSnapshot;
    void deps.store.verifyChain(taskId);
    res.json(snapshot);
  });

  // ── SSE Live Streaming Route ───────────────────────────────────────────
  router.get('/tasks/:taskId/events', (req, res) => {
    if (!authorize(req)) return auth(res);
    const taskId = req.params.taskId as string;
    res.setHeader('content-type', 'text/event-stream');
    res.setHeader('cache-control', 'no-cache');
    res.setHeader('connection', 'keep-alive');
    res.flushHeaders();

    // 1. Initial full snapshot
    const first = redactSensitive(fixtureSnapshot(taskId)) as OperatorTaskSnapshot;
    res.write(`event: operator.evidence\ndata: ${JSON.stringify({ type: 'snapshot', payload: first })}\n\n`);

    // 2. Subscribe to live streamed operator-evidence/1 envelopes
    const unsubscribe = subscribeToTaskEvidence(taskId, (envelope) => {
      const redacted = redactSensitive(envelope) as EvidenceEnvelope;
      res.write(`event: operator.evidence\ndata: ${JSON.stringify({ type: 'evidence', payload: redacted })}\n\n`);
    });

    const timer = setInterval(() => res.write(': keepalive\n\n'), 15_000);
    req.on('close', () => {
      clearInterval(timer);
      unsubscribe();
    });
  });

  // ── Ingest Evidence Envelope Route ────────────────────────────────────
  router.post('/tasks/:taskId/evidence', async (req, res) => {
    if (!authorize(req)) return auth(res);
    const taskId = req.params.taskId as string;
    const parsed = IngestEvidenceBodySchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({ error: 'INVALID_EVIDENCE_BODY', issues: parsed.error.issues });
    }
    const { kind, actorId, actorRole, payload, receiptRef, integrity } = parsed.data;
    const redactedPayload = redactSensitive(payload) as Record<string, unknown>;
    const eventId = `evt_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

    const stored = await deps.store.append({
      eventId,
      taskId,
      correlationId: `cor_${taskId}`,
      timestamp: deps.now().toISOString(),
      actorId,
      actorRole,
      kind,
      payload: redactedPayload,
      integrity,
    });

    const envelope: EvidenceEnvelope = {
      schemaVersion: 'operator-evidence/1',
      eventId: stored.eventId,
      taskId: stored.taskId,
      correlationId: stored.correlationId,
      timestamp: stored.timestamp,
      actor: { id: stored.actorId, role: stored.actorRole as ActorRole },
      kind: stored.kind,
      payload: stored.payload,
      payloadHash: stored.payloadHash,
      parentHash: stored.parentHash,
      integrity: stored.integrity,
      receiptRef: receiptRef ?? `receipt://operator/${stored.kind}/${stored.eventId}`,
    };

    broadcastTaskEvidence(taskId, envelope, deps.broadcastWs);
    res.status(201).json({ status: 'RECORDED', envelope });
  });

  // ── Gideon Evaluation Dispatch Route ──────────────────────────────────
  router.post('/tasks/:taskId/gideon/evaluate', async (req, res) => {
    if (!authorize(req)) return auth(res);
    const taskId = req.params.taskId as string;
    const snapshot = fixtureSnapshot(taskId);
    const diff = (req.body?.diff ?? snapshot.diffs[0]) as DiffEvidence | undefined;
    const testRuns = (req.body?.tests ?? snapshot.tests) as TestRunResult[];

    if (!diff) {
      return res.status(400).json({ error: 'NO_DIFF_FOUND_FOR_EVALUATION' });
    }

    const verdict = verdictFor(diff, testRuns);
    const passed = verdict === 'pass';
    const eventId = `evt_gideon_${Date.now()}`;

    const stored = await deps.store.append({
      eventId,
      taskId,
      correlationId: snapshot.correlationId,
      timestamp: deps.now().toISOString(),
      actorId: 'gideon',
      actorRole: 'gideon',
      kind: 'gideon.verdict',
      payload: {
        verdict,
        diffSha256: diff.diffSha256,
        passed,
        testsEvaluated: testRuns.length,
        allTestsPassed: testRuns.every((t) => t.status === 'passed'),
      },
      integrity: 'verified',
    });

    const envelope: EvidenceEnvelope = {
      schemaVersion: 'operator-evidence/1',
      eventId: stored.eventId,
      taskId: stored.taskId,
      correlationId: stored.correlationId,
      timestamp: stored.timestamp,
      actor: { id: 'gideon', role: 'gideon' },
      kind: 'gideon.verdict',
      payload: stored.payload,
      payloadHash: stored.payloadHash,
      parentHash: stored.parentHash,
      integrity: stored.integrity,
      receiptRef: `receipt://gideon/verdict/${stored.eventId}`,
    };

    broadcastTaskEvidence(taskId, envelope, deps.broadcastWs);
    res.status(200).json({ status: 'EVALUATED', verdict, envelope });
  });

  // ── Sentinel Decision Dispatch Route ──────────────────────────────────
  router.post('/effect-manifests/:manifestId/decision', async (req, res) => {
    if (!authorize(req)) return auth(res);
    const parsed = DecisionBodySchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({ error: 'INVALID_DECISION_BODY', issues: parsed.error.issues });
    }
    const { decision, reason } = parsed.data;
    const manifestId = req.params.manifestId as string;

    if (decision === 'deny') {
      const stored = await deps.store.append({
        eventId: `evt_deny_${Date.now()}`,
        taskId: 'task_fixture',
        correlationId: 'cor_fixture',
        timestamp: deps.now().toISOString(),
        actorId: 'sentinel',
        actorRole: 'sentinel',
        kind: 'decision.denied',
        payload: { manifestId, reason },
        integrity: 'verified',
      });

      const envelope: EvidenceEnvelope = {
        schemaVersion: 'operator-evidence/1',
        eventId: stored.eventId,
        taskId: stored.taskId,
        correlationId: stored.correlationId,
        timestamp: stored.timestamp,
        actor: { id: 'sentinel', role: 'sentinel' },
        kind: 'decision.denied',
        payload: stored.payload,
        payloadHash: stored.payloadHash,
        parentHash: stored.parentHash,
        integrity: stored.integrity,
        receiptRef: `receipt://sentinel/decision/${stored.eventId}`,
      };
      broadcastTaskEvidence(stored.taskId, envelope, deps.broadcastWs);

      return res.status(200).json({ status: 'DENIED', manifestId, envelope });
    }

    const manifest: EffectManifest = {
      schemaVersion: 'effect-manifest/1',
      manifestId,
      taskId: 'task_fixture',
      correlationId: 'cor_fixture',
      kind: 'worktree.patch.promote',
      baseRevision: 'base', candidateRevision: 'cand',
      diffSha256: 'sha256:abc',
      allowedPaths: ['apps/pwa/src/components/operator_console/**'],
      requiredEvidence: ['receipt://vfs/no-escape/1'],
      policyClass: 'engineering.write',
      expiresAt: new Date(deps.now().getTime() + 60_000).toISOString(),
      oneTimeNonce: `nonce_${Date.now()}`,
      // v1.2 fields per §5.5/§11.1 of the SADD
      effectClass: 'workspace.patch',
      declaredRiskTier: 'T2',
      declarationHash: 'sha256:' + 'a'.repeat(64),
    };
    const verdict = deps.verifyManifest(manifest, {
      now: deps.now,
      seenNonces: new Set<string>(),
      requiredEvidencePresent: deps.requiredEvidencePresent,
      gideonVerdict: deps.gideonVerdict(),
      vfsEvidenceOk: deps.vfsEvidenceOk(),
    });
    if (!verdict.approved) {
      return res.status(403).json({ status: 'BLOCKED', reasons: verdict.reasons });
    }
    const lease = deps.issueLease(manifestId);
    const stored = await deps.store.append({
      eventId: `evt_approve_${Date.now()}`,
      taskId: 'task_fixture',
      correlationId: 'cor_fixture',
      timestamp: deps.now().toISOString(),
      actorId: 'sentinel',
      actorRole: 'sentinel',
      kind: 'decision.approved',
      payload: { manifestId, leaseId: lease.leaseId },
      integrity: 'verified',
    });

    const envelope: EvidenceEnvelope = {
      schemaVersion: 'operator-evidence/1',
      eventId: stored.eventId,
      taskId: stored.taskId,
      correlationId: stored.correlationId,
      timestamp: stored.timestamp,
      actor: { id: 'sentinel', role: 'sentinel' },
      kind: 'decision.approved',
      payload: stored.payload,
      payloadHash: stored.payloadHash,
      parentHash: stored.parentHash,
      integrity: stored.integrity,
      receiptRef: `receipt://sentinel/lease/${lease.leaseId}`,
    };
    broadcastTaskEvidence(stored.taskId, envelope, deps.broadcastWs);

    res.status(200).json({ status: 'APPROVED', manifestId, lease, envelope });
  });

  return router;
}
