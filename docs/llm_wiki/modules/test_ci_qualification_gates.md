# test_ci_qualification_gates Module

**Path:** `tests/test_ci_qualification_gates.py`

## Description

CI qualification gates: deliberate negative fixtures for every guard.

An advertised feature without executable coverage, an unowned skip, a
drifted qualification input, an incomplete unsupported-capability
report, a secret in archived evidence, or a mislabeled live lane must
each fail the gates; the committed pin file must match live inputs.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `importlib.util` | `importlib.util` |
| `json` | `json` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `sys` | `sys` |
| `types` | `ModuleType` |
| `typing` | `cast` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_fake_run` | `(output: str)` | — | — |
| `test_parse_pytest_output_handles_percent_suffixes` | `()` | — | — |
| `test_advertised_feature_without_coverage_fails` | `()` | — | — |
| `test_unowned_skip_fails_and_owned_skip_passes` | `()` | — | — |
| `test_pinned_input_drift_fails` | `()` | — | — |
| `test_incomplete_unsupported_capability_report_fails` | `()` | — | — |
| `test_secret_in_evidence_is_found_and_redacted` | `()` | — | — |
| `test_live_gate_is_visibly_separate_and_never_silent` | `()` | — | — |
| `test_gate_budget_timeout_fails` | `()` | — | — |
| `test_evidence_write_is_sanitized_and_findings_fail` | `(tmp_path)` | — | — |
| `test_committed_pin_file_matches_live_inputs` | `()` | — | The candidate's pinned qualification inputs match reality. |
| `test_capability_report_on_the_real_registry_is_complete` | `()` | — | — |
