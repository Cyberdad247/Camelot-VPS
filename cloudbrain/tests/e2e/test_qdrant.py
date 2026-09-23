#!/usr/bin/env python3
"""E2E: Qdrant context-compiler verification (stdlib only).

Part of the CAMELOT_OS cloudbrain/ production-hardening pack (cloudbrain/tests/e2e/).
Adapted from the local staging pack; see the staging source of record.
VPS run: upload to /opt/data/scripts/, execute via a no-agent cron job, read results at /opt/data/cron/output/{id}/.

Runs on the VPS via the cron pattern (loopback only, no DNS):
  python3 /opt/data/scripts/e2e/test_qdrant.py

Covers gate V-DATA-008: two synthetic scopes (collections) with identical
vectors; filtered search must never leak points across scopes. Both test
collections are deleted afterwards.

Output contract: lines like `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>`,
then `--- JSON SUMMARY ---` and a JSON report. Exit 0 iff no FAIL.
"""
import datetime
import json
import secrets
import sys
import urllib.error
import urllib.request

QDRANT = "http://127.0.0.1:6333"
GATE = "V-DATA-008"
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
SUFFIX = secrets.token_hex(4)  # lowercase hex: safe in collection names
COL_A = "e2e_%s_a" % SUFFIX
COL_B = "e2e_%s_b" % SUFFIX
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


def finish():
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "WARN": 0}
    for r in RESULTS:
        counts[r["status"]] += 1
    report = {
        "script": "test_qdrant.py",
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


def http(method, path, body=None, timeout=10):
    """Returns (status:int|None, parsed:dict, raw:str)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(QDRANT + path, data=data, method=method,
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
    except Exception as e:  # noqa: BLE001 - connection errors become (None, ...)
        return None, {"_error": "%s: %s" % (type(e).__name__, e)}, ""


def search(col, scope_value):
    return http("POST", "/collections/%s/points/search" % col, {
        "vector": [1.0, 0.0, 0.0, 0.0],
        "filter": {"must": [{"key": "scope", "match": {"value": scope_value}}]},
        "limit": 10,
        "with_payload": True,
    })


def delete_collection(col):
    # Best-effort cleanup; never raises.
    try:
        http("DELETE", "/collections/%s" % col, timeout=10)
    except Exception:  # noqa: BLE001
        pass


def main():
    vectors = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]
    try:
        # 1. Create two synthetic scope collections.
        created = True
        for col in (COL_A, COL_B):
            st, body, raw = http("PUT", "/collections/%s" % col,
                                 {"vectors": {"size": 4, "distance": "Cosine"}})
            ok = st in (200, 201, 202) and body.get("status") == "ok"
            created = created and ok
            if not ok:
                check(GATE, "create-collection", False,
                      "col=%s status=%s body=%s" % (col, st, raw[:200]))
                return
        check(GATE, "create-collection", True)

        # 2. Upsert 3 vectors per scope. Vectors are IDENTICAL across scopes so
        #    that isolation must come from the payload filter, not geometry.
        upserted = True
        for col, scope in ((COL_A, "a"), (COL_B, "b")):
            points = [{"id": i + 1, "vector": vectors[i],
                       "payload": {"scope": scope, "run_id": RUN_ID, "n": i + 1}}
                      for i in range(3)]
            st, body, raw = http("PUT", "/collections/%s/points" % col, {"points": points})
            ok = st == 200 and body.get("status") == "ok"
            upserted = upserted and ok
            if not ok:
                check(GATE, "upsert-3-vectors", False,
                      "col=%s status=%s body=%s" % (col, st, raw[:200]))
                return
        check(GATE, "upsert-3-vectors", True)

        # 3. Filtered search inside scope A returns exactly its 3 points.
        st, body, raw = search(COL_A, "a")
        hits = body.get("result", []) if isinstance(body, dict) else []
        ok = (st == 200 and len(hits) == 3
              and all(isinstance(h, dict) and h.get("payload", {}).get("scope") == "a"
                      and h.get("payload", {}).get("run_id") == RUN_ID for h in hits))
        if not check(GATE, "filtered-search", ok,
                     "status=%s hits=%d body=%s" % (st, len(hits) if isinstance(hits, list) else -1, raw[:300])):
            return

        # 4. Isolation: scope-B filter inside collection A matches nothing, and
        #    collection B's points carry only scope b / this run_id.
        st_b, body_b, raw_b = search(COL_A, "b")
        hits_b = body_b.get("result", []) if isinstance(body_b, dict) else []
        st_c, body_c, raw_c = search(COL_B, "b")
        hits_c = body_c.get("result", []) if isinstance(body_c, dict) else []
        leaked = [h for h in hits_c
                  if not (isinstance(h, dict) and h.get("payload", {}).get("run_id") == RUN_ID)]
        ok_iso = (st_b == 200 and hits_b == []
                  and st_c == 200 and len(hits_c) == 3 and not leaked)
        check(GATE, "cross-scope-isolation", ok_iso,
              "A/filter=b -> %s; B/filter=b -> %d hits, %d foreign"
              % (raw_b[:120], len(hits_c) if isinstance(hits_c, list) else -1, len(leaked)))
    finally:
        # Cleanup: delete both test collections and verify they are gone.
        gone = True
        for col in (COL_A, COL_B):
            delete_collection(col)
            st, _, _ = http("GET", "/collections/%s" % col, timeout=10)
            gone = gone and (st == 404)
        check(GATE, "delete-collections", gone,
              "a collection still exists after DELETE" if not gone else "")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - harness must always emit JSON
        _rec(GATE, "harness", "FAIL", "unexpected exception: %s: %s" % (type(e).__name__, e))
    finish()
