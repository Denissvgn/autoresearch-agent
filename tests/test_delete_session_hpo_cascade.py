"""Regression: delete_session must remove ALL research_id children — including
hpo_studies — before the parent row. Previously hpo_studies was omitted, so RL/
structured-HPO sessions (which create study rows) hit SQLite
'FOREIGN KEY constraint failed' and could never be deleted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.core.results_store import ResultsStore


async def _make_session(store: ResultsStore, sid: str, tmp_path: Path):
    await store.create_session(
        session_id=sid,
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="rl",
        tag="hpo",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        focus_hint=None,
        workspace_path=str(tmp_path / "runs" / sid),
        manifest_json=json.dumps({"research_id": sid}),
        manifest_path=str(tmp_path / "runs" / sid / "research_manifest.json"),
        manifest_hash="h",
    )


@pytest.mark.asyncio
async def test_delete_session_with_hpo_study_succeeds(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    await _make_session(store, "res_hpo", tmp_path)

    # The case that used to fail: a session with an hpo_studies child row.
    await store.record_hpo_study_plan(
        research_id="res_hpo",
        study_id="hpo_res_hpo_rl",
        max_trials=10,
        search_space_json="{}",
        budget_json="{}",
        timeout_s=600,
        quick_mode=False,
    )
    assert len(await store.get_hpo_studies("res_hpo")) == 1

    ok = await store.delete_session("res_hpo")  # previously raised IntegrityError
    assert ok is True
    assert await store.get_session("res_hpo") is None
    assert await store.get_hpo_studies("res_hpo") == []


@pytest.mark.asyncio
async def test_delete_missing_session_returns_false(tmp_path: Path):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    assert await store.delete_session("nope") is False
