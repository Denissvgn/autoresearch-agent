"""Authentication dependencies for the autoresearch API."""

from __future__ import annotations

import base64
import binascii
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)
_WS_TOKEN_SUBPROTOCOL_PREFIX = "autoresearch.token."


@dataclass(frozen=True)
class AuthenticatedActor:
    """Authenticated caller context reserved for future JWT/RBAC expansion."""

    subject: str
    mechanism: str
    websocket_subprotocol: str | None = None


def _configured_token() -> str | None:
    token = settings.autoresearch_api_token
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
        detail="Autoresearch API token is not configured",
    )


def _authenticate_token(
    token: str | None,
    *,
    mechanism: str,
    websocket_subprotocol: str | None = None,
) -> AuthenticatedActor:
    configured = _configured_token()
    if not configured:
        raise _auth_not_configured()
    if not token or not secrets.compare_digest(token, configured):
        raise _auth_required()
    return AuthenticatedActor(
        subject="api-token",
        mechanism=mechanism,
        websocket_subprotocol=websocket_subprotocol,
    )


async def require_api_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedActor:
    """Require ``Authorization: Bearer <token>`` for HTTP API routes."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _auth_required()
    return _authenticate_token(credentials.credentials, mechanism="bearer")


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

    try:
        header_token = _parse_authorization_header(websocket.headers.get("authorization"))
        if header_token:
            return _authenticate_token(header_token, mechanism="bearer")

        protocol_token, selected_protocol = _parse_websocket_subprotocol_token(
            websocket.headers.get("sec-websocket-protocol")
        )
        if protocol_token:
            return _authenticate_token(
                protocol_token,
                mechanism="websocket-subprotocol",
                websocket_subprotocol=selected_protocol,
            )

        raise _auth_required()
    except HTTPException as exc:
        headers = dict(exc.headers or {})
        response = JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=headers,
        )
        try:
            await websocket.send_denial_response(response)
        except RuntimeError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
