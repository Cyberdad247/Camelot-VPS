const REALMS = {
  camelot: {
    name: 'Camelot-VPS',
    role: 'Sovereign command plane',
    transport: 'Internal command bus',
    endpoint: 'local://camelot-vps',
    repo: 'https://github.com/Cyberdad247/Camelot-VPS',
    launch: '../../',
    probe: null,
  },
  multivoice: {
    name: 'Multivoice-router',
    role: 'Voice + persona routing',
    transport: 'Bridge Proxy / Tailscale',
    endpoint: '/api/bridge/query',
    repo: 'https://github.com/Cyberdad247/Multivoice-router',
    launch: 'https://obsidian-spire-hud.vercel.app',
    probe: '/api/bifrost/probe/multivoice',
  },
  godseye: {
    name: "God's Eye View",
    role: 'Spatial intelligence + live globe',
    transport: 'UI / serialized view handoff',
    endpoint: 'https://maptheworld.ai/',
    repo: 'https://github.com/Cyberdad247/gods-eye-view',
    launch: 'https://maptheworld.ai/',
    probe: '/api/bifrost/probe/godseye',
  },
  worldmonitor: {
    name: 'WorldMonitor',
    role: 'Global intelligence + OSINT',
    transport: 'MCP / OpenAPI',
    endpoint: 'https://worldmonitor.app/mcp',
    repo: 'https://github.com/koala73/worldmonitor',
    launch: 'https://worldmonitor.app',
    probe: '/api/bifrost/probe/worldmonitor',
  },
};

