# Camelot Continuous World Director

This module turns Camelot's scrolling interfaces into a continuous navigable computational world.

## Design source

The architecture is informed by the public MIT-licensed `oso95/scroll-world` project, especially these ideas:

- weighted scene scroll distance
- mid-scene linger / dwell
- continuous camera movement rather than cut-based section changes
- mobile/scarcity-aware rendering
- reduced-motion fallback
- optional future frame-locked cinematic connector clips

Repository: `https://github.com/oso95/scroll-world`

## Assimilation boundary

Camelot does **not** vendor or mount the upstream `scroll-world` scrub runtime. The World Director is an independent React-native implementation designed around live Camelot application state.

The upstream project is optimized for cinematic landing pages. Camelot keeps a different responsibility split:

```text
scroll / camera physics  -> Camelot World Director
visible spatial grammar  -> Sir Lumen / runtime UI
live system state        -> Camelot React components
routing                  -> Sir Hermes
security / authorization -> Sir Heimdall
engineering orchestration-> Sir Helios (development-only)
```

## Battle World

`battleWorld.ts` is the canonical Battle Mode timeline. Each scene owns:

- `scrollWeight`: physical scroll distance
- `linger`: dwell around the operational midpoint
- `accent`: scene color field
- `camera`: x/y/scale/rotation/brightness/saturation/blur target

The current runtime interpolates camera state during the final portion of one scene into the next scene, creating a continuous spatial handoff instead of a hard section switch.

## Performance tiers

- **high**: full depth / beam / ring treatment
- **medium**: depth retained with reduced decorative work
- **scarcity**: mobile or <=4GB-class devices prioritize interaction over particles/effects
- **prefers-reduced-motion**: disables continuous motion and snap behavior

## Future cinematic media contract

The World Director is intentionally ready for an optional pre-rendered media layer later. When cinematic dives/connectors are introduced, seams must be produced from exact neighboring frames so the visual transition does not pop. React controls remain live overlays and must not be baked into videos.
