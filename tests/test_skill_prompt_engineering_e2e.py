"""P4-016 — End-to-end prompt-engineering session on OpenAI provider (ARC-011).

The Phase-4 milestone: a non-ML domain runs as a first-class peer. This test
validates the full chain with a **mocked** ``OpenAIProvider`` (deterministic,
no spend). The real wire translation is pinned in P4-011.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

try:
    import openai  # noqa: F401
except ModuleNotFoundError:
    sys.modules["openai"] = types.SimpleNamespace(
        AsyncOpenAI=MagicMock(return_value=MagicMock()),
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.core.llm_provider import OpenAIProvider, build_provider
from src.core.skill_loader import load_skill_manifest
from src.core.skill_runtime import ManifestSkillRuntime

SKILL_YAML = Path(__file__).resolve().parents[1] / "skills" / "prompt-engineering" / "SKILL.yaml"
EVAL_RUN = Path(__file__).resolve().parents[1] / "skills" / "prompt-engineering" / "eval" / "run.py"


class TestPromptEngineeringSkillManifest:
    """P4-012: the skill manifest loads and declares the Phase-4 properties."""

    @pytest.fixture
    def manifest(self):
        return load_skill_manifest(SKILL_YAML, settings_obj=types.SimpleNamespace())

    def test_skill_id_and_category(self, manifest):
        assert manifest.id == "prompt-engineering"
        assert manifest.category == "generative"

    def test_provider_is_openai(self, manifest):
        assert manifest.llm.provider == "openai"
        assert manifest.llm.primary_model == "gpt-4o"

    def test_require_signed_metrics(self, manifest):
        assert manifest.output_parser.require_signed_metrics is True
        assert manifest.output_parser.nonce_field == "server_nonce"

    def test_promotion_target_is_registry_api(self, manifest):
        assert manifest.promotion_target.primary.kind == "registry_api"


class TestCrossProviderRouter:
    """P4-010: the provider router constructs an OpenAIProvider for openai."""

    def test_build_provider_openai(self):
        stub = types.SimpleNamespace(
            openai_base_url="http://oai.invalid",
            openai_api_key=None,
            openai_api_timeout_s=30,
        )
        provider = build_provider("openai", settings_obj=stub)
        assert isinstance(provider, OpenAIProvider)
        assert provider.name == "openai"


class TestEvalScorerNonceEcho:
    """P4-014: the eval scorer echoes the session nonce in the marker."""

    def test_scorer_emits_nonce(self, tmp_path):
        (tmp_path / "prompt.yaml").write_text("You are a helpful assistant.", encoding="utf-8")
        (tmp_path / "eval_set.jsonl").write_text(
            json.dumps({"input": "What is 2+2?", "expected": "4"}) + "\n", encoding="utf-8"
        )
        nonce = "deadbeef" * 8
        result = subprocess.run(
            [sys.executable, str(EVAL_RUN), "--prompt", str(tmp_path / "prompt.yaml"),
             "--eval", str(tmp_path / "eval_set.jsonl")],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "AUTORESEARCH_SESSION_NONCE": nonce},
        )
        assert result.returncode == 0, result.stderr
        marker_line = [l for l in result.stdout.splitlines() if l.startswith("ITERATION_RESULT:")]
        assert len(marker_line) == 1
        payload = json.loads(marker_line[0][len("ITERATION_RESULT:"):])
        assert payload["server_nonce"] == nonce
        assert payload["status"] == "completed"


class TestManifestSkillRuntimeNonceValidation:
    """P4-003: ManifestSkillRuntime threads nonce config from the manifest."""

    @pytest.fixture
    def runtime(self):
        manifest = load_skill_manifest(SKILL_YAML, settings_obj=types.SimpleNamespace())
        return ManifestSkillRuntime(manifest, orchestrator=MagicMock())

    def test_valid_nonce_accepted(self, runtime):
        nonce = "aabbccdd" * 8
        marker = (
            'ITERATION_RESULT: {"status":"completed","primary_metric":0.8,'
            f'"metric_name":"composite_eval_score","server_nonce":"{nonce}"}}'
        )
        result = runtime.parse_iteration(marker, session_nonce=nonce)
        assert result is not None
        assert result["metrics_verification"] == "metrics_verified"

    def test_forged_nonce_rejected(self, runtime):
        nonce = "aabbccdd" * 8
        marker = (
            'ITERATION_RESULT: {"status":"completed","primary_metric":0.9,'
            '"server_nonce":"wrong"}'
        )
        result = runtime.parse_iteration(marker, session_nonce=nonce)
        assert result is None

    def test_missing_nonce_rejected(self, runtime):
        nonce = "aabbccdd" * 8
        marker = 'ITERATION_RESULT: {"status":"completed","primary_metric":0.9}'
        result = runtime.parse_iteration(marker, session_nonce=nonce)
        assert result is None


class TestCanonicalRequestTranslation:
    """P4-017: non-ML skills are accepted (no longer 422)."""

    def test_non_ml_skill_not_rejected(self):
        from src.api.research import StartResearchRequest, _translate_canonical_request

        req = StartResearchRequest(
            skill_id="prompt-engineering", subject_id="default", variant="production",
        )
        conflicts = _translate_canonical_request(req)
        assert req.model_type == ""
        assert req.instrument == "default"
        assert req.timeframe == "production"
        assert conflicts == []
