"""Prompt evaluator/bootstrap fail-closed regressions; no external services."""

from __future__ import annotations

import importlib.util
import io
import json
import shlex
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "prompt-engineering"
EXAMPLES = [{"input": "Custom question", "expected": "Custom answer"}]


@pytest.fixture
def evaluator(monkeypatch):
    monkeypatch.syspath_prepend(str(SKILL / "eval"))
    spec = importlib.util.spec_from_file_location("prompt_evaluator", SKILL / "eval" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bootstrap(monkeypatch):
    monkeypatch.syspath_prepend(str(SKILL))
    spec = importlib.util.spec_from_file_location("prompt_bootstrap", SKILL / "bootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke_bootstrap(module, monkeypatch, workspace, **extra):
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"workspace": str(workspace), **extra}))
    )
    return module.main()


def test_live_has_no_ambient_fallback(evaluator, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("SCORER_URL", "http://unused.invalid")
    result = evaluator._score_prompt("prompt", EXAMPLES)
    assert result["status"] == "eval_error"
    assert result["primary_metric"] is None
    assert result["training_gates_passed"] is False
    demo = evaluator._score_prompt("prompt", EXAMPLES, demo=True)
    assert demo["status"] == "completed"
    assert demo["scorer"] == "fallback"


@pytest.mark.parametrize("demo", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        b"{}",
        b"[]",
        b"not json",
        b'{"score":NaN}',
        b'{"score":true}',
        b'{"score":1.1}',
        b'{"score":0.9,"precision":-1}',
        b'{"status":"eval_error","score":0.9}',
    ],
)
def test_bad_remote_never_falls_back(evaluator, monkeypatch, body, demo):
    import urllib.request

    class Response(io.BytesIO):
        status = 200

    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *a: types.SimpleNamespace(open=lambda *a, **k: Response(body)),
    )
    result = evaluator._score_prompt("prompt", EXAMPLES, "https://scorer.invalid", demo=demo)
    assert result["status"] == "eval_error"
    assert result["primary_metric"] is None
    assert not result["training_gates_passed"]


@pytest.mark.parametrize("failure", [TimeoutError(), OSError("offline")])
def test_remote_transport_failure(evaluator, monkeypatch, failure):
    import urllib.request

    def fail(*a, **k):
        raise failure

    monkeypatch.setattr(urllib.request, "build_opener", fail)
    assert (
        evaluator._score_prompt("p", EXAMPLES, "https://scorer.invalid", demo=True)["status"]
        == "eval_error"
    )


def test_valid_remote_receives_selected_dataset(evaluator, monkeypatch):
    import urllib.request

    class Response(io.BytesIO):
        status = 200

    def remote(request, **kwargs):
        assert json.loads(request.data) == {"prompt": "p", "examples": EXAMPLES}
        assert not request.has_header("Authorization")
        return Response(b'{"score":0.9,"precision":0.8}')

    monkeypatch.setattr(
        urllib.request, "build_opener", lambda *a: types.SimpleNamespace(open=remote)
    )
    result = evaluator._score_prompt("p", EXAMPLES, "https://scorer.invalid")
    assert result["status"] == "completed"
    assert result["primary_metric"] == 0.9
    assert result["scorer"] == "remote"


def test_cli_error_marker_is_not_promotable(evaluator, monkeypatch, tmp_path, capsys):
    prompt = tmp_path / "prompt.yaml"
    prompt.write_text("p")
    data = tmp_path / "data.jsonl"
    data.write_text(json.dumps(EXAMPLES[0]) + "\n")
    monkeypatch.setattr(sys, "argv", ["run.py", "--prompt", str(prompt), "--eval", str(data)])
    monkeypatch.setenv("AUTORESEARCH_SESSION_NONCE", "nonce")
    assert evaluator.main() == 1
    payload = json.loads(capsys.readouterr().out.removeprefix("ITERATION_RESULT: "))
    assert payload["server_nonce"] == "nonce"
    assert payload["status"] == "eval_error"
    assert payload["primary_metric"] is None
    assert payload["training_gates_passed"] is False


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{}",
        "[]",
        "null",
        "not JSON",
        '{"input":1,"expected":"a"}',
        '{"input":"q","expected":"a","code":"print(1)"}',
    ],
)
def test_dataset_invalid_before_any_writes(bootstrap, monkeypatch, tmp_path, raw):
    source = tmp_path / "source.jsonl"
    source.write_text(raw)
    workspace = tmp_path / "ws"
    assert (
        invoke_bootstrap(bootstrap, monkeypatch, workspace, skill_params={"eval_set": str(source)})
        == 2
    )
    assert not workspace.exists()


