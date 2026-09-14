# Sir Helios Development Orchestrator

Sir Helios is a **development-only** engineering control plane for Camelot-VPS. It must never be imported into React, rendered in the World Tree, or exposed as a runtime product persona.

## Responsibility boundary

- **Helios:** surveys the current UI, architects development missions, asks Gemini for implementation packets, coordinates quality gates, and prepares handoff artifacts.
- **Sir Lumen:** visible visual/spatial design language inside Camelot.
- **Sir Codex:** implementation/compiler specialization when a mission delegates coding work.
- **Sir Calculus:** invariant and validation specialization.
- **Sir Aegis:** security review specialization.
- **Sir Pragmata:** deployment/bare-metal specialization.

The current CLI keeps those specialist roles as review responsibilities rather than inventing runtime agent calls that do not yet exist in the repository.

## Anti-Gravity Harness

The harness is a deterministic six-stage development loop:

1. `SURVEY` — inspect the current implementation before proposing changes.
2. `ARCHITECT` — define the smallest coherent architecture delta.
3. `FORGE` — ask Gemini 3.8 Flash for an implementation packet/diff.
4. `REVIEW` — require explicit review of accessibility, security, performance and product semantics.
5. `VERIFY` — run the repository's TypeScript and production-build gates.
6. `HANDOFF` — save the generated engineering artifact under `.helios/runs/` for review.

`FORGE` intentionally does **not** auto-apply model-generated patches. This prevents an engineering model from silently rewriting the production interface.

## Commands

```bash
# Development plan
npm run helios -- plan "Convert the World Tree into one continuous cinematic scroll"

# Candidate implementation packet + unified diff
npm run helios -- forge "Refactor the World Tree scroller so scroll maps to spatial depth"

# Deterministic repository gates, no model call
npm run helios:verify
```

Set `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the development shell. Never use a `VITE_*` API-key variable because Vite exposes those variables to browser bundles.

## Model

Default model configuration lives in `.helios/helios.config.json`. The requested primary engineering model is `gemini-3.8-flash` with high thinking and a low-temperature implementation profile.

## UI isolation invariant

Nothing under `.helios/` or `scripts/helios.mjs` may be imported from `src/`. The production UI should remain unaware that Sir Helios exists.
