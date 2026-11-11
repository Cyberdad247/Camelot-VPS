# SPDX-License-Identifier: MIT

# Camelot Apex OS — Control Plane Package
#
# Modules are organized into subdirectories:
#   core/     — gate, governance, HITL (anya_gate, factory_lane, soul_oversight, ...)
#   dispatch/ — routing, dispatch, agent management (bifrost, switchboard, ...)
#   runes/    — runic commands, CLI, TOON (runic_router, camelot_cli, ...)
#   infra/    — infrastructure, memory, sync, observability, bridges, phase_h, ...
#   cluster/  — swarm daemons (agents_daemon, consensus_daemon, ...)
#
# A meta-path finder intercepts ``control_plane.<module>`` imports and
# redirects them to the correct subdirectory, so legacy code like
# ``from control_plane.anya_gate import AnyaGate`` continues to work.

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_PACKAGE_DIR = Path(__file__).resolve().parent
_SUBDIRS = ("core", "dispatch", "runes", "infra", "cluster")


class _ControlPlaneModuleLoader:
    """Loader wrapper for redirected legacy imports.

    The redirected module is loaded under the REQUESTED legacy name
    (``control_plane.<leaf>``) — required so ``python -m control_plane.<leaf>``
    (runpy) sees ``spec.name == mod_name`` — then the canonical name
    (``control_plane.<subdir>.<leaf>``) is aliased in ``sys.modules`` to the
    SAME module object. Without the alias, ``control_plane.runic_router`` and
    ``control_plane.runes.runic_router`` would be two separate instances of
    one file — breaking monkeypatching (a test patch on one name would not be
    visible through the other) and identity checks. The canonical parent
    subpackage is also wired so ``import control_plane.runes.runic_router as
    x`` (which getattrs the parent) resolves.
    """

    def __init__(self, inner: Any, canonical: str):
        self._inner = inner
        self._canonical = canonical

    def create_module(self, spec: Any) -> Any:
        if hasattr(self._inner, "create_module"):
            return self._inner.create_module(spec)
        return None

    def get_code(self, fullname: str) -> Any:
        """Delegate to the inner loader so ``python -m control_plane.<name>``
        (runpy) can execute the redirected module."""
        return self._inner.get_code(fullname)

    def get_source(self, fullname: str) -> Any:
        if hasattr(self._inner, "get_source"):
            return self._inner.get_source(fullname)
        return None

    def is_package(self, fullname: str) -> bool:
        if hasattr(self._inner, "is_package"):
            return self._inner.is_package(fullname)
        return False

    def exec_module(self, module: Any) -> None:
        self._inner.exec_module(module)
        canonical = self._canonical
        sys.modules[canonical] = module
        # Wire the canonical parent chain (e.g. control_plane.runes) so the
        # getattr-based `import control_plane.runes.runic_router as x` form
        # resolves even though this loader never imported the parent package.
        parent_name = canonical.rpartition(".")[0]
        if parent_name and parent_name not in sys.modules:
            importlib.import_module(parent_name)
        parent = sys.modules.get(parent_name)
        if parent is not None:
            leaf = canonical.rpartition(".")[2]
            if not hasattr(parent, leaf):
                setattr(parent, leaf, module)
            grand_name = parent_name.rpartition(".")[0]
            grand = sys.modules.get(grand_name)
            if grand is not None and parent_name != grand_name:
                p_leaf = parent_name.rpartition(".")[2]
                if not hasattr(grand, p_leaf):
                    setattr(grand, p_leaf, parent)


