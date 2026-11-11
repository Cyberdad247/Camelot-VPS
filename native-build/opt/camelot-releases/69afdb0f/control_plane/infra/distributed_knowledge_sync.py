# SPDX-License-Identifier: MIT

"""
Distributed Knowledge Synchronization — Multi-Instance L1→L1.5→L2

Phase G: Cross-instance memory hierarchy synchronization

Architecture:
- L1 (Redis): Local cache + cluster replication
- L1.5 (Qdrant): Vector consolidation across instances
- L2 (CloudBrain): Single source of truth

Sync Protocol:
1. Write to local L1
2. Publish event → peers
3. Peers replicate to their L1
4. When all ack → promote to L1.5
5. Qdrant consolidates vectors
6. CloudBrain persists final state
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class SyncPhase(str, Enum):
    """Synchronization phases"""
    LOCAL_WRITE = "local_write"
    PEER_REPLICATION = "peer_replication"
    L1_5_CONSOLIDATION = "l1_5_consolidation"
    L2_PERSISTENCE = "l2_persistence"
    COMPLETE = "complete"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies"""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"


@dataclass
class SyncEvent:
    """Synchronization event"""
    event_id: str
    key: str
    value: str
    source_node: str
    timestamp: float
    phase: SyncPhase
    replicated_to: Set[str] = field(default_factory=set)
    vector_id: Optional[str] = None
    conflict: bool = False


@dataclass
class ReplicationAck:
    """Replication acknowledgment from peer"""
    node_id: str
    event_id: str
    timestamp: float
    success: bool
    error: Optional[str] = None


