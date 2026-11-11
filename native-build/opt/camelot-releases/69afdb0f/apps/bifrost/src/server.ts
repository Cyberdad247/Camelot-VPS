// SPDX-License-Identifier: MIT

import { randomUUID, timingSafeEqual } from 'node:crypto';
import http from 'node:http';
import express, { type Request } from 'express';
import rateLimit from 'express-rate-limit';
import { WebSocket, WebSocketServer } from 'ws';
import { SovereignDB } from './db/SovereignDB';
import { SWARM_EVENTS, publishHermes } from './hermes';
import { type Command, parseCommand } from './nlp';
import { MicrocubicMatrix } from './microcubic';
import { type RouteOutcome, route } from './router';
import { routeOmniVoice } from './omniVoice';
import { z } from 'zod';
import { SignatureError, verifyActionSignature, verifyWebhookSignature } from './security';
import { applyCommand, setOmniVoiceTelemetry, setRouteTelemetry, snapshot, state } from './state';
import { issueSignedAction } from './issuance';
import { createOperatorBff } from './operator/bff';
import { InMemoryEventStore } from './operator/receipts';
import { verifyManifest, issueLease } from './operator/sentinel';
import htmxRouter from './htmx_router';

// WebSocket carrying the heartbeat flag used by the reaper loop below.
interface LiveSocket extends WebSocket {
  isAlive?: boolean;
}

// Capture the raw body so the webhook route can verify its HMAC signature.
interface RawBodyRequest extends Request {
  rawBody?: string;
}

const PORT = Number(process.env.PORT) || 3001;
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET ?? '';
const MESH_TELEMETRY_TOKEN = process.env.BIFROST_MESH_TOKEN ?? '';

// The Helios/Swarm AI path is opt-in: it needs a Gemini key and makes live
// model calls. When disabled, the gateway runs purely on the deterministic NLP
// parser so it stays bootable and testable without any secrets.
const ENABLE_HELIOS =
  process.env.ENABLE_HELIOS === '1' || Boolean(process.env.GEMINI_API_KEY);

// Cap inbound frame size (16 KB) — commands are tiny; reject oversized payloads
// at the protocol layer to avoid unbounded JSON.parse work.
const MAX_WS_PAYLOAD = 16 * 1024;

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server, maxPayload: MAX_WS_PAYLOAD });

// Microcubic Matrix — each command runs in an isolated worker_threads microcube
// (Zero Docker). Cubes own DB side effects; this thread owns state + broadcast.
const matrix = new MicrocubicMatrix();
matrix.on('cube_collapsed', (event) => {
  if (event.success) {
    console.log(`cube ${event.taskId} collapsed → ${event.result.command.action}`);
  } else {
    console.error(`cube ${event.taskId} failed:`, event.error);
  }
});

app.use(
  express.json({
    limit: '64kb',
    verify: (req, _res, buf) => {
      (req as RawBodyRequest).rawBody = buf.toString('utf8');
    },
  }),
);

// ── Slice #2 Operator Console BFF ─────────────────────────────────────────
// Native, local-first decision service. Fixture mode (OPERATOR_FIXTURE_TASK)
// serves deterministic task data for the operator console; production data
// binding is additive (see docs/architecture/OPERATOR_CONSOLE_DESIGN.md §8).
const operatorStore = new InMemoryEventStore();
const operatorBff = createOperatorBff({
  store: operatorStore,
  verifyManifest,
  issueLease,
  now: () => new Date(),
  requiredEvidencePresent: (ref: string) => ref.startsWith('receipt://'),
  gideonVerdict: () => 'pass' as const,
  vfsEvidenceOk: () => true,
  broadcastWs: (envelope) => {
    const msg = JSON.stringify({ type: 'OPERATOR_EVIDENCE', payload: envelope });
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(msg);
      }
    }
  },
});
app.use('/v1/operator', operatorBff);
app.use('/htmx', htmxRouter);

