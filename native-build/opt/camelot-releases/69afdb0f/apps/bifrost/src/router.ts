// SPDX-License-Identifier: MIT

// HYBRID_VOICE_ASSISTANT_vMAX · //ROUTE + //REZERO
// Local-first router. Known commands run on LOCAL_TOOLS (fast path); unknown /
// complex utterances bypass to REMOTE_MCP over Tailscale. If the remote path
// fails, is untrusted, or breaches the latency budget -> //REZERO to local.

import { type CallOptions, CompilationError, callRemoteMcp } from './mcp';
import { type Command, parseCommand } from './nlp';

export type Lane = 'LOCAL_TOOLS' | 'REMOTE_MCP';

export interface RouteOutcome {
  lane: Lane;
  command: Command;
  /** Remote MCP answer; null for pure-local state commands. */
  response: string | null;
  rezeroed: boolean;
  reason?: string;
  latencyMs: number;
}

export interface RouterConfig {
  /** Remote MCP endpoint — MUST be a Tailscale URL (validated downstream). */
  remoteMcpUrl?: string;
  /** Total latency budget for the remote bypass (< 1s mandate). */
  budgetMs?: number;
  /** Injectable caller (defaults to the Tailscale-guarded MCP client). */
  caller?: (endpoint: string, query: string, opts?: CallOptions) => Promise<{ answer: string }>;
  now?: () => number;
}

// LOCAL_FIRST_ISOLATION: anchor known actions to local; unknown -> remote bypass.
export function classify(command: Command): Lane {
  return command.action === 'unknown' ? 'REMOTE_MCP' : 'LOCAL_TOOLS';
}

export async function route(raw: string, cfg: RouterConfig = {}): Promise<RouteOutcome> {
  const now = cfg.now ?? Date.now;
  const start = now();
  const command = parseCommand(raw);
  const lane = classify(command);

  if (lane === 'LOCAL_TOOLS') {
    return { lane, command, response: null, rezeroed: false, latencyMs: now() - start };
  }

  // REMOTE_MCP bypass — Tailscale only, budgeted, //REZERO on any failure.
  const budgetMs = cfg.budgetMs ?? 900;
  const caller = cfg.caller ?? callRemoteMcp;

  if (!cfg.remoteMcpUrl) {
    return rezero(command, 'no remote MCP configured', start, now);
  }

  try {
    const { answer } = await caller(cfg.remoteMcpUrl, raw, { timeoutMs: budgetMs });
    return {
      lane: 'REMOTE_MCP',
      command,
      response: answer,
      rezeroed: false,
      latencyMs: now() - start,
    };
  } catch (err) {
    const reason =
      err instanceof CompilationError
        ? `untrusted endpoint: ${err.message}`
        : `remote failure: ${(err as Error).message}`;
    return rezero(command, reason, start, now);
  }
}

// //REZERO -> collapse back to the local tools lane.
function rezero(command: Command, reason: string, start: number, now: () => number): RouteOutcome {
  return {
    lane: 'LOCAL_TOOLS',
    command,
    response: null,
    rezeroed: true,
    reason,
    latencyMs: now() - start,
  };
}
