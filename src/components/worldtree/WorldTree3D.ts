import * as THREE from 'three';
import ForceGraph3D, { ForceGraph3DInstance } from '3d-force-graph';
import { WorldTreeGraphData, GraphNode, GraphLink } from '../../types/worldTreeGraph';
import { STATE_COLORS } from '../../data/worldTreeGraphData';
import { isWebGLAvailable } from '../../utils/webglHelper';

export interface WorldTree3DOptions {
  onNodeSelect?: (node: GraphNode | null) => void;
  onNodeHover?: (node: GraphNode | null) => void;
  onNodeRightClick?: (node: GraphNode, coords: { x: number; y: number }) => void;
  searchQuery?: string;
  activeFilter?: string;
  lodMode?: 'full' | 'simplified' | 'points';
}

interface ProjectedNode {
  node: GraphNode;
  x: number;
  y: number;
  z: number;
  projX: number;
  projY: number;
  projZ: number;
  scale: number;
  radius: number;
  floorProjX: number;
  floorProjY: number;
}

export class WorldTree3D {
  container: HTMLElement;
  graphData: WorldTreeGraphData;
  options: WorldTree3DOptions;
  
  hasWebGL = false;
  graphInstance: any = null;

  selectedNode: GraphNode | null = null;
  hoveredNode: GraphNode | null = null;
  haloMeshes: Map<string, THREE.Mesh> = new Map();
  pulseClock = new THREE.Clock();
  animFrameId: number | null = null;
  isDestroyed = false;
  morphFactor = 1.0;

  // Fallback 2.5D Spatial Engine Properties
  private canvas25D: HTMLCanvasElement | null = null;
  private ctx25D: CanvasRenderingContext2D | null = null;
  private pitch = 0.52; // ~30 deg orbital tilt
  private yaw = -0.22;  // ~-12 deg orbital azimuth
  private zoom = 1.0;
  private panX = 0;
  private panY = 0;
  private isDragging = false;
  private dragButton = 0;
  private dragStart = { x: 0, y: 0 };
  private projectedNodes: Map<string, ProjectedNode> = new Map();
  private flowTime = 0;
  private isPaused = false;
  private resizeObserver: ResizeObserver | null = null;

  constructor(container: HTMLElement, graphData: WorldTreeGraphData, options: WorldTree3DOptions = {}) {
    this.container = container;
    this.graphData = graphData;
    this.options = options;

    const webglSupported = isWebGLAvailable();
    let webglInitialized = false;

    if (webglSupported) {
      webglInitialized = this.tryInitWebGL();
    }

    if (!webglInitialized) {
      this.hasWebGL = false;
      this.initFallback25D();
    }

    this.startPulseLoop();
  }

