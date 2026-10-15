# TestPluginCannotForgeVerifiedMetric

**Location:** `tests/test_plugin_runner.py:307`
**Kind:** Class
**Bases:** —
**Module:** [test_plugin_runner](../modules/test_plugin_runner.md)

## Description

X-004 T6: metrics trust stays server-side. A plugin parser produces only a
CANDIDATE result; the orchestrator re-validates the server nonce. The runner
does not itself enforce nonce semantics (that's ``output_parser._verify_nonce``),
but this test pins the contract: the plugin's output is treated as untrusted
structured data, nothing more.

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_plugin_output_is_untrusted_data` | *(async)* `(skill_dir: Path, tmp_path: Path)` | `@pytest.mark.asyncio` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_plugin_runner](../modules/test_plugin_runner.md) | 1 | — |
