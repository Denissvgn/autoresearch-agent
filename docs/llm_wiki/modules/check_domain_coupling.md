# check_domain_coupling Module

**Path:** `scripts/check_domain_coupling.py`

## Description

Domain-coupling guard: fail when TRAID-platform vocabulary creeps back in.

Checks src/ and ui/src (plus the Dockerfile) for tokens that couple the
service to the removed trading platform. The legacy alias layer
(src/core/legacy_alias.py) and the legacy phase-plan tables (kept only to
render historical DB rows) are exempt.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `pathlib` | `Path` |
| `re` | `re` |
| `sys` | `sys` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `main` | `() -> int` | — | — |
