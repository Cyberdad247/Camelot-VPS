# SPDX-License-Identifier: MIT
"""Idempotency Guardian — Phase 1B Ingress & Replay Protection.

Enforces durable idempotency keys backed by PostgreSQL / SQLite WAL
(table: `bifrost_idempotency_journal`) with a high-speed transit accelerator
(<10s fast mutex).

Ingress Protocol:
    1. FastMutex Check: Acquire short-lived mutex lock (tau <= 10s) to absorb
       high-concurrency burst traffic.
    2. Durable Assertion: Check record existence under (client_key, tenant_id) in
       `bifrost_idempotency_journal`.
    3. Payload Mismatch Detection: If record exists and manifest_hash does NOT match,
       raise IdempotencyPayloadMismatchError (HTTP 422 IDEMPOTENCY_PAYLOAD_MISMATCH).
    4. State Machine Evaluation:
       - COMPLETED / COMMITTED: Return cached, signed execution envelope (REPLAY).
       - IN_FLIGHT: Return 409 CONFLICT with Retry-After header bound to lease TTL.
       - REJECTED / Expired: Permit retry or return error.
       - Absent: Write state IN_FLIGHT, bound to the exact manifest_hash, and PROCEED.
"""
from __future__ import annotations

import enum
import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional


class IdempotencyStatus(str, enum.Enum):
    IN_FLIGHT = "IN_FLIGHT"
    COMPLETED = "COMPLETED"
    COMMITTED = "COMPLETED"  # Backward-compatible alias
    REJECTED = "REJECTED"


class IdempotencyDecision(str, enum.Enum):
    PROCEED = "PROCEED"      # New key acquired, caller must execute
    REPLAY = "REPLAY"        # Previously completed, return cached receipt/envelope
    CONFLICT = "CONFLICT"    # Currently in-flight, return 409 Conflict with Retry-After
    REJECTED = "REJECTED"    # Previously rejected


class IdempotencyConflictError(Exception):
    """Raised when an operation is already IN_FLIGHT for the given key (HTTP 409)."""
    def __init__(
        self,
        key: str,
        tenant_id: str,
        correlation_id: str,
        retry_after_sec: int = 5,
        message: str = "",
    ):
        self.key = key
        self.tenant_id = tenant_id
        self.correlation_id = correlation_id
        self.retry_after_sec = max(1, retry_after_sec)
        self.status_code = 409
        self.error_code = "IDEMPOTENCY_CONFLICT"
        super().__init__(
            message or (
                f"Operation '{key}' under tenant '{tenant_id}' is already IN_FLIGHT "
                f"(correlation: '{correlation_id}', retry_after: {self.retry_after_sec}s)."
            )
        )


class IdempotencyPayloadMismatchError(Exception):
    """Raised when an idempotency key is reused with a different payload/manifest (HTTP 422)."""
    def __init__(self, key: str, tenant_id: str, existing_hash: str, new_hash: str):
        self.key = key
        self.tenant_id = tenant_id
        self.existing_hash = existing_hash
        self.new_hash = new_hash
        self.status_code = 422
        self.error_code = "IDEMPOTENCY_PAYLOAD_MISMATCH"
        super().__init__(
            f"IDEMPOTENCY_PAYLOAD_MISMATCH: Key '{key}' for tenant '{tenant_id}' was previously bound "
            f"to manifest '{existing_hash}', cannot execute with '{new_hash}'."
        )


