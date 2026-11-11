# SPDX-License-Identifier: MIT

"""
Camelot Split-Brain OS — Pydantic AI Control Plane
===================================================
Pure reasoning layer. ALL side-effects delegated to Kinetic Edge MCP servers.
No direct filesystem, subprocess, or network I/O permitted here.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

# Add KERNEL to path for telemetry import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    _TELEMETRY_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "01_KERNEL", "senses", "telemetry_client.py")
    )
    _TELEMETRY_SPEC = importlib.util.spec_from_file_location(
        "camelot_telemetry_client",
        _TELEMETRY_PATH,
    )
    if _TELEMETRY_SPEC is None or _TELEMETRY_SPEC.loader is None:
        raise ImportError(f"Unable to load telemetry client from {_TELEMETRY_PATH}")
    _TELEMETRY_MODULE = importlib.util.module_from_spec(_TELEMETRY_SPEC)
    _TELEMETRY_SPEC.loader.exec_module(_TELEMETRY_MODULE)
    RotelClient = _TELEMETRY_MODULE.RotelClient
    logger = RotelClient("control_plane")
except Exception:
    class DummyLogger:
        def info(self, *args, **kwargs): pass
    logger = DummyLogger()

from control_plane.infra.cloud_services import CloudServiceName, CloudServiceRequest, CloudServiceRouter
from control_plane.infra.deerflow_sandbox import DeerFlowSandbox
from control_plane.infra.omc_team import OMCTeam
from control_plane.infra.sarda_engine import SARDAEngine, SARDAResult
from control_plane.core.soul_router import RouteDecision, SoulRouter

# Phase H: Metrics collection
try:
    from control_plane.infra.phase_h_integration import get_metrics
    _METRICS = get_metrics()
except Exception:
    _METRICS = None  # Graceful degradation if metrics unavailable

import time

# ---------------------------------------------------------------------------
# A2A Message Schema (Typed Agent-to-Agent Protocol)
# ---------------------------------------------------------------------------

class MessageType(str, Enum):
    TASK = "task"
    STATUS = "status"
    TOOL_REQUEST = "tool_request"
    TOOL_RESPONSE = "tool_response"


class A2AMessage(BaseModel):
    """Typed Agent-to-Agent message envelope."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    type: MessageType
    source: str
    target: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class TaskPayload(BaseModel):
    """Payload for TASK messages."""
    intent: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)


class ToolRequest(BaseModel):
    """Request to invoke a Kinetic Edge MCP tool."""
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    """Response from a Kinetic Edge MCP tool."""
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# MCP Client — delegates all I/O to Kinetic Edge
# ---------------------------------------------------------------------------

class MCPClient:
    """HTTP client for Kinetic Edge MCP servers. No local execution."""

    def __init__(self, base_url: str = "http://127.0.0.1:3001"):
        self.base_url = base_url

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """Send a tool request to the Kinetic Edge MCP server."""
        msg = A2AMessage(
            type=MessageType.TOOL_REQUEST,
            source="control_plane",
            target="kinetic_edge",
            payload=request.model_dump(),
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/tool/{request.tool_name}",
                    json=msg.model_dump(),
                )
                data = resp.json()
                # Handle PDG blocks (HTTP 403)
                if resp.status_code == 403:
                    return ToolResponse(
                        tool_name=request.tool_name,
                        success=False,
                        error=data.get("error", "PDG BLOCKED"),
                    )
                resp.raise_for_status()
                return ToolResponse(
                    tool_name=request.tool_name,
                    success=True,
                    result=data.get("result"),
                )
        except Exception as e:
            return ToolResponse(
                tool_name=request.tool_name,
                success=False,
                error=str(e),
            )


# ---------------------------------------------------------------------------
# Control Plane Agent
# ---------------------------------------------------------------------------

