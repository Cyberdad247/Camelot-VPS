#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H: Integration Helper
Wires metrics collection and anomaly detection into main system
Minimal overhead (< 0.1ms per operation)
"""

import threading
import time
from typing import Dict, Optional

from .phase_h_anomaly_detector import AnomalyDetector
from .phase_h_metrics import MetricsCollector


class MetricsMiddleware:
    """
    Integration layer for metrics collection.
    Drop-in wrapper for operation instrumentation.

    Usage:
    ```python
    metrics = MetricsMiddleware()

    # Instrument an operation
    with metrics.track('read'):
        result = do_read_operation()

    # Or manual timing
    start = time.perf_counter()
    try:
        result = do_operation()
        metrics.record('write', (time.perf_counter() - start) * 1000, success=True)
    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        metrics.record('write', duration, success=False, error_message=str(e))
    ```
    """

    def __init__(self, db_path: str = "control_plane/metrics.db", sample_rate: float = 0.1):
        self.collector = MetricsCollector(db_path=db_path, sample_rate=sample_rate)
        self.baseline = AnomalyDetector.get_phase_g_baseline()
        self.detector = AnomalyDetector(self.baseline, db_path="control_plane/anomalies.db")

    def record(
        self,
        operation_type: str,
        duration_ms: float,
        success: bool,
        error_message: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record operation directly"""
        self.collector.record_operation(operation_type, duration_ms, success, error_message, tags)

    def track(self, operation_type: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for timing operations"""
        return _TimingContext(self, operation_type, tags)

    def get_current_metrics(self) -> Dict:
        """Get current system metrics (all operation types)"""
        return self.collector.get_all_operation_stats(time_window_sec=3600)

    def get_health_status(self) -> Dict:
        """Get system health summary"""
        metrics = self.get_current_metrics()
        health = self.detector.get_health_summary(metrics)
        return {
            'status': health['status'],
            'summary': health['summary'],
            'timestamp': health['timestamp'],
            'anomalies': self.detector.get_alerts(hours=1)
        }

    def check_anomalies(self) -> Dict:
        """Check for anomalies and return result"""
        metrics = self.get_current_metrics()
        return self.detector.check(metrics)

    def cleanup_old_metrics(self, days_to_keep: int = 7):
        """Run maintenance (cleanup old records)"""
        return self.collector.cleanup_old_records(days_to_keep=days_to_keep)

    def start_background_check(self, interval_sec: int = 60):
        """
        Start background anomaly checking thread.
        Runs check every N seconds.
        """
        def check_loop():
            while True:
                try:
                    self.check_anomalies()
                    time.sleep(interval_sec)
                except Exception as e:
                    print(f"[WARN] Background anomaly check failed: {e}")
                    time.sleep(interval_sec)

        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start()
        return thread


class _TimingContext:
    """Context manager for timing operations"""

    def __init__(self, middleware: MetricsMiddleware, operation_type: str, tags: Optional[Dict]):
        self.middleware = middleware
        self.operation_type = operation_type
        self.tags = tags or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        success = exc_type is None
        error_message = str(exc_val) if exc_val else None

        self.middleware.record(
            self.operation_type,
            duration_ms,
            success,
            error_message=error_message,
            tags=self.tags
        )
        return False  # Re-raise exceptions


# Global singleton instance (optional, for convenience)
_global_metrics: Optional[MetricsMiddleware] = None


def get_metrics() -> MetricsMiddleware:
    """Get global metrics instance (create if needed)"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsMiddleware()
    return _global_metrics


def init_metrics(sample_rate: float = 0.1, db_path: str = "control_plane/metrics.db"):
    """Initialize global metrics instance"""
    global _global_metrics
    _global_metrics = MetricsMiddleware(db_path=db_path, sample_rate=sample_rate)
    _global_metrics.start_background_check(interval_sec=60)
    return _global_metrics


# ============================================================================
# EXAMPLE USAGE PATTERNS
# ============================================================================

"""
Pattern 1: Global singleton (simplest)
================================================
from phase_h_integration import init_metrics, get_metrics

# In main.py initialization
metrics = init_metrics(sample_rate=0.1)

# In operation code (anywhere)
from phase_h_integration import get_metrics

metrics = get_metrics()
with metrics.track('read', tags={'query': 'user_lookup'}):
    user = db.query('SELECT * FROM users WHERE id = ?', user_id)


Pattern 2: Instance-based (more explicit)
================================================
from phase_h_integration import MetricsMiddleware

# Create instance
metrics = MetricsMiddleware(sample_rate=0.1)
metrics.start_background_check(interval_sec=60)

# In operation code
with metrics.track('read'):
    result = database.read()


Pattern 3: Manual timing (for complex operations)
================================================
from phase_h_integration import get_metrics
import time

metrics = get_metrics()

start = time.perf_counter()
try:
    # Complex operation
    result = expensive_operation()
    duration = (time.perf_counter() - start) * 1000
    metrics.record('expensive_op', duration, success=True,
                   tags={'operation': 'data_pipeline'})
except Exception as e:
    duration = (time.perf_counter() - start) * 1000
    metrics.record('expensive_op', duration, success=False,
                   error_message=str(e))


Pattern 4: Sampling control
================================================
# Start with low sampling (1% for development)
metrics = init_metrics(sample_rate=0.01)

# Later increase for production investigation
metrics.collector.sample_rate = 0.5

# Or capture everything temporarily
metrics.collector.sample_rate = 1.0


Pattern 5: Monitoring loops
================================================
# In monitoring/admin code
from phase_h_integration import get_metrics

metrics = get_metrics()

# Get current health
health = metrics.get_health_status()
print(f"System status: {health['status']}")
print(f"Anomalies: {len(health['anomalies'])}")

# Get detailed metrics
current_metrics = metrics.get_current_metrics()
for op_type, stats in current_metrics.items():
    print(f"{op_type}: p95={stats['p95']:.2f}ms, errors={stats['error_count']}")


Pattern 6: Health checks (readiness/liveness probes)
================================================
from phase_h_integration import get_metrics

def health_check():
    metrics = get_metrics()
    health = metrics.get_health_status()

    if health['status'] == 'unhealthy':
        return {'ready': False, 'reason': health['summary']}
    return {'ready': True}
"""