@dataclass
class IdempotencyRecord:
    key: str
    tenant_id: str
    manifest_hash: str
    correlation_id: str
    status: IdempotencyStatus
    receipt_ref: Optional[str]
    response_body: Optional[str]
    expires_at: float  # Unix timestamp
    created_at: float  # Unix timestamp
    updated_at: float  # Unix timestamp

    @property
    def compound_key(self) -> str:
        return compute_compound_key(self.key, self.tenant_id, self.manifest_hash)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_compound_key(key: str, tenant_id: str, manifest_hash: str) -> str:
    """Compute deterministic SHA-256 compound tuple."""
    raw = f"{key}:{tenant_id}:{manifest_hash}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class FastMutexAccelerator:
    """In-memory fast mutex accelerator (tau <= 10s transit lock).

    Absorbs sub-second concurrent burst collisions without unnecessary DB pressure.
    """
    def __init__(self, default_ttl_sec: float = 10.0):
        self._lock = threading.Lock()
        self._default_ttl = min(default_ttl_sec, 10.0)
        self._locks: dict[str, float] = {}  # tenant:key -> expiry_ts

    def try_acquire(self, tenant_id: str, key: str, ttl_sec: Optional[float] = None) -> bool:
        lock_id = f"{tenant_id}:{key}"
        ttl = min(ttl_sec if ttl_sec is not None else self._default_ttl, 10.0)
        now = time.time()
        with self._lock:
            # Purge expired entry if present
            if lock_id in self._locks and self._locks[lock_id] <= now:
                del self._locks[lock_id]

            if lock_id in self._locks:
                return False  # Actively locked
            self._locks[lock_id] = now + ttl
            return True

    def release(self, tenant_id: str, key: str) -> None:
        lock_id = f"{tenant_id}:{key}"
        with self._lock:
            self._locks.pop(lock_id, None)

    def is_locked(self, tenant_id: str, key: str) -> bool:
        lock_id = f"{tenant_id}:{key}"
        now = time.time()
        with self._lock:
            exp = self._locks.get(lock_id)
            if exp is None:
                return False
            if exp <= now:
                del self._locks[lock_id]
                return False
            return True


