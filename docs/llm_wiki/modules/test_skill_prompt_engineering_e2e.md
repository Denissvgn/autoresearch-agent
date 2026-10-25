# test_skill_prompt_engineering_e2e Module

**Path:** `tests/test_skill_prompt_engineering_e2e.py`

## Description

P4-016 — End-to-end prompt-engineering session on OpenAI provider (ARC-011).

The Phase-4 milestone: a non-ML domain runs as a first-class peer. Two layers:

* **Asset/contract tests** (manifest shape, provider router, scorer ABI,
  runtime nonce validation, request translation) — deterministic, no spend.
* **The real end-to-end drive** (``test_prompt_engineering_session_end_to_end``,
  added by review C4 2026-08-15): a real ``AgentOrchestrator.run()`` session on
  a real ``OpenAIProvider`` (scripted only at the HTTP client boundary), a real
  governed ``eval/run.py`` subprocess under the skill's manifest command
  policy, the W11 nonce verified in the live loop, a forged marker rejected +
  audited, and the ``research_sessions`` row indistinguishable from an ML row
  except by skill identity.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `json` | `json` |
| `openai` | `openai` |
| `os` | `os` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `secrets` | `_secrets` |
| `src.api.research` | `StartResearchRequest`, `_translate_canonical_request`, `StartResearchRequest`, `_translate_canonical_request`, `StartResearchRequest`, `_translate_canonical_request` |
| `src.config` | `settings`, `settings` |
| `src.core` | `orchestrator` |
| `src.core.llm_provider` | `OpenAIProvider`, `build_provider` |
| `src.core.orchestrator` | `ResearchConfig`, `AgentOrchestrator`, `ResearchConfig` |
| `src.core.plugin_runner` | `PluginCaps`, `PluginRunner` |
| `src.core.results_store` | `ResultsStore` |
| `src.core.skill_loader` | `load_skill_manifest` |
| `src.core.skill_runtime` | `ManifestSkillRuntime` |
| `subprocess` | `subprocess` |
| `sys` | `sys` |
| `types` | `types`, `ModuleType` |
| `typing` | `cast` |
| `unittest.mock` | `MagicMock`, `AsyncMock`, `patch` |
| `yaml` | `yaml` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/api/research.py"]
    n1["src/config.py"]
    n2["src/core/llm_provider.py"]
    n3["src/core/orchestrator.py"]
    n4["src/core/plugin_runner.py"]
    n5["src/core/results_store.py"]
    n6["src/core/skill_loader.py"]
    n7["src/core/skill_runtime.py"]
    n8["tests/test_skill_prompt_engineering_e2e.py"]
    n0 --> n1
    n0 --> n2
    n0 --> n7
    n2 --> n1
    n3 --> n1
    n3 --> n2
    n3 --> n7
    n4 --> n1
    n6 --> n1
    n7 --> n1
    n7 --> n3
    n8 --> n0
    n8 --> n1
    n8 --> n2
    n8 --> n3
    n8 --> n4
    n8 --> n5
    n8 --> n6
    n8 --> n7
    click n0 "../modules/research.md"
    click n1 "../modules/config.md"
    click n2 "../modules/llm_provider.md"
    click n3 "../modules/orchestrator.md"
    click n4 "../modules/plugin_runner.md"
    click n5 "../modules/results_store.md"
    click n6 "../modules/skill_loader.md"
    click n7 "../modules/skill_runtime.md"
    click n8 "../modules/test_skill_prompt_engineering_e2e.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [research](../modules/research.md) |
| Outbound | [config](../modules/config.md) |
| Outbound | [llm_provider](../modules/llm_provider.md) |
| Outbound | [orchestrator](../modules/orchestrator.md) |
| Outbound | [plugin_runner](../modules/plugin_runner.md) |
| Outbound | [results_store](../modules/results_store.md) |
| Outbound | [skill_loader](../modules/skill_loader.md) |
| Outbound | [skill_runtime](../modules/skill_runtime.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 3 | 1 |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [TestPromptEngineeringSkillManifest](../entities/TestPromptEngineeringSkillManifest.md) | 52 | — | P4-012: the skill manifest loads and declares the Phase-4 properties. |
| [TestCrossProviderRouter](../entities/TestCrossProviderRouter.md) | 128 | — | P4-010: the provider router constructs an OpenAIProvider for openai. |
| [TestEvalScorerNonceEcho](../entities/TestEvalScorerNonceEcho.md) | 142 | — | P4-014: the eval scorer echoes the session nonce in the marker. |
| [TestManifestSkillRuntimeNonceValidation](../entities/TestManifestSkillRuntimeNonceValidation.md) | 166 | — | P4-003: ManifestSkillRuntime threads nonce config from the manifest. |
| [TestCanonicalRequestTranslation](../entities/TestCanonicalRequestTranslation.md) | 230 | — | P4-016 (was mislabeled P4-017 — no such task): non-ML skills are |
| [_ScriptedOpenAIClient](../entities/ScriptedOpenAIClient.md) | 292 | — | Stands in at the OpenAI HTTP boundary (chat.completions.create). |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `test_prompt_engineering_session_end_to_end` | *(async)* `(monkeypatch, tmp_path)` | `@pytest.mark.asyncio` | — |
