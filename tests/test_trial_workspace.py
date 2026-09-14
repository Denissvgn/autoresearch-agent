"""Per-workdir trial state tests (P2 — ``execution.concurrency`` prerequisite).

Covers the :mod:`src.core.trial_workspace` module (context, allocation,
staging with the server-dir ignore list, fail-open staging, trial-first
marker candidates, eligibility predicate), the ``cwd`` seam through
``_tool_bash`` into the governed runner, and the ``--config`` snapshot
resolution against a trial base dir.
"""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.agent_tools import _config_snapshot_path_from_command, _tool_bash
from src.core.command_runner import CommandRunResult
from src.core.trial_workspace import (
    TRIALS_DIRNAME,
    TrialContext,
    allocate_trial_dir,
    build_trial_context,
    is_trial_eligible_command,
    stage_trial_or_none,
    stage_trial_workspace,
    trial_marker_candidates,
)

_ALLOWED = ["eval/run.py", "bootstrap.py"]


# --- eligibility predicate -------------------------------------------------


def test_eligible_when_command_invokes_sanctioned_script():
    assert is_trial_eligible_command(
        ".venv/bin/python eval/run.py --config db_config.yaml", _ALLOWED
    )


def test_ineligible_for_bookkeeping_or_empty_commands():
    assert not is_trial_eligible_command(
        "cp db_config.yaml best_db_config.yaml", _ALLOWED
    )
    assert not is_trial_eligible_command("cat prompt.yaml", _ALLOWED)
    assert not is_trial_eligible_command("", _ALLOWED)
    assert not is_trial_eligible_command("anything", None)
    assert not is_trial_eligible_command(None, _ALLOWED)


# --- allocation & context --------------------------------------------------


