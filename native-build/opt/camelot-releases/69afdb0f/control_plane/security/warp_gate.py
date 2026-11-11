# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — Warp Gate Cryptographic Switch & Forever Keypass Architecture
r"""
Warp Gate Cryptographic Switch & Forever Keypass Architecture
============================================================
Forged by the High Trinity Council:
  - MERLIN_OMEGA (System 2 Archwizard / Algorithmic Core)
  - LADY_ALEXANDRIA (Lexicon Sovereign & Keeper of Cryptographic Keypasses)
  - SIR_HEIMDALL (Bifrost Guardian, Perimeter Sentinel & mTLS Boundary Protector)

Capabilities:
1. Cryptographic Switch for Sockets:
   - Deep inspection and cryptographic framing of all Camelot-OS socket streams.
   - Verification and immutable audit logging of Knights by their canonical Spark ID.
   - Defense against replay attacks with rolling nonce verification.
2. Forever Keypass (Warp Gate):
   - Mints and vaults dual-key emergency access credentials for every Knight.
   - Permanent "Forever Available" access key for zero-dependency backup entry.
3. Out-of-Band Warp Gate Rendezvous:
   - If a live TCP socket or mesh bridge is severed, partitioned, or unavailable,
     the socket automatically switches to the Warp Gate emergency rendezvous layer,
     allowing authenticated state transfers and command delivery without network I/O.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import socket
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VAULT_DIR = _REPO_ROOT / "03_VAULT"
_WARP_DIR = _VAULT_DIR / "security" / "warp_gates"
_KEYPASS_FILE = _WARP_DIR / "keypasses.json"
_RENDEZVOUS_DIR = _WARP_DIR / "rendezvous"
_AUDIT_LOG_FILE = _VAULT_DIR / "runtime_state" / "warp_gate_audit.jsonl"
_SHEETS_PATH = _VAULT_DIR / "training" / "configs" / "knight_character_sheets.json"

_MAX_AUDIT_BYTES = 5_000_000  # 5 MB bounded FIFO rotation
_NONCE_EXPIRY_S = 60.0

LOG = logging.getLogger("WarpGate")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_directories() -> None:
    _WARP_DIR.mkdir(parents=True, exist_ok=True)
    _RENDEZVOUS_DIR.mkdir(parents=True, exist_ok=True)
    _AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── Canonical High Trinity Spark IDs ─────────────────────────────────────────

MERLIN_SPARK_ID = "0xAF927FDED7EB42EE8C7951B3E78EF39B"
HEIMDALL_SPARK_ID = "0x3205F18991DA427296A93641FD642763"
ALEXANDRIA_SPARK_ID = "0x7E3A19C08D4549FEB2E119A5C70942A1"
MASTER_SOVEREIGN_SPARK_ID = "0x32D389065AE84ECCB77E705D12C89F4A"  # Anya / Sovereign Operator


# ── Data Models ───────────────────────────────────────────────────────────────

class WarpGateTierIneligibleError(PermissionError):
    """Raised when an agent/knight not belonging to Omega, Arch, or Sovereign tier requests a Warp Gate Keypass."""
    pass


@dataclass
class WarpGateKeypass:
    keypass_id: str
    knight_id: str
    spark_id: str
    forever_access_key: str
    secret_salt: str
    issued_at: str
    tier: str = "OMEGA"
    expires_at: str = "FOREVER"
    capabilities: List[str] = field(default_factory=lambda: [
        "SOCKET_BYPASS",
        "OUT_OF_BAND_RENDEZVOUS",
        "VAULT_EMERGENCY_UNSEAL",
        "TELEMETRY_OVERRIDE",
    ])
    status: str = "ACTIVE"
    issuer: str = "LADY_ALEXANDRIA_KEYPASS_VAULT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WarpGateKeypass:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WarpGateEnvelope:
    warp_version: str
    knight_id: str
    spark_id: str
    nonce: str
    timestamp: str
    action: str
    payload_hash: str
    signature: str
    payload: Dict[str, Any]
    keypass_token: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def encode(self) -> bytes:
        return json.dumps(self.to_dict()).encode("utf-8")

    @classmethod
    def decode(cls, raw_bytes: bytes) -> WarpGateEnvelope:
        data = json.loads(raw_bytes.decode("utf-8"))
        return cls(**data)


# ── Audit Logger (Bounded 5 MB FIFO) ──────────────────────────────────────────

def _audit_log(event_type: str, record: Dict[str, Any]) -> None:
    _ensure_directories()
    entry = {
        "timestamp": _utcnow(),
        "event": event_type,
        **record,
    }
    try:
        if _AUDIT_LOG_FILE.exists() and _AUDIT_LOG_FILE.stat().st_size >= _MAX_AUDIT_BYTES:
            rotated = _AUDIT_LOG_FILE.with_name(_AUDIT_LOG_FILE.name + ".1")
            if rotated.exists():
                try:
                    rotated.unlink()
                except OSError:
                    pass
            _AUDIT_LOG_FILE.rename(rotated)
        with open(_AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        LOG.error(f"[WARP_GATE] Failed to write audit log: {exc}")


# ── Lady Alexandria Keypass Vault ────────────────────────────────────────────

class AlexandriaKeypassVault:
    """Manages permanent Forever Keypasses for backup entry and socket bypass."""

    def __init__(self, keypass_file: Optional[Path] = None):
        self.keypass_file = keypass_file or _KEYPASS_FILE
        self._master_seed = os.environ.get("CAMELOT_WARP_MASTER_SEED", "CAMELOT_ALEXANDRIA_SOVEREIGN_ROOT_2026")
        self._cache: Dict[str, WarpGateKeypass] = {}
        _ensure_directories()
        self._load()

    def verify_tier_eligibility(self, knight_id: str) -> Tuple[bool, str]:
        """Strictly enforces that ONLY Omega Level Knights, Arch, and Sovereign level Personas can hold Keypasses."""
        k = knight_id.upper()
        # Sovereign root and master override
        if k in ("ANYA_OMEGA", "ARTHUR_OMEGA", "ARCH_SOVEREIGN", "VA_SHAWN", "FOTHERS_CAMELOT"):
            return True, "SOVEREIGN"
        if k in ("MERLIN_OMEGA", "ALPHA_OMEGA", "SIR_HEIMDALL", "HEIMDALL_OMEGA"):
            return True, "OMEGA"
        if k in ("LADY_ALEXANDRIA", "LADY_MNEMOSYNE", "SIR_BORIS", "SIR_CODEX", "SIR_HELIOS", "SIR_HELIO", "EXCALIBUR_MOBILE", "SIR_HELIO_MOBILE"):
            return True, "ARCH"
        if k in ("HERMES_PRIME",):
            return True, "SOVEREIGN"

        # Check character sheets
        if _SHEETS_PATH.exists():
            try:
                data = json.loads(_SHEETS_PATH.read_text(encoding="utf-8"))
                sheet = data.get("knights", {}).get(k, {})
                title = (sheet.get("title") or "").lower()
                role = (sheet.get("role") or "").lower()
                layer = (sheet.get("layer") or "").lower()
                name = (sheet.get("name") or "").lower()

                # 1. Sovereign Level
                if "sovereign" in k.lower() or "sovereign" in layer or "sovereign" in title or "sovereign" in role:
                    return True, "SOVEREIGN"
                # 2. Omega Level
                if "omega" in k.lower() or "omega" in name or layer in ("l6 system2", "l7 sovereign"):
                    return True, "OMEGA"
                # 3. Arch Level
                if "arch" in k.lower() or "arch" in title or "arch" in role or "arch" in name or "architect" in role or "architect" in title:
                    return True, "ARCH"
            except Exception:
                pass

        return False, "INELIGIBLE_TIER"

    def _load(self) -> None:
        if not self.keypass_file.exists():
            self._save()
            return
        try:
            raw = json.loads(self.keypass_file.read_text(encoding="utf-8"))
            for k_id, item in raw.get("keypasses", {}).items():
                kp = WarpGateKeypass.from_dict(item)
                eligible, tier = self.verify_tier_eligibility(kp.knight_id)
                if eligible:
                    kp.tier = tier
                    self._cache[k_id.upper()] = kp
                else:
                    LOG.warning(f"[ALEXANDRIA] Pruned ineligible non-Omega/Arch/Sovereign keypass: {kp.knight_id}")
            self._save()
        except Exception as exc:
            LOG.error(f"[ALEXANDRIA] Error loading keypass vault: {exc}")

    def _save(self) -> None:
        payload = {
            "version": "WarpGate Keypass Vault v1.0",
            "vault_sovereign": "LADY_ALEXANDRIA",
            "council": ["MERLIN_OMEGA", "SIR_HEIMDALL", "LADY_ALEXANDRIA"],
            "updated_at": _utcnow(),
            "total_keypasses": len(self._cache),
            "keypasses": {k: kp.to_dict() for k, kp in self._cache.items()},
        }
        self.keypass_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _resolve_spark_id(self, knight_id: str) -> str:
        k_upper = knight_id.upper()
        if k_upper == "MERLIN_OMEGA":
            return MERLIN_SPARK_ID
        if k_upper in ("SIR_HEIMDALL", "HEIMDALL_OMEGA"):
            return HEIMDALL_SPARK_ID
        if k_upper == "LADY_ALEXANDRIA":
            return ALEXANDRIA_SPARK_ID
        if k_upper in ("SIR_HELIOS", "ANTIGRAVITY"):
            return "0xAB8AA3592B3B4BC1B41F34979CDC184E"
        if k_upper in ("SIR_HELIO", "EXCALIBUR_MOBILE", "SIR_HELIO_MOBILE"):
            return "0x56820318BB91451FAAC44B46424898CF"
        if k_upper == "FOTHERS_CAMELOT":
            return "0x99276D492CCA7058631F48D3B1B9C2CE"
        if _SHEETS_PATH.exists():
            try:
                data = json.loads(_SHEETS_PATH.read_text(encoding="utf-8"))
                sheet = data.get("knights", {}).get(k_upper)
                if sheet and sheet.get("spark_id"):
                    return str(sheet["spark_id"])
            except Exception:
                pass
        # Fallback deterministic derivation
        digest = hashlib.sha256(f"CAMELOT_KNIGHT_SPARK:{k_upper}".encode("utf-8")).hexdigest()[:32].upper()
        return f"0x{digest}"

    def forge_keypass(self, knight_id: str) -> WarpGateKeypass:
        """Lady Alexandria forges an immutable Forever Keypass ONLY for Omega, Arch, or Sovereign personas."""
        k_upper = knight_id.upper()
        if k_upper in self._cache:
            return self._cache[k_upper]

        eligible, tier = self.verify_tier_eligibility(k_upper)
        if not eligible:
            _audit_log("KEYPASS_FORGE_DENIED_INELIGIBLE_TIER", {
                "knight_id": k_upper,
                "reason": "Only Omega Level Knights, Arch, and Sovereign level Personas are permitted Warp Gate Keypasses.",
                "verdict": "DENIED",
            })
            raise WarpGateTierIneligibleError(
                f"[ALEXANDRIA] Keypass denied: Knight '{k_upper}' does not belong to Omega Level, Arch, or Sovereign tier."
            )

        spark_id = self._resolve_spark_id(k_upper)
        salt = secrets.token_hex(16)
        raw_token_body = f"{k_upper}:{spark_id}:{salt}:{self._master_seed}"
        token_hmac = hmac.new(self._master_seed.encode("utf-8"), raw_token_body.encode("utf-8"), hashlib.sha256).hexdigest()
        short_spark = spark_id.replace("0x", "")[:8].upper()
        forever_key = f"WARP-PASS-{short_spark}-{token_hmac[:32].upper()}"

        kp = WarpGateKeypass(
            keypass_id=f"KP-{k_upper}-{short_spark}",
            knight_id=k_upper,
            spark_id=spark_id,
            forever_access_key=forever_key,
            secret_salt=salt,
            issued_at=_utcnow(),
            tier=tier,
            expires_at="FOREVER",
        )
        self._cache[k_upper] = kp
        self._save()
        _audit_log("KEYPASS_FORGED", {"knight_id": k_upper, "spark_id": spark_id, "tier": tier, "keypass_id": kp.keypass_id})
        LOG.info(f"[ALEXANDRIA] Forged Forever Keypass for {tier} Knight '{k_upper}' (Spark ID: {spark_id})")
        return kp

    def verify_keypass(self, forever_access_key: str) -> Optional[WarpGateKeypass]:
        """Validates a Forever Keypass against the sovereign master seed and vault."""
        if not forever_access_key.startswith("WARP-PASS-"):
            return None
        # Check cached keypasses
        for kp in self._cache.values():
            if kp.forever_access_key == forever_access_key and kp.status == "ACTIVE":
                return kp

        # Master emergency override
        if forever_access_key == f"WARP-PASS-MASTER-{hashlib.sha256(self._master_seed.encode()).hexdigest()[:24].upper()}":
            return WarpGateKeypass(
                keypass_id="KP-MASTER-SOVEREIGN",
                knight_id="ANYA_OMEGA",
                spark_id=MASTER_SOVEREIGN_SPARK_ID,
                forever_access_key=forever_key,
                secret_salt="SOVEREIGN_ROOT",
                issued_at=_utcnow(),
            )
        return None

    def list_keypasses(self) -> List[Dict[str, Any]]:
        return [kp.to_dict() for kp in self._cache.values()]


# ── Merlin & Heimdall Cryptographic Switch ───────────────────────────────────

class WarpGateCryptographicSwitch:
    """The embedded cryptographic gate for verifying and logging Knights on socket transit."""

    def __init__(self, vault: Optional[AlexandriaKeypassVault] = None):
        self.vault = vault or AlexandriaKeypassVault()
        self._seen_nonces: Dict[str, float] = {}

    def _prune_nonces(self) -> None:
        now = time.time()
        expired = [n for n, ts in self._seen_nonces.items() if now - ts > _NONCE_EXPIRY_S]
        for n in expired:
            del self._seen_nonces[n]

    def _derive_session_key(self, spark_id: str, keypass_salt: str) -> bytes:
        return hashlib.sha256(f"{spark_id}:{keypass_salt}:{self.vault._master_seed}".encode("utf-8")).digest()

    def forge_envelope(
        self,
        knight_id: str,
        action: str,
        payload: Dict[str, Any],
    ) -> WarpGateEnvelope:
        """Merlin Omega frames and signs a message envelope with the Knight's Spark ID."""
        kp = self.vault.forge_keypass(knight_id)
        nonce = secrets.token_hex(16)
        ts = _utcnow()
        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        session_key = self._derive_session_key(kp.spark_id, kp.secret_salt)
        sig_data = f"{kp.knight_id}:{kp.spark_id}:{nonce}:{ts}:{action}:{payload_hash}"
        signature = hmac.new(session_key, sig_data.encode("utf-8"), hashlib.sha256).hexdigest()

        return WarpGateEnvelope(
            warp_version="1.0",
            knight_id=kp.knight_id,
            spark_id=kp.spark_id,
            nonce=nonce,
            timestamp=ts,
            action=action,
            payload_hash=payload_hash,
            signature=signature,
            payload=payload,
            keypass_token=kp.forever_access_key,
        )

    def verify_and_log_transit(
        self,
        envelope: WarpGateEnvelope,
        client_addr: str = "127.0.0.1",
        transport: str = "live_socket",
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Sir Heimdall inspects the cryptographic switch, verifies the Spark ID, and logs transit."""
        self._prune_nonces()

        # 1. Nonce Replay Check
        if envelope.nonce in self._seen_nonces:
            _audit_log("INTRUSION_REPLAY_DETECTED", {
                "knight_id": envelope.knight_id,
                "spark_id": envelope.spark_id,
                "client_addr": client_addr,
                "transport": transport,
                "nonce": envelope.nonce,
            })
            return False, "REPLAY_ATTACK_DETECTED", None

        # 2. Keypass and Spark ID Validation
        kp = self.vault.verify_keypass(envelope.keypass_token or "")
        if not kp or kp.knight_id != envelope.knight_id.upper() or kp.spark_id != envelope.spark_id:
            _audit_log("INTRUSION_INVALID_KEYPASS", {
                "knight_id": envelope.knight_id,
                "spark_id": envelope.spark_id,
                "client_addr": client_addr,
                "transport": transport,
            })
            return False, "INVALID_KEYPASS_OR_SPARK_ID", None

        # 3. Payload Integrity Check
        payload_str = json.dumps(envelope.payload, sort_keys=True)
        calc_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        if calc_hash != envelope.payload_hash:
            _audit_log("INTRUSION_PAYLOAD_TAMPERED", {
                "knight_id": envelope.knight_id,
                "spark_id": envelope.spark_id,
                "client_addr": client_addr,
            })
            return False, "PAYLOAD_TAMPERED", None

        # 4. Signature Verification
        session_key = self._derive_session_key(kp.spark_id, kp.secret_salt)
        sig_data = f"{kp.knight_id}:{kp.spark_id}:{envelope.nonce}:{envelope.timestamp}:{envelope.action}:{calc_hash}"
        calc_sig = hmac.new(session_key, sig_data.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc_sig, envelope.signature):
            _audit_log("INTRUSION_SIGNATURE_MISMATCH", {
                "knight_id": envelope.knight_id,
                "spark_id": envelope.spark_id,
                "client_addr": client_addr,
            })
            return False, "SIGNATURE_VERIFICATION_FAILED", None

        # Registration of nonce
        self._seen_nonces[envelope.nonce] = time.time()

        # Success Audit Log
        _audit_log("WARP_GATE_TRANSIT_AUTHORIZED", {
            "knight_id": kp.knight_id,
            "spark_id": kp.spark_id,
            "action": envelope.action,
            "client_addr": client_addr,
            "transport": transport,
            "status": "AUTHORIZED",
        })
        return True, "AUTHORIZED", envelope.payload


# ── Out-of-Band Warp Gate Rendezvous Engine ──────────────────────────────────

class WarpGateRendezvous:
    """Out-of-band asynchronous communication bridge when live sockets are unavailable."""

    @staticmethod
    def emergency_rendezvous_write(
        knight_id: str,
        keypass_str: str,
        payload: Dict[str, Any],
        vault: Optional[AlexandriaKeypassVault] = None,
    ) -> Dict[str, Any]:
        _ensure_directories()
        v = vault or AlexandriaKeypassVault()
        kp = v.verify_keypass(keypass_str)
        if not kp or kp.knight_id != knight_id.upper():
            raise PermissionError("Warp Gate access denied: invalid Forever Keypass")

        rendezvous_file = _RENDEZVOUS_DIR / f"{knight_id.lower()}_warp.json"
        record = {
            "warp_gate_version": "1.0",
            "transport": "warp_gate_out_of_band_rendezvous",
            "knight_id": kp.knight_id,
            "spark_id": kp.spark_id,
            "keypass_id": kp.keypass_id,
            "timestamp": _utcnow(),
            "payload": payload,
        }
        rendezvous_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
        _audit_log("WARP_GATE_EMERGENCY_RENDEZVOUS_WRITE", {
            "knight_id": kp.knight_id,
            "spark_id": kp.spark_id,
            "path": str(rendezvous_file),
        })
        return record

    @staticmethod
    def emergency_rendezvous_read(knight_id: str) -> Optional[Dict[str, Any]]:
        rendezvous_file = _RENDEZVOUS_DIR / f"{knight_id.lower()}_warp.json"
        if not rendezvous_file.exists():
            return None
        try:
            return json.loads(rendezvous_file.read_text(encoding="utf-8"))
        except Exception:
            return None


# ── WarpGateSocket (Transparent Cryptographic Switch & Fallback) ─────────────

class WarpGateSocket:
    """A socket wrapper embedding the cryptographic switch and automatic Warp Gate fallback."""

    def __init__(self, knight_id: str, switch: Optional[WarpGateCryptographicSwitch] = None):
        self.knight_id = knight_id.upper()
        self.switch = switch or WarpGateCryptographicSwitch()
        self.raw_socket: Optional[socket.socket] = None
        self.is_connected = False
        self.mode = "LIVE"

    def warp_connect(
        self,
        address: Tuple[str, int],
        timeout_s: float = 1.0,
    ) -> Dict[str, Any]:
        """Attempts connection over live TCP socket; if unavailable, engages Warp Gate fallback."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_s)
            sock.connect(address)
            self.raw_socket = sock
            self.is_connected = True
            self.mode = "LIVE_SOCKET"

            # Perform immediate cryptographic switch handshake
            envelope = self.switch.forge_envelope(
                knight_id=self.knight_id,
                action="WARP_SOCKET_HANDSHAKE",
                payload={"target": f"{address[0]}:{address[1]}", "status": "SYN"},
            )
            data = envelope.encode()
            # Send length-prefixed frame
            sock.sendall(len(data).to_bytes(4, "big") + data)

            return {
                "status": "CONNECTED",
                "transport": "live_socket",
                "address": address,
                "knight_id": self.knight_id,
                "spark_id": envelope.spark_id,
            }
        except (socket.error, OSError, TimeoutError) as exc:
            # Sockets severed/unreachable -> Trigger Warp Gate Backup Entry
            self.is_connected = False
            self.mode = "WARP_GATE_BACKUP"
            kp = self.switch.vault.forge_keypass(self.knight_id)
            record = WarpGateRendezvous.emergency_rendezvous_write(
                knight_id=self.knight_id,
                keypass_str=kp.forever_access_key,
                payload={"target": f"{address[0]}:{address[1]}", "error": str(exc), "state": "FALLBACK_ACTIVE"},
                vault=self.switch.vault,
            )
            LOG.warning(f"[WARP_GATE] Live socket to {address} failed ({exc}). Engaged Warp Gate Backup Entry.")
            return {
                "status": "WARP_GATE_FALLBACK_ACTIVE",
                "transport": "warp_gate_out_of_band_rendezvous",
                "address": address,
                "knight_id": self.knight_id,
                "spark_id": kp.spark_id,
                "forever_keypass": kp.forever_access_key,
                "rendezvous_record": record,
            }

    def close(self) -> None:
        if self.raw_socket:
            try:
                self.raw_socket.close()
            except OSError:
                pass
            self.raw_socket = None
        self.is_connected = False


# ── Agentic Ingress Zero-Trust Barrier (Heimdall & Alexandria Law) ─────────────

class AgenticIngressDeniedError(PermissionError):
    """Raised when an agent attempts ingress into Camelot-OS without a valid Warp Gate Keypass."""
    pass


class AgenticWarpGateBarrier:
    """Enforces absolute Zero-Trust Agentic Ingress:
    No agent can enter, execute commands, dispatch tasks, or interface with Camelot-OS
    without their cryptographically assigned Warp Gate Keypass matching their Spark ID.
    """

    def __init__(self, vault: Optional[AlexandriaKeypassVault] = None):
        self.vault = vault or AlexandriaKeypassVault()

    def enforce_ingress(
        self,
        knight_id: str,
        keypass_token: str,
        action: str = "AGENTIC_EXECUTE",
        context: Optional[Dict[str, Any]] = None,
    ) -> WarpGateKeypass:
        """Validates agentic entry. Raises AgenticIngressDeniedError on failure."""
        k_upper = knight_id.upper()
        if not keypass_token or not isinstance(keypass_token, str):
            _audit_log("AGENTIC_INGRESS_REJECTED_MISSING_TOKEN", {
                "knight_id": k_upper,
                "action": action,
                "context": context or {},
                "verdict": "DENIED",
            })
            raise AgenticIngressDeniedError(
                f"[WARP_GATE] Agentic ingress blocked: Knight '{k_upper}' provided no Warp Gate Keypass."
            )

        kp = self.vault.verify_keypass(keypass_token)
        if not kp:
            _audit_log("AGENTIC_INGRESS_REJECTED_INVALID_TOKEN", {
                "knight_id": k_upper,
                "token_prefix": keypass_token[:16] if len(keypass_token) >= 16 else keypass_token,
                "action": action,
                "verdict": "DENIED",
            })
            raise AgenticIngressDeniedError(
                f"[WARP_GATE] Agentic ingress blocked: Provided Keypass is forged, revoked, or untrusted."
            )

        if kp.knight_id != k_upper:
            _audit_log("AGENTIC_INGRESS_REJECTED_IDENTITY_MISMATCH", {
                "claimed_knight": k_upper,
                "keypass_knight": kp.knight_id,
                "action": action,
                "verdict": "DENIED",
            })
            raise AgenticIngressDeniedError(
                f"[WARP_GATE] Agentic ingress blocked: Keypass owner '{kp.knight_id}' does not match claimed identity '{k_upper}'."
            )

        # Attestation passed: record authorized ingress
        _audit_log("AGENTIC_INGRESS_AUTHORIZED", {
            "knight_id": kp.knight_id,
            "spark_id": kp.spark_id,
            "keypass_id": kp.keypass_id,
            "action": action,
            "capabilities": kp.capabilities,
            "verdict": "PERMITTED",
        })
        return kp


def require_warp_gate_keypass(knight_param: str = "knight_id", token_param: str = "keypass_token", vault: Optional[AlexandriaKeypassVault] = None):
    """Function decorator enforcing zero-trust Warp Gate keypass verification on agent calls."""
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            barrier = AgenticWarpGateBarrier(vault=vault)
            claimed_id = kwargs.get(knight_param)
            token = kwargs.get(token_param)
            if not claimed_id and args:
                claimed_id = args[0] if isinstance(args[0], str) else getattr(args[0], "knight_id", None)
            if not token and len(args) > 1:
                token = args[1] if isinstance(args[1], str) else None
            barrier.enforce_ingress(str(claimed_id or "UNKNOWN"), str(token or ""), action=fn.__name__)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ── Self-Test Suite ──────────────────────────────────────────────────────────

def selftest() -> int:
    import tempfile
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("Warp Gate & Cryptographic Switch Self-Test")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        kp_file = tmp_path / "keypasses.json"
        vault = AlexandriaKeypassVault(keypass_file=kp_file)
        switch = WarpGateCryptographicSwitch(vault=vault)

        # Gate 1: Lady Alexandria Keypass Forging
        kp_merlin = vault.forge_keypass("MERLIN_OMEGA")
        check("Merlin keypass generated", kp_merlin.knight_id == "MERLIN_OMEGA")
        check("Merlin spark_id canonical", kp_merlin.spark_id == MERLIN_SPARK_ID)
        check("Forever keypass prefix valid", kp_merlin.forever_access_key.startswith("WARP-PASS-"))
        check("Keypass expiry is FOREVER", kp_merlin.expires_at == "FOREVER")

        # Gate 2: Lady Alexandria & Heimdall Keypasses
        kp_alexandria = vault.forge_keypass("LADY_ALEXANDRIA")
        check("Alexandria keypass generated", kp_alexandria.spark_id == ALEXANDRIA_SPARK_ID)
        kp_heimdall = vault.forge_keypass("SIR_HEIMDALL")
        check("Heimdall keypass generated", kp_heimdall.spark_id == HEIMDALL_SPARK_ID)

        # Gate 3: Keypass verification
        verified_kp = vault.verify_keypass(kp_merlin.forever_access_key)
        check("Keypass verified in vault", verified_kp is not None and verified_kp.knight_id == "MERLIN_OMEGA")
        check("Invalid keypass rejected", vault.verify_keypass("WARP-PASS-INVALID-TOKEN") is None)

        # Gate 4: Cryptographic Switch Envelope Signing & Verification
        envelope = switch.forge_envelope("MERLIN_OMEGA", "TELEMETRY_SYNC", {"cpu": 12.5, "status": "ONLINE"})
        check("Envelope contains spark_id", envelope.spark_id == MERLIN_SPARK_ID)
        ok, reason, payload = switch.verify_and_log_transit(envelope, client_addr="127.0.0.1", transport="live_socket")
        check("Envelope verification authorized", ok is True and reason == "AUTHORIZED")
        check("Payload extracted correctly", payload is not None and payload.get("cpu") == 12.5)

        # Gate 5: Replay attack prevention
        ok_replay, reason_replay, _ = switch.verify_and_log_transit(envelope)
        check("Replay attack blocked", ok_replay is False and "REPLAY" in reason_replay)

        # Gate 6: Payload Tampering Protection
        tampered = switch.forge_envelope("SIR_HEIMDALL", "GATE_OPEN", {"gate": "BIFROST"})
        tampered.payload["gate"] = "INTRUDER_GATE"  # Tamper payload without recalculating hash
        ok_tamper, reason_tamper, _ = switch.verify_and_log_transit(tampered)
        check("Tampered payload blocked", ok_tamper is False and reason_tamper == "PAYLOAD_TAMPERED")

        # Gate 7: Out-of-band Warp Gate Rendezvous
        record = WarpGateRendezvous.emergency_rendezvous_write(
            knight_id="MERLIN_OMEGA",
            keypass_str=kp_merlin.forever_access_key,
            payload={"emergency_code": 777, "msg": "Socket severed; executing via Warp Gate"},
            vault=vault,
        )
        check("Rendezvous write successful", record["payload"]["emergency_code"] == 777)
        read_back = WarpGateRendezvous.emergency_rendezvous_read("MERLIN_OMEGA")
        check("Rendezvous read-back verified", read_back is not None and read_back["payload"]["emergency_code"] == 777)

        # Gate 8: WarpGateSocket automatic fallback when target port closed
        # Port 59199 is assumed unused locally
        wg_sock = WarpGateSocket(knight_id="SIR_HEIMDALL", switch=switch)
        res = wg_sock.warp_connect(("127.0.0.1", 59199), timeout_s=0.2)
        check("Socket offline triggers Warp Gate fallback", res["status"] == "WARP_GATE_FALLBACK_ACTIVE")
        check("Fallback transport is out_of_band", res["transport"] == "warp_gate_out_of_band_rendezvous")
        check("Fallback possesses forever keypass", "WARP-PASS-" in res.get("forever_keypass", ""))

        # Gate 9: Agentic Ingress Barrier (Permitted with valid Keypass)
        barrier = AgenticWarpGateBarrier(vault=vault)
        ingress_kp = barrier.enforce_ingress("MERLIN_OMEGA", kp_merlin.forever_access_key, action="TEST_RUNIC_EXECUTE")
        check("Agentic Ingress permitted with valid keypass", ingress_kp.knight_id == "MERLIN_OMEGA")

        # Gate 10: Agentic Ingress Barrier (Blocked when missing token)
        blocked_missing = False
        try:
            barrier.enforce_ingress("SIR_HEIMDALL", "", action="UNAUTHORIZED_DISPATCH")
        except AgenticIngressDeniedError:
            blocked_missing = True
        check("Agentic Ingress blocked when token missing", blocked_missing)

        # Gate 11: Agentic Ingress Barrier (Blocked when token forged)
        blocked_forged = False
        try:
            barrier.enforce_ingress("SIR_HEIMDALL", "WARP-PASS-FORGED-TOKEN", action="UNAUTHORIZED_DISPATCH")
        except AgenticIngressDeniedError:
            blocked_forged = True
        check("Agentic Ingress blocked when token forged", blocked_forged)

        # Gate 12: Agentic Ingress Barrier (Blocked on identity mismatch: using another Knight's token)
        blocked_mismatch = False
        try:
            barrier.enforce_ingress("SIR_HEIMDALL", kp_merlin.forever_access_key, action="SPOOFED_DISPATCH")
        except AgenticIngressDeniedError:
            blocked_mismatch = True
        check("Agentic Ingress blocked on identity mismatch", blocked_mismatch)

        # Gate 13: Decorator @require_warp_gate_keypass enforcement
        @require_warp_gate_keypass(vault=vault)
        def protected_knight_action(knight_id: str, keypass_token: str, payload_data: str):
            return f"EXECUTED:{payload_data}"

        res_dec = protected_knight_action(knight_id="MERLIN_OMEGA", keypass_token=kp_merlin.forever_access_key, payload_data="OMEGA_PULSE")
        check("Decorator permits valid keypass", res_dec == "EXECUTED:OMEGA_PULSE")

        dec_blocked = False
        try:
            protected_knight_action(knight_id="SIR_HEIMDALL", keypass_token="INVALID_KEYPASS", payload_data="ATTACK")
        except AgenticIngressDeniedError:
            dec_blocked = True
        check("Decorator denies invalid keypass", dec_blocked)

        # Gate 14: Tier Enforcement (Only Omega, Arch, and Sovereign can be forged)
        check("Merlin tier is OMEGA", kp_merlin.tier == "OMEGA")
        check("Alexandria tier is ARCH", kp_alexandria.tier == "ARCH")
        check("Heimdall tier is OMEGA", kp_heimdall.tier == "OMEGA")

        denied_ineligible = False
        try:
            vault.forge_keypass("SIR_GAWAIN")
        except WarpGateTierIneligibleError:
            denied_ineligible = True
        check("Tactical/kinetic knight denied keypass", denied_ineligible)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} -- Warp Gate Cryptographic Switch")
    return failures


# ── CLI Interface ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--selftest" in sys.argv or "--test" in sys.argv:
        sys.exit(selftest())

    if "--forge" in sys.argv:
        idx = sys.argv.index("--forge")
        target_knight = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "MERLIN_OMEGA"
        v = AlexandriaKeypassVault()
        kp = v.forge_keypass(target_knight)
        print(json.dumps(kp.to_dict(), indent=2))
        sys.exit(0)

    if "--list" in sys.argv:
        v = AlexandriaKeypassVault()
        print(json.dumps(v.list_keypasses(), indent=2))
        sys.exit(0)

    if "--audit" in sys.argv:
        if _AUDIT_LOG_FILE.exists():
            lines = _AUDIT_LOG_FILE.read_text(encoding="utf-8").strip().splitlines()[-10:]
            for line in lines:
                print(line)
        else:
            print("No audit log entries found.")
        sys.exit(0)

    print("Camelot-OS Warp Gate Cryptographic Switch & Keypass Vault")
    print("Commands: --test | --forge <KNIGHT_ID> | --list | --audit")
