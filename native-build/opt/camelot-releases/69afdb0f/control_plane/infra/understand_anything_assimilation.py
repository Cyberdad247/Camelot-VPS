# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from control_plane.bio_swarm_runtime import read_bio_swarm_status
from control_plane.notebooklm_graphify_bridge import (
    DEFAULT_NOTEBOOKLM_STATE,
    load_storage_state,
    notebooklm_state_to_graph_context,
)
from control_plane.versioning import get_dynamic_version

SCHEMA = "camelot.understand-anything-assimilation/v1"
DEFAULT_OUTPUT_ROOT = Path(".understand-anything")
DEFAULT_MAX_FILES = 750

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".pytest_cache",
    ".ruff_cache",
    "graphify-out",
}

SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".md",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ps1",
}

CLOUDBRAIN_NAMES = {
    "CloudBrain_Link.md",
    "camelot_cloudbrain_v701_manifest.json",
    "squire_index_latest.json",
    "squire_vector_latest.json",
    "external_skill_sources_manifest.json",
    "knowledge_crystal",
    "notebooklm_graphify",
    "bio_swarm_runtime_latest.json",
    "bio_swarm_release_latest.json",
}


@dataclass(frozen=True)
class AssimilationResult:
    output_root: Path
    graph_path: Path
    report_path: Path
    node_count: int
    edge_count: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _node_id(kind: str, value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.:/-]+", "-", value.strip()).strip("-")
    return f"{kind}:{clean or 'root'}"


