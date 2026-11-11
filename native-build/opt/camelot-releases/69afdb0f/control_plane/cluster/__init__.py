# SPDX-License-Identifier: MIT

"""
CAMELOT-OS cluster daemon layer.

Wraps the existing in-process service algorithms (distributed_ledger_consensus,
distributed_knowledge_sync, distributed_agent_registry, metrics_collector) in
real, long-running HTTP daemons so a genuine multi-node cluster can be formed —
locally over loopback for validation, or across real nodes in production.

The original modules are subclassed, never modified: their demos still run.
"""
