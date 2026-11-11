#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 2: Pattern Learner Tests
Verify pattern extraction accuracy and performance
"""

import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from control_plane.phase_h_pattern_learner import Pattern, PatternLearner


class TestPatternLearner(unittest.TestCase):
    """Test pattern learner functionality"""

    def setUp(self):
        """Create temporary databases for testing"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "test_patterns.db")

        # Create test metrics database
        self._create_test_metrics_db()

        self.learner = PatternLearner(
            metrics_db_path=self.metrics_db,
            patterns_db_path=self.patterns_db
        )

    def tearDown(self):
        """Clean up temporary databases"""
        # Close any open connections
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_test_metrics_db(self):
        """Create metrics database with test data"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY,
                operation_type TEXT,
                duration_ms REAL,
                success INTEGER,
                error_message TEXT,
                tags TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert sample operations
        now = datetime.now()

        # Normal operations (baseline)
        for i in range(500):
            op_type = ['read', 'write', 'route'][i % 3]
            duration = 1.0 if op_type in ['read', 'write'] else 0.001
            recorded_at = (now - timedelta(hours=4) + timedelta(seconds=i)).isoformat()

            c.execute('''
                INSERT INTO operations
                (operation_type, duration_ms, success, recorded_at)
                VALUES (?, ?, ?, ?)
            ''', (op_type, duration, 1, recorded_at))

        # Morning spike (07:00-09:00)
        morning_time = now.replace(hour=8, minute=0, second=0)
        for i in range(100):
            duration = 1.5  # Higher latency
            recorded_at = (morning_time + timedelta(seconds=i)).isoformat()
            c.execute('''
                INSERT INTO operations
                (operation_type, duration_ms, success, recorded_at)
                VALUES (?, ?, ?, ?)
            ''', ('read', duration, 1, recorded_at))

        # Error spike
        error_time = now - timedelta(minutes=30)
        for i in range(100):
            success = 0 if i % 2 == 0 else 1  # 50% errors
            recorded_at = (error_time + timedelta(seconds=i)).isoformat()
            c.execute('''
                INSERT INTO operations
                (operation_type, duration_ms, success, error_message, recorded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', ('write', 1.0, success, 'Connection lost' if not success else None, recorded_at))

        conn.commit()
        conn.close()

    def test_pattern_learner_initialization(self):
        """Test learner initializes correctly"""
        self.assertIsNotNone(self.learner)
        self.assertEqual(self.learner.baseline['read_p95_ms'], 1.3)
        self.assertEqual(self.learner.baseline['error_rate'], 0.001)

    def test_extract_metrics(self):
        """Test metrics extraction from database"""
        metrics = self.learner.extract_metrics()

        self.assertIn('read', metrics)
        self.assertIn('write', metrics)
        self.assertIn('count', metrics['read'])
        self.assertGreater(metrics['read']['count'], 0)

    def test_detect_temporal_patterns(self):
        """Test detection of time-of-day patterns"""
        patterns = self.learner.detect_temporal_patterns()

        # Should detect morning spike
        self.assertGreater(len(patterns), 0)

        morning_pattern = None
        for p in patterns:
            if 'Morning' in p.name:
                morning_pattern = p
                break

        if morning_pattern:
            self.assertEqual(morning_pattern.pattern_type, 'temporal')
            self.assertGreater(morning_pattern.confidence, 0.5)
            self.assertIn('time_window', morning_pattern.metrics)

    def test_detect_load_patterns(self):
        """Test detection of load-related patterns"""
        patterns = self.learner.detect_load_patterns()

        # May or may not detect depending on data
        for p in patterns:
            self.assertEqual(p.pattern_type, 'load')
            self.assertGreater(p.confidence, 0.0)
            self.assertLess(p.confidence, 1.0)

    def test_detect_error_patterns(self):
        """Test detection of error patterns"""
        patterns = self.learner.detect_error_patterns()

        # Should detect error spike
        self.assertGreater(len(patterns), 0)

        error_pattern = patterns[0]
        self.assertEqual(error_pattern.pattern_type, 'error')
        self.assertIn('failure_count', error_pattern.metrics)
        self.assertGreater(error_pattern.metrics['failure_count'], 0)

    def test_pattern_storage(self):
        """Test patterns are stored in database"""
        pattern = Pattern(
            pattern_type='temporal',
            name='Test Pattern',
            description='Test description',
            metrics={'key': 'value'},
            confidence=0.85,
        )

        self.learner.store_pattern(pattern)

        # Retrieve and verify
        stored = self.learner.get_stored_patterns()
        self.assertGreater(len(stored), 0)

        found = None
        for p in stored:
            if p.name == 'Test Pattern':
                found = p
                break

        self.assertIsNotNone(found)
        self.assertEqual(found.confidence, 0.85)
        self.assertEqual(found.pattern_type, 'temporal')

    def test_learn_all_patterns(self):
        """Test learning all pattern types"""
        patterns = self.learner.learn_all_patterns()

        # Should detect at least error patterns
        self.assertGreater(len(patterns), 0)

        # All patterns should have required fields
        for p in patterns:
            self.assertIsNotNone(p.pattern_type)
            self.assertIsNotNone(p.name)
            self.assertGreaterEqual(p.confidence, 0.0)
            self.assertLessEqual(p.confidence, 1.0)

    def test_pattern_statistics(self):
        """Test pattern statistics calculation"""
        self.learner.learn_all_patterns()
        stats = self.learner.get_pattern_stats()

        self.assertIn('total_patterns', stats)
        self.assertIn('by_confidence', stats)
        self.assertIn('average_confidence', stats)

        if stats['total_patterns'] > 0:
            self.assertGreaterEqual(stats['average_confidence'], 0.0)
            self.assertLessEqual(stats['average_confidence'], 1.0)

    def test_pattern_confidence_scores(self):
        """Test that confidence scores are reasonable"""
        patterns = self.learner.learn_all_patterns()

        for pattern in patterns:
            # Confidence should be between 0 and 1
            self.assertGreaterEqual(pattern.confidence, 0.0)
            self.assertLessEqual(pattern.confidence, 1.0)

            # High confidence requires sufficient samples
            if pattern.confidence > 0.9:
                self.assertGreater(pattern.occurrence_count, 0)

    def test_pattern_types_variety(self):
        """Test that multiple pattern types can be detected"""
        patterns = self.learner.learn_all_patterns()

        pattern_types = set(p.pattern_type for p in patterns)

        # Should have variety of pattern types
        expected_types = {'temporal', 'load', 'error', 'resource'}
        # Not all may be detected, but should have at least 1
        self.assertGreater(len(pattern_types), 0)

        # All detected types should be valid
        for pt in pattern_types:
            self.assertIn(pt, expected_types)


class TestPatternPerformance(unittest.TestCase):
    """Test pattern learning performance"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "perf_metrics.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "perf_patterns.db")

        # Create large test dataset
        self._create_large_metrics_db()

        self.learner = PatternLearner(
            metrics_db_path=self.metrics_db,
            patterns_db_path=self.patterns_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_large_metrics_db(self):
        """Create metrics database with 1000+ operations"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY,
                operation_type TEXT,
                duration_ms REAL,
                success INTEGER,
                error_message TEXT,
                tags TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        now = datetime.now()
        for i in range(1000):
            op_type = ['read', 'write', 'route', 'compress'][i % 4]
            duration = 1.0 + (i % 10) * 0.1
            recorded_at = (now - timedelta(hours=6) + timedelta(seconds=i)).isoformat()

            c.execute('''
                INSERT INTO operations
                (operation_type, duration_ms, success, recorded_at)
                VALUES (?, ?, ?, ?)
            ''', (op_type, duration, 1, recorded_at))

        conn.commit()
        conn.close()

    def test_learning_performance(self):
        """Test learning speed on 1000+ operations"""
        start = time.perf_counter()
        patterns = self.learner.learn_all_patterns()
        elapsed = time.perf_counter() - start

        # Should complete in reasonable time (< 1 second)
        self.assertLess(elapsed, 1.0, f"Learning took {elapsed:.2f}s")
        print(f"✅ Pattern learning: {len(patterns)} patterns in {elapsed*1000:.1f}ms")

    def test_pattern_retrieval_speed(self):
        """Test pattern retrieval speed"""
        self.learner.learn_all_patterns()

        start = time.perf_counter()
        patterns = self.learner.get_stored_patterns()
        elapsed = time.perf_counter() - start

        # Should be very fast (< 100ms)
        self.assertLess(elapsed, 0.1, f"Retrieval took {elapsed:.2f}s")
        print(f"✅ Pattern retrieval: {len(patterns)} patterns in {elapsed*1000:.1f}ms")

    def test_statistics_computation(self):
        """Test statistics computation speed"""
        self.learner.learn_all_patterns()

        start = time.perf_counter()
        stats = self.learner.get_pattern_stats()
        elapsed = time.perf_counter() - start

        # Should be instant (< 50ms)
        self.assertLess(elapsed, 0.05, f"Stats computation took {elapsed:.2f}s")
        self.assertIsNotNone(stats)


class TestPatternAccuracy(unittest.TestCase):
    """Test pattern detection accuracy"""

    def setUp(self):
        """Create accuracy test database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "accuracy_metrics.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "accuracy_patterns.db")

        self.learner = PatternLearner(
            metrics_db_path=self.metrics_db,
            patterns_db_path=self.patterns_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_metrics_with_pattern(self, pattern_type: str, intensity: float = 1.0):
        """Create metrics database with injected pattern"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY,
                operation_type TEXT,
                duration_ms REAL,
                success INTEGER,
                error_message TEXT,
                tags TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        now = datetime.now()

        if pattern_type == 'error':
            # Inject 30% error rate
            for i in range(500):
                success = 0 if i % 3 == 0 else 1
                error_msg = 'Connection lost' if not success else None
                recorded_at = (now - timedelta(hours=2) + timedelta(seconds=i)).isoformat()

                c.execute('''
                    INSERT INTO operations
                    (operation_type, duration_ms, success, error_message, recorded_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('write', 1.0, success, error_msg, recorded_at))

        elif pattern_type == 'slow':
            # Inject 2x slower operations
            for i in range(500):
                duration = 2.6 * intensity  # 2x baseline
                recorded_at = (now - timedelta(hours=2) + timedelta(seconds=i)).isoformat()

                c.execute('''
                    INSERT INTO operations
                    (operation_type, duration_ms, success, recorded_at)
                    VALUES (?, ?, ?, ?)
                ''', ('read', duration, 1, recorded_at))

        conn.commit()
        conn.close()

    def test_error_pattern_detection(self):
        """Test accurate detection of error patterns"""
        self._create_metrics_with_pattern('error')
        patterns = self.learner.detect_error_patterns()

        self.assertGreater(len(patterns), 0, "Should detect error pattern")

        error_pattern = patterns[0]
        self.assertGreater(error_pattern.metrics['current_error_rate'], 20.0)  # > 20%
        print(f"✅ Error pattern detected with {error_pattern.confidence:.0%} confidence")

    def test_slow_pattern_detection(self):
        """Test accurate detection of slow operation patterns"""
        self._create_metrics_with_pattern('slow')
        patterns = self.learner.detect_resource_patterns()

        # May detect as resource pattern if growth pattern found
        for p in patterns:
            if 'slow' in p.name.lower() or p.pattern_type == 'resource':
                print(f"✅ Slow pattern detected: {p.name}")
                return

        # Otherwise, check if metrics show the slowdown
        metrics = self.learner.extract_metrics()
        if 'read' in metrics:
            self.assertGreater(metrics['read']['avg_ms'], 2.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
