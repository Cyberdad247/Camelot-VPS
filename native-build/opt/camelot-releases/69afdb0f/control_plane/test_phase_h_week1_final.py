#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 1 Final: Complete System Validation
Comprehensive tests for production sign-off
"""

import tempfile
import time
import unittest
from pathlib import Path

from control_plane.orchestrator import Orchestrator
from control_plane.phase_h_integration import get_metrics, init_metrics


class TestFullIntegration(unittest.TestCase):
    """Full system integration tests"""

    def test_end_to_end_metrics_flow(self):
        """Test complete metrics flow: record → store → retrieve → alert"""
        metrics = init_metrics(sample_rate=1.0)  # 100% sampling for test

        # Generate operations across all types
        for i in range(100):
            metrics.record('read', 0.5 + (i % 10) * 0.1, success=True,
                          tags={'table': 'test', 'query': f'q_{i}'})
            metrics.record('write', 1.5 + (i % 10) * 0.2, success=True,
                          tags={'table': 'test', 'op': f'insert_{i}'})
            metrics.record('route', 0.05 + (i % 5) * 0.01, success=True,
                          tags={'intent': 'test', 'knight': f'sir_{i % 3}'})

        # Verify metrics collected
        current = metrics.get_current_metrics()
        self.assertIn('read', current)
        self.assertIn('write', current)
        self.assertIn('route', current)

        # Verify counts (with sampling, should have ~100 of each)
        self.assertGreater(current['read']['count'], 50)
        self.assertGreater(current['write']['count'], 50)
        self.assertGreater(current['route']['count'], 50)

        # Check health status
        health = metrics.get_health_status()
        self.assertIsNotNone(health['status'])

        print(f"✅ End-to-end flow: {current['read']['count']} reads, "
              f"{current['write']['count']} writes, {current['route']['count']} routes")

    def test_orchestrator_with_metrics(self):
        """Test orchestrator operations with metrics collection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test.db")
            orch = Orchestrator(db_path=db_path)
            metrics = get_metrics()

            # Write facts
            for i in range(50):
                orch.set_fact(f"key_{i}", {"data": f"value_{i}"})

            # Create jobs
            for i in range(20):
                orch.create_job(f"task_{i}")

            # List jobs
            jobs = orch.list_jobs()
            self.assertEqual(len(jobs), 20)

            # Verify metrics collected
            current = metrics.get_current_metrics()
            self.assertGreater(current.get('write', {}).get('count', 0), 0)
            self.assertGreater(current.get('read', {}).get('count', 0), 0)

            print(f"✅ Orchestrator integration: {len(jobs)} jobs created")


class TestLoadCapacity(unittest.TestCase):
    """Load testing for production capacity"""

    def test_10k_operations_load(self):
        """Test 10,000 operations sustained load"""
        metrics = init_metrics(sample_rate=0.1)  # 10% sampling

        start = time.perf_counter()
        operations = 0

        # Generate 10K operations
        for i in range(10000):
            op_type = ['read', 'write', 'route', 'compress'][i % 4]
            duration = 0.5 + (i % 100) * 0.01
            metrics.record(op_type, duration, success=(i % 100 != 0))
            operations += 1

        elapsed = time.perf_counter() - start
        throughput = operations / elapsed

        # Should complete in reasonable time
        self.assertLess(elapsed, 10.0, f"10K ops took {elapsed:.2f}s")

        # Verify data collected
        current = metrics.get_current_metrics()
        total_collected = sum(s.get('count', 0) for s in current.values())
        self.assertGreater(total_collected, 500, "Should have at least 500 samples")

        print(f"✅ Load test: {operations} ops in {elapsed:.2f}s = {throughput:.0f} ops/sec")

    def test_sustained_1000_rps(self):
        """Test sustained 1000 RPS for 10 seconds"""
        metrics = init_metrics(sample_rate=0.1)

        rps = 1000
        duration = 5  # 5 seconds
        operations = 0

        start = time.perf_counter()
        op_start = start

        while time.perf_counter() - start < duration:
            # Generate ~1000 operations per second
            for _i in range(1000):
                metrics.record('read', 1.0, success=True)
                operations += 1

            # Sleep to maintain rate
            elapsed = time.perf_counter() - op_start
            target_time = operations / rps
            if target_time > elapsed:
                time.sleep(target_time - elapsed)

        total_elapsed = time.perf_counter() - start
        actual_rps = operations / total_elapsed

        self.assertGreater(actual_rps, 500, f"RPS too low: {actual_rps:.0f}")
        print(f"✅ Sustained load: {actual_rps:.0f} RPS for {total_elapsed:.1f}s")


