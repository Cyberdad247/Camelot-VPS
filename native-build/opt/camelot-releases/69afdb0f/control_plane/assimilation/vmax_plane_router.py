# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — vMAX 3.1 Plane & Layer Telemetry Router
r"""
control_plane.assimilation.vmax_plane_router — vMAX 3.1 Plane & Layer Telemetry Router
======================================================================================
Enforces the vMAX 3.1 Sovereign Assimilation Master Suite naming standard:
  1. Runtime Planes: RP0 to RP6 (Operational execution hierarchy)
  2. Documentation Layers: DL0 to DL5 (Constitutional truth hierarchy)

Connects the mathematical VKG equation to operational planes:
  DL0 -> V0 (Governance & Singularity)
  DL1 -> V1 (Operator Intent & Horizon)
  DL2 -> V2 (Schemas & Skeleton)
  DL3 -> V3 (Security & Shield)
  DL4 -> V4 (Infrastructure & Foundation)
  DL5 -> L5 (Recursive Reflection)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("VMAXPlaneRouter")


class RuntimePlane(str, Enum):
    """vMAX 3.1 Runtime Planes (RP0 - RP6)."""
    RP0_SOVEREIGN_INFRASTRUCTURE = "RP0_SOVEREIGN_INFRASTRUCTURE"
    RP1_AUTHORITY_AND_EVIDENCE = "RP1_AUTHORITY_AND_EVIDENCE"
    RP2_GOVERNED_CONNECTIVITY = "RP2_GOVERNED_CONNECTIVITY"
    RP3_ROUTING_AND_ORCHESTRATION = "RP3_ROUTING_AND_ORCHESTRATION"
    RP4_COGNITION_KNOWLEDGE_VOICE = "RP4_COGNITION_KNOWLEDGE_VOICE"
    RP5_EXPERIENCE_AND_COMMAND = "RP5_EXPERIENCE_AND_COMMAND"
    RP6_EXTENSIONS_AND_EMBODIMENT = "RP6_EXTENSIONS_AND_EMBODIMENT"


class DocumentationLayer(str, Enum):
    """vMAX 3.1 Documentation Truth Layers (DL0 - DL5)."""
    DL0_GOVERNANCE = "DL0_GOVERNANCE"
    DL1_INTENT = "DL1_INTENT"
    DL2_STRUCTURE = "DL2_STRUCTURE"
    DL3_GUARDRAILS = "DL3_GUARDRAILS"
    DL4_OPERATIONS = "DL4_OPERATIONS"
    DL5_REFLECTION = "DL5_REFLECTION"


# Mapping from Documentation Layers to VKG Mathematical Nodes
DL_TO_VKG_MAPPING: Dict[DocumentationLayer, str] = {
    DocumentationLayer.DL0_GOVERNANCE: "V0_SINGULARITY",
    DocumentationLayer.DL1_INTENT: "V1_HORIZON",
    DocumentationLayer.DL2_STRUCTURE: "V2_SKELETON",
    DocumentationLayer.DL3_GUARDRAILS: "V3_SHIELD",
    DocumentationLayer.DL4_OPERATIONS: "V4_FOUNDATION",
    DocumentationLayer.DL5_REFLECTION: "L5_RECURSIVE_FREQUENCY",
}

# Mapping of Knights to their primary governing Runtime Planes
KNIGHT_PLANE_AFFINITY: Dict[str, RuntimePlane] = {
    "LUKAS_Ω": RuntimePlane.RP0_SOVEREIGN_INFRASTRUCTURE,
    "LUKAS_OMEGA": RuntimePlane.RP0_SOVEREIGN_INFRASTRUCTURE,
    "ANYA_Ω": RuntimePlane.RP1_AUTHORITY_AND_EVIDENCE,
    "ANYA_OMEGA": RuntimePlane.RP1_AUTHORITY_AND_EVIDENCE,
    "SIR_ARTHUR": RuntimePlane.RP1_AUTHORITY_AND_EVIDENCE,
    "SIR_SENTINEL": RuntimePlane.RP1_AUTHORITY_AND_EVIDENCE,
    "SIR_LINK": RuntimePlane.RP2_GOVERNED_CONNECTIVITY,
    "SIR_HELIO": RuntimePlane.RP2_GOVERNED_CONNECTIVITY,
    "MERLIN_Ω": RuntimePlane.RP3_ROUTING_AND_ORCHESTRATION,
    "MERLIN_OMEGA": RuntimePlane.RP3_ROUTING_AND_ORCHESTRATION,
    "SIR_KAY": RuntimePlane.RP3_ROUTING_AND_ORCHESTRATION,
    "LADY_MNEMOSYNE": RuntimePlane.RP4_COGNITION_KNOWLEDGE_VOICE,
    "LADY_APIS": RuntimePlane.RP4_COGNITION_KNOWLEDGE_VOICE,
    "SIR_SONUS": RuntimePlane.RP4_COGNITION_KNOWLEDGE_VOICE,
    "HERMES_PRIME": RuntimePlane.RP4_COGNITION_KNOWLEDGE_VOICE,
    "SIR_HELIOS": RuntimePlane.RP4_COGNITION_KNOWLEDGE_VOICE,
    "SIR_BORIS": RuntimePlane.RP5_EXPERIENCE_AND_COMMAND,
    "SIR_LUCAS": RuntimePlane.RP5_EXPERIENCE_AND_COMMAND,
    "SIR_FORGE": RuntimePlane.RP6_EXTENSIONS_AND_EMBODIMENT,
    "SIR_CODEX": RuntimePlane.RP6_EXTENSIONS_AND_EMBODIMENT,
    "SIR_OCTAVIAN": RuntimePlane.RP6_EXTENSIONS_AND_EMBODIMENT,
}


@dataclass(frozen=True)
class PlaneRoutingVerdict:
    """Telemetry report classifying a task into its vMAX 3.1 Runtime Plane and Doc Layer."""
    task_id: str
    knight_id: str
    runtime_plane: RuntimePlane
    doc_layer: DocumentationLayer
    vkg_node: str
    ram_ceiling_mb: int
    is_server_plane: bool
    requires_hitl: bool


class VMAXPlaneRouter:
    """
    Evaluates and assigns task execution contexts to proper vMAX 3.1 Runtime Planes
    and ensures strict enforcement of resource boundaries.
    """

    @staticmethod
    def classify_task(
        task_id: str,
        knight_id: str,
        action: str,
        requested_ram_mb: int = 512,
        is_server: bool = False,
    ) -> PlaneRoutingVerdict:
        norm_knight = knight_id.upper().strip()
        plane = KNIGHT_PLANE_AFFINITY.get(norm_knight, RuntimePlane.RP3_ROUTING_AND_ORCHESTRATION)

        # Determine documentation truth layer mapping based on action type
        act_lower = action.lower()
        if any(kw in act_lower for kw in ["gov", "rule", "law", "policy", "audit", "contract"]):
            doc_layer = DocumentationLayer.DL0_GOVERNANCE
        elif any(kw in act_lower for kw in ["intent", "goal", "plan", "request"]):
            doc_layer = DocumentationLayer.DL1_INTENT
        elif any(kw in act_lower for kw in ["schema", "interface", "api", "spec"]):
            doc_layer = DocumentationLayer.DL2_STRUCTURE
        elif any(kw in act_lower for kw in ["guard", "shield", "sanitize", "security", "taint"]):
            doc_layer = DocumentationLayer.DL3_GUARDRAILS
        elif any(kw in act_lower for kw in ["reflect", "feedback", "learn", "metric"]):
            doc_layer = DocumentationLayer.DL5_REFLECTION
        else:
            doc_layer = DocumentationLayer.DL4_OPERATIONS

        vkg_node = DL_TO_VKG_MAPPING[doc_layer]

        # Enforce Camelot RAM Ceiling Law
        ram_ceiling = 8192 if is_server else 4096
        # Sir Arthur special constraint (256 MB on VPS)
        if norm_knight in ("SIR_ARTHUR", "SIR_ARTHUR_Ω") and not is_server:
            ram_ceiling = 256

        requires_hitl = requested_ram_mb > ram_ceiling or doc_layer == DocumentationLayer.DL0_GOVERNANCE

        return PlaneRoutingVerdict(
            task_id=task_id,
            knight_id=norm_knight,
            runtime_plane=plane,
            doc_layer=doc_layer,
            vkg_node=vkg_node,
            ram_ceiling_mb=ram_ceiling,
            is_server_plane=is_server,
            requires_hitl=requires_hitl,
        )
