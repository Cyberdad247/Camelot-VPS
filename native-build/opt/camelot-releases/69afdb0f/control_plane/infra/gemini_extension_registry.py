# SPDX-License-Identifier: MIT

"""Read-only Gemini CLI extension registry for Camelot control-plane synapses."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_GEMINI_ROOT = Path.home() / ".gemini" / "extensions"
DEFAULT_SKILLS_ROOT = Path.home() / ".agents" / "skills"
DEFAULT_INTEGRITY_PATH = Path.home() / ".gemini" / "extension_integrity.json"
DEFAULT_SETTINGS_PATH = Path.home() / ".gemini" / "settings.json"
DEFAULT_TRUSTED_FOLDERS_PATH = Path.home() / ".gemini" / "trustedFolders.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _manifest_path(gemini_root: Path, name: str) -> Path:
    return gemini_root / name / "gemini-extension.json"


def _adapter_path(skills_root: Path, name: str) -> Path:
    return skills_root / f"gemini-{name}" / "SKILL.md"


def _adapter_status(path: Path) -> str:
    if not path.exists():
        return "missing adapter"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        marker = "- Gemini status:"
        if line.strip().startswith(marker):
            return line.split(marker, 1)[1].strip()
    return "adapter present"


def _command_specs(extension_dir: Path) -> list[str]:
    commands_dir = extension_dir / "commands"
    if not commands_dir.exists():
        return []
    specs: list[str] = []
    for path in commands_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".toml", ".md"}:
            specs.append(path.relative_to(commands_dir).as_posix())
    return sorted(specs)


def _enabled_map(gemini_root: Path) -> dict[str, Any]:
    data = _read_json(gemini_root / "extension-enablement.json")
    return data if isinstance(data, dict) else {}


def _integrity_store(integrity_path: Path) -> dict[str, Any]:
    data = _read_json(integrity_path)
    if not isinstance(data, dict):
        return {}
    store = data.get("store")
    return store if isinstance(store, dict) else {}


def _settings_summary(settings_path: Path) -> dict[str, Any]:
    data = _read_json(settings_path)
    if not isinstance(data, dict):
        return {"path": str(settings_path), "exists": settings_path.exists()}
    return {
        "path": str(settings_path),
        "exists": True,
        "selected_auth_type": data.get("selectedAuthType"),
        "api_key_present": bool(data.get("apiKey")),
        "security_auth_type": (data.get("security") or {}).get("auth", {}).get("selectedType")
        if isinstance(data.get("security"), dict)
        else None,
    }


def _trusted_folders_summary(trusted_folders_path: Path) -> dict[str, Any]:
    data = _read_json(trusted_folders_path)
    if isinstance(data, dict):
        folders = list(data.keys())
    elif isinstance(data, list):
        folders = data
    else:
        folders = []
    normalized = [str(item) for item in folders]
    profile = str(Path.home()).lower()
    profile_wide = any(Path(item).as_posix().lower().rstrip("/") == Path.home().as_posix().lower() for item in normalized)
    return {
        "path": str(trusted_folders_path),
        "exists": trusted_folders_path.exists(),
        "folders": normalized,
        "profile_wide_trust": profile_wide or any(item.lower().rstrip("\\/") == profile for item in normalized),
    }


def _extension_record(
    name: str,
    *,
    gemini_root: Path,
    skills_root: Path,
    enabled: bool,
    enablement: Any,
    integrity_store: dict[str, Any],
) -> dict[str, Any]:
    extension_dir = gemini_root / name
    manifest = _read_json(_manifest_path(gemini_root, name))
    manifest = manifest if isinstance(manifest, dict) else {}
    commands = _command_specs(extension_dir)
    mcp_servers = manifest.get("mcpServers") if isinstance(manifest.get("mcpServers"), dict) else {}
    adapter = _adapter_path(skills_root, name)
    overrides = []
    if isinstance(enablement, dict):
        raw_overrides = enablement.get("overrides", [])
        if isinstance(raw_overrides, list):
            overrides = [str(item) for item in raw_overrides]

    return {
        "name": name,
        "version": manifest.get("version"),
        "description": manifest.get("description", ""),
        "enabled": enabled,
        "gemini_status": _adapter_status(adapter),
        "path": str(extension_dir),
        "manifest_path": str(_manifest_path(gemini_root, name)),
        "adapter": adapter.parent.name if adapter.exists() else None,
        "adapter_path": str(adapter),
        "command_specs": commands,
        "command_count": len(commands),
        "mcp_servers": sorted(mcp_servers.keys()),
        "mcp_server_count": len(mcp_servers),
        "overrides": overrides,
        "profile_wide_override": any(str(item).replace("\\", "/").lower() == "/c:/users/vizio/*" for item in overrides),
        "integrity_recorded": name in integrity_store,
    }


def _discover_extensions(gemini_root: Path, skills_root: Path, integrity_path: Path) -> list[dict[str, Any]]:
    enabled = _enabled_map(gemini_root)
    integrity = _integrity_store(integrity_path)
    names: set[str] = set(enabled)
    if gemini_root.exists():
        names.update(path.name for path in gemini_root.iterdir() if path.is_dir())
    if skills_root.exists():
        names.update(path.name.removeprefix("gemini-") for path in skills_root.glob("gemini-*") if path.is_dir())
        names.discard("extension-router")

    return [
        _extension_record(
            name,
            gemini_root=gemini_root,
            skills_root=skills_root,
            enabled=name in enabled,
            enablement=enabled.get(name),
            integrity_store=integrity,
        )
        for name in sorted(names, key=str.lower)
    ]


def summarize_gemini_extensions(
    *,
    gemini_root: Path = DEFAULT_GEMINI_ROOT,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    integrity_path: Path = DEFAULT_INTEGRITY_PATH,
    settings_path: Path = DEFAULT_SETTINGS_PATH,
    trusted_folders_path: Path = DEFAULT_TRUSTED_FOLDERS_PATH,
) -> dict[str, Any]:
    """Return high-level Gemini extension health without executing Gemini code."""
    extensions = _discover_extensions(Path(gemini_root), Path(skills_root), Path(integrity_path))
    enabled = [item for item in extensions if item["enabled"]]
    disabled = [item for item in extensions if not item["enabled"]]
    risks: list[str] = []
    if any(item["profile_wide_override"] for item in enabled):
        risks.append("PROFILE_WIDE_OVERRIDES")
    if any(item["mcp_server_count"] for item in enabled):
        risks.append("MCP_SERVER_SURFACE")
    if any(not item["integrity_recorded"] for item in disabled):
        risks.append("DISABLED_EXTENSION_INTEGRITY_GAP")
    settings = _settings_summary(Path(settings_path))
    if settings.get("api_key_present"):
        risks.append("LOCAL_API_KEY_CONFIGURED")
    trusted = _trusted_folders_summary(Path(trusted_folders_path))
    if trusted.get("profile_wide_trust"):
        risks.append("PROFILE_WIDE_TRUST")

    return {
        "status": "OK",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "roots": {
            "gemini_extensions": str(gemini_root),
            "agents_skills": str(skills_root),
            "integrity": str(integrity_path),
        },
        "counts": {
            "total": len(extensions),
            "enabled": len(enabled),
            "disabled": len(disabled),
            "with_commands": sum(1 for item in extensions if item["command_count"]),
            "with_mcp_servers": sum(1 for item in extensions if item["mcp_server_count"]),
        },
        "risks": sorted(set(risks)),
        "settings": settings,
        "trusted_folders": trusted,
        "recommendations": [
            "Prefer repo-scoped Gemini trust over profile-wide trust.",
            "Disable unused MCP-heavy extensions before broad automation.",
            "Keep credentials out of printed command output and review .gemini ACLs.",
            "Use gemini-ext inspect <name> before wiring a synapse.",
        ],
    }


def list_gemini_extensions(
    *,
    gemini_root: Path = DEFAULT_GEMINI_ROOT,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    integrity_path: Path = DEFAULT_INTEGRITY_PATH,
) -> dict[str, Any]:
    """Return all known Gemini extensions with adapter and command metadata."""
    extensions = _discover_extensions(Path(gemini_root), Path(skills_root), Path(integrity_path))
    return {
        "status": "OK",
        "count": len(extensions),
        "extensions": extensions,
    }


def inspect_gemini_extension(
    name: str,
    *,
    gemini_root: Path = DEFAULT_GEMINI_ROOT,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
    integrity_path: Path = DEFAULT_INTEGRITY_PATH,
) -> dict[str, Any]:
    """Return one extension record by exact or adapter-prefixed name."""
    records = _discover_extensions(Path(gemini_root), Path(skills_root), Path(integrity_path))
    for record in records:
        if record["name"].lower() == name.lower():
            return {"status": "OK", **record}
    target = name.removeprefix("gemini-")
    for record in records:
        if record["name"].lower() == target.lower():
            return {"status": "OK", **record}
    return {"status": "NOT_FOUND", "name": name}
