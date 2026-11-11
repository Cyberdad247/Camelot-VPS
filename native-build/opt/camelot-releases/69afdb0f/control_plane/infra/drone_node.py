# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
KBA Drone Node — a Camelot-OS empire-drone on the tailnet
=========================================================
A remote worker node (tailnet ``tag:empire-drone``) that serves KickBox Audio
services and executes ONLY through the governed bifrost→sandbox bridge. Every
command it accepts is HMAC-authenticated, signature-verified, governance-checked,
and audited before a real KBA tool runs.

Placement in the empire mesh (see 01_KERNEL/mesh/node_c/tailnet-policy.example.hujson):
    tag:omni-router  ──dispatch──▶  tag:empire-drone  (this node, ports 9000-9100)
Drones cannot reach each other; only the omni-router and knights reach them, over
the tailnet only. Bind to the drone's tailnet IP (e.g. 100.125.205.66), never 0.0.0.0.

Endpoints
    GET  /health            node + KBA + bridge status
    GET  /kba/tools         list governed tool ids
    POST /bifrost/dispatch  {"body": "<signed-json>", "signature": "<hex>"}
                            body = {"cartridge_id","tool_id","params","principal"}

Run (on the drone, after `tailscale up --advertise-tags=tag:empire-drone`):
    WEBHOOK_SECRET=... CAMELOT_CARTRIDGE_HMAC_KEY=... \
    python -m control_plane.drone_node --node-id kba-drone-1 \
        --host 100.125.205.66 --port 9000

Dispatch to it from the control plane:
    from control_plane.drone_node import dispatch_to_drone
    dispatch_to_drone("http://100.125.205.66:9000", "KBA_CORE", "kba.status", {},
                      principal="sir_boris", secret=WEBHOOK_SECRET)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from cartridge import cartridge_crypto as cc  # noqa: E402
from cartridge.cartridge_schemas import CartridgeManifest  # noqa: E402
from cartridge.kba_tools import KBA_TOOL_IDS, register_kba_tools  # noqa: E402
from cartridge.tool_registry import ToolRegistry  # noqa: E402

# Bridge core lives in 02_FORGE/cartridge (excluded from packaging); the adapter
# path-inserts it. Import the adapter first so `cartridge.*` resolves afterwards.
from control_plane.bifrost_sandbox_adapter import build_bridge, sign_body  # noqa: E402
from control_plane.cluster.http_daemon import HttpDaemon, post_json  # noqa: E402

# Sir Heimdall (perimeter guardian) + CloudBrain L2 (NotebookLM) — both optional,
# both degrade gracefully so the drone runs even if they're unavailable.
try:
    from control_plane import heimdall_watch  # noqa: E402
except Exception:  # noqa: BLE001
    heimdall_watch = None
try:
    from control_plane import cloudbrain_sync  # noqa: E402
except Exception:  # noqa: BLE001
    cloudbrain_sync = None

KBA_CARTRIDGE_ID = "KBA_CORE"
DEFAULT_TAILNET_HOST = "100.125.205.66"
DEFAULT_PORT = 9000  # empire-drone worker range (9000-9100)


def ensure_kba_cartridge(packages_dir: str | Path) -> Path:
    """
    Make the drone turnkey: ensure a SIGNED KBA_CORE manifest exists on disk that
    allows the KBA tools + safe built-ins. Signed with this drone's cartridge key
    (CAMELOT_CARTRIDGE_HMAC_KEY / Ed25519), so the sandbox will honor it in STRICT.
    """
    base = Path(packages_dir)
    pkg = base / KBA_CARTRIDGE_ID
    pkg.mkdir(parents=True, exist_ok=True)
    manifest_path = pkg / "manifest.json"

    allowed = list(KBA_TOOL_IDS) + ["echo", "utc_now", "heimdall.scan"]
    m = CartridgeManifest(
        cartridge_id=KBA_CARTRIDGE_ID,
        description="KickBox Audio services (governed)",
        signature="pending",
        risk_profile="medium",
        governance={"allowed_tools": allowed},
    )
    m.signature = cc.sign(m)  # real signature (raises if no key configured)
    dump = m.model_dump_json(indent=2) if hasattr(m, "model_dump_json") else m.json(indent=2)
    manifest_path.write_text(dump, encoding="utf-8")
    return manifest_path


