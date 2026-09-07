import { WorldTreeGraphData, GraphNode, GraphLink } from '../../types/worldTreeGraph';
import { STATE_COLORS } from '../../data/worldTreeGraphData';

export interface WorldTree2DOptions {
  onNodeSelect?: (node: GraphNode | null) => void;
  onNodeHover?: (node: GraphNode | null, coords: { x: number; y: number } | null) => void;
  onNodeRightClick?: (node: GraphNode, coords: { x: number; y: number }) => void;
  searchQuery?: string;
  activeFilter?: string;
}

export class WorldTree2D {
  container: HTMLElement;
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;
  graphData: WorldTreeGraphData;
  options: WorldTree2DOptions;

  // Viewport transform
  panX = 0;
  panY = 0;
  zoom = 1;
  isDragging = false;
  dragStartX = 0;
  dragStartY = 0;

  // Node drag
  draggedNode: GraphNode | null = null;
  hoveredNode: GraphNode | null = null;
  selectedNode: GraphNode | null = null;

  // Animation & Rendering
  animationFrameId: number | null = null;
  pulseTick = 0;
  isDestroyed = false;

  // Continuous morph parameter (0 = pure 2D, 1 = lifted 3D preview)
  morphFactor = 0;

  constructor(container: HTMLElement, graphData: WorldTreeGraphData, options: WorldTree2DOptions = {}) {
    this.container = container;
    this.graphData = graphData;
    this.options = options;

    this.canvas = document.createElement('canvas');
    this.canvas.className = 'w-full h-full block select-none cursor-grab active:cursor-grabbing';
    this.container.innerHTML = '';
    this.container.appendChild(this.canvas);

    const ctx = this.canvas.getContext('2d');
    if (!ctx) throw new Error('Unable to initialize 2D canvas context');
    this.ctx = ctx;

    this.initCanvasSize();
    this.centerView();
    this.bindEvents();
    this.startLoop();
  }

  initCanvasSize() {
    const dpr = window.devicePixelRatio || 1;
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;
    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.canvas.style.width = `${width}px`;
    this.canvas.style.height = `${height}px`;
    this.ctx.scale(dpr, dpr);
  }

