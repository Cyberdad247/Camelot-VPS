#!/usr/bin/env python3
"""E2E: Symbollect v1 codec verification (stdlib only).

Part of the CAMELOT_OS cloudbrain/ production-hardening pack (cloudbrain/tests/e2e/).
Adapted from the local staging pack; see the staging source of record.
VPS run: upload to /opt/data/scripts/, execute via a no-agent cron job, read results at /opt/data/cron/output/{id}/.

Runs on the VPS via the cron pattern (loopback only, no DNS):
  python3 /opt/data/scripts/e2e/test_symbollect.py

Covers gates:
  V-SYM-001 - golden vectors: encode/canonical/digest frozen for 5 packets.
  V-SYM-002 - canonical stability: shuffled key order -> identical canonical
              form and digest.
  V-SYM-003 - round-trip property: encode->decode->encode stable on generated values.
  V-SYM-004 - malformed-input rejection, incl. reserved-key collisions.

The codec under test is the VPS's own /opt/data/cloudbrain/handoff/symbollect.py
(override with SYMBOLLECT_PATH). Golden vectors below were frozen from the
spec; G1 reproduces the documented example byte-for-byte.

Assumption (documented): canonical() sorts by the MESSAGE's (long) keys at
every nesting level, per the doc's `canonical(msg)` definition. If the VPS
codec sorts by wire codes instead, the V-SYM-001 digest goldens will flag it -
that is exactly what a verification gate is for; V-SYM-002 (self-consistency)
is unaffected either way.

Output contract: lines like `PASS <gate> <check>` / `FAIL <gate> <check> | <reason>`,
then `--- JSON SUMMARY ---` and a JSON report. Exit 0 iff no FAIL.
"""
import datetime
import itertools
import json
import os
import secrets
import sys

SYMBOLLECT_PATH = os.environ.get("SYMBOLLECT_PATH", "/opt/data/cloudbrain/handoff")
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
STARTED = datetime.datetime.now(datetime.timezone.utc).isoformat()
RESULTS = []

# (name, message dict, frozen wire, frozen canonical, frozen digest)
GOLDENS = [
    ("doc-example",
     {"to": "gawain", "from": "anya-omega", "type": "proposal",
      "payload": {"action": "verify", "target": "manifest", "priority": 2}},
     "v=1|t=gawain|f=anya-omega|y=proposal|p={a=verify,o=manifest,z=2}",
     "v=1|f=anya-omega|p={a=verify,z=2,o=manifest}|t=gawain|y=proposal",
     "5f2d9124f0fda5ebe9383dc5dcfb4d4131f26b1e1369c8919c87c18225d10616"),
    ("ack",
     {"to": "percival", "from": "gawain", "type": "ack", "id": "h-0001"},
     "v=1|t=percival|f=gawain|y=ack|i=h-0001",
     "v=1|f=gawain|i=h-0001|t=percival|y=ack",
     "762b5b5950e589f82f55c9e73a6d78b8b46a715e1c9f19b4c4bb3ff1db5088d4"),
    ("notice-quoting",
     {"from": "bedivere", "to": "anya-omega", "type": "notice",
      "payload": {"message": "hello world", "count": "007", "ok": True}},
     'v=1|f=bedivere|t=anya-omega|y=notice|p={msg="hello world",count="007",ok=true}',
     'v=1|f=bedivere|p={count="007",msg="hello world",ok=true}|t=anya-omega|y=notice',
     "467cf24195ea55c8846edafbf5ff0b8f870433b0f842093474a1e6837039faf1"),
    ("heartbeat-list-ref-null",
     {"to": "*", "from": "anya-omega", "type": "heartbeat",
      "payload": {"knights": ["gawain", "percival"], "ctx": "~ab12cd", "note": None}},
     'v=1|t="*"|f=anya-omega|y=heartbeat|p={knights=[gawain,percival],x=~ab12cd,note=null}',
     'v=1|f=anya-omega|p={x=~ab12cd,knights=[gawain,percival],note=null}|t="*"|y=heartbeat',
     "46c0a60717aae80ad1212a1b64d2ea9ee6cbf95745c5ef7d2a5ae877024defbc"),
    ("query-nested-escapes",
     {"to": "gawain", "from": "percival", "type": "query",
      "payload": {"target": "manifest", "meta": {"reason": 'line "42" \\ done'}}},
     r'v=1|t=gawain|f=percival|y=query|p={o=manifest,m={w="line \"42\" \\ done"}}',
     r'v=1|f=percival|p={m={w="line \"42\" \\ done"},o=manifest}|t=gawain|y=query',
     "7145d60a82d9aeaab0690609743a0c2715ec1379aac548e57008f7fa87ec9022"),
]

