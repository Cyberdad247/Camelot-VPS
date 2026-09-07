/**
 * OmarchyManager - Baseline host OS configuration and edge-node monitoring.
 * Enforces the 8GB Scarcity Protocol and Zero-GUI Linux configuration.
 */

export interface OmarchySystemVitals {
  cpuUsage: number;
  memoryTotal: number; // in MB
  memoryUsed: number; // in MB
  memoryLimit: number; // 8192 MB (8GB)
  swapUsed: number;
  temperature: number;
  uptime: number;
  activeSlices: number;
  status: 'NOMINAL' | 'WARNING' | 'CRITICAL';
}

export interface SliceMetric {
  name: string;
  memoryCurrent: string;
  memoryLimit: string;
  tasks: number;
  status: 'ACTIVE' | 'THROTTLED' | 'HALTED';
}

export class OmarchyManager {
  private static instance: OmarchyManager;
  private timer: number | null = null;
  private listeners: Set<(vitals: OmarchySystemVitals, slices: SliceMetric[]) => void> = new Set();
  
  // Strict 8GB limit
  private readonly HOST_MEMORY_LIMIT = 8192; 
  
  private constructor() {
    this.startSimulation();
  }

  public static getInstance(): OmarchyManager {
    if (!OmarchyManager.instance) {
      OmarchyManager.instance = new OmarchyManager();
    }
    return OmarchyManager.instance;
  }

  public subscribe(callback: (vitals: OmarchySystemVitals, slices: SliceMetric[]) => void) {
    this.listeners.add(callback);
    // Initial emit
    callback(this.generateMockVitals(), this.generateMockSlices());
    return () => {
      this.listeners.delete(callback);
    };
  }

  private startSimulation() {
    this.timer = window.setInterval(() => {
      const vitals = this.generateMockVitals();
      const slices = this.generateMockSlices();
      this.listeners.forEach(cb => cb(vitals, slices));
    }, 2000);
  }

  public stopSimulation() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private generateMockVitals(): OmarchySystemVitals {
    const memoryUsed = 1200 + Math.random() * 800; // Fluctuates between 1.2GB and 2GB
    const usagePercent = memoryUsed / this.HOST_MEMORY_LIMIT;
    let status: 'NOMINAL' | 'WARNING' | 'CRITICAL' = 'NOMINAL';
    
    if (usagePercent > 0.85) status = 'CRITICAL';
    else if (usagePercent > 0.70) status = 'WARNING';

    return {
      cpuUsage: 15 + Math.random() * 20,
      memoryTotal: this.HOST_MEMORY_LIMIT,
      memoryUsed: parseFloat(memoryUsed.toFixed(2)),
      memoryLimit: this.HOST_MEMORY_LIMIT,
      swapUsed: Math.random() * 50, // Minimal swap
      temperature: 42 + Math.random() * 5,
      uptime: Math.floor(Date.now() / 1000) % 1000000, // mock uptime
      activeSlices: 4,
      status
    };
  }

  private generateMockSlices(): SliceMetric[] {
    return [
      {
        name: 'camelot-critical.slice',
        memoryCurrent: (150 + Math.random() * 50).toFixed(0) + 'M',
        memoryLimit: '1152M',
        tasks: 24,
        status: 'ACTIVE'
      },
      {
        name: 'camelot-control.slice',
        memoryCurrent: (80 + Math.random() * 30).toFixed(0) + 'M',
        memoryLimit: '1024M',
        tasks: 12,
        status: 'ACTIVE'
      },
      {
        name: 'camelot-data.slice',
        memoryCurrent: (600 + Math.random() * 200).toFixed(0) + 'M',
        memoryLimit: '3072M',
        tasks: 120,
        status: 'ACTIVE'
      },
      {
        name: 'camelot-workers.slice',
        memoryCurrent: (100 + Math.random() * 100).toFixed(0) + 'M',
        memoryLimit: '2304M',
        tasks: 8,
        status: 'ACTIVE'
      }
    ];
  }
}
