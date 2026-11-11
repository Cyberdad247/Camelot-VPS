#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Unit tests for Phase H MetricsCollector
"""

import tempfile
import time
import unittest
from pathlib import Path

from phase_h_metrics import MetricsCollector


class TestMetricsCollector(unittest.TestCase):
    """Test MetricsCollector class"""

    def setUp(self):
        """Create temporary database for testing"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_metrics.db")
        self.collector = MetricsCollector(db_path=self.db_path, sample_rate=1.0)

    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()

    def test_init_creates_database(self):
        """Test that initialization creates database"""
        self.assertTrue(Path(self.db_path).exists())

    def test_record_operation_success(self):
        """Test recording successful operation"""
        result = self.collector.record_operation(
            operation_type='read',
            duration_ms=1.5,
            success=True
        )
        self.assertTrue(result)

    def test_record_operation_failure(self):
        """Test recording failed operation"""
        result = self.collector.record_operation(
            operation_type='write',
            duration_ms=2.1,
            success=False,
            error_message='timeout'
        )
        self.assertTrue(result)

    def test_record_operation_with_tags(self):
        """Test recording operation with metadata tags"""
        result = self.collector.record_operation(
            operation_type='route',
            duration_ms=0.5,
            success=True,
            tags={'agent_id': 'a1', 'workload': 'heavy'}
        )
        self.assertTrue(result)

    def test_get_statistics_empty(self):
        """Test statistics on empty database"""
        stats = self.collector.get_statistics(operation_type='nonexistent')
        self.assertEqual(stats['count'], 0)
        self.assertEqual(stats['status'], 'no data')

    def test_get_statistics_single_operation(self):
        """Test statistics with single operation"""
        self.collector.record_operation('read', 1.5, True)

        stats = self.collector.get_statistics(operation_type='read')
        self.assertEqual(stats['count'], 1)
        self.assertEqual(stats['success_count'], 1)
        self.assertEqual(stats['error_count'], 0)
        self.assertEqual(stats['error_rate'], 0.0)
        self.assertAlmostEqual(stats['avg_ms'], 1.5, places=2)

    def test_get_statistics_multiple_operations(self):
        """Test statistics with multiple operations"""
        latencies = [0.5, 1.0, 1.5, 2.0, 2.5]
        for latency in latencies:
            self.collector.record_operation('read', latency, True)

        stats = self.collector.get_statistics(operation_type='read')
        self.assertEqual(stats['count'], 5)
        self.assertEqual(stats['success_count'], 5)
        self.assertEqual(stats['error_count'], 0)
        self.assertAlmostEqual(stats['avg_ms'], 1.5, places=1)

    def test_get_statistics_with_errors(self):
        """Test statistics including error rate"""
        self.collector.record_operation('read', 1.0, True)
        self.collector.record_operation('read', 2.0, True)
        self.collector.record_operation('read', 3.0, False, 'timeout')

        stats = self.collector.get_statistics(operation_type='read')
        self.assertEqual(stats['count'], 3)
        self.assertEqual(stats['success_count'], 2)
        self.assertEqual(stats['error_count'], 1)
        self.assertAlmostEqual(stats['error_rate'], 0.333, places=2)

    def test_get_statistics_percentiles(self):
        """Test percentile calculations"""
        # Record 100 operations with known distribution
        for i in range(100):
            self.collector.record_operation('read', float(i), True)

        stats = self.collector.get_statistics(operation_type='read')

        # p50 should be around 50
        self.assertTrue(40 < stats['p50'] < 60)
        # p95 should be around 95
        self.assertTrue(85 < stats['p95'] < 100)
        # p99 should be around 99
        self.assertTrue(89 < stats['p99'] < 100)

    def test_get_statistics_time_window(self):
        """Test filtering by time window"""
        # Record old operation
        self.collector.record_operation('read', 1.0, True)
        _old_time = time.time()

        # Wait a bit and record new operation
        time.sleep(0.1)
        self.collector.record_operation('read', 2.0, True)

        # Query with small time window (only recent)
        stats = self.collector.get_statistics(operation_type='read', time_window_sec=0)
        self.assertEqual(stats['count'], 1)
        self.assertAlmostEqual(stats['avg_ms'], 2.0, places=1)

    def test_get_all_operation_stats(self):
        """Test getting stats for all operation types"""
        self.collector.record_operation('read', 1.0, True)
        self.collector.record_operation('read', 2.0, True)
        self.collector.record_operation('write', 3.0, True)
        self.collector.record_operation('route', 0.5, True)

        all_stats = self.collector.get_all_operation_stats()

        self.assertEqual(len(all_stats), 3)
        self.assertIn('read', all_stats)
        self.assertIn('write', all_stats)
        self.assertIn('route', all_stats)

        self.assertEqual(all_stats['read']['count'], 2)
        self.assertEqual(all_stats['write']['count'], 1)
        self.assertEqual(all_stats['route']['count'], 1)

    def test_cleanup_old_records(self):
        """Test cleanup of old records"""
        self.collector.record_operation('read', 1.0, True)

        # Verify record exists
        event_count = self.collector.get_event_count()
        self.assertEqual(event_count, 1)

        # Delete all records (keep 0 days)
        deleted = self.collector.cleanup_old_records(days_to_keep=0)
        self.assertEqual(deleted, 1)

        # Verify record is gone
        event_count = self.collector.get_event_count()
        self.assertEqual(event_count, 0)

    def test_get_event_count(self):
        """Test event count tracking"""
        self.assertEqual(self.collector.get_event_count(), 0)

        self.collector.record_operation('read', 1.0, True)
        self.collector.record_operation('write', 2.0, True)
        self.collector.record_operation('route', 0.5, True)

        self.assertEqual(self.collector.get_event_count(), 3)

    def test_sampling(self):
        """Test sampling reduces record count"""
        sampler = MetricsCollector(
            db_path=str(Path(self.temp_dir.name) / "test_sample.db"),
            sample_rate=0.1
        )

        # Record 100 operations, expect ~10 to be captured
        for _i in range(100):
            sampler.record_operation('read', 1.0, True)

        # Count should be less than 100 due to sampling
        count = sampler.get_event_count()
        self.assertLess(count, 100)
        self.assertGreater(count, 0)

    def test_export_csv(self):
        """Test CSV export"""
        self.collector.record_operation('read', 1.0, True)
        self.collector.record_operation('write', 2.0, False, 'timeout')

        export_path = str(Path(self.temp_dir.name) / "export.csv")
        count = self.collector.export_csv(export_path)

        self.assertEqual(count, 2)
        self.assertTrue(Path(export_path).exists())

        # Verify CSV content
        with open(export_path, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 3)  # header + 2 rows
            self.assertIn('read', lines[1])
            self.assertIn('write', lines[2])


if __name__ == '__main__':
    unittest.main()
