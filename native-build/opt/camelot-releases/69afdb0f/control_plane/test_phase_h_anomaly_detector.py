#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Unit tests for Phase H AnomalyDetector
"""

import tempfile
import time
import unittest
from pathlib import Path

from phase_h_anomaly_detector import AnomalyDetector


class TestAnomalyDetector(unittest.TestCase):
    """Test AnomalyDetector class"""

    def setUp(self):
        """Create detector with test baseline"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_anomalies.db")

        self.baseline = {
            'read_p95_ms': 1.3,
            'read_p99_ms': 5.8,
            'write_p95_ms': 2.0,
            'write_p99_ms': 8.0,
            'route_p95_ms': 0.1,
        }

        self.detector = AnomalyDetector(self.baseline, db_path=self.db_path)

    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()

    def test_init_creates_database(self):
        """Test initialization creates database"""
        self.assertTrue(Path(self.db_path).exists())

    def test_check_healthy_metrics(self):
        """Test check with healthy metrics"""
        metrics = {
            'read': {'p95': 1.0, 'p99': 5.0, 'error_rate': 0.0, 'status': 'ok'},
            'write': {'p95': 1.8, 'p99': 7.0, 'error_rate': 0.0, 'status': 'ok'},
        }

        result = self.detector.check(metrics)

        self.assertEqual(result['severity'], 'ok')
        self.assertEqual(len(result['anomalies']), 0)

    def test_check_warning_threshold(self):
        """Test detection at warning threshold"""
        metrics = {
            'read': {
                'p95': 1.3 * 1.5,  # 1.5x baseline = warning
                'p99': 5.8,
                'error_rate': 0.0,
                'status': 'ok'
            }
        }

        result = self.detector.check(metrics)

        self.assertEqual(result['severity'], 'warning')
        self.assertEqual(len(result['anomalies']), 1)
        self.assertEqual(result['anomalies'][0].severity, 'warning')

    def test_check_critical_threshold(self):
        """Test detection at critical threshold"""
        metrics = {
            'read': {
                'p95': 1.3 * 3.0,  # 3x baseline = critical
                'p99': 5.8,
                'error_rate': 0.0,
                'status': 'ok'
            }
        }

        result = self.detector.check(metrics)

        self.assertEqual(result['severity'], 'critical')
        self.assertEqual(len(result['anomalies']), 1)
        self.assertEqual(result['anomalies'][0].severity, 'critical')

    def test_check_error_rate_warning(self):
        """Test error rate anomaly detection"""
        metrics = {
            'read': {
                'p95': 1.0,
                'p99': 5.0,
                'error_rate': 0.005,  # > 0.1% = warning
                'status': 'ok'
            }
        }

        result = self.detector.check(metrics)

        self.assertIn('warning', [a.severity for a in result['anomalies']])

    def test_check_error_rate_critical(self):
        """Test error rate critical threshold"""
        metrics = {
            'read': {
                'p95': 1.0,
                'p99': 5.0,
                'error_rate': 0.02,  # > 1% = critical
                'status': 'ok'
            }
        }

        result = self.detector.check(metrics)

        self.assertIn('critical', [a.severity for a in result['anomalies']])

    def test_check_multiple_anomalies(self):
        """Test detection of multiple anomalies"""
        metrics = {
            'read': {
                'p95': 1.3 * 2.0,  # warning
                'p99': 5.8,
                'error_rate': 0.01,  # critical
                'status': 'ok'
            },
            'write': {
                'p95': 2.0 * 0.8,  # healthy
                'p99': 8.0,
                'error_rate': 0.0,
                'status': 'ok'
            }
        }

        result = self.detector.check(metrics)

        self.assertEqual(len(result['anomalies']), 2)  # p95 warning + error critical
        self.assertEqual(result['severity'], 'critical')

    def test_check_skips_error_status(self):
        """Test that metrics with errors are skipped"""
        metrics = {
            'read': {
                'error': 'database connection failed',
                'status': 'error'
            }
        }

        result = self.detector.check(metrics)

        # Should skip this metric, no anomalies
        self.assertEqual(len(result['anomalies']), 0)

    def test_get_alerts_empty(self):
        """Test getting alerts when none exist"""
        alerts = self.detector.get_alerts()
        self.assertEqual(len(alerts), 0)

    def test_get_alerts_after_detection(self):
        """Test alerts are logged after detection"""
        metrics = {
            'read': {
                'p95': 1.3 * 2.0,
                'p99': 5.8,
                'error_rate': 0.0,
                'status': 'ok'
            }
        }

        self.detector.check(metrics)
        time.sleep(0.1)  # Allow time for DB write

        alerts = self.detector.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['severity'], 'warning')

    def test_resolve_anomaly(self):
        """Test resolving an anomaly"""
        metrics = {
            'read': {
                'p95': 1.3 * 2.0,
                'p99': 5.8,
                'error_rate': 0.0,
                'status': 'ok'
            }
        }

        self.detector.check(metrics)
        time.sleep(0.1)

        alerts = self.detector.get_alerts()
        self.assertEqual(len(alerts), 1)

        # Resolve first anomaly
        self.detector.resolve_anomaly(1)

        # Check again
        alerts = self.detector.get_alerts()
        self.assertEqual(len(alerts), 0)

    def test_get_health_summary_healthy(self):
        """Test health summary when healthy"""
        metrics = {
            'read': {'p95': 1.0, 'p99': 5.0, 'error_rate': 0.0, 'status': 'ok'}
        }

        summary = self.detector.get_health_summary(metrics)

        self.assertEqual(summary['status'], 'healthy')
        self.assertEqual(summary['anomaly_count'], 0)
        self.assertEqual(summary['critical_count'], 0)
        self.assertEqual(summary['warning_count'], 0)

    def test_get_health_summary_degraded(self):
        """Test health summary when degraded"""
        metrics = {
            'read': {'p95': 1.3 * 1.5, 'p99': 5.8, 'error_rate': 0.0, 'status': 'ok'}
        }

        summary = self.detector.get_health_summary(metrics)

        self.assertEqual(summary['status'], 'degraded')
        self.assertEqual(summary['warning_count'], 1)

    def test_get_health_summary_unhealthy(self):
        """Test health summary when unhealthy"""
        metrics = {
            'read': {'p95': 1.3 * 3.0, 'p99': 5.8, 'error_rate': 0.0, 'status': 'ok'}
        }

        summary = self.detector.get_health_summary(metrics)

        self.assertEqual(summary['status'], 'unhealthy')
        self.assertEqual(summary['critical_count'], 1)

    def test_phase_g_baseline(self):
        """Test getting Phase G baseline"""
        baseline = AnomalyDetector.get_phase_g_baseline()

        self.assertIn('sqlite_p95_ms', baseline)
        self.assertIn('read_p95_ms', baseline)
        self.assertIn('max_error_rate', baseline)

        # Verify values from Phase G tests
        self.assertAlmostEqual(baseline['read_p95_ms'], 1.3, places=1)
        self.assertAlmostEqual(baseline['compression_p95_ms'], 1.586, places=1)

    def test_threshold_comparison(self):
        """Test threshold comparison logic"""
        baseline = 1.0
        current_warning = 1.0 * 1.5  # 1.5x
        current_critical = 1.0 * 3.0  # 3x
        current_ok = 0.5  # Below baseline

        # Test warning
        severity = self.detector._check_threshold(baseline, current_warning)
        self.assertEqual(severity, 'warning')

        # Test critical
        severity = self.detector._check_threshold(baseline, current_critical)
        self.assertEqual(severity, 'critical')

        # Test ok
        severity = self.detector._check_threshold(baseline, current_ok)
        self.assertIsNone(severity)

    def test_max_severity(self):
        """Test severity combination logic"""
        self.assertEqual(self.detector._max_severity('ok', 'warning'), 'warning')
        self.assertEqual(self.detector._max_severity('warning', 'critical'), 'critical')
        self.assertEqual(self.detector._max_severity('ok', 'critical'), 'critical')
        self.assertEqual(self.detector._max_severity('warning', 'ok'), 'warning')


if __name__ == '__main__':
    unittest.main()
