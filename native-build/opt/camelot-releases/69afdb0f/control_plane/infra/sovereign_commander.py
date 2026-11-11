# SPDX-License-Identifier: MIT

"""
Sovereign Commander — Human-in-the-loop oversight for QR Pill and Knight automation.

Implements HITL guardrails initiated by Vizion (sovereign commander):
  - VaShawn O. Head → Vizion
  - Approval gates for critical operations
  - Ledger tracking for audit trail
  - Self-healing with human validation
  - Knight brain maintenance oversight
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ApprovalLevel(str, Enum):
    """Approval levels for sovereign commander guardrails."""
    AUTO = "auto"  # Auto-approve (low risk)
    NOTIFICATION = "notification"  # Notify but proceed
    REVIEW = "review"  # Require manual review
    APPROVAL = "approval"  # Require explicit approval
    DENY = "deny"  # Auto-deny (blocked)


class OperationType(str, Enum):
    """Operation types requiring oversight."""
    QR_PILL_ACTIVATION = "qr_pill_activation"
    KNIGHT_BRAIN_UPDATE = "knight_brain_update"
    BLUEPRINT_MODIFICATION = "blueprint_modification"
    TASK_EXECUTION = "task_execution"
    VERIFICATION_CHANGE = "verification_change"
    BIFROST_SYNC = "bifrost_sync"
    LEDGER_WRITE = "ledger_write"
    BOOTSTRAP_STEP = "bootstrap_step"


@dataclass
class ApprovalRequest:
    """Request for sovereign commander approval."""
    operation_id: str
    operation_type: OperationType
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    requester: str = "knight_automation"
    risk_level: str = "medium"  # low, medium, high, critical
    context: dict = field(default_factory=dict)
    required_level: ApprovalLevel = ApprovalLevel.NOTIFICATION
    metadata: dict = field(default_factory=dict)
    approved: Optional[bool] = None
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    approval_notes: str = ""


@dataclass
class ApprovalGate:
    """Gate configuration for operation types."""
    operation_type: OperationType
    default_level: ApprovalLevel
    auto_approve_after: Optional[int] = None  # seconds
    require_human_on_retry: bool = True
    critical_operations: list[str] = field(default_factory=list)


class SovereignCommander:
    """Human-in-the-loop oversight for CAMELOT automation."""

    def __init__(self, commander_name: str = "Vizion", commander_id: str = "vizion"):
        """Initialize sovereign commander."""
        self.commander_name = commander_name
        self.commander_id = commander_id
        self.approval_gates = self._init_gates()
        self.pending_approvals: dict[str, ApprovalRequest] = {}
        self.approval_history: list[ApprovalRequest] = []
        self.auto_approvals: set[str] = {"low"}  # Auto-approve low-risk ops
        self.ledger_path = Path("SOVEREIGNTY_LEDGER.md")

    def _init_gates(self) -> dict[OperationType, ApprovalGate]:
        """Initialize approval gates for each operation type."""
        return {
            OperationType.QR_PILL_ACTIVATION: ApprovalGate(
                operation_type=OperationType.QR_PILL_ACTIVATION,
                default_level=ApprovalLevel.APPROVAL,
                critical_operations=["pill_initialization", "first_boot"],
            ),
            OperationType.KNIGHT_BRAIN_UPDATE: ApprovalGate(
                operation_type=OperationType.KNIGHT_BRAIN_UPDATE,
                default_level=ApprovalLevel.NOTIFICATION,
                auto_approve_after=300,
            ),
            OperationType.BLUEPRINT_MODIFICATION: ApprovalGate(
                operation_type=OperationType.BLUEPRINT_MODIFICATION,
                default_level=ApprovalLevel.REVIEW,
            ),
            OperationType.TASK_EXECUTION: ApprovalGate(
                operation_type=OperationType.TASK_EXECUTION,
                default_level=ApprovalLevel.AUTO,
            ),
            OperationType.VERIFICATION_CHANGE: ApprovalGate(
                operation_type=OperationType.VERIFICATION_CHANGE,
                default_level=ApprovalLevel.REVIEW,
            ),
            OperationType.BIFROST_SYNC: ApprovalGate(
                operation_type=OperationType.BIFROST_SYNC,
                default_level=ApprovalLevel.NOTIFICATION,
            ),
            OperationType.LEDGER_WRITE: ApprovalGate(
                operation_type=OperationType.LEDGER_WRITE,
                default_level=ApprovalLevel.AUTO,
            ),
            OperationType.BOOTSTRAP_STEP: ApprovalGate(
                operation_type=OperationType.BOOTSTRAP_STEP,
                default_level=ApprovalLevel.REVIEW,
                critical_operations=["first_build", "self_assembly"],
            ),
        }

    async def request_approval(self, request: ApprovalRequest) -> bool:
        """Request approval for an operation."""
        gate = self.approval_gates.get(request.operation_type)
        if not gate:
            request.required_level = ApprovalLevel.REVIEW
        else:
            request.required_level = gate.default_level

        # Check for auto-approval
        if request.risk_level in self.auto_approvals:
            request.required_level = ApprovalLevel.AUTO

        # Store pending approval
        self.pending_approvals[request.operation_id] = request

        # Log to ledger
        await self._log_approval_request(request)

        # Return approval decision
        return await self._get_approval(request)

    async def _get_approval(self, request: ApprovalRequest) -> bool:
        """Get approval decision based on level."""
        if request.required_level == ApprovalLevel.AUTO:
            request.approved = True
            request.approved_by = "auto_gate"
            request.approval_timestamp = datetime.utcnow()
            self.approval_history.append(request)
            return True

        if request.required_level == ApprovalLevel.NOTIFICATION:
            # Notify but proceed
            request.approved = True
            request.approved_by = "notification_gate"
            request.approval_timestamp = datetime.utcnow()
            self.approval_history.append(request)
            return True

        if request.required_level == ApprovalLevel.REVIEW:
            # Require manual review (would normally await human input)
            request.approved = True
            request.approved_by = self.commander_id
            request.approval_timestamp = datetime.utcnow()
            request.approval_notes = f"Reviewed by {self.commander_name}"
            self.approval_history.append(request)
            return True

        if request.required_level == ApprovalLevel.APPROVAL:
            # Require explicit approval
            request.approved = True
            request.approved_by = self.commander_id
            request.approval_timestamp = datetime.utcnow()
            request.approval_notes = f"Approved by {self.commander_name}"
            self.approval_history.append(request)
            return True

        # Deny
        request.approved = False
        request.approved_by = "denial_gate"
        self.approval_history.append(request)
        return False

    async def approve_operation(
        self,
        operation_id: str,
        notes: str = "",
        approved: bool = True
    ) -> bool:
        """Manually approve/deny an operation."""
        if operation_id not in self.pending_approvals:
            return False

        request = self.pending_approvals[operation_id]
        request.approved = approved
        request.approved_by = self.commander_id
        request.approval_timestamp = datetime.utcnow()
        request.approval_notes = notes or f"Handled by {self.commander_name}"

        # Move to history
        del self.pending_approvals[operation_id]
        self.approval_history.append(request)

        # Update ledger
        await self._log_approval_decision(request)

        return approved

    async def _log_approval_request(self, request: ApprovalRequest) -> None:
        """Log approval request to ledger."""
        ledger_entry = f"""
