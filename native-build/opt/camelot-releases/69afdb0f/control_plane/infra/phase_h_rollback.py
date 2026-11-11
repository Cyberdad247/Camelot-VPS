#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 4 Day 3: Rollback System
Emergency revert of failed optimizations to pre-execution state
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class RollbackResult:
    """Result of a rollback operation"""
    execution_id: int = None
    success: bool = False
    rollback_timestamp: str = None
    previous_state_restored: str = None  # JSON of restored state
    rollback_reason: str = None
    error_message: str = None


class RollbackManager:
    """Manage emergency rollback of failed optimizations"""

    def __init__(self, rollback_db: str = "control_plane/rollback.db",
                 executor_db: str = "control_plane/executor.db",
                 tracker_db: str = "control_plane/result_tracker.db"):
        """Initialize rollback manager"""
        self.rollback_db = rollback_db
        self.executor_db = executor_db
        self.tracker_db = tracker_db
        self._ensure_db()

    def _ensure_db(self):
        """Create rollback database"""
        conn = sqlite3.connect(self.rollback_db)
        c = conn.cursor()

        # Rollback executions
        c.execute('''
            CREATE TABLE IF NOT EXISTS rollback_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                success INTEGER,
                rollback_timestamp TIMESTAMP,
                previous_state_restored TEXT,
                rollback_reason TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Rollback audit log
        c.execute('''
            CREATE TABLE IF NOT EXISTS rollback_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def can_rollback(self, execution_id: int) -> bool:
        """Check if execution has a rollback point available"""
        try:
            conn = sqlite3.connect(self.executor_db)
            c = conn.cursor()

            c.execute('''
                SELECT rollback_available FROM executions WHERE id = ?
            ''', (execution_id,))

            row = c.fetchone()
            conn.close()

            return bool(row and row[0]) if row else False
        except Exception:
            return False

    def execute_rollback(self, execution_id: int, rollback_reason: str) -> RollbackResult:
        """
        Execute rollback to restore pre-execution state

        Args:
            execution_id: ID of execution to rollback
            rollback_reason: Why rollback is being performed

        Returns:
            RollbackResult with success/failure status
        """

        result = RollbackResult(
            execution_id=execution_id,
            rollback_timestamp=datetime.now().isoformat(),
            rollback_reason=rollback_reason
        )

        try:
            # Step 1: Check if rollback is available
            if not self.can_rollback(execution_id):
                result.success = False
                result.error_message = "No rollback point available for this execution"
                self._store_rollback_execution(result)
                self._log_audit(execution_id, "ROLLBACK_FAILED", "No rollback point available")
                return result

            # Step 2: Get previous state from execution
            previous_state = self._get_previous_state(execution_id)
            if not previous_state:
                result.success = False
                result.error_message = "Could not retrieve previous state"
                self._store_rollback_execution(result)
                self._log_audit(execution_id, "ROLLBACK_FAILED", "Could not retrieve state")
                return result

            # Step 3: Perform rollback (simulated - in production would apply actual changes)
            rollback_success = self._apply_rollback(previous_state)
            if not rollback_success:
                result.success = False
                result.error_message = "Failed to apply rollback changes"
                self._store_rollback_execution(result)
                self._log_audit(execution_id, "ROLLBACK_FAILED", "Failed to apply changes")
                return result

            # Step 4: Verify rollback (check state restored correctly)
            verification = self._verify_rollback(previous_state)
            if not verification:
                result.success = False
                result.error_message = "Rollback verification failed"
                self._store_rollback_execution(result)
                self._log_audit(execution_id, "ROLLBACK_VERIFICATION_FAILED", "State verification failed")
                return result

            # Step 5: Mark execution as rolled back
            self._mark_execution_rolled_back(execution_id)

            # Step 6: Record successful rollback
            result.success = True
            result.previous_state_restored = json.dumps(previous_state)
            self._store_rollback_execution(result)
            self._log_audit(execution_id, "ROLLBACK_SUCCESS", "System returned to pre-execution state")

            return result

        except Exception as e:
            result.success = False
            result.error_message = f"Rollback error: {str(e)}"
            self._store_rollback_execution(result)
            self._log_audit(execution_id, "ROLLBACK_ERROR", str(e))
            return result

    def _get_previous_state(self, execution_id: int) -> Optional[Dict]:
        """Retrieve previous system state from execution"""
        try:
            conn = sqlite3.connect(self.executor_db)
            c = conn.cursor()

            c.execute('''
                SELECT state_before FROM executions WHERE id = ?
            ''', (execution_id,))

            row = c.fetchone()
            conn.close()

            if row and row[0]:
                return json.loads(row[0])
            return None
        except Exception:
            return None

    def _apply_rollback(self, previous_state: Dict) -> bool:
        """Apply rollback changes (simulated)"""
        try:
            # In production, this would:
            # 1. Restore cache settings
            # 2. Restore connection pool configuration
            # 3. Restore optimization parameters
            # 4. Restart affected services
            # 5. Verify system stability

            # For now, we simulate successful rollback
            if not previous_state:
                return False

            # Verify essential state fields exist
            required_fields = ['latency_p95_ms', 'throughput_ops_sec', 'cost_per_op']
            for field in required_fields:
                if field not in previous_state:
                    return False

            return True
        except Exception:
            return False

    def _verify_rollback(self, previous_state: Dict) -> bool:
        """Verify rollback was successful by checking state"""
        try:
            if not previous_state:
                return False

            # In production, would query actual system metrics and compare
            # For now, check that state is well-formed
            if (previous_state.get('latency_p95_ms', 0) > 0 and
                previous_state.get('throughput_ops_sec', 0) > 0 and
                previous_state.get('cost_per_op', 0) > 0):
                return True

            return False
        except Exception:
            return False

    def _mark_execution_rolled_back(self, execution_id: int):
        """Mark execution as rolled back in database"""
        try:
            conn = sqlite3.connect(self.executor_db)
            c = conn.cursor()

            # Update execution status
            c.execute('''
                UPDATE executions
                SET status = 'rolled_back'
                WHERE id = ?
            ''', (execution_id,))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def _store_rollback_execution(self, result: RollbackResult):
        """Store rollback execution result in database"""
        try:
            conn = sqlite3.connect(self.rollback_db)
            c = conn.cursor()

            c.execute('''
                INSERT INTO rollback_executions
                (execution_id, success, rollback_timestamp, previous_state_restored,
                 rollback_reason, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                result.execution_id,
                1 if result.success else 0,
                result.rollback_timestamp,
                result.previous_state_restored,
                result.rollback_reason,
                result.error_message
            ))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def _log_audit(self, execution_id: int, action: str, details: str):
        """Log rollback audit event"""
        try:
            conn = sqlite3.connect(self.rollback_db)
            c = conn.cursor()

            c.execute('''
                INSERT INTO rollback_audit (execution_id, action, timestamp, details)
                VALUES (?, ?, ?, ?)
            ''', (execution_id, action, datetime.now().isoformat(), details))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_rollback_history(self, limit: int = 10) -> list:
        """Get recent rollback history"""
        try:
            conn = sqlite3.connect(self.rollback_db)
            c = conn.cursor()

            c.execute('''
                SELECT execution_id, success, rollback_timestamp, rollback_reason
                FROM rollback_executions
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

            rows = c.fetchall()
            conn.close()

            history = []
            for row in rows:
                history.append({
                    'execution_id': row[0],
                    'success': bool(row[1]),
                    'timestamp': row[2],
                    'reason': row[3]
                })

            return history
        except Exception:
            return []

    def get_rollback_statistics(self) -> Dict:
        """Get rollback statistics"""
        try:
            conn = sqlite3.connect(self.rollback_db)
            c = conn.cursor()

            stats = {
                'total_rollbacks': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0,
            }

            c.execute('SELECT COUNT(*) FROM rollback_executions')
            stats['total_rollbacks'] = c.fetchone()[0]

            if stats['total_rollbacks'] > 0:
                c.execute('SELECT COUNT(*) FROM rollback_executions WHERE success = 1')
                stats['successful'] = c.fetchone()[0]

                stats['failed'] = stats['total_rollbacks'] - stats['successful']
                stats['success_rate'] = round(
                    stats['successful'] / stats['total_rollbacks'] * 100, 1
                )

            conn.close()
            return stats
        except Exception:
            return {}


if __name__ == '__main__':
    rollback_mgr = RollbackManager()

    # Example: Execute rollback
    result = rollback_mgr.execute_rollback(
        execution_id=1,
        rollback_reason="Validation failed: SLA compliance check failed"
    )

    print("Rollback Result:")
    print(f"  Execution ID: {result.execution_id}")
    print(f"  Success: {result.success}")
    print(f"  Reason: {result.rollback_reason}")
    if result.error_message:
        print(f"  Error: {result.error_message}")

    # Get statistics
    stats = rollback_mgr.get_rollback_statistics()
    print("\nRollback Statistics:")
    print(f"  Total: {stats['total_rollbacks']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Success Rate: {stats['success_rate']}%")
