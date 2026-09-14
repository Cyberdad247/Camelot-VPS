#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { GoogleGenAI } from '@google/genai';

const ROOT = process.cwd();
const CONFIG_PATH = path.join(ROOT, '.helios', 'helios.config.json');
const config = JSON.parse(await fs.readFile(CONFIG_PATH, 'utf8'));
const command = process.argv[2] || 'plan';
const mission = process.argv.slice(3).join(' ').trim() || 'Audit and improve the Camelot-VPS UI/UX without changing product semantics.';

const allowedCommands = new Set(['plan', 'forge', 'verify']);
if (!allowedCommands.has(command)) {
  console.error('Usage: npm run helios -- <plan|forge|verify> "mission"');
  process.exit(2);
}

const runGate = (script) => {
  console.log(`\n[HELIOS:GATE] ${script}`);
  execFileSync('npm', ['run', script], { cwd: ROOT, stdio: 'inherit', shell: process.platform === 'win32' });
};

if (command === 'verify') {
  runGate('lint');
  runGate('build');
  console.log('\n[HELIOS] Verification gates passed. No UI files were modified.');
  process.exit(0);
}

const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
if (!apiKey) {
  console.error('[HELIOS] Missing GEMINI_API_KEY or GOOGLE_API_KEY. Keep it server/dev-shell only, never VITE_* prefixed.');
  process.exit(1);
}

const ai = new GoogleGenAI({ apiKey });

async function readTargets() {
  const files = [];
  for (const rel of config.uiTargets) {
    try {
      const content = await fs.readFile(path.join(ROOT, rel), 'utf8');
      files.push({ path: rel, content });
    } catch {
      files.push({ path: rel, content: '[MISSING]' });
    }
  }
  return files;
}

const targets = await readTargets();
const sourcePacket = targets.map(file => `\n===== ${file.path} =====\n${file.content}`).join('\n');

const systemInstruction = `You are Sir Helios, the development-only Chief Engineering Orchestrator for Camelot-VPS.
You never appear in, narrate, brand, or add yourself to the user-facing UI.
You orchestrate UI/UX engineering behind the scenes using the Anti-Gravity Harness stages: SURVEY -> ARCHITECT -> FORGE -> REVIEW -> VERIFY -> HANDOFF.
Preserve the visible Camelot mythology and product semantics. Sir Lumen owns visual rendering language; Helios owns engineering orchestration.
Prioritize continuous spatial storytelling, responsive design, accessibility, reduced-motion support, maintainable React/TypeScript, performance, and truthful operational state.
Never claim a test passed unless test output proves it. Never request or expose secrets in client code.
Return concise engineering artifacts, not role-play dialogue.`;

const modeInstruction = command === 'plan'
  ? `Produce a development plan only. Do not output complete replacement files. Return sections: SURVEY, ARCHITECTURE DELTA, SCROLL/CAMERA TIMELINE, COMPONENT PLAN, ACCESSIBILITY/PERFORMANCE GATES, IMPLEMENTATION ORDER, ACCEPTANCE CRITERIA.`
  : `Produce an implementation packet. Return: SURVEY, FILES TO CHANGE, PATCH PLAN, then unified diff patches only for necessary files, followed by REVIEW CHECKLIST and VERIFY COMMANDS. Do not invent files or APIs not supported by the supplied repository context.`;

const prompt = `${modeInstruction}\n\nMISSION:\n${mission}\n\nREPOSITORY UI PACKET:\n${sourcePacket}`;

console.log(`[HELIOS] ${command.toUpperCase()} :: ${mission}`);
console.log(`[HELIOS] Model: ${config.model.id} | Harness: ${config.harness.name}`);

const response = await ai.models.generateContent({
  model: config.model.id,
  contents: prompt,
  config: {
    systemInstruction,
    temperature: config.model.temperature,
    thinkingConfig: { thinkingLevel: config.model.thinkingLevel }
  }
});

const text = response.text || '[HELIOS] Gemini returned no text output.';
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const outDir = path.join(ROOT, config.outputDirectory);
await fs.mkdir(outDir, { recursive: true });
const outPath = path.join(outDir, `${stamp}-${command}.md`);
await fs.writeFile(outPath, `# Sir Helios ${command.toUpperCase()}\n\n**Mission:** ${mission}\n\n**Model:** ${config.model.id}\n\n${text}\n`, 'utf8');

console.log(text);
console.log(`\n[HELIOS] Artifact written to ${path.relative(ROOT, outPath)}`);
console.log('[HELIOS] No user-facing UI file was automatically modified.');
