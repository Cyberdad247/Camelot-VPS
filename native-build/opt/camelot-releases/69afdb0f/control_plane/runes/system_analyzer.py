# SPDX-License-Identifier: MIT

"""
System Analyzer — Scan host system capabilities and constraints.

On QR Pill activation, analyzes:
  - CPU: cores, architecture, extensions (AVX, SSE, etc.)
  - RAM: available, type, speed
  - GPU: NVIDIA, AMD, Intel, WASM (fallback)
  - Storage: type (SSD/HDD), capacity, I/O speed
  - Network: bandwidth, latency, protocol support
  - OS: Linux/Windows/Mac, kernel version, container support
  - Python: version, available packages, performance

Outputs optimization profile for Bifrost to use.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import psutil


class CPUArchitecture(str, Enum):
    """CPU architecture types."""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    ARM32 = "arm32"
    UNKNOWN = "unknown"


class StorageType(str, Enum):
    """Storage device types."""
    SSD = "ssd"
    HDD = "hdd"
    NVME = "nvme"
    UNKNOWN = "unknown"


class GPUType(str, Enum):
    """GPU types."""
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    APPLE = "apple"
    WASM = "wasm"  # WebAssembly fallback
    NONE = "none"


@dataclass
class CPUProfile:
    """CPU system profile."""
    architecture: CPUArchitecture = CPUArchitecture.UNKNOWN
    cores: int = 1
    threads: int = 1
    freq_current_ghz: float = 0.0
    freq_max_ghz: float = 0.0
    has_avx: bool = False
    has_sse: bool = False
    has_neon: bool = False
    vendor: str = ""
    model: str = ""


@dataclass
class MemoryProfile:
    """Memory system profile."""
    total_gb: float = 0.0
    available_gb: float = 0.0
    percent_used: float = 0.0
    type: str = "ddr4"  # ddr4, ddr5, ddr3, lpddr, etc.
    speed_mhz: int = 0


@dataclass
class StorageProfile:
    """Storage system profile."""
    type: StorageType = StorageType.UNKNOWN
    total_gb: float = 0.0
    free_gb: float = 0.0
    read_speed_mbps: float = 0.0
    write_speed_mbps: float = 0.0
    io_ops_per_sec: int = 0


@dataclass
class GPUProfile:
    """GPU system profile."""
    type: GPUType = GPUType.NONE
    model: str = ""
    vram_gb: float = 0.0
    compute_capability: str = ""  # For NVIDIA: 8.6, 7.0, etc.
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None


@dataclass
class NetworkProfile:
    """Network system profile."""
    bandwidth_mbps: float = 0.0
    latency_ms: float = 0.0
    ipv4_enabled: bool = True
    ipv6_enabled: bool = False
    supports_http2: bool = True
    supports_http3: bool = False
    supports_websocket: bool = True


@dataclass
class OSProfile:
    """Operating system profile."""
    name: str = ""
    version: str = ""
    architecture: str = ""
    supports_docker: bool = False
    supports_gpu: bool = False
    supports_avx: bool = False
    supports_neon: bool = False


@dataclass
class PythonProfile:
    """Python runtime profile."""
    version: str = ""
    implementation: str = "cpython"  # cpython, pypy, etc.
    has_numpy: bool = False
    has_torch: bool = False
    has_tensorflow: bool = False
    has_onnx: bool = False
    has_redis: bool = False
    has_qdrant: bool = False


@dataclass
class SystemProfile:
    """Complete system profile."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cpu: CPUProfile = field(default_factory=CPUProfile)
    memory: MemoryProfile = field(default_factory=MemoryProfile)
    storage: StorageProfile = field(default_factory=StorageProfile)
    gpu: GPUProfile = field(default_factory=GPUProfile)
    network: NetworkProfile = field(default_factory=NetworkProfile)
    os: OSProfile = field(default_factory=OSProfile)
    python: PythonProfile = field(default_factory=PythonProfile)
    performance_tier: str = "unknown"  # edge, standard, performance, hpc
    optimization_hints: List[str] = field(default_factory=list)


