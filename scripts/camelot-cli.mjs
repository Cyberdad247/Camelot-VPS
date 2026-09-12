#!/usr/bin/env node
import { createInterface } from 'node:readline';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

const VERSION = '1.1.0';
const STATE_PATH = process.env.CAMELOT_CLI_STATE || join(homedir(), '.camelot', 'command-center-state.json');
const BIFROST_URL = process.env.BIFROST_URL || process.env.VITE_BIFROST_URL || 'http://127.0.0.1:4188';

const scenes = [
  ['overview', '00', 'Battle State', 'Understand the overall condition before acting.'],
  ['threats', '01', 'Threat Matrix', 'Identify which attack vectors are active and where they are aimed.'],
  ['telemetry', '02', 'Tactical Telemetry', 'Measure pressure, readiness, shield integrity, and response latency.'],
  ['defense', '03', 'Defense Grid', 'Arm or isolate the seven protection layers.'],
  ['brains', '04', 'Twin Brains', 'Inspect synchronized reasoning and strategic context.'],
  ['ouroboros', '05', 'Ouroboros SSM', 'Inspect recurrent tactical state and continuity.'],
  ['vfs', '06', 'VFS Defense Fabric', 'Inspect protected data movement through Camelot roots.'],
  ['counter', '07', 'Countermeasures', 'Deploy active response and reduce threat pressure.'],
  ['command', '08', 'Command Deck', 'Review events and issue sovereign commands.'],
];

const defenses = {
  memcastle: 'MemCastle Shield',
  context: 'Context Filter',
  firewall: 'AI Firewall',
  inference: 'Inference Guard',
  sandbox: 'Data Sandbox',
  vfs: 'VFS Perimeter',
  physical: 'Physical Layer',
};

const threatTypes = ['ddos', 'prompt-injection', 'data-exfiltration', 'ai-adversary', 'reconnaissance'];
const bifrostRealms = ['multivoice', 'godseye', 'worldmonitor'];
const bifrostTransports = ['mcp', 'bridge', 'tailscale', 'handoff', 'auto'];

const defaultState = () => ({
  version: VERSION,
  mode: 'battle',
  scene: 'overview',
  threatFilter: 'prompt-injection',
  threatCount: 247,
  shieldIntegrity: 99.7,
  responseLatency: 12,
  autoResponse: true,
  defenses: Object.fromEntries(Object.keys(defenses).map(id => [id, true])),
  logs: [{ at: new Date().toISOString(), message: 'CLI COMMAND CENTER INITIALIZED' }],
});

function color(code, text) {
  if (!process.stdout.isTTY || process.env.NO_COLOR) return text;
  return `\x1b[${code}m${text}\x1b[0m`;
}
const cyan = text => color('36', text);
const gold = text => color('33', text);
const green = text => color('32', text);
const red = text => color('31', text);
const dim = text => color('2', text);
const bold = text => color('1', text);

async function loadState() {
  try {
    const parsed = JSON.parse(await readFile(STATE_PATH, 'utf8'));
    return { ...defaultState(), ...parsed, defenses: { ...defaultState().defenses, ...(parsed.defenses || {}) } };
  } catch {
    return defaultState();
  }
}

