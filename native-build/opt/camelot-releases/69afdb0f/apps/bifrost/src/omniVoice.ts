// SPDX-License-Identifier: MIT

// OMNI_VOICE_DAG_VMAX — voice ingress routing for the Bifrost gateway.
//
// The Python module (control_plane/dispatch/omni_voice_dag.py) is the source of
// truth: it owns the crystal manifest, the evidence gate and the Softmax
// persona distribution. The gateway runs on the Node event loop and cannot
// import Python, so this module re-implements the *deterministic* half of that
// contract — the ᛟ_ runic bypass and P( Ki | v ) — and is pinned to Python by
// `omniVoice.crystal.json`, a fixture generated from that module:
//
//   python -m control_plane.omni_voice_dag \
//       --write-vectors apps/bifrost/src/omniVoice.crystal.json
//
// `omniVoice.test.ts` replays every vector in that fixture, so the port cannot
// silently drift from the Python implementation: edit the crystal or the
// keyword table on one side and the gateway's tests go red.
//
// Like the Python module, every path here is read-only. Routing decides; it
// never launches a process or executes the rune a bypass delegates to.

import rawCrystal from './omniVoice.crystal.json';

/** Identity the fixture must carry — a stale fixture is a hard failure. */
export const CRYSTAL_FINGERPRINT = 'νKG_CRYSTAL_OMNI_VOICE_DAG_VMAX';

/** The generator that must have produced the fixture. */
export const CRYSTAL_GENERATOR = 'control_plane.omni_voice_dag';

export type OmniVoiceStatus =
  | 'ROUTED_BYPASS'
  | 'ROUTED_SOFTMAX'
  | 'TAU_POLICY_DENIED'
  | 'FEATURE_DIM_MISMATCH';

export interface BypassCommand {
  token: string;
  knight: string;
  delegatesRune: string;
}

export interface OmniVoiceVector {
  input: string;
  status: string;
  path: string | null;
  token?: string;
  knight?: string;
  delegatesRune?: string;
  tau?: number;
  features?: number[];
  logits?: Record<string, number>;
  probabilities?: Record<string, number>;
  confidence?: number;
}

export interface OmniVoiceCrystal {
  generator: string;
  generatorVersion: string;
  fingerprint: string;
  systemIdentity: string;
  hardwareCeilingMb: number;
  bypassPrefix: string;
  featureDims: string[];
  tauPolicy: {
    allowedTauValues: number[];
    deterministicTau: number;
    exploratoryTau: number;
  };
  weights: Record<string, number[]>;
  bypassCommands: BypassCommand[];
  vectors: OmniVoiceVector[];
}

export interface SoftmaxOutcome {
  probabilities: Record<string, number>;
  logits: Record<string, number>;
  winner: string;
  confidence: number;
}

export interface OmniVoiceRoute {
  action: 'omni_voice_route';
  input: string;
  path: 'runic_bypass' | 'softmax';
  status: OmniVoiceStatus;
  knight?: string;
  token?: string;
  delegatesRune?: string;
  llmInferenceCost?: number;
  tau?: number;
  confidence?: number;
  error?: string;
}

/** Raised when a tau value escapes the Sentinel-governed policy. */
export class TauPolicyError extends Error {}

// ---------------------------------------------------------------------------
// Fixture shape (snake_case, as emitted by the Python generator)
// ---------------------------------------------------------------------------

interface RawVector {
  input: string;
  status: string;
  path: string | null;
  token?: string;
  knight?: string;
  delegates_rune?: string;
  tau?: number;
  features?: number[];
  logits?: Record<string, number>;
  probabilities?: Record<string, number>;
  confidence?: number;
}

interface RawCrystal {
  generator: string;
  generator_version: string;
  fingerprint: string;
  system_identity: string;
  hardware_ceiling_mb: number;
  bypass_prefix: string;
  feature_dims: string[];
  tau_policy: {
    allowed_tau_values: number[];
    deterministic_tau: number;
    exploratory_tau: number;
  };
  weights: Record<string, number[]>;
  bypass_commands: { token: string; knight: string; delegates_rune: string }[];
  vectors: RawVector[];
}

