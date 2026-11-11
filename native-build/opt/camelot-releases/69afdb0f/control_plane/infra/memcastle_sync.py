#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""//sync — bidirectional bridge between MemCastle (edge vault) and NotebookLM
(cloud oracle). Closes the Tier-2 <-> Tier-3 loop of the cognitive stack.

  push:  MemCastle items  -> a canonical NotebookLM note (sync_state)
  pull:  NotebookLM synthesis -> stored back into MemCastle (the "data crystal")

Edge-brain-first: if the cloud is unreachable or auth has expired, sync SKIPS
cleanly (status="skipped") and never raises — MemCastle keeps working offline.

The NotebookLM bridge is injectable (`bridge=`) so the orchestration is tested
deterministically without network; at runtime it defaults to the real
03_VAULT/training/configs/notebooklm_bridge.py.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memcastle import MemCastle  # noqa: E402

SYNC_NOTE_TITLE = "Camelot-OS MemCastle Vault Snapshot"


def _load_bridge() -> Optional[Any]:
    """Import the real NotebookLM bridge; return None if unavailable (deps/auth)."""
    repo = Path(os.environ.get("CAMELOT_OS_HOME", Path(__file__).resolve().parent.parent))
    path = repo / "03_VAULT" / "training" / "configs" / "notebooklm_bridge.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("notebooklm_bridge", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None  # missing httpx/client deps -> treat cloud as unavailable


_DEFAULT_BRIDGE = _load_bridge()


def _cloud_ok(bridge: Any) -> tuple[bool, str]:
    if bridge is None:
        return False, "notebooklm bridge unavailable (deps/import)"
    try:
        ok, msg, _latency = bridge.health_probe()
        return bool(ok), str(msg)
    except Exception as e:  # auth expired, network down, etc.
        return False, f"health_probe error: {type(e).__name__}: {e}"


def build_snapshot(mc: MemCastle, limit: int = 200) -> str:
    items = mc.recent(limit)
    lines = [
        "# MemCastle Vault Snapshot",
        f"_items: {mc.count()} (showing {len(items)})_",
        "",
    ]
    for it in items:
        lines.append(f"- {it['text']}  ({it['source'] or '-'})")
    return "\n".join(lines)


def push(mc: MemCastle, bridge: Any = _DEFAULT_BRIDGE, note_title: str = SYNC_NOTE_TITLE,
         limit: int = 200) -> dict:
    """MemCastle -> NotebookLM note. Skips cleanly if the cloud is down."""
    ok, reason = _cloud_ok(bridge)
    if not ok:
        return {"direction": "push", "status": "skipped", "reason": reason}
    snapshot = build_snapshot(mc, limit)
    try:
        res = bridge.sync_state(content=snapshot, note_title=note_title)
    except Exception as e:
        return {"direction": "push", "status": "error", "reason": f"{type(e).__name__}: {e}"}
    if isinstance(res, dict) and res.get("error"):
        return {"direction": "push", "status": "error", "reason": res["error"]}
    return {"direction": "push", "status": "ok", "remote": res, "items_pushed": len(mc.recent(limit))}


def pull(mc: MemCastle, query: str, bridge: Any = _DEFAULT_BRIDGE, source: str = "notebooklm") -> dict:
    """NotebookLM synthesis -> stored into MemCastle. Skips cleanly if cloud down."""
    ok, reason = _cloud_ok(bridge)
    if not ok:
        return {"direction": "pull", "status": "skipped", "reason": reason}
    try:
        text = bridge.synthesize(query)
    except Exception as e:
        return {"direction": "pull", "status": "error", "reason": f"{type(e).__name__}: {e}"}
    # The bridge returns an error *string* on synthesis failure — don't store it.
    if not text or (isinstance(text, str) and text.startswith("[Living Notebook synthesis failed")):
        return {"direction": "pull", "status": "error", "reason": text or "empty synthesis"}
    rid = mc.store(text, source=source, knight="sir_helio")
    return {"direction": "pull", "status": "ok", "stored_id": rid, "chars": len(text)}


def sync(mc: MemCastle, query: str, bridge: Any = _DEFAULT_BRIDGE) -> dict:
    """Bidirectional //sync: push the vault up, pull a synthesis down."""
    return {"push": push(mc, bridge), "pull": pull(mc, query, bridge)}


def _cli() -> None:
    p = argparse.ArgumentParser(description="//sync — MemCastle <-> NotebookLM")
    p.add_argument("cmd", choices=["push", "pull", "sync", "status"])
    p.add_argument("--query", default="Summarize the current Camelot-OS state.")
    args = p.parse_args()

    mc = MemCastle()
    if args.cmd == "status":
        ok, reason = _cloud_ok(_DEFAULT_BRIDGE)
        print(f"cloud reachable: {ok}  ({reason})")
        print(f"vault items: {mc.count()}")
    elif args.cmd == "push":
        print(push(mc))
    elif args.cmd == "pull":
        print(pull(mc, args.query))
    elif args.cmd == "sync":
        print(sync(mc, args.query))
    mc.close()


if __name__ == "__main__":
    _cli()
