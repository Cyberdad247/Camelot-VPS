// SPDX-License-Identifier: MIT

import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import express from 'express';
import { createOperatorBff, redactSensitive } from './bff';
import { InMemoryEventStore } from './receipts';
import { verifyManifest, issueLease } from './sentinel';
import type { EffectManifest } from './contracts';

let server: Server;
let base: string;

beforeAll(async () => {
  process.env.OPERATOR_SESSION_TOKEN = 'test-token';
  process.env.OPERATOR_FIXTURE_TASK = 'operator-console-approval';
  const app = express();
  app.use(express.json());
  const store = new InMemoryEventStore();
  const bff = createOperatorBff({
    store,
    verifyManifest,
    issueLease,
    now: () => new Date(),
    requiredEvidencePresent: (ref: string) => ref.startsWith('receipt://'),
    gideonVerdict: () => 'pass' as const,
    vfsEvidenceOk: () => true,
  });
  app.use('/v1/operator', bff);
  server = app.listen(0);
  await new Promise<void>((resolve) => server.once('listening', () => resolve()));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

describe('operator BFF', () => {
  it('rejects unauthenticated snapshot requests', async () => {
    const res = await fetch(`${base}/v1/operator/tasks/task_1/snapshot`);
    expect(res.status).toBe(401);
  });

  it('serves a typed task snapshot when authenticated', async () => {
    const res = await fetch(`${base}/v1/operator/tasks/task_1/snapshot`, {
      headers: { 'x-operator-token': 'test-token' },
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as { schemaVersion: string; integrity: string; taskGraph: unknown[] };
    expect(body.schemaVersion).toBe('operator-task-snapshot/1');
    expect(body.integrity).toBe('verified');
    expect(Array.isArray(body.taskGraph)).toBe(true);
  });

  it('redacts sensitive fields from snapshot payloads', async () => {
    const res = await fetch(`${base}/v1/operator/tasks/task_1/snapshot`, {
      headers: { 'x-operator-token': 'test-token' },
    });
    const text = await res.text();
    expect(text).not.toContain('super-secret');
  });

  it('redactSensitive masks secret/token/password/apiKey/authorization keys at any depth', () => {
    const out = redactSensitive({
      apiKey: 'k',
      visible: 1,
      nested: { token: 't', ok: true },
      list: [{ password: 'p' }, { authorization: 'bearer x' }],
    });
    expect(out).toEqual({
      apiKey: '[REDACTED]',
      visible: 1,
      nested: { token: '[REDACTED]', ok: true },
      list: [{ password: '[REDACTED]' }, { authorization: '[REDACTED]' }],
    });
  });

  it('accepts a manifest-scoped approve decision and returns a lease', async () => {
    const res = await fetch(`${base}/v1/operator/effect-manifests/eff_1/decision`, {
      method: 'POST',
      headers: { 'x-operator-token': 'test-token', 'content-type': 'application/json' },
      body: JSON.stringify({ decision: 'approve', reason: 'evidence verified' }),
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as { status: string; lease?: { leaseId: string } };
    expect(body.status).toBe('APPROVED');
    expect(body.lease?.leaseId).toBeTruthy();
  });

  it('rejects a decision body with extra command/path fields', async () => {
    const res = await fetch(`${base}/v1/operator/effect-manifests/eff_1/decision`, {
      method: 'POST',
      headers: { 'x-operator-token': 'test-token', 'content-type': 'application/json' },
      body: JSON.stringify({ decision: 'approve', command: 'rm -rf /', paths: ['/etc'] }),
    });
    expect(res.status).toBe(400);
  });

  it('exposes an SSE event stream', async () => {
    const controller = new AbortController();
    const res = await fetch(`${base}/v1/operator/tasks/task_1/events`, {
      headers: { 'x-operator-token': 'test-token' },
      signal: controller.signal,
    });
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/event-stream');
    // Close the stream so server.close() in afterAll can complete.
    controller.abort();
  });

  it('ingests an evidence envelope and redacts sensitive payload keys', async () => {
    const res = await fetch(`${base}/v1/operator/tasks/task_1/evidence`, {
      method: 'POST',
      headers: { 'x-operator-token': 'test-token', 'content-type': 'application/json' },
      body: JSON.stringify({
        kind: 'vfs.read.attestation',
        actorId: 'boris',
        actorRole: 'boris',
        payload: { path: 'apps/pwa/src/app.tsx', apiKey: 'secret-key-to-redact', status: 'verified' },
        receiptRef: 'receipt://vfs/attestation/01',
      }),
    });
    expect(res.status).toBe(201);
    const body = (await res.json()) as { status: string; envelope: { schemaVersion: string; kind: string; payload: Record<string, unknown>; receiptRef: string } };
    expect(body.status).toBe('RECORDED');
    expect(body.envelope.schemaVersion).toBe('operator-evidence/1');
    expect(body.envelope.kind).toBe('vfs.read.attestation');
    expect(body.envelope.receiptRef).toBe('receipt://vfs/attestation/01');
    expect(body.envelope.payload.apiKey).toBe('[REDACTED]');
    expect(body.envelope.payload.path).toBe('apps/pwa/src/app.tsx');
  });

  it('evaluates gideon verdict and dispatches an operator-evidence/1 envelope', async () => {
    const res = await fetch(`${base}/v1/operator/tasks/task_1/gideon/evaluate`, {
      method: 'POST',
      headers: { 'x-operator-token': 'test-token', 'content-type': 'application/json' },
      body: JSON.stringify({
        diff: {
          baseRevision: 'base',
          candidateRevision: 'cand',
          diffSha256: 'sha256:abc123',
          changedPaths: ['src/app.tsx'],
          addedLines: 10,
          removedLines: 2,
          generatedAt: new Date().toISOString(),
          gideonVerdict: 'pending',
        },
        tests: [{
          schemaVersion: 'test-run-result/1',
          runId: 'run_1',
          taskId: 'task_1',
          correlationId: 'cor_1',
          runner: 'boris-gideon-adapter',
          status: 'passed',
          startedAt: new Date().toISOString(),
          suites: [{ name: 'test-suite', status: 'passed', durationMs: 100 }],
          summary: { total: 1, passed: 1, failed: 0, skipped: 0 },
          outputHash: 'sha256:test_out',
        }],
      }),
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as { status: string; verdict: string; envelope: { kind: string; payload: Record<string, unknown> } };
    expect(body.status).toBe('EVALUATED');
    expect(body.verdict).toBe('pass');
    expect(body.envelope.kind).toBe('gideon.verdict');
    expect(body.envelope.payload.passed).toBe(true);
  });

  it('streams live evidence envelopes over SSE to connected clients', async () => {
    const controller = new AbortController();
    const res = await fetch(`${base}/v1/operator/tasks/task_live_sse/events`, {
      headers: { 'x-operator-token': 'test-token' },
      signal: controller.signal,
    });
    expect(res.status).toBe(200);

    const reader = res.body?.getReader();
    expect(reader).toBeDefined();

    // Read snapshot frame
    const firstChunk = await reader?.read();
    const firstText = new TextDecoder().decode(firstChunk?.value);
    expect(firstText).toContain('event: operator.evidence');
    expect(firstText).toContain('"type":"snapshot"');

    // Ingest new evidence while stream is active
    const postRes = await fetch(`${base}/v1/operator/tasks/task_live_sse/evidence`, {
      method: 'POST',
      headers: { 'x-operator-token': 'test-token', 'content-type': 'application/json' },
      body: JSON.stringify({
        kind: 'vfs.read.attestation',
        actorId: 'boris',
        payload: { path: 'apps/pwa/src/test.tsx', status: 'verified' },
        receiptRef: 'receipt://vfs/attestation/123',
      }),
    });
    expect(postRes.status).toBe(201);

    // Read next chunk from SSE stream
    const secondChunk = await reader?.read();
    const secondText = new TextDecoder().decode(secondChunk?.value);
    expect(secondText).toContain('event: operator.evidence');
    expect(secondText).toContain('"type":"evidence"');
    expect(secondText).toContain('vfs.read.attestation');
    expect(secondText).toContain('receipt://vfs/attestation/123');

    controller.abort();
  });
});
