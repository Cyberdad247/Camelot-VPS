#!/usr/bin/env python3
"""E2E: Redis flash-memory verification (stdlib only).

Part of the CAMELOT_OS cloudbrain/ production-hardening pack (cloudbrain/tests/e2e/).
Adapted from the local staging pack; see the staging source of record.
VPS run: upload to /opt/data/scripts/, execute via a no-agent cron job, read results at /opt/data/cron/output/{id}/.

Runs on the VPS via the cron pattern (loopback only, no DNS):
  python3 /opt/data/scripts/e2e/test_redis.py

Covers gate V-DATA-004: SET/GET round trip, TTL expiry, persistence presence.
Uses synthetic keys prefixed with a unique run ID and deletes them afterwards.

Output contract: lines like `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>`,
then `--- JSON SUMMARY ---` and a JSON report. Exit 0 iff no FAIL.
"""
import datetime
import json
import secrets
import subprocess
import sys
import time

REDIS_CLI = "/opt/data/cloudbrain/bin/redis-cli"
GATE = "V-DATA-004"
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
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
        "script": "test_redis.py",
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


def cli(*args, timeout=10):
    """Run redis-cli; returns (returncode, stdout, stderr)."""
    try:
        p = subprocess.run([REDIS_CLI, *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "redis-cli not found at %s" % REDIS_CLI
    except Exception as e:  # noqa: BLE001 - report, don't crash
        return 1, "", "%s: %s" % (type(e).__name__, e)


def main():
    keys = ["e2e:%s:probe" % RUN_ID, "e2e:%s:ttl" % RUN_ID]
    probe_key, ttl_key = keys
    probe_val = "v-%s" % RUN_ID

    try:
        # 1. Liveness: PING must return PONG.
        rc, out, err = cli("PING")
        if not check(GATE, "ping", rc == 0 and out == "PONG",
                     "rc=%s out=%r err=%r" % (rc, out, err)):
            return

        # 2. SET/GET round trip on a synthetic key.
        rc, out, err = cli("SET", probe_key, probe_val)
        ok_set = rc == 0 and out == "OK"
        rc, out, err = cli("GET", probe_key)
        check(GATE, "set-get-roundtrip", ok_set and rc == 0 and out == probe_val,
              "set_ok=%s get=%r expected=%r err=%r" % (ok_set, out, probe_val, err))

        # 3. TTL expiry: key visible before deadline, gone after.
        rc, out, err = cli("SETEX", ttl_key, "2", "t")
        ok = rc == 0 and out == "OK"
        rc, out, _ = cli("GET", ttl_key)
        ok = ok and rc == 0 and out == "t"
        time.sleep(3)  # past the 2s TTL; keeps the cron job well under timeout
        rc, out, err = cli("GET", ttl_key)
        expired = rc == 0 and out in ("", "(nil)")
        check(GATE, "ttl-expiry", ok and expired,
              "pre-expiry visible=%s post-expiry get=%r err=%r" % (ok, out, err))

        # 4. Persistence presence: RDB snapshots configured (or AOF on) and a
        #    successful background save has happened at least once.
        rc, out, err = cli("CONFIG", "GET", "save")
        save_cfg = ""
        if rc == 0:
            lines = out.splitlines()
            save_cfg = lines[1] if len(lines) > 1 else ""
        rc2, out2, err2 = cli("CONFIG", "GET", "appendonly")
        aof = out2.splitlines()[1] if rc2 == 0 and len(out2.splitlines()) > 1 else ""
        rc3, out3, err3 = cli("LASTSAVE")
        try:
            lastsave = int(out3.strip())
        except (ValueError, TypeError):
            lastsave = 0
        persisted = (save_cfg.strip() != "" or aof.strip().lower() == "yes") and lastsave > 0
        check(GATE, "persistence-configured", persisted,
              "save=%r appendonly=%r lastsave=%r" % (save_cfg, aof, out3))

        # 5. Optional: BGSAVE capability (started or already in progress both count).
        rc, out, err = cli("BGSAVE")
        ok_bgsave = rc == 0 and ("Background saving started" in out
                                 or "already in progress" in out)
        check(GATE, "bgsave-capability", ok_bgsave,
              "rc=%s out=%r err=%r" % (rc, out, err))
    finally:
        # Cleanup: delete synthetic keys and verify they are gone.
        cli("DEL", *keys)
        rc, out, _ = cli("GET", probe_key)
        check(GATE, "cleanup-keys", rc == 0 and out in ("", "(nil)"),
              "probe key still present: %r" % out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - harness must always emit JSON
        _rec(GATE, "harness", "FAIL", "unexpected exception: %s: %s" % (type(e).__name__, e))
    finish()
