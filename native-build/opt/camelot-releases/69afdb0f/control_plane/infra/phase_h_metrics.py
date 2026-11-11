#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H: Metrics Collection Engine
Captures latency, throughput, errors from all operations
Stores in SQLite event log (append-only)
"""

import random
import sqlite3
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class OperationRecord:
    """Single operation metric"""
    timestamp: float
    operation_type: str
    duration_ms: float
    success: bool
    error_message: Optional[str] = None
    tags: Dict[str, str] = None


class MetricsCollector:
    """Collect and aggregate operation metrics"""

    def __init__(self, db_path: str = "control_plane/metrics.db", sample_rate: float = 0.1):
        """
        Args:
            db_path: Path to SQLite database for event log
            sample_rate: Fraction of operations to capture (0.1 = 10%)
        """
        self.db_path = Path(db_path)
        self.sample_rate = sample_rate
        self._init_db()

    def _init_db(self):
        """Create SQLite schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main event log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                operation_type TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                success INTEGER NOT NULL,
                error_message TEXT,
                tags TEXT
            )
        ''')

        # Create index for fast queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp_operation
            ON metrics_log (timestamp, operation_type)
        ''')

        conn.commit()
        conn.close()

    def record_operation(
        self,
        operation_type: str,
        duration_ms: float,
        success: bool,
        error_message: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Record a single operation.

        Args:
            operation_type: 'read', 'write', 'route', 'compress', etc
            duration_ms: Operation latency in milliseconds
            success: Whether operation succeeded
            error_message: Error description if failed
            tags: Optional metadata {'agent_id': 'a1', 'workload': 'heavy'}

        Returns:
            True if recorded, False if sampled out
        """
        # Sampling: skip this operation?
        if random.random() > self.sample_rate:
            return False

        timestamp = time.time()
        tags_str = str(tags) if tags else None

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO metrics_log
                (timestamp, operation_type, duration_ms, success, error_message, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, operation_type, duration_ms, 1 if success else 0, error_message, tags_str))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[WARN] Failed to record metric: {e}")
            return False

    def get_statistics(
        self,
        operation_type: Optional[str] = None,
        time_window_sec: int = 3600
    ) -> Dict[str, any]:
        """
        Get aggregated statistics for last N seconds.

        Args:
            operation_type: Filter to specific operation (None = all)
            time_window_sec: Look back window in seconds

        Returns:
            {
                'p50': 1.2, 'p95': 5.3, 'p99': 12.1,
                'count': 45230, 'error_count': 2, 'error_rate': 0.004,
                'min_ms': 0.001, 'max_ms': 45.2, 'avg_ms': 1.5
            }
        """
        cutoff_time = time.time() - time_window_sec

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build query
            query = 'SELECT duration_ms, success FROM metrics_log WHERE timestamp > ?'
            params = [cutoff_time]

            if operation_type:
                query += ' AND operation_type = ?'
                params.append(operation_type)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {
                    'p50': 0, 'p95': 0, 'p99': 0,
                    'count': 0, 'error_count': 0, 'error_rate': 0,
                    'min_ms': 0, 'max_ms': 0, 'avg_ms': 0,
                    'status': 'no data'
                }

            durations = [r[0] for r in rows]
            success_flags = [r[1] for r in rows]

            error_count = sum(1 for s in success_flags if not s)
            success_count = len(durations) - error_count

            # Calculate percentiles
            sorted_durations = sorted(durations)
            p50_idx = int(len(durations) * 0.5)
            p95_idx = int(len(durations) * 0.95)
            p99_idx = int(len(durations) * 0.99)

            result = {
                'p50': sorted_durations[p50_idx] if p50_idx < len(sorted_durations) else 0,
                'p95': sorted_durations[p95_idx] if p95_idx < len(sorted_durations) else 0,
                'p99': sorted_durations[p99_idx] if p99_idx < len(sorted_durations) else 0,
                'count': len(durations),
                'success_count': success_count,
                'error_count': error_count,
                'error_rate': error_count / len(durations) if durations else 0,
                'min_ms': min(durations) if durations else 0,
                'max_ms': max(durations) if durations else 0,
                'avg_ms': statistics.mean(durations) if durations else 0,
                'status': 'ok'
            }
            return result

        except Exception as e:
            print(f"[WARN] Failed to get statistics: {e}")
            return {'status': 'error', 'error': str(e)}

    def get_all_operation_stats(self, time_window_sec: int = 3600) -> Dict[str, Dict]:
        """
        Get statistics for all operation types.

        Returns:
            {
                'read': {'p50': 1.2, 'p95': 5.3, ...},
                'write': {'p50': 2.1, 'p95': 8.9, ...},
                ...
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get unique operation types
            cursor.execute('SELECT DISTINCT operation_type FROM metrics_log')
            op_types = [row[0] for row in cursor.fetchall()]
            conn.close()

            result = {}
            for op_type in op_types:
                result[op_type] = self.get_statistics(operation_type=op_type, time_window_sec=time_window_sec)

            return result
        except Exception as e:
            print(f"[WARN] Failed to get all stats: {e}")
            return {}

    def cleanup_old_records(self, days_to_keep: int = 7):
        """Remove events older than specified days (data retention policy)"""
        cutoff_time = time.time() - (days_to_keep * 86400)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM metrics_log WHERE timestamp < ?', (cutoff_time,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            print(f"[CLEANUP] Deleted {deleted} old metric records")
            return deleted
        except Exception as e:
            print(f"[WARN] Cleanup failed: {e}")
            return 0

    def get_event_count(self) -> int:
        """Get total events in log"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM metrics_log')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def export_csv(self, filepath: str, time_window_sec: int = 3600):
        """Export metrics to CSV for analysis"""
        import csv

        cutoff_time = time.time() - time_window_sec

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT timestamp, operation_type, duration_ms, success, error_message FROM metrics_log WHERE timestamp > ? ORDER BY timestamp',
                (cutoff_time,)
            )
            rows = cursor.fetchall()
            conn.close()

            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'operation_type', 'duration_ms', 'success', 'error_message'])
                for row in rows:
                    writer.writerow(row)

            print(f"[EXPORT] Saved {len(rows)} records to {filepath}")
            return len(rows)

        except Exception as e:
            print(f"[WARN] Export failed: {e}")
            return 0
