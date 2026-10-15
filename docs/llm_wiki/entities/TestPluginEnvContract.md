# TestPluginEnvContract

**Location:** `tests/test_plugin_runner.py:53`
**Kind:** Class
**Bases:** —
**Module:** [test_plugin_runner](../modules/test_plugin_runner.md)

## Description

The plugin child env must be default-deny and strip every server secret.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_server_secret_is_stripped` | `(secret_name: str, monkeypatch)` | `@pytest.mark.parametrize('secret_name', ['ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_API_KEY', 'AUTORESEARCH_API_TOKEN', 'AUTORESEARCH_PROMETHEUS_TOKEN', 'MLFLOW_SERVICE_AUTH_TOKEN', 'RL_TRAINER_SERVICE_TOKEN', 'ML_ADMIN_TOKEN', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'])` | — |
| `test_declared_env_keys_are_merged` | `(monkeypatch)` | — | Manifest-declared ``env`` keys are allowed in (then forbidden names |
| `test_forbidden_key_not_smuggled_via_declaration` | `(monkeypatch)` | — | A manifest declaring ``ANTHROPIC_AUTH_TOKEN`` cannot smuggle it in. |
| `test_path_and_locale_survive` | `(monkeypatch)` | — | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_plugin_runner](../modules/test_plugin_runner.md) | 4 | — |