class SystemAnalyzer:
    """Analyze host system capabilities."""

    def __init__(self):
        """Initialize analyzer."""
        self.profile: Optional[SystemProfile] = None

    async def analyze(self) -> SystemProfile:
        """Run complete system analysis."""
        profile = SystemProfile()

        # Analyze each subsystem
        profile.cpu = await self._analyze_cpu()
        profile.memory = await self._analyze_memory()
        profile.storage = await self._analyze_storage()
        profile.gpu = await self._analyze_gpu()
        profile.network = await self._analyze_network()
        profile.os = await self._analyze_os()
        profile.python = await self._analyze_python()

        # Determine performance tier
        profile.performance_tier = self._determine_tier(profile)

        # Generate optimization hints
        profile.optimization_hints = self._generate_hints(profile)

        self.profile = profile
        return profile

    async def _analyze_cpu(self) -> CPUProfile:
        """Analyze CPU."""
        cpu = CPUProfile()

        try:
            cpu.cores = psutil.cpu_count(logical=False) or 1
            cpu.threads = psutil.cpu_count(logical=True) or 1
            cpu.freq_current_ghz = psutil.cpu_freq().current / 1000 if psutil.cpu_freq() else 0
            cpu.freq_max_ghz = psutil.cpu_freq().max / 1000 if psutil.cpu_freq() else 0

            # Detect architecture
            machine = platform.machine().lower()
            if "x86_64" in machine or "amd64" in machine:
                cpu.architecture = CPUArchitecture.X86_64
            elif "aarch64" in machine or "arm64" in machine:
                cpu.architecture = CPUArchitecture.ARM64
            elif "armv7" in machine or "armhf" in machine:
                cpu.architecture = CPUArchitecture.ARM32
            else:
                cpu.architecture = CPUArchitecture.UNKNOWN

            # Detect CPU extensions (basic detection)
            cpu.has_avx = self._check_avx()
            cpu.has_sse = self._check_sse()
            cpu.has_neon = self._check_neon()

            # Detect vendor/model
            cpu.vendor = platform.processor()
        except Exception:
            pass

        return cpu

    async def _analyze_memory(self) -> MemoryProfile:
        """Analyze memory."""
        memory = MemoryProfile()

        try:
            vm = psutil.virtual_memory()
            memory.total_gb = vm.total / (1024**3)
            memory.available_gb = vm.available / (1024**3)
            memory.percent_used = vm.percent
        except Exception:
            pass

        return memory

    async def _analyze_storage(self) -> StorageProfile:
        """Analyze storage."""
        storage = StorageProfile()

        try:
            disk = psutil.disk_usage("/")
            storage.total_gb = disk.total / (1024**3)
            storage.free_gb = disk.free / (1024**3)

            # Detect storage type (simplified)
            if "nvme" in str(disk).lower():
                storage.type = StorageType.NVME
            elif "ssd" in str(disk).lower():
                storage.type = StorageType.SSD
            else:
                storage.type = StorageType.HDD
        except Exception:
            pass

        return storage

    async def _analyze_gpu(self) -> GPUProfile:
        """Analyze GPU."""
        gpu = GPUProfile()

        try:
            # Try to detect NVIDIA GPU
            nvidia_gpu = self._detect_nvidia_gpu()
            if nvidia_gpu:
                gpu.type = GPUType.NVIDIA
                gpu.model = nvidia_gpu.get("model", "")
                gpu.vram_gb = nvidia_gpu.get("vram_gb", 0)
                gpu.cuda_version = nvidia_gpu.get("cuda_version")
                return gpu

            # Try to detect AMD GPU
            amd_gpu = self._detect_amd_gpu()
            if amd_gpu:
                gpu.type = GPUType.AMD
                gpu.model = amd_gpu.get("model", "")
                gpu.vram_gb = amd_gpu.get("vram_gb", 0)
                return gpu

            # Try to detect Intel GPU
            intel_gpu = self._detect_intel_gpu()
            if intel_gpu:
                gpu.type = GPUType.INTEL
                gpu.model = intel_gpu.get("model", "")
                return gpu

            # Try to detect Apple GPU
            if platform.system() == "Darwin":
                gpu.type = GPUType.APPLE
                gpu.model = "Apple Silicon"
                return gpu

        except Exception:
            pass

        # Default fallback
        gpu.type = GPUType.WASM
        return gpu

    async def _analyze_network(self) -> NetworkProfile:
        """Analyze network."""
        network = NetworkProfile()

        try:
            # Basic network detection
            network.supports_http2 = True
            network.supports_websocket = True

            # Try to detect IPv6
            import socket
            try:
                socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                network.ipv6_enabled = True
            except Exception:
                network.ipv6_enabled = False
        except Exception:
            pass

        return network

    async def _analyze_os(self) -> OSProfile:
        """Analyze operating system."""
        os_profile = OSProfile()

        try:
            os_profile.name = platform.system()
            os_profile.version = platform.release()
            os_profile.architecture = platform.machine()

            # Detect capabilities
            if os_profile.name in ["Linux", "Darwin"]:
                os_profile.supports_docker = True

            os_profile.supports_gpu = self._detect_gpu_support(os_profile.name)
            os_profile.supports_avx = self._check_avx()
            os_profile.supports_neon = self._check_neon()
        except Exception:
            pass

        return os_profile

    async def _analyze_python(self) -> PythonProfile:
        """Analyze Python runtime."""
        python = PythonProfile()

        try:
            python.version = platform.python_version()
            python.implementation = platform.python_implementation()

            # Check installed packages
            try:
                import numpy  # noqa: F401
                python.has_numpy = True
            except ImportError:
                pass

            try:
                import torch  # noqa: F401
                python.has_torch = True
            except ImportError:
                pass

            try:
                import tensorflow  # noqa: F401
                python.has_tensorflow = True
            except ImportError:
                pass

            try:
                import onnx  # noqa: F401
                python.has_onnx = True
            except ImportError:
                pass

            try:
                import redis  # noqa: F401
                python.has_redis = True
            except ImportError:
                pass

            try:
                import qdrant_client  # noqa: F401
                python.has_qdrant = True
            except ImportError:
                pass
        except Exception:
            pass

        return python

    def _check_avx(self) -> bool:
        """Check for AVX support."""
        try:
            import cpuinfo
            info = cpuinfo.get_cpu_info()
            return "avx" in info.get("flags", [])
        except Exception:
            return False

    def _check_sse(self) -> bool:
        """Check for SSE support."""
        try:
            import cpuinfo
            info = cpuinfo.get_cpu_info()
            return "sse" in info.get("flags", [])
        except Exception:
            return False

    def _check_neon(self) -> bool:
        """Check for NEON support (ARM)."""
        try:
            import cpuinfo
            info = cpuinfo.get_cpu_info()
            return "neon" in info.get("flags", [])
        except Exception:
            return False

    def _detect_nvidia_gpu(self) -> Optional[Dict]:
        """Detect NVIDIA GPU."""
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                return {
                    "model": pynvml.nvmlDeviceGetName(handle),
                    "vram_gb": pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024**3),
                    "cuda_version": pynvml.nvmlSystemGetCudaCompileVersion(),
                }
        except Exception:
            pass
        return None

    def _detect_amd_gpu(self) -> Optional[Dict]:
        """Detect AMD GPU."""
        try:
            # Simplified AMD detection
            import subprocess
            result = subprocess.run(["rocm-smi"], capture_output=True, text=True)
            if result.returncode == 0:
                return {"model": "AMD ROCM GPU"}
        except Exception:
            pass
        return None

    def _detect_intel_gpu(self) -> Optional[Dict]:
        """Detect Intel GPU."""
        try:
            import subprocess
            result = subprocess.run(["clinfo"], capture_output=True, text=True)
            if result.returncode == 0:
                return {"model": "Intel Arc/Iris"}
        except Exception:
            pass
        return None

    def _detect_gpu_support(self, os_name: str) -> bool:
        """Detect GPU support on OS."""
        if os_name == "Linux":
            try:
                import subprocess
                subprocess.run(["nvidia-smi"], capture_output=True, check=True)
                return True
            except Exception:
                pass
        elif os_name == "Darwin":
            return True  # All modern Macs have GPU
        return False

    def _determine_tier(self, profile: SystemProfile) -> str:
        """Determine performance tier."""
        cores = profile.cpu.cores
        ram_gb = profile.memory.total_gb
        has_gpu = profile.gpu.type != GPUType.NONE

        if has_gpu and cores >= 8 and ram_gb >= 32:
            return "hpc"
        elif cores >= 8 and ram_gb >= 16:
            return "performance"
        elif cores >= 4 and ram_gb >= 8:
            return "standard"
        else:
            return "edge"

    def _generate_hints(self, profile: SystemProfile) -> List[str]:
        """Generate optimization hints."""
        hints = []

        if profile.cpu.cores >= 8:
            hints.append("Multi-threaded optimization enabled")
        else:
            hints.append("Single-thread optimization mode")

        if profile.gpu.type != GPUType.NONE:
            hints.append(f"GPU acceleration available: {profile.gpu.type.value}")
        else:
            hints.append("GPU acceleration unavailable, CPU-only mode")

        if profile.memory.total_gb >= 32:
            hints.append("Large memory footprint optimization")
        elif profile.memory.total_gb < 4:
            hints.append("Low-memory edge device optimization")

        if profile.storage.type == StorageType.NVME:
            hints.append("NVME storage: enable aggressive caching")
        elif profile.storage.type == StorageType.HDD:
            hints.append("HDD storage: enable prefetching")

        if profile.cpu.has_avx:
            hints.append("AVX vector optimization available")

        if profile.python.has_torch:
            hints.append("PyTorch available: enable ML acceleration")

        if profile.python.has_redis:
            hints.append("Redis available: enable memory cache")

        if profile.python.has_qdrant:
            hints.append("Qdrant available: enable vector search")

        return hints

    def get_profile_summary(self) -> str:
        """Get human-readable profile summary."""
        if not self.profile:
            return "No analysis run yet"

        p = self.profile
        return f"""
System Analysis Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPU:     {p.cpu.cores} cores/{p.cpu.threads} threads ({p.cpu.architecture.value})
RAM:     {p.memory.total_gb:.1f} GB ({p.memory.percent_used}% used)
Storage: {p.storage.type.value} ({p.storage.total_gb:.1f} GB, {p.storage.free_gb:.1f} GB free)
GPU:     {p.gpu.type.value} {p.gpu.model}
OS:      {p.os.name} {p.os.version}
Python:  {p.python.version} ({p.python.implementation})

Performance Tier: {p.performance_tier.upper()}

Optimization Hints:
{chr(10).join(f'  • {h}' for h in p.optimization_hints)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# ── Module-level singleton ────────────────────────────────────────────────

_analyzer: Optional[SystemAnalyzer] = None


def get_system_analyzer() -> SystemAnalyzer:
    """Get or create shared SystemAnalyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SystemAnalyzer()
    return _analyzer


async def analyze_system() -> SystemProfile:
    """Run system analysis."""
    analyzer = get_system_analyzer()
    return await analyzer.analyze()
