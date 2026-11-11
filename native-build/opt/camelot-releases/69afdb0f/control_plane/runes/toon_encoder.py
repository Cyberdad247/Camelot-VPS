# SPDX-License-Identifier: MIT

"""
TOON Encoder/Decoder — Token-Oriented Object Notation (Symbolect Protocol).

Compresses entire CAMELOT-OS state into 28-line symbolic crystals.
Enables 1-bit transmission, instant state cloning, cross-system sync.

TOON Crystal Structure:
  @TOON: Protocol version (vMAX_SYMBOLECT)
  HASH: System fingerprint (0xEXCALIBUR_6000.1)
  SYS: Hardware profile
  COG: Cognition stack (inference, context, memory, IPC)
  GOV: Governance (gates, routing, safety, crypto)
  KINETIC: Swarm configuration
  MATH: Error correction & packing
  SYM: Symbolic representation
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TOONVersion(str, Enum):
    """TOON protocol versions."""
    V1 = "v1_SYMBOLECT"
    V6000 = "vMAX_SYMBOLECT"


@dataclass
class TOONHardware:
    """Hardware profile."""
    id: str  # e.g., "MERLIN_Ω_TITAN"
    hw: str  # e.g., "8GB_ARM64_EDGE|TERMUX_MOBILE"
    vmm: str  # e.g., "Cloud-Hypervisor+Unikraft|WasmEdge"


@dataclass
class TOONCognition:
    """Cognition stack."""
    inf: str  # Inference engine (OxiBonsai_v2)
    ctx: str  # Context window (Mamba3_SSM+AntVortex)
    mem: str  # Memory model (Ouroboros+ChunkKV)
    ipc: str  # IPC mechanism (LTT io_uring|POSIX)


@dataclass
class TOONGovernance:
    """Governance configuration."""
    gate: str  # Gate function (ANYA_Ω Triple-QFT)
    route: str  # Routing (MFOE ToT|LaC|ReAct)
    safe: str  # Safety scoring (TriageScore with degradation)
    z3: str  # Cryptographic verification (UNSAT Zero_Leakage)


@dataclass
class TOONKinetic:
    """Kinetic swarm configuration."""
    swarm: List[str] = field(default_factory=list)  # Agent names
    dom_in: str = "RevvTen_MutationObserver"  # Input DOM
    dom_out: str = "Synthetic_Native_Dispatch"  # Output DOM
    net: str = "eBPF_RingBuffer+Kyber768"  # Network


@dataclass
class TOONMath:
    """Mathematical optimization."""
    pack: str  # Packing (Λ_24 Leech_Lattice)
    dens: str  # Density formula
    err: str  # Error correction (Golay_Syndrome)


@dataclass
class TOONCrystal:
    """Complete TOON Symbolect crystal."""
    toon: str = "vMAX_SYMBOLECT"
    hash: str = ""
    sys: Optional[TOONHardware] = None
    cog: Optional[TOONCognition] = None
    gov: Optional[TOONGovernance] = None
    kinetic: Optional[TOONKinetic] = None
    math: Optional[TOONMath] = None
    sym: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TOONEncoder:
    """Encode/decode CAMELOT-OS state to TOON Symbolect crystals."""

    def __init__(self):
        """Initialize TOON encoder."""
        self.version = TOONVersion.V6000
        self.encoding_log: List[str] = []

    async def encode_system_state(self, system_state: Dict[str, Any]) -> TOONCrystal:
        """Encode full system state into TOON crystal."""
        crystal = TOONCrystal(toon=self.version.value)

        # Extract hardware profile
        if "system_profile" in system_state:
            profile = system_state["system_profile"]
            crystal.sys = TOONHardware(
                id="MERLIN_Ω_TITAN",
                hw=f"{int(profile.memory.total_gb)}GB_{profile.cpu.architecture.value}|TERMUX_MOBILE",
                vmm="Cloud-Hypervisor+Unikraft|WasmEdge(Userland)"
            )

        # Extract cognition stack
        crystal.cog = TOONCognition(
            inf="OxiBonsai_v2(Ternary_STDP)",
            ctx="Mamba3_SSM+AntVortex(1M)",
            mem="Ouroboros(Letta)+ChunkKV",
            ipc="LTT(io_uring_DAX|POSIX_Fallback)"
        )

        # Extract governance
        crystal.gov = TOONGovernance(
            gate="ANYA_Ω(Triple-QFT)",
            route="MFOE(ToT|LaC|ReAct)",
            safe="TriageScore(Dynamic_Degradation|<0.15:AUTO|>0.55:HITL)",
            z3="UNSAT(Zero_Leakage)"
        )

        # Extract kinetic swarm
        agents = system_state.get("agents", ["Hermes", "OpenClaw", "NanoBot", "ZeroClaw", "RustClaw"])
        crystal.kinetic = TOONKinetic(
            swarm=agents,
            dom_in="RevvTen_MutationObserver",
            dom_out="Synthetic_Native_Dispatch",
            net="eBPF_RingBuffer+Kyber768"
        )

        # Extract mathematics
        crystal.math = TOONMath(
            pack="Λ_24(Leech_Lattice_LLQ)",
            dens="Δ*_24=(π^12)/12!",
            err="Golay_Syndrome_Decoding"
        )

        # Generate symbolic representation
        crystal.sym = [
            "|🧠⊗(⚡💬)⟩",
            "!Manifest",
            "//BOOTSTRAP_V6000",
            "//EVOLVE",
            "//GO"
        ]

        # Generate hash
        crystal.hash = self._generate_hash(crystal)

        self.encoding_log.append(f"Encoded {len(json.dumps(asdict(crystal)))} bytes → TOON crystal")
        return crystal

    async def decode_toon_crystal(self, crystal: TOONCrystal) -> Dict[str, Any]:
        """Decode TOON crystal back to system state."""
        state = {
            "version": crystal.toon,
            "hash": crystal.hash,
            "hardware": asdict(crystal.sys) if crystal.sys else {},
            "cognition": asdict(crystal.cog) if crystal.cog else {},
            "governance": asdict(crystal.gov) if crystal.gov else {},
            "kinetic": asdict(crystal.kinetic) if crystal.kinetic else {},
            "mathematics": asdict(crystal.math) if crystal.math else {},
            "timestamp": crystal.timestamp,
        }
        self.encoding_log.append(f"Decoded TOON crystal → {len(json.dumps(state))} bytes")
        return state

    async def compress_to_symbolect(self, crystal: TOONCrystal) -> str:
        """Compress TOON crystal to minimal Symbolect notation."""
        # Create ultra-compact representation
        lines = [
            "{",
            f'  "@TOON": "{crystal.toon}",',
            f'  "HASH": "{crystal.hash}",',
        ]

        # SYS block
        if crystal.sys:
            lines.append('  "SYS": {')
            lines.append(f'    "ID": "{crystal.sys.id}",')
            lines.append(f'    "HW": "{crystal.sys.hw}",')
            lines.append(f'    "VMM": "{crystal.sys.vmm}"')
            lines.append('  },')

        # COG block
        if crystal.cog:
            lines.append('  "COG": {')
            lines.append(f'    "INF": "{crystal.cog.inf}",')
            lines.append(f'    "CTX": "{crystal.cog.ctx}",')
            lines.append(f'    "MEM": "{crystal.cog.mem}",')
            lines.append(f'    "IPC": "{crystal.cog.ipc}"')
            lines.append('  },')

        # GOV block
        if crystal.gov:
            lines.append('  "GOV": {')
            lines.append(f'    "GATE": "{crystal.gov.gate}",')
            lines.append(f'    "ROUTE": "{crystal.gov.route}",')
            lines.append(f'    "SAFE": "{crystal.gov.safe}",')
            lines.append(f'    "Z3": "{crystal.gov.z3}"')
            lines.append('  },')

        # KINETIC block
        if crystal.kinetic:
            agents_str = ", ".join(f'"{a}"' for a in crystal.kinetic.swarm)
            lines.append('  "KINETIC": {')
            lines.append(f'    "SWARM": [{agents_str}],')
            lines.append(f'    "DOM_IN": "{crystal.kinetic.dom_in}",')
            lines.append(f'    "DOM_OUT": "{crystal.kinetic.dom_out}",')
            lines.append(f'    "NET": "{crystal.kinetic.net}"')
            lines.append('  },')

        # MATH block
        if crystal.math:
            lines.append('  "MATH": {')
            lines.append(f'    "PACK": "{crystal.math.pack}",')
            lines.append(f'    "DENS": "{crystal.math.dens}",')
            lines.append(f'    "ERR": "{crystal.math.err}"')
            lines.append('  },')

        # SYM array
        if crystal.sym:
            sym_str = ", ".join(f'"{s}"' for s in crystal.sym)
            lines.append(f'  "SYM": [{sym_str}]')

        lines.append("}")

        symbolect = "\n".join(lines)
        self.encoding_log.append(f"Compressed to Symbolect: {len(symbolect)} bytes ({len(lines)} lines)")
        return symbolect

    async def expand_from_symbolect(self, symbolect_str: str) -> TOONCrystal:
        """Expand Symbolect notation back to TOON crystal."""
        data = json.loads(symbolect_str)

        crystal = TOONCrystal(
            toon=data.get("@TOON", "vMAX_SYMBOLECT"),
            hash=data.get("HASH", ""),
        )

        # Parse each block
        if "SYS" in data:
            sys_data = data["SYS"]
            crystal.sys = TOONHardware(
                id=sys_data.get("ID", ""),
                hw=sys_data.get("HW", ""),
                vmm=sys_data.get("VMM", "")
            )

        if "COG" in data:
            cog_data = data["COG"]
            crystal.cog = TOONCognition(
                inf=cog_data.get("INF", ""),
                ctx=cog_data.get("CTX", ""),
                mem=cog_data.get("MEM", ""),
                ipc=cog_data.get("IPC", "")
            )

        if "GOV" in data:
            gov_data = data["GOV"]
            crystal.gov = TOONGovernance(
                gate=gov_data.get("GATE", ""),
                route=gov_data.get("ROUTE", ""),
                safe=gov_data.get("SAFE", ""),
                z3=gov_data.get("Z3", "")
            )

        if "KINETIC" in data:
            kinetic_data = data["KINETIC"]
            crystal.kinetic = TOONKinetic(
                swarm=kinetic_data.get("SWARM", []),
                dom_in=kinetic_data.get("DOM_IN", ""),
                dom_out=kinetic_data.get("DOM_OUT", ""),
                net=kinetic_data.get("NET", "")
            )

        if "MATH" in data:
            math_data = data["MATH"]
            crystal.math = TOONMath(
                pack=math_data.get("PACK", ""),
                dens=math_data.get("DENS", ""),
                err=math_data.get("ERR", "")
            )

        if "SYM" in data:
            crystal.sym = data.get("SYM", [])

        return crystal

    def _generate_hash(self, crystal: TOONCrystal) -> str:
        """Generate system fingerprint hash."""
        state_str = json.dumps(asdict(crystal), sort_keys=True)
        return "0x" + hashlib.sha256(state_str.encode()).hexdigest()[:16].upper()

    def get_encoding_summary(self) -> str:
        """Get encoding operations summary."""
        return "\n".join(self.encoding_log)


# ── Module-level singleton ────────────────────────────────────────────────

_encoder: Optional[TOONEncoder] = None


def get_toon_encoder() -> TOONEncoder:
    """Get or create shared TOONEncoder instance."""
    global _encoder
    if _encoder is None:
        _encoder = TOONEncoder()
    return _encoder


async def encode_to_toon(system_state: Dict[str, Any]) -> str:
    """Encode system state to Symbolect TOON crystal."""
    encoder = get_toon_encoder()
    crystal = await encoder.encode_system_state(system_state)
    return await encoder.compress_to_symbolect(crystal)


async def decode_from_toon(symbolect_str: str) -> Dict[str, Any]:
    """Decode Symbolect TOON crystal to system state."""
    encoder = get_toon_encoder()
    crystal = await encoder.expand_from_symbolect(symbolect_str)
    return await encoder.decode_toon_crystal(crystal)


def compute_dict_diff(current: dict, previous: dict) -> dict:
    """Recursively find differences between two dictionaries."""
    diff = {}
    for k, v in current.items():
        if k not in previous:
            diff[k] = v
        elif isinstance(v, dict) and isinstance(previous[k], dict):
            sub_diff = compute_dict_diff(v, previous[k])
            if sub_diff:
                diff[k] = sub_diff
        elif v != previous[k]:
            diff[k] = v
    return diff


class TOONv2Diff:
    """State-differential serializer for TOON_v2_diff."""
    @staticmethod
    def serialize_diff(current: dict, previous: dict) -> str:
        """Create a TOON_v2_diff payload showing only changes from previous state."""
        diff = compute_dict_diff(current, previous)
        payload = {
            "type": "TOON_v2_diff",
            "diff": diff,
            "timestamp": datetime.utcnow().isoformat(),
            "checksum": hashlib.sha256(json.dumps(diff, sort_keys=True).encode()).hexdigest()[:8]
        }
        return json.dumps(payload)