class KbaDroneNode:
    def __init__(self, node_id: str, host: str, port: int, *,
                 packages_dir: Optional[str] = None,
                 enterprise_trust: bool = False, rbac: bool = False,
                 register_url: Optional[str] = None):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.register_url = register_url
        self.started = time.time()

        self.packages_dir = packages_dir or os.getenv("CAMELOT_CARTRIDGE_PACKAGES") \
            or str(Path(__file__).resolve().parent.parent / "02_FORGE" / "cartridge" / "packages")
        ensure_kba_cartridge(self.packages_dir)

        # Registry = safe built-ins + KBA services (+ Sir Heimdall if present).
        self.registry = ToolRegistry(with_builtins=True)
        register_kba_tools(self.registry)
        self._last_heimdall: Dict[str, Any] = {"status": "not yet scanned"}
        self._heimdall_thread = None
        self._heimdall_on = heimdall_watch is not None and heimdall_watch.available()
        self._cloudbrain_on = cloudbrain_sync is not None
        if self._heimdall_on:
            self.registry.register("heimdall.scan", heimdall_watch.heimdall_scan_tool)

        self.bridge = build_bridge(
            registry=self.registry,
            enterprise_trust=enterprise_trust,
            rbac=rbac,
            packages_dir=self.packages_dir,
        )

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self.daemon = HttpDaemon(host, port, self._loop)
        self._wire_routes()

    def _wire_routes(self) -> None:
        self.daemon.route("GET", "/health", self._health)
        self.daemon.route("GET", "/kba/tools", self._tools)
        self.daemon.route("GET", "/heimdall/status", self._heimdall_status)
        self.daemon.route("POST", "/bifrost/dispatch", self._dispatch)

    # ── handlers: fn(body: dict, loop) -> (status_code, obj) ───────────────────
    def _health(self, _body: dict, _loop) -> tuple[int, dict]:
        return 200, {
            "status": "healthy",
            "node_id": self.node_id,
            "role": "empire-drone",
            "service": "KickBox Audio",
            "tailnet_host": self.host,
            "port": self.port,
            "uptime_seconds": round(time.time() - self.started, 1),
            "cartridge": KBA_CARTRIDGE_ID,
            "tools": self.registry.tool_ids,
            "governance": "STRICT",
            "heimdall": self._heimdall_on,
            "cloudbrain": self._cloudbrain_on,
        }

    def _tools(self, _body: dict, _loop) -> tuple[int, dict]:
        return 200, {"cartridge": KBA_CARTRIDGE_ID, "tools": self.registry.tool_ids}

    def _heimdall_status(self, _body: dict, _loop) -> tuple[int, dict]:
        return 200, {"watcher": "SIR_HEIMDALL", "active": self._heimdall_on,
                     "cloudbrain": self._cloudbrain_on, "last_report": self._last_heimdall}

    def _dispatch(self, body: dict, _loop) -> tuple[int, dict]:
        raw = body.get("body")
        sig = body.get("signature", "")
        if not isinstance(raw, str):
            return 400, {"status": "error", "violation": "BadRequest",
                         "error": "expected {'body': <signed-json-string>, 'signature': <hex>}"}
        # Signed-RPC semantics: HTTP 200 means "dispatch was received and adjudicated".
        # The governance verdict (success / violation) is in the JSON body, so callers
        # read result['status'] / result['violation'] rather than the HTTP code — this
        # also avoids urllib treating a denial as a transport failure.
        return 200, self.bridge.handle_signed(raw, sig)

    # ── lifecycle ──────────────────────────────────────────────────────────────
    def start(self) -> None:
        self.daemon.start()
        print(f"[{self.node_id}] KBA drone listening on http://{self.host}:{self.port} "
              f"(cartridge={KBA_CARTRIDGE_ID}, tools={len(self.registry.tool_ids)})", flush=True)
        self._post_heimdall()
        if self.register_url:
            self._register_with_router()

    # ── Sir Heimdall: guardian of the Bifrost, reporting up to CloudBrain ───────
    def _sync_heimdall_to_cloudbrain(self, report: Dict[str, Any]) -> None:
        """Route a Heimdall report up to CloudBrain L2 (NotebookLM). Never raises."""
        if cloudbrain_sync is None:
            report["cloudbrain"] = "unavailable"
            return
        try:
            res = cloudbrain_sync.sync_after_event(
                event_type="heimdall_watch", command="perimeter_scan", results=report)
            report["cloudbrain"] = ("queued" if res.get("error")
                                    else "synced" if res.get("triggered") else "off")
        except Exception as e:  # noqa: BLE001
            report["cloudbrain"] = f"error:{type(e).__name__}"

    def _post_heimdall(self) -> None:
        """Activate Sir Heimdall: initial scan + CloudBrain sync, then continuous watch."""
        if not self._heimdall_on:
            print(f"[{self.node_id}] Sir Heimdall unavailable — perimeter watch off", flush=True)
            return
        try:
            rep = heimdall_watch.heimdall_scan_tool({})
            self._sync_heimdall_to_cloudbrain(rep)
            self._last_heimdall = rep
            print(f"[{self.node_id}] ⚔️ Sir Heimdall posted at the Bifrost — "
                  f"{rep.get('vector_count')} vectors ({rep.get('critical')} critical), "
                  f"cloudbrain={rep.get('cloudbrain')}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[{self.node_id}] Heimdall initial scan failed: {e}", flush=True)

        def _on_report(report: Dict[str, Any]) -> None:
            self._sync_heimdall_to_cloudbrain(report)
            self._last_heimdall = report

        self._heimdall_thread = heimdall_watch.start_heimdall_watch(
            interval_seconds=int(os.getenv("HEIMDALL_INTERVAL", "360")),
            on_report=_on_report)

    def _register_with_router(self) -> None:
        payload = {"node_id": self.node_id, "role": "empire-drone",
                   "url": f"http://{self.host}:{self.port}", "service": "KickBox Audio",
                   "tools": self.registry.tool_ids}
        resp = post_json(f"{self.register_url.rstrip('/')}/nodes/register", payload, retries=2)
        print(f"[{self.node_id}] registration -> {self.register_url}: "
              f"{'ok' if resp else 'unreachable (will retry on next boot)'}", flush=True)

    def serve_forever(self) -> None:
        self.start()
        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.daemon.stop()


