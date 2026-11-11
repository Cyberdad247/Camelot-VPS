# SPDX-License-Identifier: MIT

"""
Sovereign Inference Engine (SIE) — CAMELOT-OS native local inference layer.

Replaces the raw Ollama HTTP sidecar call with a Python-first dispatch path
that adds:
  - HITL hook: pre-generation gate to block or rewrite prompts
  - Token interceptor: per-chunk processing (filter, redact, halt)
  - Post-generation telemetry: token counts, latency, model, knight_id
  - Model manifest: CAMELOT-native registry decoupled from Ollama tags
  - Air-gapped mode: hard-block if a cloud backend is requested
  - Programmatic model lifecycle: load / unload / list without CLI

Backends (pluggable):
  OllamaBackend  — uses ollama Python SDK (default, zero extra installs)
  NullBackend    — stub for testing / air-gapped stubs

Usage (in Bifrost):
    from control_plane.sovereign_inference import SIE
    async for chunk in SIE.generate_stream("sir_ghost", prompt, system):
        yield chunk

# HITL: file-ops pre-approved — writes bounded to telemetry log and model manifest cache
"""
from __future__ import annotations

import json
import logging
import os
import time
from asyncio import to_thread
from dataclasses import asdict, dataclass, field
from ipaddress import ip_address
from pathlib import Path
from typing import AsyncIterator, Callable, Protocol, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

log = logging.getLogger("sie")

CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
_MANIFEST_PATH = CAMELOT_HOME / "03_VAULT" / "training" / "configs" / "sovereign_models.json"
_TELEMETRY_LOG = CAMELOT_HOME / "logs" / "sie_telemetry.jsonl"


# ── Hook contracts ────────────────────────────────────────────────────────────

class HITLBlock(Exception):
    """Raised by a pre_generate hook to halt dispatch before inference begins."""


@dataclass
class SIETelemetry:
    knight_id:    str
    model:        str
    backend:      str
    prompt_tokens: int
    output_tokens: int
    latency_ms:   float
    halted:       bool = False
    ts:           float = field(default_factory=time.time)


@dataclass
class SIEHooks:
    """Optional hooks injected at each stage of a generation call.

    pre_generate:
        (prompt, system) → (prompt, system)
        Raise HITLBlock to abort. Use for HITL approval, sanitisation,
        or context injection.

    token_interceptor:
        (chunk: str) → str | None
        Return the chunk as-is, modified, or None to halt the stream.

    post_generate:
        (full_text: str, telemetry: SIETelemetry) → None
        Fire-and-forget; exceptions are swallowed.
    """
    pre_generate:       Callable[[str, str], tuple[str, str]] | None = None
    token_interceptor:  Callable[[str], str | None] | None = None
    post_generate:      Callable[[str, SIETelemetry], None] | None = None


# ── Backend protocol ──────────────────────────────────────────────────────────

