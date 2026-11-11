# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Shadow Provenance — atomic SQLite ledger with .shadow rollback (P2-T07).
========================================================================
Immutable Provenance (Pillar 3) backed by SQLite instead of a flat file. Every
entry is hash-chained (SHA-256 over the prior hash + payload), making the ledger
tamper-evident and append-only.

Atomicity has two layers:
  1. SQLite transactions (BEGIN/COMMIT) for single-statement durability.
  2. A file-level ``.shadow`` snapshot taken before a multi-step mutation. If the
     mutation raises, the shadow is restored over the live DB — the prior state
     comes back exactly, even for partially-applied batches.

Run as module:
    python -m control_plane.shadow_provenance --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_GENESIS = "0" * 64


class ShadowRollback(Exception):
    """Raised to force a transaction to roll back to the shadow snapshot."""


class ShadowProvenance:
    """Append-only, hash-chained SQLite provenance ledger with shadow rollback."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.shadow_path = self.db_path.with_suffix(".shadow")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS provenance ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " ts REAL NOT NULL,"
                " payload TEXT NOT NULL,"
                " prev_hash TEXT NOT NULL,"
                " entry_hash TEXT NOT NULL)"
            )

    @staticmethod
    def _hash(prev_hash: str, payload: str, ts: float) -> str:
        return hashlib.sha256(f"{prev_hash}|{ts}|{payload}".encode()).hexdigest()

    def head_hash(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entry_hash FROM provenance ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return row["entry_hash"] if row else _GENESIS

    def append(self, payload: dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> str:
        """Append one hash-chained entry. Returns the new entry hash."""
        ts = time.time()
        body = json.dumps(payload, sort_keys=True)
        own = conn is None
        c = conn or self._connect()
        try:
            prev = c.execute(
                "SELECT entry_hash FROM provenance ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = prev["entry_hash"] if prev else _GENESIS
            entry_hash = self._hash(prev_hash, body, ts)
            c.execute(
                "INSERT INTO provenance (ts, payload, prev_hash, entry_hash) VALUES (?,?,?,?)",
                (ts, body, prev_hash, entry_hash),
            )
            if own:
                c.commit()
            return entry_hash
        finally:
            if own:
                c.close()

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM provenance").fetchone()["n"]

    def verify_chain(self) -> bool:
        """Recompute the hash chain; True iff intact (tamper-evident)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, payload, prev_hash, entry_hash FROM provenance ORDER BY id"
            ).fetchall()
        prev = _GENESIS
        for r in rows:
            if r["prev_hash"] != prev:
                return False
            if self._hash(prev, r["payload"], r["ts"]) != r["entry_hash"]:
                return False
            prev = r["entry_hash"]
        return True

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Atomic multi-step mutation guarded by a .shadow snapshot.

        Takes a file-level snapshot before yielding. On success, commits. On any
        exception, rolls back the SQLite transaction AND restores the .shadow
        snapshot over the live DB, so the prior state returns exactly. The
        exception is re-raised.
        """
        self._snapshot_shadow()
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            finally:
                conn.close()
            self._restore_shadow()
            raise
        else:
            conn.close()
        finally:
            # keep the shadow for forensic diffing only on success; clean otherwise
            pass

    def _snapshot_shadow(self) -> None:
        if self.db_path.exists():
            shutil.copy2(self.db_path, self.shadow_path)

    def _restore_shadow(self) -> None:
        if self.shadow_path.exists():
            shutil.copy2(self.shadow_path, self.db_path)


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("ShadowProvenance self-test (P2-T07)")
    tmp = Path(tempfile.mkdtemp(prefix="shadowprov_"))
    try:
        sp = ShadowProvenance(tmp / "prov.db")

        # Basic append + hash chaining
        h1 = sp.append({"event": "boot", "v": "9000.14"})
        h2 = sp.append({"event": "phase", "n": 1})
        check("two entries appended", sp.count() == 2)
        check("hash chain intact", sp.verify_chain())
        check("distinct chained hashes", h1 != h2 and len(h1) == 64)

        state_before = sp.count()
        head_before = sp.head_hash()

        # Failing transaction -> shadow restores prior state
        try:
            with sp.transaction() as conn:
                sp.append({"event": "will_be_rolled_back"}, conn=conn)
                sp.append({"event": "also_gone"}, conn=conn)
                raise ShadowRollback("simulated mid-batch failure")
        except ShadowRollback:
            pass
        check("rollback restores entry count", sp.count() == state_before)
        check("rollback restores head hash", sp.head_hash() == head_before)
        check("chain still intact after rollback", sp.verify_chain())

        # Successful transaction commits
        with sp.transaction() as conn:
            sp.append({"event": "committed_a"}, conn=conn)
            sp.append({"event": "committed_b"}, conn=conn)
        check("successful transaction commits both", sp.count() == state_before + 2)
        check("chain intact after commit", sp.verify_chain())

        # Tamper detection
        import sqlite3 as _sq
        con = _sq.connect(sp.db_path)
        con.execute("UPDATE provenance SET payload='TAMPERED' WHERE id=1")
        con.commit(); con.close()
        check("tamper detected by verify_chain", not sp.verify_chain())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — shadow_provenance")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print("ShadowProvenance — use --test to run the rollback self-test.")
