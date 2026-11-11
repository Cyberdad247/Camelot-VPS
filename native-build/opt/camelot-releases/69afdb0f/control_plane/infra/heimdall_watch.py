# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Heimdall Watch — Sir Heimdall posted at the Bifrost
===================================================
Integrates SIR_HEIMDALL (01_KERNEL/iron_gate/DEFENSE_GRID/knights/heimdall.py) —
the Eternal Watcher / perimeter guardian — into the control plane so he can guard
the bifrost→drone dispatch path:

  * `heimdall_scan_tool` — a governed tool the drone exposes; a perimeter scan can
    be dispatched to Heimdall over the Bifrost bridge (`heimdall.scan`).
  * `start_heimdall_watch` — a background daemon that runs Heimdall's continuous
    watch on the drone host, emitting threat reports to Hermes `shadow.threats`.

Heimdall lives in 01_KERNEL (not a packaged module), so we path-insert his home
the same way the drone bridges into 02_FORGE.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_KNIGHTS = _REPO / "01_KERNEL" / "iron_gate" / "DEFENSE_GRID" / "knights"
if str(_KNIGHTS) not in sys.path:
    sys.path.insert(0, str(_KNIGHTS))

try:
    from heimdall import SirHeimdall, WatchReport  # type: ignore
    _HEIMDALL_OK = True
except Exception as _e:  # noqa: BLE001 - integration must degrade, not crash the drone
    _HEIMDALL_OK = False
    _IMPORT_ERR = str(_e)


def available() -> bool:
    return _HEIMDALL_OK


def get_heimdall() -> "SirHeimdall":
    if not _HEIMDALL_OK:
        raise RuntimeError(f"Sir Heimdall unavailable: {_IMPORT_ERR}")
    # Scope his gaze to the repo, not the whole home directory (his default parents[5]).
    return SirHeimdall(repo_root=_REPO)


def _report_to_dict(report: "WatchReport") -> Dict[str, Any]:
    return {
        "watcher": "SIR_HEIMDALL",
        "clean": report.is_clean,
        "vector_count": len(report.vectors),
        "critical": report.critical_count,
        "scan_path": report.scan_path,
        "timestamp": report.timestamp,
        "vectors": [
            {"type": v.vector_type, "source": v.source, "severity": v.severity,
             "detail": v.detail, "action": v.recommended_action}
            for v in report.vectors
        ],
    }


# Scoped scan targets — Heimdall's default is the whole repo, which greps node_modules
# and never returns. For a governed tool we bound his gaze to the live code paths.
_SCAN_PATHS = [_REPO / "control_plane", _REPO / "02_FORGE" / "cartridge"]


def _bounded_scan(h: "SirHeimdall", deep_network: bool) -> "WatchReport":
    """Run Heimdall's sub-scanners over scoped paths so the tool stays fast."""
    from datetime import datetime, timezone
    vectors = []
    vectors.extend(h._scan_packages())          # pip telemetry packages (fast)
    vectors.extend(h._scan_env_leakage())       # identity env vars (instant)
    for p in _SCAN_PATHS:                        # telemetry imports, scoped
        if p.exists():
            vectors.extend(h._scan_telemetry_imports(p))
    if deep_network:                             # DNS probe to telemetry endpoints (~8s)
        vectors.extend(h._scan_network_endpoints())
    return WatchReport(vectors=vectors, scan_path=",".join(str(p) for p in _SCAN_PATHS),
                       timestamp=datetime.now(timezone.utc).isoformat())


def heimdall_scan_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Governed tool body: run a bounded Heimdall perimeter scan. Register as `heimdall.scan`.
    params: {"deep_network": bool}  — also DNS-probe known telemetry endpoints (~8s).
    """
    if not _HEIMDALL_OK:
        return {"available": False, "reason": f"Sir Heimdall not loadable: {_IMPORT_ERR}"}
    h = get_heimdall()
    report = _bounded_scan(h, deep_network=bool(params.get("deep_network", False)))
    out = _report_to_dict(report)
    # Heimdall's law: "What is reported cannot be denied." — mirror to Hermes.
    try:
        h.emit_hermes_alert(report)
        out["hermes_alerted"] = not report.is_clean
    except Exception:  # noqa: BLE001
        out["hermes_alerted"] = False
    return out


def start_heimdall_watch(interval_seconds: int = 360,
                         on_report: Optional[Callable[[Dict[str, Any]], None]] = None
                         ) -> Optional[threading.Thread]:
    """
    Post Heimdall on continuous watch in a daemon thread. Returns the thread, or
    None if Heimdall is unavailable. Never blocks / never crashes the host.
    """
    if not _HEIMDALL_OK:
        return None
    h = get_heimdall()

    def _cb(report: "WatchReport") -> None:
        if on_report:
            try:
                on_report(_report_to_dict(report))
            except Exception:  # noqa: BLE001
                pass

    def _run() -> None:
        try:
            h.watch(callback=_cb, interval_seconds=interval_seconds)
        except Exception:  # noqa: BLE001 - watch must never take down the drone
            pass

    t = threading.Thread(target=_run, name="heimdall-watch", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    import json
    print("Sir Heimdall available:", available())
    if available():
        print(json.dumps(heimdall_scan_tool({}), indent=2)[:1500])