@runtime_checkable
class SIEBackend(Protocol):
    name: str

    async def stream(
        self,
        model: str,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> AsyncIterator[str]: ...

    def list_models(self) -> list[str]: ...
    def health(self) -> bool: ...


# ── Ollama backend ────────────────────────────────────────────────────────────

class OllamaBackend:
    """Thin async wrapper over the ollama Python SDK.

    Uses ollama.AsyncClient so every call is non-blocking and plays
    nicely with the CAMELOT asyncio event loop.
    """

    name = "ollama"

    def __init__(self, host: str = "http://127.0.0.1:11434") -> None:
        self._host = host
        self._client: object | None = None

    def _get_client(self):
        if self._client is None:
            import ollama
            self._client = ollama.AsyncClient(host=self._host)
        return self._client

    async def stream(
        self,
        model: str,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        import ollama as _ollama
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            async for part in await client.chat(
                model=model,
                messages=messages,
                stream=True,
                options={"num_predict": max_tokens},
            ):
                chunk = part.message.content or ""
                if chunk:
                    yield chunk
        except _ollama.ResponseError as e:
            yield f"\n[SIE/Ollama] ResponseError: {e}"
        except Exception as e:
            yield f"\n[SIE/Ollama] {type(e).__name__}: {e}"

    def list_models(self) -> list[str]:
        import ollama
        try:
            result = ollama.list()
            return [m.model for m in result.models]
        except Exception:
            return []

    def health(self) -> bool:
        import socket
        try:
            s = socket.create_connection(("127.0.0.1", 11434), timeout=1.0)
            s.close()
            return True
        except Exception:
            return False

    async def pull(self, model: str) -> None:
        client = self._get_client()
        await client.pull(model)

    async def unload(self, model: str) -> None:
        """Ask Ollama to unload a model from VRAM/RAM."""
        client = self._get_client()
        try:
            # keepalive=0 forces immediate unload
            await client.generate(model=model, prompt="", keep_alive=0)
        except Exception:
            pass


class CLIProxyBackend:
    """Loopback-only OpenAI-compatible backend for CLIProxyAPI.

    The proxy is deliberately opt-in: SIE selects it only for an explicit
    ``cliproxy:<model>`` selector or a model manifest entry using this backend.
    """

    name = "cliproxy"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = (base_url or os.environ.get("CLIPROXY_BASE") or "http://127.0.0.1:8080/v1").rstrip("/")
        parsed = urlparse(self._base_url)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or not self._is_loopback(host):
            raise ValueError("CLIProxyAPI base URL must use a loopback host")
        self._api_key = (api_key if api_key is not None else (os.environ.get("CLIPROXY_API_KEY") or "")).strip()
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _is_loopback(host: str) -> bool:
        if host.lower() == "localhost":
            return True
        try:
            return ip_address(host).is_loopback
        except ValueError:
            return False

    def _request_json(self, path: str, body: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        data = None
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self._base_url}{path}", data=data, headers=headers, method="POST" if body is not None else "GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310 -- URL is loopback-validated above.
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CLIProxyAPI returned a non-object JSON response")
        return payload

    async def stream(
        self,
        model: str,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        if not self._api_key:
            yield "[SIE/CLIProxy] credential unavailable: set CLIPROXY_API_KEY in the runtime environment"
            return
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        # Auto-fallback is a pseudo-model on this host (502); pin to a live
        # gemini tiered model so cliproxy:default never surfaces a transport error.
        if model == "auto-fallback":
            try:
                live = self.list_models()
                if "gemini-3.7-flash-tiered" in live:
                    model = "gemini-3.7-flash-tiered"
                elif live:
                    model = live[0]
            except Exception:
                pass
        try:
            payload = await to_thread(
                self._request_json,
                "/chat/completions",
                {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": False},
            )
            content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not isinstance(content, str):
                raise ValueError("CLIProxyAPI returned a non-text completion")
            if content:
                yield content
        except (HTTPError, URLError, OSError, ValueError, IndexError, KeyError) as exc:
            yield f"[SIE/CLIProxy] {type(exc).__name__}: {exc}"

    def list_models(self) -> list[str]:
        if not self._api_key:
            return []
        try:
            payload = self._request_json("/models")
            return [item["id"] for item in payload.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]
        except (HTTPError, URLError, OSError, ValueError):
            return []

    def health(self) -> bool:
        if not self._api_key:
            return False
        try:
            self._request_json("/models")
            return True
        except (HTTPError, URLError, OSError, ValueError):
            return False


class VLLMBackend:
    """OpenAI-compatible backend for vLLM servers (e.g. `vllm serve`).

    Supports local or remote vLLM instances serving models like DeepSeek, Qwen, or Llama
    via OpenAI-compatible /v1/chat/completions and /v1/completions endpoints.
    """

    name = "vllm"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = (base_url or os.environ.get("VLLM_BASE_URL") or "http://127.0.0.1:8000/v1").rstrip("/")
        self._api_key = api_key if api_key is not None else os.environ.get("VLLM_API_KEY", "")
        self._timeout_seconds = timeout_seconds

    def _request_json(self, path: str, body: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        data = None
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self._base_url}{path}", data=data, headers=headers, method="POST" if body is not None else "GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("vLLM returned a non-object JSON response")
        return payload

    async def stream(
        self,
        model: str,
        prompt: str,
        system: str,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            payload = await to_thread(
                self._request_json,
                "/chat/completions",
                {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": False},
            )
            choices = payload.get("choices", [{}])
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            if not content and choices:
                # Fallback to text completion if message content is empty
                content = choices[0].get("text", "")
            if not isinstance(content, str):
                raise ValueError("vLLM returned a non-text completion")
            if content:
                yield content
        except (HTTPError, URLError, OSError, ValueError, IndexError, KeyError) as exc:
            yield f"[SIE/vLLM] {type(exc).__name__}: {exc}"

    def list_models(self) -> list[str]:
        try:
            payload = self._request_json("/models")
            return [item["id"] for item in payload.get("data", []) if isinstance(item, dict) and isinstance(item.get("id"), str)]
        except (HTTPError, URLError, OSError, ValueError):
            return []

    def health(self) -> bool:
        try:
            self._request_json("/models")
            return True
        except (HTTPError, URLError, OSError, ValueError):
            return False


# ── Null backend (testing / offline stub) ────────────────────────────────────

class NullBackend:
    name = "null"

    async def stream(self, model, prompt, system, max_tokens) -> AsyncIterator[str]:
        yield f"[SIE/Null] model={model} — no backend configured"

    def list_models(self) -> list[str]:
        return []

    def health(self) -> bool:
        return True


# ── Model manifest ────────────────────────────────────────────────────────────

_DEFAULT_MANIFEST: dict = {
    "version": 1,
    "models": {
        "sir_ghost":    {"backend": "ollama", "tag": "qwen3:4b",         "air_gapped": True},
        "sir_forge":    {"backend": "ollama", "tag": "qwen2.5-coder:3b", "air_gapped": True},
        "sir_zeroclaw": {"backend": "ollama", "tag": "qwen3:4b",         "air_gapped": True},
        "sir_gideon":   {"backend": "ollama", "tag": "qwen3:4b",         "air_gapped": False},
        "qwen3:4b":     {"backend": "ollama", "tag": "qwen3:4b",         "air_gapped": False},
        "qwen2.5-coder:3b": {"backend": "ollama", "tag": "qwen2.5-coder:3b", "air_gapped": False},
        "qwen3.5:4b":   {"backend": "ollama", "tag": "qwen3.5:4b",       "air_gapped": False},
        "gemma3:4b":    {"backend": "ollama", "tag": "gemma3:4b",        "air_gapped": False},
    },
}


# ── Sovereign Inference Engine ────────────────────────────────────────────────

class SovereignInferenceEngine:
    """CAMELOT-native local inference layer.

    Single shared instance — use the module-level ``SIE`` singleton.
    """

    def __init__(self) -> None:
        self._manifest: dict = {}
        self._backends: dict[str, SIEBackend] = {
            "ollama": OllamaBackend(),
            "cliproxy": CLIProxyBackend(),
            "vllm": VLLMBackend(),
            "null":   NullBackend(),
        }
        self._default_backend = "ollama"
        self._air_gapped = False
        self._load_manifest()

    # ── Manifest ──────────────────────────────────────────────────────────────

    def _load_manifest(self) -> None:
        if _MANIFEST_PATH.exists():
            try:
                self._manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
            except Exception:
                self._manifest = dict(_DEFAULT_MANIFEST)
        else:
            self._manifest = dict(_DEFAULT_MANIFEST)
            self._save_manifest()

    def _save_manifest(self) -> None:
        _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MANIFEST_PATH.write_text(
            json.dumps(self._manifest, indent=2), encoding="utf-8"
        )

    def reload_manifest(self) -> None:
        self._load_manifest()

    def register_model(
        self,
        model_id: str,
        backend: str,
        tag: str,
        air_gapped: bool = False,
    ) -> None:
        """Add or update a model entry in the manifest."""
        self._manifest.setdefault("models", {})[model_id] = {
            "backend": backend,
            "tag": tag,
            "air_gapped": air_gapped,
        }
        self._save_manifest()

    # ── Config ────────────────────────────────────────────────────────────────

    def set_air_gapped(self, enabled: bool) -> None:
        """When True, any call that would reach a cloud backend raises HITLBlock."""
        self._air_gapped = enabled

    def register_backend(self, name: str, backend: SIEBackend) -> None:
        self._backends[name] = backend

    # ── Core generation ───────────────────────────────────────────────────────

    async def generate_stream(
        self,
        model_id: str,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        hooks: SIEHooks | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from the sovereign inference layer.

        Applies hooks in order:
          1. pre_generate  — rewrite / gate prompt before dispatch
          2. token_interceptor — filter or halt per chunk
          3. post_generate — fire-and-forget telemetry
        """
        t0 = time.perf_counter()
        hooks = hooks or SIEHooks()

        # Resolve model entry from manifest
        models = self._manifest.get("models", {})
        entry = models.get(model_id) or models.get(model_id.lower())
        if entry is None and model_id.lower().startswith("cliproxy:"):
            entry = {
                "backend": "cliproxy",
                "tag": model_id.split(":", 1)[1],
                "air_gapped": False,
            }
        if entry is None and model_id.lower().startswith("vllm:"):
            entry = {
                "backend": "vllm",
                "tag": model_id.split(":", 1)[1],
                "air_gapped": False,
            }
        if entry is None:
            # Fallback: treat model_id as a raw Ollama tag
            entry = {"backend": "ollama", "tag": model_id, "air_gapped": False}

        backend_name = entry.get("backend", self._default_backend)
        model_tag = entry.get("tag", model_id)
        is_air_gapped = entry.get("air_gapped", False)

        # Air-gapped enforcement
        if self._air_gapped and not is_air_gapped:
            yield "[SIE] Air-gapped mode: request blocked — model not marked air_gapped"
            return

        backend = self._backends.get(backend_name) or self._backends["null"]

        # 1. Pre-generate hook
        if hooks.pre_generate:
            try:
                prompt, system = hooks.pre_generate(prompt, system)
            except HITLBlock as e:
                yield f"[SIE] HITL block: {e}"
                return

        # Approximate token count (word-split heuristic)
        prompt_tokens = len(prompt.split()) + len(system.split())
        output_tokens = 0
        halted = False
        full_text: list[str] = []

        # 2. Stream with token interceptor
        try:
            async for chunk in backend.stream(model_tag, prompt, system, max_tokens):
                output_tokens += len(chunk.split())
                if hooks.token_interceptor:
                    result = hooks.token_interceptor(chunk)
                    if result is None:
                        halted = True
                        break
                    chunk = result
                full_text.append(chunk)
                yield chunk
        except GeneratorExit:
            pass

        # 3. Post-generate hook (fire-and-forget)
        telemetry = SIETelemetry(
            knight_id=model_id,
            model=model_tag,
            backend=backend_name,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=(time.perf_counter() - t0) * 1000,
            halted=halted,
        )
        self._record_telemetry(telemetry)
        if hooks.post_generate:
            try:
                hooks.post_generate("".join(full_text), telemetry)
            except Exception:
                pass

    # ── Model lifecycle ───────────────────────────────────────────────────────

    async def pull(self, model_id: str) -> None:
        """Pull a model via its registered backend (Ollama: download GGUF)."""
        entry = self._manifest.get("models", {}).get(model_id, {})
        backend_name = entry.get("backend", "ollama")
        model_tag = entry.get("tag", model_id)
        backend = self._backends.get(backend_name)
        if hasattr(backend, "pull"):
            await backend.pull(model_tag)

    async def unload(self, model_id: str) -> None:
        """Unload a model from RAM (Ollama: keepalive=0)."""
        entry = self._manifest.get("models", {}).get(model_id, {})
        backend_name = entry.get("backend", "ollama")
        model_tag = entry.get("tag", model_id)
        backend = self._backends.get(backend_name)
        if hasattr(backend, "unload"):
            await backend.unload(model_tag)

    # ── Introspection ─────────────────────────────────────────────────────────

    def list_models(self) -> list[dict]:
        """Return manifest entries enriched with live availability."""
        live = set()
        for backend in self._backends.values():
            try:
                live.update(backend.list_models())
            except Exception:
                pass
        result = []
        for mid, entry in self._manifest.get("models", {}).items():
            tag = entry.get("tag", mid)
            result.append({
                "model_id":   mid,
                "tag":        tag,
                "backend":    entry.get("backend"),
                "air_gapped": entry.get("air_gapped", False),
                "available":  tag in live,
            })
        return result

    def health(self) -> dict:
        """Snapshot health of the SIE and all registered backends."""
        return {
            "air_gapped": self._air_gapped,
            "manifest_models": len(self._manifest.get("models", {})),
            "backends": {
                name: backend.health()
                for name, backend in self._backends.items()
            },
        }

    # ── Telemetry ─────────────────────────────────────────────────────────────

    def _record_telemetry(self, t: SIETelemetry) -> None:
        try:
            _TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
            with _TELEMETRY_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(t)) + "\n")
        except Exception:
            pass


# ── Module-level singleton ────────────────────────────────────────────────────

SIE = SovereignInferenceEngine()
