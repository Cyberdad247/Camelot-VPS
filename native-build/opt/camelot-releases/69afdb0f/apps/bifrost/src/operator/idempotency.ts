// SPDX-License-Identifier: MIT

import { createHash } from 'node:crypto';

export type IdempotencyStatus = 'IN_FLIGHT' | 'COMPLETED' | 'COMMITTED' | 'REJECTED';
export type IdempotencyDecision = 'PROCEED' | 'REPLAY' | 'CONFLICT' | 'REJECTED';

export interface IdempotencyRecord {
  key: string;
  tenantId: string;
  manifestHash: string;
  correlationId: string;
  status: IdempotencyStatus;
  receiptRef?: string;
  responseBody?: string;
  expiresAt: number; // Unix timestamp in ms
  createdAt: number;
  updatedAt: number;
}

export class IdempotencyConflictError extends Error {
  public readonly statusCode = 409;
  public readonly errorCode = 'IDEMPOTENCY_CONFLICT';
  public readonly retryAfterSec: number;

  constructor(
    public readonly key: string,
    public readonly tenantId: string,
    public readonly correlationId: string,
    retryAfterSec = 5,
    message?: string,
  ) {
    super(
      message ??
        `Operation '${key}' under tenant '${tenantId}' is already IN_FLIGHT (correlation: '${correlationId}').`,
    );
    this.name = 'IdempotencyConflictError';
    this.retryAfterSec = Math.max(1, retryAfterSec);
  }
}

export class IdempotencyPayloadMismatchError extends Error {
  public readonly statusCode = 422;
  public readonly errorCode = 'IDEMPOTENCY_PAYLOAD_MISMATCH';

  constructor(
    public readonly key: string,
    public readonly tenantId: string,
    public readonly existingHash: string,
    public readonly newHash: string,
  ) {
    super(
      `IDEMPOTENCY_PAYLOAD_MISMATCH: Key '${key}' for tenant '${tenantId}' was previously bound ` +
        `to manifest '${existingHash}', cannot execute with '${newHash}'.`,
    );
    this.name = 'IdempotencyPayloadMismatchError';
  }
}

/** Compute deterministic SHA-256 compound key: SHA256(client_key || tenant_id || manifest_hash). */
export function computeCompoundKey(key: string, tenantId: string, manifestHash: string): string {
  return createHash('sha256')
    .update(`${key}:${tenantId}:${manifestHash}`, 'utf8')
    .digest('hex');
}

/** FastMutex in-memory accelerator (tau <= 10s). */
export class FastMutexAccelerator {
  private locks = new Map<string, number>();

  constructor(private readonly defaultTtlMs = 10_000) {}

  tryAcquire(tenantId: string, key: string, ttlMs?: number): boolean {
    const lockId = `${tenantId}:${key}`;
    const now = Date.now();
    const ttl = Math.min(ttlMs ?? this.defaultTtlMs, 10_000);
    const existingExp = this.locks.get(lockId);
    if (existingExp && existingExp > now) {
      return false;
    }
    this.locks.set(lockId, now + ttl);
    return true;
  }

  release(tenantId: string, key: string): void {
    const lockId = `${tenantId}:${key}`;
    this.locks.delete(lockId);
  }

  isLocked(tenantId: string, key: string): boolean {
    const lockId = `${tenantId}:${key}`;
    const now = Date.now();
    const exp = this.locks.get(lockId);
    if (!exp) return false;
    if (exp <= now) {
      this.locks.delete(lockId);
      return false;
    }
    return true;
  }
}

/** In-memory and WAL-compatible Idempotency store for bifrost_idempotency_journal. */
export class InMemoryIdempotencyStore {
  private records = new Map<string, IdempotencyRecord>();

  private makeId(tenantId: string, key: string): string {
    return `${tenantId}:${key}`;
  }

  get(tenantId: string, key: string): IdempotencyRecord | undefined {
    return this.records.get(this.makeId(tenantId, key));
  }

  insertInFlight(rec: IdempotencyRecord): boolean {
    const id = this.makeId(rec.tenantId, rec.key);
    const existing = this.records.get(id);
    const now = Date.now();
    if (existing) {
      if (existing.status === 'REJECTED' || existing.expiresAt <= now) {
        this.records.delete(id);
      } else {
        return false;
      }
    }
    this.records.set(id, rec);
    return true;
  }

