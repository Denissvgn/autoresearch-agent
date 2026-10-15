# check_legacy_vocab_branching Module

**Path:** `scripts/check_legacy_vocab_branching.py`

## Description

Legacy-vocabulary branching guard.

The service is skill-driven: sessions name an installed skill and every
domain decision (paths, phase plans, promotion targets, gate evaluation)
derives from the skill manifest. The legacy ``model_type`` vocabulary
(``direction``/``volatility``/``rl``) is frozen history — readable forever,
branched on only inside the frozen legacy surfaces listed below.

This guard fails when NEW code branches on the legacy vocabulary outside
those surfaces, so the invariant is enforced by CI rather than by
convention. To extend the allowlist, add the file with a reason string —
an extension is a design decision, not a lint fix.

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