const state = {
  selectedRealm: 'multivoice',
  sealed: false,
  gates: {
    identity: true,
    integrity: true,
    intent: true,
    payload: true,
    access: true,
  },
  statuses: {
    camelot: 'online',
    multivoice: 'unknown',
    godseye: 'unknown',
    worldmonitor: 'unknown',
  },
  receipts: [
    {
      at: new Date(Date.now() - 1000 * 60 * 8),
      path: 'Camelot-VPS → Heimdall → Multivoice-router',
      transport: 'Bridge contract',
      result: 'REGISTERED',
    },
  ],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function realmLabel(id) {
  return REALMS[id]?.name || id;
}

function setStatus(realmId, status, detail = '') {
  state.statuses[realmId] = status;
  const dot = document.querySelector(`#status-${realmId}`);
  if (dot) {
    dot.classList.remove('online', 'unknown', 'degraded', 'offline');
    dot.classList.add(status);
    dot.title = detail || status;
  }
  if (state.selectedRealm === realmId) updateInspector(realmId);
}

function updateInspector(realmId) {
  const realm = REALMS[realmId];
  if (!realm) return;
  state.selectedRealm = realmId;
  $$('.realm-node').forEach((node) => node.classList.toggle('active', node.dataset.realm === realmId));
  $('#realmName').textContent = realm.name;
  $('#realmRole').textContent = realm.role;
  $('#realmTransport').textContent = realm.transport;
  $('#realmEndpoint').textContent = realm.endpoint;
  $('#realmStatus').textContent = (state.statuses[realmId] || 'unknown').toUpperCase();
  $('#repoLink').href = realm.repo;
  $('#launchRealm').dataset.href = realm.launch;
}

function updateGateSummary() {
  const passing = Object.values(state.gates).filter(Boolean).length;
  $('#gateCount').textContent = `${passing}/05`;
  $('#bridgeModeLabel').textContent = state.sealed ? 'BIFROST SEALED' : passing === 5 ? 'OPERATOR CONTROLLED' : 'CROSSING BLOCKED';
  document.body.classList.toggle('bridge-sealed', state.sealed || passing < 5);
}

function renderLedger() {
  const host = $('#ledgerRows');
  if (!state.receipts.length) {
    host.innerHTML = '<div class="ledger-empty">No local crossing receipts in this view.</div>';
    $('#receiptCount').textContent = '0000';
    return;
  }
  host.innerHTML = state.receipts
    .slice()
    .reverse()
    .map((receipt) => `
      <div class="ledger-row">
        <time>${receipt.at.toLocaleTimeString([], { hour12: false })}</time>
        <span class="ledger-path">${escapeHtml(receipt.path)}</span>
        <span class="ledger-transport">${escapeHtml(receipt.transport)}</span>
        <strong class="ledger-result">${escapeHtml(receipt.result)}</strong>
      </div>
    `)
    .join('');
  $('#receiptCount').textContent = String(state.receipts.length).padStart(4, '0');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function chooseTransport(source, destination, requested) {
  if (requested !== 'auto') return requested;
  if (source === 'worldmonitor' || destination === 'worldmonitor') return 'mcp';
  if (source === 'multivoice' || destination === 'multivoice') return 'bridge';
  if (source === 'godseye' || destination === 'godseye') return 'handoff';
  return 'tailscale';
}

function previewRoute() {
  const source = $('#routeSource').value;
  const destination = $('#routeDestination').value;
  const requested = $('#routeTransport').value;
  const transport = chooseTransport(source, destination, requested);
  $('#transportMode').textContent = transport.toUpperCase();
  $('#routePreview').innerHTML = `
    <span>${escapeHtml(realmLabel(source).toUpperCase())}</span>
    <b>→</b>
    <span>HEIMDALL 5-GATE CHECK</span>
    <b>→</b>
    <span>${escapeHtml(transport.toUpperCase())}</span>
    <b>→</b>
    <span>${escapeHtml(realmLabel(destination).toUpperCase())}</span>
  `;
  return { source, destination, transport };
}

async function probeRealm(realmId) {
  const realm = REALMS[realmId];
  if (!realm?.probe) return;
  setStatus(realmId, 'unknown', 'Probing…');
  try {
    const response = await fetch(realm.probe, { headers: { Accept: 'application/json' } });
    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload.reachable === true) {
      setStatus(realmId, 'online', payload.detail || 'Reachable through Bifrost gateway');
    } else if (response.ok && payload.reachable === false) {
      setStatus(realmId, 'degraded', payload.detail || 'Probe completed without a successful upstream response');
    } else {
      setStatus(realmId, 'degraded', payload.error || `Gateway probe failed (${response.status})`);
    }
  } catch (error) {
    setStatus(realmId, 'unknown', 'Bifrost gateway is not running; status remains unverified.');
  }
}

async function probeAll() {
  await Promise.all(['multivoice', 'godseye', 'worldmonitor'].map(probeRealm));
}

function gateAllowsCrossing() {
  return !state.sealed && Object.values(state.gates).every(Boolean);
}

async function requestCrossing(event) {
  event.preventDefault();
  const { source, destination, transport } = previewRoute();
  const intent = $('#routeIntent').value.trim();
  const payload = $('#routePayload').value.trim();

  if (!intent) {
    addReceipt(source, destination, transport, 'BLOCKED: NO INTENT');
    return;
  }

  if (!gateAllowsCrossing()) {
    addReceipt(source, destination, transport, 'BLOCKED BY HEIMDALL');
    return;
  }

  const request = { source, destination, transport, intent, payload };
  const submit = event.submitter;
  if (submit) {
    submit.disabled = true;
    submit.textContent = 'Requesting…';
  }

  try {
    const response = await fetch('/api/bifrost/crossing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(request),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      addReceipt(source, destination, transport, result.error ? `DENIED: ${result.error}` : `DENIED (${response.status})`);
      return;
    }
    addReceipt(source, destination, transport, result.result || 'ACCEPTED');
    if (result.launchUrl && result.requiresHandoff) {
      const shouldOpen = window.confirm('The crossing is approved and requires a UI handoff. Open the destination surface?');
      if (shouldOpen) window.open(result.launchUrl, '_blank', 'noopener,noreferrer');
    }
  } catch (error) {
    addReceipt(source, destination, transport, 'GATEWAY NOT RUNNING');
  } finally {
    if (submit) {
      submit.disabled = false;
      submit.textContent = 'Request Crossing';
    }
  }
}

function addReceipt(source, destination, transport, result) {
  state.receipts.push({
    at: new Date(),
    path: `${realmLabel(source)} → Heimdall → ${realmLabel(destination)}`,
    transport,
    result,
  });
  renderLedger();
}

function wireUi() {
  $$('.realm-node').forEach((node) => {
    node.addEventListener('click', () => updateInspector(node.dataset.realm));
  });

  $$('.gate-row').forEach((row) => {
    row.addEventListener('click', () => {
      const gate = row.dataset.gate;
      state.gates[gate] = !state.gates[gate];
      row.classList.toggle('pass', state.gates[gate]);
      row.classList.toggle('block', !state.gates[gate]);
      row.querySelector('b').textContent = state.gates[gate] ? 'PASS' : 'BLOCK';
      updateGateSummary();
    });
  });

  $('#sealBridge').addEventListener('click', () => {
    state.sealed = true;
    updateGateSummary();
    addReceipt('camelot', state.selectedRealm, 'policy', 'BIFROST SEALED');
  });

  $('#restoreBridge').addEventListener('click', () => {
    state.sealed = false;
    Object.keys(state.gates).forEach((gate) => { state.gates[gate] = true; });
    $$('.gate-row').forEach((row) => {
      row.classList.add('pass');
      row.classList.remove('block');
      row.querySelector('b').textContent = 'PASS';
    });
    updateGateSummary();
  });

  $('#previewRoute').addEventListener('click', previewRoute);
  $('#routeForm').addEventListener('submit', requestCrossing);
  ['routeSource', 'routeDestination', 'routeTransport'].forEach((id) => $(`#${id}`).addEventListener('change', previewRoute));

  $('#refreshAll').addEventListener('click', probeAll);
  $('#focusHermes').addEventListener('click', () => $('#routingForge').scrollIntoView({ behavior: 'smooth', block: 'center' }));
  $('#focusHeimdall').addEventListener('click', () => $('#gatehouse').scrollIntoView({ behavior: 'smooth', block: 'center' }));
  $('#launchRealm').addEventListener('click', () => {
    const href = $('#launchRealm').dataset.href;
    if (href) window.open(href, '_blank', 'noopener,noreferrer');
  });
  $('#clearLedger').addEventListener('click', () => {
    state.receipts = [];
    renderLedger();
  });
}

wireUi();
updateInspector('multivoice');
updateGateSummary();
renderLedger();
previewRoute();
probeAll();
