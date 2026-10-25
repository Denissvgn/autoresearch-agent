# run Module

**Path:** `tests/fixtures/conformance/eval/run.py`

## Description

Deterministic conformance evaluator (fixture skill package asset).

Stdlib only. The governed command runner executes this as the skill's
experiment command; stdout carries the skill's own iteration announcement —
both result channels: the declared marker line and the ``---`` delimited
key/value block — so every declared parser format reads the same observation.

Metrics are deterministic and come from the bound argv sequence; a per-
workspace counter file advances on each call so one workflow can observe a
scripted metric sequence. The counter path resolves inside the session
workspace, which makes resolved CWD/inputs observable in the result.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `pathlib` | `pathlib` |
| `sys` | `sys` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_parse_flags` | `(argv: list[str]) -> dict[str, str]` | — | — |
| `main` | `() -> int` | — | — |
