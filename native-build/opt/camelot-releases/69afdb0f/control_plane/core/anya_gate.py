# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Anya_Omega — APEE v6.5 Sovereign Gate
======================================
ANYA_IS_THE_GATE. Titanium Law #11.

Every intent enters through this pipeline. Every output exits through it.
No knight receives a raw prompt. No response returns unvalidated.

Pipeline: PARSE -> ENRICH -> COMPILE -> ROUTE -> VALIDATE
"""

from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA — set by P1-T01


import re
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# ---------------------------------------------------------------------------
# Stage output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    intent_type: str          # BUILD | RESEARCH | AUDIT | ROUTE | QUERY | FORGE | HEAL
    raw: str
    entities: list[str]
    constraints: list[str]
    complexity: float         # 0.0-1.0
    privacy: float            # 0.0-1.0
    velocity: float           # 0.0-1.0 (urgency)
    ambiguity_stripped: str   # cleaned intent with noise removed


@dataclass
class EnrichResult:
    domain: str               # go/binary | python/api | security | voice | infra | research
    cartridge_hint: str       # matching cartridge name
    ukg_refs: list[str]       # UKG node IDs relevant to intent
    context_tags: list[str]   # active service endpoints, personas
    magnitude: float          # derived from complexity + domain weight


@dataclass
class TitanPrompt:
    directive: str            # the compiled dense machine directive
    target_layer: str         # L1-L7
    execution_mode: str       # KINETIC | SWARM | ORACLE | FORGE | SENTINEL
    constraints_encoded: list[str]


@dataclass
class SocratesVerdict:
    """Northstar alignment check result (Phase 2.4 stub)."""
    aligned: bool
    alignment_note: str
    northstar_check_required: bool


@dataclass
class ValidationResult:
    passed: bool
    issues: list[str]
    iron_gate: str            # CLEARED | HITL_REQUIRED | BLOCKED
    net_lines_estimate: int
    requires_briefing: bool


@dataclass
class APEEResult:
    """Full APEE v6.5 pipeline result — the compiled artifact from Anya's gate."""
    raw_intent: str
    parse: ParseResult
    enrich: EnrichResult
    titan: TitanPrompt
    route_knight: str
    route_engine: str
    route_score: float
    route_reason: str
    validation: ValidationResult
    pipeline_ms: float
    colmad_verdict: "object | None" = None  # CrucibleVerdict for CRITICAL/HIGH intents (P1-T02)

    def render(self) -> str:
        """Returns the visible Anya pipeline block for display in responses."""
        sep = "─" * 54
        ig_color = "CLEARED" if self.validation.iron_gate == "CLEARED" else self.validation.iron_gate
        lines = [
            "",
            "🎭 ANYA_Omega — APEE v6.5 COMPILATION",
            sep,
            f"PARSE    | type={self.parse.intent_type}  complexity={self.parse.complexity:.2f}"
            f"  privacy={self.parse.privacy:.2f}",
            f"         | entities={self.parse.entities}",
            f"ENRICH   | domain={self.enrich.domain}  cartridge={self.enrich.cartridge_hint}"
            f"  magnitude={self.enrich.magnitude:.2f}",
            f"         | tags={self.enrich.context_tags}",
            f"COMPILE  | \"{self.titan.directive[:72]}\"",
            f"         | layer={self.titan.target_layer}  mode={self.titan.execution_mode}",
            f"ROUTE    | -> {self.route_knight.upper()} (W={self.route_score:.2f})",
            f"         | {self.route_reason}",
            f"VALIDATE | Iron Gate: {ig_color}  "
            f"briefing={'REQUIRED' if self.validation.requires_briefing else 'OK'}",
        ]
        if self.validation.issues:
            lines.append(f"         | issues={self.validation.issues}")
        if self.colmad_verdict is not None:
            cv = self.colmad_verdict
            lines.append(
                f"COLMAD   | {getattr(cv, 'verdict', '?')} "
                f"({getattr(cv, 'approvals', 0)}/3 approve)"
            )
        lines += [sep, f"         pipeline: {self.pipeline_ms:.0f}ms", ""]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# APEE v6.5 Stage Implementations
# ---------------------------------------------------------------------------

