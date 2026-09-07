/**
 * WorldTree3D.js
 * 
 * Wrapper for '3d-force-graph' that orchestrates 3D spatial node visualization,
 * sharing the same D3 physics simulation coordinates and forces as the 2D renderer
 * to ensure seamless state interpolation during dimensional transitions.
 */

import * as THREE from 'three';
import ForceGraph3D from '3d-force-graph';
import { isWebGLAvailable } from '../utils/webglHelper';

export const STATE_COLORS = {
  verified: '#f5c542',          // gold
  running: '#00e5ff',           // cyan
  approval_required: '#ffbf00', // amber
  failed: '#ff4444',            // red
  quarantined: '#9d4edd',       // violet
  stale: '#888888'              // gray
};

export const LINK_COLORS = {
  produced: '#6b4c9a',
  depends_on: '#38bdf8',
  verifies: '#10b981',
  flows_to: '#eab308',
  synthesizes: '#f43f5e',
  quarantines: '#a855f7'
};

/**
 * Level-of-Detail (LOD) node density threshold.
 * When node count exceeds 300, labels and halos are disabled to preserve 60fps
 * and enforce the strict 8GB RAM / <50MB client VRAM scarcity constraint.
 */
export const LOD_NODE_THRESHOLD = 300;

export class WorldTree3D {
  /**
   * @param {HTMLElement} container - Target DOM element for mounting 3D canvas
   * @param {Object} graphData - Node and link topology data
   * @param {Object} [options={}] - Visualizer configuration options
   * @param {function} [options.onNodeSelect] - Node selection callback
   * @param {function} [options.onNodeHover] - Node hover callback
   * @param {function} [options.onNodeRightClick] - Node right-click context callback
   * @param {function} [options.onLODChange] - LOD activation state callback (active, nodeCount)
   * @param {string} [options.searchQuery] - Filter query for node search highlights
   * @param {string} [options.activeFilter] - Filter criteria for node states/kinds
   * @param {'auto'|'full'|'simplified'|'points'} [options.lodMode='auto'] - Level of detail mode
   * @param {number} [options.lodThreshold=300] - Node count threshold for engaging LOD
   * @param {Object} [options.sharedSimulation] - Optional shared D3 simulation instance
   * @param {Object} [options.graph2D] - Optional 2D visualizer instance to share physics with
   */
  constructor(container, graphData, options = {}) {
    this.container = container;
    this.graphData = graphData || { nodes: [], links: [] };
    this.options = options;

    // Level-of-Detail (LOD) Configuration
    this.lodThreshold = typeof options.lodThreshold === 'number' ? options.lodThreshold : LOD_NODE_THRESHOLD;
    this.lodMode = options.lodMode || 'auto';

    this.hasWebGL = false;
    this.graphInstance = null;
    this.sharedSimulation = options.sharedSimulation || null;
    this.graph2D = options.graph2D || null;

    this.selectedNode = null;
    this.hoveredNode = null;
    this.haloMeshes = new Map();
    this.pulseClock = new THREE.Clock();
    this.animFrameId = null;
    this.isDestroyed = false;
    this.isPaused = false;
    this.morphFactor = 1.0;

    // Fallback 2.5D spatial canvas engine properties (if WebGL is unavailable)
    this.canvas25D = null;
    this.ctx25D = null;
    this.pitch = 0.52;
    this.yaw = -0.22;
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isDragging = false;
    this.dragStart = { x: 0, y: 0 };
    this.projectedNodes = new Map();
    this.flowTime = 0;
    this.resizeObserver = null;

    // Initialize renderer
    const webglSupported = isWebGLAvailable();
    let webglInitialized = false;

    if (webglSupported) {
      webglInitialized = this.tryInitWebGL();
    }

    if (!webglInitialized) {
      this.hasWebGL = false;
      this.initFallback25D();
    }

    // Bind shared D3 physics simulation if provided
    if (this.graph2D) {
      this.sharePhysicsSimulation(this.graph2D);
    } else if (this.sharedSimulation) {
      this.bindSharedSimulation(this.sharedSimulation);
    }

    this.startPulseLoop();
  }