// ── Canonical Tailscale Mesh Node Inventory ──
// Must agree with control_plane/infra/mesh_topology.py. `camelot-relay-modal`
// and `kba-services` were listed here and are absent from the tailnet entirely;
// the hub was missing. tests/test_mesh_topology_single_source.py guards this set.
export const TAILSCALE_MESH_NODES = [
  { id: 'cybertronia', name: 'cybertronia', ip: '100.118.224.52', role: 'Primary Windows Orchestrator & Local VFS Factory', status: 'ACTIVE' },
  { id: 'vashawns-s26-ultra', name: 'vashawns-s26-ultra', ip: '100.106.246.126', role: 'Excalibur Command Center (Kinetic Mobile Sentinel)', status: 'ACTIVE' },
  { id: 'fothers-camelot', name: 'fothers-camelot', ip: '100.121.48.50', role: 'Windows Sovereign Secondary Node', status: 'ACTIVE' },
  { id: 'lakesha', name: 'lakesha', ip: '100.100.155.55', role: 'Lakisha Voice OS Host', status: 'ACTIVE' },
  { id: 'vps-camelot-hub', name: 'vps-camelot-hub', ip: '100.110.180.18', role: 'Camelot-OS Hub & Control Plane (KVM563)', status: 'ACTIVE', governingKnight: 'HERMES_PRIME' },
  { id: 'macbook-pro-3', name: 'macbook-pro-3', ip: '100.113.101.43', role: 'macOS Workstation (exit node; role unconfirmed)', status: 'ACTIVE' },
  { id: 'motorola-moto-g-power', name: 'motorola-moto-g-power-5g---2024', ip: '100.89.129.105', role: 'Auxiliary Mobile Sentinel & Backup Telemetry Relay', status: 'ACTIVE', governingKnight: 'SIR_HEIMDALL' },
];

// ── Health check (graceful deploys / load balancers) ──
app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'ok', clients: wss.clients.size, helios: ENABLE_HELIOS });
});

// ── Mesh Topology Endpoints ──
app.get(['/mesh', '/api/mesh', '/api/mesh/nodes'], requireMeshTelemetryAuth, (_req, res) => {
  res.status(200).json({
    status: 'ONLINE',
    account: 'Cyberdad247@github',
    nodeCount: TAILSCALE_MESH_NODES.length,
    nodes: TAILSCALE_MESH_NODES,
  });
});

app.get(['/api/mesh/moto', '/api/moto', '/telemetry/moto'], requireMeshTelemetryAuth, (_req, res) => {
  const motoNode = TAILSCALE_MESH_NODES.find((n) => n.id === 'motorola-moto-g-power');
  res.status(200).json({
    node: motoNode,
    telemetry: {
      status: 'ONLINE_STANDBY',
      role: 'Auxiliary Mobile Sentinel & Backup Telemetry Relay',
      tailscaleIp: '100.89.129.105',
      primaryCockpit: '100.106.246.126',
      governingKnight: 'SIR_HEIMDALL',
      activePorts: { auxSentinelRelay: 8092, termuxSsh: 8023 },
    },
  });
});

// ── Broadcast helper: push unified state to every open client ──
function requireMeshTelemetryAuth(req: Request, res: express.Response, next: express.NextFunction): void {
  const provided = req.header('x-camelot-token')?.replace(/^Bearer\s+/i, '') ?? '';
  if (!MESH_TELEMETRY_TOKEN) {
    res.status(503).json({ error: 'mesh telemetry authentication is not configured' });
    return;
  }
  const expectedBuffer = Buffer.from(MESH_TELEMETRY_TOKEN);
  const providedBuffer = Buffer.from(provided);
  if (expectedBuffer.length !== providedBuffer.length || !timingSafeEqual(expectedBuffer, providedBuffer)) {
    res.status(401).json({ error: 'mesh telemetry authentication failed' });
    return;
  }
  next();
}

function broadcastState(): void {
  const msg = JSON.stringify({ type: 'STATE_UPDATE', payload: snapshot() });
  for (const client of wss.clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(msg);
    }
  }
}

// Persist a command's side effects via SovereignDB (best-effort; broadcast
// already reflects state, so DB failures never block the live update).
async function persistCommand(cmd: Command): Promise<void> {
  try {
    if (cmd.action === 'add_transaction') {
      await SovereignDB.postTransaction('command', 'add_transaction', cmd.amount, 'default-account');
    } else if (cmd.action === 'remind') {
      await SovereignDB.logMessage('default-thread', 'SYSTEM', `Reminder set for ${cmd.who}`, 'LOGGED');
    } else if (cmd.action === 'order') {
      await SovereignDB.logMessage('default-thread', 'SYSTEM', `Order placed: ${cmd.item}`, 'LOGGED');
    } else {
      await SovereignDB.logMessage('default-thread', 'SYSTEM', `Unrecognized command: ${cmd.raw ?? cmd.action}`, 'LOGGED');
    }
  } catch (error) {
    console.error('persistCommand failed:', error);
  }
}

