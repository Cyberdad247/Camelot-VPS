# Camelot-OS: Path to Production

This document outlines the critical recommendations and strategic pivots required to transition the Camelot-OS visual prototype into a mathematically sound, production-ready AI operating system.

---

## 1. Zero-Trust Security Enforcement (The Sentinel Upgrades)

The current UI visually represents the Zero-Trust mandate, but production requires cryptographic enforcement.

*   **Move from UI-Mocked Leases to Cryptographic Validation:** The `SentinelPolicyEngine.tsx` currently mocks Ed25519 signature validation. In production, this must be backed by a WebAssembly (WASM) module compiled from Rust (the actual Sentinel). The frontend must pass the base64-encoded lease to the WASM module for strict mathematical validation before the UI is allowed to proceed.
*   **Hardware-Backed Key Generation:** Integrate the Web Crypto API to generate short-lived, ephemeral Ed25519 keypairs on the client side. The "Lease" should literally be a JWT or a strictly formatted JSON payload signed by the active session key.
*   **Fail-Closed State Machine:** The React state should not have an `isValid` boolean that defaults to `true`. It must be an `OpaqueToken` that is entirely inaccessible until the WASM cryptographic validator unwraps it. If the token is missing or invalid, the UI must physically unmount the dispatch controls.

## 2. 8GB Scarcity Protocol (Memory & Concurrency)

The core mandate is operating an LLM within an 8GB ceiling without GC pauses.

*   **Migrate to a SharedArrayBuffer Architecture:** The current visualizers (like the Ouroboros Modal) use React state (`useState`) to rapidly re-render arrays of numbers. This causes massive JavaScript garbage collection (GC) churn. In production, the Ternary states MUST be stored in a `SharedArrayBuffer` (SAB). React components should only read from the SAB via a lightweight `requestAnimationFrame` loop to paint the UI, completely eliminating React state from the critical data path.
*   **Web Worker Offloading (Omarchy):** The simulation ticks (like the `simulateTraffic` in Memcastle or `tickSimulation` in TwinBrains) must be ripped out of the main UI thread. Move all state calculations into a dedicated Web Worker (the "Omarchy" worker). The worker mutates the `SharedArrayBuffer`, and the main thread only paints it.
*   **Strict Memory Profiling (Performance API):** Integrate `performance.memory` (where available in Chromium) to actively track JS heap size. If the heap crosses 50MB (the VRAM ceiling mandate), trigger an aggressive forced-cleanup or degrade the UI animations.

## 3. Data Persistence & State (The Receipt Ledger)

Currently, the Ledger receipts in the `MissionArena` are ephemeral React state.

*   **Implement Local-First SQLite (WAL2):** To realize the "WAL2 Seal", integrate a WASM-compiled SQLite database (like `wa-sqlite` or official SQLite WASM) directly in the browser. 
*   **Cryptographic Chaining:** When a mission executes, the result must be written to this local SQLite instance. Before writing, hash the result payload + the hash of the *previous* row (SHA-256 via Web Crypto API) to create a true, unbreakable cryptographic chain, just as described in the adversarial simulation suite.
*   **Sync Engine:** The local SQLite DB acts as the primary source of truth. Background sync should push these chained receipts to a remote server only when network is available, ensuring the system functions entirely offline (a critical production requirement for edge nodes).

## 4. UI/UX and Spatial Rendering (The 3D Canvas)

The visual experience is currently relying heavily on DOM manipulation and CSS transitions, which does not scale for continuous 3D scrolling.

*   **Port High-Frequency Visuals to WebGL (Three.js/React Three Fiber):** The `MasterWorldTreeDeck` and modal matrices (like Ouroboros) are pushing the limits of the DOM. To hit the `<50MB WebGL Projection` mandate, the 3D scroll matrix and ternary vector grids must be ported to a WebGL canvas using `@react-three/fiber`.
*   **Instanced Meshes for Matrices:** The 64/128/256-dimension Ternary matrix in the Ouroboros modal will lag the DOM if scaled to 4096 dimensions. Use `InstancedMesh` in WebGL to render thousands of matrix nodes in a single draw call.
*   **CSS Scroll-Driven Animations:** For DOM elements that *must* remain HTML (like typography), leverage modern CSS `animation-timeline: scroll()` to bind UI transitions directly to the scrollbar, removing JavaScript scroll event listeners entirely.

## 5. Deployment and CI/CD Automation

To meet the "Zero to Deploy < 72 hours" target.

*   **Multi-Stage Dockerfile (Strict):** Ensure the final container uses a scratch or distroless base image. 
*   **Bundle Analysis:** Add `rollup-plugin-visualizer` to the Vite build to aggressively monitor the bundle size. The strict mandate is `< 500KB`. The current Vite build warns that some chunks exceed 500KB. Code-splitting must be implemented (using `React.lazy()` for the complex Modals and 3D scenes).
*   **Lighthouse CI:** Integrate Lighthouse into the GitHub Actions pipeline to fail the build if performance drops below 90, or if accessibility (WCAG 2.2 AA) fails.
