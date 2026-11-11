# SPDX-License-Identifier: MIT

"""
CAMELOT-OS metrics daemon.

Wraps MetricsCollector (which already binds a real Prometheus /metrics server via
start_http_server) and keeps the process alive while periodically scraping each
node's /consensus/status and /agents/status to populate real gauge values.

Usage:
  python -m control_plane.cluster.metrics_daemon --port 8000 \
      --nodes "node_1=http://127.0.0.1:8443,node_2=http://127.0.0.1:8444,node_3=http://127.0.0.1:8445"
"""

from __future__ import annotations

import argparse
import time

from control_plane.metrics_collector import MetricsCollector

from .http_daemon import get_json
from .node_daemon import parse_peers


def main() -> None:
    ap = argparse.ArgumentParser(description="CAMELOT-OS metrics daemon")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--nodes", default="", help="id=url,id=url")
    ap.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args()

    _, node_addrs = parse_peers(args.nodes)
    collector = MetricsCollector(port=args.port)
    print(f"[metrics] /metrics on http://127.0.0.1:{args.port}  scraping {list(node_addrs)}", flush=True)

    while True:
        for node_id, base in node_addrs.items():
            code, cstat = get_json(f"{base}/consensus/status")
            if code == 200 and cstat:
                collector.consensus_log_size.labels(node_id=node_id).set(cstat.get("log_size", 0))

            code, astat = get_json(f"{base}/agents/status")
            if code == 200 and astat:
                collector.update_agent_count(
                    node_id, astat.get("healthy", 0), astat.get("global_agents", 0)
                )
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
