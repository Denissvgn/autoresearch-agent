# experiment_parser Module

**Path:** `src/core/experiment_parser.py`

## Description

Parse prepare.py stdout output into structured metrics.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `dataclasses` | `dataclass`, `field` |
| `json` | `json` |
| `logging` | `logging` |
| `re` | `re` |
| `typing` | `Any`, `Dict`, `List`, `Optional` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [IterationMetrics](../entities/IterationMetrics.md) | 19 | — | Parsed metrics from a single prepare.py run. |
| [HpoTrialResult](../entities/HpoTrialResult.md) | 43 | — | A single trial from an HPO study. |
| [HpoStudyResult](../entities/HpoStudyResult.md) | 54 | — | Parsed HPO study output from prepare.py --hpo mode. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `parse_prepare_output` | `(stdout: str) -> IterationMetrics` | — | Parse the --- delimited key-value block from prepare.py stdout. |
| `parse_iteration_marker` | `(text: str) -> Optional[Dict[str, Any]]` | — | Parse an ITERATION_RESULT: JSON line from agent output. |
| `is_hpo_study_output` | `(stdout: str) -> bool` | — | Quick check whether stdout contains an HPO study --- block. |
| `parse_hpo_study_output` | `(stdout: str) -> Optional[HpoStudyResult]` | — | Parse the --- delimited HPO study block from prepare.py --hpo output. |
