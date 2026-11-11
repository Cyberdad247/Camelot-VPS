#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 1: Feedback Collector Tests
Test signal collection, validation, storage, and deduplication
"""

import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_feedback_collector import FeedbackCollector, FeedbackValidator


class TestFeedbackValidator(unittest.TestCase):
    """Test signal validation"""

    def test_valid_user_satisfaction(self):
        """Test valid user satisfaction signal"""
        is_valid, msg = FeedbackValidator.validate(
            'user_satisfaction', 'user', 0.9, 0.95
        )
        self.assertTrue(is_valid)
        self.assertEqual(msg, 'valid')

    def test_valid_business_metric(self):
        """Test valid business metric signal"""
        is_valid, msg = FeedbackValidator.validate(
            'business_metric', 'monitoring', 0.89, 0.99
        )
        self.assertTrue(is_valid)

    def test_invalid_signal_type(self):
        """Test invalid signal type rejection"""
        is_valid, msg = FeedbackValidator.validate(
            'invalid_type', 'user', 0.5, 0.8
        )
        self.assertFalse(is_valid)
        self.assertIn('Invalid signal type', msg)

    def test_invalid_source(self):
        """Test invalid source rejection"""
        is_valid, msg = FeedbackValidator.validate(
            'user_satisfaction', 'invalid_source', 0.5, 0.8
        )
        self.assertFalse(is_valid)
        self.assertIn('Invalid source', msg)

    def test_satisfaction_value_range(self):
        """Test satisfaction signals must be 0-1"""
        is_valid, msg = FeedbackValidator.validate(
            'user_satisfaction', 'user', 1.5, 0.8
        )
        self.assertFalse(is_valid)
        self.assertIn('0.0-1.0', msg)

    def test_invalid_confidence(self):
        """Test confidence must be 0-1"""
        is_valid, msg = FeedbackValidator.validate(
            'user_satisfaction', 'user', 0.5, 1.5
        )
        self.assertFalse(is_valid)
        self.assertIn('Confidence must be 0.0-1.0', msg)

    def test_all_signal_types(self):
        """Test all valid signal types"""
        for signal_type in FeedbackValidator.SIGNAL_TYPES.keys():
            is_valid, msg = FeedbackValidator.validate(
                signal_type, 'monitoring', 0.5, 0.8
            )
            self.assertTrue(is_valid, f"{signal_type} should be valid")


class TestFeedbackCollector(unittest.TestCase):
    """Test feedback collection and storage"""

    def setUp(self):
        """Create temporary feedback database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.feedback_db = str(Path(self.temp_dir.name) / "test_feedback.db")
        self.collector = FeedbackCollector(feedback_db_path=self.feedback_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_collector_initialization(self):
        """Test collector initializes correctly"""
        self.assertIsNotNone(self.collector)
        self.assertEqual(self.collector.feedback_db, self.feedback_db)

    def test_collect_user_satisfaction(self):
        """Test collecting user satisfaction signal"""
        signal = self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.95,
            description='Good performance'
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal.signal_type, 'user_satisfaction')
        self.assertEqual(signal.value, 0.9)
        self.assertEqual(signal.source, 'user')

    def test_collect_business_metric(self):
        """Test collecting business metric signal"""
        signal = self.collector.collect_signal(
            signal_type='business_metric',
            source='monitoring',
            value=0.89,
            confidence=0.99,
            description='SLA compliance'
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal.signal_type, 'business_metric')
        self.assertEqual(signal.value, 0.89)

    def test_reject_invalid_signal(self):
        """Test invalid signals are rejected"""
        signal = self.collector.collect_signal(
            signal_type='invalid',
            source='user',
            value=0.5,
            confidence=0.8
        )

        self.assertIsNone(signal)

    def test_duplicate_rejection(self):
        """Test duplicate signals are rejected"""
        # Collect first signal
        signal1 = self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.95
        )
        self.assertIsNotNone(signal1)

        # Collect duplicate
        signal2 = self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.95
        )
        self.assertIsNone(signal2, "Duplicate should be rejected")

    def test_different_values_not_duplicates(self):
        """Test signals with different values are not duplicates"""
        # Collect first signal
        signal1 = self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.95
        )
        self.assertIsNotNone(signal1)

        # Collect with different value
        signal2 = self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.8,
            confidence=0.95
        )
        self.assertIsNotNone(signal2, "Different value should not be duplicate")

    def test_metadata_storage(self):
        """Test metadata is stored correctly"""
        metadata = {
            'operation_type': 'write',
            'region': 'us-east-1'
        }

        signal = self.collector.collect_signal(
            signal_type='business_metric',
            source='monitoring',
            value=0.89,
            confidence=0.99,
            metadata=metadata
        )

        self.assertIsNotNone(signal)
        self.assertIsNotNone(signal.metadata)

        # Verify metadata stored
        import json
        stored_metadata = json.loads(signal.metadata)
        self.assertEqual(stored_metadata['operation_type'], 'write')

    def test_get_signals_retrieval(self):
        """Test retrieving signals"""
        # Collect multiple signals
        for i in range(5):
            self.collector.collect_signal(
                signal_type='user_satisfaction',
                source='user',
                value=0.8 + i * 0.05,
                confidence=0.95
            )

        # Wait a moment between signals (dedup window)
        import time
        time.sleep(0.1)

        # Retrieve signals
        signals = self.collector.get_signals(hours_back=1)
        self.assertGreaterEqual(len(signals), 5)

    def test_get_signals_by_type(self):
        """Test filtering signals by type"""
        # Collect mixed signals
        self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.95
        )

        import time
        time.sleep(0.1)

        self.collector.collect_signal(
            signal_type='business_metric',
            source='monitoring',
            value=0.89,
            confidence=0.99
        )

        time.sleep(0.1)

        # Filter by type
        user_signals = self.collector.get_signals(signal_type='user_satisfaction')
        self.assertGreater(len(user_signals), 0)
        for signal in user_signals:
            self.assertEqual(signal.signal_type, 'user_satisfaction')

    def test_get_signals_by_source(self):
        """Test filtering signals by source"""
        self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.95
        )

        import time
        time.sleep(0.1)

        self.collector.collect_signal(
            signal_type='business_metric',
            source='monitoring',
            value=0.89,
            confidence=0.99
        )

        time.sleep(0.1)

        # Filter by source
        monitoring_signals = self.collector.get_signals(source='monitoring')
        for signal in monitoring_signals:
            self.assertEqual(signal.source, 'monitoring')

    def test_signal_stats(self):
        """Test signal statistics"""
        # Collect several signals
        signals_to_collect = [
            ('user_satisfaction', 'user', 0.9),
            ('business_metric', 'monitoring', 0.89),
            ('operational_constraint', 'team', 0.75),
        ]

        import time
        for sig_type, source, value in signals_to_collect:
            self.collector.collect_signal(
                signal_type=sig_type,
                source=source,
                value=value,
                confidence=0.9
            )
            time.sleep(0.1)

        stats = self.collector.get_signal_stats()

        self.assertGreater(stats['total_signals'], 0)
        self.assertIn('by_type', stats)
        self.assertIn('by_source', stats)
        self.assertGreater(stats['average_confidence'], 0)

    def test_cleanup_old_signals(self):
        """Test cleanup of old signals"""
        # Collect a signal
        self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.95
        )

        # Manually insert old signal directly
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        old_time = (datetime.now() - timedelta(days=35)).isoformat()
        c.execute('''
            INSERT INTO signals
            (signal_type, source, value, confidence, recorded_at)
            VALUES (?, ?, ?, ?, ?)
        ''', ('user_satisfaction', 'user', 0.8, 0.9, old_time))

        conn.commit()
        conn.close()

        # Verify old signal exists
        signals_before = self.collector.get_signals(hours_back=1000)
        self.assertGreater(len(signals_before), 1)

        # Cleanup
        deleted = self.collector.cleanup_old_signals(days_old=30)
        self.assertGreater(deleted, 0)

        # Verify old signal removed
        signals_after = self.collector.get_signals(hours_back=1000)
        self.assertLess(len(signals_after), len(signals_before))


