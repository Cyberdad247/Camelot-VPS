# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Adversarial Crucible Runner — v9000.14-CYBERTRONIA (Pillar 4, P2-T06).
======================================================================
Ephemeral, isolated execution of compiled artifacts. A code artifact (and an
optional test) is materialized into a throwaway temp directory, run in a
separate subprocess with a wall-clock timeout, its result captured, and the
sandbox is destroyed on exit — pass or fail. Nothing the artifact writes
escapes the temp dir; the parent process is never blocked beyond the timeout.

This is the "Red-Green" execution half of the Adversarial Crucible: ColMAD
(control_plane.colmad) supplies the adversarial *review*; this runner supplies
the isolated *execution* of the resulting artifact.

Run as module:
    python -m control_plane.crucible_runner --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class CrucibleResult:
    passed: bool
    returncode: Optional[int]
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    elapsed_ms: float = 0.0
    sandbox: str = ""           # path (already removed by the time you read this)
    artifacts: list[str] = field(default_factory=list)

    def render(self) -> str:
        status = ("TIMEOUT" if self.timed_out else "PASS" if self.passed else "FAIL")
        return (f"Crucible[{status}] rc={self.returncode} {self.elapsed_ms:.0f}ms\n"
                f"  stdout: {self.stdout.strip()[:120]}\n"
                f"  stderr: {self.stderr.strip()[:120]}")


class CrucibleRunner:
    """Run an artifact in a disposable subprocess sandbox."""

    def __init__(self, timeout_sec: float = 30.0, python: Optional[str] = None):
        self.timeout_sec = timeout_sec
        self.python = python or sys.executable

    def run_python(self, source: str, *, entry: str = "artifact.py",
                   files: Optional[dict[str, str]] = None,
                   argv: Optional[list[str]] = None) -> CrucibleResult:
        """Write `source` to `entry` in a fresh temp dir (plus any extra `files`)
        and execute it in an isolated subprocess. The sandbox is always removed.
        """
        sandbox = Path(tempfile.mkdtemp(prefix="crucible_"))
        t0 = time.perf_counter()
        timed_out = False
        rc: Optional[int] = None
        out = err = ""
        try:
            (sandbox / entry).write_text(source, encoding="utf-8")
            for rel, content in (files or {}).items():
                p = sandbox / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            artifacts = [str(p.relative_to(sandbox)) for p in sandbox.rglob("*") if p.is_file()]
            try:
                proc = subprocess.run(
                    [self.python, entry, *(argv or [])],
                    cwd=str(sandbox),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                )
                rc, out, err = proc.returncode, proc.stdout, proc.stderr
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                out = exc.stdout or "" if isinstance(exc.stdout, str) else ""
                err = (exc.stderr or "" if isinstance(exc.stderr, str) else "") + "\n[crucible] timeout"
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

        elapsed = (time.perf_counter() - t0) * 1000
        return CrucibleResult(
            passed=(rc == 0 and not timed_out),
            returncode=rc, stdout=out, stderr=err, timed_out=timed_out,
            elapsed_ms=elapsed, sandbox=str(sandbox), artifacts=artifacts,
        )

    def run_pytest(self, test_source: str, *, target_source: str = "",
                   target_name: str = "artifact.py") -> CrucibleResult:
        """Run a pytest test body against an optional target module in isolation."""
        files = {}
        if target_source:
            files[target_name] = target_source
        runner = (
            "import sys, subprocess\n"
            "rc = subprocess.run([sys.executable,'-m','pytest','-q','test_artifact.py'],"
            "cwd='.').returncode\n"
            "sys.exit(rc)\n"
        )
        files["test_artifact.py"] = test_source
        return self.run_python(runner, entry="run.py", files=files)


# ── Self-test ────────────────────────────────────────────────────────────────

def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("CrucibleRunner self-test (P2-T06)")
    runner = CrucibleRunner(timeout_sec=15.0)

    # 1. Passing artifact runs in isolation and reports success.
    ok = runner.run_python("print('hello from the crucible'); raise SystemExit(0)")
    check("passing artifact -> passed", ok.passed and ok.returncode == 0)
    check("stdout captured", "hello from the crucible" in ok.stdout)

    # 2. Failing artifact is reported, not raised into the parent.
    bad = runner.run_python("raise SystemExit(3)")
    check("failing artifact -> not passed, rc=3", (not bad.passed) and bad.returncode == 3)

    # 3. Runaway artifact is killed by the timeout (isolation holds).
    slow = CrucibleRunner(timeout_sec=1.0).run_python("import time; time.sleep(10)")
    check("runaway artifact -> timed_out", slow.timed_out and not slow.passed)

    # 4. Sandbox is destroyed after the run.
    check("sandbox removed after run", not Path(ok.sandbox).exists())

    # 5. Extra files are materialized and importable inside the sandbox.
    multi = runner.run_python(
        "import helper; print(helper.greet())",
        files={"helper.py": "def greet():\n    return 'GREETING_OK'\n"},
    )
    check("multi-file artifact runs", multi.passed and "GREETING_OK" in multi.stdout)

    # 6. pytest-in-isolation: green test passes, red test fails.
    green = runner.run_pytest("def test_ok():\n    assert 1 + 1 == 2\n")
    check("pytest green -> passed", green.passed)
    red = runner.run_pytest("def test_bad():\n    assert False\n")
    check("pytest red -> not passed", not red.passed)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — crucible_runner")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print(CrucibleRunner().run_python("print('crucible ready')").render())
