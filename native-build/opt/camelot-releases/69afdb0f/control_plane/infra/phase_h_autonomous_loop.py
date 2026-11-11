#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 4: Autonomous Optimization Loop
Orchestrate continuous autonomous optimization with learning feedback
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class LoopStatus(Enum):
    """Status of an autonomous loop iteration"""
    IDLE = "idle"
    MONITORING = "monitoring"
    EXECUTING = "executing"
    VALIDATING = "validating"
    ROLLING_BACK = "rolling_back"
    LEARNING = "learning"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class LoopIteration:
    """A single iteration of the autonomous optimization loop"""
    iteration_id: int = None
    candidate_id: int = None
    candidate_name: str = None
    status: LoopStatus = LoopStatus.IDLE
    execution_success: bool = False
    validation_success: bool = False
    rollback_triggered: bool = False
    predicted_improvement: float = 0.0
    actual_improvement: float = 0.0
    improvement_accuracy: float = 0.0
    started_at: str = None
    completed_at: str = None
    loop_duration_seconds: float = 0.0


@dataclass
class LoopMetrics:
    """Metrics tracking autonomous loop performance"""
    total_iterations: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    rollbacks_triggered: int = 0
    total_predicted_improvement: float = 0.0
    total_actual_improvement: float = 0.0
    avg_improvement_accuracy: float = 0.0
    cumulative_latency_reduction_pct: float = 0.0
    cumulative_cost_reduction_pct: float = 0.0
    avg_loop_duration_seconds: float = 0.0
    learning_efficiency: float = 0.0  # actual/predicted ratio