class TestSignalIntegration(unittest.TestCase):
    """Integration tests for signal collection workflow"""

    def setUp(self):
        """Create temporary database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.feedback_db = str(Path(self.temp_dir.name) / "test_feedback.db")
        self.collector = FeedbackCollector(feedback_db_path=self.feedback_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_user_reports_issue_workflow(self):
        """Test workflow: user reports issue"""
        # User reports issue
        signal = self.collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.2,
            confidence=0.9,
            description='Latency is terrible'
        )

        self.assertIsNotNone(signal)

        # Retrieve and verify
        signals = self.collector.get_signals(signal_type='user_satisfaction')
        self.assertGreater(len(signals), 0)
        self.assertEqual(signals[0].value, 0.2)

    def test_monitoring_tracks_metrics(self):
        """Test monitoring signal collection"""
        import time

        # Simulate metrics over time
        metrics = [0.85, 0.87, 0.89, 0.91]

        for metric in metrics:
            signal = self.collector.collect_signal(
                signal_type='business_metric',
                source='monitoring',
                value=metric,
                confidence=0.99,
                description=f'SLA compliance {metric*100:.0f}%'
            )
            self.assertIsNotNone(signal)
            time.sleep(0.1)

        # Verify all stored
        signals = self.collector.get_signals(signal_type='business_metric')
        self.assertEqual(len(signals), len(metrics))

    def test_operations_team_reports_constraint(self):
        """Test operational constraint reporting"""
        signal = self.collector.collect_signal(
            signal_type='operational_constraint',
            source='team',
            value=0.0,
            confidence=0.95,
            description='Never reduce cache below 2GB',
            metadata={'constraint_type': 'memory', 'value': '2GB'}
        )

        self.assertIsNotNone(signal)

        # Retrieve and verify
        signals = self.collector.get_signals(signal_type='operational_constraint')
        self.assertGreater(len(signals), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
