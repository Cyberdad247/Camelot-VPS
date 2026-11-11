#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 3: Business-Weighted Candidate Ranking
Re-rank optimization candidates by business impact, not just technical score
"""

import json
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Tuple

from phase_h_business_metrics import BusinessMetrics
from phase_h_optimizer import OptimizationCandidate


@dataclass
class RankedCandidate:
    """Candidate with business-weighted ranking"""
    candidate_id: int
    name: str
    technical_impact_pct: float  # Original expected impact
    business_impact_pct: float  # Business-weighted impact
    confidence: float
    safety_score: float
    technical_score: float  # Original composite score
    business_score: float  # Business-weighted score
    approval_status: str  # 'auto_apply', 'manual_review', 'reject'
    rationale: str  # Why this ranking/approval
    category: str = None
    cost_reduction_pct: float = 0.0
    availability_impact_pct: float = 0.0
    constraint_violations: List[str] = None


class BusinessOptimizer:
    """Re-rank optimization candidates with business metrics and constraints"""

    # Approval thresholds (score out of 100, normalized from weighted impacts)
    AUTO_APPLY_THRESHOLD = 55  # High confidence + safety + good impact
    MANUAL_REVIEW_THRESHOLD = 40  # Medium confidence/safety/impact
    REJECT_THRESHOLD = 20  # Low confidence or constraint violation

    def __init__(self, optimizations_db: str = "control_plane/optimizations.db",
                 business_metrics_db: str = "control_plane/business_metrics.db",
                 business_ranking_db: str = "control_plane/business_ranking.db"):
        """Initialize business optimizer"""
        self.optimizations_db = optimizations_db
        self.business_metrics = BusinessMetrics(business_metrics_db)
        self.business_ranking_db = business_ranking_db
        self._ensure_db()

    def _ensure_db(self):
        """Create business ranking database"""
        conn = sqlite3.connect(self.business_ranking_db)
        c = conn.cursor()

        # Business-weighted ranking decisions
        c.execute('''
            CREATE TABLE IF NOT EXISTS ranked_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                technical_impact_pct REAL,
                business_impact_pct REAL,
                confidence REAL,
                safety_score REAL,
                technical_score REAL,
                business_score REAL,
                approval_status TEXT,
                rationale TEXT,
                cost_reduction_pct REAL,
                availability_impact_pct REAL,
                constraint_violations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Audit trail
        c.execute('''
            CREATE TABLE IF NOT EXISTS ranking_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER,
                decision TEXT,
                reasoning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def rank_candidates_with_business_impact(self,
                                            candidates: List[OptimizationCandidate],
                                            impact_details: Dict[int, Dict] = None
                                            ) -> List[RankedCandidate]:
        """
        Re-rank candidates considering business impact

        Args:
            candidates: List of optimization candidates from Week 2
            impact_details: Dict mapping candidate_id to impact details
                           {'cost_reduction': 10, 'latency_impact': 2, 'availability_impact': 0}

        Returns:
            List of RankedCandidate objects sorted by business score
        """
        if impact_details is None:
            impact_details = {}

        ranked = []

        for candidate in candidates:
            # Get candidate details
            cand_id = candidate.id
            name = candidate.name
            category = candidate.category
            technical_impact = candidate.expected_impact_pct or 0
            confidence = candidate.confidence or 0
            safety = candidate.safety_score or 0
            tech_score = candidate.composite_score or 0

            # Get impact details
            impacts = impact_details.get(cand_id, {})
            cost_reduction = impacts.get('cost_reduction', 0)
            latency_impact = impacts.get('latency_impact', technical_impact)
            availability_impact = impacts.get('availability_impact', 0)

            # Calculate business-weighted impact
            impact_dict = {
                'latency': latency_impact,
                'cost': -cost_reduction,  # Negative = good (reduction)
                'availability': availability_impact
            }
            business_impact_raw = self.business_metrics.calculate_business_impact(impact_dict)

            # Business impact: negative = good (improvement), positive = bad (degradation)
            # Convert to 0-100 scale where higher is better
            # Map: -30 (very good) → 100, 0 (neutral) → 50, +30 (very bad) → 0
            business_impact_normalized = max(0, min(100, 50 - business_impact_raw / 0.6))

            # Calculate business-weighted score
            # Similar to technical: (impact × 0.5) + (confidence × 0.3) + (safety × 0.2)
            business_score = (business_impact_normalized * 0.5) + (confidence * 30) + (safety * 20)
            business_score = min(100, business_score)

            # Check constraint violations
            violations = self._check_constraints(candidate, impacts)

            # Determine approval status
            approval_status, rationale = self._determine_approval_status(
                business_score, confidence, safety, violations
            )

            ranked_candidate = RankedCandidate(
                candidate_id=cand_id,
                name=name,
                category=category,
                technical_impact_pct=technical_impact,
                business_impact_pct=float(business_impact_normalized),
                confidence=confidence,
                safety_score=safety,
                technical_score=tech_score,
                business_score=business_score,
                approval_status=approval_status,
                rationale=rationale,
                cost_reduction_pct=cost_reduction,
                availability_impact_pct=availability_impact,
                constraint_violations=violations
            )

            ranked.append(ranked_candidate)

        # Sort by business score (descending)
        ranked.sort(key=lambda x: x.business_score, reverse=True)

        # Store rankings
        self._store_rankings(ranked)

        return ranked

    def _check_constraints(self, candidate: OptimizationCandidate, impacts: Dict) -> List[str]:
        """Check if candidate violates any constraints"""
        violations = []

        # Check constraint types based on candidate category
        if candidate.category == 'resource_allocation':
            # Check memory constraint
            if 'memory_reduction' in impacts:
                reduction = impacts['memory_reduction']
                is_valid, msg = self.business_metrics.validate_against_constraints('memory', reduction)
                if not is_valid:
                    violations.append(msg)

        elif candidate.category == 'parameter_tuning':
            # Check connection constraint
            if 'connections' in impacts:
                connections = impacts['connections']
                is_valid, msg = self.business_metrics.validate_against_constraints('connections', connections)
                if not is_valid:
                    violations.append(msg)

        return violations

    def _determine_approval_status(self, business_score: float, confidence: float,
                                  safety: float, violations: List[str]) -> Tuple[str, str]:
        """Determine approval status based on score, confidence, safety, and violations"""

        # Hard violations reject automatically
        if violations:
            return 'reject', f"Hard constraint violation: {violations[0]}"

        # Score-based decisions
        if business_score >= self.AUTO_APPLY_THRESHOLD:
            return 'auto_apply', f"High business impact ({business_score:.0f}/100) and safe ({safety:.0%})"

        elif business_score >= self.MANUAL_REVIEW_THRESHOLD:
            if confidence >= 0.70 and safety >= 0.75:
                return 'manual_review', f"Moderate business impact ({business_score:.0f}/100) - review recommended"
            else:
                return 'reject', f"Insufficient confidence ({confidence:.0%}) or safety ({safety:.0%})"

        else:
            return 'reject', f"Low business score ({business_score:.0f}/100)"

    def _store_rankings(self, ranked_candidates: List[RankedCandidate]):
        """Store business rankings in database"""
        conn = sqlite3.connect(self.business_ranking_db)
        c = conn.cursor()

        for ranked in ranked_candidates:
            c.execute('''
                INSERT INTO ranked_candidates
                (candidate_id, name, category, technical_impact_pct, business_impact_pct,
                 confidence, safety_score, technical_score, business_score,
                 approval_status, rationale, cost_reduction_pct, availability_impact_pct,
                 constraint_violations)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ranked.candidate_id, ranked.name, ranked.category, ranked.technical_impact_pct,
                  ranked.business_impact_pct, ranked.confidence, ranked.safety_score,
                  ranked.technical_score, ranked.business_score, ranked.approval_status,
                  ranked.rationale, ranked.cost_reduction_pct, ranked.availability_impact_pct,
                  json.dumps(ranked.constraint_violations or [])))

        conn.commit()
        conn.close()

    def get_candidates_by_status(self, approval_status: str) -> List[RankedCandidate]:
        """Get candidates filtered by approval status"""
        conn = sqlite3.connect(self.business_ranking_db)
        c = conn.cursor()

        c.execute('''
            SELECT candidate_id, name, technical_impact_pct, business_impact_pct,
                   confidence, safety_score, technical_score, business_score,
                   approval_status, rationale, cost_reduction_pct, availability_impact_pct,
                   constraint_violations, category
            FROM ranked_candidates
            WHERE approval_status = ?
            ORDER BY business_score DESC
        ''', (approval_status,))

        rows = c.fetchall()
        conn.close()

        candidates = []
        for row in rows:
            violations = json.loads(row[12]) if row[12] else []
            candidate = RankedCandidate(
                candidate_id=row[0],
                name=row[1],
                technical_impact_pct=row[2],
                business_impact_pct=row[3],
                confidence=row[4],
                safety_score=row[5],
                technical_score=row[6],
                business_score=row[7],
                approval_status=row[8],
                rationale=row[9],
                cost_reduction_pct=row[10],
                availability_impact_pct=row[11],
                constraint_violations=violations
            )
            candidates.append(candidate)

        return candidates

    def get_ranking_summary(self) -> Dict:
        """Get summary of business ranking decisions"""
        conn = sqlite3.connect(self.business_ranking_db)
        c = conn.cursor()

        summary = {
            'total_candidates': 0,
            'auto_apply': 0,
            'manual_review': 0,
            'reject': 0,
            'average_business_score': 0.0,
            'constraint_violations': 0,
        }

        # Total count
        c.execute('SELECT COUNT(*) FROM ranked_candidates')
        summary['total_candidates'] = c.fetchone()[0]

        # By status
        c.execute('SELECT approval_status, COUNT(*) FROM ranked_candidates GROUP BY approval_status')
        for status, count in c.fetchall():
            if status == 'auto_apply':
                summary['auto_apply'] = count
            elif status == 'manual_review':
                summary['manual_review'] = count
            elif status == 'reject':
                summary['reject'] = count

        # Average score
        c.execute('SELECT AVG(business_score) FROM ranked_candidates')
        avg = c.fetchone()[0]
        if avg:
            summary['average_business_score'] = round(avg, 1)

        # Constraint violations
        c.execute('''
            SELECT COUNT(*) FROM ranked_candidates
            WHERE constraint_violations != '[]'
        ''')
        summary['constraint_violations'] = c.fetchone()[0]

        conn.close()

        return summary


if __name__ == '__main__':
    from phase_h_optimizer import OptimizationCandidate

    # Example usage
    optimizer = BusinessOptimizer()

    # Create sample candidates
    candidates = [
        OptimizationCandidate(
            id=1, pattern_id=1, category='parameter_tuning',
            name='Increase Pool Size',
            expected_impact_pct=8.0, confidence=0.92, safety_score=0.95,
            composite_score=0.82
        ),
        OptimizationCandidate(
            id=2, pattern_id=2, category='resource_allocation',
            name='Add Indexes',
            expected_impact_pct=12.0, confidence=0.90, safety_score=0.88,
            composite_score=0.80
        ),
    ]

    # Impact details (business context)
    impact_details = {
        1: {'latency_impact': 8, 'cost_reduction': 2},
        2: {'latency_impact': 12, 'cost_reduction': 5},
    }

    # Rank with business context
    ranked = optimizer.rank_candidates_with_business_impact(candidates, impact_details)

    print("📊 Business-Weighted Rankings:")
    for candidate in ranked:
        print(f"\n  {candidate.name}")
        print(f"    Technical impact: {candidate.technical_impact_pct:.0f}%")
        print(f"    Business impact: {candidate.business_impact_pct:.0f}%")
        print(f"    Business score: {candidate.business_score:.0f}/100")
        print(f"    Approval: {candidate.approval_status}")
        print(f"    Rationale: {candidate.rationale}")

    # Summary
    summary = optimizer.get_ranking_summary()
    print("\n📈 Summary:")
    print(f"  Total: {summary['total_candidates']}")
    print(f"  Auto-apply: {summary['auto_apply']}")
    print(f"  Manual review: {summary['manual_review']}")
    print(f"  Reject: {summary['reject']}")
    print(f"  Avg score: {summary['average_business_score']}/100")
