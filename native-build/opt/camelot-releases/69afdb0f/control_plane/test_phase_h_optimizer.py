#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 2: Optimizer Engine Tests
Verify candidate generation and ranking
"""

import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from control_plane.phase_h_optimizer import OptimizationCandidate, OptimizerEngine


class TestOptimizerEngine(unittest.TestCase):
    """Test optimizer functionality"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patterns_db = str(Path(self.temp_dir.name) / "test_patterns.db")
        self.optimizations_db = str(Path(self.temp_dir.name) / "test_optimizations.db")

        # Create test patterns database
        self._create_test_patterns_db()

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

    def _create_test_patterns_db(self):
        """Create patterns database with test data"""
        conn = sqlite3.connect(self.patterns_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE patterns (
                id INTEGER PRIMARY KEY,
                pattern_type TEXT,
                name TEXT,
                metrics TEXT,
                confidence REAL,
                last_detected TIMESTAMP,
                occurrence_count INTEGER,
                created_at TIMESTAMP
            )
        ''')

        # Temporal pattern (morning spike)
        temporal_metrics = {
            'time_window': '07:00-09:00',
            'avg_latency_ms': 1.5,
            'baseline_ms': 1.3,
            'elevation_pct': 15.4,
        }
        c.execute('''
            INSERT INTO patterns
            VALUES (1, 'temporal', 'Morning Load Spike', ?, 0.92, datetime('now'), 5, datetime('now'))
        ''', (json.dumps(temporal_metrics),))

        # Load pattern
        load_metrics = {
            'ops_per_minute_threshold': 300,
            'latency_at_load_ms': 2.0,
            'baseline_ms': 1.3,
            'correlation': 'positive',
        }
        c.execute('''
            INSERT INTO patterns
            VALUES (2, 'load', 'Load-Induced Latency', ?, 0.88, datetime('now'), 8, datetime('now'))
        ''', (json.dumps(load_metrics),))

        # Error pattern
        error_metrics = {
            'current_error_rate': 5.0,
            'baseline_error_rate': 0.1,
            'elevation_factor': 50.0,
            'failure_count': 500,
            'total_operations': 10000,
        }
        c.execute('''
            INSERT INTO patterns
            VALUES (3, 'error', 'Error Spike Detected', ?, 0.85, datetime('now'), 3, datetime('now'))
        ''', (json.dumps(error_metrics),))

        # Resource pattern
        resource_metrics = {
            'initial_latency_ms': 1.0,
            'current_latency_ms': 1.25,
            'growth_pct': 25.0,
            'hours_elapsed': 8,
        }
        c.execute('''
            INSERT INTO patterns
            VALUES (4, 'resource', 'Memory Creep Detected', ?, 0.80, datetime('now'), 2, datetime('now'))
        ''', (json.dumps(resource_metrics),))

        conn.commit()
        conn.close()

    def test_optimizer_initialization(self):
        """Test optimizer initializes correctly"""
        self.assertIsNotNone(self.optimizer)
        self.assertEqual(self.optimizer.thresholds['min_safe_confidence'], 0.7)
        self.assertEqual(self.optimizer.thresholds['auto_apply_threshold'], 0.90)

    def test_candidate_generation_from_patterns(self):
        """Test generation of candidates from patterns"""
        candidates = self.optimizer.generate_candidates_from_patterns()

        self.assertGreater(len(candidates), 0, "Should generate candidates from patterns")
        print(f"✅ Generated {len(candidates)} candidates from 4 patterns")

    def test_temporal_candidates(self):
        """Test temporal pattern candidate generation"""
        candidates = self.optimizer._generate_temporal_candidates(
            pattern_id=1,
            pattern_name='Morning Load Spike',
            metrics={'elevation_pct': 15.4, 'time_window': '07:00-09:00'},
            confidence=0.92
        )

        self.assertGreater(len(candidates), 0)

        # Check candidate properties
        for c in candidates:
            self.assertEqual(c.pattern_id, 1)
            self.assertIsNotNone(c.name)
            self.assertGreater(c.expected_impact_pct, 0)
            self.assertGreater(c.confidence, 0)
            self.assertGreater(c.safety_score, 0)

    def test_load_candidates(self):
        """Test load pattern candidate generation"""
        candidates = self.optimizer._generate_load_candidates(
            pattern_id=2,
            pattern_name='Load-Induced Latency',
            metrics={'latency_at_load_ms': 2.0, 'baseline_ms': 1.3},
            confidence=0.88
        )

        self.assertGreater(len(candidates), 0)

        for c in candidates:
            self.assertEqual(c.pattern_id, 2)
            self.assertIn(c.category, ['parameter_tuning', 'resource_allocation'])

    def test_error_candidates(self):
        """Test error pattern candidate generation"""
        candidates = self.optimizer._generate_error_candidates(
            pattern_id=3,
            pattern_name='Error Spike Detected',
            metrics={'current_error_rate': 5.0, 'elevation_factor': 50.0},
            confidence=0.85
        )

        self.assertGreater(len(candidates), 0)

        for c in candidates:
            self.assertEqual(c.pattern_id, 3)

    def test_resource_candidates(self):
        """Test resource pattern candidate generation"""
        candidates = self.optimizer._generate_resource_candidates(
            pattern_id=4,
            pattern_name='Memory Creep',
            metrics={'growth_pct': 25.0},
            confidence=0.80
        )

        self.assertGreater(len(candidates), 0)

        for c in candidates:
            self.assertEqual(c.pattern_id, 4)

    def test_candidate_scoring(self):
        """Test composite score calculation"""
        candidate = OptimizationCandidate(
            pattern_id=1,
            name='Test Candidate',
            expected_impact_pct=15.0,
            confidence=0.90,
            safety_score=0.85,
        )

        scored = self.optimizer.compute_candidate_scores([candidate])
        self.assertEqual(len(scored), 1)

        # Score = Impact×0.5 + Confidence×0.3 + Safety×0.2
        self.assertGreater(scored[0].composite_score, 0)
        self.assertLess(scored[0].composite_score, 1.0)

        expected = (0.5 * 0.5) + (0.9 * 0.3) + (0.85 * 0.2)  # Approx
        self.assertAlmostEqual(scored[0].composite_score, expected, places=2)

    def test_candidate_ranking(self):
        """Test candidate ranking by score"""
        candidates = [
            OptimizationCandidate(expected_impact_pct=20, confidence=0.9, safety_score=0.9),
            OptimizationCandidate(expected_impact_pct=5, confidence=0.7, safety_score=0.7),
            OptimizationCandidate(expected_impact_pct=15, confidence=0.85, safety_score=0.85),
        ]

        ranked = self.optimizer.rank_candidates(candidates)

        # Should be sorted by composite score (descending)
        if len(ranked) > 1:
            self.assertGreaterEqual(
                ranked[0].composite_score,
                ranked[1].composite_score
            )

    def test_candidate_storage(self):
        """Test candidate storage in database"""
        candidate = OptimizationCandidate(
            pattern_id=1,
            category='parameter_tuning',
            name='Test Candidate',
            description='Test description',
            current_value='old',
            suggested_value='new',
            expected_impact_pct=10.0,
            confidence=0.85,
            safety_score=0.90,
            composite_score=0.87,
            rationale='Test rationale',
            implementation_effort='low',
        )

        self.optimizer.store_candidate(candidate)

        # Retrieve and verify
        stored = self.optimizer.get_stored_candidates()
        self.assertGreater(len(stored), 0)

        found = None
        for c in stored:
            if c.name == 'Test Candidate':
                found = c
                break

        self.assertIsNotNone(found)
        self.assertEqual(found.confidence, 0.85)
        self.assertEqual(found.category, 'parameter_tuning')

    def test_candidates_for_approval(self):
        """Test filtering candidates for approval"""
        self.optimizer.generate_candidates_from_patterns()
        approval_candidates = self.optimizer.get_candidates_for_approval()

        self.assertIn('auto_apply', approval_candidates)
        self.assertIn('human_review', approval_candidates)
        self.assertIn('total', approval_candidates)

        # Should have some candidates
        self.assertGreater(approval_candidates['total'], 0)

    def test_candidate_statistics(self):
        """Test candidate statistics generation"""
        self.optimizer.generate_candidates_from_patterns()
        stats = self.optimizer.get_candidate_stats()

        self.assertIn('total_candidates', stats)
        self.assertIn('by_category', stats)
        self.assertIn('by_score', stats)
        self.assertIn('average_composite_score', stats)
        self.assertIn('average_impact', stats)

        if stats['total_candidates'] > 0:
            self.assertGreaterEqual(stats['average_composite_score'], 0)
            self.assertLessEqual(stats['average_composite_score'], 1.0)

    def test_quality_thresholds(self):
        """Test that low-quality candidates are filtered"""
        poor_candidate = OptimizationCandidate(
            expected_impact_pct=1.0,  # Below min_impact (3%)
            confidence=0.5,  # Below min_safe_confidence (0.7)
            safety_score=0.7,  # Below min_safety_score (0.75)
        )

        ranked = self.optimizer.rank_candidates([poor_candidate])

        # Should be filtered out
        self.assertEqual(len(ranked), 0)


class TestOptimizerPerformance(unittest.TestCase):
    """Test optimizer performance"""

    def setUp(self):
        """Create performance test database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patterns_db = str(Path(self.temp_dir.name) / "perf_patterns.db")
        self.optimizations_db = str(Path(self.temp_dir.name) / "perf_optimizations.db")

        # Create large patterns database
        self._create_large_patterns_db()

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

    def _create_large_patterns_db(self):
        """Create patterns database with 20+ patterns"""
        conn = sqlite3.connect(self.patterns_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE patterns (
                id INTEGER PRIMARY KEY,
                pattern_type TEXT,
                name TEXT,
                metrics TEXT,
                confidence REAL,
                last_detected TIMESTAMP,
                occurrence_count INTEGER,
                created_at TIMESTAMP
            )
        ''')

        pattern_types = ['temporal', 'load', 'error', 'resource']
        for i in range(20):
            pattern_type = pattern_types[i % 4]
            metrics = {
                'elevation_pct': 10 + (i % 30),
                'confidence_factor': 0.7 + (i % 25) / 100.0,
            }

            c.execute('''
                INSERT INTO patterns
                VALUES (?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'))
            ''', (i + 1, pattern_type, f'Pattern {i}', json.dumps(metrics), 0.75 + (i % 20) / 100.0, i))

        conn.commit()
        conn.close()

    def test_candidate_generation_performance(self):
        """Test generation performance on large pattern set"""
        start = time.perf_counter()
        candidates = self.optimizer.generate_candidates_from_patterns()
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 1.0, f"Generation took {elapsed:.2f}s")
        print(f"✅ Candidate generation: {len(candidates)} candidates in {elapsed*1000:.1f}ms")

    def test_ranking_performance(self):
        """Test ranking performance"""
        candidates = self.optimizer.generate_candidates_from_patterns()

        start = time.perf_counter()
        ranked = self.optimizer.rank_candidates(candidates)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.2, f"Ranking took {elapsed:.2f}s")
        print(f"✅ Candidate ranking: {len(ranked)} ranked in {elapsed*1000:.1f}ms")


