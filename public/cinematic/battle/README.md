# Battle World Cinematic Assets

Drop the rendered Battle World scene dives and exact-frame connector clips into this directory using the names documented in `src/world-director/README.md`.

Do not enable `VITE_BATTLE_CINEMATIC_MEDIA=1` until the full desktop chain has passed seam QA.

## Required seam rule

For every connector, the connector's first frame must be the actual final frame of the source scene dive, and the connector's final frame must be the actual first frame of the destination scene dive.

Never regenerate an approximate seam frame from a prompt.

## Encoding target

Recommended baseline:

- H.264 MP4
- no audio
- `+faststart`
- desktop: 1080p-class, tight GOP suitable for seeking
- mobile: 720p-class, tighter GOP than desktop

The runtime will remain poster-driven when rendered media is disabled, when reduced motion is requested, or when the device is in the scarcity quality tier.
