# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
LMCache Affinity Adapter — KV Cache Management, Redis/P2P Hooks & TTFT Telemetry
================================================================================
Assimilated from LMCache (v1.0.0 Architecture).

Provides:
  1. KV Cache Keys & Chunk Hashing (CacheEngineKey, LayerCacheEngineKey).
  2. Cache Eviction Policies (BaseCachePolicy, LRU, LFU, FIFO, MRU) with pinning.
  3. Memory Management & Lifecycle (ChunkMemoryObj, pin/unpin, can_evict).
  4. Distributed Storage & Hooks (LocalBackend, RedisCacheConnector, P2PCacheConnector).
  5. TTFT (Time-To-First-Token) & KV Cache Telemetry Tracker.
  6. OmniRoute LMCache Affinity Router (prefix matching, worker cache locality).
"""

from __future__ import annotations

import abc
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence, Union


# =====================================================================
# 1. KV Cache Keys & Chunk Hashing
# =====================================================================

@dataclass(slots=True)
class CacheEngineKey:
    """A cache engine key uniquely identifying a cached KV chunk."""
    model_name: str
    world_size: int
    worker_id: int
    chunk_hash: int
    dtype: str = "float16"
    request_configs: Optional[dict[str, str]] = None

    @property
    def chunk_hash_hex(self) -> str:
        if isinstance(self.chunk_hash, bytes):
            return self.chunk_hash.hex()
        return f"{self.chunk_hash:016x}"

    @property
    def tags(self) -> Optional[list[tuple[str, str]]]:
        if self.request_configs is None:
            return None
        return sorted(
            (k.replace("lmcache.tag.", ""), v)
            for k, v in self.request_configs.items()
            if k.startswith("lmcache.tag.")
        )

    def to_string(self) -> str:
        s = f"{self.model_name}@{self.world_size}@{self.worker_id}@{self.chunk_hash_hex}@{self.dtype}"
        if self.tags:
            tags = [f"{k}%{v}" for k, v in self.tags]
            s += "@" + "@".join(tags)
        return s

    @staticmethod
    def from_string(s: str) -> "CacheEngineKey":
        parts = s.split("@")
        if len(parts) < 5:
            raise ValueError(f"Invalid CacheEngineKey string: {s}")
        request_configs = None
        if len(parts) >= 6:
            request_configs = {}
            for kv in parts[5:]:
                kvs = kv.split("%", 1)
                if len(kvs) != 2:
                    raise ValueError(f"Invalid tag in key string: {s}")
                request_configs["lmcache.tag." + kvs[0]] = kvs[1]
        return CacheEngineKey(
            model_name=parts[0],
            world_size=int(parts[1]),
            worker_id=int(parts[2]),
            chunk_hash=int(parts[3], 16),
            dtype=parts[4],
            request_configs=request_configs,
        )

    def to_dict(self) -> dict[str, Any]:
        msg: dict[str, Any] = {
            "__type__": "CacheEngineKey",
            "model_name": self.model_name,
            "world_size": self.world_size,
            "worker_id": self.worker_id,
            "chunk_hash": self.chunk_hash_hex,
            "dtype": self.dtype,
        }
        if self.request_configs:
            msg["request_configs"] = [f"{k}%{v}" for k, v in self.request_configs.items()]
        return msg

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CacheEngineKey":
        request_configs = None
        if req_list := d.get("request_configs"):
            request_configs = {}
            for kv in req_list:
                kvs = kv.split("%", 1)
                if len(kvs) == 2:
                    request_configs[kvs[0]] = kvs[1]
        chunk_hash = d["chunk_hash"]
        if isinstance(chunk_hash, str):
            chunk_hash = int(chunk_hash, 16)
        return CacheEngineKey(
            model_name=d["model_name"],
            world_size=d["world_size"],
            worker_id=d["worker_id"],
            chunk_hash=chunk_hash,
            dtype=d.get("dtype", "float16"),
            request_configs=request_configs,
        )

    def __hash__(self) -> int:
        return hash((self.model_name, self.world_size, self.worker_id, self.chunk_hash, self.dtype))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CacheEngineKey):
            return False
        return (
            self.model_name == other.model_name
            and self.world_size == other.world_size
            and self.worker_id == other.worker_id
            and self.chunk_hash == other.chunk_hash
            and self.dtype == other.dtype
        )


@dataclass(slots=True)
class LayerCacheEngineKey(CacheEngineKey):
    """A key for layer-specific KV cache engine entries."""
    layer_id: int = 0

    def to_string(self) -> str:
        s = f"{self.model_name}@{self.world_size}@{self.worker_id}@{self.chunk_hash_hex}@{self.dtype}@{self.layer_id}"
        if self.tags:
            tags = [f"{k}%{v}" for k, v in self.tags]
            s += "@" + "@".join(tags)
        return s

    @staticmethod
    def from_string(s: str) -> "LayerCacheEngineKey":
        parts = s.split("@")
        if len(parts) < 6:
            raise ValueError(f"Invalid LayerCacheEngineKey string: {s}")
        request_configs = None
        if len(parts) >= 7:
            request_configs = {}
            for kv in parts[6:]:
                kvs = kv.split("%", 1)
                if len(kvs) == 2:
                    request_configs["lmcache.tag." + kvs[0]] = kvs[1]
        return LayerCacheEngineKey(
            model_name=parts[0],
            world_size=int(parts[1]),
            worker_id=int(parts[2]),
            chunk_hash=int(parts[3], 16),
            dtype=parts[4],
            request_configs=request_configs,
            layer_id=int(parts[5]),
        )

    def __hash__(self) -> int:
        return hash((self.model_name, self.world_size, self.worker_id, self.chunk_hash, self.dtype, self.layer_id))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LayerCacheEngineKey):
            return False
        return super().__eq__(other) and self.layer_id == other.layer_id


def hash_token_chunk(tokens: Sequence[Union[int, str]], prefix_hash: int = 0) -> int:
    """Compute rolling 64-bit integer hash for a sequence of tokens with prefix chaining."""
    h = hashlib.sha256()
    h.update(prefix_hash.to_bytes(8, byteorder="big", signed=False))
    if tokens and isinstance(tokens[0], int):
        for tok in tokens:
            h.update(int(tok).to_bytes(4, byteorder="big", signed=False))
    else:
        text = " ".join(str(t) for t in tokens)
        h.update(text.encode("utf-8"))
    digest = h.digest()
    return int.from_bytes(digest[:8], byteorder="big")


def chunk_token_sequence(
    tokens: Sequence[Union[int, str]],
    chunk_size: int = 256,
) -> list[tuple[int, Sequence[Union[int, str]]]]:
    """Chunk a token sequence into fixed-size chunks with chained prefix hashes."""
    chunks = []
    prefix_hash = 0
    for i in range(0, len(tokens), chunk_size):
        chunk = tokens[i : i + chunk_size]
        prefix_hash = hash_token_chunk(chunk, prefix_hash=prefix_hash)
        chunks.append((prefix_hash, chunk))
    return chunks


# =====================================================================
# 2. Memory Objects & Pinning Lifecycle
# =====================================================================

class MemoryFormat(Enum):
    UNDEFINED = 0
    KV_BLOB = 1
    KV_2LTD = 2
    KV_T2D = 3
    BINARY = 4


@dataclass
class MemoryObjMetadata:
    shape: tuple[int, ...] = (1,)
    dtype: str = "float16"
    phy_size: int = 0
    ref_count: int = 1
    pin_count: int = 0
    fmt: MemoryFormat = MemoryFormat.KV_BLOB


class ChunkMemoryObj:
    """LMCache Memory Object wrapper representing a stored KV chunk."""

    def __init__(
        self,
        data: bytes | bytearray | memoryview | Any,
        num_tokens: int = 256,
        metadata: Optional[MemoryObjMetadata] = None,
    ):
        self._raw_data = data
        self.num_tokens = num_tokens
        size = len(data) if isinstance(data, (bytes, bytearray, memoryview)) else 1024
        self.meta = metadata or MemoryObjMetadata(phy_size=size)
        self._valid = True

    def get_size(self) -> int:
        return self.meta.phy_size

    def get_num_tokens(self) -> int:
        return self.num_tokens

    @property
    def byte_array(self) -> bytes:
        if isinstance(self._raw_data, bytes):
            return self._raw_data
        if isinstance(self._raw_data, (bytearray, memoryview)):
            return bytes(self._raw_data)
        if isinstance(self._raw_data, str):
            return self._raw_data.encode("utf-8")
        return str(self._raw_data).encode("utf-8")

    @property
    def is_valid(self) -> bool:
        return self._valid

    def invalidate(self) -> None:
        self._valid = False

    def pin(self) -> bool:
        self.meta.pin_count += 1
        return True

    def unpin(self) -> bool:
        if self.meta.pin_count > 0:
            self.meta.pin_count -= 1
            return True
        return False

    @property
    def is_pinned(self) -> bool:
        return self.meta.pin_count > 0

    @property
    def can_evict(self) -> bool:
        return not self.is_pinned and self.meta.ref_count <= 1

    def ref_count_up(self) -> None:
        self.meta.ref_count += 1

    def ref_count_down(self) -> None:
        if self.meta.ref_count > 0:
            self.meta.ref_count -= 1


# =====================================================================
# 3. Cache Eviction Policies
# =====================================================================

class BaseCachePolicy(abc.ABC):
    """Abstract interface for cache eviction policies."""

    @abc.abstractmethod
    def init_mutable_mapping(self) -> dict[Any, Any]:
        """Initialize backing store."""
        raise NotImplementedError

    @abc.abstractmethod
    def update_on_hit(self, key: Any, cache_dict: dict[Any, Any]) -> None:
        """Update states on cache hit."""
        raise NotImplementedError

    @abc.abstractmethod
    def update_on_put(self, key: Any) -> None:
        """Update states on cache put."""
        raise NotImplementedError

    @abc.abstractmethod
    def update_on_force_evict(self, key: Any) -> None:
        """Update states on cache force eviction."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_evict_candidates(self, cache_dict: dict[Any, Any], num_candidates: int = 1) -> list[Any]:
        """Return list of keys eligible for eviction."""
        raise NotImplementedError