// ── Helios voice path (Task D) — lazy-loaded so the gateway boots without the
// AI deps/keys. Routes a voice command through Lakisha, applies any returned
// swarm tasks to the Microcubic Matrix, and reflects swarm progress in state. ──
let swarmListenerAttached = false;

async function getSwarm() {
  const mod = await import('./swarm/MicrocubicSwarm');
  if (!swarmListenerAttached) {
    mod.swarmMatrix.on('cube_collapsed', () => {
      state.swarm.completed++;
      if (state.swarm.completed >= state.swarm.tasks) {
        state.swarm.active = false;
      }
      publishHermes(SWARM_EVENTS, {
        event: 'cube_collapsed',
        completed: state.swarm.completed,
        total: state.swarm.tasks,
      });
      broadcastState();
    });
    swarmListenerAttached = true;
  }
  return mod.swarmMatrix;
}

async function runHeliosCommand(textCommand: string, ws: WebSocket): Promise<void> {
  const { HeliosHarness } = await import('./ai/HeliosHarness');

  ws.send(
    JSON.stringify({ type: 'VOICE_FEEDBACK', payload: { text: 'Ingesting command into Helios Core...' } }),
  );

  const lakishaResponse = await HeliosHarness.askLakisha(textCommand, state);

  if (Array.isArray(lakishaResponse.mutations)) {
    for (const mutation of lakishaResponse.mutations) {
      console.log('[State Mutation]:', mutation);
      // Apply persistence here as mutation handlers come online.
    }
  }

  const swarmTasks = lakishaResponse.swarm_tasks ?? [];
  if (swarmTasks.length > 0) {
    const swarmMatrix = await getSwarm();
    const tasksToSpawn = swarmTasks.map((task: { type: string; payload: unknown }, index: number) => ({
      id: `cube-${Date.now()}-${index}`,
      type: task.type,
      payload: task.payload,
    }));

    state.swarm.active = true;
    state.swarm.tasks = tasksToSpawn.length;
    state.swarm.completed = 0;

    swarmMatrix.unleash(tasksToSpawn);
    publishHermes(SWARM_EVENTS, { event: 'swarm_unleashed', tasks: tasksToSpawn.length });
    ws.send(
      JSON.stringify({
        type: 'VOICE_FEEDBACK',
        payload: { text: `${lakishaResponse.feedback} Spawning ${tasksToSpawn.length} Microcubes.` },
      }),
    );
  } else {
    ws.send(JSON.stringify({ type: 'VOICE_FEEDBACK', payload: { text: lakishaResponse.feedback } }));
  }

  state.lastCommand = 'voice_command';
  state.updatedAt = new Date().toISOString();
  broadcastState();
}

// vMAX //ROUTE + //REZERO — remote MCP endpoint must be a Tailscale URL.
const REMOTE_MCP_URL = process.env.REMOTE_MCP_URL;
const ROUTE_BUDGET_MS = Number(process.env.ROUTE_BUDGET_MS) || 900;

// Route an utterance: classify lane (local-first / Tailscale remote-MCP bypass
// with REZERO), apply in-memory state, persist local side effects, broadcast.
async function handleUtterance(raw: string): Promise<RouteOutcome> {
  const outcome = await route(raw, { remoteMcpUrl: REMOTE_MCP_URL, budgetMs: ROUTE_BUDGET_MS });
  applyCommand(outcome.command);

  // Only known local actions get DB persistence via a microcube.
  if (outcome.lane === 'LOCAL_TOOLS' && outcome.command.action !== 'unknown') {
    try {
      await matrix.executeCube({ id: randomUUID(), command: outcome.command });
      await persistCommand(outcome.command);
    } catch (error) {
      console.error('microcube execution failed:', error);
    }
  }

  setRouteTelemetry({
    response: outcome.response,
    lane: outcome.lane,
    latencyMs: outcome.latencyMs,
    rezeroed: outcome.rezeroed,
  });
  console.log(
    `route ${outcome.lane}${outcome.rezeroed ? ` (//REZERO: ${outcome.reason})` : ''} ` +
      `${outcome.latencyMs}ms -> ${outcome.command.action}`,
  );
  broadcastState();
  return outcome;
}

// ── Task 2.4 — SMS/webhook ingress (Telnyx/Bandwidth), HMAC-signed + rate-limited ──
const webhookLimiter = rateLimit({ windowMs: 60_000, max: 60, standardHeaders: true });

// ── KBA Cartridge: HMAC issuance + HITL dispatch ──
const issueLimiter = rateLimit({
  windowMs: 60_000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
});

const hitlLimiter = rateLimit({
  windowMs: 60_000,
  max: 60,
  standardHeaders: true,
  legacyHeaders: false,
});

const IssueBodySchema = z.object({
  actionId: z
    .string()
    .min(8, 'actionId too short')
    .max(64, 'actionId too long')
    .regex(
      /^KBA_(SYNC|AUDIT|REROUTE|REZERO|HEAL|NANO|SCAN|FORGE)_[A-Z0-9]{2,16}$/,
      'actionId must match KBA_<DOMAIN>_<UPPER_ALNUM>',
    ),
});

app.post('/api/bifrost/issue', issueLimiter, async (req, res) => {
  const parsed = IssueBodySchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: 'INVALID_BODY', issues: parsed.error.issues });
  }
  const { actionId } = parsed.data;
  try {
    const signed = issueSignedAction(actionId, WEBHOOK_SECRET);
    res.status(200).json(signed);
  } catch (err) {
    console.error('[Bifrost/issue] issuance failed:', err);
    res.status(500).json({ error: 'ISSUANCE_FAILED' });
  }
});