_NOISE_PATTERNS = re.compile(
    r"\b(please|kindly|could you|can you|just|simply|basically|like|you know|"
    r"i think|maybe|perhaps|would you|hey|yo|boss)\b",
    re.IGNORECASE,
)

_INTENT_TYPE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(build|compile|create|make|write|scaffold|forge|generate)\b", re.I), "BUILD"),
    (re.compile(r"\b(research|find|search|look up|investigate|analyze|analyse)\b", re.I), "RESEARCH"),
    (re.compile(r"\b(audit|review|security|scan|check|verify|validate)\b", re.I), "AUDIT"),
    (re.compile(r"\b(route|dispatch|send|assign|delegate)\b", re.I), "ROUTE"),
    (re.compile(r"\b(heal|fix|debug|repair|patch|resolve)\b", re.I), "HEAL"),
    (re.compile(r"\b(delete|remove|purge|clean|drop)\b", re.I), "FORGE"),
    (re.compile(r"\b(deploy|launch|start|boot|awaken|run)\b", re.I), "FORGE"),
]

_DOMAIN_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(go|golang|bubbletea|binary|compile|exe)\b", re.I), "go/binary"),
    (re.compile(r"\b(rust|cargo|axum|mcp)\b", re.I), "rust/kinetic"),
    (re.compile(r"\b(python|fastapi|pydantic|gradio|pip)\b", re.I), "python/api"),
    (re.compile(r"\b(security|audit|cve|vuln|sentinel|armor)\b", re.I), "security"),
    (re.compile(r"\b(voice|audio|tts|livekit|sonus)\b", re.I), "voice/media"),
    (re.compile(r"\b(next|react|node|typescript|ui|dashboard|web)\b", re.I), "web/ui"),
    (re.compile(r"\b(infra|docker|deploy|cloud|modal|k8s)\b", re.I), "infra/cloud"),
    (re.compile(r"\b(research|search|notebook|ukg|context)\b", re.I), "research"),
]

_CARTRIDGE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(cognitive|reasoning|critical thinking|tradeoff|decision)\b", re.I), "cognitive"),
    (re.compile(r"\b(bridge|handoff|terminal|ui)\b", re.I), "bridge"),
    (re.compile(r"\b(go|rust|binary|compile|kinetic)\b", re.I), "rust-kinetic"),
    (re.compile(r"\b(next|react|typescript|web|ui)\b", re.I), "nextjs"),
    (re.compile(r"\b(python|fastapi|api|pydantic)\b", re.I), "python-api"),
    (re.compile(r"\b(security|audit|cve|scan)\b", re.I), "security"),
    (re.compile(r"\b(voice|audio|livekit)\b", re.I), "voice-media"),
    (re.compile(r"\b(swarm|colony|agent|dispatch)\b", re.I), "swarm-colony"),
    (re.compile(r"\b(reason|think|plan|analyze)\b", re.I), "reasoning"),
]

_ENTITY_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z0-9_\-]{2,}|:\d{4,5}|sir_\w+|anya|merlin|lukas|"
    r"saltare|excalibur|holotable|vizion|loom\s*#?\d+)\b",
    re.IGNORECASE,
)

_PRIVACY_KEYWORDS = frozenset({"secret", "private", "credential", "key", "password", "local", "air-gapped"})
_HIGH_COMPLEXITY = frozenset({"swarm", "colony", "multi-agent", "refactor", "migrate", "architecture", "full stack"})


def _load_rtk():
    """Try to load the RTK shared library (control_plane/rtk/rtk.dll).
    Returns ctypes CDLL or None if unavailable (Rust Phase 7 not yet built).
    """
    import ctypes
    import logging
    for candidate in (
        Path(__file__).parent / "rtk" / "rtk.dll",
        Path(__file__).parent / "rtk.dll",
    ):
        if candidate.exists():
            try:
                lib = ctypes.CDLL(str(candidate))
                lib.strip_context_noise.argtypes = [ctypes.c_char_p]
                lib.strip_context_noise.restype = ctypes.c_char_p
                return lib
            except Exception as exc:
                logging.warning("[RTK] load failed: %s", exc)
    return None


_RTK_LIB = None
_RTK_ATTEMPTED = False


