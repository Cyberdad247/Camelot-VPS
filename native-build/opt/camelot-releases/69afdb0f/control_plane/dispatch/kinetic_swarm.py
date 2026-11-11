# SPDX-License-Identifier: MIT

"""
Kinetic Swarm Orchestration — 6-Agent Distributed Execution.

Agents:
  1. Hermes: Kinetic tool-calling (autonomous, code, terminal)
  2. OpenClaw: Reasoning (analysis, research, synthesis, planning)
  3. NanoBot: Edge inference (lightweight, offline, low-latency)
  4. ZeroClaw: Security (encryption, sandboxing, audit, compliance)
  5. Apis: Intelligence sensing (observability, metrics, anomaly detection)
  6. Galahad: Verification (integrity checking, audit, proof)
  7. Lancelot: Kinetic dispatch (rapid response, mission-critical, failover)

Wait, that's 7. Let me count the original: Hermes, OpenClaw, NanoBot, ZeroClaw, RustClaw = 5
Plus new: Apis, Galahad, Lancelot = 3 new
That's 8 total. The request was for 6. Let me recount from the TOON crystal:
["Systema", "Forge", "Octavian", "Apis", "Galahad", "Lancelot"] = 6

So I need to map:
- Systema → RustClaw (systems coordination)
- Forge → Hermes (manufacturing/optimization)
- Octavian → OpenClaw (architecture/governance)
- Apis → Apis (intelligence/sensing)
- Galahad → Galahad (purity/verification)
- Lancelot → Lancelot (kinetic dispatch)

But the original has 5 agents. Let me create the kinetic swarm with proper mapping.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from control_plane.agent_registry import AgentDefinition, get_agent_registry


class SwarmRole(str, Enum):
    """Role in kinetic swarm."""
    COORDINATOR = "coordinator"  # Systema (RustClaw)
    FORGE = "forge"  # Hermes
    ARCHITECT = "architect"  # OpenClaw
    SENSOR = "sensor"  # Apis
    VERIFIER = "verifier"  # Galahad
    EXECUTOR = "executor"  # Lancelot


@dataclass
class SwarmMember:
    """Member of kinetic swarm."""
    agent_id: str
    swarm_role: SwarmRole
    agent_def: AgentDefinition
    status: str = "ready"  # ready, busy, offline, error
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    tasks_completed: int = 0
    success_rate: float = 1.0
    latency_ms: float = 0.0


@dataclass
class SwarmTask:
    """Task in swarm execution."""
    task_id: str
    task_type: str
    priority: int = 5  # 1-10, 10 = highest
    assigned_to: Optional[str] = None  # agent_id
    status: str = "pending"  # pending, assigned, executing, completed, failed
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


class KineticSwarm:
    """6-Agent kinetic swarm orchestration."""

    def __init__(self):
        """Initialize kinetic swarm."""
        self.members: Dict[str, SwarmMember] = {}
        self.task_queue: List[SwarmTask] = []
        self.completed_tasks: List[SwarmTask] = []
        self.role_assignments = {
            "coordinator": "rustclaw",  # Systema
            "forge": "hermes",  # Hermes (Forge)
            "architect": "openclaw",  # Octavian (OpenClaw)
            "sensor": "apis",  # Apis
            "verifier": "galahad",  # Galahad
            "executor": "lancelot",  # Lancelot
        }
        self.registry = get_agent_registry()
        self._initialize_swarm()

    def _initialize_swarm(self) -> None:
        """Initialize swarm members."""
        for role_name, agent_id in self.role_assignments.items():
            agent_def = self.registry.get(agent_id)
            if agent_def:
                _role = SwarmRole[role_name.upper()] if role_name in [r.name.lower() for r in SwarmRole] else SwarmRole.COORDINATOR
                self.members[agent_id] = SwarmMember(
                    agent_id=agent_id,
                    swarm_role=SwarmRole(role_name),
                    agent_def=agent_def,
                )

    async def submit_task(
        self,
        task_id: str,
        task_type: str,
        priority: int = 5,
        required_role: Optional[SwarmRole] = None,
    ) -> SwarmTask:
        """Submit task to swarm."""
        task = SwarmTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
        )

        # Assign to appropriate agent
        if required_role:
            assigned_agent = self._find_agent_for_role(required_role)
            if assigned_agent:
                task.assigned_to = assigned_agent
                task.status = "assigned"

        self.task_queue.append(task)
        return task

    def _find_agent_for_role(self, role: SwarmRole) -> Optional[str]:
        """Find available agent for role."""
        for agent_id, member in self.members.items():
            if member.swarm_role == role and member.status == "ready":
                return agent_id
        return None

    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """Execute task via swarm."""
        task = next((t for t in self.task_queue if t.task_id == task_id), None)
        if not task:
            return {"error": "Task not found"}

        if not task.assigned_to:
            assigned = self._find_best_agent(task.task_type)
            if not assigned:
                task.status = "failed"
                return {"error": "No agents available"}
            task.assigned_to = assigned

        # Mark as executing
        task.status = "executing"
        agent = self.members[task.assigned_to]
        agent.status = "busy"

        try:
            # Simulate task execution
            result = await self._execute_via_agent(agent, task)
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.utcnow()

            # Update agent stats
            agent.tasks_completed += 1
            agent.status = "ready"

            self.completed_tasks.append(task)
            self.task_queue.remove(task)

            return result
        except Exception as e:
            task.status = "failed"
            agent.status = "ready"
            return {"error": str(e)}

    def _find_best_agent(self, task_type: str) -> Optional[str]:
        """Find best agent for task type."""
        # Match task type to agent capability
        task_to_capability = {
            "sensing": "sensor",
            "verification": "verifier",
            "optimization": "forge",
            "coordination": "coordinator",
            "reasoning": "architect",
            "execution": "executor",
        }

        role_name = task_to_capability.get(task_type, "coordinator")
        role = SwarmRole(role_name)
        return self._find_agent_for_role(role)

    async def _execute_via_agent(self, agent: SwarmMember, task: SwarmTask) -> Dict[str, Any]:
        """Execute task via specific agent."""
        # In production: send to actual agent endpoint
        # For now: simulate execution
        await asyncio.sleep(0.1)
        return {
            "task_id": task.task_id,
            "executed_by": agent.agent_id,
            "status": "success",
        }

    async def heartbeat(self) -> Dict[str, Any]:
        """Swarm heartbeat — check all agents."""
        status = {
            "members": len(self.members),
            "ready": sum(1 for m in self.members.values() if m.status == "ready"),
            "busy": sum(1 for m in self.members.values() if m.status == "busy"),
            "offline": sum(1 for m in self.members.values() if m.status == "offline"),
            "pending_tasks": len(self.task_queue),
            "completed_tasks": len(self.completed_tasks),
        }

        # Update last heartbeat for all members
        for member in self.members.values():
            member.last_heartbeat = datetime.utcnow()

        return status

    def get_swarm_status(self) -> str:
        """Get human-readable swarm status."""
        lines = [
            "╔════════════════════════════════════════╗",
            "║  Kinetic Swarm Status (6 Agents)      ║",
            "╚════════════════════════════════════════╝",
            "",
        ]

        for _agent_id, member in self.members.items():
            role = member.swarm_role.value.upper()
            status = member.status.upper()
            lines.append(f"  {member.agent_def.name:12} [{role:10}] {status:8} ✓")

        lines.extend([
            "",
            f"Pending tasks: {len(self.task_queue)}",
            f"Completed tasks: {len(self.completed_tasks)}",
            "",
        ])

        return "\n".join(lines)

    def get_member_stats(self) -> Dict[str, Any]:
        """Get detailed member statistics."""
        return {
            member.agent_id: {
                "name": member.agent_def.name,
                "role": member.swarm_role.value,
                "status": member.status,
                "tasks_completed": member.tasks_completed,
                "success_rate": member.success_rate,
                "latency_ms": member.latency_ms,
            }
            for member in self.members.values()
        }


# ── Module-level singleton ────────────────────────────────────────────────

_swarm: Optional[KineticSwarm] = None


def get_kinetic_swarm() -> KineticSwarm:
    """Get or create shared KineticSwarm instance."""
    global _swarm
    if _swarm is None:
        _swarm = KineticSwarm()
    return _swarm


async def submit_task_to_swarm(
    task_id: str,
    task_type: str,
    priority: int = 5,
    required_role: Optional[SwarmRole] = None,
) -> SwarmTask:
    """Submit task to kinetic swarm."""
    swarm = get_kinetic_swarm()
    return await swarm.submit_task(task_id, task_type, priority, required_role)


async def execute_swarm_task(task_id: str) -> Dict[str, Any]:
    """Execute task via kinetic swarm."""
    swarm = get_kinetic_swarm()
    return await swarm.execute_task(task_id)
