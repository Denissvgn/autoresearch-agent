"""Authentication dependencies for the autoresearch API."""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import secret_value, settings

try:
    from identity_client import introspect_token as _introspect_token
except ImportError:  # pragma: no cover - dependency is declared, fallback is defensive.
    _introspect_token = None

IdentityIntrospector = Callable[[str, str, float], Awaitable[dict[str, Any]]]
introspect_token: IdentityIntrospector | None = _introspect_token

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)
_bearer_dependency = Depends(_bearer_scheme)
_WS_TOKEN_SUBPROTOCOL_PREFIX = "autoresearch.token."
_ADMIN_ROLES = {"admin", "administrator", "ml_admin"}


@dataclass(frozen=True)
class AuthenticatedActor:
    """Authenticated caller context used for audit metadata."""

    subject: str
    actor_id: str
    mechanism: str
    websocket_subprotocol: str | None = None
    roles: tuple[str, ...] = ()


def _configured_token() -> str | None:
    token = secret_value(settings.autoresearch_api_token)
    if token is None:
        return None
    token = token.strip()
    return token or None


def _auth_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _auth_not_configured() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Autoresearch authentication is not configured",
    )


def _admin_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def token_fingerprint(token: str | None) -> str | None:
    """Return a non-reversible token fingerprint safe for audit storage."""

    if not token:
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"token_sha256:{digest[:16]}"


def _roles_from_identity_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    roles = payload.get("roles")
    if isinstance(roles, list):
        return tuple(str(role) for role in roles if role is not None)
    if isinstance(roles, str):
        return (roles,)
    role = payload.get("role")
    if isinstance(role, str) and role:
        return (role,)
    return ()


def _identity_is_admin(payload: dict[str, Any]) -> bool:
    roles = set(_roles_from_identity_payload(payload))
    return bool(payload.get("is_admin")) or bool(roles & _ADMIN_ROLES)


def _identity_subject(payload: dict[str, Any]) -> str:
    for key in ("sub", "user_id", "username", "email", "client_id"):
        value = payload.get(key)
        if value:
            return str(value)
    return "identity-token"


async def _authenticate_identity_token(
    token: str,
    *,
    mechanism: str,
    websocket_subprotocol: str | None = None,
) -> AuthenticatedActor:
    if introspect_token is None:
        logger.warning("identity-client is unavailable for autoresearch JWT introspection")
        raise _auth_required()
    try:
        payload = await introspect_token(
            settings.identity_service_url,
            token,
            settings.identity_introspection_timeout_s,
        )
    except Exception as exc:
        logger.warning("Identity token introspection failed: %s", exc)
        raise _auth_required() from exc

    if not payload or not payload.get("active"):
        raise _auth_required()
    if not _identity_is_admin(payload):
        raise _admin_required()

    subject = _identity_subject(payload)
    return AuthenticatedActor(
        subject=subject,
        actor_id=f"identity:{subject}",
        mechanism=f"{mechanism}:identity-jwt",
        websocket_subprotocol=websocket_subprotocol,
        roles=_roles_from_identity_payload(payload),
    )


async def _authenticate_token(
    token: str | None,
    *,
    mechanism: str,
    websocket_subprotocol: str | None = None,
) -> AuthenticatedActor:
    if not token:
        raise _auth_required()

    configured = _configured_token()
    if configured and secrets.compare_digest(token, configured):
        return AuthenticatedActor(
            subject="api-token",
            actor_id=token_fingerprint(token) or "unknown",
            mechanism=mechanism,
            websocket_subprotocol=websocket_subprotocol,
            roles=("admin", "ml_admin"),
        )

    if settings.identity_service_url:
        return await _authenticate_identity_token(
            token,
            mechanism=mechanism,
            websocket_subprotocol=websocket_subprotocol,
        )

    if not configured:
        raise _auth_not_configured()
    raise _auth_required()


async def require_api_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = _bearer_dependency,
) -> AuthenticatedActor:
    """Require ``Authorization: Bearer <token>`` for HTTP API routes."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        exc = _auth_required()
        await _record_auth_rejection(
            request,
            token=None,
            mechanism="missing",
            exc=exc,
        )
        raise exc
    try:
        actor = await _authenticate_token(credentials.credentials, mechanism="bearer")
    except HTTPException as exc:
        await _record_auth_rejection(
            request,
            token=credentials.credentials,
            mechanism="bearer",
            exc=exc,
        )
        raise
    request.state.auth_actor = actor
    return actor


def _audit_store_from_connection(connection: Request | WebSocket) -> Any:
    app = getattr(connection, "app", None)
    if app is None:
        app = connection.scope.get("app")
    state = getattr(app, "state", None) if app else None
    return getattr(state, "audit_store", None)


def _connection_metadata(
    connection: Request | WebSocket,
    *,
    mechanism: str,
    status_code: int,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "path": connection.url.path,
        "auth_mechanism": mechanism,
        "status_code": status_code,
    }
    method = connection.scope.get("method")
    if method:
        metadata["method"] = method
    client = connection.client
    if client:
        metadata["client_host"] = client.host
    user_agent = connection.headers.get("user-agent")
    if user_agent:
        metadata["user_agent"] = user_agent
    return metadata


async def _record_auth_rejection(
    connection: Request | WebSocket,
    *,
    token: str | None,
    mechanism: str,
    exc: HTTPException,
) -> None:
    store = _audit_store_from_connection(connection)
    if store is None:
        return
    try:
        await store.record_audit_event(
            actor_id=token_fingerprint(token) or "anonymous",
            action="auth.reject",
            request_metadata=_connection_metadata(
                connection,
                mechanism=mechanism,
                status_code=exc.status_code,
            ),
            outcome="failure",
            error_message=str(exc.detail),
        )
    except Exception:
        logger.warning("Failed to record authentication rejection audit event", exc_info=True)


def _parse_authorization_header(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def _decode_subprotocol_token(protocol: str) -> str | None:
    encoded = protocol.removeprefix(_WS_TOKEN_SUBPROTOCOL_PREFIX)
    padding = "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(f"{encoded}{padding}").decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _parse_websocket_subprotocol_token(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    for protocol in (part.strip() for part in value.split(",")):
        if not protocol.startswith(_WS_TOKEN_SUBPROTOCOL_PREFIX):
            continue
        token = _decode_subprotocol_token(protocol)
        if token:
            return token, protocol
    return None, None


async def require_websocket_auth(websocket: WebSocket) -> AuthenticatedActor | None:
    """Authenticate a WebSocket before accepting the connection."""

    attempted_token: str | None = None
    attempted_mechanism = "missing"
    try:
        header_token = _parse_authorization_header(websocket.headers.get("authorization"))
        if header_token:
            attempted_token = header_token
            attempted_mechanism = "bearer"
            return await _authenticate_token(header_token, mechanism="bearer")

        protocol_token, selected_protocol = _parse_websocket_subprotocol_token(
            websocket.headers.get("sec-websocket-protocol")
        )
        if protocol_token:
            attempted_token = protocol_token
            attempted_mechanism = "websocket-subprotocol"
            return await _authenticate_token(
                protocol_token,
                mechanism="websocket-subprotocol",
                websocket_subprotocol=selected_protocol,
            )

        raise _auth_required()
    except HTTPException as exc:
        await _record_auth_rejection(
            websocket,
            token=attempted_token,
            mechanism=attempted_mechanism,
            exc=exc,
        )
        headers = dict(exc.headers or {})
        response = JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=headers,
        )
        try:
            send_denial_response = websocket.send_denial_response
            await send_denial_response(response)
        except (AttributeError, RuntimeError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