function normalize(raw: RawCrystal): OmniVoiceCrystal {
  return {
    generator: raw.generator,
    generatorVersion: raw.generator_version,
    fingerprint: raw.fingerprint,
    systemIdentity: raw.system_identity,
    hardwareCeilingMb: raw.hardware_ceiling_mb,
    bypassPrefix: raw.bypass_prefix,
    featureDims: raw.feature_dims,
    tauPolicy: {
      allowedTauValues: raw.tau_policy.allowed_tau_values,
      deterministicTau: raw.tau_policy.deterministic_tau,
      exploratoryTau: raw.tau_policy.exploratory_tau,
    },
    weights: raw.weights,
    bypassCommands: raw.bypass_commands.map((command) => ({
      token: command.token,
      knight: command.knight,
      delegatesRune: command.delegates_rune,
    })),
    vectors: raw.vectors.map((vector) => ({
      input: vector.input,
      status: vector.status,
      path: vector.path,
      token: vector.token,
      knight: vector.knight,
      delegatesRune: vector.delegates_rune,
      tau: vector.tau,
      features: vector.features,
      logits: vector.logits,
      probabilities: vector.probabilities,
      confidence: vector.confidence,
    })),
  };
}

/** The parsed fixture. Loaded once at module import. */
export const CRYSTAL: OmniVoiceCrystal = normalize(rawCrystal as unknown as RawCrystal);

export function loadCrystal(): OmniVoiceCrystal {
  return CRYSTAL;
}

// ---------------------------------------------------------------------------
// Score helpers
// ---------------------------------------------------------------------------

/** `v · W`, left-to-right so the summation order matches Python's `sum`. */
function dot(a: number[], b: number[]): number {
  if (a.length !== b.length) {
    throw new Error(`dimension mismatch: ${a.length} features vs ${b.length} weights`);
  }
  let total = 0;
  for (let i = 0; i < a.length; i++) {
    total += a[i] * b[i];
  }
  return total;
}

/**
 * `max(d, key=lambda k: (d[k], k))` — highest score wins, ties broken by the
 * lexicographically largest persona id so the same utterance always resolves
 * to the same knight.
 */
