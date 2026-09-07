/**
 * WorldTreeTransition.js
 * 
 * Orchestrates the 800ms dimensional morph animation between 2D and 3D states,
 * executing smooth Z-axis node elevation, edge curvature warping, and
 * orbital camera choreography.
 */

export const DEFAULT_TRANSITION_DURATION = 800; // 800ms duration per specification

/**
 * Cubic Bezier easing function (easeInOutCubic)
 * Provides smooth acceleration and deceleration throughout the 800ms window.
 * @param {number} t - normalized time progress [0, 1]
 * @returns {number} eased value [0, 1]
 */
export function easeInOutCubic(t) {
  return t < 0.5 
    ? 4 * t * t * t 
    : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/**
 * Cubic ease-out function for deceleration
 * @param {number} t - normalized time progress [0, 1]
 * @returns {number}
 */
export function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Cubic ease-in function for acceleration
 * @param {number} t - normalized time progress [0, 1]
 * @returns {number}
 */
export function easeInCubic(t) {
  return t * t * t;
}

/**
 * Camera Orbital Choreography Configuration
 * Defines the continuous trajectory from top-down orthographic view
 * to dynamic 3D orbital perspective.
 */
export const CAMERA_ORBIT_CONFIG = {
  startDistance: 400,
  endDistance: 600,
  startHeight: 380,   // Top-down elevation
  endHeight: 140,     // Low orbital swoop angle
  rotationArc: Math.PI / 2, // 90-degree azimuthal rotation during morph
  lookAt: { x: 0, y: 0, z: 0 }
};

/**
 * Z-Axis Lift Configuration
 * Computes spatial altitude based on node value and trust tier.
 */
export const Z_LIFT_CONFIG = {
  baseLift: 3.0,
  tierMultiplier: 6.0,
  maxLift: 120.0,
  edgeCurvature: 0.3
};

/**
 * Calculates the Z-axis elevation for a node at a given transition progress.
 * @param {Object} node - Graph node with val or trust_tier
 * @param {number} progress - Eased transition progress [0, 1]
 * @param {Object} [config=Z_LIFT_CONFIG] - Lift configuration
 * @returns {number} Computed Z elevation
 */
export function calculateZLift(node, progress, config = Z_LIFT_CONFIG) {
  if (!node) return 0;
  const val = node.val ?? (typeof node.trust_tier === 'number' ? node.trust_tier * config.tierMultiplier : 10);
  const targetZ = Math.min(val * config.baseLift, config.maxLift);
  return targetZ * progress;
}

/**
 * Calculates camera position and trajectory along the orbital arc.
 * Transitions from top-down orthographic perspective to dynamic 3D orbital swoop.
 * @param {number} progress - Eased transition progress [0, 1]
 * @param {Object} [config=CAMERA_ORBIT_CONFIG] - Camera orbit configuration
 * @returns {{ position: {x: number, y: number, z: number}, lookAt: {x: number, y: number, z: number}, distance: number, angle: number }}
 */
export function calculateCameraOrbit(progress, config = CAMERA_ORBIT_CONFIG) {
  const cameraDistance = config.startDistance + ((config.endDistance - config.startDistance) * progress);
  const cameraAngle = config.rotationArc * progress;
  const camX = Math.sin(cameraAngle) * cameraDistance;
  const camY = config.startHeight * (1 - progress) + (config.endHeight * progress);
  const camZ = Math.cos(cameraAngle) * cameraDistance;

  return {
    position: { x: camX, y: camY, z: camZ },
    lookAt: config.lookAt || { x: 0, y: 0, z: 0 },
    distance: cameraDistance,
    angle: cameraAngle
  };
}

/**
 * Computes edge curvature for curved link geometry in 3D.
 * @param {number} progress - Eased transition progress [0, 1]
 * @param {number} [maxCurvature=Z_LIFT_CONFIG.edgeCurvature]
 * @returns {number}
 */
export function calculateEdgeCurvature(progress, maxCurvature = Z_LIFT_CONFIG.edgeCurvature) {
  return maxCurvature * progress;
}

export class WorldTreeTransition {
  /**
   * @param {Object} graphData - Graph node & edge data
   * @param {HTMLElement} container2D - DOM container for 2D Canvas
   * @param {HTMLElement} container3D - DOM container for 3D Three.js / WebGL scene
   * @param {Object} [options={}] - Transition configuration options
   * @param {number} [options.duration=800] - Animation duration in ms
   * @param {function} [options.onModeChange] - Callback when mode changes ('2D' | '3D' | 'transitioning')
   * @param {function} [options.onProgress] - Callback on frame progress [0, 1]
   * @param {function} [options.onNodeSelect] - Callback on node selection change
   */
  constructor(graphData, container2D, container3D, options = {}) {
    this.graphData = graphData;
    this.container2D = container2D;
    this.container3D = container3D;
    this.transitionDuration = options.duration || DEFAULT_TRANSITION_DURATION;
    this.options = options;

    /** @type {'2D' | '3D' | 'transitioning'} */
    this.mode = '2D';
    this.currentProgress = 0.0;
    this.isAnimating = false;
    this.animFrameId = null;

    this.graph2D = null;
    this.graph3D = null;
    this.selectedNode = null;
  }

  /**
   * Attach 2D and 3D visualizer instances
   * @param {Object} graph2D
   * @param {Object} graph3D
   */
  setRenderers(graph2D, graph3D) {
    this.graph2D = graph2D;
    this.graph3D = graph3D;
  }

  /**
   * Trigger 800ms Morph Animation to 3D state
   * Elevates nodes into Z-plane and swoops camera into orbital view.
   * @returns {Promise<void>}
   */
  async to3D() {
    if (this.mode === '3D' || this.isAnimating) return;

    this.cancelAnimation();
    this.mode = 'transitioning';
    this.isAnimating = true;
    this.options.onModeChange?.('transitioning');

    // Make both visual surfaces visible during morph
    if (this.container2D) {
      this.container2D.style.display = 'block';
      this.container2D.style.opacity = '1';
    }
    if (this.container3D) {
      this.container3D.style.display = 'block';
      this.container3D.style.opacity = '1';
    }

    // Prepare 3D graph with identical initial planar coordinates
    if (this.graph3D) {
      this.graph3D.pauseAnimation?.();

      if (this.graphData?.nodes) {
        const rawNodes = this.graphData.nodes.map(n => ({
          ...n,
          x: n.x,
          y: n.y,
          z: 0 // Start flat on the ground plane
        }));

        this.graph3D.updateData?.({
          ...this.graphData,
          nodes: rawNodes
        });
      }

      if (this.selectedNode) {
        this.graph3D.setSelectedNode?.(this.selectedNode);
      }
    }

    // Execute 800ms choreographed morph
    await this.animateMorph();

    // Finalize 3D display state
    if (this.container2D) {
      this.container2D.style.display = 'none';
      this.container2D.style.opacity = '0';
    }
    if (this.container3D) {
      this.container3D.style.display = 'block';
      this.container3D.style.opacity = '1';
    }

    if (this.graph3D) {
      this.graph3D.resumeAnimation?.();
    }

    this.mode = '3D';
    this.isAnimating = false;
    this.currentProgress = 1.0;
    this.options.onModeChange?.('3D');
    this.options.onProgress?.(1.0);
  }

  /**
   * Trigger 800ms Reverse Morph Animation back to 2D state
   * Flattens nodes to ground plane and returns camera to top-down view.
   * @returns {Promise<void>}
   */
  async to2D() {
    if (this.mode === '2D' || this.isAnimating) return;

    this.cancelAnimation();
    this.mode = 'transitioning';
    this.isAnimating = true;
    this.options.onModeChange?.('transitioning');

    if (this.graph3D) {
      this.graph3D.pauseAnimation?.();
    }

    // Display both containers during reverse morph
    if (this.container2D) {
      this.container2D.style.display = 'block';
    }
    if (this.container3D) {
      this.container3D.style.display = 'block';
    }

    // Execute 800ms reverse morph
    await this.animateMorphReverse();

    // Synchronize 3D planar positions back to 2D nodes
    if (this.graph3D && this.graph2D) {
      const g3dData = this.graph3D.graphData;
      if (g3dData?.nodes && this.graphData?.nodes) {
        g3dData.nodes.forEach(n3 => {
          const n2 = this.graphData.nodes.find(n => n.id === n3.id);
          if (n2) {
            n2.x = n3.x;
            n2.y = n3.y;
            n2.z = 0;
          }
        });
      }
      this.graph2D.setGraphData?.(this.graphData);
      if (this.selectedNode) {
        this.graph2D.setSelectedNode?.(this.selectedNode);
      }
      this.graph2D.setMorphFactor?.(0);
      this.graph2D.requestRedraw?.();
    }

    // Finalize 2D display state
    if (this.container3D) {
      this.container3D.style.display = 'none';
      this.container3D.style.opacity = '0';
    }
    if (this.container2D) {
      this.container2D.style.display = 'block';
      this.container2D.style.opacity = '1';
    }

    this.mode = '2D';
    this.isAnimating = false;
    this.currentProgress = 0.0;
    this.options.onModeChange?.('2D');
    this.options.onProgress?.(0.0);
  }

  /**
   * Continuous dimension scrubbing (e.g. from a slider or manual input)
   * Smoothly interpolates Z-lift, camera, and container opacity.
   * @param {number} fraction - Normalized dimension progress [0.0 = 2D, 1.0 = 3D]
   */
  scrubContinuously(fraction) {
    if (this.isAnimating) return;
    const progress = Math.max(0, Math.min(1, fraction));
    this.currentProgress = progress;

    if (progress <= 0.02) {
      if (this.container2D) {
        this.container2D.style.display = 'block';
        this.container2D.style.opacity = '1';
      }
      if (this.container3D) {
        this.container3D.style.display = 'none';
        this.container3D.style.opacity = '0';
      }
      this.mode = '2D';
      if (this.graph2D) {
        this.graph2D.setMorphFactor?.(0);
        this.graph2D.requestRedraw?.();
      }
    } else if (progress >= 0.98) {
      if (this.container2D) {
        this.container2D.style.display = 'none';
        this.container2D.style.opacity = '0';
      }
      if (this.container3D) {
        this.container3D.style.display = 'block';
        this.container3D.style.opacity = '1';
      }
      this.mode = '3D';
      this.applyInterpolatedState(1.0);
      this.graph3D?.resumeAnimation?.();
    } else {
      // Intermediate hybrid dimensional state
      this.mode = 'transitioning';
      if (this.container2D) {
        this.container2D.style.display = 'block';
        this.container2D.style.opacity = `${Math.max(0, 1 - progress * 1.5)}`;
      }
      if (this.container3D) {
        this.container3D.style.display = 'block';
        this.container3D.style.opacity = `${Math.min(1, progress * 1.5)}`;
      }

      this.applyInterpolatedState(progress);
    }

    this.options.onModeChange?.(this.mode);
    this.options.onProgress?.(progress);
  }

  /**
   * Internal 800ms Morph Animation Loop (2D -> 3D)
   * @returns {Promise<void>}
   */
  animateMorph() {
    const startTime = performance.now();
    const duration = this.transitionDuration;

    return new Promise(resolve => {
      const step = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Apply easeInOutCubic curve
        const eased = easeInOutCubic(progress);

        this.applyInterpolatedState(eased);
        this.currentProgress = eased;
        this.options.onProgress?.(eased);

        // DOM Opacity Cross-fading
        if (this.container2D) {
          this.container2D.style.opacity = `${Math.max(0, 1 - progress * 1.4)}`;
        }
        if (this.container3D) {
          this.container3D.style.opacity = `${Math.min(1, progress * 1.4)}`;
        }

        if (progress < 1) {
          this.animFrameId = requestAnimationFrame(step);
        } else {
          this.animFrameId = null;
          resolve();
        }
      };

      this.animFrameId = requestAnimationFrame(step);
    });
  }

  /**
   * Internal 800ms Reverse Morph Animation Loop (3D -> 2D)
   * @returns {Promise<void>}
   */
  animateMorphReverse() {
    const startTime = performance.now();
    const duration = this.transitionDuration;

    return new Promise(resolve => {
      const step = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Inverse easeInOutCubic curve
        const invProgress = 1 - progress;
        const eased = easeInOutCubic(invProgress);

        this.applyInterpolatedState(eased);
        this.currentProgress = eased;
        this.options.onProgress?.(eased);

        // DOM Opacity Cross-fading
        if (this.container2D) {
          this.container2D.style.opacity = `${Math.min(1, progress * 1.4)}`;
        }
        if (this.container3D) {
          this.container3D.style.opacity = `${Math.max(0, 1 - progress * 1.4)}`;
        }

        if (progress < 1) {
          this.animFrameId = requestAnimationFrame(step);
        } else {
          this.animFrameId = null;
          resolve();
        }
      };

      this.animFrameId = requestAnimationFrame(step);
    });
  }

  /**
   * Core State Interpolation Engine
   * Updates Z-axis lift and camera orbital choreography at progress [0, 1].
   * @param {number} eased - Eased transition progress [0, 1]
   */
  applyInterpolatedState(eased) {
    // 1. Unified 3D Method (delegates to setMorphProgress if available)
    if (typeof this.graph3D?.setMorphProgress === 'function') {
      this.graph3D.setMorphProgress(eased);
    }

    // 2. Direct ForceGraph3D / Three.js Scene Manipulation
    // Supports either graph3D as a wrapper with .graphInstance or directly as a ForceGraph3D instance
    const g3d = this.graph3D?.graphInstance || (typeof this.graph3D?.cameraPosition === 'function' ? this.graph3D : null);
    if (g3d) {
      const currentData = typeof g3d.graphData === 'function' ? g3d.graphData() : null;

      // 1. Lift nodes along Z: targetZ based on node properties and eased progress
      if (currentData?.nodes) {
        currentData.nodes.forEach(node => {
          node.z = calculateZLift(node, eased);
        });
      }

      // 2. Curve edges (increase curvature with Z-lift)
      if (currentData?.links) {
        currentData.links.forEach(link => {
          link.curvature = calculateEdgeCurvature(eased);
        });
      }

      // 3. Move camera (top-down orthographic to orbital perspective over 800ms)
      const orbit = calculateCameraOrbit(eased);

      if (typeof g3d.cameraPosition === 'function') {
        g3d.cameraPosition(
          orbit.position,
          orbit.lookAt,
          0 // Instant update during animation step
        );
      }
    }

    // 3. 2D Graph Visualizer Morph Feedback
    if (typeof this.graph2D?.setMorphFactor === 'function') {
      this.graph2D.setMorphFactor(eased);
    }
  }

  /**
   * Synchronize node selection across renderers
   * @param {Object|null} node
   */
  selectNode(node) {
    this.selectedNode = node;
    this.graph2D?.setSelectedNode?.(node);
    this.graph3D?.setSelectedNode?.(node);
    this.options.onNodeSelect?.(node);
  }

  /**
   * Cancel active animation frame
   */
  cancelAnimation() {
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
  }

  /**
   * Full cleanup
   */
  destroy() {
    this.cancelAnimation();
    this.graph2D?.destroy?.();
    this.graph3D?.destroy?.();
  }
}

export default WorldTreeTransition;
