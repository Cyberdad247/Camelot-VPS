# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Sentinel ASM — CAMELOT-OS Attack Surface Management & Continuous Scanner
=======================================================================
A dependency-light, CI-friendly security scanner for the Camelot-OS monorepo.

Design goals
------------
* **Stdlib-only core.** No pip install required to run the baseline scan. Optional
  external tools (pip-audit, npm audit, gitleaks) are used if present, skipped if not.
* **Grounded in real findings.** Every detector here maps to a concrete weakness
  observed in this repo, not a generic checklist:
      - Live secrets concentrated in a single plaintext .env (SECRET_EXPOSURE)
      - Services binding 0.0.0.0 on the LAN (OPEN_BIND)
      - Cartridge manifests trusted without signature verification (UNSIGNED_MANIFEST)
      - Dead governance fields: denied_operations / HITL_required never enforced
      - Injection sinks: exec()/shell=True/os.system (INJECTION_SINK)
      - Web-foraged / cartridge text flowing into agent context (PROMPT_INJECTION)
* **Adoptable.** Baseline file suppresses known/accepted findings so CI stays green
  until *new* surface appears. Exit code is non-zero only for NEW findings at or
  above --fail-on severity.

Usage
-----
    python -m control_plane.sentinel_asm scan                 # full scan, human output
    python -m control_plane.sentinel_asm scan --json          # machine-readable
    python -m control_plane.sentinel_asm scan --fail-on high  # CI gate
    python -m control_plane.sentinel_asm baseline              # snapshot current findings as accepted
    python -m control_plane.sentinel_asm gate-text <file>      # scan a blob for prompt-injection before it enters context

Wire into CI (verify_os.yml) as a job, and/or into .pre-commit-config.yaml as a
local hook. See the emit_ci_snippets() helper at the bottom.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

__version__ = "1.0.0"

# ── Severity model ────────────────────────────────────────────────────────────
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class Finding:
    detector: str
    severity: str
    title: str
    path: str
    line: int = 0
    evidence: str = ""
    remediation: str = ""

    def fingerprint(self) -> str:
        """Stable ID for baselining — independent of line drift where possible."""
        h = hashlib.sha256()
        h.update(f"{self.detector}|{self.path}|{self.title}|{self.evidence[:80]}".encode("utf-8", "replace"))
        return h.hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint()
        return d


# ── Scan configuration ────────────────────────────────────────────────────────
# Directories we never descend into: vendored code, virtualenvs, caches, archives.
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".ruff_cache",
    ".cache", ".mypy_cache", ".pytest_cache", "99_ARCHIVE", "99_HISTORY",
    ".worktrees", ".claude", "build", "dist", "target",
    # vendored engines with their own supply chain — audit separately, not here
    "crawl4ai", "LLM-Apps-Ref",
}
TEXT_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".yml", ".yaml", ".json",
             ".env", ".sh", ".ps1", ".toml", ".cfg", ".ini", ".md", ".txt"}
MAX_FILE_BYTES = 2_000_000


