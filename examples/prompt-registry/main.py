"""Example prompt-registry receiver (P1-3).

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
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="prompt-registry (example)", version="0.1.0")

_PROMPTS: dict[str, dict[str, Any]] = {}
_BY_IDEMPOTENCY: dict[str, dict[str, Any]] = {}
_SEQ = {"n": 0}


def _authorized(authorization: str | None) -> bool:
    expected = os.environ.get("PROMPT_REGISTRY_AUTH_TOKEN", "")
    if not expected:
        return True
    return authorization == f"Bearer {expected}"


class RegisterResponse(BaseModel):
    prompt_id: str
    status: str
    idempotent_replay: bool = False


@app.post("/api/v1/prompts", status_code=201)
async def register_prompt(
    payload: dict[str, Any],
    request: Request,
    authorization: str | None = Header(default=None),
) -> RegisterResponse:
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    idem = request.headers.get("Idempotency-Key", "")
    if idem and idem in _BY_IDEMPOTENCY:
        prior = _BY_IDEMPOTENCY[idem]
        return RegisterResponse(
            prompt_id=prior["prompt_id"],
            status=prior["status"],
            idempotent_replay=True,
        )
    _SEQ["n"] += 1
    prompt_id = f"prompt_{_SEQ['n']:04d}"
    record = {
        "prompt_id": prompt_id,
        "config": payload.get("config"),
        "target_path": payload.get("target_path"),
        "endpoint": payload.get("endpoint"),
        "promoted_at": payload.get("promoted_at"),
        "status": "registered",
        "registered_at": time.time(),
    }
    _PROMPTS[prompt_id] = record
    if idem:
        _BY_IDEMPOTENCY[idem] = record
    return RegisterResponse(prompt_id=prompt_id, status="registered")


@app.get("/api/v1/prompts")
async def list_prompts(authorization: str | None = Header(default=None)):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    return {"prompts": list(_PROMPTS.values())}


@app.get("/api/v1/prompts/{prompt_id}")
async def get_prompt(
    prompt_id: str, authorization: str | None = Header(default=None)
):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    if prompt_id not in _PROMPTS:
        raise HTTPException(status_code=404, detail="unknown prompt_id")
    return _PROMPTS[prompt_id]


@app.post("/api/v1/prompts/{prompt_id}/promote")
async def promote_prompt(
    prompt_id: str, authorization: str | None = Header(default=None)
):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    if prompt_id not in _PROMPTS:
        raise HTTPException(status_code=404, detail="unknown prompt_id")
    _PROMPTS[prompt_id]["status"] = "production"
    return _PROMPTS[prompt_id]


@app.get("/health")
async def health():
    return {"status": "ok", "registered": len(_PROMPTS)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8031")))