def test_allocate_trial_dir_creates_and_is_idempotent(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    d1 = allocate_trial_dir(str(session), turn=2, seq=3)
    d2 = allocate_trial_dir(str(session), turn=2, seq=3)
    assert d1 == d2
    assert Path(d1).is_dir()
    assert Path(d1).parent.name == TRIALS_DIRNAME
    assert Path(d1).name == "turn-002-seq-03"


def test_trial_context_workdir_defaults_to_session_workspace():
    ctx = TrialContext(
        research_id="r", turn=1, seq=1, session_workspace="/ws", trial_dir=None
    )
    assert not ctx.is_trial
    assert ctx.workdir == "/ws"
    ctx2 = TrialContext(
        research_id="r", turn=1, seq=1, session_workspace="/ws",
        trial_dir="/ws/.trials/t",
    )
    assert ctx2.is_trial
    assert ctx2.workdir == "/ws/.trials/t"


# --- staging ---------------------------------------------------------------


def test_stage_trial_workspace_copies_state_and_ignores_server_dirs(tmp_path):
    session = tmp_path / "session"
    trial = tmp_path / "trial"
    session.mkdir()
    (session / "db_config.yaml").write_text("shared_buffers_mb: 128\n")
    (session / "eval_set.jsonl").write_text('{"input": "2+2?"}\n')
    (session / "command_logs").mkdir()
    (session / "server_snapshots").mkdir()
    (session / "__pycache__").mkdir()
    (session / "command_logs" / "turn_001_x.log").write_text("log")
    (session / "server_snapshots" / "snap.json").write_text("{}")
    (session / TRIALS_DIRNAME / "old").mkdir(parents=True)

    staged = stage_trial_workspace(str(session), str(trial))
    assert staged == 2  # only the two real files
    assert (trial / "db_config.yaml").read_text() == "shared_buffers_mb: 128\n"
    assert (trial / "eval_set.jsonl").exists()
    # Server-owned dirs and the trials tree are never staged.
    assert not (trial / "command_logs").exists()
    assert not (trial / "server_snapshots").exists()
    assert not (trial / "__pycache__").exists()
    assert not (trial / TRIALS_DIRNAME).exists()


def test_stage_trial_or_none_fails_open(monkeypatch, tmp_path):
    import src.core.trial_workspace as tw

    def _boom(session_workspace, trial_dir):
        raise OSError("disk full")

    monkeypatch.setattr(tw, "stage_trial_workspace", _boom)
    assert stage_trial_or_none(str(tmp_path), str(tmp_path / "t")) is None


# --- marker candidates -----------------------------------------------------


def test_trial_marker_candidates_trial_first(tmp_path):
    session_paths = [
        Path("/ws/runs/skill/sub/var/bench_result.txt"),
        Path("/ws/runs/skill/sub/var/eval_result.json"),
    ]
    candidates = trial_marker_candidates(str(tmp_path), session_paths)
    assert candidates[0] == tmp_path / "bench_result.txt"
    assert candidates[1] == tmp_path / "eval_result.json"
    # Session paths remain as fallback after the trial copies.
    assert candidates[2:] == session_paths


# --- build_trial_context gating --------------------------------------------


def test_build_trial_context_default_concurrency_never_allocates(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "db_config.yaml").write_text("x: 1\n")
    ctx = build_trial_context(
        research_id="r", turn=1, seq=1, session_workspace=str(session),
        command=".venv/bin/python eval/run.py --config db_config.yaml",
        allowed_scripts=_ALLOWED, execution_concurrency=1,
    )
    assert not ctx.is_trial
    assert not (session / TRIALS_DIRNAME).exists()


def test_build_trial_context_eligible_command_allocates_and_stages(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "db_config.yaml").write_text("x: 1\n")
    ctx = build_trial_context(
        research_id="r", turn=1, seq=1, session_workspace=str(session),
        command=".venv/bin/python eval/run.py --config db_config.yaml",
        allowed_scripts=_ALLOWED, execution_concurrency=2,
    )
    assert ctx.is_trial
    staged_cfg = Path(ctx.trial_dir) / "db_config.yaml"
    assert staged_cfg.read_text() == "x: 1\n"


def test_build_trial_context_bookkeeping_command_not_trialed(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    ctx = build_trial_context(
        research_id="r", turn=1, seq=2, session_workspace=str(session),
        command="cp db_config.yaml best_db_config.yaml",
        allowed_scripts=_ALLOWED, execution_concurrency=3,
    )
    assert not ctx.is_trial


# --- cwd seam ---------------------------------------------------------------


class _CapturingRunner:
    captured: dict = {}

    def __init__(self, **_: object) -> None:
        pass

    def run(self, command, *, timeout_s, output_callback=None,
            proc_registry=None, research_id=None, extra_env=None, cwd=None):
        type(self).captured = {"cwd": cwd, "timeout_s": timeout_s}
        decision = MagicMock()
        decision.allowed = True
        return CommandRunResult(output="ok", decision=decision)


def test_tool_bash_threads_cwd_to_governed_runner():
    _CapturingRunner.captured = {}
    with patch("src.core.agent_tools.GovernedCommandRunner", _CapturingRunner):
        _tool_bash(
            {"command": "echo hi", "timeout_s": 30}, "/ws",
            command_deadline_mono=None,
        )
        # Default (no trial) → cwd None → runner uses the session workspace.
        assert _CapturingRunner.captured["cwd"] is None
        _tool_bash(
            {"command": "echo hi", "timeout_s": 30}, "/ws",
            command_deadline_mono=None, cwd="/ws/.trials/turn-001-seq-01",
        )
        assert _CapturingRunner.captured["cwd"] == "/ws/.trials/turn-001-seq-01"


# --- snapshot resolution against the trial base dir -------------------------


def test_config_snapshot_resolves_against_base_dir(tmp_path):
    session = tmp_path / "session"
    trial = tmp_path / "session" / ".trials" / "t1"
    session.mkdir()
    trial.mkdir(parents=True)
    (session / "db_config.yaml").write_text("session copy\n")
    (trial / "db_config.yaml").write_text("trial copy\n")

    cmd = ".venv/bin/python eval/run.py --config db_config.yaml"
    # Default: resolves against the session workspace.
    assert _config_snapshot_path_from_command(
        cmd, str(tmp_path), str(session)
    ) == str(session / "db_config.yaml")
    # Trial: resolves against the staged trial copy.
    assert _config_snapshot_path_from_command(
        cmd, str(tmp_path), str(session), base_dir=str(trial)
    ) == str(trial / "db_config.yaml")


def test_config_snapshot_base_dir_outside_session_returns_none(tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "db_config.yaml").write_text("nope\n")
    session = tmp_path / "session"
    session.mkdir()
    cmd = ".venv/bin/python eval/run.py --config db_config.yaml"
    # Containment stays anchored to the session workspace — a base dir
    # outside it can never steer the snapshot out of the session tree.
    assert _config_snapshot_path_from_command(
        cmd, str(tmp_path), str(session), base_dir=str(outside)
    ) is None