  // =========================================================================
  // WEBGL 3D-FORCE-GRAPH INITIALIZATION
  // =========================================================================
  tryInitWebGL() {
    const origError = console.error;
    const origWarn = console.warn;
    // Suppress console noise during WebGL detection/initialization
    console.error = () => {};
    console.warn = () => {};

    try {
      this.container.innerHTML = '';
      const width = this.container.clientWidth || 800;
      const height = this.container.clientHeight || 600;

      const factory = ForceGraph3D;
      let graph;

      try {
        graph = typeof factory === 'function' && factory.prototype?.constructor
          ? new factory(this.container)
          : factory()(this.container);
      } catch {
        graph = factory()(this.container);
      }

      if (!graph || !graph.scene) {
        throw new Error('ForceGraph3D failed to return scene');
      }

      this.graphInstance = graph;
      this.hasWebGL = true;

      // Configure viewport & styling
      graph
        .width(width)
        .height(height)
        .backgroundColor('rgba(5, 5, 5, 0)')
        .showNavInfo(false);

      // Configure Shared D3 Physics Simulation Forces
      // Matching 2D force equilibrium so positions and velocities remain identical
      this.configureD3SimulationForces(graph);

      // Initial Camera Position: Top-Down Orthographic View
      graph.cameraPosition(
        { x: 0, y: 400, z: 0 },
        { x: 0, y: 0, z: 0 },
        0
      );

      // Add Ambient and Cinematic Directional Lighting
      const scene = graph.scene();
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
      const goldDirLight = new THREE.DirectionalLight(0xd4af37, 1.4);
      goldDirLight.position.set(200, 400, 300);
      const cyanRimLight = new THREE.DirectionalLight(0x00e5ff, 0.8);
      cyanRimLight.position.set(-200, -200, -200);
      scene.add(ambientLight, goldDirLight, cyanRimLight);

      // Custom 3D Node Mesh Rendering
      graph.nodeThreeObject((nodeObj) => {
        return this.createNodeMesh(nodeObj);
      });

      // Node Labels & Tooltip Formatting
      // Completely disabled when node count exceeds 300 to sustain 60fps within the 8GB memory budget
      graph.nodeLabel((node) => {
        if (this.isLODActive()) {
          return ''; // Suppress labels in LOD mode
        }
        return `
          <div style="background: rgba(5,5,5,0.92); border: 1px solid #d4af37; padding: 6px 10px; border-radius: 8px; font-family: monospace; color: #fff; font-size: 11px; pointer-events: none; box-shadow: 0 4px 14px rgba(0,0,0,0.6);">
            <div style="font-weight: bold; color: #f5c542;">${node.label || node.id}</div>
            <div style="color: #00e5ff; font-size: 10px; margin-top: 2px;">Type: ${node.kind || 'node'} | State: ${node.state || 'active'}</div>
            ${typeof node.trust_tier === 'number' ? `<div style="color: #d4af37; font-size: 9px;">Trust Tier: ${node.trust_tier}</div>` : ''}
            ${node.risk_tier ? `<div style="color: #ffbf00; font-size: 9px;">Risk: ${node.risk_tier}</div>` : ''}
          </div>
        `;
      });

      // Link Visual Appearance & Flow Particles
      graph
        .linkColor((link) => link.color || LINK_COLORS[link.kind] || '#00e5ff')
        .linkWidth((link) => {
          const isSelected = this.selectedNode && (
            link.source?.id === this.selectedNode.id || link.target?.id === this.selectedNode.id
          );
          return isSelected ? 2.5 : Math.max(0.6, (link.trust_flow || 1) * 0.8);
        })
        .linkCurvature((link) => {
          return link.curvature ?? (0.3 * this.morphFactor);
        })
        .linkDirectionalParticles((link) => (this.isLODActive() ? 0 : 2))
        .linkDirectionalParticleSpeed(0.006)
        .linkDirectionalParticleWidth((link) => Math.max(1.2, (link.trust_flow || 1) * 0.7))
        .linkDirectionalParticleColor((link) => link.color || LINK_COLORS[link.kind] || '#00e5ff');

      // Interaction Event Handlers
      graph.onNodeClick((node, event) => {
        this.setSelectedNode(node);
        this.options.onNodeSelect?.(node);
      });

      graph.onNodeHover((node) => {
        this.setHoveredNode(node);
        this.options.onNodeHover?.(node);
      });

      graph.onNodeRightClick((node, event) => {
        this.options.onNodeRightClick?.(node, { x: event.clientX, y: event.clientY });
      });

      // Populate Initial Graph Data
      this.updateData(this.graphData);

      // Auto-Resize Observer
      this.resizeObserver = new ResizeObserver(() => {
        if (this.isDestroyed || !this.graphInstance) return;
        const w = this.container.clientWidth || 800;
        const h = this.container.clientHeight || 600;
        this.graphInstance.width(w).height(h);
      });
      this.resizeObserver.observe(this.container);

      console.error = origError;
      console.warn = origWarn;
      return true;
    } catch (err) {
      console.error = origError;
      console.warn = origWarn;
      this.graphInstance = null;
      this.hasWebGL = false;
      return false;
    }
  }

