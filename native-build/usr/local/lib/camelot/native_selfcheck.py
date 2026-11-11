#!/usr/bin/env python3
"""Native-topology selfcheck for the Camelot hub (serve-mode build).
Replaces the container-era selfcheck, which fails by design drift (it expects
Qdrant/Postgres that the minimal native topology deliberately dropped).

Asserts the surfaces verified live on 2026-11-07/08:
  Hermes serve API :8642, Camelot Bifrost operator API :3001, mesh bridge
  :8095 /mesh/status (token read on-box from /etc/camelot/mesh.env, never
  printed), Redis :6379 PING, BoB gateway :8102 (validation 400 = alive),
  Watchtower tick freshness (state file mtime, CONFIRM_ON_BOX path).
Exit 0 = all green. Prints one line per check + a JSON summary line.
Stdlib only.
"""
import json, os, socket, sys, time, urllib.request, urllib.error

RESULTS = []

def check(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": str(detail)[:120]})
    print(f"{'OK ' if ok else 'FAIL'} {name} {detail}".rstrip())

def http(url, headers=None, timeout=6, method="GET", body=None):
    req = urllib.request.Request(url, headers=headers or {}, method=method,
                                 data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, str(e)[:80]

# Hermes serve API — /api/status answered without login in the native build
st, body = http("http://127.0.0.1:8642/api/status")
check("hermes-serve :8642 /api/status", st == 200, f"http {st}")

# Bifrost operator API :3001 — any structured answer (incl. 401) proves the listener
st, _ = http("http://127.0.0.1:3001/v1/operator/status")
check("bifrost-operator :3001", st is not None and st < 500, f"http {st}")

# Mesh bridge :8095 /mesh/status with the on-box token (value never printed)
token = ""
try:
    for line in open("/etc/camelot/mesh.env"):
        if "=" in line and ("TOKEN" in line.split("=")[0].upper()):
            token = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
except Exception as e:
    check("mesh-bridge :8095", False, f"mesh.env unreadable: {e}")
    token = None
if token is not None:
    st, body = http("http://100.110.180.18:8095/mesh/status",
                    headers={"x-camelot-token": token})
    check("mesh-bridge :8095 /mesh/status", st == 200, f"http {st}")

# Redis PING
try:
    s = socket.create_connection(("127.0.0.1", 6379), timeout=4)
    s.sendall(b"PING\r\n")
    resp = s.recv(64).decode(errors="replace")
    s.close()
    check("redis :6379", "PONG" in resp, resp.strip())
except Exception as e:
    check("redis :6379", False, str(e)[:80])

# BoB gateway :8102 — POST /chat with no messages must answer 400 (alive + validating)
st, _ = http("http://127.0.0.1:8102/chat", method="POST",
             headers={"Content-Type": "application/json"}, body=b"{}")
check("bob-gateway :8102", st == 400, f"http {st} (400 = alive)")

# Watchtower tick freshness — CONFIRM_ON_BOX: state path in the native build
WT_STATE = os.environ.get("CAMELOT_WT_STATE", "/opt/camelot-state/runtime_state/harness_heartbeat.jsonl")
try:
    age = time.time() - os.path.getmtime(WT_STATE)
    check("watchtower tick fresh", age < 300, f"state age {int(age)}s")
except Exception as e:
    check("watchtower tick fresh", False, f"state file: {e}")

ok = all(r["ok"] for r in RESULTS)
print(json.dumps({"selfcheck": "native", "ok": ok, "results": RESULTS}))
sys.exit(0 if ok else 1)
