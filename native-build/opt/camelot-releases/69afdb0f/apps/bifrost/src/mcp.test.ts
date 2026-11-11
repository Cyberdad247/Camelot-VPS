// SPDX-License-Identifier: MIT

import { describe, expect, it, vi } from 'vitest';
import {
  CompilationError,
  type FetchLike,
  assertTailscaleEndpoint,
  callRemoteMcp,
  isTailscaleHost,
} from './mcp';

describe('isTailscaleHost (zero-trust mesh gate)', () => {
  it('accepts MagicDNS *.ts.net names', () => {
    expect(isTailscaleHost('cybertronia.tailcd0c29.ts.net')).toBe(true);
  });

  it('accepts CGNAT 100.64.0.0/10 addresses', () => {
    expect(isTailscaleHost('100.64.0.1')).toBe(true);
    expect(isTailscaleHost('100.118.224.52')).toBe(true);
    expect(isTailscaleHost('100.127.255.255')).toBe(true);
  });

  it('rejects public hosts and out-of-range 100.x', () => {
    expect(isTailscaleHost('example.com')).toBe(false);
    expect(isTailscaleHost('8.8.8.8')).toBe(false);
    expect(isTailscaleHost('100.63.0.1')).toBe(false); // below /10
    expect(isTailscaleHost('100.128.0.1')).toBe(false); // above /10
  });
});

describe('assertTailscaleEndpoint', () => {
  it('returns the URL for a Tailscale endpoint', () => {
    expect(assertTailscaleEndpoint('https://host.ts.net/mcp').hostname).toBe('host.ts.net');
  });

  it('throws CompilationError for untrusted endpoints', () => {
    expect(() => assertTailscaleEndpoint('https://evil.example.com/mcp')).toThrow(CompilationError);
  });

  it('throws CompilationError for malformed URLs', () => {
    expect(() => assertTailscaleEndpoint('not a url')).toThrow(CompilationError);
  });
});

describe('callRemoteMcp', () => {
  it('refuses untrusted endpoints BEFORE any network I/O', async () => {
    const fetchImpl = vi.fn();
    await expect(
      callRemoteMcp('https://evil.example.com/mcp', 'hello', {
        fetchImpl: fetchImpl as unknown as FetchLike,
      }),
    ).rejects.toBeInstanceOf(CompilationError);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('returns the answer from an MCP tools/call result', async () => {
    const fetchImpl: FetchLike = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ result: { content: [{ type: 'text', text: 'forty two' }] } }),
    });
    const out = await callRemoteMcp('https://host.ts.net/mcp', 'meaning of life', { fetchImpl });
    expect(out.answer).toBe('forty two');
  });

  it('throws on a non-ok HTTP status', async () => {
    const fetchImpl: FetchLike = async () => ({ ok: false, status: 503, json: async () => ({}) });
    await expect(callRemoteMcp('https://host.ts.net/mcp', 'x', { fetchImpl })).rejects.toThrow(
      /503/,
    );
  });
});