# ── Secret detectors ──────────────────────────────────────────────────────────
# High-precision provider patterns (low false-positive).
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI/proj key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenRouter key", re.compile(r"sk-or-[A-Za-z0-9_-]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[posru]_[A-Za-z0-9]{36,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Vercel token", re.compile(r"\b[A-Za-z0-9]{24}\b(?=.*VERCEL)", re.IGNORECASE)),
    ("Generic bearer/secret assignment",
     re.compile(r"(?i)(api[_-]?key|secret|password|passwd|token|auth[_-]?token)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
]
# Assignment shape used for entropy fallback. The NAME must end in a secret-ish
# word (so "sort_keys"/"keywords" don't match) and the VALUE must be quoted, so we
# only ever consider string literals — never bare code expressions like Ed25519Key().
ASSIGN_RE = re.compile(
    r"""(?i)\b([A-Z][A-Z0-9]*(?:[_-][A-Z0-9]+)*(?:_?(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|AUTH[_-]?TOKEN)))\s*[:=]\s*['"]([^'"\s]{16,})['"]"""
)
# A real credential value is a compact high-entropy token, not a code fragment.
SECRET_VALUE_RE = re.compile(r"^[A-Za-z0-9+/=_.\-]{16,}$")
CODE_TOKENS_RE = re.compile(r"(\(|\)|\[|\]|\bself\b|\bTrue\b|\bFalse\b|\bNone\b|\{|\+|\bos\.|\bget\b)")
PLACEHOLDER_RE = re.compile(r"(?i)(REDACTED|EXAMPLE|CHANGE[_-]?ME|YOUR[_-]|xxx+|<[^>]+>|\$\{|\.\.\.|placeholder|dummy|test[_-]?key|000000)")


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


# ── Injection sinks ───────────────────────────────────────────────────────────
SINK_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("eval() on dynamic input", "high", re.compile(r"\beval\s*\(")),
    ("exec() of compiled/dynamic code", "high", re.compile(r"\bexec\s*\(")),
    ("subprocess shell=True", "high", re.compile(r"shell\s*=\s*True")),
    ("os.system()", "high", re.compile(r"\bos\.system\s*\(")),
    ("pickle.loads (deserialization)", "medium", re.compile(r"pickle\.loads?\s*\(")),
    ("yaml.load without SafeLoader", "medium", re.compile(r"yaml\.load\s*\((?!.*Safe)")),
]
# f-string / concatenation flowing into a command is the dangerous variant.
DYNAMIC_CMD_RE = re.compile(r"(subprocess\.(run|call|Popen)|os\.system)\s*\(\s*f?['\"].*\{|(subprocess\.(run|call|Popen)|os\.system)\s*\(\s*[a-zA-Z_]\w*\s*\+")

# ── Network bind ──────────────────────────────────────────────────────────────
OPEN_BIND_RE = re.compile(r"""(?:host|server_name)\s*=\s*['"]0\.0\.0\.0['"]|--host['"]?\s*,?\s*['"]?0\.0\.0\.0|0\.0\.0\.0['"]?\s*[,)]""")

# ── Prompt-injection heuristics (for foraged/cartridge text gating) ───────────
PROMPT_INJECTION_SIGNATURES: list[tuple[str, re.Pattern[str]]] = [
    ("instruction override", re.compile(r"(?i)ignore (all|any|previous|prior|the above) (instructions|prompts|context)")),
    ("role hijack", re.compile(r"(?i)you are now|from now on,? you|new (system )?(prompt|instructions|role)")),
    ("exfiltration ask", re.compile(r"(?i)(print|reveal|show|repeat|leak|send).{0,30}(system prompt|api[_ ]?key|secret|\.env|credentials|token)")),
    ("tool/command coercion", re.compile(r"(?i)(run|execute|call|invoke).{0,20}(command|shell|curl|wget|rm -rf|subprocess)")),
    ("hidden-channel markers", re.compile(r"(?i)<\|?(system|im_start|endoftext)\|?>|\[INST\]|###\s*system")),
    ("data-URL / smuggle", re.compile(r"(?i)data:text/[^;]+;base64,|javascript:")),
]


class SentinelASM:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.findings: list[Finding] = []

    # ---- file walking ---------------------------------------------------------
    def _iter_files(self) -> Iterable[Path]:
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".ruff")]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() in TEXT_EXTS or p.name.startswith(".env"):
                    try:
                        if p.stat().st_size <= MAX_FILE_BYTES:
                            yield p
                    except OSError:
                        continue

    def _rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    def _read_lines(self, p: Path) -> list[str]:
        try:
            return p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    # ---- detectors ------------------------------------------------------------
    def scan_secrets(self) -> None:
        """Detect exposed credentials AND verify .env files are git-ignored."""
        tracked = self._git_tracked_files()
        for p in self._iter_files():
            rel = self._rel(p)
            is_env = p.name.startswith(".env")
            is_example = "example" in p.name or "template" in p.name or "sample" in p.name

            # A committed .env (not an example) is critical regardless of contents.
            if is_env and not is_example and rel in tracked:
                self.add(Finding(
                    "secret", "critical",
                    "Environment file with live secrets is tracked by git",
                    rel, 0, ".env is committed",
                    "git rm --cached this file, rotate every key it contained, add to .gitignore.",
                ))

            lines = self._read_lines(p)
            for i, line in enumerate(lines, 1):
                if PLACEHOLDER_RE.search(line):
                    continue
                for label, pat in SECRET_PATTERNS:
                    m = pat.search(line)
                    if m:
                        # Only critical if it lands in a tracked, non-example file.
                        sev = "critical" if (rel in tracked and not is_example) else "high"
                        self.add(Finding(
                            "secret", sev, f"Possible {label} in source",
                            rel, i, self._redact(m.group(0)),
                            "Move to a secret manager; rotate immediately if this file is or was committed.",
                        ))
                        break
                else:
                    # entropy fallback on KEY=VALUE shapes
                    am = ASSIGN_RE.search(line)
                    if am and not is_example:
                        val = am.group(2)
                        looks_like_token = bool(SECRET_VALUE_RE.match(val)) and not CODE_TOKENS_RE.search(val)
                        if looks_like_token and shannon_entropy(val) >= 4.0 and len(val) >= 24:
                            sev = "high" if rel in tracked else "medium"
                            self.add(Finding(
                                "secret", sev,
                                f"High-entropy value assigned to '{am.group(1)}'",
                                rel, i, self._redact(val),
                                "Confirm this is not a live credential; if it is, vault + rotate.",
                            ))

    def scan_open_binds(self) -> None:
        for p in self._iter_files():
            if p.suffix.lower() != ".py":
                continue
            for i, line in enumerate(self._read_lines(p), 1):
                if line.lstrip().startswith("#"):
                    continue
                if OPEN_BIND_RE.search(line):
                    self.add(Finding(
                        "open_bind", "high",
                        "Service binds 0.0.0.0 (exposed on all interfaces)",
                        self._rel(p), i, line.strip()[:120],
                        "Bind 127.0.0.1 for local-only services; front LAN/public services with auth + TLS "
                        "and put them behind a firewall/allowlist. Never 0.0.0.0 without an auth layer.",
                    ))

    def scan_injection_sinks(self) -> None:
        for p in self._iter_files():
            if p.suffix.lower() != ".py":
                continue
            rel = self._rel(p)
            for i, line in enumerate(self._read_lines(p), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                for title, sev, pat in SINK_PATTERNS:
                    if pat.search(line):
                        dynamic = bool(DYNAMIC_CMD_RE.search(line))
                        eff = "high" if dynamic else sev
                        self.add(Finding(
                            "injection_sink", eff, title, rel, i, stripped[:120],
                            "Avoid the sink; if unavoidable, use list-form subprocess with shell=False, "
                            "validate/allowlist inputs, and never interpolate untrusted data into the command.",
                        ))
                        break

    def scan_manifest_trust(self) -> None:
        """
        The cartridge sandbox enforces allowed_tools but never verifies manifest.signature
        and ignores denied_operations / HITL_required. Flag that trust gap wherever a
        CartridgeManifest is constructed or run without a signature-verification call.
        """
        verifies_signature = re.compile(r"verify_signature|_verify_signature|check_signature")
        constructs = re.compile(r"CartridgeManifest\s*\(")
        runs = re.compile(r"run_cartridge_tool\s*\(")
        reads_denied = re.compile(r"denied_operations")
        reads_hitl = re.compile(r"HITL_required")
        for p in self._iter_files():
            if p.suffix.lower() != ".py" or "test" in p.name:
                continue
            rel = self._rel(p)
            text = "\n".join(self._read_lines(p))
            if runs.search(text) or "_check_governance" in text:
                if not verifies_signature.search(text):
                    self.add(Finding(
                        "manifest_trust", "high",
                        "Cartridge executed without manifest signature verification",
                        rel, 0, "run_cartridge_tool / _check_governance present, no signature check",
                        "Verify manifest.signature (HMAC or asymmetric) against a trusted key BEFORE honoring "
                        "its allowed_tools. An unsigned manifest with allowed_tools=['*'] bypasses the gate.",
                    ))
                if not reads_denied.search(text):
                    self.add(Finding(
                        "manifest_trust", "medium",
                        "GovernancePolicy.denied_operations is never enforced",
                        rel, 0, "denied_operations declared in schema but not read at execution",
                        "Add a deny-list check in _check_governance (deny wins over allow).",
                    ))
                if not reads_hitl.search(text):
                    self.add(Finding(
                        "manifest_trust", "medium",
                        "GovernancePolicy.HITL_required is never enforced",
                        rel, 0, "HITL_required declared but no approval gate on execution path",
                        "Route HITL_required=True cartridges through the Sovereign Commander approval gate.",
                    ))

    def scan_ci_workflows(self) -> None:
        wf_dir = self.root / ".github" / "workflows"
        if not wf_dir.is_dir():
            return
        for p in wf_dir.glob("*.y*ml"):
            lines = self._read_lines(p)
            text = "\n".join(lines)
            rel = self._rel(p)
            if "pull_request_target" in text:
                self.add(Finding(
                    "ci", "high", "pull_request_target grants secrets to fork PRs",
                    rel, 0, "pull_request_target",
                    "Prefer pull_request (secrets withheld from forks). If pull_request_target is required, "
                    "never checkout/run untrusted PR head code with secrets in scope.",
                ))
            for i, line in enumerate(lines, 1):
                # untrusted expansion into a run/script body
                if re.search(r"\$\{\{\s*(github\.event\.(issue|pull_request|comment)|steps\.\w+\.outputs)", line) \
                        and ("script:" in text or "run:" in line):
                    self.add(Finding(
                        "ci", "medium", "Untrusted GitHub context interpolated into script body",
                        rel, i, line.strip()[:120],
                        "Pass values via env: and reference $VAR, don't inline ${{ }} into shell/JS bodies.",
                    ))

    def scan_dependencies(self) -> None:
        """Shell out to auditors only if installed; otherwise emit an advisory."""
        ran_any = False
        if shutil.which("pip-audit"):
            ran_any = True
            self._run_pip_audit()
        if (self.root / "package.json").exists() and shutil.which("npm"):
            ran_any = True
            self._run_npm_audit()
        if not ran_any:
            self.add(Finding(
                "dependency", "info",
                "No dependency auditor available (pip-audit / npm not found)",
                ".", 0, "",
                "pip install pip-audit; run in CI so new CVEs surface continuously.",
            ))

    def _run_pip_audit(self) -> None:
        try:
            out = subprocess.run(["pip-audit", "-f", "json"], capture_output=True,
                                 text=True, timeout=180, cwd=self.root)
            data = json.loads(out.stdout or "{}")
            for dep in data.get("dependencies", []):
                for v in dep.get("vulns", []):
                    self.add(Finding(
                        "dependency", "high",
                        f"Vulnerable dependency {dep.get('name')} {dep.get('version')}: {v.get('id')}",
                        "requirements", 0, v.get("description", "")[:120],
                        f"Upgrade to {', '.join(v.get('fix_versions', [])) or 'a patched version'}.",
                    ))
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

    def _run_npm_audit(self) -> None:
        try:
            out = subprocess.run(["npm", "audit", "--json"], capture_output=True,
                                 text=True, timeout=180, cwd=self.root, shell=False)
            data = json.loads(out.stdout or "{}")
            for name, v in (data.get("vulnerabilities") or {}).items():
                sev = v.get("severity", "medium")
                sev = sev if sev in SEVERITY_ORDER else "medium"
                self.add(Finding(
                    "dependency", sev, f"npm advisory: {name} ({v.get('severity')})",
                    "package.json", 0, "", "Run `npm audit fix` or upgrade the dependency.",
                ))
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass

    # ---- prompt-injection gate (callable at runtime, not just CI) -------------
    @staticmethod
    def gate_text(blob: str) -> list[Finding]:
        """
        Screen a text blob (web-foraged content, cartridge doc, tool output) for
        prompt-injection before it enters an agent's context window. Return
        findings; caller decides to strip, quarantine, or require HITL.
        """
        out: list[Finding] = []
        for i, line in enumerate(blob.splitlines(), 1):
            for label, pat in PROMPT_INJECTION_SIGNATURES:
                if pat.search(line):
                    out.append(Finding(
                        "prompt_injection", "high", f"Prompt-injection signature: {label}",
                        "<text>", i, line.strip()[:120],
                        "Do not pass verbatim into a privileged context. Wrap in a data-only delimiter, "
                        "strip instruction-like content, or escalate to HITL.",
                    ))
        return out

    # ---- helpers --------------------------------------------------------------
    def _git_tracked_files(self) -> set[str]:
        try:
            out = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                                 timeout=60, cwd=self.root, shell=False)
            return set(out.stdout.replace("\\", "/").splitlines())
        except (subprocess.SubprocessError, OSError):
            return set()

    @staticmethod
    def _redact(s: str) -> str:
        s = s.strip()
        if len(s) <= 8:
            return "*" * len(s)
        return f"{s[:4]}…{s[-2:]} (len={len(s)})"

    # ---- orchestration --------------------------------------------------------
    def run_all(self) -> list[Finding]:
        self.scan_secrets()
        self.scan_open_binds()
        self.scan_injection_sinks()
        self.scan_manifest_trust()
        self.scan_ci_workflows()
        self.scan_dependencies()
        self.findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 0), reverse=True)
        return self.findings