class DurableIdempotencyStore:
    """Thread-safe SQLite/PostgreSQL durable WAL store for bifrost_idempotency_journal."""

    TABLE_NAME = "bifrost_idempotency_journal"

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:", check_same_thread=False, timeout=15.0)
            self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        if self._conn is None:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                if self.db_path != ":memory:":
                    conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                        client_key TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        manifest_hash TEXT NOT NULL,
                        correlation_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        receipt_ref TEXT,
                        response_body TEXT,
                        expires_at REAL NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        PRIMARY KEY (tenant_id, client_key)
                    );
                """)
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_bifrost_idemp_tenant_manifest 
                    ON {self.TABLE_NAME} (tenant_id, manifest_hash);
                """)
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_bifrost_idemp_expiry 
                    ON {self.TABLE_NAME} (expires_at);
                """)
                conn.commit()
            finally:
                self._close_conn(conn)

    def get_by_key(self, client_key: str, tenant_id: str) -> Optional[IdempotencyRecord]:
        """Look up active record by (client_key, tenant_id)."""
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    f"SELECT * FROM {self.TABLE_NAME} WHERE client_key = ? AND tenant_id = ?",
                    (client_key, tenant_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                status_raw = row["status"]
                status_enum = (
                    IdempotencyStatus.COMPLETED
                    if status_raw in ("COMPLETED", "COMMITTED")
                    else IdempotencyStatus(status_raw)
                )
                return IdempotencyRecord(
                    key=row["client_key"],
                    tenant_id=row["tenant_id"],
                    manifest_hash=row["manifest_hash"],
                    correlation_id=row["correlation_id"],
                    status=status_enum,
                    receipt_ref=row["receipt_ref"],
                    response_body=row["response_body"],
                    expires_at=float(row["expires_at"]),
                    created_at=float(row["created_at"]),
                    updated_at=float(row["updated_at"]),
                )
            finally:
                self._close_conn(conn)

    def insert_in_flight(self, record: IdempotencyRecord) -> bool:
        """Insert IN_FLIGHT record. Returns True if inserted, False if conflict."""
        with self._lock:
            conn = self._get_conn()
            try:
                now = time.time()
                cur = conn.execute(
                    f"SELECT status, expires_at FROM {self.TABLE_NAME} WHERE client_key = ? AND tenant_id = ?",
                    (record.key, record.tenant_id),
                )
                existing = cur.fetchone()
                if existing:
                    if (
                        existing["status"] == IdempotencyStatus.REJECTED.value
                        or float(existing["expires_at"]) <= now
                    ):
                        conn.execute(
                            f"DELETE FROM {self.TABLE_NAME} WHERE client_key = ? AND tenant_id = ?",
                            (record.key, record.tenant_id),
                        )
                    else:
                        return False

                conn.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME} (
                        client_key, tenant_id, manifest_hash, correlation_id,
                        status, receipt_ref, response_body, expires_at,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.key,
                        record.tenant_id,
                        record.manifest_hash,
                        record.correlation_id,
                        record.status.value,
                        record.receipt_ref,
                        record.response_body,
                        record.expires_at,
                        record.created_at,
                        record.updated_at,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                self._close_conn(conn)

    def update_status(
        self,
        client_key: str,
        tenant_id: str,
        status: IdempotencyStatus,
        receipt_ref: Optional[str] = None,
        response_body: Optional[str] = None,
    ) -> Optional[IdempotencyRecord]:
        with self._lock:
            conn = self._get_conn()
            try:
                now = time.time()
                cur = conn.execute(
                    f"""
                    UPDATE {self.TABLE_NAME}
                    SET status = ?, receipt_ref = COALESCE(?, receipt_ref),
                        response_body = COALESCE(?, response_body),
                        updated_at = ?
                    WHERE client_key = ? AND tenant_id = ?
                    """,
                    (status.value, receipt_ref, response_body, now, client_key, tenant_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
            finally:
                self._close_conn(conn)
        return self.get_by_key(client_key, tenant_id)

    def purge_expired(self) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                now = time.time()
                cur = conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE expires_at < ?", (now,))
                deleted = cur.rowcount
                conn.commit()
                return deleted
            finally:
                self._close_conn(conn)


class IdempotencyGuardian:
    """The Sovereign Ingress Idempotency Guardian.

    Coordinates FastMutex (<10s) and PostgreSQL/SQLite WAL store for zero-drift execution.
    """

    def __init__(
        self,
        store: Optional[DurableIdempotencyStore] = None,
        fast_mutex: Optional[FastMutexAccelerator] = None,
    ):
        self.store = store or DurableIdempotencyStore(":memory:")
        self.fast_mutex = fast_mutex or FastMutexAccelerator(default_ttl_sec=10.0)

    def acquire_or_replay(
        self,
        key: str,
        tenant_id: str,
        manifest_hash: str,
        correlation_id: str,
        ttl_seconds: float = 300.0,
    ) -> tuple[IdempotencyDecision, Optional[IdempotencyRecord]]:
        """Ingress Protocol (§12.2 / Phase 1B).

        1. FastMutex Check: Acquire short-lived transit mutex lock (tau <= 10s).
        2. Assert Existence: Look up (key, tenant_id) in durable WAL.
        3. Payload Mismatch Rule: If key exists under tenant and manifest_hash differs,
           raise IdempotencyPayloadMismatchError (HTTP 422).
        4. State Evaluation:
           - COMPLETED / COMMITTED: return (REPLAY, record) with cached execution envelope.
           - IN_FLIGHT: raise IdempotencyConflictError (HTTP 409) with retry_after_sec.
           - Absent: insert IN_FLIGHT and return (PROCEED, record).
        """
        now = time.time()

        # 1. First check durable WAL for existing record
        existing = self.store.get_by_key(key, tenant_id)
        if existing:
            # Payload Mismatch check: identical key reused with different manifest
            if existing.manifest_hash != manifest_hash:
                # If expired, we allow overwrite below after purge; if active, hard-reject 422
                if existing.expires_at > now and existing.status != IdempotencyStatus.REJECTED:
                    raise IdempotencyPayloadMismatchError(
                        key=key,
                        tenant_id=tenant_id,
                        existing_hash=existing.manifest_hash,
                        new_hash=manifest_hash,
                    )
                else:
                    self.store.purge_expired()

            elif existing.expires_at <= now:
                # Expired identical record -> purge and proceed
                self.store.purge_expired()

            elif existing.status in (IdempotencyStatus.COMPLETED, IdempotencyStatus.COMMITTED):
                # Already completed: return cached signed receipt / execution envelope
                self.fast_mutex.release(tenant_id, key)
                return IdempotencyDecision.REPLAY, existing

            elif existing.status == IdempotencyStatus.IN_FLIGHT:
                # Actively in-flight in DB -> 409 CONFLICT with Retry-After header
                retry_after = max(1, int(existing.expires_at - now))
                raise IdempotencyConflictError(
                    key=key,
                    tenant_id=tenant_id,
                    correlation_id=existing.correlation_id,
                    retry_after_sec=retry_after,
                )

        # 2. FastMutex check (absorb high-concurrency burst traffic)
        if not self.fast_mutex.try_acquire(tenant_id, key, ttl_sec=min(ttl_seconds, 10.0)):
            existing = self.store.get_by_key(key, tenant_id)
            cid = existing.correlation_id if existing else correlation_id
            retry_after = max(1, int((existing.expires_at - now) if existing else 5))
            raise IdempotencyConflictError(
                key=key,
                tenant_id=tenant_id,
                correlation_id=cid,
                retry_after_sec=retry_after,
                message="FastMutex burst collision: operation is in flight",
            )

        # 3. Write state IN_FLIGHT to durable WAL
        record = IdempotencyRecord(
            key=key,
            tenant_id=tenant_id,
            manifest_hash=manifest_hash,
            correlation_id=correlation_id,
            status=IdempotencyStatus.IN_FLIGHT,
            receipt_ref=None,
            response_body=None,
            expires_at=now + ttl_seconds,
            created_at=now,
            updated_at=now,
        )

        inserted = self.store.insert_in_flight(record)
        if not inserted:
            existing = self.store.get_by_key(key, tenant_id)
            cid = existing.correlation_id if existing else correlation_id
            retry_after = max(1, int((existing.expires_at - now) if existing else 5))
            raise IdempotencyConflictError(
                key=key,
                tenant_id=tenant_id,
                correlation_id=cid,
                retry_after_sec=retry_after,
                message="Durable WAL collision: operation is in flight",
            )

        return IdempotencyDecision.PROCEED, record

    def commit(
        self,
        key: str,
        tenant_id: str,
        manifest_hash: str,
        receipt_ref: str,
        response_body: Optional[Any] = None,
    ) -> IdempotencyRecord:
        """Mark record COMPLETED with the emitted signed receipt / execution envelope."""
        # Assert matching manifest before committing
        existing = self.store.get_by_key(key, tenant_id)
        if existing and existing.manifest_hash != manifest_hash:
            raise IdempotencyPayloadMismatchError(key, tenant_id, existing.manifest_hash, manifest_hash)

        serialized_body = None
        if response_body is not None:
            if isinstance(response_body, (dict, list)):
                serialized_body = json.dumps(response_body)
            else:
                serialized_body = str(response_body)

        updated = self.store.update_status(
            client_key=key,
            tenant_id=tenant_id,
            status=IdempotencyStatus.COMPLETED,
            receipt_ref=receipt_ref,
            response_body=serialized_body,
        )
        self.fast_mutex.release(tenant_id, key)
        if not updated:
            raise ValueError(f"No idempotency record found to commit for key '{key}' under tenant '{tenant_id}'")
        return updated

    def reject(
        self,
        key: str,
        tenant_id: str,
        manifest_hash: str,
        reason: Optional[str] = None,
    ) -> IdempotencyRecord:
        """Mark record REJECTED upon execution or verification failure."""
        updated = self.store.update_status(
            client_key=key,
            tenant_id=tenant_id,
            status=IdempotencyStatus.REJECTED,
            response_body=reason,
        )
        self.fast_mutex.release(tenant_id, key)
        if not updated:
            raise ValueError(f"No idempotency record found to reject for key '{key}' under tenant '{tenant_id}'")
        return updated

    def purge_expired(self) -> int:
        return self.store.purge_expired()
