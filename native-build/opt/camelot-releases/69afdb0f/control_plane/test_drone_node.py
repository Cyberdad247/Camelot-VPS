# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Test Suite — KBA Drone Node (governed dispatch over HTTP).

Boots the drone on loopback (not the tailnet IP, for testability), then drives it
through the same signed /bifrost/dispatch path the omni-router uses over the tailnet.

Run:  python control_plane/test_drone_node.py
"""
import os
import socket
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
os.environ["WEBHOOK_SECRET"] = "drone-test-webhook"
os.environ["CAMELOT_CARTRIDGE_HMAC_KEY"] = "drone-test-cartridge"

from control_plane.cluster.http_daemon import get_json
from control_plane.drone_node import KBA_CARTRIDGE_ID, KbaDroneNode, dispatch_to_drone

SECRET = os.environ["WEBHOOK_SECRET"]


def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


def main() -> int:
    port = _free_port()
    pkgs = tempfile.mkdtemp(prefix="camelot_drone_pkgs_")
    node = KbaDroneNode("kba-drone-test", "127.0.0.1", port, packages_dir=pkgs)
    node.start()
    url = f"http://127.0.0.1:{port}"
    failures = 0

    def check(name, cond, extra=""):
        nonlocal failures
        ok = bool(cond)
        if not ok:
            failures += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {extra}" if extra and not ok else ""))

    try:
        # health
        code, health = get_json(f"{url}/health")
        check("health 200 + empire-drone role", code == 200 and health.get("role") == "empire-drone", str(health))
        check("KBA cartridge advertised", health.get("cartridge") == KBA_CARTRIDGE_ID)
        check("kba tools present", "kba.status" in health.get("tools", []))

        # tools listing
        _, tools = get_json(f"{url}/kba/tools")
        check("kba.tts in tool list", "kba.tts" in tools.get("tools", []))

        # valid signed governed dispatch → REAL execution
        r = dispatch_to_drone(url, KBA_CARTRIDGE_ID, "kba.status", {},
                              principal="sir_boris", secret=SECRET)
        check("governed kba.status success", r.get("status") == "success", str(r))
        check("real execution (not simulated)", r.get("simulated") is False, str(r))
        check("kba.status returned backends", "backends" in (r.get("result") or {}), str(r.get("result")))

        # echo builtin allowed by KBA cartridge
        r2 = dispatch_to_drone(url, KBA_CARTRIDGE_ID, "kba.echo", {"value": "ping"}, secret=SECRET)
        check("kba.echo roundtrip", (r2.get("result") or {}).get("pong") == "ping", str(r2))

        # bad HMAC → rejected at the bridge (401)
        r3 = dispatch_to_drone(url, KBA_CARTRIDGE_ID, "kba.status", {}, secret="wrong-secret")
        check("bad bridge signature rejected", r3.get("violation") == "BridgeAuthFailure", str(r3))

        # tool NOT in the KBA cartridge's allowed_tools → governance blocks it
        r4 = dispatch_to_drone(url, KBA_CARTRIDGE_ID, "http_get",
                               {"url": "http://example.com"}, secret=SECRET)
        check("ungoverned tool blocked", r4.get("violation") == "SecurityViolation", str(r4))

        # unknown cartridge
        r5 = dispatch_to_drone(url, "NO_SUCH", "kba.status", {}, secret=SECRET)
        check("unknown cartridge rejected", r5.get("violation") == "UnknownCartridge", str(r5))

    finally:
        node.daemon.stop()

    print(f"\n{'🏆 ALL PASSED' if failures == 0 else f'❌ {failures} FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    print("🧪 KBA Drone Node")
    raise SystemExit(main())