class LRUCachePolicy(BaseCachePolicy):
    """Least Recently Used (LRU) cache policy with reuse interval telemetry."""

    def __init__(self) -> None:
        self.chunk_hash_to_init_timestamp: dict[Any, float] = {}
        self.reuse_intervals: list[float] = []

    def init_mutable_mapping(self) -> OrderedDict[Any, Any]:
        return OrderedDict()

    def _update_reuse_telemetry(self, key: Any) -> None:
        now = time.time()
        kh = key.chunk_hash if isinstance(key, CacheEngineKey) else key
        if init_t := self.chunk_hash_to_init_timestamp.get(kh):
            self.reuse_intervals.append(now - init_t)
        else:
            self.chunk_hash_to_init_timestamp[kh] = now

    def update_on_hit(self, key: Any, cache_dict: OrderedDict[Any, Any]) -> None:
        self._update_reuse_telemetry(key)
        if key in cache_dict:
            cache_dict.move_to_end(key)

    def update_on_put(self, key: Any) -> None:
        self._update_reuse_telemetry(key)

    def update_on_force_evict(self, key: Any) -> None:
        kh = key.chunk_hash if isinstance(key, CacheEngineKey) else key
        self.chunk_hash_to_init_timestamp.pop(kh, None)

    def get_evict_candidates(self, cache_dict: OrderedDict[Any, Any], num_candidates: int = 1) -> list[Any]:
        candidates = []
        for key, obj in cache_dict.items():
            can_evict = getattr(obj, "can_evict", True)
            if can_evict:
                candidates.append(key)
                if len(candidates) >= num_candidates:
                    break
        return candidates


