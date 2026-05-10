# HpoStudyResult

**Location:** `src/core/experiment_parser.py:54`
**Bases:** —
**Module:** [experiment_parser](../modules/experiment_parser.md)

**Decorators:** `@dataclass`

## Description

Parsed HPO study output from prepare.py --hpo mode.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `status` | `str` | `'unknown'` | — |
| `n_trials` | `int` | `0` | — |
| `completed_trials` | `int` | `0` | — |
| `best_composite` | `Optional[float]` | `None` | — |
| `training_time_s` | `Optional[float]` | `None` | — |
| `top_trials` | `List[HpoTrialResult]` | `field(...)` | — |
| `extra` | `Dict[str, Any]` | `field(...)` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `to_dict` | `() -> Dict[str, Any]` | — | — |

## Relationships

*No cross-module references detected.*
