"""Run workspace isolation: unique roots and retained parent references.

Fresh runs of the same skill/subject/variant get distinct run roots, so a
later run can never replace or archive an older run's artifacts; continuations
reuse their parent's root deliberately and carry a content-addressed parent
snapshot as the retained reference.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.run_artifacts import ArtifactStore
from src.core.session_manager import SessionManager, _derive_workspace_path
from src.core.skill_paths import session_workspace_path


class _Workspace:
    session_path_template = "runs/{skill_id}/{subject_id}/{variant}"


class _Skill:
    workspace = _Workspace()


def test_same_subject_runs_get_distinct_run_roots():
    first = _derive_workspace_path(
        skill_id="db-config-tuning",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="",
        research_id="res_aaa",
    )
    second = _derive_workspace_path(
        skill_id="db-config-tuning",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="",
        research_id="res_bbb",
    )
    assert first != second
    # The logical subject/variant identity is retained as path metadata.
    assert first.endswith("runs/db-config-tuning/DOGE_USDT/15m/res_aaa")
    assert second.endswith("runs/db-config-tuning/DOGE_USDT/15m/res_bbb")
    # The declared template without a research id keeps its legacy shape.
    assert session_workspace_path(
        _Skill(), skill_id="db-config-tuning",
        subject_id="DOGE_USDT", variant="15m",
    ) == "runs/db-config-tuning/DOGE_USDT/15m"


def test_fresh_run_never_archives_an_older_runs_workspace(tmp_path, monkeypatch):
    from src.core import session_manager as sm_module

    monkeypatch.setattr(sm_module.settings, "workspace_root", str(tmp_path))
    manager = object.__new__(SessionManager)

    older = _derive_workspace_path(
        skill_id="db-config-tuning",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="",
        research_id="res_old",
    )
    older_root = Path(older)
    older_root.mkdir(parents=True)
    (older_root / "best_candidate.yaml").write_text(
        "metric: 9\n", encoding="utf-8",
    )

    newer = _derive_workspace_path(
        skill_id="db-config-tuning",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="",
        research_id="res_new",
    )
    newer_root = Path(newer)
    # The create flow archives only its own (unique) root: a fresh run's
    # preparation cannot touch the older run's historical workspace.
    import asyncio

    asyncio.run(manager._archive_stale_workspace(str(newer_root)))
    assert (older_root / "best_candidate.yaml").read_text(
        encoding="utf-8",
    ) == "metric: 9\n"
    archive_dir = older_root.parent / "archive"
    if archive_dir.exists():
        assert not list(archive_dir.glob("res_old.*"))

    # Re-preparing the SAME run root archives only that root's contents.
    asyncio.run(manager._archive_stale_workspace(str(older_root)))
    assert not older_root.exists()
    archived = list((older_root.parent / "archive").glob("res_old.*"))
    assert len(archived) == 1
    assert (archived[0] / "best_candidate.yaml").exists()


def test_continuation_records_a_retained_parent_reference(tmp_path, monkeypatch):
    from src.core import session_manager as sm_module

    monkeypatch.setattr(sm_module.settings, "workspace_root", str(tmp_path))
    manager = object.__new__(SessionManager)

    parent_ws = tmp_path / "parent_ws"
    parent_ws.mkdir()
    (parent_ws / "best_candidate.yaml").write_text("metric: 9\n", encoding="utf-8")
    (parent_ws / "eval_result.json").write_text("{}", encoding="utf-8")
    (parent_ws / "scratch.tmp").write_text("noise", encoding="utf-8")

    snapshot = manager._capture_parent_snapshot(str(parent_ws))
    assert snapshot is not None
    assert snapshot["file_count"] == 2

    # The retained reference resolves to exactly the parent's candidate and
    # result files — never its scratch state.
    store = ArtifactStore(tmp_path / ".artifacts")
    assert store.verify_bundle(snapshot["bundle_digest"]) is True
    dest = tmp_path / "restored"
    written = store.reconstruct(snapshot["bundle_digest"], dest)
    assert set(written) == {"best_candidate.yaml", "eval_result.json"}
    assert (dest / "best_candidate.yaml").read_text(encoding="utf-8") == (
        "metric: 9\n"
    )


def test_parent_snapshot_lives_in_the_hashed_run_spec():
    from src.core.research_manifest import build_research_manifest
    from src.core.run_spec import verify_run_spec

    snapshot = {
        "bundle_digest": "0" * 64,
        "file_count": 2,
        "source_research_id": "res_parent",
    }
    manifest = build_research_manifest(
        research_id="res_child",
        instrument="conformance-subject",
        timeframe="default",
        model_type="",
        tag="child",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        timeout_s=60,
        focus_hint=None,
        skill_id="db-config-tuning",
        parent_snapshot=snapshot,
    )
    assert manifest.run_spec is not None
    assert manifest.run_spec["parent_snapshot"] == snapshot
    # The retained reference is inside the hashed spec: tampering is visible.
    assert verify_run_spec(manifest.run_spec) is True
    tampered = dict(manifest.run_spec)
    tampered["parent_snapshot"] = {"bundle_digest": "1" * 64, "file_count": 0}
    assert verify_run_spec(tampered) is False
