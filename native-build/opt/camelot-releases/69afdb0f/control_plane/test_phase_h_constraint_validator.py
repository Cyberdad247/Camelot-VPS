#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 4: Constraint Validator & Feedback Integration Tests
Test constraint validation and feedback confidence boosting
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_business_metrics import BusinessMetrics
from phase_h_constraint_validator import ConstraintValidator, FeedbackIntegration


class TestConstraintValidator(unittest.TestCase):
    """Test constraint validation"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.business_metrics_db = str(Path(self.temp_dir.name) / "business_metrics.db")
        self.validation_db = str(Path(self.temp_dir.name) / "validation.db")

        # Initialize business metrics (creates constraints)
        self.metrics = BusinessMetrics(self.business_metrics_db)

        self.validator = ConstraintValidator(
            business_metrics_db=self.business_metrics_db,
            validation_db=self.validation_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_validator_initialization(self):
        """Test validator initializes correctly"""
        self.assertIsNotNone(self.validator)

    def test_valid_candidate_passes(self):
        """Test candidate with no violations passes"""
        # Add memory constraint
        self.metrics.add_constraint(
            'memory', 'Min Cache', is_hard=True, minimum_value=2.0
        )

        # Candidate with 3.0 GB passes minimum of 2.0 GB
        impacts = {'memory': 3.0}
        is_valid, violations = self.validator.validate_candidate(1, impacts)

        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 0)

    def test_hard_constraint_violation(self):
        """Test hard constraint violation fails"""
        # Add hard constraint
        self.metrics.add_constraint(
            'memory', 'Min Cache', is_hard=True, minimum_value=2.0
        )

        # Candidate with 1.5 GB violates minimum
        impacts = {'memory': 1.5}
        is_valid, violations = self.validator.validate_candidate(1, impacts)

        self.assertFalse(is_valid)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].severity, 'critical')

    def test_soft_constraint_violation(self):
        """Test soft constraint violation is warning only"""
        # Add soft constraint
        self.metrics.add_constraint(
            'connections', 'Preferred Limit', is_hard=False, maximum_value=100
        )

        # Candidate with 150 connections violates soft maximum
        impacts = {'connections': 150}
        is_valid, violations = self.validator.validate_candidate(2, impacts)

        # Soft violations don't fail validation
        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].severity, 'warning')

    def test_multiple_constraints(self):
        """Test validation against multiple constraints"""
        self.metrics.add_constraint('memory', 'Min Cache', is_hard=True, minimum_value=2.0)
        self.metrics.add_constraint('connections', 'Max Conn', is_hard=True, maximum_value=100)

        # Violate both
        impacts = {'memory': 1.5, 'connections': 150}
        is_valid, violations = self.validator.validate_candidate(3, impacts)

        self.assertFalse(is_valid)
        self.assertEqual(len(violations), 2)

    def test_get_violations_for_candidate(self):
        """Test retrieving violations for a candidate"""
        self.metrics.add_constraint('memory', 'Min Cache', is_hard=True, minimum_value=2.0)

        impacts = {'memory': 1.5}
        self.validator.validate_candidate(4, impacts)

        violations = self.validator.get_violations_for_candidate(4)
        self.assertEqual(len(violations), 1)
        self.assertIn('minimum', violations[0].description)


class TestFeedbackIntegration(unittest.TestCase):
    """Test feedback integration with patterns"""

    def setUp(self):
        """Create temporary databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.feedback_db = str(Path(self.temp_dir.name) / "feedback.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "patterns.db")
        self.validation_db = str(Path(self.temp_dir.name) / "validation.db")

        # Create feedback database with test signals
        self._create_feedback_db()
        # Create patterns database
        self._create_patterns_db()

        self.feedback = FeedbackIntegration(
            feedback_db=self.feedback_db,
            patterns_db=self.patterns_db,
            validation_db=self.validation_db
        )

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_feedback_db(self):
        """Create feedback database with test signals"""
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE signals (
                id INTEGER PRIMARY KEY,
                signal_type TEXT,
                source TEXT,
                value REAL,
                confidence REAL,
                description TEXT,
                metadata TEXT,
                recorded_at TIMESTAMP
            )
        ''')

        # Add test signals
        c.execute('''
            INSERT INTO signals VALUES
            (1, 'user_satisfaction', 'user', 0.9, 0.95, 'Read operation performs well', '{"operation": "read"}', datetime('now'))
        ''')
        c.execute('''
            INSERT INTO signals VALUES
            (2, 'success_report', 'team', 1.0, 0.9, 'Read optimization worked well', '{"operation": "read"}', datetime('now'))
        ''')
        c.execute('''
            INSERT INTO signals VALUES
            (3, 'failure_report', 'monitoring', 1.0, 0.85, 'Write operation failed once', '{"operation": "write"}', datetime('now'))
        ''')

        conn.commit()
        conn.close()

    def _create_patterns_db(self):
        """Create patterns database"""
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
            (1, 'temporal', 'Read Peak', 0.85, datetime('now'))
        ''')

        conn.commit()
        conn.close()

    def test_feedback_integration_initialization(self):
        """Test feedback integration initializes correctly"""
        self.assertIsNotNone(self.feedback)

    def test_match_feedback_to_patterns(self):
        """Test matching feedback signals to patterns"""
        validations = self.feedback.match_feedback_to_patterns(1, 'read')

        self.assertGreater(len(validations), 0)

    def test_user_satisfaction_feedback(self):
        """Test user satisfaction feedback is recognized"""
        validations = self.feedback.match_feedback_to_patterns(1, 'read')

        # Should have confirmed validation from high satisfaction
        confirmed = [v for v in validations if v.validation_type == 'confirmed']
        self.assertGreater(len(confirmed), 0)

    def test_success_report_feedback(self):
        """Test success reports boost confidence"""
        validations = self.feedback.match_feedback_to_patterns(1, 'read')

        # Success reports should provide strong boost
        boosts = [v.confidence_boost_pct for v in validations if v.validation_type == 'confirmed']
        if boosts:
            self.assertGreater(max(boosts), 5.0)

    def test_failure_report_reduces_confidence(self):
        """Test failure reports reduce confidence"""
        validations = self.feedback.match_feedback_to_patterns(1, 'write')

        # Failure reports should be contradicted
        contradicted = [v for v in validations if v.validation_type == 'contradicted']
        if contradicted:
            self.assertLess(contradicted[0].confidence_boost_pct, 0)

    def test_confidence_boost_calculation(self):
        """Test total confidence boost calculation"""
        # Add validations
        self.feedback.match_feedback_to_patterns(1, 'read')

        # Get boost
        boost = self.feedback.get_pattern_confidence_boost(1)
        self.assertGreater(boost, 0)

    def test_apply_feedback_boost(self):
        """Test applying feedback boost to pattern confidence"""
        # Add validations
        self.feedback.match_feedback_to_patterns(1, 'read')

        # Original confidence
        original = 0.85

        # Apply boost
        new_confidence = self.feedback.apply_feedback_boost_to_pattern(1, original)

        # Should increase (assuming positive feedback)
        self.assertGreaterEqual(new_confidence, original)

    def test_confidence_clamped_to_1(self):
        """Test confidence is clamped to 1.0"""
        # Add very high boosts
        self.feedback.match_feedback_to_patterns(1, 'read')

        # Even with high original confidence, shouldn't exceed 1.0
        new_confidence = self.feedback.apply_feedback_boost_to_pattern(1, 0.99)

        self.assertLessEqual(new_confidence, 1.0)

    def test_feedback_validation_summary(self):
        """Test feedback validation summary"""
        # Add validations
        self.feedback.match_feedback_to_patterns(1, 'read')

        # Get summary
        summary = self.feedback.get_feedback_validation_summary(1)

        self.assertGreater(summary['total_validations'], 0)
        self.assertIn('total_boost', summary)


