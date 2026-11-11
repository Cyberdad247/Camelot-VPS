// SPDX-License-Identifier: MIT

import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { WebSocket } from 'ws';

// Iron Gate Test B (verification.md §2.B) — Live WebSocket Synchronization.
// Connect a mock client and assert the gateway transmits a STATE_UPDATE frame
// carrying valid unified business metrics. No DB is contacted (no command sent).

let server: Server;
let wss: import('ws').WebSocketServer;
let url: string;

beforeAll(async () => {
  // Bind a dedicated test port (server.ts treats 0 as falsy → use a real one).
  process.env.PORT = '34117';
  const mod = await import('./server');
  server = mod.server;
  wss = mod.wss;
  if (!server.listening) {
    await new Promise<void>((resolve) => server.once('listening', () => resolve()));
  }
  const addr = server.address() as AddressInfo;
  url = `ws://127.0.0.1:${addr.port}`;
});

afterAll(async () => {
  for (const client of wss.clients) client.terminate();
  wss.close();
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

describe('Bifrost WebSocket gateway', () => {
  it('rejects anonymous mesh telemetry requests', async () => {
    const response = await fetch(
      `http://127.0.0.1:${(server.address() as AddressInfo).port}/api/mesh/nodes`,
    );

    expect(response.status).toBe(503);
  });

  it('serves the upstream health contract', async () => {
    const response = await fetch(`${url.replace(/^ws/, 'http')}/health`);
    const body = (await response.json()) as {
      status: string;
      clients: number;
      helios: boolean;
    };

    expect(response.status).toBe(200);
    expect(body.status).toBe('ok');
    expect(Number.isInteger(body.clients)).toBe(true);
    expect(typeof body.helios).toBe('boolean');
  });

  it('transmits a STATE_UPDATE with valid metrics on connect', async () => {
    const ws = new WebSocket(url);

    const frame = await new Promise<{ type: string; payload: Record<string, unknown> }>(
      (resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('no STATE_UPDATE within 4s')), 4000);
        ws.on('message', (data) => {
          clearTimeout(timer);
          resolve(JSON.parse(data.toString()));
        });
        ws.on('error', reject);
      },
    );
    ws.close();

    expect(frame.type).toBe('STATE_UPDATE');
    expect(typeof frame.payload.portfolioValuation).toBe('number');
    expect(frame.payload.portfolioValuation).toBe(14_200_000);
    expect(typeof frame.payload.updatedAt).toBe('string');
  });
});
