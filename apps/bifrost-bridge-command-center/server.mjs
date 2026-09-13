import http from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const PORT = Number(process.env.BIFROST_PORT || 4188);
const HOST = process.env.BIFROST_HOST || '127.0.0.1';
const SHADOWD_URL = String(process.env.CAMELOT_SHADOW_URL || 'http://127.0.0.1:4190').replace(/\/$/, '');
const SHADOWD_TOKEN = String(process.env.CAMELOT_SHADOW_TOKEN || '');
const HITL_TOKEN = String(process.env.CAMELOT_HITL_TOKEN || '');
const ALLOWED_ORIGINS = new Set(
  String(process.env.BIFROST_ALLOWED_ORIGINS || 'http://127.0.0.1:3000,http://localhost:3000')
    .split(',')
    .map(value => value.trim())
    .filter(Boolean)
);

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

function corsHeaders(req) {
  const origin = req.headers.origin;
  if (!origin || !ALLOWED_ORIGINS.has(origin)) return {};
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    // Deliberately excludes X-Camelot-HITL-Assertion. Browser JavaScript is not
    // an authenticated human-approval surface.
    'Access-Control-Allow-Headers': 'Content-Type,Accept',
    'Access-Control-Max-Age': '600',
    Vary: 'Origin',
  };
}

function sendJson(req, res, status, payload) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    ...corsHeaders(req),
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

function secureEquals(actual, expected) {
  const a = Buffer.from(String(actual || ''), 'utf8');
  const b = Buffer.from(String(expected || ''), 'utf8');
  if (!a.length || a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

function requireHitlAssertion(req) {
  if (!HITL_TOKEN || HITL_TOKEN.length < 24) {
    return { ok: false, status: 503, error: 'Authenticated HITL is not configured on Bifrost' };
  }
  const supplied = req.headers['x-camelot-hitl-assertion'];
  if (!secureEquals(supplied, HITL_TOKEN)) {
    return { ok: false, status: 403, error: 'A valid server-authenticated HITL assertion is required' };
  }
  return { ok: true };
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
        'User-Agent': 'Camelot-Bifrost/1.2',
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
  const envelope = { jsonrpc: '2.0', id: `bifrost-${Date.now()}`, method, params };
  const response = await fetchWithTimeout(target, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json, text/event-stream',
      'User-Agent': 'Camelot-Bifrost/1.2',
    },
    body: JSON.stringify(envelope),
  }, 8000);
  const text = await response.text();
  return { ok: response.ok, status: response.status, text: text.slice(0, 16000) };
}

