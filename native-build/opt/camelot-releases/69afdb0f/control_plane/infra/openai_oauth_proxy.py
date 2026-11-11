# SPDX-License-Identifier: MIT

"""OpenAI OAuth Dev Proxy — ChatGPT Account-to-API local bridge for CAMELOT-OS.

Assimilated from ``openai-oauth`` (zero external deps outside Python stdlib):
- Turns a ChatGPT user/pro account into an OpenAI-compatible API on ``http://127.0.0.1:10531/v1``.
- Zero API key required — leverages local token cache at ``~/.codex/auth.json`` or ``$CODEX_HOME/auth.json``.
- Automatic OAuth token refresh before expiry.
- Endpoints:
    - ``GET  /health``
    - ``GET  /v1/models``
    - ``POST /v1/chat/completions`` (streaming + non-streaming, function/tool calls)
    - ``POST /v1/responses`` (Codex responses protocol)
    - ``POST /v1/images/generations`` (GPT Image 2 generation)
    - ``POST /v1/images/edits`` (Multipart image edit)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger("camelot.openai_oauth_proxy")

# ── Constants & Configuration ────────────────────────────────────────────────

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10531
DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_OPENAI_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_OPENAI_OAUTH_ISSUER = "https://auth.openai.com"
DEFAULT_CODEX_CLIENT_VERSION = "0.144.1"
CODEX_IMAGE_MODEL = "gpt-image-2"

REFRESH_EXPIRY_MARGIN_SECONDS = 5 * 60  # 5 minutes margin
REFRESH_INTERVAL_SECONDS = 55 * 60      # 55 minutes interval
MODEL_CATALOG_TTL_SECONDS = 5 * 60     # 5 minutes model cache


# ── Token & Auth Management ──────────────────────────────────────────────────

@dataclass
class StoredTokens:
    id_token: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    account_id: Optional[str] = None


@dataclass
class EffectiveAuth:
    access_token: str
    account_id: str
    is_fedramp: bool = False
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None
    source_path: Optional[str] = None
    last_refresh: Optional[str] = None


def decode_base64_url(val: str) -> Optional[str]:
    """Decode base64url encoded string."""
    try:
        padded = val + "=" * ((-len(val) % 4) + 4 if len(val) % 4 != 0 else 0)
        padded = padded.replace("-", "+").replace("_", "/")
        raw = base64.b64decode(padded)
        return raw.decode("utf-8")
    except Exception:
        return None


def parse_jwt_claims(token: Optional[str]) -> Optional[dict[str, Any]]:
    """Parse JWT claims without crypto verification (for expiry & account discovery)."""
    if not token or "." not in token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload_str = decode_base64_url(parts[1])
    if not payload_str:
        return None
    try:
        data = json.loads(payload_str)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def derive_account_id(id_token: Optional[str]) -> Optional[str]:
    """Derive ChatGPT account_id from JWT claims."""
    claims = parse_jwt_claims(id_token)
    if not claims:
        return None
    auth_claim = claims.get("https://api.openai.com/auth")
    if isinstance(auth_claim, dict):
        acc_id = auth_claim.get("chatgpt_account_id")
        if isinstance(acc_id, str) and acc_id:
            return acc_id
    top_acc_id = claims.get("chatgpt_account_id")
    if isinstance(top_acc_id, str) and top_acc_id:
        return top_acc_id
    return None


def derive_chatgpt_account_is_fedramp(token: Optional[str]) -> bool:
    """Derive FedRAMP account boolean from token claims."""
    claims = parse_jwt_claims(token)
    if not claims:
        return False
    auth_claim = claims.get("https://api.openai.com/auth")
    if isinstance(auth_claim, dict) and auth_claim.get("is_fedramp") is True:
        return True
    return claims.get("is_fedramp") is True


def resolve_auth_file_candidates(custom_path: Optional[str] = None) -> list[str]:
    """Resolve candidate filepaths for auth.json in order of priority."""
    if custom_path:
        return [custom_path]
    candidates: list[str] = []
    codex_home = os.getenv("CODEX_HOME")
    if codex_home:
        candidates.append(os.path.join(codex_home, "auth.json"))
    user_home = Path.home()
    candidates.append(str(user_home / ".codex" / "auth.json"))
    # Also check Camelot credentials vault if present
    camelot_home = os.getenv("CAMELOT_HOME", ".")
    candidates.append(str(Path(camelot_home) / "03_VAULT" / "credentials" / "oauth_creds.json"))

    seen = set()
    result = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def parse_iso_date(val: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 date string to UTC datetime."""
    if not val or not isinstance(val, str):
        return None
    try:
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def should_refresh_access_token(
    access_token: Optional[str],
    last_refresh: Optional[str],
    now: Optional[datetime] = None,
) -> bool:
    """Check whether token should be refreshed based on exp or last_refresh time."""
    if not access_token:
        return True
    now_dt = now or datetime.now(timezone.utc)
    claims = parse_jwt_claims(access_token)
    if claims and isinstance(claims.get("exp"), (int, float)):
        expiry_ts = float(claims["exp"])
        if expiry_ts <= now_dt.timestamp() + REFRESH_EXPIRY_MARGIN_SECONDS:
            return True

    refreshed_at = parse_iso_date(last_refresh)
    if refreshed_at:
        if refreshed_at.timestamp() <= now_dt.timestamp() - REFRESH_INTERVAL_SECONDS:
            return True
    return False


