/**
 * WebGL Detection and Safety Utility
 * Safely probes for WebGL support without triggering unhandled errors,
 * console noise, or uncaught exception overlays in sandboxed/headless environments.
 */

let cachedWebGLAvailable: boolean | null = null;

export function isWebGLAvailable(): boolean {
  if (cachedWebGLAvailable !== null) {
    return cachedWebGLAvailable;
  }

  if (typeof window === 'undefined' || typeof document === 'undefined') {
    cachedWebGLAvailable = false;
    return false;
  }

  try {
    const canvas = document.createElement('canvas');
    
    // Intercept context creation error event
    canvas.addEventListener('webglcontextcreationerror', (e) => {
      e.preventDefault();
    }, false);

    // Suppress console output during probe to avoid polluting logs or triggering alarms
    const origError = console.error;
    const origWarn = console.warn;
    console.error = () => {};
    console.warn = () => {};

    let gl: any = null;
    try {
      gl = canvas.getContext('webgl2', { failIfMajorPerformanceCaveat: false }) ||
           canvas.getContext('webgl', { failIfMajorPerformanceCaveat: false }) ||
           canvas.getContext('experimental-webgl', { failIfMajorPerformanceCaveat: false });
    } catch {
      gl = null;
    } finally {
      console.error = origError;
      console.warn = origWarn;
    }

    cachedWebGLAvailable = Boolean(gl && typeof gl.getParameter === 'function');
    return cachedWebGLAvailable;
  } catch {
    cachedWebGLAvailable = false;
    return false;
  }
}
