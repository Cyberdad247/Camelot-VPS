# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-
"""
Agent-Native MDX — schema, validation, rendering (v9000.14, Pillar BRAIN, P3-T01).
=================================================================================
A structured, machine-authored document format the knights emit instead of raw
markdown. Each document is a typed block list rendered to MDX (Markdown + JSX
components) for the HTMX Bifrost Board. Five components are supported:

    Summary         — headline + risk band
    FileMap         — files to be created/modified/deleted
    Diagram         — a mermaid diagram
    ApprovalButton  — a HITL approval control (htmx-wired on the board)
    ContextSources  — the World Tree / FirnFlow sources that grounded the plan

``validate_mdx(doc)`` checks a document against MDX_JSON_SCHEMA (jsonschema if
installed; a self-contained fallback otherwise). ``render_mdx(doc)`` emits the
MDX text.

Run as module:
    python -m control_plane.mdx_schema --test
"""
from __future__ import annotations

__version__ = "9000.14"  # CYBERTRONIA

import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOC_KINDS = ("visual-plan", "visual-recap", "bifrost-insight")
RISK_BANDS = ("AUTO", "PROMPT", "HUMAN_GATE", "CRITICAL")
FILE_ACTIONS = ("create", "modify", "delete")

# ── JSON Schema (Draft 2020-12) ──────────────────────────────────────────────
MDX_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentNativeMDX",
    "type": "object",
    "required": ["version", "kind", "title", "blocks"],
    "additionalProperties": False,
    "properties": {
        "version": {"const": "9000.14"},
        "kind": {"enum": list(DOC_KINDS)},
        "title": {"type": "string", "minLength": 1},
        "blocks": {
            "type": "array",
            "items": {
                "oneOf": [
                    {
                        "type": "object", "additionalProperties": False,
                        "required": ["type", "text", "risk"],
                        "properties": {
                            "type": {"const": "Summary"},
                            "text": {"type": "string", "minLength": 1},
                            "risk": {"enum": list(RISK_BANDS)},
                        },
                    },
                    {
                        "type": "object", "additionalProperties": False,
                        "required": ["type", "files"],
                        "properties": {
                            "type": {"const": "FileMap"},
                            "files": {
                                "type": "array",
                                "items": {
                                    "type": "object", "additionalProperties": False,
                                    "required": ["path", "action"],
                                    "properties": {
                                        "path": {"type": "string", "minLength": 1},
                                        "action": {"enum": list(FILE_ACTIONS)},
                                        "note": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                    {
                        "type": "object", "additionalProperties": False,
                        "required": ["type", "source"],
                        "properties": {
                            "type": {"const": "Diagram"},
                            "format": {"const": "mermaid"},
                            "source": {"type": "string", "minLength": 1},
                        },
                    },
                    {
                        "type": "object", "additionalProperties": False,
                        "required": ["type", "action_id", "label", "tier"],
                        "properties": {
                            "type": {"const": "ApprovalButton"},
                            "action_id": {"type": "string", "minLength": 1},
                            "label": {"type": "string", "minLength": 1},
                            "tier": {"enum": list(RISK_BANDS)},
                        },
                    },
                    {
                        "type": "object", "additionalProperties": False,
                        "required": ["type", "sources"],
                        "properties": {
                            "type": {"const": "ContextSources"},
                            "sources": {
                                "type": "array",
                                "items": {
                                    "type": "object", "additionalProperties": False,
                                    "required": ["name"],
                                    "properties": {
                                        "name": {"type": "string", "minLength": 1},
                                        "ref": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                ]
            },
        },
    },
}

_VALID_BLOCK_TYPES = {"Summary", "FileMap", "Diagram", "ApprovalButton", "ContextSources"}


def validate_mdx(doc: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate an Agent-Native MDX document. Returns (ok, errors)."""
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(MDX_JSON_SCHEMA)
        errors = [f"{'/'.join(map(str, e.path))}: {e.message}"
                  for e in validator.iter_errors(doc)]
        return (not errors), errors
    except ImportError:
        return _validate_fallback(doc)


def _validate_fallback(doc: dict[str, Any]) -> tuple[bool, list[str]]:
    """Dependency-free structural validation (mirrors the JSON Schema)."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return False, ["document must be an object"]
    if doc.get("version") != "9000.14":
        errors.append("version must be '9000.14'")
    if doc.get("kind") not in DOC_KINDS:
        errors.append(f"kind must be one of {DOC_KINDS}")
    if not isinstance(doc.get("title"), str) or not doc.get("title"):
        errors.append("title must be a non-empty string")
    blocks = doc.get("blocks")
    if not isinstance(blocks, list):
        return False, errors + ["blocks must be an array"]
    for i, b in enumerate(blocks):
        if not isinstance(b, dict) or b.get("type") not in _VALID_BLOCK_TYPES:
            errors.append(f"blocks[{i}]: invalid or missing component type")
            continue
        t = b["type"]
        if t == "Summary" and (not b.get("text") or b.get("risk") not in RISK_BANDS):
            errors.append(f"blocks[{i}] Summary: needs text + valid risk")
        elif t == "FileMap" and not isinstance(b.get("files"), list):
            errors.append(f"blocks[{i}] FileMap: needs files array")
        elif t == "Diagram" and not b.get("source"):
            errors.append(f"blocks[{i}] Diagram: needs source")
        elif t == "ApprovalButton" and not (b.get("action_id") and b.get("label")
                                            and b.get("tier") in RISK_BANDS):
            errors.append(f"blocks[{i}] ApprovalButton: needs action_id/label/tier")
        elif t == "ContextSources" and not isinstance(b.get("sources"), list):
            errors.append(f"blocks[{i}] ContextSources: needs sources array")
    return (not errors), errors


def render_mdx(doc: dict[str, Any]) -> str:
    """Render a validated document to MDX text (Markdown + JSX components)."""
    lines = [f"# {doc.get('title', 'Untitled')}",
             f"<!-- kind={doc.get('kind')} version={doc.get('version')} -->", ""]
    for b in doc.get("blocks", []):
        t = b.get("type")
        if t == "Summary":
            lines += [f"<Summary risk=\"{b['risk']}\">", b["text"], "</Summary>", ""]
        elif t == "FileMap":
            lines.append("<FileMap>")
            for f in b.get("files", []):
                note = f" — {f['note']}" if f.get("note") else ""
                lines.append(f"  - `{f['action']}` **{f['path']}**{note}")
            lines += ["</FileMap>", ""]
        elif t == "Diagram":
            lines += ["<Diagram format=\"mermaid\">", "```mermaid",
                      b["source"].strip(), "```", "</Diagram>", ""]
        elif t == "ApprovalButton":
            lines += [f"<ApprovalButton actionId=\"{b['action_id']}\" "
                      f"tier=\"{b['tier']}\">{b['label']}</ApprovalButton>", ""]
        elif t == "ContextSources":
            lines.append("<ContextSources>")
            for s in b.get("sources", []):
                ref = f" ({s['ref']})" if s.get("ref") else ""
                lines.append(f"  - {s['name']}{ref}")
            lines += ["</ContextSources>", ""]
    return "\n".join(lines)


# ── Self-test ────────────────────────────────────────────────────────────────

def _sample_doc() -> dict[str, Any]:
    return {
        "version": "9000.14",
        "kind": "visual-plan",
        "title": "Build status dashboard",
        "blocks": [
            {"type": "Summary", "text": "Add a Go BubbleTea status dashboard.", "risk": "PROMPT"},
            {"type": "FileMap", "files": [
                {"path": "cmd/dash/main.go", "action": "create", "note": "entrypoint"},
                {"path": "go.mod", "action": "modify"},
            ]},
            {"type": "Diagram", "format": "mermaid", "source": "graph TD; A-->B"},
            {"type": "ContextSources", "sources": [
                {"name": "FirnFlow KERNEL", "ref": "L1"},
            ]},
            {"type": "ApprovalButton", "action_id": "job-123", "label": "Approve & Execute", "tier": "PROMPT"},
        ],
    }


def _selftest() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("Agent-Native MDX self-test (P3-T01)")

    ok, errors = validate_mdx(_sample_doc())
    check(f"valid sample passes (errors={errors})", ok)

    # Malformed: bad risk band
    bad1 = _sample_doc(); bad1["blocks"][0]["risk"] = "NOPE"
    ok1, e1 = validate_mdx(bad1)
    check("invalid risk band rejected", not ok1 and len(e1) >= 1)

    # Malformed: unknown block type
    bad2 = _sample_doc(); bad2["blocks"].append({"type": "Bogus"})
    ok2, _ = validate_mdx(bad2)
    check("unknown component rejected", not ok2)

    # Malformed: wrong version
    bad3 = _sample_doc(); bad3["version"] = "1.0"
    ok3, _ = validate_mdx(bad3)
    check("wrong version rejected", not ok3)

    # Render produces JSX components + mermaid
    mdx = render_mdx(_sample_doc())
    check("render emits <Summary>", "<Summary risk=\"PROMPT\">" in mdx)
    check("render emits <ApprovalButton>", "<ApprovalButton actionId=\"job-123\"" in mdx)
    check("render emits mermaid block", "```mermaid" in mdx)

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURE(S)'} — mdx_schema")
    return failures


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(1 if _selftest() else 0)
    print(render_mdx(_sample_doc()))
