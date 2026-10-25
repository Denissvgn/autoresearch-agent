# phases Module

**Path:** `tests/fixtures/skill_cases/adaptive-phase/phases.py`

## Description

Adaptive phase-advancement plugin (motivating skill case 1).

The completion rule adapts to the evidence history: advance early when
the stage records convergence, or when the recent trend plateaus. Fixed
declarative evidence_keys cannot express "advance on early convergence
OR a plateau in the recent history" — the rule needs the values, not just
the keys. Input: JSON on stdin; output: JSON on stdout (pinned schema).

## Imports

| Source | Symbols |
|--------|---------|
| `json` | `json` |
| `sys` | `sys` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `main` | `() -> None` | — | — |
