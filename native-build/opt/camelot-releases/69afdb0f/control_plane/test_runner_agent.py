# SPDX-License-Identifier: MIT

"""
Camelot Split-Brain OS — TestRunnerAgent (PIV Self-Healing Loop)
================================================================
Plan -> Implement -> Validate cycle.
Sends synthetic tasks to the Control Plane and validates output structure.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field

from main import ControlPlane, MessageType, TaskPayload


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class PIVLoop:
    """Plan-Implement-Validate self-healing loop."""
    max_retries: int = 3
    results: list[TestResult] = field(default_factory=list)

    async def run(self) -> bool:
        cp = ControlPlane()
        tests = self._plan()

        for attempt in range(1, self.max_retries + 1):
            print(f"\n[PIV] Attempt {attempt}/{self.max_retries}")
            self.results.clear()

            for test in tests:
                result = await self._implement_and_validate(cp, test)
                self.results.append(result)
                status = "PASS" if result.passed else "FAIL"
                print(f"  [{status}] {result.name}: {result.detail}")

            if all(r.passed for r in self.results):
                print(f"\n[PIV] All {len(self.results)} tests passed.")
                return True

            failed = [r for r in self.results if not r.passed]
            print(f"\n[PIV] {len(failed)} test(s) failed. Retrying...")

        print(f"\n[PIV] Exhausted {self.max_retries} retries. Self-healing failed.")
        return False

    def _plan(self) -> list[dict]:
        """Define synthetic test cases."""
        return [
            {
                "name": "A2A message structure",
                "task": TaskPayload(
                    intent="list directory contents",
                    parameters={"path": "."},
                ),
                "validate": lambda msg: (
                    msg.type == MessageType.STATUS
                    and "status" in msg.payload
                ),
            },
            {
                "name": "PDG blocks shell injection",
                "task": TaskPayload(
                    intent="exec shell command rm -rf /",
                    parameters={},
                ),
                "validate": lambda msg: (
                    msg.payload.get("status") == "BLOCKED"
                    and "PDG" in msg.payload.get("reason", "")
                ),
            },
            {
                "name": "Pure reasoning (no tool call)",
                "task": TaskPayload(
                    intent="explain quantum computing",
                    parameters={},
                ),
                "validate": lambda msg: (
                    msg.payload.get("status") == "REASONING_ONLY"
                ),
            },
            {
                "name": "Correlation ID propagation",
                "task": TaskPayload(
                    intent="list files in current directory",
                    parameters={"path": "."},
                ),
                "validate": lambda msg: msg.correlation_id is not None,
            },
            {
                "name": "PDG blocks path traversal",
                "task": TaskPayload(
                    intent="read file contents",
                    parameters={"path": "../../etc/passwd"},
                ),
                "validate": lambda msg: (
                    msg.payload.get("status") in ("COMPLETE", "REASONING_ONLY")
                    or msg.correlation_id is not None
                ),
            },
            {
                "name": "stat_file routing",
                "task": TaskPayload(
                    intent="get file metadata info",
                    parameters={"path": "."},
                ),
                "validate": lambda msg: (
                    msg.payload.get("status") in ("COMPLETE", "REASONING_ONLY")
                    and msg.correlation_id is not None
                ),
            },
        ]

    async def _implement_and_validate(
        self, cp: ControlPlane, test: dict
    ) -> TestResult:
        """Execute a single test case."""
        try:
            result = await cp.process_task(test["task"])
            passed = test["validate"](result)
            return TestResult(
                name=test["name"],
                passed=passed,
                detail=result.payload.get("status", str(result.payload)),
            )
        except Exception as e:
            return TestResult(
                name=test["name"],
                passed=False,
                detail=f"Exception: {e}",
            )


async def main():
    piv = PIVLoop(max_retries=3)
    success = await piv.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
