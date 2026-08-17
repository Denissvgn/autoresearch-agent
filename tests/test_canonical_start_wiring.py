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


async def _healthy_preflight(*, model_type: str) -> Dict[str, Any]:
    return {
        "schema_version": "autoresearch_service_preflight.v1",
        "status": "ready",
        "model_type": model_type,
        "required_ready": True,
        "override_allowed_unready": False,
        "services": {
            "mlflow_service": {
                "url": "http://mlflow-service:8000",
                "required": True,
                "status": "ready",
            }
        },
        "required_failures": [],
    }


def _configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Same settings surface the preflight session-start test configures; the
    # preflight call itself is monkeypatched, so only the workspace roots and
    # manifest-referenced attributes matter here.
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspace"))
    monkeypatch.setattr(settings, "mlflow_tracking_uri", "http://mlflow:5000")
    monkeypatch.setattr(settings, "mlflow_service_url", "http://mlflow-service:8000")
    monkeypatch.setattr(settings, "data_ingest_url", "http://data-ingest:8000")
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "host_configs"))


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
    """The exact scenario from the review: canonical skill_params must not be
    silently dropped (previously ran with enable_hpo=False, hpo_trials=20)."""
    _configure(monkeypatch, tmp_path)
    session, orch = await _start_and_capture(
        monkeypatch,
        tmp_path,
        skill_id="ml-direction",
        skill_params={"enable_hpo": True, "hpo_trials": 100},
        subject_id="DOGE_USDT",
        variant="15m",
    )
    assert orch.run_called
    cfg = orch.captured_config
    assert cfg is not None
    assert cfg.skill_id == "ml-direction"
    assert cfg.enable_hpo is True
    assert cfg.hpo_trials == 100
    assert cfg.subject_id == "DOGE_USDT"
    assert cfg.variant == "15m"
    assert cfg.skill_params["enable_hpo"] is True
    assert cfg.skill_params["hpo_trials"] == 100
    # The canonical HPO intent propagates past the config: the built HPO plan
    # (merged into the session manifest) is enabled, not "disabled".
    import json

    manifest = json.loads(session["manifest_json"])
    assert manifest["hpo"]["enabled"] is True


async def test_skill_params_win_over_legacy_flat_fields(monkeypatch, tmp_path):
    """Canonical wins when both shapes are present — including an explicit
    false / small value overriding a truthy legacy one."""
    _configure(monkeypatch, tmp_path)
    _, orch = await _start_and_capture(
        monkeypatch,
        tmp_path,
        enable_hpo=True,
        hpo_trials=200,
        skill_id="ml-direction",
        skill_params={"enable_hpo": False, "hpo_trials": 5},
    )
    cfg = orch.captured_config
    assert cfg is not None
    assert cfg.enable_hpo is False
    assert cfg.hpo_trials == 5


async def test_legacy_start_keeps_transitional_defaults(monkeypatch, tmp_path):
    """Back-compat: without canonical fields, skill_id stays empty (transitional
    runtime) and the flat legacy HPO knobs behave exactly as before."""
    _configure(monkeypatch, tmp_path)
    _, orch = await _start_and_capture(
        monkeypatch, tmp_path, enable_hpo=True, hpo_trials=50,
    )
    cfg = orch.captured_config
    assert cfg is not None
    assert cfg.skill_id == ""
    assert cfg.enable_hpo is True
    assert cfg.hpo_trials == 50
    # Flat fields mirror into skill_params per ResearchConfig.__post_init__.
    assert cfg.skill_params["enable_hpo"] is True
    assert cfg.skill_params["hpo_trials"] == 50