def test_bootstrap_uses_data_only_and_preserves_edits(bootstrap, monkeypatch, tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps(EXAMPLES[0]) + "\n")
    (tmp_path / "run.py").write_text("raise RuntimeError('not copied')")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "prompt.yaml").write_text("user edit")
    params = {"eval_set": str(source)}
    assert invoke_bootstrap(bootstrap, monkeypatch, workspace, skill_params=params) == 0
    assert json.loads((workspace / "eval_set.jsonl").read_text()) == EXAMPLES[0]
    assert (workspace / "prompt.yaml").read_text() == "user edit"
    assert {p.name for p in workspace.iterdir()} == {
        "prompt.yaml",
        "best_prompt.yaml",
        "eval_set.jsonl",
    }
    assert invoke_bootstrap(bootstrap, monkeypatch, workspace, skill_params=params) == 0


def test_bootstrap_requires_server_demo(bootstrap, monkeypatch, tmp_path):
    workspace = tmp_path / "ws"
    assert (
        invoke_bootstrap(bootstrap, monkeypatch, workspace, skill_params={"demo_mode": True}) == 2
    )
    assert invoke_bootstrap(bootstrap, monkeypatch, workspace, demo_mode="true") == 2
    assert invoke_bootstrap(bootstrap, monkeypatch, workspace, demo_mode=True) == 0


def test_bootstrap_rejects_symlink_dataset(bootstrap, monkeypatch, tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps(EXAMPLES[0]))
    link = tmp_path / "link.jsonl"
    link.symlink_to(source)
    assert (
        invoke_bootstrap(
            bootstrap, monkeypatch, tmp_path / "ws", skill_params={"eval_set": str(link)}
        )
        == 2
    )


@pytest.mark.parametrize(
    "demo,environment,expected",
    [(False, "development", "false"), (True, "development", "true"), (True, "production", "false")],
)
def test_command_wiring_is_explicit(monkeypatch, demo, environment, expected):
    from src.config import settings
    from src.core.skill_loader import load_skill_manifest
    from src.core.skill_runtime import ManifestSkillRuntime

    monkeypatch.setattr(settings, "demo_mode", demo)
    monkeypatch.setattr(settings, "environment", environment)
    runtime = ManifestSkillRuntime(load_skill_manifest(SKILL / "SKILL.yaml"), None)
    config = types.SimpleNamespace(
        skill_params={"scorer_url": "https://scorer.invalid/eval", "demo_mode": not demo}
    )
    params = runtime.evaluator_command_params(config)
    assert params == {
        "--eval": "eval_set.jsonl",
        "--scorer-url": "https://scorer.invalid/eval",
        "--demo": expected,
    }
    argv = shlex.split(runtime.experiment_command(config))
    assert argv[argv.index("--demo") + 1] == expected
    assert argv[argv.index("--scorer-url") + 1] == "https://scorer.invalid/eval"


@pytest.mark.asyncio
@pytest.mark.parametrize("dry", [False, True])
async def test_runner_threads_dataset_and_server_demo(monkeypatch, tmp_path, dry):
    from src.config import settings
    from src.core.bootstrap_runner import BootstrapRunner
    from src.core.plugin_runner import PluginResult
    from src.core.skill_loader import load_layout, load_skill_manifest

    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "environment", "development")
    workspace = tmp_path / "ws"
    supplied = {"eval_set": "custom.jsonl", "demo_mode": False}
    captured = {}

    class Runner:
        async def run(self, **kwargs):
            captured.update(kwargs["input_json"])
            return PluginResult(ok=True, kind="bootstrap", plugin_path="bootstrap.py", output={})

    manifest = load_skill_manifest(SKILL / "SKILL.yaml")
    outcome = await BootstrapRunner(plugin_runner=Runner()).run(
        skill_dir=SKILL,
        layout=load_layout(SKILL, manifest),
        manifest=manifest,
        workspace=workspace,
        skill_params=supplied,
        dry=dry,
    )
    assert outcome.ok
    assert captured["demo_mode"] is True
    assert captured["skill_params"]["eval_set"] == str(workspace / "custom.jsonl")
    assert supplied["eval_set"] == "custom.jsonl"
