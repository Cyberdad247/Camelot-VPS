import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';

export class WorldTreeScene {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.scene = new THREE.Scene();
        // Use a very dark purple/black fog for depth
        this.scene.fog = new THREE.FogExp2(0x050505, 0.02);

        this.camera = new THREE.PerspectiveCamera(75, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
        this.camera.position.z = 30;
        this.camera.position.y = 10;
        this.camera.lookAt(0, 0, 0);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        // Ensure transparent background to let the CSS gradient shine through
        this.renderer.setClearColor(0x000000, 0); 
        this.container.innerHTML = ''; // clear placeholder
        this.container.appendChild(this.renderer.domElement);

        this.nodes = [];
        this.initGeometry();
        this.bindEvents();
        this.animate();
    }

    initGeometry() {
        // Core cluster (Sentinel, Bifrost, etc)
        const coreGeo = new THREE.IcosahedronGeometry(2, 1);
        const coreMat = new THREE.MeshBasicMaterial({ color: 0xD4AF37, wireframe: true });
        this.coreNode = new THREE.Mesh(coreGeo, coreMat);
        this.scene.add(this.coreNode);

        // Add some ambient particles representing memories
        const geo = new THREE.BufferGeometry();
        const vertices = [];
        for (let i = 0; i < 500; i++) {
            vertices.push(
                THREE.MathUtils.randFloatSpread(100),
                THREE.MathUtils.randFloatSpread(100),
                THREE.MathUtils.randFloatSpread(100)
            );
        }
        geo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        const mat = new THREE.PointsMaterial({ color: 0x2E0854, size: 0.5 });
        this.particleSystem = new THREE.Points(geo, mat);
        this.scene.add(this.particleSystem);
    }

    addMemoryNode(id) {
        const geo = new THREE.SphereGeometry(0.5, 16, 16);
        const mat = new THREE.MeshBasicMaterial({ color: 0x34d399 }); // Emerald for new memory
        const mesh = new THREE.Mesh(geo, mat);
        
        // Random position around core
        mesh.position.set(
            THREE.MathUtils.randFloatSpread(20),
            THREE.MathUtils.randFloatSpread(20),
            THREE.MathUtils.randFloatSpread(20)
        );
        
        this.scene.add(mesh);
        this.nodes.push({ id, mesh, createdAt: Date.now() });

        // Scroll-linked camera choreo: zoom to new node momentarily
        this.targetCameraPos = mesh.position.clone().add(new THREE.Vector3(0, 0, 10));
    }

    bindEvents() {
        window.addEventListener('resize', () => {
            if (!this.container) return;
            this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        });

        // Listen for SSE events simulated in HTMX or dispatched to window
        window.addEventListener('graph_update', (e) => {
            if (e.detail && e.detail.node_id) {
                this.addMemoryNode(e.detail.node_id);
            }
        });
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        
        // Gentle rotation
        this.coreNode.rotation.y += 0.005;
        this.coreNode.rotation.x += 0.002;
        this.particleSystem.rotation.y -= 0.001;

        // Camera interpolation (scroll-linked effect)
        if (this.targetCameraPos) {
            this.camera.position.lerp(this.targetCameraPos, 0.05);
            // Return to wide view after 3 seconds of a new node
            if (this.nodes.length > 0 && Date.now() - this.nodes[this.nodes.length-1].createdAt > 3000) {
                this.targetCameraPos = new THREE.Vector3(0, 10, 30);
            }
        }

        this.camera.lookAt(this.scene.position);
        this.renderer.render(this.scene, this.camera);
    }
}
