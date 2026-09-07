import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { isWebGLAvailable } from '../utils/webglHelper';
import { 
  Layers, 
  RotateCcw, 
  X, 
  Maximize2, 
  Minimize2, 
  MousePointer, 
  Compass, 
  Box, 
  Sparkles, 
  ShieldCheck, 
  Info, 
  Eye, 
  Sliders, 
  Volume2, 
  VolumeX,
  Lock,
  Unlock,
  Move,
  ArrowDown
} from 'lucide-react';
import { audioEngine } from '../utils/audioEngine';

interface FixedThreeUiOverlayProps {
  onClose?: () => void;
  isEmbedded?: boolean;
}

interface SelectedNodeInfo {
  id: string;
  name: string;
  type: string;
  color: string;
  position: { x: number; y: number; z: number };
  connections: number;
  status: string;
}

export const FixedThreeUiOverlay: React.FC<FixedThreeUiOverlayProps> = ({
  onClose,
  isEmbedded = false
}) => {
  // Canvas and Container Refs
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Engine References
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const objectsGroupRef = useRef<THREE.Group | null>(null);
  const reqAnimRef = useRef<number | null>(null);

  // State Management
  const [hasWebGL, setHasWebGL] = useState<boolean>(true);
  const [selectedNode, setSelectedNode] = useState<SelectedNodeInfo | null>({
    id: 'node-001',
    name: 'Apex Memcastle Core',
    type: 'Celestial Spire Node',
    color: '#D4AF37',
    position: { x: 0, y: 3.5, z: 0 },
    connections: 12,
    status: 'ACTIVE_ZERO_TRUST'
  });
  const [isPanelCollapsed, setIsPanelCollapsed] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [canvasPointerEvents, setCanvasPointerEvents] = useState<'auto' | 'none'>('auto');
  const [scrollModeActive, setScrollModeActive] = useState<boolean>(false);
  const [scrollProgress, setScrollProgress] = useState<number>(0);
  const [wireframeMode, setWireframeMode] = useState<boolean>(false);
  const [nodeCount, setNodeCount] = useState<number>(18);
  const [edgeCount, setEdgeCount] = useState<number>(24);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [hoveredNodeName, setHoveredNodeName] = useState<string | null>(null);

  // Raycaster Refs
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mouseRef = useRef<THREE.Vector2>(new THREE.Vector2());

  // Initialize Three.js or 2.5D Fallback Canvas
  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    const parent = canvas.parentElement || document.body;
    const width = parent.clientWidth || window.innerWidth;
    const height = parent.clientHeight || window.innerHeight;

    let cleanupFn: (() => void) | null = null;
    const webglSupported = isWebGLAvailable();
    let renderer: THREE.WebGLRenderer | null = null;

    if (webglSupported) {
      const origError = console.error;
      const origWarn = console.warn;
      try {
        console.error = () => {};
        console.warn = () => {};
        renderer = new THREE.WebGLRenderer({
          canvas,
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance'
        });
      } catch {
        renderer = null;
      } finally {
        console.error = origError;
        console.warn = origWarn;
      }
    }

    if (renderer) {
      setHasWebGL(true);

      // 1. Scene setup
      const scene = new THREE.Scene();
      sceneRef.current = scene;

      // 2. Camera setup
      const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
      camera.position.set(0, 5, 15);
      camera.lookAt(0, 0, 0);
      cameraRef.current = camera;

      // 3. Renderer configuration
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      rendererRef.current = renderer;

      // 4. Lighting Rig
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
      scene.add(ambientLight);

      const dirLight = new THREE.DirectionalLight(0xd4af37, 2.0);
      dirLight.position.set(10, 20, 15);
      scene.add(dirLight);

      const pointLight = new THREE.PointLight(0x00e5ff, 2, 30);
      pointLight.position.set(-10, -5, 5);
      scene.add(pointLight);

      // 5. Build 3D Node Graph Mesh
      const group = new THREE.Group();
      objectsGroupRef.current = group;
      scene.add(group);

      const nodeGeom = new THREE.SphereGeometry(0.8, 32, 32);
      const colors = [0xd4af37, 0x00e5ff, 0xc084fc, 0x10b981, 0xf59e0b];
      const names = [
        'Apex Memcastle Core', 'Cognitive Canopy Node', 'Twin Brains Sync',
        'Axis Trunk SSM', 'Ouroboros Loop', 'Ancient Roots Conduit',
        'Viking Refractions DMA', 'Redis Vector Palace', 'Zero-Trust Gate'
      ];

      const nodesList: THREE.Mesh[] = [];

      for (let i = 0; i < 18; i++) {
        const angle = (i / 18) * Math.PI * 2;
        const radius = 6 + Math.sin(i * 2) * 2;
        const y = Math.sin(i * 1.5) * 4;

        const colorHex = colors[i % colors.length];
        const mat = new THREE.MeshStandardMaterial({
          color: colorHex,
          emissive: colorHex,
          emissiveIntensity: 0.3,
          roughness: 0.2,
          metalness: 0.8,
          wireframe: wireframeMode
        });

        const mesh = new THREE.Mesh(nodeGeom, mat);
        mesh.position.set(Math.cos(angle) * radius, y, Math.sin(angle) * radius);
        mesh.userData = {
          id: `node-${String(i + 1).padStart(3, '0')}`,
          name: names[i % names.length],
          type: i % 2 === 0 ? 'Primary Gateway' : 'Data Conduit',
          color: `#${colorHex.toString(16).padStart(6, '0')}`,
          connections: Math.floor(Math.random() * 10) + 3,
          status: 'ONLINE_SECURE'
        };
        group.add(mesh);
        nodesList.push(mesh);
      }

      // 6. Connect Edges
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x38bdf8,
        transparent: true,
        opacity: 0.4
      });

      for (let i = 0; i < nodesList.length; i++) {
        const nextIdx = (i + 1) % nodesList.length;
        const crossIdx = (i + 5) % nodesList.length;

        const p1 = nodesList[i].position;
        const p2 = nodesList[nextIdx].position;
        const p3 = nodesList[crossIdx].position;

        const geom1 = new THREE.BufferGeometry().setFromPoints([p1, p2]);
        const line1 = new THREE.Line(geom1, lineMat);
        group.add(line1);

        const geom2 = new THREE.BufferGeometry().setFromPoints([p1, p3]);
        const line2 = new THREE.Line(geom2, lineMat);
        group.add(line2);
      }

      // Mouse Orbit & Dragging
      let isDragging = false;
      let prevMouse = { x: 0, y: 0 };

      const onMouseDown = (e: MouseEvent) => {
        if (canvasPointerEvents === 'none') return;
        isDragging = true;
        prevMouse = { x: e.clientX, y: e.clientY };
      };

      const onMouseMove = (e: MouseEvent) => {
        // Raycasting Hover
        const rect = canvas.getBoundingClientRect();
        mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        if (cameraRef.current && objectsGroupRef.current) {
          raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current);
          const intersects = raycasterRef.current.intersectObjects(objectsGroupRef.current.children);
          if (intersects.length > 0) {
            const hit = intersects[0].object;
            if (hit.userData && hit.userData.name) {
              setHoveredNodeName(hit.userData.name);
            }
          } else {
            setHoveredNodeName(null);
          }
        }

        if (!isDragging || !objectsGroupRef.current) return;
        const dx = e.clientX - prevMouse.x;
        const dy = e.clientY - prevMouse.y;

        objectsGroupRef.current.rotation.y += dx * 0.005;
        objectsGroupRef.current.rotation.x += dy * 0.005;

        prevMouse = { x: e.clientX, y: e.clientY };
      };

      const onMouseUp = () => {
        isDragging = false;
      };

      // Raycast Click Handler
      const onClick = (e: MouseEvent) => {
        if (canvasPointerEvents === 'none') return;
        const rect = canvas.getBoundingClientRect();
        mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        if (cameraRef.current && objectsGroupRef.current) {
          raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current);
          const intersects = raycasterRef.current.intersectObjects(objectsGroupRef.current.children);
          if (intersects.length > 0) {
            const hitMesh = intersects[0].object as THREE.Mesh;
            if (hitMesh.userData) {
              audioEngine.playClick();
              setSelectedNode({
                id: hitMesh.userData.id,
                name: hitMesh.userData.name,
                type: hitMesh.userData.type,
                color: hitMesh.userData.color,
                position: {
                  x: Number(hitMesh.position.x.toFixed(2)),
                  y: Number(hitMesh.position.y.toFixed(2)),
                  z: Number(hitMesh.position.z.toFixed(2))
                },
                connections: hitMesh.userData.connections,
                status: hitMesh.userData.status
              });
            }
          }
        }
      };

      canvas.addEventListener('mousedown', onMouseDown);
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
      canvas.addEventListener('click', onClick);

      const handleResize = () => {
        const w = parent.clientWidth || window.innerWidth;
        const h = parent.clientHeight || window.innerHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };
      window.addEventListener('resize', handleResize);

      // Render Loop
      const animate = () => {
        reqAnimRef.current = requestAnimationFrame(animate);
        if (group && !isDragging) {
          group.rotation.y += 0.003;
        }
        renderer.render(scene, camera);
      };
      animate();

      cleanupFn = () => {
        if (reqAnimRef.current) cancelAnimationFrame(reqAnimRef.current);
        window.removeEventListener('resize', handleResize);
        canvas.removeEventListener('mousedown', onMouseDown);
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
        canvas.removeEventListener('click', onClick);
        renderer.dispose();
      };
    } else {
      // 2.5D Canvas Fallback
      setHasWebGL(false);
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      let rotY = 0;
      let animId: number | null = null;

      const render25D = () => {
        animId = requestAnimationFrame(render25D);
        rotY += 0.008;

        const cw = (canvas.width = (parent.clientWidth || window.innerWidth) * Math.min(window.devicePixelRatio, 2));
        const ch = (canvas.height = (parent.clientHeight || window.innerHeight) * Math.min(window.devicePixelRatio, 2));
        ctx.clearRect(0, 0, cw, ch);

        const cx = cw / 2;
        const cy = ch / 2;

        ctx.fillStyle = '#D4AF37';
        for (let i = 0; i < 18; i++) {
          const ang = (i / 18) * Math.PI * 2 + rotY;
          const rad = 140 * (cw / 1000);
          const px = cx + Math.cos(ang) * rad;
          const py = cy + Math.sin(i * 1.5) * 40 + Math.sin(ang) * 30;

          ctx.beginPath();
          ctx.arc(px, py, 12, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(px, py);
          ctx.stroke();
        }
      };
      render25D();

      cleanupFn = () => {
        if (animId) cancelAnimationFrame(animId);
      };
    }

    return () => {
      if (cleanupFn) cleanupFn();
    };
  }, [canvasPointerEvents]);

  // Update wireframe mode dynamically
  useEffect(() => {
    if (!objectsGroupRef.current) return;
    objectsGroupRef.current.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach((m) => (m.wireframe = wireframeMode));
        } else {
          child.material.wireframe = wireframeMode;
        }
      }
    });
  }, [wireframeMode]);

  // Handle scroll events when scroll content mode is active
  const handleScrollContent = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const progress = target.scrollTop / (target.scrollHeight - target.clientHeight);
    setScrollProgress(progress);

    if (cameraRef.current) {
      cameraRef.current.position.z = 15 - progress * 8;
      cameraRef.current.position.y = 5 + progress * 6;
      cameraRef.current.lookAt(0, 0, 0);
    }
  };

  return (
    <div 
      ref={containerRef}
      className={`relative w-full ${isEmbedded ? 'h-[720px] rounded-3xl' : 'h-screen fixed inset-0'} bg-[#0d0c15] text-slate-100 overflow-hidden select-none font-sans`}
    >
      {/* =========================================================================
          1. FIXED THREE.JS CANVAS (Z-INDEX: 0, POINTER-EVENTS: AUTO)
          Per Section 2.1: Layering with z-index
          ========================================================================= */}
      <canvas
        ref={canvasRef}
        id="three-canvas"
        className="absolute top-0 left-0 w-full h-full cursor-grab active:cursor-grabbing transition-opacity duration-300"
        style={{
          zIndex: 0,
          pointerEvents: canvasPointerEvents
        }}
        title="Three.js 3D Viewport - Click objects to inspect"
      />

      {/* Hovered Node Label Tooltip */}
      {hoveredNodeName && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-10 pointer-events-none px-3 py-1 rounded-full bg-black/90 border border-[#D4AF37] text-[#D4AF37] text-xs font-mono font-bold shadow-xl animate-fadeIn">
          🎯 {hoveredNodeName}
        </div>
      )}

      {/* =========================================================================
          2. HTML UI OVERLAY CONTAINER (Z-INDEX: 1, POINTER-EVENTS: NONE)
          Passes clicks through to canvas unless over interactive UI elements
          ========================================================================= */}
      <div 
        id="ui-overlay"
        className="absolute top-0 left-0 w-full h-full flex flex-col justify-between"
        style={{
          zIndex: 1,
          pointerEvents: 'none' // Crucial: Allows 3D mouse interaction through overlay
        }}
      >
        {/* =========================================================================
            2.1 FIXED HEADER (Z-INDEX: 10, POINTER-EVENTS: AUTO)
            ========================================================================= */}
        <header className="hud-header w-full h-16 bg-gradient-to-b from-[#1a1825]/95 via-[#1a1825]/80 to-transparent border-b border-[#1f1d2e] px-6 flex items-center justify-between z-10 pointer-events-auto backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-[#D4AF37]/20 border border-[#D4AF37]/60 flex items-center justify-center text-[#D4AF37] font-bold">
              ⚜️
            </div>
            <div>
              <h1 className="text-sm font-bold font-heraldic text-white flex items-center gap-2">
                3D Graph & Spatial UI Overlay
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 border border-emerald-500/50 text-emerald-400">
                  {hasWebGL ? 'WebGL 2.0' : '2.5D Canvas'}
                </span>
              </h1>
              <p className="text-[10px] font-mono text-slate-400">
                Pattern: Fixed Canvas (z-0) ⟷ Pass-Through UI Overlay (z-1)
              </p>
            </div>
          </div>

          {/* Quick Control Tools */}
          <div className="flex items-center gap-2 text-xs font-mono">
            {/* Scroll Mode Switch */}
            <button
              onClick={() => {
                setScrollModeActive(!scrollModeActive);
                audioEngine.playClick();
              }}
              className={`px-3 py-1.5 rounded-xl border flex items-center gap-1.5 transition-all cursor-pointer ${
                scrollModeActive
                  ? 'bg-purple-950 border-purple-500 text-purple-300 shadow-[0_0_12px_rgba(168,85,247,0.4)]'
                  : 'bg-black/60 border-slate-700 text-slate-300 hover:text-white'
              }`}
            >
              <Move className="w-3.5 h-3.5 text-purple-400" />
              <span>Scroll Content: {scrollModeActive ? 'ON' : 'OFF'}</span>
            </button>

            {/* Canvas Interaction Lock */}
            <button
              onClick={() => {
                const next = canvasPointerEvents === 'auto' ? 'none' : 'auto';
                setCanvasPointerEvents(next);
                audioEngine.playClick();
              }}
              className={`px-3 py-1.5 rounded-xl border flex items-center gap-1.5 transition-all cursor-pointer ${
                canvasPointerEvents === 'auto'
                  ? 'bg-emerald-950 border-emerald-500 text-emerald-300'
                  : 'bg-amber-950 border-amber-500 text-amber-300'
              }`}
              title="Toggle Pointer Events on 3D Canvas"
            >
              {canvasPointerEvents === 'auto' ? <Unlock className="w-3.5 h-3.5 text-emerald-400" /> : <Lock className="w-3.5 h-3.5 text-amber-400" />}
              <span>3D Input: {canvasPointerEvents === 'auto' ? 'ALLOWED' : 'BLOCKED'}</span>
            </button>

            {/* Reset View */}
            <button
              onClick={() => {
                if (cameraRef.current) {
                  cameraRef.current.position.set(0, 5, 15);
                  cameraRef.current.lookAt(0, 0, 0);
                }
                if (objectsGroupRef.current) {
                  objectsGroupRef.current.rotation.set(0, 0, 0);
                }
                audioEngine.playClick();
              }}
              className="px-3 py-1.5 rounded-xl bg-black/60 hover:bg-black border border-slate-700 hover:border-[#D4AF37] text-slate-200 hover:text-white transition-all cursor-pointer flex items-center gap-1"
            >
              <RotateCcw className="w-3.5 h-3.5 text-[#D4AF37]" />
              <span className="hidden sm:inline">Reset View</span>
            </button>

            {/* Modal Opener */}
            <button
              onClick={() => {
                setIsModalOpen(true);
                audioEngine.playClick();
              }}
              className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-[#D4AF37] to-amber-500 text-black font-bold hover:brightness-110 transition-all cursor-pointer shadow-lg"
            >
              Open Dialog
            </button>

            {onClose && (
              <button
                onClick={onClose}
                className="p-1.5 rounded-xl bg-black/60 hover:bg-red-950/80 border border-slate-700 hover:border-red-500 text-slate-400 hover:text-red-300 transition-all cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </header>

        {/* =========================================================================
            2.2 MAIN BODY VIEWPORT (OPTIONAL SCROLLABLE CONTENT OVERLAY)
            Per Section 3: Advanced Scrollable Content Over Fixed Canvas
            ========================================================================= */}
        {scrollModeActive ? (
          <div 
            onScroll={handleScrollContent}
            className="w-full flex-1 overflow-y-auto pointer-events-auto z-1 px-6 py-8 space-y-[80vh] scroll-smooth"
          >
            <div className="max-w-md bg-[#1a1825]/90 border border-[#1f1d2e] rounded-2xl p-6 backdrop-blur-md shadow-2xl space-y-2">
              <span className="text-[10px] font-mono text-[#D4AF37] uppercase tracking-wider">Scroll Section 01</span>
              <h2 className="text-xl font-bold font-heraldic text-white">Axis Mundi Apex Strata</h2>
              <p className="text-xs text-slate-300 leading-relaxed">
                Scroll down to navigate camera altitude through the 3D space. The canvas remains <code className="text-[#D4AF37]">position: fixed</code> at z-index 0.
              </p>
              <div className="pt-2 text-[10px] font-mono text-cyan-400 flex items-center gap-1">
                <ArrowDown className="w-3.5 h-3.5 animate-bounce" /> Scroll to transition camera...
              </div>
            </div>

            <div className="max-w-md bg-[#1a1825]/90 border border-cyan-800/60 rounded-2xl p-6 backdrop-blur-md shadow-2xl space-y-2 ml-auto">
              <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">Scroll Section 02</span>
              <h2 className="text-xl font-bold font-heraldic text-white">Cognitive Canopy & Twin Brains</h2>
              <p className="text-xs text-slate-300 leading-relaxed">
                Camera position Z updates dynamically from {15 - scrollProgress * 8} to 7 as scroll progress increases.
              </p>
            </div>

            <div className="max-w-md bg-[#1a1825]/90 border border-purple-800/60 rounded-2xl p-6 backdrop-blur-md shadow-2xl space-y-2">
              <span className="text-[10px] font-mono text-purple-400 uppercase tracking-wider">Scroll Section 03</span>
              <h2 className="text-xl font-bold font-heraldic text-white">Ancient VFS Root Refractions</h2>
              <p className="text-xs text-slate-300 leading-relaxed">
                Full 3D object hit testing and raycasting remains fully operational over the background scene.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex-1 w-full relative">
            {/* Instruction Badge */}
            <div className="absolute top-4 left-6 pointer-events-auto">
              <div className="px-3 py-2 rounded-2xl bg-black/85 backdrop-blur-md border border-slate-800 text-[11px] font-mono space-y-1 shadow-2xl">
                <div className="flex items-center gap-2 text-[#D4AF37] font-bold">
                  <MousePointer className="w-3.5 h-3.5" /> 3D INTERACTION GUIDE
                </div>
                <p className="text-slate-400 text-[10px]">
                  • Drag on canvas to rotate 3D node lattice<br />
                  • Click any sphere to select node & inspect in right panel
                </p>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            2.3 COLLAPSIBLE SIDE PANEL / NODE INSPECTOR (Z-INDEX: 20, POINTER-EVENTS: AUTO)
            Per Section 4.2: Collapsible Side Panel
            ========================================================================= */}
        <aside 
          className={`hud-panel absolute top-20 right-6 w-80 max-h-[calc(100vh-160px)] bg-[#1a1825]/95 border border-[#1f1d2e] rounded-2xl p-5 shadow-2xl z-20 pointer-events-auto backdrop-blur-md overflow-y-auto transition-all duration-300 ${
            isPanelCollapsed ? 'translate-x-[calc(100%+40px)] opacity-50' : 'translate-x-0 opacity-100'
          }`}
        >
          <div className="flex items-center justify-between border-b border-[#1f1d2e] pb-3 mb-3">
            <h2 className="text-xs font-bold font-mono text-white uppercase tracking-wider flex items-center gap-2">
              <Info className="w-4 h-4 text-[#D4AF37]" /> Node Details Inspector
            </h2>
            <button
              onClick={() => setIsPanelCollapsed(!isPanelCollapsed)}
              className="text-slate-400 hover:text-white text-xs font-mono p-1 rounded bg-black/40 border border-slate-800"
              title="Collapse Side Panel"
            >
              {isPanelCollapsed ? 'Expand ◀' : 'Collapse ▶'}
            </button>
          </div>

          {selectedNode ? (
            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 rounded-xl bg-black/60 border border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white text-sm">{selectedNode.name}</span>
                  <span 
                    className="w-3 h-3 rounded-full shadow-[0_0_8px_currentColor]"
                    style={{ backgroundColor: selectedNode.color, color: selectedNode.color }}
                  />
                </div>
                <div className="text-[10px] text-slate-400">{selectedNode.id} • {selectedNode.type}</div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="bg-black/40 border border-slate-800 rounded-lg p-2">
                  <span className="text-slate-500 block">POSITION (X,Y,Z)</span>
                  <span className="text-cyan-300 font-bold">{selectedNode.position.x}, {selectedNode.position.y}, {selectedNode.position.z}</span>
                </div>
                <div className="bg-black/40 border border-slate-800 rounded-lg p-2">
                  <span className="text-slate-500 block">CONNECTIONS</span>
                  <span className="text-emerald-400 font-bold">{selectedNode.connections} Edges</span>
                </div>
              </div>

              <div className="p-2.5 rounded-xl bg-black/40 border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-500 block">SECURITY STATUS</span>
                <span className="text-xs font-bold text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> {selectedNode.status}
                </span>
              </div>

              {/* Toggle Wireframe for Mesh */}
              <button
                onClick={() => {
                  setWireframeMode(!wireframeMode);
                  audioEngine.playClick();
                }}
                className={`w-full py-2 rounded-xl text-xs font-mono font-bold border transition-all cursor-pointer flex items-center justify-center gap-2 ${
                  wireframeMode
                    ? 'bg-amber-950 border-amber-500 text-amber-300'
                    : 'bg-black/80 border-slate-700 text-slate-300 hover:text-white'
                }`}
              >
                <Box className="w-3.5 h-3.5 text-[#D4AF37]" />
                <span>Wireframe Mode: {wireframeMode ? 'ON' : 'OFF'}</span>
              </button>
            </div>
          ) : (
            <div className="text-slate-500 text-xs font-mono text-center py-6">
              Click any 3D node in the scene to inspect properties...
            </div>
          )}
        </aside>

        {/* Collapsed Panel Handle */}
        {isPanelCollapsed && (
          <button
            onClick={() => setIsPanelCollapsed(false)}
            className="absolute top-20 right-2 z-20 pointer-events-auto px-2 py-3 rounded-l-xl bg-[#1a1825] border border-[#1f1d2e] text-[#D4AF37] font-mono text-xs font-bold shadow-2xl hover:bg-black transition-all cursor-pointer"
          >
            ◀ Inspector
          </button>
        )}

        {/* =========================================================================
            2.4 FIXED FOOTER HUD (Z-INDEX: 10, POINTER-EVENTS: AUTO)
            Per Section 4.1: Fixed Header + Footer
            ========================================================================= */}
        <footer className="hud-footer w-full h-10 bg-gradient-to-t from-[#1a1825]/95 via-[#1a1825]/80 to-transparent border-t border-[#1f1d2e] px-6 flex items-center justify-between text-xs font-mono text-slate-400 z-10 pointer-events-auto backdrop-blur-md">
          <div className="flex items-center gap-6">
            <span>Nodes: <strong className="text-white">{nodeCount}</strong></span>
            <span>Edges: <strong className="text-cyan-400">{edgeCount}</strong></span>
            <span className="hidden md:inline">Renderer: <strong className="text-emerald-400">THREE.WebGLRenderer</strong></span>
          </div>

          <div className="flex items-center gap-4 text-[11px]">
            {scrollModeActive && (
              <span className="text-[#D4AF37]">
                Scroll Progress: <strong>{(scrollProgress * 100).toFixed(0)}%</strong>
              </span>
            )}
            <span className="text-slate-500 hidden sm:inline">🖱️ Drag: Rotate | Click Node: Raycast Inspect</span>
          </div>
        </footer>
      </div>

      {/* =========================================================================
          3. MODAL / DIALOG OVERLAY (Z-INDEX: 100, POINTER-EVENTS: AUTO)
          Per Section 4.3: Modal/dialog overlay
          Blocks canvas interaction while active
          ========================================================================= */}
      {isModalOpen && (
        <div 
          className="ui-modal-overlay fixed inset-0 w-full h-full bg-black/75 backdrop-blur-md z-[100] pointer-events-auto flex items-center justify-center p-4 animate-fadeIn"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsModalOpen(false);
          }}
        >
          <div className="ui-modal bg-[#1a1825] border border-[#1f1d2e] rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-start justify-between border-b border-[#1f1d2e] pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[#D4AF37]" />
                <h3 className="text-base font-bold font-heraldic text-white">
                  HTML UI Overlay Architecture
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg bg-black/40 border border-slate-800 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              This dialog operates at <code className="text-[#D4AF37]">z-index: 100</code> with full pointer capture. While open, background 3D raycasting and mouse drag are automatically safe.
            </p>

            <div className="p-3 rounded-2xl bg-black/60 border border-slate-800 space-y-2 text-xs font-mono">
              <div className="text-[#D4AF37] font-bold">Z-INDEX HIERARCHY SUMMARY:</div>
              <div className="text-slate-300">• z-index 0: Fixed Three.js WebGL Canvas</div>
              <div className="text-slate-300">• z-index 1: UI Container (pointer-events: none)</div>
              <div className="text-slate-300">• z-index 10: Fixed Header & Footer HUDs</div>
              <div className="text-slate-300">• z-index 20: Collapsible Node Inspector Panel</div>
              <div className="text-emerald-400">• z-index 100: Active Dialog Modals</div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-[#D4AF37] hover:bg-amber-400 text-black font-bold text-xs cursor-pointer transition-all shadow-lg"
              >
                Close & Resume 3D Session
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