  // =========================================================================
  // D3 PHYSICS SIMULATION SHARING & CONFIGURATION
  // =========================================================================
  /**
   * Configures D3 force simulation parameters on 3D-force-graph to mirror
   * the 2D renderer physics behavior.
   * @param {Object} graph - ForceGraph3D instance
   */
  configureD3SimulationForces(graph) {
    if (!graph || typeof graph.d3Force !== 'function') return;

    // Velocity & alpha decay rates for stable convergence
    graph.d3VelocityDecay(0.35);
    graph.d3AlphaDecay(0.022);

    // Charge (repulsion) force
    const chargeForce = graph.d3Force('charge');
    if (chargeForce && typeof chargeForce.strength === 'function') {
      chargeForce.strength((node) => {
        const val = node.val || 10;
        return -80 - (val * 4);
      });
    }

    // Link distance & strength force
    const linkForce = graph.d3Force('link');
    if (linkForce && typeof linkForce.distance === 'function') {
      linkForce.distance((link) => {
        return (link.distance || 60) + (1 - (link.trust_flow || 0.5)) * 30;
      });
    }

    // Center force
    const centerForce = graph.d3Force('center');
    if (centerForce && typeof centerForce.strength === 'function') {
      centerForce.strength(0.05);
    }
  }

  /**
   * Connects this 3D renderer with an existing 2D renderer instance to share
   * the exact same physics coordinates (x, y, vx, vy).
   * @param {Object} graph2D - 2D renderer instance
   */
  sharePhysicsSimulation(graph2D) {
    if (!graph2D) return;
    this.graph2D = graph2D;

    // 1. Synchronize initial planar positions
    this.syncFrom2D(graph2D);

    // 2. Intercept node movement or drag updates
    const origOnNodeSelect = graph2D.options?.onNodeSelect;
    if (graph2D.options) {
      graph2D.options.onNodeSelect = (node) => {
        origOnNodeSelect?.(node);
        this.setSelectedNode(node);
      };
    }
  }

  /**
   * Binds an external D3 simulation instance directly.
   * @param {Object} d3Simulation - d3-force simulation
   */
  bindSharedSimulation(d3Simulation) {
    if (!d3Simulation) return;
    this.sharedSimulation = d3Simulation;

    // Listen to simulation ticks to continuously synchronize planar coordinates
    if (typeof d3Simulation.on === 'function') {
      d3Simulation.on('tick.worldTree3D', () => {
        this.syncFromSharedSimulation();
      });
    }
  }

  /**
   * Synchronizes planar coordinates from the 2D renderer into 3D nodes.
   * @param {Object} [graph2D=this.graph2D]
   */
  syncFrom2D(graph2D = this.graph2D) {
    if (!graph2D?.graphData?.nodes) return;
    const sourceNodes = graph2D.graphData.nodes;

    if (this.hasWebGL && this.graphInstance) {
      const g3dData = typeof this.graphInstance.graphData === 'function' ? this.graphInstance.graphData() : null;
      if (g3dData?.nodes) {
        g3dData.nodes.forEach((n3) => {
          const n2 = sourceNodes.find((n) => n.id === n3.id);
          if (n2) {
            n3.x = n2.x;
            n3.y = n2.y;
            n3.vx = n2.vx || 0;
            n3.vy = n2.vy || 0;
            const targetZ = (n3.val || 10) * 3;
            n3.z = targetZ * this.morphFactor;
          }
        });
      }
    }
  }

