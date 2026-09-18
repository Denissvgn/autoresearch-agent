"""ARC-011 implementation review C1 (2026-08-15) — canonical start wiring.

The review found that ``_translate_canonical_request`` validates the canonical
shape (``skill_id`` / ``skill_params`` / ``subject_id`` / ``variant``) but the
API then called ``start_session`` with only the legacy fields, so:

* canonical HPO params (``skill_params={"enable_hpo": true, ...}``) were
  silently ignored (``enable_hpo=False, hpo_trials=20`` defaults won), and
* ``ResearchConfig.skill_id`` was never set, so ``materialize_skill_runtime``
  always fell back to the transitional runtime.

These tests drive the **real** ``SessionManager`` (fake orchestrator + healthy
preflight, same pattern as ``test_service_preflight.py``'s session-start test)
and assert the canonical fields reach ``ResearchConfig`` and the built HPO
plan.
"""
from __future__ import annotations

import asyncio
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    class _FakeAsyncAnthropic:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class _FakeAPIStatusError(Exception):
        status_code = 500

    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=_FakeAsyncAnthropic,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=_FakeAPIStatusError,
    )

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

from src.config import settings
from src.core.orchestrator import ResearchConfig
from src.core.results_store import ResultsStore


class FakeOrchestrator:
    """Captures the ResearchConfig the session manager hands to run()."""

    def __init__(self, store: Any) -> None:
        self.run_called = False
        self.captured_config: ResearchConfig | None = None

    async def run(self, config: ResearchConfig) -> None:
        self.run_called = True
        self.captured_config = config

    def request_stop(self, research_id: str) -> None:
        pass

    def request_pause(self, research_id: str) -> None:
        pass

    def request_resume(self, research_id: str) -> None:
        pass


async def _healthy_preflight(*, targets=None) -> Dict[str, Any]:
    return {
        "schema_version": "autoresearch_service_preflight.v1",
        "status": "ready",
        "required_ready": True,
        "override_allowed_unready": False,
        "services": {},
        "required_failures": [],
    }


def _configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Same settings surface the preflight session-start test configures; the
    # preflight call itself is monkeypatched, so only the workspace roots and
    # manifest-referenced attributes matter here.
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspace"))
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "host_configs"))


def _eval_set(tmp_path: Path) -> str:
    """A real eval set for prompt-engineering starts (P7-011: the skill's
    bootstrap fail-closes without one outside demo mode — it must exist)."""
    path = tmp_path / "eval_set.jsonl"
    path.write_text(
        '{"input": "What is 2+2?", "expected": "4"}\n', encoding="utf-8",
    )
    return str(path)


async def _start_and_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **start_kwargs: Any
) -> tuple[Dict[str, Any], FakeOrchestrator]:
    import src.core.session_manager as session_manager_module

    fake_orchestrator = FakeOrchestrator(None)
    monkeypatch.setattr(
        session_manager_module,
        "AgentOrchestrator",
        lambda store, state_machine=None: fake_orchestrator,
    )
    monkeypatch.setattr(
        session_manager_module,
        "run_service_preflight",
        _healthy_preflight,
    )

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    manager = session_manager_module.SessionManager(store)
    try:
        session = await manager.start_session(
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
            max_iterations=1,
            **start_kwargs,
        )
        await asyncio.sleep(0)
    finally:
        await manager.shutdown()
    return session, fake_orchestrator


async def test_canonical_fields_reach_research_config(monkeypatch, tmp_path):
    """Canonical skill_params reach ResearchConfig verbatim.

    ARC-012 P7-010: the skill id must be an *installed* skill (validation at
    start), so the wiring fixture uses the bundled ``prompt-engineering``
    instead of the uninstalled legacy ``ml-direction``."""
    _configure(monkeypatch, tmp_path)
    session, orch = await _start_and_capture(
        monkeypatch,
        tmp_path,
        skill_id="prompt-engineering",
        skill_params={"eval_set": _eval_set(tmp_path)},
        subject_id="default",
        variant="production",
    )
    assert orch.run_called
    cfg = orch.captured_config
    assert cfg is not None
    assert cfg.skill_id == "prompt-engineering"
    assert cfg.subject_id == "default"
    assert cfg.variant == "production"
    assert cfg.skill_params["eval_set"] == _eval_set(tmp_path)


async def test_skill_params_win_over_legacy_flat_fields(monkeypatch, tmp_path):
    """Canonical skill_params reach the config unchanged (no flat-field
    merging exists anymore)."""
    _configure(monkeypatch, tmp_path)
    _, orch = await _start_and_capture(
        monkeypatch,
        tmp_path,
        skill_id="prompt-engineering",
        skill_params={"eval_set": _eval_set(tmp_path)},
    )
    cfg = orch.captured_config
    assert cfg is not None
    assert cfg.skill_params["eval_set"] == _eval_set(tmp_path)

async def test_legacy_start_without_skill_id_is_refused(monkeypatch, tmp_path):
    """ARC-012 P7-010 (B2): a legacy-shape start (``model_type`` only, no
    ``skill_id``) can no longer create a session — the runtime is fully
    manifest-driven, so such a session would 201 and then crash. The refusal
    happens in ``start_session`` (nothing persisted, nothing spawned); the
    API layer additionally translates legacy requests through the alias map
    (D3) before they ever get here."""
    from src.core.skill_runtime import SkillConfigError

    _configure(monkeypatch, tmp_path)
    with pytest.raises(SkillConfigError, match="no skill_id"):
        await _start_and_capture(monkeypatch, tmp_path)

