# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

DEFAULT_NOTEBOOKLM_STATE = Path.home() / ".notebooklm" / "storage_state.json"
DEFAULT_CORPUS_ROOT = Path("03_VAULT/runtime_state/notebooklm_graphify")


@dataclass(frozen=True)
class NotebookLMSource:
    source_id: str
    title: str
    source_type: str
    uri: str | None = None
    text: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class NotebookLMNotebook:
    notebook_id: str
    title: str
    description: str | None = None
    sources: tuple[NotebookLMSource, ...] = ()


def _stringify(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _candidate_keys(mapping: dict[str, Any], keys: Iterable[str]) -> Iterator[Any]:
    for key in keys:
        if key in mapping:
            value = mapping[key]
            if value is not None:
                yield value


def _pick_first(mapping: dict[str, Any], keys: Iterable[str], fallback: Any = None) -> Any:
    for value in _candidate_keys(mapping, keys):
        return value
    return fallback


def load_storage_state(storage_state_path: Path = DEFAULT_NOTEBOOKLM_STATE) -> dict[str, Any]:
    if not storage_state_path.exists():
        raise FileNotFoundError(f"NotebookLM storage state not found: {storage_state_path}")
    with storage_state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("NotebookLM storage state must be a JSON object")
    return payload


def _normalize_sources(raw_sources: Any) -> tuple[NotebookLMSource, ...]:
    if not raw_sources:
        return ()
    normalized: list[NotebookLMSource] = []
    for index, item in enumerate(raw_sources):
        if not isinstance(item, dict):
            continue
        source_id = _stringify(_pick_first(item, ("id", "source_id", "document_id", "uuid"), index), f"source-{index}")
        title = _stringify(_pick_first(item, ("title", "name", "display_name", "filename", "source_title"), source_id), source_id)
        source_type = _stringify(_pick_first(item, ("type", "source_type", "kind", "mime_type"), "unknown"), "unknown")
        uri = _pick_first(item, ("url", "uri", "source_url", "link", "href"))
        text = _pick_first(item, ("text", "content", "body", "summary", "excerpt"))
        created_at = _pick_first(item, ("created_at", "createdAt", "updated_at", "updatedAt"))
        normalized.append(
            NotebookLMSource(
                source_id=source_id,
                title=title,
                source_type=source_type,
                uri=_stringify(uri) if uri is not None else None,
                text=_stringify(text) if text is not None else None,
                created_at=_stringify(created_at) if created_at is not None else None,
            )
        )
    return tuple(normalized)


def _normalize_notebooks(payload: dict[str, Any]) -> tuple[NotebookLMNotebook, ...]:
    raw_notebooks = _pick_first(payload, ("notebooks", "items", "documents", "collections"), [])
    if isinstance(raw_notebooks, dict):
        raw_notebooks = list(raw_notebooks.values())
    if not isinstance(raw_notebooks, list):
        raw_notebooks = []

    notebooks: list[NotebookLMNotebook] = []
    for index, item in enumerate(raw_notebooks):
        if not isinstance(item, dict):
            continue
        notebook_id = _stringify(_pick_first(item, ("id", "notebook_id", "uuid", "document_id"), index), f"notebook-{index}")
        title = _stringify(_pick_first(item, ("title", "name", "display_name", "notebook_title"), notebook_id), notebook_id)
        description = _pick_first(item, ("description", "summary", "notes", "prompt"))
        raw_sources = _pick_first(item, ("sources", "children", "entries", "source_list"), [])
        notebooks.append(
            NotebookLMNotebook(
                notebook_id=notebook_id,
                title=title,
                description=_stringify(description) if description is not None else None,
                sources=_normalize_sources(raw_sources),
            )
        )

    if notebooks:
        return tuple(notebooks)

    # Fall back to a single synthetic notebook if the state only stores flat sources.
    sources = _normalize_sources(_pick_first(payload, ("sources", "files", "documents"), []))
    if sources:
        return (
            NotebookLMNotebook(
                notebook_id="notebooklm-root",
                title=_stringify(_pick_first(payload, ("title", "name"), "NotebookLM Mirror"), "NotebookLM Mirror"),
                description=_stringify(_pick_first(payload, ("description", "summary"), None)) or None,
                sources=sources,
            ),
        )

    return ()


def notebooklm_state_to_graph_context(payload: dict[str, Any]) -> dict[str, Any]:
    notebooks = _normalize_notebooks(payload)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notebook_count": len(notebooks),
        "source_count": sum(len(notebook.sources) for notebook in notebooks),
        "notebooks": [
            {
                "notebook_id": notebook.notebook_id,
                "title": notebook.title,
                "description": notebook.description,
                "sources": [
                    {
                        "source_id": source.source_id,
                        "title": source.title,
                        "source_type": source.source_type,
                        "uri": source.uri,
                        "text": source.text,
                        "created_at": source.created_at,
                    }
                    for source in notebook.sources
                ],
            }
            for notebook in notebooks
        ],
    }


