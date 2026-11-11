# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — CONFIDENTIAL AND PROPRIETARY
"""
Bifrost → Sandbox Adapter (control-plane shim)
==============================================
Thin control-plane handle on the governed dispatch seam. The bridge core lives in
the cartridge package (02_FORGE/cartridge/bifrost_bridge.py) where all its
collaborators are; that tree is intentionally excluded from setuptools packaging,
so we add it to sys.path the same way the rest of the repo bridges into 02_FORGE.

Use this from the bifrost gateway ingress instead of routing a governed command
straight to a terminal:

    from control_plane.bifrost_sandbox_adapter import get_bridge
    result = get_bridge().handle_signed(raw_body, hmac_signature)

Environment:
    WEBHOOK_SECRET               shared HMAC secret (same as bifrost_gateway)
    CAMELOT_CARTRIDGE_PACKAGES   dir of fabricated manifests (default 02_FORGE/cartridge/packages)
    plus the trust/RBAC env from cartridge_trust / cartridge_rbac.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent.parent
_FORGE = _REPO / "02_FORGE"
if str(_FORGE) not in sys.path:
    sys.path.insert(0, str(_FORGE))

# Imported after the path insert so `cartridge` resolves to 02_FORGE/cartridge.
from cartridge.bifrost_bridge import (  # noqa: E402
    BifrostCartridgeBridge,
    GovernedDispatch,
    packages_manifest_loader,
    sign_body,
)
from cartridge.cartridge_rbac import RBACPolicy  # noqa: E402
from cartridge.cartridge_trust import TrustManager  # noqa: E402
from cartridge.sandbox import TrustMode  # noqa: E402
from cartridge.tool_registry import ToolRegistry  # noqa: E402

_DEFAULT_PACKAGES = _FORGE / "cartridge" / "packages"
_bridge: Optional[BifrostCartridgeBridge] = None


def build_bridge(
    *,
    registry: Optional[ToolRegistry] = None,
    enterprise_trust: bool = True,
    rbac: bool = True,
    packages_dir: Optional[str] = None,
    trust_mode: TrustMode = TrustMode.STRICT,
) -> BifrostCartridgeBridge:
    """Construct a fully-wired bridge (trust lifecycle + RBAC + real executor).

    PR #3 of NOTES_MNEMOSYNE_WIRING.md: register `dispatch_to_appwrite` so
    Bifrost ingress can route signed-RPC traffic to the Appwrite egress
    surface. Tolerates any ToolRegistry API (`register`, `bind`, or
    attribute assignment) for forward-compat with future cartridge versions.
    """
    pkg = packages_dir or os.getenv("CAMELOT_CARTRIDGE_PACKAGES") or str(_DEFAULT_PACKAGES)
    active_registry = registry or ToolRegistry(with_builtins=True)
    try:
        from control_plane.bifrost_appwrite_dispatch import dispatch_to_appwrite
        if hasattr(active_registry, "register"):
            active_registry.register("appwrite_egress", dispatch_to_appwrite)
        elif hasattr(active_registry, "bind"):
            active_registry.bind("appwrite_egress", dispatch_to_appwrite)
        else:
            active_registry.appwrite_egress = dispatch_to_appwrite
    except Exception:
        # Graceful degradation if PR #3 module not yet materialized
        # (e.g., during a partial checkout / CI smoke before PR #3 lands).
        pass
    return BifrostCartridgeBridge(
        manifest_loader=packages_manifest_loader(pkg),
        registry=active_registry,
        trust_manager=TrustManager() if enterprise_trust else None,
        rbac=RBACPolicy() if rbac else None,
        trust_mode=trust_mode,
    )


def get_bridge() -> BifrostCartridgeBridge:
    """Process-wide singleton bridge for the gateway ingress path."""
    global _bridge
    if _bridge is None:
        _bridge = build_bridge()
    return _bridge


__all__ = [
    "BifrostCartridgeBridge", "GovernedDispatch", "packages_manifest_loader",
    "sign_body", "build_bridge", "get_bridge",
]


if __name__ == "__main__":
    b = get_bridge()
    print("Bifrost→Sandbox adapter ready.")
    print("  packages:", os.getenv("CAMELOT_CARTRIDGE_PACKAGES") or str(_DEFAULT_PACKAGES))
    print("  tools   :", b._registry.tool_ids)