def _stage_rtk_strip(raw: str) -> str:
    """Stage 0: RTK strip — remove HTML/XML/markdown noise before parse.
    Falls back to a regex-only strip if rtk.dll is not present.
    Phase 2.2 (EXCALIBUR_A_QNF): RTK ctypes bridge.
    """
    global _RTK_LIB, _RTK_ATTEMPTED
    if not _RTK_ATTEMPTED:
        _RTK_LIB = _load_rtk()
        _RTK_ATTEMPTED = True

    if _RTK_LIB is not None:
        try:
            result = _RTK_LIB.strip_context_noise(raw.encode("utf-8"))
            if result:
                return result.decode("utf-8", errors="replace")
        except Exception:
            pass

    # Pure-Python fallback: strip HTML tags + markdown fences
    stripped = re.sub(r"<[^>]+>", " ", raw)
    stripped = re.sub(r"```[^\n]*\n.*?```", " ", stripped, flags=re.DOTALL)
    stripped = re.sub(r"\s{2,}", " ", stripped).strip()
    return stripped


def _stage_socrates(titan: TitanPrompt, triage: "object") -> SocratesVerdict:
    """Stage after VALIDATE: Northstar alignment check stub (Phase 2.4).
    For HIGH/HUMAN_GATE priority: log that alignment check is required.
    Returns SocratesVerdict — always aligned in stub form; wired to
    full Sir Socrates agent in a future Phase.
    """
    import logging
    hitl_tier = getattr(triage, "hitl_tier", "AUTO")
    priority = getattr(triage, "priority", "NORMAL")
    needs_check = hitl_tier in ("HUMAN_GATE",) or priority in ("HIGH", "CRITICAL")
    if needs_check:
        logging.info(
            "[SIR_SOCRATES] Northstar alignment check required — "
            "directive=%r  priority=%s  hitl=%s",
            titan.directive[:80],
            priority,
            hitl_tier,
        )
    return SocratesVerdict(
        aligned=True,
        alignment_note="stub — full Socrates agent pending Sir Socrates Knight impl",
        northstar_check_required=needs_check,
    )


def _stage_socrates_full(intent: str, hitl_tier: str) -> None:
    """Stage 7: full SirSocrates examination for HIGH/CRITICAL intents.

    Imports SirSocrates lazily (avoids circular imports). Logs verdict to
    logs/northstar_verdicts.jsonl via Lady Alexandria integration. No-ops
    silently if sir_socrates module is unavailable.
    """
    if hitl_tier not in ("PROMPT", "HUMAN_GATE"):
        return
    try:
        import importlib.util as _ilu
        from pathlib import Path as _P
        _spec = _ilu.spec_from_file_location(
            "sir_socrates",
            _P(__file__).resolve().parent / "sir_socrates.py",
        )
        if not _spec or not _spec.loader:
            return
        import sys as _sys
        if "sir_socrates" not in _sys.modules:
            _mod = _ilu.module_from_spec(_spec)
            _sys.modules["sir_socrates"] = _mod
            _spec.loader.exec_module(_mod)
        else:
            _mod = _sys.modules["sir_socrates"]
        exam = _mod.SirSocrates().examine(intent, triage_tier=hitl_tier)
        if not exam.overall_aligned:
            import logging as _log
            _log.warning(
                "[SIR_SOCRATES] Northstar drift detected — verdict=%s blocking=%s",
                exam.verdict, exam.blocking_questions,
            )
    except Exception:
        pass   # non-blocking — Socrates unavailable should not crash the pipeline


def _stage_parse(raw: str) -> ParseResult:
    cleaned = _NOISE_PATTERNS.sub("", raw).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    intent_type = "QUERY"
    for pattern, itype in _INTENT_TYPE_MAP:
        if pattern.search(cleaned):
            intent_type = itype
            break

    entities = list(dict.fromkeys(
        e.strip() for e in _ENTITY_PATTERN.findall(cleaned) if len(e.strip()) > 2
    ))[:8]

    constraints = []
    if re.search(r"\b(max|limit|ceiling|under|less than|<)\s*\d+", cleaned, re.I):
        constraints.append("has_numerical_constraint")
    if re.search(r"\b(only|never|always|must|shall)\b", cleaned, re.I):
        constraints.append("has_hard_constraint")
    if re.search(r"\b(today|now|urgent|immediately|asap)\b", cleaned, re.I):
        constraints.append("velocity_high")

    privacy = 0.9 if any(kw in cleaned.lower() for kw in _PRIVACY_KEYWORDS) else 0.0
    complexity = min(1.0, 0.3 + 0.1 * len(entities) + (0.3 if any(kw in cleaned.lower() for kw in _HIGH_COMPLEXITY) else 0.0))
    velocity = 0.8 if "velocity_high" in constraints else 0.5

    return ParseResult(
        intent_type=intent_type,
        raw=raw,
        entities=entities,
        constraints=constraints,
        complexity=complexity,
        privacy=privacy,
        velocity=velocity,
        ambiguity_stripped=cleaned,
    )