class AutonomousOptimizationLoop:
    """Orchestrate continuous autonomous optimization with learning feedback"""

    def __init__(self, loop_db: str = "control_plane/autonomous_loop.db",
                 executor_db: str = "control_plane/executor.db",
                 tracker_db: str = "control_plane/result_tracker.db",
                 rollback_db: str = "control_plane/rollback.db"):
        """Initialize autonomous optimization loop"""
        self.loop_db = loop_db
        self.executor_db = executor_db
        self.tracker_db = tracker_db
        self.rollback_db = rollback_db
        self._ensure_db()
        self._max_concurrent_optimizations = 1  # One at a time
        self._min_iteration_interval_seconds = 60  # Wait between iterations
        self._max_rollback_rate = 0.3  # Stop if >30% rollback rate

    def _ensure_db(self):
        """Create autonomous loop database"""
        conn = sqlite3.connect(self.loop_db)
        c = conn.cursor()

        # Loop iterations
        c.execute('''
            CREATE TABLE IF NOT EXISTS loop_iterations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                candidate_name TEXT,
                status TEXT,
                execution_success INTEGER,
                validation_success INTEGER,
                rollback_triggered INTEGER,
                predicted_improvement REAL,
                actual_improvement REAL,
                improvement_accuracy REAL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                loop_duration_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Loop metrics log
        c.execute('''
            CREATE TABLE IF NOT EXISTS loop_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP,
                total_iterations INTEGER,
                successful_executions INTEGER,
                failed_executions INTEGER,
                rollbacks_triggered INTEGER,
                avg_improvement_accuracy REAL,
                cumulative_latency_reduction REAL,
                cumulative_cost_reduction REAL,
                learning_efficiency REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Loop control (stop conditions, throttling)
        c.execute('''
            CREATE TABLE IF NOT EXISTS loop_control (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loop_enabled INTEGER,
                last_iteration_at TIMESTAMP,
                emergency_stop INTEGER,
                stop_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def run_autonomous_loop_iteration(self) -> Optional[LoopIteration]:
        """
        Execute one iteration of the autonomous optimization loop

        Returns:
            LoopIteration with results, or None if conditions not met
        """

        iteration = LoopIteration(
            status=LoopStatus.MONITORING,
            started_at=datetime.now().isoformat()
        )

        try:
            # Step 1: Check if loop should run
            if not self._should_run_iteration():
                return None

            # Step 2: Select next candidate to optimize
            candidate = self._select_next_candidate()
            if not candidate:
                return None

            iteration.candidate_id = candidate['id']
            iteration.candidate_name = candidate['name']
            iteration.predicted_improvement = candidate['predicted_improvement']

            # Step 3: Execute optimization
            iteration.status = LoopStatus.EXECUTING
            execution_result = self._execute_optimization(candidate)
            iteration.execution_success = execution_result.get('success', False)

            if not iteration.execution_success:
                iteration.status = LoopStatus.COMPLETE
                iteration.completed_at = datetime.now().isoformat()
                self._store_iteration(iteration)
                return iteration

            # Step 4: Validate results
            iteration.status = LoopStatus.VALIDATING
            validation_result = self._validate_results(candidate)
            iteration.validation_success = validation_result.get('success', False)
            iteration.actual_improvement = validation_result.get('actual_improvement', 0.0)

            # Step 5: Calculate improvement accuracy
            if iteration.predicted_improvement > 0:
                iteration.improvement_accuracy = (iteration.actual_improvement /
                                                 iteration.predicted_improvement * 100)

            # Step 6: Decide on rollback
            if not iteration.validation_success:
                iteration.status = LoopStatus.ROLLING_BACK
                rollback_result = self._trigger_rollback(candidate, validation_result)
                iteration.rollback_triggered = rollback_result.get('success', False)

            # Step 7: Learn from results
            iteration.status = LoopStatus.LEARNING
            self._feed_learning_back(candidate, iteration)

            # Step 8: Store iteration and update metrics
            iteration.status = LoopStatus.COMPLETE
            iteration.completed_at = datetime.now().isoformat()
            iteration.loop_duration_seconds = self._calculate_duration(
                iteration.started_at, iteration.completed_at
            )

            self._store_iteration(iteration)
            self._update_loop_metrics(iteration)

            return iteration

        except Exception:
            iteration.status = LoopStatus.ERROR
            iteration.completed_at = datetime.now().isoformat()
            self._store_iteration(iteration)
            return iteration

    def _should_run_iteration(self) -> bool:
        """Check if conditions are met to run next iteration"""
        try:
            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            # Check if loop is enabled
            c.execute('SELECT loop_enabled, emergency_stop FROM loop_control ORDER BY created_at DESC LIMIT 1')
            row = c.fetchone()
            conn.close()

            if row:
                if not row[0]:  # loop_enabled = 0
                    return False
                if row[1]:  # emergency_stop = 1
                    return False

            # Check throttling (min interval between iterations)
            c.execute('''
                SELECT last_iteration_at FROM loop_control
                ORDER BY created_at DESC LIMIT 1
            ''')
            row = c.fetchone()

            if row and row[0]:
                last_iter = datetime.fromisoformat(row[0])
                if (datetime.now() - last_iter).total_seconds() < self._min_iteration_interval_seconds:
                    return False

            # Check rollback rate
            metrics = self.get_loop_metrics()
            if metrics and metrics.total_iterations > 0:
                rollback_rate = metrics.rollbacks_triggered / metrics.total_iterations
                if rollback_rate > self._max_rollback_rate:
                    self._emergency_stop("Rollback rate exceeded threshold")
                    return False

            return True
        except Exception:
            return False

    def _select_next_candidate(self) -> Optional[Dict]:
        """Select next candidate to optimize based on highest potential"""
        # In production, this would query from BusinessOptimizer results
        # For now, return mock candidate
        return {
            'id': 1,
            'name': 'Optimize Connection Pool',
            'predicted_improvement': 5.5,
            'operation_type': 'read'
        }

    def _execute_optimization(self, candidate: Dict) -> Dict:
        """Execute optimization candidate"""
        try:
            # In production, would call OptimizationExecutor.execute_candidate()
            # For now, simulate successful execution
            return {
                'success': True,
                'execution_id': 1,
                'execution_time_seconds': 0.08
            }
        except Exception:
            return {'success': False}

    def _validate_results(self, candidate: Dict) -> Dict:
        """Validate optimization results against predictions"""
        try:
            # In production, would call ResultTracker.validate_execution_result()
            # For now, simulate successful validation
            return {
                'success': True,
                'actual_improvement': 5.3,
                'all_metrics_valid': True,
                'sla_compliant': True,
                'kpi_compliant': True
            }
        except Exception:
            return {'success': False}

    def _trigger_rollback(self, candidate: Dict, validation_result: Dict) -> Dict:
        """Trigger rollback if validation fails"""
        try:
            # In production, would call RollbackManager.execute_rollback()
            # For now, simulate rollback
            return {
                'success': True,
                'rollback_reason': validation_result.get('failure_reason', 'Unknown')
            }
        except Exception:
            return {'success': False}

    def _feed_learning_back(self, candidate: Dict, iteration: LoopIteration):
        """Feed learning back to Week 3 systems for improved predictions"""
        try:
            # In production, would update:
            # - BusinessMetrics with actual SLA/KPI achieved
            # - FeedbackCollector with success/failure signals
            # - Pattern confidence in learning system

            # Track that we successfully learned from this iteration
            pass
        except Exception:
            pass

    def _store_iteration(self, iteration: LoopIteration):
        """Store loop iteration in database"""
        try:
            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            c.execute('''
                INSERT INTO loop_iterations
                (candidate_id, candidate_name, status, execution_success,
                 validation_success, rollback_triggered, predicted_improvement,
                 actual_improvement, improvement_accuracy, started_at,
                 completed_at, loop_duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                iteration.candidate_id,
                iteration.candidate_name,
                iteration.status.value,
                1 if iteration.execution_success else 0,
                1 if iteration.validation_success else 0,
                1 if iteration.rollback_triggered else 0,
                iteration.predicted_improvement,
                iteration.actual_improvement,
                iteration.improvement_accuracy,
                iteration.started_at,
                iteration.completed_at,
                iteration.loop_duration_seconds
            ))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def _update_loop_metrics(self, iteration: LoopIteration):
        """Update aggregate loop metrics"""
        try:
            metrics = self.get_loop_metrics()

            metrics.total_iterations += 1
            if iteration.execution_success:
                metrics.successful_executions += 1
            else:
                metrics.failed_executions += 1

            if iteration.rollback_triggered:
                metrics.rollbacks_triggered += 1

            metrics.total_predicted_improvement += iteration.predicted_improvement
            metrics.total_actual_improvement += iteration.actual_improvement

            if metrics.total_iterations > 0:
                metrics.avg_improvement_accuracy = (
                    metrics.total_actual_improvement / metrics.total_predicted_improvement * 100
                    if metrics.total_predicted_improvement > 0 else 0.0
                )
                metrics.learning_efficiency = (
                    metrics.total_actual_improvement / metrics.total_predicted_improvement
                    if metrics.total_predicted_improvement > 0 else 0.0
                )

            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            c.execute('''
                INSERT INTO loop_metrics
                (timestamp, total_iterations, successful_executions,
                 failed_executions, rollbacks_triggered, avg_improvement_accuracy,
                 learning_efficiency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                metrics.total_iterations,
                metrics.successful_executions,
                metrics.failed_executions,
                metrics.rollbacks_triggered,
                metrics.avg_improvement_accuracy,
                metrics.learning_efficiency
            ))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def _calculate_duration(self, start: str, end: str) -> float:
        """Calculate duration between timestamps"""
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            return (end_dt - start_dt).total_seconds()
        except Exception:
            return 0.0

    def _emergency_stop(self, reason: str):
        """Trigger emergency stop of autonomous loop"""
        try:
            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            c.execute('''
                UPDATE loop_control
                SET emergency_stop = 1, stop_reason = ?
                WHERE id = (SELECT MAX(id) FROM loop_control)
            ''', (reason,))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def enable_autonomous_loop(self):
        """Enable autonomous optimization loop"""
        try:
            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            c.execute('''
                INSERT INTO loop_control
                (loop_enabled, emergency_stop, stop_reason)
                VALUES (1, 0, NULL)
            ''')

            conn.commit()
            conn.close()
        except Exception:
            pass

    def disable_autonomous_loop(self):
        """Disable autonomous optimization loop"""
        try:
            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            c.execute('''
                UPDATE loop_control
                SET loop_enabled = 0
                WHERE id = (SELECT MAX(id) FROM loop_control)
            ''')

            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_loop_metrics(self) -> LoopMetrics:
        """Get current loop metrics"""
        try:
            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            c.execute('''
                SELECT
                    COUNT(*) as total_iterations,
                    SUM(CASE WHEN execution_success = 1 THEN 1 ELSE 0 END) as successful_executions,
                    SUM(CASE WHEN execution_success = 0 THEN 1 ELSE 0 END) as failed_executions,
                    SUM(CASE WHEN rollback_triggered = 1 THEN 1 ELSE 0 END) as rollbacks_triggered,
                    SUM(predicted_improvement) as total_predicted,
                    SUM(actual_improvement) as total_actual,
                    AVG(improvement_accuracy) as avg_accuracy,
                    AVG(loop_duration_seconds) as avg_duration
                FROM loop_iterations
            ''')

            row = c.fetchone()
            conn.close()

            if row:
                metrics = LoopMetrics(
                    total_iterations=int(row[0] or 0),
                    successful_executions=int(row[1] or 0),
                    failed_executions=int(row[2] or 0),
                    rollbacks_triggered=int(row[3] or 0),
                    total_predicted_improvement=float(row[4] or 0),
                    total_actual_improvement=float(row[5] or 0),
                    avg_improvement_accuracy=float(row[6] or 0),
                    avg_loop_duration_seconds=float(row[7] or 0)
                )
                if metrics.total_predicted_improvement > 0:
                    metrics.learning_efficiency = (
                        metrics.total_actual_improvement / metrics.total_predicted_improvement
                    )
                return metrics

            return LoopMetrics()
        except Exception:
            return LoopMetrics()

    def get_iteration_history(self, limit: int = 20) -> List[LoopIteration]:
        """Get recent iteration history"""
        try:
            conn = sqlite3.connect(self.loop_db)
            c = conn.cursor()

            c.execute('''
                SELECT
                    candidate_id, candidate_name, status, execution_success,
                    validation_success, rollback_triggered, predicted_improvement,
                    actual_improvement, improvement_accuracy, started_at,
                    completed_at, loop_duration_seconds
                FROM loop_iterations
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

            rows = c.fetchall()
            conn.close()

            iterations = []
            for row in rows:
                iteration = LoopIteration(
                    candidate_id=row[0],
                    candidate_name=row[1],
                    status=LoopStatus(row[2]),
                    execution_success=bool(row[3]),
                    validation_success=bool(row[4]),
                    rollback_triggered=bool(row[5]),
                    predicted_improvement=float(row[6]),
                    actual_improvement=float(row[7]),
                    improvement_accuracy=float(row[8]),
                    started_at=row[9],
                    completed_at=row[10],
                    loop_duration_seconds=float(row[11])
                )
                iterations.append(iteration)

            return iterations
        except Exception:
            return []


if __name__ == '__main__':
    loop = AutonomousOptimizationLoop()

    # Enable and run autonomous loop
    loop.enable_autonomous_loop()

    # Run one iteration
    iteration = loop.run_autonomous_loop_iteration()

    if iteration:
        print("Autonomous Loop Iteration Complete:")
        print(f"  Candidate: {iteration.candidate_name}")
        print(f"  Status: {iteration.status.value}")
        print(f"  Execution Success: {iteration.execution_success}")
        print(f"  Validation Success: {iteration.validation_success}")
        print(f"  Predicted Improvement: {iteration.predicted_improvement:.1f}%")
        print(f"  Actual Improvement: {iteration.actual_improvement:.1f}%")
        print(f"  Accuracy: {iteration.improvement_accuracy:.1f}%")
        print(f"  Duration: {iteration.loop_duration_seconds:.3f}s")

    # Get metrics
    metrics = loop.get_loop_metrics()
    print("\nAutonomous Loop Metrics:")
    print(f"  Total Iterations: {metrics.total_iterations}")
    print(f"  Successful: {metrics.successful_executions}")
    print(f"  Rollbacks: {metrics.rollbacks_triggered}")
    print(f"  Avg Accuracy: {metrics.avg_improvement_accuracy:.1f}%")
    print(f"  Learning Efficiency: {metrics.learning_efficiency:.2f}x")
