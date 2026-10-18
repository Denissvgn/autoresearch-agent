"""Run restore: pinned-contract reconstruction and explicit recovery states.

A restore must reproduce the recorded scorer, dataset, model configuration,
fixed parameters, limits, and objective policy exactly. Anything that cannot
satisfy the pinned contract — a missing artifact, an unbound credential, a
changed registry, a tampered spec — produces an actionable recovery state,
never a fresh run disguised as a resume.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from src.core.research_manifest import build_research_manifest
from src.core.results_store import ResultsStore
from src.core.run_restore import (
    BLOCKER_MANIFEST_UNREADABLE,
    BLOCKER_MISSING_ARTIFACT,
    BLOCKER_MISSING_CREDENTIAL,
    BLOCKER_SKILL_DRIFT,
    BLOCKER_SPEC_TAMPERED,
    RECOVERY_KINDS,
    RecoveryRequired,
    assess_recovery,
    raise_unless_ready,
    restore_contract,
)
from src.core.run_spec import build_run_spec
from src.core.session_manager import SessionManager

_MANAGERS: list = []


@pytest.fixture(autouse=True)
def _stop_manager_background_tasks():
    yield
    for manager in _MANAGERS:
        task = getattr(manager, "_lease_task", None)
        if task is not None:
            task.cancel()
    _MANAGERS.clear()


def _pinned_spec(*, skill_version=None, params=None, parent_snapshot=None) -> dict:
    from src.core.run_spec import skill_package_dir
    from src.core.skill_registry import default_registry

    if skill_version is None:
        current = default_registry.get("prompt-engineering")
        skill_version = getattr(current, "version", None)
    return build_run_spec(
        skill_params=params
        or {
            "scorer_endpoint": "https://scorer.internal/v1",
            "eval_set": "eval/set.jsonl",
            "knob": 0.42,
            "api_token": "secret-value",
        },
        param_schema=None,
        skill_id="prompt-engineering",
        skill_version=skill_version,
        skill_dir=skill_package_dir("prompt-engineering"),
        objective_policy={"metric": "auc", "direction": "maximize"},
        policy={"approval_required": False},
        effective_config={
            "model_type": "trend",
            "max_iterations": 7,
            "max_budget_usd": 23.5,
        },
        parent_snapshot=parent_snapshot,
    )


def test_contract_extraction_reports_pinned_values():
    spec = _pinned_spec()
    contract = restore_contract(spec)
    assert contract["skill_params"]["scorer_endpoint"] == (
        "https://scorer.internal/v1"
    )
    assert contract["skill_params"]["knob"] == 0.42
    assert contract["objective_policy"] == {
        "metric": "auc",
        "direction": "maximize",
    }
    assert contract["effective_config"]["max_budget_usd"] == 23.5


def test_pause_and_harness_resume_never_block_on_contract():
    for kind in ("pause_resume", "harness_resume"):
        report = assess_recovery(kind=kind, session_id="res_1", run_spec={})
        assert report.ready is True
        assert report.blockers == []
        assert report.kind == kind
    assert set(RECOVERY_KINDS) == {
        "pause_resume",
        "harness_resume",
        "continuation",
        "restart_recovery",
    }


class _FakeArtifactStore:
    def __init__(self, present):
        self._present = set(present)

    def verify_bundle(self, digest: str) -> bool:
        return digest in self._present


def test_missing_artifact_is_an_actionable_blocker():
    report = assess_recovery(
        kind="restart_recovery",
        session_id="res_1",
        run_spec=_pinned_spec(),
        env={"SKILL_PARAM_API_TOKEN": "bound"},
        artifact_digests=["bundle-a", "bundle-b"],
        artifact_store=_FakeArtifactStore({"bundle-a"}),
    )
    assert report.ready is False
    codes = [b.code for b in report.blockers]
    assert codes == [BLOCKER_MISSING_ARTIFACT]
    assert "bundle-b" in report.blockers[0].detail
    assert "not substitute a fresh run" in report.blockers[0].remediation
    with pytest.raises(RecoveryRequired) as excinfo:
        raise_unless_ready(report)
    assert "missing_artifact" in str(excinfo.value)
    assert excinfo.value.report is report


def test_missing_credential_names_the_binding():
    report = assess_recovery(
        kind="continuation",
        session_id="res_1",
        run_spec=_pinned_spec(),
        env={},
    )
    assert report.ready is False
    codes = [b.code for b in report.blockers]
    assert codes == [BLOCKER_MISSING_CREDENTIAL]
    assert "api_token" in report.blockers[0].detail
    assert "SKILL_PARAM_API_TOKEN" in report.blockers[0].detail
    assert report.blockers[0].remediation


def test_skill_drift_is_an_actionable_blocker():
    report = assess_recovery(
        kind="continuation",
        session_id="res_1",
        run_spec=_pinned_spec(),
        env={},
        current_skill_version="2.0.0",
    )
    codes = [b.code for b in report.blockers]
    assert BLOCKER_SKILL_DRIFT in codes
    drift = [b for b in report.blockers if b.code == BLOCKER_SKILL_DRIFT][0]
    assert "migrate explicitly" in drift.remediation


async def _create_parent(
    store: ResultsStore,
    *,
    session_id: str,
    workspace: Path,
    run_spec: dict = None,
    raw_manifest: dict = None,
) -> None:
    if raw_manifest is not None:
        manifest_json = json.dumps(raw_manifest)
    else:
        manifest = build_research_manifest(
            research_id=session_id,
            instrument="default",
            timeframe="production",
            model_type="",
            tag=session_id,
            quick_mode=True,
            max_iterations=7,
            max_budget_usd=23.5,
            timeout_s=0,
            focus_hint=None,
            skill_id="prompt-engineering",
            skill_params={},
        )
        if run_spec is not None:
            manifest.run_spec = run_spec
        manifest_json = manifest.model_dump_json()
    await store.create_session(
        session_id=session_id,
        instrument="default",
        timeframe="production",
        model_type="",
        skill_id="prompt-engineering",
        subject_id="default",
        variant="production",
        tag=session_id,
        quick_mode=True,
        max_iterations=7,
        max_budget_usd=23.5,
        focus_hint=None,
        workspace_path=str(workspace),
        manifest_path=str(workspace / "research_manifest.json"),
        manifest_json=manifest_json,
        manifest_hash="manifest-sha",
    )
    await store.update_session(session_id, status="resumable")


def _manager(store: ResultsStore) -> SessionManager:
    manager = SessionManager(store)
    _MANAGERS.append(manager)

    class FakeOrchestrator:
        async def run(self, config) -> None:
            await store.update_session(config.id, status="completed")

        def request_stop(self, research_id: str) -> None:
            pass

        def request_pause(self, research_id: str) -> None:
            pass

        def request_resume(self, research_id: str) -> None:
            pass

    manager._orchestrator = FakeOrchestrator()

    async def healthy_preflight(config):
        return {
            "schema_version": "autoresearch_service_preflight.v1",
            "status": "ready",
        }

    manager._run_preflight = healthy_preflight
    return manager


@pytest.mark.asyncio
async def test_restart_resume_reproduces_nondefault_contract(
    tmp_path: Path, monkeypatch
):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "parent"
    workspace.mkdir(parents=True)
    spec = _pinned_spec()
    await _create_parent(
        store,
        session_id="res_parent",
        workspace=workspace,
        run_spec=spec,
    )
    monkeypatch.setenv("SKILL_PARAM_API_TOKEN", "bound")
    manager = _manager(store)

    resumed = await manager.resume_interrupted_session(
        "res_parent", reason="restart"
    )

    child = await store.get_session(resumed["id"])
    child_manifest = json.loads(child["manifest_json"])
    child_spec = child_manifest["run_spec"]
    # scorer references and fixed parameters reproduce the pin exactly
    assert child_spec["skill_params"]["scorer_endpoint"] == (
        "https://scorer.internal/v1"
    )
    assert child_spec["skill_params"]["knob"] == 0.42
    assert child_spec["skill_params"]["eval_set"] == "eval/set.jsonl"
    # objective policy and model configuration are preserved
    assert child_spec["objective_policy"] == {
        "metric": "auc",
        "direction": "maximize",
    }
    assert child_spec["skill_id"] == spec["skill_id"]
    assert child_spec["skill_version"] == spec["skill_version"]
    assert child_spec["skill_params"] == spec["skill_params"]
    # limits inherit the parent's pinned values, never today's defaults
    assert child["max_budget_usd"] == 23.5
    assert child_spec["effective_config"]["max_budget_usd"] == 23.5
    # lineage: which recovery mode produced the child, and from where
    assert child_manifest["runtime"]["resumed_from"] == "res_parent"
    assert child_manifest["runtime"]["recovery_kind"] == "restart_recovery"
    assert child["resumed_from"] == "res_parent"


@pytest.mark.asyncio
async def test_changed_registry_requires_explicit_migration(
    tmp_path: Path, monkeypatch
):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "parent"
    workspace.mkdir(parents=True)
    await _create_parent(
        store,
        session_id="res_parent",
        workspace=workspace,
        run_spec=_pinned_spec(skill_version="0.0.1-stale"),
    )
    monkeypatch.setenv("SKILL_PARAM_API_TOKEN", "bound")
    manager = _manager(store)

    with pytest.raises(RecoveryRequired, match="migrate explicitly") as excinfo:
        await manager.resume_interrupted_session("res_parent", reason="restart")
    codes = [b["code"] for b in excinfo.value.report.as_dict()["blockers"]]
    assert "skill_drift" in codes
    # a blocked restore spawns nothing — it is not a fresh run disguised
    # as a resume
    rows = await store.list_sessions()
    assert [r for r in rows if r.get("resumed_from")] == []

    # the operator's explicit migration choice proceeds and preserves lineage
    child = await manager.continue_session("res_parent", allow_skill_drift=True)
    assert child["resumed_from"] == "res_parent"


@pytest.mark.asyncio
async def test_missing_credential_reference_is_actionable(
    tmp_path: Path, monkeypatch
):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "parent"
    workspace.mkdir(parents=True)
    await _create_parent(
        store,
        session_id="res_parent",
        workspace=workspace,
        run_spec=_pinned_spec(),
    )
    monkeypatch.delenv("SKILL_PARAM_API_TOKEN", raising=False)
    manager = _manager(store)

    with pytest.raises(RecoveryRequired, match="SKILL_PARAM_API_TOKEN"):
        await manager.continue_session("res_parent")
    rows = await store.list_sessions()
    assert [r for r in rows if r.get("resumed_from")] == []

    monkeypatch.setenv("SKILL_PARAM_API_TOKEN", "bound")
    child = await manager.continue_session("res_parent")
    assert child["resumed_from"] == "res_parent"


@pytest.mark.asyncio
async def test_unreadable_checkpoint_is_actionable(
    tmp_path: Path, monkeypatch
):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "parent"
    workspace.mkdir(parents=True)
    # a manifest that claims a pinned run spec but fails validation is an
    # unreadable checkpoint, never a legacy parent
    await _create_parent(
        store,
        session_id="res_parent",
        workspace=workspace,
        raw_manifest={
            "research_id": "res_parent",
            "run_spec": {"skill_params": {"knob": 1}},
        },
    )
    monkeypatch.setenv("SKILL_PARAM_API_TOKEN", "bound")
    manager = _manager(store)

    with pytest.raises(RecoveryRequired, match="manifest_unreadable"):
        await manager.resume_interrupted_session("res_parent", reason="restart")
    rows = await store.list_sessions()
    assert [r for r in rows if r.get("resumed_from")] == []


@pytest.mark.asyncio
async def test_duplicate_resume_is_refused(tmp_path: Path, monkeypatch):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "parent"
    workspace.mkdir(parents=True)
    await _create_parent(
        store,
        session_id="res_parent",
        workspace=workspace,
        run_spec=_pinned_spec(),
    )
    monkeypatch.setenv("SKILL_PARAM_API_TOKEN", "bound")
    manager = _manager(store)

    release = asyncio.Event()

    class BlockingOrchestrator:
        async def run(self, config) -> None:
            await store.update_session(config.id, status="running")
            await release.wait()
            await store.update_session(config.id, status="completed")

        def request_stop(self, research_id: str) -> None:
            pass

        def request_pause(self, research_id: str) -> None:
            pass

        def request_resume(self, research_id: str) -> None:
            pass

    manager._orchestrator = BlockingOrchestrator()
    first = await manager.resume_interrupted_session(
        "res_parent", reason="restart"
    )
    # the first recovery child is still live: a second resume is a double
    # trigger and must not spawn a divergent sibling
    with pytest.raises(RuntimeError, match="duplicate resume"):
        await manager.resume_interrupted_session("res_parent", reason="double")

    # once the child settles, a later recovery is legitimate
    release.set()
    for _ in range(100):
        row = await store.get_session(first["id"])
        if row and row["status"] in ("completed", "failed", "timed_out"):
            break
        await asyncio.sleep(0.02)

    class CompletingOrchestrator:
        async def run(self, config) -> None:
            await store.update_session(config.id, status="completed")

        def request_stop(self, research_id: str) -> None:
            pass

        def request_pause(self, research_id: str) -> None:
            pass

        def request_resume(self, research_id: str) -> None:
            pass

    manager._orchestrator = CompletingOrchestrator()
    second = await manager.resume_interrupted_session(
        "res_parent", reason="later recovery"
    )
    assert second["id"] != first["id"]
    assert second["resumed_from"] == "res_parent"


@pytest.mark.asyncio
async def test_pause_resume_stays_in_place(tmp_path: Path, monkeypatch):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "parent"
    workspace.mkdir(parents=True)
    await _create_parent(
        store,
        session_id="res_parent",
        workspace=workspace,
        run_spec=_pinned_spec(),
    )
    monkeypatch.setenv("SKILL_PARAM_API_TOKEN", "bound")
    manager = _manager(store)

    # pause_resume is in-place and owner-scoped: a foreign worker cannot
    # resume it and no new session row appears
    ok = await manager.resume_session("res_parent")
    assert ok is False
    rows = await store.list_sessions()
    assert [r for r in rows if r.get("resumed_from")] == []

    # continuation is the mode that creates a new session with lineage
    child = await manager.continue_session("res_parent")
    assert child["id"] != "res_parent"
    assert child["resumed_from"] == "res_parent"


@pytest.mark.asyncio
async def test_missing_snapshot_artifact_produces_recovery_state(
    tmp_path: Path, monkeypatch
):
    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    workspace = tmp_path / "runs" / "parent"
    workspace.mkdir(parents=True)
    await _create_parent(
        store,
        session_id="res_parent",
        workspace=workspace,
        run_spec=_pinned_spec(
            parent_snapshot={"digest": "b" * 64, "files": {}},
        ),
    )
    monkeypatch.setenv("SKILL_PARAM_API_TOKEN", "bound")
    manager = _manager(store)

    with pytest.raises(RecoveryRequired, match="missing_artifact") as excinfo:
        await manager.resume_interrupted_session("res_parent", reason="restart")
    codes = [b["code"] for b in excinfo.value.report.as_dict()["blockers"]]
    assert "missing_artifact" in codes
    rows = await store.list_sessions()
    assert [r for r in rows if r.get("resumed_from")] == []
