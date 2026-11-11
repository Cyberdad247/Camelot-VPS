# SPDX-License-Identifier: MIT

"""
Bifrost Integration — Deep system integration during QR Pill bootstrap.

# HITL: file-ops pre-approved — writes bounded to runtime state (pill config, logs)

On pill activation:
  1. System analyzer scans host capabilities
  2. Bifrost integration layer activates
  3. Self-optimizer configures CAMELOT-OS for this system
  4. Forge rebuilds/customizes based on analysis
  5. Ledger tracks all optimizations
  6. Continuous monitoring + adaptive optimization

Result: CAMELOT-OS reports a governed integration status; unimplemented forge steps remain planned.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from control_plane.system_analyzer import (
    GPUType,
    StorageType,
    SystemAnalyzer,
    SystemProfile,
)

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
BIFROST_RUNTIME_DIR = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "bifrost"


@dataclass
class OptimizationProfile:
    """Optimization configuration for this system."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    system_profile: Optional[SystemProfile] = None

    # CPU optimizations
    enable_multithreading: bool = False
    thread_pool_size: int = 1
    enable_avx: bool = False
    enable_sse: bool = False
    enable_neon: bool = False

    # GPU optimizations
    gpu_type: str = "none"
    enable_gpu_acceleration: bool = False
    gpu_memory_pool_mb: int = 0
    cuda_device_id: int = 0

    # Memory optimizations
    cache_size_mb: int = 256
    memory_pool_gb: float = 0.5
    enable_memory_compression: bool = False

    # Storage optimizations
    storage_type: str = "hdd"
    enable_ssd_optimization: bool = False
    prefetch_depth: int = 1
    io_batch_size: int = 16

    # Network optimizations
    enable_http2: bool = True
    enable_http3: bool = False
    enable_websocket: bool = True
    bandwidth_mbps: float = 100.0

    # Feature flags
    enable_redis: bool = False
    enable_qdrant: bool = False
    enable_pytorch: bool = False
    enable_tensorflow: bool = False

    # Scaling
    replica_count: int = 1
    worker_processes: int = 1
    async_workers: int = 4

    # Performance tier
    performance_tier: str = "standard"

    # Applied optimizations (ledger)
    applied_optimizations: List[str] = field(default_factory=list)


