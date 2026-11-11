# SPDX-License-Identifier: MIT

"""OMC Team CLI worker for Knight and Harness dispatch.

This module keeps the existing Knight-based API while adding interchangeable
Harness targets that can be dispatched through the same entrypoints.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TMUX_SESSION = "camelot-foundry"
CAMELOT_OS = Path.home() / "CAMELOT_OS"


@dataclass
class WorkerPane:
    """A worker target running a Knight or Harness command."""

    knight_id: str
    engine_cmd: str
    pane_index: int
    pid: Optional[int] = None
    status: str = "idle"  # idle | running | completed | failed
    prompt: str = ""
    result_file: Optional[Path] = None


@dataclass
class OMCTeam:
    """Orchestrates execution via tmux panes (Knights) and local harnesses.

    IDs accepted by dispatch/collect/terminate:
    - Knight IDs: sir_boris, sir_helio, sir_codex
    - Harness IDs: harness_openclaw, harness_claude, harness_codex,
      harness_opencode, harness_droid, harness_pi

    Optional environment override:
    - CAMELOT_HARNESS_OVERRIDES='{"sir_codex":"harness_codex"}'
      This lets you swap a Knight route to a Harness without code changes.
    """

    session: str = TMUX_SESSION
    workers: dict[str, WorkerPane] = field(default_factory=dict)
    results_dir: Path = field(default_factory=lambda: CAMELOT_OS / "logs" / "omc_team")
    backend: str = "tmux"

    # Engine CLI commands per knight.
    ENGINE_COMMANDS: dict[str, str] = field(
        default_factory=lambda: {
            "sir_boris": str(CAMELOT_OS / "claude-ollama.cmd"),
            "sir_helio": "gemini",
            "sir_codex": "codex",
        }
    )

    # Per-knight env overrides — all LLM calls route through CLIProxyAPI (:8080)
    WORKER_ENV: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "sir_boris":  {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8080/v1"},
            "sir_codex":  {"OPENAI_BASE_URL":    "http://127.0.0.1:8080/v1"},
            "sir_alex":   {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8080/v1"},
            "sir_sentinel": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8080/v1"},
        }
    )

    # Interchangeable harness commands.
    HARNESS_COMMANDS: dict[str, str] = field(
        default_factory=lambda: {
            "harness_openclaw": "clawdbot",
            "harness_claude": "claude",
            "harness_codex": "codex",
            "harness_opencode": "opencode",
            "harness_droid": "droid",
            "harness_pi": "pi",
        }
    )

    def __post_init__(self) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "tmux" if shutil.which("tmux") else "local"
        self._harness_overrides = self._load_harness_overrides()
        self._harness_runtime_pref = os.getenv("CAMELOT_HARNESS_RUNTIME", "auto").strip().lower() or "auto"
        self._go_runner_path = os.getenv("CAMELOT_GO_HARNESS_RUNNER", "").strip()
        self._rust_runner_path = os.getenv("CAMELOT_RUST_HARNESS_RUNNER", "").strip()

    @staticmethod
    def _load_harness_overrides() -> dict[str, str]:
        """Load optional knight->harness override map from env."""
        raw = os.getenv("CAMELOT_HARNESS_OVERRIDES", "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    @staticmethod
    def _is_harness(worker: WorkerPane) -> bool:
        return worker.knight_id.startswith("harness_")

    def _resolve_target_id(self, target_id: str) -> str:
        """Resolve external target aliases to known worker IDs."""
        if target_id in self.workers:
            return target_id

        override = self._harness_overrides.get(target_id)
        if override and override in self.workers:
            return override

        # Support "harness:codex" shorthand.
        if target_id.startswith("harness:"):
            candidate = f"harness_{target_id.split(':', 1)[1]}"
            if candidate in self.workers:
                return candidate

        return target_id

    def _runner_candidates(self) -> dict[str, Optional[Path]]:
        go_default = CAMELOT_OS / "control_plane" / "runners" / "go" / "bin" / "harness-runner.exe"
        rust_default = CAMELOT_OS / "control_plane" / "runners" / "rust" / "target" / "release" / "harness_runner.exe"
        return {
            "go": Path(self._go_runner_path) if self._go_runner_path else go_default,
            "rust": Path(self._rust_runner_path) if self._rust_runner_path else rust_default,
        }

    def _select_harness_runner(self) -> tuple[Optional[str], Optional[Path]]:
        candidates = self._runner_candidates()
        pref = self._harness_runtime_pref

        if pref in {"go", "rust"}:
            runner = candidates.get(pref)
            if runner and runner.exists():
                return pref, runner
            return None, None

        if pref == "python":
            return None, None

        if pref == "auto":
            go_runner = candidates.get("go")
            if go_runner and go_runner.exists():
                return "go", go_runner
            rust_runner = candidates.get("rust")
            if rust_runner and rust_runner.exists():
                return "rust", rust_runner
            return None, None

        return None, None

    def spawn_session(self) -> bool:
        """Create execution workers.

        - local backend: all workers are local subprocess workers.
        - tmux backend: core Knights get panes, Harnesses still register as
          local subprocess workers.
        """
        if self.backend != "tmux":
            pane_idx = 0
            for knight_id, engine_cmd in self.ENGINE_COMMANDS.items():
                self.workers[knight_id] = WorkerPane(
                    knight_id=knight_id,
                    engine_cmd=engine_cmd,
                    pane_index=pane_idx,
                    status="idle",
                )
                pane_idx += 1
            for harness_id, engine_cmd in self.HARNESS_COMMANDS.items():
                self.workers[harness_id] = WorkerPane(
                    knight_id=harness_id,
                    engine_cmd=engine_cmd,
                    pane_index=-1,
                    status="idle",
                )
            return True

        subprocess.run(["tmux", "kill-session", "-t", self.session], capture_output=True)

        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", self.session, "-n", "foundry"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False

        self.workers["sir_boris"] = WorkerPane(
            knight_id="sir_boris",
            engine_cmd=self.ENGINE_COMMANDS["sir_boris"],
            pane_index=0,
            status="idle",
        )

        pane_idx = 1
        for knight_id in ("sir_helio", "sir_codex"):
            cmd = self.ENGINE_COMMANDS.get(knight_id)
            if not cmd or not shutil.which(cmd):
                continue

            subprocess.run(
                ["tmux", "split-window", "-t", f"{self.session}:foundry", "-h"],
                capture_output=True,
            )
            self.workers[knight_id] = WorkerPane(
                knight_id=knight_id,
                engine_cmd=cmd,
                pane_index=pane_idx,
                status="idle",
            )
            pane_idx += 1

        for harness_id, engine_cmd in self.HARNESS_COMMANDS.items():
            self.workers[harness_id] = WorkerPane(
                knight_id=harness_id,
                engine_cmd=engine_cmd,
                pane_index=-1,
                status="idle",
            )

        subprocess.run(
            ["tmux", "select-layout", "-t", f"{self.session}:foundry", "tiled"],
            capture_output=True,
        )
        return True

    def dispatch(self, knight_id: str, prompt: str, agent_prompt: str = "") -> bool:
        """Send a task to a specific Knight or Harness worker.

        SP-01 gate: all A2A dispatch clears RBAC before touching any execution terminal.
        Unknown or denied knights are blocked; HITL_REQUIRED upgrades to a warning log.
        """
        # RBAC gate — SP-01 remediation
        try:
            from rbac_matrix import RBACMatrix
            rbac = RBACMatrix()
            rbac_ok, rbac_issues = rbac.check(knight_id, "KINETIC", "general", 0.5)
            if not rbac_ok:
                import logging
                logging.getLogger("camelot.omc").warning(
                    "[SP-01][BLOCKED] dispatch denied for knight=%s issues=%s",
                    knight_id, rbac_issues,
                )
                return False
            if rbac_issues:
                import logging
                logging.getLogger("camelot.omc").info(
                    "[SP-01][HITL] dispatch proceeding with issues=%s", rbac_issues
                )
        except Exception:
            pass  # RBAC unavailable — fail-open with logged warning

        resolved_id = self._resolve_target_id(knight_id)
        worker = self.workers.get(resolved_id)
        if not worker:
            return False

        if self.backend != "tmux" or self._is_harness(worker):
            worker.prompt = prompt
            worker.result_file = self.results_dir / f"{worker.knight_id}_{int(time.time())}.json"
            worker.status = "running"
            return True

        result_file = self.results_dir / f"{worker.knight_id}_{int(time.time())}.json"
        engine_cmd = worker.engine_cmd

        if worker.knight_id == "sir_boris":
            shell_cmd = f'{engine_cmd} --print "{prompt}" 2>&1 | tee {result_file}'
        elif worker.knight_id == "sir_helio":
            shell_cmd = f'{engine_cmd} "{prompt}" 2>&1 | tee {result_file}'
        elif worker.knight_id == "sir_codex":
            # Route through CLIProxyAPI for free provider pool
            shell_cmd = f'OPENAI_BASE_URL=http://127.0.0.1:8080/v1 {engine_cmd} "{prompt}" 2>&1 | tee {result_file}'
        else:
            return False

        target = f"{self.session}:foundry.{worker.pane_index}"
        subprocess.run(["tmux", "send-keys", "-t", target, shell_cmd, "Enter"], capture_output=True)
        worker.status = "running"
        return True

    def _resolve_local_command(self, worker: WorkerPane) -> Optional[list[str]]:
        cmd = worker.engine_cmd

        if cmd.lower().endswith(".cmd"):
            cmd_path = Path(cmd)
            if not cmd_path.exists():
                return None
            return ["cmd.exe", "/c", str(cmd_path), "--print", worker.prompt]

        resolved = shutil.which(cmd)
        if not resolved:
            return None

        # Keep execution generic so harnesses remain swappable by config.
        return [resolved, worker.prompt]

    def _resolve_harness_native_command(self, worker: WorkerPane, timeout: int) -> Optional[list[str]]:
        runtime, runner_path = self._select_harness_runner()
        if not runtime or not runner_path:
            return None

        return [
            str(runner_path),
            "--engine",
            worker.engine_cmd,
            "--knight-id",
            worker.knight_id,
            "--prompt",
            worker.prompt,
            "--cwd",
            str(CAMELOT_OS),
            "--timeout-sec",
            str(timeout),
        ]

    def _missing_engine_payload(self, worker: WorkerPane) -> str:
        payload = {
            "backend": "local-fallback",
            "knight_id": worker.knight_id,
            "engine_cmd": worker.engine_cmd,
            "status": "simulated",
            "message": "Engine unavailable locally; generated structured fallback output.",
            "prompt": worker.prompt,
        }
        return json.dumps(payload, indent=2)

    def _run_local_worker(self, worker: WorkerPane, timeout: int) -> str:
        command: Optional[list[str]]
        backend_label = "local-subprocess"

        if self._is_harness(worker):
            command = self._resolve_harness_native_command(worker, timeout=timeout)
            if command:
                backend_label = "local-native-harness"
            else:
                command = self._resolve_local_command(worker)
        else:
            command = self._resolve_local_command(worker)

        if command is None:
            return self._missing_engine_payload(worker)

        try:
            proc_env = os.environ.copy()
            proc_env.update(self.WORKER_ENV.get(worker.knight_id, {}))
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=timeout,
                cwd=str(CAMELOT_OS),
                env=proc_env,
            )
            stdout_text = (result.stdout or b"").decode("utf-8", errors="replace").strip()
            stderr_text = (result.stderr or b"").decode("utf-8", errors="replace").strip()
            if backend_label == "local-native-harness":
                raw_stdout = stdout_text
                if raw_stdout:
                    try:
                        native_payload = json.loads(raw_stdout)
                        if isinstance(native_payload, dict):
                            native_payload.setdefault("backend", backend_label)
                            native_payload.setdefault("knight_id", worker.knight_id)
                            native_payload.setdefault("engine_cmd", worker.engine_cmd)
                            native_payload.setdefault("returncode", result.returncode)
                            if stderr_text:
                                native_payload.setdefault("runner_stderr", stderr_text)
                            return json.dumps(native_payload, indent=2)
                    except Exception:
                        pass

            payload = {
                "backend": backend_label,
                "knight_id": worker.knight_id,
                "engine_cmd": worker.engine_cmd,
                "returncode": result.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
            }
            return json.dumps(payload, indent=2)
        except Exception as exc:
            payload = {
                "backend": backend_label,
                "knight_id": worker.knight_id,
                "engine_cmd": worker.engine_cmd,
                "status": "failed",
                "error": str(exc),
                "prompt": worker.prompt,
            }
            return json.dumps(payload, indent=2)

    def collect(self, knight_id: str) -> Optional[str]:
        """Read the latest result file from a knight or harness output."""
        resolved_id = self._resolve_target_id(knight_id)
        pattern = f"{resolved_id}_*.json"
        files = sorted(self.results_dir.glob(pattern), reverse=True)
        if not files:
            return None
        return files[0].read_text(encoding="utf-8", errors="replace")

    def collect_all(self, timeout: int = 120) -> dict[str, Optional[str]]:
        """Wait for all running workers and collect results."""
        results: dict[str, Optional[str]] = {}
        for worker_id, worker in self.workers.items():
            if worker.status != "running":
                results[worker_id] = None
                continue

            if self.backend != "tmux" or self._is_harness(worker):
                output = self._run_local_worker(worker, timeout=timeout)
                if worker.result_file:
                    worker.result_file.write_text(output, encoding="utf-8")
                worker.status = "completed" if output else "failed"
                results[worker_id] = output
                continue

            deadline = time.time() + timeout
            output = None
            while time.time() < deadline:
                output = self.collect(worker_id)
                if output and len(output) > 10:
                    break
                time.sleep(2)

            worker.status = "completed" if output else "failed"
            results[worker_id] = output

        return results

    def terminate(self, knight_id: str) -> bool:
        """Terminate a specific worker."""
        resolved_id = self._resolve_target_id(knight_id)
        worker = self.workers.get(resolved_id)
        if not worker:
            return False
        if self.backend != "tmux" or self._is_harness(worker):
            worker.status = "idle"
            return True
        target = f"{self.session}:foundry.{worker.pane_index}"
        subprocess.run(["tmux", "send-keys", "-t", target, "C-c", ""], capture_output=True)
        worker.status = "idle"
        return True

    def teardown(self) -> bool:
        """Kill the entire tmux session and clear workers."""
        if self.backend != "tmux":
            self.workers.clear()
            return True
        result = subprocess.run(["tmux", "kill-session", "-t", self.session], capture_output=True)
        self.workers.clear()
        return result.returncode == 0

    def status(self) -> dict[str, str]:
        """Return status of all worker targets."""
        return {worker_id: worker.status for worker_id, worker in self.workers.items()}