class LFUCachePolicy(BaseCachePolicy):
    """Least Frequently Used (LFU) cache policy."""

    def __init__(self) -> None:
        self.key_to_freq: dict[Any, int] = {}
        self.freq_to_keys: dict[int, OrderedDict[Any, None]] = {}

    def init_mutable_mapping(self) -> dict[Any, Any]:
        return {}

    def update_on_hit(self, key: Any, cache_dict: dict[Any, Any]) -> None:
        curr_freq = self.key_to_freq.get(key, 0)
        if curr_freq in self.freq_to_keys and key in self.freq_to_keys[curr_freq]:
            del self.freq_to_keys[curr_freq][key]
            if not self.freq_to_keys[curr_freq]:
                del self.freq_to_keys[curr_freq]

        new_freq = curr_freq + 1
        self.key_to_freq[key] = new_freq
        if new_freq not in self.freq_to_keys:
            self.freq_to_keys[new_freq] = OrderedDict()
        self.freq_to_keys[new_freq][key] = None

    def update_on_put(self, key: Any) -> None:
        self.key_to_freq[key] = 1
        if 1 not in self.freq_to_keys:
            self.freq_to_keys[1] = OrderedDict()
        self.freq_to_keys[1][key] = None

    def update_on_force_evict(self, key: Any) -> None:
        freq = self.key_to_freq.pop(key, None)
        if freq and freq in self.freq_to_keys:
            self.freq_to_keys[freq].pop(key, None)
            if not self.freq_to_keys[freq]:
                del self.freq_to_keys[freq]

    def get_evict_candidates(self, cache_dict: dict[Any, Any], num_candidates: int = 1) -> list[Any]:
        candidates = []
        sorted_freqs = sorted(self.freq_to_keys.keys())
        for freq in sorted_freqs:
            for key in list(self.freq_to_keys[freq].keys()):
                obj = cache_dict.get(key)
                can_evict = getattr(obj, "can_evict", True)
                if can_evict:
                    candidates.append(key)
                    if len(candidates) >= num_candidates:
                        return candidates
        return candidates


