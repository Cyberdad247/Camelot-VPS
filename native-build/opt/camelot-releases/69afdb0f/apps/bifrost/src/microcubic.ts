// SPDX-License-Identifier: MIT

import { EventEmitter } from 'node:events';
import path from 'node:path';
import { Worker } from 'node:worker_threads';
import type { Command } from './nlp';

// A unit of isolated work dispatched into a microcube (worker_threads V8 thread).
export interface CubeTask {
  id: string;
  command: Command;
}

export interface CubeResult {
  taskId: string;
  command: Command;
  persisted: boolean;
}

// Resolve the worker entry for both tsx (dev → .ts) and compiled (prod → .js).
const ext = path.extname(__filename) || '.js';
const WORKER_PATH = path.join(__dirname, `cubeWorker${ext}`);

/**
 * MicrocubicMatrix — runs each task in an isolated worker_threads "microcube".
 * Zero Docker required: V8 thread isolation with message-passing. Emits
 * `cube_collapsed` on completion (success or failure).
 */
export class MicrocubicMatrix extends EventEmitter {
  executeCube(task: CubeTask): Promise<CubeResult> {
    return new Promise((resolve, reject) => {
      const worker = new Worker(WORKER_PATH, { workerData: task });

      worker.on('message', (result: CubeResult) => {
        this.emit('cube_collapsed', { taskId: task.id, success: true, result });
        resolve(result);
      });

      worker.on('error', (error) => {
        this.emit('cube_collapsed', { taskId: task.id, success: false, error });
        reject(error);
      });

      worker.on('exit', (code) => {
        if (code !== 0) reject(new Error(`Microcube stopped with exit code ${code}`));
      });
    });
  }
}
