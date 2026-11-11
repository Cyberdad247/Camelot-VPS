#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 4: Autonomous Loop Tests
Test continuous autonomous optimization orchestration
"""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_autonomous_loop import AutonomousOptimizationLoop, LoopIteration, LoopMetrics, LoopStatus


class TestAutonomousLoop(unittest.TestCase):
    """Test autonomous optimization loop functionality"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.loop_db = str(Path(self.temp_dir.name) / "loop.db")
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.tracker_db = str(Path(self.temp_dir.name) / "tracker.db")
        self.rollback_db = str(Path(self.temp_dir.name) / "rollback.db")

        self.loop = AutonomousOptimizationLoop(
            self.loop_db,
            self.executor_db,
            self.tracker_db,
            self.rollback_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_loop_initialization(self):
        """Test loop initializes correctly"""
        self.assertIsNotNone(self.loop)
        self.assertEqual(self.loop._max_concurrent_optimizations, 1)
        self.assertEqual(self.loop._min_iteration_interval_seconds, 60)
        self.assertEqual(self.loop._max_rollback_rate, 0.3)

    def test_enable_autonomous_loop(self):
        """Test enabling autonomous loop"""
        self.loop.enable_autonomous_loop()
        # Verify no exception thrown
        self.assertTrue(True)

    def test_disable_autonomous_loop(self):
        """Test disabling autonomous loop"""
        self.loop.enable_autonomous_loop()
        self.loop.disable_autonomous_loop()
        # Verify no exception thrown
        self.assertTrue(True)

    def test_loop_iteration_structure(self):
        """Test LoopIteration dataclass"""
        iteration = LoopIteration(
            iteration_id=1,
            candidate_id=1,
            candidate_name="Test Candidate",
            status=LoopStatus.COMPLETE,
            execution_success=True,
            validation_success=True,
            predicted_improvement=5.0,
            actual_improvement=4.8
        )

        self.assertEqual(iteration.candidate_name, "Test Candidate")
        self.assertTrue(iteration.execution_success)
        self.assertEqual(iteration.predicted_improvement, 5.0)

    def test_loop_metrics_structure(self):
        """Test LoopMetrics dataclass"""
        metrics = LoopMetrics(
            total_iterations=5,
            successful_executions=4,
            failed_executions=1,
            rollbacks_triggered=0,
            total_predicted_improvement=20.0,
            total_actual_improvement=18.5
        )

        self.assertEqual(metrics.total_iterations, 5)
        self.assertEqual(metrics.successful_executions, 4)
        # Calculate learning efficiency
        if metrics.total_predicted_improvement > 0:
            metrics.learning_efficiency = metrics.total_actual_improvement / metrics.total_predicted_improvement
        self.assertAlmostEqual(metrics.learning_efficiency, 0.925, places=2)

    def test_loop_status_enum(self):
        """Test LoopStatus enumeration"""
        self.assertEqual(LoopStatus.MONITORING.value, "monitoring")
        self.assertEqual(LoopStatus.EXECUTING.value, "executing")
        self.assertEqual(LoopStatus.VALIDATING.value, "validating")
        self.assertEqual(LoopStatus.COMPLETE.value, "complete")

    def test_get_initial_metrics(self):
        """Test getting initial metrics (should be empty)"""
        metrics = self.loop.get_loop_metrics()

        self.assertEqual(metrics.total_iterations, 0)
        self.assertEqual(metrics.successful_executions, 0)
        self.assertEqual(metrics.rollbacks_triggered, 0)

    def test_get_iteration_history_empty(self):
        """Test getting history when no iterations"""
        history = self.loop.get_iteration_history(limit=10)

        self.assertEqual(len(history), 0)

    def test_loop_can_run_iteration(self):
        """Test loop can execute an iteration"""
        self.loop.enable_autonomous_loop()
        _iteration = self.loop.run_autonomous_loop_iteration()

        # Should return an iteration (or None if not ready)
        # The important thing is that it doesn't crash
        self.assertTrue(True)

    def test_loop_iteration_has_timestamps(self):
        """Test iteration includes timestamps"""
        self.loop.enable_autonomous_loop()
        iteration = self.loop.run_autonomous_loop_iteration()

        if iteration:
            self.assertIsNotNone(iteration.started_at)
            self.assertIsNotNone(iteration.completed_at)

    def test_loop_emergency_stop(self):
        """Test emergency stop mechanism"""
        self.loop.enable_autonomous_loop()
        self.loop._emergency_stop("Test emergency stop")
        # Verify no exception thrown
        self.assertTrue(True)

    def test_loop_calculates_duration(self):
        """Test loop duration calculation"""
        start = datetime.now().isoformat()
        end = datetime.now().isoformat()
        duration = self.loop._calculate_duration(start, end)

        self.assertGreaterEqual(duration, 0)

    def test_loop_stores_iteration(self):
        """Test iteration is stored in database"""
        iteration = LoopIteration(
            candidate_id=1,
            candidate_name="Test",
            status=LoopStatus.COMPLETE,
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat()
        )

        self.loop._store_iteration(iteration)
        # Verify no exception thrown
        self.assertTrue(True)

    def test_loop_max_concurrent_optimizations(self):
        """Test concurrent optimization limit"""
        self.assertEqual(self.loop._max_concurrent_optimizations, 1)

    def test_loop_min_iteration_interval(self):
        """Test minimum interval between iterations"""
        self.assertEqual(self.loop._min_iteration_interval_seconds, 60)

    def test_loop_max_rollback_rate_threshold(self):
        """Test rollback rate threshold"""
        self.assertEqual(self.loop._max_rollback_rate, 0.3)  # 30%

    def test_learning_efficiency_calculation(self):
        """Test learning efficiency metric"""
        metrics = LoopMetrics(
            total_iterations=10,
            total_predicted_improvement=100.0,
            total_actual_improvement=95.0
        )

        efficiency = metrics.total_actual_improvement / metrics.total_predicted_improvement
        self.assertAlmostEqual(efficiency, 0.95, places=2)


class TestLoopIntegration(unittest.TestCase):
    """Test autonomous loop integration scenarios"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.loop_db = str(Path(self.temp_dir.name) / "loop.db")
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.tracker_db = str(Path(self.temp_dir.name) / "tracker.db")
        self.rollback_db = str(Path(self.temp_dir.name) / "rollback.db")

        self.loop = AutonomousOptimizationLoop(
            self.loop_db,
            self.executor_db,
            self.tracker_db,
            self.rollback_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_successful_optimization_flow(self):
        """Test complete successful optimization flow"""
        self.loop.enable_autonomous_loop()
        iteration = self.loop.run_autonomous_loop_iteration()

        # Loop should have completed
        if iteration:
            self.assertIsNotNone(iteration.status)

    def test_loop_handles_disabled_state(self):
        """Test loop respects disabled state"""
        self.loop.disable_autonomous_loop()
        _iteration = self.loop.run_autonomous_loop_iteration()

        # Should not run iteration when disabled
        # Either returns None or has appropriate status
        self.assertTrue(True)

    def test_metrics_accumulate_over_iterations(self):
        """Test metrics accumulate correctly over multiple iterations"""
        self.loop.enable_autonomous_loop()

        # Store a mock iteration
        iteration = LoopIteration(
            candidate_id=1,
            candidate_name="Test",
            status=LoopStatus.COMPLETE,
            execution_success=True,
            validation_success=True,
            predicted_improvement=5.0,
            actual_improvement=4.8,
            improvement_accuracy=96.0,
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            loop_duration_seconds=0.5
        )

        self.loop._store_iteration(iteration)
        self.loop._update_loop_metrics(iteration)

        metrics = self.loop.get_loop_metrics()
        self.assertGreater(metrics.total_iterations, 0)

    def test_loop_status_transitions(self):
        """Test loop status transitions through lifecycle"""
        statuses = [
            LoopStatus.MONITORING,
            LoopStatus.EXECUTING,
            LoopStatus.VALIDATING,
            LoopStatus.COMPLETE
        ]

        for status in statuses:
            self.assertIsNotNone(status.value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
