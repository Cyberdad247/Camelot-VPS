// SPDX-License-Identifier: MIT

import { createHash } from 'node:crypto';

/** Stable, key-sorted JSON serialization (deterministic across key orders). */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(sortKeys(value));
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value !== null && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(record).sort()) out[key] = sortKeys(record[key]);
    return out;
  }
  return value;
}

/** `sha256:`-prefixed hex digest, matching the design's diffSha256 convention. */
export function sha256Hex(text: string): string {
  return `sha256:${createHash('sha256').update(text, 'utf8').digest('hex')}`;
}

/** Content hash of an arbitrary payload via canonical JSON. */
export function payloadHash(payload: unknown): string {
  return sha256Hex(canonicalJson(payload));
}
