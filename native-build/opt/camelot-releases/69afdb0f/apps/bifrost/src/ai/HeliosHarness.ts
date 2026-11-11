// SPDX-License-Identifier: MIT

import { GoogleGenerativeAI } from '@google/generative-ai';
import dotenv from 'dotenv';

dotenv.config();

const ai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || '');
const proModel = ai.getGenerativeModel({ model: 'gemini-1.5-pro' });

export class HeliosHarness {
  public static async askLakisha(command: string, state: any): Promise<any> {
    const prompt = `
      Context: ${JSON.stringify(state)}
      User Command: ${command}
      
      You are Lakisha, the Executive AI Knight of the Sovereign Universal Ecosystem. 
      You manage Vault_Ω (Accounting), Raven_Ω (Marketing), and Echo_Ω (Comms). 
      Analyze the user's command and the current system state. 
      You MUST output a valid JSON object containing:
      1. "feedback": A concise, professional response to the Sovereign.
      2. "mutations": An array of database actions to take. Use this exact format:
         - For Ledger: { "target": "vault", "action": "postTransaction", "entity": "Name", "desc": "Reason", "amount": 5000, "accountId": "uuid" }
      3. "swarm_tasks": An array of bulk tasks to delegate to the Microcubic Swarm. Use this exact format:
         - For SMS: { "type": "draft_tenant_notice", "payload": { "tenantName": "John", "threadId": "uuid", "issue": "Late Rent", "tone": "firm" } }
    `;
    
    const result = await proModel.generateContent(prompt);
    return JSON.parse(result.response.text());
  }
}