  updateStatus(
    tenantId: string,
    key: string,
    status: IdempotencyStatus,
    receiptRef?: string,
    responseBody?: string,
  ): IdempotencyRecord | undefined {
    const id = this.makeId(tenantId, key);
    const existing = this.records.get(id);
    if (!existing) return undefined;
    const updated: IdempotencyRecord = {
      ...existing,
      status,
      receiptRef: receiptRef ?? existing.receiptRef,
      responseBody: responseBody ?? existing.responseBody,
      updatedAt: Date.now(),
    };
    this.records.set(id, updated);
    return updated;
  }

  purgeExpired(): number {
    const now = Date.now();
    let count = 0;
    for (const [k, v] of this.records.entries()) {
      if (v.expiresAt <= now) {
        this.records.delete(k);
        count++;
      }
    }
    return count;
  }
}

/** TypeScript Idempotency Guardian coordinating FastMutex and Storage. */
export class IdempotencyGuardian {
  constructor(
    private readonly store = new InMemoryIdempotencyStore(),
    private readonly fastMutex = new FastMutexAccelerator(),
  ) {}

  acquireOrReplay(
    key: string,
    tenantId: string,
    manifestHash: string,
    correlationId: string,
    ttlMs = 300_000,
  ): { decision: IdempotencyDecision; record?: IdempotencyRecord } {
    const now = Date.now();

    // 1. Assert existing record in journal
    const existing = this.store.get(tenantId, key);
    if (existing) {
      // Payload mismatch rule (HTTP 422)
      if (existing.manifestHash !== manifestHash) {
        if (existing.expiresAt > now && existing.status !== 'REJECTED') {
          throw new IdempotencyPayloadMismatchError(key, tenantId, existing.manifestHash, manifestHash);
        } else {
          this.store.purgeExpired();
        }
      } else if (existing.expiresAt <= now) {
        this.store.purgeExpired();
      } else if (existing.status === 'COMPLETED' || existing.status === 'COMMITTED') {
        this.fastMutex.release(tenantId, key);
        return { decision: 'REPLAY', record: existing };
      } else if (existing.status === 'IN_FLIGHT') {
        const retrySec = Math.max(1, Math.round((existing.expiresAt - now) / 1000));
        throw new IdempotencyConflictError(key, tenantId, existing.correlationId, retrySec);
      }
    }

    // 2. FastMutex check (<10s)
    if (!this.fastMutex.tryAcquire(tenantId, key, Math.min(ttlMs, 10_000))) {
      const ex = this.store.get(tenantId, key);
      const cid = ex?.correlationId ?? correlationId;
      const retrySec = Math.max(1, Math.round(((ex?.expiresAt ?? now + 5000) - now) / 1000));
      throw new IdempotencyConflictError(key, tenantId, cid, retrySec, 'FastMutex burst collision');
    }

    // 3. Register IN_FLIGHT
    const rec: IdempotencyRecord = {
      key,
      tenantId,
      manifestHash,
      correlationId,
      status: 'IN_FLIGHT',
      expiresAt: now + ttlMs,
      createdAt: now,
      updatedAt: now,
    };

    const inserted = this.store.insertInFlight(rec);
    if (!inserted) {
      const ex = this.store.get(tenantId, key);
      const cid = ex?.correlationId ?? correlationId;
      const retrySec = Math.max(1, Math.round(((ex?.expiresAt ?? now + 5000) - now) / 1000));
      throw new IdempotencyConflictError(key, tenantId, cid, retrySec, 'Durable store collision');
    }

    return { decision: 'PROCEED', record: rec };
  }

  commit(
    key: string,
    tenantId: string,
    manifestHash: string,
    receiptRef: string,
    responseBody?: unknown,
  ): IdempotencyRecord {
    const existing = this.store.get(tenantId, key);
    if (existing && existing.manifestHash !== manifestHash) {
      throw new IdempotencyPayloadMismatchError(key, tenantId, existing.manifestHash, manifestHash);
    }

    const serialized =
      responseBody !== undefined
        ? typeof responseBody === 'string'
          ? responseBody
          : JSON.stringify(responseBody)
        : undefined;

    const updated = this.store.updateStatus(tenantId, key, 'COMPLETED', receiptRef, serialized);
    this.fastMutex.release(tenantId, key);
    if (!updated) {
      throw new Error(`No idempotency record found to commit for key: ${key} under tenant ${tenantId}`);
    }
    return updated;
  }

  reject(key: string, tenantId: string, manifestHash: string, reason?: string): IdempotencyRecord {
    const updated = this.store.updateStatus(tenantId, key, 'REJECTED', undefined, reason);
    this.fastMutex.release(tenantId, key);
    if (!updated) {
      throw new Error(`No idempotency record found to reject for key: ${key} under tenant ${tenantId}`);
    }
    return updated;
  }
}