class DistributedKnowledgeSync:
    """Distributed knowledge hierarchy synchronization"""

    def __init__(self, node_id: str, peers: List[str]):
        """
        Initialize distributed knowledge sync

        Args:
            node_id: This node's identifier
            peers: List of peer node IDs
        """
        self.node_id = node_id
        self.peers = peers
        self.all_nodes = [node_id] + peers

        # Sync state
        self.events: Dict[str, SyncEvent] = {}
        self.pending_replication: Dict[str, SyncEvent] = {}
        self.acks: Dict[str, List[ReplicationAck]] = {}

        # Conflict resolution
        self.conflict_strategy = ConflictResolution.LAST_WRITE_WINS

        # Statistics
        self.sync_count = 0
        self.conflict_count = 0

        print(f"🔄 KnowledgeSync: Node {node_id} initialized with {len(peers)} peers")

    async def write_to_l1(self, key: str, value: str) -> str:
        """
        Write data to local L1 (Redis)

        Args:
            key: Data key
            value: Data value

        Returns:
            Event ID
        """
        event_id = self._generate_event_id(key, value)
        timestamp = time.time()

        # Create sync event
        event = SyncEvent(
            event_id=event_id,
            key=key,
            value=value,
            source_node=self.node_id,
            timestamp=timestamp,
            phase=SyncPhase.LOCAL_WRITE,
        )

        self.events[event_id] = event
        self.pending_replication[event_id] = event

        print(f"✏️  L1 Write: {key} = {value[:20]}... (event: {event_id[:8]}...)")

        # Initiate replication
        await self._replicate_to_peers(event)

        return event_id

    async def _replicate_to_peers(self, event: SyncEvent):
        """
        Phase 1: Replicate to all peers (L1 cluster)

        Args:
            event: Event to replicate
        """
        event.phase = SyncPhase.PEER_REPLICATION

        replication_tasks = []
        for peer in self.peers:
            task = self._send_replication(peer, event)
            replication_tasks.append(task)

        # Wait for replication (with timeout)
        results = await asyncio.gather(*replication_tasks, return_exceptions=True)

        # Count successful replications
        success_count = sum(1 for r in results if isinstance(r, ReplicationAck) and r.success)
        event.replicated_to = {self.node_id}  # Our own node

        print(f"📤 Replication: {event.event_id[:8]}... replicated to {success_count}/{len(self.peers)} peers")

        # If majority replicated, promote to L1.5
        if success_count >= len(self.peers) // 2:
            await self._consolidate_to_l1_5(event)
        else:
            # Store pending for retry
            self.pending_replication[event.event_id] = event

    async def _send_replication(self, peer: str, event: SyncEvent) -> ReplicationAck:
        """
        Send replication to peer

        Args:
            peer: Peer node ID
            event: Event to replicate

        Returns:
            Replication acknowledgment
        """
        try:
            # Simulate network latency
            await asyncio.sleep(0.01)

            # Create acknowledgment
            ack = ReplicationAck(
                node_id=peer,
                event_id=event.event_id,
                timestamp=time.time(),
                success=True,
            )

            # Track acknowledgment
            if event.event_id not in self.acks:
                self.acks[event.event_id] = []
            self.acks[event.event_id].append(ack)

            event.replicated_to.add(peer)

            return ack

        except Exception as e:
            return ReplicationAck(
                node_id=peer,
                event_id=event.event_id,
                timestamp=time.time(),
                success=False,
                error=str(e),
            )

    async def _consolidate_to_l1_5(self, event: SyncEvent):
        """
        Phase 2: Consolidate to L1.5 (Qdrant vector store)

        Args:
            event: Event to consolidate
        """
        event.phase = SyncPhase.L1_5_CONSOLIDATION

        # Create vector from event data
        vector_id = await self._create_vector(event)
        event.vector_id = vector_id

        print(f"🧠 L1.5 Consolidation: {event.event_id[:8]}... → vector {vector_id[:8]}...")

        # Promote to L2 persistence
        await self._persist_to_l2(event)

    async def _create_vector(self, event: SyncEvent) -> str:
        """
        Create vector embedding for event

        Args:
            event: Event to vectorize

        Returns:
            Vector ID
        """
        # Simplified: use hash of data as vector ID
        import hashlib
        data_str = f"{event.key}:{event.value}"
        vector_id = hashlib.sha256(data_str.encode()).hexdigest()[:12]

        # In production, would create 384D embedding
        # vector = await embedding_service.embed(data_str)

        return vector_id

    async def _persist_to_l2(self, event: SyncEvent):
        """
        Phase 3: Persist to L2 (CloudBrain)

        Args:
            event: Event to persist
        """
        event.phase = SyncPhase.L2_PERSISTENCE

        # Simulate CloudBrain persistence
        # In production, would upload to CloudBrain via API
        await asyncio.sleep(0.05)

        event.phase = SyncPhase.COMPLETE
        self.sync_count += 1

        print(f"☁️  L2 Persisted: {event.event_id[:8]}... (sync complete)")

        # Clean up pending
        if event.event_id in self.pending_replication:
            del self.pending_replication[event.event_id]

    async def handle_replication_from_peer(self, event: SyncEvent, source_peer: str) -> bool:
        """
        Handle incoming replication from peer

        Args:
            event: Event from peer
            source_peer: Peer node ID

        Returns:
            True if handled successfully
        """
        # Check for conflicts
        if event.key in self.events:
            existing = self.events[event.key]

            if existing.timestamp > event.timestamp:
                # Local is newer
                if self.conflict_strategy == ConflictResolution.LAST_WRITE_WINS:
                    # Keep local version
                    return True
            else:
                # Remote is newer
                self.conflict_count += 1
                print(f"⚠️  Conflict: {event.key} (remote is newer)")

        # Store replicated event
        self.events[event.key] = event
        event.replicated_to.add(source_peer)

        print(f"📥 Replication received: {event.key} from {source_peer}")

        return True

    async def get_sync_status(self) -> Dict:
        """Get synchronization status"""
        completed = sum(1 for e in self.events.values() if e.phase == SyncPhase.COMPLETE)
        pending = len(self.pending_replication)

        return {
            'node_id': self.node_id,
            'total_events': len(self.events),
            'completed': completed,
            'pending': pending,
            'sync_count': self.sync_count,
            'conflict_count': self.conflict_count,
            'peers': len(self.peers),
        }

    async def wait_for_sync(self, event_id: str, timeout: float = 5.0) -> bool:
        """
        Wait for event to complete synchronization

        Args:
            event_id: Event to wait for
            timeout: Maximum wait time

        Returns:
            True if sync completed, False if timeout
        """
        start = time.time()

        while time.time() - start < timeout:
            if event_id in self.events:
                event = self.events[event_id]
                if event.phase == SyncPhase.COMPLETE:
                    return True

            await asyncio.sleep(0.1)

        return False

    def _generate_event_id(self, key: str, value: str) -> str:
        """Generate unique event ID"""
        import hashlib
        data = f"{self.node_id}:{key}:{value}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


# ── Module-level singleton ────────────────────────────────────────────────

_sync: Optional[DistributedKnowledgeSync] = None


def get_distributed_knowledge_sync(node_id: str = "node_default", peers: List[str] = None) -> DistributedKnowledgeSync:
    """Get or create distributed knowledge sync instance"""
    global _sync
    if _sync is None:
        peers = peers or []
        _sync = DistributedKnowledgeSync(node_id, peers)
    return _sync


async def sync_demo():
    """Demo: Multi-node knowledge synchronization"""
    # Simulate 3-node cluster
    sync_node1 = DistributedKnowledgeSync("node_1", ["node_2", "node_3"])
    sync_node2 = DistributedKnowledgeSync("node_2", ["node_1", "node_3"])
    sync_node3 = DistributedKnowledgeSync("node_3", ["node_1", "node_2"])

    # Node 1 writes data
    event_id = await sync_node1.write_to_l1("user_profile", '{"name": "Alice", "role": "admin"}')

    # Wait for sync to complete
    success = await sync_node1.wait_for_sync(event_id, timeout=5.0)

    print(f"\n✅ Sync Result: {'Success' if success else 'Timeout'}")
    print(f"Node 1 Status: {await sync_node1.get_sync_status()}")
    print(f"Node 2 Status: {await sync_node2.get_sync_status()}")
    print(f"Node 3 Status: {await sync_node3.get_sync_status()}")


if __name__ == "__main__":
    asyncio.run(sync_demo())
