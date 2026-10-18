"""Pinned-evaluator and interpreter-environment regressions.

Declared evaluator entrypoints must run only from digest-pinned package
assets; the sanctioned interpreter and the import/search path must not be
shadowable from the candidate tree; attempt provenance records the
evaluator and environment identity computed server-side at launch; and
candidate execution sees neither result-signing nor operator credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from src.core.agent_tools import _execute_tool
from src.core.command_policy import evaluate_command_policy
from src.core.command_runner import GovernedCommandRunner
from src.core.iteration_snapshot import build_iteration_attempt_snapshot
from src.core.orchestrator import AgentOrchestrator


def _workspace(tmp_path: Path) -> tuple[str, str]:
    workspace = tmp_path / "workspace"
    session = workspace / "runs" / "subject"
    session.mkdir(parents=True)
    python_path = workspace / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)
    return str(workspace), str(session)


def _pin_script(base: Path, script_name: str, content: str) -> tuple[dict, Path]:
    """Create a digest-pinned packaged script outside the workspace.

    ``base/pkg`` stands in for the installed ``skills/<id>/`` tree: the
    policy resolves declared entrypoints here (digest-verified before
    launch), never at a same-named agent-writable workspace copy.
    """
    pkg = base / "pkg"
    script_path = pkg / script_name
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    extension = {
        "allowed_scripts": {script_name},
        "script_paths": {script_name: str(script_path)},
        "script_digests": {script_name: digest},
    }
    return extension, script_path


def test_workspace_shadow_of_declared_evaluator_never_runs(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension, packaged = _pin_script(
        tmp_path, "eval/run.py", "print('packaged')\n"
    )
    shadow = Path(workspace) / "eval" / "run.py"
    shadow.parent.mkdir(parents=True)
    shadow.write_text("print('shadowed')\n", encoding="utf-8")

    decision = evaluate_command_policy(
        ".venv/bin/python eval/run.py --prompt prompt.yaml",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )

    assert decision.allowed, decision.reason
    assert str(packaged) in decision.argv
    assert str(shadow) not in decision.argv
    # The pin keeps the workspace-venv binding in argv: interpreter detection
    # (and the venv's installed packages) follows the invoked path, not the
    # resolved base interpreter.
    interpreter_binding = os.path.join(workspace, ".venv", "bin", "python")
    assert decision.argv[0] == interpreter_binding
    assert decision.argv[1:3] == ["-E", "-s"]


def test_declared_script_without_pinned_asset_fails_instead_of_workspace_fallback(
    tmp_path: Path,
):
    workspace, session = _workspace(tmp_path)
    fallback = Path(workspace) / "eval" / "run.py"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("print('fallback')\n", encoding="utf-8")

    decision = evaluate_command_policy(
        ".venv/bin/python eval/run.py",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension={"allowed_scripts": {"eval/run.py"}},
    )

    assert fallback.is_file()  # the workspace fallback exists and still must not run
    assert not decision.allowed
    assert "workspace fallbacks are not allowed" in decision.reason


def test_changed_pinned_evaluator_fails_before_launch(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension, packaged = _pin_script(
        tmp_path, "eval/run.py", "print('original')\n"
    )
    packaged.write_text("print('tampered')\n", encoding="utf-8")

    decision = evaluate_command_policy(
        ".venv/bin/python eval/run.py",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )

    assert not decision.allowed
    assert "changed since pinning" in decision.reason


def test_missing_pinned_evaluator_fails_before_launch(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    extension, packaged = _pin_script(tmp_path, "eval/run.py", "print('x')\n")
    packaged.unlink()

    decision = evaluate_command_policy(
        ".venv/bin/python eval/run.py",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )

    assert not decision.allowed
    assert "missing or unreadable" in decision.reason


def test_missing_pinned_interpreter_fails_before_launch(tmp_path: Path):
    workspace, session = _workspace(tmp_path)
    Path(workspace, ".venv", "bin", "python").unlink()
    extension, _ = _pin_script(tmp_path, "eval/run.py", "print('x')\n")

    decision = evaluate_command_policy(
        ".venv/bin/python eval/run.py",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )

    assert not decision.allowed
    assert "pinned interpreter is missing" in decision.reason


def test_full_tool_loop_executes_packaged_evaluator_not_workspace_shadow(
    tmp_path: Path,
):
    from src.core.tool_access import build_tool_access_context

    workspace, session = _workspace(tmp_path)
    result_path = Path(workspace) / "who_ran.txt"
    extension, packaged = _pin_script(
        tmp_path,
        "eval/run.py",
        "import pathlib\n"
        f"pathlib.Path({str(result_path)!r}).write_text('PACKAGED')\n",
    )
    shadow = Path(workspace) / "eval" / "run.py"
    shadow.parent.mkdir(parents=True)
    shadow.write_text(
        "import pathlib\n"
        f"pathlib.Path({str(result_path)!r}).write_text('SHADOWED')\n",
        encoding="utf-8",
    )

    access = build_tool_access_context(session, workspace_root=workspace)
    result = _execute_tool(
        "bash",
        {"command": ".venv/bin/python eval/run.py --prompt prompt.yaml"},
        access,
        policy_extension=extension,
    )

    assert result.meta["returncode"] == 0, result.content
    assert result_path.read_text(encoding="utf-8") == "PACKAGED"
    identity = result.meta["execution_identity"]
    assert identity["evaluator"]["path"] == str(packaged)
    assert (
        identity["evaluator"]["sha256"]
        == extension["script_digests"]["eval/run.py"]
    )
    assert identity["interpreter"]["path"] == os.path.realpath(
        os.path.join(workspace, ".venv", "bin", "python")
    )
    assert identity["import_flags"] == ["-E", "-s"]


def test_planted_interpreter_under_candidate_tree_is_never_launched(
    tmp_path: Path,
):
    workspace, session = _workspace(tmp_path)
    planted = Path(session) / ".venv" / "bin" / "python"
    planted.parent.mkdir(parents=True)
    marker = Path(workspace) / "planted_ran.txt"
    planted.write_text(
        f"#!/bin/sh\ntouch {marker}\nexit 1\n", encoding="utf-8"
    )
    planted.chmod(0o755)
    extension, _ = _pin_script(tmp_path, "eval/run.py", "print('trusted')\n")

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    result = runner.run(
        ".venv/bin/python eval/run.py",
        cwd=session,
        timeout_s=60,
    )

    assert result.returncode == 0, result.output
    assert "trusted" in result.output
    assert not marker.exists()


def test_import_and_search_path_shadowing_cannot_change_evaluator_imports(
    tmp_path: Path, monkeypatch
):
    workspace, session = _workspace(tmp_path)
    pkg = tmp_path / "pkg"
    (pkg / "eval").mkdir(parents=True)
    (pkg / "eval" / "helper.py").write_text(
        "MARKER = 'PKG-HELPER'\n", encoding="utf-8"
    )
    result_path = Path(workspace) / "import_report.json"
    content = (
        "import json, os, pathlib, site, sys, uuid\n"
        "import helper\n"
        "report = {\n"
        "    'helper_file': helper.__file__,\n"
        "    'helper_marker': helper.MARKER,\n"
        "    'uuid_file': uuid.__file__,\n"
        "    'path0': sys.path[0],\n"
        "    'pythonpath': os.environ.get('PYTHONPATH'),\n"
        "    'no_user_site': os.environ.get('PYTHONNOUSERSITE'),\n"
        "    'user_site': site.ENABLE_USER_SITE,\n"
        "}\n"
        f"pathlib.Path({str(result_path)!r}).write_text(json.dumps(report))\n"
    )
    script_path = pkg / "eval" / "run.py"
    script_path.write_text(content, encoding="utf-8")
    extension = {
        "allowed_scripts": {"eval/run.py"},
        "script_paths": {"eval/run.py": str(script_path)},
        "script_digests": {
            "eval/run.py": hashlib.sha256(content.encode("utf-8")).hexdigest()
        },
    }
    # Candidate-controlled shadowing surfaces: a same-named dependency in the
    # working directory, a startup hook in the working directory, and a
    # shadow module on a poisoned PYTHONPATH.
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir()
    (shadow_dir / "uuid.py").write_text(
        "raise SystemExit('shadow imported')\n", encoding="utf-8"
    )
    (Path(session) / "helper.py").write_text(
        "MARKER = 'CWD-HELPER'\n", encoding="utf-8"
    )
    (Path(session) / "sitecustomize.py").write_text(
        "raise SystemExit('sitecustomize ran')\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(shadow_dir))

    runner = GovernedCommandRunner(
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    result = runner.run(
        ".venv/bin/python eval/run.py", cwd=session, timeout_s=60
    )

    assert result.returncode == 0, result.output
    report = json.loads(result_path.read_text(encoding="utf-8"))
    assert report["helper_marker"] == "PKG-HELPER"
    assert report["helper_file"] == str(pkg / "eval" / "helper.py")
    assert report["path0"] == str(pkg / "eval")
    assert report["uuid_file"] != str(shadow_dir / "uuid.py")
    assert "shadow" not in report["uuid_file"]
    assert report["pythonpath"] is None
    assert report["no_user_site"] == "1"
    assert report["user_site"] is False


def test_evaluator_child_env_carries_nonce_but_no_operator_credentials(
    tmp_path: Path, monkeypatch
):
    from src.core.tool_access import build_tool_access_context

    workspace, session = _workspace(tmp_path)
    monkeypatch.setenv("AUTORESEARCH_API_TOKEN", "operator-secret")
    monkeypatch.setenv(
        "AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER", "signing-secret"
    )
    env_path = Path(workspace) / "env.json"
    extension, _ = _pin_script(
        tmp_path,
        "eval/run.py",
        "import json, os, pathlib\n"
        f"pathlib.Path({str(env_path)!r}).write_text(json.dumps(dict(os.environ)))\n",
    )

    access = build_tool_access_context(session, workspace_root=workspace)
    result = _execute_tool(
        "bash",
        {"command": ".venv/bin/python eval/run.py --prompt prompt.yaml"},
        access,
        extra_env={"AUTORESEARCH_SESSION_NONCE": "n" * 32},
        policy_extension=extension,
    )

    assert result.meta["returncode"] == 0, result.content
    child_env = json.loads(env_path.read_text(encoding="utf-8"))
    assert child_env.get("AUTORESEARCH_SESSION_NONCE") == "n" * 32
    assert "AUTORESEARCH_API_TOKEN" not in child_env
    assert "AUTORESEARCH_PRODUCTION_APPROVAL_VERIFIER" not in child_env
    dumped = json.dumps(child_env)
    assert "operator-secret" not in dumped
    assert "signing-secret" not in dumped


def test_evaluation_data_digests_record_identity_and_refuse_aliased_data(
    tmp_path: Path,
):
    workspace, session = _workspace(tmp_path)
    extension, _ = _pin_script(tmp_path, "eval/run.py", "print('x')\n")
    extension["write_protected_files"] = ["eval_set.jsonl", "later.jsonl"]
    dataset = Path(session) / "eval_set.jsonl"
    dataset.write_text('{"q": 1}\n', encoding="utf-8")

    decision = evaluate_command_policy(
        ".venv/bin/python eval/run.py --eval eval_set.jsonl",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )

    assert decision.allowed, decision.reason
    data = decision.execution_identity["evaluation_data"]
    assert data["eval_set.jsonl"] == hashlib.sha256(b'{"q": 1}\n').hexdigest()
    assert data["later.jsonl"] == "missing"

    # A symlink planted where evaluation data must be is tampering: the
    # launch fails before the evaluator can consume the aliased file.
    dataset.unlink()
    dataset.symlink_to(Path(workspace) / ".env")
    decision2 = evaluate_command_policy(
        ".venv/bin/python eval/run.py --eval eval_set.jsonl",
        workspace_root=workspace,
        session_workspace=session,
        policy_extension=extension,
    )
    assert not decision2.allowed
    assert "evaluation data" in decision2.reason


def test_attempt_provenance_carries_server_computed_execution_identity(
    tmp_path: Path,
):
    identity = {
        "schema_version": "autoresearch_execution_identity.v1",
        "evaluator": {
            "name": "eval/run.py",
            "path": "/pkg/eval/run.py",
            "sha256": "a" * 64,
        },
        "interpreter": {"path": "/venv/bin/python", "sha256": "b" * 64},
    }
    marker = {
        "status": "ok",
        # A self-reported marker must not be able to forge provenance.
        "execution_identity": {"evaluator": {"sha256": "forged"}},
    }
    AgentOrchestrator._attach_runtime_command_metadata(
        marker, {"runtime_command_id": 7, "execution_identity": identity}
    )
    assert marker["execution_identity"] == identity

    untrusted = {"execution_identity": {"evaluator": {"sha256": "forged"}}}
    AgentOrchestrator._attach_runtime_command_metadata(untrusted, {})
    assert "execution_identity" not in untrusted

    snapshot = build_iteration_attempt_snapshot(
        research_id="res_pin",
        iteration=1,
        turn=1,
        command=".venv/bin/python eval/run.py",
        config_snapshot="cfg: 1\n",
        workspace=str(tmp_path),
        marker=marker,
    )
    assert snapshot["execution_identity"] == identity


def test_manifest_runtime_extension_pins_packaged_scripts_with_digests():
    from src.core.skill_registry import SkillRegistry
    from src.core.skill_runtime import ManifestSkillRuntime

    manifest = SkillRegistry().get("prompt-engineering")
    ext = ManifestSkillRuntime(manifest, host=None).command_policy_extension()

    assert "eval/run.py" in ext["script_paths"]
    assert set(ext["script_digests"]) == set(ext["script_paths"])
    for name, path in ext["script_paths"].items():
        assert Path(path).is_file()
        assert ext["script_digests"][name] == hashlib.sha256(
            Path(path).read_bytes()
        ).hexdigest()