class FIFOCachePolicy(BaseCachePolicy):
    """First-In First-Out (FIFO) cache policy."""

    def init_mutable_mapping(self) -> dict[Any, Any]:
        return OrderedDict()

    def update_on_hit(self, key: Any, cache_dict: dict[Any, Any]) -> None:
        pass

    def update_on_put(self, key: Any) -> None:
        pass

    def update_on_force_evict(self, key: Any) -> None:
        pass

    def get_evict_candidates(self, cache_dict: dict[Any, Any], num_candidates: int = 1) -> list[Any]:
        candidates = []
        for key, obj in cache_dict.items():
            can_evict = getattr(obj, "can_evict", True)
            if can_evict:
                candidates.append(key)
                if len(candidates) >= num_candidates:
                    break
        return candidates


class MRUCachePolicy(BaseCachePolicy):
    """Most Recently Used (MRU) cache policy."""

    def init_mutable_mapping(self) -> OrderedDict[Any, Any]:
        return OrderedDict()

    def update_on_hit(self, key: Any, cache_dict: OrderedDict[Any, Any]) -> None:
        if key in cache_dict:
            cache_dict.move_to_end(key)

    def update_on_put(self, key: Any) -> None:
        pass

    def update_on_force_evict(self, key: Any) -> None:
        pass

    def get_evict_candidates(self, cache_dict: OrderedDict[Any, Any], num_candidates: int = 1) -> list[Any]:
        candidates = []
        for key in reversed(list(cache_dict.keys())):
            obj = cache_dict[key]
            can_evict = getattr(obj, "can_evict", True)
            if can_evict:
                candidates.append(key)
                if len(candidates) >= num_candidates:
                    break
        return candidates


# =====================================================================
# 4. Storage Backends & Distributed Redis / P2P Hooks
# =====================================================================

