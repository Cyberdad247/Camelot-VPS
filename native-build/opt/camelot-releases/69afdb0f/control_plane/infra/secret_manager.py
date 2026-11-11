# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
SecretManager — zero-cost, sovereign secret storage for CAMELOT-OS.

No paid vault, no cloud KMS, no Docker. Secrets live in a local Fernet-encrypted
file (~/.camelot/secrets.enc); the master key is read from $CAMELOT_SECRET_KEY or
an auto-generated local keyfile (~/.camelot/secret.key, 0600). Reads honor an
environment override (a process env var of the same name wins), so ops can inject
secrets without persisting them.

Values are never logged; an append-only audit (names + op + ts, no values) lands
in ~/.camelot/secret_audit.jsonl. If `cryptography` is unavailable the manager
runs in env-only mode (get works from env; persistence raises).

Usage:
    from control_plane.secret_manager import get_secret_manager
    sm = get_secret_manager()
    sm.set("WEBHOOK_SECRET", "…")
    token = sm.get("WEBHOOK_SECRET")     # env override > encrypted store
    sm.rotate_key()                      # re-encrypt under a fresh master key
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken

    _CRYPTO = True
except Exception:  # pragma: no cover - exercised only without cryptography
    _CRYPTO = False

_CAMELOT_HOME = Path(os.environ.get("CAMELOT_HOME", str(Path.home() / ".camelot")))


class SecretError(RuntimeError):
    """Raised on unrecoverable secret-store errors (bad key, no crypto, I/O)."""