def _stage_enrich(parse: ParseResult) -> EnrichResult:
    domain = "general"
    for pattern, d in _DOMAIN_MAP:
        if pattern.search(parse.ambiguity_stripped):
            domain = d
            break

    cartridge = "reasoning"
    for pattern, c in _CARTRIDGE_MAP:
        if pattern.search(parse.ambiguity_stripped):
            cartridge = c
            break

    # Light UKG probe — look for matching node files without loading full graph
    ukg_refs: list[str] = []
    ukg_dir = ROOT / "03_VAULT" / "training" / "configs" / "memory"
    if ukg_dir.exists():
        for node_file in list(ukg_dir.glob("*.json"))[:3]:
            ukg_refs.append(node_file.stem)

    context_tags: list[str] = []
    for svc, port in [("saltare", 8085), ("excalibur", 8000), ("holotable", 3000)]:
        import socket
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.15):
                context_tags.append(f"{svc}:{port}:ONLINE")
        except OSError:
            context_tags.append(f"{svc}:{port}:OFFLINE")

    magnitude = min(1.0, parse.complexity + (0.1 if len(context_tags) > 2 else 0.0))

    return EnrichResult(
        domain=domain,
        cartridge_hint=cartridge,
        ukg_refs=ukg_refs,
        context_tags=context_tags,
        magnitude=magnitude,
    )


def _stage_compile(parse: ParseResult, enrich: EnrichResult) -> TitanPrompt:
    # Strip filler, compress to imperative dense directive
    directive = parse.ambiguity_stripped
    # Remove trailing punctuation softness
    directive = re.sub(r"[.!?]+$", "", directive).strip()
    # Title-case imperative if starts with verb pattern
    if parse.intent_type in ("BUILD", "FORGE", "HEAL", "AUDIT"):
        directive = directive[0].upper() + directive[1:] if directive else directive

    layer_map = {
        "BUILD": "L2", "FORGE": "L2", "HEAL": "L3",
        "AUDIT": "L6", "ROUTE": "L5", "RESEARCH": "L4", "QUERY": "L7",
    }
    mode_map = {
        "go/binary": "KINETIC", "rust/kinetic": "KINETIC",
        "python/api": "FORGE", "security": "SENTINEL",
        "voice/media": "ORACLE", "web/ui": "FORGE",
        "infra/cloud": "SWARM", "research": "ORACLE", "general": "FORGE",
    }

    return TitanPrompt(
        directive=directive,
        target_layer=layer_map.get(parse.intent_type, "L3"),
        execution_mode=mode_map.get(enrich.domain, "FORGE"),
        constraints_encoded=parse.constraints,
    )


def _stage_route(parse: ParseResult, enrich: EnrichResult) -> tuple[str, str, float, str]:
    try:
        from .soul_router import SoulRouter
        router = SoulRouter()
        decision = router.route(
            parse.ambiguity_stripped,
            velocity=parse.velocity,
            magnitude=enrich.magnitude,
            privacy=parse.privacy,
        )
        return decision.knight_id, decision.engine, decision.weight, decision.reason
    except Exception as e:
        return "sir_boris", "claude_code", 0.85, f"FALLBACK: soul_router unavailable ({e})"