MALFORMED = [
    "",                       # empty
    "t=gawain",               # missing version cell
    "v=2|t=gawain",           # wrong version
    "v=1|t={unclosed",        # unbalanced map
    'v=1|t="unterminated',    # unbalanced string
    "v=1|t=[1,2",             # unbalanced list
    "v=1|bad key=x",          # space in key
    "v=1|t=gawain|t",         # cell without '='
    "v=1||t=x",               # empty cell
    "v=1|t=gawain|p={a=}",    # empty value in map
    "v=1|t='single'",         # single quotes not in grammar
]

# Literal keys that collide with reserved dictionary codes: encode must refuse.
COLLIDING_KEYS = ["t", "f", "y", "p", "v", "msg", "st", "ts", "cx", "cs"]


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
        "script": "test_symbollect.py",
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


def load_symbollect():
    if SYMBOLLECT_PATH not in sys.path:
        sys.path.insert(0, SYMBOLLECT_PATH)
    try:
        import symbollect  # noqa: E402
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)
    for fn in ("encode", "decode", "canonical", "digest"):
        if not callable(getattr(symbollect, fn, None)):
            return None, "symbollect.%s missing or not callable" % fn
    return symbollect, ""


def shuffled_variants(msg):
    """Yield the message with several key-insertion orders (top + nested)."""
    keys = list(msg.keys())
    variants = []
    for perm in itertools.islice(itertools.permutations(keys), 6):
        v = {}
        for k in perm:
            val = msg[k]
            if isinstance(val, dict):
                sub = list(val.keys())
                val = {sk: val[sk] for sk in reversed(sub)}
            v[k] = val
        variants.append(v)
    return variants


