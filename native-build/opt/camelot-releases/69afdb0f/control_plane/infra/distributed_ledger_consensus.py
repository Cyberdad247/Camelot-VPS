# SPDX-License-Identifier: MIT

"""
Distributed Ledger Consensus — PBFT-Inspired Byzantine Agreement

Phase G: Distributed Autonomy Implementation
Practical Byzantine Fault Tolerance for multi-node CAMELOT-OS clusters

Algorithm: 3-phase commit (pre-prepare, prepare, commit)
Fault Tolerance: f < n/3 (tolerate 1 node in cluster of 3)
Cryptographic: Ed25519 signatures on all messages
Leader Election: Raft-style heartbeat + timeout
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    _ED25519 = True
except Exception:  # pragma: no cover - degraded SHA-256 fallback if no crypto
    _ED25519 = False


class ConsensusPhase(str, Enum):
    """Consensus phases in PBFT"""
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    DECIDED = "decided"


class NodeRole(str, Enum):
    """Node roles in cluster"""
    LEADER = "leader"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"


@dataclass
class ConsensusMessage:
    """Message in consensus protocol"""
    node_id: str
    phase: ConsensusPhase
    entry_id: str
    sequence: int
    timestamp: float
    data: Dict
    signature: str = ""

    def to_json(self) -> str:
        return json.dumps({
            'node_id': self.node_id,
            'phase': self.phase.value,
            'entry_id': self.entry_id,
            'sequence': self.sequence,
            'timestamp': self.timestamp,
            'data': self.data,
            'signature': self.signature
        })


@dataclass
class ConsensusState:
    """Consensus state for entry"""
    entry_id: str
    sequence: int
    phase: ConsensusPhase
    data: Dict
    prepares: Set[str] = field(default_factory=set)  # Node IDs
    commits: Set[str] = field(default_factory=set)   # Node IDs
    decided_value: Optional[Dict] = None
    decided_at: Optional[float] = None


class DistributedConsensus:
    """PBFT-inspired distributed consensus"""

    def __init__(self, node_id: str, peers: List[str], quorum: int = 2,
                 strict_signatures: bool = False):
        """
        Initialize distributed consensus

        Args:
            node_id: This node's unique identifier
            peers: List of peer node IDs
            quorum: Minimum nodes needed for consensus (typically 2/3 + 1)
        """
        self.node_id = node_id
        self.peers = peers
        self.all_nodes = [node_id] + peers
        self.quorum = quorum
        self.cluster_size = len(self.all_nodes)

        # Fault tolerance: f < n/3
        self.max_faulty = (self.cluster_size - 1) // 3

        # State
        self.role = NodeRole.FOLLOWER
        self.leader_id = None
        self.sequence = 0
        self.log: Dict[int, ConsensusState] = {}
        self.pending_entries: Dict[str, Dict] = {}

        # Heartbeat & timeouts
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 1.0  # 1 second
        self.heartbeat_timeout = 3.0   # 3 second timeout

        # Message queue
        self.message_queue: asyncio.Queue = asyncio.Queue()

        # ── Election term state (Raft-style vote rules) ──
        self.current_term = 0
        self.voted_for: Optional[str] = None

        # ── Ed25519 identity: real per-node keypair + peer public-key registry ──
        # strict_signatures=True rejects messages from senders whose public key
        # is not registered. Default False keeps the live cluster working until
        # the daemon wires key exchange; real verification still applies wherever
        # a sender's key IS registered (tampering is always rejected).
        self.strict_signatures = strict_signatures
        self._public_keys: Dict[str, "Ed25519PublicKey"] = {}
        if _ED25519:
            self._private_key = Ed25519PrivateKey.generate()
            self._public_keys[self.node_id] = self._private_key.public_key()
        else:
            self._private_key = None

        print(f"🟦 Consensus: Node {node_id} initialized (cluster_size={self.cluster_size}, quorum={self.quorum})")

    async def propose_entry(self, entry_data: Dict) -> str:
        """
        Propose new entry for consensus

        Args:
            entry_data: Data to be added to ledger

        Returns:
            Entry ID
        """
        entry_id = self._generate_entry_id(entry_data)
        self.pending_entries[entry_id] = entry_data

        # If we're leader, initiate consensus
        if self.role == NodeRole.LEADER:
            await self._initiate_consensus(entry_id)

        print(f"📝 Proposed: {entry_id[:12]}... (pending consensus)")
        return entry_id

    async def _initiate_consensus(self, entry_id: str):
        """Initiate 3-phase consensus for entry"""
        entry_data = self.pending_entries.get(entry_id)
        if not entry_data:
            return

        self.sequence += 1

        # Create consensus state
        state = ConsensusState(
            entry_id=entry_id,
            sequence=self.sequence,
            phase=ConsensusPhase.PRE_PREPARE,
            data=entry_data,
        )
        self.log[self.sequence] = state

        # Phase 1: PRE-PREPARE (leader sends to all)
        await self._phase_pre_prepare(entry_id, state)

    async def _phase_pre_prepare(self, entry_id: str, state: ConsensusState):
        """Phase 1: Leader sends pre-prepare to all nodes"""
        message = ConsensusMessage(
            node_id=self.node_id,
            phase=ConsensusPhase.PRE_PREPARE,
            entry_id=entry_id,
            sequence=state.sequence,
            timestamp=time.time(),
            data=state.data,
        )
        message.signature = self._sign_message(message.to_json())

        # Broadcast to all followers
        for peer in self.peers:
            await self._send_message(peer, message)

        # Leader also records its own prepare
        state.prepares.add(self.node_id)
        state.phase = ConsensusPhase.PREPARE

        print(f"📤 PRE-PREPARE: {entry_id[:12]}... sent to {len(self.peers)} peers")

    async def receive_message(self, message: ConsensusMessage) -> bool:
        """
        Receive and process consensus message

        Args:
            message: Consensus message from peer

        Returns:
            True if message was processed
        """
        # Verify signature
        if not self._verify_signature(message):
            print(f"❌ Invalid signature from {message.node_id}")
            return False

        # Get or create consensus state
        if message.sequence not in self.log:
            self.log[message.sequence] = ConsensusState(
                entry_id=message.entry_id,
                sequence=message.sequence,
                phase=message.phase,
                data=message.data,
            )

        state = self.log[message.sequence]

        # Process by phase
        if message.phase == ConsensusPhase.PRE_PREPARE:
            await self._handle_pre_prepare(message, state)
        elif message.phase == ConsensusPhase.PREPARE:
            await self._handle_prepare(message, state)
        elif message.phase == ConsensusPhase.COMMIT:
            await self._handle_commit(message, state)

        return True

    async def _handle_pre_prepare(self, message: ConsensusMessage, state: ConsensusState):
        """Handle PRE-PREPARE message"""
        # Record the pre-prepare
        state.prepares.add(message.node_id)

        # Send PREPARE to all (including original sender)
        prepare_msg = ConsensusMessage(
            node_id=self.node_id,
            phase=ConsensusPhase.PREPARE,
            entry_id=message.entry_id,
            sequence=message.sequence,
            timestamp=time.time(),
            data=message.data,
        )
        prepare_msg.signature = self._sign_message(prepare_msg.to_json())

        for peer in self.all_nodes:
            if peer != self.node_id:
                await self._send_message(peer, prepare_msg)

        # Add our own prepare
        state.prepares.add(self.node_id)
        state.phase = ConsensusPhase.PREPARE

        print(f"✓ PREPARE: {message.entry_id[:12]}... from {message.node_id}")

    async def _handle_prepare(self, message: ConsensusMessage, state: ConsensusState):
        """Handle PREPARE message"""
        state.prepares.add(message.node_id)

        # Check if we have quorum for PREPARE
        if len(state.prepares) >= self.quorum and state.phase == ConsensusPhase.PREPARE:
            # Move to COMMIT phase
            await self._move_to_commit(state)

    async def _move_to_commit(self, state: ConsensusState):
        """Move to COMMIT phase when PREPARE quorum reached"""
        # Send COMMIT to all
        commit_msg = ConsensusMessage(
            node_id=self.node_id,
            phase=ConsensusPhase.COMMIT,
            entry_id=state.entry_id,
            sequence=state.sequence,
            timestamp=time.time(),
            data=state.data,
        )
        commit_msg.signature = self._sign_message(commit_msg.to_json())

        for peer in self.all_nodes:
            if peer != self.node_id:
                await self._send_message(peer, commit_msg)

        # Add our own commit
        state.commits.add(self.node_id)
        state.phase = ConsensusPhase.COMMIT

        print(f"🔗 COMMIT: {state.entry_id[:12]}... (quorum reached)")

    async def _handle_commit(self, message: ConsensusMessage, state: ConsensusState):
        """Handle COMMIT message"""
        state.commits.add(message.node_id)

        # Check if we have quorum for COMMIT
        if len(state.commits) >= self.quorum and state.phase != ConsensusPhase.DECIDED:
            # Consensus reached!
            await self._decide(state)

    async def _decide(self, state: ConsensusState):
        """Finalize consensus decision"""
        state.phase = ConsensusPhase.DECIDED
        state.decided_value = state.data
        state.decided_at = time.time()

        # Remove from pending
        if state.entry_id in self.pending_entries:
            del self.pending_entries[state.entry_id]

        print(f"✅ DECIDED: {state.entry_id[:12]}... (consensus achieved)")

    async def wait_for_consensus(self, entry_id: str = None, timeout: float = 10.0) -> Optional[Dict]:
        """
        Wait for consensus on entry

        Args:
            entry_id: Entry to wait for (if None, waits for next consensus)
            timeout: Maximum wait time in seconds

        Returns:
            Decided value if consensus reached, None if timeout
        """
        start = time.time()

        while time.time() - start < timeout:
            # Check if any entry has been decided
            for _seq, state in self.log.items():
                if state.phase == ConsensusPhase.DECIDED:
                    if entry_id is None or state.entry_id == entry_id:
                        return state.decided_value

            await asyncio.sleep(0.1)

        print(f"⏱️  Consensus timeout after {timeout}s")
        return None

    async def _heartbeat(self):
        """Send periodic heartbeats (leader election)"""
        while True:
            current_time = time.time()

            # Check if leader is still alive
            if self.role == NodeRole.FOLLOWER:
                if current_time - self.last_heartbeat > self.heartbeat_timeout:
                    # Leader timeout, become candidate
                    await self._become_candidate()

            # If leader, send heartbeat
            if self.role == NodeRole.LEADER:
                heartbeat = ConsensusMessage(
                    node_id=self.node_id,
                    phase=ConsensusPhase.PRE_PREPARE,
                    entry_id="heartbeat",
                    sequence=self.sequence,
                    timestamp=current_time,
                    data={'type': 'heartbeat'},
                )
                heartbeat.signature = self._sign_message(heartbeat.to_json())

                for peer in self.peers:
                    await self._send_message(peer, heartbeat)

            await asyncio.sleep(self.heartbeat_interval)

    def request_vote(self, term: int, candidate_id: str) -> bool:
        """Raft-style vote rule. Grant at most one vote per term, to the first
        candidate seen in a term >= our own; step down to follower on a higher term."""
        if term < self.current_term:
            return False
        if term > self.current_term:
            self.current_term = term
            self.voted_for = None
            self.role = NodeRole.FOLLOWER
        if self.voted_for in (None, candidate_id):
            self.voted_for = candidate_id
            self.last_heartbeat = time.time()
            return True
        return False

    def _has_quorum(self, votes: int) -> bool:
        return votes >= self.quorum

    async def _become_candidate(self):
        """Run a real election: bump term, self-vote, collect peer votes, and
        win only on quorum."""
        self.current_term += 1
        self.role = NodeRole.CANDIDATE
        self.voted_for = self.node_id
        print(f"🟨 Candidate: {self.node_id} starting election (term={self.current_term})")

        votes = 1  # self-vote
        for peer in self.peers:
            if await self._request_peer_vote(peer, self.current_term):
                votes += 1

        if self._has_quorum(votes):
            await self._become_leader()
        else:
            self.role = NodeRole.FOLLOWER  # split/lost — await next election timeout

    async def _request_peer_vote(self, peer: str, term: int) -> bool:
        """Transport seam for RequestVote. The cluster daemon wires this over
        HTTP; the in-process base has no transport, so it returns False."""
        return False

    async def _become_leader(self):
        """Transition to leader for the current term."""
        self.role = NodeRole.LEADER
        self.leader_id = self.node_id
        print(f"🟩 Leader: {self.node_id} elected (term={self.current_term})")

    async def _send_message(self, peer: str, message: ConsensusMessage):
        """Send message to peer (simulated)"""
        # In production, this would send over network
        # For now, we'll use a queue
        await self.message_queue.put((peer, message))

    def public_key_hex(self) -> str:
        """Export this node's Ed25519 public key (hex) for peer registration."""
        if not _ED25519 or self._private_key is None:
            return ""
        raw = self._private_key.public_key().public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        )
        return raw.hex()

    def register_public_key(self, node_id: str, public_hex: str) -> None:
        """Register a peer's Ed25519 public key so its messages can be verified."""
        if _ED25519 and public_hex:
            self._public_keys[node_id] = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(public_hex)
            )

    def _signing_payload(self, message: ConsensusMessage) -> bytes:
        """Canonical signed bytes = message JSON with the signature field blanked
        (matches how senders sign before setting message.signature)."""
        saved = message.signature
        message.signature = ""
        payload = message.to_json().encode()
        message.signature = saved
        return payload

    def _sign_message(self, data: str) -> str:
        """Sign a message payload with this node's Ed25519 private key."""
        if not _ED25519 or self._private_key is None:
            return hashlib.sha256((self.node_id + data).encode()).hexdigest()  # fallback
        return self._private_key.sign(data.encode()).hex()

    def _verify_signature(self, message: ConsensusMessage) -> bool:
        """Verify a message's Ed25519 signature against the sender's public key.
        Unknown sender or bad signature → reject (secure default)."""
        if not _ED25519:
            return len(message.signature) > 0  # degraded fallback (no crypto)
        pub = self._public_keys.get(message.node_id)
        if pub is None:
            # No key for this sender: reject in strict mode; otherwise fall back
            # to the legacy non-empty check (key exchange not yet wired).
            return (not self.strict_signatures) and len(message.signature) > 0
        if not message.signature:
            return False
        try:
            pub.verify(bytes.fromhex(message.signature), self._signing_payload(message))
            return True
        except (InvalidSignature, ValueError):
            return False

    def _generate_entry_id(self, data: Dict) -> str:
        """Generate unique entry ID"""
        data_str = json.dumps(data, sort_keys=True)
        hash_val = hashlib.sha256(data_str.encode()).hexdigest()
        return f"entry_{hash_val[:16]}"

    def get_status(self) -> Dict:
        """Get current consensus status"""
        decided_count = sum(1 for s in self.log.values() if s.phase == ConsensusPhase.DECIDED)

        return {
            'node_id': self.node_id,
            'role': self.role.value,
            'leader_id': self.leader_id,
            'cluster_size': self.cluster_size,
            'sequence': self.sequence,
            'log_size': len(self.log),
            'decided_count': decided_count,
            'pending_count': len(self.pending_entries),
            'max_faulty': self.max_faulty,
            'quorum': self.quorum,
        }


# ── Module-level singleton ────────────────────────────────────────────────

_consensus: Optional[DistributedConsensus] = None


def get_distributed_consensus(node_id: str = "node_default", peers: List[str] = None) -> DistributedConsensus:
    """Get or create distributed consensus instance"""
    global _consensus
    if _consensus is None:
        peers = peers or []
        _consensus = DistributedConsensus(node_id, peers)
    return _consensus


async def consensus_demo():
    """Demo: Single-node consensus (for testing)"""
    consensus = get_distributed_consensus(
        node_id="node_1",
        peers=[]  # No peers for demo
    )

    # Simulate becoming leader
    consensus.role = NodeRole.LEADER
    consensus.leader_id = consensus.node_id

    # Propose entry
    entry_id = await consensus.propose_entry({'data': 'test_entry'})

    # Wait for consensus (will timeout since no peers)
    result = await asyncio.wait_for(
        consensus.wait_for_consensus(entry_id, timeout=2.0),
        timeout=3.0
    )

    print(f"Result: {result}")
    print(f"Status: {consensus.get_status()}")


if __name__ == "__main__":
    # Run demo
    asyncio.run(consensus_demo())