class BifrostIntegration:
    """Bifrost bridge integration for QR Pill bootstrap."""

    def __init__(self):
        """Initialize Bifrost integration."""
        self.analyzer = SystemAnalyzer()
        self.optimization_profile: Optional[OptimizationProfile] = None
        self.is_integrated = False
        self.integration_status = "NOT_STARTED"
        self.optimization_ledger: List[str] = []

    async def integrate(self, pill_id: str) -> bool:
        """Integrate with Bifrost bridge during pill bootstrap."""
        self.is_integrated = False
        self.integration_status = "IN_PROGRESS"
        self.optimization_ledger.clear()
        try:
            system_profile = await self.analyzer.analyze()
            print(f"[BIFROST] System analyzed: {system_profile.performance_tier} tier")

            opt_profile = await self._generate_optimization_profile(system_profile)
            self.optimization_profile = opt_profile

            if not await self._apply_optimizations(pill_id):
                self.integration_status = "FAILED"
                self.optimization_ledger.append("✗ Optimization profile was not prepared")
                await self._log_integration(pill_id)
                return False
            if not await self._configure_bifrost(opt_profile):
                self.integration_status = "FAILED"
                await self._log_integration(pill_id)
                return False
            if not await self._forge_camelot_os(opt_profile):
                self.integration_status = "PARTIAL"
                await self._log_integration(pill_id)
                return False

            self.is_integrated = True
            self.integration_status = "INTEGRATED"
            await self._log_integration(pill_id)
            return True

        except Exception as e:
            self.is_integrated = False
            self.integration_status = "FAILED"
            print(f"[BIFROST] Integration failed: {e}")
            return False

    async def _generate_optimization_profile(
        self, system_profile: SystemProfile
    ) -> OptimizationProfile:
        """Generate optimization profile from system analysis."""
        opt = OptimizationProfile(system_profile=system_profile)

        # CPU optimizations
        if system_profile.cpu.cores >= 4:
            opt.enable_multithreading = True
            opt.thread_pool_size = max(system_profile.cpu.cores - 1, 2)
        else:
            opt.thread_pool_size = 1

        opt.enable_avx = system_profile.cpu.has_avx
        opt.enable_sse = system_profile.cpu.has_sse
        opt.enable_neon = system_profile.cpu.has_neon

        # GPU optimizations
        if system_profile.gpu.type != GPUType.NONE and system_profile.gpu.type != GPUType.WASM:
            opt.enable_gpu_acceleration = True
            opt.gpu_type = system_profile.gpu.type.value
            opt.gpu_memory_pool_mb = int(system_profile.gpu.vram_gb * 1024 * 0.8)  # Use 80%

        # Memory optimizations
        total_ram_gb = system_profile.memory.total_gb
        if total_ram_gb >= 32:
            opt.cache_size_mb = 4096
            opt.memory_pool_gb = 8.0
            opt.replica_count = 2
        elif total_ram_gb >= 16:
            opt.cache_size_mb = 2048
            opt.memory_pool_gb = 4.0
        elif total_ram_gb >= 8:
            opt.cache_size_mb = 1024
            opt.memory_pool_gb = 2.0
        elif total_ram_gb >= 4:
            opt.cache_size_mb = 512
            opt.memory_pool_gb = 1.0
            opt.enable_memory_compression = True
        else:
            opt.cache_size_mb = 256
            opt.memory_pool_gb = 0.5
            opt.enable_memory_compression = True

        # Storage optimizations
        opt.storage_type = system_profile.storage.type.value
        if system_profile.storage.type == StorageType.NVME:
            opt.enable_ssd_optimization = True
            opt.io_batch_size = 64
            opt.prefetch_depth = 4
        elif system_profile.storage.type == StorageType.SSD:
            opt.enable_ssd_optimization = True
            opt.io_batch_size = 32
            opt.prefetch_depth = 2
        else:
            opt.io_batch_size = 16
            opt.prefetch_depth = 1

        # Network optimizations
        opt.enable_http2 = system_profile.network.supports_http2
        opt.enable_http3 = system_profile.network.supports_http3
        opt.enable_websocket = system_profile.network.supports_websocket

        # Feature flags based on installed packages
        opt.enable_redis = system_profile.python.has_redis
        opt.enable_qdrant = system_profile.python.has_qdrant
        opt.enable_pytorch = system_profile.python.has_torch
        opt.enable_tensorflow = system_profile.python.has_tensorflow

        # Performance tier
        opt.performance_tier = system_profile.performance_tier

        # Worker scaling
        if system_profile.performance_tier == "hpc":
            opt.worker_processes = system_profile.cpu.cores
            opt.async_workers = system_profile.cpu.cores * 2
        elif system_profile.performance_tier == "performance":
            opt.worker_processes = max(system_profile.cpu.cores // 2, 2)
            opt.async_workers = system_profile.cpu.cores
        else:
            opt.worker_processes = 1
            opt.async_workers = 4

        return opt

    async def _apply_optimizations(self, pill_id: str) -> bool:
        """Prepare an optimization profile for downstream configuration."""
        if not self.optimization_profile:
            return False

        opt = self.optimization_profile
        ledger = []

        if opt.enable_multithreading:
            ledger.append(f"↪ planned: CPU multithreading ({opt.thread_pool_size} threads)")
        if opt.enable_avx:
            ledger.append("↪ planned: CPU AVX vector optimization")
        if opt.enable_sse:
            ledger.append("↪ planned: CPU SSE optimization")
        if opt.enable_neon:
            ledger.append("↪ planned: CPU NEON optimization (ARM)")

        if opt.enable_gpu_acceleration:
            ledger.append(f"↪ planned: GPU {opt.gpu_type} acceleration ({opt.gpu_memory_pool_mb}MB)")
        else:
            ledger.append("↪ planned: GPU CPU-only mode")

        ledger.append(f"↪ planned: memory cache ({opt.cache_size_mb}MB)")
        if opt.enable_memory_compression:
            ledger.append("↪ planned: memory compression for edge devices")

        ledger.append(f"↪ planned: storage {opt.storage_type.upper()} optimization")
        if opt.enable_ssd_optimization:
            ledger.append(f"↪ planned: SSD prefetch depth={opt.prefetch_depth}")

        if opt.enable_http2:
            ledger.append("↪ planned: HTTP/2")
        if opt.enable_websocket:
            ledger.append("↪ planned: WebSocket")

        if opt.enable_redis:
            ledger.append("↪ planned: Redis L1 cache")
        if opt.enable_qdrant:
            ledger.append("↪ planned: Qdrant L2 search")
        if opt.enable_pytorch:
            ledger.append("↪ planned: PyTorch ML")

        if opt.worker_processes > 1:
            ledger.append(f"↪ planned: {opt.worker_processes} worker processes")
        ledger.append(f"↪ planned: {opt.async_workers} async workers")

        opt.applied_optimizations = ledger
        self.optimization_ledger.extend(ledger)
        return True

    async def _configure_bifrost(self, opt: OptimizationProfile) -> bool:
        """Configure Bifrost bridge for optimizations."""
        try:
            config = {
                "multithreading": opt.enable_multithreading,
                "thread_pool_size": opt.thread_pool_size,
                "gpu_enabled": opt.enable_gpu_acceleration,
                "gpu_type": opt.gpu_type,
                "gpu_memory_pool_mb": opt.gpu_memory_pool_mb,
                "cache_size_mb": opt.cache_size_mb,
                "memory_pool_gb": opt.memory_pool_gb,
                "storage_type": opt.storage_type,
                "enable_ssd_optimization": opt.enable_ssd_optimization,
                "http2": opt.enable_http2,
                "websocket": opt.enable_websocket,
                "redis_enabled": opt.enable_redis,
                "qdrant_enabled": opt.enable_qdrant,
                "pytorch_enabled": opt.enable_pytorch,
                "worker_processes": opt.worker_processes,
                "async_workers": opt.async_workers,
                "performance_tier": opt.performance_tier,
            }

            # Write config to Bifrost
            config_path = BIFROST_RUNTIME_DIR / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            import json
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            self.optimization_ledger.append(f"✓ Bifrost: Configuration written to {config_path}")
            return True
        except Exception as e:
            self.optimization_ledger.append(f"✗ Bifrost: Config failed: {e}")
            return False

    async def _forge_camelot_os(self, opt: OptimizationProfile) -> bool:
        """Self-forge CAMELOT-OS based on system profile."""
        try:
            forge_steps = []

            # Step 1: Customize main.py
            forge_steps.append("Forging main.py...")
            await self._forge_main_py(opt)
            self.optimization_ledger.append("↪ planned (no-op): main.py")

            # Step 2: Customize bifrost.py
            forge_steps.append("Forging bifrost.py...")
            await self._forge_bifrost_py(opt)
            self.optimization_ledger.append("↪ planned (no-op): bifrost.py")

            # Step 3: Customize knight_knowledgebase.py
            forge_steps.append("Forging knight_knowledgebase.py...")
            await self._forge_knight_brain(opt)
            self.optimization_ledger.append("↪ planned (no-op): knight_knowledgebase.py")

            # Step 4: Customize memory pyramid
            forge_steps.append("Forging memory pyramid...")
            await self._forge_memory_pyramid(opt)
            self.optimization_ledger.append("↪ planned (no-op): memory pyramid")

            # Step 5: Customize distance travel
            forge_steps.append("Forging distance travel...")
            await self._forge_distance_travel(opt)
            self.optimization_ledger.append("↪ planned (no-op): distance travel")

            # Step 6: Generate system-specific startup scripts
            forge_steps.append("Generating startup scripts...")
            if not await self._forge_startup_scripts(opt):
                return False
            self.optimization_ledger.append("✓ Generated: startup scripts")
            self.optimization_ledger.append("↪ partial: forge plan contains no-op steps")
            return False
        except Exception as e:
            self.optimization_ledger.append(f"✗ Forge failed: {e}")
            return False

    async def _forge_main_py(self, opt: OptimizationProfile) -> bool:
        """Customize main.py for system."""
        # Would customize startup parameters, thread pool, etc.
        return True

    async def _forge_bifrost_py(self, opt: OptimizationProfile) -> bool:
        """Customize bifrost.py for system."""
        # Would customize dispatch pool, caching, etc.
        return True

    async def _forge_knight_brain(self, opt: OptimizationProfile) -> bool:
        """Customize Knight brain for system."""
        # Would optimize knowledge base caching, vector search, etc.
        return True

    async def _forge_memory_pyramid(self, opt: OptimizationProfile) -> bool:
        """Customize memory pyramid (Redis/Qdrant/CloudBrain)."""
        if opt.enable_redis:
            self.optimization_ledger.append("  ↪ planned (no-op): Redis L1 cache")
        if opt.enable_qdrant:
            self.optimization_ledger.append("  ↪ planned (no-op): Qdrant L2 search")
        self.optimization_ledger.append("  ↪ planned (no-op): CloudBrain L3 synthesis")
        return True

    async def _forge_distance_travel(self, opt: OptimizationProfile) -> bool:
        """Customize distance travel for system."""
        self.optimization_ledger.append(f"  ↪ planned (no-op): agent pool ({opt.async_workers} workers)")
        self.optimization_ledger.append("  ↪ planned (no-op): consensus voting")
        self.optimization_ledger.append(f"  ↪ planned (no-op): memory sync for {opt.storage_type}")
        return True

    async def _forge_startup_scripts(self, opt: OptimizationProfile) -> bool:
        """Generate system-specific startup scripts."""
        script = self._generate_startup_script(opt)
        script_path = BIFROST_RUNTIME_DIR / "startup.sh"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, "w") as f:
            f.write(script)
        script_path.chmod(0o700)
        self.optimization_ledger.append(f"✓ Startup script: {script_path}")
        return True

    def _generate_startup_script(self, opt: OptimizationProfile) -> str:
        """Generate startup script."""
        return f"""#!/bin/bash
# CAMELOT-OS Startup Script (auto-generated for {opt.performance_tier} system)

# CPU optimization
export OPENBLAS_NUM_THREADS={opt.thread_pool_size}
export MKL_NUM_THREADS={opt.thread_pool_size}
export OMP_NUM_THREADS={opt.thread_pool_size}

# GPU optimization
{"export CUDA_DEVICE_ORDER=PCI_BUS_ID" if opt.enable_gpu_acceleration else "# GPU disabled"}
export CUDA_VISIBLE_DEVICES={opt.cuda_device_id if opt.enable_gpu_acceleration else ""}

# Memory optimization
export MALLOC_TRIM_THRESHOLD_={1024 * 1024}

# Start CAMELOT-OS
python -m control_plane.main \\
    --workers {opt.worker_processes} \\
    --async-workers {opt.async_workers} \\
    --cache-size-mb {opt.cache_size_mb} \\
    --memory-pool-gb {opt.memory_pool_gb} \\
    --performance-tier {opt.performance_tier} \\
    --enable-gpu {str(opt.enable_gpu_acceleration).lower()} \\
    --gpu-type {opt.gpu_type}
"""

    async def _log_integration(self, pill_id: str, status: str | None = None) -> None:
        """Log integration state to the governed runtime directory."""
        ledger_path = BIFROST_RUNTIME_DIR / "integration_ledger.md"
        profile = self.optimization_profile
        system_profile = profile.system_profile if profile else None
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = f"""
## QR Pill Integration: {pill_id}
**Timestamp**: {timestamp}
**Status**: {status or self.integration_status}

### System Profile
- Performance Tier: {profile.performance_tier.upper() if profile else 'unknown'}
- CPU: {system_profile.cpu.cores if system_profile else 'unknown'} cores
- RAM: {system_profile.memory.total_gb if system_profile else 'unknown'} GB
- Storage: {profile.storage_type if profile else 'unknown'}
- GPU: {profile.gpu_type if profile else 'none'}

### Planned and Applied Changes
"""
        for opt in self.optimization_ledger:
            entry += f"- {opt}\n"

        entry += "\n"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(entry)

    def get_optimization_summary(self) -> str:
        """Get optimization summary."""
        if not self.optimization_profile:
            return "No optimization profile"

        opt = self.optimization_profile
        return f"""
Bifrost Integration Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Performance Tier: {opt.performance_tier.upper()}

CPU:
  Multithreading: {opt.enable_multithreading} ({opt.thread_pool_size} threads)
  AVX: {opt.enable_avx}
  SSE: {opt.enable_sse}

GPU:
  Enabled: {opt.enable_gpu_acceleration}
  Type: {opt.gpu_type}
  Memory: {opt.gpu_memory_pool_mb} MB

Memory:
  Cache: {opt.cache_size_mb} MB
  Pool: {opt.memory_pool_gb} GB
  Compression: {opt.enable_memory_compression}

Storage:
  Type: {opt.storage_type}
  SSD Optimization: {opt.enable_ssd_optimization}
  I/O Batch: {opt.io_batch_size}

Scaling:
  Worker Processes: {opt.worker_processes}
  Async Workers: {opt.async_workers}
  Replicas: {opt.replica_count}

Features:
  Redis: {opt.enable_redis}
  Qdrant: {opt.enable_qdrant}
  PyTorch: {opt.enable_pytorch}

Planned Optimizations: {len(opt.applied_optimizations)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# ── Module-level singleton ────────────────────────────────────────────────

_bifrost: Optional[BifrostIntegration] = None


def get_bifrost_integration() -> BifrostIntegration:
    """Get or create shared BifrostIntegration instance."""
    global _bifrost
    if _bifrost is None:
        _bifrost = BifrostIntegration()
    return _bifrost


async def integrate_with_bifrost(pill_id: str) -> bool:
    """Integrate pill with Bifrost bridge."""
    bifrost = get_bifrost_integration()
    return await bifrost.integrate(pill_id)
