#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 2 Day 4: Full Pipeline Integration Tests
Validate Pattern Learner → Optimizer Engine → Learning Dashboard
"""

import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from control_plane.phase_h_optimizer import OptimizerEngine
from control_plane.phase_h_pattern_learner import PatternLearner

sys.path.insert(0, str(Path(__file__).parent.parent / 'dashboards'))
from phase_h_learning_dashboard import LearningDashboard


class TestFullPipeline(unittest.TestCase):
    """Test complete learning pipeline integration"""

    def setUp(self):
        """Create temporary databases for full pipeline"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "metrics.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "patterns.db")
        self.optimizations_db = str(Path(self.temp_dir.name) / "optimizations.db")

        # Create metrics database with realistic data
        self._create_realistic_metrics_db()

        # Initialize components
        self.learner = PatternLearner(
            metrics_db_path=self.metrics_db,
            patterns_db_path=self.patterns_db
        )
        self.optimizer = OptimizerEngine(
            patterns_db_path=self.patterns_db,
            optimizations_db_path=self.optimizations_db
        )
        self.dashboard = LearningDashboard(
            patterns_db=self.patterns_db,
            optimizations_db=self.optimizations_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_realistic_metrics_db(self):
        """Create metrics database with realistic operational data"""
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
                recorded_at TIMESTAMP
            )
        ''')

        now = datetime.now()

        # Simulate 2000 realistic operations over 6 hours
        op_types = ['read', 'write', 'route', 'compress']

        for i in range(2000):
            op_type = op_types[i % 4]

            # Realistic latencies
            if op_type == 'read':
                duration = 0.8 + (i % 10) * 0.1
            elif op_type == 'write':
                duration = 1.5 + (i % 10) * 0.2
            elif op_type == 'route':
                duration = 0.05 + (i % 5) * 0.01
            else:  # compress
                duration = 1.2 + (i % 10) * 0.15

            # Add some anomalies
            if i % 150 == 0:
                duration *= 2.5  # Occasional slow operation
            if i % 200 == 0 and op_type == 'write':
                success = 0  # Occasional error
            else:
                success = 1

            error_msg = "Connection timeout" if not success else None
            recorded_at = (now - timedelta(hours=6) + timedelta(seconds=i * 10)).isoformat()

            c.execute('''
                INSERT INTO operations
                (operation_type, duration_ms, success, error_message, recorded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (op_type, duration, success, error_msg, recorded_at))

        conn.commit()
        conn.close()

    def test_end_to_end_pipeline(self):
        """Test complete pipeline: metrics → patterns → candidates → dashboard"""
        # Step 1: Extract patterns
        patterns = self.learner.learn_all_patterns()
        self.assertGreater(len(patterns), 0, "Should extract patterns from metrics")

        # Step 2: Generate candidates
        candidates = self.optimizer.generate_candidates_from_patterns()
        self.assertGreater(len(candidates), 0, "Should generate candidates from patterns")

        # Step 3: Dashboard reads both
        pattern_metrics = self.dashboard.get_pattern_metrics()
        candidate_metrics = self.dashboard.get_candidate_metrics()

        self.assertEqual(pattern_metrics['total'], len(patterns))
        self.assertGreater(candidate_metrics['total'], 0)

        print(f"✅ Pipeline: {len(patterns)} patterns → {len(candidates)} candidates → dashboard")

    def test_pattern_learner_to_optimizer(self):
        """Test Pattern Learner output feeds into Optimizer"""
        # Learn patterns
        patterns = self.learner.learn_all_patterns()

        # Optimizer reads patterns from database
        candidates = self.optimizer.generate_candidates_from_patterns()

        # Should have relationship: patterns generate candidates
        if len(patterns) > 0:
            self.assertGreater(len(candidates), 0)

    def test_optimizer_to_dashboard(self):
        """Test Optimizer output displays correctly in Dashboard"""
        # Generate candidates
        self.optimizer.generate_candidates_from_patterns()

        # Dashboard reads and displays
        metrics = self.dashboard.get_candidate_metrics()

        self.assertGreater(metrics['total'], 0)
        self.assertIn('by_category', metrics)
        self.assertIn('top_candidates', metrics)

    def test_dashboard_comprehensive_metrics(self):
        """Test dashboard computes all required metrics"""
        # Run full pipeline
        self.learner.learn_all_patterns()
        self.optimizer.generate_candidates_from_patterns()

        # Get all dashboard metrics
        patterns = self.dashboard.get_pattern_metrics()
        candidates = self.dashboard.get_candidate_metrics()
        health = self.dashboard.get_learning_health_status()
        projections = self.dashboard.get_improvement_projections()

        # Verify structure
        self.assertIn('total', patterns)
        self.assertIn('total', candidates)
        self.assertIn('status', health)
        self.assertIn('total_potential_improvement', projections)

    def test_learning_health_reflects_progress(self):
        """Test learning health status reflects pipeline progress"""
        # Before running pipeline
        health_before = self.dashboard.get_learning_health_status()
        self.assertEqual(health_before['status'], 'initializing')

        # Run full pipeline
        self.learner.learn_all_patterns()
        self.optimizer.generate_candidates_from_patterns()

        # After running pipeline
        health_after = self.dashboard.get_learning_health_status()
        self.assertNotEqual(health_after['status'], 'initializing')

    def test_pipeline_performance(self):
        """Test entire pipeline completes in reasonable time"""
        start = time.perf_counter()

        # Full pipeline
        self.learner.learn_all_patterns()
        self.optimizer.generate_candidates_from_patterns()
        self.dashboard.get_pattern_metrics()
        self.dashboard.get_candidate_metrics()
        self.dashboard.get_learning_health_status()

        elapsed = time.perf_counter() - start

        # Should complete in < 2 seconds
        self.assertLess(elapsed, 2.0, f"Pipeline took {elapsed:.2f}s")
        print(f"✅ Pipeline performance: {elapsed*1000:.0f}ms")

    def test_json_export_completeness(self):
        """Test JSON export includes all pipeline data"""
        # Run pipeline
        self.learner.learn_all_patterns()
        self.optimizer.generate_candidates_from_patterns()

        # Export
        data = self.dashboard.get_json_export()

        # Verify all components present
        self.assertIn('patterns', data)
        self.assertIn('candidates', data)
        self.assertIn('health', data)
        self.assertIn('projections', data)

        # Verify data not empty
        self.assertGreater(data['patterns']['total'], 0)
        self.assertGreater(data['candidates']['total'], 0)


