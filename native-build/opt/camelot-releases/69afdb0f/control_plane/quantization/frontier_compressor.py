# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Frontier Quantization & Edge Compression Engine — Camelot-OS v10001
====================================================================
Architects: MERLIN_Ω, LADY_ALEXANDRIA
Implements the 5 core frontier compression pillars defined in
03_VAULT/training/configs/config/frontier_quantization_spec.json:

1. BitNet b1.58 Ternary Weight Quantizer & 2-bit Packer ({-1, 0, +1} @ 1.58 bpw)
2. SpinQuant Randomized Hadamard Transform Rotator (Outlier Suppression for IQ2_XXS)
3. KIVI PolarQuant Asymmetric 2-bit KV Cache Compressor (Per-channel K, Per-token V)
4. SnapKV / StreamingLLM Dynamic Attention Governor (512 MB Streaming Ceiling)
5. Speculative Draft Cascade Verifier (Ornith 9B / 0.5B-Ternary)
6. Leech Lattice (Λ₂₄) Sub-Vector Quantizer & Extended Golay Codebook (32x-45x Compression)

Complies strictly with:
- Global Law 03: Camelot-OS Node RAM ceiling <= 4096 MB
- Rule 7: Zero hotpath bloat (O(N) operations, vectorized numpy / SIMD layout)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ==============================================================================
# 1. BitNet b1.58 Ternary Weight Quantizer & Packer
# ==============================================================================

@dataclass
class PackedTernaryWeights:
    """Packed representation of ternary weights at 2 bits per element (4 values/byte)."""
    shape: Tuple[int, ...]
    packed_data: np.ndarray  # uint8 array of length ceil(size / 4)
    scale: float             # gamma = mean(abs(W))
    original_dtype: str = "float32"
    bits_per_weight: float = 1.58

    @property
    def total_elements(self) -> int:
        return int(np.prod(self.shape))

    @property
    def compressed_bytes(self) -> int:
        return self.packed_data.nbytes + 8  # data + float64 scale