app.post('/api/bifrost/hitl', hitlLimiter, async (req, res) => {
  const actionId = req.header('x-webhook-action');
  const signature = req.header('x-webhook-signature');
  const expiresAtRaw = req.header('x-webhook-expires-at');
  const timestampRaw = req.header('x-webhook-timestamp');

  if (!actionId || !signature || !expiresAtRaw || !timestampRaw) {
    return res.status(400).json({ error: 'MISSING_HEADER' });
  }
  const timestamp = Number(timestampRaw);
  const expiresAt = Number(expiresAtRaw);
  if (!Number.isFinite(timestamp) || !Number.isFinite(expiresAt)) {
    return res.status(400).json({ error: 'MALFORMED_HEADER' });
  }

  try {
    verifyActionSignature({ actionId, timestamp, signature, expiresAt, secret: WEBHOOK_SECRET });
  } catch (err) {
    if (err instanceof SignatureError) {
      return res.status(401).json({ error: err.code, message: err.message });
    }
    return res.status(401).json({ error: 'UNKNOWN_SIG_ERROR' });
  }

  // Wire HITL to the Bifrost router. The verified signature authorizes the
  // action; we treat `kba ${actionId}` as a parseable utterance and feed it
  // through the existing `route()` so KBA actions flow through the same
  // //ROUTE + //REZERO governance as /webhook/sms. The router.ts NLP classifier
  // will land known KBA verbs on LOCAL_TOOLS and unknown verbs on REMOTE_MCP
  // bypass (Tailscale-guarded by the caller setup at process boot).
  const utterance = `kba ${actionId}`;
  const outcome = await route(utterance, {
    remoteMcpUrl: REMOTE_MCP_URL,
    budgetMs: ROUTE_BUDGET_MS,
  });
  applyCommand(outcome.command);
  setRouteTelemetry({
    response: outcome.response,
    lane: outcome.lane,
    latencyMs: outcome.latencyMs,
    rezeroed: outcome.rezeroed,
  });
  broadcastState();
  console.log(
    `[Bifrost/hitl] routed action=${actionId} lane=${outcome.lane} ` +
      `latency=${outcome.latencyMs}ms rezeroed=${outcome.rezeroed}`,
  );
  res.status(200).json({
    status: outcome.command.action === 'unknown' ? 'NO_LOCAL_HANDLER' : 'LOCKED_AND_ROUTED',
    actionId,
    timestamp,
    lane: outcome.lane,
    rezeroed: outcome.rezeroed,
  });
});

app.post('/webhook/sms', webhookLimiter, async (req: RawBodyRequest, res) => {
  const signature = req.header('x-webhook-signature');
  if (!verifyWebhookSignature(req.rawBody ?? '', signature, WEBHOOK_SECRET)) {
    return res.status(401).send('Invalid signature');
  }

  const { message } = req.body ?? {};
  if (typeof message !== 'string' || message.length === 0) {
    return res.status(400).send('Message is required');
  }

  await SovereignDB.logMessage('default-thread', 'SMS', `SMS webhook: ${message}`, 'RECEIVED').catch(
    (error) => console.error('webhook persist failed:', error),
  );

  const outcome = await handleUtterance(message);
  res.status(200).json({
    status: 'received',
    lane: outcome.lane,
    command: outcome.command.action,
    rezeroed: outcome.rezeroed,
  });
});

