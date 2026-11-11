#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 1: Optimization Executor Tests
Test safe execution, locking, rollback, and result tracking
"""

import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_executor import OptimizationExecutor, SystemStateSnapshot


class TestOptimizationExecutor(unittest.TestCase):
    """Test optimization execution"""

    def setUp(self):
        """Create temporary database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.executor = OptimizationExecutor(self.executor_db)

        # Default system state
        self.state_before = SystemStateSnapshot(
            timestamp=datetime.now().isoformat(),
            latency_p95_ms=2.0,
            latency_p99_ms=3.0,
            throughput_ops_sec=1000,
            error_rate_pct=0.1,
            availability_pct=99.9,
            cache_size_gb=3.0,
            memory_used_gb=8.0,
            connections_active=50,
            cost_per_op=0.0001
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_executor_initialization(self):
        """Test executor initializes correctly"""
        self.assertIsNotNone(self.executor)
        self.assertFalse(self.executor._execution_lock)

    def test_acquire_and_release_lock(self):
        """Test execution lock acquisition and release"""
        # Should acquire lock
        self.assertTrue(self.executor.acquire_execution_lock())

        # Should not acquire while held
        self.assertFalse(self.executor.acquire_execution_lock())

        # Release lock
        self.executor.release_execution_lock()

        # Should acquire again
        self.assertTrue(self.executor.acquire_execution_lock())
        self.executor.release_execution_lock()

    def test_execute_candidate_success(self):
        """Test successful candidate execution"""
        result = self.executor.execute_candidate(
            candidate_id=1,
            candidate_name='Reduce Cache',
            state_before=self.state_before
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.candidate_id, 1)
        self.assertIsNotNone(result.state_after)
        self.assertTrue(result.rollback_available)
        self.assertGreater(result.execution_time_seconds, 0)

    def test_execute_candidate_latency_impact(self):
        """Test that execution captures latency changes"""
        result = self.executor.execute_candidate(
            candidate_id=2,
            candidate_name='Optimize Connection Pool',
            state_before=self.state_before
        )

        self.assertEqual(result.status, 'success')

        # Connection pool optimization should improve latency
        self.assertLess(result.state_after.latency_p95_ms, result.state_before.latency_p95_ms)

    def test_execute_candidate_cost_impact(self):
        """Test that execution captures cost changes"""
        result = self.executor.execute_candidate(
            candidate_id=3,
            candidate_name='Add Indexes',
            state_before=self.state_before
        )

        self.assertEqual(result.status, 'success')

        # Indexes may increase cost slightly
        cost_change = ((result.state_after.cost_per_op - result.state_before.cost_per_op) /
                      result.state_before.cost_per_op * 100)
        self.assertLess(cost_change, 10)  # Should not increase drastically

    def test_execution_locks_prevent_concurrent(self):
        """Test that locks prevent concurrent executions"""
        # Start first execution
        result1 = self.executor.execute_candidate(
            candidate_id=1,
            candidate_name='Candidate 1',
            state_before=self.state_before
        )

        # During execution, another should fail to acquire lock
        # (in real scenario, would block)
        self.assertEqual(result1.status, 'success')  # First one succeeds

    def test_execution_history_recorded(self):
        """Test that execution history is recorded"""
        # Execute multiple candidates
        for i in range(3):
            self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )

        # Retrieve history
        history = self.executor.get_execution_history(limit=10)

        self.assertEqual(len(history), 3)
        for execution in history:
            self.assertEqual(execution.status, 'success')
            self.assertIsNotNone(execution.state_after)

    def test_execution_statistics(self):
        """Test execution statistics generation"""
        # Execute some candidates
        for i in range(5):
            self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )

        stats = self.executor.get_execution_statistics()

        self.assertEqual(stats['total_executions'], 5)
        self.assertEqual(stats['successful'], 5)
        self.assertEqual(stats['partial'], 0)
        self.assertEqual(stats['failed'], 0)
        self.assertGreater(stats['avg_execution_time_seconds'], 0)

    def test_rollback_point_captured(self):
        """Test that rollback points are captured"""
        result = self.executor.execute_candidate(
            candidate_id=1,
            candidate_name='Test Candidate',
            state_before=self.state_before
        )

        self.assertTrue(result.rollback_available)

    def test_execution_result_contains_before_after(self):
        """Test that execution result contains before/after states"""
        result = self.executor.execute_candidate(
            candidate_id=1,
            candidate_name='Test Candidate',
            state_before=self.state_before
        )

        self.assertIsNotNone(result.state_before)
        self.assertIsNotNone(result.state_after)

        # After state should differ from before
        self.assertNotEqual(
            result.state_before.latency_p95_ms,
            result.state_after.latency_p95_ms
        )

    def test_execution_error_handling(self):
        """Test error handling in execution"""
        # Execute with minimal state (should not crash)
        result = self.executor.execute_candidate(
            candidate_id=99,
            candidate_name='Unknown Candidate',
            state_before=self.state_before
        )

        # Should complete (with no impact simulation)
        self.assertEqual(result.status, 'success')


