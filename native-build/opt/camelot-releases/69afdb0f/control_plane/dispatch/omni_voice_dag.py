# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-
"""
Omni-Voice D.A.G. — Crystal Loader, Evidence Gate & Persona Dispatch.
======================================================================
Loads the ``νKG_CRYSTAL_OMNI_VOICE_DAG_VMAX`` manifest, proves its D.A.G.
topology and 384 MB memory ceiling hold, binds every declared service to a
real repository path, and routes voice intent either through a ``ᛟ_`` runic
bypass or through the Softmax persona distribution.

Why this module exists
----------------------
The Omni-Voice manifest arrived as **pasted sovereign seed** text. Per the
repository constitution, pasted dispatch text is draft material, never
authority: a claim may only be labelled ``confirmed`` when a local artifact
reproduces it. This module is the gate that performs that check instead of
trusting the prose, and it mirrors the ``GCMN_GOVERNANCE`` precedent in
``control_plane/runes/runic_router.py``.

Every routing path here is **read-only** — it validates and decides, and it
never spawns a process, mounts a cartridge, or touches the harness queue.
Promoting a ``planned`` node to ``confirmed`` requires the artifact to exist
on disk, not an edit to this file.

Run as module:
    python -m control_plane.omni_voice_dag --test
    python -m control_plane.omni_voice_dag --validate
    python -m control_plane.omni_voice_dag --route "ᛟ_SILENCE"
    python -m control_plane.omni_voice_dag --route "forge a new audio pipeline"
"""

from __future__ import annotations

__version__ = "9000.27"  # CYBERTRONIA — camelot-audio-dsp ingress promoted to confirmed

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CAMELOT_HOME = Path(__file__).resolve().parent.parent.parent
CRYSTAL_PATH = CAMELOT_HOME / "03_VAULT" / "runtime_state" / "omni_voice_dag_vmax_crystal.json"

SCHEMA_VERSION = "camelot.omni-voice-dag/1"

# Evidence classes from the repository constitution. A claim promoted to
# `confirmed` must be backed by a live artifact; anything else is reported
# honestly rather than as working infrastructure.
EVIDENCE_CONFIRMED = "confirmed"
EVIDENCE_PLANNED = "planned"
EVIDENCE_ASPIRATIONAL = "aspirational"
EVIDENCE_REJECTED = "rejected"
EVIDENCE_CLASSES = (
    EVIDENCE_CONFIRMED,
    EVIDENCE_PLANNED,
    EVIDENCE_ASPIRATIONAL,
    EVIDENCE_REJECTED,
)

# Runes whose `ᛟ_` tokens must resolve to a real entry in the runic router
# table. Enforced by tests so the bypass can never drift into a dead token.
BYPASS_DELEGATE_RUNES = (
    "//VOICE_ROUTER",
    "//MULTIVOICE_ROUTE",
    "//STATUS",
    "//FORGE",
    "//BIFROST_LOCK",
)


class CrystalError(ValueError):
    """Raised when the crystal is structurally invalid or self-contradictory."""


class TauPolicyError(ValueError):
    """Raised when a tau value escapes the Sentinel-governed policy."""


# ---------------------------------------------------------------------------
# Crystal model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    node_id: str
    stage: int
    title: str
    declared_service: str
    declared_runtime: str
    action: str
    memory_budget_mb: int
    predecessors: tuple[str, ...]
    evidence_class: str
    resolved_paths: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class BypassCommand:
    token: str
    knight: str
    delegates_rune: str


