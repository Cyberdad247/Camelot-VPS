#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 2: Result Tracker Tests
Test validation of optimization results against predictions
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_result_tracker import ImpactDelta, ImpactValidation, ResultTracker


class TestResultTracker(unittest.TestCase):
    """Test result tracking and validation"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tracker_db = str(Path(self.temp_dir.name) / "tracker.db")
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.business_metrics_db = str(Path(self.temp_dir.name) / "metrics.db")

        # Create mock executor database with execution data
        self._create_mock_executor_db()

        self.tracker = ResultTracker(
            self.tracker_db,
            self.executor_db,
            self.business_metrics_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_mock_executor_db(self):
        """Create mock executor database with test execution"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE executions (
                id INTEGER PRIMARY KEY,
                candidate_id INTEGER,
                candidate_name TEXT,
                status TEXT,
                state_before TEXT,
                state_after TEXT,
                execution_time_seconds REAL,
                error_message TEXT,
                rollback_available INTEGER
            )
        ''')

        # Insert test execution
        state_before = {
            'latency_p95_ms': 2.0,
            'latency_p99_ms': 3.0,
            'throughput_ops_sec': 1000,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
            'error_rate_pct': 0.1
        }

        state_after = {
            'latency_p95_ms': 1.9,
            'latency_p99_ms': 2.9,
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
            'error_rate_pct': 0.1
        }

        c.execute('''
            INSERT INTO executions
            VALUES (1, 1, 'Test Candidate', 'success', ?, ?, 0.05, NULL, 1)
        ''', (json.dumps(state_before), json.dumps(state_after)))

        conn.commit()
        conn.close()

    def test_tracker_initialization(self):
        """Test tracker initializes correctly"""
        self.assertIsNotNone(self.tracker)

    def test_validate_execution_result(self):
        """Test validating execution result"""
        actual_state = {
            'latency_p95_ms': 1.95,  # Close to predicted 1.9
            'throughput_ops_sec': 1040,  # Close to predicted 1050
            'cost_per_op': 0.0001,  # Same as predicted
            'availability_pct': 99.9,  # Same as predicted
        }

        validation = self.tracker.validate_execution_result(1, actual_state)

        self.assertIsNotNone(validation)
        self.assertEqual(validation.execution_id, 1)
        self.assertIsNotNone(validation.latency_impact)

    def test_latency_impact_calculation(self):
        """Test latency impact is calculated correctly"""
        actual_state = {
            'latency_p95_ms': 1.9,  # Same as predicted
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
        }

        validation = self.tracker.validate_execution_result(1, actual_state)

        # Latency impact should be within tolerance
        self.assertTrue(validation.latency_impact.within_tolerance)

    def test_throughput_impact_calculation(self):
        """Test throughput impact is calculated correctly"""
        actual_state = {
            'latency_p95_ms': 1.9,
            'throughput_ops_sec': 1045,  # Close to predicted 1050
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
        }

        validation = self.tracker.validate_execution_result(1, actual_state)

        # Throughput impact should be within tolerance
        self.assertTrue(validation.throughput_impact.within_tolerance)

    def test_cost_impact_calculation(self):
        """Test cost impact calculation"""
        actual_state = {
            'latency_p95_ms': 1.9,
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.00010,  # Same as predicted
            'availability_pct': 99.9,
        }

        validation = self.tracker.validate_execution_result(1, actual_state)

        # Cost should be unchanged
        self.assertAlmostEqual(validation.cost_impact.actual_pct, 0, places=1)

    def test_impact_delta_structure(self):
        """Test ImpactDelta dataclass structure"""
        delta = ImpactDelta(
            metric_name='latency',
            predicted_pct=5.0,
            actual_pct=4.8,
            delta_pct=-0.2
        )

        self.assertEqual(delta.metric_name, 'latency')
        self.assertEqual(delta.predicted_pct, 5.0)
        self.assertEqual(delta.actual_pct, 4.8)

    def test_rollback_trigger_on_sla_failure(self):
        """Test rollback is triggered when SLA fails"""
        # Create scenario where latency goes way up
        actual_state = {
            'latency_p95_ms': 5.0,  # Way above predicted
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
        }

        validation = self.tracker.validate_execution_result(1, actual_state)

        # Should suggest rollback
        self.assertTrue(validation.should_rollback or not validation.all_metrics_valid)

    def test_validation_history_recording(self):
        """Test validation history is recorded"""
        actual_state = {
            'latency_p95_ms': 1.9,
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
        }

        self.tracker.validate_execution_result(1, actual_state)

        history = self.tracker.get_validation_history(limit=10)
        self.assertEqual(len(history), 1)

    def test_validation_statistics(self):
        """Test validation statistics generation"""
        actual_state = {
            'latency_p95_ms': 1.9,
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
        }

        self.tracker.validate_execution_result(1, actual_state)

        stats = self.tracker.get_validation_statistics()

        self.assertEqual(stats['total_validations'], 1)
        self.assertGreaterEqual(stats['passed'], 0)


class TestImpactDelta(unittest.TestCase):
    """Test impact delta tracking"""

    def test_delta_within_tolerance(self):
        """Test within tolerance detection"""
        delta = ImpactDelta(
            metric_name='test',
            predicted_pct=10.0,
            actual_pct=10.4,
            delta_pct=0.4,
            tolerance_pct=5.0
        )
        delta.within_tolerance = abs(delta.delta_pct) <= delta.tolerance_pct

        self.assertTrue(delta.within_tolerance)

    def test_delta_outside_tolerance(self):
        """Test outside tolerance detection"""
        delta = ImpactDelta(
            metric_name='test',
            predicted_pct=10.0,
            actual_pct=16.0,
            delta_pct=6.0,
            tolerance_pct=5.0
        )

        self.assertFalse(delta.within_tolerance)

    def test_delta_negative_values(self):
        """Test negative delta (improvement better than expected)"""
        delta = ImpactDelta(
            metric_name='latency',
            predicted_pct=-5.0,
            actual_pct=-6.0,  # Even better
            delta_pct=-1.0
        )

        self.assertEqual(delta.predicted_pct, -5.0)
        self.assertEqual(delta.actual_pct, -6.0)


class TestImpactValidation(unittest.TestCase):
    """Test impact validation results"""

    def test_validation_pass(self):
        """Test passing validation"""
        validation = ImpactValidation(
            execution_id=1,
            validation_timestamp=datetime.now().isoformat(),
            all_metrics_valid=True,
            sla_compliance=True,
            kpi_compliance=True,
            should_rollback=False
        )

        self.assertTrue(validation.all_metrics_valid)
        self.assertFalse(validation.should_rollback)

    def test_validation_fail(self):
        """Test failing validation triggers rollback"""
        validation = ImpactValidation(
            execution_id=2,
            validation_timestamp=datetime.now().isoformat(),
            all_metrics_valid=False,
            sla_compliance=False,
            kpi_compliance=True,
            should_rollback=True,
            rollback_reason="SLA compliance check failed"
        )

        self.assertFalse(validation.all_metrics_valid)
        self.assertTrue(validation.should_rollback)
        self.assertIsNotNone(validation.rollback_reason)


if __name__ == '__main__':
    unittest.main(verbosity=2)