function argmax(scores: Record<string, number>): string {
  const keys = Object.keys(scores);
  let best = keys[0];
  for (const key of keys) {
    const value = scores[key];
    if (value > scores[best] || (value === scores[best] && key > best)) {
      best = key;
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Runic bypass
// ---------------------------------------------------------------------------

/**
 * Return the bypass command if `text` opens with a declared `ᛟ_` token.
 *
 * The token must be the first whitespace-delimited word, so a glyph spoken
 * mid-sentence cannot hijack the audio stream. Trailing ASR punctuation is
 * tolerated; nothing else is.
 */
export function detectRune(
  text: string,
  crystal: OmniVoiceCrystal = CRYSTAL,
): BypassCommand | null {
  if (!text || !text.trim()) return null;
  const head = text.trim().split(/\s+/)[0];
  if (!head.startsWith(crystal.bypassPrefix)) return null;

  const table = new Map(crystal.bypassCommands.map((command) => [command.token, command]));
  return table.get(head) ?? table.get(head.replace(/[.,!?;:]+$/, '')) ?? null;
}

// ---------------------------------------------------------------------------
// Feature projection
// ---------------------------------------------------------------------------

/**
 * Deterministic keyword -> feature projection. Cheap and fully explainable: no
 * inference cost, which is the constraint the `ᛟ_` bypass exists to protect.
 * Must stay in lockstep with `infer_features()` in the Python module.
 */
const FEATURE_KEYWORDS: Record<string, string[]> = {
  lexical_intent: ['why', 'how', 'explain', 'what', 'reason'],
  urgency: ['now', 'immediately', 'asap', 'urgent', 'critical'],
  privacy_sensitive: ['secret', 'token', 'key', 'password', 'private'],
  telemetry_request: ['status', 'metrics', 'telemetry', 'report', 'health'],
  build_intent: ['forge', 'build', 'implement', 'create', 'compile'],
  audio_focus: ['voice', 'audio', 'speak', 'listen', 'say'],
};

export function inferFeatures(text: string, crystal: OmniVoiceCrystal = CRYSTAL): number[] {
  const lowered = text.toLowerCase();
  return crystal.featureDims.map((dim) => {
    const needles = FEATURE_KEYWORDS[dim] ?? [];
    return needles.some((needle) => lowered.includes(needle)) ? 1 : 0;
  });
}

// ---------------------------------------------------------------------------
// Softmax persona dispatch
// ---------------------------------------------------------------------------

/**
 * Clamp a requested tau to the Sentinel-governed policy.
 *
 * `τ=0` is deterministic execution, `τ=1` is exploratory persona routing. Any
 * value outside the declared policy is rejected rather than silently clamped,
 * so an exploratory drift stays visible instead of hiding.
 */
export function resolveTau(crystal: OmniVoiceCrystal, tau?: number): number {
  const chosen = tau === undefined ? crystal.tauPolicy.deterministicTau : tau;
  if (!crystal.tauPolicy.allowedTauValues.includes(chosen)) {
    throw new TauPolicyError(
      `tau=${chosen} violates Sentinel policy [${crystal.tauPolicy.allowedTauValues.join(', ')}]`,
    );
  }
  return chosen;
}

/**
 * Compute `P(K_i|v) = exp(v·W_i / τ) / Σ_j exp(v·W_j / τ)`.
 *
 * `τ=0` collapses the distribution to a one-hot argmax with confidence `1.0` —
 * deterministic execution, no sampling. `τ>0` produces a true softmax, shifted
 * by the max logit so it stays numerically stable.
 */
export function softmaxDispatch(
  features: number[],
  weights: Record<string, number[]>,
  tau: number,
): SoftmaxOutcome {
  if (tau < 0) throw new Error('tau must be non-negative');

  const knights = Object.keys(weights);
  if (knights.length === 0) throw new Error('no persona weight vectors supplied');

  const logits: Record<string, number> = {};
  for (const knight of knights) {
    logits[knight] = dot(features, weights[knight]);
  }

  if (tau === 0) {
    const winner = argmax(logits);
    const probabilities: Record<string, number> = {};
    for (const knight of knights) {
      probabilities[knight] = knight === winner ? 1 : 0;
    }
    return { probabilities, logits, winner, confidence: 1 };
  }

  const scaled: Record<string, number> = {};
  for (const knight of knights) {
    scaled[knight] = logits[knight] / tau;
  }
  const peak = Math.max(...knights.map((knight) => scaled[knight]));

  const exps: Record<string, number> = {};
  let total = 0;
  for (const knight of knights) {
    const value = Math.exp(scaled[knight] - peak);
    exps[knight] = value;
    total += value;
  }

  const probabilities: Record<string, number> = {};
  for (const knight of knights) {
    probabilities[knight] = exps[knight] / total;
  }
  const winner = argmax(probabilities);
  return { probabilities, logits, winner, confidence: probabilities[winner] };
}

// ---------------------------------------------------------------------------
// Routing
// ---------------------------------------------------------------------------

export interface RouteOptions {
  tau?: number;
  features?: number[];
  crystal?: OmniVoiceCrystal;
}

/**
 * Route one voice utterance: runic bypass first, Softmax second.
 *
 * The bypass short-circuits before any inference work, which is the entire
 * point of the `ᛟ_` lane.
 */
export function routeOmniVoice(text: string, options: RouteOptions = {}): OmniVoiceRoute {
  const crystal = options.crystal ?? CRYSTAL;

  const bypass = detectRune(text, crystal);
  if (bypass) {
    return {
      action: 'omni_voice_route',
      input: text,
      path: 'runic_bypass',
      status: 'ROUTED_BYPASS',
      token: bypass.token,
      knight: bypass.knight,
      delegatesRune: bypass.delegatesRune,
      llmInferenceCost: 0,
    };
  }

  let tau: number;
  try {
    tau = resolveTau(crystal, options.tau);
  } catch (err) {
    return {
      action: 'omni_voice_route',
      input: text,
      path: 'softmax',
      status: 'TAU_POLICY_DENIED',
      error: (err as Error).message,
    };
  }

  const features = options.features ?? inferFeatures(text, crystal);
  if (features.length !== crystal.featureDims.length) {
    return {
      action: 'omni_voice_route',
      input: text,
      path: 'softmax',
      status: 'FEATURE_DIM_MISMATCH',
      error: `feature vector has ${features.length} dims, crystal declares ${crystal.featureDims.length}`,
    };
  }

  try {
    const { winner, confidence } = softmaxDispatch(features, crystal.weights, tau);
    return {
      action: 'omni_voice_route',
      input: text,
      path: 'softmax',
      status: 'ROUTED_SOFTMAX',
      tau,
      knight: winner,
      confidence,
    };
  } catch (err) {
    return {
      action: 'omni_voice_route',
      input: text,
      path: 'softmax',
      status: 'FEATURE_DIM_MISMATCH',
      error: (err as Error).message,
    };
  }
}
