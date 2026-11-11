// SPDX-License-Identifier: MIT

// HYBRID_VOICE_ASSISTANT_vMAX · ZERO_TRUST_MESH
// Remote MCP client. Security mandate: remote executions MUST route exclusively
// through the encrypted Tailscale mesh. Any non-Tailscale endpoint throws a
// CompilationError (untrusted connection).

/** Thrown when a remote endpoint is outside the trusted Tailscale mesh. */
export class CompilationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CompilationError';
  }
}

// Tailscale CGNAT range 100.64.0.0/10 -> second octet 64..127.
const TS_CGNAT = /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}$/;
// MagicDNS names live under *.ts.net.
const TS_MAGICDNS = /\.ts\.net$/i;

export function isTailscaleHost(host: string): boolean {
  return TS_MAGICDNS.test(host) || TS_CGNAT.test(host);
}

/** Validate that a URL targets the Tailscale mesh, or throw CompilationError. */
export function assertTailscaleEndpoint(url: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new CompilationError(`Invalid MCP endpoint: ${url}`);
  }
  if (!isTailscaleHost(parsed.hostname)) {
    throw new CompilationError(
      `Untrusted connection: ${parsed.hostname} is not a Tailscale endpoint. Remote MCP must route exclusively through the encrypted Tailscale mesh.`,
    );
  }
  return parsed;
}

export interface HttpResponseLike {
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
}

export type FetchLike = (
  url: string,
  init: { method: string; headers: Record<string, string>; body: string; signal: AbortSignal },
) => Promise<HttpResponseLike>;

export interface CallOptions {
  timeoutMs?: number;
  fetchImpl?: FetchLike;
}

export interface McpResult {
  answer: string;
}

// Pull a text answer out of an MCP tools/call result (or a simple shape).
function extractAnswer(data: unknown): string {
  const d = data as {
    error?: { message?: string };
    result?: { content?: Array<{ type?: string; text?: string }> } | string;
    answer?: string;
  };
  if (d?.error) throw new Error(d.error.message ?? 'MCP error');

  const content = typeof d?.result === 'object' ? d.result?.content : undefined;
  if (Array.isArray(content)) {
    const text = content
      .filter((c) => c?.type === 'text' && typeof c.text === 'string')
      .map((c) => c.text)
      .join(' ')
      .trim();
    if (text) return text;
  }
  if (typeof d?.result === 'string') return d.result;
  if (typeof d?.answer === 'string') return d.answer;
  throw new Error('MCP response missing answer');
}

/**
 * Call a remote MCP server over the Tailscale mesh. The endpoint is validated
 * BEFORE any network access. Aborts after timeoutMs (the //REZERO latency gate).
 */
export async function callRemoteMcp(
  endpoint: string,
  query: string,
  opts: CallOptions = {},
): Promise<McpResult> {
  assertTailscaleEndpoint(endpoint); // zero-trust gate first — no untrusted I/O

  const timeoutMs = opts.timeoutMs ?? 900;
  const doFetch = opts.fetchImpl ?? (globalThis.fetch as unknown as FetchLike);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await doFetch(endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'tools/call',
        params: { name: 'query', arguments: { query } },
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`MCP HTTP ${res.status}`);
    return { answer: extractAnswer(await res.json()) };
  } finally {
    clearTimeout(timer);
  }
}
