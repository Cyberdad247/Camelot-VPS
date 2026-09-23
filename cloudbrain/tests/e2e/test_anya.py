#!/usr/bin/env python3
"""E2E: Anya Omega routing + policy verification (stdlib only).

Part of the CAMELOT_OS cloudbrain/ production-hardening pack (cloudbrain/tests/e2e/).
Adapted from the local staging pack; see the staging source of record.
VPS run: upload to /opt/data/scripts/, execute via a no-agent cron job, read results at /opt/data/cron/output/{id}/.

Runs on the VPS via the cron pattern (loopback only, no DNS):
  python3 /opt/data/scripts/e2e/test_anya.py

Covers gates:
  V-CAP-002 - capability registry: ephemeral knight registers with declared
              capabilities; the registry reflects them.
  V-MESH-008 - digest-attached delivery: a routed proposal arrives at the
              knight's broker queue with Symbollect wire + sha256 digest; the
              digest is recomputed from the canonical form and must match.
  V-MESH-006 - authority-minting quarantine: a `grant`-type message is
              quarantined by policy and never delivered.

The Symbollect codec is imported from the VPS's own
/opt/data/cloudbrain/handoff/symbollect.py (override with SYMBOLLECT_PATH);
V-MESH-008 FAILs if the codec is missing, since digest verification then has
no reference implementation.

The ephemeral knight name is unique per run. The registry file is durable, so
cleanup attempts DELETE /knights/{knight} but treats 404/405 as a WARN (see
README.md known limitations).

Output contract: lines like `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>`,
then `--- JSON SUMMARY ---` and a JSON report. Exit 0 iff no FAIL.
"""
import datetime
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ANYA = "http://127.0.0.1:8003"
MESH = "http://127.0.0.1:8002"
SYMBOLLECT_PATH = os.environ.get("SYMBOLLECT_PATH", "/opt/data/cloudbrain/handoff")
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
TOKEN = secrets.token_hex(4)
KNIGHT = "e2e-knight-%s" % TOKEN
QUEUE = "e2e-anya-%s" % TOKEN
CONSUMER = "e2e-ac-%s" % TOKEN
CAPS = ["e2e-probe", "symbollect-v1"]
STARTED = datetime.datetime.now(datetime.timezone.utc).isoformat()
RESULTS = []


def _rec(gate, name, status, detail=""):
    RESULTS.append({"gate": gate, "check": name, "status": status, "detail": detail})
    line = "%s %s %s" % (status, gate, name)
    if detail and status in ("FAIL", "SKIP", "WARN"):
        line += " | %s" % detail
    print(line, flush=True)


def check(gate, name, ok, detail=""):
    _rec(gate, name, "PASS" if ok else "FAIL", detail)
    return bool(ok)


def warn(gate, name, detail=""):
    _rec(gate, name, "WARN", detail)


def finish():
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "WARN": 0}
    for r in RESULTS:
        counts[r["status"]] += 1
    report = {
        "script": "test_anya.py",
        "run_id": RUN_ID,
        "started_utc": STARTED,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "results": RESULTS,
        "summary": counts,
        "verdict": "PASS" if counts["FAIL"] == 0 else "FAIL",
    }
    print("--- JSON SUMMARY ---", flush=True)
    print(json.dumps(report, indent=2), flush=True)
    sys.exit(0 if counts["FAIL"] == 0 else 1)


def http(base, method, path, body=None, query=None, timeout=10):
    """Returns (status:int|None, parsed:dict|list, raw:str)."""
    url = base + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = {"_raw": raw}
            return resp.status, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {"_raw": raw}
        return e.code, parsed, raw
    except Exception as e:  # noqa: BLE001
        return None, {"_error": "%s: %s" % (type(e).__name__, e)}, ""


def pick(d, *names):
    if isinstance(d, dict):
        for n in names:
            if d.get(n) not in (None, ""):
                return d[n]
    return None


def load_symbollect():
    """Import the VPS's own symbollect codec; returns module or None."""
    if SYMBOLLECT_PATH not in sys.path:
        sys.path.insert(0, SYMBOLLECT_PATH)
    try:
        import symbollect  # noqa: E402
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)
    for fn in ("encode", "decode", "canonical", "digest"):
        if not callable(getattr(symbollect, fn, None)):
            return None, "symbollect.%s missing" % fn
    return symbollect, ""


