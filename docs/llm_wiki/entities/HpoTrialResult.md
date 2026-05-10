# HpoTrialResult

**Location:** `src/core/experiment_parser.py:43`
**Bases:** —
**Module:** [experiment_parser](../modules/experiment_parser.md)

**Decorators:** `@dataclass`

## Description

A single trial from an HPO study.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `rank` | `int` | *required* | — |
| `trial_number` | `int` | *required* | — |
| `composite_score` | `float` | *required* | — |
| `params` | `Dict[str, Any]` | `field(...)` | — |
| `metrics` | `Dict[str, float]` | `field(...)` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

*No cross-module references detected.*
