import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface ThreeWorldTreeSceneProps {
  onHotspotClick?: (zone: string) => void;
  energyPulseTrigger?: number; // increments on trigger
  depthLayer?: number; // from Graphify slider
}

export const ThreeWorldTreeScene: React.FC<ThreeWorldTreeSceneProps> = ({
  onHotspotClick,
  energyPulseTrigger = 0,
  depthLayer = 5
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mouseRef = useRef<{ x: number; y: number; targetX: number; targetY: number }>({
    x: 0,
    y: 0,
    targetX: 0,
    targetY: 0
  });

  const shockwavesRef = useRef<{ mesh: THREE.Mesh; scale: number; opacity: number }[]>([]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    // 1. Scene & Camera setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 100);

    // 2. WebGL Renderer with transparency
    let renderer: THREE.WebGLRenderer;
    const originalError = console.error;
    const originalWarn = console.warn;
    try {
      // Temporarily suppress console.error and console.warn to avoid triggering error overlays for WebGL fallback
      console.error = () => {};
      console.warn = () => {};
      
      const canvas = document.createElement('canvas');
      canvas.addEventListener('webglcontextcreationerror', (e) => {
        e.preventDefault();
      }, false);
      
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      
      if (!gl) {
        throw new Error('WebGL not supported');
      }
      
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, canvas });
      
      // Restore console methods
      console.error = originalError;
      console.warn = originalWarn;
    } catch (e) {
      // Restore console methods
      console.error = originalError;
      console.warn = originalWarn;
      console.log("WebGL is not supported or context could not be created in this environment. Proceeding without 3D background.");
      return;
    }
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // 3. Ambient & Directional Lights
    const ambientLight = new THREE.AmbientLight(0x1e3a8a, 1.5);
    scene.add(ambientLight);

    const goldPointLight = new THREE.PointLight(0xfbbf24, 2.5, 120);
    goldPointLight.position.set(0, 0, 30);
    scene.add(goldPointLight);

    const cyanPointLight = new THREE.PointLight(0x22d3ee, 2.0, 100);
    cyanPointLight.position.set(25, 10, 20);
    scene.add(cyanPointLight);

    const purplePointLight = new THREE.PointLight(0xa855f7, 2.0, 100);
    purplePointLight.position.set(-25, 10, 20);
    scene.add(purplePointLight);

    // 4. 3D Particle Cloud (Bioluminescent Spores)
    const particleCount = 180;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const velocities: { vx: number; vy: number; vz: number; radius: number; angle: number; speed: number; yBase: number }[] = [];

    const palette = [
      new THREE.Color('#22d3ee'),
      new THREE.Color('#34d399'),
      new THREE.Color('#fbbf24'),
      new THREE.Color('#c084fc'),
      new THREE.Color('#38bdf8'),
      new THREE.Color('#f59e0b')
    ];

    for (let i = 0; i < particleCount; i++) {
      const radius = 10 + Math.random() * 45;
      const angle = Math.random() * Math.PI * 2;
      const yBase = (Math.random() - 0.45) * 60;
      
      positions[i * 3] = Math.cos(angle) * radius;
      positions[i * 3 + 1] = yBase;
      positions[i * 3 + 2] = Math.sin(angle) * radius * 0.4;

      const col = palette[Math.floor(Math.random() * palette.length)];
      colors[i * 3] = col.r;
      colors[i * 3 + 1] = col.g;
      colors[i * 3 + 2] = col.b;

      velocities.push({
        vx: (Math.random() - 0.5) * 0.05,
        vy: 0.04 + Math.random() * 0.08,
        vz: (Math.random() - 0.5) * 0.05,
        radius,
        angle,
        speed: (Math.random() * 0.008 + 0.003) * (Math.random() > 0.5 ? 1 : -1),
        yBase
      });
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Particle Material with Soft Circular Point Texture
    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d')!;
    const grad = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.3, 'rgba(255, 255, 255, 0.8)');
    grad.addColorStop(0.7, 'rgba(255, 255, 255, 0.2)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 32, 32);

    const pointTexture = new THREE.CanvasTexture(canvas);

    const particleMat = new THREE.PointsMaterial({
      size: 2.2,
      vertexColors: true,
      map: pointTexture,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    const particleSystem = new THREE.Points(particleGeo, particleMat);
    scene.add(particleSystem);

    // 4.5 Holographic Grid Floor
    const gridHelper = new THREE.GridHelper(200, 100, 0x22d3ee, 0x0891b2);
    gridHelper.position.set(0, -45, 0);
    gridHelper.material.transparent = true;
    gridHelper.material.opacity = 0.25;
    gridHelper.material.blending = THREE.AdditiveBlending;
    scene.add(gridHelper);

    // 5. 3D Coiled Ouroboros Golden Serpent Torus
    const ouroborosGroup = new THREE.Group();
    const torusGeo = new THREE.TorusGeometry(12, 0.8, 16, 64);
    const torusMat = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      emissive: 0xd97706,
      emissiveIntensity: 0.4,
      metalness: 0.9,
      roughness: 0.2,
      wireframe: false
    });
    const ouroborosTorus = new THREE.Mesh(torusGeo, torusMat);
    ouroborosTorus.rotation.x = Math.PI * 0.45;
    ouroborosGroup.add(ouroborosTorus);

    // Inner wireframe energy cage
    const cageGeo = new THREE.TorusGeometry(12.4, 0.9, 8, 32);
    const cageMat = new THREE.MeshBasicMaterial({
      color: 0xfef08a,
      wireframe: true,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending
    });
    const ouroborosCage = new THREE.Mesh(cageGeo, cageMat);
    ouroborosCage.rotation.x = Math.PI * 0.45;
    ouroborosGroup.add(ouroborosCage);

    ouroborosGroup.position.set(0, 0, 5);
    scene.add(ouroborosGroup);

    // 6. 3D Glowing Synaptic Brain Spheres (Left & Right)
    // Left Brain Sphere
    const leftBrainGroup = new THREE.Group();
    const brainGeo = new THREE.IcosahedronGeometry(7, 2);
    const leftBrainMat = new THREE.MeshBasicMaterial({
      color: 0xc084fc,
      wireframe: true,
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending
    });
    const leftBrainMesh = new THREE.Mesh(brainGeo, leftBrainMat);
    leftBrainGroup.add(leftBrainMesh);
    leftBrainGroup.position.set(-36, 1, 0);
    scene.add(leftBrainGroup);

    // Right Brain Sphere
    const rightBrainGroup = new THREE.Group();
    const rightBrainMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      wireframe: true,
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending
    });
    const rightBrainMesh = new THREE.Mesh(brainGeo, rightBrainMat);
    rightBrainGroup.add(rightBrainMesh);
    rightBrainGroup.position.set(36, 1, 0);
    scene.add(rightBrainGroup);

    // 7. 3D Glowing Synaptic Conduit Pulses (Traveling Photons)
    const leftCurve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(-36, 1, 0),
      new THREE.Vector3(-18, -10, 10),
      new THREE.Vector3(0, -6, 5)
    );
    const rightCurve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(36, 1, 0),
      new THREE.Vector3(18, -10, 10),
      new THREE.Vector3(0, -6, 5)
    );

    // Visible Conduits
    const leftConduitGeo = new THREE.BufferGeometry().setFromPoints(leftCurve.getPoints(50));
    const leftConduitMat = new THREE.LineBasicMaterial({ color: 0xc084fc, transparent: true, opacity: 0.15, blending: THREE.AdditiveBlending });
    const leftConduit = new THREE.Line(leftConduitGeo, leftConduitMat);
    scene.add(leftConduit);

    const rightConduitGeo = new THREE.BufferGeometry().setFromPoints(rightCurve.getPoints(50));
    const rightConduitMat = new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.15, blending: THREE.AdditiveBlending });
    const rightConduit = new THREE.Line(rightConduitGeo, rightConduitMat);
    scene.add(rightConduit);

    // Left Photon
    const photonGeo = new THREE.SphereGeometry(0.9, 12, 12);
    const leftPhotonMat = new THREE.MeshBasicMaterial({
      color: 0xf472b6,
      blending: THREE.AdditiveBlending
    });
    const leftPhoton = new THREE.Mesh(photonGeo, leftPhotonMat);
    scene.add(leftPhoton);

    // Right Photon
    const rightPhotonMat = new THREE.MeshBasicMaterial({
      color: 0x22d3ee,
      blending: THREE.AdditiveBlending
    });
    const rightPhoton = new THREE.Mesh(photonGeo, rightPhotonMat);
    scene.add(rightPhoton);

    // 8. 3D Floating Viking Drakkar Vessel
    const shipGroup = new THREE.Group();
    
    // 8b. Central Data Spine (Yggdrasil Core)
    const spineGeo = new THREE.CylinderGeometry(2, 2, 160, 12, 30, true);
    const spineMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      wireframe: true,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending
    });
    const dataSpine = new THREE.Mesh(spineGeo, spineMat);
    scene.add(dataSpine);

    const outerSpineGeo = new THREE.CylinderGeometry(5, 5, 160, 16, 20, true);
    const outerSpineMat = new THREE.MeshBasicMaterial({
      color: 0x22d3ee,
      wireframe: true,
      transparent: true,
      opacity: 0.1,
      blending: THREE.AdditiveBlending
    });
    const outerDataSpine = new THREE.Mesh(outerSpineGeo, outerSpineMat);
    scene.add(outerDataSpine);
    
    // Hull
    const hullGeo = new THREE.CylinderGeometry(0.8, 1.4, 8, 8);
    const hullMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      emissive: 0x0369a1,
      metalness: 0.8,
      roughness: 0.3
    });
    const hull = new THREE.Mesh(hullGeo, hullMat);
    hull.rotation.z = Math.PI / 2;
    shipGroup.add(hull);

    // Sail
    const sailGeo = new THREE.PlaneGeometry(5, 5);
    const sailMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      wireframe: true,
      transparent: true,
      opacity: 0.7,
      side: THREE.DoubleSide
    });
    const sail = new THREE.Mesh(sailGeo, sailMat);
    sail.position.set(0, 3, 0);
    shipGroup.add(sail);

    shipGroup.position.set(0, -28, 10);
    shipGroup.scale.set(0.6, 0.6, 0.6);
    scene.add(shipGroup);

    // 9. Resize Handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // 10. Mouse Move Parallax
    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      mouseRef.current.targetX = x * 10;
      mouseRef.current.targetY = y * 6;
    };
    container.addEventListener('mousemove', handleMouseMove);

    // 11. Animation Loop
    let clock = new THREE.Clock();
    let animId: number;

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // Smooth camera interpolation to mouse
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.05;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.05;
      camera.position.x = mouseRef.current.x;
      camera.position.y = mouseRef.current.y;
      camera.lookAt(0, 0, 0);

      // Animate Particles
      const posAttr = particleGeo.attributes.position as THREE.BufferAttribute;
      const posArray = posAttr.array as Float32Array;

      for (let i = 0; i < particleCount; i++) {
        const vel = velocities[i];
        vel.angle += vel.speed;
        vel.yBase += vel.vy;
        if (vel.yBase > 35) vel.yBase = -35;

        posArray[i * 3] = Math.cos(vel.angle) * vel.radius;
        posArray[i * 3 + 1] = vel.yBase + Math.sin(elapsedTime + i) * 1.5;
        posArray[i * 3 + 2] = Math.sin(vel.angle) * vel.radius * 0.5;
      }
      posAttr.needsUpdate = true;

      // Animate Ouroboros Torus
      ouroborosTorus.rotation.z = elapsedTime * 0.3;
      ouroborosCage.rotation.z = -elapsedTime * 0.4;
      ouroborosGroup.position.y = Math.sin(elapsedTime * 0.8) * 1.2;
      const ouroScale = 1 + Math.sin(elapsedTime * 0.5) * 0.03;
      ouroborosGroup.scale.set(ouroScale, ouroScale, ouroScale);

      // Animate Twin Brains
      leftBrainMesh.rotation.y = elapsedTime * 0.4;
      leftBrainMesh.rotation.x = Math.sin(elapsedTime * 0.3) * 0.2;
      leftBrainGroup.position.y = 1 + Math.sin(elapsedTime * 0.9) * 0.8;
      const leftScale = 1 + Math.sin(elapsedTime * 1.5) * 0.05;
      leftBrainGroup.scale.set(leftScale, leftScale, leftScale);

      rightBrainMesh.rotation.y = -elapsedTime * 0.4;
      rightBrainMesh.rotation.x = Math.cos(elapsedTime * 0.3) * 0.2;
      rightBrainGroup.position.y = 1 + Math.cos(elapsedTime * 0.9) * 0.8;
      const rightScale = 1 + Math.cos(elapsedTime * 1.5) * 0.05;
      rightBrainGroup.scale.set(rightScale, rightScale, rightScale);

      // Animate Central Spine
      dataSpine.rotation.y = elapsedTime * -0.05;
      dataSpine.position.y = Math.sin(elapsedTime * 0.2) * 2;
      outerDataSpine.rotation.y = elapsedTime * 0.03;
      outerDataSpine.position.y = Math.sin(elapsedTime * 0.3) * 1.5;

      // Animate Traveling Photons along conduits
      const leftT = (elapsedTime * 0.6) % 1;
      const leftPos = leftCurve.getPoint(leftT);
      leftPhoton.position.copy(leftPos);

      const rightT = (elapsedTime * 0.6 + 0.5) % 1;
      const rightPos = rightCurve.getPoint(rightT);
      rightPhoton.position.copy(rightPos);

      // Animate Drakkar Ship
      shipGroup.position.x = Math.sin(elapsedTime * 0.5) * 8;
      shipGroup.position.y = -28 + Math.sin(elapsedTime * 1.2) * 0.8;
      shipGroup.rotation.z = Math.sin(elapsedTime * 0.8) * 0.08;

      // Animate Shockwaves
      for (let s = shockwavesRef.current.length - 1; s >= 0; s--) {
        const sw = shockwavesRef.current[s];
        sw.scale += 0.04;
        sw.opacity -= 0.015;
        sw.mesh.scale.set(sw.scale, sw.scale, sw.scale);
        (sw.mesh.material as THREE.MeshBasicMaterial).opacity = Math.max(0, sw.opacity);

        if (sw.opacity <= 0) {
          scene.remove(sw.mesh);
          shockwavesRef.current.splice(s, 1);
        }
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      container.removeEventListener('mousemove', handleMouseMove);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  // Spawn Shockwave on energy pulse trigger
  useEffect(() => {
    if (energyPulseTrigger > 0 && containerRef.current) {
      const ringGeo = new THREE.RingGeometry(1, 1.4, 32);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xfacc15,
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.position.set(0, 0, 10);
      shockwavesRef.current.push({
        mesh: ringMesh,
        scale: 1,
        opacity: 0.9
      });
    }
  }, [energyPulseTrigger]);

  return (
    <div 
      ref={containerRef} 
      className="absolute inset-0 w-full h-full pointer-events-none z-10 overflow-hidden"
    />
  );
};
