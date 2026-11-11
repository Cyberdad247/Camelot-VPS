# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
pqcrypto_bridge.py — Python bridge to camelot-pqcrypto Rust binary
====================================================================
P2-D. Wraps kinetic_edge/pqcrypto/target/release/camelot-pqcrypto.exe
Provides ML-KEM-768 + ML-DSA-65 operations to Python control plane.

Build (requires cargo):
    cd kinetic_edge/pqcrypto
    cargo build --release
    # binary: target/release/camelot-pqcrypto.exe (Windows) or camelot-pqcrypto (Linux)

Usage:
    from control_plane.pqcrypto_bridge import PQCrypto
    pq = PQCrypto()
    kem_kp = pq.kem_keygen()          # generate key pair
    enc    = pq.kem_encapsulate(peer_ek)
    ss     = pq.kem_decapsulate(enc["ciphertext"], dk)
    dsa_kp = pq.dsa_keygen()
    signed = pq.dsa_sign(b"payload", sk, "sir_boris")
    valid  = pq.dsa_verify(signed)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

CAMELOT_HOME = Path(__file__).parent.parent
_BINARY_CANDIDATES = [
    CAMELOT_HOME / "kinetic_edge" / "pqcrypto" / "target" / "release" / "camelot-pqcrypto.exe",
    CAMELOT_HOME / "kinetic_edge" / "pqcrypto" / "target" / "release" / "camelot-pqcrypto",
    CAMELOT_HOME / "bin" / "camelot-pqcrypto.exe",
    CAMELOT_HOME / "bin" / "camelot-pqcrypto",
]


def _find_binary() -> Optional[Path]:
    for p in _BINARY_CANDIDATES:
        if p.exists():
            return p
    return None


class PQCrypto:
    """
    Thin Python wrapper around camelot-pqcrypto Rust binary.
    All ops go through subprocess — zero Python crypto dependencies.
    Kinetic Purity Law #1: Rust binary handles all crypto, not Python.
    """

    def __init__(self) -> None:
        self._bin = _find_binary()
        if self._bin is None:
            self._stub = True
        else:
            self._stub = False

    def available(self) -> bool:
        return not self._stub

    def _run(self, *args: str) -> dict:
        if self._stub:
            return {"error": "camelot-pqcrypto binary not found — run: cd kinetic_edge/pqcrypto && cargo build --release"}
        result = subprocess.run(
            [str(self._bin), *args],
            capture_output=True, text=True, timeout=15,
            cwd=str(CAMELOT_HOME),
        )
        if result.returncode != 0:
            raise RuntimeError(f"pqcrypto error: {result.stderr.strip()}")
        return json.loads(result.stdout.strip())

    # ── ML-KEM-768 ────────────────────────────────────────────────────────────

    def kem_keygen(self) -> dict:
        """Generate ML-KEM-768 key pair. Returns {encap_key, decap_key, algorithm, key_size_bytes}."""
        return self._run("kem-keygen")

    def kem_encapsulate(self, peer_encap_key_hex: str) -> dict:
        """Encapsulate against peer's encap key. Returns {ciphertext, shared_secret}."""
        return self._run("kem-encapsulate", peer_encap_key_hex)

    def kem_decapsulate(self, ciphertext_hex: str, decap_key_hex: str) -> str:
        """Decapsulate ciphertext with own decap key. Returns shared_secret hex string."""
        result = self._run("kem-decapsulate", ciphertext_hex, decap_key_hex)
        return result.get("shared_secret", "")

    # ── ML-DSA-65 ─────────────────────────────────────────────────────────────

    def dsa_keygen(self) -> dict:
        """Generate ML-DSA-65 signing key pair. Returns {sign_key, verify_key, algorithm, key_size_bytes}."""
        return self._run("dsa-keygen")

    def dsa_sign(self, message: bytes, sign_key_hex: str, knight_id: str) -> dict:
        """Sign message bytes with ML-DSA-65. Returns SignedPayload dict."""
        msg_hex = message.hex()
        return self._run("dsa-sign", msg_hex, sign_key_hex, knight_id)

    def dsa_verify(self, signed_payload: dict) -> bool:
        """Verify a SignedPayload. Returns True if signature is valid."""
        if "error" in signed_payload:
            return False
        result = self._run("dsa-verify", json.dumps(signed_payload))
        return bool(result.get("valid", False))

    # ── Self-test ─────────────────────────────────────────────────────────────

    def self_test(self) -> dict:
        """Run KEM + DSA round-trip test. Returns {status: PASS/FAIL, kem_ok, dsa_ok}."""
        return self._run("self-test")

    # ── A2A channel helper ────────────────────────────────────────────────────

    def secure_a2a_channel(self, sender_id: str, receiver_ek_hex: str) -> dict:
        """
        Establish a post-quantum secure A2A channel.
        Returns {shared_secret, ciphertext, sender_id} — send ciphertext to receiver.
        Receiver calls kem_decapsulate(ciphertext, own_dk) to recover shared_secret.
        Both sides then use shared_secret as AES-256-GCM key for the session.
        """
        enc = self.kem_encapsulate(receiver_ek_hex)
        if "error" in enc:
            return enc
        return {
            "shared_secret": enc["shared_secret"],
            "ciphertext":    enc["ciphertext"],
            "sender_id":     sender_id,
            "algorithm":     "ML-KEM-768",
            "note": "shared_secret → AES-256-GCM session key; send ciphertext to receiver",
        }

    def status(self) -> dict:
        return {
            "binary_found": self.available(),
            "binary_path": str(self._bin) if self._bin else None,
            "algorithms": ["ML-KEM-768 (FIPS 203)", "ML-DSA-65 (FIPS 204)"],
            "security_level": "NIST Level 3",
            "build_cmd": "cd kinetic_edge/pqcrypto && cargo build --release",
        }
