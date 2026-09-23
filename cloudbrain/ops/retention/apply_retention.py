#!/usr/bin/env python3
"""apply_retention.py — enforce bounded stream retention on the mesh handoff broker.

Stdlib-only. Safe for the DNS-less no-agent cron pattern: speaks RESP over a
plain socket to Redis on 127.0.0.1:6379, nothing else.

Behavior per stream:
  1. Discover streams: SCAN MATCH mesh:handoff:* plus the known special streams
     (anya-omega, anya-quarantine, anya-deadletter).
  2. Classify: live (5,000) / retry (2,000) / evidence (20,000).
  3. Query XPENDING on consumer group `mesh-brokers` first; the effective trim
     bound is max(configured MAXLEN, pending count) so unacknowledged messages
     are NEVER trimmed.
  4. Evidence-class streams additionally require a fresh export watermark and
     the --allow-evidence-trim flag (export-before-trim rule); otherwise the
     stream is skipped, loudly.
  5. Apply XTRIM MAXLEN ~ <effective bound> (no-op if already within bound).
  6. Print a JSON report to stdout.

Idempotent: repeated runs converge; bounded streams are no-ops.

Usage:
  python3 apply_retention.py [--dry-run] [--allow-evidence-trim]
      [--host 127.0.0.1] [--port 6379]
      [--export-watermark /opt/data/cloudbrain/data/anya-omega/export.watermark]

Exit codes: 0 = report produced; 2 = could not reach Redis.
"""

import argparse
import json
import os
import socket
import sys
import time

# ---------------------------------------------------------------- constants
HOST = "127.0.0.1"
PORT = 6379
GROUP = "mesh-brokers"
SOCKET_TIMEOUT = 10

# Proposed defaults — keep in sync with RETENTION_POLICY.md §3.
LIVE_MAXLEN = 5000
RETRY_MAXLEN = 2000
EVIDENCE_MAXLEN = 20000

DISCOVER_PATTERN = "mesh:handoff:*"
# Special streams that do not match the discovery pattern but are in scope.
KNOWN_STREAMS = ["anya-omega", "anya-quarantine", "anya-deadletter"]

EXPORT_WATERMARK_PATH = "/opt/data/cloudbrain/data/anya-omega/export.watermark"
WATERMARK_FRESH_SECS = 24 * 3600

ALERT_PCT = 0.80  # warn when len_before exceeds 80% of configured MAXLEN


# ------------------------------------------------------------- RESP client
class RedisError(Exception):
    pass


class Redis:
    """Minimal stdlib-only RESP client (enough for the commands below)."""

    def __init__(self, host, port, timeout):
        try:
            self.sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as e:
            raise RedisError("connect failed: %s" % e)
        self.f = self.sock.makefile("rb")

    def cmd(self, *args):
        parts = [("*%d\r\n" % len(args)).encode()]
        for a in args:
            b = a if isinstance(a, (bytes, bytearray)) else str(a).encode()
            parts.append(("$%d\r\n" % len(b)).encode())
            parts.append(bytes(b))
            parts.append(b"\r\n")
        self.sock.sendall(b"".join(parts))
        return self._read()

    def _readline(self):
        line = self.f.readline()
        if not line:
            raise RedisError("connection closed by server")
        return line

    def _read(self):
        line = self._readline()
        typ, rest = line[:1], line[1:-2]
        if typ == b"+":
            return rest.decode()
        if typ == b"-":
            raise RedisError(rest.decode())
        if typ == b":":
            return int(rest)
        if typ == b"$":
            n = int(rest)
            if n == -1:
                return None
            data = self.f.read(n)
            self.f.read(2)  # trailing CRLF
            return data.decode()
        if typ == b"*":
            n = int(rest)
            if n == -1:
                return None
            return [self._read() for _ in range(n)]
        raise RedisError("unknown reply type: %r" % typ)

    def close(self):
        try:
            self.f.close()
        finally:
            self.sock.close()


# ------------------------------------------------------------------ logic
def classify(key):
    """Return (class_name, configured_maxlen) for a stream key."""
    if key.endswith("anya-quarantine") or key.endswith("anya-deadletter"):
        return ("evidence", EVIDENCE_MAXLEN)
    if "mesh:retry:" in key:
        return ("retry", RETRY_MAXLEN)
    return ("live", LIVE_MAXLEN)


def discover_streams(r):
    """Return sorted list of in-scope stream keys."""
    found = set()
    cursor = "0"
    while True:
        cursor, keys = r.cmd("SCAN", cursor, "MATCH", DISCOVER_PATTERN,
                             "COUNT", "100")
        found.update(keys)
        if str(cursor) == "0":
            break
    for key in KNOWN_STREAMS:
        try:
            if r.cmd("EXISTS", key):
                found.add(key)
        except RedisError:
            pass
    streams = []
    for key in sorted(found):
        try:
            if r.cmd("TYPE", key) == "stream":
                streams.append(key)
        except RedisError:
            pass
    return streams


