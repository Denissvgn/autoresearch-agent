"""P4-016 — End-to-end prompt-engineering session on OpenAI provider (ARC-011).

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

    def test_valid_nonce_accepted_as_bytes(self, runtime):
        """P4-003 wiring: the orchestrator passes ``session_nonce`` as ``bytes``
        (derived from ``bytes.fromhex(config.session_nonce)``). The runtime's
        ``parse_iteration`` must hex-encode the bytes for comparison — this is
        the exact shape the hot-path call at orchestrator.py uses."""
        nonce_hex = "aabbccdd" * 8
        nonce_bytes = bytes.fromhex(nonce_hex)
        marker = (
            'ITERATION_RESULT: {"status":"completed","primary_metric":0.82,'
            f'"metric_name":"composite_eval_score","server_nonce":"{nonce_hex}"}}'
        )
        result = runtime.parse_iteration(marker, session_nonce=nonce_bytes)
        assert result is not None
        assert result["metrics_verification"] == "metrics_verified"
        assert result["primary_metric"] == 0.82

    def test_forged_marker_rejected_as_bytes(self, runtime):
        """P4-003 wiring: a forged nonce (bytes session nonce, wrong echoed
        value) is rejected. This is the path that, in the orchestrator, makes
        the ``if marker:`` branch treat the marker as absent and emits the
        ``metrics.forged`` audit event."""
        nonce_bytes = bytes.fromhex("aabbccdd" * 8)
        marker = (
            'ITERATION_RESULT: {"status":"completed","primary_metric":0.99,'
            '"server_nonce":"deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"}'
        )
        result = runtime.parse_iteration(marker, session_nonce=nonce_bytes)
        assert result is None  # forged → rejected (orchestrator won't record it)


class TestCanonicalRequestTranslation:
    """P4-016 (was mislabeled P4-017 — no such task): non-ML skills are
    accepted (no longer 422)."""

    def test_non_ml_skill_not_rejected(self):
        from src.api.research import StartResearchRequest, _translate_canonical_request

        req = StartResearchRequest(
            skill_id="prompt-engineering", subject_id="default", variant="production",
        )
        conflicts = _translate_canonical_request(req)
        # Identity alias fallback: a non-legacy skill is its own model_type.
        assert req.model_type == "prompt-engineering"
        assert req.instrument == "default"
        assert req.timeframe == "production"
        assert conflicts == []


# ============================================================================
# P4-016 — the REAL end-to-end drive (ARC-011 review C4, 2026-08-15).
#
# The Phase-4 close-out claimed this milestone was met while no session had
# ever run: the old "e2e" tests never entered AgentOrchestrator.run(), and the
# skill's command policy was dead config (C2-3). This drive exercises, in one
# session: canonical skill materialization (C1/C2), the manifest command
# policy executing the REAL governed eval subprocess, per-command W11 nonce
# delivery (C3), nonce-verified marker recording, forged-marker rejection +
# audit, cross-provider turns through the real OpenAIProvider translation, and
# the §7.14 "indistinguishable from an ML row" property.
# ============================================================================


class _ScriptedOpenAIClient:
    """Stands in at the OpenAI HTTP boundary (chat.completions.create).

    Content-driven (not turn-counted) so continuation kicks between turns
    don't desync the script:
    1. no eval output seen yet → run the eval via the bash tool;
    2. eval output present, not yet relayed → relay its exact marker line
       in the SAME response that issues the next eval (the marker-relay
       contract: a marker is only honored in a turn that itself ran a
       training command — this is how real agents behave);
    3. relayed, not yet forged → emit a FORGED marker (tampered nonce),
       again alongside a real eval call;
    4. otherwise → TERMINATE_REQUEST + end turn.
    Tool-free calls (the insights path) get plain JSON text.
    """

    def __init__(self, eval_command: str, session_ws: Path, nonce_is: str) -> None:
        self.calls: list[dict] = []
        self._eval_command = eval_command
        self._session_ws = session_ws
        self._forged_marker = (
            'ITERATION_RESULT: {"status":"completed","primary_metric":0.999,'
            '"metric_name":"composite_eval_score","training_gates_passed":true,'
            f'"server_nonce":"{nonce_is}"}}'
        )
        self._relayed = False
        self._forged_sent = False
        self.relayed_marker: str | None = None

    def _chat(self, *, content=None, tool_calls=None, finish="stop"):
        message = types.SimpleNamespace(content=content, tool_calls=tool_calls)
        choice = types.SimpleNamespace(message=message, finish_reason=finish)
        usage = types.SimpleNamespace(prompt_tokens=12, completion_tokens=34)
        return types.SimpleNamespace(choices=[choice], usage=usage, model="gpt-4o")

    @staticmethod
    def _tool_call(call_id: str, name: str, args: dict):
        fn = types.SimpleNamespace(name=name, arguments=json.dumps(args))
        return types.SimpleNamespace(id=call_id, type="function", function=fn)

    def _eval_tool_call(self, call_id: str):
        return self._tool_call(
            call_id, "bash",
            {"command": self._eval_command, "timeout_s": 60},
        )

    def _marker_from_request(self, kwargs: dict) -> str | None:
        for msg in kwargs.get("messages") or []:
            content = msg.get("content") if isinstance(msg, dict) else None
            if isinstance(content, str) and "ITERATION_RESULT:" in content:
                for line in content.splitlines():
                    if line.startswith("ITERATION_RESULT:"):
                        return line
        return None

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if "tools" not in kwargs:  # insights/completion path
            return self._chat(content='{"summary": "e2e session complete"}')
        marker = self._marker_from_request(kwargs)
        if marker is None:
            return self._chat(
                tool_calls=[self._eval_tool_call("call_eval_1")],
                finish="tool_calls",
            )
        if not self._relayed:
            self._relayed = True
            self.relayed_marker = marker
            return self._chat(
                content=f"Eval finished — relaying the result.\n{marker}",
                tool_calls=[self._eval_tool_call("call_eval_2")],
                finish="tool_calls",
            )
        if not self._forged_sent:
            self._forged_sent = True
            return self._chat(
                content=(
                    "Another run went even better:\n" + self._forged_marker
                ),
                tool_calls=[self._eval_tool_call("call_eval_3")],
                finish="tool_calls",
            )
        return self._chat(
            content=(
                "TERMINATE_REQUEST: iterations complete, terminating\n"
                "phase=promotion_proposal"
            ),
        )


@pytest.mark.asyncio
async def test_prompt_engineering_session_end_to_end(monkeypatch, tmp_path):
    import secrets as _secrets

    from src.config import settings
    from src.core import orchestrator as orchestrator_module
    from src.core.orchestrator import AgentOrchestrator, ResearchConfig
    from src.core.plugin_runner import PluginCaps, PluginRunner
    from src.core.results_store import ResultsStore

    # ── Hermetic workspace root: policy root + cwd for governed commands. ──
    ws_root = tmp_path / "workspace"
    venv_bin = ws_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    os.symlink(sys.executable, venv_bin / "python")
    monkeypatch.setattr(settings, "workspace_root", str(ws_root))

    # ── Render the session workspace with the REAL bootstrap (P4-015 ABI). ──
    session_ws = (
        ws_root / "runs" / "autotuner" / "default_production" / "prompt-engineering"
    )
    session_ws.mkdir(parents=True)
    bootstrap = await PluginRunner().run(
        skill_dir=SKILL_YAML.parent,
        plugin="bootstrap.py",
        kind="bootstrap",
        input_json={
            "workspace": str(session_ws), "mode": "live", "skill_params": {},
        },
        caps=PluginCaps(fs_write="workspace", timeout_s=30.0),
        workspace=session_ws,
    )
    assert bootstrap.ok, f"bootstrap failed: {bootstrap.error}"
    assert (session_ws / "prompt.yaml").is_file()
    assert (session_ws / "eval_set.jsonl").is_file()

    # ── Seed the session (the session-manager part of the flow). ───────────
    store = ResultsStore(str(tmp_path / "e2e.sqlite"))
    await store.initialize()
    research_id = "res_pe_e2e0001"
    nonce_hex = _secrets.token_hex(32)
    await store.create_session(
        session_id=research_id,
        instrument="default",
        timeframe="production",
        model_type="",  # canonical non-ML session (P4-016 translation)
        tag="p4-016-e2e",
        quick_mode=False,
        max_iterations=10,
        max_budget_usd=5.0,
        focus_hint=None,
        workspace_path=str(session_ws),
    )
    config = ResearchConfig(
        id=research_id,
        instrument="default",
        timeframe="production",
        model_type="",
        skill_id="prompt-engineering",
        tag="p4-016-e2e",
        max_iterations=10,
        max_budget_usd=5.0,
        timeout_s=600,
        workspace_path=str(session_ws),
        session_nonce=nonce_hex,
    )

    # ── Real OpenAIProvider, scripted only at the HTTP boundary. ───────────
    eval_command = (
        ".venv/bin/python eval/run.py "
        f"--prompt {session_ws / 'prompt.yaml'} "
        f"--eval {session_ws / 'eval_set.jsonl'}"
    )
    scripted = _ScriptedOpenAIClient(
        eval_command, session_ws, nonce_is="00" * 32,
    )
    provider = build_provider(
        "openai",
        settings_obj=types.SimpleNamespace(
            openai_base_url="http://oai.invalid",
            openai_api_key="test-key",
            openai_api_timeout_s=30,
        ),
    )
    provider._client = types.SimpleNamespace(  # noqa: SLF001
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=scripted.create),
        ),
    )
    # P4-010 per-session selection calls this symbol inside orchestrator.
    monkeypatch.setattr(
        orchestrator_module, "build_provider", lambda name, **kw: provider,
    )

    orchestrator = AgentOrchestrator(store)
    from unittest.mock import AsyncMock, patch

    with patch.object(
        orchestrator, "_load_claude_md_async",
        new=AsyncMock(return_value=""),
    ):
        await orchestrator.run(config)

    # ── The session row: terminal + §7.14 indistinguishable from ML. ───────
    session = await store.get_session(research_id)
    assert session is not None, "run() must leave a research_sessions row"
    assert session["status"] in {"completed", "stopped"}
    assert str(session.get("terminal_reason") or "").startswith(
        "agent_self_terminated",
    )
    assert isinstance(session.get("best_iteration"), int)
    assert session["best_iteration"] >= 1
    assert (session.get("effective_iteration_count") or 0) >= 1

    # ── Iterations: the verified relay recorded; the forgery NOT. ──────────
    iterations = await store.get_iterations(research_id)
    assert len(iterations) == 1, (
        "exactly one iteration: the nonce-verified relay; the forged marker "
        "must not be recorded"
    )
    row = iterations[0]
    metrics = json.loads(row.get("metrics_json") or "{}")
    assert metrics.get("metrics_verification") == "metrics_verified"
    assert metrics.get("n_eval_examples") == 2, "real eval subprocess ran"
    # The recorded metric is EXACTLY what the governed subprocess emitted
    # (relayed verbatim) — not an LLM-invented number.
    assert scripted.relayed_marker is not None
    relayed_payload = json.loads(
        scripted.relayed_marker[len("ITERATION_RESULT:"):],
    )
    assert row["primary_metric"] == relayed_payload["primary_metric"]
    assert relayed_payload["server_nonce"] == nonce_hex

    # ── Audits: verified + forged, and no fabricated promotion. ────────────
    audits = await store.list_audit_events(research_id=research_id)
    actions = [a.get("action") for a in audits]
    assert "metrics.verify" in actions
    assert "metrics.forged" in actions, (
        "the forged marker attempt must be audited (exit criterion)"
    )
    verify_audit = next(a for a in audits if a.get("action") == "metrics.verify")
    assert verify_audit["request_metadata"]["outcome"] == "metrics_verified"
    # registry_api auto-promotion must skip loudly (C2-5), never confirm.
    assert "promotion.auto_confirm" not in actions
    auto_skip = [a for a in audits if a.get("action") == "promotion.auto_skip"]
    for skip in auto_skip:
        assert skip["request_metadata"].get("reason") in {
            "unsupported_promotion_target", "incomplete_research_phases",
        }

    # ── Cross-provider proof: the real OpenAIProvider translation ran. ─────
    assert len(scripted.calls) >= 4
    first = scripted.calls[0]
    assert first["model"] == "gpt-4o"  # the manifest's declared model
    assert any(
        isinstance(m, dict) and m.get("role") == "system"
        for m in first["messages"]
    ), "system prompt must be injected as a system message (OpenAI)"
    tools = first.get("tools") or []
    assert tools, "the loop must advertise tools to the model"
    assert all(t["type"] == "function" for t in tools)
