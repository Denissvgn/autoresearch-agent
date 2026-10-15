# dataset Module

**Path:** `skills/prompt-engineering/eval/dataset.py`

## Description

Bounded JSONL data loading shared by the packaged bootstrap and evaluator.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `stat` | `stat` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `load_examples` | `(path: str \| Path) -> list[dict[str, str]]` | — | Read data only: regular .jsonl files, no symlinks or executable content. |
