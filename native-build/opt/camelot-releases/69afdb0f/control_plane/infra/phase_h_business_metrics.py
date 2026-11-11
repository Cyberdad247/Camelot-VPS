#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 2: Business Metric Integration
Define and manage SLA/KPI/cost metrics and business weighting
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class SLAThreshold:
    """SLA threshold for operation type"""
    operation_type: str
    p95_latency_ms: float  # p95 latency target (milliseconds)
    p99_latency_ms: float  # p99 latency target
    availability_pct: float  # availability target (0-100)
    error_rate_pct: float  # max acceptable error rate (0-100)


@dataclass
class KPITarget:
    """KPI target for operation type"""
    operation_type: str
    throughput_ops_sec: float  # target throughput
    cost_per_op: float  # target cost per operation ($)
    success_rate_pct: float  # target success rate (0-100)


@dataclass
class Constraint:
    """Operational constraint"""
    id: int = None
    constraint_type: str = None  # 'memory', 'connections', 'latency', etc.
    name: str = None
    is_hard: bool = True  # hard = never violate, soft = prefer not to
    minimum_value: float = None
    maximum_value: float = None
    description: str = None
    created_at: str = None


class BusinessMetrics:
    """Manage business metrics, SLAs, KPIs, and constraints"""

    def __init__(self, metrics_db_path: str = "control_plane/business_metrics.db"):
        """Initialize business metrics manager"""
        self.metrics_db = metrics_db_path
        self._ensure_db()
        self._init_defaults()

    def _ensure_db(self):
        """Create business metrics database and tables"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        # SLA thresholds
        c.execute('''
            CREATE TABLE IF NOT EXISTS sla_thresholds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT UNIQUE NOT NULL,
                p95_latency_ms REAL NOT NULL,
                p99_latency_ms REAL NOT NULL,
                availability_pct REAL NOT NULL,
                error_rate_pct REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # KPI targets
        c.execute('''
            CREATE TABLE IF NOT EXISTS kpi_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT UNIQUE NOT NULL,
                throughput_ops_sec REAL NOT NULL,
                cost_per_op REAL NOT NULL,
                success_rate_pct REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Operational constraints
        c.execute('''
            CREATE TABLE IF NOT EXISTS constraints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                constraint_type TEXT NOT NULL,
                name TEXT UNIQUE NOT NULL,
                is_hard INTEGER NOT NULL,
                minimum_value REAL,
                maximum_value REAL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Business weighting (priorities)
        c.execute('''
            CREATE TABLE IF NOT EXISTS business_weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT UNIQUE NOT NULL,
                weight REAL NOT NULL,
                rationale TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def _init_defaults(self):
        """Initialize default SLAs, KPIs, and weights"""
        # Default SLAs (based on Phase G baseline)
        default_slas = [
            SLAThreshold('read', p95_latency_ms=2.0, p99_latency_ms=3.0,
                        availability_pct=99.9, error_rate_pct=0.1),
            SLAThreshold('write', p95_latency_ms=2.0, p99_latency_ms=3.0,
                        availability_pct=99.9, error_rate_pct=0.1),
            SLAThreshold('route', p95_latency_ms=0.5, p99_latency_ms=1.0,
                        availability_pct=99.95, error_rate_pct=0.05),
            SLAThreshold('compress', p95_latency_ms=2.5, p99_latency_ms=4.0,
                        availability_pct=99.8, error_rate_pct=0.2),
        ]

        for sla in default_slas:
            self.set_sla_threshold(sla)

        # Default KPIs
        default_kpis = [
            KPITarget('read', throughput_ops_sec=1000, cost_per_op=0.0001,
                     success_rate_pct=99.9),
            KPITarget('write', throughput_ops_sec=500, cost_per_op=0.00015,
                     success_rate_pct=99.9),
            KPITarget('route', throughput_ops_sec=5000, cost_per_op=0.00005,
                     success_rate_pct=99.95),
            KPITarget('compress', throughput_ops_sec=200, cost_per_op=0.0002,
                     success_rate_pct=99.8),
        ]

        for kpi in default_kpis:
            self.set_kpi_target(kpi)

        # Default business weights
        default_weights = {
            'latency': 1.0,           # baseline
            'cost': 1.5,              # cost reduction valued 1.5x latency
            'availability': 2.0,      # uptime valued 2x latency
            'throughput': 1.2,        # throughput valued 1.2x latency
            'safety': 2.5,            # safety/stability valued 2.5x latency
        }

        for metric, weight in default_weights.items():
            self.set_business_weight(metric, weight)

    def set_sla_threshold(self, sla: SLAThreshold):
        """Set or update SLA threshold for operation type"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            INSERT OR REPLACE INTO sla_thresholds
            (operation_type, p95_latency_ms, p99_latency_ms, availability_pct, error_rate_pct)
            VALUES (?, ?, ?, ?, ?)
        ''', (sla.operation_type, sla.p95_latency_ms, sla.p99_latency_ms,
              sla.availability_pct, sla.error_rate_pct))

        conn.commit()
        conn.close()

    def get_sla_threshold(self, operation_type: str) -> Optional[SLAThreshold]:
        """Get SLA threshold for operation type"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            SELECT operation_type, p95_latency_ms, p99_latency_ms, availability_pct, error_rate_pct
            FROM sla_thresholds
            WHERE operation_type = ?
        ''', (operation_type,))

        row = c.fetchone()
        conn.close()

        if not row:
            return None

        return SLAThreshold(
            operation_type=row[0],
            p95_latency_ms=row[1],
            p99_latency_ms=row[2],
            availability_pct=row[3],
            error_rate_pct=row[4]
        )

    def set_kpi_target(self, kpi: KPITarget):
        """Set or update KPI target for operation type"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            INSERT OR REPLACE INTO kpi_targets
            (operation_type, throughput_ops_sec, cost_per_op, success_rate_pct)
            VALUES (?, ?, ?, ?)
        ''', (kpi.operation_type, kpi.throughput_ops_sec, kpi.cost_per_op,
              kpi.success_rate_pct))

        conn.commit()
        conn.close()

    def get_kpi_target(self, operation_type: str) -> Optional[KPITarget]:
        """Get KPI target for operation type"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            SELECT operation_type, throughput_ops_sec, cost_per_op, success_rate_pct
            FROM kpi_targets
            WHERE operation_type = ?
        ''', (operation_type,))

        row = c.fetchone()
        conn.close()

        if not row:
            return None

        return KPITarget(
            operation_type=row[0],
            throughput_ops_sec=row[1],
            cost_per_op=row[2],
            success_rate_pct=row[3]
        )

    def add_constraint(self, constraint_type: str, name: str, is_hard: bool = True,
                      minimum_value: float = None, maximum_value: float = None,
                      description: str = None) -> Optional[Constraint]:
        """Add operational constraint"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        try:
            c.execute('''
                INSERT INTO constraints
                (constraint_type, name, is_hard, minimum_value, maximum_value, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (constraint_type, name, 1 if is_hard else 0, minimum_value, maximum_value, description))

            constraint_id = c.lastrowid
            conn.commit()

            constraint = Constraint(
                id=constraint_id,
                constraint_type=constraint_type,
                name=name,
                is_hard=is_hard,
                minimum_value=minimum_value,
                maximum_value=maximum_value,
                description=description,
                created_at=datetime.now().isoformat()
            )

            return constraint

        finally:
            conn.close()

    def get_constraints(self, is_hard: bool = None) -> List[Constraint]:
        """Get constraints, optionally filtered by hard/soft"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        if is_hard is not None:
            c.execute('''
                SELECT id, constraint_type, name, is_hard, minimum_value, maximum_value, description, created_at
                FROM constraints
                WHERE is_hard = ?
                ORDER BY constraint_type
            ''', (1 if is_hard else 0,))
        else:
            c.execute('''
                SELECT id, constraint_type, name, is_hard, minimum_value, maximum_value, description, created_at
                FROM constraints
                ORDER BY constraint_type
            ''')

        rows = c.fetchall()
        conn.close()

        constraints = []
        for row in rows:
            constraint = Constraint(
                id=row[0],
                constraint_type=row[1],
                name=row[2],
                is_hard=bool(row[3]),
                minimum_value=row[4],
                maximum_value=row[5],
                description=row[6],
                created_at=row[7]
            )
            constraints.append(constraint)

        return constraints

    def validate_against_constraints(self, constraint_type: str, value: float) -> Tuple[bool, str]:
        """Validate a value against constraints"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            SELECT name, is_hard, minimum_value, maximum_value
            FROM constraints
            WHERE constraint_type = ?
        ''', (constraint_type,))

        rows = c.fetchall()
        conn.close()

        for row in rows:
            name, is_hard, min_val, max_val = row

            # Check minimum
            if min_val is not None and value < min_val:
                if is_hard:
                    return False, f"Hard constraint violation: {name} minimum {min_val}, got {value}"
                else:
                    return False, f"Soft constraint violation: {name} minimum {min_val}, got {value}"

            # Check maximum
            if max_val is not None and value > max_val:
                if is_hard:
                    return False, f"Hard constraint violation: {name} maximum {max_val}, got {value}"
                else:
                    return False, f"Soft constraint violation: {name} maximum {max_val}, got {value}"

        return True, "valid"

    def set_business_weight(self, metric_name: str, weight: float, rationale: str = None):
        """Set business weight for metric (how much it matters relative to latency)"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('''
            INSERT OR REPLACE INTO business_weights
            (metric_name, weight, rationale)
            VALUES (?, ?, ?)
        ''', (metric_name, weight, rationale))

        conn.commit()
        conn.close()

    def get_business_weight(self, metric_name: str) -> float:
        """Get business weight for metric"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('SELECT weight FROM business_weights WHERE metric_name = ?', (metric_name,))
        row = c.fetchone()
        conn.close()

        return row[0] if row else 1.0

    def get_all_weights(self) -> Dict[str, float]:
        """Get all business weights"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        c.execute('SELECT metric_name, weight FROM business_weights ORDER BY weight DESC')
        rows = c.fetchall()
        conn.close()

        return {row[0]: row[1] for row in rows}

    def calculate_business_impact(self, impact_dict: Dict[str, float]) -> float:
        """Calculate weighted business impact from impact dictionary

        Args:
            impact_dict: {'latency': 5, 'cost': -10, 'availability': 0}
                         (positive = good, negative = bad)

        Returns:
            Weighted impact score
        """
        weighted_impact = 0.0

        for metric, impact_pct in impact_dict.items():
            weight = self.get_business_weight(metric)
            weighted_impact += impact_pct * weight

        return weighted_impact

    def get_metrics_status(self) -> Dict:
        """Get comprehensive metrics status"""
        conn = sqlite3.connect(self.metrics_db)
        c = conn.cursor()

        status = {
            'sla_count': 0,
            'kpi_count': 0,
            'hard_constraints': 0,
            'soft_constraints': 0,
            'business_weights': {},
        }

        # Count SLAs
        c.execute('SELECT COUNT(*) FROM sla_thresholds')
        status['sla_count'] = c.fetchone()[0]

        # Count KPIs
        c.execute('SELECT COUNT(*) FROM kpi_targets')
        status['kpi_count'] = c.fetchone()[0]

        # Count constraints
        c.execute('SELECT is_hard, COUNT(*) FROM constraints GROUP BY is_hard')
        for is_hard, count in c.fetchall():
            if is_hard:
                status['hard_constraints'] = count
            else:
                status['soft_constraints'] = count

        # Get weights
        c.execute('SELECT metric_name, weight FROM business_weights')
        status['business_weights'] = {row[0]: row[1] for row in c.fetchall()}

        conn.close()

        return status


if __name__ == '__main__':
    metrics = BusinessMetrics()

    # Get status
    status = metrics.get_metrics_status()
    print("📊 Business Metrics Status:")
    print(f"  SLA thresholds: {status['sla_count']}")
    print(f"  KPI targets: {status['kpi_count']}")
    print(f"  Hard constraints: {status['hard_constraints']}")
    print(f"  Soft constraints: {status['soft_constraints']}")
    print(f"  Business weights: {status['business_weights']}")

    # Get SLA
    read_sla = metrics.get_sla_threshold('read')
    print("\n📋 Read SLA:")
    print(f"  p95: {read_sla.p95_latency_ms}ms")
    print(f"  p99: {read_sla.p99_latency_ms}ms")
    print(f"  Availability: {read_sla.availability_pct}%")

    # Add constraint
    constraint = metrics.add_constraint(
        constraint_type='memory',
        name='Minimum Cache Size',
        is_hard=True,
        minimum_value=2.0,
        description='Never reduce cache below 2GB'
    )
    print(f"\n✅ Added constraint: {constraint.name}")

    # Validate
    is_valid, msg = metrics.validate_against_constraints('memory', 1.5)
    print(f"  Validation (1.5GB): {msg}")

    is_valid, msg = metrics.validate_against_constraints('memory', 3.0)
    print(f"  Validation (3.0GB): {msg}")
