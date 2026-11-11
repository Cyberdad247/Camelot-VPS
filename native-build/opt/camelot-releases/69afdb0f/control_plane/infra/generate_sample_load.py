#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""
Phase H Day 3: Generate Sample Load
Populates metrics database with realistic operation data for dashboard display
"""

import random
import time

from control_plane.phase_h_integration import get_metrics


def generate_reads(count: int = 100):
    """Generate read operations"""
    metrics = get_metrics()
    print(f"[LOAD] Generating {count} read operations...")

    for i in range(count):
        # Realistic read latency: 0.5-2ms
        duration_ms = random.uniform(0.5, 2.0)
        success = random.random() > 0.01  # 99% success rate

        metrics.record(
            'read',
            duration_ms,
            success=success,
            error_message="Connection timeout" if not success else None,
            tags={'table': random.choice(['jobs', 'blackboard', 'metrics']), 'operation': 'select'}
        )

        if (i + 1) % 20 == 0:
            print(f"  [{i + 1}/{count}] reads generated")


def generate_writes(count: int = 50):
    """Generate write operations"""
    metrics = get_metrics()
    print(f"[LOAD] Generating {count} write operations...")

    for i in range(count):
        # Realistic write latency: 1-5ms
        duration_ms = random.uniform(1.0, 5.0)
        success = random.random() > 0.02  # 98% success rate

        metrics.record(
            'write',
            duration_ms,
            success=success,
            error_message="Constraint violation" if not success else None,
            tags={'table': random.choice(['jobs', 'blackboard']), 'operation': 'insert'}
        )

        if (i + 1) % 10 == 0:
            print(f"  [{i + 1}/{count}] writes generated")


def generate_routes(count: int = 200):
    """Generate routing decisions"""
    metrics = get_metrics()
    print(f"[LOAD] Generating {count} routing operations...")

    for i in range(count):
        # Realistic routing latency: 0.01-0.1ms
        duration_ms = random.uniform(0.01, 0.1)
        success = True  # Routing always succeeds

        metrics.record(
            'route',
            duration_ms,
            success=success,
            tags={'intent': random.choice(['code_gen', 'orchestration', 'data_query']),
                  'knight': random.choice(['sir_forge', 'sir_boris', 'sir_sonus'])}
        )

        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{count}] routes generated")


def generate_compress(count: int = 30):
    """Generate compression operations"""
    metrics = get_metrics()
    print(f"[LOAD] Generating {count} compression operations...")

    for i in range(count):
        # Realistic compression latency: 0.1-2ms
        duration_ms = random.uniform(0.1, 2.0)
        success = True  # Compression always succeeds

        metrics.record(
            'compress',
            duration_ms,
            success=success,
            tags={'format': random.choice(['symbolect', 'json', 'toon'])}
        )

        if (i + 1) % 10 == 0:
            print(f"  [{i + 1}/{count}] compressions generated")


def print_metrics_summary():
    """Print collected metrics summary"""
    metrics = get_metrics()
    current_metrics = metrics.get_current_metrics()

    print("\n" + "=" * 80)
    print("📊 METRICS SUMMARY")
    print("=" * 80)

    if not current_metrics:
        print("  [No metrics collected]")
        return

    for op_type in sorted(current_metrics.keys()):
        stats = current_metrics[op_type]
        if stats.get('status') != 'ok':
            continue

        count = stats.get('count', 0)
        p50 = stats.get('p50', 0)
        p95 = stats.get('p95', 0)
        p99 = stats.get('p99', 0)
        error_rate = stats.get('error_rate', 0)

        print(f"\n{op_type.upper()}:")
        print(f"  Count:      {count}")
        print(f"  p50:        {p50:.4f}ms")
        print(f"  p95:        {p95:.4f}ms")
        print(f"  p99:        {p99:.4f}ms")
        print(f"  Error Rate: {error_rate:.2%}")

    # Health check
    health = metrics.get_health_status()
    print(f"\n💚 SYSTEM HEALTH: {health.get('status', 'unknown').upper()}")
    print(f"   {health.get('summary', 'N/A')}")

    print("=" * 80)


def main():
    """Generate sample load"""
    print("\n" + "=" * 80)
    print("🚀 PHASE H DAY 3: SAMPLE LOAD GENERATOR")
    print("=" * 80)

    start = time.time()

    # Generate operations
    generate_reads(100)
    generate_writes(50)
    generate_routes(200)
    generate_compress(30)

    elapsed = time.time() - start
    print(f"\n✅ Load generation complete in {elapsed:.2f}s")

    # Print summary
    time.sleep(1)  # Allow metrics to process
    print_metrics_summary()

    print("\n✅ Sample load ready for dashboard display")
    print("   Run: python dashboards/phase_h_live_dashboard.py --mode once")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
