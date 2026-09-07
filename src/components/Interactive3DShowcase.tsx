import React, { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { isWebGLAvailable } from '../utils/webglHelper';
import { 
  Sparkles, 
  Layers, 
  Orbit, 
  Maximize2, 
  Minimize2, 
  Volume2, 
  VolumeX, 
  Activity, 
  Zap, 
  Cpu, 
  Database, 
  ShieldCheck, 
  Eye, 
  Sliders, 
  RefreshCw, 
  ExternalLink, 
  TreeDeciduous, 
  Compass, 
  Terminal, 
  Lock, 
  ArrowUpRight, 
  CheckCircle2, 
  Play, 
  Pause,
  Box,
  Flame,
  Binary
} from 'lucide-react';
import { audioEngine } from '../utils/audioEngine';
import { FixedThreeUiOverlay } from './FixedThreeUiOverlay';

interface Interactive3DShowcaseProps {
  vitals?: any;
  onNavigateTab?: (tab: string) => void;
  onExecuteCommand?: (cmd: string) => void;
  onSwitchContinuityView?: (view: 'scroller' | 'hud' | 'unified' | 'split') => void;
}

// Technology & Ecosystem items for the two-row infinite carousel
interface TechItem {
  id: string;
  name: string;
  category: string;
  badge: string;
  desc: string;
  icon: string;
  glow: string;
}

const CAROUSEL_ROW_1: TechItem[] = [
  { id: 'gemini', name: 'Gemini 3.8 Flash', category: 'Reasoning Kernel', badge: '1M Context', desc: 'Multimodal Spatial Synthesis Engine', icon: '⚡', glow: 'rgba(212, 175, 55, 0.5)' },
  { id: 'nextjs', name: 'Next.js 16 + React 19', category: 'App Framework', badge: 'v16.0 Canary', desc: 'Isomorphic Server Actions & Fluid DOM', icon: '⚛️', glow: 'rgba(0, 229, 255, 0.5)' },
  { id: 'three', name: 'Three.js WebGL/WebGPU', category: 'Spatial Canvas', badge: '60 FPS', desc: 'Transparent Buffer & Dynamic Mesh Shaders', icon: '🔮', glow: 'rgba(192, 132, 252, 0.5)' },
  { id: 'tailwind', name: 'Tailwind CSS v4', category: 'Kinetic Styling', badge: 'Zero Runtime', desc: 'Engineered Obsidian & Gold Theme System', icon: '🎨', glow: 'rgba(56, 189, 248, 0.5)' },
  { id: 'redis', name: 'Redis MemCastle', category: 'Memory Architecture', badge: 'Port 6379', desc: '/vfs/mempalace/* Zero-Trust Key-Value Cache', icon: '💎', glow: 'rgba(239, 68, 68, 0.5)' },
  { id: 'z3', name: 'Z3 SMT Prover', category: 'Formal Verification', badge: '44 Theorems', desc: 'Neurosymbolic Proof Checker for Zero Faults', icon: '🛡️', glow: 'rgba(34, 197, 94, 0.5)' },
  { id: 'bitnet', name: 'BitNet 1.58b', category: 'Ternary Network', badge: '{-1,0,1}', desc: 'Zero-Multiplication Energy Efficient Core', icon: '🦾', glow: 'rgba(245, 158, 11, 0.5)' },
  { id: 'wasm', name: 'WASM32 Zero-Copy', category: 'Bytecode Engine', badge: '<50MB VRAM', desc: 'Edge Confinement & DMA Memory Slabs', icon: '⚙️', glow: 'rgba(168, 85, 247, 0.5)' }
];

const CAROUSEL_ROW_2: TechItem[] = [
  { id: 'neo4j', name: 'Neo4j UKG Lattice', category: 'Graph Database', badge: 'L1-L7 Topology', desc: 'Unified Knowledge Graph Spatial Vectors', icon: '🌿', glow: 'rgba(52, 211, 153, 0.5)' },
  { id: 'viking', name: 'Viking Drakkar Refractions', category: 'DMA Channels', badge: '12μs Latency', desc: 'Lock-Free Shared Memory Ring Buffers', icon: '⚓', glow: 'rgba(14, 165, 233, 0.5)' },
  { id: 'solfeggio', name: 'Solfeggio 528Hz', category: 'Acoustic Harmonics', badge: 'Axis Mundi', desc: 'Cellular Coherence Audio Synthesizer', icon: '🎼', glow: 'rgba(234, 179, 8, 0.5)' },
  { id: 'stitch', name: 'Sir Stitch', category: 'Knight of Motion', badge: 'effects_menu', desc: 'Kinetic Frame-Scroll Matrix Physics', icon: '🧵', glow: 'rgba(217, 70, 239, 0.5)' },
  { id: 'visage', name: 'Sir Visage', category: 'Knight of Vision', badge: 'immersive_web', desc: 'WebGPU Spatial Isolation & Baked Lighting', icon: '👁️', glow: 'rgba(99, 102, 241, 0.5)' },
  { id: 'hydron', name: 'Sir Hydron', category: 'Knight of Depth', badge: 'editorial_web', desc: 'CSS Z-Index Sandwiches & 0.00 CLS Protocol', icon: '🌊', glow: 'rgba(6, 182, 212, 0.5)' },
  { id: 'merlin', name: 'Merlin Ω', category: 'DAG Orchestrator', badge: 'Topological Sort', desc: 'Triple-QFT Symbolic Task Decomposer', icon: '🧙‍♂️', glow: 'rgba(244, 63, 94, 0.5)' },
  { id: 'anya', name: 'Anya Ω Aegis', category: 'Security Hypervisor', badge: 'Zero-Trust', desc: 'Immutable Edge Boundary Sentinel', icon: '⚜️', glow: 'rgba(212, 175, 55, 0.5)' }
];

export const Interactive3DShowcase: React.FC<Interactive3DShowcaseProps> = ({
  vitals,
  onNavigateTab,
  onExecuteCommand,
  onSwitchContinuityView
}) => {
  // 3D Canvas Mounting Ref
  const mountRef = useRef<HTMLDivElement | null>(null);

  // 3D Scene Interactive Controls
  const [isRotating, setIsRotating] = useState<boolean>(true);
  const [rotationSpeed, setRotationSpeed] = useState<number>(0.008);
  const [wireframeMode, setWireframeMode] = useState<boolean>(false);
  const [explodeValue, setExplodeValue] = useState<number>(20);
  const [activeLighting, setActiveLighting] = useState<'luxora' | 'cyber' | 'purple' | 'studio'>('luxora');
  const [activeStrataPreset, setActiveStrataPreset] = useState<'apex' | 'canopy' | 'trunk' | 'roots'>('apex');
  const [soundActive, setSoundActive] = useState<boolean>(true);
  const [selectedNodeTelemetry, setSelectedNodeTelemetry] = useState<any>(null);
  const [solfeggioFreq, setSolfeggioFreq] = useState<number>(528);
  const [activeTabFeature, setActiveTabFeature] = useState<'3d_model' | 'kinetic_scroll' | 'bento_mesh' | 'solfeggio'>('3d_model');

  // Engine Status
  const [hasWebGL, setHasWebGL] = useState<boolean>(true);
  const [showUiOverlayDemo, setShowUiOverlayDemo] = useState<boolean>(false);

  // Three.js References
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const strataLayersRef = useRef<THREE.Group[]>([]);
  const dirLightRef = useRef<THREE.DirectionalLight | null>(null);
  const rimLightRef = useRef<THREE.DirectionalLight | null>(null);
  const reqAnimRef = useRef<number | null>(null);

  // Reactive state refs for 60fps animation loops
  const isRotatingRef = useRef(isRotating);
  isRotatingRef.current = isRotating;
  const rotationSpeedRef = useRef(rotationSpeed);
  rotationSpeedRef.current = rotationSpeed;
  const wireframeModeRef = useRef(wireframeMode);
  wireframeModeRef.current = wireframeMode;
  const explodeValueRef = useRef(explodeValue);
  explodeValueRef.current = explodeValue;
  const activeLightingRef = useRef(activeLighting);
  activeLightingRef.current = activeLighting;
  const targetStrataYRef = useRef(0);

  // Performance & LOD Telemetry
  const simulatedNodes = 348;
  const isLODActive = simulatedNodes > 300;
  const ramUtilization = vitals?.usedRamMB ? (vitals.usedRamMB / 8192) * 100 : 59.7;

  // Initialize Interactive 3D Model Stage with WebGL / 2.5D Fallback
  useEffect(() => {
    if (!mountRef.current) return;
    const container = mountRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;

    let cleanupFn: (() => void) | null = null;

    // 1. WebGL Availability Probe
    const webglSupported = isWebGLAvailable();
    let renderer: THREE.WebGLRenderer | null = null;

    if (webglSupported) {
      const origError = console.error;
      const origWarn = console.warn;
      try {
        console.error = () => {};
        console.warn = () => {};
        renderer = new THREE.WebGLRenderer({
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

      // --- THREE.JS WEBGL RENDERER INITIALIZATION ---
      const scene = new THREE.Scene();
      sceneRef.current = scene;

      const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
      camera.position.set(0, 35, 95);
      camera.lookAt(0, 5, 0);
      cameraRef.current = camera;

      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      rendererRef.current = renderer;
      container.replaceChildren(renderer.domElement);

      const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
      scene.add(ambientLight);

      const dirLight = new THREE.DirectionalLight(0xd4af37, 1.8);
      dirLight.position.set(40, 60, 40);
      scene.add(dirLight);
      dirLightRef.current = dirLight;

      const rimLight = new THREE.DirectionalLight(0x00e5ff, 1.2);
      rimLight.position.set(-40, -20, -30);
      scene.add(rimLight);
      rimLightRef.current = rimLight;

      const rootGroup = new THREE.Group();
      modelGroupRef.current = rootGroup;
      scene.add(rootGroup);

      strataLayersRef.current = [];

      // Layer 0: Roots
      const rootsGroup = new THREE.Group();
      rootsGroup.position.y = -20;
      for (let i = 0; i < 6; i++) {
        const angle = (i / 6) * Math.PI * 2;
        const rootCurve = new THREE.CubicBezierCurve3(
          new THREE.Vector3(0, 0, 0),
          new THREE.Vector3(Math.cos(angle) * 10, -5, Math.sin(angle) * 10),
          new THREE.Vector3(Math.cos(angle) * 22, -15, Math.sin(angle) * 22),
          new THREE.Vector3(Math.cos(angle) * 32, -22, Math.sin(angle) * 32)
        );
        const rootGeom = new THREE.TubeGeometry(rootCurve, 20, 0.8, 8, false);
        const rootMat = new THREE.MeshStandardMaterial({
          color: 0x10b981,
          emissive: 0x064e3b,
          roughness: 0.3,
          metalness: 0.8,
          wireframe: wireframeMode
        });
        const rootMesh = new THREE.Mesh(rootGeom, rootMat);
        rootsGroup.add(rootMesh);
      }
      rootGroup.add(rootsGroup);
      strataLayersRef.current.push(rootsGroup);

      // Layer 1: Trunk & Ouroboros
      const trunkGroup = new THREE.Group();
      trunkGroup.position.y = -5;
      const trunkGeom = new THREE.CylinderGeometry(3.5, 6.5, 24, 16);
      const trunkMat = new THREE.MeshStandardMaterial({
        color: 0xf59e0b,
        emissive: 0x78350f,
        roughness: 0.4,
        metalness: 0.6,
        wireframe: wireframeMode
      });
      const trunkMesh = new THREE.Mesh(trunkGeom, trunkMat);
      trunkGroup.add(trunkMesh);

      const ringGeom = new THREE.TorusGeometry(10, 0.6, 12, 36);
      const ringMat = new THREE.MeshStandardMaterial({
        color: 0xd4af37,
        emissive: 0xd4af37,
        emissiveIntensity: 0.4,
        metalness: 0.9,
        roughness: 0.1
      });
      const ringMesh = new THREE.Mesh(ringGeom, ringMat);
      ringMesh.rotation.x = Math.PI / 2.3;
      trunkGroup.add(ringMesh);

      rootGroup.add(trunkGroup);
      strataLayersRef.current.push(trunkGroup);

      // Layer 2: Canopy & Twin Brains
      const canopyGroup = new THREE.Group();
      canopyGroup.position.y = 12;
      const canopyGeom = new THREE.IcosahedronGeometry(14, 1);
      const canopyMat = new THREE.MeshStandardMaterial({
        color: 0xc084fc,
        emissive: 0x581c87,
        wireframe: true,
        roughness: 0.2,
        metalness: 0.7
      });
      const canopyMesh = new THREE.Mesh(canopyGeom, canopyMat);
      canopyGroup.add(canopyMesh);

      const brain1 = new THREE.Mesh(
        new THREE.SphereGeometry(3.2, 16, 16),
        new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x0284c7, metalness: 0.8 })
      );
      brain1.position.set(-14, 3, 0);
      canopyGroup.add(brain1);

      const brain2 = new THREE.Mesh(
        new THREE.SphereGeometry(3.2, 16, 16),
        new THREE.MeshStandardMaterial({ color: 0xc084fc, emissive: 0x7e22ce, metalness: 0.8 })
      );
      brain2.position.set(14, 3, 0);
      canopyGroup.add(brain2);

      rootGroup.add(canopyGroup);
      strataLayersRef.current.push(canopyGroup);

      // Layer 3: Apex Memcastle
      const apexGroup = new THREE.Group();
      apexGroup.position.y = 28;
      const spireGeom = new THREE.ConeGeometry(5, 16, 6);
      const spireMat = new THREE.MeshStandardMaterial({
        color: 0xd4af37,
        emissive: 0xf59e0b,
        emissiveIntensity: 0.5,
        metalness: 0.95,
        roughness: 0.1,
        wireframe: wireframeMode
      });
      const spireMesh = new THREE.Mesh(spireGeom, spireMat);
      apexGroup.add(spireMesh);

      const crownGeom = new THREE.TorusGeometry(7.5, 0.4, 8, 32);
      const crownMat = new THREE.MeshBasicMaterial({ color: 0xffe066 });
      const crownMesh = new THREE.Mesh(crownGeom, crownMat);
      crownMesh.rotation.x = Math.PI / 2;
      crownMesh.position.y = 2;
      apexGroup.add(crownMesh);

      rootGroup.add(apexGroup);
      strataLayersRef.current.push(apexGroup);

      // Particles
      const particleCount = 240;
      const particleGeom = new THREE.BufferGeometry();
      const particlePositions = new Float32Array(particleCount * 3);
      for (let i = 0; i < particleCount * 3; i += 3) {
        const radius = 18 + Math.random() * 26;
        const theta = Math.random() * Math.PI * 2;
        const phi = (Math.random() - 0.5) * Math.PI;
        particlePositions[i] = radius * Math.cos(phi) * Math.cos(theta);
        particlePositions[i + 1] = (Math.random() - 0.5) * 60;
        particlePositions[i + 2] = radius * Math.cos(phi) * Math.sin(theta);
      }
      particleGeom.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
      const particleMat = new THREE.PointsMaterial({
        color: 0xd4af37,
        size: 1.2,
        transparent: true,
        opacity: 0.75
      });
      const particleSystem = new THREE.Points(particleGeom, particleMat);
      rootGroup.add(particleSystem);

      // Drag Orbit
      let isDragging = false;
      let previousMousePosition = { x: 0, y: 0 };
      const onMouseDown = (e: MouseEvent) => {
        isDragging = true;
        previousMousePosition = { x: e.clientX, y: e.clientY };
      };
      const onMouseMove = (e: MouseEvent) => {
        if (!isDragging || !rootGroup) return;
        const deltaX = e.clientX - previousMousePosition.x;
        const deltaY = e.clientY - previousMousePosition.y;
        rootGroup.rotation.y += deltaX * 0.008;
        rootGroup.rotation.x += deltaY * 0.006;
        rootGroup.rotation.x = Math.max(-Math.PI / 4, Math.min(Math.PI / 4, rootGroup.rotation.x));
        previousMousePosition = { x: e.clientX, y: e.clientY };
      };
      const onMouseUp = () => {
        isDragging = false;
      };

      container.addEventListener('mousedown', onMouseDown);
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);

      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const nw = entry.contentRect.width;
          const nh = entry.contentRect.height;
          if (nw > 0 && nh > 0) {
            camera.aspect = nw / nh;
            camera.updateProjectionMatrix();
            renderer.setSize(nw, nh);
          }
        }
      });
      resizeObserver.observe(container);

      const animate = () => {
        reqAnimRef.current = requestAnimationFrame(animate);
        if (isRotatingRef.current && !isDragging && rootGroup) {
          rootGroup.rotation.y += rotationSpeedRef.current;
        }
        ringMesh.rotation.z += 0.015;
        crownMesh.rotation.z -= 0.01;
        particleSystem.rotation.y += 0.002;
        renderer.render(scene, camera);
      };
      animate();

      cleanupFn = () => {
        if (reqAnimRef.current) cancelAnimationFrame(reqAnimRef.current);
        resizeObserver.disconnect();
        container.removeEventListener('mousedown', onMouseDown);
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
        renderer.dispose();
        container.replaceChildren();
      };
    } else {
      // --- 2.5D KINETIC CANVAS FALLBACK ENGINE (SANDBOX COMPATIBLE) ---
      setHasWebGL(false);
      const canvas = document.createElement('canvas');
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      canvas.style.display = 'block';
      container.replaceChildren(canvas);

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      let currentCamY = 0;
      let rotX = 0.25;
      let rotY = 0;
      let isDragging = false;
      let prevMouse = { x: 0, y: 0 };
      let animId: number | null = null;
      let time = 0;

      // 60 orbital particles
      const particles: { x: number; y: number; z: number; speed: number; radius: number }[] = [];
      for (let i = 0; i < 60; i++) {
        const rad = 25 + Math.random() * 50;
        const angle = Math.random() * Math.PI * 2;
        particles.push({
          x: Math.cos(angle) * rad,
          y: (Math.random() - 0.5) * 160,
          z: Math.sin(angle) * rad,
          speed: 0.005 + Math.random() * 0.01,
          radius: 1 + Math.random() * 2
        });
      }

      const onMouseDown = (e: MouseEvent) => {
        isDragging = true;
        prevMouse = { x: e.clientX, y: e.clientY };
      };
      const onMouseMove = (e: MouseEvent) => {
        if (!isDragging) return;
        const dx = e.clientX - prevMouse.x;
        const dy = e.clientY - prevMouse.y;
        rotY += dx * 0.008;
        rotX += dy * 0.006;
        rotX = Math.max(-Math.PI / 4, Math.min(Math.PI / 4, rotX));
        prevMouse = { x: e.clientX, y: e.clientY };
      };
      const onMouseUp = () => {
        isDragging = false;
      };

      container.addEventListener('mousedown', onMouseDown);
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);

      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const nw = entry.contentRect.width;
          const nh = entry.contentRect.height;
          if (nw > 0 && nh > 0) {
            canvas.width = nw * dpr;
            canvas.height = nh * dpr;
          }
        }
      });
      resizeObserver.observe(container);

      const render25D = () => {
        animId = requestAnimationFrame(render25D);
        time += 0.02;

        if (isRotatingRef.current && !isDragging) {
          rotY += rotationSpeedRef.current;
        }

        currentCamY += (targetStrataYRef.current - currentCamY) * 0.08;

        const cw = canvas.width;
        const ch = canvas.height;
        ctx.clearRect(0, 0, cw, ch);

        const cx = cw / 2;
        const cy = ch / 2 + currentCamY * (cw / 800);
        const fov = 440;

        const project = (x: number, y: number, z: number) => {
          const cosY = Math.cos(rotY);
          const sinY = Math.sin(rotY);
          const x1 = x * cosY - z * sinY;
          const z1 = z * cosY + x * sinY;

          const cosX = Math.cos(rotX);
          const sinX = Math.sin(rotX);
          const y2 = y * cosX - z1 * sinX;
          const z2 = z1 * cosX + y * sinX;

          const scale = fov / (fov + z2 + 200);
          return {
            x: cx + x1 * scale * (cw / 700),
            y: cy - y2 * scale * (ch / 500),
            scale: scale * (cw / 700),
            depth: z2
          };
        };

        const palette = activeLightingRef.current;
        let primaryCol = '#D4AF37';
        let glowCol = 'rgba(212, 175, 55, 0.4)';

        if (palette === 'cyber') {
          primaryCol = '#00E5FF';
          glowCol = 'rgba(0, 229, 255, 0.4)';
        } else if (palette === 'purple') {
          primaryCol = '#C084FC';
          glowCol = 'rgba(192, 132, 252, 0.4)';
        } else if (palette === 'studio') {
          primaryCol = '#E2E8F0';
          glowCol = 'rgba(255, 255, 255, 0.2)';
        }

        const isWire = wireframeModeRef.current;
        const factor = explodeValueRef.current / 20;

        // 1. Orbital Particles
        ctx.fillStyle = primaryCol;
        for (const p of particles) {
          const px = Math.cos(time * p.speed * 20 + p.radius) * (35 + p.radius * 8);
          const pz = Math.sin(time * p.speed * 20 + p.radius) * (35 + p.radius * 8);
          const pt = project(px, p.y, pz);
          if (pt.scale > 0) {
            const alpha = Math.max(0.15, Math.min(0.85, (pt.depth + 100) / 200));
            ctx.globalAlpha = alpha;
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, Math.max(1, p.radius * pt.scale), 0, Math.PI * 2);
            ctx.fill();
          }
        }
        ctx.globalAlpha = 1.0;

        // 2. Strata 0: Roots Conduits
        const rootsY = -55 * factor;
        ctx.strokeStyle = '#10B981';
        ctx.lineWidth = Math.max(1.5, 2.5 * (cw / 800));
        for (let i = 0; i < 6; i++) {
          const ang = (i / 6) * Math.PI * 2;
          const pStart = project(0, rootsY + 15, 0);
          const pMid = project(Math.cos(ang) * 35, rootsY, Math.sin(ang) * 35);
          const pEnd = project(Math.cos(ang) * 65, rootsY - 20, Math.sin(ang) * 65);

          ctx.beginPath();
          ctx.moveTo(pStart.x, pStart.y);
          ctx.quadraticCurveTo(pMid.x, pMid.y, pEnd.x, pEnd.y);
          ctx.stroke();

          ctx.fillStyle = '#34D399';
          ctx.beginPath();
          ctx.arc(pEnd.x, pEnd.y, Math.max(2, 4 * pEnd.scale), 0, Math.PI * 2);
          ctx.fill();
        }

        // 3. Strata 1: Axis Trunk & Ouroboros Ring
        const trunkY = -10 * factor;
        ctx.strokeStyle = isWire ? primaryCol : '#F59E0B';
        ctx.lineWidth = Math.max(2, 4 * (cw / 800));
        const pTrunkBottom = project(0, trunkY - 25, 0);
        const pTrunkTop = project(0, trunkY + 25, 0);
        ctx.beginPath();
        ctx.moveTo(pTrunkBottom.x, pTrunkBottom.y);
        ctx.lineTo(pTrunkTop.x, pTrunkTop.y);
        ctx.stroke();

        ctx.strokeStyle = primaryCol;
        ctx.lineWidth = Math.max(1.5, 3 * (cw / 800));
        ctx.beginPath();
        for (let a = 0; a <= Math.PI * 2 + 0.1; a += Math.PI / 12) {
          const ringRad = 28;
          const rx = Math.cos(a + time * 0.5) * ringRad;
          const rz = Math.sin(a + time * 0.5) * ringRad;
          const ry = trunkY + Math.sin(a * 2 + time) * 3;
          const pt = project(rx, ry, rz);
          if (a === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.stroke();

        // 4. Strata 2: Cognitive Canopy & Twin Brains
        const canopyY = 40 * factor;
        ctx.strokeStyle = isWire ? '#C084FC' : glowCol;
        ctx.lineWidth = Math.max(1, 1.5 * (cw / 800));
        for (let ring = -2; ring <= 2; ring++) {
          const rad = Math.cos((ring / 2.5) * (Math.PI / 2)) * 32;
          const ry = canopyY + ring * 10;
          ctx.beginPath();
          for (let a = 0; a <= Math.PI * 2 + 0.1; a += Math.PI / 8) {
            const pt = project(Math.cos(a) * rad, ry, Math.sin(a) * rad);
            if (a === 0) ctx.moveTo(pt.x, pt.y);
            else ctx.lineTo(pt.x, pt.y);
          }
          ctx.stroke();
        }

        const b1Ang = time * 0.6;
        const b1 = project(Math.cos(b1Ang) * 46, canopyY + 5, Math.sin(b1Ang) * 46);
        ctx.fillStyle = '#38BDF8';
        ctx.beginPath();
        ctx.arc(b1.x, b1.y, Math.max(3, 7 * b1.scale), 0, Math.PI * 2);
        ctx.fill();

        const b2Ang = b1Ang + Math.PI;
        const b2 = project(Math.cos(b2Ang) * 46, canopyY - 5, Math.sin(b2Ang) * 46);
        ctx.fillStyle = '#C084FC';
        ctx.beginPath();
        ctx.arc(b2.x, b2.y, Math.max(3, 7 * b2.scale), 0, Math.PI * 2);
        ctx.fill();

        // 5. Strata 3: Apex Spire & Crown Ring
        const apexY = 95 * factor;
        const pApexTop = project(0, apexY + 35, 0);
        ctx.strokeStyle = primaryCol;
        ctx.lineWidth = Math.max(1.5, 2.5 * (cw / 800));
        for (let i = 0; i < 4; i++) {
          const ang = (i / 4) * Math.PI * 2 + time * 0.3;
          const pBase = project(Math.cos(ang) * 14, apexY, Math.sin(ang) * 14);
          ctx.beginPath();
          ctx.moveTo(pBase.x, pBase.y);
          ctx.lineTo(pApexTop.x, pApexTop.y);
          ctx.stroke();
        }

        ctx.strokeStyle = '#FFE066';
        ctx.lineWidth = Math.max(1, 2 * (cw / 800));
        ctx.beginPath();
        for (let a = 0; a <= Math.PI * 2 + 0.1; a += Math.PI / 10) {
          const pt = project(Math.cos(a) * 20, apexY + 12, Math.sin(a) * 20);
          if (a === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.stroke();

        ctx.fillStyle = '#FFF5C0';
        ctx.beginPath();
        ctx.arc(pApexTop.x, pApexTop.y, Math.max(3, 6 * pApexTop.scale), 0, Math.PI * 2);
        ctx.fill();
      };
      render25D();

      cleanupFn = () => {
        if (animId) cancelAnimationFrame(animId);
        resizeObserver.disconnect();
        container.removeEventListener('mousedown', onMouseDown);
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
        container.replaceChildren();
      };
    }

    return () => {
      if (cleanupFn) cleanupFn();
    };
  }, []);

  // Update wireframe mode dynamically across all meshes (when WebGL active)
  useEffect(() => {
    if (!modelGroupRef.current) return;
    modelGroupRef.current.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach((m) => (m.wireframe = wireframeMode));
        } else {
          child.material.wireframe = wireframeMode;
        }
      }
    });
  }, [wireframeMode]);

  // Update explode layer spacing (when WebGL active)
  useEffect(() => {
    const layers = strataLayersRef.current;
    if (layers.length < 4) return;
    const factor = explodeValue / 20; // 1.0 is default
    layers[0].position.y = -20 * factor;
    layers[1].position.y = -5 * factor;
    layers[2].position.y = 12 * factor;
    layers[3].position.y = 28 * factor;
  }, [explodeValue]);

  // Update lighting palette dynamically (when WebGL active)
  useEffect(() => {
    if (!dirLightRef.current || !rimLightRef.current) return;
    if (activeLighting === 'luxora') {
      dirLightRef.current.color.setHex(0xd4af37);
      rimLightRef.current.color.setHex(0x00e5ff);
    } else if (activeLighting === 'cyber') {
      dirLightRef.current.color.setHex(0x00e5ff);
      rimLightRef.current.color.setHex(0x39ff14);
    } else if (activeLighting === 'purple') {
      dirLightRef.current.color.setHex(0xc084fc);
      rimLightRef.current.color.setHex(0xd946ef);
    } else {
      dirLightRef.current.color.setHex(0xffffff);
      rimLightRef.current.color.setHex(0xe2e8f0);
    }
  }, [activeLighting]);

  // Set camera angle or 2.5D focus to specific strata
  const handleSelectStrata = (preset: 'apex' | 'canopy' | 'trunk' | 'roots') => {
    audioEngine.playClick();
    setActiveStrataPreset(preset);

    if (preset === 'apex') {
      targetStrataYRef.current = 65;
      if (cameraRef.current) {
        cameraRef.current.position.set(0, 38, 75);
        cameraRef.current.lookAt(0, 24, 0);
      }
      setSelectedNodeTelemetry({
        strata: 'Apex Memcastle',
        altitude: '+4500m',
        protocol: 'Port 6379 // Zero-Trust Redis Gateway',
        activeNodes: 64,
        status: 'SECURE_SAT'
      });
    } else if (preset === 'canopy') {
      targetStrataYRef.current = 25;
      if (cameraRef.current) {
        cameraRef.current.position.set(0, 20, 80);
        cameraRef.current.lookAt(0, 10, 0);
      }
      setSelectedNodeTelemetry({
        strata: 'Cognitive Canopy & Twin Brains',
        altitude: '+2800m',
        protocol: 'Open-Notebook (8502) ⟷ NotebookLM Sink',
        activeNodes: 128,
        status: 'SYNCED_DMA'
      });
    } else if (preset === 'trunk') {
      targetStrataYRef.current = -5;
      if (cameraRef.current) {
        cameraRef.current.position.set(0, 2, 85);
        cameraRef.current.lookAt(0, -5, 0);
      }
      setSelectedNodeTelemetry({
        strata: 'Axis Trunk & Ouroboros SSM',
        altitude: '+1200m',
        protocol: '1.58-Bit Ternary Recurrent Loop W_ij',
        activeNodes: 86,
        status: 'TERNARY_LOCKED'
      });
    } else {
      targetStrataYRef.current = -45;
      if (cameraRef.current) {
        cameraRef.current.position.set(0, -18, 75);
        cameraRef.current.lookAt(0, -20, 0);
      }
      setSelectedNodeTelemetry({
        strata: 'VFS Ancient Roots & Viking Refractions',
        altitude: '+0000m',
        protocol: '/vfs/refractions/* DMA Ring Buffers',
        activeNodes: 70,
        status: 'DMA_ACTIVE'
      });
    }
  };

  // Play Solfeggio Harmonic frequency tone
  const handlePlaySolfeggio = (freq: number) => {
    setSolfeggioFreq(freq);
    if (soundActive) {
      audioEngine.playSecretHarmonic(freq);
    }
  };

  return (
    <div className="w-full min-h-screen bg-[#050505] text-slate-100 flex flex-col selection:bg-[#D4AF37] selection:text-black">
      {/* Top Banner: Video Architectural Synthesis Tag */}
      <div className="w-full bg-gradient-to-r from-black via-[#120824] to-black border-b border-[#D4AF37]/30 px-4 py-2 flex items-center justify-between flex-wrap gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-[#D4AF37]/20 border border-[#D4AF37]/50 text-[#D4AF37] font-bold font-mono text-[10px] tracking-wider flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> GEMINI 3.8 FLASH ARCHITECTURE
          </span>
          <span className="text-slate-400 hidden md:inline">
            Interactive 3D Website Implementation // Inspired by Antigravity & DeepMind Tutorial
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setShowUiOverlayDemo(true);
              audioEngine.playClick();
            }}
            className="px-2.5 py-1 rounded bg-purple-950/80 hover:bg-purple-900 border border-purple-500/60 text-purple-300 text-[10px] font-mono font-bold flex items-center gap-1 transition-all cursor-pointer shadow-[0_0_10px_rgba(168,85,247,0.3)]"
          >
            <Layers className="w-3 h-3 text-purple-400" /> 3D CANVAS + OVERLAY
          </button>

          {/* Quick Jump back to 2D ➔ 3D HUD or 7 Pics Deck */}
          {onSwitchContinuityView && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => onSwitchContinuityView('hud')}
                className="px-2 py-1 rounded bg-black/60 hover:bg-black border border-cyan-500/40 text-cyan-300 text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer"
              >
                <TreeDeciduous className="w-3 h-3 text-cyan-400" /> 2D ➔ 3D HUD
              </button>
              <button
                onClick={() => onSwitchContinuityView('scroller')}
                className="px-2 py-1 rounded bg-black/60 hover:bg-black border border-[#D4AF37]/40 text-[#D4AF37] text-[10px] font-mono flex items-center gap-1 transition-all cursor-pointer"
              >
                <Layers className="w-3 h-3 text-[#D4AF37]" /> 7 PICS SCROLL
              </button>
            </div>
          )}

          {/* Sound Mute/Unmute */}
          <button
            onClick={() => {
              setSoundActive(!soundActive);
              audioEngine.setEnabled(!soundActive);
            }}
            className="p-1 rounded bg-slate-900 border border-slate-700 text-slate-400 hover:text-white transition-all cursor-pointer"
            title={soundActive ? 'Mute Audio' : 'Enable Audio'}
          >
            {soundActive ? <Volume2 className="w-3.5 h-3.5 text-[#D4AF37]" /> : <VolumeX className="w-3.5 h-3.5 text-slate-500" />}
          </button>
        </div>
      </div>

      {/* =========================================================================
          HERO SECTION: CINEMATIC 3D AXIS MUNDI WITH ORTHOGRAPHIC Z-INDEX SANDWICH
          ========================================================================= */}
      <section className="relative w-full min-h-[640px] lg:min-h-[720px] flex items-center justify-center overflow-hidden px-4 py-12">
        {/* Layer 0: Background Deep Atmosphere & Radial Gradient */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(46,8,84,0.35)_0%,rgba(5,5,5,0.95)_70%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_0%,rgba(5,5,5,0.9)_95%)] pointer-events-none" />

        {/* Layer 0: Massive Typographic Parallax Watermark (Underneath 3D Canvas) */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none select-none z-0 opacity-15">
          <h1 className="text-[12vw] font-black tracking-tighter font-heraldic text-transparent bg-clip-text bg-gradient-to-b from-[#D4AF37] via-white to-transparent leading-none">
            AXIS MUNDI
          </h1>
          <p className="text-xl md:text-3xl font-mono text-[#D4AF37] tracking-[0.4em] mt-2">
            WORLD TREE // 3D SPATIAL COMPUTATION
          </p>
        </div>

        {/* Layer 1: Interactive 3D Model Stage Canvas (Transparent WebGL Viewport) */}
        <div 
          ref={mountRef} 
          className="absolute inset-0 z-10 w-full h-full cursor-grab active:cursor-grabbing"
          title="Click and drag to rotate the 3D Axis Mundi Model"
        />

        {/* Layer 2: Foreground HUD Controls & Typography (Z-Index Layering Sandwich) */}
        <div className="relative z-20 max-w-6xl w-full pointer-events-none flex flex-col justify-between min-h-[540px]">
          {/* Top Title & Mission Badge */}
          <div className="flex flex-col items-center text-center space-y-3 pointer-events-auto">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-black/80 border border-[#D4AF37]/60 shadow-[0_0_20px_rgba(212,175,55,0.3)]">
              <span className={`w-2 h-2 rounded-full ${hasWebGL ? 'bg-emerald-400 animate-ping' : 'bg-cyan-400 animate-pulse'}`} />
              <span className="text-[11px] font-mono font-bold text-[#D4AF37] tracking-widest uppercase">
                {hasWebGL ? 'Interactive 3D Web Engine • Gemini 3.8 Flash' : 'Kinetic 2.5D Spatial Engine • Zero-WebGL Edge Mode'}
              </span>
            </div>

            <h2 className="text-3xl sm:text-5xl lg:text-6xl font-black font-heraldic tracking-tight text-white drop-shadow-[0_4px_24px_rgba(0,0,0,0.9)]">
              Hyper-Spatial <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#D4AF37] via-amber-200 to-[#D4AF37]">World Tree</span>
            </h2>

            <p className="max-w-2xl text-xs sm:text-sm text-slate-300 font-sans leading-relaxed drop-shadow-md">
              A sovereign, cinematic spatial interface demonstrating <span className="text-[#D4AF37] font-semibold">interactive 3D model manipulation</span>, 
              <span className="text-cyan-400 font-semibold"> dual-direction infinite marquee carousels</span>, and 
              <span className="text-purple-400 font-semibold"> responsive bento grid telemetry</span> confined strictly within 8GB RAM & &lt;50MB VRAM limits.
            </p>
          </div>

          {/* Center-Right Quick Floating 3D Controls */}
          <div className="flex items-center justify-between w-full pointer-events-auto mt-auto pt-8 flex-wrap gap-4">
            {/* Left: Strata Camera Presets */}
            <div className="flex items-center gap-1.5 bg-black/85 backdrop-blur-md p-1.5 rounded-2xl border border-slate-800 shadow-2xl">
              <span className="text-[10px] font-mono text-slate-400 px-2 font-bold flex items-center gap-1">
                <Compass className="w-3.5 h-3.5 text-[#D4AF37]" /> STRATA:
              </span>
              {(['apex', 'canopy', 'trunk', 'roots'] as const).map((preset) => (
                <button
                  key={preset}
                  onClick={() => handleSelectStrata(preset)}
                  className={`px-3 py-1 rounded-xl text-[10px] font-mono font-bold capitalize transition-all cursor-pointer ${
                    activeStrataPreset === preset
                      ? 'bg-gradient-to-r from-[#D4AF37] to-amber-500 text-black shadow-[0_0_12px_rgba(212,175,55,0.5)]'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>

            {/* Right: 3D Stage Tooling (Rotate, Wireframe, Lighting, Explode) */}
            <div className="flex items-center gap-2 bg-black/85 backdrop-blur-md p-1.5 rounded-2xl border border-slate-800 shadow-2xl flex-wrap">
              {/* Auto-Rotation Toggle */}
              <button
                onClick={() => {
                  setIsRotating(!isRotating);
                  audioEngine.playClick();
                }}
                className={`px-3 py-1.5 rounded-xl text-[10px] font-mono font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                  isRotating 
                    ? 'bg-cyan-950 border border-cyan-500/60 text-cyan-300' 
                    : 'bg-slate-900 border border-slate-700 text-slate-400'
                }`}
                title="Toggle Automated 3D Rotation"
              >
                {isRotating ? <Pause className="w-3 h-3 text-cyan-400" /> : <Play className="w-3 h-3 text-slate-400" />}
                <span>{isRotating ? 'ROTATE: ON' : 'PAUSED'}</span>
              </button>

              {/* Wireframe Mode Toggle */}
              <button
                onClick={() => {
                  setWireframeMode(!wireframeMode);
                  audioEngine.playClick();
                }}
                className={`px-3 py-1.5 rounded-xl text-[10px] font-mono font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                  wireframeMode 
                    ? 'bg-amber-950 border border-amber-500 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.4)]' 
                    : 'bg-slate-900 border border-slate-700 text-slate-400 hover:text-white'
                }`}
                title="Toggle Wireframe Mesh Rendering"
              >
                <Box className="w-3 h-3" />
                <span>WIREFRAME: {wireframeMode ? 'ON' : 'OFF'}</span>
              </button>

              {/* Lighting Preset Selector */}
              <div className="flex items-center gap-1 border-l border-slate-800 pl-2">
                <span className="text-[9px] font-mono text-slate-500">LIGHT:</span>
                {(['luxora', 'cyber', 'purple', 'studio'] as const).map((l) => (
                  <button
                    key={l}
                    onClick={() => {
                      setActiveLighting(l);
                      audioEngine.playClick();
                    }}
                    className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase transition-all cursor-pointer ${
                      activeLighting === l
                        ? 'bg-[#D4AF37] text-black'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {l[0]}
                  </button>
                ))}
              </div>

              {/* Explode Layers Slider */}
              <div className="flex items-center gap-1.5 border-l border-slate-800 pl-2">
                <span className="text-[9px] font-mono text-slate-500">EXPLODE:</span>
                <input
                  type="range"
                  min="10"
                  max="45"
                  value={explodeValue}
                  onChange={(e) => setExplodeValue(Number(e.target.value))}
                  className="w-16 accent-[#D4AF37] cursor-pointer"
                  title="Explode/Contract 3D Strata Distance"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Selected Node Telemetry Banner (If preset is clicked) */}
      {selectedNodeTelemetry && (
        <div className="max-w-6xl mx-auto w-full px-4 -mt-4 mb-4">
          <div className="bg-black/90 border border-[#D4AF37]/50 rounded-2xl p-3 flex items-center justify-between flex-wrap gap-3 shadow-[0_0_20px_rgba(212,175,55,0.2)] animate-fadeIn">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#D4AF37]/10 border border-[#D4AF37]/40 flex items-center justify-center text-[#D4AF37] font-bold">
                ⚜️
              </div>
              <div>
                <h4 className="text-xs font-bold text-white font-heraldic">{selectedNodeTelemetry.strata}</h4>
                <p className="text-[10px] font-mono text-slate-400">{selectedNodeTelemetry.protocol}</p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-[10px] font-mono">
              <span className="text-slate-400">ALTITUDE: <strong className="text-[#D4AF37]">{selectedNodeTelemetry.altitude}</strong></span>
              <span className="text-slate-400">NODES: <strong className="text-cyan-400">{selectedNodeTelemetry.activeNodes}</strong></span>
              <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/40 font-bold">
                {selectedNodeTelemetry.status}
              </span>
              <button
                onClick={() => setSelectedNodeTelemetry(null)}
                className="text-slate-500 hover:text-white ml-2 text-xs"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TWO-ROW INFINITE LOGO & TECH MARQUEE CAROUSEL
          Direct implementation of the video's marquee component
          ========================================================================= */}
      <section className="w-full py-10 bg-gradient-to-b from-[#050505] via-[#090810] to-[#050505] border-y border-slate-800/80 overflow-hidden relative">
        <div className="max-w-6xl mx-auto px-4 mb-6 flex items-center justify-between">
          <div>
            <div className="inline-flex items-center gap-1.5 text-[10px] font-mono text-[#D4AF37] font-bold uppercase tracking-wider">
              <Sparkles className="w-3 h-3" /> Autonomous Ecosystem
            </div>
            <h3 className="text-xl sm:text-2xl font-bold font-heraldic text-white">
              Sovereign Technology Lattice
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400 hidden sm:inline">
            Hover cards to pause infinite stream
          </span>
        </div>

        {/* Marquee Row 1: Leftward Infinite Drift */}
        <div className="relative w-full overflow-hidden mb-3">
          <div className="animate-marquee-left flex gap-3 py-1">
            {/* Double the array for smooth seamless loop */}
            {[...CAROUSEL_ROW_1, ...CAROUSEL_ROW_1].map((tech, idx) => (
              <div
                key={`r1-${tech.id}-${idx}`}
                onClick={() => {
                  audioEngine.playHoverBeep();
                  handlePlaySolfeggio(528);
                }}
                className="min-w-[260px] max-w-[280px] bg-[#0c0d16]/90 hover:bg-[#151624] border border-slate-800 hover:border-[#D4AF37]/60 rounded-xl p-3 flex items-center gap-3 transition-all cursor-pointer group shadow-lg"
                style={{
                  boxShadow: `0 0 15px ${tech.glow}`
                }}
              >
                <div className="w-10 h-10 rounded-xl bg-black/60 border border-slate-700 group-hover:border-[#D4AF37] flex items-center justify-center text-xl shrink-0 transition-transform group-hover:scale-110">
                  {tech.icon}
                </div>
                <div className="overflow-hidden">
                  <div className="flex items-center justify-between gap-1">
                    <h5 className="text-xs font-bold text-white truncate group-hover:text-[#D4AF37] transition-colors">
                      {tech.name}
                    </h5>
                    <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 shrink-0">
                      {tech.badge}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-sans truncate mt-0.5">
                    {tech.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Marquee Row 2: Rightward Infinite Drift */}
        <div className="relative w-full overflow-hidden">
          <div className="animate-marquee-right flex gap-3 py-1">
            {[...CAROUSEL_ROW_2, ...CAROUSEL_ROW_2].map((tech, idx) => (
              <div
                key={`r2-${tech.id}-${idx}`}
                onClick={() => {
                  audioEngine.playHoverBeep();
                  handlePlaySolfeggio(639);
                }}
                className="min-w-[260px] max-w-[280px] bg-[#0c0d16]/90 hover:bg-[#151624] border border-slate-800 hover:border-cyan-400/60 rounded-xl p-3 flex items-center gap-3 transition-all cursor-pointer group shadow-lg"
                style={{
                  boxShadow: `0 0 15px ${tech.glow}`
                }}
              >
                <div className="w-10 h-10 rounded-xl bg-black/60 border border-slate-700 group-hover:border-cyan-400 flex items-center justify-center text-xl shrink-0 transition-transform group-hover:scale-110">
                  {tech.icon}
                </div>
                <div className="overflow-hidden">
                  <div className="flex items-center justify-between gap-1">
                    <h5 className="text-xs font-bold text-white truncate group-hover:text-cyan-300 transition-colors">
                      {tech.name}
                    </h5>
                    <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-cyan-300 shrink-0">
                      {tech.badge}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-sans truncate mt-0.5">
                    {tech.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* =========================================================================
          MODERN BENTO GRID ARCHITECTURE (Highlight from Video)
          ========================================================================= */}
      <section className="max-w-6xl mx-auto w-full px-4 py-16">
        <div className="text-center space-y-2 mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#D4AF37]/10 border border-[#D4AF37]/40 text-[#D4AF37] text-xs font-mono font-bold uppercase">
            <Layers className="w-3.5 h-3.5" /> High-Performance Bento Scaffolding
          </div>
          <h2 className="text-2xl sm:text-4xl font-black font-heraldic text-white">
            Engineered Modularity & Telemetry
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto">
            Zero-allocation cards orchestrating 3D visual rendering, edge memory limits, and real-time audio harmonics.
          </p>
        </div>

        {/* Bento Grid Container */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 auto-rows-[220px]">
          {/* Card 1: 3D Model Mesh Inspector (Spans 2 cols, 2 rows) */}
          <div className="md:col-span-2 md:row-span-2 bg-[#090b14]/90 border border-slate-800 hover:border-[#D4AF37]/60 rounded-3xl p-6 flex flex-col justify-between relative overflow-hidden group shadow-xl transition-all">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#D4AF37]/5 rounded-full blur-3xl pointer-events-none" />
            
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#D4AF37]/20 border border-[#D4AF37]/50 text-[#D4AF37]">
                  SPATIAL MESH CORE
                </span>
                <span className="text-xs font-mono text-slate-500">
                  LOD MODE: {isLODActive ? 'AUTOMATIC (>300 NODES)' : 'NOMINAL'}
                </span>
              </div>
              <h3 className="text-xl font-bold font-heraldic text-white group-hover:text-[#D4AF37] transition-colors">
                Axis Mundi Procedural Topology
              </h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Rendered with zero-copy vertex passes. Geometry automatically simplifies sphere segments and disables halos/labels when density surpasses 300 nodes.
              </p>
            </div>

            {/* Live Mesh Stats */}
            <div className="grid grid-cols-3 gap-3 my-4">
              <div className="bg-black/60 border border-slate-800 rounded-xl p-3 text-center">
                <span className="text-[10px] font-mono text-slate-500 block">TRIANGLES</span>
                <span className="text-base font-mono font-bold text-white">4,820</span>
              </div>
              <div className="bg-black/60 border border-slate-800 rounded-xl p-3 text-center">
                <span className="text-[10px] font-mono text-slate-500 block">CLIENT VRAM</span>
                <span className="text-base font-mono font-bold text-emerald-400">&lt;28 MB</span>
              </div>
              <div className="bg-black/60 border border-slate-800 rounded-xl p-3 text-center">
                <span className="text-[10px] font-mono text-slate-500 block">FRAME RATE</span>
                <span className="text-base font-mono font-bold text-cyan-400">60.0 FPS</span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-800">
              <span className="text-slate-400 font-mono">Status: <strong className={hasWebGL ? "text-emerald-400" : "text-amber-400"}>{hasWebGL ? "WebGL 2.0 Native" : "2.5D Canvas (Sandboxed)"}</strong></span>
              <button
                onClick={() => {
                  setWireframeMode(!wireframeMode);
                  audioEngine.playClick();
                }}
                className="px-3 py-1 rounded-lg bg-black hover:bg-[#D4AF37]/20 border border-slate-700 hover:border-[#D4AF37] text-white text-[11px] font-mono font-bold transition-all cursor-pointer"
              >
                Toggle Wireframe
              </button>
            </div>
          </div>

          {/* Card 2: Level-of-Detail (LOD) Performance System */}
          <div className="bg-[#090b14]/90 border border-slate-800 hover:border-cyan-400/60 rounded-3xl p-5 flex flex-col justify-between relative overflow-hidden group shadow-xl transition-all">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-cyan-400 font-bold flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> LOD ENGINE
              </span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </div>

            <div>
              <h4 className="text-sm font-bold font-heraldic text-white">Density Threshold</h4>
              <p className="text-[11px] text-slate-400 mt-1">
                Halos and HTML labels are suppressed when node count exceeds 300.
              </p>
            </div>

            {/* Density Meter */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-[10px] font-mono text-slate-400">
                <span>Active Nodes: {simulatedNodes}</span>
                <span className="text-amber-400 font-bold">LOD ACTIVE</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div className="h-full bg-gradient-to-r from-cyan-500 to-amber-500 w-[78%]" />
              </div>
              <span className="text-[9px] font-mono text-slate-500 block">Threshold: 300 nodes</span>
            </div>
          </div>

          {/* Card 3: 8GB Scarcity Protocol & Respiration Barometer */}
          <div className="bg-[#090b14]/90 border border-slate-800 hover:border-amber-400/60 rounded-3xl p-5 flex flex-col justify-between relative overflow-hidden group shadow-xl transition-all">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-amber-400 font-bold flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5" /> 8GB BOUNDARY
              </span>
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-950 text-amber-300">
                SCARCITY
              </span>
            </div>

            <div>
              <h4 className="text-sm font-bold font-heraldic text-white">Respiration Pulse</h4>
              <p className="text-[11px] text-slate-400 mt-1">
                Breathing cycle rhythm dynamically adapts to host memory pressure.
              </p>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-mono">
                <span className="text-slate-400">RAM Pressure</span>
                <span className="text-white font-bold">{ramUtilization.toFixed(1)}% (4.89 GB)</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-emerald-500 via-amber-500 to-red-500"
                  style={{ width: `${ramUtilization}%` }}
                />
              </div>
              <span className="text-[9px] font-mono text-slate-500 block">Edge cap: 8,192 MB</span>
            </div>
          </div>

          {/* Card 4: Solfeggio Harmonic Synthesizer */}
          <div className="bg-[#090b14]/90 border border-slate-800 hover:border-[#D4AF37]/60 rounded-3xl p-5 flex flex-col justify-between relative overflow-hidden group shadow-xl transition-all">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-[#D4AF37] font-bold flex items-center gap-1">
                <Flame className="w-3.5 h-3.5" /> SOLFEGGIO TUNER
              </span>
              <span className="text-[9px] font-mono text-cyan-300 font-bold">{solfeggioFreq} Hz</span>
            </div>

            <div>
              <h4 className="text-sm font-bold font-heraldic text-white">Axis Mundi Harmonics</h4>
              <p className="text-[11px] text-slate-400 mt-1">
                Procedural audio synthesis based on golden ratio frequencies.
              </p>
            </div>

            {/* Quick Frequency Buttons */}
            <div className="grid grid-cols-3 gap-1.5">
              {[432, 528, 639].map((freq) => (
                <button
                  key={freq}
                  onClick={() => handlePlaySolfeggio(freq)}
                  className={`py-1 rounded-lg text-[10px] font-mono font-bold border transition-all cursor-pointer ${
                    solfeggioFreq === freq
                      ? 'bg-[#D4AF37] text-black border-[#D4AF37]'
                      : 'bg-black/60 border-slate-800 text-slate-300 hover:text-white'
                  }`}
                >
                  {freq}Hz
                </button>
              ))}
            </div>
          </div>

          {/* Card 5: Kinetic Z-Index Sandwiches (Sir Hydron & Sir Stitch) */}
          <div className="bg-[#090b14]/90 border border-slate-800 hover:border-purple-400/60 rounded-3xl p-5 flex flex-col justify-between relative overflow-hidden group shadow-xl transition-all">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-purple-400 font-bold flex items-center gap-1">
                <Binary className="w-3.5 h-3.5" /> Z-INDEX ARCHITECTURE
              </span>
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple-950 text-purple-300">
                0.00 CLS
              </span>
            </div>

            <div>
              <h4 className="text-sm font-bold font-heraldic text-white">DOM Sandwich Layers</h4>
              <p className="text-[11px] text-slate-400 mt-1">
                L0 DOM Typography ➔ L1 Spatial Canvas ➔ L2 Foreground HUD Controls.
              </p>
            </div>

            <div className="text-[10px] font-mono space-y-1 bg-black/60 p-2 rounded-xl border border-slate-800">
              <div className="text-slate-400">L0: Typography (z-1)</div>
              <div className="text-[#D4AF37]">L1: 3D Canvas (z-10, pointer:none)</div>
              <div className="text-cyan-300">L2: Active Controls (z-20)</div>
            </div>

            <button
              onClick={() => {
                setShowUiOverlayDemo(true);
                audioEngine.playClick();
              }}
              className="w-full py-1.5 rounded-xl bg-purple-950/80 hover:bg-purple-900 border border-purple-500/60 text-purple-300 text-[10px] font-mono font-bold transition-all cursor-pointer shadow-[0_0_10px_rgba(168,85,247,0.3)] mt-2"
            >
              Launch Fixed Canvas Overlay Demo
            </button>
          </div>
        </div>
      </section>

      {/* Fixed Three.js Canvas + Overlay UI Modal Viewport */}
      {showUiOverlayDemo && (
        <div className="fixed inset-0 z-[200] bg-black">
          <FixedThreeUiOverlay onClose={() => setShowUiOverlayDemo(false)} />
        </div>
      )}

      {/* =========================================================================
          BOTTOM DOCK & NAVIGATION
          ========================================================================= */}
      <footer className="w-full bg-black/95 border-t border-slate-800/80 px-4 py-6 mt-auto">
        <div className="max-w-6xl mx-auto flex items-center justify-between flex-wrap gap-4 text-xs font-mono text-slate-400">
          <div className="flex items-center gap-2">
            <span className="text-[#D4AF37] font-bold font-heraldic">WORLD TREE 3D</span>
            <span>• Gemini 3.8 Flash Spatial Showcase</span>
          </div>

          <div className="flex items-center gap-3">
            {onNavigateTab && (
              <>
                <button
                  onClick={() => onNavigateTab('deck')}
                  className="hover:text-white transition-colors cursor-pointer"
                >
                  World Tree Deck
                </button>
                <button
                  onClick={() => onNavigateTab('bento')}
                  className="hover:text-white transition-colors cursor-pointer"
                >
                  Bento Grid Hub
                </button>
                <button
                  onClick={() => onNavigateTab('operator')}
                  className="hover:text-white transition-colors cursor-pointer"
                >
                  HTMX Operator Console
                </button>
              </>
            )}
            <span className="text-slate-600">|</span>
            <span className="text-emerald-400">⚜️ SOVEREIGN TRUTH</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
