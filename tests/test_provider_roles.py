"""Provider/model roles and capabilities resolve consistently on every path.

The manifest's primary/insight model roles and output caps apply to all
provider paths including the default one; capabilities are validated before
session side effects; provider-specific request options stay behind the
adapter and unsupported combinations are rejected with actionable
diagnostics instead of silently substituting another model.
"""
from __future__ import annotations

import types

import pytest

from src.core.llm_provider import (
    AnthropicProvider,
    ModelRoles,
    OpenAIProvider,
    ProviderCapabilities,
    ProviderCapabilityMismatch,
    RequiredCapabilities,
    UnsupportedModelSetting,
    clamp_output_tokens,
    resolve_model_roles,
)
from src.core.skill_manifest import LLMConfig


class _Settings:
    anthropic_model = "settings-primary"
    anthropic_default_haiku_model = "settings-haiku"
    max_output_tokens_per_call = 8192


def test_manifest_roles_apply_on_the_default_provider_path():
    cfg = LLMConfig(
        provider="anthropic",
        primary_model="skill-primary",
        insight_model="skill-insight",
        max_output_tokens=4096,
    )
    roles = resolve_model_roles(cfg, _Settings)
    assert roles == ModelRoles(
        primary_model="skill-primary",
        insight_model="skill-insight",
        max_output_tokens=4096,
    )
    # an anthropic skill without a primary override falls back to the
    # configured default; the insight role falls back to the primary model
    fallback = resolve_model_roles(
        LLMConfig(provider="anthropic", primary_model=""), _Settings
    )
    assert fallback.primary_model == "settings-primary"
    assert fallback.insight_model == "settings-primary"


def test_nonanthropic_without_primary_model_is_rejected_with_diagnostics():
    cfg = LLMConfig(provider="openai", primary_model="")
    with pytest.raises(UnsupportedModelSetting) as excinfo:
        resolve_model_roles(cfg, _Settings)
    message = str(excinfo.value)
    assert "openai" in message
    assert "llm.primary_model" in message


def test_clamp_output_tokens_honors_provider_and_settings_caps():
    capped = ProviderCapabilities(
        native_tool_use=True,
        streaming=False,
        system_prompt=True,
        max_context_tokens=200_000,
        max_output_tokens=8192,
    )
    assert clamp_output_tokens(
        capped, requested=16_384, settings_cap=32_000
    ) == 8192
    assert clamp_output_tokens(capped, requested=2048, settings_cap=32_000) == 2048
    uncapped = ProviderCapabilities(
        native_tool_use=True,
        streaming=False,
        system_prompt=True,
        max_context_tokens=32_000,
    )
    assert clamp_output_tokens(
        uncapped, requested=16_384, settings_cap=4096
    ) == 4096


class _FakeMessages:
    def __init__(self) -> None:
        self.captured: dict = {}

    async def create(self, **kwargs):
        self.captured = kwargs
        usage = types.SimpleNamespace(input_tokens=1, output_tokens=1)
        block = types.SimpleNamespace(type="text", text="ok")
        return types.SimpleNamespace(
            content=[block], stop_reason="end_turn", usage=usage,
        )


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


def _anthropic_provider():
    provider = AnthropicProvider(
        base_url="https://example.invalid", api_key="k", timeout_s=5.0,
    )
    client = _FakeAnthropicClient()
    provider._client = client
    return provider, client


@pytest.mark.asyncio
async def test_anthropic_request_honors_roles_and_caps():
    provider, client = _anthropic_provider()
    cfg = LLMConfig(
        provider="anthropic",
        primary_model="skill-primary",
        max_output_tokens=4096,
    )
    roles = resolve_model_roles(cfg, _Settings)
    output_cap = clamp_output_tokens(
        provider.capabilities(),
        requested=roles.max_output_tokens,
        settings_cap=_Settings.max_output_tokens_per_call,
    )
    await provider.messages_create(
        model=roles.primary_model,
        system=None,
        messages=[],
        tools=[],
        max_tokens=output_cap,
    )
    assert client.messages.captured["model"] == "skill-primary"
    assert client.messages.captured["max_tokens"] == 4096


class _FakeCompletions:
    def __init__(self) -> None:
        self.captured: dict = {}

    async def create(self, **kwargs):
        self.captured = kwargs
        usage = types.SimpleNamespace(prompt_tokens=1, completion_tokens=1)
        choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content="ok"),
            finish_reason="stop",
        )
        return types.SimpleNamespace(choices=[choice], usage=usage)


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = types.SimpleNamespace(completions=_FakeCompletions())


def _openai_provider():
    provider = OpenAIProvider(
        base_url="https://example.invalid", api_key="k", timeout_s=5.0,
    )
    client = _FakeOpenAIClient()
    provider._client = client
    return provider, client


@pytest.mark.asyncio
async def test_openai_request_honors_roles_and_caps():
    provider, client = _openai_provider()
    cfg = LLMConfig(
        provider="openai",
        primary_model="skill-primary",
        max_output_tokens=2048,
    )
    roles = resolve_model_roles(cfg, _Settings)
    output_cap = clamp_output_tokens(
        provider.capabilities(),
        requested=roles.max_output_tokens,
        settings_cap=_Settings.max_output_tokens_per_call,
    )
    await provider.messages_create(
        model=roles.primary_model,
        system=None,
        messages=[],
        tools=[],
        max_tokens=output_cap,
    )
    assert client.chat.completions.captured["model"] == "skill-primary"
    assert client.chat.completions.captured["max_tokens"] == 2048


