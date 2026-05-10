# auth Module

**Path:** `src/api/auth.py`

## Description

Authentication dependencies for the autoresearch API.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `base64` | `base64` |
| `binascii` | `binascii` |
| `collections.abc` | `Awaitable`, `Callable` |
| `dataclasses` | `dataclass` |
| `fastapi` | `Depends`, `HTTPException`, `Request`, `WebSocket`, `status` |
| `fastapi.responses` | `JSONResponse` |
| `fastapi.security` | `HTTPAuthorizationCredentials`, `HTTPBearer` |
| `hashlib` | `hashlib` |
| `identity_client` | `introspect_token` |
| `logging` | `logging` |
| `secrets` | `secrets` |
| `src.config` | `secret_value`, `settings` |
| `typing` | `Any` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [AuthenticatedActor](../entities/AuthenticatedActor.md) | 37 | — | Authenticated caller context used for audit metadata. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_configured_token` | `() -> str | None` | — | — |
| `_auth_required` | `() -> HTTPException` | — | — |
| `_auth_not_configured` | `() -> HTTPException` | — | — |
| `_admin_required` | `() -> HTTPException` | — | — |
| `token_fingerprint` | `(token: str | None) -> str | None` | — | Return a non-reversible token fingerprint safe for audit storage. |
| `_roles_from_identity_payload` | `(payload: dict[str, Any]) -> tuple[str, Ellipsis]` | — | — |
| `_identity_is_admin` | `(payload: dict[str, Any]) -> bool` | — | — |
| `_identity_subject` | `(payload: dict[str, Any]) -> str` | — | — |
| `_authenticate_identity_token` | `*(async)* (token: str) -> AuthenticatedActor` | — | — |
| `_authenticate_token` | `*(async)* (token: str | None) -> AuthenticatedActor` | — | — |
| `require_api_auth` | `*(async)* (request: Request, credentials: HTTPAuthorizationCredentials | None = _bearer_dependency) -> AuthenticatedActor` | — | Require ``Authorization: Bearer <token>`` for HTTP API routes. |
| `_audit_store_from_connection` | `(connection: Request | WebSocket) -> Any` | — | — |
| `_connection_metadata` | `(connection: Request | WebSocket) -> dict[str, object]` | — | — |
| `_record_auth_rejection` | `*(async)* (connection: Request | WebSocket) -> None` | — | — |
| `_parse_authorization_header` | `(value: str | None) -> str | None` | — | — |
| `_decode_subprotocol_token` | `(protocol: str) -> str | None` | — | — |
| `_parse_websocket_subprotocol_token` | `(value: str | None) -> tuple[str | None, str | None]` | — | — |
| `require_websocket_auth` | `*(async)* (websocket: WebSocket) -> AuthenticatedActor | None` | — | Authenticate a WebSocket before accepting the connection. |