  centerView() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;
    this.panX = width / 2;
    this.panY = height / 2;
    this.zoom = Math.min(width / 900, height / 700, 1.1);
  }

  setGraphData(graphData: WorldTreeGraphData) {
    this.graphData = graphData;
    this.requestRedraw();
  }

  setSelectedNode(node: GraphNode | null) {
    this.selectedNode = node;
    this.requestRedraw();
  }

  setFilter(filter: string) {
    this.options.activeFilter = filter;
    this.requestRedraw();
  }

  setSearchQuery(query: string) {
    this.options.searchQuery = query;
    this.requestRedraw();
  }

  setMorphFactor(factor: number) {
    this.morphFactor = Math.max(0, Math.min(1, factor));
    this.requestRedraw();
  }

  bindEvents() {
    const canvas = this.canvas;

    const onResize = () => {
      this.initCanvasSize();
      this.requestRedraw();
    };
    window.addEventListener('resize', onResize);

    canvas.addEventListener('mousedown', (e) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const hit = this.findNodeAt(mouseX, mouseY);
      if (hit) {
        this.draggedNode = hit;
        this.selectedNode = hit;
        if (this.options.onNodeSelect) {
          this.options.onNodeSelect(hit);
        }
      } else {
        this.isDragging = true;
        this.dragStartX = mouseX - this.panX;
        this.dragStartY = mouseY - this.panY;
      }
      this.requestRedraw();
    });

    window.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.draggedNode) {
        // Update dragged node position in graph coordinates
        const graphCoords = this.screenToGraph(mouseX, mouseY);
        this.draggedNode.x = graphCoords.x;
        this.draggedNode.y = graphCoords.y;
        this.requestRedraw();
      } else if (this.isDragging) {
        this.panX = mouseX - this.dragStartX;
        this.panY = mouseY - this.dragStartY;
        this.requestRedraw();
      } else {
        const hit = this.findNodeAt(mouseX, mouseY);
        if (hit !== this.hoveredNode) {
          this.hoveredNode = hit;
          if (this.options.onNodeHover) {
            this.options.onNodeHover(hit, hit ? { x: mouseX, y: mouseY } : null);
          }
          this.requestRedraw();
        }
      }
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.draggedNode = null;
    });

    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // Zoom centered at mouse position
      const newZoom = Math.max(0.2, Math.min(3.5, this.zoom * zoomFactor));
      this.panX = mouseX - (mouseX - this.panX) * (newZoom / this.zoom);
      this.panY = mouseY - (mouseY - this.panY) * (newZoom / this.zoom);
      this.zoom = newZoom;
      this.requestRedraw();
    }, { passive: false });

    canvas.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const hit = this.findNodeAt(mouseX, mouseY);
      if (hit && this.options.onNodeRightClick) {
        this.options.onNodeRightClick(hit, { x: e.clientX, y: e.clientY });
      }
    });
  }

  screenToGraph(screenX: number, screenY: number) {
    return {
      x: (screenX - this.panX) / this.zoom,
      y: (screenY - this.panY) / this.zoom
    };
  }

  graphToScreen(graphX: number, graphY: number, graphZ = 0) {
    // When morphFactor > 0, orthographic projection simulates perspective angle shift
    const zOffset = graphZ * this.morphFactor * 0.4;
    return {
      x: (graphX * this.zoom) + this.panX,
      y: ((graphY - zOffset) * this.zoom) + this.panY
    };
  }

  findNodeAt(screenX: number, screenY: number): GraphNode | null {
    const nodes = this.graphData.nodes;
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i];
      if (this.isNodeFilteredOut(node)) continue;

      const screen = this.graphToScreen(node.x, node.y, node.z);
      const radius = this.getNodeRadius(node) * this.zoom;
      const dx = screenX - screen.x;
      const dy = screenY - screen.y;
      if (dx * dx + dy * dy <= (radius + 6) * (radius + 6)) {
        return node;
      }
    }
    return null;
  }

  getNodeRadius(node: GraphNode): number {
    return Math.max(7, Math.min(22, 5 + (node.trust_tier * 3)));
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

  startLoop() {
    const loop = () => {
      if (this.isDestroyed) return;
      this.pulseTick += 0.04;
      this.draw();
      this.animationFrameId = requestAnimationFrame(loop);
    };
    this.animationFrameId = requestAnimationFrame(loop);
  }

  requestRedraw() {
    // Redraw triggered by next animation frame
  }

  draw() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;
    const ctx = this.ctx;

    ctx.save();
    ctx.clearRect(0, 0, width, height);

    // Deep Kinetic Obsidian background with orthographic cad grid
    ctx.fillStyle = '#050505';
    ctx.fillRect(0, 0, width, height);

    // Subtle 2D CAD Grid
    this.drawGrid(ctx, width, height);

    // Draw Links
    this.drawLinks(ctx);

    // Draw Nodes
    this.drawNodes(ctx);

    ctx.restore();
  }

  drawGrid(ctx: CanvasRenderingContext2D, width: number, height: number) {
    const gridSize = 40 * this.zoom;
    const offsetX = this.panX % gridSize;
    const offsetY = this.panY % gridSize;

    ctx.save();
    ctx.strokeStyle = 'rgba(34, 211, 238, 0.07)';
    ctx.lineWidth = 1;

    ctx.beginPath();
    for (let x = offsetX; x < width; x += gridSize) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
    }
    for (let y = offsetY; y < height; y += gridSize) {
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
    }
    ctx.stroke();

    // Central Axis Mundi Plumb Crosshair
    ctx.strokeStyle = 'rgba(212, 175, 55, 0.25)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(this.panX, 0);
    ctx.lineTo(this.panX, height);
    ctx.moveTo(0, this.panY);
    ctx.lineTo(width, this.panY);
    ctx.stroke();

    ctx.restore();
  }

  drawLinks(ctx: CanvasRenderingContext2D) {
    const links = this.graphData.links;
    const nodes = this.graphData.nodes;
    const nodeMap = new Map<string, GraphNode>();
    nodes.forEach(n => nodeMap.set(n.id, n));

    links.forEach(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' ? link.target.id : link.target;
      const source = nodeMap.get(sourceId);
      const target = nodeMap.get(targetId);

      if (!source || !target) return;
      if (this.isNodeFilteredOut(source) && this.isNodeFilteredOut(target)) return;

      const p1 = this.graphToScreen(source.x, source.y, source.z);
      const p2 = this.graphToScreen(target.x, target.y, target.z);

      const isSelected = this.selectedNode && 
        (this.selectedNode.id === source.id || this.selectedNode.id === target.id);

      ctx.save();
      ctx.strokeStyle = isSelected ? '#D4AF37' : link.color || 'rgba(107, 76, 154, 0.4)';
      ctx.lineWidth = (isSelected ? 2.5 : 1.2) * this.zoom;

      // In 2D: Straight lines (morphFactor curves them slightly during morph)
      ctx.beginPath();
      if (this.morphFactor > 0.05) {
        const midX = (p1.x + p2.x) / 2;
        const midY = (p1.y + p2.y) / 2 - (40 * this.morphFactor * this.zoom);
        ctx.moveTo(p1.x, p1.y);
        ctx.quadraticCurveTo(midX, midY, p2.x, p2.y);
      } else {
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
      }
      ctx.stroke();

      // Flow particle on active links
      if (link.active) {
        const t = (this.pulseTick * 0.5) % 1;
        const px = p1.x + (p2.x - p1.x) * t;
        const py = p1.y + (p2.y - p1.y) * t;
        ctx.fillStyle = isSelected ? '#ffffff' : link.color;
        ctx.beginPath();
        ctx.arc(px, py, 2.5 * this.zoom, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.restore();
    });
  }

  drawNodes(ctx: CanvasRenderingContext2D) {
    const nodes = this.graphData.nodes;
    const hasSearch = Boolean(this.options.searchQuery?.trim());

    nodes.forEach(node => {
      const isFiltered = this.isNodeFilteredOut(node);
      const isSearchMatch = hasSearch && this.isNodeSearchMatched(node);
      const isSelected = this.selectedNode?.id === node.id;
      const isHovered = this.hoveredNode?.id === node.id;

      const screen = this.graphToScreen(node.x, node.y, node.z);
      const radius = this.getNodeRadius(node) * this.zoom;

      ctx.save();
      if (isFiltered) {
        ctx.globalAlpha = 0.15;
      } else if (hasSearch && !isSearchMatch) {
        ctx.globalAlpha = 0.25;
      }

      // 3.1 Node Halos & State Rings according to specification:
      // verified: pulsing gold ring
      // running: cyan glow
      // approval_required: amber pulse
      // failed: red flicker
      // quarantined: violet static
      // stale: none
      const color = node.color || STATE_COLORS[node.state] || '#888888';

      if (node.state === 'verified') {
        const pulse = 1 + 0.25 * Math.sin(this.pulseTick * 3);
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, (radius + 4) * pulse, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(245, 197, 66, 0.4)';
        ctx.lineWidth = 2 * this.zoom;
        ctx.stroke();
      } else if (node.state === 'running') {
        const glowRadius = radius + 6 + 2 * Math.sin(this.pulseTick * 4);
        const grad = ctx.createRadialGradient(screen.x, screen.y, radius, screen.x, screen.y, glowRadius);
        grad.addColorStop(0, 'rgba(0, 229, 255, 0.6)');
        grad.addColorStop(1, 'rgba(0, 229, 255, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();
      } else if (node.state === 'approval_required') {
        const pulse = 1 + 0.3 * Math.abs(Math.sin(this.pulseTick * 2.5));
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, (radius + 5) * pulse, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 191, 0, 0.5)';
        ctx.lineWidth = 1.5 * this.zoom;
        ctx.stroke();
      } else if (node.state === 'failed') {
        const flicker = Math.random() > 0.4 ? 1 : 0.4;
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, radius + 3, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255, 68, 68, ${flicker * 0.7})`;
        ctx.lineWidth = 2 * this.zoom;
        ctx.stroke();
      } else if (node.state === 'quarantined') {
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, radius + 4, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(157, 78, 221, 0.8)';
        ctx.lineWidth = 2 * this.zoom;
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Selection Ring
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(screen.x, screen.y, radius + 7, 0, Math.PI * 2);
        ctx.strokeStyle = '#D4AF37';
        ctx.lineWidth = 3 * this.zoom;
        ctx.stroke();
      }

      // Node Body Circle
      ctx.beginPath();
      ctx.arc(screen.x, screen.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#050505';
      ctx.lineWidth = 2 * this.zoom;
      ctx.stroke();

      // Node Label
      if (this.zoom > 0.65 || isSelected || isHovered || isSearchMatch) {
        ctx.font = `${Math.max(10, Math.round(11 * this.zoom))}px monospace`;
        ctx.fillStyle = isSelected ? '#D4AF37' : '#e2e8f0';
        ctx.textAlign = 'center';
        ctx.fillText(node.label, screen.x, screen.y + radius + 13 * this.zoom);

        // State & Risk Badge
        ctx.font = `${Math.max(8, Math.round(9 * this.zoom))}px monospace`;
        ctx.fillStyle = '#94a3b8';
        ctx.fillText(`[${node.risk_tier} • T${node.trust_tier}]`, screen.x, screen.y + radius + 24 * this.zoom);
      }

      ctx.restore();
    });
  }

  destroy() {
    this.isDestroyed = true;
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    this.container.innerHTML = '';
  }
}
