# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
DeerFlow 2.0 — Sandboxed Sub-Agent Execution
==============================================
Two-tier validation and execution:

  Tier 1 (Native): Zero-overhead syntax validation using local toolchains.
    - Python: ast.parse() + compile() (in-process, ~0ms)
    - Rust:   rustc --error-format=short (native binary, ~200ms)
    - Go:     go vet / go build (native binary, ~300ms)

  Tier 2 (Docker): Full isolated execution for untrusted code.
    - 2GB RAM limit per container, max 3 concurrent (semaphore-gated)
    - Read-only filesystem, tmpfs scratch, no network

Native validation is the default. Docker is opt-in for execution.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"
SANDBOX_SERVICE = "deerflow-sandbox"
OUTPUT_DIR = Path(__file__).parent.parent / "logs" / "deerflow"

# Titanium Law: 8GB ceiling. Max 3 containers x 2GB = 6GB, leaving 2GB for host.
MAX_CONTAINERS = 3
_CONTAINER_SEMAPHORE = threading.Semaphore(MAX_CONTAINERS)

# Docker images per language
_IMAGES = {
    "python": "python:3.11-slim",
    "rust": "rust:1.78-slim",
    "go": "golang:1.22-alpine",
}


@dataclass
class SandboxConfig:
    """Configuration for a DeerFlow sandbox instance."""
    mem_limit: str = "2g"
    cpus: float = 2.0
    timeout_sec: int = 300
    read_only: bool = True
    network: bool = False  # no network by default for isolation


