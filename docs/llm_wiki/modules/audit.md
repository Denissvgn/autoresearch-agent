# audit Module

**Path:** `src/api/audit.py`

## Description

Audit helpers for protected autoresearch API endpoints.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `fastapi` | `Request` |
| `src.api.auth` | `AuthenticatedActor` |
| `typing` | `Any` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_request_actor` | `(request: Request) -> AuthenticatedActor | None` | — | — |
| `request_metadata` | `(request: Request, extra: dict[str, Any] | None = None) -> dict[str, Any]` | — | Build sanitized request metadata without credentials. |
| `record_api_audit_event` | `*(async)* (request: Request, store) -> dict[str, Any] | None` | — | Record one audit event for a state-changing API request. |