# ── Baseline (accepted findings) ──────────────────────────────────────────────
BASELINE_PATH = Path(".sentinel_baseline.json")


def load_baseline(root: Path) -> set[str]:
    p = root / BASELINE_PATH
    if p.exists():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def write_baseline(root: Path, findings: list[Finding]) -> None:
    fps = sorted({f.fingerprint() for f in findings})
    (root / BASELINE_PATH).write_text(json.dumps(fps, indent=2), encoding="utf-8")


# ── Reporting ─────────────────────────────────────────────────────────────────
_SEV_ICON = {"critical": "🟥", "high": "🟧", "medium": "🟨", "low": "🟦", "info": "⬜"}


def print_report(findings: list[Finding], baseline: set[str]) -> None:
    new = [f for f in findings if f.fingerprint() not in baseline]
    known = len(findings) - len(new)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    print(f"\nSentinel ASM v{__version__} — {len(findings)} findings "
          f"({len(new)} new, {known} baselined)")
    print("  " + "  ".join(f"{_SEV_ICON.get(s,'')} {s}:{counts.get(s,0)}"
                           for s in ("critical", "high", "medium", "low", "info")))
    print("─" * 72)
    for f in findings:
        tag = "NEW" if f.fingerprint() not in baseline else "   "
        loc = f"{f.path}:{f.line}" if f.line else f.path
        print(f"{_SEV_ICON.get(f.severity,'')} [{tag}] {f.severity.upper():8s} {f.title}")
        print(f"          {loc}")
        if f.evidence:
            print(f"          ↳ {f.evidence}")
        if f.remediation:
            print(f"          ⚑ {f.remediation}")
    print("─" * 72)