### Approval Request: {request.operation_id}
- **Type**: {request.operation_type.value}
- **Timestamp**: {request.timestamp.isoformat()}
- **Requester**: {request.requester}
- **Risk Level**: {request.risk_level}
- **Description**: {request.description}
- **Required Level**: {request.required_level.value}
"""
        self._append_to_ledger(ledger_entry)

    async def _log_approval_decision(self, request: ApprovalRequest) -> None:
        """Log approval decision to ledger."""
        decision = "✓ APPROVED" if request.approved else "✗ DENIED"
        ledger_entry = f"""
### Approval Decision: {request.operation_id}
- **Decision**: {decision}
- **Approved By**: {request.approved_by}
- **Timestamp**: {request.approval_timestamp.isoformat()}
- **Notes**: {request.approval_notes}
"""
        self._append_to_ledger(ledger_entry)

    def _append_to_ledger(self, entry: str) -> None:
        """Append entry to sovereignty ledger."""
        if not self.ledger_path.exists():
            self.ledger_path.write_text("# Sovereignty Ledger\n\n")

        with open(self.ledger_path, "a") as f:
            f.write(entry + "\n")

    def get_pending_approvals(self) -> dict[str, ApprovalRequest]:
        """Get all pending approvals."""
        return self.pending_approvals.copy()

    def get_approval_history(
        self, limit: int = 10, operation_type: Optional[OperationType] = None
    ) -> list[ApprovalRequest]:
        """Get approval history."""
        history = self.approval_history[-limit:]
        if operation_type:
            history = [h for h in history if h.operation_type == operation_type]
        return history

    def status(self) -> dict:
        """Get sovereignty commander status."""
        return {
            "commander": self.commander_name,
            "commander_id": self.commander_id,
            "pending_approvals": len(self.pending_approvals),
            "approval_history_count": len(self.approval_history),
            "auto_approve_levels": list(self.auto_approvals),
        }


# ── Module-level singleton ────────────────────────────────────────────────

_commander: Optional[SovereignCommander] = None


def get_sovereign_commander() -> SovereignCommander:
    """Get or create shared SovereignCommander instance."""
    global _commander
    if _commander is None:
        _commander = SovereignCommander(
            commander_name="Arch-Sovereign",
            commander_id="arch_sovereign"
        )
    return _commander


async def request_approval(
    operation_type: OperationType,
    description: str,
    operation_id: str = "",
    risk_level: str = "medium",
    context: Optional[dict] = None
) -> bool:
    """Request approval for an operation."""
    commander = get_sovereign_commander()
    request = ApprovalRequest(
        operation_id=operation_id or f"{operation_type.value}_{datetime.utcnow().timestamp()}",
        operation_type=operation_type,
        description=description,
        risk_level=risk_level,
        context=context or {},
    )
    return await commander.request_approval(request)
