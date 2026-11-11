# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""Deployment executor for verified GitHub push events.

Runs (as a background job) the pipeline the receiver library documents:
fetch -> verify SHA -> hard reset -> build -> rsync into the web root.

Safety contract (do not relax):
- Only the branch named by CAMELOT_DEPLOY_BRANCH (default: main) deploys.
  Every other ref is IGNORED with a receipt — a feature-branch push must
  never clobber production.
- The pushed SHA is validated against ^[0-9a-f]{40}$ and must match the
  fetched origin view; a mismatch SKIPS the deploy instead of deploying a
  state the box cannot see.
- All commands are fixed strings — no shell interpolation of payload data.
- Whole pipeline is opt-in: CAMELOT_DEPLOY_ENABLED=1 in the receiver's unit
  environment. Without it the receiver only writes receipts (test/CI safe).
"""

from __future__ import annotations

import dataclasses
import logging
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Optional

LOG = logging.getLogger("camelot.vps_webhook_deploy")

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_URL = "https://github.com/Cyberdad247/Camelot-VPS.git"
_RUN_TIMEOUT_S = 900


@dataclass
class DeployResult:
    status: str  # DEPLOYED | IGNORED | SKIPPED | FAILED
    ref: str = ""
    commit_sha: str = ""
    steps: list = field(default_factory=list)
    error: str = ""

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _cfg(name: str, default: str) -> str:
    return os.getenv(name, default)


def _run(cmd: list, cwd: Optional[str], steps: list, label: str) -> subprocess.CompletedProcess:
    steps.append(label)
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=_RUN_TIMEOUT_S,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        raise RuntimeError(f"{label} failed (rc={proc.returncode}): {' | '.join(tail)}")
    return proc


def execute_deploy(payload: dict) -> DeployResult:
    """Blocking pipeline. Call from a worker thread; HTTP path must not wait."""
    ref = str(payload.get("ref", ""))
    sha = str(payload.get("after", ""))
    branch = _cfg("CAMELOT_DEPLOY_BRANCH", "main")
    repo_dir = _cfg("CAMELOT_DEPLOY_REPO_DIR", "/opt/camelot-vps")
    output_dir = _cfg("CAMELOT_DEPLOY_OUTPUT_DIR", os.path.join(repo_dir, "dist"))
    target_dir = _cfg("CAMELOT_DEPLOY_TARGET_DIR", "/var/www/worldtree")

    result = DeployResult(status="", ref=ref, commit_sha=sha)

    if ref != f"refs/heads/{branch}":
        result.status = "IGNORED"
        result.error = f"branch {ref} is not the deploy branch (refs/heads/{branch})"
        return result
    if not _SHA_RE.match(sha):
        result.status = "SKIPPED"
        result.error = "payload 'after' is not a full 40-hex SHA"
        return result

    git = ["git", "-C", repo_dir]
    try:
        if not os.path.isdir(os.path.join(repo_dir, ".git")):
            parent = os.path.dirname(repo_dir)
            _run(["git", "clone", _REPO_URL, repo_dir], parent, result.steps, "clone")

        _run(git + ["fetch", "origin", branch], repo_dir, result.steps, f"fetch origin/{branch}")
        view = subprocess.run(
            git + ["rev-parse", f"origin/{branch}"],
            cwd=repo_dir, capture_output=True, text=True, timeout=60, encoding="utf-8",
        ).stdout.strip()
        if view != sha:  # eventual-consistency guard: never deploy an unseen SHA
            result.status = "SKIPPED"
            result.error = f"origin view ({view[:7] or 'none'}) does not match pushed SHA"
            return result

        dirty = subprocess.run(
            git + ["status", "--porcelain"], cwd=repo_dir,
            capture_output=True, text=True, timeout=60, encoding="utf-8",
        ).stdout
        if dirty.strip():
            LOG.warning("deploy checkout carries %d dirty path(s); hard reset proceeds", len(dirty.splitlines()))
        _run(git + ["reset", "--hard", sha], repo_dir, result.steps, f"reset --hard {sha[:7]}")

        if not os.path.isdir(os.path.join(repo_dir, "node_modules")):
            _run(
                ["bash", "-lc", "npm install --no-audit --no-fund"],
                repo_dir, result.steps, "npm install",
            )
        _run(["bash", "-lc", "npm run build"], repo_dir, result.steps, "npm run build")

        if not os.path.isdir(output_dir):
            raise RuntimeError(f"build output dir {output_dir} missing after build")
        _run(
            ["rsync", "-a", "--delete", f"{output_dir}/", f"{target_dir}/"],
            repo_dir, result.steps, f"rsync -> {target_dir}",
        )
    except Exception as exc:  # noqa: BLE001 - failures are receipt content, not crashes
        result.status = "FAILED"
        result.error = str(exc)
        LOG.error("deploy FAILED for %s: %s", sha[:7], exc)
        return result

    result.status = "DEPLOYED"
    LOG.info("deploy DEPLOYED %s (%d steps)", sha[:7], len(result.steps))
    return result


def spawn_deploy(payload: dict, on_done) -> threading.Thread:
    """Run execute_deploy in a daemon thread; on_done(result) fires on completion."""

    def _worker() -> None:
        on_done(execute_deploy(payload))

    thread = threading.Thread(target=_worker, name="webhook-deploy", daemon=True)
    thread.start()
    return thread
