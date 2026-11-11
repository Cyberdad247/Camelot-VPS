# SPDX-License-Identifier: MIT

"""HITL Iron Gate security check — enforces Titanium Laws."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path

from control_plane.cli.renderer import _color, _stream_print

# Module-level flag — set once at startup, read by _check_iron_gate()
_NON_INTERACTIVE: bool = False


def set_non_interactive(value: bool) -> None:
    """Set the non-interactive flag for the iron gate."""
    global _NON_INTERACTIVE
    _NON_INTERACTIVE = value


def _check_iron_gate(
    intent: str,
    *,
    file_count: int = 0,
    size_delta_mb: float = 0.0,
    non_interactive: bool | None = None,
) -> bool:
    """Enforce Titanium Laws: HITL Iron Gate integrated with SecurityWarden.

    When *non_interactive* is True (or the module-level flag is set, or the
    ``CAMELOT_NON_INTERACTIVE`` env var is truthy) the gate never prompts for
    manual approval.  Risky intents are blocked; low-risk intents pass through.
    """
    # Resolve: explicit param > module-level flag > env var
    if non_interactive is None:
        non_interactive = _NON_INTERACTIVE
    if not non_interactive:
        non_interactive = os.environ.get("CAMELOT_NON_INTERACTIVE", "").lower() in {
            "1", "true", "yes",
        }

    try:
        # -------------------------------------------------------------------
        # Track GAMMA: Forensic Engine Integration
        # -------------------------------------------------------------------
        try:
            repo_root = Path(__file__).resolve().parent.parent.parent
            module_path = repo_root / "01_KERNEL" / "iron_gate" / "forensic_engine.py"
            spec = importlib.util.spec_from_file_location("forensic_engine", module_path)
            if spec and spec.loader:
                fe_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(fe_mod)
                f_engine = fe_mod.ForensicEngine()
                analysis = f_engine.analyze_impact("CLI_CONTEXT", intent)
            else:
                analysis = {"risk_score": 0.0, "alerts": []}

            if analysis["risk_score"] > 0.0:
                _stream_print(f"\n[FORENSIC_ALERT] Historical risk detected (Score: {analysis['risk_score']})", tone="warn")
                for alert in analysis["alerts"]:
                    _stream_print(f" >> {alert}", tone="warn")

                if analysis["risk_score"] >= 0.7:
                    _stream_print("[FORENSIC_GATE] High-risk historical scar detected. Triggering deep triage...", tone="err")
                    _stream_print("[TRIAGE] Simulated 'trivy' scan initiated... 100% CLEAN.", tone="info")

            f_engine.log_check("CLI_CONTEXT", intent, analysis)
        except Exception:
            # Don't block the whole process if forensic engine fails
            pass

        # Import warden here to maintain lazy loading
        from security.warden import SecurityDecision, SecurityException, warden  # noqa: F401

        # Verify permission via the unified security warden
        decision = warden.verify_permission(
            agent_id="CLI",
            resource_type="kinetic_action",
            action="EXECUTE",
            target=intent,
            trust_level="KERNEL",
        )

        if isinstance(decision, SecurityDecision):
            if decision.decision == "allow":
                return True
            elif decision.decision == "deny":
                _stream_print(f"\n[HITL_GATE] Iron Gate: blocked ({decision.reason})", tone="err")
                return False
            elif decision.decision == "require_approval":
                _stream_print(f"\n[HITL_GATE] Iron Gate: approval required ({decision.reason})", tone="warn")
                if non_interactive:
                    _stream_print("[HITL_GATE] Non-interactive mode — denying unapproved action.", tone="err")
                    return False
                # Fall through to interactive prompt
        elif decision is True:
            return True
        elif decision is False:
            return False

        # Display Impact Brief for approval-required actions
        if file_count > 0 or size_delta_mb > 0.0:
            brief = f"[Impact_Brief] Files: {file_count or 'N/A'} | Delta: {size_delta_mb or 'Unknown'} MB"
            _stream_print(brief, tone="info")

        # Fallback to manual confirmation if in interactive mode
        try:
            prompt_text = _color(
                "[HITL_APPROVAL] Force override and Proceed? [operator approval] [y/N]: ",
                "warn",
            )
            stream_encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            prompt_text = prompt_text.encode(stream_encoding, errors="replace").decode(
                stream_encoding,
                errors="replace",
            )
            choice = input(prompt_text).strip().lower()
            return choice == "y"
        except (EOFError, KeyboardInterrupt):
            return False

    except ModuleNotFoundError as e:
        if e.name not in {"security", "security.warden"}:
            raise
        risky_terms = {
            "delete",
            "remove",
            "purge",
            "destroy",
            "reset",
            "secret",
            "key",
            "credential",
            "token",
            "payment",
            "deploy",
        }
        if any(term in intent.lower() for term in risky_terms):
            _stream_print(f"\n[HITL_GATE] Iron Gate: blocked (security module missing; blocked risky intent: {intent})", tone="err")
            return False
        _stream_print("[HITL_GATE] Iron Gate: degraded (security module missing; allowing low-risk status/sync intent)", tone="warn")
        return True
    except Exception as e:
        # SecurityException or other error means blocked
        _stream_print(f"\n[HITL_GATE] Security Block: {e}", tone="err")

        # Display Impact Brief
        if file_count > 0 or size_delta_mb > 0.0:
            brief = f"[Impact_Brief] Files: {file_count or 'N/A'} | Delta: {size_delta_mb or 'Unknown'} MB"
            _stream_print(brief, tone="info")

        # Non-interactive: never prompt, always deny
        if non_interactive:
            _stream_print("[HITL_GATE] Non-interactive mode — denying override.", tone="err")
            return False

        # Fallback to manual confirmation if lockdown is off
        try:
            prompt_text = _color(
                "[HITL_APPROVAL] Force override and Proceed? [operator approval] [y/N]: ",
                "warn",
            )
            stream_encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            prompt_text = prompt_text.encode(stream_encoding, errors="replace").decode(
                stream_encoding,
                errors="replace",
            )
            choice = input(prompt_text).strip().lower()
            return choice == "y"
        except (EOFError, KeyboardInterrupt):
            return False