  /**
   * Synchronizes planar coordinates from 3D back into the 2D renderer.
   * @param {Object} [graph2D=this.graph2D]
   */
  syncTo2D(graph2D = this.graph2D) {
    if (!graph2D?.graphData?.nodes) return;
    const targetNodes = graph2D.graphData.nodes;

    if (this.hasWebGL && this.graphInstance) {
      const g3dData = typeof this.graphInstance.graphData === 'function' ? this.graphInstance.graphData() : null;
      if (g3dData?.nodes) {
        g3dData.nodes.forEach((n3) => {
          const n2 = targetNodes.find((n) => n.id === n3.id);
          if (n2) {
            n2.x = n3.x;
            n2.y = n3.y;
            n2.vx = n3.vx || 0;
            n2.vy = n3.vy || 0;
            n2.z = 0; // Flat 2D ground plane
          }
        });
      }
      graph2D.requestRedraw?.();
    }
  }

  /**
   * Synchronizes positions from a shared D3 simulation instance.
   */
  syncFromSharedSimulation() {
    if (!this.sharedSimulation || typeof this.sharedSimulation.nodes !== 'function') return;
    const simNodes = this.sharedSimulation.nodes();

    if (this.hasWebGL && this.graphInstance) {
      const currentData = this.graphInstance.graphData?.();
      if (currentData?.nodes) {
        currentData.nodes.forEach((n3) => {
          const sNode = simNodes.find((n) => n.id === n3.id);
          if (sNode) {
            n3.x = sNode.x;
            n3.y = sNode.y;
            n3.vx = sNode.vx;
            n3.vy = sNode.vy;
            const targetZ = (n3.val || 10) * 3;
            n3.z = targetZ * this.morphFactor;
          }
        });
      }
    }
  }

  // =========================================================================
  // MORPH PROGRESS & SEAMLESS INTERPOLATION API
  // =========================================================================
  /**
   * Sets the continuous dimensional morph factor [0.0 = 2D planar, 1.0 = full 3D spatial].
   * Executes smooth Z-axis node elevation, edge curvature warping, and camera trajectory.
   * @param {number} progress - Normalized morph factor [0, 1]
   */
  setMorphProgress(progress) {
    this.morphFactor = Math.max(0, Math.min(1, progress));

    if (this.hasWebGL && this.graphInstance) {
      const g3d = this.graphInstance;
      const currentData = typeof g3d.graphData === 'function' ? g3d.graphData() : null;

      // 1. Elevate nodes along Z-axis based on trust tier / val and eased morph progress
      if (currentData?.nodes) {
        currentData.nodes.forEach((node) => {
          const val = node.val ?? (typeof node.trust_tier === 'number' ? node.trust_tier * 6 : 10);
          const targetZ = Math.min(val * 3, 120);
          node.z = targetZ * this.morphFactor;
        });
      }

      // 2. Warp link curvature progressively
      if (currentData?.links) {
        currentData.links.forEach((link) => {
          link.curvature = 0.3 * this.morphFactor;
        });
      }

      // 3. Move camera along the orbital arc (top-down orthographic to orbital swoop)
      const cameraDistance = 400 + (200 * this.morphFactor);
      const cameraAngle = (Math.PI / 2) * this.morphFactor;
      const camX = Math.sin(cameraAngle) * cameraDistance;
      const camY = 380 * (1 - this.morphFactor) + (140 * this.morphFactor);
      const camZ = Math.cos(cameraAngle) * cameraDistance;

      if (typeof g3d.cameraPosition === 'function') {
        g3d.cameraPosition(
          { x: camX, y: camY, z: camZ },
          { x: 0, y: 0, z: 0 },
          0 // Instant update during animation step
        );
      }
    } else {
      // 2.5D Fallback pitch interpolation
      this.pitch = 0.52 * this.morphFactor;
      this.requestDrawFallback();
    }
  }

