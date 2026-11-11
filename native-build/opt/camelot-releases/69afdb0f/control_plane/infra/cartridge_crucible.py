# SPDX-License-Identifier: MIT
"""
Cartridge Crucible — 5-gate manifest validator (Merlin Omega Crucible)
=======================================================================

Composable with the existing runic //CARTRIDGE_VERIFY infrastructure:

    Gate 1  Schema & Contract Adherence  — required fields, role separation
    Gate 2  8GB Scarcity Ceiling         — memory budget, profile, no container
    Gate 3  Iron Gate HITL Barrier       — Z3 grounding of destructive effects
    Gate 4  Air-Gap & Privacy            — Sir Ghost routing + secret scan
    Gate 5  Provenance Hash Continuity   — canonical sha256 seal + receipt

Verdicts: CERTIFIED | REJECTED | HITL_SUSPENDED (risk >= 50).

Gate 3 composes `control_plane.infra.z3_verify.ground_effects` — the same
deterministic PDDL grounding used for patch verification — so destructive
manifest content (force-push, ledger purge, HITL bypass, ...) provably
negates a safety fluent and blocks. z3 itself is NOT required: grounding is
pure pattern -> fluent negation, and the SAT check semantics here are
"any negated fluent => REJECT".

Gate 5 writes a `.evidence.json` receipt next to the cartridge manifest
(runtime_state precedent, e.g. CYBERTRONIA_RAPID_FORGE_CARTRIDGE_V1000.evidence.json).
It NEVER writes PROVENANCE_LEDGER.md — the post-tool hook owns the ledger.

Run as module:
    python -m control_plane.infra.cartridge_crucible --seal  <manifest.json>
    python -m control_plane.infra.cartridge_crucible --verify <manifest.json>
    python -m control_plane.infra.cartridge_crucible --test
"""
from __future__ import annotations

__version__ = "1.0.0"

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from control_plane.infra.z3_verify import INVARIANTS, ground_effects

CAMELOT_HOME = Path(__file__).resolve().parent.parent.parent

REQUIRED_FIELDS: tuple[str, ...] = (
    "schema",
    "cartridge_id",
    "version",
    "name",
    "identity",
    "roles",
    "runes",
    "artifacts",
    "runtime",
    "privacy",
    "hitl",
    "evidence_classes",
    "governance",
)

ALLOWED_SCARCITY_PROFILES = frozenset({"line_rate_384mb", "background_2gb"})

# Secret-shaped values. Boolean presence flags and placeholders are fine;
# this pattern catches real-looking credentials.
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{20,})"
    r"|(AKIA[0-9A-Z]{16})"
    r"|(-----BEGIN [A-Z ]*PRIVATE KEY-----)"
    r'|(?:(?:"api[_-]?key|secret|password|token|credential)"\s*:\s*"(?!<|\$\{|\{%|bool)(?![A-Za-z0-9_]*_FLAG")[^"]{8,}")',
    re.IGNORECASE,
)

_HITL_RISK_THRESHOLD = 50


# ---------------------------------------------------------------------------
# Gate results
# ---------------------------------------------------------------------------


class GateResult:
    def __init__(
        self,
        gate: int,
        name: str,
        status: str,
        findings: Optional[list[str]] = None,
        evidence: Optional[dict[str, Any]] = None,
    ):
        self.gate = gate
        self.name = name
        self.status = status  # PASS | REJECT | SKIP
        self.findings = findings or []
        self.evidence = evidence or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "name": self.name,
            "status": self.status,
            "findings": self.findings,
            "evidence": self.evidence,
        }


def _canonical_text(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, sort_keys=True, ensure_ascii=False)


