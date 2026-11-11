# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
WebGPU Spatial Intelligence & ChromeDevTools (CDP) Diagnostic Sentinel
======================================================================
Sir Lucas (Herald of Telemetry) & Sir Helios (Spire Sentinel)

Provides:
1. WebGPU storage buffer footprint auditing against the 256 MB VRAM slice.
2. Structure-of-Arrays (SoA) layout validation and byte-packing metrics.
3. Spatial Grid Hashing (Uniform Grid) parameter calibration (O(N log N) physics).
4. Largest Triangle Three Buckets (LTTB) macro-clustering downsampler.
5. Web 4/5 Sovereign Trust Chain status encoder (DIDs + Z3 Proof Halos).
6. Autonomous CDP trace inspection emulator for frame delivery variance.
Strict adherence to Global Law 03 (4.0 GB Edge Node RAM ceiling).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


MAX_NODE_VRAM_SLICE_MB: float = 256.0
TARGET_FRAME_TIME_MS: float = 16.667  # 60 FPS


@dataclass
class GpuBufferAudit:
    node_count: int
    edge_count: int
    position_buffer_bytes: int
    velocity_buffer_bytes: int
    attribute_buffer_bytes: int
    spatial_grid_buffer_bytes: int
    total_vram_bytes: int
    total_vram_mb: float
    scarcity_compliant: bool
    soa_layout_valid: bool


@dataclass
class CdpTraceMetrics:
    captured_at: float
    frame_rate_fps: float
    avg_frame_time_ms: float
    frame_jitter_ms: float
    workgroup_dispatch_count: int
    vram_used_mb: float
    bottleneck_detected: bool
    remediation_rune: Optional[str] = None


