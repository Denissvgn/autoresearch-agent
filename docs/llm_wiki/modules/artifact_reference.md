# artifact_reference Module

**Path:** `src/core/artifact_reference.py`

## Description

Artifact reference normalization for autoresearch metadata.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `collections.abc` | `MutableMapping` |
| `typing` | `Any` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/results.py"]
    n1["src/core/artifact_reference.py"]
    n2["src/core/config_promoter.py"]
    n3["src/core/consistency_validator.py"]
    n4["src/core/iteration_snapshot.py"]
    n5["src/core/orchestrator.py"]
    n6["src/core/output_parser.py"]
    n7["src/core/postgres_state_store.py"]
    n8["src/core/research_phase_plan.py"]
    n9["src/core/research_state.py"]
    n10["src/core/result_artifact.py"]
    n11["src/core/state_store.py"]
    n0 --> n1
    n0 --> n3
    n0 --> n9
    n2 --> n1
    n2 --> n3
    n2 --> n8
    n2 --> n11
    n3 --> n1
    n4 --> n1
    n5 --> n1
    n5 --> n2
    n5 --> n3
    n5 --> n4
    n5 --> n6
    n5 --> n8
    n5 --> n10
    n5 --> n11
    n6 --> n1
    n7 --> n1
    n7 --> n11
    n8 --> n1
    n8 --> n3
    n9 --> n1
    n9 --> n3
    n9 --> n8
    n10 --> n1
    n11 --> n1
    click n0 "../modules/results.md"
    click n1 "../modules/artifact_reference.md"
    click n2 "../modules/config_promoter.md"
    click n3 "../modules/consistency_validator.md"
    click n4 "../modules/iteration_snapshot.md"
    click n5 "../modules/orchestrator.md"
    click n6 "../modules/output_parser.md"
    click n7 "../modules/postgres_state_store.md"
    click n8 "../modules/research_phase_plan.md"
    click n9 "../modules/research_state.md"
    click n10 "../modules/result_artifact.md"
    click n11 "../modules/state_store.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [results](../modules/results.md) |
| Inbound | [config_promoter](../modules/config_promoter.md) |
| Inbound | [consistency_validator](../modules/consistency_validator.md) |
| Inbound | [iteration_snapshot](../modules/iteration_snapshot.md) |
| Inbound | [orchestrator](../modules/orchestrator.md) |
| Inbound | [output_parser](../modules/output_parser.md) |
| Inbound | [postgres_state_store](../modules/postgres_state_store.md) |
| Inbound | [research_phase_plan](../modules/research_phase_plan.md) |
| Inbound | [research_state](../modules/research_state.md) |
| Inbound | [result_artifact](../modules/result_artifact.md) |
| Inbound | [state_store](../modules/state_store.md) |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `normalize_optional_artifact_ref` | `(value: Any) -> str \| None` | — | Return a real artifact reference string or None for sentinel values. |
| `is_sentinel_artifact_ref` | `(value: Any) -> bool` | — | Return True when an explicit artifact reference value is a sentinel. |
| `first_valid_artifact_ref` | `(*values: Any) -> str \| None` | — | Return the first normalized artifact reference from candidates. |
| `normalize_artifact_references_in_mapping` | `(payload: MutableMapping[str, Any], *, keys: frozenset[str] = ARTIFACT_REFERENCE_KEYS) -> bool` | — | Normalize known artifact-reference fields in a nested mapping. |
