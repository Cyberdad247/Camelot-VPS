# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — Cloudbrain MCP Server
r"""
Cloudbrain Model Context Protocol (MCP) Server.
Exposes Camelot OS Worldtree Cloudbrain nodes (NotebookLM) to Antigravity CLI,
Claude Code, and any MCP-compliant agent harness.
"""

import sys
from pathlib import Path

CAMELOT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(CAMELOT_ROOT))
sys.path.insert(0, str(CAMELOT_ROOT / "01_KERNEL"))
sys.path.insert(0, str(CAMELOT_ROOT / "vfs"))

from mcp.server.fastmcp import FastMCP
from memory.cloudbrain_connector import (
    CloudBrainConnector,
    KNIGHT_NOTEBOOKS,
    list_all_notebooks,
    route_by_domain,
)
from vfs.notebooklm_client import (
    NOTEBOOKLM_AVAILABLE,
    query_notebook_async,
    push_note_async,
    push_source_async,
)
from control_plane.memcastle import MemCastle
from control_plane.graphify import extract_triplets
from memory.graphiti_engine import KnightGraphitiEngine

mcp_server = FastMCP("camelot-cloudbrain")


@mcp_server.tool()
def list_cloudbrains() -> list[dict]:
    """List all registered Camelot Worldtree Cloudbrain nodes and their active NotebookLM UUUDs."""
    return list_all_notebooks()


@mcp_server.tool()
def route_cloudbrain_by_domain(keywords: list[str]) -> list[str]:
    """Find the best Cloudbrain nodes for a task using keyword routing."""
    return route_by_domain(keywords)


@mcp_server.tool()
async def query_cloudbrain(knight_id: str, question: str) -> str:
    """Query a specific Knight Cloudbrain node (eg SIR_BORIS, HERMES_PRIME, BIO_KINETIC_SWARM, ANYA_OMEGA)."""
    kid = knight_id.upper()
    if NOTEBOOKLM_AVAILABLE:
        try:
            answer = await query_notebook_async(kid, question)
            if answer:
                return answer
        except Exception:
            pass
    connector = CloudBrainConnector(knight_id=kid)
    answer = connector.query_notebook(question)
    if answer:
        return answer
    return f"No response or notebook not queryable for node: {kid}"


@mcp_server.tool()
async def push_cloudbrain_note(knight_id: str, title: str, content: str) -> str:
    """Push an artifact or operational note to a Knight Cloudbrain node and local Open-Notebook tissue."""
    kid = knight_id.upper()
    connector = CloudBrainConnector(knight_id=kid)
    connector._sync_open_notebook_local("note", title, content)
    ok = False
    if NOTEBOOKLM_AVAILABLE:
        try:
            ok = await push_note_async(kid, title, content)
        except Exception:
            pass
    if not ok:
        ok = connector.push_to_notebook(artifact_type="note", content=content, title=title)
    if ok:
        return f"Successfully pushed note '{title}' to {kid} Cloudbrain."
    return f"Local tissue mirrored, but remote NotebookLM push skipped/failed for {kid}."


@mcp_server.tool()
async def push_cloudbrain_source(knight_id: str, title: str, content: str) -> str:
    """Push a full text source or code artifact to a Knight Cloudbrain notebook."""
    kid = knight_id.upper()
    connector = CloudBrainConnector(knight_id=kid)
    connector._sync_open_notebook_local("source", title, content)
    ok = False
    if NOTEBOOKLM_AVAILABLE:
        try:
            ok = await push_source_async(kid, title, content)
        except Exception:
            pass
    if not ok:
        ok = connector.push_to_notebook(artifact_type="source", content=content, title=title)
    if ok:
        return f"Successfully pushed source '{title}' to {kid} Cloudbrain."
    return f"Local tissue mirrored, but remote NotebookLM source upload skipped/failed for {kid}."


@mcp_server.tool()
def memcastle_store(text: str, source: str = "mcp", knight: str = "SIR_MNEMO") -> str:
    """Store text and semantic embedding into Tier-2 MemCastle (sqlite-vec KNN)."""
    mc = MemCastle()
    try:
        row_id = mc.store(text=text, source=source, knight=knight)
        return f"Stored into MemCastle (Row ID: {row_id}, Knight: {knight})"
    finally:
        mc.close()


@mcp_server.tool()
def memcastle_search(query: str, k: int = 5) -> list[dict]:
    """Search Tier-2 MemCastle vector database using sqlite-vec KNN search."""
    mc = MemCastle()
    try:
        results = mc.search(query=query, k=k)
        return results
    finally:
        mc.close()


@mcp_server.tool()
def graphify_extract(text: str) -> list[dict]:
    """Extract semantic (subject, predicate, object) triplets from text using Graphify."""
    triplets = extract_triplets(text)
    return [{"head": t.head, "relation": t.relation, "tail": t.tail} for t in triplets]


@mcp_server.tool()
def assimilation_status() -> dict:
    """Return status of assimilated intelligence, memory layers, and CloudBrain integrations."""
    return {
        "tier_1_context": "Ouroboros WAL / In-Memory Session",
        "tier_2_vector": "MemCastle sqlite-vec + Graphify NLP Triplet Extractor",
        "tier_3_cloudbrain": "WorldTree VFS (open_viking://) + NotebookLM CloudBrain",
        "assimilated_components": [
            "Understand-Anything (Codebase Knowledge Graph & AST Flow)",
            "book-to-skill (Procedural Technical Document to Agent Skill)",
            "codebase-memory-mcp (Photographic AST & Dependency Graph)",
            "notebooklm-py (Async NotebookLM Client Substrate)",
            "anything-to-notebooklm (Multi-Source Document & Media Preprocessor)",
            "notebooklm-mcp (FastMCP CloudBrain Citation & Query Server)"
        ],
        "qdrant_rest_cluster": "https://2b135578-55c5-43d0-b82a-f5061f4ff6ee.us-east4-0.gcp.cloud.qdrant.io",
        "status": "ASSIMILATED_ACTIVE",
    }


