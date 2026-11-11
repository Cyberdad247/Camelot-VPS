// SPDX-License-Identifier: MIT

import { parentPort, workerData } from 'node:worker_threads';
import { SovereignDB } from './db/SovereignDB';
import type { CubeResult, CubeTask } from './microcubic';

// Runs inside an isolated microcube (worker_threads). Performs the command's
// DB side effects, posts the result back to the matrix, then disconnects.
async function run(): Promise<void> {
  const task = workerData as CubeTask;
  const cmd = task.command;

  try {
    if (cmd.action === 'add_transaction') {
      await SovereignDB.postTransaction('command', 'add_transaction', cmd.amount, 'default-account');
    } else if (cmd.action === 'remind') {
      await SovereignDB.logMessage('default-thread', 'SYSTEM', `Reminder set for ${cmd.who}`, 'LOGGED');
    } else if (cmd.action === 'order') {
      await SovereignDB.logMessage('default-thread', 'SYSTEM', `Order placed: ${cmd.item}`, 'LOGGED');
    } else {
      await SovereignDB.logMessage('default-thread', 'SYSTEM', `Unrecognized command: ${cmd.raw}`, 'LOGGED');
    }

    const result: CubeResult = { taskId: task.id, command: cmd, persisted: true };
    parentPort?.postMessage(result);
  } catch (err) {
    console.error('[CubeWorker] execution failed:', err);
    throw err;
  }
}

run().catch((err) => {
  // Re-throw so the Worker emits 'error' and the matrix rejects/handles it.
  throw err;
});
