# SPDX-License-Identifier: MIT

"""Lady M (Lady Mnemosyne) — Squire Swarm Governance Engine
Implements SQUIRE_MERGE, SQUIRE_PURGE, SQUIRE_TRIAGE, SQUIRE_BRIEF.
Lady M commands all 35 knights and dispatches research briefings.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import smtplib
import subprocess
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
import sys

# Connect to KERNEL for Cloudbrain
CAMELOT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(CAMELOT_ROOT / "01_KERNEL"))
try:
    from memory.cloudbrain_connector import CloudBrainConnector
except ImportError:
    CloudBrainConnector = None

try:
    from infra.knight_registry import LIBRARIAN_REGISTRY
except ImportError:
    LIBRARIAN_REGISTRY = None

LOG = logging.getLogger("lady_m")
LEDGER       = CAMELOT_ROOT / "PROVENANCE_LEDGER.md"
HARNESS_Q    = CAMELOT_ROOT / "logs" / "harness_queue.jsonl"
MISSIONS     = CAMELOT_ROOT / "03_VAULT" / "Missions"
BRIEFING_DIR = CAMELOT_ROOT / "logs" / "briefings"
BRIEFING_DIR.mkdir(parents=True, exist_ok=True)

# ── Governance config ─────────────────────────────────────────────────────────
SENTINEL_EMAIL = os.getenv("CAMELOT_BRIEFING_EMAIL", "vizion711@gmail.com")
SMTP_HOST      = os.getenv("CAMELOT_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("CAMELOT_SMTP_PORT", "465"))
SMTP_USER      = os.getenv("CAMELOT_SMTP_USER", "")
SMTP_PASS      = os.getenv("CAMELOT_SMTP_PASS", "")

RISK_THRESHOLD = int(os.getenv("CAMELOT_RISK_THRESHOLD", "50"))


@dataclass
class SquireReport:
    path: str
    risk_score: int
    secrets: list[str]
    dead_files: list[str]
    recommendations: list[str]
    sha256: str = field(default="")

    def __post_init__(self):
        raw = json.dumps({"p": self.path, "r": self.risk_score, "s": self.secrets})
        self.sha256 = hashlib.sha256(raw.encode()).hexdigest()[:12]


# ── SQUIRE_TRIAGE ─────────────────────────────────────────────────────────────
class SquireTriage:
    """L0 fast scan: count files, detect secrets, measure entropy drift."""

    SECRET_PATTERNS = [
        re.compile(r"sk-ant-[a-zA-Z0-9\-_]{20,}"),
        re.compile(r"sk-[a-zA-Z0-9]{32,}"),
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]"),
        re.compile(r"(?i)(?:api[_-]?key|bearer|token|password|passwd|secret)\s*[=:]\s*['\"][A-Za-z0-9+/\-_]{24,}['\"]"),
        re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    ]

    def run(self, scan_path: Path = CAMELOT_ROOT) -> SquireReport:
        LOG.info("[TRIAGE] Scanning %s", scan_path)
        risk   = 0
        found_secrets: list[str] = []
        dead:   list[str]        = []
        recs:   list[str]        = []

        ignore_dirs = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".ruff_cache", "target", ".secrets_backup"}
        
        for root, dirs, files in os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                fp = Path(root) / file

                # Secret scan with streaming line-by-line inspection to prevent MemoryError
                if fp.suffix in (".exe", ".dll", ".so", ".dylib", ".bin", ".zip", ".tar", ".gz", ".7z", ".png", ".jpg", ".jpeg", ".ico", ".pdf", ".db", ".sqlite", ".rdb", ".lock", ".log"):
                    continue

                try:
                    stat = fp.stat()
                    if stat.st_size > 512 * 1024:  # Skip files > 512KB from deep secret scan
                        continue
                    
                    found_in_file = False
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            if "boolean" in line.lower() or "dummy" in line.lower() or "example" in line.lower():
                                continue
                            for pat in self.SECRET_PATTERNS:
                                m = pat.search(line)
                                if m:
                                    found_secrets.append(f"{fp.name}:{pat.pattern[:15]}")
                                    risk += 25
                                    found_in_file = True
                                    break
                            if found_in_file:
                                break
                except OSError:
                    continue

                # Dead asset detection
                if fp.suffix in (".pyc", ".cache", ".bak", ".tmp") and stat.st_size == 0:
                    dead.append(str(fp))
                    risk += 5

        if risk >= RISK_THRESHOLD:
            recs.append("HITL gate triggered: review secret disclosures before proceeding.")
        if dead:
            recs.append(f"Run SQUIRE_PURGE to remove {len(dead)} dead artifacts.")

        report = SquireReport(
            path=str(scan_path),
            risk_score=min(risk, 100),
            secrets=found_secrets[:10],
            dead_files=dead[:20],
            recommendations=recs,
        )
        LOG.info("[TRIAGE] Risk=%d, Secrets=%d", report.risk_score, len(found_secrets))
        return report


# ── SQUIRE_PURGE ─────────────────────────────────────────────────────────────
class SquirePurge:
    """RTK Scythe: delete dead files; pull codebase toward zero-entropy asymptote."""

    PURGE_EXTENSIONS = {".pyc", ".bak", ".tmp", ".cache"}
    PURGE_DIRS       = {"__pycache__", ".pytest_cache"}

    def run(self, dry_run: bool = False) -> list[str]:
        purged: list[str] = []
        ignore_dirs = {".git", ".venv", "node_modules", "target"}
        for root, dirs, files in os.walk(CAMELOT_ROOT):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                fp = Path(root) / file
                if fp.suffix in self.PURGE_EXTENSIONS or fp.parent.name in self.PURGE_DIRS:
                    if not dry_run:
                        fp.unlink(missing_ok=True)
                    purged.append(str(fp))

        LOG.info("[PURGE] %s %d artifacts", "DRY" if dry_run else "DELETED", len(purged))
        return purged


# ── SQUIRE_MERGE ──────────────────────────────────────────────────────────────
class SquireMerge:
    """Integrate staged foreign repos from .camelot/vault/staging/ after audit."""

    STAGING = CAMELOT_ROOT / ".camelot" / "vault" / "staging"

    def list_staged(self) -> list[Path]:
        if not self.STAGING.exists():
            return []
        return [p for p in self.STAGING.iterdir() if p.is_dir()]

    def merge(self, repo_name: str, triage_report: SquireReport) -> dict[str, Any]:
        if triage_report.risk_score >= RISK_THRESHOLD or triage_report.secrets:
            return {"status": "BLOCKED", "reason": "HITL gate triggered — review required."}

        source = self.STAGING / repo_name
        target = CAMELOT_ROOT / "04_KINETIC" / repo_name
        if not source.exists():
            return {"status": "ERROR", "reason": f"{source} not found."}

        target.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["robocopy", str(source), str(target), "/E", "/NFL", "/NDL"],
            capture_output=True, text=True, check=False
        )
        LOG.info("[MERGE] %s -> %s (rc=%d)", source, target, result.returncode)
        return {"status": "MERGED", "path": str(target), "rc": result.returncode}


# ── SQUIRE_BRIEF (Lady M daily briefing) ─────────────────────────────────────
class SquireBrief:
    """Compile a sovereign daily briefing digest and send it to the sentinel email."""

    def compile(self, triage: SquireReport | None = None) -> str:
        pending = 0
        try:
            lines   = HARNESS_Q.read_text(encoding="utf-8").splitlines()
            pending = sum(1 for l in lines if '"status":"pending"' in l)
        except OSError:
            pass

        now  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        body = textwrap.dedent(f"""\
            ╔══════════════════════════════════════╗
            ║   CAMELOT-OS DAILY SOVEREIGN BRIEF   ║
            ╚══════════════════════════════════════╝
            Generated: {now}

            ── SYSTEM STATUS ────────────────────────
            Queue Pending       : {pending}
            Ledger              : {LEDGER.name} ({LEDGER.stat().st_size if LEDGER.exists() else 'missing'} bytes)
        """)

        if triage:
            body += textwrap.dedent(f"""\

                ── SQUIRE TRIAGE REPORT ─────────────────
                Scan Path           : {triage.path}
                Risk Score          : {triage.risk_score} / 100
                Secrets Detected    : {len(triage.secrets)}
                Dead Artifacts      : {len(triage.dead_files)}
                Recommendations     :
            """)
            for rec in triage.recommendations:
                body += f"  - {rec}\n"

        body += textwrap.dedent("""\

            ── MISSIONS DIRECTORY ───────────────────
        """)
        if MISSIONS.exists():
            for f in sorted(MISSIONS.iterdir())[:5]:
                body += f"  {f.name}\n"

        body += "\n⚜️  Lady M | Lady Mnemosyne | Camelot Sovereign Swarm"
        return body

    def send(self, body: str) -> bool:
        if not SMTP_USER or not SMTP_PASS:
            LOG.warning("[BRIEF] SMTP credentials not set. Saving locally only.")
            ts   = datetime.utcnow().strftime("%Y%m%d_%H%M")
            dest = BRIEFING_DIR / f"brief_{ts}.txt"
            dest.write_text(body, encoding="utf-8")
            LOG.info("[BRIEF] Saved to %s", dest)
            return False

        msg               = MIMEMultipart("alternative")
        msg["Subject"]    = f"⚔️  Camelot Sovereign Brief — {datetime.utcnow().strftime('%Y-%m-%d')}"
        msg["From"]       = SMTP_USER
        msg["To"]         = SENTINEL_EMAIL
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as srv:
                srv.login(SMTP_USER, SMTP_PASS)
                srv.sendmail(SMTP_USER, SENTINEL_EMAIL, msg.as_string())
            LOG.info("[BRIEF] Sent to %s", SENTINEL_EMAIL)
        except Exception as exc:
            LOG.error("[BRIEF] Send failed: %s", exc)

        # ── Worldtree Cloudbrain Sync ──
        if CloudBrainConnector:
            try:
                cb = CloudBrainConnector(knight_id="LADY_MNEMOSYNE")
                cb.push_to_notebook(
                    artifact_type="note",
                    content=body,
                    title=f"Sovereign Brief - {datetime.utcnow().strftime('%Y-%m-%d')}"
                )
                LOG.info("[BRIEF] Synced Sovereign Brief to Lady Mnemosyne's Cloudbrain")
                return True
            except Exception as exc:
                LOG.error("[BRIEF] Cloudbrain Sync failed: %s", exc)
                return False
        return True


# ── Lady M Orchestrator ───────────────────────────────────────────────────────
class LadyM:
    """
    Lady Mnemosyne — Sovereign Swarm Commander.
    Dispatches TRIAGE → PURGE → MERGE → BRIEF in sequence.
    """
    def __init__(self):
        self.triage = SquireTriage()
        self.purge  = SquirePurge()
        self.merge  = SquireMerge()
        self.brief  = SquireBrief()

    def run_full_sweep(self, scan_path: Path = CAMELOT_ROOT, dry_run: bool = False) -> dict:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        LOG.info("⚜️  Lady M — Full Sovereign Sweep initiated")

        # 1. Triage
        report = self.triage.run(scan_path)

        # 2. Purge
        purged = self.purge.run(dry_run=dry_run)

        # 3. Merge staged repos
        merges: list[dict] = []
        for staged in self.merge.list_staged():
            result = self.merge.merge(staged.name, report)
            merges.append({"repo": staged.name, **result})

        # 4. Brief
        body    = self.brief.compile(triage=report)
        sent    = self.brief.send(body)

        # 5. Rune Router dispatch — route brief to best-fit Worldtree notebooks
        if _rune_router:
            LOG.info("[LADY_M] ᛟ Engaging Rune Router for SQUIRE_BRIEF dispatch...")
            _rune_router.route(
                task="sovereign daily brief triage memory sweep",
                content=body,
                artifact_type="note",
            )

        return {
            "triage":   {"risk": report.risk_score, "secrets": len(report.secrets)},
            "purged":   len(purged),
            "merges":   merges,
            "brief_sent": sent,
        }


if __name__ == "__main__":
    result = LadyM().run_full_sweep()
    print(json.dumps(result, indent=2))