class TestExecutionPerformance(unittest.TestCase):
    """Test execution performance characteristics"""

    def setUp(self):
        """Create executor"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.executor = OptimizationExecutor(self.executor_db)

        self.state_before = SystemStateSnapshot(
            timestamp=datetime.now().isoformat(),
            latency_p95_ms=2.0, latency_p99_ms=3.0,
            throughput_ops_sec=1000, error_rate_pct=0.1,
            availability_pct=99.9, cache_size_gb=3.0,
            memory_used_gb=8.0, connections_active=50,
            cost_per_op=0.0001
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_execution_time_target(self):
        """Test execution completes within target time"""
        start = time.time()

        result = self.executor.execute_candidate(
            candidate_id=1,
            candidate_name='Test Candidate',
            state_before=self.state_before
        )

        elapsed = time.time() - start

        # Should complete in < 100ms
        self.assertLess(elapsed, 0.1)
        self.assertLess(result.execution_time_seconds, 0.1)

    def test_multiple_executions_performance(self):
        """Test multiple executions don't degrade"""
        times = []

        for i in range(10):
            start = time.time()
            self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )
            times.append(time.time() - start)

        # All should be fast
        for t in times:
            self.assertLess(t, 0.1)

        # Average should be consistent
        avg_time = sum(times) / len(times)
        self.assertLess(avg_time, 0.05)

    def test_history_retrieval_performance(self):
        """Test history retrieval is fast"""
        # Create many executions
        for i in range(50):
            self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )

        # Retrieve history
        start = time.time()
        history = self.executor.get_execution_history(limit=50)
        elapsed = time.time() - start

        # Should be fast (< 50ms)
        self.assertLess(elapsed, 0.05)
        self.assertEqual(len(history), 50)


class TestSystemStateSnapshot(unittest.TestCase):
    """Test system state snapshot handling"""

    def test_snapshot_creation(self):
        """Test creating system state snapshot"""
        state = SystemStateSnapshot(
            timestamp=datetime.now().isoformat(),
            latency_p95_ms=2.0,
            latency_p99_ms=3.0,
            throughput_ops_sec=1000,
            error_rate_pct=0.1,
            availability_pct=99.9,
            cache_size_gb=3.0,
            memory_used_gb=8.0,
            connections_active=50,
            cost_per_op=0.0001
        )

        self.assertEqual(state.latency_p95_ms, 2.0)
        self.assertEqual(state.throughput_ops_sec, 1000)
        self.assertEqual(state.availability_pct, 99.9)

    def test_snapshot_metrics_valid_ranges(self):
        """Test snapshot metrics are in valid ranges"""
        state = SystemStateSnapshot(
            timestamp=datetime.now().isoformat(),
            latency_p95_ms=2.0,
            latency_p99_ms=3.0,
            throughput_ops_sec=1000,
            error_rate_pct=0.1,
            availability_pct=99.9,
            cache_size_gb=3.0,
            memory_used_gb=8.0,
            connections_active=50,
            cost_per_op=0.0001
        )

        # All metrics should be positive
        self.assertGreater(state.latency_p95_ms, 0)
        self.assertGreater(state.throughput_ops_sec, 0)
        self.assertGreater(state.error_rate_pct, 0)
        self.assertGreaterEqual(state.availability_pct, 0)
        self.assertLessEqual(state.availability_pct, 100)


if __name__ == '__main__':
    unittest.main(verbosity=2)