@dataclass
class SandboxResult:
    """Result from a sandboxed execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    sandbox_id: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class DeerFlowSandbox:
    """Manages Docker-based sandboxed execution for SARDA sub-agents.

    Each execution runs in an isolated container with:
    - 2GB RAM limit (Titanium Law: 8GB total ceiling)
    - Read-only filesystem (no host pollution)
    - 512MB tmpfs for scratch space
    - No network access (default)
    - Auto-cleanup after execution
    - Max 3 concurrent containers (semaphore-gated)
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._docker_available: Optional[bool] = None

    @property
    def active_containers(self) -> int:
        """Number of sandbox containers currently running."""
        return MAX_CONTAINERS - _CONTAINER_SEMAPHORE._value

    def check_docker(self) -> bool:
        """Verify Docker is available and running."""
        if self._docker_available is not None:
            return self._docker_available
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True, text=True, timeout=10,
            )
            self._docker_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._docker_available = False
        return self._docker_available

    def _build_base_cmd(self, sandbox_id: str) -> list[str]:
        """Build the common docker run prefix with security constraints."""
        cmd = [
            "docker", "run", "--rm",
            "--name", sandbox_id,
            "--memory", self.config.mem_limit,
            f"--cpus={self.config.cpus}",
            "--read-only",
            "--tmpfs", "/tmp:size=512m",
            "--security-opt", "no-new-privileges:true",
        ]
        if not self.config.network:
            cmd.extend(["--network", "none"])
        cmd.extend(["-v", f"{OUTPUT_DIR.resolve()}:/workspace/output"])
        return cmd

    def _run_container(
        self,
        cmd: list[str],
        sandbox_id: str,
        timeout: int,
        stdin_data: Optional[str] = None,
    ) -> SandboxResult:
        """Execute a docker run command with semaphore gating and telemetry."""
        _CONTAINER_SEMAPHORE.acquire()
        start = time.perf_counter()
        timed_out = False
        try:
            result = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True, text=True,
                timeout=timeout,
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = -1
            stdout = ""
            stderr = f"Sandbox timed out after {timeout}s"
            subprocess.run(
                ["docker", "kill", sandbox_id],
                capture_output=True, timeout=10,
            )
        finally:
            _CONTAINER_SEMAPHORE.release()

        duration_ms = (time.perf_counter() - start) * 1000

        sandbox_result = SandboxResult(
            exit_code=exit_code,
            stdout=stdout[:10000],
            stderr=stderr[:5000],
            duration_ms=round(duration_ms, 1),
            sandbox_id=sandbox_id,
            timed_out=timed_out,
        )

        # Log execution telemetry
        log_file = OUTPUT_DIR / f"{sandbox_id}.json"
        log_file.write_text(json.dumps({
            "sandbox_id": sandbox_id,
            "exit_code": exit_code,
            "duration_ms": sandbox_result.duration_ms,
            "timed_out": timed_out,
            "stdout_len": len(stdout),
            "stderr_len": len(stderr),
        }, indent=2), encoding="utf-8")

        return sandbox_result

    def execute_python(
        self,
        code: str,
        sandbox_id: str = "",
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """Execute Python code in an isolated Docker container.

        Code is passed via stdin pipe to prevent shell injection.
        """
        if not sandbox_id:
            sandbox_id = f"df_py_{int(time.time())}"
        timeout = timeout or self.config.timeout_sec

        if not self.check_docker():
            return SandboxResult(
                exit_code=-1, stdout="", stderr="Docker not available",
                duration_ms=0, sandbox_id=sandbox_id,
            )

        cmd = self._build_base_cmd(sandbox_id)
        cmd.extend(["-i", _IMAGES["python"], "python", "-"])

        return self._run_container(cmd, sandbox_id, timeout, stdin_data=code)

    def execute_compiled(
        self,
        code: str,
        language: str,
        sandbox_id: str = "",
        timeout: Optional[int] = None,
    ) -> SandboxResult:
        """Compile and execute Rust or Go code in an isolated Docker container.

        Args:
            code: Source code to compile and run.
            language: "rust" or "go".
            sandbox_id: Optional identifier.
            timeout: Override default timeout (seconds).
        """
        if language not in ("rust", "go"):
            return SandboxResult(
                exit_code=-1, stdout="",
                stderr=f"Unsupported language: {language}. Use 'rust' or 'go'.",
                duration_ms=0, sandbox_id=sandbox_id or "err",
            )

        if not sandbox_id:
            sandbox_id = f"df_{language}_{int(time.time())}"
        timeout = timeout or self.config.timeout_sec

        if not self.check_docker():
            return SandboxResult(
                exit_code=-1, stdout="", stderr="Docker not available",
                duration_ms=0, sandbox_id=sandbox_id,
            )

        cmd = self._build_base_cmd(sandbox_id)

        if language == "rust":
            # Write to tmpfs, compile, run
            shell_cmd = (
                "cat > /tmp/main.rs && "
                "rustc /tmp/main.rs -o /tmp/out 2>&1 && "
                "/tmp/out"
            )
            cmd.extend(["-i", _IMAGES["rust"], "sh", "-c", shell_cmd])
        else:  # go
            shell_cmd = (
                "cat > /tmp/main.go && "
                "cd /tmp && go run main.go"
            )
            cmd.extend(["-i", _IMAGES["go"], "sh", "-c", shell_cmd])

        return self._run_container(cmd, sandbox_id, timeout, stdin_data=code)

    # ------------------------------------------------------------------
    # Tier 1: Native Validation (zero overhead, no Docker required)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_python_native(code: str) -> SandboxResult:
        """Validate Python syntax using ast.parse() + compile(). Zero overhead."""
        start = time.perf_counter()
        try:
            ast.parse(code, filename="<forge>")
            compile(code, "<forge>", "exec")
            duration = (time.perf_counter() - start) * 1000
            return SandboxResult(
                exit_code=0, stdout="OK", stderr="",
                duration_ms=round(duration, 1), sandbox_id="native_py",
            )
        except SyntaxError as e:
            duration = (time.perf_counter() - start) * 1000
            return SandboxResult(
                exit_code=1, stdout="",
                stderr=f"SyntaxError: {e.msg} (line {e.lineno})",
                duration_ms=round(duration, 1), sandbox_id="native_py",
            )

    @staticmethod
    def validate_rust_native(code: str, timeout: int = 15) -> SandboxResult:
        """Validate Rust syntax using local rustc. ~200ms typical."""
        rustc = shutil.which("rustc")
        if not rustc:
            return SandboxResult(
                exit_code=-1, stdout="", stderr="rustc not found on PATH",
                duration_ms=0, sandbox_id="native_rs",
            )

        tmp_dir = None
        start = time.perf_counter()
        try:
            tmp_dir = tempfile.mkdtemp(prefix="df_rs_")
            src = Path(tmp_dir) / "main.rs"
            src.write_text(code, encoding="utf-8")

            result = subprocess.run(
                [rustc, "--edition", "2021", "--error-format=short",
                 str(src), "-o", os.devnull],
                capture_output=True, text=True, timeout=timeout,
                cwd=tmp_dir,
            )
            duration = (time.perf_counter() - start) * 1000
            return SandboxResult(
                exit_code=result.returncode,
                stdout=result.stdout[:5000],
                stderr=result.stderr[:5000],
                duration_ms=round(duration, 1),
                sandbox_id="native_rs",
            )
        except subprocess.TimeoutExpired:
            duration = (time.perf_counter() - start) * 1000
            return SandboxResult(
                exit_code=-1, stdout="",
                stderr=f"rustc timed out after {timeout}s",
                duration_ms=round(duration, 1),
                sandbox_id="native_rs", timed_out=True,
            )
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def validate_go_native(code: str, timeout: int = 15) -> SandboxResult:
        """Validate Go syntax using local go vet. ~300ms typical."""
        go_bin = shutil.which("go")
        if not go_bin:
            return SandboxResult(
                exit_code=-1, stdout="", stderr="go not found on PATH",
                duration_ms=0, sandbox_id="native_go",
            )

        tmp_dir = None
        start = time.perf_counter()
        try:
            tmp_dir = tempfile.mkdtemp(prefix="df_go_")
            src = Path(tmp_dir) / "main.go"
            src.write_text(code, encoding="utf-8")

            # Initialize a throwaway module so go vet works
            subprocess.run(
                [go_bin, "mod", "init", "forge_validate"],
                capture_output=True, text=True, timeout=5,
                cwd=tmp_dir,
            )

            result = subprocess.run(
                [go_bin, "vet", str(src)],
                capture_output=True, text=True, timeout=timeout,
                cwd=tmp_dir,
            )
            duration = (time.perf_counter() - start) * 1000
            return SandboxResult(
                exit_code=result.returncode,
                stdout=result.stdout[:5000],
                stderr=result.stderr[:5000],
                duration_ms=round(duration, 1),
                sandbox_id="native_go",
            )
        except subprocess.TimeoutExpired:
            duration = (time.perf_counter() - start) * 1000
            return SandboxResult(
                exit_code=-1, stdout="",
                stderr=f"go vet timed out after {timeout}s",
                duration_ms=round(duration, 1),
                sandbox_id="native_go", timed_out=True,
            )
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Unified validate_code: native-first, Docker as fallback
    # ------------------------------------------------------------------

    def validate_code(
        self,
        code: str,
        language: str = "python",
        sandbox_id: str = "",
        use_docker: bool = False,
        timeout: int = 30,
    ) -> SandboxResult:
        """Validate code syntax. Native toolchain by default, Docker opt-in.

        Args:
            code: Source code to validate.
            language: "python", "rust", or "go".
            use_docker: Force Docker sandbox instead of native validation.
            timeout: Timeout in seconds.

        Returns:
            SandboxResult — success=True means code is syntactically valid.
        """
        # Tier 1: Native validation (default — zero overhead)
        if not use_docker:
            if language == "python":
                return self.validate_python_native(code)
            elif language == "rust":
                return self.validate_rust_native(code, timeout)
            elif language == "go":
                return self.validate_go_native(code, timeout)

        # Tier 2: Docker sandbox (opt-in or unsupported native language)
        if not sandbox_id:
            sandbox_id = f"df_val_{int(time.time())}"

        if not self.check_docker():
            # Final fallback: try native even if Docker was requested
            if language == "python":
                return self.validate_python_native(code)
            return SandboxResult(
                exit_code=-1, stdout="", stderr="Docker not available and no native validator",
                duration_ms=0, sandbox_id=sandbox_id,
            )

        if language == "python":
            validation_code = (
                "import sys\n"
                "code = sys.stdin.read()\n"
                "try:\n"
                "    compile(code, '<forge>', 'exec')\n"
                "    print('OK')\n"
                "except SyntaxError as e:\n"
                "    print(f'SyntaxError: {e}', file=sys.stderr)\n"
                "    sys.exit(1)\n"
            )
            cmd = self._build_base_cmd(sandbox_id)
            cmd.extend(["-i", _IMAGES["python"], "python", "-"])
            return self._run_container(cmd, sandbox_id, timeout,
                                       stdin_data=validation_code + "\n" + code)
        elif language == "rust":
            shell_cmd = "cat > /tmp/main.rs && rustc --edition 2021 /tmp/main.rs -o /dev/null 2>&1"
            cmd = self._build_base_cmd(sandbox_id)
            cmd.extend(["-i", _IMAGES["rust"], "sh", "-c", shell_cmd])
            return self._run_container(cmd, sandbox_id, timeout, stdin_data=code)
        elif language == "go":
            shell_cmd = "cat > /tmp/main.go && cd /tmp && go build -o /dev/null main.go 2>&1"
            cmd = self._build_base_cmd(sandbox_id)
            cmd.extend(["-i", _IMAGES["go"], "sh", "-c", shell_cmd])
            return self._run_container(cmd, sandbox_id, timeout, stdin_data=code)
        else:
            return SandboxResult(
                exit_code=-1, stdout="",
                stderr=f"Validation not supported for language: {language}",
                duration_ms=0, sandbox_id=sandbox_id,
            )

    def validate_compose(self) -> bool:
        """Validate that docker-compose.yml includes the DeerFlow sandbox."""
        if not COMPOSE_FILE.exists():
            return False
        content = COMPOSE_FILE.read_text(encoding="utf-8")
        return SANDBOX_SERVICE in content

    def status(self) -> dict:
        """Return sandbox system status including native toolchain availability."""
        return {
            "docker_available": self.check_docker(),
            "compose_configured": self.validate_compose(),
            "output_dir": str(OUTPUT_DIR),
            "active_containers": self.active_containers,
            "max_containers": MAX_CONTAINERS,
            "native_toolchains": {
                "python": True,  # Always available (ast.parse is stdlib)
                "rustc": shutil.which("rustc") is not None,
                "go": shutil.which("go") is not None,
            },
            "validation_mode": "native" if not self.check_docker() else "native (docker available for execution)",
            "config": {
                "mem_limit": self.config.mem_limit,
                "cpus": self.config.cpus,
                "timeout_sec": self.config.timeout_sec,
                "read_only": self.config.read_only,
                "network": self.config.network,
            },
        }
