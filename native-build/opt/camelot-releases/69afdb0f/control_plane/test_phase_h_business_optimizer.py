#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 3: Business Optimizer Tests
Test business-weighted ranking and approval thresholds
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_business_optimizer import BusinessOptimizer
from phase_h_optimizer import OptimizationCandidate


class TestBusinessRanking(unittest.TestCase):
    """Test business-weighted candidate ranking"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.optimizations_db = str(Path(self.temp_dir.name) / "optimizations.db")
        self.business_metrics_db = str(Path(self.temp_dir.name) / "business_metrics.db")
        self.business_ranking_db = str(Path(self.temp_dir.name) / "business_ranking.db")

        self.optimizer = BusinessOptimizer(
            optimizations_db=self.optimizations_db,
            business_metrics_db=self.business_metrics_db,
            business_ranking_db=self.business_ranking_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_ranking_initialization(self):
        """Test optimizer initializes correctly"""
        self.assertIsNotNone(self.optimizer)
        self.assertIsNotNone(self.optimizer.business_metrics)

    def test_rank_single_candidate(self):
        """Test ranking single candidate"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='Increase Pool',
                expected_impact_pct=8.0, confidence=0.92, safety_score=0.95,
                composite_score=0.82
            )
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].name, 'Increase Pool')
        self.assertGreater(ranked[0].business_score, 0)
        self.assertIsNotNone(ranked[0].approval_status)

    def test_rank_multiple_candidates(self):
        """Test ranking multiple candidates"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='Low Impact', expected_impact_pct=2.0,
                confidence=0.50, safety_score=0.70, composite_score=0.40
            ),
            OptimizationCandidate(
                id=2, pattern_id=2, category='resource_allocation',
                name='High Impact', expected_impact_pct=15.0,
                confidence=0.95, safety_score=0.90, composite_score=0.90
            ),
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)

        self.assertEqual(len(ranked), 2)
        # Higher score should come first
        self.assertGreater(ranked[0].business_score, ranked[1].business_score)

    def test_cost_reduction_improves_ranking(self):
        """Test that cost reduction improves business score"""
        candidate = OptimizationCandidate(
            id=1, pattern_id=1, category='parameter_tuning',
            name='Cost Optimization',
            expected_impact_pct=5.0,
            confidence=0.85, safety_score=0.85, composite_score=0.75
        )

        # Without cost reduction
        ranked1 = self.optimizer.rank_candidates_with_business_impact([candidate])
        score1 = ranked1[0].business_score

        # With cost reduction
        impact_details = {1: {'latency_impact': 5, 'cost_reduction': 15}}
        ranked2 = self.optimizer.rank_candidates_with_business_impact([candidate], impact_details)
        score2 = ranked2[0].business_score

        # Cost reduction should improve score (cost valued 1.5x latency)
        self.assertGreater(score2, score1)

    def test_approval_status_auto_apply(self):
        """Test auto-apply approval for high-confidence candidates"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='High Confidence',
                expected_impact_pct=20.0,
                confidence=0.95, safety_score=0.95, composite_score=0.95
            )
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)

        self.assertEqual(ranked[0].approval_status, 'auto_apply')
        self.assertIn('High business impact', ranked[0].rationale)

    def test_approval_status_manual_review(self):
        """Test manual review approval for medium-confidence candidates"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='Medium Confidence',
                expected_impact_pct=10.0,
                confidence=0.75, safety_score=0.80, composite_score=0.70
            )
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)

        self.assertEqual(ranked[0].approval_status, 'manual_review')
        self.assertIn('review recommended', ranked[0].rationale)

    def test_approval_status_reject(self):
        """Test rejection for low-confidence candidates"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='Low Confidence',
                expected_impact_pct=3.0,
                confidence=0.40, safety_score=0.50, composite_score=0.30
            )
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)

        self.assertEqual(ranked[0].approval_status, 'reject')

    def test_get_candidates_by_status(self):
        """Test filtering candidates by approval status"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='High Conf', expected_impact_pct=20.0,
                confidence=0.95, safety_score=0.95, composite_score=0.95
            ),
            OptimizationCandidate(
                id=2, pattern_id=2, category='resource_allocation',
                name='Low Conf', expected_impact_pct=2.0,
                confidence=0.40, safety_score=0.50, composite_score=0.30
            ),
        ]

        self.optimizer.rank_candidates_with_business_impact(candidates)

        auto_apply = self.optimizer.get_candidates_by_status('auto_apply')
        self.assertGreater(len(auto_apply), 0)

        reject = self.optimizer.get_candidates_by_status('reject')
        self.assertGreater(len(reject), 0)

    def test_ranking_summary(self):
        """Test ranking summary generation"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='High', expected_impact_pct=20.0,
                confidence=0.95, safety_score=0.95, composite_score=0.95
            ),
            OptimizationCandidate(
                id=2, pattern_id=2, category='resource_allocation',
                name='Medium', expected_impact_pct=10.0,
                confidence=0.75, safety_score=0.80, composite_score=0.70
            ),
        ]

        self.optimizer.rank_candidates_with_business_impact(candidates)

        summary = self.optimizer.get_ranking_summary()

        self.assertGreater(summary['total_candidates'], 0)
        self.assertGreaterEqual(summary['auto_apply'], 0)
        self.assertGreaterEqual(summary['manual_review'], 0)
        self.assertGreaterEqual(summary['reject'], 0)
        self.assertGreater(summary['average_business_score'], 0)


