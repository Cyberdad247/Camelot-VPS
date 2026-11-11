// SPDX-License-Identifier: MIT

import { GoogleGenerativeAI } from '@google/generative-ai';
import { EventEmitter } from 'events';
import dotenv from 'dotenv';
import { SovereignDB } from '../db/SovereignDB';

dotenv.config();

const ai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || '');
const flashModel = ai.getGenerativeModel({ model: 'gemini-1.5-flash' });

// The Microcubic Task Interface
export interface SwarmTask {
  id: string;
  type: string;
  payload: any;
}

class MicrocubicMatrix extends EventEmitter {
  private queue: SwarmTask[] = [];
  private activeCubes: number = 0;
  private readonly MAX_CONCURRENCY = 10; // Strict limit to prevent Google API 429 errors
  private readonly RATE_LIMIT_DELAY_MS = 1000;

  /**
   * Ingests a bulk array of tasks from Lakisha and ignites the Swarm.
   */
  public unleash(tasks: SwarmTask[]) {
    console.log(`[Microcubic Matrix] Ingesting ${tasks.length} tasks. Spawning WASM isolates...`);
    this.queue.push(...tasks);
    this.processMatrix();
  }

  /**
   * The internal loop that manages the Microcubic VMs.
   */
  private async processMatrix() {
    if (this.queue.length === 0 || this.activeCubes >= this.MAX_CONCURRENCY) {
      return;
    }

    // Spawn a new Microcube for the next task
    const task = this.queue.shift();
    if (task) {
      this.activeCubes++;
      this.executeCube(task).finally(() => {
        this.activeCubes--;
        // Throttle the next spawn to respect API limits
        setTimeout(() => this.processMatrix(), this.RATE_LIMIT_DELAY_MS);
      });
    }

    // Recursively fill the concurrency pool
    this.processMatrix();
  }

  /**
   * The isolated execution environment (Simulating the WASM MicroVM).
   */
  private async executeCube(task: SwarmTask) {
    console.log(`[Microcube ${task.id}] Booting... Executing task: ${task.type}`);
    
    try {
      let result;

      if (task.type === 'draft_tenant_notice') {
        const { tenantName, threadId, issue, tone } = task.payload;
        const prompt = `Write a short, ${tone} SMS notice to tenant ${tenantName} regarding: ${issue}. Keep it under 160 characters.`;
        
        const response = await flashModel.generateContent(prompt);
        result = response.response.text();
        
        console.log(`[Microcube ${task.id}] Task Complete. Output: ${result}`);
        
        // KINETIC ACTION: Write directly to Echo_Ω Database
        await SovereignDB.logMessage(
          threadId || 'default-thread', 
          'SMS', 
          result, 
          'STAGED_FOR_DELIVERY'
        );
      }

      // Emit telemetry back to the Bifrost Bridge
      this.emit('cube_collapsed', { taskId: task.id, success: true, result });

    } catch (error) {
      console.error(`[Microcube ${task.id}] FATAL EXCEPTION:`, error);
      this.emit('cube_collapsed', { taskId: task.id, success: false, error });
      
      // Re-queue on failure
      this.queue.push(task);
    }
  }
}

// Export the singleton instance of the Swarm Matrix
export const swarmMatrix = new MicrocubicMatrix();