@dataclass
class Crystal:
    """Parsed, validated Omni-Voice D.A.G. manifest."""

    schema_version: str
    fingerprint: str
    system_identity: str
    hardware_ceiling_mb: int
    nodes: list[Node]
    node_order: list[str]
    parallel_threads: list[str]
    fan_out_at: str
    reduce_at: str
    memory_invariants: list[str]
    bypass_prefix: str
    bypass_commands: dict[str, BypassCommand]
    feature_dims: list[str]
    weights: dict[str, list[float]]
    allowed_tau_values: tuple[int, ...]
    deterministic_tau: int
    exploratory_tau: int
    provenance: dict[str, Any] = field(default_factory=dict)

    # -- evidence reporting -------------------------------------------------

    def evidence_summary(self) -> dict[str, int]:
        """Count nodes per evidence class (always all four keys present)."""
        summary = {cls: 0 for cls in EVIDENCE_CLASSES}
        for node in self.nodes:
            summary[node.evidence_class] += 1
        return summary

    def memory_total_mb(self) -> int:
        return sum(node.memory_budget_mb for node in self.nodes)

    def unconfirmed_nodes(self) -> list[str]:
        return [n.node_id for n in self.nodes if n.evidence_class != EVIDENCE_CONFIRMED]


# ---------------------------------------------------------------------------
# Loading & structural validation
# ---------------------------------------------------------------------------


