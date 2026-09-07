const fs = require('fs');
const content = fs.readFileSync('src/data/bootstrapData.ts', 'utf-8');

const newLaws = `  {
    id: 9,
    title: 'RAPID AUTONOMOUS PROTOCOLS',
    description: 'Enforces self-scaffolding, testing, documentation, and error-healing within bounded time limits.',
    enforcement: 'Automated CI/CD Quality Gates & Linter Thresholds',
    status: 'VERIFYING',
    axiom: 'scaffold_to_mvp: <4_hours | feature_to_production: <24_hours'
  },
  {
    id: 10,
    title: 'AI CODING GUARDS',
    description: 'Prevents hallucination, bloat, magic, and unsafe operations. Dry principles mandated.',
    enforcement: 'Max 30 lines per function, 300 lines per file.',
    status: 'ENFORCED',
    axiom: 'If uncertain, insert {{PLACEHOLDER}} and ASK_SOVEREIGN'
  },
  {
    id: 11,
    title: 'GRILLE GATE PEDAGOGY',
    description: 'Renormalization (strip fluff) -> Quantization (TOON format) -> Pedagogy Interrupt (Ask instead of hallucinate).',
    enforcement: 'Triple QFT Pipeline',
    status: 'VERIFYING',
    axiom: 'Zero-loss scaffolding & deterministic compilation.'
  }`;

let newContent = content.replace(
  "    axiom: 'If a dependency exceeds memory quota, it is terminated.'\n  }",
  "    axiom: 'If a dependency exceeds memory quota, it is terminated.'\n  },\n" + newLaws
);

fs.writeFileSync('src/data/bootstrapData.ts', newContent);
