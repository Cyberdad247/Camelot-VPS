#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H: Anomaly Detection Engine
Detects deviations from healthy baseline
Generates alerts on anomalies
"""

import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Anomaly:
    """Single detected anomaly"""
    timestamp: float
    severity: str  # 'warning' or 'critical'
    metric_name: str
    baseline_value: float
    current_value: float
    reason: str


class AnomalyDetector:
    """Detect deviations from baseline"""

    def __init__(self, baseline_metrics: Dict[str, float], db_path: str = "control_plane/anomalies.db"):
        """
        Args:
            baseline_metrics: Healthy baseline from Phase G tests
                {
                    'read_p95_ms': 1.3,
                    'read_p99_ms': 5.8,
                    'write_p95_ms': 2.1,
                    ...
                }
            db_path: Path to alert log database
        """
        self.baseline = baseline_metrics
        self.db_path = db_path
        self.warning_threshold = 1.5  # 1.5x baseline = warning
        self.critical_threshold = 3.0  # 3x baseline = critical
        self._init_db()

    def _init_db(self):
        """Create SQLite schema for alert log"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    severity TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    baseline_value REAL NOT NULL,
                    current_value REAL NOT NULL,
                    reason TEXT NOT NULL,
                    resolved INTEGER DEFAULT 0
                )
            ''')

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to init anomaly db: {e}")

    def check(self, current_metrics: Dict[str, Dict]) -> Dict:
        """
        Check current metrics against baseline.

        Args:
            current_metrics: Output from MetricsCollector.get_all_operation_stats()
                {
                    'read': {'p50': 1.2, 'p95': 5.3, 'p99': 12.1, ...},
                    'write': {'p50': 2.1, 'p95': 8.9, ...},
                    ...
                }

        Returns:
            {
                'anomalies': [Anomaly, ...],
                'severity': 'ok' | 'warning' | 'critical',
                'timestamp': 1234567890.123
            }
        """
        anomalies: List[Anomaly] = []
        max_severity = 'ok'

        for op_type, stats in current_metrics.items():
            if 'error' in stats or stats.get('status') != 'ok':
                continue

            # Check p95 latency
            p95_key = f"{op_type}_p95_ms"
            if p95_key in self.baseline:
                p95_baseline = self.baseline[p95_key]
                p95_current = stats.get('p95', 0)

                severity = self._check_threshold(p95_baseline, p95_current)
                if severity:
                    anomalies.append(Anomaly(
                        timestamp=time.time(),
                        severity=severity,
                        metric_name=p95_key,
                        baseline_value=p95_baseline,
                        current_value=p95_current,
                        reason=f"p95 latency elevated: {p95_current:.2f}ms vs baseline {p95_baseline:.2f}ms"
                    ))
                    max_severity = self._max_severity(max_severity, severity)

            # Check error rate
            error_rate = stats.get('error_rate', 0)
            if error_rate > 0.001:  # > 0.1%
                severity = 'warning' if error_rate < 0.01 else 'critical'
                anomalies.append(Anomaly(
                    timestamp=time.time(),
                    severity=severity,
                    metric_name=f"{op_type}_error_rate",
                    baseline_value=0.0,
                    current_value=error_rate,
                    reason=f"Error rate elevated: {error_rate*100:.2f}% in {op_type}"
                ))
                max_severity = self._max_severity(max_severity, severity)

        # Log anomalies to database
        for anomaly in anomalies:
            self._log_anomaly(anomaly)

        return {
            'anomalies': anomalies,
            'count': len(anomalies),
            'severity': max_severity,
            'timestamp': time.time()
        }

    def _check_threshold(self, baseline: float, current: float) -> Optional[str]:
        """
        Check if current value exceeds thresholds.

        Returns:
            'critical', 'warning', or None
        """
        if current >= baseline * self.critical_threshold:
            return 'critical'
        elif current >= baseline * self.warning_threshold:
            return 'warning'
        return None

    def _max_severity(self, sev1: str, sev2: str) -> str:
        """Return max severity"""
        severity_order = {'ok': 0, 'warning': 1, 'critical': 2}
        return sev1 if severity_order.get(sev1, 0) >= severity_order.get(sev2, 0) else sev2

    def _log_anomaly(self, anomaly: Anomaly):
        """Log anomaly to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO anomalies
                (timestamp, severity, metric_name, baseline_value, current_value, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (anomaly.timestamp, anomaly.severity, anomaly.metric_name,
                  anomaly.baseline_value, anomaly.current_value, anomaly.reason))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to log anomaly: {e}")

    def get_alerts(self, hours: int = 1) -> List[Dict]:
        """Get recent unresolved anomalies"""
        cutoff_time = time.time() - (hours * 3600)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, severity, metric_name, baseline_value, current_value, reason
                FROM anomalies
                WHERE timestamp > ? AND resolved = 0
                ORDER BY timestamp DESC
            ''', (cutoff_time,))

            rows = cursor.fetchall()
            conn.close()

            alerts = []
            for row in rows:
                alerts.append({
                    'timestamp': row[0],
                    'severity': row[1],
                    'metric_name': row[2],
                    'baseline_value': row[3],
                    'current_value': row[4],
                    'reason': row[5]
                })
            return alerts

        except Exception as e:
            print(f"[WARN] Failed to get alerts: {e}")
            return []

    def get_health_summary(self, current_metrics: Dict[str, Dict]) -> Dict:
        """
        Get overall health summary.

        Returns:
            {
                'status': 'healthy' | 'degraded' | 'unhealthy',
                'anomaly_count': 5,
                'critical_count': 1,
                'warning_count': 4,
                'summary': '1 critical, 4 warnings'
            }
        """
        check_result = self.check(current_metrics)
        anomalies = check_result['anomalies']

        critical_count = sum(1 for a in anomalies if a.severity == 'critical')
        warning_count = sum(1 for a in anomalies if a.severity == 'warning')

        if critical_count > 0:
            status = 'unhealthy'
        elif warning_count > 0:
            status = 'degraded'
        else:
            status = 'healthy'

        summary = f"{critical_count} critical, {warning_count} warnings"

        return {
            'status': status,
            'anomaly_count': len(anomalies),
            'critical_count': critical_count,
            'warning_count': warning_count,
            'summary': summary,
            'timestamp': time.time()
        }

    def resolve_anomaly(self, anomaly_id: int):
        """Mark anomaly as resolved"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE anomalies SET resolved = 1 WHERE id = ?', (anomaly_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to resolve anomaly: {e}")

    @staticmethod
    def get_phase_g_baseline() -> Dict[str, float]:
        """
        Return baseline from Phase G test results.
        From test_results_local_20260622_204006/baseline.json
        """
        return {
            # Baseline latencies (from Phase G tests)
            'sqlite_avg_ms': 0.0078,
            'sqlite_p95_ms': 0.0182,
            'routing_avg_ms': 0.00039,
            'routing_p95_ms': 0.00087,
            'compression_avg_ms': 0.164,
            'compression_p95_ms': 1.586,

            # Load test sustained 1000 RPS results
            'read_p50_ms': 0.4,
            'read_p95_ms': 1.3,
            'read_p99_ms': 5.8,
            'write_p50_ms': 0.5,
            'write_p95_ms': 1.3,
            'write_p99_ms': 5.8,
            'route_p50_ms': 0.4,
            'route_p95_ms': 1.2,
            'route_p99_ms': 2.8,

            # Acceptable thresholds
            'max_error_rate': 0.001,  # 0.1%
            'max_memory_growth_mb_per_min': 5,
        }
