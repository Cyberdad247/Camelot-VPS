#!/usr/bin/env python3
"""E2E: liveness vs readiness probing for every cloudbrain service (stdlib only).

Part of the CAMELOT_OS cloudbrain/ production-hardening pack (cloudbrain/tests/e2e/).
Adapted from the local staging pack; see the staging source of record.
VPS run: upload to /opt/data/scripts/, execute via a no-agent cron job, read results at /opt/data/cron/output/{id}/.

Runs on the VPS via the cron pattern (loopback only, no DNS):
  python3 /opt/data/scripts/e2e/test_health_semantics.py

Covers gates:
  V-SVC-005 - liveness: each service's process responds.
  V-SVC-006 - readiness: each service can serve its real workload.

HONEST GAP (documented, not hidden): every service currently exposes a SINGLE
health endpoint, so liveness and readiness cannot be distinguished for all of
them. Where no credential-free readiness probe exists, the script emits WARN
(not FAIL) with the reason, and the README records what a proper
liveness/readiness split would require.

Probes used:
  redis      live: redis-cli PING            ready: SET/GET probe round trip
  qdrant     live: GET / -> 200             ready: GET /collections -> 200
  surrealdb  live: GET /health -> 200       ready: WARN (auth-gated; the real
                                            authenticated path is V-DATA-009)
  openviking live: GET /health -> 200       ready: WARN (single endpoint; no
                                            deeper probe documented)
  mesh       live: GET /health -> 200       ready: GET /handoff/pending -> 200
                                            (proves the streams layer answers)
  anya       live: GET /health -> 200       ready: health body reports broker
                                            reachability, else WARN

Output contract: lines like `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>`,
then `--- JSON SUMMARY ---` and a JSON report. Exit 0 iff no FAIL.
"""
import datetime
import json
import secrets
import subprocess
import sys
import urllib.error
import urllib.request

REDIS_CLI = "/opt/data/cloudbrain/bin/redis-cli"
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
STARTED = datetime.datetime.now(datetime.timezone.utc).isoformat()
RESULTS = []

SERVICES = {
    "qdrant": "http://127.0.0.1:6333",
    "surrealdb": "http://127.0.0.1:8000",
    "openviking": "http://127.0.0.1:1933",
    "mesh": "http://127.0.0.1:8002",
    "anya": "http://127.0.0.1:8003",
}


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
        "script": "test_health_semantics.py",
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


def http_get(base, path, timeout=8):
    """Returns (status:int|None, parsed, raw:str)."""
    req = urllib.request.Request(base + path, method="GET")
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


def redis_cli(*args, timeout=10):
    try:
        p = subprocess.run([REDIS_CLI, *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "redis-cli not found at %s" % REDIS_CLI
    except Exception as e:  # noqa: BLE001
        return 1, "", "%s: %s" % (type(e).__name__, e)


def main():
    # --- redis ---
    rc, out, err = redis_cli("PING")
    live = rc == 0 and out == "PONG"
    check("V-SVC-005", "redis-liveness", live, "rc=%s out=%r err=%r" % (rc, out, err))
    if live:
        key, val = "e2e:%s:ready" % RUN_ID, "ready-%s" % RUN_ID
        rc1, o1, _ = redis_cli("SET", key, val)
        rc2, o2, _ = redis_cli("GET", key)
        redis_cli("DEL", key)
        check("V-SVC-006", "redis-readiness", rc1 == 0 and o1 == "OK" and rc2 == 0 and o2 == val,
              "set=%r get=%r" % (o1, o2))
    else:
        check("V-SVC-006", "redis-readiness", False, "liveness failed; readiness not attempted")

    # --- qdrant ---
    st, _, raw = http_get(SERVICES["qdrant"], "/")
    live = st == 200
    check("V-SVC-005", "qdrant-liveness", live, "status=%s body=%s" % (st, raw[:160]))
    if live:
        st2, _, raw2 = http_get(SERVICES["qdrant"], "/collections")
        check("V-SVC-006", "qdrant-readiness", st2 == 200,
              "GET /collections status=%s body=%s" % (st2, raw2[:160]))
    else:
        check("V-SVC-006", "qdrant-readiness", False, "liveness failed; readiness not attempted")

    # --- surrealdb ---
    st, _, raw = http_get(SERVICES["surrealdb"], "/health")
    live = st == 200
    check("V-SVC-005", "surrealdb-liveness", live, "status=%s body=%s" % (st, raw[:160]))
    warn("V-SVC-006", "surrealdb-readiness",
         "single /health endpoint; no credential-free readiness probe - "
         "authenticated readiness is covered by V-DATA-009 (test_surrealdb.py)")

    # --- openviking ---
    st, _, raw = http_get(SERVICES["openviking"], "/health")
    live = st == 200
    check("V-SVC-005", "openviking-liveness", live, "status=%s body=%s" % (st, raw[:160]))
    warn("V-SVC-006", "openviking-readiness",
         "single /health endpoint; no deeper readiness probe is documented for "
         "OpenViking 0.4.21 - readiness currently == liveness")

    # --- mesh broker ---
    st, _, raw = http_get(SERVICES["mesh"], "/health")
    live = st == 200
    check("V-SVC-005", "mesh-liveness", live, "status=%s body=%s" % (st, raw[:160]))
    if live:
        st2, _, raw2 = http_get(SERVICES["mesh"], "/handoff/pending")
        check("V-SVC-006", "mesh-readiness", st2 == 200,
              "GET /handoff/pending status=%s (proves streams layer answers) body=%s"
              % (st2, raw2[:160]))
    else:
        check("V-SVC-006", "mesh-readiness", False, "liveness failed; readiness not attempted")

    # --- anya omega ---
    st, body, raw = http_get(SERVICES["anya"], "/health")
    live = st == 200
    check("V-SVC-005", "anya-liveness", live, "status=%s body=%s" % (st, raw[:160]))
    if live:
        blob = json.dumps(body).lower() if isinstance(body, dict) else raw.lower()
        broker_ok = ("broker" in blob and ("ok" in blob or "true" in blob or "up" in blob))
        if broker_ok:
            check("V-SVC-006", "anya-readiness", True,
                  "health body reports broker reachability")
        else:
            warn("V-SVC-006", "anya-readiness",
                 "/health does not expose broker/ingress state in a parseable form; "
                 "body=%s" % raw[:200])
    else:
        check("V-SVC-006", "anya-readiness", False, "liveness failed; readiness not attempted")

    # Documented gap: one endpoint per service, liveness != readiness.
    warn("V-SVC-006", "health-endpoint-gap",
         "all services expose a single health endpoint: a 200 proves the process "
         "answers, not that dependencies (redis streams, registry load, queue "
         "depth) are healthy. A proper split needs /live (process up) vs /ready "
         "(dependency checks: redis writable, qdrant collections reachable, "
         "surrealdb authenticated query, broker stream writable, anya registry "
         "loaded + ingress draining). See README.md.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - harness must always emit JSON
        _rec("V-SVC-005", "harness", "FAIL", "unexpected exception: %s: %s" % (type(e).__name__, e))
    finish()
