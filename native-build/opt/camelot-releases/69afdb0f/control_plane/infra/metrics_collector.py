# SPDX-License-Identifier: MIT

"""
Metrics Collector — Prometheus Instrumentation for CAMELOT-OS

Comprehensive metrics collection for:
- System health (CPU, memory, disk)
- Consensus performance (latency, success rate, phases)
- Knowledge synchronization (replication lag, events/sec)
- Agent network (health, routing, latency)
- Error rates and failures

Integrates with Prometheus for scraping every 15 seconds.
"""

from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, Summary, start_http_server


class MetricsCollector:
    """Prometheus metrics collection for CAMELOT-OS"""

    def __init__(self, port: int = 8000):
        """
        Initialize metrics collector

        Args:
            port: Port for Prometheus /metrics endpoint
        """
        self.port = port

        # Start Prometheus HTTP server
        start_http_server(port)

        # ── System Metrics ────────────────────────────────────────

        self.system_memory_bytes = Gauge(
            'camelot_system_memory_bytes',
            'System memory usage in bytes',
            labelnames=['instance', 'type']  # type: used, available, total
        )

        self.system_cpu_percent = Gauge(
            'camelot_system_cpu_percent',
            'CPU utilization percentage',
            labelnames=['instance']
        )

        self.system_disk_bytes = Gauge(
            'camelot_system_disk_bytes',
            'Disk usage in bytes',
            labelnames=['instance', 'path']
        )

        self.system_uptime_seconds = Gauge(
            'camelot_system_uptime_seconds',
            'System uptime in seconds',
            labelnames=['instance']
        )

        # ── Consensus Metrics ────────────────────────────────────────

        self.consensus_proposals_total = Counter(
            'camelot_consensus_proposals_total',
            'Total consensus proposals',
            labelnames=['node_id', 'phase', 'status']  # status: success, failed, timeout
        )

        self.consensus_latency_seconds = Histogram(
            'camelot_consensus_latency_seconds',
            'Consensus latency from proposal to decision',
            labelnames=['node_id'],
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        )

        self.consensus_phase_duration_seconds = Summary(
            'camelot_consensus_phase_duration_seconds',
            'Duration of consensus phase',
            labelnames=['node_id', 'phase']  # phase: pre_prepare, prepare, commit
        )

        self.consensus_log_size = Gauge(
            'camelot_consensus_log_size',
            'Consensus log size (number of entries)',
            labelnames=['node_id']
        )

        self.consensus_leader_changes_total = Counter(
            'camelot_consensus_leader_changes_total',
            'Total number of leader changes',
            labelnames=['cluster']
        )

        # ── Knowledge Sync Metrics ────────────────────────────────────

        self.sync_events_total = Counter(
            'camelot_sync_events_total',
            'Total sync events processed',
            labelnames=['node_id', 'phase', 'status']  # status: success, conflict, timeout
        )

        self.sync_latency_seconds = Histogram(
            'camelot_sync_latency_seconds',
            'Knowledge sync latency (L1 write to L2 persist)',
            labelnames=['node_id'],
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
        )

        self.sync_replication_lag_seconds = Gauge(
            'camelot_sync_replication_lag_seconds',
            'Replication lag between nodes',
            labelnames=['source_node', 'target_node']
        )

        self.sync_conflicts_total = Counter(
            'camelot_sync_conflicts_total',
            'Total sync conflicts detected',
            labelnames=['node_id', 'resolution']  # resolution: last_write_wins, merge
        )

        self.sync_data_events_per_second = Gauge(
            'camelot_sync_events_per_second',
            'Data events per second',
            labelnames=['node_id']
        )

        self.sync_vector_consolidations_total = Counter(
            'camelot_sync_vector_consolidations_total',
            'Total vector consolidations to L1.5',
            labelnames=['node_id']
        )

        # ── Agent Network Metrics ────────────────────────────────────

        self.agent_requests_total = Counter(
            'camelot_agent_requests_total',
            'Total agent requests',
            labelnames=['agent_id', 'status', 'method']  # status: success, error
        )

        self.agent_latency_seconds = Histogram(
            'camelot_agent_latency_seconds',
            'Agent response latency',
            labelnames=['agent_id'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
        )

        self.agent_health_status = Gauge(
            'camelot_agent_health_status',
            'Agent health status (0=dark, 1=degraded, 2=healthy)',
            labelnames=['agent_id', 'node_id', 'role']  # role: forge, coordinator, etc
        )

        self.agent_load = Gauge(
            'camelot_agent_load',
            'Agent current load (0-1)',
            labelnames=['agent_id']
        )

        self.agent_uptime_seconds = Gauge(
            'camelot_agent_uptime_seconds',
            'Agent uptime in seconds',
            labelnames=['agent_id']
        )

        self.agent_count = Gauge(
            'camelot_agent_count',
            'Number of healthy agents',
            labelnames=['node_id', 'role']  # role: all, forge, coordinator
        )

        self.agent_routing_decisions_total = Counter(
            'camelot_agent_routing_decisions_total',
            'Total agent routing decisions',
            labelnames=['strategy', 'selected_agent']  # strategy: least_loaded, geographic, consensus
        )

        # ── Error & Failure Metrics ────────────────────────────────────

        self.errors_total = Counter(
            'camelot_errors_total',
            'Total errors by type',
            labelnames=['component', 'error_type', 'severity']  # severity: warning, error, critical
        )

        self.failures_total = Counter(
            'camelot_failures_total',
            'Total failures (consensus failures, sync failures, etc)',
            labelnames=['component', 'failure_type']
        )

        self.timeouts_total = Counter(
            'camelot_timeouts_total',
            'Total timeout events',
            labelnames=['component', 'operation']
        )

        self.recovery_time_seconds = Histogram(
            'camelot_recovery_time_seconds',
            'Time to recover from failure',
            labelnames=['component', 'failure_type'],
            buckets=[1, 5, 10, 30, 60, 300]  # 1s to 5min
        )

        # ── Data Consistency Metrics ──────────────────────────────────

        self.data_loss_events_total = Counter(
            'camelot_data_loss_events_total',
            'Data loss events (should be 0)',
            labelnames=['component']
        )

        self.data_divergence_detected = Counter(
            'camelot_data_divergence_detected',
            'Data divergence between nodes',
            labelnames=['node_id_a', 'node_id_b']
        )

        self.consistency_check_duration_seconds = Histogram(
            'camelot_consistency_check_duration_seconds',
            'Duration of consistency check',
            labelnames=['check_type'],
            buckets=[0.1, 0.5, 1.0, 5.0]
        )

        # ── Performance Metrics ───────────────────────────────────────

        self.request_rate_per_second = Gauge(
            'camelot_request_rate_per_second',
            'Request rate (requests per second)',
            labelnames=['component']
        )

        self.throughput_bytes_per_second = Gauge(
            'camelot_throughput_bytes_per_second',
            'Throughput in bytes per second',
            labelnames=['component']
        )

        self.p95_latency_ms = Gauge(
            'camelot_p95_latency_ms',
            'P95 latency in milliseconds',
            labelnames=['operation']
        )

        self.p99_latency_ms = Gauge(
            'camelot_p99_latency_ms',
            'P99 latency in milliseconds',
            labelnames=['operation']
        )

        print(f"✅ Metrics collector initialized (port {port})")

    # ── Recording Methods ─────────────────────────────────────────────

    def record_consensus_proposal(self, node_id: str, phase: str, success: bool, latency_seconds: float):
        """Record consensus proposal"""
        status = "success" if success else "failed"
        self.consensus_proposals_total.labels(
            node_id=node_id,
            phase=phase,
            status=status
        ).inc()

        if success:
            self.consensus_latency_seconds.labels(node_id=node_id).observe(latency_seconds)

    def record_sync_event(self, node_id: str, phase: str, success: bool, latency_seconds: float):
        """Record sync event"""
        status = "success" if success else "timeout"
        self.sync_events_total.labels(
            node_id=node_id,
            phase=phase,
            status=status
        ).inc()

        if success:
            self.sync_latency_seconds.labels(node_id=node_id).observe(latency_seconds)

    def record_agent_request(self, agent_id: str, success: bool, latency_seconds: float, method: str):
        """Record agent request"""
        status = "success" if success else "error"
        self.agent_requests_total.labels(
            agent_id=agent_id,
            status=status,
            method=method
        ).inc()

        if success:
            self.agent_latency_seconds.labels(agent_id=agent_id).observe(latency_seconds)

    def record_agent_health(self, agent_id: str, node_id: str, role: str, health_status: int):
        """Record agent health status (0=dark, 1=degraded, 2=healthy)"""
        self.agent_health_status.labels(
            agent_id=agent_id,
            node_id=node_id,
            role=role
        ).set(health_status)

    def record_error(self, component: str, error_type: str, severity: str = "error"):
        """Record error"""
        self.errors_total.labels(
            component=component,
            error_type=error_type,
            severity=severity
        ).inc()

    def record_failure(self, component: str, failure_type: str):
        """Record failure"""
        self.failures_total.labels(
            component=component,
            failure_type=failure_type
        ).inc()

    def record_recovery(self, component: str, failure_type: str, recovery_seconds: float):
        """Record recovery from failure"""
        self.recovery_time_seconds.labels(
            component=component,
            failure_type=failure_type
        ).observe(recovery_seconds)

    def update_system_metrics(self, instance: str, memory_percent: float, cpu_percent: float):
        """Update system resource metrics"""
        import psutil
        vm = psutil.virtual_memory()

        self.system_memory_bytes.labels(instance=instance, type="used").set(vm.used)
        self.system_memory_bytes.labels(instance=instance, type="available").set(vm.available)
        self.system_memory_bytes.labels(instance=instance, type="total").set(vm.total)

        self.system_cpu_percent.labels(instance=instance).set(cpu_percent)

    def update_agent_count(self, node_id: str, healthy_count: int, total_count: int):
        """Update agent count metrics"""
        self.agent_count.labels(node_id=node_id, role="all").set(healthy_count)

    def get_metrics_port(self) -> int:
        """Get Prometheus metrics endpoint port"""
        return self.port


# ── Module-level singleton ────────────────────────────────────────────

_collector: Optional[MetricsCollector] = None


def get_metrics_collector(port: int = 8000) -> MetricsCollector:
    """Get or create metrics collector instance"""
    global _collector
    if _collector is None:
        _collector = MetricsCollector(port)
    return _collector


# ── Usage Examples ────────────────────────────────────────────────────

async def example_usage():
    """Example metrics recording"""
    collector = get_metrics_collector(port=8000)

    # Record consensus proposal
    collector.record_consensus_proposal(
        node_id="node_1",
        phase="commit",
        success=True,
        latency_seconds=0.087
    )

    # Record sync event
    collector.record_sync_event(
        node_id="node_1",
        phase="l1_5_consolidation",
        success=True,
        latency_seconds=0.045
    )

    # Record agent request
    collector.record_agent_request(
        agent_id="hermes_1",
        success=True,
        latency_seconds=0.012,
        method="dispatch"
    )

    # Record agent health
    collector.record_agent_health(
        agent_id="hermes_1",
        node_id="node_1",
        role="forge",
        health_status=2  # healthy
    )

    # Record error
    collector.record_error(
        component="consensus",
        error_type="timeout",
        severity="warning"
    )

    print("Metrics available at: http://localhost:8000/metrics")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
