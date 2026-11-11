# KBA Drone Node — Deployment Runbook

A Camelot-OS **empire-drone** on the tailnet that serves **KickBox Audio (KBA)**
services and executes *only* through the governed bifrost→sandbox bridge. Every
command is HMAC-authenticated, signature-verified, governance-checked, and audited
before a real KBA tool runs.

## Mesh placement
Per `01_KERNEL/mesh/node_c/tailnet-policy.example.hujson`:

```
tag:omni-router ──dispatch──▶ tag:empire-drone (KBA drone, ports 9000-9100)
```
Drones can't reach each other; only the omni-router and knights reach them, over
the tailnet only. The drone binds its **tailnet IP** — never `0.0.0.0`.

## What runs
- `control_plane/drone_node.py` — the node (HTTP: `/health`, `/kba/tools`, `/bifrost/dispatch`)
- `02_FORGE/cartridge/kba_tools.py` — governed KBA tools: `kba.status`, `kba.echo`, `kba.tts`, `kba.transcribe`, `kba.voices`
- On boot it writes a **signed** `KBA_CORE` cartridge (allows the KBA tools + `echo`/`utc_now`)

## Deploy (on the kba-services box)
```bash
export WEBHOOK_SECRET='<shared-hmac-secret>'          # same value the omni-router signs with
export CAMELOT_CARTRIDGE_HMAC_KEY='<cartridge-signing-key>'   # or: python -m cartridge.cartridge_crypto keygen
export TS_AUTHKEY='tskey-...'                          # optional: reusable/ephemeral tailnet key
export OMNI_ROUTER_URL='http://<omni-router-tailnet-ip>'  # optional: auto-register

bash bin/kba_drone_boot.sh
```
The script runs `tailscale up --advertise-tags=tag:empire-drone`, auto-detects the
box's tailnet IP (`tailscale ip -4`), and binds the drone there. To force a specific
IP: `KBA_DRONE_HOST=100.125.205.66 bash bin/kba_drone_boot.sh`.

> **IP note:** as of this writing the tailnet shows `kba-services` at `100.71.218.75`
> (offline). The drone binds whatever IP the box actually has when it boots, so you
> don't need to hardcode `100.125.205.66` — but if you want to pin it, set
> `KBA_DRONE_HOST`. Confirm reachability from the control plane with
> `tailscale ping <ip>` before dispatching.

## Dispatch a governed command (from the control plane / omni-router)
```python
from control_plane.drone_node import dispatch_to_drone
r = dispatch_to_drone("http://100.125.205.66:9000", "KBA_CORE", "kba.status", {},
                      principal="sir_boris", secret=WEBHOOK_SECRET)
# r["status"] == "success", r["simulated"] is False, r["result"]["backends"] = {...}
```
Or raw over the wire — POST to `/bifrost/dispatch`:
```json
{"body": "<json:{cartridge_id,tool_id,params,principal}>", "signature": "<hmac-sha256-hex>"}
```

## Enforcement (verified)
| Attempt | Result |
|---|---|
| Valid signed dispatch, allowed tool | `success` + real output |
| Forged / missing HMAC | `BridgeAuthFailure` |
| Tool not in `KBA_CORE.allowed_tools` | `SecurityViolation` |
| Tampered manifest | `SignatureViolation` |
| Unknown cartridge | `UnknownCartridge` |
| `--enterprise-trust` + revoked cartridge | `SignatureViolation` |
| `--rbac` + `HITL_required`, non-approver principal | `HITLRequired` |

## Hardening flags
- `--enterprise-trust` — key-id rotation / revocation / tamper-evident audit (needs `~/.camelot/trust_store.json`)
- `--rbac` — lifecycle RBAC (needs `~/.camelot/cartridge_rbac.json`)
Both auto-enable in `kba_drone_boot.sh` if their config files exist.

## Health check
```bash
curl http://<drone-tailnet-ip>:9000/health
```

## Tests
```bash
python control_plane/test_drone_node.py        # boots on loopback, drives the full path
```
