#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 2: Optimizer Engine
Generates and ranks optimization candidates from detected patterns
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class OptimizationCandidate:
    """Suggested optimization with scoring"""
    id: Optional[int] = None
    pattern_id: Optional[int] = None
    category: str = ""  # parameter_tuning, resource_allocation, compression, caching, routing
    name: str = ""
    description: str = ""
    current_value: str = ""
    suggested_value: str = ""
    expected_impact_pct: float = 0.0  # % improvement
    confidence: float = 0.0  # 0.0-1.0 how confident
    safety_score: float = 0.0  # 0.0-1.0 risk of regression
    composite_score: float = 0.0  # Impact×0.5 + Confidence×0.3 + Safety×0.2
    rationale: str = ""
    implementation_effort: str = ""  # low, medium, high
    accepted: Optional[bool] = None
    applied_at: Optional[str] = None
    result_impact_pct: Optional[float] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


class OptimizerEngine:
    """Generate optimization candidates from patterns"""

    def __init__(self, patterns_db_path: str = "control_plane/patterns.db",
                 optimizations_db_path: str = "control_plane/optimizations.db"):
        """Initialize optimizer"""
        self.patterns_db = patterns_db_path
        self.optimizations_db = optimizations_db_path
        self._ensure_db()
        self._load_thresholds()

    def _ensure_db(self):
        """Create optimizations database if needed"""
        conn = sqlite3.connect(self.optimizations_db)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY,
                pattern_id INTEGER,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                current_value TEXT,
                suggested_value TEXT,
                expected_impact_pct REAL,
                confidence REAL,
                safety_score REAL,
                composite_score REAL,
                rationale TEXT,
                implementation_effort TEXT,
                accepted INTEGER,
                applied_at TIMESTAMP,
                result_impact_pct REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(pattern_id) REFERENCES patterns(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS optimization_log (
                id INTEGER PRIMARY KEY,
                candidate_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                status TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(candidate_id) REFERENCES candidates(id)
            )
        ''')

        conn.commit()
        conn.close()

    def _load_thresholds(self):
        """Load optimization decision thresholds"""
        self.thresholds = {
            'min_safe_confidence': 0.7,  # Confidence must be 70%+
            'min_safety_score': 0.75,  # Safety score must be 75%+
            'min_impact': 0.03,  # Minimum 3% improvement
            'high_priority': 0.85,  # Score 85%+ is high priority
            'auto_apply_threshold': 0.90,  # Auto-apply if score > 90%
        }

    def generate_candidates_from_patterns(self) -> List[OptimizationCandidate]:
        """Generate candidates from detected patterns"""
        candidates = []

        if not Path(self.patterns_db).exists():
            return candidates

        try:
            conn = sqlite3.connect(self.patterns_db)
            c = conn.cursor()

            c.execute('SELECT id, pattern_type, name, metrics, confidence FROM patterns ORDER BY confidence DESC')

            for row in c.fetchall():
                pattern_id, pattern_type, pattern_name, metrics_json, confidence = row

                try:
                    metrics = json.loads(metrics_json) if metrics_json else {}
                except json.JSONDecodeError:
                    metrics = {}

                # Generate candidates based on pattern type
                if pattern_type == 'temporal':
                    candidates.extend(self._generate_temporal_candidates(pattern_id, pattern_name, metrics, confidence))
                elif pattern_type == 'load':
                    candidates.extend(self._generate_load_candidates(pattern_id, pattern_name, metrics, confidence))
                elif pattern_type == 'error':
                    candidates.extend(self._generate_error_candidates(pattern_id, pattern_name, metrics, confidence))
                elif pattern_type == 'resource':
                    candidates.extend(self._generate_resource_candidates(pattern_id, pattern_name, metrics, confidence))

            conn.close()

            # Store all candidates
            for candidate in candidates:
                self.store_candidate(candidate)

        except Exception as e:
            print(f"Error generating candidates: {e}")

        return candidates

    def _generate_temporal_candidates(self, pattern_id: int, pattern_name: str, metrics: Dict, confidence: float) -> List[OptimizationCandidate]:
        """Generate candidates for temporal patterns (time-of-day spikes)"""
        candidates = []

        elevation = metrics.get('elevation_pct', 0)

        if elevation > 15:  # Significant spike
            # Candidate 1: Increase SQLite connection pool
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='parameter_tuning',
                name='Increase SQLite Connection Pool',
                description=f'Detected {elevation:.0f}% latency spike during {metrics.get("time_window", "peak hours")}. '
                           f'Increase connection pool to handle burst load.',
                current_value='5 connections',
                suggested_value='8 connections',
                expected_impact_pct=8.0,
                confidence=confidence * 0.95,
                safety_score=0.95,  # Very safe - can be easily reverted
                rationale='Morning spike pattern detected. Additional connections allow parallel operations.',
                implementation_effort='low',
            ))

            # Candidate 2: Pre-warming connections
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='parameter_tuning',
                name='Enable Connection Pre-warming',
                description='Pre-establish connections before peak hours to reduce latency.',
                current_value='disabled',
                suggested_value='enabled (07:00 daily)',
                expected_impact_pct=5.0,
                confidence=confidence * 0.85,
                safety_score=0.90,
                rationale='Eliminates cold-start latency during known spike windows.',
                implementation_effort='medium',
            ))

        return candidates

    def _generate_load_candidates(self, pattern_id: int, pattern_name: str, metrics: Dict, confidence: float) -> List[OptimizationCandidate]:
        """Generate candidates for load patterns (RPS vs latency)"""
        candidates = []

        elevation = metrics.get('elevation_pct', 0) if 'elevation_pct' in metrics else (
            (metrics.get('latency_at_load_ms', 0) - metrics.get('baseline_ms', 1.0)) / metrics.get('baseline_ms', 1.0) * 100
        )

        if elevation > 15:  # Significant load correlation
            # Candidate: Optimize query execution
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='parameter_tuning',
                name='Add Database Query Indexes',
                description='High load causes latency increase. Database indexes will improve query performance.',
                current_value='basic indexes',
                suggested_value='optimized indexes on frequent queries',
                expected_impact_pct=12.0,
                confidence=confidence * 0.90,
                safety_score=0.88,
                rationale='Query optimization is one of highest-impact improvements. Risk is schema validation required.',
                implementation_effort='medium',
            ))

            # Candidate: Increase queue depth
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='resource_allocation',
                name='Increase Operation Queue Depth',
                description='Larger queue allows batching more operations, reducing per-op overhead.',
                current_value='100 operations',
                suggested_value='500 operations',
                expected_impact_pct=7.0,
                confidence=confidence * 0.80,
                safety_score=0.85,
                rationale='Trade-off: increased memory for better throughput under load.',
                implementation_effort='low',
            ))

        return candidates

    def _generate_error_candidates(self, pattern_id: int, pattern_name: str, metrics: Dict, confidence: float) -> List[OptimizationCandidate]:
        """Generate candidates for error patterns"""
        candidates = []

        _error_rate = metrics.get('current_error_rate', 0)
        elevation = metrics.get('elevation_factor', 1.0)

        if elevation > 3:  # 3x+ error rate increase
            # Candidate: Connection pool sizing
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='parameter_tuning',
                name='Increase Connection Pool Timeout',
                description='High error rates indicate connection exhaustion. Increase timeout to prevent rejections.',
                current_value='30 seconds',
                suggested_value='60 seconds',
                expected_impact_pct=25.0,
                confidence=confidence * 0.92,
                safety_score=0.92,
                rationale='Prevents "connection unavailable" errors during spikes.',
                implementation_effort='low',
            ))

            # Candidate: Implement retry logic
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='parameter_tuning',
                name='Add Exponential Backoff Retry',
                description='Automatic retry with backoff helps recover from transient errors.',
                current_value='no retry',
                suggested_value='3 retries with exponential backoff',
                expected_impact_pct=15.0,
                confidence=confidence * 0.85,
                safety_score=0.88,
                rationale='Recovers from temporary network glitches without user intervention.',
                implementation_effort='medium',
            ))

        return candidates

    def _generate_resource_candidates(self, pattern_id: int, pattern_name: str, metrics: Dict, confidence: float) -> List[OptimizationCandidate]:
        """Generate candidates for resource patterns (memory creep, etc)"""
        candidates = []

        growth_pct = metrics.get('growth_pct', 0)

        if growth_pct > 15:  # Significant growth
            # Candidate: Compression
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='compression',
                name='Enable Aggressive Data Compression',
                description='Memory usage growing. Enable compression to reduce footprint.',
                current_value='compression_disabled',
                suggested_value='compression_enabled (ratio=0.8)',
                expected_impact_pct=20.0,
                confidence=confidence * 0.85,
                safety_score=0.80,  # CPU increase is minor trade-off
                rationale='Reduces memory growth while adding minimal CPU overhead.',
                implementation_effort='medium',
            ))

            # Candidate: Cache optimization
            candidates.append(OptimizationCandidate(
                pattern_id=pattern_id,
                category='caching',
                name='Reduce Cache TTL and Size',
                description='Aggressive caching causing memory creep. Reduce TTL and max size.',
                current_value='TTL=3600s, Size=1GB',
                suggested_value='TTL=600s, Size=256MB',
                expected_impact_pct=10.0,
                confidence=confidence * 0.80,
                safety_score=0.75,  # May increase database load
                rationale='Trade-off: reduce memory at cost of more frequent cache misses.',
                implementation_effort='low',
            ))

        return candidates

    def compute_candidate_scores(self, candidates: List[OptimizationCandidate]) -> List[OptimizationCandidate]:
        """Compute composite scores for all candidates"""
        scored = []

        for candidate in candidates:
            # Composite score = Impact×0.5 + Confidence×0.3 + Safety×0.2
            impact_factor = min(candidate.expected_impact_pct / 30.0, 1.0)  # Normalize to 1.0 at 30%
            confidence_factor = candidate.confidence
            safety_factor = candidate.safety_score

            composite = (
                impact_factor * 0.5 +
                confidence_factor * 0.3 +
                safety_factor * 0.2
            )

            candidate.composite_score = round(composite, 3)
            scored.append(candidate)

        # Sort by composite score
        return sorted(scored, key=lambda c: c.composite_score, reverse=True)

    def rank_candidates(self, candidates: List[OptimizationCandidate]) -> List[OptimizationCandidate]:
        """Rank candidates by quality and priority"""
        # Compute scores
        scored = self.compute_candidate_scores(candidates)

        # Filter by minimum thresholds
        qualified = [
            c for c in scored
            if c.confidence >= self.thresholds['min_safe_confidence']
            and c.safety_score >= self.thresholds['min_safety_score']
            and c.expected_impact_pct >= self.thresholds['min_impact']
        ]

        return qualified[:10]  # Return top 10

    def get_candidates_for_approval(self) -> List[OptimizationCandidate]:
        """Get candidates ready for human review/approval"""
        candidates = self.generate_candidates_from_patterns()
        ranked = self.rank_candidates(candidates)

        # Filter for auto-apply candidates (score >= 90%)
        auto_apply = [c for c in ranked if c.composite_score >= self.thresholds['auto_apply_threshold']]
        human_review = [c for c in ranked if c.composite_score < self.thresholds['auto_apply_threshold']]

        return {
            'auto_apply': auto_apply,
            'human_review': human_review,
            'total': len(ranked),
        }

    def store_candidate(self, candidate: OptimizationCandidate):
        """Store candidate in database"""
        conn = sqlite3.connect(self.optimizations_db)
        c = conn.cursor()

        c.execute('''
            INSERT INTO candidates
            (pattern_id, category, name, description, current_value, suggested_value,
             expected_impact_pct, confidence, safety_score, composite_score, rationale,
             implementation_effort)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            candidate.pattern_id,
            candidate.category,
            candidate.name,
            candidate.description,
            candidate.current_value,
            candidate.suggested_value,
            candidate.expected_impact_pct,
            candidate.confidence,
            candidate.safety_score,
            candidate.composite_score,
            candidate.rationale,
            candidate.implementation_effort,
        ))

        conn.commit()
        conn.close()

    def get_stored_candidates(self, limit: int = 50) -> List[OptimizationCandidate]:
        """Retrieve stored candidates from database"""
        candidates = []

        try:
            conn = sqlite3.connect(self.optimizations_db)
            c = conn.cursor()

            c.execute('''
                SELECT * FROM candidates
                ORDER BY composite_score DESC
                LIMIT ?
            ''', (limit,))

            for row in c.fetchall():
                candidate = OptimizationCandidate(
                    id=row[0],
                    pattern_id=row[1],
                    category=row[2],
                    name=row[3],
                    description=row[4],
                    current_value=row[5],
                    suggested_value=row[6],
                    expected_impact_pct=row[7],
                    confidence=row[8],
                    safety_score=row[9],
                    composite_score=row[10],
                    rationale=row[11],
                    implementation_effort=row[12],
                    accepted=row[13],
                    applied_at=row[14],
                    result_impact_pct=row[15],
                    created_at=row[16],
                )
                candidates.append(candidate)

            conn.close()
        except Exception as e:
            print(f"Error retrieving candidates: {e}")

        return candidates

    def get_candidate_stats(self) -> Dict:
        """Get statistics about generated candidates"""
        candidates = self.get_stored_candidates(limit=1000)

        by_category = {}
        by_score = {'high': 0, 'medium': 0, 'low': 0}

        for c in candidates:
            # By category
            if c.category not in by_category:
                by_category[c.category] = 0
            by_category[c.category] += 1

            # By score
            if c.composite_score >= 0.8:
                by_score['high'] += 1
            elif c.composite_score >= 0.6:
                by_score['medium'] += 1
            else:
                by_score['low'] += 1

        return {
            'total_candidates': len(candidates),
            'by_category': by_category,
            'by_score': by_score,
            'average_composite_score': sum(c.composite_score for c in candidates) / len(candidates) if candidates else 0.0,
            'average_impact': sum(c.expected_impact_pct for c in candidates) / len(candidates) if candidates else 0.0,
            'top_candidates': [
                {
                    'name': c.name,
                    'category': c.category,
                    'impact': c.expected_impact_pct,
                    'score': c.composite_score,
                }
                for c in candidates[:5]
            ],
        }


if __name__ == '__main__':
    optimizer = OptimizerEngine()

    print("🔧 Generating optimization candidates...")
    candidates = optimizer.generate_candidates_from_patterns()

    print(f"\n✅ Generated {len(candidates)} candidates:")
    for c in candidates[:5]:
        print(f"  • {c.name}")
        print(f"    Impact: {c.expected_impact_pct:.0f}%, Score: {c.composite_score:.0%}")

    print("\n📊 Candidate Statistics:")
    stats = optimizer.get_candidate_stats()
    print(f"  Total candidates: {stats['total_candidates']}")
    print(f"  Average impact: {stats['average_impact']:.1f}%")
    print(f"  High-quality: {stats['by_score']['high']}")