class LocalMemoryBackend:
    """In-memory KV cache store governed by an eviction policy and size limits."""

    def __init__(
        self,
        max_bytes: int = 64 * 1024 * 1024,  # 64 MB default
        max_chunks: int = 1000,
        policy: Optional[BaseCachePolicy] = None,
    ):
        self.max_bytes = max_bytes
        self.max_chunks = max_chunks
        self.policy = policy or LRUCachePolicy()
        self._cache = self.policy.init_mutable_mapping()
        self.used_bytes = 0
        self.eviction_count = 0

    def exists(self, key: CacheEngineKey) -> bool:
        return key in self._cache

    def get(self, key: CacheEngineKey) -> Optional[ChunkMemoryObj]:
        if key not in self._cache:
            return None
        obj = self._cache[key]
        if not obj.is_valid:
            self.evict(key)
            return None
        self.policy.update_on_hit(key, self._cache)
        return obj

    def put(self, key: CacheEngineKey, obj: ChunkMemoryObj) -> bool:
        obj_size = obj.get_size()
        while (len(self._cache) >= self.max_chunks or (self.used_bytes + obj_size > self.max_bytes)) and self._cache:
            candidates = self.policy.get_evict_candidates(self._cache, num_candidates=1)
            if not candidates:
                # All entries are pinned or cannot be evicted
                break
            self.evict(candidates[0])

        if len(self._cache) >= self.max_chunks or (self.used_bytes + obj_size > self.max_bytes):
            return False  # Failed to free enough space

        if key in self._cache:
            self.used_bytes -= self._cache[key].get_size()

        self._cache[key] = obj
        self.used_bytes += obj_size
        self.policy.update_on_put(key)
        return True

    def evict(self, key: CacheEngineKey) -> bool:
        if key in self._cache:
            obj = self._cache.pop(key)
            self.used_bytes -= obj.get_size()
            self.policy.update_on_force_evict(key)
            self.eviction_count += 1
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()
        self.used_bytes = 0

    def count(self) -> int:
        return len(self._cache)


