# SPDX-License-Identifier: MIT
"""Read-only contract catalog validation for the Camelot CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from control_plane.cli.constants import CAMELOT_HOME
from control_plane.cli.renderer import _emit

DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _failure(path: Path, message: str) -> str:
    return f"{path.name}: {message}"


def _validate_schema_file(path: Path) -> list[str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [_failure(path, f"unable to read JSON ({type(exc).__name__})")]

    if document.get("$schema") != DIALECT:
        return [_failure(path, "schema dialect is not Draft 2020-12")]

    try:
        Draft202012Validator.check_schema(document)
    except Exception as exc:
        return [_failure(path, f"schema validation failed ({type(exc).__name__})")]

    return []


def _validate_catalog(contracts_dir: Path, schema_files: list[Path]) -> list[str]:
    index_path = contracts_dir / "index.json"
    try:
        catalog = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [_failure(index_path, f"unable to read catalog ({type(exc).__name__})")]

    errors: list[str] = []
    if catalog.get("$schema") != DIALECT:
        errors.append(_failure(index_path, "catalog dialect is not Draft 2020-12"))

    entries = catalog.get("schemas")
    if not isinstance(entries, list):
        return errors + [_failure(index_path, "catalog schemas must be an array")]

    listed = {entry.get("file"): entry for entry in entries if isinstance(entry, dict)}
    on_disk = {path.name for path in schema_files}
    for name in sorted(on_disk - set(listed)):
        errors.append(_failure(index_path, f"schema missing from catalog: {name}"))
    for name in sorted(set(listed) - on_disk):
        errors.append(_failure(index_path, f"catalog schema missing on disk: {name}"))

    for name in sorted(set(listed) & on_disk):
        entry = listed[name]
        expected_id = f"https://camelot-os/schemas/{name}"
        if entry.get("$id") != expected_id:
            errors.append(_failure(index_path, f"catalog id mismatch for {name}"))

    return errors


def validate_contracts(path: str | Path | None = None) -> dict[str, Any]:
    """Validate schemas without writing files or resolving external references."""
    target = Path(path) if path is not None else CAMELOT_HOME / "packages" / "contracts"
    errors: list[str] = []

    if not target.exists():
        errors.append(_failure(target, "path does not exist"))
        return {
            "status": "FAIL",
            "read_only": True,
            "root": str(target),
            "schema_count": 0,
            "errors": errors,
        }

    if target.is_file():
        schema_files = [target]
        catalog_errors: list[str] = []
    elif target.is_dir():
        schema_files = sorted(target.glob("*.schema.json"))
        if not schema_files:
            errors.append(_failure(target, "no *.schema.json files found"))
        catalog_errors = _validate_catalog(target, schema_files)
    else:
        errors.append(_failure(target, "path is not a file or directory"))
        schema_files = []
        catalog_errors = []

    for schema_path in schema_files:
        errors.extend(_validate_schema_file(schema_path))
    errors.extend(catalog_errors)

    return {
        "status": "PASS" if not errors else "FAIL",
        "read_only": True,
        "root": str(target),
        "schema_count": len(schema_files),
        "errors": errors,
    }


def handle_contracts(args: Any, _config_mgr: Any, _prov_mgr: Any, _argv: list[str]) -> int:
    result = validate_contracts(getattr(args, "path", None))
    _emit(result, json_mode=getattr(args, "json", False), title="Contract Schema Validation")
    return 0 if result["status"] == "PASS" else 1