def load_crystal(path: Optional[Path] = None) -> Crystal:
    """Read + structurally validate the crystal. Raises :class:`CrystalError`."""
    crystal_path = Path(path) if path is not None else CRYSTAL_PATH
    if not crystal_path.exists():
        raise CrystalError(f"crystal manifest not found: {crystal_path}")
    try:
        raw = json.loads(crystal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise CrystalError(f"crystal manifest is not valid JSON: {exc}") from exc
    return parse_crystal(raw)


def parse_crystal(raw: dict[str, Any]) -> Crystal:
    """Validate a crystal payload and return the typed model."""
    schema = raw.get("schema_version")
    if schema != SCHEMA_VERSION:
        raise CrystalError(f"unsupported schema_version {schema!r}; expected {SCHEMA_VERSION!r}")

    ceiling = raw.get("hardware_ceiling_mb")
    if not isinstance(ceiling, int) or ceiling <= 0:
        raise CrystalError("hardware_ceiling_mb must be a positive integer")

    raw_nodes = raw.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise CrystalError("crystal declares no nodes")

    nodes: list[Node] = []
    seen_ids: set[str] = set()
    for entry in raw_nodes:
        if not isinstance(entry, dict):
            raise CrystalError("every node must be an object")
        node_id = entry.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            raise CrystalError("every node requires a non-empty node_id")
        if node_id in seen_ids:
            raise CrystalError(f"duplicate node_id {node_id!r}")
        seen_ids.add(node_id)

        evidence = entry.get("evidence_class")
        if evidence not in EVIDENCE_CLASSES:
            raise CrystalError(f"node {node_id!r} has invalid evidence_class {evidence!r}")

        budget = entry.get("memory_budget_mb")
        if not isinstance(budget, int) or budget < 0:
            raise CrystalError(f"node {node_id!r} requires a non-negative integer memory_budget_mb")

        predecessors = entry.get("predecessors", [])
        if not isinstance(predecessors, list):
            raise CrystalError(f"node {node_id!r} predecessors must be a list")

        resolved = entry.get("resolved_paths", [])
        if not isinstance(resolved, list):
            raise CrystalError(f"node {node_id!r} resolved_paths must be a list")
        if evidence == EVIDENCE_CONFIRMED and not resolved:
            raise CrystalError(
                f"node {node_id!r} claims evidence_class='confirmed' without a resolved_paths artifact"
            )

        nodes.append(
            Node(
                node_id=node_id,
                stage=int(entry.get("stage", 0)),
                title=str(entry.get("title", "")),
                declared_service=str(entry.get("declared_service", "")),
                declared_runtime=str(entry.get("declared_runtime", "")),
                action=str(entry.get("action", "")),
                memory_budget_mb=budget,
                predecessors=tuple(str(p) for p in predecessors),
                evidence_class=str(evidence),
                resolved_paths=tuple(str(p) for p in resolved),
                notes=str(entry.get("notes", "")),
            )
        )

    # Dangling edges would make the topology unsound.
    for node in nodes:
        for pred in node.predecessors:
            if pred not in seen_ids:
                raise CrystalError(f"node {node.node_id!r} references unknown predecessor {pred!r}")

    node_order = topological_order(nodes)

    total_mb = sum(n.memory_budget_mb for n in nodes)
    if total_mb > ceiling:
        raise CrystalError(
            f"memory ceiling breached: nodes total {total_mb} MB > hardware_ceiling_mb {ceiling} MB"
        )

    parallel = raw.get("parallel_threads", {}) or {}
    threads = parallel.get("threads", []) or []
    if not isinstance(threads, list):
        raise CrystalError("parallel_threads.threads must be a list")
    fan_out_at = str(parallel.get("fan_out_at", ""))
    reduce_at = str(parallel.get("reduce_at", ""))
    for anchor in (fan_out_at, reduce_at):
        if anchor and anchor not in seen_ids:
            raise CrystalError(f"parallel_threads anchor {anchor!r} is not a declared node")
    for thread in threads:
        if thread not in seen_ids:
            raise CrystalError(f"parallel thread {thread!r} is not a declared node")

    bypass = raw.get("runic_bypass", {}) or {}
    prefix = str(bypass.get("prefix", "ᛟ_"))
    commands: dict[str, BypassCommand] = {}
    for entry in bypass.get("commands", []) or []:
        token = str(entry.get("token", ""))
        if not token.startswith(prefix):
            raise CrystalError(f"bypass token {token!r} does not carry the declared prefix {prefix!r}")
        commands[token] = BypassCommand(
            token=token,
            knight=str(entry.get("knight", "")),
            delegates_rune=str(entry.get("delegates_rune", "")),
        )

    dispatch = raw.get("persona_dispatch", {}) or {}
    feature_dims = [str(d) for d in dispatch.get("feature_dims", []) or []]
    if not feature_dims:
        raise CrystalError("persona_dispatch.feature_dims must declare at least one dimension")
    weights: dict[str, list[float]] = {}
    for knight, vector in (dispatch.get("weights", {}) or {}).items():
        vec = [float(w) for w in vector]
        if len(vec) != len(feature_dims):
            raise CrystalError(
                f"persona {knight!r} weight vector has {len(vec)} dims, expected {len(feature_dims)}"
            )
        weights[str(knight)] = vec
    if not weights:
        raise CrystalError("persona_dispatch must declare at least one persona weight vector")

    tau_policy = dispatch.get("tau_policy", {}) or {}
    allowed_tau = tuple(int(t) for t in tau_policy.get("allowed_tau_values", []) or [])
    if not allowed_tau:
        raise CrystalError("tau_policy.allowed_tau_values must not be empty")

    return Crystal(
        schema_version=SCHEMA_VERSION,
        fingerprint=str(raw.get("fingerprint", "")),
        system_identity=str(raw.get("system_identity", "")),
        hardware_ceiling_mb=ceiling,
        nodes=nodes,
        node_order=node_order,
        parallel_threads=[str(t) for t in threads],
        fan_out_at=fan_out_at,
        reduce_at=reduce_at,
        memory_invariants=[str(i) for i in raw.get("memory_invariants", []) or []],
        bypass_prefix=prefix,
        bypass_commands=commands,
        feature_dims=feature_dims,
        weights=weights,
        allowed_tau_values=allowed_tau,
        deterministic_tau=int(tau_policy.get("deterministic_tau", 0)),
        exploratory_tau=int(tau_policy.get("exploratory_tau", 1)),
        provenance=dict(raw.get("provenance", {}) or {}),
    )


def topological_order(nodes: Sequence[Node]) -> list[str]:
    """Kahn topological sort. Raises :class:`CrystalError` on a cycle."""
    indegree = {n.node_id: len(n.predecessors) for n in nodes}
    successors: dict[str, list[str]] = {n.node_id: [] for n in nodes}
    for node in nodes:
        for pred in node.predecessors:
            successors[pred].append(node.node_id)

    ready = [nid for nid in indegree if indegree[nid] == 0]
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for nxt in successors[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)

    if len(order) != len(nodes):
        raise CrystalError("crystal topology contains a cycle; the D.A.G. is not acyclic")
    return order


# ---------------------------------------------------------------------------
# Live evidence gate
# ---------------------------------------------------------------------------


def resolve_evidence(crystal: Crystal, root: Optional[Path] = None) -> dict[str, Any]:
    """Re-check every ``resolved_paths`` claim against the live filesystem.

    A node labelled ``confirmed`` whose artifact is missing is downgraded to
    ``planned`` in the report. Claims never self-certify.
    """
    base = Path(root) if root is not None else CAMELOT_HOME
    report: dict[str, Any] = {
        "root": str(base),
        "nodes": {},
        "verified": [],
        "downgraded": [],
        "unconfirmed": [],
    }
    for node in crystal.nodes:
        missing = [p for p in node.resolved_paths if not (base / p).exists()]
        found = [p for p in node.resolved_paths if (base / p).exists()]
        effective = node.evidence_class
        if node.evidence_class == EVIDENCE_CONFIRMED and not found:
            # A confirmed claim with no artifact on disk is a lie until proven
            # otherwise; report it as planned rather than as working infra.
            effective = EVIDENCE_PLANNED
            report["downgraded"].append(node.node_id)
        elif node.evidence_class == EVIDENCE_CONFIRMED:
            report["verified"].append(node.node_id)
        else:
            report["unconfirmed"].append(node.node_id)

        report["nodes"][node.node_id] = {
            "declared_evidence_class": node.evidence_class,
            "effective_evidence_class": effective,
            "declared_service": node.declared_service,
            "declared_runtime": node.declared_runtime,
            "resolved_paths": list(node.resolved_paths),
            "found_paths": found,
            "missing_paths": missing,
            # For planned/aspirational nodes the listed paths are the live
            # precursor artifacts, not a deployed instance of the service.
            "precursor_found": bool(found),
        }
    return report


# ---------------------------------------------------------------------------
# Runic bypass
# ---------------------------------------------------------------------------


def detect_rune(text: str, crystal: Optional[Crystal] = None) -> Optional[BypassCommand]:
    """Return the bypass command if ``text`` opens with a declared ``ᛟ_`` token.

    The token must be the first whitespace-delimited word so a mid-sentence
    glyph cannot hijack the audio stream.
    """
    if not text or not text.strip():
        return None
    table = crystal.bypass_commands if crystal is not None else _default_bypass_commands()
    prefix = crystal.bypass_prefix if crystal is not None else "ᛟ_"
    head = text.strip().split()[0]
    if not head.startswith(prefix):
        return None
    normalized = head
    if normalized not in table:
        # Tolerate trailing punctuation from speech-to-text, nothing more.
        normalized = head.rstrip(".,!?;:")
    return table.get(normalized)


def _default_bypass_commands() -> dict[str, BypassCommand]:
    """Standalone bypass table used when no crystal is supplied (degraded mode)."""
    return {
        "ᛟ_SUMMON": BypassCommand("ᛟ_SUMMON", "sir_sonus", "//VOICE_ROUTER"),
        "ᛟ_MULTIVOICE": BypassCommand("ᛟ_MULTIVOICE", "sir_sonus", "//MULTIVOICE_ROUTE"),
        "ᛟ_STATUS": BypassCommand("ᛟ_STATUS", "sir_lucas", "//STATUS"),
        "ᛟ_FORGE": BypassCommand("ᛟ_FORGE", "sir_forge", "//FORGE"),
        "ᛟ_SILENCE": BypassCommand("ᛟ_SILENCE", "sir_sentinel", "//BIFROST_LOCK"),
    }


# ---------------------------------------------------------------------------
# Softmax persona dispatch
# ---------------------------------------------------------------------------


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} features vs {len(b)} weights")
    return sum(x * y for x, y in zip(a, b, strict=True))


