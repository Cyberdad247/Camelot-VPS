/**
 * Ouroboros / Ternary Integration Schemas
 * Phase 4: BitNet 1.58b Quantization schemas defining non-binary state transitions.
 */

export type TernaryWeight = -1 | 0 | 1;

export interface ITernaryVector {
  id: string;
  weights: TernaryWeight[];
  magnitude: number;
}

export interface IOuroborosState {
  loopId: string;
  currentStep: number;
  maxIterations: number;
  triggerCondition: string;
  haltCondition: string;
  fallbackAction: string;
  // Non-binary state representation at the current step
  activeVector: ITernaryVector;
}

export interface ITernaryQuantizationConfig {
  modelId: string;
  weightFormat: TernaryWeight;
  scalingFactor: number;
  activationBits: 8 | 16;
  zeroPoint: number;
}
