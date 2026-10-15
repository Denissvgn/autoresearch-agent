# check_doc_references Module

**Path:** `scripts/check_doc_references.py`

## Description

Referenced-doc integrity guard.

Fails when a code comment, test, script, or workflow references a
``docs/<...>.md`` file that does not exist on disk. Code prose pointing at a
design document is a contract: when the target is deleted or renamed the
reference silently rots. Run in CI so a change that deletes or renames a
doc must also fix the sites referencing it.

Exemptions: none by design — if a reference must survive without a file,
rephrase the comment so it does not carry a docs-relative markdown path (the
doc scan only matches literal path-shaped strings).

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
