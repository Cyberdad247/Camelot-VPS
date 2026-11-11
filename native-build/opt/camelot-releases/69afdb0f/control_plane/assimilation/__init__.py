# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — Assimilation Package Init
"""
control_plane.assimilation
==========================
vMAX 3.1 & CloudBrain Sovereign Assimilation Suite:
- VMAXPlaneRouter: Maps RP0-RP6 Runtime Planes and DL0-DL5 Documentation Layers to VKG topologies.
- MasterCompendiumMutator: Enforces the O(1) slot-economy in-place mutation protocol.
"""

from control_plane.assimilation.vmax_plane_router import (
    DocumentationLayer,
    PlaneRoutingVerdict,
    RuntimePlane,
    VMAXPlaneRouter,
    DL_TO_VKG_MAPPING,
    KNIGHT_PLANE_AFFINITY,
)
from control_plane.assimilation.compendium_mutator import (
    CompendiumMutationResult,
    MasterCompendiumMutator,
)

__all__ = [
    "DocumentationLayer",
    "PlaneRoutingVerdict",
    "RuntimePlane",
    "VMAXPlaneRouter",
    "DL_TO_VKG_MAPPING",
    "KNIGHT_PLANE_AFFINITY",
    "CompendiumMutationResult",
    "MasterCompendiumMutator",
]
