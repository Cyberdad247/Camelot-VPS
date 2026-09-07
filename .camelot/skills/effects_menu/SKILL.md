---
name: effects_menu
description: Frame-by-Frame Scroll Physics & Kinetic Motion for Sir Stitch. Maps pre-rendered 3D image sequences to window.scrollY progression via canvas drawImage to maintain <50MB VRAM.
---

# effects_menu

**Target Knight:** Sir Stitch  
**Domain:** Frame-by-Frame Scroll Physics & Kinetic Motion  
**Identity:** `Ω_SKILL_EFFECTS_MENU`

## Execution Logic
- Bypasses expensive real-time 3D polygon generation.
- Accepts high-fidelity pre-rendered sequences (e.g., JPEG/WEBP frames 001 to 150).
- Uses `HTMLCanvasElement.drawImage()` with `requestAnimationFrame` to swap 2D frames smoothly.
- Limits client VRAM strictly to `<50MB` and respects the 8GB host memory boundary.

## Kinetic Hook Protocol
- Uses scroll progress (from `useScroll` or `window.scrollY`) normalized between `[0, 1]`.
- Directly addresses image sequence frames via `Math.floor(progress * (totalFrames - 1))`.
- Integrates memory interrupt triggers and garbage collection checks if buffer pressure reaches 90%.

⚜️_SOVEREIGN_TRUTH
