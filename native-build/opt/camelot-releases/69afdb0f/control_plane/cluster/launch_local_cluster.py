# SPDX-License-Identifier: MIT

"""
Launch a real 3-node CAMELOT-OS cluster on loopback and validate it.

Spawns three node daemons (127.0.0.1:8443/8444/8445) + one metrics daemon
(:8000), waits for health, then exercises the cluster for real:
  * consensus  — propose on the leader, confirm ALL nodes reach DECIDED
  * sync       — write on node_1, confirm replication to node_2 & node_3
  * agents     — confirm the global registry converges across nodes via gossip
  * metrics    — confirm Prometheus /metrics is live with camelot_* series

Prints a PASS/FAIL report and exits non-zero if any check fails.

Usage:
  python -m control_plane.cluster.launch_local_cluster          # validate then tear down
  python -m control_plane.cluster.launch_local_cluster --keep   # leave running
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

from .http_daemon import get_json, post_json

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"

NODES: List[Dict] = [
    {"id": "node_1", "port": 8443, "leader": True},
    {"id": "node_2", "port": 8444, "leader": False},
    {"id": "node_3", "port": 8445, "leader": False},
]
METRICS_PORT = 8000


def base_url(port: int) -> str:
    return f"http://{HOST}:{port}"


def peers_spec(self_id: str) -> str:
    return ",".join(
        f"{n['id']}={base_url(n['port'])}" for n in NODES if n["id"] != self_id
    )


def all_nodes_spec() -> str:
    return ",".join(f"{n['id']}={base_url(n['port'])}" for n in NODES)


def spawn_node(node: Dict) -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "control_plane.cluster.node_daemon",
        "--node-id", node["id"], "--host", HOST, "--port", str(node["port"]),
        "--peers", peers_spec(node["id"]),
    ]
    if node["leader"]:
        cmd.append("--leader")
    return subprocess.Popen(cmd, cwd=str(REPO_ROOT))


def spawn_metrics() -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "control_plane.cluster.metrics_daemon",
        "--port", str(METRICS_PORT), "--nodes", all_nodes_spec(),
    ]
    return subprocess.Popen(cmd, cwd=str(REPO_ROOT))


def wait_healthy(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    pending = {n["port"] for n in NODES}
    while time.time() < deadline and pending:
        for port in list(pending):
            code, _ = get_json(f"{base_url(port)}/health", timeout=1.5)
            if code == 200:
                pending.discard(port)
        if pending:
            time.sleep(0.5)
    return not pending


def poll(predicate, timeout: float = 8.0, interval: float = 0.3) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def check_consensus() -> Tuple[bool, str]:
    res = post_json(f"{base_url(8443)}/consensus/propose", {"entry": {"data": "validation_tx"}})
    if not res or "entry_id" not in res:
        return False, "leader did not accept proposal"

    def decided_everywhere() -> bool:
        for n in NODES:
            code, st = get_json(f"{base_url(n['port'])}/consensus/status")
            if code != 200 or not st or st.get("decided_count", 0) < 1:
                return False
        return True

    if poll(decided_everywhere, timeout=8.0):
        return True, "all 3 nodes reached DECIDED on the proposed entry"
    # Report what each node got to for diagnostics.
    states = []
    for n in NODES:
        _, st = get_json(f"{base_url(n['port'])}/consensus/status")
        states.append(f"{n['id']}:decided={st.get('decided_count') if st else '?'}")
    return False, "quorum not reached — " + ", ".join(states)


def check_sync() -> Tuple[bool, str]:
    res = post_json(f"{base_url(8443)}/sync/write", {"key": "user_profile", "value": "alice"})
    if not res or "event_id" not in res:
        return False, "node_1 did not accept write"

    def replicated() -> bool:
        ok_src = False
        peers_ok = 0
        for n in NODES:
            code, st = get_json(f"{base_url(n['port'])}/sync/status")
            if code != 200 or not st:
                return False
            if n["id"] == "node_1" and st.get("completed", 0) >= 1:
                ok_src = True
            if n["id"] != "node_1" and st.get("total_events", 0) >= 1:
                peers_ok += 1
        return ok_src and peers_ok == 2

    if poll(replicated, timeout=6.0):
        return True, "node_1 write completed L1→L1.5→L2 and replicated to node_2 & node_3"
    return False, "replication did not reach both peers"


def check_agents() -> Tuple[bool, str]:
    def converged() -> bool:
        for n in NODES:
            code, st = get_json(f"{base_url(n['port'])}/agents/status")
            if code != 200 or not st or st.get("global_agents", 0) < 6:
                return False
        return True

    if poll(converged, timeout=10.0):
        return True, "global registry converged to 6 agents on all nodes (gossip working)"
    counts = []
    for n in NODES:
        _, st = get_json(f"{base_url(n['port'])}/agents/status")
        counts.append(f"{n['id']}:{st.get('global_agents') if st else '?'}")
    return False, "registry did not converge — " + ", ".join(counts)


def check_metrics() -> Tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{base_url(METRICS_PORT)}/metrics", timeout=3) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return False, f"/metrics unreachable: {exc}"
    if "camelot_" in text:
        return True, "Prometheus /metrics live with camelot_* series"
    return False, "/metrics responded but no camelot_* series found"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="leave the cluster running")
    args = ap.parse_args()

    procs: List[subprocess.Popen] = []
    print("=" * 64)
    print("CAMELOT-OS — local 3-node cluster bring-up")
    print("=" * 64)
    try:
        for n in NODES:
            procs.append(spawn_node(n))
        procs.append(spawn_metrics())

        print("\nWaiting for nodes to report healthy ...")
        if not wait_healthy():
            print("❌ nodes never became healthy")
            return 2
        print("✅ all 3 nodes healthy\n")

        checks = [
            ("Consensus (real quorum)", check_consensus),
            ("Knowledge sync (replication)", check_sync),
            ("Agent registry (gossip)", check_agents),
            ("Metrics (Prometheus)", check_metrics),
        ]
        results = []
        for name, fn in checks:
            ok, detail = fn()
            results.append((name, ok, detail))
            print(f"{'✅' if ok else '❌'} {name}\n    {detail}")

        passed = sum(1 for _, ok, _ in results if ok)
        print("\n" + "-" * 64)
        print(f"RESULT: {passed}/{len(results)} checks passed")
        print("-" * 64)

        if args.keep:
            print("\n--keep set: cluster left running. Try:")
            print(f"  curl {base_url(8443)}/health")
            print(f"  curl {base_url(8443)}/consensus/status")
            print(f"  curl {base_url(METRICS_PORT)}/metrics")
            print("Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        return 0 if passed == len(results) else 1
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("\nCluster stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
