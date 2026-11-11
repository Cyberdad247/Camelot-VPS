// SPDX-License-Identifier: MIT

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Gateway-side client for the file-based Hermes bus consumed by the Python
// control plane (control_plane/hermes_bridge.py). Mirrors that module exactly:
//   channel "a.b"  →  ~/.hermes/sessions/a_b.jsonl
//   one JSON object per line, with `ts` + `channel` injected.
const HERMES_HOME = process.env.HERMES_HOME
  ? path.resolve(process.env.HERMES_HOME)
  : path.join(os.homedir(), '.hermes');

const SESSIONS_DIR = path.join(HERMES_HOME, 'sessions');

// Channel CAMELOT knights already subscribe to for swarm/gateway activity.
export const SWARM_EVENTS = 'swarm.events';

export function publishHermes(channel: string, payload: Record<string, unknown>): boolean {
  try {
    fs.mkdirSync(SESSIONS_DIR, { recursive: true });
    const file = path.join(SESSIONS_DIR, `${channel.replace(/\./g, '_')}.jsonl`);
    const message = { ts: new Date().toISOString(), channel, ...payload };
    fs.appendFileSync(file, `${JSON.stringify(message)}\n`, 'utf8');
    return true;
  } catch (error) {
    // Bus emission is best-effort — never let it break the request path.
    console.error('[hermes] publish failed:', error);
    return false;
  }
}
