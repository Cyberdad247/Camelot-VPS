# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
Camelot Vitals & Prometheus Observability Exporter (`camelot-vitals`)
====================================================================
Collects and formats system telemetry, eBPF PSI memory metrics, Sentinel lease
activity, and Aoede sub-50ms voice latency into Prometheus text format and
structured JSON alerts.

Core Mandate: "Observability is truth; metrics are the heartbeat of the Lattice."
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

LOG = logging.getLogger("camelot.vitals")


@dataclass
class MetricSample:
    name: str
    labels: Dict[str, str]
    value: float
    help_text: str
    metric_type: str = "gauge"


@dataclass
class HealthAlert:
    alert_id: str
    severity: str  # "INFO" | "WARNING" | "CRITICAL"
    alert_type: str
    message: str
    timestamp: str
    node: str


class CamelotVitalsCollector:
    """Prometheus Exporter & Sovereign Health Telemetry Engine."""

    def __init__(self, node_id: str = "vps_cybertronia"):
        self.node_id = node_id
        self.alerts: List[HealthAlert] = []

    def collect_metrics(
        self,
        vps_memory_used_mb: float = 4800.0,
        s26_memory_used_mb: float = 240.0,
        psi_pressure_ratio: float = 0.05,
        active_leases_count: int = 12,
        aoede_voice_latency_ms: float = 24.5,
        bifrost_ops_per_sec: float = 24000.0
    ) -> List[MetricSample]:
        """Collects the full set of system metrics across the mesh."""
        samples = [
            MetricSample(
                name="camelot_node_memory_bytes",
                labels={"node": "vps_hub", "slice": "systemd_root"},
                value=vps_memory_used_mb * 1024 * 1024,
                help_text="Current memory usage in bytes on VPS Hub (7.2GB cap)",
                metric_type="gauge"
            ),
            MetricSample(
                name="camelot_node_memory_bytes",
                labels={"node": "s26_orb", "slice": "audio_dsp"},
                value=s26_memory_used_mb * 1024 * 1024,
                help_text="Current memory usage in bytes on S26 Edge Orb (350MB slice)",
                metric_type="gauge"
            ),
            MetricSample(
                name="camelot_psi_memory_pressure_ratio",
                labels={"node": self.node_id},
                value=psi_pressure_ratio,
                help_text="Kernel eBPF PSI memory pressure ratio (0.0 to 1.0)",
                metric_type="gauge"
            ),
            MetricSample(
                name="camelot_sentinel_active_leases_total",
                labels={"tenant": "tenant_sovereign_001"},
                value=float(active_leases_count),
                help_text="Number of actively valid Sentinel Capability Leases",
                metric_type="gauge"
            ),
            MetricSample(
                name="camelot_aoede_voice_latency_ms",
                labels={"pipeline": "s2s_opus_wasm"},
                value=aoede_voice_latency_ms,
                help_text="Sub-50ms Aoede S2S glass-to-ear audio latency in milliseconds",
                metric_type="gauge"
            ),
            MetricSample(
                name="camelot_bifrost_packet_throughput_ops",
                labels={"engine": "9router"},
                value=bifrost_ops_per_sec,
                help_text="9router high-throughput packet operations per second",
                metric_type="counter"
            )
        ]
        return samples

    def export_prometheus_text(self, samples: List[MetricSample]) -> str:
        """Formats MetricSamples into standard Prometheus exposition format."""
        lines = []
        for s in samples:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(s.labels.items()))
            lines.append(f"# HELP {s.name} {s.help_text}")
            lines.append(f"# TYPE {s.name} {s.metric_type}")
            if label_str:
                lines.append(f"{s.name}{{{label_str}}} {s.value}")
            else:
                lines.append(f"{s.name} {s.value}")
        return "\n".join(lines) + "\n"

    def evaluate_health_alerts(
        self,
        vps_memory_used_mb: float,
        psi_pressure_ratio: float,
        aoede_voice_latency_ms: float
    ) -> List[HealthAlert]:
        """Evaluates health conditions and generates structured alerts."""
        alerts = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. VPS Memory Pressure (>7.2GB)
        if vps_memory_used_mb >= 7200.0 or psi_pressure_ratio >= 0.90:
            alerts.append(HealthAlert(
                alert_id=f"alt_mem_{int(time.time())}",
                severity="CRITICAL",
                alert_type="MEMORY_PRESSURE_EXCEEDED",
                message=f"Memory pressure on VPS Hub exceeds threshold: {vps_memory_used_mb}MB / PSI: {psi_pressure_ratio}",
                timestamp=now_iso,
                node="vps_hub"
            ))

        # 2. Audio Latency Spike (>100ms)
        if aoede_voice_latency_ms > 100.0:
            alerts.append(HealthAlert(
                alert_id=f"alt_lat_{int(time.time())}",
                severity="WARNING",
                alert_type="VOICE_LATENCY_DEGRADED",
                message=f"Aoede voice latency spike detected: {aoede_voice_latency_ms}ms (SLA: <50ms)",
                timestamp=now_iso,
                node="s26_orb"
            ))

        self.alerts.extend(alerts)
        return alerts
