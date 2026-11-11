// SPDX-License-Identifier: MIT

import { describe, expect, it } from 'vitest';
import { InMemoryEventStore } from './receipts';

function makeEvt(taskId: string, kind: string, payload: Record<string, unknown>, idx: number) {
  return {
    eventId: `evt_${taskId}_${idx}`,
    taskId,
    correlationId: `cor_${taskId}`,
    timestamp: `2026-08-14T13:4${idx}:00Z`,
    actorId: 'sir_gideon',
    actorRole: 'gideon' as const,
    kind,
    payload,
    integrity: 'verified' as const,
  };
}

describe('receipt event store', () => {
  it('is append-only and links parent hashes per task', async () => {
    const store = new InMemoryEventStore();
    await store.append(makeEvt('t1', 'diff.verified', { diffSha256: 'sha256:a' }, 0));
    await store.append(makeEvt('t1', 'test.passed', { runId: 'r1' }, 1));
    await store.append(makeEvt('t2', 'diff.verified', { diffSha256: 'sha256:b' }, 0));

    const t1 = await store.listByTask('t1');
    expect(t1).toHaveLength(2);
    // listByTask returns newest-first: the newest event chains to the oldest.
    expect(t1[0]!.parentHash).toBe(t1[1]!.payloadHash);
    expect(t1[1]!.parentHash).toBeUndefined();
    // Task 2's events do not chain across tasks.
    const t2 = await store.listByTask('t2');
    expect(t2[0]!.parentHash).toBeUndefined();
  });

  it('computePayloadHash hashes canonical payload', async () => {
    const store = new InMemoryEventStore();
    const evt = makeEvt('t3', 'receipt.signed', { decision: 'approve' }, 0);
    const stored = await store.append(evt);
    expect(stored.payloadHash).toMatch(/^sha256:[0-9a-f]{64}$/);
  });

  it('verifyChain is true for an unbroken chain and false when tampered', async () => {
    const store = new InMemoryEventStore();
    await store.append(makeEvt('t4', 'a', { n: 1 }, 0));
    await store.append(makeEvt('t4', 'b', { n: 2 }, 1));
    const ok = await store.verifyChain('t4');
    expect(ok).toMatchObject({ valid: true, length: 2 });

    // Simulate an append that ignored the parent hash.
    const store2 = new InMemoryEventStore();
    await store2.append(makeEvt('t5', 'a', { n: 1 }, 0));
    await store2.append({ ...makeEvt('t5', 'b', { n: 2 }, 1), parentHash: 'sha256:forged' });
    const bad = await store2.verifyChain('t5');
    expect(bad.valid).toBe(false);
  });
});
