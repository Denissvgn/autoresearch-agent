# test_deployment_inputs Module

**Path:** `tests/test_deployment_inputs.py`

## Description

_Auto-generated from `tests/test_deployment_inputs.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `pathlib` | `Path` |
| `subprocess` | `subprocess` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_git` | `() -> subprocess.CompletedProcess[str]` | — | — |
| `test_env_example_exists_and_contains_only_sanitized_values` | `()` | — | — |
| `test_autoresearch_ui_build_inputs_are_tracked_and_outputs_ignored` | `()` | — | — |
| `test_autoresearch_backend_uses_src_layout_and_committed_lockfile` | `()` | — | — |
| `test_autoresearch_dockerfile_matches_ml_service_runtime_contract` | `()` | — | — |
| `test_autoresearch_deployment_documents_single_instance_constraint` | `()` | — | — |
| `test_readme_uses_tracked_env_template_without_token_samples` | `()` | — | — |
