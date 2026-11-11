# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
import json
import sqlite3
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

# Phase H: Metrics collection
try:
    from .phase_h_integration import get_metrics
    _METRICS = get_metrics()
except Exception:
    _METRICS = None  # Graceful degradation if metrics unavailable

class JobStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW_REQUESTED = "review_requested"
    COMPLETED = "completed"
    FAILED = "failed"

class Orchestrator:
    """Hybrid Hive-Crystal Orchestrator: Blackboard + Job Queue."""
    def __init__(self, db_path: str = "C:/Users/vizio/CAMELOT_OS/03_VAULT/runtime_state/orchestrator.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS blackboard (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                assigned_to TEXT,
                status TEXT NOT NULL,
                acceptance_tests TEXT DEFAULT '[]',
                result TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
        """)
        self._conn.commit()

    def set_fact(self, key: str, value: Any):
        now = time.time()
        val_str = json.dumps(value) if not isinstance(value, str) else value

        # Phase H: Track write operation
        start = time.perf_counter()
        try:
            self._conn.execute(
                "INSERT INTO blackboard (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?",
                (key, val_str, now, val_str, now)
            )
            self._conn.commit()

            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('write', duration_ms, success=True, tags={'table': 'blackboard'})
        except Exception as e:
            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('write', duration_ms, success=False, error_message=str(e), tags={'table': 'blackboard'})
            raise

    def create_job(self, task: str, acceptance_tests: List[str] = None) -> int:
        now = time.time()
        tests_str = json.dumps(acceptance_tests or [])

        # Phase H: Track write operation
        start = time.perf_counter()
        try:
            cur = self._conn.execute(
                "INSERT INTO jobs (task, status, acceptance_tests, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (task, JobStatus.PENDING.value, tests_str, now, now)
            )
            self._conn.commit()

            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('write', duration_ms, success=True, tags={'table': 'jobs'})

            return cur.lastrowid
        except Exception as e:
            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('write', duration_ms, success=False, error_message=str(e), tags={'table': 'jobs'})
            raise

    def list_jobs(self) -> List[Dict[str, Any]]:
        # Phase H: Track read operation
        start = time.perf_counter()
        try:
            rows = self._conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()

            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('read', duration_ms, success=True, tags={'table': 'jobs', 'operation': 'list'})

            return [dict(r) for r in rows]
        except Exception as e:
            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('read', duration_ms, success=False, error_message=str(e), tags={'table': 'jobs'})
            raise