def _stage_validate(
    parse: ParseResult,
    titan: TitanPrompt,
    enrich: EnrichResult,
    knight_id: str = "sir_boris",
) -> ValidationResult:
    issues: list[str] = []
    iron_gate = "CLEARED"

    # Iron Gate HITL triggers
    net_lines_estimate = max(10, int(parse.complexity * 80))
    requires_briefing = len(parse.entities) > 5 or parse.complexity > 0.7

    if net_lines_estimate > 50 or parse.complexity > 0.8:
        iron_gate = "HITL_REQUIRED"
        issues.append(f"complexity={parse.complexity:.2f} exceeds threshold — BriefingScript required")

    if parse.privacy >= 0.8 and titan.execution_mode != "KINETIC":
        issues.append("privacy flag raised — verify air-gapped routing")

    if not titan.directive.strip():
        issues.append("directive is empty after compilation")
        iron_gate = "BLOCKED"

    # SP-01 RBAC ACL check (Shatterpoint remediation)
    try:
        from .rbac_matrix import RBACMatrix
        rbac = RBACMatrix()
        rbac_ok, rbac_issues = rbac.check(
            knight_id, titan.execution_mode, enrich.domain, parse.complexity
        )
        if not rbac_ok:
            iron_gate = "BLOCKED"
            issues.extend(rbac_issues)
        elif rbac_issues:
            issues.extend(rbac_issues)
            if iron_gate == "CLEARED":
                iron_gate = "HITL_REQUIRED"
    except Exception as rbac_err:
        issues.append(f"RBAC matrix unavailable ({rbac_err}) — defaulting to HITL_REQUIRED")
        if iron_gate == "CLEARED":
            iron_gate = "HITL_REQUIRED"

    passed = iron_gate != "BLOCKED"

    return ValidationResult(
        passed=passed,
        issues=issues,
        iron_gate=iron_gate,
        net_lines_estimate=net_lines_estimate,
        requires_briefing=requires_briefing,
    )


# ---------------------------------------------------------------------------
# APEE v7.0 — Self-Triaging Stage (Pillar 1, EXCALIBUR_A_QNF)
# ---------------------------------------------------------------------------

# Destructive / shatterpoint signals (Ouroboros Adaptive Governance, v999 NLM).
_SHATTERPOINT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(rm\s+-rf|rmdir|del\s+/|format|drop\s+(table|database))\b", re.I), "destructive_autonomy"),
    (re.compile(r"\b(force\s*push|--force|reset\s+--hard)\b", re.I), "destructive_git"),
    (re.compile(r"\b(secret|credential|password|api[_\s-]?key|exfiltrat)\b", re.I), "secret_leakage"),
    (re.compile(r"\b(bypass|disable|skip)\s+(hitl|verification|ledger|security)\b", re.I), "verification_bypass"),
    (re.compile(r"\b(prod|production)\b.*\b(deploy|mutate|delete|drop)\b", re.I), "prod_mutation"),
]

# Intents that must be mathematically verified before execution (Z3, v999 NLM).
_Z3_PATTERNS = re.compile(
    r"\b(git\s+(patch|apply|merge|commit)|state\s+machine|pddl|workflow\s+merge|"
    r"\.shadow|rebase)\b", re.I,
)

# Lane assignment by intent_type + velocity.
_LANE_BY_INTENT: dict[str, str] = {
    "AUDIT": "CRITICAL", "FORGE": "HIGH", "BUILD": "HIGH",
    "HEAL": "NORMAL", "ROUTE": "NORMAL", "RESEARCH": "BACKGROUND", "QUERY": "NORMAL",
}

_CARTRIDGE_HINT_BY_DOMAIN: dict[str, str] = {
    "research": "ANT", "infra/cloud": "BEAVER", "rust/kinetic": "BEAVER",
    "go/binary": "BEAVER", "python/api": "SPIDER", "web/ui": "SPIDER",
    "security": "OCTOPUS",
}