class TestPipelineDataFlow(unittest.TestCase):
    """Test data flows correctly through pipeline"""

    def setUp(self):
        """Create integrated test environment"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "flow_metrics.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "flow_patterns.db")
        self.optimizations_db = str(Path(self.temp_dir.name) / "flow_optimizations.db")

        self._create_test_metrics_db()

        self.learner = PatternLearner(
            metrics_db_path=self.metrics_db,
            patterns_db_path=self.patterns_db
        )
        self.optimizer = OptimizerEngine(
            patterns_db_path=self.patterns_db,
            optimizations_db_path=self.optimizations_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_test_metrics_db(self):
        """Create test metrics with known patterns"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY,
                operation_type TEXT,
                duration_ms REAL,
                success INTEGER,
                error_message TEXT,
                recorded_at TIMESTAMP
            )
        ''')

        # Insert 500 test operations
        now = datetime.now()
        for i in range(500):
            op_type = ['read', 'write'][i % 2]
            duration = 1.0 + (i % 20) * 0.1
            success = 1 if i % 50 != 0 else 0

            recorded_at = (now - timedelta(hours=4) + timedelta(seconds=i)).isoformat()

            c.execute('''
                INSERT INTO operations
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (i+1, op_type, duration, success, None if success else "Error", recorded_at))

        conn.commit()
        conn.close()

    def test_pattern_pattern_id_flow(self):
        """Test pattern IDs flow correctly to candidates"""
        # Learn patterns
        self.learner.learn_all_patterns()

        # Generate candidates
        candidates = self.optimizer.generate_candidates_from_patterns()

        # Verify candidates have pattern references
        for candidate in candidates:
            self.assertIsNotNone(candidate.pattern_id)

    def test_metrics_preserved_through_pipeline(self):
        """Test metrics are preserved through each stage"""
        # Get baseline metrics
        _baseline = self.learner.extract_metrics()

        # Learn patterns
        patterns = self.learner.learn_all_patterns()

        # Metrics should be preserved in pattern database
        if patterns:
            stored_patterns = self.learner.get_stored_patterns()
            self.assertEqual(len(stored_patterns), len(patterns))

    def test_candidate_ranking_consistency(self):
        """Test candidate ranking is consistent"""
        # Generate candidates twice
        candidates1 = self.optimizer.generate_candidates_from_patterns()
        candidates_sorted1 = self.optimizer.rank_candidates(candidates1)

        # Retrieve from database
        candidates_db = self.optimizer.get_stored_candidates()

        # Top candidates should be consistent
        if candidates_sorted1 and candidates_db:
            self.assertEqual(
                candidates_sorted1[0].name,
                candidates_db[0].name
            )


