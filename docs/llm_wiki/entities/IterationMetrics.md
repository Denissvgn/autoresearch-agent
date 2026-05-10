# IterationMetrics

**Location:** `src/core/experiment_parser.py:19`
**Bases:** —
**Module:** [experiment_parser](../modules/experiment_parser.md)

**Decorators:** `@dataclass`

## Description

Parsed metrics from a single prepare.py run.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `status` | `str` | `'unknown'` | — |
| `primary_metric` | `Optional[float]` | `None` | — |
| `metric_name` | `Optional[str]` | `None` | — |
| `direction` | `str` | `'higher_is_better'` | — |
| `all_gates_passed` | `bool` | `False` | — |
| `training_time_s` | `Optional[float]` | `None` | — |
| `extra` | `Dict[str, Any]` | `field(...)` | — |

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `to_dict` | `() -> Dict[str, Any]` | — | — |

## Relationships

*No cross-module references detected.*
