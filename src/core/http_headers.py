"""Request-header binding for the autoresearch API.

Normalizes the ``X-Request-ID`` correlation header: caller-supplied values are
echoed and missing values are auto-generated so every request carries a stable
identifier for logs and audit events. Bound values are exposed on
``connection.state.request_headers`` for downstream consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Header
from starlette.requests import HTTPConnection

REQUEST_ID_HEADER = "X-Request-ID"

RequestIdHeaderParam = Annotated[
    str | None,
    Header(
        alias=REQUEST_ID_HEADER,
        description="Correlation identifier; auto-generated UUID4 when missing.",
    ),
]


@dataclass(slots=True)
class RequestHeaders:
    """Normalized inbound request headers."""

    request_id: str


async def bind_request_headers(
    connection: HTTPConnection,
    request_id: RequestIdHeaderParam = None,
) -> RequestHeaders:
    """Bind normalized request headers to the connection state."""

    normalized = (request_id or "").strip() or str(uuid4())
    headers = RequestHeaders(request_id=normalized)
    connection.state.request_headers = headers
    return headers


def _has_request_header_dependency(dependencies: list) -> bool:
    return any(
        getattr(dependency, "dependency", None) is bind_request_headers
        for dependency in dependencies
    )


def ensure_app_request_headers(app: FastAPI) -> FastAPI:
    """Ensure every route binds normalized request headers."""

    if not _has_request_header_dependency(app.router.dependencies):
        app.router.dependencies.append(Depends(bind_request_headers))

    if not getattr(app.state, "_request_headers_router_hook", False):
        original_include_router = app.include_router

        @wraps(original_include_router)
        def include_router_with_headers(router: APIRouter, *args, **kwargs):
            if not _has_request_header_dependency(router.dependencies):
                router.dependencies.append(Depends(bind_request_headers))
            return original_include_router(router, *args, **kwargs)

        app.include_router = include_router_with_headers  # type: ignore[assignment]
        app.state._request_headers_router_hook = True

    return app
