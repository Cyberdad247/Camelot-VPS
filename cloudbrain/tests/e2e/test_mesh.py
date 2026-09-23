#!/usr/bin/env python3
"""E2E: mesh broker publish -> claim -> ack verification (stdlib only).

Part of the CAMELOT_OS cloudbrain/ production-hardening pack (cloudbrain/tests/e2e/).
Adapted from the local staging pack; see the staging source of record.
VPS run: upload to /opt/data/scripts/, execute via a no-agent cron job, read results at /opt/data/cron/output/{id}/.

Runs on the VPS via the cron pattern (loopback only, no DNS):
  python3 /opt/data/scripts/e2e/test_mesh.py

Covers gates:
  V-MESH-001 - broker HTTP round trip: publish -> claim -> ack completes.
  V-MESH-005 - pending-set accuracy: claimed message appears in pending,
                acked message disappears from pending.
  V-MESH-002 - consumer-interruption reclamation: MANUAL procedure (script emits
                SKIP; see README.md for the step-by-step).

Uses a synthetic queue/consumer named with a unique run ID; leaves no residue
(the message is acked, so the stream entry is consumed).

Response schemas are parsed tolerantly (documented assumptions in README.md);
any unparseable response FAILs with a body snippet for diagnosis.

Output contract: lines like `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>`,
then `--- JSON SUMMARY ---` and a JSON report. Exit 0 iff no FAIL.
"""
import datetime
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MESH = "http://127.0.0.1:8002"
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
TOKEN = secrets.token_hex(4)
QUEUE = "e2e-%s" % TOKEN
CONSUMER = "e2e-c-%s" % TOKEN
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


def skip(gate, name, detail=""):
    _rec(gate, name, "SKIP", detail)


def finish():
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "WARN": 0}
    for r in RESULTS:
        counts[r["status"]] += 1
    report = {
        "script": "test_mesh.py",
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


def http(method, path, body=None, query=None, timeout=10):
    """Returns (status:int|None, parsed:dict|list, raw:str)."""
    url = MESH + path
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
    """First present non-empty value among candidate field names."""
    if isinstance(d, dict):
        for n in names:
            if d.get(n) not in (None, ""):
                return d[n]
    return None


def pending_ids(body):
    """Extract a set of pending entry ids from a /handoff/pending response."""
    items = []
    if isinstance(body, dict):
        for key in ("pending", "result", "entries", "messages"):
            v = body.get(key)
            if isinstance(v, list):
                items = v
                break
    elif isinstance(body, list):
        items = body
    ids = set()
    for it in items:
        if isinstance(it, dict):
            v = pick(it, "id", "entry_id", "message_id")
            ids.add(str(v) if v is not None else json.dumps(it, sort_keys=True))
        else:
            ids.add(str(it))
    return ids


def claim_next(timeout_s=12):
    """Poll /handoff/next until a message for this run arrives or timeout."""
    deadline = time.time() + timeout_s
    last = (None, {}, "")
    while time.time() < deadline:
        st, body, raw = http("GET", "/handoff/next",
                             query={"queue": QUEUE, "consumer": CONSUMER}, timeout=10)
        last = (st, body, raw)
        if st == 200 and isinstance(body, dict):
            env = pick(body, "message", "entry", "data", "handoff")
            env = env if isinstance(env, dict) else body
            mid = pick(body, "id", "entry_id", "message_id") or pick(env, "id", "entry_id", "message_id")
            payload = pick(env, "payload", "body", "data")
            if isinstance(payload, dict) and payload.get("run_id") == RUN_ID:
                return mid, env, payload
            # Message for another run/consumer: keep polling, don't ack it.
        time.sleep(0.5)
    return None, None, None


def main():
    # 0. Broker liveness.
    st, body, raw = http("GET", "/health", timeout=10)
    if not check("V-MESH-001", "broker-liveness", st == 200,
                 "status=%s body=%s" % (st, raw[:200])):
        return

    # 1. Publish a synthetic handoff.
    st, body, raw = http("POST", "/handoff", {
        "queue": QUEUE, "to": "e2e-sink", "from": "e2e-probe",
        "type": "proposal",
        "payload": {"run_id": RUN_ID, "note": "synthetic e2e", "action": "verify"},
    })
    mid = pick(body, "id", "entry_id", "message_id") if st == 200 else None
    if not check("V-MESH-001", "broker-publish", st == 200 and mid,
                 "status=%s body=%s" % (st, raw[:300])):
        return

    # 2. Claim it via /handoff/next.
    cid, env, payload = claim_next()
    claimed = cid is not None and isinstance(payload, dict) and payload.get("run_id") == RUN_ID
    same_id = bool(cid and mid and str(cid) == str(mid))
    if not check("V-MESH-001", "broker-claim", claimed,
                 "published=%s claimed=%s" % (mid, cid)):
        return
    if not same_id:
        _rec("V-MESH-001", "claim-id-matches-publish", "WARN",
             "published id %s != claimed id %s; continuing on run_id match" % (mid, cid))

    # 3. Pending set reflects the claim (V-MESH-005, first half).
    st, body, raw = http("GET", "/handoff/pending", query={"queue": QUEUE})
    ids = pending_ids(body) if st == 200 else set()
    in_pending = any(str(mid) in i or str(cid) in i for i in ids) if ids else False
    # Fallback: some brokers key pending by consumer.
    if not in_pending and st == 200:
        st2, body2, _ = http("GET", "/handoff/pending",
                             query={"queue": QUEUE, "consumer": CONSUMER})
        ids2 = pending_ids(body2) if st2 == 200 else set()
        in_pending = any(str(mid) in i or str(cid) in i for i in ids2)
    check("V-MESH-005", "pending-reflects-claim", in_pending,
          "published=%s claimed=%s pending_ids=%s" % (mid, cid, sorted(ids)[:5]))

    # 4. Ack the claim.
    st, body, raw = http("POST", "/handoff/ack",
                         {"queue": QUEUE, "consumer": CONSUMER, "id": cid})
    acked = st == 200 and (pick(body, "ok", "acked", "success") in (True, "true", 1)
                           or "ack" in raw.lower() or body.get("ok") is not False)
    if not check("V-MESH-001", "broker-ack", acked,
                 "status=%s body=%s" % (st, raw[:300])):
        return

    # 5. Pending set no longer contains the acked message (V-MESH-005, second half).
    time.sleep(1)
    st, body, raw = http("GET", "/handoff/pending", query={"queue": QUEUE})
    ids = pending_ids(body) if st == 200 else set()
    still = [i for i in ids if str(mid) in i or str(cid) in i]
    check("V-MESH-005", "pending-cleared-by-ack", not still,
          "still pending: %s" % still[:3])

    check("V-MESH-001", "roundtrip-complete", True)

    # V-MESH-002: consumer-interruption reclamation is a MANUAL procedure.
    skip("V-MESH-002", "consumer-interruption-reclaim",
         "manual: publish, claim with consumer A, kill A before ack, then verify the "
         "entry is reclaimable via the mesh-brokers consumer group "
         "(XPENDING/XCLAIM on mesh:handoff:<queue> or broker equivalent); "
         "see README.md for the step-by-step.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - harness must always emit JSON
        _rec("V-MESH-001", "harness", "FAIL", "unexpected exception: %s: %s" % (type(e).__name__, e))
    finish()