def resolve_tau(crystal: Crystal, tau: Optional[int] = None) -> int:
    """Clamp a requested tau to the Sentinel-governed policy.

    ``τ=0`` is deterministic execution, ``τ=1`` is exploratory persona
    routing. Any value outside the declared policy is rejected rather than
    silently clamped, so an exploratory drift stays visible in telemetry.
    """
    chosen = crystal.deterministic_tau if tau is None else int(tau)
    if chosen not in crystal.allowed_tau_values:
        raise TauPolicyError(
            f"tau={chosen} violates Sentinel policy {list(crystal.allowed_tau_values)}"
        )
    return chosen


def softmax_dispatch(
    features: Sequence[float],
    weights: dict[str, Sequence[float]],
    tau: int,
) -> tuple[dict[str, float], dict[str, float], str, float]:
    """Compute ``P(K_i|v) = exp(v·W_i / τ) / Σ_j exp(v·W_j / τ)``.

    Returns ``(probabilities, logits, selected_persona, confidence)``.

    ``τ=0`` collapses the distribution to a one-hot argmax with confidence
    ``1.0`` — deterministic execution, no sampling. ``τ>0`` produces a true
    softmax, shifted by the max logit so it is numerically stable.
    """
    if tau < 0:
        raise ValueError("tau must be non-negative")
    if not weights:
        raise ValueError("no persona weight vectors supplied")

    logits = {knight: dot(features, vec) for knight, vec in weights.items()}

    if tau == 0:
        # Deterministic lane: highest logit wins, ties broken lexicographically
        # so the same utterance always selects the same knight.
        winner = max(logits, key=lambda k: (logits[k], k))
        probs = {knight: (1.0 if knight == winner else 0.0) for knight in logits}
        return probs, logits, winner, 1.0

    scaled = {knight: value / tau for knight, value in logits.items()}
    peak = max(scaled.values())
    exps = {knight: math.exp(value - peak) for knight, value in scaled.items()}
    total = sum(exps.values())
    probs = {knight: value / total for knight, value in exps.items()}
    winner = max(probs, key=lambda k: (probs[k], k))
    return probs, logits, winner, probs[winner]