def _stage_triage(parse: "ParseResult", enrich: "EnrichResult", knight_id: str):
    """APEE v7.0 self-triage. Computes risk_entropy and HITL tier from the
    parse/enrich signals. Returns a TriageScore (schema lives in factory_lane).

    Risk entropy thresholds (Ouroboros Adaptive Governance):
        < 0.15            -> AUTO
        0.15 .. 0.55      -> PROMPT
        > 0.55 / shatter  -> HUMAN_GATE
    """
    from .factory_lane import TriageScore

    text = parse.ambiguity_stripped.lower()

    # Shatterpoint detection
    shatterpoints: list[str] = []
    for pattern, label in _SHATTERPOINT_PATTERNS:
        if pattern.search(text) and label not in shatterpoints:
            shatterpoints.append(label)

    requires_z3 = bool(_Z3_PATTERNS.search(text))

    # Read-only intents (QUERY/RESEARCH with no destructive verbs) are inherently
    # low-risk regardless of token-surface complexity, so discount the complexity
    # contribution. The parser's "complexity" is really an entity-count proxy.
    read_only = parse.intent_type in ("QUERY", "RESEARCH") and not shatterpoints
    complexity_weight = 0.18 if read_only else 0.45

    # risk_entropy: weighted blend of complexity, privacy, shatterpoint pressure
    shatter_pressure = min(1.0, 0.4 * len(shatterpoints))
    risk_entropy = min(
        1.0,
        complexity_weight * parse.complexity + 0.35 * parse.privacy + shatter_pressure,
    )
    if requires_z3:
        risk_entropy = max(risk_entropy, 0.6)

    # HITL tier from entropy + hard overrides
    if shatterpoints or risk_entropy > 0.55 or requires_z3:
        hitl_tier = "HUMAN_GATE"
    elif risk_entropy >= 0.15:
        hitl_tier = "PROMPT"
    else:
        hitl_tier = "AUTO"

    # Lane: shatterpoints force CRITICAL
    if shatterpoints:
        lane = "CRITICAL"
    else:
        lane = _LANE_BY_INTENT.get(parse.intent_type, "NORMAL")
        if "velocity_high" in parse.constraints and lane == "BACKGROUND":
            lane = "NORMAL"

    reason_bits = [f"entropy={risk_entropy:.2f}"]
    if shatterpoints:
        reason_bits.append(f"shatter={shatterpoints}")
    if requires_z3:
        reason_bits.append("z3_required")

    cartridge = _CARTRIDGE_HINT_BY_DOMAIN.get(enrich.domain, "DEFAULT")

    return TriageScore(
        auto_dispatchable=(hitl_tier == "AUTO"),
        priority=lane,
        hitl_tier=hitl_tier,
        risk_entropy=round(risk_entropy, 3),
        risk_reason=" ".join(reason_bits),
        assigned_knight=knight_id,
        estimated_tokens=max(512, int(parse.complexity * 8192)),
        cost_ceiling_usd=0.0,  # 38 free models via CLIProxy OAuth
        shatterpoints_detected=shatterpoints,
        requires_z3_verification=requires_z3,
        cartridge_hint=cartridge,
    )


def _stage_colmad(raw_intent: str, triage) -> "object | None":
    """Stage 6.5 (P1-T02): for CRITICAL-lane or HUMAN_GATE intents, run the
    ColMAD 3-persona adversarial crucible before the proposal is allowed to
    proceed. Returns a CrucibleVerdict (or None for low-risk intents that do
    not warrant a debate). Failure to import/run ColMAD is non-fatal — the
    pipeline degrades gracefully to None.
    """
    is_high = triage.priority == "CRITICAL" or triage.hitl_tier == "HUMAN_GATE"
    if not is_high:
        return None
    try:
        from .colmad import ColMAD
        return ColMAD().crucible(raw_intent)
    except Exception:  # pragma: no cover - defensive: never break the gate
        return None


# ---------------------------------------------------------------------------
# AnyaGate — the sovereign entry/exit point
# ---------------------------------------------------------------------------