# ── control-plane client: dispatch a governed command to a drone ──────────────
def dispatch_to_drone(drone_url: str, cartridge_id: str, tool_id: str,
                      params: Optional[Dict[str, Any]] = None, *,
                      principal: Optional[str] = None,
                      secret: Optional[str] = None, timeout: float = 10.0) -> Dict[str, Any]:
    """Sign a governed dispatch and POST it to a drone's /bifrost/dispatch."""
    secret = secret if secret is not None else os.getenv("WEBHOOK_SECRET", "")
    raw = json.dumps({"cartridge_id": cartridge_id, "tool_id": tool_id,
                      "params": params or {}, "principal": principal})
    envelope = {"body": raw, "signature": sign_body(raw, secret)}
    resp = post_json(f"{drone_url.rstrip('/')}/bifrost/dispatch", envelope, timeout=timeout, retries=1)
    return resp if resp is not None else {"status": "error", "error": "drone unreachable"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Camelot-OS KBA drone node")
    ap.add_argument("--node-id", default="kba-drone-1")
    ap.add_argument("--host", default=os.getenv("KBA_DRONE_HOST", DEFAULT_TAILNET_HOST),
                    help="tailnet IP to bind (default the KBA drone tailnet address)")
    ap.add_argument("--port", type=int, default=int(os.getenv("KBA_DRONE_PORT", DEFAULT_PORT)))
    ap.add_argument("--packages-dir", default=None)
    ap.add_argument("--enterprise-trust", action="store_true",
                    help="use TrustManager (kid rotation / revocation / audit)")
    ap.add_argument("--rbac", action="store_true", help="enforce lifecycle RBAC")
    ap.add_argument("--register-url", default=os.getenv("OMNI_ROUTER_URL"),
                    help="omni-router base URL to register this drone with")
    args = ap.parse_args()

    if not os.getenv("WEBHOOK_SECRET"):
        print("[warn] WEBHOOK_SECRET not set — dispatch auth will reject everything.", flush=True)
    if not (os.getenv("CAMELOT_CARTRIDGE_HMAC_KEY") or os.getenv("CAMELOT_CARTRIDGE_PRIVATE_KEY")):
        print("[fatal] no cartridge signing key — cannot sign the KBA manifest. "
              "Set CAMELOT_CARTRIDGE_HMAC_KEY or run cartridge_crypto keygen.", flush=True)
        raise SystemExit(2)

    node = KbaDroneNode(args.node_id, args.host, args.port,
                        packages_dir=args.packages_dir,
                        enterprise_trust=args.enterprise_trust, rbac=args.rbac,
                        register_url=args.register_url)
    node.serve_forever()


if __name__ == "__main__":
    main()