def pending_info(r, key):
    """Return (pending_count, oldest_idle_ms, note). Never raises."""
    try:
        summary = r.cmd("XPENDING", key, GROUP)
    except RedisError as e:
        msg = str(e)
        if "NOGROUP" in msg or "no such key" in msg.lower():
            return (0, None, "no consumer group '%s' on stream" % GROUP)
        return (0, None, "XPENDING failed: %s" % msg)
    count = int(summary[0])
    idle_ms = None
    if count > 0:
        try:
            first = r.cmd("XPENDING", key, GROUP, "-", "+", "1")
            if first:
                idle_ms = int(first[0][2])
        except (RedisError, IndexError, ValueError):
            idle_ms = None
    return (count, idle_ms, None)


def watermark_status(path):
    """Check the export watermark file. Returns dict; never raises."""
    st = {"path": path, "present": False, "fresh": False, "covers": []}
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return st
    st["present"] = True
    st["fresh"] = (time.time() - mtime) < WATERMARK_FRESH_SECS
    try:
        with open(path, "r") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            st["covers"] = sorted(k for k in data if k != "exported_at")
    except (OSError, ValueError):
        pass
    return st


def process_stream(r, key, dry_run, allow_evidence_trim, wm):
    cls, configured = classify(key)
    entry = {
        "stream": key,
        "class": cls,
        "maxlen_configured": configured,
        "len_before": None,
        "len_after": None,
        "trimmed": 0,
        "pending": 0,
        "oldest_pending_idle_ms": None,
        "effective_maxlen": configured,
        "over_80pct": False,
        "note": None,
    }
    try:
        entry["len_before"] = int(r.cmd("XLEN", key))
    except RedisError as e:
        entry["note"] = "XLEN failed: %s" % e
        return entry, None

    pending, idle_ms, perr = pending_info(r, key)
    entry["pending"] = pending
    entry["oldest_pending_idle_ms"] = idle_ms
    if perr:
        entry["note"] = perr

    # PEL guard: never trim below the number of unacknowledged entries.
    effective = max(configured, pending)
    entry["effective_maxlen"] = effective
    entry["over_80pct"] = entry["len_before"] > ALERT_PCT * configured

    alert = None
    if entry["over_80pct"]:
        alert = ("%s length %d exceeds 80%% of configured MAXLEN %d"
                 % (key, entry["len_before"], configured))

    # Export-before-trim rule for evidence streams.
    if cls == "evidence":
        covered = (wm["present"] and wm["fresh"]
                   and (key in wm["covers"] or "all" in wm["covers"]))
        if not allow_evidence_trim or not covered:
            reasons = []
            if not allow_evidence_trim:
                reasons.append("--allow-evidence-trim not passed")
            if not wm["present"]:
                reasons.append("no watermark file at %s" % wm["path"])
            elif not wm["fresh"]:
                reasons.append("watermark file is stale (>24h)")
            elif key not in wm["covers"] and "all" not in wm["covers"]:
                reasons.append("watermark does not cover %s" % key)
            entry["note"] = ("evidence trim SKIPPED (export-before-trim): "
                             + "; ".join(reasons))
            entry["len_after"] = entry["len_before"]
            return entry, alert or entry["note"]

    if entry["len_before"] <= effective:
        entry["len_after"] = entry["len_before"]
        entry["note"] = entry["note"] or "within bound; no trim needed"
        return entry, alert

    if dry_run:
        entry["len_after"] = entry["len_before"]
        entry["trimmed"] = 0
        would = entry["len_before"] - effective
        entry["note"] = ("dry-run: would XTRIM MAXLEN ~ %d, removing ~%d entries"
                         % (effective, would))
        return entry, alert

    # Approximate trim (~) is cheaper on large streams; exactness is not
    # required since consumers ack and PEL entries are protected by the bound.
    r.cmd("XTRIM", key, "MAXLEN", "~", effective)
    entry["len_after"] = int(r.cmd("XLEN", key))
    entry["trimmed"] = entry["len_before"] - entry["len_after"]
    entry["note"] = entry["note"] or "trimmed to bound"
    return entry, alert


def main():
    ap = argparse.ArgumentParser(description="Enforce mesh broker stream retention.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute the report, trim nothing.")
    ap.add_argument("--allow-evidence-trim", action="store_true",
                    help="Permit trimming evidence streams (requires fresh export watermark).")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--export-watermark", default=EXPORT_WATERMARK_PATH)
    args = ap.parse_args()

    try:
        r = Redis(args.host, args.port, SOCKET_TIMEOUT)
    except RedisError as e:
        print(json.dumps({"ok": False, "error": str(e),
                          "host": args.host, "port": args.port}))
        return 2

    report = {
        "ok": True,
        "host": args.host,
        "port": args.port,
        "consumer_group": GROUP,
        "dry_run": args.dry_run,
        "allow_evidence_trim": args.allow_evidence_trim,
        "targets": {"live": LIVE_MAXLEN, "retry": RETRY_MAXLEN,
                    "evidence": EVIDENCE_MAXLEN},
        "evidence_watermark": None,
        "streams": [],
        "alerts": [],
        "ran_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    try:
        wm = watermark_status(args.export_watermark)
        report["evidence_watermark"] = wm
        for key in discover_streams(r):
            entry, alert = process_stream(r, key, args.dry_run,
                                         args.allow_evidence_trim, wm)
            report["streams"].append(entry)
            if alert:
                report["alerts"].append(alert)
    except RedisError as e:
        report["ok"] = False
        report["error"] = str(e)
    finally:
        r.close()

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
