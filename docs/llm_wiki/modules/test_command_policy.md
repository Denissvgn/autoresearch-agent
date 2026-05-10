# test_command_policy Module

**Path:** `tests/test_command_policy.py`

## Description

_Auto-generated from `tests/test_command_policy.py`._

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `anthropic` | `anthropic` |
| `os` | `os` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core.command_policy` | `evaluate_command_policy` |
| `src.core.command_runner` | `GovernedCommandRunner`, `redact_sensitive_text` |
| `src.core.orchestrator` | `_execute_tool` |
| `sys` | `sys` |
| `time` | `time` |
| `types` | `types` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [_FakeAsyncAnthropic](../entities/test_command_policy__FakeAsyncAnthropic.md) | 17 | — | — |
| [_FakeAPIStatusError](../entities/test_command_policy__FakeAPIStatusError.md) | 21 | `Exception` | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_workspace` | `(tmp_path: Path) -> tuple[str, str]` | — | — |
| `test_command_policy_allows_known_training_operations` | `(tmp_path: Path)` | — | — |
| `test_command_policy_blocks_unsafe_commands` | `(tmp_path: Path, command: str)` | `@pytest.mark.parametrize('command', ['curl https://example.com', '.venv/bin/python -m pip install pandas', 'git status', 'docker ps', '.venv/bin/python scripts/autotuner/promote.py --config runs/autotuner/DOGE_USDT_15m/direction/best_train.yaml', '.venv/bin/python scripts/autotuner/direction/prepare.py --config /etc/passwd', '.venv/bin/python scripts/autotuner/direction/prepare.py --config train.yaml 2>&1', '.venv/bin/python scripts/autotuner/setup.py --instrument $(cat /run/secrets/token)', 'cat /etc/passwd', 'cp train.yaml /tmp/best_train.yaml', ".venv/bin/python -c 'print(123)'", 'cat results.json | head', 'ln -s train.yaml linked.yaml'])` | — |
| `test_command_policy_rejects_symlink_escape_for_cat` | `(tmp_path: Path)` | — | — |
| `test_file_tools_reject_and_filter_symlink_escapes` | `(tmp_path: Path)` | — | — |
| `test_governed_runner_executes_without_shell_and_redacts_output` | `(tmp_path: Path)` | — | — |
| `test_governed_runner_timeout_cleans_process_group` | `(tmp_path: Path)` | — | — |
| `_process_exists` | `(pid: int) -> bool` | — | — |
| `test_execute_tool_returns_policy_rejection_metadata` | `(tmp_path: Path)` | — | — |
| `test_redaction_handles_bearer_and_env_like_values` | `()` | — | — |
