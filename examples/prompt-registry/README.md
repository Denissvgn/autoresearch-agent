# Example: prompt-registry receiver (P1-3)

A minimal receiver that proves the `registry_api` / `webhook` promotion
target end-to-end. `autoresearch-agent` delivers a confirmed promotion as:

```
POST /api/v1/prompts
Idempotency-Key: <sha256 of promoted content>
Authorization: Bearer <PROMPT_REGISTRY_AUTH_TOKEN>   (when configured)
{"target_path": ..., "config": "<winner yaml>", "promoted_at": ...}
```

## Run it

```bash
pip install fastapi uvicorn
PROMPT_REGISTRY_AUTH_TOKEN=secret python examples/prompt-registry/main.py
# -> listening on :8031
```

## Point the skill at it

Edit `skills/prompt-engineering/SKILL.yaml`:

```yaml
promotion_target:
  primary:
    kind: registry_api
    registry: prompt-registry
    register_endpoint: http://localhost:8031/api/v1/prompts
    auth_secret: PROMPT_REGISTRY_AUTH_TOKEN
```

then hot-reload skills:

```bash
curl -X POST -H "Authorization: Bearer $AUTORESEARCH_API_TOKEN" \
     http://localhost:8030/api/v1/skills/reload
```

## Promote

From the UI (Promote page) or API:

```bash
curl -X POST -H "Authorization: Bearer $AUTORESEARCH_API_TOKEN" \
     http://localhost:8030/api/v1/research/<id>/promote/confirm
```

The confirm now:

1. runs the full gate pipeline (unchanged),
2. writes a local provenance copy under `<workspace>/promotions/`,
3. POSTs the winner to this receiver (retries on 5xx, fail-closed on final
   failure — the API answers 500 with the delivery error).

Verify:

```bash
curl -H "Authorization: Bearer secret" http://localhost:8031/api/v1/prompts
```

The receiver also honors `Idempotency-Key` replays and exposes
`POST /api/v1/prompts/{id}/promote` for the production-scope flow.