def route_intent(
    text: str,
    features: Optional[Sequence[float]] = None,
    tau: Optional[int] = None,
    crystal: Optional[Crystal] = None,
) -> dict[str, Any]:
    """Route one voice utterance: runic bypass first, softmax second.

    The bypass short-circuits before any inference work, which is the entire
    point of the ``ᛟ_`` lane.
    """
    loaded = crystal
    loaded_error: Optional[str] = None
    if loaded is None:
        try:
            loaded = load_crystal()
        except CrystalError as exc:
            loaded_error = str(exc)

    bypass = detect_rune(text, loaded)
    if bypass is not None:
        return {
            "action": "omni_voice_route",
            "input": text,
            "path": "runic_bypass",
            "token": bypass.token,
            "knight": bypass.knight,
            "delegates_rune": bypass.delegates_rune,
            "llm_inference_cost": 0,
            "status": "ROUTED_BYPASS",
        }

    if loaded is None:
        return {
            "action": "omni_voice_route",
            "input": text,
            "path": "unavailable",
            "error": loaded_error or "crystal unavailable",
            "status": "CRYSTAL_UNAVAILABLE",
        }

    try:
        chosen_tau = resolve_tau(loaded, tau)
    except TauPolicyError as exc:
        return {
            "action": "omni_voice_route",
            "input": text,
            "path": "softmax",
            "error": str(exc),
            "status": "TAU_POLICY_DENIED",
        }

    if features is None:
        features = infer_features(text, loaded)
    if len(features) != len(loaded.feature_dims):
        return {
            "action": "omni_voice_route",
            "input": text,
            "path": "softmax",
            "error": (
                f"feature vector has {len(features)} dims, crystal declares "
                f"{len(loaded.feature_dims)}"
            ),
            "status": "FEATURE_DIM_MISMATCH",
        }

    probs, logits, winner, confidence = softmax_dispatch(features, loaded.weights, chosen_tau)
    return {
        "action": "omni_voice_route",
        "input": text,
        "path": "softmax",
        "tau": chosen_tau,
        "features": [round(f, 4) for f in features],
        "logits": {k: round(v, 4) for k, v in logits.items()},
        "probabilities": {k: round(v, 6) for k, v in probs.items()},
        "knight": winner,
        "confidence": round(confidence, 6),
        "status": "ROUTED_SOFTMAX",
    }


