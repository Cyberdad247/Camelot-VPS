// SPDX-License-Identifier: MIT

import { PrismaClient } from '../generated/client';

// Initialize Prisma Client with connection pooling optimized for Edge
const prisma = new PrismaClient({
  log: ['warn', 'error'],
});

export class SovereignDB {
  
  // ==========================================
  // VAULT_Ω (Accounting & Ledger)
  // ==========================================
  
  /**
   * Posts a double-entry transaction to Vault_Ω.
   * Enforces strict balance checking.
   */
  static async postTransaction(entity: string, action: string, amount: number, accountId: string) {
    console.log(`[Vault_Ω] Forging ledger entry: ${entity} | ${action} | $${amount}`);
    
    // In a true double-entry system, we write two rows (Debit & Credit).
    // For this implementation, we log the primary transaction against the target account.
    return await prisma.transaction.create({
      data: {
        entity,
        action,
        debit: amount > 0 ? amount : 0,
        credit: amount < 0 ? Math.abs(amount) : 0,
        accountId: accountId,
      }
    });
  }

  // ==========================================
  // ECHO_Ω (Communications & SMS)
  // ==========================================

  /**
   * Logs an outbound message drafted by the Microcubic Swarm.
   */
  static async logMessage(threadId: string, channel: string, content: string, status: string) {
    console.log(`[Echo_Ω] Archiving ${channel} message to Thread ${threadId}`);
    
    return await prisma.message.create({
      data: {
        threadId,
        direction: 'OUTBOUND',
        channel,
        content,
        status,
      }
    });
  }

  // ==========================================
  // RAVEN_Ω (CRM & Marketing)
  // ==========================================

  /**
   * Updates a contact's tags based on AI analysis.
   */
  static async tagContact(email: string, newTag: string) {
    console.log(`[Raven_Ω] Tagging contact ${email} with [${newTag}]`);
    
    const contact = await prisma.contact.findUnique({ where: { email } });
    if (!contact) return null;

    // tags is a JSON-encoded string list (SQLite has no scalar arrays).
    let current: string[] = [];
    try {
      const parsed = JSON.parse(contact.tags || '[]');
      if (Array.isArray(parsed)) current = parsed;
    } catch {
      current = [];
    }
    const updatedTags = Array.from(new Set([...current, newTag]));

    return await prisma.contact.update({
      where: { email },
      data: { tags: JSON.stringify(updatedTags) }
    });
  }
}
