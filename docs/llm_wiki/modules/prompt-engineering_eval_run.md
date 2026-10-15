# run Module

**Path:** `skills/prompt-engineering/eval/run.py`

## Description

Fail-closed prompt scoring with an explicit remote endpoint or demo mode.

The server must force --eval, --scorer-url and --demo at execution time.
Ambient provider credentials and scorer URLs are deliberately ignored.
Remote errors never fall through to synthetic success, even in demo mode.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `argparse` | `argparse` |
| `dataset` | `load_examples` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `math` | `math` |
| `os` | `os` |
| `sys` | `sys` |
| `urllib.parse` | `urlsplit` |
| `urllib.request` | `urllib.request` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_fallback_score` | `(prompt_text: str, eval_examples: list[dict]) -> dict` | — | Deterministic offline fallback (no network / no scorer_url). |
| `_try_remote_scorer` | `(prompt_text, eval_examples, scorer_url, timeout_s = 15.0)` | — | POST to the explicit endpoint; None means failure, never fallback. |
| `_score_prompt` | `(prompt_text, eval_examples, scorer_url = None, *, demo = False)` | — | — |
| `_error` | `(message, n = 0)` | — | — |
| `main` | `() -> int` | — | — |
| `_emit` | `(**fields: object) -> None` | — | Emit an ``ITERATION_RESULT:`` JSON line with the anti-forgery nonce. |
