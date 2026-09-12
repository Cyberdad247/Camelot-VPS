import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const PORT = Number(process.env.BIFROST_PORT || 4188);
const HOST = process.env.BIFROST_HOST || '127.0.0.1';

const REALMS = {
  multivoice: {
    baseUrl: process.env.MULTIVOICE_BASE_URL || 'https://obsidian-spire-hud.vercel.app',
    healthPath: '/api/health',
    launchUrl: process.env.MULTIVOICE_BASE_URL || 'https://obsidian-spire-hud.vercel.app',
  },
  godseye: {
    baseUrl: process.env.GODS_EYE_BASE_URL || 'https://maptheworld.ai',
    healthPath: '/',
    launchUrl: process.env.GODS_EYE_BASE_URL || 'https://maptheworld.ai',
  },
  worldmonitor: {
    baseUrl: process.env.WORLDMONITOR_BASE_URL || 'https://worldmonitor.app',
    healthPath: '/mcp',
    launchUrl: process.env.WORLDMONITOR_BASE_URL || 'https://worldmonitor.app',
  },
};

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
};

function sendJson(res, status, payload) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
  });
  res.end(JSON.stringify(payload));
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 64 * 1024) throw new Error('Request body too large');
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

async function fetchWithTimeout(url, init = {}, timeoutMs = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal, redirect: 'follow' });
  } finally {
    clearTimeout(timer);
  }
}

async function probeRealm(realmId) {
  const realm = REALMS[realmId];
  if (!realm) return { reachable: false, detail: 'Unknown realm' };
  const url = new URL(realm.healthPath, realm.baseUrl).toString();
  try {
    const response = await fetchWithTimeout(url, {
      method: 'GET',
      headers: {
        Accept: realmId === 'worldmonitor' ? 'text/markdown,text/plain;q=0.9,*/*;q=0.5' : 'application/json,text/html;q=0.9,*/*;q=0.5',
        'User-Agent': 'Camelot-Bifrost/1.0',
      },
    }, 4500);
    return {
      reachable: response.ok || (realmId === 'worldmonitor' && response.status === 405),
      detail: `${realmId} responded HTTP ${response.status}`,
      status: response.status,
    };
  } catch (error) {
    return {
      reachable: false,
      detail: error instanceof Error ? error.message : 'Probe failed',
    };
  }
}

function validateCrossing(body) {
  const source = String(body.source || '');
  const destination = String(body.destination || '');
  const transport = String(body.transport || '');
  const intent = String(body.intent || '').trim();
  const payload = String(body.payload || '');
  const allowedRealms = new Set(['camelot', 'multivoice', 'godseye', 'worldmonitor']);
  const allowedTransports = new Set(['mcp', 'bridge', 'tailscale', 'handoff', 'auto']);

  if (!allowedRealms.has(source) || !allowedRealms.has(destination)) return { error: 'Unknown realm' };
  if (source === destination) return { error: 'Source and destination must differ' };
  if (!allowedTransports.has(transport)) return { error: 'Unsupported transport' };
  if (!intent || intent.length > 1000) return { error: 'Intent is required and must be under 1000 characters' };
  if (payload.length > 12000) return { error: 'Payload exceeds 12KB operator limit' };

  return { source, destination, transport, intent, payload };
}

async function worldMonitorMcpCall(method, params = {}) {
  const target = new URL('/mcp', REALMS.worldmonitor.baseUrl).toString();
  const envelope = {
    jsonrpc: '2.0',
    id: `bifrost-${Date.now()}`,
    method,
    params,
  };
  const response = await fetchWithTimeout(target, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json, text/event-stream',
      'User-Agent': 'Camelot-Bifrost/1.0',
    },
    body: JSON.stringify(envelope),
  }, 8000);
  const text = await response.text();
  return { ok: response.ok, status: response.status, text: text.slice(0, 16000) };
}

