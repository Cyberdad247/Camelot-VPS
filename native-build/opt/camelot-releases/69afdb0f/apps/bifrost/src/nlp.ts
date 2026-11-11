// SPDX-License-Identifier: MIT

// Task 2.3 — Natural-language command parser.
// Maps keyword sequences (e.g. "add transaction 15000", "remind Andre",
// "order espresso") into structured commands for the agent router.

export type KbaDomain =
  | 'sync'
  | 'audit'
  | 'reroute'
  | 'rezero'
  | 'heal'
  | 'nano'
  | 'scan'
  | 'forge';

export type Command =
  | { action: 'add_transaction'; amount: number }
  | { action: 'remind'; who: string }
  | { action: 'order'; item: string }
  | { action: 'kba'; domain: KbaDomain; raw: string }
  | { action: 'unknown'; raw: string };

export function parseCommand(input: string): Command {
  const text = input.trim().toLowerCase();

  const tx = text.match(/^add\s+transaction\s+\$?([\d,]+(?:\.\d+)?)/);
  if (tx) {
    return { action: 'add_transaction', amount: Number(tx[1].replace(/,/g, '')) };
  }

  // KBA Cartridge bridge — server.ts emits `kba KBA_<DOMAIN>_<discriminator>`
  // utterances after a verified /api/bifrost/hitl dispatch. Lowercased, the
  // prefix is `kba kba_<domain>_<id>`. We match the enum and drop the suffix.
  const kba = text.match(/^kba\s+kba_(sync|audit|reroute|rezero|heal|nano|scan|forge)_[a-z0-9]+/);
  if (kba) {
    return { action: 'kba', domain: kba[1] as KbaDomain, raw: input };
  }

  const remind = text.match(/^remind\s+(\w+)/);
  if (remind) {
    return { action: 'remind', who: remind[1] };
  }

  const order = text.match(/^order\s+(.+)/);
  if (order) {
    return { action: 'order', item: order[1].trim() };
  }

  return { action: 'unknown', raw: input };
}

