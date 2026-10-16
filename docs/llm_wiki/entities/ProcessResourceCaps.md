# ProcessResourceCaps

**Location:** `src/core/process_limits.py:63`
**Kind:** Class
**Bases:** —
**Module:** [process_limits](../modules/process_limits.md)

**Decorators:** `@dataclass(frozen=True)`

## Description

Finite resource caps for one candidate-controlled subprocess tree.

``None`` means the cap is not requested for this run. Every configured
value is enforced at the OS boundary or the parent boundary as described
in the module docstring; unenforceable configured caps raise
:class:`UnenforceableResourceCapabilityError` at spawn time.

## Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `wall_s` | `Optional[float]` | `None` | — |
| `cpu_s` | `Optional[float]` | `None` | — |
| `rss_mb` | `Optional[int]` | `None` | — |
| `max_processes` | `Optional[int]` | `None` | — |
| `max_output_bytes` | `Optional[int]` | `None` | — |
| `max_file_write_bytes` | `Optional[int]` | `None` | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ProcessResourceCaps (src/core/process_limits.py)"]
    n1["GovernedCommandRunner.run (src/core/command_runner.py)"]
    n2["PluginRunner.run (src/core/plugin_runner.py)"]
    n3["bounded_drain (src/core/process_limits.py)"]
    n4["rlimit_prefix (src/core/process_limits.py)"]
    n5["TreeResourceGuard.__init__ (src/core/process_limits.py)"]
    n6["_guarded_run (tests/test_process_limits.py)"]
    n7["test_cpu_breach_stops_tree_within_bound (tests/test_process_limits.py)"]
    n8["test_file_write_quota_enforced_at_kernel (tests/test_process_limits.py)"]
    n9["test_memory_breach_stops_tree_within_bound (tests/test_process_limits.py)"]
    n10["test_output_breach_stops_tree_and_capture_stays_bounded (tests/test_process_limits.py)"]
    n11["test_process_count_breach_stops_tree_with_no_orphans (tests/test_process_limits.py)"]
    n12["test_termination_latency_within_documented_bound (tests/test_process_limits.py)"]
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
    click n0 "../modules/process_limits.md"
    click n1 "../modules/command_runner.md"
    click n2 "../modules/plugin_runner.md"
    click n3 "../modules/process_limits.md"
    click n4 "../modules/process_limits.md"
    click n5 "../modules/process_limits.md"
    click n6 "../modules/test_process_limits.md"
    click n7 "../modules/test_process_limits.md"
    click n8 "../modules/test_process_limits.md"
    click n9 "../modules/test_process_limits.md"
    click n10 "../modules/test_process_limits.md"
    click n11 "../modules/test_process_limits.md"
    click n12 "../modules/test_process_limits.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [process_limits](../modules/process_limits.md) | 0 | `cpu_s`, `max_file_write_bytes`, `max_output_bytes`, `max_processes`, `rss_mb`, `wall_s` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `GovernedCommandRunner.run` | call | [command_runner](../modules/command_runner.md) | 1 |
| `PluginRunner.run` | call | [plugin_runner](../modules/plugin_runner.md) | 1 |
| `bounded_drain` | type_reference | [process_limits](../modules/process_limits.md) | — |
| `rlimit_prefix` | type_reference | [process_limits](../modules/process_limits.md) | — |
| `TreeResourceGuard.__init__` | type_reference | [process_limits](../modules/process_limits.md) | — |
| `_guarded_run` | type_reference | [test_process_limits](../modules/test_process_limits.md) | — |
| `test_cpu_breach_stops_tree_within_bound` | call | [test_process_limits](../modules/test_process_limits.md) | 1 |
| `test_file_write_quota_enforced_at_kernel` | call | [test_process_limits](../modules/test_process_limits.md) | 1 |
| `test_memory_breach_stops_tree_within_bound` | call | [test_process_limits](../modules/test_process_limits.md) | 1 |
| `test_output_breach_stops_tree_and_capture_stays_bounded` | call | [test_process_limits](../modules/test_process_limits.md) | 1 |
| `test_process_count_breach_stops_tree_with_no_orphans` | call | [test_process_limits](../modules/test_process_limits.md) | 1 |
| `test_termination_latency_within_documented_bound` | call | [test_process_limits](../modules/test_process_limits.md) | 1 |

> References: showing 12 of 14 logical references; 2 omitted by the 12-row generated summary limit.