async function executeCrossing(crossing) {
  const { source, destination, transport, intent, payload } = crossing;

  // Bifrost never acts as a generic open proxy. Every remote destination is
  // selected from REALMS above, and each adapter exposes only a narrow action.
  if (destination === 'worldmonitor' && transport === 'mcp') {
    // This performs a safe MCP capability discovery. Tool execution is a
    // separate future gate because it requires tool-specific schemas and auth.
    const result = await worldMonitorMcpCall('tools/list', {});
    if (!result.ok) {
      return { result: `MCP DISCOVERY FAILED (${result.status})`, detail: result.text };
    }
    return { result: 'MCP CAPABILITIES DISCOVERED', detail: result.text };
  }

  if (destination === 'multivoice' && (transport === 'bridge' || transport === 'tailscale')) {
    const probe = await probeRealm('multivoice');
    if (!probe.reachable) return { result: 'MULTIVOICE UNREACHABLE', detail: probe.detail };
    return {
      result: 'MULTIVOICE HANDOFF READY',
      requiresHandoff: true,
      launchUrl: REALMS.multivoice.launchUrl,
      detail: 'Bridge health verified. Remote voice/persona mutation remains an explicit action inside Multivoice-router.',
    };
  }

  if (destination === 'godseye') {
    const probe = await probeRealm('godseye');
    return {
      result: probe.reachable ? 'SPATIAL HANDOFF READY' : 'SPATIAL SURFACE UNVERIFIED',
      requiresHandoff: true,
      launchUrl: REALMS.godseye.launchUrl,
      detail: `${probe.detail}. Intent preserved for operator handoff: ${intent}${payload ? ' // payload supplied' : ''}`,
    };
  }

  if (destination === 'worldmonitor' && transport !== 'mcp') {
    const probe = await probeRealm('worldmonitor');
    return {
      result: probe.reachable ? 'WORLDMONITOR HANDOFF READY' : 'WORLDMONITOR UNVERIFIED',
      requiresHandoff: true,
      launchUrl: REALMS.worldmonitor.launchUrl,
      detail: probe.detail,
    };
  }

  return {
    result: 'ROUTE VALIDATED',
    detail: 'Crossing contract validated locally. No remote mutation was performed.',
  };
}

async function serveStatic(req, res, pathname) {
  const requested = pathname === '/' ? '/index.html' : pathname;
  const safePath = normalize(requested).replace(/^([.][.][/\\])+/, '');
  const filePath = join(ROOT, safePath);
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  try {
    const info = await stat(filePath);
    if (!info.isFile()) throw new Error('Not a file');
    const body = await readFile(filePath);
    res.writeHead(200, {
      'Content-Type': MIME[extname(filePath)] || 'application/octet-stream',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Content-Security-Policy': "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'",
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not found');
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host || `${HOST}:${PORT}`}`);

  if (req.method === 'GET' && url.pathname === '/api/bifrost/config') {
    return sendJson(res, 200, {
      realms: Object.fromEntries(Object.entries(REALMS).map(([id, realm]) => [id, { launchUrl: realm.launchUrl }])),
      policy: 'allowlisted-fail-closed',
    });
  }

  const probeMatch = url.pathname.match(/^\/api\/bifrost\/probe\/(multivoice|godseye|worldmonitor)$/);
  if (req.method === 'GET' && probeMatch) {
    const result = await probeRealm(probeMatch[1]);
    return sendJson(res, 200, result);
  }

  if (req.method === 'POST' && url.pathname === '/api/bifrost/crossing') {
    try {
      const body = await readJson(req);
      const crossing = validateCrossing(body);
      if (crossing.error) return sendJson(res, 400, crossing);
      const result = await executeCrossing(crossing);
      return sendJson(res, 200, result);
    } catch (error) {
      return sendJson(res, 500, { error: error instanceof Error ? error.message : 'Crossing failed' });
    }
  }

  if (url.pathname.startsWith('/api/')) return sendJson(res, 404, { error: 'Unknown Bifrost endpoint' });
  return serveStatic(req, res, url.pathname);
});

server.listen(PORT, HOST, () => {
  console.log(`[BIFROST] Hermes/Heimdall command center listening on http://${HOST}:${PORT}`);
  console.log('[BIFROST] Remote targets are allowlisted. No arbitrary proxy route is exposed.');
});
