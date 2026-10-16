"""One resolved execution request: policy/process parity regressions.

The execution request contract (F06): executable, typed argv, fixed
arguments, CWD, inputs, outputs, and timeout resolve once into one
immutable request that authorization, pre-run snapshots, sequential and
parallel execution, and result lookup all consume. Live and demo templates
route through the same resolver; shell-dependent templates and unsupported
executable bindings are rejected with migration diagnostics.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
import yaml

from src.core.agent_tools import (
    _config_snapshot_path_from_command,
    _execute_tool,
)
from src.core.command_policy import evaluate_command_policy
from src.core.command_runner import GovernedCommandRunner
from src.core.execution_request import (
    resolve_execution_request,
    template_migration_reason,
)
from src.core.result_artifact import enrich_marker_from_result_artifact
from src.core.skill_registry import SkillRegistry
from src.core.skill_runtime import ManifestSkillRuntime, SkillConfigError
from src.core.tool_access import build_tool_access_context

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_CONTENT = (
    "import pathlib, sys\n"
    "config_path = sys.argv[sys.argv.index('--config') + 1]\n"
    "text = pathlib.Path(config_path).read_text(encoding='utf-8')\n"
    "pathlib.Path('seen.txt').write_text(text, encoding='utf-8')\n"
)


def _workspace(tmp_path: Path) -> tuple[str, str]:
    workspace = tmp_path / "workspace"
    session = workspace / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    session.mkdir(parents=True)
    python_path = workspace / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    return str(workspace), str(session)


def _pin(tmp_path: Path, content: str = EVAL_CONTENT) -> dict:
    pkg = tmp_path / "pkg"
    script = pkg / "eval" / "run.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(content, encoding="utf-8")
    return {
        "allowed_scripts": {"eval/run.py"},
        "script_paths": {"eval/run.py": str(script)},
        "script_digests": {
            "eval/run.py": hashlib.sha256(content.encode("utf-8")).hexdigest()
        },
        "config_flag": "--config",
        "copyable_files": ["db_config.yaml", "my config.yaml"],
    }


def test_live_template_with_bare_config_path_executes_end_to_end(tmp_path: Path):
    """F06 reproduction: the declared live experiment command (bare config
    filename) used to pass policy and then die with ``No such file or
    directory``. The resolved request must hand the subprocess the exact
    config the session workspace holds."""
    manifest = yaml.safe_load(
        (REPO_ROOT / "skills" / "db-config-tuning" / "SKILL.yaml").read_text(
            encoding="utf-8"
        )
    )
    live_template = manifest["prompt"]["experiment_command"].strip()
    assert live_template.endswith("--target-latency-ms 10")

    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    (Path(session) / "db_config.yaml").write_text("max_conn: 7\n", encoding="utf-8")

    access = build_tool_access_context(session, workspace_root=workspace)
    result = _execute_tool(
        "bash",
        {"command": live_template},
        access,
        policy_extension=extension,
    )

    assert result.meta["returncode"] == 0, result.content
    assert (Path(session) / "seen.txt").read_text(encoding="utf-8") == (
        "max_conn: 7\n"
    )
    request = result.meta["execution_request"]
    assert request["config_path"] == str(Path(session) / "db_config.yaml")
    assert request["config_path"] in request["argv"]


def _resolve(command: str, workspace: str, session: str, extension: dict, workdir=None):
    decision = evaluate_command_policy(
        command,
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
        workdir=workdir,
    )
    return decision


def test_absolute_and_relative_inputs_resolve_to_one_path(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    config = Path(session) / "db_config.yaml"
    config.write_text("x: 1\n", encoding="utf-8")
    expected = str(config.resolve())

    for spelling in (
        ".venv/bin/python eval/run.py --config db_config.yaml",
        ".venv/bin/python eval/run.py --config ./db_config.yaml",
        f".venv/bin/python eval/run.py --config {config}",
    ):
        decision = _resolve(spelling, workspace, session, extension)
        assert decision.allowed, decision.reason
        assert decision.request.config_path == expected
        assert expected in decision.request.argv


def test_paths_with_spaces_resolve_as_single_arguments(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    config = Path(session) / "my config.yaml"
    config.write_text("x: 2\n", encoding="utf-8")

    decision = _resolve(
        '.venv/bin/python eval/run.py --config "my config.yaml"',
        workspace, session, extension,
    )

    assert decision.allowed, decision.reason
    resolved = str(config.resolve())
    assert decision.request.config_path == resolved
    assert resolved in decision.request.argv
    assert decision.request.argv.count(resolved) == 1


def test_duplicate_flags_cannot_override_a_validated_argument(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    (Path(session) / "db_config.yaml").write_text("x: 1\n", encoding="utf-8")

    for command in (
        # Two config values: argparse would take the last one — the
        # validated first value must not be overridable.
        ".venv/bin/python eval/run.py --config db_config.yaml --config /etc/hostname",
        # Mixed spellings of the same flag.
        ".venv/bin/python eval/run.py --config=db_config.yaml --config /etc/hostname",
        # Duplicate fixed argument on a non-config flag.
        ".venv/bin/python eval/run.py --target-latency-ms 10 --target-latency-ms 999",
    ):
        decision = _resolve(command, workspace, session, extension)
        assert not decision.allowed, command
        assert "duplicate argument" in decision.reason


def test_equals_spelling_faces_identical_validation(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    (Path(session) / "db_config.yaml").write_text("x: 1\n", encoding="utf-8")

    outside = _resolve(
        ".venv/bin/python eval/run.py --config=/etc/hostname",
        workspace, session, extension,
    )
    assert not outside.allowed
    assert "session workspace" in outside.reason

    inside = _resolve(
        ".venv/bin/python eval/run.py --config=db_config.yaml",
        workspace, session, extension,
    )
    assert inside.allowed, inside.reason
    resolved = str((Path(session) / "db_config.yaml").resolve())
    # Normalized to the same typed pair the two-token spelling produces.
    assert resolved in inside.request.argv
    assert inside.request.config_path == resolved
    assert "--config=/etc/hostname" not in inside.request.argv


def test_policy_and_process_observe_the_same_arguments(tmp_path: Path):
    content = (
        "import json, pathlib, sys\n"
        "pathlib.Path('argv_echo.json').write_text("
        "json.dumps(sys.argv[1:]), encoding='utf-8')\n"
    )
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path, content)
    (Path(session) / "db_config.yaml").write_text("x: 1\n", encoding="utf-8")

    access = build_tool_access_context(session, workspace_root=workspace)
    result = _execute_tool(
        "bash",
        {"command": ".venv/bin/python eval/run.py --config db_config.yaml --tag 'my run'"},
        access,
        policy_extension=extension,
    )

    assert result.meta["returncode"] == 0, result.content
    request = result.meta["execution_request"]
    echoed = (Path(session) / "argv_echo.json").read_text(encoding="utf-8")
    import json

    assert json.loads(echoed) == request["argv"][
        request["argv"].index(request["script"]) + 1:
    ]


def test_relative_outputs_land_in_the_attempt_output_root(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    (Path(session) / "db_config.yaml").write_text("x: 1\n", encoding="utf-8")

    access = build_tool_access_context(session, workspace_root=workspace)
    result = _execute_tool(
        "bash",
        {"command": ".venv/bin/python eval/run.py --config db_config.yaml"},
        access,
        policy_extension=extension,
    )

    assert result.meta["returncode"] == 0, result.content
    assert (Path(session) / "seen.txt").is_file()
    assert not (Path(workspace) / "seen.txt").exists()


def test_sequential_and_parallel_requests_stay_at_parity(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    (Path(session) / "db_config.yaml").write_text("x: 1\n", encoding="utf-8")
    trial = Path(session) / ".trials" / "turn-001-seq-01"
    trial.mkdir(parents=True)
    (trial / "db_config.yaml").write_text("x: 1\n", encoding="utf-8")

    command = (
        ".venv/bin/python eval/run.py --config db_config.yaml --target-latency-ms 10"
    )
    sequential = _resolve(command, workspace, session, extension)
    parallel = _resolve(command, workspace, session, extension, workdir=str(trial))

    assert sequential.allowed and parallel.allowed
    seq, par = sequential.request, parallel.request
    # Same executable, script, flags, and argument order — only the
    # attempt-rooted path values differ.
    assert seq.executable == par.executable
    assert seq.script == par.script
    assert [a.split("=")[0] for a in seq.fixed_arguments] == [
        a.split("=")[0] for a in par.fixed_arguments
    ]
    assert par.cwd == str(trial)
    assert seq.config_path == str((Path(session) / "db_config.yaml").resolve())
    assert par.config_path == str((trial / "db_config.yaml").resolve())

    # And each attempt writes its relative output into its own root.
    for decision in (sequential, parallel):
        runner = GovernedCommandRunner(
            workspace_root=workspace,
            session_workspace=session,
            policy_extension=extension,
        )
        result = runner.run(command, timeout_s=60, resolved=decision)
        assert result.returncode == 0, result.output
        assert (Path(decision.request.cwd) / "seen.txt").is_file()
    assert not (Path(workspace) / "seen.txt").exists()


def test_shell_dependent_templates_are_rejected_with_migration_diagnostics():
    for template in (
        ".venv/bin/python eval/run.py | tee log",
        ".venv/bin/python eval/run.py --config $CONFIG",
        ".venv/bin/python eval/run.py --config a\n.venv/bin/python eval/run.py --config b",
        ".venv/bin/python eval/run.py --config {unknown_place}",
    ):
        reason = template_migration_reason(template)
        assert reason is not None, template
        assert "migrate" in reason

    assert template_migration_reason(
        ".venv/bin/python eval/run.py --config {session_workspace}/db_config.yaml"
    ) is None


def test_template_shape_is_enforced_at_run_start(tmp_path: Path):
    manifest_yaml = (
        REPO_ROOT / "skills" / "prompt-engineering" / "SKILL.yaml"
    ).read_text(encoding="utf-8")
    bad = manifest_yaml.replace(
        ".venv/bin/python eval/run.py --prompt prompt.yaml --eval eval_set.jsonl --demo false",
        ".venv/bin/python eval/run.py --prompt prompt.yaml | tee log",
    )
    assert bad != manifest_yaml
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "prompt-engineering"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.yaml").write_text(bad, encoding="utf-8")

    manifest = SkillRegistry(root=skills_root).get("prompt-engineering")
    with pytest.raises(SkillConfigError, match="migrate"):
        ManifestSkillRuntime(manifest, orchestrator=None).command_policy_extension()


def test_unsupported_executable_bindings_are_rejected(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = dict(_pin(tmp_path))
    extension["allowed_executables"] = ["cp", "cat", "jq"]

    decision = evaluate_command_policy(
        "jq . results.json",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    assert not decision.allowed
    assert "unsupported" in decision.reason
    assert "jq" in decision.reason

    # At load/start the declaration itself is refused — a skill may not
    # advertise a binding with no runner contract.
    manifest_yaml = (
        REPO_ROOT / "skills" / "prompt-engineering" / "SKILL.yaml"
    ).read_text(encoding="utf-8")
    declaring = manifest_yaml.replace(
        "allowed_executables: [cp, cat]",
        "allowed_executables: [cp, cat, jq]",
    )
    assert declaring != manifest_yaml
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "prompt-engineering"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.yaml").write_text(declaring, encoding="utf-8")
    manifest = SkillRegistry(root=skills_root).get("prompt-engineering")
    with pytest.raises(SkillConfigError, match="unsupported executable binding"):
        ManifestSkillRuntime(manifest, orchestrator=None).command_policy_extension()


def test_python_bindings_must_be_explicitly_qualified(tmp_path: Path):
    manifest_yaml = (
        REPO_ROOT / "skills" / "prompt-engineering" / "SKILL.yaml"
    ).read_text(encoding="utf-8")
    qualified = manifest_yaml.replace(
        'allowed_python: [".venv/bin/python", "./.venv/bin/python"]',
        'allowed_python: ["python3"]',
    )
    assert qualified != manifest_yaml
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "prompt-engineering"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.yaml").write_text(qualified, encoding="utf-8")

    manifest = SkillRegistry(root=skills_root).get("prompt-engineering")
    with pytest.raises(SkillConfigError, match="explicitly qualified"):
        ManifestSkillRuntime(manifest, orchestrator=None).command_policy_extension()


def test_bundled_skills_advertise_only_supported_bindings():
    for skill_id in ("code-refactor", "db-config-tuning", "prompt-engineering"):
        manifest = SkillRegistry().get(skill_id)
        ext = ManifestSkillRuntime(manifest, orchestrator=None).command_policy_extension()
        assert set(ext.get("allowed_executables") or ()) <= {"cp", "cat"}
        assert set(ext.get("allowed_python") or ()) <= {
            ".venv/bin/python",
            "./.venv/bin/python",
        }


def test_result_ingestion_prefers_the_attempt_output_root(tmp_path: Path):
    session = tmp_path / "workspace" / "runs" / "skill"
    trial = session / ".trials" / "turn-001-seq-01"
    trial.mkdir(parents=True)
    (trial / "results.json").write_text('{"primary_metric": 1}', encoding="utf-8")

    marker = {"results_json_path": "results.json"}
    snapshot = enrich_marker_from_result_artifact(
        marker=marker,
        workspace=str(session),
        iteration=1,
        output_root=str(trial),
    )
    assert snapshot is not None
    assert snapshot["result_artifact_source_path"] == str(
        (trial / "results.json").resolve()
    )
    assert snapshot["result_artifact_sha256"]


def test_pre_run_snapshot_and_request_agree_on_the_config_path(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension = _pin(tmp_path)
    (Path(session) / "db_config.yaml").write_text("x: 1\n", encoding="utf-8")
    command = ".venv/bin/python eval/run.py --config db_config.yaml"

    decision = _resolve(command, workspace, session, extension)
    snapshot_path = _config_snapshot_path_from_command(
        command, workspace, session, policy_extension=extension
    )

    assert decision.allowed, decision.reason
    assert snapshot_path == decision.request.config_path