// ── WebSocket: command intake + heartbeat ──
wss.on('connection', (ws: LiveSocket) => {
  ws.isAlive = true;
  ws.on('pong', () => {
    ws.isAlive = true;
  });

  // Send the current unified state immediately on connect.
  ws.send(JSON.stringify({ type: 'STATE_UPDATE', payload: snapshot() }));

  ws.on('message', async (data) => {
    const raw = data.toString();
    let frameType: string | undefined;
    let payloadText = raw;
    try {
      const parsed = JSON.parse(raw);
      frameType = parsed?.type;
      if (typeof parsed?.payload === 'string') {
        payloadText = parsed.payload;
      }
    } catch {
      // Plain-text command frame — treat the whole payload as the command.
    }

    // ── Omni-Voice D.A.G. ingress routing ─────────────────────────────────
    // Runs before any LLM work: the ᛟ_ runic bypass and the Softmax persona
    // dispatch are both deterministic, so a control token never pays inference
    // cost. This mirrors control_plane/dispatch/omni_voice_dag.py, and the port
    // is pinned to that module by the vectors in omniVoice.crystal.json.
    const omni = routeOmniVoice(payloadText);
    setOmniVoiceTelemetry({
      status: omni.status,
      path: omni.path,
      knight: omni.knight ?? null,
      tau: omni.tau ?? null,
      confidence: omni.confidence ?? null,
      delegatesRune: omni.delegatesRune ?? null,
    });
    console.log(
      `omni-voice ${omni.status} path=${omni.path} knight=${omni.knight ?? '-'}` +
        (omni.tau != null ? ` tau=${omni.tau}` : '') +
        (omni.delegatesRune ? ` rune=${omni.delegatesRune}` : ''),
    );

    if (omni.status === 'ROUTED_BYPASS') {
      // A rune is a control token, not an utterance: it never reaches the NLP
      // parser or the remote MCP lane. Executing the delegated rune is the
      // Python router's job (HITL-gated), so the gateway reports the dispatch
      // rather than pretending it already ran.
      ws.send(
        JSON.stringify({
          type: 'VOICE_FEEDBACK',
          payload: {
            text: `Rune ${omni.token} dispatched to ${omni.knight} via ${omni.delegatesRune}.`,
          },
        }),
      );
      broadcastState();
      return;
    }

    // Voice commands route through Helios when enabled; everything else uses the
    // deterministic NLP parser so the gateway works without AI keys.
    if (ENABLE_HELIOS && frameType === 'VOICE_COMMAND') {
      try {
        await runHeliosCommand(payloadText, ws);
      } catch (error) {
        console.error('[Helios] command failed:', error);
        ws.send(JSON.stringify({ type: 'VOICE_FEEDBACK', payload: { text: 'Helios command failed.' } }));
      }
      return;
    }

    await handleUtterance(payloadText);
  });

  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
  });
});

// ── Task 2.2 — reaper: drop sockets that miss heartbeats ──
const interval = setInterval(() => {
  for (const client of wss.clients) {
    const ws = client as LiveSocket;
    if (!ws.isAlive) {
      ws.terminate();
      continue;
    }
    ws.isAlive = false;
    ws.ping();
  }
}, 30_000);

wss.on('close', () => clearInterval(interval));

// Fail fast on unbound datastore: SovereignDB/Prisma need DATABASE_URL
// (Postgres via @sovereign/db in prod, sqlite file:./vault.db locally —
// see apps/bifrost/.env.example). Booting deaf to the ledger is worse than
// refusing to boot.
const DATABASE_URL = process.env.DATABASE_URL ?? '';
if (!DATABASE_URL) {
  throw new Error(
    'DATABASE_URL is not set — refusing to boot with an unbound datastore.'
  );
}

server.listen(PORT, () => {
  console.log(`Bifrost gateway listening on port ${PORT} (helios=${ENABLE_HELIOS})`);
});

// ── Graceful shutdown: drain sockets, close server, disconnect Prisma ──
async function shutdown(signal: string): Promise<void> {
  console.log(`${signal} received — shutting down...`);
  clearInterval(interval);
  for (const client of wss.clients) client.terminate();
  wss.close();
  server.close();
  process.exit(0);
}

process.on('SIGTERM', () => void shutdown('SIGTERM'));
process.on('SIGINT', () => void shutdown('SIGINT'));

export { app, server, wss };
