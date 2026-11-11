// SPDX-License-Identifier: MIT

import type { DiffEvidence, TestRunResult } from './contracts';

export type GideonVerdict = 'pass' | 'fail' | 'pending' | 'unavailable';

export const GIDEON_UNAVAILABLE = {
  state: 'AUDIT_SUSPENDED',
  message: 'Gideon audit adapter unavailable; promotion and write approval blocked.',
  lastVerifiedTimestamp: null,
} as const;

/**
 * Deterministic verdict composition for slice #2. The real PEER Gideon
 * adapter (design §17 Q2) replaces the body when it ships; the contract —
 * returning one of the four verdicts and never crashing on outage — is the
 * stable surface the BFF and panels depend on.
 */
export function verdictFor(
  diff: DiffEvidence,
  testRuns: TestRunResult[],
  opts: { unavailable?: boolean } = {},
): GideonVerdict {
  if (opts.unavailable) return 'unavailable';
  if (testRuns.some((t) => t.status === 'failed')) return 'fail';
  if (testRuns.some((t) => t.status === 'passed') && testRuns.every((t) => t.status === 'passed')) {
    return 'pass';
  }
  return 'pending';
}