def _slugify(value: str) -> str:
    slug = []
    for char in value.lower():
        if char.isalnum():
            slug.append(char)
        elif slug and slug[-1] != "-":
            slug.append("-")
    text = "".join(slug).strip("-")
    return text or "item"


def materialize_graphify_corpus(
    storage_state_path: Path = DEFAULT_NOTEBOOKLM_STATE,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
) -> Path:
    payload = load_storage_state(storage_state_path)
    context = notebooklm_state_to_graph_context(payload)

    corpus_root.mkdir(parents=True, exist_ok=True)
    notebooks_dir = corpus_root / "notebooks"
    sources_dir = corpus_root / "sources"
    notebooks_dir.mkdir(parents=True, exist_ok=True)
    sources_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "storage_state_path": str(storage_state_path),
        "generated_at": context["generated_at"],
        "notebook_count": context["notebook_count"],
        "source_count": context["source_count"],
        "notebooks": [],
    }

    for notebook in context["notebooks"]:
        notebook_slug = _slugify(f'{notebook["title"]}-{notebook["notebook_id"]}')
        notebook_path = notebooks_dir / f"{notebook_slug}.md"
        notebook_lines = [
            f"# {notebook['title']}",
            "",
            f"- Notebook ID: `{notebook['notebook_id']}`",
            f"- Source count: {len(notebook['sources'])}",
        ]
        if notebook["description"]:
            notebook_lines.extend(["", "## Description", "", notebook["description"]])
        if notebook["sources"]:
            notebook_lines.extend(["", "## Sources"])
            for source in notebook["sources"]:
                source_slug = _slugify(f'{source["title"]}-{source["source_id"]}')
                source_path = sources_dir / f"{notebook_slug}--{source_slug}.md"
                source_lines = [
                    f"# {source['title']}",
                    "",
                    f"- Source ID: `{source['source_id']}`",
                    f"- Source type: `{source['source_type']}`",
                ]
                if source["uri"]:
                    source_lines.append(f"- URI: {source['uri']}")
                if source["created_at"]:
                    source_lines.append(f"- Created at: {source['created_at']}")
                if source["text"]:
                    source_lines.extend(["", "## Content", "", source["text"]])
                source_path.write_text("\n".join(source_lines).rstrip() + "\n", encoding="utf-8")
                notebook_lines.append(f"- [{source['title']}]({source_path.as_posix()})")
        notebook_path.write_text("\n".join(notebook_lines).rstrip() + "\n", encoding="utf-8")

        manifest["notebooks"].append(
            {
                "notebook_id": notebook["notebook_id"],
                "title": notebook["title"],
                "path": notebook_path.as_posix(),
                "sources": [
                    {
                        "source_id": source["source_id"],
                        "title": source["title"],
                    }
                    for source in notebook["sources"]
                ],
            }
        )

    (corpus_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return corpus_root


def build_graphify_command(corpus_root: Path, *, no_viz: bool = True, force: bool = True) -> list[str]:
    command = ["graphify", "extract", str(corpus_root)]
    if no_viz:
        command.append("--no-viz")
    if force:
        command.append("--force")
    return command


def run_graphify(corpus_root: Path, *, dry_run: bool = True) -> list[str]:
    command = build_graphify_command(corpus_root)
    if dry_run:
        return command
    if shutil.which(command[0]) is None:
        raise RuntimeError(
            "graphify is not installed on PATH. Install Graphify first, then rerun the mirror."
        )
    subprocess.run(command, check=True)
    return command


def mirror_notebooklm_to_graphify(
    storage_state_path: Path = DEFAULT_NOTEBOOKLM_STATE,
    corpus_root: Path = DEFAULT_CORPUS_ROOT,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    corpus_path = materialize_graphify_corpus(storage_state_path=storage_state_path, corpus_root=corpus_root)
    command = run_graphify(corpus_path, dry_run=dry_run)
    return {
        "storage_state_path": str(storage_state_path),
        "corpus_root": str(corpus_path),
        "graphify_command": command,
        "dry_run": dry_run,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mirror NotebookLM state into a Graphify-ready corpus.")
    parser.add_argument(
        "--storage-state",
        type=Path,
        default=DEFAULT_NOTEBOOKLM_STATE,
        help="Path to NotebookLM storage_state.json",
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=DEFAULT_CORPUS_ROOT,
        help="Directory where Graphify-ready corpus files will be written",
    )
    parser.add_argument(
        "--run-graphify",
        action="store_true",
        help="Execute graphify extract after materializing the corpus",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = mirror_notebooklm_to_graphify(
        storage_state_path=args.storage_state,
        corpus_root=args.corpus_root,
        dry_run=not args.run_graphify,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
