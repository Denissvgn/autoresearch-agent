# jsonl_driver Module

**Path:** `examples/jsonl_driver.py`

## Description

Custom JSONL driver: a managed external research driver.

This program speaks the versioned JSONL transport on stdout and knows
nothing about the host's internals. It proposes candidates and requests
evaluation — its proposals are candidates (model-proposed), never
verified results or promotion approvals. Its ordinary shell activity
(digesting files here) is ordinary tool access, not evaluator execution.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `os` | `os` |
| `subprocess` | `subprocess` |
| `sys` | `sys` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `emit` | `(event: dict) -> None` | — | — |
| `main` | `() -> int` | — | — |