@mcp_server.tool()
def graphiti_query(knight_id: str, entity_name: str, limit: int = 25) -> dict:
    """Query a Knight's Graphiti temporal knowledge graph for targeted entity subgraphs, reducing token consumption."""
    engine = KnightGraphitiEngine(knight_id=knight_id)
    return engine.query_subgraph(entity_name=entity_name, limit=limit)


@mcp_server.tool()
def graphiti_add_fact(
    knight_id: str,
    subject: str,
    predicate: str,
    object_: str,
    source: str = "mcp",
) -> str:
    """Add a temporal fact triplet to a Knight's Graphiti knowledge graph."""
    engine = KnightGraphitiEngine(knight_id=knight_id)
    fact_id = engine.add_fact(subject=subject, predicate=predicate, object_=object_, source=source)
    return f"Fact {fact_id} added to {knight_id.upper()} Graphiti knowledge graph."


@mcp_server.tool()
def graphiti_stats(knight_id: str) -> dict:
    """Get entity, fact count, and database size for a Knight's Graphiti knowledge graph."""
    engine = KnightGraphitiEngine(knight_id=knight_id)
    return engine.stats()


@mcp_server.tool()
def cloudbrain_status() -> dict:
    """Check the health and integration status of NotebookLM and Worldtree Cloudbrain."""
    return {
        "notebooklm_library_available": NOTEBOOKLM_AVAILABLE,
        "registered_nodes_count": len(KNIGHT_NOTEBOOKS),
        "active_uuid_nodes_count": len(list_all_notebooks()),
        "auth_state_exists": Path(r"C:\Users\vizio\.notebooklm\storage_state.json").exists(),
        "graphiti_engine_partitioned_knights": len(KNIGHT_NOTEBOOKS),
    }


@mcp_server.tool()
def excalibur_mobile_scrcpy_command(
    device_ip: str = "100.106.246.126:5555",
    bitrate_mbps: int = 8,
    audio_opus: bool = True,
) -> str:
    """Generate the native scrcpy low-latency command for Excalibur Command Center (S26 Ultra)."""
    audio_flag = "--audio-codec=opus" if audio_opus else "--no-audio"
    return f"scrcpy -s {device_ip} --video-bit-rate {bitrate_mbps}M --max-fps 60 {audio_flag}"


@mcp_server.tool()
def excalibur_adb_tap(x: int, y: int, device_ip: str = "100.106.246.126:5555") -> str:
    """Inject a tap touch action into the Excalibur mobile sentinel via ADB over Tailscale."""
    import subprocess
    cmd = ["adb", "-s", device_ip, "shell", "input", "tap", str(x), str(y)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return f"Tap at ({x}, {y}) dispatched to {device_ip}. Exit: {res.returncode}"
    except Exception as e:
        return f"Tap failed: {e}"


@mcp_server.tool()
def get_notebook_manifest() -> dict:
    """Get the master NotebookLM WorldTree Manifest summary across all 294 nodes and 7 categories."""
    try:
        from merlin.context.merlin_infinite_context import merlin_context
        return {
            "version": merlin_context.manifest.get("version", "2.0.0"),
            "total_notebooks": merlin_context.manifest.get("total_notebooks", 294),
            "worldtree_root_uuid": merlin_context.manifest.get("worldtree_root_uuid"),
            "categories": merlin_context.manifest.get("categories", []),
            "active_sovereign_knights": len(KNIGHT_NOTEBOOKS),
        }
    except Exception as e:
        return {"error": str(e), "total_knights": len(KNIGHT_NOTEBOOKS)}


@mcp_server.tool()
def route_by_manifest(intent_or_query: str) -> dict:
    """Route an intent or query using Merlin Infinite Context Engine across the 294 NotebookLM Manifest."""
    try:
        from merlin.context.merlin_infinite_context import merlin_context
        category, knight_id, notebook_uuid = merlin_context.categorize_intent(intent_or_query)
        meta = merlin_context.manifest.get("notebooks", {}).get(notebook_uuid, {})
        return {
            "intent": intent_or_query,
            "recommended_category": category,
            "recommended_knight": knight_id,
            "target_notebook_uuid": notebook_uuid,
            "notebook_title": meta.get("title", "Unknown"),
            "anchor_tether": meta.get("anchor_tether", "a0a4bfb9-e847-4c38-be39-7aee398f0795"),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp_server.tool()
def crystallize_infinite_context(
    raw_text: str,
    title: str,
    category: str = "",
    target_knight: str = "",
) -> dict:
    """Crystallize arbitrary text using Merlin Infinite Context Engine with living system instructions."""
    try:
        from merlin.context.merlin_infinite_context import merlin_context
        cat = category if category else None
        kid = target_knight.upper() if target_knight else None
        crystal = merlin_context.crystallize(
            raw_text=raw_text,
            title=title,
            category_override=cat,
            target_knight=kid,
        )
        return {
            "crystal_id": crystal.crystal_id,
            "category": crystal.category,
            "target_knight": crystal.target_knight,
            "target_notebook_uuid": crystal.target_notebook_uuid,
            "l0_flash_summary": crystal.l0_flash_summary,
            "l1_semantic_outline": crystal.l1_semantic_outline,
            "l2_triplets_count": len(crystal.l2_knowledge_triplets),
            "full_markdown_length": len(crystal.full_markdown_source),
            "created_at": crystal.created_at,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp_server.run()