class TestPipelineWithLoad(unittest.TestCase):
    """Test pipeline with realistic load"""

    def setUp(self):
        """Create load test environment"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "load_metrics.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "load_patterns.db")
        self.optimizations_db = str(Path(self.temp_dir.name) / "load_optimizations.db")

        self._create_large_metrics_db()

        self.learner = PatternLearner(
            metrics_db_path=self.metrics_db,
            patterns_db_path=self.patterns_db
        )
        self.optimizer = OptimizerEngine(
            patterns_db_path=self.patterns_db,
            optimizations_db_path=self.optimizations_db
        )
        self.dashboard = LearningDashboard(
            patterns_db=self.patterns_db,
            optimizations_db=self.optimizations_db
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
        """Create large metrics database (5000+ operations)"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY,
                operation_type TEXT,
                duration_ms REAL,
                success INTEGER,
                recorded_at TIMESTAMP
            )
        ''')

        now = datetime.now()
        for i in range(5000):
            op_type = ['read', 'write', 'route', 'compress'][i % 4]
            duration = 1.0 + (i % 100) * 0.01
            success = 1 if i % 100 != 0 else 0

            recorded_at = (now - timedelta(hours=12) + timedelta(seconds=i * 5)).isoformat()

            c.execute('''
                INSERT INTO operations
                VALUES (?, ?, ?, ?, ?)
            ''', (i+1, op_type, duration, success, recorded_at))

        conn.commit()
        conn.close()

    def test_pipeline_with_5000_operations(self):
        """Test pipeline processes 5000+ operations correctly"""
        # Verify data loaded
        metrics = self.learner.extract_metrics()
        self.assertGreater(len(metrics), 0)

        # Run pipeline
        start = time.perf_counter()
        patterns = self.learner.learn_all_patterns()
        candidates = self.optimizer.generate_candidates_from_patterns()
        dashboard_health = self.dashboard.get_learning_health_status()
        elapsed = time.perf_counter() - start

        # Verify results
        self.assertGreater(len(patterns), 0)
        self.assertGreater(len(candidates), 0)
        self.assertIsNotNone(dashboard_health)

        # Should complete in reasonable time
        self.assertLess(elapsed, 3.0, f"Large pipeline took {elapsed:.2f}s")
        print(f"✅ Large pipeline (5000 ops): {len(patterns)} patterns, {len(candidates)} candidates in {elapsed*1000:.0f}ms")

    def test_dashboard_scales_with_data(self):
        """Test dashboard handles large datasets"""
        # Generate patterns and candidates
        self.learner.learn_all_patterns()
        self.optimizer.generate_candidates_from_patterns()

        # Dashboard should handle large datasets
        start = time.perf_counter()
        metrics = self.dashboard.get_pattern_metrics()
        candidates = self.dashboard.get_candidate_metrics()
        self.dashboard.get_learning_health_status()
        elapsed = time.perf_counter() - start

        # Should be fast
        self.assertLess(elapsed, 0.5, f"Dashboard took {elapsed:.2f}s")

        # Should have data
        self.assertGreater(metrics['total'], 0)
        self.assertGreater(candidates['total'], 0)


class TestPipelineErrorHandling(unittest.TestCase):
    """Test pipeline error handling and resilience"""

    def setUp(self):
        """Create error test environment"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patterns_db = str(Path(self.temp_dir.name) / "error_patterns.db")
        self.optimizations_db = str(Path(self.temp_dir.name) / "error_optimizations.db")

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_missing_metrics_db(self):
        """Test pipeline handles missing metrics database"""
        learner = PatternLearner(
            metrics_db_path=str(Path(self.temp_dir.name) / "nonexistent.db"),
            patterns_db_path=self.patterns_db
        )

        # Should not crash
        patterns = learner.learn_all_patterns()
        self.assertEqual(len(patterns), 0)

    def test_missing_patterns_db(self):
        """Test optimizer handles missing patterns database"""
        optimizer = OptimizerEngine(
            patterns_db_path=str(Path(self.temp_dir.name) / "nonexistent.db"),
            optimizations_db_path=self.optimizations_db
        )

        # Should not crash
        candidates = optimizer.generate_candidates_from_patterns()
        self.assertEqual(len(candidates), 0)

    def test_missing_all_databases(self):
        """Test dashboard handles missing databases"""
        dashboard = LearningDashboard(
            patterns_db=str(Path(self.temp_dir.name) / "nonexistent_p.db"),
            optimizations_db=str(Path(self.temp_dir.name) / "nonexistent_o.db")
        )

        # Should not crash
        metrics = dashboard.get_pattern_metrics()
        health = dashboard.get_learning_health_status()

        self.assertEqual(metrics['total'], 0)
        self.assertEqual(health['status'], 'initializing')


if __name__ == '__main__':
    from datetime import timedelta
    unittest.main(verbosity=2)
