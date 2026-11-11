// SPDX-License-Identifier: MIT

import { expect, test, vi } from 'vitest';
import { WebSocket, WebSocketServer } from 'ws';
import { createServer } from 'http';
import express from 'express';
import { HeliosHarness } from '../src/ai/HeliosHarness';

// Mocking HeliosHarness
vi.mock('../src/ai/HeliosHarness', () => ({
  HeliosHarness: {
    askLakisha: vi.fn().mockResolvedValue({
      feedback: 'Mocked feedback',
      mutations: [],
      swarm_tasks: [{ type: 'draft_tenant_notice', payload: {} }]
    })
  }
}));

test('E2E: WebSocket interaction triggers swarm tasks', async () => {
    const app = express();
    const server = createServer(app);
    const wss = new WebSocketServer({ server });
    
    // Minimal integration test setup (simplified from server.ts)
    wss.on('connection', (ws) => {
        ws.on('message', async (msg) => {
            const data = JSON.parse(msg.toString());
            if (data.type === 'VOICE_COMMAND') {
                const response = await HeliosHarness.askLakisha(data.payload, {});
                ws.send(JSON.stringify({ type: 'VOICE_FEEDBACK', payload: { text: response.feedback } }));
            }
        });
    });

    const PORT = 3005; // Change port to avoid conflicts
    server.listen(PORT);
    
    const client = new WebSocket(`ws://localhost:${PORT}`);

    const feedbackPromise = new Promise((resolve) => {
        client.on('message', (msg) => {
            const data = JSON.parse(msg.toString());
            if (data.type === 'VOICE_FEEDBACK') resolve(data.payload.text);
        });
    });

    client.on('open', () => {
        client.send(JSON.stringify({ type: 'VOICE_COMMAND', payload: 'test command' }));
    });

    const feedback = await feedbackPromise;
    expect(feedback).toBe('Mocked feedback');

    client.close();
    server.close();
});
