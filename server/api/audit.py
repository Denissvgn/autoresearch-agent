"""Audit helpers for protected autoresearch API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from server.api.auth import AuthenticatedActor


def _request_actor(request: Request) -> AuthenticatedActor | None:
    actor = getattr(request.state, "auth_actor", None)
    return actor if isinstance(actor, AuthenticatedActor) else None


def request_metadata(request: Request, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build sanitized request metadata without credentials."""

    actor = _request_actor(request)
    metadata: dict[str, Any] = {
        "method": request.method,
        "path": request.url.path,
    }
    if request.client:
        metadata["client_host"] = request.client.host
    user_agent = request.headers.get("user-agent")
    if user_agent:
        metadata["user_agent"] = user_agent
    if actor:
        metadata["actor_subject"] = actor.subject
        metadata["auth_mechanism"] = actor.mechanism
    if extra:
        metadata.update({key: value for key, value in extra.items() if value is not None})
    return metadata


async def record_api_audit_event(
    request: Request,
    store,
    *,
    action: str,
    outcome: str,
    research_id: str | None = None,
    pipeline_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> dict[str, Any] | None:
    """Record one audit event for a state-changing API request."""

    actor = _request_actor(request)
    return await store.record_audit_event(
        actor_id=actor.actor_id if actor else "unknown",
        action=action,
        research_id=research_id,
        pipeline_id=pipeline_id,
        request_metadata=request_metadata(request, metadata),
        outcome=outcome,
        error_message=error_message,
    )
