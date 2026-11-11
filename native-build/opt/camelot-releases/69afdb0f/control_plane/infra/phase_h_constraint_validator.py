#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 4: Constraint Validation & Feedback Integration
Validate constraints and integrate user feedback into pattern confidence
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple


@dataclass
class ConstraintViolation:
    """Constraint violation record"""
    constraint_id: int
    constraint_name: str
    violation_type: str  # 'hard' or 'soft'
    current_value: float
    threshold_value: float
    severity: str  # 'critical' (hard) or 'warning' (soft)
    description: str


@dataclass
class FeedbackValidation:
    """Feedback validation linking user signals to patterns/candidates"""
    id: int = None
    pattern_id: int = None
    candidate_id: int = None
    feedback_signal_id: int = None
    confidence_boost_pct: float = 0.0  # How much to boost pattern confidence
    validation_type: str = None  # 'confirmed', 'contradicted', 'partial'
    feedback_text: str = None
    created_at: str = None


class ConstraintValidator:
    """Validate candidates against operational constraints"""

    def __init__(self, business_metrics_db: str = "control_plane/business_metrics.db",
                 validation_db: str = "control_plane/constraint_validation.db"):
        """Initialize constraint validator"""
        self.business_metrics_db = business_metrics_db
        self.validation_db = validation_db
        self._ensure_db()

    def _ensure_db(self):
        """Create validation database"""
        conn = sqlite3.connect(self.validation_db)
        c = conn.cursor()

        # Constraint violation log
        c.execute('''
            CREATE TABLE IF NOT EXISTS constraint_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                constraint_id INTEGER,
                constraint_name TEXT,
                violation_type TEXT,
                current_value REAL,
                threshold_value REAL,
                severity TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Feedback validation links
        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback_validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id INTEGER,
                candidate_id INTEGER,
                feedback_signal_id INTEGER,
                confidence_boost_pct REAL,
                validation_type TEXT,
                feedback_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def validate_candidate(self, candidate_id: int, candidate_impacts: Dict) -> Tuple[bool, List[ConstraintViolation]]:
        """
        Validate candidate against all constraints

        Args:
            candidate_id: ID of candidate being validated
            candidate_impacts: Dict of impacts {'memory': 1.5, 'connections': 50, etc.}

        Returns:
            (is_valid, list of violations)
        """
        violations = []

        # Get constraints from business metrics
        conn = sqlite3.connect(self.business_metrics_db)
        c = conn.cursor()

        c.execute('''
            SELECT id, constraint_type, name, is_hard, minimum_value, maximum_value
            FROM constraints
            ORDER BY is_hard DESC
        ''')

        constraints = c.fetchall()
        conn.close()

        # Check each constraint
        for constraint_id, constraint_type, name, is_hard, min_val, max_val in constraints:
            if constraint_type not in candidate_impacts:
                continue

            current_value = candidate_impacts[constraint_type]

            # Check minimum
            if min_val is not None and current_value < min_val:
                violation = ConstraintViolation(
                    constraint_id=constraint_id,
                    constraint_name=name,
                    violation_type='hard' if is_hard else 'soft',
                    current_value=current_value,
                    threshold_value=min_val,
                    severity='critical' if is_hard else 'warning',
                    description=f"{name}: minimum {min_val}, got {current_value}"
                )
                violations.append(violation)

            # Check maximum
            if max_val is not None and current_value > max_val:
                violation = ConstraintViolation(
                    constraint_id=constraint_id,
                    constraint_name=name,
                    violation_type='hard' if is_hard else 'soft',
                    current_value=current_value,
                    threshold_value=max_val,
                    severity='critical' if is_hard else 'warning',
                    description=f"{name}: maximum {max_val}, got {current_value}"
                )
                violations.append(violation)

        # Store violations
        self._store_violations(candidate_id, violations)

        # Hard violations fail validation
        has_hard_violation = any(v.violation_type == 'hard' for v in violations)

        return not has_hard_violation, violations

    def _store_violations(self, candidate_id: int, violations: List[ConstraintViolation]):
        """Store constraint violations in database"""
        conn = sqlite3.connect(self.validation_db)
        c = conn.cursor()

        for violation in violations:
            c.execute('''
                INSERT INTO constraint_violations
                (candidate_id, constraint_id, constraint_name, violation_type,
                 current_value, threshold_value, severity, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (candidate_id, violation.constraint_id, violation.constraint_name,
                  violation.violation_type, violation.current_value, violation.threshold_value,
                  violation.severity, violation.description))

        conn.commit()
        conn.close()

    def get_violations_for_candidate(self, candidate_id: int) -> List[ConstraintViolation]:
        """Get all violations for a candidate"""
        conn = sqlite3.connect(self.validation_db)
        c = conn.cursor()

        c.execute('''
            SELECT id, constraint_id, constraint_name, violation_type,
                   current_value, threshold_value, severity, description
            FROM constraint_violations
            WHERE candidate_id = ?
            ORDER BY severity DESC
        ''', (candidate_id,))

        rows = c.fetchall()
        conn.close()

        violations = []
        for row in rows:
            violation = ConstraintViolation(
                constraint_id=row[1],
                constraint_name=row[2],
                violation_type=row[3],
                current_value=row[4],
                threshold_value=row[5],
                severity=row[6],
                description=row[7]
            )
            violations.append(violation)

        return violations


class FeedbackIntegration:
    """Integrate feedback signals to boost pattern confidence"""

    def __init__(self, feedback_db: str = "control_plane/feedback.db",
                 patterns_db: str = "control_plane/patterns.db",
                 validation_db: str = "control_plane/constraint_validation.db"):
        """Initialize feedback integration"""
        self.feedback_db = feedback_db
        self.patterns_db = patterns_db
        self.validation_db = validation_db
        self._ensure_db()

    def _ensure_db(self):
        """Ensure database tables exist"""
        conn = sqlite3.connect(self.validation_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback_validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id INTEGER,
                candidate_id INTEGER,
                feedback_signal_id INTEGER,
                confidence_boost_pct REAL,
                validation_type TEXT,
                feedback_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def match_feedback_to_patterns(self, pattern_id: int, operation_type: str) -> List[FeedbackValidation]:
        """
        Match feedback signals to a pattern and boost confidence

        Args:
            pattern_id: ID of pattern to validate
            operation_type: Operation type for pattern (read, write, route, etc.)

        Returns:
            List of validation records
        """
        validations = []

        # Get feedback signals matching this operation type
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        c.execute('''
            SELECT id, signal_type, source, value, confidence, description, metadata
            FROM signals
            WHERE description LIKE ? OR metadata LIKE ?
            ORDER BY confidence DESC
        ''', (f'%{operation_type}%', f'%{operation_type}%'))

        signals = c.fetchall()
        conn.close()

        # Evaluate each signal
        for signal in signals:
            signal_id, signal_type, source, value, signal_confidence, description, metadata = signal

            # Determine validation type and confidence boost
            if signal_type == 'user_satisfaction':
                if value >= 0.8:
                    validation_type = 'confirmed'
                    boost = 10.0  # 10% confidence boost
                elif value < 0.3:
                    validation_type = 'contradicted'
                    boost = -5.0  # Reduce confidence
                else:
                    validation_type = 'partial'
                    boost = 5.0

            elif signal_type == 'success_report':
                validation_type = 'confirmed'
                boost = 15.0  # Strong confirmation

            elif signal_type == 'failure_report':
                validation_type = 'contradicted'
                boost = -10.0

            else:
                continue  # Skip other signal types

            # Create validation record
            validation = FeedbackValidation(
                pattern_id=pattern_id,
                feedback_signal_id=signal_id,
                confidence_boost_pct=boost,
                validation_type=validation_type,
                feedback_text=description,
                created_at=datetime.now().isoformat()
            )

            validations.append(validation)

            # Store validation
            self._store_validation(validation)

        return validations

    def _store_validation(self, validation: FeedbackValidation):
        """Store feedback validation in database"""
        conn = sqlite3.connect(self.validation_db)
        c = conn.cursor()

        c.execute('''
            INSERT INTO feedback_validations
            (pattern_id, candidate_id, feedback_signal_id, confidence_boost_pct,
             validation_type, feedback_text)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (validation.pattern_id, validation.candidate_id, validation.feedback_signal_id,
              validation.confidence_boost_pct, validation.validation_type, validation.feedback_text))

        conn.commit()
        conn.close()

    def get_pattern_confidence_boost(self, pattern_id: int) -> float:
        """
        Calculate total confidence boost for a pattern from feedback

        Returns:
            Confidence boost percentage (can be negative)
        """
        conn = sqlite3.connect(self.validation_db)
        c = conn.cursor()

        c.execute('''
            SELECT SUM(confidence_boost_pct)
            FROM feedback_validations
            WHERE pattern_id = ?
        ''', (pattern_id,))

        total_boost = c.fetchone()[0] or 0.0
        conn.close()

        return total_boost

    def apply_feedback_boost_to_pattern(self, pattern_id: int, current_confidence: float) -> float:
        """
        Apply feedback boosts to pattern confidence

        Args:
            pattern_id: ID of pattern
            current_confidence: Current pattern confidence (0-1)

        Returns:
            New confidence after feedback boost
        """
        boost_pct = self.get_pattern_confidence_boost(pattern_id)

        # Convert boost percentage to confidence adjustment
        # +10% boost means increase by 10% of remaining confidence
        adjustment = (1.0 - current_confidence) * (boost_pct / 100.0)

        new_confidence = current_confidence + adjustment
        return max(0.0, min(1.0, new_confidence))  # Clamp to 0-1

    def get_feedback_validation_summary(self, pattern_id: int) -> Dict:
        """Get summary of feedback validation for a pattern"""
        conn = sqlite3.connect(self.validation_db)
        c = conn.cursor()

        summary = {
            'total_validations': 0,
            'confirmed': 0,
            'contradicted': 0,
            'partial': 0,
            'total_boost': 0.0,
        }

        c.execute('''
            SELECT validation_type, COUNT(*), SUM(confidence_boost_pct)
            FROM feedback_validations
            WHERE pattern_id = ?
            GROUP BY validation_type
        ''', (pattern_id,))

        for validation_type, count, boost in c.fetchall():
            summary['total_validations'] += count

            if validation_type == 'confirmed':
                summary['confirmed'] = count
            elif validation_type == 'contradicted':
                summary['contradicted'] = count
            elif validation_type == 'partial':
                summary['partial'] = count

            summary['total_boost'] += boost or 0.0

        conn.close()

        return summary


if __name__ == '__main__':
    # Example usage
    validator = ConstraintValidator()

    # Validate a candidate
    impacts = {'memory': 2.0, 'connections': 50}
    is_valid, violations = validator.validate_candidate(1, impacts)

    print("Constraint Validation:")
    print(f"  Valid: {is_valid}")
    print(f"  Violations: {len(violations)}")

    # Feedback integration
    feedback = FeedbackIntegration()

    # Match feedback to pattern
    validations = feedback.match_feedback_to_patterns(1, 'read')
    print(f"\nFeedback Validations: {len(validations)}")

    # Get confidence boost
    boost = feedback.get_pattern_confidence_boost(1)
    print(f"  Total boost: {boost:.1f}%")

    # Apply boost
    new_confidence = feedback.apply_feedback_boost_to_pattern(1, 0.85)
    print(f"  New confidence: {new_confidence:.2f}")