def _classify_layer(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    suffix = path.suffix.lower()
    if "control_plane" in parts or "01_kernel" in parts:
        return "control-plane"
    if "02_forge" in parts or suffix in {".tsx", ".jsx"}:
        return "interface"
    if "03_vault" in parts:
        return "memory"
    if "05_infrastructure" in parts or suffix in {".tf", ".toml", ".yaml", ".yml"}:
        return "infrastructure"
    if "tests" in parts or path.name.startswith("test_"):
        return "verification"
    if suffix in {".md", ".json"}:
        return "knowledge"
    return "source"


def _skip_dir(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _iter_project_files(root: Path, max_files: int = DEFAULT_MAX_FILES) -> Iterable[Path]:
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= max_files:
            break
        if not path.is_file() or _skip_dir(path.relative_to(root)):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        count += 1
        yield path


def _extract_python_imports(text: str) -> list[str]:
    imports: list[str] = []
    for line in text.splitlines()[:200]:
        stripped = line.strip()
        if stripped.startswith("import "):
            imports.extend(part.strip().split(" ")[0] for part in stripped[7:].split(","))
        elif stripped.startswith("from "):
            module = stripped[5:].split(" import ", 1)[0].strip()
            if module:
                imports.append(module)
    return [item for item in imports if item and not item.startswith(".")]


def _file_summary(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".") or "file"
    return f"{suffix} artifact in Camelot OS layer {_classify_layer(path)}"


def _cloudbrain_artifacts(root: Path) -> list[Path]:
    runtime = root / "03_VAULT" / "runtime_state"
    if not runtime.exists():
        return []
    artifacts: list[Path] = []
    for item in runtime.iterdir():
        if item.name in CLOUDBRAIN_NAMES or "cloudbrain" in item.name.lower() or "notebook" in item.name.lower():
            artifacts.append(item)
    return sorted(artifacts)


def _notebooklm_metadata() -> dict[str, Any]:
    try:
        context = notebooklm_state_to_graph_context(load_storage_state(DEFAULT_NOTEBOOKLM_STATE))
        return {
            "path": str(DEFAULT_NOTEBOOKLM_STATE),
            "available": True,
            "notebook_count": context["notebook_count"],
            "source_count": context["source_count"],
        }
    except Exception as exc:
        return {
            "path": str(DEFAULT_NOTEBOOKLM_STATE),
            "available": False,
            "error": type(exc).__name__,
        }


def build_assimilation_graph(root: Path, *, max_files: int = DEFAULT_MAX_FILES) -> dict[str, Any]:
    root = root.resolve()
    version = get_dynamic_version()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    root_id = _node_id("repo", root.name)
    nodes[root_id] = {
        "id": root_id,
        "label": root.name,
        "type": "repository",
        "path": ".",
        "layer": "root",
        "summary": "Camelot OS repository root",
    }

    module_by_name: dict[str, str] = {}
    for file_path in _iter_project_files(root, max_files=max_files):
        rel = _rel(file_path, root)
        file_id = _node_id("file", rel)
        layer = _classify_layer(file_path.relative_to(root))
        nodes[file_id] = {
            "id": file_id,
            "label": file_path.name,
            "type": "file",
            "path": rel,
            "layer": layer,
            "summary": _file_summary(file_path.relative_to(root)),
            "size": file_path.stat().st_size,
        }
        edges.append(
            {
                "id": _node_id("edge", f"{root_id}->{file_id}"),
                "source": root_id,
                "target": file_id,
                "type": "contains",
                "confidence": "extracted",
            }
        )
        if file_path.suffix == ".py":
            module_by_name[file_path.stem] = file_id

    for file_path in _iter_project_files(root, max_files=max_files):
        if file_path.suffix != ".py":
            continue
        source_id = _node_id("file", _rel(file_path, root))
        try:
            imports = _extract_python_imports(file_path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        for module in imports:
            target_id = module_by_name.get(module.rsplit(".", 1)[-1])
            if not target_id or target_id == source_id:
                continue
            edges.append(
                {
                    "id": _node_id("edge", f"{source_id}->{target_id}:imports"),
                    "source": source_id,
                    "target": target_id,
                    "type": "imports",
                    "confidence": "extracted",
                }
            )

    cloudbrain_id = _node_id("system", "cloudbrain")
    nodes[cloudbrain_id] = {
        "id": cloudbrain_id,
        "label": "Cloudbrain Artifacts",
        "type": "artifact-group",
        "path": "03_VAULT/runtime_state",
        "layer": "memory",
        "summary": "Selected runtime artifacts relevant to Cloudbrain, NotebookLM, graph, and swarm state",
    }
    edges.append(
        {
            "id": _node_id("edge", f"{root_id}->{cloudbrain_id}"),
            "source": root_id,
            "target": cloudbrain_id,
            "type": "has_runtime_artifacts",
            "confidence": "extracted",
        }
    )

    for artifact in _cloudbrain_artifacts(root):
        rel = _rel(artifact, root)
        artifact_id = _node_id("artifact", rel)
        nodes[artifact_id] = {
            "id": artifact_id,
            "label": artifact.name,
            "type": "cloudbrain-artifact",
            "path": rel,
            "layer": "memory",
            "summary": "Cloudbrain-compatible runtime artifact selected for assimilation",
            "size": artifact.stat().st_size if artifact.is_file() else None,
        }
        edges.append(
            {
                "id": _node_id("edge", f"{cloudbrain_id}->{artifact_id}"),
                "source": cloudbrain_id,
                "target": artifact_id,
                "type": "references",
                "confidence": "extracted",
            }
        )

    notebook_meta = _notebooklm_metadata()
    notebook_id = _node_id("external", "notebooklm")
    nodes[notebook_id] = {
        "id": notebook_id,
        "label": "NotebookLM External State",
        "type": "external-cloudbrain",
        "path": notebook_meta["path"],
        "layer": "memory",
        "summary": "External NotebookLM state is referenced by path and summarized without secret contents",
        "metadata": notebook_meta,
    }
    edges.append(
        {
            "id": _node_id("edge", f"{cloudbrain_id}->{notebook_id}"),
            "source": cloudbrain_id,
            "target": notebook_id,
            "type": "mirrors_external_state",
            "confidence": "extracted",
        }
    )

    bio_id = _node_id("system", "bio-swarm")
    nodes[bio_id] = {
        "id": bio_id,
        "label": "Bio-Kinetic Swarm",
        "type": "swarm-runtime",
        "path": "control_plane/bio_swarm_runtime.py",
        "layer": "orchestration",
        "summary": "Bio-Swarm runtime status attached to the understanding graph",
        "metadata": read_bio_swarm_status(root),
    }
    edges.append(
        {
            "id": _node_id("edge", f"{root_id}->{bio_id}"),
            "source": root_id,
            "target": bio_id,
            "type": "orchestrates",
            "confidence": "extracted",
        }
    )

    return {
        "schema": SCHEMA,
        "generated_utc": _now(),
        "source": "Egonex-AI/Understand-Anything compatible Camelot adapter",
        "camelot_version": version.label,
        "camelot_version_source": version.source,
        "root": str(root),
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "max_files": max_files,
        },
    }


def write_understand_anything_artifacts(
    root: Path,
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    max_files: int = DEFAULT_MAX_FILES,
) -> AssimilationResult:
    root = root.resolve()
    out = (root / output_root).resolve() if not output_root.is_absolute() else output_root
    out.mkdir(parents=True, exist_ok=True)
    graph = build_assimilation_graph(root, max_files=max_files)
    graph_path = out / "knowledge-graph.json"
    report_path = out / "CAMELOT_ASSIMILATION_REPORT.md"
    config_path = out / "config.json"

    graph_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    config_path.write_text(
        json.dumps(
            {
                "language": "en",
                "adapter": SCHEMA,
                "source_repo": "https://github.com/Egonex-AI/Understand-Anything",
                "cloudbrain_mode": "metadata-only",
                "bio_swarm_mode": "status-only",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_render_report(graph), encoding="utf-8")
    return AssimilationResult(
        output_root=out,
        graph_path=graph_path,
        report_path=report_path,
        node_count=graph["stats"]["nodes"],
        edge_count=graph["stats"]["edges"],
    )


def _render_report(graph: dict[str, Any]) -> str:
    stats = graph["stats"]
    return "\n".join(
        [
            "# Camelot Understand-Anything Assimilation",
            "",
            f"- Schema: `{graph['schema']}`",
            f"- Generated: `{graph['generated_utc']}`",
            f"- Camelot version: `{graph['camelot_version']}`",
            f"- Nodes: {stats['nodes']}",
            f"- Edges: {stats['edges']}",
            f"- Max scanned files: {stats['max_files']}",
            "",
            "## Integration Notes",
            "",
            "- Produces `.understand-anything/knowledge-graph.json` for graph inspection.",
            "- Includes selected Cloudbrain runtime artifacts by metadata.",
            "- References NotebookLM external state without copying token or browser contents.",
            "- Adds Bio-Kinetic Swarm runtime status as an orchestration node.",
            "- Keeps the upstream Understand-Anything plugin optional.",
            "",
        ]
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Camelot Understand-Anything assimilation artifacts.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = write_understand_anything_artifacts(
        args.root,
        output_root=args.output_root,
        max_files=args.max_files,
    )
    print(json.dumps(result.__dict__ | {"output_root": str(result.output_root), "graph_path": str(result.graph_path), "report_path": str(result.report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