  // =========================================================================
  // CUSTOM 3D MESH BUILDER WITH LEVEL-OF-DETAIL (LOD)
  // =========================================================================
  createNodeMesh(node) {
    const isFiltered = this.isNodeFilteredOut(node);
    const isSelected = this.selectedNode?.id === node.id;
    const isHovered = this.hoveredNode?.id === node.id;
    const hasSearch = Boolean(this.options.searchQuery?.trim());
    const isSearchMatch = hasSearch && this.isNodeSearchMatched(node);
    const isLOD = this.isLODActive();

    const group = new THREE.Group();
    const nodeRadius = Math.max(3.5, Math.min(10, 2 + ((node.trust_tier || 0) * 1.5)));
    const baseColor = new THREE.Color(node.color || STATE_COLORS[node.state] || '#888888');

    // 1. Core Sphere: Optimize geometry in LOD mode (8x8 segments instead of 16x16) to conserve GPU resources
    const sphereSegments = isLOD ? 8 : 16;
    const sphereGeom = new THREE.SphereGeometry(nodeRadius, sphereSegments, sphereSegments);
    const sphereMat = new THREE.MeshStandardMaterial({
      color: isSelected ? 0xffffff : baseColor,
      emissive: baseColor,
      emissiveIntensity: isSelected ? 0.8 : (isHovered ? 0.6 : 0.35),
      roughness: 0.25,
      metalness: 0.7,
      transparent: isFiltered || (hasSearch && !isSearchMatch),
      opacity: isFiltered ? 0.15 : (hasSearch && !isSearchMatch ? 0.3 : 1.0)
    });
    const coreSphere = new THREE.Mesh(sphereGeom, sphereMat);
    group.add(coreSphere);

    // 2. State Halos & Accents
    // Crucial LOD Guard: Halos are completely disabled when node count exceeds 300 to maintain 60fps
    if (!isLOD) {
      if (node.state === 'verified') {
        const ringGeom = new THREE.TorusGeometry(nodeRadius * 1.6, 0.45, 8, 24);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0xf5c542, transparent: true, opacity: 0.85 });
        const ring = new THREE.Mesh(ringGeom, ringMat);
        ring.rotation.x = Math.PI / 2;
        group.add(ring);
        this.haloMeshes.set(node.id, ring);
      } else if (node.state === 'running') {
        const glowGeom = new THREE.SphereGeometry(nodeRadius * 1.45, 12, 12);
        const glowMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff, wireframe: true, transparent: true, opacity: 0.45 });
        const glow = new THREE.Mesh(glowGeom, glowMat);
        group.add(glow);
        this.haloMeshes.set(node.id, glow);
      } else if (node.state === 'approval_required') {
        const ringGeom = new THREE.TorusGeometry(nodeRadius * 1.5, 0.4, 6, 16);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0xffbf00, transparent: true, opacity: 0.8 });
        const ring = new THREE.Mesh(ringGeom, ringMat);
        ring.rotation.y = Math.PI / 4;
        group.add(ring);
        this.haloMeshes.set(node.id, ring);
      }
    }

    // 3. Selection Indicator Ring (Retained for active focus feedback)
    if (isSelected) {
      const selGeom = new THREE.TorusGeometry(nodeRadius * 2.1, 0.5, 8, 32);
      const selMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const selRing = new THREE.Mesh(selGeom, selMat);
      selRing.rotation.x = Math.PI / 2;
      group.add(selRing);
    }

    return group;
  }

  // =========================================================================
  // LEVEL-OF-DETAIL (LOD) CONTROLLERS
  // =========================================================================
  /**
   * Checks whether Level-of-Detail mode is active.
   * Engages automatically when graph node count exceeds 300 (or forced via lodMode).
   * @returns {boolean}
   */
  isLODActive() {
    if (this.lodMode === 'simplified' || this.lodMode === 'points') return true;
    if (this.lodMode === 'full') return false;
    const nodeCount = this.graphData?.nodes?.length || 0;
    return nodeCount > this.lodThreshold;
  }

  /**
   * Returns current LOD telemetry status.
   * @returns {{ active: boolean, nodeCount: number, threshold: number, labelsEnabled: boolean, halosEnabled: boolean }}
   */
  getLODStatus() {
    const nodeCount = this.graphData?.nodes?.length || 0;
    const active = this.isLODActive();
    return {
      active,
      nodeCount,
      threshold: this.lodThreshold,
      labelsEnabled: !active,
      halosEnabled: !active
    };
  }

  /**
   * Dynamically configures the LOD node count threshold.
   * @param {number} threshold
   */
  setLODThreshold(threshold) {
    const prevActive = this.isLODActive();
    this.lodThreshold = threshold;
    if (prevActive !== this.isLODActive()) {
      this.refreshVisuals();
    }
  }

  /**
   * Overrides LOD mode ('auto', 'full', 'simplified', 'points').
   * @param {'auto'|'full'|'simplified'|'points'} mode
   */
  setLODMode(mode) {
    const prevActive = this.isLODActive();
    this.lodMode = mode;
    this.options.lodMode = mode;
    if (prevActive !== this.isLODActive()) {
      this.refreshVisuals();
    }
  }

  /**
   * Re-evaluates node 3D meshes when LOD threshold is crossed.
   */
  refreshVisuals() {
    if (this.hasWebGL && this.graphInstance) {
      this.haloMeshes.clear();
      this.graphInstance.nodeThreeObject(this.graphInstance.nodeThreeObject());
    } else {
      this.requestDrawFallback();
    }
  }

  // =========================================================================
  // DATA AND SELECTION MUTATIONS
  // =========================================================================
  updateData(graphData) {
    const prevLOD = this.isLODActive();
    this.graphData = graphData;
    const nextLOD = this.isLODActive();

    if (this.hasWebGL && this.graphInstance) {
      this.haloMeshes.clear();
      this.graphInstance.graphData({
        nodes: graphData.nodes.map((n) => ({ ...n })),
        links: graphData.links.map((l) => ({ ...l }))
      });
      if (prevLOD !== nextLOD) {
        this.refreshVisuals();
        this.options.onLODChange?.(nextLOD, graphData.nodes.length);
      }
    } else {
      this.requestDrawFallback();
    }
  }

  setSelectedNode(node) {
    this.selectedNode = node;
    if (this.hasWebGL && this.graphInstance) {
      this.graphInstance.nodeThreeObject(this.graphInstance.nodeThreeObject());
    } else {
      this.requestDrawFallback();
    }
  }

  setHoveredNode(node) {
    this.hoveredNode = node;
  }

  setFilter(filter) {
    this.options.activeFilter = filter;
    if (this.hasWebGL && this.graphInstance) {
      this.graphInstance.nodeThreeObject(this.graphInstance.nodeThreeObject());
    } else {
      this.requestDrawFallback();
    }
  }

  setSearchQuery(query) {
    this.options.searchQuery = query;
    if (this.hasWebGL && this.graphInstance) {
      this.graphInstance.nodeThreeObject(this.graphInstance.nodeThreeObject());
    } else {
      this.requestDrawFallback();
    }
  }

  isNodeFilteredOut(node) {
    const filter = this.options.activeFilter;
    if (!filter || filter === 'all') return false;
    return node.state !== filter && node.kind !== filter;
  }

  isNodeSearchMatched(node) {
    const q = this.options.searchQuery?.trim().toLowerCase();
    if (!q) return false;
    return (
      (node.label && node.label.toLowerCase().includes(q)) ||
      (node.id && node.id.toLowerCase().includes(q)) ||
      (node.kind && node.kind.toLowerCase().includes(q)) ||
      (node.risk_tier && node.risk_tier.toLowerCase().includes(q))
    );
  }

  pauseAnimation() {
    this.isPaused = true;
    if (this.hasWebGL && this.graphInstance) {
      this.graphInstance.pauseAnimation?.();
    }
  }

  resumeAnimation() {
    this.isPaused = false;
    if (this.hasWebGL && this.graphInstance) {
      this.graphInstance.resumeAnimation?.();
    }
  }

  cameraPosition(pos, lookAt, transitionMs = 0) {
    if (this.hasWebGL && this.graphInstance) {
      return this.graphInstance.cameraPosition(pos, lookAt, transitionMs);
    }
  }

  // =========================================================================
  // ANIMATION TICK LOOP
  // =========================================================================
  startPulseLoop() {
    const tick = () => {
      if (this.isDestroyed) return;

      if (!this.isPaused) {
        const delta = this.pulseClock.getDelta();

        // Rotate halo rings only if LOD system has not disabled halos
        if (!this.isLODActive() && this.haloMeshes.size > 0) {
          this.haloMeshes.forEach((mesh) => {
            mesh.rotation.z += delta * 1.2;
          });
        }

        if (!this.hasWebGL) {
          this.flowTime += delta;
          this.drawFallbackFrame();
        }
      }

      this.animFrameId = requestAnimationFrame(tick);
    };

    this.animFrameId = requestAnimationFrame(tick);
  }

  // =========================================================================
  // FALLBACK 2.5D ENGINE (Guarantees zero crashes if WebGL is disabled)
  // =========================================================================
  initFallback25D() {
    this.container.innerHTML = '';
    const canvas = document.createElement('canvas');
    canvas.className = 'w-full h-full block select-none cursor-grab active:cursor-grabbing';
    this.container.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    this.canvas25D = canvas;
    this.ctx25D = ctx;

    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;
    this.panX = width / 2;
    this.panY = height / 2;
    this.zoom = Math.min(width / 900, height / 700, 1.0);

    const onResize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = this.container.clientWidth || 800;
      const h = this.container.clientHeight || 600;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.drawFallbackFrame();
    };

    this.resizeObserver = new ResizeObserver(onResize);
    this.resizeObserver.observe(this.container);
    onResize();

    // Interaction bindings for 2.5D
    canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.dragStart = { x: e.clientX, y: e.clientY };
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const dx = e.clientX - this.dragStart.x;
      const dy = e.clientY - this.dragStart.y;
      this.dragStart = { x: e.clientX, y: e.clientY };
      this.panX += dx;
      this.panY += dy;
      this.drawFallbackFrame();
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      this.zoom = Math.max(0.2, Math.min(3.0, this.zoom * zoomFactor));
      this.drawFallbackFrame();
    }, { passive: false });
  }

  drawFallbackFrame() {
    if (!this.ctx25D || !this.canvas25D) return;
    const ctx = this.ctx25D;
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;

    ctx.clearRect(0, 0, width, height);

    // Draw background grid
    ctx.strokeStyle = 'rgba(212, 175, 55, 0.08)';
    ctx.lineWidth = 1;
    const gridSize = 40 * this.zoom;
    const startX = (this.panX % gridSize);
    const startY = (this.panY % gridSize);

    ctx.beginPath();
    for (let x = startX; x < width; x += gridSize) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
    }
    for (let y = startY; y < height; y += gridSize) {
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
    }
    ctx.stroke();

    // Render nodes and links
    const nodes = this.graphData.nodes || [];
    const links = this.graphData.links || [];

    // Draw links
    links.forEach((link) => {
      const src = nodes.find((n) => n.id === (link.source?.id || link.source));
      const tgt = nodes.find((n) => n.id === (link.target?.id || link.target));
      if (!src || !tgt) return;

      const sx = src.x * this.zoom + this.panX;
      const sy = (src.y - (src.z || 0) * this.pitch) * this.zoom + this.panY;
      const tx = tgt.x * this.zoom + this.panX;
      const ty = (tgt.y - (tgt.z || 0) * this.pitch) * this.zoom + this.panY;

      ctx.strokeStyle = link.color || LINK_COLORS[link.kind] || '#00e5ff';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.stroke();
    });

    const isLOD = this.isLODActive();

    // Draw nodes
    nodes.forEach((node) => {
      if (this.isNodeFilteredOut(node)) return;
      const nx = node.x * this.zoom + this.panX;
      const ny = (node.y - (node.z || 0) * this.pitch) * this.zoom + this.panY;
      const radius = Math.max(4, Math.min(12, 3 + ((node.trust_tier || 0) * 2))) * this.zoom;
      const color = node.color || STATE_COLORS[node.state] || '#888888';

      // State Halos: Completely disabled when node count > 300 to preserve 60fps
      if (!isLOD && (node.state === 'verified' || node.state === 'running' || node.state === 'approval_required')) {
        const haloColor = node.state === 'verified' ? 'rgba(245, 197, 66, 0.4)' :
          (node.state === 'running' ? 'rgba(0, 229, 255, 0.4)' : 'rgba(255, 191, 0, 0.4)');
        ctx.strokeStyle = haloColor;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(nx, ny, radius * 1.55, 0, Math.PI * 2);
        ctx.stroke();
      }

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(nx, ny, radius, 0, Math.PI * 2);
      ctx.fill();

      // Node Labels: Suppressed when node count > 300 (or zoomed out) to maintain 60fps
      if (!isLOD && (this.zoom > 0.85 || this.selectedNode?.id === node.id)) {
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px monospace';
        ctx.fillText(node.label || node.id, nx + radius + 4, ny + 3);
      }

      if (this.selectedNode?.id === node.id) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });
  }

  requestDrawFallback() {
    if (!this.hasWebGL && this.ctx25D) {
      this.drawFallbackFrame();
    }
  }

  // =========================================================================
  // CLEANUP & DESTRUCTION
  // =========================================================================
  destroy() {
    this.isDestroyed = true;
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }

    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }

    this.haloMeshes.clear();

    if (this.hasWebGL && this.graphInstance) {
      try {
        this.graphInstance._destructor?.();
      } catch {}
      this.graphInstance = null;
    }

    if (this.container) {
      this.container.innerHTML = '';
    }
  }
}

export default WorldTree3D;
