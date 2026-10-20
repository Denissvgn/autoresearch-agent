"""Parameter-to-work binding contract: traceability and fixed-argument enforcement.

Submitted (nondefault) values trace from the resolved skill_params into the
rendered commands, the resolved execution request, and the actual evaluator
behavior for every bundled skill. Operator-fixed arguments (demo, dataset,
scorer, bound parameter flags) cannot be changed or dropped by model-authored
argv, duplicate/alias override attempts are rejected, live and demo render
with identical bound values, and no core branch keyed on a skill name remains.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from src.core.execution_request import resolve_execution_request
from src.core.skill_loader import load_skill_manifest
from src.core.skill_manifest import ParameterBindings, ResearchSkillManifest
from src.core.skill_runtime import ManifestSkillRuntime

REPO_ROOT = Path(__file__).resolve().parents[1]


def _runtime(skill: str) -> ManifestSkillRuntime:
    return ManifestSkillRuntime(
        load_skill_manifest(REPO_ROOT / "skills" / skill / "SKILL.yaml"), MagicMock())


def _config(skill: str, **params: Any):
    return types.SimpleNamespace(
        skill_params=params, workspace_path="/ws",
        subject_id="s", variant="v", instrument="i", timeframe="t",
    )


NONDEFAULT: dict[str, dict[str, Any]] = {
    "db-config-tuning": {"target_latency_ms": 25, "bench_duration_s": 90},
    "code-refactor": {"target_file": "custom_target.py"},
    "prompt-engineering": {
        "eval_set": "my_set.jsonl", "scorer_url": "https://scorer.invalid/e",
    },
}


@pytest.mark.parametrize("skill", sorted(NONDEFAULT))
def test_nondefault_values_trace_into_rendered_commands(skill: str) -> None:
    """API-submitted values are visible in both rendered commands."""
    runtime = _runtime(skill)
    config = _config(skill, **NONDEFAULT[skill])
    live = runtime.experiment_command(config)
    demo = runtime.demo_experiment_command(config)
    for command in (live, demo):
        argv = shlex.split(command)
        for flag, value in runtime.bound_arguments(config).items():
            assert flag in argv, (skill, flag, command)
            assert argv[argv.index(flag) + 1] == value, (skill, flag, command)


@pytest.mark.parametrize("skill", sorted(NONDEFAULT))
def test_live_and_demo_binding_parity(skill: str) -> None:
    """Live and demo commands carry identical bound flag values."""
    runtime = _runtime(skill)
    config = _config(skill, **NONDEFAULT[skill])

    def bound_map(command: str) -> dict[str, str]:
        argv = shlex.split(command)
        found = {}
        for flag in runtime.bound_arguments(config):
            found[flag] = argv[argv.index(flag) + 1]
        return found

    assert bound_map(runtime.experiment_command(config)) == bound_map(
        runtime.demo_experiment_command(config)
    )


def test_no_core_branch_on_skill_name() -> None:
    """Bundled-skill differences live in manifest bindings, not core branches."""
    offenders = []
    for path in (REPO_ROOT / "src" / "core").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ('skill_id == "prompt-engineering"', 'skill_id != "prompt-engineering"'):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == []


def test_bindings_must_reference_declared_parameters() -> None:
    with pytest.raises(ValueError):
        ParameterBindings(fixed_flags={"no-dashes": "x"})
    doc = yaml.safe_load(
        (REPO_ROOT / "skills" / "db-config-tuning" / "SKILL.yaml").read_text(encoding="utf-8")
    )
    doc["parameter_bindings"]["evaluator_flags"]["undeclared"] = "--x"
    with pytest.raises(ValueError):
        ResearchSkillManifest.model_validate(doc)


# --- enforcement: model-authored argv cannot change operator-fixed args -----


def _resolve_fixture(tmp_path: Path, bound: dict[str, str]):
    ws = tmp_path / "workspace"
    session = ws / "runs" / "x"
    session.mkdir(parents=True)
    (ws / ".venv" / "bin").mkdir(parents=True)
    (ws / ".venv" / "bin" / "python").symlink_to(sys.executable)
    script = ws / "eval" / "run.py"
    script.parent.mkdir()
    script.write_text("print(1)\n", encoding="utf-8")
    extension = {
        "allowed_scripts": {"eval/run.py"},
        "script_paths": {"eval/run.py": str(script)},
        "script_digests": {
            "eval/run.py": hashlib.sha256(script.read_bytes()).hexdigest()
        },
        "config_flag": "--config",
        "bound_arguments": dict(bound),
    }
    return str(ws), str(session), extension


def _resolve(ws: str, session: str, ext: dict, command: str):
    return resolve_execution_request(
        command, workspace_root=ws, session_workspace=session,
        policy_extension=ext, timeout_s=60,
    )


BOUND = {
    "--target-latency-ms": "25",
    "--bench-duration-s": "90",
    "--demo": "false",
    "--scorer-url": "https://scorer.invalid/e",
}


def test_model_cannot_change_operator_fixed_args(tmp_path: Path) -> None:
    ws, session, ext = _resolve_fixture(tmp_path, BOUND)
    attempts = [
        ".venv/bin/python eval/run.py --config db_config.yaml --target-latency-ms 99",
        ".venv/bin/python eval/run.py --config db_config.yaml --demo true",
        ".venv/bin/python eval/run.py --config db_config.yaml --scorer-url https://evil.invalid/e",
        ".venv/bin/python eval/run.py --config db_config.yaml --bench-duration-s 99999",
        # Bare spelling of a bound flag cannot drop its operator-fixed value.
        ".venv/bin/python eval/run.py --config db_config.yaml --target-latency-ms 25 "
        "--bench-duration-s 90 --scorer-url https://scorer.invalid/e --demo",
    ]
    for command in attempts:
        request, reason = _resolve(ws, session, ext, command)
        assert request is None, command
        assert "operator-fixed argument" in reason, reason


def test_duplicate_and_alias_override_attempts_rejected(tmp_path: Path) -> None:
    ws, session, ext = _resolve_fixture(tmp_path, BOUND)
    attempts = [
        # Duplicate spellings of a bound flag.
        ".venv/bin/python eval/run.py --config db_config.yaml --target-latency-ms 25 "
        "--target-latency-ms 25 --bench-duration-s 90 --demo false --scorer-url https://scorer.invalid/e",
        # Alias spelling trying to smuggle a second value.
        ".venv/bin/python eval/run.py --config db_config.yaml --target-latency-ms=25 "
        "--target-latency-ms=99 --bench-duration-s 90 --demo false --scorer-url https://scorer.invalid/e",
    ]
    for command in attempts:
        request, reason = _resolve(ws, session, ext, command)
        assert request is None, command
        assert reason, command


def test_missing_bound_args_are_supplied_in_the_request(tmp_path: Path) -> None:
    """Dropping a bound flag does not unbind it: the request carries it."""
    ws, session, ext = _resolve_fixture(tmp_path, BOUND)
    request, reason = _resolve(
        ws, session, ext,
        ".venv/bin/python eval/run.py --config db_config.yaml",
    )
    assert reason is None, reason
    argv = list(request.argv)
    for flag, value in BOUND.items():
        assert flag in argv
        assert argv[argv.index(flag) + 1] == value
    # And a model supplying the identical values resolves to the same argv.
    request2, reason2 = _resolve(
        ws, session, ext,
        ".venv/bin/python eval/run.py --config db_config.yaml "
        "--target-latency-ms 25 --bench-duration-s 90 --demo false "
        "--scorer-url https://scorer.invalid/e",
    )
    assert reason2 is None, reason2
    assert request2.argv == request.argv


# --- actual evaluator behavior follows the nondefault values ---------------


def test_evaluator_behavior_follows_nondefault_values(tmp_path: Path) -> None:
    """The DB bench reports the submitted duration and gates on the submitted
    latency target (the hard-coded-value reproduction)."""
    session = tmp_path / "ws"
    session.mkdir()
    (session / "db_config.yaml").write_text("max_conn: 100\n", encoding="utf-8")
    script = REPO_ROOT / "skills" / "db-config-tuning" / "eval" / "run.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--config", "db_config.yaml",
         "--target-latency-ms", "25", "--bench-duration-s", "90"],
        cwd=session, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.split("ITERATION_RESULT: ", 1)[1])
    assert result["bench_duration_s"] == 90
    assert result["target_latency_ms"] == 25
    # The gate follows the submitted target: p99 (37.5) <= 25*3 but not 10*3.
    assert result["p99_within_slo"] is True
    control = subprocess.run(
        [sys.executable, str(script), "--config", "db_config.yaml",
         "--target-latency-ms", "10", "--bench-duration-s", "60"],
        cwd=session, capture_output=True, text=True, timeout=60,
    )
    control_result = json.loads(control.stdout.split("ITERATION_RESULT: ", 1)[1])
    assert control_result["p99_within_slo"] is False


def test_code_skill_uses_requested_candidate_source(tmp_path: Path) -> None:
    """The code skill initializes and evaluates the requested target file."""
    import asyncio

    from src.core.plugin_runner import PluginCaps, PluginRunner

    session = tmp_path / "ws"
    session.mkdir()
    result = asyncio.run(PluginRunner().run(
        skill_dir=REPO_ROOT / "skills" / "code-refactor",
        plugin="bootstrap.py", kind="bootstrap",
        input_json={
            "workspace": str(session), "mode": "live",
            "skill_params": {"target_file": "custom_target.py"},
        },
        caps=PluginCaps(fs_write="workspace", timeout_s=30.0), workspace=session,
    ))
    assert result.ok, result.error
    assert (session / "custom_target.py").is_file()
    assert not (session / "refactor_target.py").exists()
    eval_script = REPO_ROOT / "skills" / "code-refactor" / "eval" / "run.py"
    proc = subprocess.run(
        [sys.executable, str(eval_script),
         "--target", "custom_target.py", "--tests", "tests_target.jsonl"],
        cwd=session, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"status": "completed"' in proc.stdout


def test_command_template_placeholders_are_validated_at_load() -> None:
    doc = yaml.safe_load(
        (REPO_ROOT / "skills" / "db-config-tuning" / "SKILL.yaml").read_text(encoding="utf-8")
    )
    doc["prompt"]["experiment_command"] = "run --bogus {unknown_token}"
    with pytest.raises(ValueError):
        ResearchSkillManifest.model_validate(doc)
    doc["prompt"]["experiment_command"] = "run"
    doc["parameter_bindings"]["fixed_flags"] = {"--x": "{unknown_token}"}
    with pytest.raises(ValueError):
        ResearchSkillManifest.model_validate(doc)
