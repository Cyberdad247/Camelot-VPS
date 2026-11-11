# SPDX-License-Identifier: MIT

"""NotebookLM login handler — headed Google sign-in via Playwright Chromium."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

from control_plane.cli.renderer import _stream_print


def _cmd_camelot_notebooklm_login(args: Any) -> int:
    """Headed interactive Google sign-in to NotebookLM via Playwright Chromium.

    Persists page.context.storage_state() to args.state_path so cloudbrain_sync
    can pick it up. Falls back to a HITL manual recipe when Playwright is
    missing, no Google auth cookies are captured, or the atomic write hits a
    read-only filesystem.

    The wait is cookie-based rather than URL-based: the old ``**/notebook**``
    URL glob matched Google's sign-in redirect URL (its ``continue`` parameter
    contains "/notebook.google.com/"), so the helper returned before sign-in
    completed and saved only anonymous sign-in-page cookies.
    """

    target = Path(args.state_path)
    json_mode = bool(getattr(args, "json", False))

    def _has_auth_cookie(cookies: list[dict]) -> bool:
        # Authenticated Google session cookies: SID, HSID, SSID, OSID, LSID,
        # APISID, SAPISID, __Secure-1PAPISID, __Secure-3PSID, ... Anonymous
        # sessions only carry NID/AEC, which never contain "SID".
        return any(
            "SID" in (c.get("name") or "") and "google.com" in (c.get("domain") or "")
            for c in cookies
        )

    if importlib.util.find_spec("playwright") is None:
        payload = {
            "status": "FALLBACK",
            "reason": "playwright_missing",
            "instruction": "pip install playwright && playwright install chromium",
            "manual_recipe": [
                "1. pip install playwright && playwright install chromium",
                "2. python -m control_plane.camelot_cli cloudbrain notebooklm login",
                "3. In the Chromium window that opens, sign in interactively",
            ],
        }
        if json_mode:
            print(json.dumps(payload, indent=2))
        else:
            _stream_print(
                "[notebooklm.login] Playwright unavailable. Manual recipe:",
                tone="warn",
            )
            for line in payload["manual_recipe"]:
                _stream_print(f"  {line}")
        return 0

    from playwright.sync_api import sync_playwright

    timeout_ms = max(1, int(getattr(args, "timeout", 300))) * 1000
    headless = bool(getattr(args, "headless", False))

    if not json_mode:
        _stream_print(
            f"[notebooklm.login] launching Chromium (headless={headless}). Sign in interactively within {timeout_ms // 1000}s.",
            tone="warn",
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto("https://notebooklm.google.com")
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            if _has_auth_cookie(ctx.cookies()):
                break
            if page.url.startswith("https://notebooklm.google.com/notebook/"):
                break
            if time.monotonic() >= deadline:
                break
            page.wait_for_timeout(2000)
        state = ctx.storage_state()
        browser.close()

    cookies = state.get("cookies", [])
    has_google = _has_auth_cookie(cookies)
    # Defensive: some cookie records may have a missing/None domain; coerce
    # to "" so sorted({...}) doesn't TypeError on a malformed record.
    domains = sorted({c.get("domain") or "" for c in cookies})

    if not has_google:
        payload = {
            "status": "FALLBACK",
            "reason": "no_google_auth_cookie",
            "cookies_captured": len(cookies),
            "domains": domains,
        }
        if json_mode:
            print(json.dumps(payload, indent=2))
        else:
            _stream_print(
                "[notebooklm.login] no authenticated Google session cookie captured; sign-in likely did not complete.",
                tone="err",
            )
        return 0

    if getattr(args, "dry_run", False):
        payload = {
            "status": "DRY_RUN_OK",
            "cookies_captured": len(cookies),
            "domains": domains,
            "target": str(target),
            "would_overwrite": target.exists(),
        }
        if json_mode:
            print(json.dumps(payload, indent=2))
        else:
            _stream_print(
                f"[notebooklm.login] DRY-RUN OK; {len(cookies)} cookies across {len(domains)} domains would write to {target}",
                tone="accent",
            )
        return 0

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / (target.name + ".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(target)
    except OSError as e:
        payload = {
            "status": "FALLBACK",
            "reason": "atomic_write_failed",
            "error": str(e),
            "target": str(target),
        }
        if json_mode:
            print(json.dumps(payload, indent=2))
        else:
            _stream_print(
                f"[notebooklm.login] atomic write failed: {e}; storage_state.json NOT modified.",
                tone="err",
            )
        return 0

    payload = {
        "status": "SUCCESS",
        "cookies_saved": len(cookies),
        "domains": domains,
        "path": str(target),
    }
    if json_mode:
        print(json.dumps(payload, indent=2))
    else:
        _stream_print(
            f"[notebooklm.login] saved {len(cookies)} cookies across {len(domains)} domains to {target}",
            tone="accent",
        )
    return 0
