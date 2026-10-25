# SignificanceConfig

**Location:** `src/core/skill_manifest.py:294`
**Kind:** Pydantic model
**Bases:** `BaseModel`
**Module:** [skill_manifest](../modules/skill_manifest.md)

## Description

Multi-seed significance gate (P2 ops — ``metric_schema.significance``).

When declared, keep/discard decisions compare mean±standard-error across
repeated observations of the same config (each seed rerun is a new
sample; the trial-identity hash keeps them distinct) instead of the
fixed-epsilon point test. Absent ⇒ legacy behavior, byte-identical.

## Model Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `extra` | `'forbid'` | model_config |

## Attributes

| Name | Type | Wire name | Required | Nullable | Default | Constraints | Examples | Description |
|------|------|-----------|----------|----------|---------|-------------|-------------|----------|
| `min_samples` | `int` | `min_samples` | No | No | `2` | ge=1; le=10 | — | — |
| `min_sigma` | `float` | `min_sigma` | No | No | `1.0` | ge=0.0 | — | — |
| `planned_repeats` | `int` | `planned_repeats` | No | No | `1` | ge=1; le=10 | — | — |
| `holdout_required` | `bool` | `holdout_required` | No | No | `False` | — | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["SignificanceConfig (src/core/skill_manifest.py)"]
    n1["BaseModel"]
    n2["test_manifest_declares_the_repeat_policy (tests/test_observation_identity.py)"]
    n3["test_noisy_fixture_falls_back_visibly_and_never_qualifies (tests/test_observation_identity.py)"]
    n4["test_sample_counts_and_holdouts_gate_qualification (tests/test_observation_identity.py)"]
    n0 --> n1
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/skill_manifest.md"
    click n2 "../modules/test_observation_identity.md"
    click n3 "../modules/test_observation_identity.md"
    click n4 "../modules/test_observation_identity.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [skill_manifest](../modules/skill_manifest.md) | 0 | `holdout_required`, `min_samples`, `min_sigma`, `planned_repeats` |

### Structure

| Kind | Entity | Module |
|---|---|---|
| Base | `BaseModel` | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `test_manifest_declares_the_repeat_policy` | call | [test_observation_identity](../modules/test_observation_identity.md) | 3 |
| `test_noisy_fixture_falls_back_visibly_and_never_qualifies` | call | [test_observation_identity](../modules/test_observation_identity.md) | 1 |
| `test_sample_counts_and_holdouts_gate_qualification` | call | [test_observation_identity](../modules/test_observation_identity.md) | 2 |