async function saveState(state) {
  await mkdir(dirname(STATE_PATH), { recursive: true });
  await writeFile(STATE_PATH, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
}

function appendLog(state, message) {
  state.logs = [{ at: new Date().toISOString(), message }, ...(state.logs || [])].slice(0, 100);
}

function sceneInfo(id) {
  return scenes.find(scene => scene[0] === id);
}

function readiness(state) {
  const active = Object.values(state.defenses).filter(Boolean).length;
  return Math.round((active / Object.keys(defenses).length) * 100);
}

function banner() {
  console.log(`${gold('♜')} ${bold('CAMELOT-OS')} ${cyan('SOVEREIGN TERMINAL')} ${dim(`v${VERSION}`)}`);
  console.log(dim('World Director · Battle Mode · Bifrost'));
}

function printStatus(state) {
  const scene = sceneInfo(state.scene) || scenes[0];
  const modeColor = state.mode === 'lockdown' ? gold : state.mode === 'battle' ? red : green;
  console.log(`\n${bold('SYSTEM STATUS')}`);
  console.log(`  Mode          ${modeColor(state.mode.toUpperCase())}`);
  console.log(`  Scene         ${gold(scene[1])} ${scene[2]} ${dim(`(${scene[0]})`)}`);
  console.log(`  Threats       ${state.threatCount}`);
  console.log(`  Filter        ${state.threatFilter}`);
  console.log(`  Defense       ${readiness(state)}% ready`);
  console.log(`  Shield        ${state.shieldIntegrity.toFixed(1)}%`);
  console.log(`  Latency       ${state.responseLatency}ms`);
  console.log(`  Auto-response ${state.autoResponse ? green('ENABLED') : red('DISABLED')}`);
  console.log(`  Bifrost       ${dim(BIFROST_URL)}`);
  console.log(`  State file    ${dim(STATE_PATH)}\n`);
}

function help() {
  console.log(`\n${bold('CAMELOT CLI COMMANDS')}\n`);
  console.log(`  ${cyan('status')}                              system snapshot`);
  console.log(`  ${cyan('mode')} <nominal|battle|lockdown>      change Battle Mode state`);
  console.log(`  ${cyan('scene list')}                          list World Director scenes`);
  console.log(`  ${cyan('scene go')} <id|00..08>                move terminal context to a scene`);
  console.log(`  ${cyan('scene explain')} [id]                  explain current/selected subsystem`);
  console.log(`  ${cyan('threat list')}                         list threat filters`);
  console.log(`  ${cyan('threat filter')} <type>                apply threat filter`);
  console.log(`  ${cyan('defense list')}                        show seven defense layers`);
  console.log(`  ${cyan('defense arm|disarm|toggle')} <id>      change one defense layer`);
  console.log(`  ${cyan('defense all')} <on|off>                arm/disarm all layers`);
  console.log(`  ${cyan('auto')} <on|off>                       toggle autonomous response`);
  console.log(`  ${cyan('counter deploy')}                      deploy countermeasure swarm`);
  console.log(`  ${cyan('command')} <text...>                   record sovereign command`);
  console.log(`  ${cyan('log')} [count]                         show recent battle events`);
  console.log(`  ${cyan('bifrost status')}                      read Bifrost gateway config`);
  console.log(`  ${cyan('bifrost probe')} <realm>               probe multivoice|godseye|worldmonitor`);
  console.log(`  ${cyan('bifrost cross')} <realm> <transport> <intent...>`);
  console.log(`                                        request a governed crossing`);
  console.log(`  ${cyan('reset')}                               reset CLI operational state`);
  console.log(`  ${cyan('help')}                                show this command map`);
  console.log(`  ${cyan('exit')}                                leave interactive terminal\n`);
  console.log(dim('One-shot: `npm run camelot -- status` · Interactive: `npm run camelot`'));
}

function resolveScene(value) {
  if (!value) return null;
  const normalized = value.toLowerCase();
  return scenes.find(scene => scene[0] === normalized || scene[1] === normalized) || null;
}

function normalizeThreat(value = '') {
  return value.trim().toLowerCase().replace(/\s+/g, '-');
}

async function bifrostRequest(path, init = {}) {
  const url = `${BIFROST_URL}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: { accept: 'application/json', ...(init.headers || {}) },
    });
    const body = await response.json().catch(() => ({ status: response.status }));
    if (!response.ok) throw new Error(body?.error || `HTTP ${response.status}`);
    return body;
  } finally {
    clearTimeout(timer);
  }
}

async function execute(argv, state) {
  const [command = 'help', sub, ...rest] = argv;
  switch (command.toLowerCase()) {
    case 'status': printStatus(state); break;
    case 'mode': {
      const next = String(sub || '').toLowerCase();
      if (!['nominal', 'battle', 'lockdown'].includes(next)) throw new Error('mode requires nominal, battle, or lockdown');
      state.mode = next;
      if (next === 'nominal') { state.threatCount = 18; state.responseLatency = 22; }
      if (next === 'battle') { state.threatCount = Math.max(state.threatCount, 247); state.responseLatency = 12; }
      if (next === 'lockdown') {
        state.threatCount = Math.max(state.threatCount, 247); state.shieldIntegrity = 100; state.responseLatency = 8; state.autoResponse = true;
        Object.keys(defenses).forEach(id => { state.defenses[id] = true; });
      }
      appendLog(state, `${next.toUpperCase()} STATE ENGAGED`);
      console.log(green(`✓ ${next.toUpperCase()} engaged`));
      break;
    }
    case 'scene': {
      if (sub === 'list' || !sub) { scenes.forEach(([id, index, label]) => console.log(`${state.scene === id ? green('●') : dim('○')} ${gold(index)} ${label.padEnd(22)} ${dim(id)}`)); break; }
      if (sub === 'go') {
        const target = resolveScene(rest[0]); if (!target) throw new Error(`unknown scene: ${rest[0] || '(missing)'}`);
        state.scene = target[0]; appendLog(state, `WORLD DIRECTOR CONTEXT // ${target[2].toUpperCase()}`);
        console.log(green(`✓ Context moved to ${target[1]} ${target[2]}`)); console.log(dim(target[3])); break;
      }
      if (sub === 'explain') { const target = resolveScene(rest[0]) || sceneInfo(state.scene); console.log(`${gold(target[1])} ${bold(target[2])}\n${target[3]}`); break; }
      throw new Error('scene supports list, go <id>, or explain [id]');
    }
    case 'threat': {
      if (sub === 'list' || !sub) { threatTypes.forEach(type => console.log(`${state.threatFilter === type ? green('●') : dim('○')} ${type}`)); break; }
      if (sub === 'filter') {
        const type = normalizeThreat(rest.join(' ')); if (!threatTypes.includes(type)) throw new Error(`unknown threat type: ${type || '(missing)'}`);
        state.threatFilter = type; appendLog(state, `THREAT FILTER // ${type.toUpperCase()}`); console.log(green(`✓ Threat filter applied: ${type}`)); break;
      }
      throw new Error('threat supports list or filter <type>');
    }
    case 'defense': {
      if (sub === 'list' || !sub) { Object.entries(defenses).forEach(([id, label]) => console.log(`${state.defenses[id] ? green('● ACTIVE') : red('○ OFFLINE')}  ${label.padEnd(22)} ${dim(id)}`)); break; }
      if (sub === 'all') {
        const enabled = rest[0] === 'on'; if (!['on', 'off'].includes(rest[0])) throw new Error('defense all requires on or off');
        Object.keys(defenses).forEach(id => { state.defenses[id] = enabled; }); appendLog(state, `ALL DEFENSE LAYERS ${enabled ? 'ARMED' : 'DISARMED'}`);
        console.log(enabled ? green('✓ All defense layers armed') : red('! All defense layers disarmed')); break;
      }
      if (['arm', 'disarm', 'toggle'].includes(sub)) {
        const id = rest[0]; if (!defenses[id]) throw new Error(`unknown defense: ${id || '(missing)'}`);
        state.defenses[id] = sub === 'toggle' ? !state.defenses[id] : sub === 'arm'; appendLog(state, `${defenses[id].toUpperCase()} ${state.defenses[id] ? 'ARMED' : 'DISARMED'}`);
        console.log(`${state.defenses[id] ? green('✓ ARMED') : red('! DISARMED')} ${defenses[id]}`); break;
      }
      throw new Error('defense supports list, all <on|off>, arm|disarm|toggle <id>');
    }
    case 'auto': {
      if (!['on', 'off'].includes(sub)) throw new Error('auto requires on or off'); state.autoResponse = sub === 'on';
      appendLog(state, `AUTONOMOUS RESPONSE ${state.autoResponse ? 'ENABLED' : 'DISABLED'}`); console.log(green(`✓ Autonomous response ${state.autoResponse ? 'enabled' : 'disabled'}`)); break;
    }
    case 'counter': {
      if (sub !== 'deploy') throw new Error('counter currently supports deploy');
      state.threatCount = Math.max(0, state.threatCount - 64); state.shieldIntegrity = Math.min(100, state.shieldIntegrity + 0.2); state.responseLatency = Math.max(6, state.responseLatency - 2);
      appendLog(state, 'COUNTERMEASURE SWARM DEPLOYED // 1,284 ROUTES/MIN'); console.log(green('✓ Countermeasure swarm deployed'));
      console.log(dim(`Threats ${state.threatCount} · Shield ${state.shieldIntegrity.toFixed(1)}% · Latency ${state.responseLatency}ms`)); break;
    }
    case 'command': {
      const text = [sub, ...rest].filter(Boolean).join(' ').trim(); if (!text) throw new Error('command requires text');
      appendLog(state, `COMMAND EXECUTED // ${text.toUpperCase()}`); console.log(green(`✓ Command recorded: ${text}`)); break;
    }
    case 'log': {
      const count = Math.min(50, Math.max(1, Number.parseInt(sub || '10', 10) || 10)); (state.logs || []).slice(0, count).forEach(item => console.log(`${dim(item.at)}  ${item.message}`)); break;
    }
    case 'bifrost': {
      if (sub === 'status') { console.log(JSON.stringify(await bifrostRequest('/api/bifrost/config'), null, 2)); break; }
      if (sub === 'probe') {
        const realm = rest[0]; if (!bifrostRealms.includes(realm)) throw new Error('bifrost probe requires multivoice, godseye, or worldmonitor');
        console.log(JSON.stringify(await bifrostRequest(`/api/bifrost/probe/${realm}`), null, 2)); break;
      }
      if (sub === 'cross') {
        const [destination, transport, ...intentParts] = rest;
        if (!bifrostRealms.includes(destination)) throw new Error('bifrost cross requires destination multivoice, godseye, or worldmonitor');
        if (!bifrostTransports.includes(transport)) throw new Error(`unsupported transport: ${transport || '(missing)'}`);
        const intent = intentParts.join(' ').trim(); if (!intent) throw new Error('bifrost cross requires an intent');
        const result = await bifrostRequest('/api/bifrost/crossing', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ source: 'camelot', destination, transport, intent, payload: '' }) });
        appendLog(state, `BIFROST CROSSING // ${destination.toUpperCase()} // ${result.result || 'COMPLETE'}`);
        console.log(green(`✓ ${result.result || 'Crossing evaluated'}`)); if (result.detail) console.log(dim(result.detail)); if (result.requiresHandoff && result.launchUrl) console.log(`${gold('Handoff:')} ${result.launchUrl}`); break;
      }
      throw new Error('bifrost supports status, probe <realm>, or cross <realm> <transport> <intent...>');
    }
    case 'reset': {
      const fresh = defaultState(); Object.keys(state).forEach(key => delete state[key]); Object.assign(state, fresh); console.log(green('✓ CLI state reset')); break;
    }
    case 'help': case '?': help(); break;
    case 'exit': case 'quit': return { exit: true };
    default: throw new Error(`unknown command: ${command}. Run help.`);
  }
  await saveState(state);
  return { exit: false };
}

