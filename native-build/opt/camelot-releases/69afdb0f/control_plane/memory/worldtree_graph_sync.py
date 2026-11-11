# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
"""
WorldTree Neo4j Multi-Tissue Memory Sync (`camelot-worldtree-sync`)
==================================================================
Synchronizes local SQLite WAL2 bi-temporal memory facts and Open-Notebook
tissues into the master VPS Neo4j GraphMemory backplane under Master Root UUID
`a0a4bfb9-e847-4c38-be39-7aee398f0795`.

Core Mandate: "Memories are topological nodes; the WorldTree links the 38 Knights to one unified lattice."
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("camelot.worldtree_sync")

WORLDTREE_ROOT_UUID = "a0a4bfb9-e847-4c38-be39-7aee398f0795"


@dataclass
class CypherFactStatement:
    statement_id: str
    cypher_query: str
    parameters: Dict[str, Any]
    worldtree_anchor: str
    status: str  # "STAGED" | "COMMITTED" | "ROLLED_BACK"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GraphSyncSummary:
    batch_id: str
    root_uuid: str
    total_facts_staged: int
    total_facts_committed: int
    knights_tethered: int
    sync_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorldTreeGraphSyncEngine:
    """Bi-Temporal Neo4j Cypher Fact Sync & Knight Graph Memory Engine."""

    def __init__(self, sync_dir: Optional[Path] = None):
        self.sync_dir = sync_dir or Path("03_VAULT/runtime_state/worldtree_sync")
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self.staged_statements: List[CypherFactStatement] = []

    def stage_bitemporal_fact_cypher(
        self,
        tenant_id: str,
        namespace: str,
        subject: str,
        predicate: str,
        object_value: str,
        valid_from: str,
        recorded_from: str,
        confidence: float = 1.0
    ) -> CypherFactStatement:
        """Translates a bi-temporal memory fact into an idempotent Neo4j Cypher query."""
        stmt_id = f"cypher_{uuid.uuid4().hex[:10]}"
        
        cypher = (
            "MERGE (root:WorldTreeRoot {uuid: $root_uuid}) "
            "MERGE (sub:Entity {name: $subject, tenant: $tenant_id}) "
            "MERGE (sub)-[:TETHERED_TO]->(root) "
            "CREATE (f:BiTemporalFact { "
            "  fact_id: $stmt_id, "
            "  namespace: $namespace, "
            "  predicate: $predicate, "
            "  object_value: $object_value, "
            "  confidence: $confidence, "
            "  valid_from: datetime($valid_from), "
            "  recorded_from: datetime($recorded_from) "
            "}) "
            "CREATE (sub)-[:ASSERTS]->(f)"
        )

        params = {
            "root_uuid": WORLDTREE_ROOT_UUID,
            "tenant_id": tenant_id,
            "subject": subject,
            "stmt_id": stmt_id,
            "namespace": namespace,
            "predicate": predicate,
            "object_value": object_value,
            "confidence": confidence,
            "valid_from": valid_from,
            "recorded_from": recorded_from
        }

        stmt = CypherFactStatement(
            statement_id=stmt_id,
            cypher_query=cypher,
            parameters=params,
            worldtree_anchor=WORLDTREE_ROOT_UUID,
            status="STAGED"
        )

        self.staged_statements.append(stmt)
        LOG.info(f"[WORLDTREE_SYNC] Staged Cypher fact {stmt_id}: ({subject}) -[{predicate}]-> ({object_value})")
        return stmt

    def commit_sync_batch(self, knights_count: int = 38) -> GraphSyncSummary:
        """Simulates atomic commit of staged Cypher statements to VPS Neo4j."""
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        staged_count = len(self.staged_statements)

        for stmt in self.staged_statements:
            stmt.status = "COMMITTED"

        summary = GraphSyncSummary(
            batch_id=batch_id,
            root_uuid=WORLDTREE_ROOT_UUID,
            total_facts_staged=staged_count,
            total_facts_committed=staged_count,
            knights_tethered=knights_count
        )

        summary_file = self.sync_dir / f"{batch_id}_summary.json"
        summary_file.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
        
        self.staged_statements.clear()
        LOG.info(f"[WORLDTREE_SYNC] Committed batch {batch_id} with {staged_count} facts across {knights_count} Knights.")
        return summary