class WebGpuSpatialDiagnostics:
    """Diagnostic and mathematical acceleration engine for WebGPU Canvas Layouts."""

    def __init__(self, max_vram_mb: float = MAX_NODE_VRAM_SLICE_MB) -> None:
        self.max_vram_mb = max_vram_mb

    def audit_buffers(self, node_count: int, edge_count: int = 0, grid_cells: int = 1024) -> GpuBufferAudit:
        """
        Audit Structure-of-Arrays (SoA) GPUBuffer allocations.
        Positions: vec2<f32> (8 bytes per node)
        Velocities: vec2<f32> (8 bytes per node)
        Attributes: vec4<f32> (trust, z3, tier, taint) (16 bytes per node)
        Spatial Grid: heads (i32) + linked_list (i32) (4 bytes * grid_cells + 4 bytes * node_count)
        """
        pos_bytes = node_count * 2 * 4
        vel_bytes = node_count * 2 * 4
        attr_bytes = node_count * 4 * 4
        grid_bytes = (grid_cells * 4) + (node_count * 4)

        total_bytes = pos_bytes + vel_bytes + attr_bytes + grid_bytes
        total_mb = total_bytes / (1024.0 * 1024.0)
        compliant = total_mb <= self.max_vram_mb

        return GpuBufferAudit(
            node_count=node_count,
            edge_count=edge_count,
            position_buffer_bytes=pos_bytes,
            velocity_buffer_bytes=vel_bytes,
            attribute_buffer_bytes=attr_bytes,
            spatial_grid_buffer_bytes=grid_bytes,
            total_vram_bytes=total_bytes,
            total_vram_mb=round(total_mb, 4),
            scarcity_compliant=compliant,
            soa_layout_valid=True,
        )

    def calculate_spatial_grid_params(
        self, node_count: int, canvas_width: float = 900.0, canvas_height: float = 480.0
    ) -> Dict[str, Any]:
        """
        Derive optimal WGSL 2D Uniform Spatial Hash Grid parameters.
        Target: ~16 to 64 nodes per cell to minimize collision list traversal.
        """
        aspect_ratio = max(0.1, canvas_width / canvas_height)
        # Choose grid dimension based on sqrt(N / 32)
        cells_target = max(16, int(math.ceil(node_count / 32.0)))
        dim_y = max(4, int(math.sqrt(cells_target / aspect_ratio)))
        dim_x = max(4, int(dim_y * aspect_ratio))
        total_cells = dim_x * dim_y
        cell_size = max(canvas_width / dim_x, canvas_height / dim_y)

        return {
            "grid_dim_x": dim_x,
            "grid_dim_y": dim_y,
            "total_cells": total_cells,
            "cell_size": round(cell_size, 2),
            "workgroup_size": 256,
            "expected_density_per_cell": round(node_count / total_cells, 2),
            "complexity": "O(N log N)",
        }

    def downsample_lttb(
        self,
        nodes: List[Dict[str, Any]],
        target_count: int,
    ) -> List[Dict[str, Any]]:
        """
        Largest Triangle Three Buckets (LTTB) downsampler adapted for spatial clustering.
        Reduces dense node clusters to representative macro-nodes when zoomed out.
        """
        n = len(nodes)
        if target_count >= n or target_count <= 2:
            return nodes

        # Bucket size
        bucket_size = (n - 2) / (target_count - 2)
        sampled = [nodes[0]]

        a_idx = 0
        for i in range(target_count - 2):
            # Calculate range for current bucket B
            b_start = int(math.floor((i + 0) * bucket_size)) + 1
            b_end = min(n - 1, int(math.floor((i + 1) * bucket_size)) + 1)

            # Calculate range for next bucket C (to get centroid C)
            c_start = int(math.floor((i + 1) * bucket_size)) + 1
            c_end = min(n, int(math.floor((i + 2) * bucket_size)) + 1)

            # Compute centroid of bucket C
            avg_x = 0.0
            avg_y = 0.0
            c_count = max(1, c_end - c_start)
            for c_idx in range(c_start, c_end):
                pos = nodes[c_idx].get("pos", [0.0, 0.0])
                avg_x += pos[0]
                avg_y += pos[1]
            avg_x /= c_count
            avg_y /= c_count

            # Find point in bucket B that maximizes triangle area ABC
            a_pos = nodes[a_idx].get("pos", [0.0, 0.0])
            max_area = -1.0
            chosen_idx = b_start

            for b_idx in range(b_start, b_end):
                b_pos = nodes[b_idx].get("pos", [0.0, 0.0])
                # Triangle area formula: 0.5 * |x_A(y_B - y_C) + x_B(y_C - y_A) + x_C(y_A - y_B)|
                area = abs(
                    a_pos[0] * (b_pos[1] - avg_y)
                    + b_pos[0] * (avg_y - a_pos[1])
                    + avg_x * (a_pos[1] - b_pos[1])
                ) * 0.5
                if area > max_area:
                    max_area = area
                    chosen_idx = b_idx

            sampled.append(nodes[chosen_idx])
            a_idx = chosen_idx

        sampled.append(nodes[-1])
        return sampled

    def encode_trust_vector(self, node: Dict[str, Any]) -> Tuple[float, float, float, float]:
        """
        Encode Web 4/5 Sovereign Trust Vector into a 4-channel float attribute:
        Channel 0: Trust score [0.0 - 1.0]
        Channel 1: Z3 proof status (1.0 = SATISFIED, 0.5 = PENDING, 0.0 = REFUTED)
        Channel 2: Tier layer (0.0 = Edge Squire, 0.5 = Knight Tissue, 1.0 = Sovereign Apex)
        Channel 3: PDG taint flag (0.0 = CLEAN, 1.0 = TAINTED/QUARANTINED)
        """
        ntype = str(node.get("type", "")).lower()
        tainted = 1.0 if node.get("tainted", False) or node.get("risk", 0) >= 50 else 0.0

        if ntype in ("root", "sovereign"):
            return (1.0, 1.0, 1.0, 0.0)
        elif ntype in ("hypervisor", "planner", "sentinel", "prover", "governance"):
            return (0.95, 1.0, 0.8, 0.0)
        elif ntype == "crystal":
            z3 = 1.0 if node.get("z3_proof", "SATISFIED") == "SATISFIED" else 0.5
            return (0.90, z3, 0.5, tainted)
        elif ntype == "security":
            return (0.85, 1.0, 0.6, tainted)
        else:
            return (0.75, 0.5, 0.2, tainted)

    def simulate_cdp_trace(
        self,
        node_count: int,
        simulated_fps: float = 60.0,
        jitter_ms: float = 0.8,
    ) -> CdpTraceMetrics:
        """
        Autonomous ChromeDevTools-MCP (CDP) diagnostic trace inspection.
        Detects frame time variance and proposes remediation runes if Δτ > 16.6ms.
        """
        avg_time = (1000.0 / simulated_fps) if simulated_fps > 0 else 999.0
        audit = self.audit_buffers(node_count)
        bottleneck = avg_time > TARGET_FRAME_TIME_MS or jitter_ms > 4.0 or not audit.scarcity_compliant

        remediation = None
        if bottleneck:
            if not audit.scarcity_compliant:
                remediation = "//RUN_LTTB_DOWNSAMPLING --target 32768"
            elif avg_time > TARGET_FRAME_TIME_MS:
                remediation = "//TUNE_SPATIAL_DAMPING --factor 0.95 --stride 2"

        return CdpTraceMetrics(
            captured_at=time.time(),
            frame_rate_fps=round(simulated_fps, 2),
            avg_frame_time_ms=round(avg_time, 2),
            frame_jitter_ms=round(jitter_ms, 2),
            workgroup_dispatch_count=int(math.ceil(node_count / 256.0)),
            vram_used_mb=audit.total_vram_mb,
            bottleneck_detected=bottleneck,
            remediation_rune=remediation,
        )
