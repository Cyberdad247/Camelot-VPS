#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 5: Load Testing & Performance Validation
Comprehensive load testing of complete autonomous system
"""

import concurrent.futures
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_autonomous_loop import AutonomousOptimizationLoop
from phase_h_executor import OptimizationExecutor, SystemStateSnapshot
from phase_h_result_tracker import ResultTracker
from phase_h_rollback import RollbackManager


class TestLoadPerformance(unittest.TestCase):
    """Load test all components under realistic scenarios"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.tracker_db = str(Path(self.temp_dir.name) / "tracker.db")
        self.rollback_db = str(Path(self.temp_dir.name) / "rollback.db")
        self.loop_db = str(Path(self.temp_dir.name) / "loop.db")

        self.executor = OptimizationExecutor(self.executor_db)
        self.tracker = ResultTracker(self.tracker_db, self.executor_db, "")
        self.rollback = RollbackManager(self.rollback_db, self.executor_db, self.tracker_db)
        self.loop = AutonomousOptimizationLoop(self.loop_db, self.executor_db, self.tracker_db, self.rollback_db)

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

    def test_executor_performance_100_executions(self):
        """Load test: 100 executions should complete < 10 seconds"""
        start = time.time()

        for i in range(100):
            self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )

        elapsed = time.time() - start

        # Target: 100 executions < 10 seconds (100ms per execution)
        self.assertLess(elapsed, 10.0, f"100 executions took {elapsed:.2f}s, target < 10s")

    def test_executor_individual_execution_time(self):
        """Performance target: Single execution < 100ms"""
        start = time.time()

        self.executor.execute_candidate(
            candidate_id=1,
            candidate_name='Test Candidate',
            state_before=self.state_before
        )

        elapsed = time.time() - start

        # Target: Single execution < 100ms
        self.assertLess(elapsed, 0.1, f"Single execution took {elapsed:.3f}s, target < 100ms")

    def test_tracker_validation_performance(self):
        """Performance target: Result validation < 50ms"""
        actual_state = {
            'latency_p95_ms': 1.9,
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
        }

        start = time.time()

        for _i in range(50):
            self.tracker.validate_execution_result(1, actual_state)

        elapsed = time.time() - start
        avg_time = elapsed / 50

        # Target: < 50ms per validation
        self.assertLess(avg_time, 0.05, f"Avg validation took {avg_time*1000:.1f}ms, target < 50ms")

    def test_rollback_performance(self):
        """Performance target: Rollback < 100ms"""
        self.rollback.enable_autonomous_loop = lambda: None  # Mock

        start = time.time()

        for _i in range(20):
            self.rollback.execute_rollback(1, "Test rollback")

        elapsed = time.time() - start
        avg_time = elapsed / 20

        # Target: < 100ms per rollback
        self.assertLess(avg_time, 0.1, f"Avg rollback took {avg_time*1000:.1f}ms, target < 100ms")

    def test_memory_stability_1000_iterations(self):
        """Test memory stability over 1000 iterations"""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        for i in range(1000):
            self.executor.execute_candidate(
                candidate_id=i % 100,
                candidate_name=f'Candidate {i % 100}',
                state_before=self.state_before
            )

            # Clear every 100 iterations
            if i % 100 == 0:
                import gc
                gc.collect()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        # Target: Memory growth < 100MB over 1000 iterations
        self.assertLess(memory_growth, 100, f"Memory grew by {memory_growth:.1f}MB, target < 100MB")

    def test_concurrent_candidate_selection(self):
        """Test candidate selection under concurrent load"""
        results = []

        def select_candidate():
            return self.loop._select_next_candidate()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(select_candidate) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All selections should succeed
        self.assertEqual(len(results), 10)

    def test_database_concurrent_writes(self):
        """Test database handles concurrent writes"""
        def execute_and_store(i):
            return self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_and_store, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All executions should complete
        self.assertEqual(len(results), 20)

    def test_end_to_end_pipeline_performance(self):
        """End-to-end: Execute -> Validate -> Rollback < 500ms"""
        actual_state = {
            'latency_p95_ms': 1.9,
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001,
            'availability_pct': 99.9,
        }

        start = time.time()

        # Execute
        _exec_result = self.executor.execute_candidate(
            candidate_id=1,
            candidate_name='Test',
            state_before=self.state_before
        )

        # Validate
        val_result = self.tracker.validate_execution_result(1, actual_state)

        # Rollback (if needed)
        if not val_result.validation_success:
            _rb_result = self.rollback.execute_rollback(1, "Test")

        elapsed = time.time() - start

        # Target: < 500ms for complete pipeline
        self.assertLess(elapsed, 0.5, f"E2E pipeline took {elapsed*1000:.1f}ms, target < 500ms")

    def test_execution_throughput_capacity(self):
        """Test maximum execution throughput"""
        start = time.time()
        count = 0

        # Execute as many as possible in 5 seconds
        while time.time() - start < 5.0:
            self.executor.execute_candidate(
                candidate_id=count % 100,
                candidate_name=f'Candidate {count % 100}',
                state_before=self.state_before
            )
            count += 1

        elapsed = time.time() - start
        throughput = count / elapsed

        # Target: > 50 executions per second
        self.assertGreater(throughput, 50, f"Throughput {throughput:.1f} ops/sec, target > 50")

    def test_metrics_consistency_under_load(self):
        """Test metrics remain consistent under load"""
        # Execute multiple iterations
        for i in range(50):
            self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )

        stats = self.executor.get_execution_statistics()

        # Total should match sum of categories
        total = stats['successful'] + stats['partial'] + stats['failed']
        self.assertEqual(stats['total_executions'], total)


class TestSystemStability(unittest.TestCase):
    """Test system stability under sustained load"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.executor = OptimizationExecutor(self.executor_db)

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

    def test_sustained_load_500_executions(self):
        """Sustained load test: 500 executions without errors"""
        errors = 0

        for i in range(500):
            try:
                result = self.executor.execute_candidate(
                    candidate_id=i,
                    candidate_name=f'Candidate {i}',
                    state_before=self.state_before
                )
                if result.status == 'failed':
                    errors += 1
            except Exception:
                errors += 1

        # Target: < 5% error rate
        error_rate = errors / 500
        self.assertLess(error_rate, 0.05, f"Error rate {error_rate*100:.1f}%, target < 5%")

    def test_lock_release_reliability(self):
        """Test locks are always released properly"""
        for i in range(100):
            self.executor.execute_candidate(
                candidate_id=i,
                candidate_name=f'Candidate {i}',
                state_before=self.state_before
            )

        # After 100 executions, should be able to acquire lock immediately
        start = time.time()
        acquired = self.executor.acquire_execution_lock()
        elapsed = time.time() - start

        self.assertTrue(acquired, "Should be able to acquire lock after executions")
        self.assertLess(elapsed, 0.1, "Lock acquisition should be immediate")

        self.executor.release_execution_lock()


if __name__ == '__main__':
    unittest.main(verbosity=2)
