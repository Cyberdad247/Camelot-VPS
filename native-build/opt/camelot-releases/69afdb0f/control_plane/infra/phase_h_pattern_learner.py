#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 2: Pattern Learner
Extracts stable patterns from operational metrics
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Pattern:
    """Detected performance pattern"""
    id: Optional[int] = None
    pattern_type: str = ""  # temporal, load, error, resource, anomaly
    name: str = ""
    description: str = ""
    metrics: Dict = None  # Pattern definition
    confidence: float = 0.0  # 0.0-1.0
    last_detected: Optional[str] = None
    occurrence_count: int = 0
    created_at: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        d = asdict(self)
        if self.metrics:
            d['metrics'] = json.dumps(self.metrics) if not isinstance(self.metrics, str) else self.metrics
        return d


@dataclass
class PatternScore:
    """Pattern match score"""
    pattern_id: int
    pattern_name: str
    confidence: float
    match_score: float  # 0.0-1.0 how well current metrics match
    details: Dict


class PatternLearner:
    """Learn patterns from metrics database"""

    def __init__(self, metrics_db_path: str = "control_plane/metrics.db",
                 patterns_db_path: str = "control_plane/patterns.db"):
        """Initialize pattern learner"""
        self.metrics_db = metrics_db_path
        self.patterns_db = patterns_db_path
        self._ensure_db()
        self._load_baseline()

    def _ensure_db(self):
        """Create patterns database if needed"""
        conn = sqlite3.connect(self.patterns_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                metrics TEXT NOT NULL,
                confidence REAL,
                last_detected TIMESTAMP,
                occurrence_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS pattern_matches (
                id INTEGER PRIMARY KEY,
                pattern_id INTEGER NOT NULL,
                match_score REAL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY(pattern_id) REFERENCES patterns(id)
            )
        ''')

        conn.commit()
        conn.close()

    def _load_baseline(self):
        """Load Phase G baseline for pattern detection"""
        self.baseline = {
            'read_p95_ms': 1.3,
            'write_p95_ms': 1.3,
            'route_p95_ms': 0.001,
            'compress_p95_ms': 1.5,
            'error_rate': 0.001,  # 0.1%
            'healthy_rps': 1000,
        }

    def extract_metrics(self) -> Dict:
        """Extract current metrics from metrics database"""
        if not Path(self.metrics_db).exists():
            return {}

        try:
            conn = sqlite3.connect(self.metrics_db)
            c = conn.cursor()

            metrics = {}

            # Get statistics for each operation type
            c.execute('''
                SELECT operation_type,
                       COUNT(*) as count,
                       AVG(duration_ms) as avg_ms,
                       MIN(duration_ms) as min_ms,
                       MAX(duration_ms) as max_ms
                FROM operations
                WHERE recorded_at >= datetime('now', '-24 hours')
                GROUP BY operation_type
            ''')

            for row in c.fetchall():
                op_type, count, avg_ms, min_ms, max_ms = row
                if op_type:
                    metrics[op_type] = {
                        'count': count,
                        'avg_ms': avg_ms,
                        'min_ms': min_ms,
                        'max_ms': max_ms,
                    }

            conn.close()
            return metrics
        except Exception as e:
            print(f"Error extracting metrics: {e}")
            return {}

    def detect_temporal_patterns(self) -> List[Pattern]:
        """Detect time-of-day patterns"""
        patterns = []

        if not Path(self.metrics_db).exists():
            return patterns

        try:
            conn = sqlite3.connect(self.metrics_db)
            c = conn.cursor()

            # Check for morning spike (07:00-09:00)
            c.execute('''
                SELECT COUNT(*) as count,
                       AVG(duration_ms) as avg_latency,
                       MAX(duration_ms) as max_latency
                FROM operations
                WHERE strftime('%H', recorded_at) IN ('07', '08', '09')
                AND recorded_at >= datetime('now', '-7 days')
            ''')

            row = c.fetchone()
            if row and row[0] > 100:  # Sufficient samples
                count, avg_latency, max_latency = row
                baseline_latency = self.baseline['read_p95_ms']

                if avg_latency and avg_latency > baseline_latency * 1.15:  # 15% above baseline
                    confidence = min(0.95, count / 1000.0)  # Confidence based on sample count
                    patterns.append(Pattern(
                        pattern_type='temporal',
                        name='Morning Load Spike',
                        description='Higher latency during 07:00-09:00 hours',
                        metrics={
                            'time_window': '07:00-09:00',
                            'avg_latency_ms': round(avg_latency, 2),
                            'baseline_ms': baseline_latency,
                            'elevation_pct': round((avg_latency - baseline_latency) / baseline_latency * 100, 1),
                        },
                        confidence=confidence,
                    ))

            conn.close()
        except Exception as e:
            print(f"Error detecting temporal patterns: {e}")

        return patterns

    def detect_load_patterns(self) -> List[Pattern]:
        """Detect load-related patterns (RPS vs latency correlation)"""
        patterns = []

        if not Path(self.metrics_db).exists():
            return patterns

        try:
            conn = sqlite3.connect(self.metrics_db)
            c = conn.cursor()

            # Detect sustained high-load periods
            c.execute('''
                SELECT COUNT(*) as ops_per_minute,
                       AVG(duration_ms) as avg_latency,
                       CAST(strftime('%H:%M', recorded_at) AS TEXT) as minute
                FROM operations
                WHERE recorded_at >= datetime('now', '-6 hours')
                GROUP BY minute
                ORDER BY ops_per_minute DESC
                LIMIT 5
            ''')

            high_load_samples = []
            for row in c.fetchall():
                ops_per_minute, avg_latency, minute = row
                if ops_per_minute > 200:  # High load threshold
                    high_load_samples.append({
                        'ops_per_minute': ops_per_minute,
                        'avg_latency_ms': avg_latency,
                    })

            if len(high_load_samples) >= 3:  # Need multiple samples
                avg_ops = sum(s['ops_per_minute'] for s in high_load_samples) / len(high_load_samples)
                avg_latency = sum(s['avg_latency_ms'] for s in high_load_samples) / len(high_load_samples)
                baseline_latency = self.baseline['read_p95_ms']

                if avg_latency > baseline_latency * 1.5:
                    confidence = min(0.90, len(high_load_samples) / 10.0)
                    patterns.append(Pattern(
                        pattern_type='load',
                        name='Load-Induced Latency',
                        description=f'Latency increases under {avg_ops:.0f}+ ops/min load',
                        metrics={
                            'ops_per_minute_threshold': round(avg_ops),
                            'latency_at_load_ms': round(avg_latency, 2),
                            'baseline_ms': baseline_latency,
                            'correlation': 'positive',
                        },
                        confidence=confidence,
                    ))

            conn.close()
        except Exception as e:
            print(f"Error detecting load patterns: {e}")

        return patterns

    def detect_error_patterns(self) -> List[Pattern]:
        """Detect error spike patterns"""
        patterns = []

        if not Path(self.metrics_db).exists():
            return patterns

        try:
            conn = sqlite3.connect(self.metrics_db)
            c = conn.cursor()

            # Get overall error rate
            c.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as failures
                FROM operations
                WHERE recorded_at >= datetime('now', '-6 hours')
            ''')

            row = c.fetchone()
            if row:
                total, failures = row
                if total > 100 and failures:
                    error_rate = failures / total
                    baseline_error = self.baseline['error_rate']

                    if error_rate > baseline_error * 10:  # 10x baseline error
                        confidence = min(0.85, total / 5000.0)
                        patterns.append(Pattern(
                            pattern_type='error',
                            name='Error Spike Detected',
                            description=f'Error rate {error_rate*100:.1f}% (baseline {baseline_error*100:.1f}%)',
                            metrics={
                                'current_error_rate': round(error_rate * 100, 2),
                                'baseline_error_rate': round(baseline_error * 100, 2),
                                'elevation_factor': round(error_rate / baseline_error, 1),
                                'failure_count': failures,
                                'total_operations': total,
                            },
                            confidence=confidence,
                        ))

            conn.close()
        except Exception as e:
            print(f"Error detecting error patterns: {e}")

        return patterns

    def detect_resource_patterns(self) -> List[Pattern]:
        """Detect resource utilization patterns"""
        patterns = []

        # Note: Resource patterns would require actual resource monitoring
        # For now, we infer from operation latency clustering

        if not Path(self.metrics_db).exists():
            return patterns

        try:
            conn = sqlite3.connect(self.metrics_db)
            c = conn.cursor()

            # Detect if ops are getting slower over time (potential memory creep)
            c.execute('''
                SELECT
                    CAST((julianday(recorded_at) - (SELECT julianday(MIN(recorded_at)) FROM operations)) / 3600 AS INTEGER) as hours_elapsed,
                    AVG(duration_ms) as avg_latency
                FROM operations
                WHERE recorded_at >= datetime('now', '-8 hours')
                GROUP BY CAST((julianday(recorded_at) - (SELECT julianday(MIN(recorded_at)) FROM operations)) / 3600 AS INTEGER)
                ORDER BY hours_elapsed
            ''')

            rows = c.fetchall()
            if len(rows) >= 3:
                first_hour_latency = rows[0][1] if rows[0][1] else 0
                last_hour_latency = rows[-1][1] if rows[-1][1] else 0

                if first_hour_latency > 0:
                    growth = (last_hour_latency - first_hour_latency) / first_hour_latency
                    if growth > 0.20:  # 20% growth over 8 hours
                        confidence = min(0.80, len(rows) / 10.0)
                        patterns.append(Pattern(
                            pattern_type='resource',
                            name='Memory Creep Detected',
                            description='Gradual latency increase indicating possible memory growth',
                            metrics={
                                'initial_latency_ms': round(first_hour_latency, 2),
                                'current_latency_ms': round(last_hour_latency, 2),
                                'growth_pct': round(growth * 100, 1),
                                'hours_elapsed': len(rows),
                            },
                            confidence=confidence,
                        ))

            conn.close()
        except Exception as e:
            print(f"Error detecting resource patterns: {e}")

        return patterns

    def learn_all_patterns(self) -> List[Pattern]:
        """Learn all pattern types"""
        all_patterns = []

        all_patterns.extend(self.detect_temporal_patterns())
        all_patterns.extend(self.detect_load_patterns())
        all_patterns.extend(self.detect_error_patterns())
        all_patterns.extend(self.detect_resource_patterns())

        # Store patterns
        for pattern in all_patterns:
            self.store_pattern(pattern)

        return all_patterns

    def store_pattern(self, pattern: Pattern):
        """Store pattern in database"""
        conn = sqlite3.connect(self.patterns_db)
        c = conn.cursor()

        metrics_json = json.dumps(pattern.metrics) if pattern.metrics else '{}'

        c.execute('''
            INSERT OR REPLACE INTO patterns
            (pattern_type, name, description, metrics, confidence, occurrence_count, last_detected)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            pattern.pattern_type,
            pattern.name,
            pattern.description,
            metrics_json,
            pattern.confidence,
            pattern.occurrence_count + 1,
            datetime.now().isoformat(),
        ))

        conn.commit()
        conn.close()

    def get_stored_patterns(self) -> List[Pattern]:
        """Retrieve all stored patterns"""
        patterns = []

        try:
            conn = sqlite3.connect(self.patterns_db)
            c = conn.cursor()

            c.execute('SELECT * FROM patterns ORDER BY confidence DESC')

            for row in c.fetchall():
                pattern = Pattern(
                    id=row[0],
                    pattern_type=row[1],
                    name=row[2],
                    description=row[3],
                    metrics=json.loads(row[4]) if row[4] else {},
                    confidence=row[5],
                    last_detected=row[6],
                    occurrence_count=row[7],
                    created_at=row[8],
                )
                patterns.append(pattern)

            conn.close()
        except Exception as e:
            print(f"Error retrieving patterns: {e}")

        return patterns

    def get_pattern_stats(self) -> Dict:
        """Get statistics about detected patterns"""
        patterns = self.get_stored_patterns()

        return {
            'total_patterns': len(patterns),
            'by_type': {},
            'by_confidence': {
                'high': len([p for p in patterns if p.confidence >= 0.8]),
                'medium': len([p for p in patterns if 0.6 <= p.confidence < 0.8]),
                'low': len([p for p in patterns if p.confidence < 0.6]),
            },
            'average_confidence': sum(p.confidence for p in patterns) / len(patterns) if patterns else 0.0,
            'patterns': [
                {
                    'name': p.name,
                    'type': p.pattern_type,
                    'confidence': p.confidence,
                    'occurrences': p.occurrence_count,
                }
                for p in patterns[:10]  # Top 10
            ],
        }


if __name__ == '__main__':
    learner = PatternLearner()

    print("🔍 Learning patterns from metrics...")
    patterns = learner.learn_all_patterns()

    print(f"\n✅ Detected {len(patterns)} patterns:")
    for pattern in patterns:
        print(f"  • {pattern.name} ({pattern.pattern_type})")
        print(f"    Confidence: {pattern.confidence:.0%}")
        if pattern.metrics:
            print(f"    Details: {pattern.metrics}")

    print("\n📊 Pattern Statistics:")
    stats = learner.get_pattern_stats()
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  High confidence: {stats['by_confidence']['high']}")
    print(f"  Average confidence: {stats['average_confidence']:.0%}")