class AnyaGate:
    """
    ANYA_IS_THE_GATE — Titanium Law #11.

    Usage:
        gate = AnyaGate()
        result = gate.process("build a BubbleTea dashboard in Go")
        print(result.render())        # visible pipeline block
        # then execute against result.titan.directive
        # then call gate.validate_output(response_text) before returning to user
    """

    def process(self, raw_intent: str) -> APEEResult:
        t0 = time.perf_counter()

        raw_intent = _stage_rtk_strip(raw_intent)   # Stage 0: RTK noise strip
        parse   = _stage_parse(raw_intent)
        enrich  = _stage_enrich(parse)
        titan   = _stage_compile(parse, enrich)
        knight, engine, weight, reason = _stage_route(parse, enrich)
        triage_for_socrates = _stage_triage(parse, enrich, knight)
        validation = _stage_validate(parse, titan, enrich, knight_id=knight)

        # Stage 6.5 (P1-T02): ColMAD adversarial crucible for CRITICAL/HIGH intents
        colmad_verdict = _stage_colmad(raw_intent, triage_for_socrates)

        # Stage 7 (post-triage): SirSocrates Northstar examination for HIGH/CRITICAL
        _stage_socrates_full(raw_intent, triage_for_socrates.hitl_tier)

        ms = (time.perf_counter() - t0) * 1000

        return APEEResult(
            raw_intent=raw_intent,
            parse=parse,
            enrich=enrich,
            titan=titan,
            route_knight=knight,
            route_engine=engine,
            route_score=weight,
            route_reason=reason,
            validation=validation,
            pipeline_ms=ms,
            colmad_verdict=colmad_verdict,
        )

    def triage(self, raw_intent: str):
        """APEE v7.0 self-triage entry point. Returns a TriageScore without
        running the full compile/validate pipeline — used by the factory lane
        to assign priority and HITL tier. Additive to process(); does not
        replace it.
        """
        parse = _stage_parse(raw_intent)
        enrich = _stage_enrich(parse)
        knight, _engine, _weight, _reason = _stage_route(parse, enrich)
        return _stage_triage(parse, enrich, knight)

    def validate_output(self, response: str) -> tuple[bool, list[str]]:
        """Exit gate — validate a response before it leaves the system."""
        issues: list[str] = []
        if not response or not response.strip():
            issues.append("empty response — blocked at exit gate")
            return False, issues
        if len(response) < 10:
            issues.append("response suspiciously short")
        if re.search(r"\b(i don't know|i cannot|i'm not sure)\b", response, re.I):
            issues.append("response contains uncertainty markers — consider Merlin escalation")
        return len(issues) == 0, issues


class AnyaCompiler:
    """Ethereal Compiler (Layer 7) implementing Triple-QFT Protocol.

    P1-T06 note: this is NOT a duplicate of the APEE ``_stage_*`` pipeline. It is
    a deliberately lightweight compiler (renormalize/quantize/pedagogy/compile →
    Titan_Prompt glyph + confidence scalar) consumed by ``camelot_cli._run_task``
    for fast intent shaping. The APEE pipeline (AnyaGate.process) is the heavy
    governance path. The only true name collision is the unrelated
    ``01_KERNEL/titan/memory/compiler.AnyaCompiler`` in a different subsystem.
    """

    def __init__(self):
        self.anchor_tokens = {
            "build", "refactor", "create", "deploy", "audit", "fix",
            "scaffold", "status", "sync", "research", "blueprint", "precise",
            "ctx7"
        }

    def renormalize(self, intent: str) -> str:
        """Strip conversational noise and irrelevant operators (Phase: Physics)."""
        fillers = {
            "please", "can you", "i need to", "help me", "i want to",
            "would like to", "could you", "make sure to"
        }
        clean = intent.lower()
        for filler in fillers:
            clean = clean.replace(filler, "")

        # Remove extra punctuation and whitespace
        clean = re.sub(r'[^\w\s]', '', clean)
        return " ".join(clean.split())

    def quantize(self, intent: str) -> list[str]:
        """Identify Anchor Tokens for context compression (Phase: Engineering)."""
        words = set(intent.lower().split())
        found = words.intersection(self.anchor_tokens)
        return sorted(list(found))

    def pedagogy(self, intent: str) -> bool:
        """Check if the intent is ambiguous and needs clarification (Phase: Pedagogy)."""
        clean = self.renormalize(intent)
        words = clean.split()
        # Heuristic: < 2 words is usually ambiguous for a system command
        if len(words) < 2 and not any(w in self.anchor_tokens for w in words):
            return True
        return False

    def compile(self, raw_intent: str) -> tuple[str, float]:
        """Compile raw intent and return Titan Prompt + Confidence Scalar."""
        clean = self.renormalize(raw_intent)
        anchors = self.quantize(clean)

        # Calculate confidence scalar based on anchor presence
        score = 1.0 if anchors else 0.5
        if len(clean.split()) < 3 and not anchors:
            score = 0.3

        if not anchors:
            return clean, score

        # Format as a high-density Titan Prompt glyph
        prompt = f"⌖ Titan_Prompt | Intent: {clean} | ⌘ Anchors: {', '.join(anchors)}"
        return prompt, score
