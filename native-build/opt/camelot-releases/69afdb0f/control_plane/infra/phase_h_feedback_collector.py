#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 1: Feedback Signal Collection Infrastructure
Collect and store user, business, and operational feedback signals
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class FeedbackSignal:
    """Feedback signal with metadata"""
    id: int = None
    signal_type: str = None  # user_satisfaction, business_metric, constraint, etc.
    source: str = None  # "user", "monitoring", "team", "system"
    value: float = None  # 0.0-1.0 for satisfaction, numeric for metrics
    confidence: float = None  # 0.0-1.0 confidence in this signal
    description: str = None  # Human-readable description
    metadata: str = None  # JSON metadata (operation_type, constraint_name, etc.)
    recorded_at: str = None


class FeedbackValidator:
    """Validate feedback signals for quality and correctness"""

    # Valid signal types
    SIGNAL_TYPES = {
        'user_satisfaction': 0.9,  # User explicitly rates experience
        'latency_perception': 0.8,  # User-reported latency feeling
        'business_metric': 0.95,  # KPI/SLA tracking
        'operational_constraint': 0.9,  # Hard constraint from ops
        'success_report': 0.85,  # "We tried it, worked!"
        'failure_report': 0.85,  # "We tried it, failed!"
        'cost_feedback': 0.8,  # Cost-related feedback
        'availability_feedback': 0.9,  # Uptime/reliability feedback
    }

    # Valid sources
    VALID_SOURCES = {'user', 'monitoring', 'team', 'system', 'manual', 'automated'}

    @staticmethod
    def validate(signal_type: str, source: str, value: float,
                 confidence: float) -> tuple[bool, str]:
        """Validate signal for quality and correctness"""

        # Check signal type
        if signal_type not in FeedbackValidator.SIGNAL_TYPES:
            return False, f"Invalid signal type: {signal_type}"

        # Check source
        if source not in FeedbackValidator.VALID_SOURCES:
            return False, f"Invalid source: {source}"

        # Check value range
        if not isinstance(value, (int, float)):
            return False, f"Value must be numeric, got {type(value)}"

        # For satisfaction-like signals, clamp to 0-1
        if signal_type in ['user_satisfaction', 'latency_perception', 'cost_feedback']:
            if not (0.0 <= value <= 1.0):
                return False, f"Value must be 0.0-1.0 for {signal_type}, got {value}"

        # Check confidence
        if not (0.0 <= confidence <= 1.0):
            return False, f"Confidence must be 0.0-1.0, got {confidence}"

        return True, "valid"