def infer_features(text: str, crystal: Crystal) -> list[float]:
    """Deterministic keyword -> feature projection.

    Cheap and fully explainable: no inference cost, which is the constraint
    the ``ᛟ_`` bypass exists to protect. Extend the keyword table rather than
    reaching for a model.
    """
    lowered = text.lower()
    keywords = {
        "lexical_intent": ("why", "how", "explain", "what", "reason"),
        "urgency": ("now", "immediately", "asap", "urgent", "critical"),
        "privacy_sensitive": ("secret", "token", "key", "password", "private"),
        "telemetry_request": ("status", "metrics", "telemetry", "report", "health"),
        "build_intent": ("forge", "build", "implement", "create", "compile"),
        "audio_focus": ("voice", "audio", "speak", "listen", "say"),
    }
    vector: list[float] = []
    for dim in crystal.feature_dims:
        needles = keywords.get(dim, ())
        vector.append(1.0 if any(needle in lowered for needle in needles) else 0.0)
    return vector


# ---------------------------------------------------------------------------
# Cross-language parity fixture
# ---------------------------------------------------------------------------

# Utterances that pin the gateway's TypeScript port to this module. The tuple
# is ``(text, tau)``; tau is ignored for runic-bypass inputs.
PARITY_UTTERANCES: tuple[tuple[str, Optional[int]], ...] = (
    # Runic bypass — every declared token, plus the rejection cases.
    ("ᛟ_SUMMON the voice knight", None),
    ("ᛟ_SILENCE", None),
    ("ᛟ_STATUS", None),
    ("ᛟ_MULTIVOICE", None),
    ("ᛟ_FORGE", None),
    ("ᛟ_SILENCE.", None),
    ("please ᛟ_SILENCE", None),
    ("ᛟ_NOPE", None),
    ("", None),
    # Softmax dispatch — deterministic (tau=0) and exploratory (tau=1) lanes.
    ("forge a new audio pipeline now", 0),
    ("forge a new audio pipeline now", 1),
    ("let me speak to you", 0),
    ("my password and private key leaked", 0),
    ("status report on the swarm health", 0),
    ("what is the reason for this", 0),
    ("immediately fix the urgent thing", 0),
    ("create a new build for the voice pipeline", 1),
)


