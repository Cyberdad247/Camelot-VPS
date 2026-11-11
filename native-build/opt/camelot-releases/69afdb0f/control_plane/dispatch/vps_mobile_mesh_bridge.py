# SPDX-License-Identifier: MIT
import base64
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

from control_plane.dispatch.edge_protocol import EdgeProtocol, ValidationResult, issue_snapshot

# --- HERMES_PRIME freshness (restored from 4d5bfebd after a merge regression) ---
# A cycle is treated as current for GRACE x cadence before the status degrades,
# so one slow or skipped run does not flap the dashboard.
HERMES_PRIME_CADENCE_S = 60
HERMES_PRIME_GRACE_MULTIPLIER = 3

PHIAL_STATE_PATH = os.path.join(
    os.path.dirname(__file__), '../../03_VAULT/runtime_state/hermes_prime_phial.json'
)


def read_phial_state() -> dict[str, Any]:
    """PhialEngine state as last written, or {} if absent or unreadable."""
    if not os.path.exists(PHIAL_STATE_PATH):
        return {}
    try:
        with open(PHIAL_STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"phial state unreadable: {e}")
        return {}


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        ts = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _latest_cycle(state: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Most recent memory entry carrying a parseable timestamp."""
    memory = state.get('memory') if isinstance(state, dict) else None
    if not isinstance(memory, list):
        return None
    for entry in reversed(memory):
        if isinstance(entry, dict) and _parse_ts(entry.get('ts')) is not None:
            return entry
    return None


def hermes_prime_status(
    state: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Derive liveness from the state the engine actually writes.

    Returns ALWAYS_ON_HUB only when a cycle landed inside the freshness window.
    Otherwise STALE (state present but old), UNPARSEABLE (state present, no
    usable timestamp) or NO_STATE (nothing written yet). Diagnostics ride along
    so a dashboard can show why, rather than just a degraded label.
    """
    if state is None:
        state = read_phial_state()
    if not isinstance(state, dict):
        state = {}
    if now is None:
        now = datetime.now(timezone.utc)

    memory = state.get('memory')
    result: dict[str, Any] = {
        "status": "NO_STATE",
        "cycles": len(memory) if isinstance(memory, list) else 0,
        "last_cycle_ts": None,
        "last_cycle_age_s": None,
        "fresh_within_s": HERMES_PRIME_CADENCE_S * HERMES_PRIME_GRACE_MULTIPLIER,
        "cadence_s": HERMES_PRIME_CADENCE_S,
    }

    latest = _latest_cycle(state)
    if latest is None:
        if result["cycles"]:
            result["status"] = "UNPARSEABLE"
        return result

    ts = _parse_ts(latest.get('ts'))
    if ts is None:  # pragma: no cover - _latest_cycle already guarantees a ts
        result["status"] = "UNPARSEABLE"
        return result

    age = (now - ts).total_seconds()
    result["last_cycle_ts"] = latest.get('ts')
    result["last_cycle_age_s"] = round(age, 3)
    result["status"] = "ALWAYS_ON_HUB" if age <= result["fresh_within_s"] else "STALE"
    return result

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
LOG = logging.getLogger('VpsMobileMeshBridge')

VPS_HOST = '162.35.107.134'
VPS_TAILSCALE_IP = '100.110.180.18'
FATHERS_CAMELOT_TAILSCALE = '100.121.48.49'
MOBILE_TAILSCALE_IP = '100.106.246.126'
LOCAL_CYBERTRONIA_IP = '100.118.224.52'
MOTO_TAILSCALE_IP = '100.89.129.105'
LOCAL_BIFROST_PORT = int(os.getenv('BIFROST_PORT', 3001))
BRIDGE_PORT = int(os.getenv('VPS_BRIDGE_PORT', 8095))
EDGE_ENVELOPE_HEADER = "x-camelot-edge-envelope"
_edge_protocol_cache: tuple[str, EdgeProtocol] | None = None

TOPOLOGY_PATH = os.path.join(os.path.dirname(__file__), '../../03_VAULT/runtime_state/sovereign_mesh_topology.json')

def load_mesh_topology() -> dict:
    if os.path.exists(TOPOLOGY_PATH):
        try:
            with open(TOPOLOGY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            LOG.warning(f"Failed to read topology file: {e}")
    try:
        from control_plane.infra.mesh_topology import canonical_topology_dict
        return canonical_topology_dict()
    except Exception:
        return {
            "system": "CAMELOT-OS Sovereign Autonomous Ecosystem",
            "nodes": {
                "cybertronia": {"tailscale_ip": LOCAL_CYBERTRONIA_IP, "role": "Primary Kinetic Execution Node"},
                "vashawns_s26_ultra": {"tailscale_ip": MOBILE_TAILSCALE_IP, "role": "Excalibur Command Center"},
                "fothers_camelot": {"tailscale_ip": FATHERS_CAMELOT_TAILSCALE, "role": "Secondary Windows Node"},
                "lakesha": {"tailscale_ip": "100.100.155.55", "role": "Lakisha Voice OS Host"},
                "motorola_moto_g_power": {"tailscale_ip": MOTO_TAILSCALE_IP, "role": "Auxiliary Mobile Sentinel"},
                "vps_hub_kvm563": {
                    "public_ip": VPS_HOST,
                    "tailscale_ip": VPS_TAILSCALE_IP,
                    "role": "Camelot-OS Sovereign Hub & Control Plane",
                    "governing_knights": ["HERMES_PRIME", "SIR_HEIMDALL"],
                    "always_on": True,
                }
            }
        }

def is_mesh_request_authorized(headers: dict, client_addr: str = "127.0.0.1") -> bool:
    """Require runtime mesh token OR valid Warp Gate Forever Keypass (Lady Alexandria / Heimdall)."""
    # 1. Warp Gate Forever Keypass check
    warp_keypass = headers.get("x-camelot-warp-keypass", "").strip()
    if warp_keypass:
        try:
            from control_plane.security.warp_gate import AlexandriaKeypassVault
            v = AlexandriaKeypassVault()
            kp = v.verify_keypass(warp_keypass)
            if kp:
                return True
        except Exception:
            pass

    # 2. Legacy mesh token check
    expected = os.getenv("MESH_BRIDGE_TOKEN", "").strip()
    provided = headers.get("x-camelot-token", "").strip()
    if expected and provided and hmac.compare_digest(provided, expected):
        return True
    return False


def is_tailnet_bind_host(host: str) -> bool:
    """Only permit the bridge to listen on a 100.64.0.0/10 Tailnet address."""
    parts = host.split(".")
    return len(parts) == 4 and all(part.isdigit() for part in parts) and 64 <= int(parts[1]) <= 127 and parts[0] == "100" and all(0 <= int(part) <= 255 for part in parts)


def _edge_protocol_from_environment() -> EdgeProtocol | None:
    global _edge_protocol_cache
    raw_registry = os.getenv("CAMELOT_EDGE_PUBLIC_KEYS_JSON", "")
    if not raw_registry:
        return None
    if _edge_protocol_cache and _edge_protocol_cache[0] == raw_registry:
        return _edge_protocol_cache[1]
    try:
        values = json.loads(raw_registry)
        public_keys = {
            str(device_id): base64.b64decode(str(public_key), validate=True)
            for device_id, public_key in values.items()
        }
        protocol = EdgeProtocol(public_keys)
    except (TypeError, ValueError, json.JSONDecodeError):
        LOG.error("CAMELOT_EDGE_PUBLIC_KEYS_JSON is invalid; edge routes remain closed")
        return None
    _edge_protocol_cache = (raw_registry, protocol)
    return protocol


def edge_request_authorized(headers: dict, *, now: int | None = None) -> ValidationResult:
    encoded = headers.get(EDGE_ENVELOPE_HEADER, "")
    if not encoded:
        return ValidationResult(False, "missing-edge-envelope")
    protocol = _edge_protocol_from_environment()
    if protocol is None:
        return ValidationResult(False, "edge-registry-unavailable")
    try:
        envelope = json.loads(base64.b64decode(encoded, validate=True))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ValidationResult(False, "malformed-edge-envelope")
    return protocol.validate_envelope(envelope, now=int(time.time()) if now is None else now)


class MeshBridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/v1/edge/snapshot":
            result = edge_request_authorized(self.headers)
            if not result.ok:
                self._send_json({"error": result.reason}, code=401, edge=True)
                return
            signing_key = os.getenv("CAMELOT_EDGE_SNAPSHOT_SIGNING_KEY_B64", "")
            if not signing_key:
                self._send_json({"error": "edge-snapshot-signer-unavailable"}, code=503, edge=True)
                return
            try:
                envelope = json.loads(base64.b64decode(self.headers[EDGE_ENVELOPE_HEADER], validate=True))
                snapshot = issue_snapshot(
                    device_id=str(envelope["device_id"]),
                    now=int(time.time()),
                    expires_at=int(time.time()) + 3600,
                    signing_key_b64=signing_key,
                )
            except (KeyError, TypeError, ValueError):
                self._send_json({"error": "edge-snapshot-issuance-failed"}, code=503, edge=True)
                return
            self._send_json(snapshot, edge=True)
            return
        if not is_mesh_request_authorized(self.headers):
            self._send_json({"error": "mesh bridge authentication failed"}, code=401)
            return
        if self.path in ['/mesh/status', '/', '/api/topology']:
            topology_data = load_mesh_topology()
            status = {
                'mesh_status': 'ONLINE',
                'timestamp': topology_data.get('timestamp'),
                'account': topology_data.get('tailscale_account', 'Cyberdad247@github'),
                'nodes': topology_data.get('nodes', {}),
                'bifrost_co_governors': ['HERMES_PRIME', "SIR_HEIMDALL"],
            }
            self._send_json(status)
        elif self.path in ['/bifrost/knights', '/api/bifrost/knights']:
            hermes = hermes_prime_status()
            knights = [
                {"id": "SIR_HEIMDALL", "role": "Bifrost Guardian & Boundary Sentinel", "status": "ALWAYS_ON_HUB"},
                {
                    "id": "HERMES_PRIME",
                    "role": "Always-on VPS Co-Pilot & MGV Synthesis",
                    "status": hermes["status"],
                    "last_cycle_age_s": hermes["last_cycle_age_s"],
                    "cycles": hermes["cycles"],
                },
                {"id": "SIR_LANCELOT", "role": "Kinetic Edge & Frontline Defense", "status": "ACTIVE_ESCORT"},
                {"id": "SIR_GALAHAD", "role": "Verification, Chivalric Purity & Z3 Formal Gate", "status": "ACTIVE_ESCORT"},
                {"id": "SIR_SENTINEL", "role": "AgentArmor, Zero-Trust Leases & Security Shield", "status": "ACTIVE_ESCORT"},
                {"id": "LADY_MNEMOSYNE", "role": "Living Memory Guardian & World Tree Spine", "status": "ACTIVE_ESCORT"},
                {"id": "SIR_HELIO", "role": "Voice OS & Phonetic Mesh Dispatch", "status": "ACTIVE_ESCORT"},
            ]
            self._send_json({"bifrost_knights": knights, "hub": "162.35.107.134"})
        elif self.path in ['/hermes/telemetry', '/api/hermes']:
            phial_state_path = os.path.join(os.path.dirname(__file__), '../../03_VAULT/runtime_state/hermes_prime_phial.json')
            phial_data = {}
            if os.path.exists(phial_state_path):
                try:
                    with open(phial_state_path, 'r', encoding='utf-8') as f:
                        phial_data = json.load(f)
                except Exception:
                    pass
            # Derived verdict served here (wiring contract; keys literal for the pin).
            hermes = hermes_prime_status()
            self._send_json({
                "agent": "HERMES_PRIME",
                "role": "VPS Hub Co-Pilot & Research Synthesis",
                "host": VPS_HOST,
                "phial_engine": phial_data,
                "status": hermes["status"],
                "last_cycle_ts": hermes["last_cycle_ts"],
                "last_cycle_age_s": hermes["last_cycle_age_s"],
                "cycles": hermes["cycles"],
                "fresh_within_s": hermes["fresh_within_s"],
                "cadence_s": hermes["cadence_s"],
            })
        elif self.path in ['/telemetry/cockpit', '/api/cockpit', '/excalibur/cockpit']:
            always_on_path = os.path.join(os.path.dirname(__file__), '../../03_VAULT/runtime_state/cybertronia_always_on.json')
            cockpit_state = {}
            if os.path.exists(always_on_path):
                try:
                    with open(always_on_path, 'r', encoding='utf-8') as f:
                        cockpit_state = json.load(f)
                except Exception:
                    pass
            self._send_json({
                "source": "cybertronia_always_on",
                "mobile_sentinel": MOBILE_TAILSCALE_IP,
                "cockpit": "Excalibur Command Center (S26 Ultra)",
                "live_state": cockpit_state or {"status": "ACTIVE_SENTINEL", "host": "cybertronia"},
            })
        elif self.path in ['/telemetry/moto', '/api/moto', '/moto/sentinel', '/api/sentinel/moto']:
            self._send_json({
                "source": "motorola_moto_g_power",
                "tailscale_ip": MOTO_TAILSCALE_IP,
                "designation": "AUXILIARY_MOBILE_SENTINEL",
                "role": "Auxiliary Mobile Sentinel & Backup Telemetry Relay",
                "model": "Motorola Moto G Power 5G (2024)",
                "status": "ONLINE_STANDBY",
                "active_ports": {"aux_sentinel_relay": 8092, "termux_ssh": 8023},
                "primary_cockpit_peer": MOBILE_TAILSCALE_IP,
                "mesh_gateway": f"http://{LOCAL_CYBERTRONIA_IP}:{BRIDGE_PORT}",
                "bifrost_port": LOCAL_BIFROST_PORT,
                "governing_knight": "SIR_HEIMDALL",
            })
        elif self.path in ['/mesh/nodes', '/api/mesh/nodes']:
            topology_data = load_mesh_topology()
            self._send_json({
                "account": topology_data.get('tailscale_account', 'Cyberdad247@github'),
                "nodes": topology_data.get('nodes', {}),
            })
        elif self.path in ['/heimdall/governance', '/api/heimdall']:
            gov_path = os.path.join(os.path.dirname(__file__), '../../03_VAULT/runtime_state/heimdall_bifrost_governance_latest.json')
            gov_data = {}
            if os.path.exists(gov_path):
                try:
                    with open(gov_path, 'r', encoding='utf-8') as f:
                        gov_data = json.load(f)
                except Exception:
                    pass
            self._send_json({"guardian": "SIR_HEIMDALL", "governance": gov_data})
        elif self.path in ['/v1/warp/keypasses', '/api/warp/keypasses']:
            from control_plane.security.warp_gate import AlexandriaKeypassVault
            v = AlexandriaKeypassVault()
            self._send_json({"warp_gate": "ONLINE", "keypasses": v.list_keypasses()})
        elif self.path in ['/v1/warp/audit', '/api/warp/audit']:
            from control_plane.security.warp_gate import _AUDIT_LOG_FILE
            entries = []
            if _AUDIT_LOG_FILE.exists():
                lines = _AUDIT_LOG_FILE.read_text(encoding="utf-8").strip().splitlines()[-25:]
                entries = [json.loads(line) for line in lines if line]
            self._send_json({"warp_gate_audit": entries})
        elif self.path in ['/watchtower/telemetry', '/api/watchtower', '/api/watchtower/telemetry']:
            wt_state = {}
            try:
                from control_plane.infra.watchtower import resource_snapshot
                snap = resource_snapshot(cpu_sample_s=0.1)
                server_ram_mb = round((snap.get("commit_total_bytes") or 0) / (1024 * 1024), 1)
                wt_state = {
                    "status": "ONLINE",
                    "commit_pct": snap.get("commit_pct"),
                    "physical_available_bytes": snap.get("physical_available_bytes"),
                    "cpu_pct": snap.get("cpu_pct"),
                    "server_memory_limit_mb": 8192,
                    "server_memory_used_mb": server_ram_mb,
                    "server_ceiling_ok": server_ram_mb <= 8192,
                    "governor": "ENFORCED",
                }
            except Exception as e:
                wt_state = {"status": "DEGRADED", "error": str(e)}

            hermes = hermes_prime_status()
            self._send_json({
                "node": "vps_hub_kvm563",
                "role": "CAMELOT_HUB_CONTROL_PLANE",
                "host": VPS_HOST,
                "watchtower": wt_state,
                "knights": {
                    "co_governors": ["HERMES_PRIME", "SIR_HEIMDALL"],
                    "hermes_prime": hermes,
                    "bifrost_status": "ACTIVE_3001",
                    "roster": [
                        {"id": "SIR_HEIMDALL", "status": "ALWAYS_ON_HUB", "role": "Bifrost Guardian & Boundary Sentinel"},
                        {"id": "HERMES_PRIME", "status": hermes.get("status", "ALWAYS_ON_HUB"), "role": "Always-on VPS Co-Pilot & MGV Synthesis"},
                        {"id": "SIR_FORGE", "status": "ACTIVE_ESCORT", "role": "SSU Reconciler & Builder"},
                        {"id": "SIR_SENTINEL", "status": "ACTIVE_ESCORT", "role": "Zero-Trust Armor & Integrity Gate"},
                        {"id": "LADY_APIS", "status": "ACTIVE_ESCORT", "role": "Bio-Kinetic Swarm Mother & NullClaw Conductor"},
                    ],
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path not in {"/v1/edge/receipts", "/v1/edge/outbox"}:
            self.send_response(404)
            self.end_headers()
            return
        result = edge_request_authorized(self.headers)
        if not result.ok:
            self._send_json({"error": result.reason}, code=401, edge=True)
            return
        self._send_json({"status": "accepted"}, edge=True)

    def _send_json(self, data: dict, code: int = 200, edge: bool = False):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        if not edge:
            self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))

def run_server():
    bind_host = os.getenv("VPS_BRIDGE_BIND_HOST", VPS_TAILSCALE_IP)
    if not is_tailnet_bind_host(bind_host):
        raise RuntimeError("VPS_BRIDGE_BIND_HOST must be a Tailnet 100.64.0.0/10 address")
    server = HTTPServer((bind_host, BRIDGE_PORT), MeshBridgeHandler)
    LOG.info(f'Full Mesh Bridge active on {bind_host}:{BRIDGE_PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == '__main__':
    run_server()