class FeedbackCollector:
    """Collect and store feedback signals in SQLite"""

    def __init__(self, feedback_db_path: str = "control_plane/feedback.db"):
        """Initialize feedback collector"""
        self.feedback_db = feedback_db_path
        self._ensure_db()

    def _ensure_db(self):
        """Create feedback database and tables"""
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        # Signals table
        c.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_type TEXT NOT NULL,
                source TEXT NOT NULL,
                value REAL NOT NULL,
                confidence REAL NOT NULL,
                description TEXT,
                metadata TEXT,
                recorded_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Signal index for fast queries
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_signals_type_time
            ON signals(signal_type, recorded_at DESC)
        ''')

        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_signals_source
            ON signals(source)
        ''')

        # Deduplication tracking (prevent duplicate signals in time window)
        c.execute('''
            CREATE TABLE IF NOT EXISTS signal_dedup (
                id INTEGER PRIMARY KEY,
                signal_type TEXT NOT NULL,
                source TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                last_seen TIMESTAMP NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

    def collect_signal(self, signal_type: str, source: str, value: float,
                      confidence: float, description: str = None,
                      metadata: Dict = None) -> Optional[FeedbackSignal]:
        """
        Collect a feedback signal

        Args:
            signal_type: Type of signal (see FeedbackValidator.SIGNAL_TYPES)
            source: Source of signal (user, monitoring, team, system)
            value: Numeric value (0-1 for satisfaction, any for metrics)
            confidence: Confidence in this signal (0-1)
            description: Human-readable description
            metadata: Additional metadata (JSON)

        Returns:
            FeedbackSignal if successful, None if rejected
        """

        # Validate signal
        is_valid, msg = FeedbackValidator.validate(signal_type, source, value, confidence)
        if not is_valid:
            return None

        # Check for duplicates
        if self._is_duplicate(signal_type, source, value):
            return None

        # Store signal
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None
        now = datetime.now().isoformat()

        try:
            c.execute('''
                INSERT INTO signals
                (signal_type, source, value, confidence, description, metadata, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (signal_type, source, value, confidence, description, metadata_json, now))

            signal_id = c.lastrowid
            conn.commit()

            # Update dedup tracking
            self._update_dedup(signal_type, source, value)

            signal = FeedbackSignal(
                id=signal_id,
                signal_type=signal_type,
                source=source,
                value=value,
                confidence=confidence,
                description=description,
                metadata=metadata_json,
                recorded_at=now
            )

            return signal

        finally:
            conn.close()

    def _is_duplicate(self, signal_type: str, source: str, value: float) -> bool:
        """Check if signal is duplicate within 5-minute window"""
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        value_hash = str((signal_type, source, round(value, 2)))
        cutoff = (datetime.now() - timedelta(minutes=5)).isoformat()

        c.execute('''
            SELECT 1 FROM signal_dedup
            WHERE signal_type = ? AND source = ? AND value_hash = ?
            AND last_seen > ?
        ''', (signal_type, source, value_hash, cutoff))

        is_dup = c.fetchone() is not None
        conn.close()

        return is_dup

    def _update_dedup(self, signal_type: str, source: str, value: float):
        """Update deduplication tracking"""
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        value_hash = str((signal_type, source, round(value, 2)))
        now = datetime.now().isoformat()

        c.execute('''
            INSERT OR REPLACE INTO signal_dedup
            (signal_type, source, value_hash, last_seen)
            VALUES (?, ?, ?, ?)
        ''', (signal_type, source, value_hash, now))

        conn.commit()
        conn.close()

    def get_signals(self, hours_back: int = 24, signal_type: str = None,
                   source: str = None) -> List[FeedbackSignal]:
        """
        Retrieve signals from the past N hours

        Args:
            hours_back: How many hours to look back (default 24)
            signal_type: Filter by signal type (optional)
            source: Filter by source (optional)

        Returns:
            List of FeedbackSignal objects
        """
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        cutoff = (datetime.now() - timedelta(hours=hours_back)).isoformat()

        query = 'SELECT * FROM signals WHERE recorded_at > ?'
        params = [cutoff]

        if signal_type:
            query += ' AND signal_type = ?'
            params.append(signal_type)

        if source:
            query += ' AND source = ?'
            params.append(source)

        query += ' ORDER BY recorded_at DESC'

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signal = FeedbackSignal(
                id=row[0],
                signal_type=row[1],
                source=row[2],
                value=row[3],
                confidence=row[4],
                description=row[5],
                metadata=row[6],
                recorded_at=row[7]
            )
            signals.append(signal)

        return signals

    def get_signal_stats(self) -> Dict:
        """Get statistics about collected signals"""
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        stats = {
            'total_signals': 0,
            'by_type': {},
            'by_source': {},
            'average_confidence': 0.0,
            'recent_24h': 0,
        }

        # Total count
        c.execute('SELECT COUNT(*) FROM signals')
        stats['total_signals'] = c.fetchone()[0]

        # By type
        c.execute('''
            SELECT signal_type, COUNT(*) FROM signals
            GROUP BY signal_type
        ''')
        stats['by_type'] = {row[0]: row[1] for row in c.fetchall()}

        # By source
        c.execute('''
            SELECT source, COUNT(*) FROM signals
            GROUP BY source
        ''')
        stats['by_source'] = {row[0]: row[1] for row in c.fetchall()}

        # Average confidence
        c.execute('SELECT AVG(confidence) FROM signals')
        avg_conf = c.fetchone()[0]
        if avg_conf:
            stats['average_confidence'] = round(avg_conf, 2)

        # Recent 24h
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        c.execute('SELECT COUNT(*) FROM signals WHERE recorded_at > ?', (cutoff,))
        stats['recent_24h'] = c.fetchone()[0]

        conn.close()

        return stats

    def cleanup_old_signals(self, days_old: int = 30):
        """Remove signals older than N days"""
        conn = sqlite3.connect(self.feedback_db)
        c = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days_old)).isoformat()

        c.execute('DELETE FROM signals WHERE recorded_at < ?', (cutoff,))
        deleted = c.rowcount

        c.execute('DELETE FROM signal_dedup WHERE last_seen < ?', (cutoff,))

        conn.commit()
        conn.close()

        return deleted


if __name__ == '__main__':
    # Example usage
    collector = FeedbackCollector()

    # Collect some example signals
    signals = [
        {
            'type': 'user_satisfaction',
            'source': 'user',
            'value': 0.9,
            'confidence': 0.95,
            'desc': 'User reports good performance'
        },
        {
            'type': 'business_metric',
            'source': 'monitoring',
            'value': 0.89,
            'confidence': 0.99,
            'desc': 'SLA compliance 89%'
        },
        {
            'type': 'operational_constraint',
            'source': 'team',
            'value': 0.0,
            'confidence': 0.95,
            'desc': 'Never reduce memory below 2GB'
        },
    ]

    for sig in signals:
        signal = collector.collect_signal(
            signal_type=sig['type'],
            source=sig['source'],
            value=sig['value'],
            confidence=sig['confidence'],
            description=sig['desc']
        )
        if signal:
            print(f"✅ Collected: {signal.signal_type} from {signal.source}")
        else:
            print(f"❌ Rejected: {sig['type']}")

    # Show stats
    stats = collector.get_signal_stats()
    print("\n📊 Signal Stats:")
    print(f"  Total: {stats['total_signals']}")
    print(f"  By type: {stats['by_type']}")
    print(f"  By source: {stats['by_source']}")
    print(f"  Avg confidence: {stats['average_confidence']}")