class ControlPlane:
    """
    Pydantic AI reasoning agent.

    Receives tasks, decomposes them, and delegates I/O to Kinetic Edge
    via typed A2A messages. Never touches the filesystem directly.
    """

    def __init__(self, mcp_url: str = "http://127.0.0.1:3001"):
        self.mcp = MCPClient(base_url=mcp_url)
        self.cloud_services = CloudServiceRouter()
        self.soul_router = SoulRouter()
        self.deerflow = DeerFlowSandbox()
        self.sarda = SARDAEngine(
            soul_router=self.soul_router,
            deerflow=self.deerflow,
        )
        self.message_log: list[A2AMessage] = []

        # Titanium Law: verify weight lock on boot
        assert self.soul_router.verify_weight_lock(), (
            "WEIGHT LOCK VIOLATED: W_orchestration != 0.85"
        )

    def _extract_privacy(self, task: TaskPayload) -> float:
        privacy = 0.0
        for constraint in task.constraints:
            if constraint.startswith("privacy="):
                try:
                    privacy = float(constraint.split("=", 1)[1])
                except ValueError:
                    privacy = 0.0
        return privacy

    def _load_active_cartridge(self) -> str:
        active_path = Path(".camelot/active_cartridge.txt")
        if not active_path.exists():
            return ""
        try:
            active_name = active_path.read_text(encoding="utf-8").strip().upper()
        except Exception:
            return ""
        if not active_name:
            return ""
        path = Path(f".camelot/cartridges/{active_name}.md")
        if not path.exists():
            return ""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return ""
        logger.info("ACTIVE_CARTRIDGE_LOADED", name=active_name)
        return f"\n--- ACTIVE CARTRIDGE: {active_name} ---\n{content}\n"

    def _ingest_cartridges(self, intent: str) -> str:
        """Detect and load data cartridges into the context."""
        matches = re.findall(r"LOAD:\s*(\w+)", intent.upper())
        cartridge_context = "" if matches else self._load_active_cartridge()
        for name in matches:
            path = Path(f".camelot/cartridges/{name}.md")
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    cartridge_context += f"\n--- CARTRIDGE: {name} ---\n{content}\n"
                    logger.info("CARTRIDGE_LOADED", name=name)
                except Exception as exc:
                    logger.info("CARTRIDGE_LOAD_FAILED", name=name, error=str(exc))
        return cartridge_context

    def _cloud_policy_check(
        self,
        task: TaskPayload,
        request: CloudServiceRequest,
    ) -> Optional[str]:
        """Apply capability-scoped checks before invoking cloud services."""
        privacy = self._extract_privacy(task)
        intent = task.intent.lower()
        allow_sensitive_remote = "allow_remote_sensitive" in task.constraints

        if request.service in {CloudServiceName.CLOUDBRAIN_STATUS, CloudServiceName.HEALTH_ROLLUP}:
            return None

        if request.service is CloudServiceName.CLOUDBRAIN_MEMORY and privacy >= 0.95:
            return "High-privacy memory recall requires tighter local-only handling."

        if request.service is CloudServiceName.RESEARCH_AGENCY:
            if any(term in intent for term in {"write", "delete", "modify", "execute"}):
                return "Research agency is read-only and cannot be used for write-oriented tasks."
            if privacy >= 0.8 and not allow_sensitive_remote:
                return "Remote research is blocked for sensitive tasks without allow_remote_sensitive."

        return None

    def _should_autoresearch(self, intent: str) -> bool:
        lower = intent.lower()
        return any(term in lower for term in {"research", "deep dive", "deep-dive", "investigate"})

    def _research_compute_tier(self, intent: str, privacy: float = 0.0) -> str:
        lower = intent.lower()
        if privacy >= 0.8:
            return "kinetic"
        if any(
            term in lower
            for term in {"deep dive", "deep-dive", "investigate", "production ready", "production readiness"}
        ):
            return "apex"
        return "hybrid"

    def _northstar_aspect(self, intent: str) -> str:
        lower = intent.lower()
        if any(term in lower for term in {"audit", "review", "feedback", "critique"}):
            return "audit"
        if any(term in lower for term in {"architecture", "system", "design"}):
            return "architecture"
        if any(term in lower for term in {"ops", "operations", "runtime", "deploy"}):
            return "operations"
        if any(term in lower for term in {"growth", "market", "audience"}):
            return "growth"
        return "research"

    def _blueprint_budget_mode(self, task: TaskPayload) -> str:
        lower = task.intent.lower()
        if any(term in lower for term in {"resource constrained", "lean", "efficient", "minimal"}):
            return "lean"
        if any(term in lower for term in {"balanced", "moderate"}):
            return "balanced"
        return "lean"

    def _precise_memory_gb(self, task: TaskPayload) -> int:
        lower = task.intent.lower()
        if any(term in lower for term in {"8gb", "resource constrained", "lean"}):
            return 8
        if any(term in lower for term in {"16gb", "balanced"}):
            return 16
        if any(term in lower for term in {"32gb", "apex"}):
            return 32
        return 8

    async def _fetch_research_context(
        self,
        intent: str,
        privacy: float = 0.0,
    ) -> str:
        request = CloudServiceRequest(
            service=CloudServiceName.RESEARCH_AGENCY,
            payload={
                "objective": intent,
                "constraints": [f"privacy={privacy}"],
                "agent_id": "lady_apis",
                "compute_tier": self._research_compute_tier(intent, privacy),
            },
        )
        result = await self.cloud_services.invoke(request)
        if not result.success:
            return ""

        brief = str(result.result.get("brief", "")).strip()
        memory_count = result.result.get("memory_count", 0)
        return f"[RESEARCH_AGENCY]\n{brief}\n[memory_count={memory_count}]"

    @staticmethod
    def _execution_target_for_service(service: CloudServiceName) -> str:
        cloud_brain_services = {
            CloudServiceName.CLOUDBRAIN_STATUS,
            CloudServiceName.CLOUDBRAIN_MEMORY,
            CloudServiceName.NOTEBOOKLM_HEALTH,
            CloudServiceName.NOTEBOOKLM_SYNTHESIZE,
            CloudServiceName.NOTEBOOKLM_SYNC,
            CloudServiceName.NOTEBOOKLM_RESEARCH_START,
            CloudServiceName.NOTEBOOKLM_RESEARCH_POLL,
            CloudServiceName.NOTEBOOKLM_STUDIO_LIST,
            CloudServiceName.NOTEBOOKLM_STUDIO_GENERATE,
            CloudServiceName.NOTEBOOKLM_SOURCES_LIST,
            CloudServiceName.NOTEBOOKLM_SOURCES_ADD,
            CloudServiceName.NOTEBOOKLM_SOURCES_DELETE,
            CloudServiceName.HEALTH_ROLLUP,
        }
        if service in cloud_brain_services:
            return "cloud_brain"
        return "remote_service"

    def _resolve_route_context(self, task: TaskPayload) -> tuple[RouteDecision, str]:
        preferred_knight = str(
            task.parameters.get("preferred_knight")
            or task.parameters.get("agent_id")
            or ""
        ).strip().lower()
        intent = task.intent
        if preferred_knight in {"sir_alex", "alex"}:
            intent = f"cognitive {intent}"
        elif preferred_knight in {"sir_link", "link"}:
            intent = f"bridge {intent}"

        route_task = TaskPayload(
            intent=intent,
            parameters=task.parameters,
            constraints=task.constraints,
        )
        decision = self.route_to_knight(route_task)
        execution_target = str(task.parameters.get("execution_target") or "").strip().lower()
        if not execution_target:
            if decision.knight_id == "sir_link":
                execution_target = "local_terminal"
            elif decision.knight_id == "sir_alex":
                execution_target = "analysis_only"
            else:
                execution_target = "local_dispatch"
        return decision, execution_target

    async def process_task(self, task: TaskPayload) -> A2AMessage:
        """Decompose a task and execute via MCP tool delegation."""
        # Detect and ingest cartridges
        cartridge_data = self._ingest_cartridges(task.intent)
        if cartridge_data:
            task.intent = f"{cartridge_data}\n--- INTENT ---\n{task.intent}"

        route_decision, execution_target = self._resolve_route_context(task)
        route_summary = {
            "knight_id": route_decision.knight_id,
            "engine": route_decision.engine,
            "reason": route_decision.reason,
            "score": route_decision.score,
        }

        logger.info("PROCESSING_TASK", intent=task.intent)
        task_msg = A2AMessage(
            type=MessageType.TASK,
            source="user",
            target="control_plane",
            payload=task.model_dump(),
        )
        self.message_log.append(task_msg)

        # AgentArmor PDG check: block if untrusted data flows to shell sink
        if self._pdg_check(task):
            return A2AMessage(
                type=MessageType.STATUS,
                source="control_plane",
                target="user",
                payload={"status": "BLOCKED", "reason": "AgentArmor PDG violation"},
                correlation_id=task_msg.id,
            )

        cloud_req = self._plan_cloud_service(task)
        if cloud_req:
            policy_error = self._cloud_policy_check(task, cloud_req)
            if policy_error:
                blocked_msg = A2AMessage(
                    type=MessageType.STATUS,
                    source="control_plane",
                    target="user",
                    payload={
                        "status": "BLOCKED",
                        "task": task.intent,
                        "service": cloud_req.service.value,
                        "route": route_summary,
                        "execution_target": execution_target,
                        "reason": policy_error,
                    },
                    correlation_id=task_msg.id,
                )
                self.message_log.append(blocked_msg)
                return blocked_msg

            logger.info("EXECUTING_CLOUD_SERVICE", service=cloud_req.service.value)
            cloud_result = await self.cloud_services.invoke(cloud_req)
            response_msg = A2AMessage(
                type=MessageType.TOOL_RESPONSE,
                source="cloudbrain",
                target="control_plane",
                payload=cloud_result.model_dump(),
                correlation_id=task_msg.id,
            )
            self.message_log.append(response_msg)

            status_msg = A2AMessage(
                type=MessageType.STATUS,
                source="control_plane",
                target="user",
                payload={
                    "status": "COMPLETE" if cloud_result.success else "FAILED",
                    "task": task.intent,
                    "service": cloud_req.service.value,
                    "source": cloud_result.source,
                    "route": route_summary,
                    "execution_target": self._execution_target_for_service(cloud_req.service),
                    "result": cloud_result.result if cloud_result.success else {},
                    "error": cloud_result.error,
                },
                correlation_id=task_msg.id,
            )
            logger.info("TASK_PROCESS_STATUS", status=status_msg.payload.get("status"))
            self.message_log.append(status_msg)
            return status_msg

        # Phase 2: Merlin's Videneptus Routing (Generative Intent detection)
        generative_keywords = {"build", "refactor", "create", "scaffold", "feature", "fix", "implement"}
        if any(k in task.intent.lower() for k in generative_keywords):
            logger.info("MERLIN_ROUTING_TO_SARDA", intent=task.intent)
            privacy = self._extract_privacy(task)
            sarda_result = self.sarda_execute(task.intent, privacy=privacy)

            status_msg = A2AMessage(
                type=MessageType.STATUS,
                source="control_plane",
                target="user",
                payload={
                    "status": "COMPLETE" if sarda_result.critique and sarda_result.critique.passed else "FAILED",
                    "task": task.intent,
                    "service": "SARDA_ENGINE",
                    "route": route_summary,
                    "execution_target": execution_target,
                    "result": json.loads(sarda_result.to_json()),
                },
                correlation_id=task_msg.id,
            )
            self.message_log.append(status_msg)
            return status_msg

        # Route to appropriate MCP tool
        tool_req = self._plan_tool_call(task)
        if tool_req:
            logger.info("EXECUTING_TOOL_CALL", tool=tool_req.tool_name)
            result = await self.mcp.call_tool(tool_req)
            response_msg = A2AMessage(
                type=MessageType.TOOL_RESPONSE,
                source="kinetic_edge",
                target="control_plane",
                payload=result.model_dump(),
                correlation_id=task_msg.id,
            )
            self.message_log.append(response_msg)

        status_msg = A2AMessage(
            type=MessageType.STATUS,
            source="control_plane",
            target="user",
            payload={
                "status": "COMPLETE" if (tool_req and result.success) else "REASONING_ONLY",
                "task": task.intent,
                "route": route_summary,
                "execution_target": execution_target,
            },
            correlation_id=task_msg.id,
        )
        logger.info("TASK_PROCESS_STATUS", status=status_msg.payload.get("status"))
        self.message_log.append(status_msg)
        return status_msg

    def _pdg_check(self, task: TaskPayload) -> bool:
        """Program Dependency Graph security check.
        Block if untrusted source data could reach a shell execution sink."""
        dangerous_intents = {"exec", "shell", "eval", "subprocess", "os.system"}
        return any(d in task.intent.lower() for d in dangerous_intents)

    def route_to_knight(self, task: TaskPayload) -> RouteDecision:
        """Route task to appropriate knight via MFOE Soul Equation.

        Privacy >= 0.8 forces Sir Ghost (air-gapped).
        Complexity >= 0.8 forces multi-agent plan output.
        """
        # Phase H: Track routing operation
        start = time.perf_counter()
        try:
            privacy = 0.0
            magnitude = 0.5
            velocity = 0.5

            # Extract routing hints from constraints
            for c in task.constraints:
                if c.startswith("privacy="):
                    privacy = float(c.split("=", 1)[1])
                elif c.startswith("complexity="):
                    magnitude = float(c.split("=", 1)[1])
                elif c.startswith("velocity="):
                    velocity = float(c.split("=", 1)[1])

            result = self.soul_router.route(
                task.intent,
                velocity=velocity,
                magnitude=magnitude,
                privacy=privacy,
            )

            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('route', duration_ms, success=True,
                               tags={'intent': task.intent, 'knight': result.knight_id})

            return result
        except Exception as e:
            if _METRICS:
                duration_ms = (time.perf_counter() - start) * 1000
                _METRICS.record('route', duration_ms, success=False, error_message=str(e),
                               tags={'intent': task.intent})
            raise

    def _plan_tool_call(self, task: TaskPayload) -> Optional[ToolRequest]:
        """Map task intent to an MCP tool call. Returns None for pure reasoning."""
        intent = task.intent.lower()
        if "list" in intent and ("dir" in intent or "file" in intent):
            return ToolRequest(
                tool_name="list_directory",
                arguments=task.parameters,
            )
        if "read" in intent and "file" in intent:
            return ToolRequest(
                tool_name="read_file",
                arguments=task.parameters,
            )
        if "stat" in intent or "info" in intent or "metadata" in intent:
            return ToolRequest(
                tool_name="stat_file",
                arguments=task.parameters,
            )
        # Pure reasoning — no tool needed
        return None

    def _plan_cloud_service(self, task: TaskPayload) -> Optional[CloudServiceRequest]:
        """Map task intent to a cloudbrain or research agency service."""
        intent = task.intent.lower()

        # Omega₃ — NotebookLM Cloud Brain (check before generic cloudbrain keywords).
        if any(k in intent for k in {"notebooklm health", "oracle health", "brain health"}):
            return CloudServiceRequest(service=CloudServiceName.NOTEBOOKLM_HEALTH)

        if any(k in intent for k in {
            "notebooklm sync", "cloud brain sync", "sync cloud brain",
            "sync notebooklm", "omega sync", "ω_sync",
        }):
            payload: dict[str, Any] = {}
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            if task.parameters.get("note_title"):
                payload["note_title"] = str(task.parameters["note_title"])
            if task.parameters.get("extra_summary"):
                payload["extra_summary"] = str(task.parameters["extra_summary"])
            if task.parameters.get("content"):
                payload["content"] = str(task.parameters["content"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_SYNC,
                payload=payload,
            )

        if any(k in intent for k in {
            "synthesize", "ask brain", "ask the brain", "ask oracle",
            "notebook query", "notebooklm query", "cloud brain query",
        }):
            query = str(
                task.parameters.get("query")
                or task.parameters.get("question")
                or task.intent
            )
            payload: dict[str, Any] = {"query": query}
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            if "use_cache" in task.parameters:
                payload["use_cache"] = bool(task.parameters["use_cache"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_SYNTHESIZE,
                payload=payload,
            )

        # Omega₃.2 — LADY_APIS research dispatch
        if any(k in intent for k in {
            "notebook research", "notebooklm research",
            "deep research", "deep-dive research", "brain research",
        }):
            payload = {
                "query": str(task.parameters.get("query") or task.parameters.get("objective") or task.intent),
                "source": str(task.parameters.get("source", "web")),
                "mode": str(task.parameters.get("mode", "fast")),
            }
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_RESEARCH_START,
                payload=payload,
            )
        if any(k in intent for k in {"research poll", "research status", "poll research"}):
            payload = {}
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_RESEARCH_POLL,
                payload=payload,
            )

        # Omega₃.3 — SIR_SONUS studio dispatch
        if any(k in intent for k in {
            "studio list", "list artifacts", "list audio", "list video",
            "list reports", "list infographics", "list slide",
        }):
            artifact_type = str(task.parameters.get("artifact_type") or "audio")
            payload = {"artifact_type": artifact_type}
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_STUDIO_LIST,
                payload=payload,
            )
        if any(k in intent for k in {
            "generate audio", "generate video", "generate podcast",
            "generate report", "generate infographic", "generate slides",
            "generate mind map", "studio create", "studio generate",
        }):
            mapping = {
                "audio": "audio", "podcast": "audio",
                "video": "video",
                "report": "report",
                "infographic": "infographic",
                "slide": "slides", "slides": "slides",
                "mind map": "mind_map", "mindmap": "mind_map",
            }
            chosen = task.parameters.get("artifact_type")
            if not chosen:
                for k, v in mapping.items():
                    if k in intent:
                        chosen = v
                        break
            payload = {"artifact_type": str(chosen or "audio")}
            if task.parameters.get("instructions"):
                payload["instructions"] = str(task.parameters["instructions"])
            if task.parameters.get("source_ids"):
                payload["source_ids"] = list(task.parameters["source_ids"])
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_STUDIO_GENERATE,
                payload=payload,
            )

        # Omega₃.4 — MASON sources dispatch
        if any(k in intent for k in {"list sources", "sources list", "show sources"}):
            payload = {}
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_LIST,
                payload=payload,
            )
        if any(k in intent for k in {"add source", "add url", "add notebook source"}):
            payload = {}
            for k in ("url", "text", "title", "notebook_id"):
                if task.parameters.get(k) is not None:
                    payload[k] = task.parameters[k] if k != "notebook_id" else str(task.parameters[k])
            if task.parameters.get("wait") is not None:
                payload["wait"] = bool(task.parameters["wait"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_ADD,
                payload=payload,
            )
        if any(k in intent for k in {"delete source", "remove source"}):
            payload = {"source_id": str(task.parameters.get("source_id", ""))}
            if task.parameters.get("notebook_id"):
                payload["notebook_id"] = str(task.parameters["notebook_id"])
            return CloudServiceRequest(
                service=CloudServiceName.NOTEBOOKLM_SOURCES_DELETE,
                payload=payload,
            )

        if any(keyword in intent for keyword in {"health rollup", "unified health", "system health", "cloudbrain health", "ecosystem health"}) or intent == "health":
            return CloudServiceRequest(service=CloudServiceName.HEALTH_ROLLUP)

        if any(keyword in intent for keyword in {"cloudbrain", "notebook", "memory status"}):
            return CloudServiceRequest(service=CloudServiceName.CLOUDBRAIN_STATUS)

        if any(keyword in intent for keyword in {"research health", "research status", "agency health"}):
            return CloudServiceRequest(service=CloudServiceName.RESEARCH_AGENCY_HEALTH)

        if any(keyword in intent for keyword in {"northstar health", "war room health"}):
            return CloudServiceRequest(service=CloudServiceName.NORTHSTAR_HEALTH)

        if any(keyword in intent for keyword in {"blueprint health", "development blueprint health"}):
            return CloudServiceRequest(service=CloudServiceName.DEVELOPMENT_BLUEPRINT_HEALTH)

        if any(keyword in intent for keyword in {"precise health", "precise mode health", "swarm health"}):
            return CloudServiceRequest(service=CloudServiceName.PRECISE_MODE_HEALTH)

        if any(keyword in intent for keyword in {"eldergod health", "elder god forge health", "eldergod forge health"}):
            return CloudServiceRequest(service=CloudServiceName.ELDERGOD_FORGE_HEALTH)

        if any(keyword in intent for keyword in {"eldergod", "elder god forge", "eldergod forge"}):
            privacy = self._extract_privacy(task)
            return CloudServiceRequest(
                service=CloudServiceName.ELDERGOD_FORGE,
                payload={
                    "objective": str(task.parameters.get("objective") or task.intent),
                    "compute_tier": str(
                        task.parameters.get("compute_tier")
                        or self._research_compute_tier(task.intent, privacy)
                    ),
                    "multiverse_enabled": bool(task.parameters.get("multiverse_enabled", True)),
                    "omega_directive": str(task.parameters.get("omega_directive", "absolute_singularity")),
                },
            )

        if any(keyword in intent for keyword in {"memory", "context", "recall"}):
            return CloudServiceRequest(
                service=CloudServiceName.CLOUDBRAIN_MEMORY,
                payload={"agent_id": str(task.parameters.get("agent_id", "merlin"))},
            )

        if any(keyword in intent for keyword in {"research", "deep dive", "deep-dive", "investigate"}):
            privacy = self._extract_privacy(task)
            return CloudServiceRequest(
                service=CloudServiceName.RESEARCH_AGENCY,
                payload={
                    "objective": str(task.parameters.get("objective") or task.intent),
                    "constraints": [
                        str(item) for item in task.parameters.get("constraints", task.constraints)
                    ],
                    "agent_id": str(task.parameters.get("agent_id", "lady_apis")),
                    "compute_tier": str(
                        task.parameters.get("compute_tier")
                        or self._research_compute_tier(task.intent, privacy)
                    ),
                },
            )

        if any(keyword in intent for keyword in {"northstar", "war room", "brainstorm"}):
            privacy = self._extract_privacy(task)
            return CloudServiceRequest(
                service=CloudServiceName.NORTHSTAR,
                payload={
                    "objective": str(task.parameters.get("objective") or task.intent),
                    "aspect": str(task.parameters.get("aspect") or self._northstar_aspect(task.intent)),
                    "constraints": [
                        str(item) for item in task.parameters.get("constraints", task.constraints)
                    ],
                    "agent_id": str(task.parameters.get("agent_id", "northstar")),
                    "cartridge": str(task.parameters.get("cartridge", "COGNITIVE")),
                    "compute_tier": str(
                        task.parameters.get("compute_tier")
                        or self._research_compute_tier(task.intent, privacy)
                    ),
                    "multilogin_enabled": bool(task.parameters.get("multilogin_enabled", True)),
                    "browser_isolation": str(task.parameters.get("browser_isolation", "team")),
                    "template": task.parameters.get("template"),
                },
            )

        if any(keyword in intent for keyword in {"blueprint", "development blueprint", "resource constrained"}):
            privacy = self._extract_privacy(task)
            return CloudServiceRequest(
                service=CloudServiceName.DEVELOPMENT_BLUEPRINT,
                payload={
                    "objective": str(task.parameters.get("objective") or task.intent),
                    "compute_tier": str(
                        task.parameters.get("compute_tier")
                        or self._research_compute_tier(task.intent, privacy)
                    ),
                    "budget_mode": str(task.parameters.get("budget_mode") or self._blueprint_budget_mode(task)),
                    "team_size": int(task.parameters.get("team_size", 1)),
                    "horizon_days": int(task.parameters.get("horizon_days", 30)),
                    "prioritize_local_first": bool(task.parameters.get("prioritize_local_first", True)),
                    "multilogin_enabled": bool(task.parameters.get("multilogin_enabled", True)),
                    "template": task.parameters.get("template"),
                },
            )

        if any(keyword in intent for keyword in {"precise mode", "nano-knight", "nano knight", "swarm"}):
            privacy = self._extract_privacy(task)
            return CloudServiceRequest(
                service=CloudServiceName.PRECISE_MODE,
                payload={
                    "objective": str(task.parameters.get("objective") or task.intent),
                    "compute_tier": str(
                        task.parameters.get("compute_tier")
                        or self._research_compute_tier(task.intent, privacy)
                    ),
                    "browser_isolation": str(task.parameters.get("browser_isolation", "agency")),
                    "residential_proxy_enabled": bool(
                        task.parameters.get("residential_proxy_enabled", True)
                    ),
                    "stealth_enabled": bool(task.parameters.get("stealth_enabled", True)),
                    "ephemeral_sessions": bool(task.parameters.get("ephemeral_sessions", True)),
                    "operator_count": int(task.parameters.get("operator_count", 1)),
                    "memory_gb": int(task.parameters.get("memory_gb", self._precise_memory_gb(task))),
                },
            )

        return None

    # ------------------------------------------------------------------
    # OMC Team — Parallel Foundry Dispatch
    # ------------------------------------------------------------------

    def spawn_team(self) -> bool:
        """Spawn tmux session with Foundry Council engine panes."""
        self._omc_team = OMCTeam()
        return self._omc_team.spawn_session()

    def dispatch_parallel(
        self, tasks: list[tuple[str, str]]
    ) -> dict[str, bool]:
        """Dispatch tasks to multiple workers in parallel.

        Args:
            tasks: List of (worker_id, prompt) tuples.
                worker_id can be a Knight ID (sir_*) or Harness ID
                (harness_* or harness:<name> shorthand).

        Returns:
            Dict of worker_id -> dispatch success.
        """
        if not hasattr(self, "_omc_team"):
            self.spawn_team()
        return {
            knight_id: self._omc_team.dispatch(knight_id, prompt)
            for knight_id, prompt in tasks
        }

    def list_dispatch_targets(self) -> list[str]:
        """Return all available dispatch target IDs (knights + harnesses)."""
        if not hasattr(self, "_omc_team"):
            self.spawn_team()
        return sorted(self._omc_team.workers.keys())

    def collect_team_results(self, timeout: int = 120) -> dict:
        """Collect results from all running team workers."""
        if not hasattr(self, "_omc_team"):
            return {}
        return self._omc_team.collect_all(timeout=timeout)

    def team_self_test(
        self,
        *,
        worker_id: str = "harness_codex",
        prompt: str = "codex",
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Run a safe dispatch probe and validate harness JSON contract."""
        if not hasattr(self, "_omc_team"):
            self.spawn_team()

        targets = self.list_dispatch_targets()
        if worker_id not in targets and not worker_id.startswith("harness:"):
            return {
                "status": "FAILED",
                "worker_id": worker_id,
                "error": "unknown_dispatch_target",
                "available_targets": targets,
            }

        dispatched = self.dispatch_parallel([(worker_id, prompt)]).get(worker_id, False)
        if not dispatched:
            return {
                "status": "FAILED",
                "worker_id": worker_id,
                "error": "dispatch_failed",
            }

        collected = self.collect_team_results(timeout=timeout)
        raw_output = collected.get(worker_id)
        if not raw_output and worker_id.startswith("harness:"):
            alias = f"harness_{worker_id.split(':', 1)[1]}"
            raw_output = collected.get(alias)

        if not raw_output:
            return {
                "status": "FAILED",
                "worker_id": worker_id,
                "error": "no_output_collected",
            }

        try:
            payload = json.loads(raw_output)
        except Exception as exc:
            return {
                "status": "FAILED",
                "worker_id": worker_id,
                "error": "invalid_json_output",
                "exception": str(exc),
                "raw_output": raw_output[:1000],
            }

        required = {"backend", "knight_id", "engine_cmd"}
        missing = sorted(item for item in required if item not in payload)
        has_completion = ("returncode" in payload) or (str(payload.get("status", "")).lower() in {"simulated", "completed"})
        pass_contract = not missing and has_completion
        pass_execution = bool(payload.get("returncode") == 0 or str(payload.get("status", "")).lower() == "simulated")

        return {
            "status": "PASSED" if (pass_contract and pass_execution) else "FAILED",
            "worker_id": worker_id,
            "contract_passed": pass_contract,
            "execution_passed": pass_execution,
            "missing_keys": missing,
            "payload": payload,
        }

    def teardown_team(self) -> bool:
        """Kill the Foundry tmux session."""
        if not hasattr(self, "_omc_team"):
            return True
        return self._omc_team.teardown()


    # ------------------------------------------------------------------
    # DeerFlow 2.0 — Sandbox Status
    # ------------------------------------------------------------------

    def deerflow_status(self) -> dict:
        """Return DeerFlow sandbox system status for HUD/CLI."""
        return self.deerflow.status()

    # ------------------------------------------------------------------
    # SARDA Engine — Map-Reduce-Critique Dispatch
    # ------------------------------------------------------------------

    def sarda_plan(self, intent: str, privacy: float = 0.0) -> SARDAResult:
        """Dry-run SARDA: decompose and route without executing.

        Use this to preview which Knights will handle which sub-tasks
        before committing to a full Map-Reduce cycle.
        """
        augmented_intent = intent
        if self._should_autoresearch(intent):
            research_context = asyncio.run(self._fetch_research_context(intent, privacy=privacy))
            if research_context:
                augmented_intent = f"{intent}\n\n{research_context}"

        result = self.sarda.dry_run(augmented_intent, privacy=privacy)
        self.message_log.append(A2AMessage(
            type=MessageType.STATUS,
            source="sarda_engine",
            target="user",
            payload={
                "status": "PLAN",
                "task_id": result.task_id,
                "sub_tasks": len(result.sub_tasks),
                "knights": [st.knight_id for st in result.sub_tasks],
                "research_augmented": augmented_intent != intent,
            },
        ))
        return result

    def sarda_execute(
        self,
        intent: str,
        context: str = "",
        privacy: float = 0.0,
        timeout: int = 120,
    ) -> SARDAResult:
        """Full SARDA Map-Reduce-Critique cycle.

        MAP -> REDUCE -> CRITIQUE. Logs all phases to message_log.
        Returns SARDAResult with telemetry and critique verdict.
        """
        augmented_context = context
        if self._should_autoresearch(intent):
            research_context = asyncio.run(self._fetch_research_context(intent, privacy=privacy))
            if research_context:
                augmented_context = f"{context}\n\n{research_context}".strip()

        result = self.sarda.execute(
            intent=intent,
            context=augmented_context,
            privacy=privacy,
            timeout=timeout,
        )
        self.message_log.append(A2AMessage(
            type=MessageType.STATUS,
            source="sarda_engine",
            target="user",
            payload={
                "status": "SARDA_COMPLETE",
                "task_id": result.task_id,
                "phase": result.phase.value,
                "critique_passed": result.critique.passed if result.critique else None,
                "critique_confidence": result.critique.confidence if result.critique else None,
                "total_ms": result.total_ms,
                "research_augmented": augmented_context != context,
            },
        ))
        return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    cp = ControlPlane()
    task = TaskPayload(
        intent="list directory contents",
        parameters={"path": "."},
        constraints=["kinetic_purity"],
    )
    result = await cp.process_task(task)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
