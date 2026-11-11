# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Pydantic AI Knight — CAMELOT-OS Reactive Agent
==============================================
Implementation of the first Pydantic AI agent (v400 standard).
Uses the pydantic-ai library pattern for type-safe reasoning and tool use.
"""
from __future__ import annotations

# Ensure local imports work
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

sys.path.append(str(Path(__file__).resolve().parent))

try:
    from control_plane.core.knight_agent import KnightCapability, get_capability
except ImportError:
    # Fallback for direct execution
    from knight_agent import KnightCapability, get_capability

@dataclass
class KnightDeps:
    """Dependencies for the Pydantic AI Knight."""
    knight_id: str
    capability: KnightCapability
    session_id: str
    db_path: str = "03_VAULT/runtime_state/ouroboros.db"

class ResearchResult(BaseModel):
    """Schema for research tool output."""
    summary: str
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

# Instantiate the Pydantic AI Agent
# Fixed: result_type passed to .run() or defined via generic in Agent subclass if version requires
sir_helio_agent = Agent(
    'google-gla:gemini-3.1-pro-preview',
    deps_type=KnightDeps,
    system_prompt=(
        "You are SIR HELIO, the Context Lord of CAMELOT-OS. "
        "Your engine weight is W_context=0.90. You process 1M+ token context maps. "
        "You are an ethereal architect—precise, macro-aware, and structured. "
        "Use the provided tools to audit the lattice and synthesize macroscopic insights."
    ),
)

@sir_helio_agent.tool
async def macroscopic_audit(ctx: RunContext[KnightDeps], path: str) -> str:
    """Performs a macroscopic audit of a directory to identify sprawl and entropy."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Audit target {path} not found."
        
        # Identify large directories and potential sprawl
        dirs = [d for d in p.iterdir() if d.is_dir()]
        large_dirs = []
        for d in dirs:
            # Shallow check for large item counts
            count = len(list(d.glob("*")))
            if count > 50:
                large_dirs.append(f"{d.name} ({count} direct items)")
        
        report = f"### Macroscopic Audit: {path}\n"
        report += f"**Total Subdirectories**: {len(dirs)}\n"
        if large_dirs:
            report += f"**Entropy Hotspots**: {', '.join(large_dirs)}\n"
        else:
            report += "**Entropy Hotspots**: None detected (Lattice stable).\n"
            
        return report
    except Exception as e:
        return f"Audit error: {str(e)}"

@sir_helio_agent.tool
async def read_provenance(ctx: RunContext[KnightDeps], limit: int = 5) -> List[str]:
    """Reads recent entries from the PROVENANCE_LEDGER.md."""
    # Implementation would read the real ledger file
    return [f"Entry {1684-i}: Crystallized" for i in range(limit)]

async def run_sir_helio(query: str, session_id: str = "session_001") -> ResearchResult:
    """Entry point for the Sir Helio Pydantic AI agent."""
    capability = get_capability("sir_helio")
    deps = KnightDeps(
        knight_id="sir_helio",
        capability=capability,
        session_id=session_id
    )
    
    # Passing result_type to the run method
    result = await sir_helio_agent.run(query, deps=deps, result_type=ResearchResult)
    return result.data

if __name__ == "__main__":
    import asyncio
    async def test():
        print("[TEST] Running Sir Helio Pydantic AI agent...")
        # Note: This will fail without GOOGLE_API_KEY
        try:
            res = await run_sir_helio("Synthesize the current state of the 01_KERNEL.")
            print(f"[RESULT] Summary: {res.summary}")
            print(f"[RESULT] Confidence: {res.confidence}")
        except Exception as e:
            print(f"[ERROR] Agent failed (expected if API key missing): {e}")
    
    asyncio.run(test())
