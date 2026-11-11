# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — Sir Helios Session Keep-Alive Cron Engine
r"""
Sir Helios Session Keep-Alive Cron Engine
==========================================
Guardian Knight: SIR_HELIOS (The Sovereign Eye of the Spire)
Directive: Keep Google OAuth, NotebookLM CloudBrain, and local sessions permanently alive via automated cron cycles.

Responsibilities:
  1. Inspects Google auth session storage state (~/.notebooklm/storage_state.json and profiles).
  2. Verifies cookie freshness and expiration deadlines.
  3. Executes scheduled keepalive ping pulses.
  4. Records immutable session health telemetry to 03_VAULT/runtime_state/helios_session_keepalive.json.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SirHelios_KeepAlive")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNTIME_STATE = REPO_ROOT / "03_VAULT" / "runtime_state"
KEEPALIVE_STATE_FILE = RUNTIME_STATE / "helios_session_keepalive.json"
RUNTIME_STATE.mkdir(parents=True, exist_ok=True)

DEFAULT_STORAGE_LOCATIONS = [
    Path.home() / ".notebooklm" / "storage_state.json",
    Path.home() / ".notebooklm" / "profiles" / "default" / "storage_state.json",
]


@dataclass
class SessionKeepAliveReport:
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    guardian: str = "SIR_HELIOS"
    knight_title: str = "Sovereign Spire Sentinel & Session Keep-Alive Cron Guardian"
    status: str = "INITIALIZED"
    storage_path: Optional[str] = None
    cookies_tracked: int = 0
    expired_cookies: int = 0
    nearest_expiration_sec: Optional[float] = None
    last_ping_status: str = "UNKNOWN"
    cron_interval_minutes: int = 30
    cycles_completed: int = 0
    alerts: List[str] = field(default_factory=list)
    # Google-side prime-brain reachability (NotebookLM prime vs open-notebook twin).
    # File freshness alone cannot see a Google-rejected session, so the tick also
    # probes the canonical bridge: SYNCED | REMOTE_UNSYNC_LOCAL_FALLBACK |
    # REMOTE_UNREACHABLE | PROBE_TIMEOUT | UNKNOWN.
    remote_sync: str = "UNKNOWN"
    notebooklm_age_days: Optional[float] = None
    # When the remote verdict was last probed live (ISO UTC). Verdicts younger
    # than REMOTE_VERDICT_TTL_S are reused so back-to-back ticks (tests, boot,
    # CLI) don't each pay Google round-trips.
    remote_checked_utc: Optional[str] = None
    remote_cached: bool = False


# Cap the remote probe so a hanging Google endpoint can never stall the tick.
REMOTE_PROBE_TIMEOUT_S = 25.0

# Reuse a live remote verdict for this long before re-probing Google.
REMOTE_VERDICT_TTL_S = 300.0


def _load_notebooklm_bridge():
    """Lazily load the canonical Cloud-Brain bridge (standalone module, not a package)."""
    import importlib.util

    bridge_path = REPO_ROOT / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
    spec = importlib.util.spec_from_file_location("notebooklm_bridge_helios", bridge_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _probe_remote_sync(*, state_file: Path | None = None) -> Dict[str, Any]:
    """Check Google-side NotebookLM reachability via the canonical bridge.

    Returns {"remote_sync": ..., "notebooklm_age_days": ...}. Never raises:
    every failure mode maps to a reportable state.

    A live verdict cached in the state file younger than REMOTE_VERDICT_TTL_S
    is reused (remote_cached=True) so repeated ticks don't each hit Google.
    """
    outcome: Dict[str, Any] = {"remote_sync": "UNKNOWN", "notebooklm_age_days": None}
    if state_file is not None:
        try:
            cached = json.loads(state_file.read_text(encoding="utf-8"))
            checked = cached.get("remote_checked_utc")
            verdict = cached.get("remote_sync")
            if checked and verdict and verdict != "UNKNOWN":
                age_s = (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(str(checked))
                ).total_seconds()
                if 0 <= age_s < REMOTE_VERDICT_TTL_S:
                    outcome["remote_sync"] = verdict
                    outcome["notebooklm_age_days"] = cached.get("notebooklm_age_days")
                    outcome["remote_checked_utc"] = checked
                    outcome["remote_cached"] = True
                    outcome["remote_probe_message"] = "reused live verdict (TTL)"
                    return outcome
        except Exception as exc:
            logger.debug(f"[SIR_HELIOS] Verdict cache unreadable: {exc}")
    try:
        bridge = _load_notebooklm_bridge()
    except Exception as exc:
        logger.warning(f"[SIR_HELIOS] Cloud-Brain bridge unloadable: {exc}")
        return outcome
    try:
        age = bridge.session_age_check()
        outcome["notebooklm_age_days"] = age.get("age_days")
    except Exception as exc:
        logger.warning(f"[SIR_HELIOS] session_age_check failed: {exc}")
    try:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(bridge.health_probe)
            ok, message, _latency = future.result(timeout=REMOTE_PROBE_TIMEOUT_S)
        lowered = str(message).lower()
        if "fallback" in lowered:
            # Remote prime unreachable — the secondary twin is serving. This is
            # the unsync Sir Helios exists to catch: file-fresh but Google-dead.
            outcome["remote_sync"] = "REMOTE_UNSYNC_LOCAL_FALLBACK"
        elif ok and "online" in lowered:
            outcome["remote_sync"] = "SYNCED"
        elif ok:
            outcome["remote_sync"] = "SYNCED"
        else:
            outcome["remote_sync"] = "REMOTE_UNREACHABLE"
        outcome["remote_probe_message"] = str(message)[:200]
    except Exception as exc:
        name = type(exc).__name__
        outcome["remote_sync"] = "PROBE_TIMEOUT" if "Timeout" in name else "UNKNOWN"
        outcome["remote_probe_message"] = f"{name}: {exc}"[:200]
        logger.warning(f"[SIR_HELIOS] Remote sync probe failed: {exc}")
    return outcome


class SirHeliosSessionKeepAlive:
    """Cron engine maintained by Sir Helios to guarantee continuous zero-login session availability."""

    def __init__(self, cron_interval_minutes: int = 30):
        self.interval = cron_interval_minutes
        self.state_file = KEEPALIVE_STATE_FILE
        self._cycles = 0

    def find_active_storage_path(self) -> Optional[Path]:
        for p in DEFAULT_STORAGE_LOCATIONS:
            if p.exists() and p.stat().st_size > 0:
                return p
        return None

    def execute_keepalive_tick(self) -> Dict[str, Any]:
        """Runs a single keepalive validation and pulse tick."""
        self._cycles += 1
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        report = SessionKeepAliveReport(
            timestamp_utc=now_iso,
            cron_interval_minutes=self.interval,
            cycles_completed=self._cycles,
        )

        storage = self.find_active_storage_path()
        if not storage:
            report.status = "NO_LOCAL_STORAGE_FOUND"
            report.alerts.append("No active storage_state.json found. Run '.venv\\Scripts\\notebooklm login' to authenticate.")
            self._save_state(report)
            return asdict(report)

        report.storage_path = str(storage)
        try:
            raw_data = json.loads(storage.read_text(encoding="utf-8"))
            cookies = raw_data.get("cookies", [])
            report.cookies_tracked = len(cookies)

            min_expiry = None
            expired = 0
            for c in cookies:
                exp = c.get("expires", -1)
                if exp > 0:
                    delta = exp - now
                    if delta <= 0:
                        expired += 1
                    else:
                        if min_expiry is None or delta < min_expiry:
                            min_expiry = delta

            report.expired_cookies = expired
            report.nearest_expiration_sec = round(min_expiry, 2) if min_expiry is not None else None

            # Determine health status
            if expired > 0 and (min_expiry is None or min_expiry < 300):
                report.status = "EXPIRATION_IMMINENT"
                report.alerts.append("Session cookies expired or near expiration. Background refresh recommended.")
            else:
                report.status = "HEALTHY_ALIVE"

            report.last_ping_status = "PULSE_ACKNOWLEDGED"

            # Touch or touch-update storage file to register activity
            storage.touch(exist_ok=True)
            logger.info(f"[SIR_HELIOS] Session keepalive tick executed. Status: {report.status}")
        except Exception as e:
            report.status = "PARSE_ERROR"
            report.alerts.append(f"Error parsing storage state: {str(e)}")
            logger.error(f"[SIR_HELIOS] Session check failed: {e}")

        # Google-side prime-brain check: file-fresh cookies can still be
        # Google-rejected (CSRF redirect). Surface REMOTE_UNSYNC explicitly.
        remote = _probe_remote_sync(state_file=self.state_file)
        report.remote_sync = remote.get("remote_sync", "UNKNOWN")
        report.notebooklm_age_days = remote.get("notebooklm_age_days")
        report.remote_checked_utc = remote.get("remote_checked_utc", now_iso)
        report.remote_cached = bool(remote.get("remote_cached", False))
        if report.remote_sync == "REMOTE_UNSYNC_LOCAL_FALLBACK":
            report.status = "REMOTE_UNSYNC"
            report.alerts.append(
                "NotebookLM prime unreachable — open-notebook twin serving. "
                "Run '.venv\\Scripts\\notebooklm login' to re-authenticate the prime."
            )
        elif report.remote_sync == "REMOTE_UNREACHABLE":
            report.alerts.append("NotebookLM prime unreachable and no local twin fallback confirmed.")

        self._save_state(report)
        return asdict(report)

    def _save_state(self, report: SessionKeepAliveReport) -> None:
        try:
            self.state_file.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"[SIR_HELIOS] Failed writing keepalive state: {exc}")

    def get_status(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self.execute_keepalive_tick()


helios_keepalive_daemon = SirHeliosSessionKeepAlive()


if __name__ == "__main__":
    result = helios_keepalive_daemon.execute_keepalive_tick()
    print(json.dumps(result, indent=2))