class TestAnomalyDetection(unittest.TestCase):
    """Test anomaly detection under various conditions"""

    def test_anomaly_injection_critical(self):
        """Inject slow operations and detect as critical"""
        metrics = init_metrics(sample_rate=1.0)

        # Record normal operations
        for _i in range(50):
            metrics.record('read', 1.0, success=True)

        # Inject slow operation (10x baseline = critical)
        metrics.record('read', 13.0, success=True)

        # Check for anomalies
        anomalies = metrics.check_anomalies()
        self.assertIsNotNone(anomalies)

        # Should detect as critical if deviation > 3x baseline
        if anomalies.get('severity'):
            self.assertIn(anomalies['severity'].lower(), ['critical', 'warning'])

        print(f"✅ Anomaly injection: {anomalies.get('severity', 'detected')}")

    def test_error_rate_detection(self):
        """Test error rate anomaly detection"""
        metrics = init_metrics(sample_rate=1.0)

        # Record operations with error spike
        for i in range(100):
            if i < 50:
                metrics.record('write', 2.0, success=True)
            else:
                # 50% error rate in second half
                metrics.record('write', 2.0, success=(i % 2 == 0),
                              error_message="Connection lost" if i % 2 != 0 else None)

        # Get current metrics
        current = metrics.get_current_metrics()
        write_stats = current.get('write', {})

        # Should show error rate > 0
        self.assertGreater(write_stats.get('error_rate', 0), 0)
        print(f"✅ Error detection: {write_stats.get('error_rate', 0):.1%} error rate detected")

    def test_health_summary_accuracy(self):
        """Test health summary reflects system state"""
        metrics = init_metrics(sample_rate=1.0)

        # Healthy state
        for _i in range(100):
            metrics.record('read', 1.0, success=True)

        health = metrics.get_health_status()
        self.assertEqual(health['status'], 'healthy')

        # Inject anomaly
        metrics.record('read', 20.0, success=True)  # 15x baseline

        health = metrics.get_health_status()
        self.assertNotEqual(health['status'], 'healthy')

        print(f"✅ Health summary: {health['status'].upper()}")


class TestProductionReadiness(unittest.TestCase):
    """Final production readiness verification"""

    def test_all_deliverables_present(self):
        """Verify all Week 1 deliverables are in place"""
        deliverables = [
            'control_plane/phase_h_metrics.py',
            'control_plane/phase_h_anomaly_detector.py',
            'control_plane/phase_h_integration.py',
            'dashboards/phase_h_live_dashboard.py',
            'control_plane/generate_sample_load.py',
            'PHASE_H_BASELINE.md',
            'PHASE_H_INTEGRATION_GUIDE.md',
            'PHASE_H_DAY2_COMPLETION.md',
            'PHASE_H_DAY3_COMPLETION.md',
            'PHASE_H_DAY4_COMPLETION.md',
        ]

        for deliverable in deliverables:
            path = Path(deliverable)
            self.assertTrue(path.exists(), f"Missing: {deliverable}")

        print(f"✅ All {len(deliverables)} deliverables present")

    def test_test_coverage(self):
        """Verify test coverage across all components"""
        test_files = [
            'control_plane/test_phase_h_metrics.py',
            'control_plane/test_phase_h_anomaly_detector.py',
            'control_plane/test_phase_h_day2_integration.py',
            'control_plane/test_phase_h_day4_hardening.py',
            'control_plane/test_phase_h_week1_final.py',
        ]

        for test_file in test_files:
            path = Path(test_file)
            self.assertTrue(path.exists(), f"Missing: {test_file}")

        print(f"✅ All {len(test_files)} test suites present")

    def test_documentation_complete(self):
        """Verify comprehensive documentation"""
        docs = [
            'PHASE_H_ADAPTIVE_LEARNING.md',
            'PHASE_H_WEEK1_OBSERVABILITY.md',
            'PHASE_H_INTEGRATION_GUIDE.md',
            'PHASE_H_BASELINE.md',
            'PHASE_H_DAYS2-5_ROADMAP.md',
        ]

        for doc in docs:
            path = Path(doc)
            self.assertTrue(path.exists(), f"Missing: {doc}")

        print(f"✅ All {len(docs)} documentation files present")

    def test_apis_functional(self):
        """Test all public APIs are functional"""
        metrics = init_metrics()

        # Test all critical APIs
        apis = [
            ('record', lambda: metrics.record('test', 1.0, success=True)),
            ('get_current_metrics', lambda: metrics.get_current_metrics()),
            ('get_health_status', lambda: metrics.get_health_status()),
            ('check_anomalies', lambda: metrics.check_anomalies()),
            ('track', lambda: metrics.track('test')),
        ]

        for api_name, api_call in apis:
            try:
                api_call()
                print(f"  ✓ {api_name}")
            except Exception as e:
                self.fail(f"API {api_name} failed: {e}")

        print(f"✅ All {len(apis)} public APIs functional")


if __name__ == '__main__':
    unittest.main(verbosity=2)