@pytest.mark.asyncio
async def test_insight_calls_honor_the_manifest_role_and_cap():
    cfg = LLMConfig(
        provider="anthropic",
        primary_model="skill-primary",
        insight_model="skill-insight",
        max_output_tokens=128,
    )
    roles = resolve_model_roles(cfg, _Settings)

    provider, client = _anthropic_provider()
    await provider.complete(
        model=roles.insight_model,
        prompt="p",
        max_tokens=clamp_output_tokens(
            provider.capabilities(),
            requested=min(300, roles.max_output_tokens),
            settings_cap=_Settings.max_output_tokens_per_call,
        ),
    )
    assert client.messages.captured["model"] == "skill-insight"
    assert client.messages.captured["max_tokens"] == 128

    openai_provider, openai_client = _openai_provider()
    openai_roles = resolve_model_roles(
        LLMConfig(
            provider="openai",
            primary_model="skill-primary",
            insight_model="skill-insight",
            max_output_tokens=64,
        ),
        _Settings,
    )
    await openai_provider.complete(
        model=openai_roles.insight_model,
        prompt="p",
        max_tokens=clamp_output_tokens(
            openai_provider.capabilities(),
            requested=min(300, openai_roles.max_output_tokens),
            settings_cap=_Settings.max_output_tokens_per_call,
        ),
    )
    assert openai_client.chat.completions.captured["model"] == "skill-insight"
    assert openai_client.chat.completions.captured["max_tokens"] == 64


def test_output_cap_demand_rejects_unsatisfiable_settings():
    capped = ProviderCapabilities(
        native_tool_use=True,
        streaming=False,
        system_prompt=True,
        max_context_tokens=200_000,
        max_output_tokens=8192,
    )
    RequiredCapabilities(max_output_tokens=4096).check(capped, "anthropic")
    with pytest.raises(ProviderCapabilityMismatch) as excinfo:
        RequiredCapabilities(max_output_tokens=16_384).check(capped, "anthropic")
    message = str(excinfo.value)
    assert "max_output_tokens" in message
    assert "reduce" in message


@pytest.mark.asyncio
async def test_unsupported_combination_fails_before_session_creation(
    tmp_path, monkeypatch
):
    import src.core.skill_runtime as skill_runtime_mod
    import src.core.support_matrix as support_matrix_mod
    from src.core.orchestrator import ResearchConfig
    from src.core.results_store import ResultsStore
    from src.core.session_manager import SessionManager

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    manager = SessionManager(store)

    demanding = types.SimpleNamespace(
        llm=LLMConfig(
            provider="anthropic",
            primary_model="skill-primary",
            required_max_context_tokens=500_000,
        )
    )
    fake_runtime = types.SimpleNamespace(manifest=demanding)
    monkeypatch.setattr(
        skill_runtime_mod,
        "materialize_skill_runtime",
        lambda orchestrator, config: fake_runtime,
    )
    monkeypatch.setattr(
        support_matrix_mod, "validate_manifest_support", lambda manifest: [],
    )

    config = ResearchConfig(
        id="res_cap",
        instrument="EURUSD",
        timeframe="1h",
        model_type="",
        skill_id="prompt-engineering",
        skill_params={},
        subject_id="EURUSD",
        variant="1h",
    )
    with pytest.raises(ProviderCapabilityMismatch, match="max_context_tokens"):
        SessionManager._validate_session_skill(config)
    # the refusal happens before any side effect: no run row exists
    assert await store.list_sessions() == []
    assert await store.get_session("res_cap") is None


def test_effective_config_records_requested_versus_effective_identity():
    from src.config import settings
    from src.core.research_manifest import _model_identity

    manifest = types.SimpleNamespace(
        llm=LLMConfig(
            provider="anthropic",
            primary_model="",
            insight_model="skill-insight",
            max_output_tokens=128,
        )
    )
    identity = _model_identity(manifest)
    # requested is what the manifest asked for; effective is what the
    # runtime resolves (the default primary on this provider path)
    assert identity["requested"]["primary_model"] == ""
    assert identity["effective"]["primary_model"] == settings.anthropic_model
    assert identity["effective"]["insight_model"] == "skill-insight"
    assert identity["effective"]["max_output_tokens"] == 128

    unresolvable = types.SimpleNamespace(
        llm=LLMConfig(provider="openai", primary_model="")
    )
    identity = _model_identity(unresolvable)
    assert identity["effective"] is None
    assert "primary_model" in identity["error"]


def test_global_provider_and_model_override_routes_skill_to_local_llm():
    from src.core.llm_provider import resolve_effective_provider

    # Skill manifest declares anthropic + claude, but operator configures
    # a local Ollama provider + local model globally via settings.
    cfg = LLMConfig(
        provider="anthropic",
        primary_model="claude-sonnet-4-20250514",
        insight_model="claude-haiku-4-20250514",
        max_output_tokens=4096,
    )
    local_settings = types.SimpleNamespace(
        llm_provider="ollama",
        llm_model="qwen2.5-coder:32b",
        llm_insight_model="",
        max_output_tokens_per_call=8192,
    )
    assert resolve_effective_provider(cfg, local_settings) == "ollama"
    roles = resolve_model_roles(cfg, local_settings)
    assert roles.primary_model == "qwen2.5-coder:32b"
    assert roles.insight_model == "qwen2.5-coder:32b"
    assert roles.max_output_tokens == 4096
