#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Week 3 Day 2: Business Metrics Tests
Test SLA/KPI management, constraints, and business weighting
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from phase_h_business_metrics import BusinessMetrics, KPITarget, SLAThreshold


class TestSLAManagement(unittest.TestCase):
    """Test SLA threshold management"""

    def setUp(self):
        """Create temporary metrics database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.metrics = BusinessMetrics(metrics_db_path=self.metrics_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_get_default_sla(self):
        """Test default SLA thresholds are loaded"""
        read_sla = self.metrics.get_sla_threshold('read')
        self.assertIsNotNone(read_sla)
        self.assertEqual(read_sla.operation_type, 'read')
        self.assertGreater(read_sla.p95_latency_ms, 0)
        self.assertGreater(read_sla.availability_pct, 0)

    def test_set_custom_sla(self):
        """Test setting custom SLA"""
        custom_sla = SLAThreshold(
            operation_type='custom_op',
            p95_latency_ms=5.0,
            p99_latency_ms=10.0,
            availability_pct=99.5,
            error_rate_pct=0.5
        )

        self.metrics.set_sla_threshold(custom_sla)

        retrieved = self.metrics.get_sla_threshold('custom_op')
        self.assertEqual(retrieved.p95_latency_ms, 5.0)
        self.assertEqual(retrieved.availability_pct, 99.5)

    def test_sla_for_all_default_ops(self):
        """Test SLA exists for all default operation types"""
        op_types = ['read', 'write', 'route', 'compress']

        for op in op_types:
            sla = self.metrics.get_sla_threshold(op)
            self.assertIsNotNone(sla, f"Missing SLA for {op}")
            self.assertEqual(sla.operation_type, op)


class TestKPIManagement(unittest.TestCase):
    """Test KPI target management"""

    def setUp(self):
        """Create temporary metrics database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.metrics = BusinessMetrics(metrics_db_path=self.metrics_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_get_default_kpi(self):
        """Test default KPI targets are loaded"""
        read_kpi = self.metrics.get_kpi_target('read')
        self.assertIsNotNone(read_kpi)
        self.assertEqual(read_kpi.operation_type, 'read')
        self.assertGreater(read_kpi.throughput_ops_sec, 0)
        self.assertGreater(read_kpi.cost_per_op, 0)

    def test_set_custom_kpi(self):
        """Test setting custom KPI"""
        custom_kpi = KPITarget(
            operation_type='custom_op',
            throughput_ops_sec=2000,
            cost_per_op=0.00012,
            success_rate_pct=99.95
        )

        self.metrics.set_kpi_target(custom_kpi)

        retrieved = self.metrics.get_kpi_target('custom_op')
        self.assertEqual(retrieved.throughput_ops_sec, 2000)
        self.assertEqual(retrieved.cost_per_op, 0.00012)

    def test_kpi_for_all_default_ops(self):
        """Test KPI exists for all default operation types"""
        op_types = ['read', 'write', 'route', 'compress']

        for op in op_types:
            kpi = self.metrics.get_kpi_target(op)
            self.assertIsNotNone(kpi, f"Missing KPI for {op}")
            self.assertEqual(kpi.operation_type, op)


class TestConstraintManagement(unittest.TestCase):
    """Test constraint management"""

    def setUp(self):
        """Create temporary metrics database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.metrics = BusinessMetrics(metrics_db_path=self.metrics_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_add_hard_constraint(self):
        """Test adding hard constraint"""
        constraint = self.metrics.add_constraint(
            constraint_type='memory',
            name='Minimum Cache',
            is_hard=True,
            minimum_value=2.0,
            description='Never reduce below 2GB'
        )

        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.name, 'Minimum Cache')
        self.assertTrue(constraint.is_hard)
        self.assertEqual(constraint.minimum_value, 2.0)

    def test_add_soft_constraint(self):
        """Test adding soft constraint"""
        constraint = self.metrics.add_constraint(
            constraint_type='connections',
            name='Preferred Connection Limit',
            is_hard=False,
            maximum_value=100,
            description='Prefer to stay under 100 connections'
        )

        self.assertIsNotNone(constraint)
        self.assertFalse(constraint.is_hard)

    def test_get_constraints_filtered(self):
        """Test retrieving constraints with filtering"""
        # Add constraints
        self.metrics.add_constraint('memory', 'Hard Memory', is_hard=True, minimum_value=2.0)
        self.metrics.add_constraint('connections', 'Soft Connections', is_hard=False, maximum_value=100)

        # Get hard constraints
        hard = self.metrics.get_constraints(is_hard=True)
        self.assertGreaterEqual(len(hard), 1)
        for c in hard:
            self.assertTrue(c.is_hard)

        # Get soft constraints
        soft = self.metrics.get_constraints(is_hard=False)
        self.assertGreaterEqual(len(soft), 1)
        for c in soft:
            self.assertFalse(c.is_hard)

    def test_validate_against_hard_constraint(self):
        """Test validation against hard constraint"""
        self.metrics.add_constraint(
            constraint_type='memory',
            name='Min Cache',
            is_hard=True,
            minimum_value=2.0
        )

        # Below minimum (violates hard constraint)
        is_valid, msg = self.metrics.validate_against_constraints('memory', 1.5)
        self.assertFalse(is_valid)
        self.assertIn('Hard constraint', msg)

        # At minimum (passes)
        is_valid, msg = self.metrics.validate_against_constraints('memory', 2.0)
        self.assertTrue(is_valid)

        # Above minimum (passes)
        is_valid, msg = self.metrics.validate_against_constraints('memory', 3.0)
        self.assertTrue(is_valid)

    def test_validate_against_soft_constraint(self):
        """Test validation against soft constraint"""
        self.metrics.add_constraint(
            constraint_type='connections',
            name='Preferred Conn Limit',
            is_hard=False,
            maximum_value=100
        )

        # Exceeds soft maximum
        is_valid, msg = self.metrics.validate_against_constraints('connections', 150)
        self.assertFalse(is_valid)
        self.assertIn('Soft constraint', msg)


class TestBusinessWeighting(unittest.TestCase):
    """Test business metric weighting"""

    def setUp(self):
        """Create temporary metrics database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.metrics = BusinessMetrics(metrics_db_path=self.metrics_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_default_weights_loaded(self):
        """Test default business weights are loaded"""
        weights = self.metrics.get_all_weights()

        self.assertGreater(len(weights), 0)
        self.assertIn('latency', weights)
        self.assertIn('cost', weights)
        self.assertIn('availability', weights)

    def test_get_weight(self):
        """Test retrieving individual weight"""
        weight = self.metrics.get_business_weight('cost')
        self.assertGreater(weight, 0)

    def test_set_custom_weight(self):
        """Test setting custom business weight"""
        self.metrics.set_business_weight('custom_metric', 3.5, 'Very important')

        weight = self.metrics.get_business_weight('custom_metric')
        self.assertEqual(weight, 3.5)

    def test_weight_default_value(self):
        """Test unknown metric returns default weight"""
        weight = self.metrics.get_business_weight('nonexistent_metric')
        self.assertEqual(weight, 1.0)

    def test_calculate_weighted_impact_latency_only(self):
        """Test impact calculation with latency only"""
        impact = self.metrics.calculate_business_impact({'latency': 10})
        # latency weight is 1.0 by default
        self.assertEqual(impact, 10.0)

    def test_calculate_weighted_impact_cost_prioritized(self):
        """Test impact calculation with cost prioritized"""
        # Setup: cost valued 2x latency
        self.metrics.set_business_weight('latency', 1.0)
        self.metrics.set_business_weight('cost', 2.0)

        # Scenario: +10% latency, -20% cost
        impact = self.metrics.calculate_business_impact({
            'latency': 10,
            'cost': -20
        })

        # Expected: 10*1.0 + (-20)*2.0 = 10 - 40 = -30 (bad, cost reduction beats latency)
        self.assertEqual(impact, -30.0)

    def test_calculate_weighted_impact_availability_critical(self):
        """Test impact calculation with availability critical"""
        self.metrics.set_business_weight('latency', 1.0)
        self.metrics.set_business_weight('availability', 3.0)

        # Scenario: -5% latency, -1% availability
        impact = self.metrics.calculate_business_impact({
            'latency': -5,
            'availability': -1
        })

        # Expected: -5*1.0 + (-1)*3.0 = -5 - 3 = -8 (bad, availability loss critical)
        self.assertEqual(impact, -8.0)


class TestMetricsIntegration(unittest.TestCase):
    """Integration tests for complete metrics system"""

    def setUp(self):
        """Create temporary metrics database"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.metrics_db = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.metrics = BusinessMetrics(metrics_db_path=self.metrics_db)

    def tearDown(self):
        """Clean up"""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_complete_metrics_status(self):
        """Test complete metrics status retrieval"""
        status = self.metrics.get_metrics_status()

        self.assertGreater(status['sla_count'], 0)
        self.assertGreater(status['kpi_count'], 0)
        self.assertGreater(len(status['business_weights']), 0)

    def test_metrics_workflow(self):
        """Test complete workflow: check SLA, KPI, constraints, and weight impact"""
        # 1. Check SLA
        read_sla = self.metrics.get_sla_threshold('read')
        self.assertIsNotNone(read_sla)

        # 2. Check KPI
        read_kpi = self.metrics.get_kpi_target('read')
        self.assertIsNotNone(read_kpi)

        # 3. Add constraint
        self.metrics.add_constraint(
            'memory', 'Min Cache', is_hard=True, minimum_value=2.0
        )

        # 4. Validate against constraint
        is_valid, _ = self.metrics.validate_against_constraints('memory', 2.5)
        self.assertTrue(is_valid)

        # 5. Calculate weighted impact
        impact = self.metrics.calculate_business_impact({
            'latency': 5,
            'cost': -10,
            'availability': 0
        })

        self.assertIsInstance(impact, float)

    def test_business_case_cost_reduction(self):
        """Test real-world case: cost reduction with slight latency increase"""
        # Setup priorities: cost valued 2x latency
        self.metrics.set_business_weight('latency', 1.0)
        self.metrics.set_business_weight('cost', 2.0)

        # Candidate: +2% latency, -10% cost
        impact = self.metrics.calculate_business_impact({
            'latency': 2,
            'cost': -10
        })

        # Expected: 2*1.0 + (-10)*2.0 = 2 - 20 = -18
        # Negative because cost savings (2*10 = 20) > latency cost (2*1 = 2)
        # So this is a GOOD trade-off overall
        self.assertEqual(impact, -18.0)

        # Should be approved despite latency increase
        self.assertLess(impact, 0)  # Negative = cost reduction wins

    def test_business_case_uptime_critical(self):
        """Test real-world case: availability is critical"""
        # Setup priorities: availability valued 3x latency
        self.metrics.set_business_weight('latency', 1.0)
        self.metrics.set_business_weight('availability', 3.0)

        # Candidate: -8% latency, -0.5% availability
        impact = self.metrics.calculate_business_impact({
            'latency': -8,
            'availability': -0.5
        })

        # Expected: -8*1.0 + (-0.5)*3.0 = -8 - 1.5 = -9.5
        # Even though latency improves, availability loss is critical
        self.assertEqual(impact, -9.5)

        # Should NOT be approved due to uptime loss
        self.assertLess(impact, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
