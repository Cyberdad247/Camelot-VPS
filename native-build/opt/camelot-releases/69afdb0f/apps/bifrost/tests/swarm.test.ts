// SPDX-License-Identifier: MIT

import { expect, test, vi } from 'vitest';
import { swarmMatrix, SwarmTask } from '../src/swarm/MicrocubicSwarm';

// Stub the DB boundary so the test exercises swarm orchestration in isolation
// (no live Prisma/network dependency).
vi.mock('../src/db/SovereignDB', () => ({
  SovereignDB: { logMessage: vi.fn().mockResolvedValue({}) },
}));

// Improved mocking of GoogleGenerativeAI
vi.mock('@google/generative-ai', () => {
  class MockGoogleGenerativeAI {
    getGenerativeModel() {
      return {
        generateContent: vi.fn().mockResolvedValue({
          response: { text: () => 'Mocked response' }
        })
      };
    }
  }
  return {
    GoogleGenerativeAI: MockGoogleGenerativeAI
  };
});

test('MicrocubicMatrix processes tasks and emits collapse event', async () => {
    const tasks: SwarmTask[] = [
        { id: '1', type: 'draft_tenant_notice', payload: { tenantName: 'John', issue: 'Late rent', tone: 'firm' } }
    ];

    const collapsePromise = new Promise((resolve) => {
        swarmMatrix.once('cube_collapsed', (data) => resolve(data));
    });

    swarmMatrix.unleash(tasks);

    const result: any = await collapsePromise;
    expect(result.success).toBe(true);
    expect(result.taskId).toBe('1');
    expect(result.result).toBe('Mocked response');
});

test('MicrocubicMatrix respects concurrency limits', async () => {
    const tasks: SwarmTask[] = Array.from({ length: 20 }).map((_, i) => ({
        id: `con-${i}`,
        type: 'draft_tenant_notice',
        payload: { tenantName: `Tenant ${i}`, issue: 'Update', tone: 'neutral' }
    }));

    let collapseCount = 0;
    swarmMatrix.on('cube_collapsed', () => {
        collapseCount++;
    });

    swarmMatrix.unleash(tasks);

    // Concurrency limit is 10, so they shouldn't all finish immediately
    expect(collapseCount).toBeLessThan(20);
});
