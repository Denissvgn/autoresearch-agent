# test_codex_harness Module

**Path:** `tests/test_codex_harness.py`

## Description

Codex harness adapter: recorded protocol fixtures and common contracts.

The recorded transcripts are the conformance fixtures: they pin the
documented ``codex exec --json`` shapes (current and the known pre-v0.44
drift) and the mapping into the common event/proposal/usage contracts.
The live smoke is bounded and opt-in.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `shutil` | `shutil` |
| `src.core.codex_harness` | `CODEX_INTERFACE`, `CODEX_SCHEMA_PIN`, `UNSUPPORTED_OPTIONAL_FEATURES`, `CodexHarnessAdapter`, `CodexRunConfig`, `map_candidate_changes`, `map_usage`, `normalize_codex_event` |
| `src.core.harness_adapter` | `request_pause`, `request_steer` |
| `src.core.harness_contract` | `ATTACH_MODE_CONTINUATION`, `ATTACH_MODE_NATIVE_RESUME`, `HarnessContractError`, `HarnessLifecycleError`, `UnsupportedCapabilityError` |
| `src.core.research_kernel` | `AttemptResult`, `run_kernel_lifecycle` |
| `sys` | `sys` |
| `time` | `time` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/codex_harness.py"]
    n1["src/core/harness_adapter.py"]
    n2["src/core/harness_contract.py"]
    n3["src/core/research_kernel.py"]
    n4["tests/test_codex_harness.py"]
    n0 --> n2
    n1 --> n2
    n4 --> n0
    n4 --> n1
    n4 --> n2
    n4 --> n3
    click n0 "../modules/codex_harness.md"
    click n1 "../modules/harness_adapter.md"
    click n2 "../modules/harness_contract.md"
    click n3 "../modules/research_kernel.md"
    click n4 "../modules/test_codex_harness.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [codex_harness](../modules/codex_harness.md) |
| Outbound | [harness_adapter](../modules/harness_adapter.md) |
| Outbound | [harness_contract](../modules/harness_contract.md) |
| Outbound | [research_kernel](../modules/research_kernel.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_fake_codex_script` | `(tmp_path, events)` | — | A stub 'codex' that replays the recorded fixture on stdout. |
| `_run_fixture` | `(tmp_path, events = None)` | — | — |
| `test_recorded_fixture_maps_into_common_contracts` | `(tmp_path)` | — | — |
| `test_legacy_schema_drift_parses_defensively` | `()` | — | — |
| `test_unknown_native_events_are_tolerated` | `()` | — | — |
| `test_only_demonstrated_features_are_advertised` | `()` | — | — |
| `test_attach_is_honest_and_close_is_idempotent` | `(tmp_path)` | — | — |
| `test_denied_permissions_fail_never_hang_or_succeed` | `(tmp_path)` | — | — |
| `test_adapter_executes_kernel_lifecycle` | `(tmp_path)` | — | — |
| `test_live_smoke_is_bounded_and_opt_in` | `(tmp_path)` | — | Opt-in live smoke: explicit version, auth mode, usage, teardown. |
