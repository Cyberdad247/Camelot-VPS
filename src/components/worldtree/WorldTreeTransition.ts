import { WorldTreeGraphData, GraphNode, TransitionMode } from '../../types/worldTreeGraph';
import { WorldTree2D } from './WorldTree2D';
import { WorldTree3D } from './WorldTree3D';

export interface WorldTreeTransitionOptions {
  duration?: number;
  onModeChange?: (mode: TransitionMode) => void;
  onProgress?: (progress: number) => void;
  onNodeSelect?: (node: GraphNode | null) => void;
}

export class WorldTreeTransition {
  graphData: WorldTreeGraphData;
  container2D: HTMLElement;
  container3D: HTMLElement;
  mode: TransitionMode = '2D';
  transitionDuration: number;
  options: WorldTreeTransitionOptions;

  graph2D: WorldTree2D | null = null;
  graph3D: WorldTree3D | null = null;
  selectedNode: GraphNode | null = null;

  private isAnimating = false;
  private currentProgress = 0;

  constructor(
    graphData: WorldTreeGraphData,
    container2D: HTMLElement,
    container3D: HTMLElement,
    options: WorldTreeTransitionOptions = {}
  ) {
    this.graphData = graphData;
    this.container2D = container2D;
    this.container3D = container3D;
    this.transitionDuration = options.duration || 800;
    this.options = options;
  }

  setRenderers(graph2D: WorldTree2D, graph3D: WorldTree3D) {
    this.graph2D = graph2D;
    this.graph3D = graph3D;
  }

  async to3D() {
    if (this.mode !== '2D' || this.isAnimating) return;
    this.mode = 'transitioning';
    this.isAnimating = true;
    this.options.onModeChange?.('transitioning');

    // Ensure 3D container is visible during transition so Three.js renders camera and node morph
    this.container3D.style.display = 'block';
    this.container3D.style.opacity = '1';
    this.container2D.style.display = 'block';
    this.container2D.style.opacity = '1';

    if (this.graph3D) {
      this.graph3D.pauseAnimation();

      // Copy 2D node positions directly to 3D to ensure node identity & position continuity
      const rawNodes = this.graphData.nodes.map(n => ({
        ...n,
        x: n.x,
        y: n.y,
        z: 0
      }));
      this.graph3D.updateData({
        ...this.graphData,
        nodes: rawNodes
      });

      // Preserve selection state
      if (this.selectedNode) {
        this.graph3D.setSelectedNode(this.selectedNode);
      }
    }

    // Execute 800ms Morph Animation
    await this.animateMorph();

    // Finalize 3D mode
    this.container2D.style.display = 'none';
    this.container2D.style.opacity = '0';
    this.container3D.style.display = 'block';
    this.container3D.style.opacity = '1';

    if (this.graph3D) {
      this.graph3D.resumeAnimation();
    }

    this.mode = '3D';
    this.isAnimating = false;
    this.currentProgress = 1.0;
    this.options.onModeChange?.('3D');
    this.options.onProgress?.(1.0);
  }

  async to2D() {
    if (this.mode !== '3D' || this.isAnimating) return;
    this.mode = 'transitioning';
    this.isAnimating = true;
    this.options.onModeChange?.('transitioning');

    if (this.graph3D) {
      this.graph3D.pauseAnimation();
    }

    // Both visible during reverse morph
    this.container2D.style.display = 'block';
    this.container3D.style.display = 'block';

    // Execute Reverse Morph Animation
    await this.animateMorphReverse();

    // Copy 3D planar positions back into 2D graph data
    if (this.graph3D && this.graph2D) {
      const g3dData = this.graph3D.graphData;
      if (g3dData?.nodes) {
        g3dData.nodes.forEach(n3 => {
          const n2 = this.graphData.nodes.find(n => n.id === n3.id);
          if (n2) {
            n2.x = n3.x;
            n2.y = n3.y;
            n2.z = 0;
          }
        });
      }
      this.graph2D.setGraphData(this.graphData);
      if (this.selectedNode) {
        this.graph2D.setSelectedNode(this.selectedNode);
      }
      this.graph2D.setMorphFactor(0);
      this.graph2D.requestRedraw();
    }

    // Finalize 2D mode
    this.container3D.style.display = 'none';
    this.container3D.style.opacity = '0';
    this.container2D.style.display = 'block';
    this.container2D.style.opacity = '1';

    this.mode = '2D';
    this.isAnimating = false;
    this.currentProgress = 0.0;
    this.options.onModeChange?.('2D');
    this.options.onProgress?.(0.0);
  }