def claim_from_queue(queue, consumer, run_id, timeout_s=15, ack=True):
    """Poll the mesh broker for a delivery tagged with run_id.

    Returns (entry_id, delivery_dict) or (None, None). Claimed entries are
    acked when ack=True so the test leaves no residue.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        st, body, _ = http(MESH, "GET", "/handoff/next",
                           query={"queue": queue, "consumer": consumer}, timeout=10)
        if st == 200 and isinstance(body, dict):
            env = pick(body, "message", "entry", "data", "handoff")
            env = env if isinstance(env, dict) else body
            eid = pick(body, "id", "entry_id", "message_id") or pick(env, "id", "entry_id", "message_id")
            # Delivery may be the envelope itself or nested under message/payload.
            cand = env
            payload = pick(cand, "payload", "body", "data")
            if not isinstance(payload, dict) and isinstance(cand.get("message"), dict):
                cand = cand["message"]
                payload = pick(cand, "payload", "body", "data")
            if isinstance(payload, dict) and payload.get("run_id") == run_id:
                if ack and eid:
                    http(MESH, "POST", "/handoff/ack",
                         {"queue": queue, "consumer": consumer, "id": eid}, timeout=10)
                return eid, {"envelope": env, "payload": payload, "delivery": cand}
            if ack and eid:
                # Not ours (another run's leftover): ack to keep the queue clean
                # only if it is clearly stale e2e traffic; otherwise leave it.
                if isinstance(payload, dict) and str(payload.get("run_id", "")).startswith("20"):
                    http(MESH, "POST", "/handoff/ack",
                         {"queue": queue, "consumer": consumer, "id": eid}, timeout=10)
        time.sleep(0.5)
    return None, None


def main():
    codec, codec_err = load_symbollect()
    if not check("V-MESH-008", "symbollect-codec-import", codec is not None,
                 "SYMBOLLECT_PATH=%s err=%s" % (SYMBOLLECT_PATH, codec_err)):
        return

    st, body, raw = http(ANYA, "GET", "/health", timeout=10)
    if not check("V-CAP-002", "anya-liveness", st == 200,
                 "status=%s body=%s" % (st, raw[:200])):
        return

    # 1. Register the ephemeral test knight (V-CAP-002).
    st, body, raw = http(ANYA, "POST", "/knights",
                         {"knight": KNIGHT, "queue": QUEUE, "capabilities": CAPS})
    registered = st == 200 and isinstance(body, dict)
    if not check("V-CAP-002", "knight-register", registered,
                 "status=%s body=%s" % (st, raw[:300])):
        return

    # 2. Registry reflects the knight with its declared capabilities.
    st, body, raw = http(ANYA, "GET", "/knights")
    entry = None
    if st == 200 and isinstance(body, dict):
        knights = pick(body, "knights", "registry", "result")
        if isinstance(knights, dict):  # some registries are name -> entry maps
            entry = knights.get(KNIGHT)
        elif isinstance(knights, list):
            for e in knights:
                if isinstance(e, dict) and pick(e, "knight", "name") == KNIGHT:
                    entry = e
                    break
    caps = pick(entry, "capabilities", "caps") if isinstance(entry, dict) else None
    check("V-CAP-002", "registry-reflects-capabilities",
          isinstance(entry, dict) and isinstance(caps, list) and all(c in caps for c in CAPS),
          "entry=%s" % (json.dumps(entry)[:300] if entry else raw[:200]))

    # 3. Route a proposal to the test knight (V-MESH-008).
    st, body, raw = http(ANYA, "POST", "/route", {
        "to": KNIGHT, "from": "e2e-probe", "type": "proposal",
        "payload": {"run_id": RUN_ID, "action": "verify", "target": "manifest", "priority": 2},
    })
    routed = (st == 200 and isinstance(body, dict)
              and "quarantin" not in json.dumps(body).lower())
    if not check("V-MESH-008", "route-proposal", routed,
                 "status=%s body=%s" % (st, raw[:300])):
        return

    # 4. Delivery arrives with Symbollect wire + digest; digest verifies.
    eid, found = claim_from_queue(QUEUE, CONSUMER, RUN_ID, timeout_s=15)
    if not check("V-MESH-008", "delivery-received", found is not None,
                 "no delivery for run_id on queue %s within 15s" % QUEUE):
        return
    payload = found["payload"]
    wire = payload.get("symbollect")
    dg = payload.get("digest")
    if not check("V-MESH-008", "delivery-has-wire-and-digest",
                 isinstance(wire, str) and wire.startswith("v=1|") and isinstance(dg, str) and len(dg) == 64,
                 "symbollect=%r digest=%r" % (wire[:80] if isinstance(wire, str) else wire, dg)):
        return
    try:
        decoded = codec.decode(wire)
    except Exception as e:  # noqa: BLE001
        check("V-MESH-008", "digest-verifies", False, "codec.decode failed: %s: %s" % (type(e).__name__, e))
        return
    recomputed = codec.digest(decoded)
    check("V-MESH-008", "digest-verifies", recomputed == dg,
          "wire=%s recomputed=%s attached=%s" % (wire, recomputed, dg))

    # 5. A grant-type message must be quarantined, never delivered (V-MESH-006).
    st, body, raw = http(ANYA, "POST", "/route", {
        "to": KNIGHT, "from": "e2e-probe", "type": "grant",
        "payload": {"run_id": RUN_ID, "capability": "mint-test"},
    })
    quarantined = (st == 200 and isinstance(body, dict)
                   and ("quarantin" in json.dumps(body).lower()
                        or pick(body, "status", "decision") in ("quarantined", "quarantine")))
    if not check("V-MESH-006", "grant-quarantined", quarantined,
                 "status=%s body=%s" % (st, raw[:300])):
        return
    # Confirm nothing for this run_id lands in the knight's queue afterwards.
    eid2, found2 = claim_from_queue(QUEUE, CONSUMER + "-q", RUN_ID, timeout_s=6)
    leaked = False
    if found2 is not None:
        d2 = found2["delivery"] if isinstance(found2["delivery"], dict) else {}
        leaked = pick(d2, "type") == "grant" or found2["payload"].get("capability") == "mint-test"
    check("V-MESH-006", "grant-never-delivered", not leaked,
          "a grant-type delivery reached the knight queue" if leaked else "")


if __name__ == "__main__":
    try:
        try:
            main()
        finally:
            # Best-effort unregister; the registry file is durable, so a unique
            # per-run name guarantees no collision even if this is unsupported.
            try:
                st, _, _ = http(ANYA, "DELETE", "/knights/%s" % urllib.parse.quote(KNIGHT), timeout=10)
                if st not in (200, 202, 204):
                    warn("V-CAP-002", "knight-unregister",
                         "DELETE /knights/{knight} returned %s; registry is durable, "
                         "unique test name avoids collision" % st)
            except Exception as e:  # noqa: BLE001
                warn("V-CAP-002", "knight-unregister", "cleanup attempt failed: %s" % e)
    except Exception as e:  # noqa: BLE001 - harness must always emit JSON
        _rec("V-CAP-002", "harness", "FAIL", "unexpected exception: %s: %s" % (type(e).__name__, e))
    finish()
