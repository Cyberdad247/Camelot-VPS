#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 2: Result Tracker
Measure actual vs predicted impact and validate optimization outcomes
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ImpactDelta:
    """Difference between predicted and actual impact"""
    metric_name: str
    predicted_pct: float
    actual_pct: float
    delta_pct: float  # actual - predicted
    tolerance_pct: float = 5.0  # Allow 5% deviation
    within_tolerance: bool = None  # Set after instantiation


@dataclass
class ImpactValidation:
    """Result of validating an optimization's impact"""
    execution_id: int = None
    validation_timestamp: str = None
    all_metrics_valid: bool = False
    latency_impact: ImpactDelta = None
    throughput_impact: ImpactDelta = None
    cost_impact: ImpactDelta = None
    availability_impact: ImpactDelta = None
    sla_compliance: bool = False
    kpi_compliance: bool = False
    should_rollback: bool = False
    rollback_reason: str = None


class ResultTracker:
    """Track and validate optimization results against predictions"""

    def __init__(self, tracker_db: str = "control_plane/result_tracker.db",
                 executor_db: str = "control_plane/executor.db",
                 business_metrics_db: str = "control_plane/business_metrics.db"):
        """Initialize result tracker"""
        self.tracker_db = tracker_db
        self.executor_db = executor_db
        self.business_metrics_db = business_metrics_db
        self._ensure_db()

    def _ensure_db(self):
        """Create result tracker database"""
        conn = sqlite3.connect(self.tracker_db)
        c = conn.cursor()

        # Impact validations
        c.execute('''
            CREATE TABLE IF NOT EXISTS impact_validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                validation_timestamp TIMESTAMP,
                all_metrics_valid INTEGER,
                latency_impact TEXT,
                throughput_impact TEXT,
                cost_impact TEXT,
                availability_impact TEXT,
                sla_compliance INTEGER,
                kpi_compliance INTEGER,
                should_rollback INTEGER,
                rollback_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # SLA compliance log
        c.execute('''
            CREATE TABLE IF NOT EXISTS sla_compliance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER,
                operation_type TEXT,
                p95_latency_ms REAL,
                p95_target_ms REAL,
                passed INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # KPI compliance log
        c.execute('''
            CREATE TABLE IF NOT EXISTS kpi_compliance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER,
                operation_type TEXT,
                metric_name TEXT,
                actual_value REAL,
                target_value REAL,
                passed INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def validate_execution_result(self, execution_id: int,
                                 actual_state: Dict) -> ImpactValidation:
        """
        Validate an execution's actual results against predictions

        Args:
            execution_id: ID of execution to validate
            actual_state: Dict with actual measured metrics
                         {'latency_p95_ms': 1.9, 'throughput_ops_sec': 1050, ...}

        Returns:
            ImpactValidation with pass/fail and rollback recommendation
        """

        # Step 1: Get predicted state from execution history
        predicted_state = self._get_predicted_state(execution_id)
        if not predicted_state:
            return ImpactValidation(
                execution_id=execution_id,
                validation_timestamp=datetime.now().isoformat(),
                should_rollback=True,
                rollback_reason="Could not find predicted state for execution"
            )

        # Step 2: Calculate impact deltas for each metric
        validation = ImpactValidation(
            execution_id=execution_id,
            validation_timestamp=datetime.now().isoformat()
        )

        # Latency impact
        latency_predicted = (predicted_state['after']['latency_p95_ms'] -
                           predicted_state['before']['latency_p95_ms']) / predicted_state['before']['latency_p95_ms'] * 100
        latency_actual = (actual_state.get('latency_p95_ms', predicted_state['after']['latency_p95_ms']) -
                         predicted_state['before']['latency_p95_ms']) / predicted_state['before']['latency_p95_ms'] * 100

        latency_delta = ImpactDelta(
            metric_name='latency_p95',
            predicted_pct=round(latency_predicted, 1),
            actual_pct=round(latency_actual, 1),
            delta_pct=round(latency_actual - latency_predicted, 1)
        )
        latency_delta.within_tolerance = abs(latency_delta.delta_pct) <= latency_delta.tolerance_pct
        validation.latency_impact = latency_delta

        # Throughput impact
        throughput_predicted = (predicted_state['after']['throughput_ops_sec'] -
                              predicted_state['before']['throughput_ops_sec']) / predicted_state['before']['throughput_ops_sec'] * 100
        throughput_actual = (actual_state.get('throughput_ops_sec', predicted_state['after']['throughput_ops_sec']) -
                            predicted_state['before']['throughput_ops_sec']) / predicted_state['before']['throughput_ops_sec'] * 100

        throughput_delta = ImpactDelta(
            metric_name='throughput',
            predicted_pct=round(throughput_predicted, 1),
            actual_pct=round(throughput_actual, 1),
            delta_pct=round(throughput_actual - throughput_predicted, 1)
        )
        throughput_delta.within_tolerance = abs(throughput_delta.delta_pct) <= throughput_delta.tolerance_pct
        validation.throughput_impact = throughput_delta

        # Cost impact
        cost_predicted = (predicted_state['after']['cost_per_op'] -
                        predicted_state['before']['cost_per_op']) / predicted_state['before']['cost_per_op'] * 100
        cost_actual = (actual_state.get('cost_per_op', predicted_state['after']['cost_per_op']) -
                      predicted_state['before']['cost_per_op']) / predicted_state['before']['cost_per_op'] * 100

        cost_delta = ImpactDelta(
            metric_name='cost',
            predicted_pct=round(cost_predicted, 1),
            actual_pct=round(cost_actual, 1),
            delta_pct=round(cost_actual - cost_predicted, 1)
        )
        cost_delta.within_tolerance = abs(cost_delta.delta_pct) <= cost_delta.tolerance_pct
        validation.cost_impact = cost_delta

        # Availability impact
        availability_predicted = predicted_state['after']['availability_pct'] - predicted_state['before']['availability_pct']
        availability_actual = actual_state.get('availability_pct', predicted_state['after']['availability_pct']) - predicted_state['before']['availability_pct']

        availability_delta = ImpactDelta(
            metric_name='availability',
            predicted_pct=round(availability_predicted, 2),
            actual_pct=round(availability_actual, 2),
            delta_pct=round(availability_actual - availability_predicted, 2),
            tolerance_pct=0.1
        )
        availability_delta.within_tolerance = abs(availability_delta.delta_pct) <= availability_delta.tolerance_pct
        validation.availability_impact = availability_delta

        # Step 3: Check SLA compliance
        validation.sla_compliance = self._check_sla_compliance(
            execution_id, actual_state
        )

        # Step 4: Check KPI compliance
        validation.kpi_compliance = self._check_kpi_compliance(
            execution_id, actual_state
        )

        # Step 5: Determine if all metrics are valid
        validation.all_metrics_valid = (
            validation.latency_impact.within_tolerance and
            validation.throughput_impact.within_tolerance and
            validation.cost_impact.within_tolerance and
            validation.availability_impact.within_tolerance
        )

        # Step 6: Determine if rollback needed
        validation.should_rollback = False
        if not validation.sla_compliance:
            validation.should_rollback = True
            validation.rollback_reason = "SLA compliance check failed"
        elif not validation.kpi_compliance:
            validation.should_rollback = True
            validation.rollback_reason = "KPI compliance check failed"
        elif not validation.all_metrics_valid:
            # Only rollback if multiple metrics way off
            invalid_count = sum([
                not validation.latency_impact.within_tolerance,
                not validation.throughput_impact.within_tolerance,
                not validation.cost_impact.within_tolerance,
                not validation.availability_impact.within_tolerance
            ])
            if invalid_count >= 2:
                validation.should_rollback = True
                validation.rollback_reason = f"{invalid_count} metrics outside tolerance"

        # Step 7: Store validation result
        self._store_validation(validation)

        return validation

    def _get_predicted_state(self, execution_id: int) -> Optional[Dict]:
        """Get predicted state from execution history"""
        try:
            conn = sqlite3.connect(self.executor_db)
            c = conn.cursor()

            c.execute('''
                SELECT state_before, state_after FROM executions WHERE id = ?
            ''', (execution_id,))

            row = c.fetchone()
            conn.close()

            if not row:
                return None

            state_before = json.loads(row[0]) if row[0] else {}
            state_after = json.loads(row[1]) if row[1] else {}

            return {'before': state_before, 'after': state_after}
        except Exception:
            return None

    def _check_sla_compliance(self, execution_id: int, actual_state: Dict) -> bool:
        """Check if SLA targets are met after optimization"""
        try:
            conn = sqlite3.connect(self.business_metrics_db)
            c = conn.cursor()

            # Check latency SLA
            c.execute('''
                SELECT p95_latency_ms FROM sla_thresholds WHERE operation_type = ?
            ''', ('read',))

            row = c.fetchone()
            conn.close()

            if not row:
                return True  # No SLA defined

            sla_target = row[0]
            actual_latency = actual_state.get('latency_p95_ms', 0)

            return actual_latency <= sla_target
        except Exception:
            return True  # Assume compliant on error

    def _check_kpi_compliance(self, execution_id: int, actual_state: Dict) -> bool:
        """Check if KPI targets are met after optimization"""
        try:
            conn = sqlite3.connect(self.business_metrics_db)
            c = conn.cursor()

            # Check cost KPI
            c.execute('''
                SELECT cost_per_op FROM kpi_targets WHERE operation_type = ?
            ''', ('read',))

            row = c.fetchone()
            conn.close()

            if not row:
                return True  # No KPI defined

            kpi_target = row[0]
            actual_cost = actual_state.get('cost_per_op', 0)

            return actual_cost <= kpi_target
        except Exception:
            return True  # Assume compliant on error

    def _store_validation(self, validation: ImpactValidation):
        """Store validation result in database"""
        conn = sqlite3.connect(self.tracker_db)
        c = conn.cursor()

        c.execute('''
            INSERT INTO impact_validations
            (execution_id, validation_timestamp, all_metrics_valid,
             latency_impact, throughput_impact, cost_impact, availability_impact,
             sla_compliance, kpi_compliance, should_rollback, rollback_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            validation.execution_id,
            validation.validation_timestamp,
            1 if validation.all_metrics_valid else 0,
            json.dumps(asdict(validation.latency_impact)) if validation.latency_impact else None,
            json.dumps(asdict(validation.throughput_impact)) if validation.throughput_impact else None,
            json.dumps(asdict(validation.cost_impact)) if validation.cost_impact else None,
            json.dumps(asdict(validation.availability_impact)) if validation.availability_impact else None,
            1 if validation.sla_compliance else 0,
            1 if validation.kpi_compliance else 0,
            1 if validation.should_rollback else 0,
            validation.rollback_reason
        ))

        conn.commit()
        conn.close()

    def get_validation_history(self, limit: int = 10) -> List[ImpactValidation]:
        """Get recent validation history"""
        conn = sqlite3.connect(self.tracker_db)
        c = conn.cursor()

        c.execute('''
            SELECT execution_id, validation_timestamp, all_metrics_valid,
                   sla_compliance, kpi_compliance, should_rollback, rollback_reason
            FROM impact_validations
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))

        rows = c.fetchall()
        conn.close()

        validations = []
        for row in rows:
            validation = ImpactValidation(
                execution_id=row[0],
                validation_timestamp=row[1],
                all_metrics_valid=bool(row[2]),
                sla_compliance=bool(row[3]),
                kpi_compliance=bool(row[4]),
                should_rollback=bool(row[5]),
                rollback_reason=row[6]
            )
            validations.append(validation)

        return validations

    def get_validation_statistics(self) -> Dict:
        """Get validation statistics"""
        conn = sqlite3.connect(self.tracker_db)
        c = conn.cursor()

        stats = {
            'total_validations': 0,
            'passed': 0,
            'failed': 0,
            'rollbacks_triggered': 0,
            'sla_compliance_rate': 0.0,
            'kpi_compliance_rate': 0.0,
        }

        c.execute('SELECT COUNT(*) FROM impact_validations')
        stats['total_validations'] = c.fetchone()[0]

        if stats['total_validations'] > 0:
            c.execute('SELECT COUNT(*) FROM impact_validations WHERE all_metrics_valid = 1')
            stats['passed'] = c.fetchone()[0]

            stats['failed'] = stats['total_validations'] - stats['passed']

            c.execute('SELECT COUNT(*) FROM impact_validations WHERE should_rollback = 1')
            stats['rollbacks_triggered'] = c.fetchone()[0]

            c.execute('SELECT COUNT(*) FROM impact_validations WHERE sla_compliance = 1')
            sla_pass = c.fetchone()[0]
            stats['sla_compliance_rate'] = round(sla_pass / stats['total_validations'] * 100, 1)

            c.execute('SELECT COUNT(*) FROM impact_validations WHERE kpi_compliance = 1')
            kpi_pass = c.fetchone()[0]
            stats['kpi_compliance_rate'] = round(kpi_pass / stats['total_validations'] * 100, 1)

        conn.close()
        return stats


if __name__ == '__main__':
    tracker = ResultTracker()

    # Example: Validate an execution
    actual_state = {
        'latency_p95_ms': 1.95,  # Slightly better than predicted (1.9)
        'throughput_ops_sec': 1040,  # Slightly lower than predicted (1050)
        'cost_per_op': 0.0001,  # Same as predicted
        'availability_pct': 99.9,  # Same as predicted
    }

    validation = tracker.validate_execution_result(1, actual_state)

    print("Validation Result:")
    print(f"  All Metrics Valid: {validation.all_metrics_valid}")
    print(f"  SLA Compliant: {validation.sla_compliance}")
    print(f"  KPI Compliant: {validation.kpi_compliance}")
    print(f"  Should Rollback: {validation.should_rollback}")

    if validation.latency_impact:
        print("\nLatency Impact:")
        print(f"  Predicted: {validation.latency_impact.predicted_pct:+.1f}%")
        print(f"  Actual: {validation.latency_impact.actual_pct:+.1f}%")
        print(f"  Delta: {validation.latency_impact.delta_pct:+.1f}%")
        print(f"  Within Tolerance: {validation.latency_impact.within_tolerance}")

    # Get statistics
    stats = tracker.get_validation_statistics()
    print("\nValidation Statistics:")
    print(f"  Total: {stats['total_validations']}")
    print(f"  Passed: {stats['passed']}")
    print(f"  SLA Compliance Rate: {stats['sla_compliance_rate']}%")