  // Scrub dimension continuously from 0.0 (pure 2D) to 1.0 (pure 3D)
  scrubContinuously(fraction: number) {
    if (this.isAnimating) return;
    const progress = Math.max(0, Math.min(1, fraction));
    this.currentProgress = progress;

    if (progress <= 0.02) {
      this.container2D.style.display = 'block';
      this.container2D.style.opacity = '1';
      this.container3D.style.display = 'none';
      this.mode = '2D';
      if (this.graph2D) {
        this.graph2D.setMorphFactor(0);
        this.graph2D.requestRedraw();
      }
    } else if (progress >= 0.98) {
      this.container2D.style.display = 'none';
      this.container3D.style.display = 'block';
      this.container3D.style.opacity = '1';
      this.mode = '3D';
      if (this.graph3D) {
        this.applyInterpolatedState(1.0);
        this.graph3D.resumeAnimation();
      }
    } else {
      // Intermediate hybrid state
      this.mode = 'transitioning';
      this.container2D.style.display = 'block';
      this.container2D.style.opacity = `${Math.max(0, 1 - progress * 1.5)}`;
      this.container3D.style.display = 'block';
      this.container3D.style.opacity = `${Math.min(1, progress * 1.5)}`;

      if (this.graph2D) {
        this.graph2D.setMorphFactor(progress);
      }
      if (this.graph3D) {
        this.applyInterpolatedState(progress);
      }
    }

    this.options.onModeChange?.(this.mode);
    this.options.onProgress?.(progress);
  }

  private animateMorph(): Promise<void> {
    const startTime = performance.now();
    const duration = this.transitionDuration;

    return new Promise(resolve => {
      const step = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Ease function (easeInOutCubic) per Section 2.4
        const eased = progress < 0.5
          ? 4 * progress * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 3) / 2;

        this.applyInterpolatedState(eased);
        this.currentProgress = eased;
        this.options.onProgress?.(eased);

        // Fade 2D to 3D smoothly
        this.container2D.style.opacity = `${Math.max(0, 1 - progress * 1.4)}`;
        this.container3D.style.opacity = `${Math.min(1, progress * 1.4)}`;

        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          resolve();
        }
      };

      requestAnimationFrame(step);
    });
  }

  private animateMorphReverse(): Promise<void> {
    const startTime = performance.now();
    const duration = this.transitionDuration;

    return new Promise(resolve => {
      const step = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Inverse easeInOutCubic
        const invProgress = 1 - progress;
        const eased = invProgress < 0.5
          ? 4 * invProgress * invProgress * invProgress
          : 1 - Math.pow(-2 * invProgress + 2, 3) / 2;

        this.applyInterpolatedState(eased);
        this.currentProgress = eased;
        this.options.onProgress?.(eased);

        this.container2D.style.opacity = `${Math.min(1, progress * 1.4)}`;
        this.container3D.style.opacity = `${Math.max(0, 1 - progress * 1.4)}`;

        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          resolve();
        }
      };

      requestAnimationFrame(step);
    });
  }

  private applyInterpolatedState(eased: number) {
    if (this.graph3D) {
      this.graph3D.setMorphProgress(eased);
    }

    if (this.graph2D) {
      this.graph2D.setMorphFactor(eased);
    }
  }

  selectNode(node: GraphNode | null) {
    this.selectedNode = node;
    if (this.graph2D) this.graph2D.setSelectedNode(node);
    if (this.graph3D) this.graph3D.setSelectedNode(node);
    this.options.onNodeSelect?.(node);
  }

  destroy() {
    this.graph2D?.destroy();
    this.graph3D?.destroy();
  }
}
