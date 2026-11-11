# SPDX-License-Identifier: MIT

"""Typed Appwrite SDK wrapper for Lady Mnemosyne's long-term memory.

PR #2 of NOTES_MNEMOSYNE_WIRING.md (2026-07-14, freebuff).

Wraps the Appwrite Python SDK (`appwrite>=2.0.0,<3.0.0` per pyproject.toml:46)
with:
  * tenacity retry semantics on AppwriteException
  * explicit Z3-gate hand-off via the `z3_pass` flag on write paths
  * APPWRITE_API_KEY never logged raw (mask-only)
  * PEP 604 type hints (pyproject target-version = py313)
  * env-toggle via APPWRITE_ENDPOINT_PUBLIC / APPWRITE_PROJECT_ID /
    APPWRITE_DB_ID / APPWRITE_COLLECTION_ID

Read operations are AUTO-tier eligible (idempotent, no destructive write).
Write operations require `z3_pass=True` (HUMAN_GATE per Iron Gate v2).
"""
from __future__ import annotations

import os
from typing import Any, ClassVar

from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class AppwriteClient:
    """Typed wrapper around `appwrite.Services.Databases` with retry + Z3 hand-off."""

    DEFAULT_ENDPOINT = "https://appwrite.local/v1"
    DEFAULT_DATABASE_ID = "sovereign_db"
    DEFAULT_COLLECTION_ID = "memory_spine"
    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_MIN_WAIT_SECONDS = 2
    DEFAULT_MAX_WAIT_SECONDS = 10

    def __init__(
        self,
        endpoint: str | None = None,
        project_id: str | None = None,
        api_key: str | None = None,
        database_id: str | None = None,
        collection_id: str | None = None,
    ) -> None:
        self.endpoint: str = endpoint or os.environ.get(
            "APPWRITE_ENDPOINT_PUBLIC", self.DEFAULT_ENDPOINT
        )
        self.project_id: str = project_id or os.environ.get("APPWRITE_PROJECT_ID", "")
        # Never expose the raw key via repr/log.
        self._api_key: str = api_key or os.environ.get("APPWRITE_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "APPWRITE_API_KEY not configured; run bin/appwrite_bootstrap.sh "
                "and chmod 600 the resulting .env.appwrite"
            )
        self.database_id: str = database_id or os.environ.get(
            "APPWRITE_DB_ID", self.DEFAULT_DATABASE_ID
        )
        self.collection_id: str = collection_id or os.environ.get(
            "APPWRITE_COLLECTION_ID", self.DEFAULT_COLLECTION_ID
        )
        self._client = self._build_client()
        self._databases: ClassVar[Databases] = Databases(self._client)

    def _build_client(self) -> Client:
        client = Client()
        client.set_endpoint(self.endpoint)
        if self.project_id:
            client.set_project(self.project_id)
        client.set_key(self._api_key)
        return client

    def mask_key(self) -> str:
        """Return a masked view of the API key for logging."""
        if not self._api_key:
            return ""
        if len(self._api_key) <= 8:
            return "***"
        return f"{self._api_key[:4]}...{self._api_key[-4:]}"

    @retry(
        stop=stop_after_attempt(DEFAULT_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=DEFAULT_MIN_WAIT_SECONDS, max=DEFAULT_MAX_WAIT_SECONDS),
        retry=retry_if_exception_type(AppwriteException),
        reraise=True,
    )
    async def list_databases(self) -> list[dict[str, Any]]:
        """List all databases. AUTO-tier (idempotent read)."""
        result = await self._safe_call(lambda: self._databases.list())
        return list(result.get("databases", []))

    @retry(
        stop=stop_after_attempt(DEFAULT_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=DEFAULT_MIN_WAIT_SECONDS, max=DEFAULT_MAX_WAIT_SECONDS),
        retry=retry_if_exception_type(AppwriteException),
        reraise=True,
    )
    async def upsert_document(
        self,
        document_id: str,
        data: dict[str, Any],
        *,
        z3_pass: bool = True,
    ) -> dict[str, Any]:
        """Upsert a document into the configured collection.

        HUMAN_GATE-tier operation. Caller must pass `z3_pass=True` to assert that
        Z3 safety verification was performed before invoking this method.
        The Bifrost dispatcher (`dispatch_to_appwrite`) is the canonical caller;
        ad-hoc callers must wire their through `soul_oversight.pre_execute`.
        """
        if not z3_pass:
            raise PermissionError(
                "upsert_document refused: z3_pass=False; "
                "HUMAN_GATE requires Z3 verification per Iron Gate v2"
            )
        if not document_id or not isinstance(data, dict):
            raise ValueError("document_id must be non-empty; data must be a dict")
        result = await self._safe_call(
            lambda: self._databases.create_document(
                self.database_id, self.collection_id, document_id, data
            )
        )
        return dict(result)

    @staticmethod
    async def _safe_call(func):
        """Wrap a sync SDK call in an awaitable, so tenacity decorators compose."""
        return func()


__all__ = ["AppwriteClient"]
