# SPDX-License-Identifier: MIT

"""Production evidence wrapper for the Bio-Swarm Rust spawner."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

RUNTIME_SCHEMA = "camelot.bio-swarm-runtime/v1"
RELEASE_SCHEMA = "camelot.bio-swarm-release/v1"


@dataclass(frozen=True)
class BioSwarmPaths:
    root: Path
    queue_path: Path
    state_path: Path
    release_path: Path
    binary_candidates: tuple[Path, ...]

    @classmethod
    def for_root(cls, root: Path | str | None = None) -> "BioSwarmPaths":
        repo_root = Path(root or Path(__file__).resolve().parent.parent).resolve()
        runtime_dir = repo_root / "03_VAULT" / "runtime_state"
        return cls(
            root=repo_root,
            queue_path=repo_root / "logs" / "harness_queue.jsonl",
            state_path=runtime_dir / "bio_swarm_runtime_latest.json",
            release_path=runtime_dir / "bio_swarm_release_latest.json",
            binary_candidates=(
                repo_root / "bin" / "swarm-spawner.exe",
                repo_root / "kinetic_edge" / "swarm_spawner" / "target" / "release" / "swarm-spawner.exe",
                repo_root / "target" / "release" / "swarm-spawner.exe",
            ),
        )

    def with_overrides(
        self,
        *,
        queue_path: Path | str | None = None,
        state_path: Path | str | None = None,
    ) -> "BioSwarmPaths":
        return BioSwarmPaths(
            root=self.root,
            queue_path=Path(queue_path).resolve() if queue_path else self.queue_path,
            state_path=Path(state_path).resolve() if state_path else self.state_path,
            release_path=self.release_path,
            binary_candidates=self.binary_candidates,
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path | None) -> str | None:
    if not path or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _coerce_paths(paths: BioSwarmPaths | Path | str | None = None) -> BioSwarmPaths:
    if isinstance(paths, BioSwarmPaths):
        return paths
    return BioSwarmPaths.for_root(paths)


def _find_binary(paths: BioSwarmPaths) -> Path | None:
    for candidate in paths.binary_candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def read_bio_swarm_status(paths: BioSwarmPaths | Path | str | None = None) -> dict[str, Any]:
    resolved = _coerce_paths(paths)
    binary = _find_binary(resolved)
    runtime = _read_json(resolved.state_path)
    release = _read_json(resolved.release_path)
    binary_exists = binary is not None
    status = "BINARY_MISSING"
    if binary_exists and runtime:
        status = "READY"
    elif binary_exists:
        status = "READY_NO_STATE"
    return {
        "schema": RUNTIME_SCHEMA,
        "generated_utc": _now(),
        "status": status,
        "binary_exists": binary_exists,
        "binary_path": str(binary) if binary else None,
        "binary_sha256": _sha256(binary),
        "state_exists": resolved.state_path.exists(),
        "state_path": str(resolved.state_path),
        "queue_path": str(resolved.queue_path),
        "release_path": str(resolved.release_path),
        "runtime": runtime,
        "release": release,
    }


def preflight_bio_swarm(paths: BioSwarmPaths | Path | str | None = None) -> dict[str, Any]:
    resolved = _coerce_paths(paths)
    binary = _find_binary(resolved)
    issues: list[str] = []
    if binary is None:
        issues.append("swarm-spawner.exe is missing; build kinetic_edge/swarm_spawner first")
    try:
        resolved.state_path.parent.mkdir(parents=True, exist_ok=True)
        resolved.queue_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        issues.append(f"runtime directory is not writable: {exc}")
    return {
        "schema": RUNTIME_SCHEMA,
        "generated_utc": _now(),
        "status": "PREFLIGHT_PASS" if not issues else "PREFLIGHT_BLOCKED",
        "issues": issues,
        "binary_path": str(binary) if binary else None,
        "binary_sha256": _sha256(binary),
        "state_path": str(resolved.state_path),
        "queue_path": str(resolved.queue_path),
    }


def write_bio_swarm_runtime_status(paths: BioSwarmPaths | Path | str | None = None) -> dict[str, Any]:
    resolved = _coerce_paths(paths)
    status = read_bio_swarm_status(resolved)
    if status["status"] == "READY_NO_STATE":
        status["status"] = "READY"
    resolved.state_path.parent.mkdir(parents=True, exist_ok=True)
    resolved.state_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def _write_fixture_queue(queue_path: Path) -> None:
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "BIO_SWARM_SELF_TEST",
        "knight": "sir_codex",
        "type": "FORGE",
        "directive": "write deterministic bio-swarm fixture",
        "priority": 1,
        "submitted": _now(),
    }
    queue_path.write_text(json.dumps(task) + "\n", encoding="utf-8")


def _release_payload(
    *,
    paths: BioSwarmPaths,
    binary: Path,
    command: Sequence[str],
    returncode: int,
    stdout: str,
    stderr: str,
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    runtime_status = runtime.get("status") if runtime else None
    verdict = "PASS" if returncode == 0 and runtime_status == "PASS" else "FAIL"
    return {
        "schema": RELEASE_SCHEMA,
        "generated_utc": _now(),
        "status": verdict,
        "verdict": verdict,
        "binary_path": str(binary),
        "binary_sha256": _sha256(binary),
        "queue_path": str(paths.queue_path),
        "state_path": str(paths.state_path),
        "command": list(command),
        "returncode": returncode,
        "stdout": stdout[-12000:],
        "stderr": stderr[-4000:],
        "runtime": runtime,
    }


def run_bio_swarm_once(
    paths: BioSwarmPaths | Path | str | None = None,
    *,
    queue_path: Path | str | None = None,
    state_path: Path | str | None = None,
    fixture: bool = False,
    timeout: int = 30,
) -> dict[str, Any]:
    resolved = _coerce_paths(paths).with_overrides(queue_path=queue_path, state_path=state_path)
    preflight = preflight_bio_swarm(resolved)
    if preflight["status"] != "PREFLIGHT_PASS":
        return preflight
    if fixture:
        _write_fixture_queue(resolved.queue_path)
    binary = Path(preflight["binary_path"])
    command = [
        str(binary),
        "--once",
        "--queue",
        str(resolved.queue_path),
        "--state",
        str(resolved.state_path),
        "--json",
    ]
    env = os.environ.copy()
    env["CAMELOT_OS_HOME"] = str(resolved.root)
    completed = subprocess.run(
        command,
        cwd=str(resolved.root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    try:
        runtime = json.loads(stdout) if stdout else _read_json(resolved.state_path)
    except json.JSONDecodeError:
        runtime = _read_json(resolved.state_path)
    if not isinstance(runtime, dict):
        runtime = None
    release = _release_payload(
        paths=resolved,
        binary=binary,
        command=command,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        runtime=runtime,
    )
    resolved.release_path.parent.mkdir(parents=True, exist_ok=True)
    resolved.release_path.write_text(json.dumps(release, indent=2), encoding="utf-8")
    return release