def refresh_openai_oauth_tokens(
    refresh_token: str,
    client_id: str = DEFAULT_OPENAI_OAUTH_CLIENT_ID,
    issuer: str = DEFAULT_OPENAI_OAUTH_ISSUER,
    token_url: Optional[str] = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Exchange refresh token with OpenAI OAuth server."""
    target_url = token_url or f"{issuer.rstrip('/')}/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        target_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError("Invalid OAuth response body.")
        return parsed


def load_auth_tokens(
    auth_file_path: Optional[str] = None,
    ensure_fresh: bool = True,
    client_id: str = DEFAULT_OPENAI_OAUTH_CLIENT_ID,
    issuer: str = DEFAULT_OPENAI_OAUTH_ISSUER,
) -> EffectiveAuth:
    """Load, validate, and optionally refresh ChatGPT OAuth credentials."""
    candidates = resolve_auth_file_candidates(auth_file_path)
    loaded_data: dict[str, Any] = {}
    found_path: Optional[str] = None

    for candidate in candidates:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        loaded_data = data
                        found_path = candidate
                        break
            except Exception as e:
                logger.debug("Failed reading candidate %s: %s", candidate, e)

    tokens_dict = loaded_data.get("tokens", {})
    if not isinstance(tokens_dict, dict):
        tokens_dict = {}

    access_token = tokens_dict.get("access_token") or loaded_data.get("access_token")
    id_token = tokens_dict.get("id_token") or loaded_data.get("id_token")
    refresh_token = tokens_dict.get("refresh_token") or loaded_data.get("refresh_token")
    account_id = (
        tokens_dict.get("account_id")
        or loaded_data.get("account_id")
        or derive_account_id(id_token)
        or derive_account_id(access_token)
    )
    last_refresh = loaded_data.get("last_refresh")
    is_fedramp = (
        derive_chatgpt_account_is_fedramp(id_token)
        or derive_chatgpt_account_is_fedramp(access_token)
    )

    now_dt = datetime.now(timezone.utc)
    if ensure_fresh and refresh_token and should_refresh_access_token(access_token, last_refresh, now_dt):
        try:
            refreshed = refresh_openai_oauth_tokens(
                refresh_token=refresh_token,
                client_id=client_id,
                issuer=issuer,
            )
            access_token = refreshed.get("access_token", access_token)
            id_token = refreshed.get("id_token", id_token)
            refresh_token = refreshed.get("refresh_token", refresh_token)
            account_id = (
                refreshed.get("account_id")
                or derive_account_id(id_token)
                or derive_account_id(access_token)
                or account_id
            )
            is_fedramp = is_fedramp or derive_chatgpt_account_is_fedramp(id_token)
            last_refresh = now_dt.isoformat()

            # Save back to file if possible
            write_target = found_path or candidates[0]
            try:
                os.makedirs(os.path.dirname(os.path.abspath(write_target)), exist_ok=True)
                save_data = dict(loaded_data)
                save_data["auth_mode"] = "chatgpt"
                save_data["tokens"] = {
                    "id_token": id_token,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "account_id": account_id,
                }
                save_data["last_refresh"] = last_refresh
                with open(write_target, "w", encoding="utf-8") as f:
                    json.dump(save_data, f, indent=2)
                found_path = write_target
            except Exception as e:
                logger.warning("Could not persist refreshed tokens to %s: %s", write_target, e)
        except Exception as e:
            logger.warning("OAuth token refresh failed: %s", e)

    if not access_token:
        raise ValueError("ChatGPT access token not found. Run `npx openai-oauth login` or configure auth.json.")
    if not account_id:
        raise ValueError("ChatGPT account id not found in token claims or auth.json.")

    return EffectiveAuth(
        access_token=str(access_token),
        account_id=str(account_id),
        is_fedramp=bool(is_fedramp),
        id_token=str(id_token) if id_token else None,
        refresh_token=str(refresh_token) if refresh_token else None,
        source_path=found_path,
        last_refresh=str(last_refresh) if last_refresh else None,
    )


# ── Upstream Codex Client & Normalization ────────────────────────────────────

class OpenAIOAuthClient:
    """Client that dispatches requests to ChatGPT Codex upstream using OAuth Bearer headers."""

    def __init__(
        self,
        base_url: str = DEFAULT_CODEX_BASE_URL,
        auth_file_path: Optional[str] = None,
        client_version: str = DEFAULT_CODEX_CLIENT_VERSION,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_file_path = auth_file_path
        self.client_version = client_version
        self._models_cache: list[str] = []
        self._models_cache_exp: float = 0.0
        self._lock = threading.Lock()

    def get_auth(self) -> EffectiveAuth:
        return load_auth_tokens(auth_file_path=self.auth_file_path)

    def request(
        self,
        endpoint: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: float = 60.0,
    ) -> Tuple[int, dict[str, str], bytes]:
        auth = self.get_auth()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req_headers = {
            "Authorization": f"Bearer {auth.access_token}",
            "chatgpt-account-id": auth.account_id,
            "Accept": "application/json",
            "User-Agent": f"CamelotOS-OpenAIOAuth/{self.client_version}",
        }
        if auth.is_fedramp:
            req_headers["X-OpenAI-Fedramp"] = "true"
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                resp_body = resp.read()
                return resp.status, resp_headers, resp_body
        except urllib.error.HTTPError as e:
            resp_headers = {k.lower(): v for k, v in e.headers.items()}
            resp_body = e.read()
            return e.code, resp_headers, resp_body

    def list_models(self) -> list[str]:
        with self._lock:
            if self._models_cache and time.time() < self._models_cache_exp:
                return list(self._models_cache)

        endpoint = f"models?client_version={urllib.parse.quote(self.client_version)}"
        status, _, body = self.request(endpoint, method="GET")
        if status != 200:
            # Fallback default models if upstream endpoint fails or in offline dev
            fallback_models = [
                "gpt-5.6-terra",
                "gpt-5.6-sol",
                "gpt-5.5",
                "gpt-5.5-codex",
                "gpt-5.4",
                "gpt-5.4-mini",
                "gpt-5.2",
                "gpt-4.1-mini",
                CODEX_IMAGE_MODEL,
            ]
            return fallback_models

        try:
            parsed = json.loads(body.decode("utf-8"))
            raw_models = parsed.get("models", [])
            models: list[str] = []
            for m in raw_models:
                if isinstance(m, dict) and "slug" in m:
                    models.append(m["slug"])
            if CODEX_IMAGE_MODEL not in models:
                models.append(CODEX_IMAGE_MODEL)

            with self._lock:
                self._models_cache = models
                self._models_cache_exp = time.time() + MODEL_CATALOG_TTL_SECONDS
            return models
        except Exception:
            return ["gpt-5.5", "gpt-5.4", CODEX_IMAGE_MODEL]

    def chat_completions(self, chat_req: dict[str, Any]) -> Tuple[int, dict[str, Any]]:
        """Transform chat completions request to Codex responses format and return OpenAI response."""
        model = chat_req.get("model") or "gpt-5.4"
        messages = chat_req.get("messages") or []
        tools = chat_req.get("tools")

        # Convert messages to Codex responses format
        input_items: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                input_items.append({
                    "role": role,
                    "content": [{"type": "input_text", "text": content}],
                })
            elif isinstance(content, list):
                parts = []
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text":
                        parts.append({"type": "input_text", "text": p.get("text", "")})
                input_items.append({"role": role, "content": parts})

        codex_body: dict[str, Any] = {
            "model": model,
            "input": input_items,
            "instructions": "",
            "store": False,
        }
        if tools:
            codex_body["tools"] = tools

        status, _, raw_resp = self.request(
            "responses",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(codex_body).encode("utf-8"),
        )

        if status != 200:
            try:
                err_data = json.loads(raw_resp.decode("utf-8"))
            except Exception:
                err_data = {"error": {"message": raw_resp.decode("utf-8", errors="ignore")}}
            return status, err_data

        # Parse upstream Codex response and format as standard OpenAI ChatCompletion
        try:
            upstream_data = json.loads(raw_resp.decode("utf-8"))
        except Exception:
            upstream_data = {}

        # Extract text content and tool calls
        text_content = ""
        tool_calls: list[dict[str, Any]] = []

        output_items = upstream_data.get("output", [])
        if isinstance(output_items, list):
            for item in output_items:
                if isinstance(item, dict):
                    if item.get("type") == "message":
                        for c in item.get("content", []):
                            if isinstance(c, dict) and c.get("type") in ("text", "output_text"):
                                text_content += c.get("text", "")
                    elif item.get("type") == "tool_call":
                        tc_id = item.get("id") or f"call_{secrets.token_hex(8)}"
                        fn_name = item.get("name") or (item.get("function", {}).get("name", ""))
                        fn_args = item.get("arguments") or (item.get("function", {}).get("arguments", "{}"))
                        if isinstance(fn_args, dict):
                            fn_args = json.dumps(fn_args)
                        tool_calls.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": fn_args,
                            },
                        })

        resp_obj: dict[str, Any] = {
            "id": f"chatcmpl_{secrets.token_hex(12)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text_content if text_content else None,
                    },
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(json.dumps(messages)) // 4,
                "completion_tokens": len(text_content) // 4,
                "total_tokens": (len(json.dumps(messages)) + len(text_content)) // 4,
            },
        }
        if tool_calls:
            resp_obj["choices"][0]["message"]["tool_calls"] = tool_calls

        return 200, resp_obj

    def generate_image(self, img_req: dict[str, Any]) -> Tuple[int, dict[str, Any]]:
        """Generate images via upstream Codex image endpoint."""
        prompt = img_req.get("prompt")
        if not prompt or not isinstance(prompt, str):
            return 400, {"error": {"message": "`prompt` must be a non-empty string."}}

        model = img_req.get("model") or CODEX_IMAGE_MODEL
        upstream_payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }
        for k in ("background", "n", "quality", "size"):
            if k in img_req:
                upstream_payload[k] = img_req[k]

        status, _, raw_resp = self.request(
            "images/generations",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(upstream_payload).encode("utf-8"),
        )
        try:
            parsed = json.loads(raw_resp.decode("utf-8"))
            return status, parsed
        except Exception:
            return status, {"error": {"message": raw_resp.decode("utf-8", errors="ignore")}}

    def edit_image(self, body_bytes: bytes, content_type: str) -> Tuple[int, dict[str, Any]]:
        """Edit images via upstream Codex image edit endpoint."""
        status, _, raw_resp = self.request(
            "images/edits",
            method="POST",
            headers={"Content-Type": content_type},
            body=body_bytes,
        )
        try:
            parsed = json.loads(raw_resp.decode("utf-8"))
            return status, parsed
        except Exception:
            return status, {"error": {"message": raw_resp.decode("utf-8", errors="ignore")}}


# ── HTTP Server & Request Handler ────────────────────────────────────────────

class OpenAIOAuthProxyHandler(BaseHTTPRequestHandler):
    """HTTP Request handler implementing OpenAI-compatible REST API endpoints."""

    client: OpenAIOAuthClient

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/health":
            self._send_json(200, {"ok": True, "replay_state": "stateless", "engine": "openai_oauth_proxy"})
            return

        if path == "/v1/models":
            try:
                models = self.client.list_models()
                self._send_json(200, {
                    "object": "list",
                    "data": [
                        {
                            "id": m,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "openai-oauth",
                        }
                        for m in models
                    ],
                })
            except Exception as e:
                logger.error("Error listing models: %s", e)
                self._send_json(502, {"error": {"message": str(e), "type": "upstream_error"}})
            return

        self._send_json(404, {"error": {"message": "Route not found.", "type": "not_found_error"}})

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        content_type = self.headers.get("Content-Type", "application/json")

        if path == "/v1/chat/completions":
            try:
                req_json = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except Exception:
                self._send_json(400, {"error": {"message": "Invalid JSON body."}})
                return

            # Check if streaming is requested
            if req_json.get("stream") is True:
                self._handle_chat_stream(req_json)
                return

            try:
                status, resp_data = self.client.chat_completions(req_json)
                self._send_json(status, resp_data)
            except Exception as e:
                logger.error("Chat completion error: %s", e)
                self._send_json(500, {"error": {"message": str(e)}})
            return

        if path == "/v1/responses":
            # Codex direct responses proxy
            try:
                status, _, raw_resp = self.client.request(
                    "responses",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    body=body_bytes,
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(raw_resp)
            except Exception as e:
                self._send_json(500, {"error": {"message": str(e)}})
            return

        if path == "/v1/images/generations":
            try:
                req_json = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                status, resp_data = self.client.generate_image(req_json)
                self._send_json(status, resp_data)
            except Exception as e:
                self._send_json(500, {"error": {"message": str(e)}})
            return

        if path == "/v1/images/edits":
            try:
                status, resp_data = self.client.edit_image(body_bytes, content_type)
                self._send_json(status, resp_data)
            except Exception as e:
                self._send_json(500, {"error": {"message": str(e)}})
            return

        self._send_json(404, {"error": {"message": "Route not found.", "type": "not_found_error"}})

    def _handle_chat_stream(self, req_json: dict[str, Any]) -> None:
        """Stream chat completions as Server-Sent Events (SSE)."""
        model = req_json.get("model") or "gpt-5.4"
        created = int(time.time())
        stream_id = f"chatcmpl_{secrets.token_hex(12)}"

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Emit initial role chunk
        initial_chunk = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        self.wfile.write(f"data: {json.dumps(initial_chunk)}\n\n".encode("utf-8"))
        self.wfile.flush()

        # Execute non-streaming call under the hood and stream delta chunks
        try:
            status, resp_data = self.client.chat_completions(req_json)
            if status == 200 and "choices" in resp_data and resp_data["choices"]:
                msg = resp_data["choices"][0].get("message", {})
                content = msg.get("content") or ""
                tool_calls = msg.get("tool_calls")

                # Stream content in small tokens/words
                if content:
                    words = content.split(" ")
                    for i, w in enumerate(words):
                        space = " " if i < len(words) - 1 else ""
                        chunk = {
                            "id": stream_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {"content": w + space}, "finish_reason": None}],
                        }
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
                        self.wfile.flush()

                if tool_calls:
                    chunk = {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {"tool_calls": tool_calls}, "finish_reason": None}],
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
                    self.wfile.flush()

            # Emit final finish_reason chunk
            final_chunk = {
                "id": stream_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as e:
            logger.error("Streaming error: %s", e)

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard request logs
        pass


class OpenAIOAuthProxyServer:
    """Threaded HTTP server for local OpenAI OAuth proxy."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        auth_file_path: Optional[str] = None,
        base_url: str = DEFAULT_CODEX_BASE_URL,
    ):
        self.host = host
        self.port = port
        self.client = OpenAIOAuthClient(base_url=base_url, auth_file_path=auth_file_path)
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self, daemon: bool = True) -> bool:
        """Start the proxy server in background thread."""
        try:
            handler_class = type(
                "ConfiguredOpenAIOAuthProxyHandler",
                (OpenAIOAuthProxyHandler,),
                {"client": self.client},
            )
            self._server = HTTPServer((self.host, self.port), handler_class)
            self._running = True
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=daemon)
            self._thread.start()
            logger.info("OpenAIOAuthProxy running on http://%s:%d/v1", self.host, self.port)
            return True
        except Exception as e:
            logger.warning("Failed to start OpenAIOAuthProxy on %s:%d: %s", self.host, self.port, e)
            return False

    def stop(self) -> None:
        """Stop the proxy server."""
        if self._server and self._running:
            self._running = False
            self._server.shutdown()
            self._server.server_close()
            if self._thread:
                self._thread.join(timeout=2.0)
            logger.info("OpenAIOAuthProxy stopped.")

    @property
    def is_running(self) -> bool:
        return self._running


# ── Global Singleton & Convenience Helpers ───────────────────────────────────

_proxy_server: Optional[OpenAIOAuthProxyServer] = None


def get_oauth_proxy_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    auth_file_path: Optional[str] = None,
) -> OpenAIOAuthProxyServer:
    """Get or instantiate global proxy server singleton."""
    global _proxy_server
    if _proxy_server is None:
        _proxy_server = OpenAIOAuthProxyServer(
            host=host,
            port=port,
            auth_file_path=auth_file_path,
        )
    return _proxy_server


def is_oauth_proxy_healthy(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 1.0,
) -> bool:
    """Check whether local OpenAI OAuth proxy is responding on /health."""
    url = f"http://{host}:{port}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("ok") is True
    except Exception:
        pass
    return False
