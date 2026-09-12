# Camelot Continuous World Director

This module turns Camelot's scrolling interfaces into a continuous navigable computational world.

## Design source

The architecture is informed by the public MIT-licensed `oso95/scroll-world` project, especially these ideas:

- weighted scene scroll distance
- mid-scene linger / dwell
- continuous camera movement rather than cut-based section changes
- mobile/scarcity-aware rendering
- reduced-motion fallback
- frame-locked cinematic connector discipline

Repository: `https://github.com/oso95/scroll-world`

## Assimilation boundary

Camelot does **not** vendor or mount the upstream `scroll-world` scrub runtime. The World Director is an independent React-native implementation designed around live Camelot application state.

The upstream project is optimized for cinematic landing pages. Camelot keeps a different responsibility split:

```text
scroll / camera physics   -> Camelot World Director
cinematic media scrubbing -> BattleCinematicLayer
visible spatial grammar   -> Sir Lumen / runtime UI
live system state         -> Camelot React components
routing                   -> Sir Hermes
security / authorization  -> Sir Heimdall
engineering orchestration -> Sir Helios (development-only)
```

## Battle World

`battleWorld.ts` is the canonical Battle Mode timeline. Each scene owns:

- `scrollWeight`: physical scroll distance
- `linger`: dwell around the operational midpoint
- `accent`: scene color field
- `camera`: x/y/scale/rotation/brightness/saturation/blur target

The runtime interpolates camera state during the final portion of one scene into the next scene, creating a continuous spatial handoff instead of a hard section switch.

## Cinematic media runtime

`cinematicManifest.ts` defines the optional rendered-media contract for all nine Battle World scenes plus the eight inter-scene connectors.

`BattleCinematicLayer.tsx` mounts inside the persistent `.battle-stage` and keeps rendered media behind the live React controls. It supports:

- poster-first fallback, so the World Director works before any video exists
- optional per-scene desktop and mobile clips
- optional desktop and mobile connector clips
- scroll-to-`currentTime` scrubbing
- seek coalescing so a new seek is not issued while the decoder is already seeking
- first-pointer muted play/pause priming for mobile/iOS decoders
- reduced-motion poster-only fallback
- scarcity-tier poster-only behavior
- connector crossfade during the final 28% of a scene

Enable rendered media only after assets have been generated and verified:

```env
VITE_BATTLE_CINEMATIC_MEDIA="1"
```

When unset or `0`, Camelot uses the same World Director, camera timeline and live interfaces with poster/CSS motion only.

## Expected cinematic asset paths

```text
public/cinematic/battle/
├── 00-overview.mp4
├── 01-threats.mp4
├── 02-telemetry.mp4
├── 03-defense.mp4
├── 04-brains.mp4
├── 05-ouroboros.mp4
├── 06-vfs.mp4
├── 07-counter.mp4
├── 08-command.mp4
├── connectors/
│   ├── 00-01.mp4
│   ├── 01-02.mp4
│   ├── 02-03.mp4
│   ├── 03-04.mp4
│   ├── 04-05.mp4
│   ├── 05-06.mp4
│   ├── 06-07.mp4
│   └── 07-08.mp4
└── mobile/
    ├── 00-overview.mp4 ... 08-command.mp4
    └── connectors/00-01.mp4 ... 07-08.mp4
```

## Seam invariant

Every connector must be rendered from exact neighboring frames:

```text
source scene ACTUAL last frame
             ↓
       connector first frame
       connector last frame
             ↓
destination scene ACTUAL first frame
```

The IDs in `cinematicManifest.ts` are the handoff contract. Do not approximate seams from prompts or regenerate "similar" frames. The actual source/destination frames are authoritative.

## Performance tiers

- **high**: full depth, cinematic media, grain, beams and rings
- **medium**: cinematic media allowed but decorative churn is reduced
- **scarcity**: poster/CSS motion only; video and expensive decoration are suppressed
- **prefers-reduced-motion**: poster-only rendering with continuous motion disabled

Live controls, routing, security decisions and command execution must never be baked into cinematic video. Media is scenery; Camelot remains executable React above it.
