// SPDX-License-Identifier: MIT

import type { Command, KbaDomain } from './nlp';

// Microcubic swarm lifecycle, surfaced to the PWA alongside business metrics.
export interface SwarmStatus {
  active: boolean;
  tasks: number;
  completed: number;
}

// Omni-Voice D.A.G. decision for the latest utterance: which lane the router
// took (runic bypass vs. Softmax persona) and with what confidence. Mirrors the
// subset of `routeOmniVoice()` that the voice HUD renders.
export interface OmniVoiceTelemetry {
  status: string;
  path: string;
  knight: string | null;
  tau: number | null;
  confidence: number | null;
  /** Rune a deterministic bypass delegated to; null on the Softmax lane. */
  delegatesRune: string | null;
}

// Unified, in-memory business metrics broadcast to the PWA as STATE_UPDATE.
export interface SovereignState {
  portfolioValuation: number;
  transactionsCount: number;
  // KBA Cartridge counters — incremented on every /api/bifrost/hitl dispatch
  // whose `route("kba KBA_<DOMAIN>_<id>")` parses to `action: 'kba'`.
  kbaActionsCount: number;
  kbaActionsByDomain: Record<KbaDomain, number>;
  lastKbaDomain: KbaDomain | null;
  lastCommand: string | null;
  // Remote MCP answer for the latest utterance; null for pure-local commands.
  lastResponse: string | null;
  // vMAX telemetry: which lane served the last utterance + server route time.
  lastLane: string | null;
  lastLatencyMs: number | null;
  lastRezeroed: boolean;
  // Omni-Voice D.A.G. ingress routing decision for the latest utterance.
  lastOmniVoice: OmniVoiceTelemetry | null;
  updatedAt: string;
  swarm: SwarmStatus;
}

// Placeholder baseline ($14.2M) — demo only, NOT real financial data.
export const BASELINE_VALUATION = 14_200_000;

export const state: SovereignState = {
  portfolioValuation: BASELINE_VALUATION,
  transactionsCount: 0,
  kbaActionsCount: 0,
  kbaActionsByDomain: {
    sync: 0,
    audit: 0,
    reroute: 0,
    rezero: 0,
    heal: 0,
    nano: 0,
    scan: 0,
    forge: 0,
  },
  lastKbaDomain: null,
  lastCommand: null,
  lastResponse: null,
  lastLane: null,
  lastLatencyMs: null,
  lastRezeroed: false,
  lastOmniVoice: null,
  updatedAt: new Date().toISOString(),
  swarm: { active: false, tasks: 0, completed: 0 },
};

/**
 * Apply a parsed command to the in-memory state (pure w.r.t. the DB).
 * Returns the mutated state so callers can broadcast it.
 */
export function applyCommand(cmd: Command, s: SovereignState = state): SovereignState {
  if (cmd.action === 'add_transaction') {
    s.portfolioValuation += cmd.amount;
    s.transactionsCount += 1;
  } else if (cmd.action === 'kba') {
    return applyKbaAction(cmd, s);
  }
  s.lastCommand = cmd.action;
  s.updatedAt = new Date().toISOString();
  return s;
}

/**
 * Apply a KBA-domain action. Increments the universal counter plus the
 * per-domain counter, and stamps lastKbaDomain. Pulled out of applyCommand
 * so KBA Cartridge v1002+ can inject per-verb MicrocubicMatrix side-effects
 * without bloating the main applyCommand dispatch.
 */
function applyKbaAction(
  cmd: Extract<Command, { action: 'kba' }>,
  s: SovereignState,
): SovereignState {
  s.kbaActionsCount += 1;
  s.kbaActionsByDomain[cmd.domain] += 1;
  s.lastKbaDomain = cmd.domain;
  s.lastCommand = cmd.action;
  s.updatedAt = new Date().toISOString();
  return s;
}

/** Record route telemetry (answer, lane, server latency, rezero) for the utterance. */
export function setRouteTelemetry(
  telemetry: { response: string | null; lane: string; latencyMs: number; rezeroed: boolean },
  s: SovereignState = state,
): SovereignState {
  s.lastResponse = telemetry.response;
  s.lastLane = telemetry.lane;
  s.lastLatencyMs = telemetry.latencyMs;
  s.lastRezeroed = telemetry.rezeroed;
  s.updatedAt = new Date().toISOString();
  return s;
}

/**
 * Record the Omni-Voice D.A.G. routing decision for the current utterance.
 *
 * Deliberately does NOT bump `updatedAt`. The client treats an `updatedAt`
 * change as "a reply is ready to speak", and a routing decision is a sub-signal
 * of the utterance rather than a reply of its own — so a `ᛟ_` control token
 * updates the HUD without triggering speech.
 */
export function setOmniVoiceTelemetry(
  telemetry: OmniVoiceTelemetry,
  s: SovereignState = state,
): SovereignState {
  s.lastOmniVoice = telemetry;
  return s;
}

export function snapshot(s: SovereignState = state): SovereignState {
  return { ...s, swarm: { ...s.swarm } };
}

