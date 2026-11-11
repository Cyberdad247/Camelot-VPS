# SPDX-License-Identifier: MIT

"""TOON manifest compiler for Camelot configuration payloads.

The compiler is intentionally conservative: it redacts sensitive keys before
serialization and writes evidence metrics instead of repeating compression
claims from proposals.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # PyYAML is optional in some Camelot shells.
    import yaml  # type: ignore
except Exception:  # pragma: no cover - exercised when PyYAML is absent
    yaml = None


SENSITIVE_KEY_RE = re.compile(r"(secret|token|password|api[_-]?key|private[_-]?key|credential)", re.I)
SIMPLE_SCALAR_RE = re.compile(r"^[A-Za-z0-9_./:@+-]+$")


DEFAULT_MANIFEST_RELATIVE_PATHS = (
    ".camelot-config.yaml",
    "config.json",
    "01_KERNEL/EXCALIBUR/config/system_manifest.json",
    "01_KERNEL/EXCALIBUR/config/api_manifest.yaml",
    "01_KERNEL/EXCALIBUR/roster.yaml",
    "03_VAULT/runtime_state/switchboard_manifest.json",
)


@dataclass(frozen=True)
class ToonKvPair:
    key: str
    value: str


def default_manifest_paths(root: Path) -> list[Path]:
    """Return existing default Camelot config manifests, excluding secret stores."""
    paths: list[Path] = []
    for relative in DEFAULT_MANIFEST_RELATIVE_PATHS:
        path = root / relative
        if path.exists() and not SENSITIVE_KEY_RE.search(path.name):
            paths.append(path)
    return paths


def build_scarcity_core_manifest() -> dict[str, Any]:
    """Materialize the proposed 4GB scarcity-core TOON payload as structured data."""
    return {
        "MemoryManager": {
            "physical_limit_mb": 3072,
            "zram_size_mb": 1024,
            "zram_compression_algo": "lz4",
            "oom_score_adj": -1000,
            "swappiness": 100,
        },
        "Cgroups": {
            "cpu_max_pct": 85,
            "io_weight": 100,
            "memory_high_limit_mb": 2900,
            "memory_max_limit_mb": 3072,
        },
        "DAX": {
            "enable_zero_copy_shared_memory": True,
            "dax_device_path": "/dev/dax0.0",
        },
        "skills": [
            {
                "constraints": {"mem": 67108864, "max_threads": 2},
                "entrypoint": "/bin/sve-compiler",
                "id": "skill:sve-compilation",
                "name": "ARM64 SVE Compiler",
            },
            {
                "constraints": {"mem": 16777216, "max_threads": 1},
                "entrypoint": "/bin/ebpf-fuzz",
                "id": "skill:ebpf-telemetry",
                "name": "Freebuff Telemetry",
            },
        ],
        "agents": [
            {
                "environment": "unikraft-5mb-base",
                "limit_ms": 5000,
                "name": "Sir Helios",
                "role": "AGI Macro-Oracle",
            },
            {
                "environment": "unikraft-5mb-compiler",
                "limit_ms": 3000,
                "name": "Sir Codex",
                "role": "Local Edge Fabricator",
            },
            {
                "environment": "unikraft-5mb-security",
                "limit_ms": 2000,
                "name": "Freebuff Oracle",
                "role": "Red Team Cyber-Aegis",
            },
        ],
        "tasks": [
            {"deps": [], "id": "TASK_01_BOOTSTRAP_MEMFD", "status": "pending"},
            {"deps": ["TASK_01"], "id": "TASK_02_THAW_LEDGER", "status": "pending"},
            {"deps": ["TASK_02"], "id": "TASK_03_HELIOS_BLUEPRINT", "status": "pending"},
            {"deps": ["TASK_03"], "id": "TASK_04_CODEX_SCAFFOLD", "status": "pending"},
            {"deps": ["TASK_04"], "id": "TASK_05_FREEBUFF_FUZZ", "status": "pending"},
            {"deps": ["TASK_05"], "id": "TASK_06_CRITICAL_VALIDATE", "status": "pending"},
        ],
    }


def redact_sensitive(value: Any, key: str = "") -> Any:
    """Replace sensitive values with presence flags while preserving structure."""
    if SENSITIVE_KEY_RE.search(key):
        return _presence(value)
    if isinstance(value, dict):
        return {str(k): redact_sensitive(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item, key) for item in value]
    return value


def encode_toon_document(document: dict[str, Any], *, title: str | None = None) -> str:
    """Encode a dictionary into indent-based TOON with folded uniform arrays."""
    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
    for key, value in document.items():
        _emit_node(lines, key, redact_sensitive(value, key), indent=0)
    return "\n".join(lines).rstrip() + "\n"


def parse_toon_config(raw_toon: str) -> list[ToonKvPair]:
    """Parse simple key/value lines from TOON, skipping folded array headers."""
    pairs: list[ToonKvPair] = []
    for line in raw_toon.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#") or "items[" in trimmed:
            continue
        if ":" in trimmed:
            key, value = trimmed.split(":", 1)
            pairs.append(ToonKvPair(key=key.strip(), value=value.strip()))
    return pairs


def load_manifest(path: Path) -> Any:
    """Load a JSON or YAML manifest."""
    suffix = path.suffix.lower()
    raw = path.read_text(encoding="utf-8")
    if suffix == ".json":
        return json.loads(raw)
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to compile YAML manifests")
        return yaml.safe_load(raw)
    raise ValueError(f"Unsupported manifest type: {path}")


def compile_manifest_documents(documents: dict[str, Any]) -> str:
    """Encode named manifest documents into one TOON payload."""
    safe_docs = {name: redact_sensitive(doc, name) for name, doc in documents.items()}
    return encode_toon_document(safe_docs, title="TOON Spec v3.2 -- Compressed Camelot System Manifest")


def compile_manifest_paths(paths: list[Path], *, root: Path) -> tuple[str, dict[str, Any]]:
    """Load, redact, encode, and measure manifest paths."""
    documents: dict[str, Any] = {}
    input_paths: list[str] = []
    original_bytes = 0
    for path in paths:
        resolved = path if path.is_absolute() else root / path
        data = load_manifest(resolved)
        relative = _display_path(resolved, root)
        documents[relative] = data if data is not None else {}
        input_paths.append(relative)
        original_bytes += len(resolved.read_bytes())

    toon = compile_manifest_documents(documents)
    metrics = _metrics(toon, original_bytes=original_bytes, input_paths=input_paths)
    metrics["evidence_class"] = "confirmed"
    return toon, metrics


def write_compiled_manifest(paths: list[Path], *, root: Path, output_path: Path) -> dict[str, Any]:
    """Compile manifest paths and write TOON plus evidence JSON artifacts."""
    toon, metrics = compile_manifest_paths(paths, root=root)
    _write_artifacts(toon, metrics, output_path=output_path)
    return metrics


def write_scarcity_core_artifacts(root: Path) -> dict[str, Any]:
    """Write the proposed scarcity-core manifest as a planned runtime artifact."""
    output_path = root / "03_VAULT" / "runtime_state" / "camelot.toon"
    manifest = build_scarcity_core_manifest()
    original_bytes = len(json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    toon = encode_toon_document(
        manifest,
        title="TOON Spec v3.2 -- Compressed Camelot System Manifest",
    )
    metrics = _metrics(toon, original_bytes=original_bytes, input_paths=["user_proposed_scarcity_core_manifest"])
    metrics.update(
        {
            "status": "WROTE",
            "evidence_class": "planned",
            "note": "Proposed payload materialized; runtime integration is not active until wired and tested.",
        }
    )
    _write_artifacts(toon, metrics, output_path=output_path)
    return metrics


def _emit_node(lines: list[str], key: str, value: Any, *, indent: int) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        lines.append(f"{prefix}{key}:")
        for child_key, child_value in value.items():
            _emit_node(lines, child_key, child_value, indent=indent + 2)
    elif _is_uniform_dict_array(value):
        fields = list(value[0].keys()) if value else []
        lines.append(f"{prefix}{key}: items[{len(value)}]{{{','.join(fields)}}}:")
        for item in value:
            row = ",".join(_format_row_value(item[field]) for field in fields)
            lines.append(f"{prefix}  {row}")
    elif isinstance(value, list):
        lines.append(f"{prefix}{key}: {_format_row_value(value)}")
    else:
        lines.append(f"{prefix}{key}: {_format_scalar(value)}")


def _is_uniform_dict_array(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    if not all(isinstance(item, dict) for item in value):
        return False
    fields = list(value[0].keys())
    field_set = set(fields)
    return all(set(item.keys()) == field_set for item in value)


def _format_row_value(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + "|".join(f"{key}:{_format_row_value(val)}" for key, val in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_format_row_value(item) for item in value) + "]"
    return _format_scalar(value)


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if SIMPLE_SCALAR_RE.match(text):
        return text
    return json.dumps(text, ensure_ascii=False, separators=(",", ":"))


def _presence(value: Any) -> bool:
    if value in ("", None, False):
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _metrics(toon: str, *, original_bytes: int, input_paths: list[str]) -> dict[str, Any]:
    toon_bytes = len(toon.encode("utf-8"))
    reduction_pct = 0.0
    if original_bytes:
        reduction_pct = round((1 - (toon_bytes / original_bytes)) * 100, 2)
    return {
        "status": "COMPILED",
        "format": "TOON",
        "spec": "v3.2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_paths": input_paths,
        "bytes_original": original_bytes,
        "bytes_toon": toon_bytes,
        "reduction_pct": reduction_pct,
        "sha256": hashlib.sha256(toon.encode("utf-8")).hexdigest(),
    }


def _write_artifacts(toon: str, metrics: dict[str, Any], *, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(toon, encoding="utf-8")
    evidence_path = output_path.with_suffix(output_path.suffix + ".evidence.json")
    metrics["output_path"] = str(output_path)
    metrics["evidence_path"] = str(evidence_path)
    evidence_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