def build_parity_fixture(crystal: Optional[Crystal] = None) -> dict[str, Any]:
    """Emit the cross-language parity fixture consumed by the Bifrost gateway.

    The gateway routes voice commands in TypeScript on the Node event loop and
    cannot import this module, so ``apps/bifrost`` re-implements the
    deterministic contract. This fixture is generated *from* the Python
    implementation and is what keeps the two honest: the gateway's tests replay
    every vector below and fail the moment the port drifts.

    Regenerate with::

        python -m control_plane.omni_voice_dag \\
            --write-vectors apps/bifrost/src/omniVoice.crystal.json

    Numeric fields are emitted at full precision (no ``round``-ing) so the
    parity assertions can use a tolerance instead of comparing rounded text.
    """
    loaded = crystal if crystal is not None else load_crystal()

    vectors: list[dict[str, Any]] = []
    for text, requested_tau in PARITY_UTTERANCES:
        decision = route_intent(text, tau=requested_tau, crystal=loaded)
        entry: dict[str, Any] = {
            "input": text,
            "status": decision["status"],
            "path": decision.get("path"),
        }
        if decision["status"] == "ROUTED_BYPASS":
            entry["token"] = decision["token"]
            entry["knight"] = decision["knight"]
            entry["delegates_rune"] = decision["delegates_rune"]
        elif decision["status"] == "ROUTED_SOFTMAX":
            tau = resolve_tau(loaded, requested_tau)
            features = [float(f) for f in infer_features(text, loaded)]
            probs, logits, winner, confidence = softmax_dispatch(features, loaded.weights, tau)
            entry["tau"] = tau
            entry["features"] = features
            entry["logits"] = {knight: logits[knight] for knight in sorted(logits)}
            entry["probabilities"] = {knight: probs[knight] for knight in sorted(probs)}
            entry["knight"] = winner
            entry["confidence"] = confidence
        vectors.append(entry)

    return {
        "generator": "control_plane.omni_voice_dag",
        "generator_version": __version__,
        "fingerprint": loaded.fingerprint,
        "system_identity": loaded.system_identity,
        "hardware_ceiling_mb": loaded.hardware_ceiling_mb,
        "bypass_prefix": loaded.bypass_prefix,
        "feature_dims": list(loaded.feature_dims),
        "tau_policy": {
            "allowed_tau_values": list(loaded.allowed_tau_values),
            "deterministic_tau": loaded.deterministic_tau,
            "exploratory_tau": loaded.exploratory_tau,
        },
        "weights": {knight: [float(w) for w in loaded.weights[knight]] for knight in sorted(loaded.weights)},
        "bypass_commands": [
            {
                "token": command.token,
                "knight": command.knight,
                "delegates_rune": command.delegates_rune,
            }
            for command in (loaded.bypass_commands[token] for token in sorted(loaded.bypass_commands))
        ],
        "vectors": vectors,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def self_test() -> int:
    """Side-effect-free self test. Mirrors the ``python -m ... --test`` convention."""
    failures: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    try:
        crystal = load_crystal()
    except CrystalError as exc:
        print(f"FAIL  crystal load: {exc}", file=sys.stderr)
        return 1

    check("schema_version", crystal.schema_version == SCHEMA_VERSION)
    check("node_count", len(crystal.nodes) == 5)
    check("topology_acyclic", len(crystal.node_order) == len(crystal.nodes))
    check("node_01_first", crystal.node_order[0] == "node_01_ingress")
    check("egress_last", crystal.node_order[-1] == "node_04_egress")
    check("fan_out_at_routing", crystal.fan_out_at == "node_02_routing")
    check("reduce_at_egress", crystal.reduce_at == "node_04_egress")
    check("parallel_thread_count", len(crystal.parallel_threads) == 2)
    check("memory_within_ceiling", crystal.memory_total_mb() <= crystal.hardware_ceiling_mb)

    # Deterministic lane must be a one-hot argmax.
    probs0, _, winner0, conf0 = softmax_dispatch(
        [1.0, 0.0, 0.0, 0.0, 0.0, 1.0], crystal.weights, crystal.deterministic_tau
    )
    check("tau0_one_hot", sorted(probs0.values())[-1] == 1.0 and sorted(probs0.values())[0] == 0.0)
    check("tau0_confidence", conf0 == 1.0)
    check("tau0_audio_winner", winner0 in ("sir_sonus", "sir_helio"))

    # Exploratory lane must yield a normalised distribution.
    probs1, _, winner1, conf1 = softmax_dispatch(
        [1.0, 1.0, 0.0, 0.0, 0.0, 1.0], crystal.weights, crystal.exploratory_tau
    )
    check("tau1_normalised", abs(sum(probs1.values()) - 1.0) < 1e-9)
    check("tau1_confidence_in_range", 0.0 < conf1 <= 1.0)
    check("tau1_winner_declared", winner1 in crystal.weights)

    # Bypass must be unrecognised mid-sentence.
    check("bypass_first_word", detect_rune("ᛟ_SILENCE now", crystal) is not None)
    check("bypass_mid_sentence_rejected", detect_rune("please ᛟ_SILENCE", crystal) is None)
    check("bypass_unknown_rejected", detect_rune("ᛟ_NOPE", crystal) is None)

    silence = detect_rune("ᛟ_SILENCE", crystal)
    check("silence_knight", silence is not None and silence.knight == "sir_sentinel")

    # Live evidence gate must not upgrade a claim on its own.
    report = resolve_evidence(crystal)
    check("evidence_report_shape", set(report) >= {"nodes", "verified", "downgraded"})
    check("routing_node_verified", "node_02_routing" in report["verified"])
    # The ingress node was promoted from `planned` to `confirmed` when the real
    # Rust/WASM crate landed; a missing artifact would demote it again on sight.
    check("ingress_node_verified", "node_01_ingress" in report["verified"])
    check("ingress_no_missing_artifacts", not report["nodes"]["node_01_ingress"]["missing_paths"])

    # Delegate runes must exist in the real router table.
    try:
        from control_plane.runes import runic_router as rr

        for cmd in crystal.bypass_commands.values():
            check(f"delegate_rune::{cmd.delegates_rune}", cmd.delegates_rune in rr.RUNIC_COMMANDS)
    except Exception as exc:  # pragma: no cover - import guard only
        print(f"WARN  runic_router unavailable, skipping delegate check: {exc}", file=sys.stderr)

    if failures:
        print("FAIL  omni_voice_dag self-test:", file=sys.stderr)
        for name in failures:
            print(f"  - {name}", file=sys.stderr)
        return 1

    summary = crystal.evidence_summary()
    print(
        f"PASS  omni_voice_dag v{__version__} :: {len(crystal.nodes)} nodes, "
        f"{crystal.memory_total_mb()}/{crystal.hardware_ceiling_mb} MB, "
        f"confirmed={summary[EVIDENCE_CONFIRMED]} planned={summary[EVIDENCE_PLANNED]} "
        f"aspirational={summary[EVIDENCE_ASPIRATIONAL]}"
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omni_voice_dag",
        description="Omni-Voice D.A.G. crystal loader, evidence gate and persona dispatch.",
    )
    parser.add_argument("--test", action="store_true", help="run the side-effect-free self test")
    parser.add_argument("--validate", action="store_true", help="validate the crystal and report evidence")
    parser.add_argument("--route", metavar="UTTERANCE", default=None, help="route one voice utterance")
    parser.add_argument("--tau", type=int, default=None, help="override tau (Sentinel policy applies)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--vectors",
        action="store_true",
        help="emit the cross-language parity fixture consumed by apps/bifrost as JSON",
    )
    parser.add_argument(
        "--write-vectors",
        metavar="PATH",
        default=None,
        help="write the cross-language parity fixture to PATH",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.test:
        return self_test()

    if args.vectors or args.write_vectors:
        try:
            fixture = build_parity_fixture()
        except CrystalError as exc:
            print(f"FAIL  {exc}", file=sys.stderr)
            return 1
        if args.write_vectors:
            target = Path(args.write_vectors)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(
                f"[omni-voice] parity fixture written to {target} "
                f"({len(fixture['vectors'])} vectors, generator v{fixture['generator_version']})"
            )
        else:
            print(json.dumps(fixture, ensure_ascii=False, indent=2))
        return 0

    if args.route is not None:
        result = route_intent(args.route, tau=args.tau)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"[omni-voice] {result['status']} path={result.get('path')}")
            if result.get("knight"):
                print(f"  knight={result['knight']} confidence={result.get('confidence')}")
            if result.get("delegates_rune"):
                print(f"  delegates={result['delegates_rune']}")
            if result.get("error"):
                print(f"  error={result['error']}")
        return 0 if result["status"] in ("ROUTED_BYPASS", "ROUTED_SOFTMAX") else 2

    # Default: validate.
    try:
        crystal = load_crystal()
    except CrystalError as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1

    report = {
        "fingerprint": crystal.fingerprint,
        "system_identity": crystal.system_identity,
        "schema_version": crystal.schema_version,
        "node_order": crystal.node_order,
        "memory_total_mb": crystal.memory_total_mb(),
        "hardware_ceiling_mb": crystal.hardware_ceiling_mb,
        "evidence_summary": crystal.evidence_summary(),
        "unconfirmed_nodes": crystal.unconfirmed_nodes(),
        "live_evidence": resolve_evidence(crystal),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[omni-voice] {crystal.system_identity} :: {crystal.fingerprint}")
        print(f"  topology: {' -> '.join(crystal.node_order)}")
        print(f"  memory:   {crystal.memory_total_mb()} / {crystal.hardware_ceiling_mb} MB")
        summary = crystal.evidence_summary()
        print(
            "  evidence: "
            + " ".join(f"{cls}={summary[cls]}" for cls in EVIDENCE_CLASSES)
        )
        if crystal.unconfirmed_nodes():
            print(f"  unconfirmed: {', '.join(crystal.unconfirmed_nodes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
