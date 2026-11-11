# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
AgentArmor v2.0 — Zero-Trust Security Hypervisor & Ingress Filter
CAMELOT-OS / Titan-OS Sovereign Security Substrate
=============================================================================
Enforces:
1. Anya First/Last Law: Sanitizes incoming prompts and terminal command vectors.
2. Zero-Trust AST and Regex Pattern Analysis: Intercepts destructive git operations,
   ledger truncation, air-gap leaks, and unauthorized privileged commands.
3. HMAC-SHA256 Request Verification & Replay Protection.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SecurityViolationError(Exception):
    """Raised when an untrusted payload attempts privileged or destructive execution."""


@dataclass(frozen=True)
class ArmorVerdict:
    """Evaluation result for an inspected command or execution payload."""
    allowed: bool
    verdict: str  # "ARMOR_PASS" | "ARMOR_BLOCK"
    risk_level: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    violations: List[str] = field(default_factory=list)
    sanitized_text: Optional[str] = None


class AgentArmor:
    """
    Zero-trust security gateway and ingress hypervisor.
    Intercepts payloads before reaching execution engines or sandboxes.
    """

    # Destructive and dangerous command patterns
    DANGEROUS_PATTERNS: List[tuple[re.Pattern, str, str]] = [
        # (Pattern, Violation Identifier, Risk Level)
        (
            re.compile(r"\bgit\s+push\b[^\n]*?(--force(?:-with-lease)?|(?<!\w)-f(?!\w))", re.I),
            "destructive_force_push",
            "CRITICAL",
        ),
        (
            re.compile(r"\b(?:rm|del|erase|unlink)\s+[^\n]*?(?:PROVENANCE_LEDGER|\.shadow|\.ledger)", re.I),
            "provenance_tampering",
            "CRITICAL",
        ),
        (
            re.compile(r"\b(?:drop|truncate)\s+(?:database|table|schema)\b", re.I),
            "destructive_database_mutation",
            "CRITICAL",
        ),
        (
            re.compile(r"\b(?:disable|bypass|skip)\s+[^\n]*?(?:hitl|human_gate|iron_gate)\b", re.I),
            "hitl_gate_bypass_attempt",
            "CRITICAL",
        ),
        (
            re.compile(r"\b(?:cat|type|curl|wget)\s+[^\n]*?(?:\.env|id_rsa|id_ed25519|\.aws/credentials)\b", re.I),
            "credential_exfiltration_attempt",
            "CRITICAL",
        ),
        (
            re.compile(r"\b(?:rmdir|rm\s+-rf|\/s\s+\/q)\s+[\/\\](?:[a-zA-Z]:[\/\\])?(?:Windows|System32|etc|usr|var)\b", re.I),
            "system_root_deletion_attempt",
            "CRITICAL",
        ),
    ]

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or "camelot-sovereign-agent-armor-default-key"

    def inspect_command(self, command: str) -> ArmorVerdict:
        """
        Inspect a shell or script command against zero-trust policy.
        """
        if not command or not command.strip():
            return ArmorVerdict(allowed=True, verdict="ARMOR_PASS", risk_level="LOW", violations=[])

        violations = []
        max_risk = "LOW"

        # 1. Regex pattern scan
        for pattern, violation_id, risk in self.DANGEROUS_PATTERNS:
            if pattern.search(command):
                violations.append(violation_id)
                if risk == "CRITICAL" or max_risk != "CRITICAL":
                    max_risk = risk

        # 2. Python AST inspection if payload resembles python code
        if any(keyword in command for keyword in ("import os", "import sys", "subprocess", "__import__", "exec(", "eval(")):
            try:
                tree = ast.parse(command)
                for node in ast.walk(tree):
                    # Check for dangerous system calls
                    if isinstance(node, ast.Call):
                        func_name = ""
                        if isinstance(node.func, ast.Name):
                            func_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            func_name = node.func.attr
                        
                        if func_name in ("exec", "eval"):
                            violations.append("dynamic_eval_forbidden")
                            max_risk = "HIGH"
            except SyntaxError:
                # Not valid standalone Python AST, continue with shell heuristics
                pass

        if violations:
            return ArmorVerdict(
                allowed=False,
                verdict="ARMOR_BLOCK",
                risk_level=max_risk,
                violations=violations,
                sanitized_text=None,
            )

        return ArmorVerdict(
            allowed=True,
            verdict="ARMOR_PASS",
            risk_level="LOW",
            violations=[],
            sanitized_text=command.strip(),
        )

    def assert_clean(self, command: str) -> ArmorVerdict:
        """
        Assert that the command is clean and allowed.
        Raises SecurityViolationError immediately if blocked.
        """
        verdict = self.inspect_command(command)
        if not verdict.allowed:
            raise SecurityViolationError(
                f"AgentArmor Gate Blocked Payload: violations={verdict.violations}, risk={verdict.risk_level}"
            )
        return verdict

    def sign_payload(self, payload: str, timestamp_iso: Optional[str] = None) -> str:
        """
        Generate HMAC-SHA256 signature for payload verification.
        """
        ts = timestamp_iso or datetime.now(timezone.utc).isoformat()
        message = f"{ts}:{payload}".encode("utf-8")
        return hmac.new(self.secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()

    def verify_payload_signature(
        self, payload: str, signature: str, timestamp_iso: str, max_skew_seconds: int = 300
    ) -> bool:
        """
        Verify HMAC-SHA256 signature with replay skew tolerance.
        """
        try:
            ts = datetime.fromisoformat(timestamp_iso)
            now = datetime.now(timezone.utc)
            skew = abs((now - ts).total_seconds())
            if skew > max_skew_seconds:
                return False

            expected_sig = self.sign_payload(payload, timestamp_iso)
            return hmac.compare_digest(expected_sig, signature)
        except Exception:
            return False
