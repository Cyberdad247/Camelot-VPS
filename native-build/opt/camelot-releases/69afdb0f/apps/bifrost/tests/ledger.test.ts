// SPDX-License-Identifier: MIT

import { expect, test, vi } from 'vitest';
import { GoogleGenerativeAI } from '@google/generative-ai';

// Mocking GoogleGenerativeAI
vi.mock('@google/generative-ai', () => {
  class MockGoogleGenerativeAI {
    getGenerativeModel() {
      return {
        generateContent: vi.fn().mockResolvedValue({
          response: { text: () => '9942: Coffee Bean purchase anomaly found.' }
        })
      };
    }
  }
  return {
    GoogleGenerativeAI: MockGoogleGenerativeAI
  };
});

test('Ledger Needle Test: Gemini 1.5 Pro identifies the anomaly', async () => {
    const ai = new GoogleGenerativeAI('mock-key');
    const proModel = ai.getGenerativeModel({ model: 'gemini-1.5-pro' });
    
    const mockLedger = "Transaction ID 9942: Coffee Bean purchase categorized as Property Maintenance\n" + "X".repeat(1000); // Simulated large context
    
    const response = await proModel.generateContent(`Find anomaly: ${mockLedger}`);
    const text = response.response.text();
    
    expect(text).toContain('9942');
    expect(text.toLowerCase()).toContain('coffee');
});
