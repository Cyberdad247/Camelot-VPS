#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 1: Optimization Executor
Apply approved optimization candidates safely with execution tracking
"""

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List


@dataclass
class SystemStateSnapshot:
    """Snapshot of system state at a point in time"""
    timestamp: str
    latency_p95_ms: float
    latency_p99_ms: float
    throughput_ops_sec: float
    error_rate_pct: float
    availability_pct: float
    cache_size_gb: float
    memory_used_gb: float
    connections_active: int
    cost_per_op: float
    notes: str = None


@dataclass
class ExecutionResult:
    """Result of applying an optimization candidate"""
    execution_id: int = None
    candidate_id: int = None
    candidate_name: str = None
    status: str = None  # 'success', 'partial', 'failed'
    state_before: SystemStateSnapshot = None
    state_after: SystemStateSnapshot = None
    execution_time_seconds: float = None
    error_message: str = None
    rollback_available: bool = False
    created_at: str = None


class OptimizationExecutor:
    """Execute approved optimization candidates on live system"""

    def __init__(self, executor_db: str = "control_plane/executor.db"):
        """Initialize optimization executor"""
        self.executor_db = executor_db
        self._ensure_db()
        self._execution_lock = False

    def _ensure_db(self):
        """Create executor database"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        # Execution history
        c.execute('''
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                candidate_name TEXT,
                status TEXT,
                state_before TEXT,
                state_after TEXT,
                execution_time_seconds REAL,
                error_message TEXT,
                rollback_available INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Execution locks (prevent concurrent changes)
        c.execute('''
            CREATE TABLE IF NOT EXISTS execution_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                locked_at TIMESTAMP,
                locked_by TEXT,
                reason TEXT,
                expires_at TIMESTAMP
            )
        ''')

        # Rollback points (system state snapshots for rollback)
        c.execute('''
            CREATE TABLE IF NOT EXISTS rollback_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER,
                system_state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def acquire_execution_lock(self, reason: str = "optimization_execution") -> bool:
        """Try to acquire exclusive execution lock"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        # Check if lock already exists
        c.execute('''
            SELECT id FROM execution_locks
            WHERE expires_at > datetime('now')
        ''')

        if c.fetchone():
            conn.close()
            return False  # Lock held by another process

        # Acquire lock (30 second timeout)
        c.execute('''
            INSERT INTO execution_locks (locked_by, reason, expires_at)
            VALUES (?, ?, datetime('now', '+30 seconds'))
        ''', ('executor', reason))

        conn.commit()
        conn.close()
        return True

    def release_execution_lock(self):
        """Release execution lock"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        c.execute('DELETE FROM execution_locks WHERE locked_by = ?', ('executor',))

        conn.commit()
        conn.close()

    def execute_candidate(self, candidate_id: int, candidate_name: str,
                         state_before: SystemStateSnapshot) -> ExecutionResult:
        """
        Execute an optimization candidate

        Args:
            candidate_id: ID of candidate to execute
            candidate_name: Name of candidate
            state_before: System state snapshot before execution

        Returns:
            ExecutionResult with success/failure details
        """

        # Acquire lock
        if not self.acquire_execution_lock(f"executing_{candidate_name}"):
            return ExecutionResult(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                status='failed',
                error_message='Could not acquire execution lock (another optimization in progress)',
                created_at=datetime.now().isoformat()
            )

        start_time = time.time()
        result = None

        try:
            # Step 1: Capture pre-execution state
            result = ExecutionResult(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                state_before=state_before,
                created_at=datetime.now().isoformat()
            )

            # Step 2: Apply optimization (simulated - in real system this would execute changes)
            # For testing, we simulate the execution
            result.status = 'success'
            result.state_after = self._simulate_optimization_impact(
                state_before, candidate_name
            )

            # Step 3: Record execution time
            result.execution_time_seconds = time.time() - start_time

            # Step 4: Store execution result (and get ID back)
            execution_id = self._store_execution(result)
            result.execution_id = execution_id

            # Step 5: Store rollback point (after execution stored)
            self._store_rollback_point(execution_id, state_before)
            result.rollback_available = True

            return result

        except Exception as e:
            if result is None:
                result = ExecutionResult(
                    candidate_id=candidate_id,
                    candidate_name=candidate_name,
                    created_at=datetime.now().isoformat()
                )
            result.status = 'failed'
            result.error_message = str(e)
            result.execution_time_seconds = time.time() - start_time
            result.rollback_available = False

            self._store_execution(result)
            return result

        finally:
            self.release_execution_lock()

    def _simulate_optimization_impact(self, state_before: SystemStateSnapshot,
                                     candidate_name: str) -> SystemStateSnapshot:
        """
        Simulate the impact of an optimization candidate

        In production, this would execute actual system changes and measure results.
        """

        # Map candidate name to expected impact
        impact_map = {
            'Reduce Cache': {
                'latency_p95_ms': 2.1,    # +5% latency
                'latency_p99_ms': 3.1,
                'throughput_ops_sec': 950,  # -5% throughput
                'cost_per_op': 0.000095,  # -5% cost
            },
            'Optimize Connection Pool': {
                'latency_p95_ms': 1.9,    # -5% latency
                'latency_p99_ms': 2.9,
                'throughput_ops_sec': 1050,  # +5% throughput
                'cost_per_op': 0.0001,    # neutral cost
            },
            'Add Indexes': {
                'latency_p95_ms': 1.6,    # -20% latency
                'latency_p99_ms': 2.4,
                'throughput_ops_sec': 1100,  # +10% throughput
                'cost_per_op': 0.000105,  # +5% cost
            },
        }

        # Default (no impact if candidate not found)
        impacts = impact_map.get(candidate_name, {
            'latency_p95_ms': state_before.latency_p95_ms,
            'latency_p99_ms': state_before.latency_p99_ms,
            'throughput_ops_sec': state_before.throughput_ops_sec,
            'cost_per_op': state_before.cost_per_op,
        })

        state_after = SystemStateSnapshot(
            timestamp=datetime.now().isoformat(),
            latency_p95_ms=impacts.get('latency_p95_ms', state_before.latency_p95_ms),
            latency_p99_ms=impacts.get('latency_p99_ms', state_before.latency_p99_ms),
            throughput_ops_sec=impacts.get('throughput_ops_sec', state_before.throughput_ops_sec),
            error_rate_pct=state_before.error_rate_pct,  # Typically unchanged
            availability_pct=state_before.availability_pct,  # Typically unchanged
            cache_size_gb=state_before.cache_size_gb - 0.3 if 'Reduce Cache' in candidate_name else state_before.cache_size_gb,
            memory_used_gb=state_before.memory_used_gb,
            connections_active=state_before.connections_active,
            notes=f"After {candidate_name} execution"
        )

        return state_after

    def _store_rollback_point(self, execution_id: int, state: SystemStateSnapshot):
        """Store system state for potential rollback"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        c.execute('''
            INSERT INTO rollback_points (execution_id, system_state)
            VALUES (?, ?)
        ''', (execution_id, json.dumps(asdict(state))))

        conn.commit()
        conn.close()

    def _store_execution(self, result: ExecutionResult) -> int:
        """Store execution result in database and return execution ID"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        c.execute('''
            INSERT INTO executions
            (candidate_id, candidate_name, status, state_before, state_after,
             execution_time_seconds, error_message, rollback_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.candidate_id,
            result.candidate_name,
            result.status,
            json.dumps(asdict(result.state_before)) if result.state_before else None,
            json.dumps(asdict(result.state_after)) if result.state_after else None,
            result.execution_time_seconds,
            result.error_message,
            1 if result.rollback_available else 0
        ))

        execution_id = c.lastrowid
        conn.commit()
        conn.close()

        return execution_id

    def get_execution_history(self, limit: int = 10) -> List[ExecutionResult]:
        """Get recent execution history"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        c.execute('''
            SELECT candidate_id, candidate_name, status, state_before, state_after,
                   execution_time_seconds, error_message, rollback_available, created_at
            FROM executions
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))

        rows = c.fetchall()
        conn.close()

        results = []
        for row in rows:
            state_before = json.loads(row[3]) if row[3] else None
            state_after = json.loads(row[4]) if row[4] else None

            if state_before:
                state_before = SystemStateSnapshot(**state_before)
            if state_after:
                state_after = SystemStateSnapshot(**state_after)

            result = ExecutionResult(
                candidate_id=row[0],
                candidate_name=row[1],
                status=row[2],
                state_before=state_before,
                state_after=state_after,
                execution_time_seconds=row[5],
                error_message=row[6],
                rollback_available=bool(row[7]),
                created_at=row[8]
            )
            results.append(result)

        return results

    def get_execution_statistics(self) -> Dict:
        """Get statistics on executions"""
        conn = sqlite3.connect(self.executor_db)
        c = conn.cursor()

        stats = {
            'total_executions': 0,
            'successful': 0,
            'partial': 0,
            'failed': 0,
            'avg_execution_time_seconds': 0.0,
            'avg_latency_improvement_pct': 0.0,
            'avg_cost_change_pct': 0.0,
        }

        # Total and by status
        c.execute('SELECT COUNT(*) FROM executions')
        stats['total_executions'] = c.fetchone()[0]

        c.execute('SELECT status, COUNT(*) FROM executions GROUP BY status')
        for status, count in c.fetchall():
            if status == 'success':
                stats['successful'] = count
            elif status == 'partial':
                stats['partial'] = count
            elif status == 'failed':
                stats['failed'] = count

        # Average execution time
        c.execute('SELECT AVG(execution_time_seconds) FROM executions WHERE status = ?', ('success',))
        avg_time = c.fetchone()[0]
        if avg_time:
            stats['avg_execution_time_seconds'] = round(avg_time, 2)

        conn.close()

        return stats


if __name__ == '__main__':
    executor = OptimizationExecutor()

    # Example: Create and execute a candidate
    state_before = SystemStateSnapshot(
        timestamp=datetime.now().isoformat(),
        latency_p95_ms=2.0,
        latency_p99_ms=3.0,
        throughput_ops_sec=1000,
        error_rate_pct=0.1,
        availability_pct=99.9,
        cache_size_gb=3.0,
        memory_used_gb=8.0,
        connections_active=50,
        cost_per_op=0.0001
    )

    result = executor.execute_candidate(1, 'Reduce Cache', state_before)

    print("Execution Result:")
    print(f"  Candidate: {result.candidate_name}")
    print(f"  Status: {result.status}")
    print(f"  Time: {result.execution_time_seconds:.3f}s")
    print(f"  Rollback Available: {result.rollback_available}")

    if result.state_before and result.state_after:
        latency_change = ((result.state_after.latency_p95_ms - result.state_before.latency_p95_ms) /
                         result.state_before.latency_p95_ms * 100)
        cost_change = ((result.state_after.cost_per_op - result.state_before.cost_per_op) /
                      result.state_before.cost_per_op * 100)
        print(f"  Latency Change: {latency_change:+.1f}%")
        print(f"  Cost Change: {cost_change:+.1f}%")

    # Get statistics
    stats = executor.get_execution_statistics()
    print("\nExecution Statistics:")
    print(f"  Total: {stats['total_executions']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Avg Time: {stats['avg_execution_time_seconds']:.3f}s")
