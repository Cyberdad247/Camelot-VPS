// SPDX-License-Identifier: MIT

import { payloadHash } from './chain';

export interface NewOperatorEvent {
  eventId: string;
  taskId: string;
  correlationId: string;
  timestamp: string;
  actorId: string;
  actorRole: string;
  kind: string;
  payload: Record<string, unknown>;
  integrity: 'verified' | 'pending_anchor' | 'unavailable' | 'integrity_failed';
  /** Optional explicit link (used by the tamper test); defaults to the task's last hash. */
  parentHash?: string;
}

export interface StoredEvent extends NewOperatorEvent {
  payloadHash: string;
  parentHash?: string;
}

export interface ChainVerification {
  valid: boolean;
  length: number;
  brokenAt?: string; // eventId where the link broke
}

/** Storage contract — Prisma-backed in production, in-memory in tests. */
export interface EventStore {
  append(evt: NewOperatorEvent): Promise<StoredEvent>;
  listByTask(taskId: string, limit?: number): Promise<StoredEvent[]>;
  verifyChain(taskId: string): Promise<ChainVerification>;
}

/**
 * In-memory store used by unit tests and by the `--fixture` harness mode.
 * Mirrors the Prisma-backed store's append-only + hash-chain semantics.
 */
export class InMemoryEventStore implements EventStore {
  private rows: StoredEvent[] = [];

  async append(evt: NewOperatorEvent): Promise<StoredEvent> {
    const last = (await this.listByTask(evt.taskId, 1))[0];
    const stored: StoredEvent = {
      ...evt,
      payloadHash: payloadHash(evt.payload),
      parentHash: evt.parentHash ?? last?.payloadHash,
    };
    this.rows.push(stored);
    return stored;
  }

  async listByTask(taskId: string, limit = 50): Promise<StoredEvent[]> {
    return this.rows
      .filter((r) => r.taskId === taskId)
      .slice(-limit)
      .reverse();
  }

  async verifyChain(taskId: string): Promise<ChainVerification> {
    const rows = (await this.listByTask(taskId, 1000)).reverse();
    let expectedParent: string | undefined;
    for (const row of rows) {
      if (row.parentHash !== expectedParent) {
        return { valid: false, length: rows.length, brokenAt: row.eventId };
      }
      expectedParent = row.payloadHash;
    }
    return { valid: true, length: rows.length };
  }
}

/**
 * Prisma-backed append-only store over the `OperatorEvent` model.
 * Lazy client binding: constructed with an injected client for tests, or
 * creates the generated client on first use in production.
 */
export function createPrismaEventStore(prisma?: unknown): EventStore {
  let client: {
    operatorEvent: {
      create(data: unknown): Promise<unknown>;
      findMany(args: unknown): Promise<Array<Record<string, unknown>>>;
    };
  } = prisma as never;
  if (!client) {
    // Lazy require keeps import-time side effects off the operator plane.
    // The generated client is at src/generated/client (see server.ts usage).
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { PrismaClient } = require('../generated/client');
    client = new PrismaClient();
  }
  return {
    async append(evt: NewOperatorEvent): Promise<StoredEvent> {
      const last = (await this.listByTask(evt.taskId, 1))[0];
      const stored: StoredEvent = {
        ...evt,
        payloadHash: payloadHash(evt.payload),
        parentHash: evt.parentHash ?? last?.payloadHash,
      };
      await client.operatorEvent.create({
        data: {
          eventId: stored.eventId,
          taskId: stored.taskId,
          correlationId: stored.correlationId,
          timestamp: stored.timestamp,
          actorId: stored.actorId,
          actorRole: stored.actorRole,
          kind: stored.kind,
          payload: JSON.stringify(stored.payload),
          payloadHash: stored.payloadHash,
          parentHash: stored.parentHash,
          integrity: stored.integrity,
        },
      });
      return stored;
    },
    async listByTask(taskId: string, limit = 50): Promise<StoredEvent[]> {
      const rows = (await client.operatorEvent.findMany({
        where: { taskId },
        orderBy: { createdAt: 'desc' },
        take: limit,
      })) as Array<Record<string, unknown>>;
      return rows.map((r) => ({
        eventId: String(r.eventId),
        taskId: String(r.taskId),
        correlationId: String(r.correlationId),
        timestamp: String(r.timestamp),
        actorId: String(r.actorId),
        actorRole: String(r.actorRole),
        kind: String(r.kind),
        payload: JSON.parse(String(r.payload ?? '{}')),
        payloadHash: String(r.payloadHash),
        parentHash: r.parentHash == null ? undefined : String(r.parentHash),
        integrity: String(r.integrity) as StoredEvent['integrity'],
      }));
    },
    async verifyChain(taskId: string): Promise<ChainVerification> {
      const rows = (await this.listByTask(taskId, 1000)).reverse();
      let expectedParent: string | undefined;
      for (const row of rows) {
        if (row.parentHash !== expectedParent) {
          return { valid: false, length: rows.length, brokenAt: row.eventId };
        }
        expectedParent = row.payloadHash;
      }
      return { valid: true, length: rows.length };
    },
  };
}