  // =========================================================================
  // WEBGL INITIALIZATION (Protected by Error Boundary & Console Silence)
  // =========================================================================
  private tryInitWebGL(): boolean {
    const origError = console.error;
    const origWarn = console.warn;
    // Suppress Three.js console error output during probe
    console.error = () => {};
    console.warn = () => {};

    try {
      this.container.innerHTML = '';
      const width = this.container.clientWidth || 800;
      const height = this.container.clientHeight || 600;

      const factory: any = ForceGraph3D;
      let graph: ForceGraph3DInstance;
      
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

      // Apply viewport sizing and theme
      graph.width(width);
      graph.height(height);
      graph.backgroundColor('#050505');
      graph.showNavInfo(false);

      // Initial camera position
      graph.cameraPosition(
        { x: 0, y: 400, z: 0 },
        { x: 0, y: 0, z: 0 },
        0
      );

      // Add lights
      const scene = graph.scene();
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
      const goldDirLight = new THREE.DirectionalLight(0xd4af37, 1.4);
      goldDirLight.position.set(200, 400, 300);
      const cyanRimLight = new THREE.DirectionalLight(0x00e5ff, 0.8);
      cyanRimLight.position.set(-200, -200, -200);
      scene.add(ambientLight, goldDirLight, cyanRimLight);

      // Custom 3D Node Rendering with Halos
      graph.nodeThreeObject((nodeObj: any) => {
        const node = nodeObj as GraphNode;
        const isFiltered = this.isNodeFilteredOut(node);
        const isSelected = this.selectedNode?.id === node.id;
        const isHovered = this.hoveredNode?.id === node.id;
        const hasSearch = Boolean(this.options.searchQuery?.trim());
        const isSearchMatch = hasSearch && this.isNodeSearchMatched(node);

        const group = new THREE.Group();
        const nodeRadius = Math.max(3.5, Math.min(10, 2 + (node.trust_tier * 1.5)));
        const baseColor = new THREE.Color(node.color || STATE_COLORS[node.state] || '#888888');

        // Base Core Sphere
        const sphereGeom = new THREE.SphereGeometry(nodeRadius, 16, 16);
        const sphereMat = new THREE.MeshStandardMaterial({
          color: isSelected ? 0xffffff : baseColor,
          emissive: baseColor,
          emissiveIntensity: isSelected ? 0.8 : 0.35,
          roughness: 0.25,
          metalness: 0.7,
          transparent: isFiltered,
          opacity: isFiltered ? 0.15 : (hasSearch && !isSearchMatch ? 0.3 : 1.0)
        });
        const coreSphere = new THREE.Mesh(sphereGeom, sphereMat);
        group.add(coreSphere);

        // State Halos
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
        } else if (node.state === 'failed') {
          const octGeom = new THREE.OctahedronGeometry(nodeRadius * 1.4, 0);
          const octMat = new THREE.MeshBasicMaterial({ color: 0xff4444, wireframe: true, transparent: true, opacity: 0.85 });
          const oct = new THREE.Mesh(octGeom, octMat);
          group.add(oct);
          this.haloMeshes.set(node.id, oct);
        } else if (node.state === 'quarantined') {
          const octGeom = new THREE.BoxGeometry(nodeRadius * 1.8, nodeRadius * 1.8, nodeRadius * 1.8);
          const octMat = new THREE.MeshBasicMaterial({ color: 0x9d4edd, wireframe: true, transparent: true, opacity: 0.7 });
          const oct = new THREE.Mesh(octGeom, octMat);
          group.add(oct);
          this.haloMeshes.set(node.id, oct);
        }

        // Selection Marker
        if (isSelected) {
          const selectRingGeom = new THREE.TorusGeometry(nodeRadius * 2.1, 0.6, 8, 32);
          const selectRingMat = new THREE.MeshBasicMaterial({ color: 0xd4af37 });
          const selectRing = new THREE.Mesh(selectRingGeom, selectRingMat);
          selectRing.rotation.x = Math.PI / 3;
          group.add(selectRing);
        }

        // Sprite Label for nodes
        const isLODLabel = this.options.lodMode !== 'points' && 
          (this.graphData.nodes.length <= 100 || isSelected || isHovered || isSearchMatch);

        if (isLODLabel) {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          if (ctx) {
            canvas.width = 256;
            canvas.height = 64;
            ctx.fillStyle = 'rgba(5, 5, 5, 0.75)';
            ctx.roundRect ? ctx.roundRect(10, 10, 236, 44, 8) : ctx.rect(10, 10, 236, 44);
            ctx.fill();
            ctx.strokeStyle = isSelected ? '#d4af37' : '#38bdf8';
            ctx.lineWidth = 2;
            ctx.stroke();

            ctx.font = 'bold 16px monospace';
            ctx.fillStyle = isSelected ? '#d4af37' : '#f8fafc';
            ctx.textAlign = 'center';
            ctx.fillText(node.label.slice(0, 18), 128, 32);

            ctx.font = '12px monospace';
            ctx.fillStyle = '#94a3b8';
            ctx.fillText(`[${node.risk_tier} • T${node.trust_tier}]`, 128, 48);

            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true });
            const sprite = new THREE.Sprite(spriteMat);
            sprite.position.set(0, nodeRadius + 9, 0);
            sprite.scale.set(30, 8, 1);
            group.add(sprite);
          }
        }

        return group;
      });

      // Links setup
      graph.linkColor((link: any) => link.color || '#6b4c9a');
      graph.linkCurvature('curvature');
      graph.linkDirectionalArrowLength(4);
      graph.linkDirectionalArrowRelPos(1);
      graph.linkDirectionalParticles((link: any) => link.active ? 3 : 1);
      graph.linkDirectionalParticleSpeed((link: any) => link.active ? 0.007 : 0.003);
      graph.linkDirectionalParticleWidth(2.0);

      // Interactions
      graph.onNodeClick((node: any) => {
        this.selectedNode = node as GraphNode;
        if (this.options.onNodeSelect) {
          this.options.onNodeSelect(this.selectedNode);
        }
        this.flyToNode(node);
        this.refreshGraph();
      });

      graph.onNodeHover((node: any) => {
        this.hoveredNode = node as GraphNode | null;
        if (this.options.onNodeHover) {
          this.options.onNodeHover(this.hoveredNode);
        }
      });

      graph.onNodeRightClick((node: any, event: MouseEvent) => {
        if (this.options.onNodeRightClick) {
          this.options.onNodeRightClick(node as GraphNode, { x: event.clientX, y: event.clientY });
        }
      });

      graph.onBackgroundClick(() => {
        this.selectedNode = null;
        if (this.options.onNodeSelect) {
          this.options.onNodeSelect(null);
        }
        this.refreshGraph();
      });

      this.updateData(this.graphData);
      return true;
    } catch {
      this.hasWebGL = false;
      this.graphInstance = null;
      return false;
    } finally {
      console.error = origError;
      console.warn = origWarn;
    }
  }

  // =========================================================================
  // FALLBACK 2.5D SPATIAL PROJECTION ENGINE (Zero-VRAM Sandboxed Mode)
  // Provides orbital camera, depth sorting, Z-lift, 3D arcs & state halos.
  // =========================================================================
  private initFallback25D() {
    this.container.innerHTML = '';
    this.container.style.position = 'relative';
    this.container.style.overflow = 'hidden';

    const canvas = document.createElement('canvas');
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.display = 'block';
    canvas.style.cursor = 'grab';
    this.container.appendChild(canvas);

    this.canvas25D = canvas;
    this.ctx25D = canvas.getContext('2d');

    this.updateCanvasDimensions();

    // Mouse & Touch Controls for Orbital Camera
    canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.dragButton = e.button;
      this.dragStart = { x: e.clientX, y: e.clientY };
      canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) {
        // Hover detection
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        this.checkHoverFallback(mouseX, mouseY);
        return;
      }

      const dx = e.clientX - this.dragStart.x;
      const dy = e.clientY - this.dragStart.y;
      this.dragStart = { x: e.clientX, y: e.clientY };

      if (this.dragButton === 0) {
        // Orbit (Yaw & Pitch)
        this.yaw += dx * 0.006;
        this.pitch = Math.max(0.05, Math.min(Math.PI / 2.2, this.pitch + dy * 0.006));
      } else {
        // Pan
        this.panX += dx;
        this.panY += dy;
      }
      this.requestDrawFallback();
    });

    window.addEventListener('mouseup', () => {
      if (this.isDragging) {
        this.isDragging = false;
        if (this.canvas25D) this.canvas25D.style.cursor = 'grab';
      }
    });

    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      this.zoom = Math.max(0.35, Math.min(3.5, this.zoom * zoomFactor));
      this.requestDrawFallback();
    }, { passive: false });

    canvas.addEventListener('click', (e) => {
      const rect = canvas.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;

      const hit = this.getNodeAtScreenPos(clickX, clickY);
      if (hit) {
        this.selectedNode = hit;
        if (this.options.onNodeSelect) {
          this.options.onNodeSelect(hit);
        }
        this.flyToNode(hit);
      } else {
        this.selectedNode = null;
        if (this.options.onNodeSelect) {
          this.options.onNodeSelect(null);
        }
      }
      this.requestDrawFallback();
    });

    canvas.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const clickY = e.clientY - rect.top;
      const hit = this.getNodeAtScreenPos(clickX, clickY);
      if (hit && this.options.onNodeRightClick) {
        this.options.onNodeRightClick(hit, { x: e.clientX, y: e.clientY });
      }
    });

    // Resize handling
    this.resizeObserver = new ResizeObserver(() => {
      this.updateCanvasDimensions();
      this.requestDrawFallback();
    });
    this.resizeObserver.observe(this.container);

    this.requestDrawFallback();
  }

  private updateCanvasDimensions() {
    if (!this.canvas25D) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;

    this.canvas25D.width = width * dpr;
    this.canvas25D.height = height * dpr;
    if (this.ctx25D) {
      this.ctx25D.resetTransform?.();
      this.ctx25D.scale(dpr, dpr);
    }
  }

  private checkHoverFallback(screenX: number, screenY: number) {
    const hit = this.getNodeAtScreenPos(screenX, screenY);
    if (hit?.id !== this.hoveredNode?.id) {
      this.hoveredNode = hit;
      if (this.options.onNodeHover) {
        this.options.onNodeHover(hit);
      }
      this.requestDrawFallback();
    }
  }

  private getNodeAtScreenPos(screenX: number, screenY: number): GraphNode | null {
    let closestNode: GraphNode | null = null;
    let closestDist = Infinity;

    // Check in reverse depth order (front to back)
    Array.from(this.projectedNodes.values())
      .sort((a, b) => b.projZ - a.projZ)
      .forEach(pn => {
        const dx = screenX - pn.projX;
        const dy = screenY - pn.projY;
        const dist = Math.hypot(dx, dy);
        if (dist <= pn.radius + 6 && dist < closestDist) {
          closestDist = dist;
          closestNode = pn.node;
        }
      });

    return closestNode;
  }

  // Draw 2.5D Frame
  private drawFallbackFrame() {
    if (!this.ctx25D || !this.canvas25D) return;
    const ctx = this.ctx25D;
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;

    ctx.clearRect(0, 0, width, height);

    // Cosmic Obsidian Background
    const bgGrad = ctx.createRadialGradient(width / 2, height / 2, 40, width / 2, height / 2, width * 0.7);
    bgGrad.addColorStop(0, '#0a0a14');
    bgGrad.addColorStop(0.6, '#050508');
    bgGrad.addColorStop(1, '#020204');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    const centerX = width / 2 + this.panX;
    const centerY = height / 2 + this.panY;
    const focalLength = 650;

    // 1. Draw 3D Isometric Horizon Grid
    this.drawIsometricFloorGrid(ctx, centerX, centerY, focalLength);

    // 2. Project all 3D nodes
    this.projectedNodes.clear();
    const cosY = Math.cos(this.yaw);
    const sinY = Math.sin(this.yaw);
    const cosP = Math.cos(this.pitch);
    const sinP = Math.sin(this.pitch);

    this.graphData.nodes.forEach(node => {
      const rawX = (node.x || 0) * 0.9;
      const rawY = (node.y || 0) * 0.9;
      // Z lift based on trust tier, altitude and current morph factor
      const rawZ = ((node.val || 6) * 4 + (node.trust_tier * 8)) * this.morphFactor;

      // Rotate Yaw around Y
      const x1 = rawX * cosY + rawZ * sinY;
      const z1 = -rawX * sinY + rawZ * cosY;

      // Rotate Pitch around X
      const y2 = rawY * cosP - z1 * sinP;
      const z2 = rawY * sinP + z1 * cosP;

      // Perspective Scale
      const pScale = (focalLength / (focalLength + z2 + 300)) * this.zoom;
      const projX = centerX + x1 * pScale;
      const projY = centerY + y2 * pScale;

      // Floor shadow projection (Z = 0)
      const floorX1 = rawX * cosY;
      const floorZ1 = -rawX * sinY;
      const floorY2 = rawY * cosP - floorZ1 * sinP;
      const floorZ2 = rawY * sinP + floorZ1 * cosP;
      const floorScale = (focalLength / (focalLength + floorZ2 + 300)) * this.zoom;
      const floorProjX = centerX + floorX1 * floorScale;
      const floorProjY = centerY + floorY2 * floorScale;

      const baseRadius = Math.max(4, Math.min(12, 3 + (node.trust_tier * 1.5)));
      const radius = baseRadius * pScale;

      this.projectedNodes.set(node.id, {
        node,
        x: rawX,
        y: rawY,
        z: rawZ,
        projX,
        projY,
        projZ: z2,
        scale: pScale,
        radius,
        floorProjX,
        floorProjY
      });
    });

    // 3. Draw Z-Elevation Drop Stems & Floor Shadows
    this.projectedNodes.forEach(pn => {
      if (this.morphFactor > 0.05) {
        // Floor shadow spot
        ctx.beginPath();
        ctx.ellipse(pn.floorProjX, pn.floorProjY, pn.radius * 1.3, pn.radius * 0.6, 0, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(212, 175, 55, 0.12)';
        ctx.fill();

        // Dashed elevation drop stem
        ctx.beginPath();
        ctx.setLineDash([3, 4]);
        ctx.moveTo(pn.floorProjX, pn.floorProjY);
        ctx.lineTo(pn.projX, pn.projY);
        ctx.strokeStyle = 'rgba(212, 175, 55, 0.22)';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });

    // 4. Draw Links with 3D Arcs and Flow Particles
    this.graphData.links.forEach(link => {
      const sourceId = typeof link.source === 'object' ? (link.source as any).id : link.source;
      const targetId = typeof link.target === 'object' ? (link.target as any).id : link.target;
      const pSource = this.projectedNodes.get(sourceId);
      const pTarget = this.projectedNodes.get(targetId);
      if (!pSource || !pTarget) return;

      const isSourceSelected = this.selectedNode?.id === sourceId;
      const isTargetSelected = this.selectedNode?.id === targetId;
      const isLinkActive = isSourceSelected || isTargetSelected;

      // Arc apex lifting upwards in 3D
      const midX = (pSource.projX + pTarget.projX) / 2;
      const midY = (pSource.projY + pTarget.projY) / 2 - (35 * this.morphFactor * this.zoom);

      // Quadratic Bezier Arc
      ctx.beginPath();
      ctx.moveTo(pSource.projX, pSource.projY);
      ctx.quadraticCurveTo(midX, midY, pTarget.projX, pTarget.projY);
      ctx.strokeStyle = isLinkActive ? '#d4af37' : (link.color || 'rgba(107, 76, 154, 0.55)');
      ctx.lineWidth = isLinkActive ? 2.5 : 1.2;
      ctx.stroke();

      // Flow particle along curve
      if (link.active || isLinkActive) {
        const particleT = ((this.flowTime * 0.6 + (link.flow_rate || 1)) % 1);
        const invT = 1 - particleT;
        // Bezier formula B(t) = (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
        const pX = invT * invT * pSource.projX + 2 * invT * particleT * midX + particleT * particleT * pTarget.projX;
        const pY = invT * invT * pSource.projY + 2 * invT * particleT * midY + particleT * particleT * pTarget.projY;

        ctx.beginPath();
        ctx.arc(pX, pY, 2.5 * this.zoom, 0, Math.PI * 2);
        ctx.fillStyle = isLinkActive ? '#fef08a' : '#22d3ee';
        ctx.shadowColor = '#00e5ff';
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    });

    // 5. Draw Depth-Sorted Nodes (Back to Front)
    const sortedNodes = Array.from(this.projectedNodes.values()).sort((a, b) => b.projZ - a.projZ);

    sortedNodes.forEach(pn => {
      const node = pn.node;
      const isSelected = this.selectedNode?.id === node.id;
      const isHovered = this.hoveredNode?.id === node.id;
      const isFiltered = this.isNodeFilteredOut(node);
      const hasSearch = Boolean(this.options.searchQuery?.trim());
      const isSearchMatch = hasSearch && this.isNodeSearchMatched(node);

      ctx.save();
      ctx.globalAlpha = isFiltered ? 0.2 : (hasSearch && !isSearchMatch ? 0.35 : 1.0);

      // State Halos
      this.drawNodeHalos(ctx, pn, isSelected, isHovered);

      // Core 3D Sphere with radial gradient
      const sphereGrad = ctx.createRadialGradient(
        pn.projX - pn.radius * 0.35,
        pn.projY - pn.radius * 0.35,
        pn.radius * 0.1,
        pn.projX,
        pn.projY,
        pn.radius
      );
      const baseColor = node.color || STATE_COLORS[node.state] || '#38bdf8';
      sphereGrad.addColorStop(0, '#ffffff');
      sphereGrad.addColorStop(0.35, baseColor);
      sphereGrad.addColorStop(1, '#050510');

      ctx.beginPath();
      ctx.arc(pn.projX, pn.projY, pn.radius, 0, Math.PI * 2);
      ctx.fillStyle = sphereGrad;
      ctx.fill();
      ctx.strokeStyle = isSelected ? '#ffffff' : baseColor;
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.stroke();

      // Selection Marker
      if (isSelected) {
        ctx.beginPath();
        ctx.ellipse(pn.projX, pn.projY, pn.radius * 1.9, pn.radius * 0.9, Math.PI / 4, 0, Math.PI * 2);
        ctx.strokeStyle = '#d4af37';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Labels (LOD controlled)
      const shouldDrawLabel = this.options.lodMode !== 'points' && 
        (this.graphData.nodes.length <= 100 || isSelected || isHovered || isSearchMatch);

      if (shouldDrawLabel) {
        const labelText = node.label.slice(0, 16);
        ctx.font = 'bold 10px monospace';
        const textWidth = ctx.measureText(labelText).width;
        const boxW = textWidth + 12;
        const boxH = 16;
        const boxX = pn.projX - boxW / 2;
        const boxY = pn.projY + pn.radius + 4;

        ctx.fillStyle = 'rgba(5, 5, 5, 0.85)';
        ctx.strokeStyle = isSelected ? '#d4af37' : '#38bdf8';
        ctx.lineWidth = 1;
        ctx.fillRect(boxX, boxY, boxW, boxH);
        ctx.strokeRect(boxX, boxY, boxW, boxH);

        ctx.fillStyle = isSelected ? '#d4af37' : '#f8fafc';
        ctx.textAlign = 'center';
        ctx.fillText(labelText, pn.projX, boxY + 12);
      }

      ctx.restore();
    });

    // 6. Watermark / Fallback Badge
    ctx.font = '9px monospace';
    ctx.fillStyle = 'rgba(212, 175, 55, 0.7)';
    ctx.fillText('SPATIAL PROJECTION: 2.5D HARDWARE COMPATIBILITY MATRIX [VIRTUAL VRAM]', 14, height - 14);
  }

  private drawIsometricFloorGrid(ctx: CanvasRenderingContext2D, centerX: number, centerY: number, focalLength: number) {
    ctx.save();
    ctx.strokeStyle = 'rgba(147, 51, 234, 0.12)';
    ctx.lineWidth = 1;

    const gridSize = 450;
    const step = 90;
    const cosY = Math.cos(this.yaw);
    const sinY = Math.sin(this.yaw);
    const cosP = Math.cos(this.pitch);
    const sinP = Math.sin(this.pitch);

    const projectPoint = (x: number, y: number, z: number) => {
      const x1 = x * cosY + z * sinY;
      const z1 = -x * sinY + z * cosY;
      const y2 = y * cosP - z1 * sinP;
      const z2 = y * sinP + z1 * cosP;
      const scale = (focalLength / (focalLength + z2 + 300)) * this.zoom;
      return { x: centerX + x1 * scale, y: centerY + y2 * scale };
    };

    for (let i = -gridSize; i <= gridSize; i += step) {
      const p1 = projectPoint(i, 0, -gridSize);
      const p2 = projectPoint(i, 0, gridSize);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();

      const p3 = projectPoint(-gridSize, 0, i);
      const p4 = projectPoint(gridSize, 0, i);
      ctx.beginPath();
      ctx.moveTo(p3.x, p3.y);
      ctx.lineTo(p4.x, p4.y);
      ctx.stroke();
    }
    ctx.restore();
  }

  private drawNodeHalos(ctx: CanvasRenderingContext2D, pn: ProjectedNode, isSelected: boolean, isHovered: boolean) {
    const node = pn.node;
    const elapsed = this.pulseClock.getElapsedTime();

    if (node.state === 'verified') {
      const pulse = 1 + 0.15 * Math.sin(elapsed * 4);
      ctx.beginPath();
      ctx.ellipse(pn.projX, pn.projY, pn.radius * 1.6 * pulse, pn.radius * 0.7 * pulse, 0, 0, Math.PI * 2);
      ctx.strokeStyle = '#f5c542';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    } else if (node.state === 'running') {
      const pulse = 1 + 0.2 * Math.sin(elapsed * 5);
      ctx.beginPath();
      ctx.arc(pn.projX, pn.projY, pn.radius * 1.5 * pulse, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.6)';
      ctx.lineWidth = 1.2;
      ctx.stroke();
    } else if (node.state === 'approval_required') {
      const pulse = 1 + 0.18 * Math.cos(elapsed * 4);
      ctx.beginPath();
      ctx.ellipse(pn.projX, pn.projY, pn.radius * 1.5 * pulse, pn.radius * 0.6 * pulse, Math.PI / 4, 0, Math.PI * 2);
      ctx.strokeStyle = '#ffbf00';
      ctx.lineWidth = 1.4;
      ctx.stroke();
    } else if (node.state === 'failed') {
      const pulse = 1 + 0.25 * Math.sin(elapsed * 8);
      ctx.beginPath();
      ctx.rect(pn.projX - pn.radius * 1.3 * pulse, pn.projY - pn.radius * 1.3 * pulse, pn.radius * 2.6 * pulse, pn.radius * 2.6 * pulse);
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 1.2;
      ctx.stroke();
    } else if (node.state === 'quarantined') {
      ctx.beginPath();
      ctx.arc(pn.projX, pn.projY, pn.radius * 1.7, 0, Math.PI * 2);
      ctx.strokeStyle = '#a855f7';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  private requestDrawFallback() {
    if (!this.hasWebGL && this.ctx25D) {
      this.drawFallbackFrame();
    }
  }

  // =========================================================================
  // PUBLIC CONTINUITY API (Seamlessly shared by ThreeJS and 2.5D Fallback)
  // =========================================================================
  setMorphProgress(progress: number) {
    this.morphFactor = progress;

    if (this.hasWebGL && this.graphInstance) {
      const g3d = this.graphInstance;
      const currentData = g3d.graphData();
      if (currentData?.nodes) {
        currentData.nodes.forEach((node: any) => {
          const targetZ = (node.val || 10) * 3;
          node.z = targetZ * progress;
        });
      }
      if (currentData?.links) {
        currentData.links.forEach((link: any) => {
          link.curvature = 0.3 * progress;
        });
      }
      const cameraDistance = 400 + (200 * progress);
      const cameraAngle = (Math.PI / 2) * progress;
      const camX = Math.sin(cameraAngle) * cameraDistance;
      const camY = 380 * (1 - progress) + (140 * progress);
      const camZ = Math.cos(cameraAngle) * cameraDistance;

      g3d.cameraPosition(
        { x: camX, y: camY, z: camZ },
        { x: 0, y: 0, z: 0 },
        0
      );
    } else {
      // 2.5D Fallback: Interpolate pitch from top-down (0) to orbital (0.52)
      this.pitch = 0.52 * progress;
      this.requestDrawFallback();
    }
  }

  updateData(graphData: WorldTreeGraphData) {
    this.graphData = graphData;
    if (this.hasWebGL && this.graphInstance) {
      this.haloMeshes.clear();
      this.graphInstance.graphData({
        nodes: graphData.nodes.map(n => ({ ...n })),
        links: graphData.links.map(l => ({ ...l }))
      });
    } else {
      this.requestDrawFallback();
    }
  }

  refreshGraph() {
    if (this.hasWebGL && this.graphInstance) {
      this.graphInstance.nodeThreeObject(this.graphInstance.nodeThreeObject());
    } else {
      this.requestDrawFallback();
    }
  }

  setSelectedNode(node: GraphNode | null) {
    this.selectedNode = node;
    if (node) {
      this.flyToNode(node);
    }
    this.refreshGraph();
  }

  setFilter(filter: string) {
    this.options.activeFilter = filter;
    this.refreshGraph();
  }

  setSearchQuery(query: string) {
    this.options.searchQuery = query;
    this.refreshGraph();
    if (query) {
      const match = this.graphData.nodes.find(n => this.isNodeSearchMatched(n));
      if (match) {
        this.flyToNode(match);
      }
    }
  }

  flyToNode(node: any) {
    if (!node) return;
    if (this.hasWebGL && this.graphInstance) {
      const distance = 90;
      const distRatio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
      this.graphInstance.cameraPosition(
        {
          x: (node.x || 0) * distRatio,
          y: (node.y || 0) * distRatio + 30,
          z: (node.z || 0) * distRatio + distance
        },
        { x: node.x || 0, y: node.y || 0, z: node.z || 0 },
        1000
      );
    } else {
      // 2.5D Fallback: Smooth pan to node
      this.panX = -(node.x || 0) * 0.8;
      this.panY = -(node.y || 0) * 0.8;
      this.zoom = 1.35;
      this.requestDrawFallback();
    }
  }

  resetCamera() {
    if (this.hasWebGL && this.graphInstance) {
      this.graphInstance.cameraPosition(
        { x: 0, y: 180, z: 420 },
        { x: 0, y: 0, z: 0 },
        900
      );
    } else {
      this.pitch = 0.52;
      this.yaw = -0.22;
      this.zoom = 1.0;
      this.panX = 0;
      this.panY = 0;
      this.requestDrawFallback();
    }
  }

  startPulseLoop() {
    const tick = () => {
      if (this.isDestroyed) return;
      const elapsed = this.pulseClock.getElapsedTime();
      this.flowTime += 0.02;

      if (this.hasWebGL) {
        // Animate ThreeJS halos
        this.haloMeshes.forEach(mesh => {
          mesh.rotation.z += 0.02;
          mesh.rotation.y += 0.015;
          const scalePulse = 1 + 0.12 * Math.sin(elapsed * 4);
          mesh.scale.set(scalePulse, scalePulse, scalePulse);
        });
      } else {
        // Redraw 2.5D frame for pulsing halos & flow particles
        if (!this.isPaused) {
          this.drawFallbackFrame();
        }
      }

      this.animFrameId = requestAnimationFrame(tick);
    };
    this.animFrameId = requestAnimationFrame(tick);
  }

  isNodeFilteredOut(node: GraphNode): boolean {
    const filter = this.options.activeFilter;
    if (!filter || filter === 'all') return false;
    return node.state !== filter && node.kind !== filter;
  }

  isNodeSearchMatched(node: GraphNode): boolean {
    const q = this.options.searchQuery?.trim().toLowerCase();
    if (!q) return false;
    return (
      node.label.toLowerCase().includes(q) ||
      node.id.toLowerCase().includes(q) ||
      node.kind.toLowerCase().includes(q) ||
      node.risk_tier.toLowerCase().includes(q)
    );
  }

  pauseAnimation() {
    this.isPaused = true;
    if (this.graphInstance?.pauseAnimation) {
      this.graphInstance.pauseAnimation();
    }
  }

  resumeAnimation() {
    this.isPaused = false;
    if (this.graphInstance?.resumeAnimation) {
      this.graphInstance.resumeAnimation();
    }
  }

  resize() {
    if (this.hasWebGL && this.graphInstance && this.container) {
      this.graphInstance.width(this.container.clientWidth || 800);
      this.graphInstance.height(this.container.clientHeight || 600);
    } else {
      this.updateCanvasDimensions();
      this.requestDrawFallback();
    }
  }

  destroy() {
    this.isDestroyed = true;
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    if (this.graphInstance?._destructor) {
      this.graphInstance._destructor();
    }
    this.container.innerHTML = '';
  }
}
