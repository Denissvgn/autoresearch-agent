# main Module

**Path:** `examples/prompt-registry/main.py`

## Description

Example prompt-registry receiver (P1-3).

A tiny FastAPI service that exercises the ``registry_api`` / ``webhook``
promotion target end-to-end:

    POST /api/v1/prompts            — register a promoted prompt (the
                                       WebhookPromotionTarget delivery)
    GET  /api/v1/prompts            — list registered prompts
    GET  /api/v1/prompts/{id}       — fetch one prompt
    POST /api/v1/prompts/{id}/promote — mark a prompt production

Auth: when ``PROMPT_REGISTRY_AUTH_TOKEN`` is set, requests must carry
``Authorization: Bearer <token>`` (matching the skill manifest's
``auth_secret`` wiring). Idempotency is honored via the ``Idempotency-Key``
header: a repeated key returns the original record instead of duplicating.

Run::

    pip install fastapi uvicorn
    PROMPT_REGISTRY_AUTH_TOKEN=secret python main.py   # :8031

Then point the prompt-engineering skill at it (skills/prompt-engineering/
SKILL.yaml ``promotion_target.primary.register_endpoint`` ->
``http://localhost:8031/api/v1/prompts``) and reload skills
(``POST /api/v1/skills/reload``). A confirmed promotion now lands here.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `fastapi` | `FastAPI`, `HTTPException`, `Header`, `Request` |
| `os` | `os` |
| `pydantic` | `BaseModel` |
| `time` | `time` |
| `typing` | `Any` |
| `uvicorn` | `uvicorn` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 3 | 2 |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [RegisterResponse](../entities/RegisterResponse.md) | 50 | `BaseModel` | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_authorized` | `(authorization: str \| None) -> bool` | — | — |
| `register_prompt` | *(async)* `(payload: dict[str, Any], request: Request, authorization: str \| None = Header(default=None)) -> RegisterResponse` | `@app.post('/api/v1/prompts', status_code=201)` | — |
| `list_prompts` | *(async)* `(authorization: str \| None = Header(default=None))` | `@app.get('/api/v1/prompts')` | — |
| `get_prompt` | *(async)* `(prompt_id: str, authorization: str \| None = Header(default=None))` | `@app.get('/api/v1/prompts/{prompt_id}')` | — |
| `promote_prompt` | *(async)* `(prompt_id: str, authorization: str \| None = Header(default=None))` | `@app.post('/api/v1/prompts/{prompt_id}/promote')` | — |
| `health` | *(async)* `()` | `@app.get('/health')` | — |