def main():
    codec, err = load_symbollect()
    if not check("V-SYM-001", "codec-import", codec is not None,
                 "SYMBOLLECT_PATH=%s err=%s" % (SYMBOLLECT_PATH, err)):
        return

    # V-SYM-001: golden vectors.
    for name, msg, wire, canon, dg in GOLDENS:
        try:
            got_wire = codec.encode(msg)
        except Exception as e:  # noqa: BLE001
            check("V-SYM-001", "golden-%s-wire" % name, False, "encode raised %s: %s" % (type(e).__name__, e))
            continue
        check("V-SYM-001", "golden-%s-wire" % name, got_wire == wire,
              "got=%r want=%r" % (got_wire, wire))
        try:
            got_canon = codec.canonical(msg)
        except Exception as e:  # noqa: BLE001
            check("V-SYM-001", "golden-%s-canonical" % name, False, "canonical raised %s: %s" % (type(e).__name__, e))
            continue
        check("V-SYM-001", "golden-%s-canonical" % name, got_canon == canon,
              "got=%r want=%r" % (got_canon, canon))
        try:
            got_dg = codec.digest(msg)
        except Exception as e:  # noqa: BLE001
            check("V-SYM-001", "golden-%s-digest" % name, False, "digest raised %s: %s" % (type(e).__name__, e))
            continue
        check("V-SYM-001", "golden-%s-digest" % name, got_dg == dg,
              "got=%r want=%r" % (got_dg, dg))
        try:
            back = codec.decode(wire)
        except Exception as e:  # noqa: BLE001
            check("V-SYM-001", "golden-%s-decode" % name, False, "decode raised %s: %s" % (type(e).__name__, e))
            continue
        check("V-SYM-001", "golden-%s-decode" % name, back == msg,
              "got=%r want=%r" % (back, msg))

    # V-SYM-002: canonical stability under key-order shuffling.
    base = GOLDENS[0][1]
    canons = set()
    digests = set()
    stable = True
    for v in shuffled_variants(base):
        try:
            canons.add(codec.canonical(v))
            digests.add(codec.digest(v))
        except Exception as e:  # noqa: BLE001
            stable = False
            check("V-SYM-002", "canonical-stability", False,
                  "raised on shuffled variant: %s: %s" % (type(e).__name__, e))
            break
    if stable:
        check("V-SYM-002", "canonical-stability",
              len(canons) == 1 and len(digests) == 1,
              "distinct canonicals=%d digests=%d" % (len(canons), len(digests)))

    # V-SYM-003: round-trip property on a generated corpus.
    corpus = [
        {"key1": 1, "key2": -2, "key3": 2.75, "key4": True, "key5": False,
         "key6": None, "key7": "bare-symbol_1", "key8": "has space",
         "key9": "007", "key10": "true", "key11": 'q" b\\s', "key12": "l1\nl2",
         "key13": [1, "two", None, True, [3, 4], {"key14": "deep"}],
         "key15": {"key16": {"key17": ["~ref9", 5]}}, "key18": "~ctxid-1"},
        {"to": "x", "from": "y", "type": "notice",
         "payload": {"data": {"alpha": [None, {"beta": ""}]}, "num": 0}},
        {"to": "knight-1", "from": "knight_2.x", "type": "heartbeat", "id": "A-0"},
    ]
    rt_ok = True
    for i, m in enumerate(corpus):
        try:
            w1 = codec.encode(m)
            d1 = codec.decode(w1)
            w2 = codec.encode(d1)
            d2 = codec.decode(w2)
            ok = (w1 == w2) and (d1 == d2) and (d1 == m) and (codec.digest(d1) == codec.digest(m))
        except Exception as e:  # noqa: BLE001
            ok = False
            detail = "msg#%d raised %s: %s" % (i, type(e).__name__, e)
        else:
            detail = "msg#%d wire=%r" % (i, w1[:120])
        if not ok:
            rt_ok = False
            check("V-SYM-003", "roundtrip-msg-%d" % i, False, detail)
    if rt_ok:
        check("V-SYM-003", "roundtrip-property", True)

    # V-SYM-004: malformed packets rejected; reserved-key collisions refused.
    rejected = 0
    for i, bad in enumerate(MALFORMED):
        try:
            codec.decode(bad)
            check("V-SYM-004", "malformed-rejected-%d" % i, False,
                  "decode(%r) did not raise" % bad)
        except Exception:  # noqa: BLE001 - raising is the expected outcome
            rejected += 1
    check("V-SYM-004", "malformed-rejected", rejected == len(MALFORMED),
          "%d/%d malformed inputs rejected" % (rejected, len(MALFORMED)))

    refused = 0
    for k in COLLIDING_KEYS:
        try:
            codec.encode({k: "literal"})
            check("V-SYM-004", "reserved-collision-%s" % k, False,
                  "encode({%r: ...}) did not raise" % k)
        except Exception:  # noqa: BLE001 - raising is the expected outcome
            refused += 1
    check("V-SYM-004", "reserved-collision-refused", refused == len(COLLIDING_KEYS),
          "%d/%d colliding keys refused" % (refused, len(COLLIDING_KEYS)))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - harness must always emit JSON
        _rec("V-SYM-001", "harness", "FAIL", "unexpected exception: %s: %s" % (type(e).__name__, e))
    finish()
