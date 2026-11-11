// SPDX-License-Identifier: MIT

import { describe, expect, it, vi } from 'vitest';
import { CompilationError } from './mcp';
import { classify, route } from './router';

const TS_URL = 'https://host.ts.net/mcp';

describe('classify (LOCAL_FIRST_ISOLATION)', () => {
  it('routes known commands to LOCAL_TOOLS', () => {
    expect(classify({ action: 'add_transaction', amount: 100 })).toBe('LOCAL_TOOLS');
    expect(classify({ action: 'remind', who: 'andre' })).toBe('LOCAL_TOOLS');
  });

  it('routes unknown utterances to REMOTE_MCP', () => {
    expect(classify({ action: 'unknown', raw: 'what is the weather' })).toBe('REMOTE_MCP');
  });
});

describe('route (//ROUTE + //REZERO)', () => {
  it('keeps known commands local without touching the remote caller', async () => {
    const caller = vi.fn();
    const out = await route('add transaction 15000', { remoteMcpUrl: TS_URL, caller });
    expect(out.lane).toBe('LOCAL_TOOLS');
    expect(out.rezeroed).toBe(false);
    expect(out.command.action).toBe('add_transaction');
    expect(caller).not.toHaveBeenCalled();
  });

  it('bypasses unknown utterances to REMOTE_MCP and returns the answer', async () => {
    const caller = vi.fn(async () => ({ answer: 'It is sunny.' }));
    const out = await route('what is the weather', { remoteMcpUrl: TS_URL, caller });
    expect(out.lane).toBe('REMOTE_MCP');
    expect(out.response).toBe('It is sunny.');
    expect(out.rezeroed).toBe(false);
    expect(caller).toHaveBeenCalledOnce();
  });

  it('//REZERO to local when no remote is configured', async () => {
    const out = await route('what is the weather');
    expect(out.lane).toBe('LOCAL_TOOLS');
    expect(out.rezeroed).toBe(true);
    expect(out.reason).toMatch(/no remote/i);
  });

  it('//REZERO to local on remote failure (timeout/error)', async () => {
    const caller = vi.fn(async () => {
      throw new Error('aborted');
    });
    const out = await route('research quantum tunneling', { remoteMcpUrl: TS_URL, caller });
    expect(out.lane).toBe('LOCAL_TOOLS');
    expect(out.rezeroed).toBe(true);
    expect(out.reason).toMatch(/remote failure/i);
  });

  it('//REZERO to local on an untrusted (non-Tailscale) endpoint', async () => {
    const caller = vi.fn(async () => {
      throw new CompilationError('not a Tailscale endpoint');
    });
    const out = await route('ask something', {
      remoteMcpUrl: 'https://evil.example.com/mcp',
      caller,
    });
    expect(out.lane).toBe('LOCAL_TOOLS');
    expect(out.rezeroed).toBe(true);
    expect(out.reason).toMatch(/untrusted/i);
  });
});
