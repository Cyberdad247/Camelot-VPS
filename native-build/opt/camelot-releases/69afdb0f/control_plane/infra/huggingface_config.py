# Copyright (c) 2026 Invisioned Marketing Inc. All rights reserved.
# Camelot Apex OS — HuggingFace Hub & Inference Configuration
r"""
Configures HuggingFace model cache, fast transfer engine, download timeouts,
and embedding model defaults for Camelot-OS.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_HF_CACHE = _REPO_ROOT / ".cache" / "huggingface"
_DEFAULT_HF_CACHE.mkdir(parents=True, exist_ok=True)


class HuggingFaceConfig:
    """Manages HuggingFace environment settings, model cache, and Hub configurations."""

    def __init__(self):
        self.cache_dir = Path(os.getenv("HF_HOME", str(_DEFAULT_HF_CACHE)))
        self.fast_transfer = os.getenv("HF_HUB_ENABLE_HF_TRANSFER", "1") == "1"
        self.download_timeout = int(os.getenv("HF_HUB_DOWNLOAD_TIMEOUT", "600"))
        self.default_embedding_model = os.getenv("HF_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        self.token_configured = bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN"))
        self._apply_env()

    def _apply_env(self) -> None:
        """Applies configured HuggingFace environment variables to current process."""
        os.environ["HF_HOME"] = str(self.cache_dir)
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1" if self.fast_transfer else "0"
        os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = str(self.download_timeout)

    def get_status(self) -> Dict[str, Any]:
        """Returns HuggingFace hub configuration status."""
        return {
            "cache_dir": str(self.cache_dir),
            "fast_transfer_enabled": self.fast_transfer,
            "download_timeout_sec": self.download_timeout,
            "default_embedding_model": self.default_embedding_model,
            "token_configured": self.token_configured,
            "status": "CONFIGURED",
        }


def get_huggingface_config() -> HuggingFaceConfig:
    """Singleton getter for HuggingFace configuration."""
    return HuggingFaceConfig()


if __name__ == "__main__":
    import json
    cfg = get_huggingface_config()
    print(json.dumps(cfg.get_status(), indent=2))