def emit_ci_snippets() -> None:
    print("""
# ── verify_os.yml job ────────────────────────────────────────────
  sentinel-asm:
    name: Attack Surface Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pip-audit          # optional but recommended
      - run: python -m control_plane.sentinel_asm scan --fail-on high

# ── .pre-commit-config.yaml local hook ───────────────────────────
  - repo: local
    hooks:
      - id: sentinel-asm
        name: Sentinel ASM secret/bind scan
        entry: python -m control_plane.sentinel_asm scan --fail-on critical
        language: system
        pass_filenames: false
""")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="sentinel_asm", description="Camelot-OS attack surface scanner")
    sub = ap.add_subparsers(dest="cmd")

    sp = sub.add_parser("scan", help="run all detectors")
    sp.add_argument("--root", default=".", help="repo root to scan")
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.add_argument("--fail-on", default="none",
                    choices=["none", "info", "low", "medium", "high", "critical"],
                    help="exit non-zero if a NEW finding at/above this severity exists")

    bp = sub.add_parser("baseline", help="snapshot current findings as accepted")
    bp.add_argument("--root", default=".")

    gp = sub.add_parser("gate-text", help="screen a text file for prompt injection")
    gp.add_argument("file")

    sub.add_parser("ci-snippets", help="print CI / pre-commit wiring")

    args = ap.parse_args(argv)

    if args.cmd == "ci-snippets":
        emit_ci_snippets()
        return 0

    if args.cmd == "gate-text":
        blob = Path(args.file).read_text(encoding="utf-8", errors="replace")
        fs = SentinelASM.gate_text(blob)
        print(json.dumps([f.to_dict() for f in fs], indent=2))
        return 1 if fs else 0

    if args.cmd == "baseline":
        root = Path(args.root)
        findings = SentinelASM(root).run_all()
        write_baseline(root, findings)
        print(f"Baselined {len(findings)} findings → {root / BASELINE_PATH}")
        return 0

    if args.cmd == "scan":
        root = Path(args.root)
        scanner = SentinelASM(root)
        findings = scanner.run_all()
        baseline = load_baseline(root)
        new = [f for f in findings if f.fingerprint() not in baseline]

        if args.json:
            print(json.dumps({
                "version": __version__,
                "total": len(findings),
                "new": len(new),
                "findings": [f.to_dict() for f in findings],
            }, indent=2))
        else:
            print_report(findings, baseline)

        if args.fail_on != "none":
            threshold = SEVERITY_ORDER[args.fail_on]
            worst_new = max((SEVERITY_ORDER.get(f.severity, 0) for f in new), default=-1)
            if worst_new >= threshold:
                if not args.json:
                    print(f"\n✗ FAIL: new finding at/above '{args.fail_on}'. "
                          f"Fix, or accept via `sentinel_asm baseline`.")
                return 1
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