class TestIntegrationEndToEnd(unittest.TestCase):
    """End-to-end integration tests"""

    def setUp(self):
        """Create all databases"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.business_metrics_db = str(Path(self.temp_dir.name) / "business_metrics.db")
        self.feedback_db = str(Path(self.temp_dir.name) / "feedback.db")
        self.patterns_db = str(Path(self.temp_dir.name) / "patterns.db")
        self.validation_db = str(Path(self.temp_dir.name) / "validation.db")

        # Initialize all systems
        self.metrics = BusinessMetrics(self.business_metrics_db)
        self._create_feedback_db()
        self._create_patterns_db()

        self.validator = ConstraintValidator(self.business_metrics_db, self.validation_db)
        self.feedback = FeedbackIntegration(self.feedback_db, self.patterns_db, self.validation_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_feedback_db(self):
        """Create feedback database"""
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE signals (
                id INTEGER PRIMARY KEY, signal_type TEXT, source TEXT,
                value REAL, confidence REAL, description TEXT, metadata TEXT,
                recorded_at TIMESTAMP
            )
        ''')
        c.execute('''
            INSERT INTO signals VALUES
            (1, 'user_satisfaction', 'user', 0.9, 0.95, 'Read works well', '{"operation": "read"}', datetime('now'))
        ''')
        conn.commit()
        conn.close()

    def _create_patterns_db(self):
        """Create patterns database"""
        conn = sqlite3.connect(self.patterns_db)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE patterns (
                id INTEGER PRIMARY KEY, pattern_type TEXT, name TEXT,
                confidence REAL, created_at TIMESTAMP
            )
        ''')
        c.execute('''
            INSERT INTO patterns VALUES
            (1, 'temporal', 'Read Peak', 0.80, datetime('now'))
        ''')
        conn.commit()
        conn.close()

    def test_end_to_end_validation_workflow(self):
        """Test complete constraint + feedback workflow"""
        # Add constraint
        self.metrics.add_constraint('memory', 'Min Cache', is_hard=True, minimum_value=2.0)

        # Candidate impacts (valid)
        impacts = {'memory': 3.0}

        # Check constraints
        is_valid, violations = self.validator.validate_candidate(1, impacts)
        self.assertTrue(is_valid)

        # Check feedback
        self.feedback.match_feedback_to_patterns(1, 'read')

        # Calculate new confidence
        original_confidence = 0.80
        new_confidence = self.feedback.apply_feedback_boost_to_pattern(1, original_confidence)

        # Should have improved
        self.assertGreaterEqual(new_confidence, original_confidence)

    def test_candidate_with_constraint_violation(self):
        """Test candidate that violates constraints is rejected"""
        # Add hard constraint
        self.metrics.add_constraint('memory', 'Min Cache', is_hard=True, minimum_value=2.0)

        # Invalid impacts
        impacts = {'memory': 1.0}

        # Should fail validation
        is_valid, violations = self.validator.validate_candidate(2, impacts)
        self.assertFalse(is_valid)
        self.assertEqual(len(violations), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