class TestCandidateQuality(unittest.TestCase):
    """Test candidate quality and accuracy"""

    def test_high_impact_candidates(self):
        """Test that high-impact candidates are identified"""
        high_impact = OptimizationCandidate(
            expected_impact_pct=20.0,
            confidence=0.95,
            safety_score=0.95,
        )

        low_impact = OptimizationCandidate(
            expected_impact_pct=2.0,
            confidence=0.95,
            safety_score=0.95,
        )

        optimizer = OptimizerEngine()
        scored_high = optimizer.compute_candidate_scores([high_impact])
        scored_low = optimizer.compute_candidate_scores([low_impact])

        # High impact should score better
        self.assertGreater(
            scored_high[0].composite_score,
            scored_low[0].composite_score
        )

    def test_safe_candidates_prioritized(self):
        """Test that safe candidates are prioritized"""
        safe = OptimizationCandidate(
            expected_impact_pct=10.0,
            confidence=0.9,
            safety_score=0.95,
        )

        risky = OptimizationCandidate(
            expected_impact_pct=10.0,
            confidence=0.9,
            safety_score=0.60,
        )

        optimizer = OptimizerEngine()
        scored_safe = optimizer.compute_candidate_scores([safe])
        scored_risky = optimizer.compute_candidate_scores([risky])

        # Safe should score better
        self.assertGreater(
            scored_safe[0].composite_score,
            scored_risky[0].composite_score
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