class SecretManager:
    def __init__(
        self,
        store_path: Optional[Path] = None,
        key_path: Optional[Path] = None,
        audit_path: Optional[Path] = None,
    ) -> None:
        self._store = store_path or (_CAMELOT_HOME / "secrets.enc")
        self._keyfile = key_path or (_CAMELOT_HOME / "secret.key")
        self._audit = audit_path or (_CAMELOT_HOME / "secret_audit.jsonl")
        self._fernet = Fernet(self._load_or_create_key()) if _CRYPTO else None

    # ── key management ──────────────────────────────────────────────────────
    def _load_or_create_key(self) -> bytes:
        env_key = os.environ.get("CAMELOT_SECRET_KEY")
        if env_key:
            return env_key.encode()
        if self._keyfile.exists():
            return self._keyfile.read_bytes()
        key = Fernet.generate_key()
        self._keyfile.parent.mkdir(parents=True, exist_ok=True)
        self._keyfile.write_bytes(key)
        try:
            os.chmod(self._keyfile, 0o600)  # best-effort (no-op on some Windows FS)
        except OSError:
            pass
        return key

    # ── store I/O ───────────────────────────────────────────────────────────
    def _read_store(self) -> dict:
        if self._fernet is None:
            return {}
        if not self._store.exists():
            return {}
        raw = self._store.read_bytes()
        if not raw:
            return {}
        try:
            return json.loads(self._fernet.decrypt(raw).decode("utf-8"))
        except InvalidToken as exc:
            raise SecretError("cannot decrypt secret store (wrong/rotated key?)") from exc

    def _write_store(self, data: dict) -> None:
        if self._fernet is None:
            raise SecretError("cryptography unavailable — cannot persist secrets")
        self._store.parent.mkdir(parents=True, exist_ok=True)
        self._store.write_bytes(self._fernet.encrypt(json.dumps(data).encode("utf-8")))

    def _audit_log(self, op: str, name: str) -> None:
        try:
            self._audit.parent.mkdir(parents=True, exist_ok=True)
            with open(self._audit, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.time(), "op": op, "name": name}) + "\n")
        except OSError:
            pass  # audit is best-effort; never block the operation

    # ── public API ──────────────────────────────────────────────────────────
    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Resolve a secret: process env override first, then encrypted store."""
        env_val = os.environ.get(name)
        if env_val is not None:
            return env_val
        return self._read_store().get(name, default)

    def set(self, name: str, value: str) -> None:
        data = self._read_store()
        data[name] = value
        self._write_store(data)
        self._audit_log("set", name)

    def delete(self, name: str) -> bool:
        data = self._read_store()
        if name not in data:
            return False
        del data[name]
        self._write_store(data)
        self._audit_log("delete", name)
        return True

    def list_names(self) -> list[str]:
        """Return secret names only (never values)."""
        return sorted(self._read_store().keys())

    def rotate_key(self) -> bytes:
        """Generate a fresh master key, re-encrypt the store, persist the key.

        Returns the new key. If $CAMELOT_SECRET_KEY is in use, also update that
        env/secret to the returned value (the keyfile is written regardless).
        """
        if self._fernet is None:
            raise SecretError("cryptography unavailable — cannot rotate")
        data = self._read_store()  # decrypt with current key
        new_key = Fernet.generate_key()
        self._fernet = Fernet(new_key)
        self._write_store(data)  # re-encrypt under the new key
        self._keyfile.parent.mkdir(parents=True, exist_ok=True)
        self._keyfile.write_bytes(new_key)
        try:
            os.chmod(self._keyfile, 0o600)
        except OSError:
            pass
        self._audit_log("rotate_key", "*")
        return new_key


# ── module-level singleton ──────────────────────────────────────────────────
_sm: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    global _sm
    if _sm is None:
        _sm = SecretManager()
    return _sm


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    return get_secret_manager().get(name, default)


# ── credential validators ────────────────────────────────────────────────────

def looks_like_gemini_key(value: Optional[str]) -> bool:
    """True if `value` matches the Google AI Studio / Gemini key shape (AIza…).

    Catches the common mistake of pasting an OAuth/ephemeral token (AQ.…, ya29.…)
    where a long-lived GEMINI_API_KEY is expected.
    """
    if not value:
        return False
    import re

    return bool(re.fullmatch(r"AIza[0-9A-Za-z_\-]{35}", value.strip()))


# ── CLI: store/inspect secrets without echoing values ─────────────────────────

def _main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import getpass

    parser = argparse.ArgumentParser(description="CAMELOT-OS secret manager (local, encrypted)")
    sub = parser.add_subparsers(dest="cmd")

    p_set = sub.add_parser("set", help="Store a secret (value read via hidden prompt — never echoed)")
    p_set.add_argument("name")

    sub.add_parser("status", help="List stored secret names (never values)")

    p_check = sub.add_parser("check", help="Report whether a secret is present (+ format hint)")
    p_check.add_argument("name")

    p_del = sub.add_parser("delete", help="Delete a stored secret")
    p_del.add_argument("name")

    sub.add_parser("rotate", help="Rotate the master key (re-encrypt the store)")

    args = parser.parse_args(argv)
    sm = get_secret_manager()

    if args.cmd == "set":
        value = getpass.getpass(f"{args.name} (hidden): ")
        if not value:
            print("[abort] empty value")
            return 1
        if args.name == "GEMINI_API_KEY" and not looks_like_gemini_key(value):
            print("[warn] value does not look like a Gemini key (expected 'AIza…', 39 chars).")
        sm.set(args.name, value)
        print(f"[ok] stored {args.name} (encrypted; value not displayed)")
    elif args.cmd == "status":
        names = sm.list_names()
        print(f"{len(names)} secret(s): {', '.join(names) if names else '(none)'}")
    elif args.cmd == "check":
        present = sm.get(args.name) is not None
        print(f"{args.name}: {'present' if present else 'MISSING'}")
        if args.name == "GEMINI_API_KEY" and present:
            ok = looks_like_gemini_key(sm.get(args.name))
            print(f"  format: {'looks valid (AIza…)' if ok else 'WARNING — not an AIza… Gemini key'}")
        return 0 if present else 1
    elif args.cmd == "delete":
        print("[ok] deleted" if sm.delete(args.name) else "[noop] not found")
    elif args.cmd == "rotate":
        sm.rotate_key()
        print("[ok] master key rotated; store re-encrypted")
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