async function executeCrossing(crossing) {
  const { destination, transport, intent, payload } = crossing;

  if (destination === 'worldmonitor' && transport === 'mcp') {
    const result = await worldMonitorMcpCall('tools/list', {});
    if (!result.ok) return { result: `MCP DISCOVERY FAILED (${result.status})`, detail: result.text };
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

  return { result: 'ROUTE VALIDATED', detail: 'Crossing contract validated locally. No remote mutation was performed.' };
}

async function shadowRequest(path, init = {}, requireAuth = true) {
  if (requireAuth && !SHADOWD_TOKEN) {
    return { ok: false, status: 503, body: { error: 'Shadow Subspace is not configured on this Bifrost gateway' } };
  }
  const response = await fetchWithTimeout(`${SHADOWD_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(requireAuth ? { Authorization: `Bearer ${SHADOWD_TOKEN}` } : {}),
      ...(init.headers || {}),
    },
  }, 7000);
  const text = await response.text();
  let body;
  try { body = text ? JSON.parse(text) : {}; }
  catch { body = { detail: text.slice(0, 16000) }; }
  return { ok: response.ok, status: response.status, body };
}

async function proxyShadow(req, res, path, { method = 'GET', body = null, requireAuth = true } = {}) {
  try {
    const result = await shadowRequest(path, {
      method,
      ...(body === null ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    }, requireAuth);
    return sendJson(req, res, result.status, result.body);
  } catch (error) {
    return sendJson(req, res, 502, { error: error instanceof Error ? error.message : 'Shadow Subspace unavailable' });
  }
}

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

async function serveStatic(req, res, pathname) {
  const requested = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const filePath = resolve(ROOT, requested);
  const rootPrefix = ROOT.endsWith(sep) ? ROOT : `${ROOT}${sep}`;
  if (filePath !== ROOT && !filePath.startsWith(rootPrefix)) {
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
      ...corsHeaders(req),
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8', ...corsHeaders(req) });
    res.end('Not found');
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host || `${HOST}:${PORT}`}`);

  if (req.method === 'OPTIONS' && url.pathname.startsWith('/api/bifrost/')) {
    const headers = corsHeaders(req);
    if (!Object.keys(headers).length && req.headers.origin) {
      return sendJson(req, res, 403, { error: 'Origin not allowed by Bifrost' });
    }
    res.writeHead(204, headers);
    return res.end();
  }

  if (req.method === 'GET' && url.pathname === '/api/bifrost/config') {
    return sendJson(req, res, 200, {
      realms: Object.fromEntries(Object.entries(REALMS).map(([id, realm]) => [id, { launchUrl: realm.launchUrl }])),
      shadow: {
        configured: Boolean(SHADOWD_TOKEN),
        boundary: 'loopback-authenticated',
        publicCredentialExposure: false,
        hitlAuthenticated: Boolean(HITL_TOKEN && HITL_TOKEN.length >= 24),
      },
      policy: 'allowlisted-fail-closed',
      allowedOrigins: [...ALLOWED_ORIGINS],
    });
  }

  const probeMatch = url.pathname.match(/^\/api\/bifrost\/probe\/(multivoice|godseye|worldmonitor)$/);
  if (req.method === 'GET' && probeMatch) {
    const result = await probeRealm(probeMatch[1]);
    return sendJson(req, res, 200, result);
  }

  if (req.method === 'POST' && url.pathname === '/api/bifrost/crossing') {
    try {
      const body = await readJson(req);
      const crossing = validateCrossing(body);
      if (crossing.error) return sendJson(req, res, 400, crossing);
      const result = await executeCrossing(crossing);
      return sendJson(req, res, 200, result);
    } catch (error) {
      return sendJson(req, res, 500, { error: error instanceof Error ? error.message : 'Crossing failed' });
    }
  }

  if (req.method === 'GET' && url.pathname === '/api/bifrost/shadow/health') {
    return proxyShadow(req, res, '/health', { requireAuth: false });
  }
  if (req.method === 'GET' && url.pathname === '/api/bifrost/shadow/sessions') {
    return proxyShadow(req, res, '/v1/shadow/sessions');
  }
  if (req.method === 'POST' && url.pathname === '/api/bifrost/shadow/sessions') {
    try { return proxyShadow(req, res, '/v1/shadow/sessions', { method: 'POST', body: await readJson(req) }); }
    catch (error) { return sendJson(req, res, 400, { error: error instanceof Error ? error.message : 'Invalid session request' }); }
  }

  const sessionMatch = url.pathname.match(/^\/api\/bifrost\/shadow\/sessions\/([^/]+)$/);
  if (req.method === 'GET' && sessionMatch && isUuid(sessionMatch[1])) {
    return proxyShadow(req, res, `/v1/shadow/sessions/${sessionMatch[1]}`);
  }

  const effectListMatch = url.pathname.match(/^\/api\/bifrost\/shadow\/sessions\/([^/]+)\/effects$/);
  if (req.method === 'POST' && effectListMatch && isUuid(effectListMatch[1])) {
    try { return proxyShadow(req, res, `/v1/shadow/sessions/${effectListMatch[1]}/effects`, { method: 'POST', body: await readJson(req) }); }
    catch (error) { return sendJson(req, res, 400, { error: error instanceof Error ? error.message : 'Invalid effect request' }); }
  }

  const approvalMatch = url.pathname.match(/^\/api\/bifrost\/shadow\/sessions\/([^/]+)\/effects\/([^/]+)\/(approve|deny)$/);
  if (req.method === 'POST' && approvalMatch && isUuid(approvalMatch[1]) && isUuid(approvalMatch[2])) {
    const hitl = requireHitlAssertion(req);
    if (!hitl.ok) return sendJson(req, res, hitl.status, { error: hitl.error });
    try {
      const [, sessionId, effectId, decision] = approvalMatch;
      return proxyShadow(req, res, `/v1/shadow/sessions/${sessionId}/effects/${effectId}/${decision}`, { method: 'POST', body: await readJson(req) });
    } catch (error) {
      return sendJson(req, res, 400, { error: error instanceof Error ? error.message : 'Invalid HITL decision' });
    }
  }

  const writeMatch = url.pathname.match(/^\/api\/bifrost\/shadow\/sessions\/([^/]+)\/files\/write$/);
  if (req.method === 'POST' && writeMatch && isUuid(writeMatch[1])) {
    try { return proxyShadow(req, res, `/v1/shadow/sessions/${writeMatch[1]}/files/write`, { method: 'POST', body: await readJson(req) }); }
    catch (error) { return sendJson(req, res, 400, { error: error instanceof Error ? error.message : 'Invalid shadow write' }); }
  }

  const readMatch = url.pathname.match(/^\/api\/bifrost\/shadow\/sessions\/([^/]+)\/files\/read$/);
  if (req.method === 'GET' && readMatch && isUuid(readMatch[1])) {
    const path = String(url.searchParams.get('path') || '');
    if (!path || path.length > 512) return sendJson(req, res, 400, { error: 'A bounded shadow path is required' });
    return proxyShadow(req, res, `/v1/shadow/sessions/${readMatch[1]}/files/read?path=${encodeURIComponent(path)}`);
  }

  const receiptsMatch = url.pathname.match(/^\/api\/bifrost\/shadow\/sessions\/([^/]+)\/receipts$/);
  if (req.method === 'GET' && receiptsMatch && isUuid(receiptsMatch[1])) {
    return proxyShadow(req, res, `/v1/shadow/sessions/${receiptsMatch[1]}/receipts`);
  }

  const sealMatch = url.pathname.match(/^\/api\/bifrost\/shadow\/sessions\/([^/]+)\/seal$/);
  if (req.method === 'POST' && sealMatch && isUuid(sealMatch[1])) {
    return proxyShadow(req, res, `/v1/shadow/sessions/${sealMatch[1]}/seal`, { method: 'POST', body: {} });
  }

  if (url.pathname.startsWith('/api/')) return sendJson(req, res, 404, { error: 'Unknown Bifrost endpoint' });
  return serveStatic(req, res, url.pathname);
});

server.listen(PORT, HOST, () => {
  console.log(`[BIFROST] Hermes/Heimdall command center listening on http://${HOST}:${PORT}`);
  console.log('[BIFROST] Remote targets are allowlisted. No arbitrary proxy route is exposed.');
  console.log(`[BIFROST] Shadow Subspace adapter: ${SHADOWD_TOKEN ? 'configured' : 'disabled (missing CAMELOT_SHADOW_TOKEN)'}`);
  console.log(`[BIFROST] Authenticated HITL: ${HITL_TOKEN && HITL_TOKEN.length >= 24 ? 'configured' : 'disabled'}`);
  console.log(`[BIFROST] Allowed UI origins: ${[...ALLOWED_ORIGINS].join(', ') || '(none)'}`);
});
