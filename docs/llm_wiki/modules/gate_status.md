# gate_status Module

**Path:** `src/core/gate_status.py`

## Description

Compatibility helpers for autoresearch gate-status fields.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `logging` | `logging` |
| `typing` | `Any`, `Mapping`, `MutableMapping`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/results.py"]
    n1["src/core/config_promoter.py"]
    n2["src/core/consistency_validator.py"]
    n3["src/core/development_gate_bundle.py"]
    n4["src/core/gate_status.py"]
    n5["src/core/iteration_context.py"]
    n6["src/core/orchestrator.py"]
    n7["src/core/output_parser.py"]
    n8["src/core/postgres_state_store.py"]
    n9["src/core/research_state.py"]
    n10["src/core/state_store.py"]
    n0 --> n2
    n0 --> n4
    n0 --> n9
    n1 --> n2
    n1 --> n3
    n1 --> n4
    n1 --> n10
    n2 --> n4
    n3 --> n4
    n5 --> n2
    n5 --> n4
    n6 --> n2
    n6 --> n4
    n6 --> n5
    n6 --> n7
    n6 --> n10
    n7 --> n4
    n8 --> n4
    n8 --> n10
    n9 --> n2
    n9 --> n4
    n10 --> n4
    click n0 "../modules/results.md"
    click n1 "../modules/config_promoter.md"
    click n2 "../modules/consistency_validator.md"
    click n3 "../modules/development_gate_bundle.md"
    click n4 "../modules/gate_status.md"
    click n5 "../modules/iteration_context.md"
    click n6 "../modules/orchestrator.md"
    click n7 "../modules/output_parser.md"
    click n8 "../modules/postgres_state_store.md"
    click n9 "../modules/research_state.md"
    click n10 "../modules/state_store.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [results](../modules/results.md) |
| Inbound | [config_promoter](../modules/config_promoter.md) |
| Inbound | [consistency_validator](../modules/consistency_validator.md) |
| Inbound | [development_gate_bundle](../modules/development_gate_bundle.md) |
| Inbound | [iteration_context](../modules/iteration_context.md) |
| Inbound | [orchestrator](../modules/orchestrator.md) |
| Inbound | [output_parser](../modules/output_parser.md) |
| Inbound | [postgres_state_store](../modules/postgres_state_store.md) |
| Inbound | [research_state](../modules/research_state.md) |
| Inbound | [state_store](../modules/state_store.md) |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `coerce_bool` | `(value: Any, default: bool = False) -> bool` | — | Coerce common marker/API bool encodings to a real bool. |
| `parse_metrics_payload` | `(raw: Any) -> dict[str, Any]` | — | Return a metrics_json payload as a mapping, or an empty dict. |
| `training_gates_passed_from` | `(payload: Mapping[str, Any], *, default: bool = False) -> bool` | — | Read the canonical training-gates flag with legacy fallback. |
| `training_gates_passed_from_iteration` | `(row: Mapping[str, Any], *, default: bool = False) -> bool` | — | Read training gates from an iteration row and its metrics_json. |
| `normalize_training_gate_aliases` | `(payload: MutableMapping[str, Any], *, legacy_value: Any = None, default: bool = False, logger: Optional[logging.Logger] = None, context: str = '') -> bool` | — | Populate canonical and legacy training gate keys on a mutable payload. |
| `consistency_report_passed` | `(report: Any) -> Optional[bool]` | — | Return report.passed when a consistency report mapping is available. |