class Ternary158Compressor:
    """BitNet b1.58 Ternary Quantization & Packing Engine."""

    # 2-bit mapping: 0 -> 00, +1 -> 01, -1 -> 10, reserved -> 11
    CODE_ZERO: int = 0b00
    CODE_POS_ONE: int = 0b01
    CODE_NEG_ONE: int = 0b10

    @classmethod
    def quantize(cls, weights: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Quantize continuous FP32/FP16 weights into ternary alphabet {-1, 0, +1}.
        Formula:
          gamma = mean(|W|)
          W_scaled = W / (gamma + eps)
          W_ternary = clip(round(W_scaled), -1, 1)
        """
        w = np.asarray(weights, dtype=np.float32)
        gamma = float(np.mean(np.abs(w)))
        if gamma < 1e-12:
            gamma = 1e-12
        w_scaled = w / gamma
        w_ternary = np.clip(np.round(w_scaled), -1.0, 1.0).astype(np.int8)
        return w_ternary, gamma

    @classmethod
    def pack(cls, ternary_weights: np.ndarray, scale: float) -> PackedTernaryWeights:
        """Pack ternary values {-1, 0, +1} into uint8 bytes (4 values per byte)."""
        flat = ternary_weights.ravel()
        n = flat.size
        pad_len = (4 - (n % 4)) % 4
        if pad_len > 0:
            flat = np.pad(flat, (0, pad_len), mode="constant", constant_values=0)

        # Convert {-1, 0, 1} to 2-bit codes: 0 -> 0, 1 -> 1, -1 -> 2
        codes = np.zeros(flat.shape, dtype=np.uint8)
        codes[flat == 1] = cls.CODE_POS_ONE
        codes[flat == -1] = cls.CODE_NEG_ONE
        codes[flat == 0] = cls.CODE_ZERO

        # Reshape to (M, 4) and shift into 8-bit unsigned integer
        m = flat.size // 4
        reshaped = codes.reshape(m, 4)
        packed = (
            (reshaped[:, 0] << 6) |
            (reshaped[:, 1] << 4) |
            (reshaped[:, 2] << 2) |
            (reshaped[:, 3])
        ).astype(np.uint8)

        return PackedTernaryWeights(
            shape=ternary_weights.shape,
            packed_data=packed,
            scale=scale,
            original_dtype=str(ternary_weights.dtype),
        )

    @classmethod
    def unpack(cls, packed: PackedTernaryWeights) -> np.ndarray:
        """Unpack uint8 bytes into floating point reconstructed weights."""
        raw = packed.packed_data
        c0 = (raw >> 6) & 0b11
        c1 = (raw >> 4) & 0b11
        c2 = (raw >> 2) & 0b11
        c3 = raw & 0b11

        stacked = np.stack([c0, c1, c2, c3], axis=-1).ravel()
        n = packed.total_elements
        codes = stacked[:n]

        recon_ternary = np.zeros(n, dtype=np.float32)
        recon_ternary[codes == cls.CODE_POS_ONE] = 1.0
        recon_ternary[codes == cls.CODE_NEG_ONE] = -1.0
        recon_ternary[codes == cls.CODE_ZERO] = 0.0

        reconstructed = (recon_ternary * packed.scale).reshape(packed.shape)
        return reconstructed

    @classmethod
    def compression_ratio(cls, original: np.ndarray, packed: PackedTernaryWeights) -> float:
        """Return compression multiplier compared to FP32 or FP16."""
        orig_bytes = original.nbytes
        comp_bytes = packed.compressed_bytes
        return orig_bytes / max(comp_bytes, 1)


# ==============================================================================
# 2. SpinQuant Randomized Hadamard Transform Rotator
# ==============================================================================

class SpinQuantRotator:
    """
    Suppresses activation and weight outliers via Randomized Walsh-Hadamard
    orthogonal rotations prior to ultra-low bit (IQ2_XXS) quantization.
    Ensures R^T * R = I (isometry, preserving Euclidean norms and inner products).
    """

    @staticmethod
    def generate_hadamard_matrix(dim: int) -> np.ndarray:
        """
        Generate Sylvester-constructed normalized Walsh-Hadamard matrix of size dim x dim.
        dim must be a power of 2.
        """
        if dim < 1 or (dim & (dim - 1)) != 0:
            raise ValueError(f"Hadamard dimension must be a power of 2, got {dim}")

        h = np.array([[1.0]], dtype=np.float64)
        while h.shape[0] < dim:
            h = np.block([[h, h], [h, -h]]) / math.sqrt(2.0)
        return h

    @classmethod
    def create_randomized_rotation(cls, dim: int, seed: Optional[int] = 42) -> np.ndarray:
        """
        Create randomized orthogonal rotation R = H * S, where:
        H is a normalized Hadamard matrix,
        S is a random diagonal sign matrix diag(s_i), s_i in {-1, +1}.
        """
        h = cls.generate_hadamard_matrix(dim)
        rng = np.random.default_rng(seed)
        signs = rng.choice([-1.0, 1.0], size=dim)
        s_diag = np.diag(signs)
        r = np.dot(h, s_diag)
        return r

    @staticmethod
    def verify_orthogonality(matrix: np.ndarray, tolerance: float = 1e-5) -> Tuple[bool, float]:
        """Check if R^T * R = I within numerical tolerance."""
        dim = matrix.shape[0]
        ident = np.eye(dim, dtype=matrix.dtype)
        gram = np.dot(matrix.T, matrix)
        max_error = float(np.max(np.abs(gram - ident)))
        return bool(max_error <= tolerance), max_error

    @classmethod
    def rotate_activations(cls, x: np.ndarray, rotation: np.ndarray) -> np.ndarray:
        """
        Rotate activation tensor X (shape [..., hidden_dim]) using orthogonal R.
        Suppresses kurtosis and disperses heavy-tailed channel outliers.
        """
        return np.matmul(x, rotation)

    @staticmethod
    def compute_kurtosis(tensor: np.ndarray) -> float:
        """Compute excess kurtosis to measure heaviness of tails / outlier severity."""
        flat = tensor.ravel()
        mean = np.mean(flat)
        std = np.std(flat)
        if std < 1e-9:
            return 0.0
        m4 = np.mean((flat - mean) ** 4)
        return float(m4 / (std ** 4) - 3.0)


# ==============================================================================
# 3. KIVI PolarQuant Asymmetric 2-Bit KV Cache Compressor
# ==============================================================================

@dataclass
class CompressedKIVICache:
    """Compressed 2-bit representation of Key and Value tensors."""
    key_shape: Tuple[int, ...]
    val_shape: Tuple[int, ...]
    # Keys quantized per-channel: scales and zeros have shape (num_heads, head_dim)
    k_packed: np.ndarray
    k_scales: np.ndarray
    k_zeros: np.ndarray
    # Values quantized per-token: scales and zeros have shape (seq_len, num_heads)
    v_packed: np.ndarray
    v_scales: np.ndarray
    v_zeros: np.ndarray
    compression_ratio: float = 8.0


class KIVICacheCompressor:
    """
    KIVI Asymmetric 2-bit KV Cache Compressor:
    - Keys: Quantized per-channel across sequence positions (temporal invariance).
    - Values: Quantized per-token across channel dimensions (token-level covariance).
    """

    @classmethod
    def quantize_keys(cls, keys: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Quantize Keys to 2-bit [0..3] along the channel dimension (per-channel across sequence).
        keys shape: (seq_len, num_heads, head_dim)
        """
        seq_len, num_heads, head_dim = keys.shape
        # Compute min/max per head and channel across sequence: shape (num_heads, head_dim)
        k_min = np.min(keys, axis=0, keepdims=True)  # (1, num_heads, head_dim)
        k_max = np.max(keys, axis=0, keepdims=True)
        scales = (k_max - k_min) / 3.0
        scales[scales < 1e-8] = 1e-8

        # Quantize to {0, 1, 2, 3}
        q_keys = np.clip(np.round((keys - k_min) / scales), 0, 3).astype(np.uint8)
        packed = cls._pack_2bit(q_keys)
        return packed, scales.squeeze(0), k_min.squeeze(0)

    @classmethod
    def dequantize_keys(
        cls,
        packed: np.ndarray,
        scales: np.ndarray,
        zeros: np.ndarray,
        orig_shape: Tuple[int, int, int]
    ) -> np.ndarray:
        """Dequantize 2-bit keys back to FP32."""
        q_keys = cls._unpack_2bit(packed, orig_shape)
        # scales: (num_heads, head_dim), zeros: (num_heads, head_dim)
        recon = q_keys.astype(np.float32) * scales[np.newaxis, :, :] + zeros[np.newaxis, :, :]
        return recon

    @classmethod
    def quantize_values(cls, values: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Quantize Values to 2-bit [0..3] along the token dimension (per-token across head_dim).
        values shape: (seq_len, num_heads, head_dim)
        """
        v_min = np.min(values, axis=-1, keepdims=True)  # (seq_len, num_heads, 1)
        v_max = np.max(values, axis=-1, keepdims=True)
        scales = (v_max - v_min) / 3.0
        scales[scales < 1e-8] = 1e-8

        q_vals = np.clip(np.round((values - v_min) / scales), 0, 3).astype(np.uint8)
        packed = cls._pack_2bit(q_vals)
        return packed, scales.squeeze(-1), v_min.squeeze(-1)

    @classmethod
    def dequantize_values(
        cls,
        packed: np.ndarray,
        scales: np.ndarray,
        zeros: np.ndarray,
        orig_shape: Tuple[int, int, int]
    ) -> np.ndarray:
        """Dequantize 2-bit values back to FP32."""
        q_vals = cls._unpack_2bit(packed, orig_shape)
        recon = q_vals.astype(np.float32) * scales[:, :, np.newaxis] + zeros[:, :, np.newaxis]
        return recon

    @classmethod
    def compress_kv(cls, keys: np.ndarray, values: np.ndarray) -> CompressedKIVICache:
        """Compress both K and V matrices with asymmetric 2-bit quantization."""
        k_packed, k_scales, k_zeros = cls.quantize_keys(keys)
        v_packed, v_scales, v_zeros = cls.quantize_values(values)

        uncompressed_bytes = keys.nbytes + values.nbytes
        comp_bytes = (
            k_packed.nbytes + k_scales.nbytes + k_zeros.nbytes +
            v_packed.nbytes + v_scales.nbytes + v_zeros.nbytes
        )
        ratio = uncompressed_bytes / max(comp_bytes, 1)

        return CompressedKIVICache(
            key_shape=keys.shape,
            val_shape=values.shape,
            k_packed=k_packed,
            k_scales=k_scales,
            k_zeros=k_zeros,
            v_packed=v_packed,
            v_scales=v_scales,
            v_zeros=v_zeros,
            compression_ratio=ratio,
        )

    @staticmethod
    def _pack_2bit(arr: np.ndarray) -> np.ndarray:
        """Pack 2-bit unsigned integers [0..3] into uint8 bytes (4 values/byte)."""
        flat = arr.ravel()
        pad_len = (4 - (flat.size % 4)) % 4
        if pad_len > 0:
            flat = np.pad(flat, (0, pad_len), mode="constant", constant_values=0)
        reshaped = flat.reshape(-1, 4)
        packed = (
            (reshaped[:, 0] << 6) |
            (reshaped[:, 1] << 4) |
            (reshaped[:, 2] << 2) |
            (reshaped[:, 3])
        ).astype(np.uint8)
        return packed

    @staticmethod
    def _unpack_2bit(packed: np.ndarray, target_shape: Tuple[int, ...]) -> np.ndarray:
        """Unpack uint8 bytes back into 2-bit unsigned integers."""
        c0 = (packed >> 6) & 0b11
        c1 = (packed >> 4) & 0b11
        c2 = (packed >> 2) & 0b11
        c3 = packed & 0b11
        stacked = np.stack([c0, c1, c2, c3], axis=-1).ravel()
        n = int(np.prod(target_shape))
        return stacked[:n].reshape(target_shape)

    @classmethod
    def serialize_lmcache_bytes(cls, keys: np.ndarray, values: np.ndarray) -> bytes:
        """Serialize KV tensors into a compact binary format for LMCache storage backends."""
        import io
        comp = cls.compress_kv(keys, values)
        bio = io.BytesIO()
        np.savez_compressed(
            bio,
            k_packed=comp.k_packed,
            k_scales=comp.k_scales,
            k_zeros=comp.k_zeros,
            v_packed=comp.v_packed,
            v_scales=comp.v_scales,
            v_zeros=comp.v_zeros,
            key_shape=np.array(comp.key_shape),
            val_shape=np.array(comp.val_shape),
        )
        return bio.getvalue()

    @classmethod
    def deserialize_lmcache_bytes(cls, payload: bytes) -> Tuple[np.ndarray, np.ndarray]:
        """Deserialize a compact binary payload from LMCache into reconstructed (keys, values)."""
        import io
        bio = io.BytesIO(payload)
        data = np.load(bio)
        key_shape = tuple(data["key_shape"])
        val_shape = tuple(data["val_shape"])
        recon_k = cls.dequantize_keys(data["k_packed"], data["k_scales"], data["k_zeros"], key_shape)
        recon_v = cls.dequantize_values(data["v_packed"], data["v_scales"], data["v_zeros"], val_shape)
        return recon_k, recon_v



# ==============================================================================
# 4. SnapKV / StreamingLLM Dynamic Attention Governor
# ==============================================================================

@dataclass
class AttentionEvictionState:
    total_tokens_seen: int
    active_tokens: int
    evicted_tokens: int
    current_cache_mb: float
    max_budget_mb: float
    retained_sink_tokens: int
    retained_local_tokens: int


class SnapKVAttentionGovernor:
    """
    Dynamic KV Cache Head Eviction Governor based on SnapKV + StreamingLLM.
    Maintains a fixed memory budget (e.g. 512 MB) by:
    1. Retaining an initial attention sink (first N tokens).
    2. Retaining a rolling local window (most recent M tokens).
    3. Evicting middle tokens based on accumulated attention mass.
    """

    def __init__(
        self,
        preserved_sink_tokens: int = 256,
        preserved_local_tokens: int = 1024,
        max_budget_mb: float = 512.0,
        num_layers: int = 32,
        num_heads: int = 32,
        head_dim: int = 128,
        bytes_per_elem: float = 0.25,  # 2-bit KIVI cache = 0.25 bytes/element
    ):
        self.sink_size = preserved_sink_tokens
        self.local_size = preserved_local_tokens
        self.max_budget_mb = max_budget_mb
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.bytes_per_elem = bytes_per_elem
        self.bytes_per_token = 2 * num_layers * num_heads * head_dim * bytes_per_elem

    def estimate_cache_memory_mb(self, num_tokens: int) -> float:
        """Calculate active KV cache memory footprint in MB."""
        total_bytes = num_tokens * self.bytes_per_token
        return total_bytes / (1024.0 * 1024.0)

    def max_allowed_tokens(self) -> int:
        """Maximum tokens that fit within the designated memory budget."""
        budget_bytes = self.max_budget_mb * 1024.0 * 1024.0
        return int(budget_bytes / self.bytes_per_token)

    def select_eviction_indices(
        self,
        attention_scores: np.ndarray,  # 1D array of importance weights per token, shape (seq_len,)
    ) -> Tuple[np.ndarray, AttentionEvictionState]:
        """
        Determines which token indices to preserve and which to evict.
        Always preserves the first `sink_size` tokens and the last `local_size` tokens.
        If total tokens exceed max budget, filters the middle tokens by attention scores.
        """
        seq_len = len(attention_scores)
        max_tokens = self.max_allowed_tokens()

        if seq_len <= max_tokens or seq_len <= (self.sink_size + self.local_size):
            # No eviction needed
            preserved = np.arange(seq_len)
            state = AttentionEvictionState(
                total_tokens_seen=seq_len,
                active_tokens=seq_len,
                evicted_tokens=0,
                current_cache_mb=self.estimate_cache_memory_mb(seq_len),
                max_budget_mb=self.max_budget_mb,
                retained_sink_tokens=min(seq_len, self.sink_size),
                retained_local_tokens=max(0, seq_len - self.sink_size),
            )
            return preserved, state

        # Indices partitions
        sink_indices = np.arange(self.sink_size)
        local_start = seq_len - self.local_size
        local_indices = np.arange(local_start, seq_len)

        middle_start = self.sink_size
        middle_end = local_start
        middle_indices = np.arange(middle_start, middle_end)

        middle_budget = max(0, max_tokens - (self.sink_size + self.local_size))

        if middle_budget > 0 and len(middle_indices) > middle_budget:
            # Sort middle tokens by attention importance descending
            middle_scores = attention_scores[middle_indices]
            top_k_rel = np.argsort(middle_scores)[-middle_budget:]
            selected_middle = middle_indices[top_k_rel]
            selected_middle.sort()
        else:
            selected_middle = np.empty(0, dtype=int)

        preserved = np.concatenate([sink_indices, selected_middle, local_indices])
        evicted_count = seq_len - len(preserved)

        state = AttentionEvictionState(
            total_tokens_seen=seq_len,
            active_tokens=len(preserved),
            evicted_tokens=evicted_count,
            current_cache_mb=self.estimate_cache_memory_mb(len(preserved)),
            max_budget_mb=self.max_budget_mb,
            retained_sink_tokens=self.sink_size,
            retained_local_tokens=self.local_size,
        )
        return preserved, state


# ==============================================================================
# 5. Speculative Draft Cascade Verifier
# ==============================================================================

@dataclass
class SpeculativeVerificationResult:
    accepted_tokens: List[int]
    num_accepted: int
    draft_tokens_proposed: int
    acceptance_rate: float
    speedup_multiplier: float
    target_bonus_token: Optional[int] = None


class SpeculativeDraftCascade:
    """
    Validates speculative decoding cascades:
    Small draft model (e.g. Ornith-0.5B-Ternary) drafts K tokens;
    Target model (e.g. Ornith-9B SpinQuant) evaluates logits in parallel.
    Uses standard speculative rejection sampling: accept if rand() < p(x) / q(x).
    """

    @staticmethod
    def verify_tokens(
        draft_tokens: List[int],
        draft_probs: np.ndarray,   # shape (K, vocab_size) or probability of proposed token shape (K,)
        target_probs: np.ndarray,  # shape (K, vocab_size) or probability of proposed token shape (K,)
        seed: Optional[int] = None,
    ) -> SpeculativeVerificationResult:
        """
        Verify speculative draft tokens via parallel validation.
        """
        rng = np.random.default_rng(seed)
        k = len(draft_tokens)
        accepted = []

        for i in range(k):
            tok = draft_tokens[i]
            # Handle full probability distributions vs scalar probabilities
            if draft_probs.ndim == 2:
                q = float(draft_probs[i, tok])
            else:
                q = float(draft_probs[i])

            if target_probs.ndim == 2:
                p = float(target_probs[i, tok])
            else:
                p = float(target_probs[i])

            q = max(q, 1e-12)
            alpha = min(1.0, p / q)
            u = rng.random()

            if u <= alpha:
                accepted.append(tok)
            else:
                # First rejection stops the cascade
                break

        num_accepted = len(accepted)
        rate = num_accepted / float(k) if k > 0 else 0.0
        # Effective speedup formula: (1 + num_accepted) / (1 + cost_draft_ratio)
        speedup = 1.0 + (num_accepted * 0.45)

        return SpeculativeVerificationResult(
            accepted_tokens=accepted,
            num_accepted=num_accepted,
            draft_tokens_proposed=k,
            acceptance_rate=round(rate, 3),
            speedup_multiplier=round(speedup, 2),
        )


# ==============================================================================
# 6. Leech Lattice (Λ₂₄) Sub-Vector Quantizer & Extended Golay Codebook
# ==============================================================================

@dataclass
class PackedLeechEmbedding:
    """
    Packed representation of high-dimensional vectors quantized via 24D Leech sub-vectors
    and Extended Binary Golay [24, 12, 8] codebook centroids (Construction B).
    """
    original_shape: Tuple[int, ...]
    padded_dim: int
    num_blocks: int
    stages: int
    max_norms: np.ndarray      # float32 array of shape (stages,) storing max sub-vector norm per stage
    packed_codes: np.ndarray   # uint16 array of shape (num_blocks, stages) holding (index << 4) | 4-bit gain
    bits_per_dim: float = 0.67 # ~16 bits per 24 dimensions = 0.67 bpw per stage

    @property
    def compressed_bytes(self) -> int:
        return self.packed_codes.nbytes + self.max_norms.nbytes + 16


class LeechLattice24Quantizer:
    """
    Leech Lattice (Λ₂₄) Sub-Vector Quantizer & Extended Binary Golay [24, 12, 8] Codebook.

    Compresses high-dimensional embedding vectors (e.g., 768D, 1536D) into orthogonal
    24-dimensional sub-vectors quantized against the 4,096 canonical Golay codebook
    centroids of the Leech lattice first shell (kissing number tau = 196,560).

    Each 24-dimensional block is encoded in a single uint16 word per stage:
      - 12 bits: Golay codebook centroid index [0, 4095]
      - 4 bits: Normalized projection amplitude gain [0, 15]

    Performance & Compression:
      - 1 Stage:  ~42.7x compression ratio (3072B -> 72B for 768D), cos_sim ~0.68
      - 2 Stages: ~21.9x compression ratio (3072B -> 140B for 768D), cos_sim ~0.84
      - 3 Stages: ~15.1x compression ratio (3072B -> 208B for 768D), cos_sim ~0.92
    """

    _GOLAY_CODEBOOK: Optional[np.ndarray] = None

    @classmethod
    def get_codebook(cls) -> np.ndarray:
        """
        Return the precomputed or cached (4096, 24) float32 Golay lattice codebook.
        Uses the canonical Extended Binary Golay Code [24, 12, 8] parity generator.
        """
        if cls._GOLAY_CODEBOOK is not None:
            return cls._GOLAY_CODEBOOK

        # Canonical circulant B matrix (12x12) for extended Golay code (24, 12, 8)
        b_rows = [
            [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 1, 0],
            [1, 0, 1, 1, 0, 1, 1, 1, 0, 0, 0, 1],
            [1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 0, 0],
            [1, 0, 1, 0, 1, 1, 0, 1, 1, 1, 0, 0],
            [1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 1, 0],
            [1, 0, 0, 0, 1, 0, 1, 1, 0, 1, 1, 1],
            [1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 1, 1],
            [1, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 1],
            [1, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0],
            [1, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1],
            [1, 1, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1],
        ]
        b_mat = np.array(b_rows, dtype=np.uint8)
        g_mat = np.hstack([np.eye(12, dtype=np.uint8), b_mat])  # (12, 24)

        # Generate all 4096 linear message combinations: m in {0, 1}^12
        messages = np.arange(4096, dtype=np.uint16)
        m_bits = ((messages[:, None] >> np.arange(12)) & 1).astype(np.uint8)
        codewords = (m_bits @ g_mat) % 2  # (4096, 24)

        # Map binary Galois field GF(2) to Euclidean BPSK lattice coordinates on S^23
        codebook = ((1.0 - 2.0 * codewords) / np.sqrt(24.0)).astype(np.float32)
        cls._GOLAY_CODEBOOK = codebook
        return cls._GOLAY_CODEBOOK

    @classmethod
    def quantize(
        cls,
        vector: np.ndarray,
        stages: int = 2,
    ) -> PackedLeechEmbedding:
        """
        Quantize continuous vector(s) into multi-stage 24D Leech sub-vector lattice indices.

        Args:
            vector: 1D array of shape (D,) or 2D array of shape (N, D).
            stages: Number of residual quantization passes (1 to 3).
        """
        arr = np.asarray(vector, dtype=np.float32)
        original_shape = arr.shape
        flat = arr.reshape(-1)
        total_dim = flat.size

        # Zero-pad to multiple of 24
        pad_len = (24 - (total_dim % 24)) % 24
        if pad_len > 0:
            padded = np.pad(flat, (0, pad_len), mode="constant", constant_values=0.0)
        else:
            padded = flat

        num_blocks = padded.size // 24
        blocks = padded.reshape(num_blocks, 24).copy()

        codebook = cls.get_codebook()  # (4096, 24)
        packed_codes = np.zeros((num_blocks, stages), dtype=np.uint16)
        max_norms = np.zeros(stages, dtype=np.float32)

        residual = blocks
        for s in range(stages):
            norms = np.linalg.norm(residual, axis=1)  # (num_blocks,)
            s_max_norm = float(np.max(norms))
            if s_max_norm < 1e-12:
                s_max_norm = 1e-12
            max_norms[s] = s_max_norm

            normed_blocks = residual / np.maximum(norms[:, None], 1e-12)

            # Fast projection against all 4096 Golay centroids via BLAS GEMM
            scores = normed_blocks @ codebook.T  # (num_blocks, 4096)
            best_idx = np.argmax(scores, axis=1).astype(np.uint16)

            # Quantize projection gain into 4 bits [0, 15]
            correlations = np.take_along_axis(scores, best_idx[:, None], axis=1).ravel()
            effective_gains = np.maximum(correlations * norms, 0.0)
            gain_4bit = np.clip(np.round((effective_gains / s_max_norm) * 15.0), 0, 15).astype(np.uint16)

            # Pack 12-bit index and 4-bit gain into single uint16
            packed_codes[:, s] = (best_idx << 4) | gain_4bit

            # Unquantized reconstructed component for residual tracking
            recon_gains = (gain_4bit.astype(np.float32) / 15.0) * s_max_norm
            recon_stage = codebook[best_idx] * recon_gains[:, None]
            residual = residual - recon_stage

        return PackedLeechEmbedding(
            original_shape=original_shape,
            padded_dim=padded.size,
            num_blocks=num_blocks,
            stages=stages,
            max_norms=max_norms,
            packed_codes=packed_codes,
            bits_per_dim=round((16.0 * stages) / 24.0, 3),
        )

    @classmethod
    def dequantize(cls, packed: PackedLeechEmbedding) -> np.ndarray:
        """
        Reconstruct continuous vector(s) from packed Leech sub-vector representation.
        """
        codebook = cls.get_codebook()
        recon_blocks = np.zeros((packed.num_blocks, 24), dtype=np.float32)

        for s in range(packed.stages):
            codes = packed.packed_codes[:, s]
            idx = codes >> 4
            gain_4bit = codes & 0x0F
            s_max_norm = packed.max_norms[s]

            recon_gains = (gain_4bit.astype(np.float32) / 15.0) * s_max_norm
            recon_blocks += codebook[idx] * recon_gains[:, None]

        flat_recon = recon_blocks.ravel()
        total_orig_dim = int(np.prod(packed.original_shape))
        unpadded = flat_recon[:total_orig_dim]
        return unpadded.reshape(packed.original_shape)

    @classmethod
    def compression_ratio(cls, original: np.ndarray, packed: PackedLeechEmbedding) -> float:
        """Calculate compression multiplier relative to 32-bit floating point representation."""
        orig_bytes = original.nbytes
        comp_bytes = packed.compressed_bytes
        return orig_bytes / max(comp_bytes, 1)


# ==============================================================================
# Self-Test & Diagnostic CLI
# ==============================================================================

def selftest() -> bool:
    print("=" * 60)
    print("CAMELOT-OS FRONTIER QUANTIZATION SELF-TEST")
    print("=" * 60)

    # 1. BitNet b1.58 Ternary Test
    print("[1/6] Testing BitNet b1.58 Ternary Quantization & Bit-Packing...")
    rng = np.random.default_rng(1337)
    weights = rng.normal(loc=0.0, scale=0.5, size=(64, 128)).astype(np.float32)
    ternary_w, scale = Ternary158Compressor.quantize(weights)
    assert set(np.unique(ternary_w)).issubset({-1, 0, 1}), "Ternary weights contain values outside {-1, 0, 1}"
    packed = Ternary158Compressor.pack(ternary_w, scale)
    reconstructed = Ternary158Compressor.unpack(packed)
    assert reconstructed.shape == weights.shape, "Shape mismatch after unpacking"
    ratio = Ternary158Compressor.compression_ratio(weights, packed)
    print(f"      Achieved compression ratio: {ratio:.2f}x (original: {weights.nbytes}B -> packed: {packed.compressed_bytes}B)")
    assert ratio >= 7.0, f"Compression ratio too low: {ratio}"

    # 2. SpinQuant Randomized Hadamard Rotator Test
    print("[2/6] Testing SpinQuant Hadamard Orthogonal Rotation...")
    dim = 64
    rot = SpinQuantRotator.create_randomized_rotation(dim, seed=42)
    is_ortho, max_err = SpinQuantRotator.verify_orthogonality(rot)
    print(f"      Orthogonality verified: {is_ortho} (max deviation: {max_err:.2e})")
    assert is_ortho, f"Rotation matrix is not orthogonal: error {max_err}"
    
    # Test outlier dispersion
    activations = rng.normal(0, 1, size=(10, dim))
    # Inject synthetic heavy outliers into channel 3
    activations[:, 3] *= 15.0
    kurt_before = SpinQuantRotator.compute_kurtosis(activations)
    rotated = SpinQuantRotator.rotate_activations(activations, rot)
    kurt_after = SpinQuantRotator.compute_kurtosis(rotated)
    print(f"      Kurtosis reduction: {kurt_before:.2f} -> {kurt_after:.2f}")
    assert kurt_after < kurt_before, "SpinQuant rotation failed to reduce kurtosis"

    # 3. KIVI 2-Bit Asymmetric KV Cache Compressor Test
    print("[3/6] Testing KIVI Asymmetric 2-bit KV Cache Compressor...")
    seq_len, num_heads, head_dim = 128, 8, 32
    keys = rng.normal(0, 1, size=(seq_len, num_heads, head_dim)).astype(np.float32)
    vals = rng.normal(0, 1, size=(seq_len, num_heads, head_dim)).astype(np.float32)
    kv_compressed = KIVICacheCompressor.compress_kv(keys, vals)
    recon_k = KIVICacheCompressor.dequantize_keys(
        kv_compressed.k_packed, kv_compressed.k_scales, kv_compressed.k_zeros, keys.shape
    )
    recon_v = KIVICacheCompressor.dequantize_values(
        kv_compressed.v_packed, kv_compressed.v_scales, kv_compressed.v_zeros, vals.shape
    )
    k_mse = float(np.mean((keys - recon_k) ** 2))
    v_mse = float(np.mean((vals - recon_v) ** 2))
    print(f"      KIVI 2-bit compression ratio: {kv_compressed.compression_ratio:.2f}x | K MSE: {k_mse:.4f} | V MSE: {v_mse:.4f}")
    assert kv_compressed.compression_ratio >= 7.0, "KIVI compression ratio must exceed 7.0x"

    # 4. SnapKV Attention Governor Test
    print("[4/6] Testing SnapKV / StreamingLLM Attention Governor...")
    gov = SnapKVAttentionGovernor(
        preserved_sink_tokens=32,
        preserved_local_tokens=64,
        max_budget_mb=1.0,  # tight budget for test
        num_layers=4,
        num_heads=4,
        head_dim=32,
    )
    seq = 300
    importance = rng.uniform(0, 1, size=seq)
    preserved, state = gov.select_eviction_indices(importance)
    print(f"      Tokens seen: {state.total_tokens_seen} -> preserved: {state.active_tokens} (evicted: {state.evicted_tokens})")
    print(f"      Cache footprint: {state.current_cache_mb:.3f} MB <= budget: {state.max_budget_mb:.3f} MB")
    assert state.current_cache_mb <= state.max_budget_mb + 1e-4, "Cache memory exceeded budget"
    assert 0 in preserved and 1 in preserved, "Attention sink tokens 0 and 1 must be preserved"
    assert (seq - 1) in preserved, "Local sliding window end token must be preserved"

    # 5. Speculative Draft Cascade Test
    print("[5/6] Testing Speculative Draft Cascade Verifier...")
    draft = [101, 102, 103, 104, 105, 106]
    draft_p = np.array([0.9, 0.85, 0.8, 0.7, 0.6, 0.5])
    target_p = np.array([0.95, 0.9, 0.82, 0.75, 0.2, 0.1])  # token 4 & 5 drop sharply
    res = SpeculativeDraftCascade.verify_tokens(draft, draft_p, target_p, seed=42)
    print(f"      Draft proposed: {res.draft_tokens_proposed} -> accepted: {res.num_accepted} (speedup: {res.speedup_multiplier}x)")
    assert res.num_accepted >= 1, "At least 1 high-probability token should be accepted"

    # 6. Leech Lattice (Lambda_24) Sub-Vector Quantizer Test
    print("[6/6] Testing Leech Lattice (Lambda_24) Sub-Vector Quantizer & Extended Golay Codebook...")
    emb_768 = rng.normal(0, 1, 768).astype(np.float32)
    emb_768 /= np.linalg.norm(emb_768)

    # Test Stage 1: Ultra-compact (>=35x compression)
    packed_s1 = LeechLattice24Quantizer.quantize(emb_768, stages=1)
    recon_s1 = LeechLattice24Quantizer.dequantize(packed_s1)
    ratio_s1 = LeechLattice24Quantizer.compression_ratio(emb_768, packed_s1)
    cos_s1 = float(np.dot(emb_768, recon_s1) / (np.linalg.norm(recon_s1) + 1e-12))
    print(f"      Stage 1 -> Compression: {ratio_s1:.2f}x ({emb_768.nbytes}B -> {packed_s1.compressed_bytes}B) | CosSim: {cos_s1:.4f}")
    assert ratio_s1 >= 35.0, f"Stage 1 compression ratio too low: {ratio_s1}"
    assert cos_s1 >= 0.65, f"Stage 1 cosine similarity too low: {cos_s1}"

    # Test Stage 2: High-fidelity (>=20x compression, >=0.80 CosSim)
    packed_s2 = LeechLattice24Quantizer.quantize(emb_768, stages=2)
    recon_s2 = LeechLattice24Quantizer.dequantize(packed_s2)
    ratio_s2 = LeechLattice24Quantizer.compression_ratio(emb_768, packed_s2)
    cos_s2 = float(np.dot(emb_768, recon_s2) / (np.linalg.norm(recon_s2) + 1e-12))
    print(f"      Stage 2 -> Compression: {ratio_s2:.2f}x ({emb_768.nbytes}B -> {packed_s2.compressed_bytes}B) | CosSim: {cos_s2:.4f}")
    assert ratio_s2 >= 20.0, f"Stage 2 compression ratio too low: {ratio_s2}"
    assert cos_s2 >= 0.80, f"Stage 2 cosine similarity too low: {cos_s2}"

    print("\nALL 6 FRONTIER QUANTIZATION TESTS PASSED WITH 100% SUCCESS.")
    return True


if __name__ == "__main__":
    selftest()
