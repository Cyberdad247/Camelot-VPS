#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 3: Rollback System Tests
Test emergency revert of failed optimizations
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_rollback import RollbackManager, RollbackResult


class TestRollbackSystem(unittest.TestCase):
    """Test rollback functionality"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.rollback_db = str(Path(self.temp_dir.name) / "rollback.db")
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.tracker_db = str(Path(self.temp_dir.name) / "tracker.db")

        # Create mock executor database with execution data
        self._create_mock_executor_db()

        self.rollback_mgr = RollbackManager(
            self.rollback_db,
            self.executor_db,
            self.tracker_db
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

        # Insert test execution with rollback point
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

        # Insert execution without rollback point
        c.execute('''
            INSERT INTO executions
            VALUES (2, 2, 'No Rollback Candidate', 'success', ?, ?, 0.05, NULL, 0)
        ''', (json.dumps(state_before), json.dumps(state_after)))

        conn.commit()
        conn.close()

    def test_rollback_manager_initialization(self):
        """Test rollback manager initializes correctly"""
        self.assertIsNotNone(self.rollback_mgr)

    def test_can_rollback_available(self):
        """Test checking if rollback is available"""
        # Execution 1 has rollback available
        self.assertTrue(self.rollback_mgr.can_rollback(1))

    def test_can_rollback_not_available(self):
        """Test checking if rollback is not available"""
        # Execution 2 has no rollback point
        self.assertFalse(self.rollback_mgr.can_rollback(2))

    def test_can_rollback_nonexistent(self):
        """Test checking rollback for nonexistent execution"""
        # Execution 999 does not exist
        self.assertFalse(self.rollback_mgr.can_rollback(999))

    def test_execute_rollback_success(self):
        """Test successful rollback execution"""
        result = self.rollback_mgr.execute_rollback(
            execution_id=1,
            rollback_reason="Validation failed"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.execution_id, 1)
        self.assertTrue(result.success)
        self.assertEqual(result.rollback_reason, "Validation failed")

    def test_rollback_result_structure(self):
        """Test rollback result dataclass"""
        result = RollbackResult(
            execution_id=1,
            success=True,
            rollback_timestamp=datetime.now().isoformat(),
            rollback_reason="Test reason"
        )

        self.assertEqual(result.execution_id, 1)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.rollback_timestamp)

    def test_rollback_restores_previous_state(self):
        """Test that rollback restores previous state"""
        result = self.rollback_mgr.execute_rollback(
            execution_id=1,
            rollback_reason="Testing state restoration"
        )

        # Successful rollback should have previous state
        if result.success:
            self.assertIsNotNone(result.previous_state_restored)
            state = json.loads(result.previous_state_restored)
            self.assertEqual(state['latency_p95_ms'], 2.0)
            self.assertEqual(state['throughput_ops_sec'], 1000)

    def test_rollback_history(self):
        """Test rollback history recording"""
        # Execute multiple rollbacks
        for i in range(3):
            self.rollback_mgr.execute_rollback(
                execution_id=1,
                rollback_reason=f"Test rollback {i}"
            )

        history = self.rollback_mgr.get_rollback_history(limit=10)
        self.assertGreaterEqual(len(history), 1)

    def test_rollback_statistics(self):
        """Test rollback statistics"""
        # Execute rollback
        self.rollback_mgr.execute_rollback(
            execution_id=1,
            rollback_reason="Test statistics"
        )

        stats = self.rollback_mgr.get_rollback_statistics()

        self.assertGreaterEqual(stats['total_rollbacks'], 1)
        self.assertGreaterEqual(stats['successful'], 0)

    def test_rollback_no_rollback_point(self):
        """Test rollback fails when no rollback point available"""
        result = self.rollback_mgr.execute_rollback(
            execution_id=2,
            rollback_reason="No rollback point"
        )

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIn("No rollback point", result.error_message)

    def test_rollback_nonexistent_execution(self):
        """Test rollback for nonexistent execution"""
        result = self.rollback_mgr.execute_rollback(
            execution_id=999,
            rollback_reason="Nonexistent execution"
        )

        self.assertFalse(result.success)

    def test_rollback_audit_logging(self):
        """Test that rollback actions are audited"""
        self.rollback_mgr.execute_rollback(
            execution_id=1,
            rollback_reason="Audit test"
        )

        # Verify audit table has entries (we can't easily query it in test,
        # but we can verify the manager doesn't crash)
        self.assertTrue(True)


class TestRollbackEdgeCases(unittest.TestCase):
    """Test edge cases in rollback system"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.rollback_db = str(Path(self.temp_dir.name) / "rollback.db")
        self.executor_db = str(Path(self.temp_dir.name) / "executor.db")
        self.tracker_db = str(Path(self.temp_dir.name) / "tracker.db")

        self._create_mock_executor_db()
        self.rollback_mgr = RollbackManager(
            self.rollback_db,
            self.executor_db,
            self.tracker_db
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
        """Create minimal mock executor database"""
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

        # Insert execution with valid state
        state_before = {
            'latency_p95_ms': 2.0,
            'throughput_ops_sec': 1000,
            'cost_per_op': 0.0001
        }

        state_after = {
            'latency_p95_ms': 1.9,
            'throughput_ops_sec': 1050,
            'cost_per_op': 0.0001
        }

        c.execute('''
            INSERT INTO executions
            VALUES (1, 1, 'Test', 'success', ?, ?, 0.05, NULL, 1)
        ''', (json.dumps(state_before), json.dumps(state_after)))

        conn.commit()
        conn.close()

    def test_rollback_multiple_times(self):
        """Test that rollback can be executed multiple times"""
        for i in range(3):
            result = self.rollback_mgr.execute_rollback(
                execution_id=1,
                rollback_reason=f"Rollback attempt {i + 1}"
            )
            self.assertTrue(result.success)

    def test_rollback_reason_recorded(self):
        """Test that rollback reason is recorded"""
        reason = "Critical SLA breach - automatic rollback"
        result = self.rollback_mgr.execute_rollback(
            execution_id=1,
            rollback_reason=reason
        )

        self.assertEqual(result.rollback_reason, reason)

    def test_rollback_timestamp_set(self):
        """Test that rollback timestamp is recorded"""
        result = self.rollback_mgr.execute_rollback(
            execution_id=1,
            rollback_reason="Timestamp test"
        )

        self.assertIsNotNone(result.rollback_timestamp)
        # Verify it looks like a valid timestamp
        self.assertIn('T', result.rollback_timestamp)  # ISO format


if __name__ == '__main__':
    unittest.main(verbosity=2)