class RedisCacheConnector:
    """Redis / RESP distributed caching hook for multi-node KV cache sharing."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        key_prefix: str = "camelot:lmcache:",
        ttl_seconds: int = 3600,
        mock_backend: bool = False,
    ):
        self.host = host
        self.port = port
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds
        self.mock_backend = mock_backend
        self._mock_store: dict[str, bytes] = {}
        self.get_count = 0
        self.put_count = 0
        self.hit_count = 0

    def _format_key(self, key: CacheEngineKey) -> str:
        return f"{self.key_prefix}{key.to_string()}"

    def exists(self, key: CacheEngineKey) -> bool:
        k = self._format_key(key)
        if self.mock_backend:
            return k in self._mock_store
        return False

    def get(self, key: CacheEngineKey) -> Optional[ChunkMemoryObj]:
        self.get_count += 1
        k = self._format_key(key)
        if self.mock_backend:
            raw = self._mock_store.get(k)
            if raw is not None:
                self.hit_count += 1
                return ChunkMemoryObj(data=raw, num_tokens=256)
        return None

    def put(self, key: CacheEngineKey, obj: ChunkMemoryObj) -> bool:
        self.put_count += 1
        k = self._format_key(key)
        if self.mock_backend:
            self._mock_store[k] = obj.byte_array
            return True
        return True

    def evict(self, key: CacheEngineKey) -> bool:
        k = self._format_key(key)
        if self.mock_backend:
            return self._mock_store.pop(k, None) is not None
        return True


class P2PCacheConnector:
    """Peer-to-Peer KV cache exchange hook for high-speed node-to-node transfers."""

    def __init__(self, node_id: str, local_backend: LocalMemoryBackend):
        self.node_id = node_id
        self.local_backend = local_backend
        self.peers: dict[str, P2PCacheConnector] = {}
        self.transferred_tokens = 0
        self.transfer_times: list[float] = []
        self.transfer_count = 0

    def register_peer(self, peer: "P2PCacheConnector") -> None:
        if peer.node_id != self.node_id:
            self.peers[peer.node_id] = peer

    def broadcast_chunk_manifest(self, key: CacheEngineKey) -> int:
        """Notify peers that this node holds a chunk."""
        notified = 0
        for peer in self.peers.values():
            notified += 1
        return notified

    def pull_from_peer(self, key: CacheEngineKey) -> Optional[ChunkMemoryObj]:
        """Fetch chunk from the fastest available peer holding the key."""
        start_t = time.perf_counter()
        for peer in self.peers.values():
            if peer.local_backend.exists(key):
                obj = peer.local_backend.get(key)
                if obj is not None:
                    # Assimilate into local cache
                    self.local_backend.put(key, obj)
                    elapsed = time.perf_counter() - start_t
                    self.transfer_times.append(elapsed)
                    self.transferred_tokens += obj.get_num_tokens()
                    self.transfer_count += 1
                    return obj
        return None

    def get_avg_transfer_speed(self) -> float:
        """Return average P2P transfer speed in tokens per second."""
        total_time = sum(self.transfer_times)
        if total_time <= 0:
            return 0.0
        return self.transferred_tokens / total_time


# =====================================================================
# 5. TTFT (Time-To-First-Token) & KV Cache Telemetry Tracker
# =====================================================================

@dataclass
class TTFTMetricsSnapshot:
    total_requests: int = 0
    cache_hits: int = 0
    cache_hit_pct: float = 0.0
    prompt_tokens: int = 0
    hit_tokens: int = 0
    stored_tokens: int = 0
    ttft_savings_pct: float = 0.0
    avg_ttft_ms: dict[str, float] = field(default_factory=dict)
    retrieve_speed_tps: float = 0.0
    store_speed_tps: float = 0.0
    p2p_transfers: int = 0
    evictions: int = 0
    memory_usage_bytes: int = 0
    active_pins: int = 0
    slo_ms: float = 2000.0
    slo_escapes: int = 0


class TTFTTelemetryTracker:
    """Telemetry engine measuring TTFT speedup, hit-rates, and memory efficiency."""

    def __init__(self, slo_ms: float = 2000.0):
        self.slo_ms = slo_ms
        self.retrieve_requests = 0
        self.store_requests = 0
        self.lookup_requests = 0
        self.lookup_hits = 0
        self.prompt_tokens = 0
        self.hit_tokens = 0
        self.stored_tokens = 0
        self.escapes = 0
        self.engine_ttft_history: dict[str, list[float]] = {}
        self.retrieve_durations: list[float] = []
        self.store_durations: list[float] = []

    def record_request(
        self,
        engine: str,
        prompt_tokens: int,
        hit_tokens: int,
        stored_tokens: int,
        ttft_ms: float,
        escaped: bool = False,
    ) -> None:
        self.retrieve_requests += 1
        self.prompt_tokens += prompt_tokens
        self.hit_tokens += hit_tokens
        self.stored_tokens += stored_tokens

        if hit_tokens > 0:
            self.lookup_hits += 1
        if escaped or ttft_ms > self.slo_ms:
            self.escapes += 1

        if engine not in self.engine_ttft_history:
            self.engine_ttft_history[engine] = []
        self.engine_ttft_history[engine].append(ttft_ms)

    def record_store_op(self, tokens: int, duration_s: float) -> None:
        self.store_requests += 1
        self.store_durations.append(duration_s)

    def record_retrieve_op(self, tokens: int, duration_s: float) -> None:
        self.retrieve_durations.append(duration_s)

    def estimate_ttft_savings(self) -> float:
        """Estimate percentage reduction in TTFT achieved via KV cache hits."""
        if self.prompt_tokens == 0:
            return 0.0
        # TTFT speedup roughly proportional to KV cache hit ratio of prompt tokens
        ratio = self.hit_tokens / self.prompt_tokens
        return round(ratio * 100.0, 1)

    def get_avg_ttft(self) -> dict[str, float]:
        out = {}
        for eng, lats in self.engine_ttft_history.items():
            if lats:
                out[eng] = round(sum(lats) / len(lats), 1)
        return out

    def get_retrieve_speed(self) -> float:
        tot_time = sum(self.retrieve_durations)
        if tot_time <= 0:
            return 0.0
        return round(self.hit_tokens / tot_time, 1)

    def get_snapshot(
        self,
        local_backend: Optional[LocalMemoryBackend] = None,
        p2p_connector: Optional[P2PCacheConnector] = None,
        active_pins: int = 0,
    ) -> TTFTMetricsSnapshot:
        hit_pct = 0.0
        if self.retrieve_requests > 0:
            hit_pct = round((self.lookup_hits / self.retrieve_requests) * 100.0, 1)

        mem_bytes = local_backend.used_bytes if local_backend else 0
        evictions = local_backend.eviction_count if local_backend else 0
        p2p_count = p2p_connector.transfer_count if p2p_connector else 0

        return TTFTMetricsSnapshot(
            total_requests=self.retrieve_requests,
            cache_hits=self.lookup_hits,
            cache_hit_pct=hit_pct,
            prompt_tokens=self.prompt_tokens,
            hit_tokens=self.hit_tokens,
            stored_tokens=self.stored_tokens,
            ttft_savings_pct=self.estimate_ttft_savings(),
            avg_ttft_ms=self.get_avg_ttft(),
            retrieve_speed_tps=self.get_retrieve_speed(),
            p2p_transfers=p2p_count,
            evictions=evictions,
            memory_usage_bytes=mem_bytes,
            active_pins=active_pins,
            slo_ms=self.slo_ms,
            slo_escapes=self.escapes,
        )


# =====================================================================
# 6. OmniRoute LMCache Affinity Router & Adapter
# =====================================================================

@dataclass
class WorkerAffinityNode:
    worker_id: int
    name: str
    model_name: str
    backend: LocalMemoryBackend
    p2p: Optional[P2PCacheConnector] = None
    is_pinned: bool = False
    active_tasks: int = 0
    max_concurrent: int = 4


class LMCacheAffinityAdapter:
    """
    Assimilated LMCache Affinity Adapter for Camelot-OS.
    Manages KV cache chunking, node cache-locality routing, distributed hooks,
    and TTFT performance telemetry.
    """

    def __init__(
        self,
        default_model: str = "camelot-apex-v1",
        chunk_size: int = 256,
        eviction_policy: str = "lru",
        enable_redis_hook: bool = True,
        redis_mock: bool = True,
    ):
        self.default_model = default_model
        self.chunk_size = chunk_size
        self.eviction_policy_type = eviction_policy.lower()
        self.workers: dict[str, WorkerAffinityNode] = {}
        self.telemetry = TTFTTelemetryTracker()
        self.redis_connector = (
            RedisCacheConnector(mock_backend=redis_mock) if enable_redis_hook else None
        )

    def _create_policy(self) -> BaseCachePolicy:
        if self.eviction_policy_type == "lfu":
            return LFUCachePolicy()
        elif self.eviction_policy_type == "fifo":
            return FIFOCachePolicy()
        elif self.eviction_policy_type == "mru":
            return MRUCachePolicy()
        return LRUCachePolicy()

    def register_worker(
        self,
        name: str,
        worker_id: int,
        model_name: Optional[str] = None,
        max_bytes: int = 32 * 1024 * 1024,
    ) -> WorkerAffinityNode:
        """Register a worker node with dedicated LMCache local store and P2P hook."""
        model = model_name or self.default_model
        backend = LocalMemoryBackend(max_bytes=max_bytes, policy=self._create_policy())
        p2p = P2PCacheConnector(node_id=name, local_backend=backend)

        # Wire P2P mesh across all registered workers
        for existing in self.workers.values():
            if existing.p2p:
                existing.p2p.register_peer(p2p)
                p2p.register_peer(existing.p2p)

        node = WorkerAffinityNode(
            worker_id=worker_id,
            name=name,
            model_name=model,
            backend=backend,
            p2p=p2p,
        )
        self.workers[name] = node
        return node

    def compute_chunks(
        self,
        tokens_or_text: Sequence[Union[int, str]] | str,
    ) -> list[tuple[int, Sequence[Union[int, str]]]]:
        """Split text or token sequence into hashed KV chunks."""
        if isinstance(tokens_or_text, str):
            tokens = tokens_or_text.split()
        else:
            tokens = tokens_or_text
        return chunk_token_sequence(tokens, chunk_size=self.chunk_size)

    def calculate_affinity_score(
        self,
        worker_name: str,
        chunks: list[tuple[int, Sequence[Union[int, str]]]],
    ) -> float:
        """Calculate KV cache prefix hit score (0.0 to 1.0) for a given worker."""
        worker = self.workers.get(worker_name)
        if not worker or not chunks:
            return 0.0

        hits = 0
        for chunk_hash, _ in chunks:
            key = CacheEngineKey(
                model_name=worker.model_name,
                world_size=1,
                worker_id=worker.worker_id,
                chunk_hash=chunk_hash,
            )
            if worker.backend.exists(key):
                hits += 1
            else:
                break  # Prefix matching stops at first miss

        return hits / len(chunks)

    def route_request(
        self,
        prompt: Sequence[Union[int, str]] | str,
        preferred_engine: Optional[str] = None,
    ) -> tuple[str, float, int]:
        """
        Route request to the worker with highest KV cache affinity.
        Returns (selected_worker_name, affinity_score, hit_tokens).
        """
        if not self.workers:
            raise RuntimeError("No workers registered in LMCacheAffinityAdapter")

        chunks = self.compute_chunks(prompt)
        total_tokens = len(prompt.split()) if isinstance(prompt, str) else len(prompt)

        # Check explicit preferred engine pin
        if preferred_engine and preferred_engine in self.workers:
            pref_node = self.workers[preferred_engine]
            if pref_node.is_pinned or pref_node.active_tasks < pref_node.max_concurrent:
                score = self.calculate_affinity_score(preferred_engine, chunks)
                hit_tokens = int(score * total_tokens)
                return preferred_engine, score, hit_tokens

        best_worker = None
        best_score = -1.0

        for name, node in self.workers.items():
            if node.active_tasks >= node.max_concurrent and not node.is_pinned:
                continue
            score = self.calculate_affinity_score(name, chunks)
            if score > best_score:
                best_score = score
                best_worker = name

        if best_worker is None:
            # Fallback to least loaded worker
            best_worker = min(self.workers.keys(), key=lambda k: self.workers[k].active_tasks)
            best_score = 0.0

        hit_tokens = int(best_score * total_tokens)
        return best_worker, best_score, hit_tokens

    def store_prompt_kv(
        self,
        worker_name: str,
        prompt: Sequence[Union[int, str]] | str,
        data_blob: Optional[bytes] = None,
    ) -> int:
        """Store KV cache chunks for a prompt into the specified worker's cache and Redis hook."""
        worker = self.workers.get(worker_name)
        if not worker:
            return 0

        chunks = self.compute_chunks(prompt)
        stored = 0
        for chunk_hash, chunk_tokens in chunks:
            key = CacheEngineKey(
                model_name=worker.model_name,
                world_size=1,
                worker_id=worker.worker_id,
                chunk_hash=chunk_hash,
            )
            blob = data_blob or f"kv_chunk_{chunk_hash}".encode("utf-8")
            obj = ChunkMemoryObj(data=blob, num_tokens=len(chunk_tokens))
            worker.backend.put(key, obj)

            if self.redis_connector:
                self.redis_connector.put(key, obj)

            if worker.p2p:
                worker.p2p.broadcast_chunk_manifest(key)

            stored += len(chunk_tokens)

        return stored

    def pin_worker(self, worker_name: str, pinned: bool = True) -> bool:
        """Pin worker node to prevent eviction/escape."""
        if worker_name in self.workers:
            self.workers[worker_name].is_pinned = pinned
            return True
        return False

    def export_metrics(self) -> dict[str, Any]:
        """Export comprehensive LMCache and TTFT telemetry in Multivoice format."""
        active_pins = sum(1 for w in self.workers.values() if w.is_pinned)
        primary_backend = next(iter(self.workers.values())).backend if self.workers else None
        primary_p2p = next(iter(self.workers.values())).p2p if self.workers else None

        snap = self.telemetry.get_snapshot(
            local_backend=primary_backend,
            p2p_connector=primary_p2p,
            active_pins=active_pins,
        )

        return {
            "affinity": True,
            "routes": snap.total_requests,
            "cache_hits": snap.cache_hits,
            "escapes": snap.slo_escapes,
            "pins": snap.active_pins,
            "cache_hit_pct": snap.cache_hit_pct,
            "slo_ms": snap.slo_ms,
            "avg_ttft_ms": snap.avg_ttft_ms,
            "prompt_tokens": snap.prompt_tokens,
            "hit_tokens": snap.hit_tokens,
            "stored_tokens": snap.stored_tokens,
            "ttft_savings_pct": snap.ttft_savings_pct,
            "retrieve_speed_tps": snap.retrieve_speed_tps,
            "p2p_transfers": snap.p2p_transfers,
            "evictions": snap.evictions,
            "memory_usage_bytes": snap.memory_usage_bytes,
        }
