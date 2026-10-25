# DriverHost

**Location:** `src/core/driver_host.py:147`
**Kind:** Class
**Bases:** —
**Module:** [driver_host](../modules/driver_host.md)

## Description

Supervises one custom driver process through the JSONL transport.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `__init__` | `(config: DriverHostConfig) -> None` | — | — |
| `start` | `() -> None` | — | Launch the driver in its isolated context. |
| `_drain_stderr` | `() -> None` | — | Bounded stderr capture: never unbounded, never lost silently. |
| `_record` | `(event: dict[str, Any]) -> None` | — | — |
| `events` | `(*, wait_s: float = 0.0) -> list[dict[str, Any]]` | — | Drain the normalized events delivered so far. |
| `wait` | `(*, timeout_s: float) -> DriverOutcome` | — | Wait for the driver to finish; enforce the start deadline. |
| `cancel` | `(*, reason: str = '') -> None` | — | Terminate the driver's whole process group, bounded in time. |
| `_finish` | `(status: str, reason: str) -> DriverOutcome` | — | — |
| `outcome` | `() -> Optional[DriverOutcome]` | `@property` | — |
| `stderr_tail` | `() -> str` | `@property` | The bounded tail of the driver's stderr (diagnostics). |
| `handshake_ok` | `() -> bool` | `@property` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["DriverHost (src/core/driver_host.py)"]
    n1["_EventReader.__init__ (src/core/driver_host.py)"]
    n2["DriverHost.__init__ (src/core/driver_host.py)"]
    n3["test_credential_isolation (tests/test_driver_host.py)"]
    n4["test_descendant_cleanup_kills_the_process_group (tests/test_driver_host.py)"]
    n5["test_malformed_stream_is_bounded (tests/test_driver_host.py)"]
    n6["test_mid_event_process_death_is_attributed (tests/test_driver_host.py)"]
    n7["test_oversized_events_are_refused (tests/test_driver_host.py)"]
    n8["test_stalled_consumer_backpressure_is_bounded (tests/test_driver_host.py)"]
    n9["test_start_deadline_times_out_with_cleanup (tests/test_driver_host.py)"]
    n10["test_stderr_is_bounded_captured (tests/test_driver_host.py)"]
    n11["test_valid_stream_and_example_driver (tests/test_driver_host.py)"]
    n12["test_custom_process_driver_in_the_shared_contract (tests/test_harness_contracts_g4.py)"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    n5 --> n0
    n6 --> n0
    n7 --> n0
    n8 --> n0
    n9 --> n0
    n10 --> n0
    n11 --> n0
    n12 --> n0
    click n0 "../modules/driver_host.md"
    click n1 "../modules/driver_host.md"
    click n2 "../modules/driver_host.md"
    click n3 "../modules/test_driver_host.md"
    click n4 "../modules/test_driver_host.md"
    click n5 "../modules/test_driver_host.md"
    click n6 "../modules/test_driver_host.md"
    click n7 "../modules/test_driver_host.md"
    click n8 "../modules/test_driver_host.md"
    click n9 "../modules/test_driver_host.md"
    click n10 "../modules/test_driver_host.md"
    click n11 "../modules/test_driver_host.md"
    click n12 "../modules/test_harness_contracts_g4.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [driver_host](../modules/driver_host.md) | 11 | — |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `_EventReader.__init__` | type_reference | [driver_host](../modules/driver_host.md) | — |
| `DriverHost.__init__` | type_reference | [driver_host](../modules/driver_host.md) | — |
| `test_credential_isolation` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_descendant_cleanup_kills_the_process_group` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_malformed_stream_is_bounded` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_mid_event_process_death_is_attributed` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_oversized_events_are_refused` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_stalled_consumer_backpressure_is_bounded` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_start_deadline_times_out_with_cleanup` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_stderr_is_bounded_captured` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_valid_stream_and_example_driver` | call | [test_driver_host](../modules/test_driver_host.md) | 1 |
| `test_custom_process_driver_in_the_shared_contract` | call | [test_harness_contracts_g4](../modules/test_harness_contracts_g4.md) | 1 |
