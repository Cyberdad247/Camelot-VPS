#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 5: End-to-End Integration Tests
Test complete flow: signals → metrics → ranking → constraints → decisions
"""

import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_business_metrics import BusinessMetrics
from phase_h_business_optimizer import BusinessOptimizer
from phase_h_constraint_validator import ConstraintValidator, FeedbackIntegration
from phase_h_feedback_collector import FeedbackCollector
from phase_h_optimizer import OptimizationCandidate


class TestEndToEndWorkflow(unittest.TestCase):
    """Test complete Week 3 workflow"""

    def setUp(self):
        """Create all databases"""
        self.temp_dir = tempfile.TemporaryDirectory()

        self.feedback_db = str(Path(self.temp_dir.name) / "feedback.db")
        self.business_metrics_db = str(Path(self.temp_dir.name) / "business_metrics.db")
        self.optimizations_db = str(Path(self.temp_dir.name) / "optimizations.db")
        self.business_ranking_db = str(Path(self.temp_dir.name) / "business_ranking.db")
        self.validation_db = str(Path(self.temp_dir.name) / "validation.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "patterns.db")

        # Initialize all systems
        self.feedback_collector = FeedbackCollector(self.feedback_db)
        self.metrics = BusinessMetrics(self.business_metrics_db)
        self.optimizer = BusinessOptimizer(
            self.optimizations_db,
            self.business_metrics_db,
            self.business_ranking_db
        )
        self.validator = ConstraintValidator(self.business_metrics_db, self.validation_db)
        self.feedback_integration = FeedbackIntegration(
            self.feedback_db,
            self.patterns_db,
            self.validation_db
        )

        self._create_test_patterns_db()

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_test_patterns_db(self):
        """Create patterns database for testing"""
        conn = sqlite3.connect(self.patterns_db)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE patterns (
                id INTEGER PRIMARY KEY,
                pattern_type TEXT,
                name TEXT,
                confidence REAL,
                created_at TIMESTAMP
            )
        ''')
        c.execute('''
            INSERT INTO patterns VALUES
            (1, 'temporal', 'Read Peak', 0.80, datetime('now')),
            (2, 'load', 'Write Surge', 0.75, datetime('now'))
        ''')
        conn.commit()
        conn.close()

    def test_workflow_cost_optimization_scenario(self):
        """Test complete workflow: Cost optimization with constraints"""

        # Step 1: Collect user feedback
        self.feedback_collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.2,  # Very dissatisfied with costs
            confidence=0.95,
            description='Costs are too high for read operations',
            metadata={'operation': 'read', 'concern': 'budget'}
        )

        self.feedback_collector.collect_signal(
            signal_type='business_metric',
            source='monitoring',
            value=0.15,  # 15% cost increase
            confidence=0.90,
            description='Monthly costs increased 15%',
            metadata={'operation': 'read', 'metric_type': 'cost'}
        )

        # Verify signals collected
        signals = self.feedback_collector.get_signals(hours_back=1, signal_type='user_satisfaction')
        self.assertEqual(len(signals), 1)

        # Step 2: Define business priorities
        self.metrics.set_business_weight('latency', 1.0)
        self.metrics.set_business_weight('cost', 2.0)  # Cost valued 2x latency
        self.metrics.set_business_weight('availability', 3.0)

        # Add constraints
        self.metrics.add_constraint(
            'memory', 'Min Cache', is_hard=True, minimum_value=2.0,
            description='Never reduce below 2GB'
        )

        # Step 3: Create optimization candidates
        candidates = [
            OptimizationCandidate(
                id=1, pattern_id=1, category='resource_allocation',
                name='Reduce Cache by 10%',
                expected_impact_pct=2.0,
                confidence=0.90, safety_score=0.92, composite_score=0.88
            ),
            OptimizationCandidate(
                id=2, pattern_id=2, category='parameter_tuning',
                name='Optimize Connection Pool',
                expected_impact_pct=5.0,
                confidence=0.85, safety_score=0.88, composite_score=0.85
            ),
        ]

        # Step 4: Rank with business impact
        impact_details = {
            1: {'latency_impact': 2, 'cost_reduction': 10},  # +2% latency, -10% cost
            2: {'latency_impact': 5, 'cost_reduction': 3},   # +5% latency, -3% cost
        }

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates, impact_details)

        self.assertEqual(len(ranked), 2)
        # Candidate 1 should rank higher (better cost reduction)
        self.assertGreater(ranked[0].business_score, ranked[1].business_score)

        # Step 5: Validate constraints
        impacts_1 = {'memory': 2.7}  # 10% reduction from 3GB
        is_valid, violations = self.validator.validate_candidate(1, impacts_1)
        self.assertTrue(is_valid)  # Passes minimum
        self.assertEqual(len(violations), 0)

        # Step 6: Integrate feedback
        validations = self.feedback_integration.match_feedback_to_patterns(1, 'read')
        self.assertGreater(len(validations), 0)

        # Get feedback summary
        summary = self.feedback_integration.get_feedback_validation_summary(1)
        self.assertGreater(summary['total_validations'], 0)

        # Step 7: Final decision
        self.assertEqual(ranked[0].approval_status, 'auto_apply')
        self.assertIn('High business impact', ranked[0].rationale)

    def test_workflow_uptime_critical_scenario(self):
        """Test complete workflow: Uptime critical - flag for review despite latency gain"""

        # Step 1: Collect feedback emphasizing uptime importance
        self.feedback_collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.95,
            confidence=0.98,
            description='Uptime is critical for business',
            metadata={'operation': 'write', 'concern': 'availability'}
        )

        self.feedback_collector.collect_signal(
            signal_type='success_report',
            source='team',
            value=1.0,
            confidence=0.95,
            description='99.99% uptime achieved last month',
            metadata={'operation': 'write', 'metric': 'availability'}
        )

        # Step 2: Set availability as critical
        self.metrics.set_business_weight('latency', 1.0)
        self.metrics.set_business_weight('cost', 1.5)
        self.metrics.set_business_weight('availability', 3.0)  # Critical

        # Step 3: Create candidate with low confidence that risks availability
        candidates = [
            OptimizationCandidate(
                id=3, pattern_id=1, category='parameter_tuning',
                name='Low Confidence Optimization',
                expected_impact_pct=2.0,
                confidence=0.45, safety_score=0.50, composite_score=0.40
            ),
        ]

        # Candidate with low confidence despite availability being critical
        impact_details = {
            3: {
                'latency_impact': 2,  # +2% latency (small degradation)
                'availability_impact': -0.5,  # -0.5% availability (risk)
                'cost_reduction': 0
            }
        }

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates, impact_details)

        # Low confidence + availability risk should flag for review or reject
        self.assertIn(ranked[0].approval_status, ['manual_review', 'reject'])

    def test_workflow_mixed_signals_scenario(self):
        """Test workflow with conflicting signals"""

        # Step 1: Collect mixed signals
        self.feedback_collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.7,
            confidence=0.85,
            description='Latency improved but costs up',
            metadata={'operation': 'read', 'sentiment': 'mixed'}
        )

        self.feedback_collector.collect_signal(
            signal_type='failure_report',
            source='monitoring',
            value=1.0,
            confidence=0.90,
            description='One incident in past month',
            metadata={'operation': 'read', 'metric': 'reliability'}
        )

        # Step 2: Setup balanced weights
        self.metrics.set_business_weight('latency', 1.0)
        self.metrics.set_business_weight('cost', 1.5)
        self.metrics.set_business_weight('availability', 2.0)

        # Step 3: Create candidate
        candidates = [
            OptimizationCandidate(
                id=4, pattern_id=1, category='resource_allocation',
                name='Balanced Optimization',
                expected_impact_pct=7.0,
                confidence=0.78, safety_score=0.80, composite_score=0.76
            ),
        ]

        impact_details = {
            4: {'latency_impact': 7, 'cost_reduction': 5, 'availability_impact': -0.1}
        }

        ranked = self.optimizer.rank_candidates_with_business_impact(candidates, impact_details)

        # Should be manual review (moderate impact, mixed signals)
        self.assertIn(ranked[0].approval_status, ['manual_review', 'auto_apply'])

    def test_performance_metrics(self):
        """Test performance characteristics of full pipeline"""

        # Benchmark signal collection
        start = time.time()
        for i in range(100):
            self.feedback_collector.collect_signal(
                signal_type='business_metric',
                source='monitoring',
                value=0.5 + i * 0.001,
                confidence=0.95,
                description=f'Metric {i}'
            )
        signal_time = time.time() - start

        # Should handle 100 signals in < 1 second
        self.assertLess(signal_time, 1.0)

        # Benchmark retrieval
        start = time.time()
        self.feedback_collector.get_signals(hours_back=24)
        retrieval_time = time.time() - start

        # Should retrieve in < 100ms
        self.assertLess(retrieval_time, 0.1)

        # Benchmark ranking
        candidates = [
            OptimizationCandidate(
                id=i, pattern_id=1, category='parameter_tuning',
                name=f'Candidate {i}',
                expected_impact_pct=5.0 + i * 0.1,
                confidence=0.8 + i * 0.001,
                safety_score=0.85,
                composite_score=0.80
            )
            for i in range(50)
        ]

        start = time.time()
        self.optimizer.rank_candidates_with_business_impact(candidates)
        ranking_time = time.time() - start

        # Should rank 50 candidates in < 500ms
        self.assertLess(ranking_time, 0.5)

    def test_complete_pipeline_statistics(self):
        """Test complete pipeline generates correct statistics"""

        # Collect various signals
        for i in range(10):
            self.feedback_collector.collect_signal(
                signal_type='user_satisfaction',
                source='user',
                value=0.7 + i * 0.02,
                confidence=0.90
            )

        # Create and rank candidates
        candidates = [
            OptimizationCandidate(
                id=i, pattern_id=1, category='parameter_tuning',
                name=f'Candidate {i}',
                expected_impact_pct=5.0,
                confidence=0.85, safety_score=0.90, composite_score=0.85
            )
            for i in range(10)
        ]

        self.optimizer.rank_candidates_with_business_impact(candidates)

        # Get summary
        summary = self.optimizer.get_ranking_summary()

        self.assertEqual(summary['total_candidates'], 10)
        self.assertGreater(summary['average_business_score'], 0)

        # Get feedback stats
        stats = self.feedback_collector.get_signal_stats()
        self.assertEqual(stats['total_signals'], 10)
        # Stats contains signal type counts and other info
        self.assertIn('total_signals', stats)

    def test_error_recovery(self):
        """Test system handles errors gracefully"""

        # Try to validate with non-existent constraint type
        impacts = {'nonexistent': 1.5}
        is_valid, violations = self.validator.validate_candidate(999, impacts)

        # Should pass (no constraint for this type)
        self.assertTrue(is_valid)

        # Try to get candidates for non-existent approval status
        candidates = self.optimizer.get_candidates_by_status('unknown_status')
        self.assertEqual(len(candidates), 0)

        # Try to rank empty candidate list
        ranked = self.optimizer.rank_candidates_with_business_impact([])
        self.assertEqual(len(ranked), 0)


class TestDataIntegrity(unittest.TestCase):
    """Test data integrity across Week 3 systems"""

    def setUp(self):
        """Create all databases"""
        self.temp_dir = tempfile.TemporaryDirectory()

        self.feedback_db = str(Path(self.temp_dir.name) / "feedback.db")
        self.business_metrics_db = str(Path(self.temp_dir.name) / "business_metrics.db")
        self.business_ranking_db = str(Path(self.temp_dir.name) / "business_ranking.db")
        self.validation_db = str(Path(self.temp_dir.name) / "validation.db")

        self.feedback_collector = FeedbackCollector(self.feedback_db)
        self.metrics = BusinessMetrics(self.business_metrics_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_duplicate_prevention(self):
        """Test duplicates are prevented"""

        # Collect same signal multiple times
        for _ in range(3):
            self.feedback_collector.collect_signal(
                signal_type='user_satisfaction',
                source='user',
                value=0.8,
                confidence=0.95,
                description='Same signal'
            )

        # Should only count 1 (duplicates prevented in 5-min window)
        signals = self.feedback_collector.get_signals(hours_back=1)
        self.assertEqual(len(signals), 1)

    def test_confidence_bounds(self):
        """Test confidence values stay within bounds"""

        # Collect signals with extreme confidence
        self.feedback_collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.9,
            confidence=0.0,  # Min
            description='Low confidence'
        )

        self.feedback_collector.collect_signal(
            signal_type='user_satisfaction',
            source='user',
            value=0.8,
            confidence=1.0,  # Max
            description='High confidence'
        )

        signals = self.feedback_collector.get_signals(hours_back=1)

        for signal in signals:
            self.assertGreaterEqual(signal.confidence, 0.0)
            self.assertLessEqual(signal.confidence, 1.0)

    def test_constraint_consistency(self):
        """Test constraint data is consistent"""

        # Add constraint
        _constraint = self.metrics.add_constraint(
            'memory', 'Min Cache', is_hard=True, minimum_value=2.0
        )

        # Retrieve and verify
        retrieved = self.metrics.get_constraints(is_hard=True)

        names = [c.name for c in retrieved]
        self.assertIn('Min Cache', names)

        # Verify values match
        min_cache = next(c for c in retrieved if c.name == 'Min Cache')
        self.assertEqual(min_cache.minimum_value, 2.0)
        self.assertTrue(min_cache.is_hard)


if __name__ == '__main__':
    unittest.main(verbosity=2)