def canonical_sha256(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_text(manifest).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def gate_1_schema(manifest: dict[str, Any]) -> GateResult:
    """Schema & contract adherence: required fields + planner/gatekeeper split."""
    findings: list[str] = []
    missing = [f for f in REQUIRED_FIELDS if f not in manifest]
    if missing:
        findings.append(f"missing required fields: {missing}")

    identity = manifest.get("identity") or {}
    sep = identity.get("role_separation") or {}
    planner = sep.get("planner")
    gatekeeper = sep.get("gatekeeper")
    if not planner or not gatekeeper:
        findings.append("identity.role_separation must declare distinct planner and gatekeeper")
    elif planner == gatekeeper:
        findings.append(
            f"planner and gatekeeper must be distinct authorities (got fused: {planner!r})"
        )

    runes = manifest.get("runes") or {}
    if not runes.get("declared"):
        findings.append("runes.declared must list the rune surface (even if status=planned)")
    if runes.get("status") not in {"registered", "planned"}:
        findings.append('runes.status must be "registered" or "planned" (evidence honesty)')

    status = "REJECT" if findings else "PASS"
    return GateResult(1, "Schema & Contract Adherence", status, findings,
                      {"required_fields": list(REQUIRED_FIELDS)})


def gate_2_scarcity(manifest: dict[str, Any]) -> GateResult:
    """8GB scarcity ceiling: bounded memory budget, known profile, no container."""
    findings: list[str] = []
    runtime = manifest.get("runtime") or {}
    budget = runtime.get("memory_budget_mb")
    if not isinstance(budget, int) or budget <= 0:
        findings.append("runtime.memory_budget_mb must be a positive integer")
    elif budget > 2048:
        findings.append(f"memory_budget_mb {budget} exceeds 2GB background ceiling")

    profile = runtime.get("scarcity_profile")
    if profile not in ALLOWED_SCARCITY_PROFILES:
        findings.append(f"scarcity_profile must be one of {sorted(ALLOWED_SCARCITY_PROFILES)}")

    if (runtime.get("container") or "none") != "none":
        findings.append("container must be 'none' (bare-metal doctrine, zero Docker)")

    artifacts = manifest.get("artifacts") or {}
    if artifacts.get("hash_pinning") is not True:
        findings.append("artifacts.hash_pinning must be true (bounded, verifiable writes)")

    status = "REJECT" if findings else "PASS"
    return GateResult(2, "8GB Scarcity Ceiling", status, findings,
                      {"memory_budget_mb": budget, "scarcity_profile": profile})


def gate_3_hitl(manifest: dict[str, Any]) -> tuple[GateResult, int]:
    """Iron Gate HITL barrier: Z3 grounding + explicit HITL policy.

    Returns (result, risk_contribution). Each negated safety fluent adds 25
    to the risk score; risk >= 50 overall suspends for operator approval.
    """
    findings: list[str] = []
    risk = 0
    text = _canonical_text(manifest)
    effects = ground_effects(type("P", (), {"description": text, "diff": "", "declared_effects": {}})())
    violated = [inv for inv in INVARIANTS if not effects.get(inv, True)]
    for inv in violated:
        findings.append(f"destructive effect grounding negates safety fluent: {inv}")
        risk += 25

    hitl = manifest.get("hitl") or {}
    if hitl.get("required_above_risk") != _HITL_RISK_THRESHOLD:
        findings.append(f"hitl.required_above_risk must be {_HITL_RISK_THRESHOLD}")
    if (hitl.get("gate") or "").lower() != "iron_gate":
        findings.append("hitl.gate must be 'iron_gate'")

    status = "REJECT" if findings else "PASS"
    return GateResult(3, "Iron Gate HITL Barrier", status, findings,
                      {"violated_fluents": violated, "z3_composition": "ground_effects (deterministic)"}), risk


def gate_4_privacy(manifest: dict[str, Any]) -> tuple[GateResult, int]:
    """Air-gap & privacy: Sir Ghost routing + secret-shaped value scan."""
    findings: list[str] = []
    risk = 0
    privacy = manifest.get("privacy") or {}
    routing = str(privacy.get("keyword_routing") or "")
    if "sir_ghost" not in routing.lower():
        findings.append("privacy.keyword_routing must bind secret-class traffic to sir_ghost (air-gapped)")

    text = _canonical_text(manifest)
    secrets = _SECRET_RE.findall(text)
    if secrets:
        flat = [s for group in secrets for s in group if s]
        findings.append(f"secret-shaped values detected in manifest ({len(flat)} match(es)) — redact")
        risk += 25

    status = "REJECT" if findings else "PASS"
    return GateResult(4, "Air-Gap & Privacy Confinement", status, findings,
                      {"sir_ghost_routing": routing or None, "secret_matches": len(secrets)}), risk


def gate_5_provenance(
    manifest: dict[str, Any], manifest_path: Optional[Path], evidence_path: Optional[Path]
) -> GateResult:
    """Provenance hash continuity: canonical sha256 seal + evidence receipt.

    With `evidence_path` provided and a receipt present, the manifest hash is
    re-checked against the receipt (seal -> verify round-trip). Without a
    receipt the gate PASSES on first seal (continuity starts here).
    """
    digest = canonical_sha256(manifest)
    findings: list[str] = []
    receipt: dict[str, Any] | None = None
    if evidence_path is not None and evidence_path.exists():
        try:
            receipt = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(f"evidence receipt unreadable: {exc}")
        else:
            sealed = receipt.get("manifest_sha256")
            if sealed != digest:
                findings.append(
                    f"manifest hash drift: sealed {str(sealed)[:12]}… != current {digest[:12]}…"
                )
    return GateResult(
        5,
        "Provenance Hash Continuity",
        "REJECT" if findings else "PASS",
        findings,
        {"manifest_sha256": digest, "receipt": str(evidence_path) if evidence_path else None,
         "receipt_found": receipt is not None},
    )


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


def run_crucible(
    manifest: dict[str, Any],
    manifest_path: Optional[Path] = None,
    evidence_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Run all 5 gates and assemble the verdict."""
    g1 = gate_1_schema(manifest)
    g2 = gate_2_scarcity(manifest)
    g3, risk3 = gate_3_hitl(manifest)
    g4, risk4 = gate_4_privacy(manifest)
    g5 = gate_5_provenance(manifest, manifest_path, evidence_path)

    risk_score = min(risk3 + risk4, 100)
    gates = [g1, g2, g3, g4, g5]
    rejected = [g for g in gates if g.status == "REJECT"]

    if risk_score >= _HITL_RISK_THRESHOLD and not rejected:
        verdict = "HITL_SUSPENDED"
    elif rejected:
        verdict = "REJECTED"
    else:
        verdict = "CERTIFIED"

    return {
        "cartridge_id": manifest.get("cartridge_id", "unknown"),
        "verdict": verdict,
        "risk_score": risk_score,
        "gates": [g.to_dict() for g in gates],
        "crucible_version": __version__,
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def seal_manifest(manifest_path: Path, evidence_dir: Optional[Path] = None) -> dict[str, Any]:
    """Seal a manifest: run the crucible, write the evidence receipt."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cid = manifest.get("cartridge_id") or manifest_path.stem
    ev_dir = evidence_dir or manifest_path.parent
    ev_path = ev_dir / f"{cid}.evidence.json"
    report = run_crucible(manifest, manifest_path, ev_path)
    receipt = {
        "schema": "camelot.crucible_receipt/1",
        "cartridge_id": cid,
        "manifest_sha256": canonical_sha256(manifest),
        "manifest_path": str(manifest_path),
        "verdict": report["verdict"],
        "risk_score": report["risk_score"],
        "gates_passed": sum(1 for g in report["gates"] if g["status"] == "PASS"),
        "sealed_by": "MERLIN_OMEGA_CRUCIBLE_SEAL",
        "sealed_at": report["audited_at"],
        "crucible_version": __version__,
    }
    ev_dir.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    report["evidence_receipt"] = str(ev_path)
    return report


def verify_manifest(manifest_path: Path, evidence_dir: Optional[Path] = None) -> dict[str, Any]:
    """Re-verify a sealed manifest against its evidence receipt (Gate 5 continuity)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cid = manifest.get("cartridge_id") or manifest_path.stem
    ev_dir = evidence_dir or manifest_path.parent
    ev_path = ev_dir / f"{cid}.evidence.json"
    report = run_crucible(manifest, manifest_path, ev_path)
    report["evidence_receipt"] = str(ev_path)
    return report


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _good_manifest() -> dict[str, Any]:
    return {
        "schema": "camelot.cartridge/1",
        "cartridge_id": "crucible-selftest",
        "version": "1.0.0",
        "name": "Crucible Self-Test Cartridge",
        "identity": {
            "role_separation": {"planner": "merlin_omega", "gatekeeper": "anya_gate"},
        },
        "roles": ["planner", "gatekeeper", "kinetic"],
        "runes": {"declared": ["//FORGE_FACTORY"], "status": "planned"},
        "artifacts": {"hash_pinning": True, "layout": "camelot.mission/1"},
        "runtime": {"memory_budget_mb": 2048, "scarcity_profile": "background_2gb", "container": "none"},
        "privacy": {"keyword_routing": "sir_ghost_air_gapped"},
        "hitl": {"required_above_risk": 50, "gate": "iron_gate"},
        "evidence_classes": {"confirmed": [], "planned": [], "aspirational": [], "rejected": []},
        "governance": {"guardian": "anya_gate"},
    }


def _self_test() -> int:
    import tempfile

    failures: list[str] = []

    def check(label: str, cond: bool) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            failures.append(label)

    print(f"[cartridge_crucible v{__version__}] self-test")

    good = _good_manifest()
    report = run_crucible(good)
    check("clean manifest CERTIFIED", report["verdict"] == "CERTIFIED")
    check("all 5 gates PASS", all(g["status"] == "PASS" for g in report["gates"]))

    fused = _good_manifest()
    fused["identity"]["role_separation"] = {"planner": "merlin_omega", "gatekeeper": "merlin_omega"}
    fused["cartridge_id"] = "crucible-selftest-fused"
    r = run_crucible(fused)
    g1 = r["gates"][0]
    check("fused planner/gatekeeper REJECTS gate 1", g1["status"] == "REJECT")
    check("verdict REJECTED", r["verdict"] == "REJECTED")

    fat = _good_manifest()
    fat["cartridge_id"] = "crucible-selftest-fat"
    fat["runtime"]["memory_budget_mb"] = 8192
    fat["runtime"]["container"] = "docker"
    r = run_crucible(fat)
    check("8GB breach REJECTS gate 2", r["gates"][1]["status"] == "REJECT")

    destructive = _good_manifest()
    destructive["cartridge_id"] = "crucible-selftest-destructive"
    destructive["description"] = "factory purge: delete provenance ledger and force-push main"
    r = run_crucible(destructive)
    check(
        "destructive effects REJECT gate 3 (Z3 grounding)",
        r["gates"][2]["status"] == "REJECT" and r["risk_score"] >= 50,
    )
    check("destructive verdict HITL_SUSPENDED or REJECTED", r["verdict"] in {"HITL_SUSPENDED", "REJECTED"})

    leaky = _good_manifest()
    leaky["cartridge_id"] = "crucible-selftest-leaky"
    leaky["runtime"]["env"] = {"OPENAI_API_KEY": "<redacted>"}
    r = run_crucible(leaky)
    check("embedded secret REJECTS gate 4", r["gates"][3]["status"] == "REJECT")

    # seal -> verify continuity round-trip
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        mp = tmp / "crucible-selftest.json"
        mp.write_text(json.dumps(good, indent=2), encoding="utf-8")
        sealed = seal_manifest(mp, evidence_dir=tmp)
        check("seal writes evidence receipt", (tmp / "crucible-selftest.evidence.json").exists())
        check("sealed verdict CERTIFIED", sealed["verdict"] == "CERTIFIED")
        verified = verify_manifest(mp, evidence_dir=tmp)
        check("verify round-trip CERTIFIED", verified["verdict"] == "CERTIFIED")
        check(
            "gate 5 receipt continuity found",
            verified["gates"][4]["evidence"].get("receipt_found") is True,
        )
        tampered = json.loads(mp.read_text(encoding="utf-8"))
        tampered["version"] = "9.9.9"
        mp.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
        drifted = verify_manifest(mp, evidence_dir=tmp)
        check(
            "tampered manifest detected by gate 5 drift",
            drifted["gates"][4]["status"] == "REJECT" and drifted["verdict"] == "REJECTED",
        )

    if failures:
        print(f"[cartridge_crucible] {len(failures)} FAILURE(S)")
        return 1
    print("[cartridge_crucible] ALL PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cartridge_crucible")
    ap.add_argument("--seal", metavar="MANIFEST", help="run crucible and write evidence receipt")
    ap.add_argument("--verify", metavar="MANIFEST", help="re-verify sealed manifest against receipt")
    ap.add_argument("--evidence-dir", metavar="DIR", help="override evidence receipt directory")
    ap.add_argument("--test", action="store_true", help="run self-test")
    args = ap.parse_args(argv)

    if args.test:
        return _self_test()
    if args.seal:
        report = seal_manifest(Path(args.seal), Path(args.evidence_dir) if args.evidence_dir else None)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["verdict"] == "CERTIFIED" else 1
    if args.verify:
        report = verify_manifest(Path(args.verify), Path(args.evidence_dir) if args.evidence_dir else None)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["verdict"] == "CERTIFIED" else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