class TestApprovalThresholds(unittest.TestCase):
    """Test approval threshold logic"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.optimizations_db = str(Path(self.temp_dir.name) / "optimizations.db")
        self.business_metrics_db = str(Path(self.temp_dir.name) / "business_metrics.db")
        self.business_ranking_db = str(Path(self.temp_dir.name) / "business_ranking.db")

        self.optimizer = BusinessOptimizer(
            optimizations_db=self.optimizations_db,
            business_metrics_db=self.business_metrics_db,
            business_ranking_db=self.business_ranking_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_threshold_auto_apply_high_score(self):
        """Test auto-apply triggered at high business score"""
        # Very high confidence and safety → high score
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='Excellent', expected_impact_pct=25.0,
                confidence=0.98, safety_score=0.96, composite_score=0.97
            )
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)
        self.assertEqual(ranked[0].approval_status, 'auto_apply')

    def test_threshold_manual_review_medium(self):
        """Test manual review at medium business score"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='Good', expected_impact_pct=10.0,
                confidence=0.80, safety_score=0.80, composite_score=0.75
            )
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)
        self.assertEqual(ranked[0].approval_status, 'manual_review')

    def test_threshold_reject_low_score(self):
        """Test rejection at low business score"""
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='parameter_tuning',
                name='Poor', expected_impact_pct=2.0,
                confidence=0.30, safety_score=0.40, composite_score=0.25
            )
        ]

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates)
        self.assertEqual(ranked[0].approval_status, 'reject')


class TestBusinessScoreCalculation(unittest.TestCase):
    """Test business score calculation logic"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.optimizations_db = str(Path(self.temp_dir.name) / "optimizations.db")
        self.business_metrics_db = str(Path(self.temp_dir.name) / "business_metrics.db")
        self.business_ranking_db = str(Path(self.temp_dir.name) / "business_ranking.db")

        self.optimizer = BusinessOptimizer(
            optimizations_db=self.optimizations_db,
            business_metrics_db=self.business_metrics_db,
            business_ranking_db=self.business_ranking_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_business_score_vs_technical_score(self):
        """Test that business score differs from technical score"""
        candidate = OptimizationCandidate(
            id=1, pattern_id=1, category='parameter_tuning',
            name='Test', expected_impact_pct=8.0,
            confidence=0.85, safety_score=0.85, composite_score=0.75
        )

        ranked = self.optimizer.rank_candidates_with_business_impact([candidate])

        # Business score should be calculated differently
        self.assertNotEqual(ranked[0].technical_score, ranked[0].business_score)

    def test_cost_savings_boost_score(self):
        """Test that cost savings boost business score"""
        candidate = OptimizationCandidate(
            id=1, pattern_id=1, category='parameter_tuning',
            name='Cost Saver', expected_impact_pct=5.0,
            confidence=0.80, safety_score=0.80, composite_score=0.70
        )

        # Setup: cost valued 2x latency
        self.optimizer.business_metrics.set_business_weight('cost', 2.0)

        impact_details = {1: {'latency_impact': 5, 'cost_reduction': 10}}
        ranked = self.optimizer.rank_candidates_with_business_impact([candidate], impact_details)

        # Cost reduction should boost score
        self.assertGreater(ranked[0].business_score, 50)


if __name__ == '__main__':
    unittest.main(verbosity=2)
