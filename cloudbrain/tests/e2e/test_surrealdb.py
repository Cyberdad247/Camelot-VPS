#!/usr/bin/env python3
"""E2E: SurrealDB authenticated record-lifecycle verification (stdlib only).

Part of the CAMELOT_OS cloudbrain/ production-hardening pack (cloudbrain/tests/e2e/).
Adapted from the local staging pack; see the staging source of record.
VPS run: upload to /opt/data/scripts/, execute via a no-agent cron job, read results at /opt/data/cron/output/{id}/.

Runs on the VPS via the cron pattern (loopback only, no DNS):
  python3 /opt/data/scripts/e2e/test_surrealdb.py

Covers gate V-DATA-009: authenticated CREATE / SELECT / DELETE of a synthetic
record. Credentials are sourced at runtime from /opt/data/cloudbrain/open-notebook.env
(mode 600) by PATH ONLY - values are never printed, logged, or embedded in the
report. A self-check FAILs the run if any credential value appears in the output.

Output contract: lines like `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>`,
then `--- JSON SUMMARY ---` and a JSON report. Exit 0 iff no FAIL.
"""
import base64
import datetime
import json
import re
import secrets
import sys
import urllib.error
import urllib.request

SURREAL = "http://127.0.0.1:8000"
ENV_PATH = "/opt/data/cloudbrain/open-notebook.env"
GATE = "V-DATA-009"
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
RID = "rec-" + secrets.token_hex(4)  # synthetic record id; [A-Za-z0-9_-] only
STARTED = datetime.datetime.now(datetime.timezone.utc).isoformat()
RESULTS = []
_SECRETS = []  # credential VALUES, memory-only; used solely for the leak self-check


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
        "script": "test_surrealdb.py",
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


def load_credentials(path):
    """Parse KEY=VALUE env file. Returns (user, password, ns, db, key_names).

    Values are kept in memory only and never returned in any printable detail.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        return None, "cannot read %s: %s" % (path, e)

    env = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        if k:
            env[k] = v

    def find(*preferred, contains=()):
        for k in preferred:
            if env.get(k):
                return env[k], k
        for k, v in env.items():
            lk = k.lower()
            if v and any(c in lk for c in contains):
                return v, k
        return None, None

    user, user_key = find("SURREAL_USER", "SURREALDB_USER", "DB_USER", "SURREALDB_USERNAME",
                          contains=("username", "user", "login"))
    password, pass_key = find("SURREAL_PASS", "SURREAL_PASSWORD", "SURREALDB_PASS",
                              "SURREALDB_PASSWORD", "DB_PASS", "DB_PASSWORD",
                              contains=("password", "passwd", "secret", "pwd", "token"))
    ns, _ = find("SURREAL_NS", "SURREALDB_NS", "NS", "NAMESPACE", contains=("namespace",))
    db, _ = find("SURREAL_DB", "SURREALDB_DB", "DB", "DATABASE", contains=("database",))
    ns = ns or "e2e"
    db = db or "e2e"

    if not user or not password:
        return None, ("found keys: %s; user_key=%s pass_key=%s"
                      % (sorted(env.keys()), user_key, pass_key))
    _SECRETS.extend([user, password])
    return {"user": user, "password": password, "ns": ns, "db": db,
            "user_key": user_key, "pass_key": pass_key}, ""


def sql(creds, query, timeout=10):
    """POST raw SQL to /sql. Returns (status:int|None, results:list|None, note:str)."""
    token = base64.b64encode(("%s:%s" % (creds["user"], creds["password"])).encode()).decode()
    req = urllib.request.Request(
        SURREAL + "/sql", data=query.encode("utf-8"), method="POST",
        headers={"Content-Type": "text/plain", "Accept": "application/json",
                 "Surreal-NS": creds["ns"], "Surreal-DB": creds["db"],
                 "Authorization": "Basic " + token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw), ""
            except ValueError:
                return resp.status, None, "non-JSON response: %s" % raw[:200]
    except urllib.error.HTTPError as e:
        # Status only: never echo bodies that might carry auth context.
        return e.code, None, "HTTP %s" % e.code
    except Exception as e:  # noqa: BLE001
        return None, None, "%s: %s" % (type(e).__name__, e)


def all_ok(results):
    return (isinstance(results, list) and results
            and all(isinstance(r, dict) and r.get("status") == "OK" for r in results))


def main():
    creds, err = load_credentials(ENV_PATH)
    if not check(GATE, "env-credentials-loadable", creds is not None, err):
        return
    assert re.fullmatch(r"[A-Za-z0-9_-]+", RID) and re.fullmatch(r"[A-Za-z0-9_-]+", RUN_ID.replace(":", ""))

    # Authenticated CREATE of a synthetic record.
    st, res, note = sql(creds,
        "CREATE e2e_verify:%s CONTENT {run_id: '%s', note: 'synthetic e2e', n: 1};"
        % (RID, RUN_ID))
    created = (st == 200 and all_ok(res)
               and res[0].get("result") and res[0]["result"][0].get("id") == "e2e_verify:" + RID)
    if not check(GATE, "authenticated-create", created,
                 "status=%s note=%s" % (st, note or "result id mismatch")):
        return

    # Authenticated SELECT: the record is queryable and matches this run.
    st, res, note = sql(creds, "SELECT * FROM e2e_verify WHERE run_id = '%s';" % RUN_ID)
    rows = res[0].get("result", []) if all_ok(res) else []
    selected = (st == 200 and len(rows) == 1
                and rows[0].get("id") == "e2e_verify:" + RID
                and rows[0].get("run_id") == RUN_ID)
    if not check(GATE, "authenticated-query", selected,
                 "status=%s rows=%d note=%s" % (st, len(rows), note)):
        return

    # Authenticated DELETE: record removed, re-query returns nothing.
    st, res, note = sql(creds, "DELETE e2e_verify WHERE run_id = '%s';" % RUN_ID)
    ok_del = st == 200 and all_ok(res)
    st2, res2, note2 = sql(creds, "SELECT * FROM e2e_verify WHERE run_id = '%s';" % RUN_ID)
    rows2 = res2[0].get("result", []) if all_ok(res2) else None
    check(GATE, "authenticated-delete", ok_del and st2 == 200 and rows2 == [],
          "del_status=%s requery_status=%s rows=%s" % (st, st2, rows2 if rows2 is not None else note2))

    # Self-check: no credential VALUE may appear in anything we are about to print.
    blob = json.dumps(RESULTS) + RUN_ID + RID
    leaked = [s for s in _SECRETS if s and len(s) >= 4 and s in blob]
    check(GATE, "no-secret-in-output", not leaked,
          "credential value present in report output" if leaked else "")


if __name__ == "__main__":
    try:
        try:
            main()
        finally:
            # Best-effort cleanup of the synthetic record (needs creds; skip silently).
            try:
                creds, _ = load_credentials(ENV_PATH)
                if creds:
                    sql(creds, "DELETE e2e_verify WHERE run_id = '%s';" % RUN_ID)
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001 - harness must always emit JSON
        _rec(GATE, "harness", "FAIL", "unexpected exception: %s: %s" % (type(e).__name__, e))
    finish()