function tokenize(line) {
  const tokens = []; let current = ''; let quote = null;
  for (const ch of line.trim()) {
    if ((ch === '"' || ch === "'") && (!quote || quote === ch)) { quote = quote ? null : ch; continue; }
    if (/\s/.test(ch) && !quote) { if (current) { tokens.push(current); current = ''; } continue; }
    current += ch;
  }
  if (current) tokens.push(current); return tokens;
}

async function interactive(state) {
  banner(); printStatus(state); console.log(dim('Type `help` for commands. Arrow history is supported by your terminal.\n'));
  const rl = createInterface({ input: process.stdin, output: process.stdout, historySize: 100, prompt: `${gold('camelot')} ${cyan('❯')} ` });
  rl.prompt();
  rl.on('line', async line => {
    const args = tokenize(line); if (!args.length) { rl.prompt(); return; }
    try { const result = await execute(args, state); if (result.exit) { rl.close(); return; } }
    catch (error) { console.error(red(`✗ ${error instanceof Error ? error.message : String(error)}`)); }
    rl.prompt();
  });
  rl.on('close', () => console.log(dim('\nCamelot terminal closed.')));
}

const state = await loadState();
const argv = process.argv.slice(2);
if (argv.length) {
  try { const result = await execute(argv, state); if (result.exit) process.exit(0); }
  catch (error) { console.error(red(`✗ ${error instanceof Error ? error.message : String(error)}`)); process.exitCode = 1; }
} else {
  await interactive(state);
}
