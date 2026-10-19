"""HTTP client for the attached-agent API.

The CLI drives the API through this client only — no internal Python
classes cross the boundary. Credentials arrive by reference (an
environment variable or a file), never as command-line arguments, and
error surfaces are redacted so a credential can never leak into logs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional

import httpx

DEFAULT_BASE_URL_ENV = "AUTORESEARCH_API_URL"
DEFAULT_CREDENTIAL_ENV = "AUTORESEARCH_AGENT_CREDENTIAL"
DEFAULT_TIMEOUT_S = 30.0


class AgentClientError(Exception):
    """An API or transport failure with a stable, redacted message."""

    def __init__(self, message: str, *, status: Optional[int] = None) -> None:
        self.status = status
        super().__init__(message)


class AgentAuthError(AgentClientError):
    """The scoped credential was refused (or missing)."""


class AgentConflictError(AgentClientError):
    """The request conflicts with an earlier one (idempotency)."""


class AgentLimitError(AgentClientError):
    """A size or rate limit refused the request."""


def resolve_credential(
    *,
    credential_env: str = DEFAULT_CREDENTIAL_ENV,
    credential_file: Optional[str] = None,
) -> str:
    """Load the scoped credential by reference, never from argv."""
    if credential_file:
        return Path(credential_file).read_text(encoding="utf-8").strip()
    value = os.environ.get(credential_env, "").strip()
    if not value:
        raise AgentAuthError(
            f"no credential: set ${credential_env} or use --credential-file"
        )
    return value


def redact(text: str, secret: Optional[str]) -> str:
    """Never let a credential surface in output or logs."""
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


class AgentClient:
    """The attached-agent API client with bounded waits."""

    def __init__(
        self,
        *,
        base_url: str,
        credential: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._credential = credential
        self._timeout = timeout_s
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_s,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # -- the attached-agent operations --------------------------------
    async def create_or_attach(self, **body: Any) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/agent/runs", body=body)

    async def constraints(self, run_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/agent/runs/{run_id}/constraints"
        )

    async def submit_candidate(
        self,
        run_id: str,
        *,
        content: bytes,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/agent/runs/{run_id}/candidates",
            body={
                "digest": hashlib.sha256(content).hexdigest(),
                "content": content.decode("utf-8"),
            },
            headers={"Idempotency-Key": idempotency_key},
        )

    async def request_evaluation(self, run_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/v1/agent/runs/{run_id}/evaluations"
        )

    async def results(self, run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/agent/runs/{run_id}/results")

    async def promotion_preview(self, run_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/api/v1/agent/runs/{run_id}/promotion-preview"
        )

    async def lifecycle(self, run_id: str, *, action: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/agent/runs/{run_id}/lifecycle",
            body={"action": action},
        )

    async def events(self, run_id: str, *, cursor: int = 0) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/agent/runs/{run_id}/events",
            params={"cursor": cursor},
        )

    # -- plumbing -----------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        request_headers = {
            "Authorization": f"Bearer {self._credential}",
            **(dict(headers) if headers else {}),
        }
        try:
            response = await self._client.request(
                method,
                path,
                json=dict(body) if body is not None else None,
                headers=request_headers,
                params=dict(params) if params else None,
            )
        except httpx.HTTPError as exc:
            raise AgentClientError(
                redact(f"transport failure: {exc}", self._credential)
            ) from None
        if response.status_code >= 400:
            raise self._error(response)
        try:
            return dict(response.json())
        except ValueError:
            return {"raw": response.text}

    def _error(self, response: httpx.Response) -> AgentClientError:
        message = redact(
            f"API error {response.status_code}: {response.text}",
            self._credential,
        )
        status = response.status_code
        if status in (401, 403):
            return AgentAuthError(message, status=status)
        if status == 409:
            return AgentConflictError(message, status=status)
        if status in (413, 429):
            return AgentLimitError(message, status=status)
        return AgentClientError(message, status=status)
