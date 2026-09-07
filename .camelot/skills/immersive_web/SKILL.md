---
name: immersive_web
description: WebGPU Spatial Optimization & Spline Isolation for Sir Visage. Transparent canvas mounting, Obsidian/Gold palette enforcement, and pre-baked ambient lighting.
---

# immersive_web

**Target Knight:** Sir Visage  
**Domain:** WebGPU Spatial Optimization & Spline Isolation  
**Identity:** `Ω_SKILL_IMMERSIVE_WEB`

## Execution Logic
- Controls export and mounting parameters for lightweight interactive 3D elements.
- Strips background environments (`background: transparent; alpha: true`) and all third-party branding, UI chrome, or debug overlays.
- Color tokens enforced:
  - **Kinetic Obsidian:** `#050505`
  - **Luxora Gold:** `#D4AF37`
  - **Royal Purple:** `#2E0854`
  - **Cyan Accent:** `#00E5FF`

## Lighting Constraint
- Bakes shadows and ambient occlusion directly into texture maps prior to export.
- Eliminates expensive runtime multi-light shadow computations to maintain smooth 60fps on edge devices with `<50MB` VRAM usage.

⚜️_SOVEREIGN_TRUTH
