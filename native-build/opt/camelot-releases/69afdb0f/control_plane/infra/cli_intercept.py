# SPDX-License-Identifier: MIT

"""CLI Intercept — Bridges camelot-cli to the MFOE Soul Router.

Every camelot-cli command passes through this intercept layer which:
1. Parses the intent from the command string
2. Scores it through the Soul Equation (S_omega = alpha*V + beta*M + gamma*P + delta*E)
3. Routes to the optimal Foundry Knight / engine
4. Dispatches execution to the appropriate backend (CLIProxyAPI, Ollama, or direct)

Usage:
    from control_plane.cli_intercept import CLIIntercept
    intercept = CLIIntercept()
    result = intercept.process("critique this architecture")
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from control_plane.main import ControlPlane, TaskPayload
from control_plane.core.soul_router import PRIVACY_KEYWORDS, RouteDecision, SoulRouter

CAMELOT_OS = Path(os.environ.get("CAMELOT_OS", Path.home() / "CAMELOT_OS"))
OMNIROUTE_CONFIG = CAMELOT_OS / "03_VAULT" / "training" / "configs" / "config" / "omniroute.json"


# ---------------------------------------------------------------------------
# Complexity & Scaling Estimator
# ---------------------------------------------------------------------------

# Keywords that indicate high complexity (magnitude >= 0.7)
_HIGH_COMPLEXITY = frozenset({
    "architecture", "refactor", "migrate", "redesign", "multi-agent",
    "microservice", "deploy", "infrastructure", "pipeline", "orchestrat",
    "scaling", "shard", "consensus", "evolution", "v1000", "hard-production",
})

# Keywords that indicate a quick, narrow request (magnitude <= 0.2)
_LOW_COMPLEXITY = frozenset({
    "status", "list", "show", "who", "help", "ping", "version",
    "simple", "quick", "small", "one-line", "one line",
})

# Keywords that indicate high velocity / immediate execution preference.
_URGENT = frozenset({
    "urgent", "asap", "immediately", "now", "today", "fast", "quickly",
})

# Keywords that suggest linear scaling / SSM preference
_LINEAR_REASONING = frozenset({
    "infinite context", "long context", "large file", "entire repo",
    "ouroboros", "mamba", "ssm", "1.58-bit", "bitnet",
})


def estimate_complexity(intent: str) -> float:
    """Estimate complexity score [0.0-1.0] from intent keywords."""
    lower = intent.lower()
    score = 0.4
    
    if any(kw in lower for kw in _HIGH_COMPLEXITY):
        score = 0.8
    elif any(kw in lower for kw in _LOW_COMPLEXITY):
        score = 0.2
        
    # Structural indicator: count code references or paths
    # (e.g. "update src/foo.py and tests/bar.py")
    path_count = len(re.findall(r'[a-zA-Z0-9_\-\./]+\.[a-z]{2,4}', lower))
    if path_count > 3:
        score = max(score, 0.75)
    elif path_count > 1:
        score = max(score, 0.6)
        
    # Word count heuristic
    word_count = len(lower.split())
    if word_count > 100:
        score = max(score, 0.9)
    elif word_count > 50:
        score = max(score, 0.7)
        
    return score


def estimate_linear_scaling_need(intent: str) -> float:
    """Estimate if this task requires linear scaling (SSM) [0.0-1.0]."""
    lower = intent.lower()
    if any(kw in lower for kw in _LINEAR_REASONING):
        return 0.9
    if "context" in lower and "long" in lower:
        return 0.85
    return 0.0


# ---------------------------------------------------------------------------
# Affinity & Retention API
# ---------------------------------------------------------------------------

_SCHEMA_INTENTS = frozenset({
    "//boot", "//scan", "omega_audit", "omega_reforge", "omega_sync",
    "genesis", "blueprint", "titanium_laws", "harness",
})

_MISSION_INTENTS = frozenset({
    "//forge", "//plan", "//heal", "refactor", "migrate", "deploy",
})


def generate_affinity_key(intent: str) -> str:
    """Generate a cache affinity key by abstracting out dynamic values.
    
    This ensures that structural identical prompts (e.g. 'Audit file X' and 
    'Audit file Y') route to the same worker node to maximize prefix hits.
    """
    # 1. Strip file paths and code references
    structural = re.sub(r'[a-zA-Z0-9_\-\./]+\.[a-z]{2,4}', '<FILE>', intent)
    
    # 2. Strip UUIDs (Mission IDs / Notebook IDs)
    structural = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '<UUID>', structural)
    
    # 3. Strip raw numbers
    structural = re.sub(r'\b\d+\b', '<NUM>', structural)
    
    # 4. Normalize whitespace
    structural = " ".join(structural.split()).lower()
    
    return hashlib.md5(structural.encode()).hexdigest()[:8]


def estimate_retention_class(intent: str) -> str:
    """Determine the semantic retention class [SCHEMA_STATIC | SESSION_STATE | ONE_OFF]."""
    lower = intent.lower()
    
    # 1. SCHEMA_STATIC: System-level prompts and tool definitions
    if any(kw in lower for kw in _SCHEMA_INTENTS):
        return "SCHEMA_STATIC"
        
    # 2. SESSION_STATE: Multi-turn mission logic
    if any(kw in lower for kw in _MISSION_INTENTS):
        return "SESSION_STATE"
        
    # 3. ONE_OFF: Low-value ephemeral chat
    return "ONE_OFF"


def estimate_velocity(intent: str) -> float:
    """Estimate urgency score [0.0-1.0] from intent keywords."""
    lower = intent.lower()
    if any(kw in lower for kw in _URGENT):
        return 0.9
    return 0.5


def estimate_privacy(intent: str) -> float:
    """Estimate privacy score [0.0-1.0] from intent keywords."""
    lower = intent.lower()
    if any(kw in lower for kw in PRIVACY_KEYWORDS):
        return 0.95
    return 0.0


# ---------------------------------------------------------------------------
# Dispatch Result
# ---------------------------------------------------------------------------

@dataclass
class DispatchResult:
    """Result of intercepting and routing a CLI command."""
    route: RouteDecision
    engine_cmd: str
    model: str
    backend_url: str
    retention_class: str = "ONE_OFF"
    affinity_key: str = ""
    force_plan_mode: bool = False
    intercepted: bool = True


# ---------------------------------------------------------------------------
# CLI Intercept
# ---------------------------------------------------------------------------

class CLIIntercept:
    """Intercept layer between camelot-cli and the Foundry Council engines."""

    def __init__(self):
        self.router = SoulRouter()
        self._omniroute = self._load_omniroute()

    def _load_omniroute(self) -> dict:
        """Load omniroute.json for engine execution paths."""
        if OMNIROUTE_CONFIG.exists():
            return json.loads(OMNIROUTE_CONFIG.read_text(encoding="utf-8"))
        return {}

    def intercept(self, intent: str) -> DispatchResult:
        """Intercept a CLI command and route through the Soul Equation.

        Args:
            intent: Raw command/prompt string from camelot-cli.

        Returns:
            DispatchResult with the selected engine, model, and backend URL.
        """
        # Score the intent
        velocity = estimate_velocity(intent)
        magnitude = estimate_complexity(intent)
        privacy = estimate_privacy(intent)
        linear_need = estimate_linear_scaling_need(intent)
        retention = estimate_retention_class(intent)
        affinity = generate_affinity_key(intent)

        # Route through MFOE matrix
        decision = self.router.route(
            intent,
            velocity=velocity,
            magnitude=magnitude,
            privacy=privacy,
            linear_need=linear_need,
        )

        # Map decision to engine execution details
        engine_cmd, model, backend_url = self._resolve_engine(decision)

        # Check if complexity spike forces plan mode
        force_plan = magnitude >= 0.8

        return DispatchResult(
            route=decision,
            engine_cmd=engine_cmd,
            model=model,
            backend_url=backend_url,
            retention_class=retention,
            affinity_key=affinity,
            force_plan_mode=force_plan,
        )

    def _resolve_engine(self, decision: RouteDecision) -> tuple[str, str, str]:
        """Resolve a RouteDecision to concrete engine CLI command, model, and URL."""
        engines = self._omniroute.get("engines", {})
        upstream = self._omniroute.get("upstream", {})

        _knight = decision.knight_id
        engine_name = decision.engine

        # Agentic OpenAI-compatible engines (Agents-A1, etc.).
        # Agents-A1 is a 35B MoE agentic LLM served locally via vLLM or
        # SGLang; it speaks the OpenAI wire format over HTTP (not Ollama's
        # API). Distinguished from the open_coder/local_qwen/ouroboros_ssm
        # cluster by its agentic-first design (tool use, planning,
        # multi-step). Resolve order:
        #   1. AGENTS_A1_BASE_URL env var (operators set this when the
        #      inference server is exposed via a public tunnel because
        #      Vercel Edge cannot reach localhost).
        #   2. omniroute.json agents_a1.execution_path.
        #   3. http://127.0.0.1:8000/v1 (local vLLM default).
        if engine_name == "agents_a1":
            engine_cfg = engines.get("agents_a1", {})
            model = engine_cfg.get("model", "InternScience/Agents-A1")
            # `.strip()` defends against `AGENTS_A1_BASE_URL="  https://...  "`
            # which would otherwise pass the falsy check but fail the
            # `startswith("http")` check downstream. Empty string (env
            # explicitly cleared) is correctly treated as unset via `or`.
            base = (
                (os.environ.get("AGENTS_A1_BASE_URL") or "").strip()
                or engine_cfg.get("execution_path", "http://127.0.0.1:8000/v1")
            )
            url = base if base.startswith(("http://", "https://")) else f"http://{base}"
            # `openai_compat` signals to the downstream execution layer
            # that this endpoint speaks OpenAI's chat-completions API
            # (so it can be driven with the openai SDK + custom baseURL).
            # NOTE: no executor currently handles this cmd value; the
            # Camelot CLI side is dispatch-only here, and the pwa-cockpit
            # has its own adapter (`AgentsA1Adapter` in TypeScript). A
            # future bifrost/runner must add a handler to actually invoke
            # the endpoint from camelot-cli.
            return ("openai_compat", model, url)

        # Local engines (Open Coder / Sir Ghost / Ouroboros) -> Ollama or local path
        if engine_name in ("open_coder", "local_qwen", "ouroboros_ssm"):
            engine_cfg = engines.get(engine_name, engines.get("open_coder", {}))
            model = engine_cfg.get("model", "qwen3:1.7b" if engine_name != "ouroboros_ssm" else "mamba-3:8b-1.58b")
            host = engine_cfg.get("execution_path", "localhost:11434")
            url = f"http://{host}"
            cmd = "ollama" if engine_name != "ouroboros_ssm" else "ouroboros"
            return (cmd, model, url)

        # Cloud engines -> CLIProxyAPI
        cliproxy = upstream.get("cliproxy", {})
        base_url = cliproxy.get("base_url", "http://127.0.0.1:8080/v1")

        if engine_name == "claude_code":
            return ("claude", "claude-opus-4-6", base_url)
        elif engine_name == "antigravity.cli":
            return ("gemini", "gemini-2.5-pro", base_url)
        elif engine_name == "openai_codex":
            return ("codex", "gpt-5.3-codex", base_url)
        elif engine_name == "open_source":
            return ("ollama", "qwen3:8b", "http://127.0.0.1:11434")

        # Fallback
        return ("claude", "claude-sonnet-4-6", base_url)

    def format_route_log(self, result: DispatchResult) -> str:
        """Format a human-readable route log line."""
        r = result.route
        lines = [
            f"[INTERCEPT] {r.knight_id} via {result.engine_cmd} [Retention: {result.retention_class}]",
            f"  Model: {result.model} @ {result.backend_url}",
            f"  Score: S_omega={r.score:.4f} (W={r.weight})",
            f"  Tensor: V={r.tensor.velocity} M={r.tensor.magnitude} P={r.tensor.privacy}",
            f"  Reason: {r.reason}",
        ]
        if result.force_plan_mode:
            lines.append("  [GATE] COMPLEXITY_SPIKE: Plan Mode enforced before execution")
        if r.privacy_override:
            lines.append("  [SHIELD] PRIVACY_OVERRIDE: Routed to air-gapped local engine")
        return "\n".join(lines)


async def _run_cloudbrain_action(args: argparse.Namespace) -> dict[str, Any]:
    cp = ControlPlane()
    if args.cloudbrain_command == "status":
        task = TaskPayload(intent="cloudbrain status", constraints=[])
        return (await cp.process_task(task)).model_dump()
    if args.cloudbrain_command == "sync":
        task = TaskPayload(
            intent="cloud brain sync",
            parameters={
                "notebook_id": args.notebook_id,
                "note_title": args.note_title,
                "extra_summary": args.summary,
            },
            constraints=[],
        )
        return (await cp.process_task(task)).model_dump()
    if args.cloudbrain_command == "memory":
        task = TaskPayload(
            intent="memory recall",
            parameters={"agent_id": args.agent_id},
            constraints=[f"privacy={args.privacy}"],
        )
        return (await cp.process_task(task)).model_dump()
    if args.cloudbrain_command == "research":
        task = TaskPayload(
            intent="research investigate objective",
            parameters={
                "objective": args.objective,
                "agent_id": args.agent_id,
                "constraints": list(args.constraint or []),
            },
            constraints=[f"privacy={args.privacy}", *(args.constraint or [])],
        )
        return (await cp.process_task(task)).model_dump()
    raise ValueError(f"Unsupported cloudbrain command: {args.cloudbrain_command}")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Camelot canonical CLI intercept")
    sub = parser.add_subparsers(dest="command")

    route_parser = sub.add_parser("route", help="Route an intent through the Soul Router")
    route_parser.add_argument("intent", nargs="+")

    cloudbrain = sub.add_parser("cloudbrain", help="Invoke cloudbrain and research actions")
    cloudbrain_sub = cloudbrain.add_subparsers(dest="cloudbrain_command", required=True)

    cloudbrain_sub.add_parser("status", help="Show cloudbrain status")
    sync = cloudbrain_sub.add_parser("sync", help="Sync local Camelot state into the canonical Cloud Brain notebook")
    sync.add_argument("--notebook-id", default="")
    sync.add_argument("--note-title", default="")
    sync.add_argument("--summary", default="")

    memory = cloudbrain_sub.add_parser("memory", help="Recall cloudbrain memory")
    memory.add_argument("--agent-id", default="merlin")
    memory.add_argument("--privacy", type=float, default=0.0)

    research = cloudbrain_sub.add_parser("research", help="Invoke the research agency")
    research.add_argument("objective")
    research.add_argument("--agent-id", default="lady_apis")
    research.add_argument("--privacy", type=float, default=0.0)
    research.add_argument("--constraint", action="append")

    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.command == "route":
        intercept = CLIIntercept()
        result = intercept.intercept(" ".join(args.intent))
        print(intercept.format_route_log(result))
        return 0

    if args.command == "cloudbrain":
        print(json.dumps(asyncio.run(_run_cloudbrain_action(args)), indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