class _ExistingModuleLoader:
    """Loader that returns an already-imported canonical module for a legacy
    alias (e.g. ``control_plane.runes.runic_router`` was imported first, then
    ``control_plane.runic_router``). Ensures both names share one instance.

    ``module_from_spec`` overwrites the shared module's ``__spec__``/
    ``__name__``/``__package__`` with the alias spec before ``exec_module``
    runs, which would break ``importlib.reload()`` and introspection. The
    loader captures the module's ORIGINAL canonical spec in ``create_module``
    (before the overwrite) and restores it here without re-executing the
    module body — the module is already fully executed.
    """

    def __init__(self, existing: Any):
        self._existing = existing
        self._original_spec = None

    def create_module(self, spec: Any) -> Any:
        # Capture before module_from_spec() overwrites __spec__ below.
        self._original_spec = self._existing.__spec__
        return self._existing

    def exec_module(self, module: Any) -> None:
        orig = self._original_spec
        if orig is not None:
            module.__spec__ = orig
            module.__loader__ = orig.loader
            module.__name__ = orig.name
            module.__package__ = orig.parent

    def get_code(self, fullname: str) -> Any:
        spec = self._existing.__spec__
        if spec is not None and spec.loader is not None:
            return spec.loader.get_code(spec.name)
        return None

    def get_source(self, fullname: str) -> Any:
        spec = self._existing.__spec__
        if spec is not None and spec.loader is not None:
            inner = spec.loader
            if hasattr(inner, "get_source"):
                return inner.get_source(spec.name)
        return None

    def is_package(self, fullname: str) -> bool:
        return False


class _ControlPlaneModuleFinder:
    """Meta-path finder that redirects ``control_plane.<name>`` imports
    to ``control_plane.<subdir>.<name>`` when the bare module has been
    moved into a subdirectory."""

    def find_spec(self, fullname: str, path: Any, target: Any = None) -> Any:
        if not fullname.startswith("control_plane."):
            return None
        # Skip the package itself and dunder modules
        if fullname == "control_plane":
            return None
        if fullname.split(".")[-1].startswith("_"):
            return None

        # Only redirect bare legacy imports (control_plane.<name>). Imports
        # that already name a real subdirectory (control_plane.<subdir>.<name>)
        # must resolve through normal package machinery — redirecting them
        # loads the file under the wrong __package__, breaking their relative
        # imports (e.g. cli_intercept's `from .main` resolved to
        # control_plane.runes.main instead of control_plane.infra.main).
        parts = fullname.split(".")
        if len(parts) > 2 and parts[1] in _SUBDIRS:
            return None
        leaf = parts[-1]

        for subdir in _SUBDIRS:
            candidate = _PACKAGE_DIR / subdir / f"{leaf}.py"
            if candidate.is_file():
                canonical = f"control_plane.{subdir}.{leaf}"
                # The canonical module may already be imported (canonical
                # name used before the legacy alias). Reuse that instance so
                # both names stay one object instead of double-loading.
                #
                # ``importlib.reload()`` is the exception. It re-executes a
                # module by re-running its body, but ``_ExistingModuleLoader``
                # deliberately skips execution (the module is already loaded),
                # so a reload would leave stale module-level state behind —
                # e.g. a session flag stuck at True. ``reload()`` is the only
                # caller that passes ``target``, so treat a non-None target as
                # the reload signal and fall through to a genuine
                # re-execution under the requested name.
                if canonical in sys.modules and target is None:
                    spec = importlib.util.spec_from_loader(fullname, _ExistingModuleLoader(sys.modules[canonical]))
                    spec.submodule_search_locations = None
                    return spec
                # Load under the REQUESTED legacy name (runpy's ``-m`` path
                # requires spec.name == requested name), then alias the
                # canonical name to the same object.
                spec = importlib.util.spec_from_file_location(fullname, str(candidate))
                if spec is not None:
                    spec.submodule_search_locations = None
                    spec.loader = _ControlPlaneModuleLoader(spec.loader, canonical)
                    return spec

        return None


def _install() -> None:
    """Insert the redirecting finder into sys.meta_path once."""
    for entry in sys.meta_path:
        if isinstance(entry, _ControlPlaneModuleFinder):
            return
    sys.meta_path.insert(0, _ControlPlaneModuleFinder())


_install()
