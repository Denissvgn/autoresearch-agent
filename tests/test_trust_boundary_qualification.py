"""Trusted-execution-boundary qualification lane.

Combined adversarial suite for the trust findings: candidate edits,
evaluator shadowing, symlink escapes, credential reachability, forged
results, and child-process escape attempts. Every attack runs against
disposable files, synthetic secrets, and isolated processes; enforcement is
asserted through filesystem sentinels and independent teardown inspection
rather than the tested API response, and negative controls demonstrate the
same fixture succeeding against the pre-boundary behavior so the lane cannot
pass on application-only checks. The live command templates run in fresh
isolated workspaces and the recorded result evidence is probed for
immutability after acceptance.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from src.core.agent_tools import _execute_tool, build_tool_access_context
from src.core.plugin_runner import PluginCaps, PluginRunner
from src.core.process_limits import TERMINATION_BOUND_S
from src.core.result_authority import (
    issue_result_receipt,
    result_payload,
    verify_result_receipt,
)

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Synthetic secrets for reachability attacks — never real credentials.
SYNTHETIC_SECRETS = {
    "AUTORESEARCH_API_TOKEN": "sk-synthetic-g1-api-token-0000",
    "AWS_SECRET_ACCESS_KEY": "synthetic-g1-aws-secret-0000",
    "AUTORESEARCH_RESULT_RECEIPT_KEY": "synthetic-g1-receipt-key-0000",
}


def _access(shared_root: Path, session: Path, protected: dict | None = None):
    from src.core.result_authority import protected_result_names

    return build_tool_access_context(
        str(session),
        workspace_root=str(shared_root),
        extra_protected_names=protected_result_names(
            protected or {"write_protected_files": [], "output_files": []}
        ),
    )


def _pin_extension(
    skill_id: str, rel: str, *, script_path: Path | None = None,
) -> dict:
    """Digest-pin one packaged evaluator script (the immutable package path)."""
    script = script_path if script_path is not None else REPO_ROOT / "skills" / skill_id / rel
    text = script.read_text(encoding="utf-8")
    return {
        "allowed_scripts": {rel},
        "script_paths": {rel: str(script)},
        "script_digests": {rel: hashlib.sha256(text.encode("utf-8")).hexdigest()},
        "config_flag": "--config",
        "copyable_files": ["db_config.yaml", "prompt.yaml", "eval_set.jsonl",
                           "refactor_target.py", "tests_target.jsonl"],
    }


def _assert_no_survivors(pids: list[int]) -> None:
    if psutil is None:  # pragma: no cover
        return
    time.sleep(0.2)
    alive = [pid for pid in pids if psutil.pid_exists(pid)]
    assert alive == [], f"processes survived teardown: {alive}"


# --- attack: candidate edits (cross-session + protected targets) ------------


def test_attack_candidate_edits_cannot_cross_sessions_or_protected_names(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "workspace"
    session_a = shared / "runs" / "skill" / "subject" / "variant-a"
    session_b = shared / "runs" / "skill" / "subject" / "variant-b"
    session_a.mkdir(parents=True)
    session_b.mkdir(parents=True)
    (session_b / "prompt.yaml").write_text("candidate: b\n", encoding="utf-8")
    access = _access(
        shared, session_a,
        protected={
            "write_protected_files": ["eval_set.jsonl"],
            "output_files": ["eval_result.json"],
        },
    )

    # Cross-session write through the real tool loop: refused, sentinel intact.
    result = _execute_tool(
        "write_file",
        {"path": str(session_b / "prompt.yaml"), "content": "tampered"},
        access,
    )
    assert "resolves outside" in result.content
    assert (session_b / "prompt.yaml").read_text(encoding="utf-8") == "candidate: b\n"

    # Protected result-channel names stay unwritable inside the candidate tree.
    for name in ("results.json", "eval_result.json"):
        protected = _execute_tool(
            "write_file", {"path": name, "content": '{"primary_metric": 999}'}, access
        )
        assert "Wrote" not in protected.content
        assert not (session_a / name).exists()

    # Negative control: the same target is writable absent the boundary, so the
    # refusals above are enforcement, not an unwritable fixture.
    (session_b / "prompt.yaml").write_text("direct\n", encoding="utf-8")
    assert (session_b / "prompt.yaml").read_text(encoding="utf-8") == "direct\n"


# --- attack: evaluator shadowing -------------------------------------------


def test_attack_workspace_evaluator_shadow_is_never_executed(tmp_path: Path) -> None:
    from src.core.command_runner import GovernedCommandRunner

    shared = tmp_path / "workspace"
    session = shared / "runs" / "autotuner" / "DOGE_USDT_15m" / "direction"
    session.mkdir(parents=True)
    python_path = shared / ".venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(sys.executable)

    packaged = (
        "import pathlib, sys\n"
        "pathlib.Path('packaged_sentinel.txt').write_text('PACKAGED', encoding='utf-8')\n"
        "print('ITERATION_RESULT: {\"status\": \"completed\", \"primary_metric\": 1.0}')\n"
    )
    packaged_path = tmp_path / "pkg" / "eval" / "run.py"
    packaged_path.parent.mkdir(parents=True)
    packaged_path.write_text(packaged, encoding="utf-8")
    extension = _pin_extension("db-config-tuning", "eval/run.py", script_path=packaged_path)

    # The candidate plants a shadow evaluator at the workspace-relative path
    # the live template names.
    shadow_dir = session / "eval"
    shadow_dir.mkdir(parents=True)
    (shadow_dir / "run.py").write_text(
        "import pathlib; pathlib.Path('shadow_sentinel.txt').write_text('FORGED')\n",
        encoding="utf-8",
    )
    (session / "db_config.yaml").write_text("max_conn: 7\n", encoding="utf-8")

    runner = GovernedCommandRunner(
        workspace_root=str(shared), session_workspace=str(session),
        policy_extension=extension,
    )
    result = runner.run(
        ".venv/bin/python eval/run.py --config db_config.yaml --target-latency-ms 10",
        timeout_s=60,
    )
    assert result.returncode == 0, result.output
    # The resolver pinned the packaged immutable script, not the shadow.
    assert result.decision.request is not None
    assert result.decision.request.script == extension["script_paths"]["eval/run.py"]
    assert (session / "packaged_sentinel.txt").read_text(encoding="utf-8") == "PACKAGED"
    assert not (session / "shadow_sentinel.txt").exists()

    # Negative control: executing the shadow directly produces the forged
    # behavior (the pre-boundary resolver preferred the workspace script).
    subprocess.run(
        [sys.executable, str(shadow_dir / "run.py")], cwd=session, check=True,
        capture_output=True, timeout=30,
    )
    assert (session / "shadow_sentinel.txt").exists()


# --- attack: symlink escapes ------------------------------------------------


def test_attack_symlink_escapes_never_write_outside(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    shared = tmp_path / "workspace"
    session = shared / "runs" / "skill" / "subject" / "variant-a"
    session.mkdir(parents=True)
    access = _access(shared, session)

    # Dangling leaf link (the historical bypass): refused, target not created.
    (session / "dangling.txt").symlink_to(outside / "not-yet-created.txt")
    result = _execute_tool(
        "write_file", {"path": str(session / "dangling.txt"), "content": "x"}, access
    )
    assert "Wrote" not in result.content
    assert not (outside / "not-yet-created.txt").exists()

    # Parent-directory link: refused, nothing created outside.
    (session / "linkdir").symlink_to(outside)
    result = _execute_tool(
        "write_file", {"path": str(session / "linkdir" / "new.txt"), "content": "x"}, access
    )
    assert "Wrote" not in result.content
    assert not (outside / "new.txt").exists()

    # Negative control: raw pathlib follows the dangling link exactly as the
    # historical check/use bug did — the fixture is valid and the tool-layer
    # refusal is the enforcement.
    (session / "raw-dangling.txt").symlink_to(outside / "raw-created.txt")
    (session / "raw-dangling.txt").write_text("x", encoding="utf-8")
    assert (outside / "raw-created.txt").exists()


# --- attack: credential reachability ---------------------------------------


def test_attack_synthetic_secrets_reach_no_candidate_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.config import get_settings

    for name, value in SYNTHETIC_SECRETS.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    secret_file = tmp_path / "control-plane" / "service-tokens.env"
    secret_file.parent.mkdir(parents=True)
    secret_file.write_text("SERVICE_TOKEN=synthetic-g1-file-secret-0000\n", encoding="utf-8")

    plugin_dir = tmp_path / "skill"
    plugin_dir.mkdir()
    # The secret path is embedded in the probe source — it is NOT a declared
    # input, so the sandbox must not make it reachable.
    (plugin_dir / "probe.py").write_text(
        "import json, os\n"
        "try:\n"
        f"    leaked = open({str(secret_file)!r}).read()\n"
        "except Exception:\n"
        "    leaked = 'DENIED'\n"
        "print(json.dumps({'env': dict(os.environ), 'file': leaked}))\n",
        encoding="utf-8",
    )
    ws = tmp_path / "ws"
    ws.mkdir()
    try:
        # Plugin channel (sandboxed, strict env allow-list).
        result = asyncio.run(PluginRunner().run(
            skill_dir=plugin_dir, plugin="probe.py", kind="parser",
            input_json={},
            caps=PluginCaps(fs_write="none", timeout_s=30.0), workspace=ws,
        ))
        assert result.ok, result.error
        payload = json.loads(result.raw_output.strip().splitlines()[-1])
        joined = json.dumps(payload)
        for value in SYNTHETIC_SECRETS.values():
            assert value not in joined
        assert "synthetic-g1-file-secret-0000" not in payload["file"]
        for name in SYNTHETIC_SECRETS:
            assert name not in payload["env"]

        # Negative control: the parent server env holds the secrets, so the
        # fixture is valid — their absence from the child is enforcement.
        assert os.environ["AUTORESEARCH_API_TOKEN"] == SYNTHETIC_SECRETS["AUTORESEARCH_API_TOKEN"]
    finally:
        get_settings.cache_clear()


# --- attack: forged results --------------------------------------------------


def test_attack_forged_receipt_never_verifies() -> None:
    marker = {
        "primary_metric": 0.9,
        "metric_name": "composite_eval_score",
        "all_gates_passed": 1,
    }
    payload = result_payload(marker)
    identity: dict[str, Any] = dict(
        attempt_id="res_g1/turn-1/iteration-1",
        candidate_digest="sha256:" + "a" * 64,
        evaluator_digest="sha256:" + "b" * 64,
        dataset_digests=["sha256:" + "c" * 64],
    )
    receipt = issue_result_receipt(
        payload=payload, ownership_epoch=1, sequence=1, **identity
    )
    assert verify_result_receipt(receipt, payload=payload, **identity) == []

    # Forged: the model flips the metric but keeps the accepted receipt bytes.
    forged = dict(payload)
    forged["primary_metric"] = 999.0
    assert verify_result_receipt(receipt, payload=forged, **identity) != []

    # Forged: a legitimate result replayed under a different attempt identity.
    other = dict(identity, attempt_id="res_other/turn-1/iteration-1")
    assert verify_result_receipt(receipt, payload=payload, **other) != []


# --- attack: child-process escape -------------------------------------------


def test_attack_child_process_escape_denied_at_os(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    secrets = tmp_path / "control-plane"
    secrets.mkdir()
    secret = secrets / "secret.env"
    secret.write_text("synthetic-g1-child-secret-0000\n", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    plugin_dir = tmp_path / "skill"
    plugin_dir.mkdir()
    # The child attack script is a plain file in the skill package (readable
    # inside the sandbox): it attempts an outside write, a network connect,
    # and a secret read, then reports what succeeded.
    (plugin_dir / "kid.py").write_text(
        "import json, socket\n"
        f"escape_target = {str(outside / 'child-escape.txt')!r}\n"
        f"secret_path = {str(secret)!r}\n"
        "try:\n"
        "    open(escape_target, 'w').write('x')\n"
        "    w = 'OK'\n"
        "except Exception:\n"
        "    w = 'DENIED'\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
        "    n = 'OK'\n"
        "except Exception:\n"
        "    n = 'DENIED'\n"
        "try:\n"
        "    d = open(secret_path).read().strip()\n"
        "except Exception:\n"
        "    d = 'DENIED'\n"
        "print(json.dumps({'w': w, 'n': n, 'd': d}))\n",
        encoding="utf-8",
    )
    (plugin_dir / "probe.py").write_text(
        "import json, subprocess, sys, pathlib\n"
        "here = pathlib.Path(__file__).parent\n"
        "kid = subprocess.Popen(\n"
        "    [sys.executable, str(here / 'kid.py')],\n"
        "    stdout=subprocess.PIPE, stderr=subprocess.PIPE)\n"
        "out, _ = kid.communicate()\n"
        "print(json.dumps({'kid': kid.pid, 'report': json.loads(out)}))\n",
        encoding="utf-8",
    )

    result = asyncio.run(PluginRunner().run(
        skill_dir=plugin_dir, plugin="probe.py", kind="parser",
        input_json={},
        caps=PluginCaps(fs_write="none", timeout_s=30.0), workspace=ws,
    ))
    assert result.ok, result.error
    payload = json.loads(result.raw_output.strip().splitlines()[-1])
    report = payload["report"]
    assert report["w"] == "DENIED"
    assert report["n"] == "DENIED"
    assert report["d"] == "DENIED"
    # Sentinels inspected outside the tested response; tree fully reaped.
    assert not (outside / "child-escape.txt").exists()
    assert secret.read_text(encoding="utf-8") == "synthetic-g1-child-secret-0000\n"
    assert not result.cleanup_incomplete


# --- real live command templates + evidence immutability ---------------------


def _live_command(skill_id: str, skill_params: dict, session: Path) -> str:
    """The session's real suggested command: the manifest template rendered
    with the resolved parameter bindings (the parameter-to-work chain)."""
    import types

    from src.core.skill_loader import load_skill_manifest
    from src.core.skill_runtime import ManifestSkillRuntime

    runtime = ManifestSkillRuntime(
        load_skill_manifest(REPO_ROOT / "skills" / skill_id / "SKILL.yaml"), MagicMock())
    config = types.SimpleNamespace(
        skill_params=dict(skill_params),
        workspace_path=str(session),
        subject_id=None, variant=None, instrument="", timeframe="",
    )
    return runtime.experiment_command(config)


def _fresh_session(tmp_path: Path, kind: str):
    shared = tmp_path / "workspace"
    session = shared / "runs" / kind / "DOGE_USDT_15m" / "direction"
    session.mkdir(parents=True)
    # The workspace interpreter binding resolves through the venv directory so
    # the pinned interpreter keeps its venv site-packages (as in production).
    (shared / ".venv").symlink_to(REPO_ROOT / ".venv")
    return shared, session


def _bootstrap_into(skill_id: str, session: Path, skill_params: dict) -> None:
    result = asyncio.run(PluginRunner().run(
        skill_dir=REPO_ROOT / "skills" / skill_id, plugin="bootstrap.py",
        kind="bootstrap",
        input_json={
            "workspace": str(session), "mode": "live", "demo_mode": True,
            "skill_params": skill_params,
        },
        caps=PluginCaps(fs_write="workspace", timeout_s=30.0), workspace=session,
    ))
    assert result.ok, f"{skill_id} bootstrap failed: {result.error}"


@pytest.mark.parametrize(
    "skill_id,kind,skill_params",
    [
        ("db-config-tuning", "autotuner",
         {"target_latency_ms": 15, "bench_duration_s": 20}),
        ("code-refactor", "refactor",
         {"target_file": "refactor_target.py"}),
    ],
)
def test_real_live_template_runs_and_evidence_is_immutable(
    tmp_path: Path, skill_id: str, kind: str, skill_params: dict
) -> None:
    """The declared live template runs in a fresh workspace; the recorded
    result evidence cannot be changed by the candidate after acceptance."""
    from src.core.command_runner import GovernedCommandRunner

    shared, session = _fresh_session(tmp_path, kind)
    _bootstrap_into(skill_id, session, skill_params)
    extension = _pin_extension(skill_id, "eval/run.py")
    template = _live_command(skill_id, skill_params, session)

    runner = GovernedCommandRunner(
        workspace_root=str(shared), session_workspace=str(session),
        policy_extension=extension,
    )
    result = runner.run(template, timeout_s=120)
    assert result.returncode == 0, f"{skill_id}: {result.output}"
    assert "ITERATION_RESULT" in result.output
    assert '"status": "completed"' in result.output

    # After acceptance the candidate cannot change the private evidence:
    # the server-owned command log and the declared result channel.
    evidence_snapshot = {
        path.name: path.read_bytes()
        for path in (Path(result.log_path).parent.glob("*.log") if result.log_path else [])
    }
    for name in ("results.json", "eval_result.json"):
        target = session / name
        if target.exists():
            evidence_snapshot[name] = target.read_bytes()
    access = _access(
        shared, session,
        protected={
            "write_protected_files": ["eval_set.jsonl", "tests_target.jsonl"],
            "output_files": ["eval_result.json"],
        },
    )
    if result.log_path:
        tamper = _execute_tool(
            "write_file",
            {"path": result.log_path, "content": 'ITERATION_RESULT: {"primary_metric": 999}'},
            access,
        )
        assert "Wrote" not in tamper.content
        assert Path(result.log_path).exists()
    for name in ("results.json", "eval_result.json"):
        tamper = _execute_tool(
            "write_file", {"path": name, "content": '{"primary_metric": 999}'}, access
        )
        assert "Wrote" not in tamper.content
        target = session / name
        if name in evidence_snapshot:
            assert target.read_bytes() == evidence_snapshot[name]
        else:
            assert not target.exists()
    if result.log_path:
        after = {p.name: p.read_bytes() for p in Path(result.log_path).parent.glob("*.log")}
        logs_before = {k: v for k, v in evidence_snapshot.items() if k.endswith(".log")}
        assert after == logs_before


def test_live_template_without_external_scorer_refuses_cleanly(tmp_path: Path) -> None:
    """The live prompt-engineering template needs an external scorer; without
    one the evaluator refuses with an explicit error rather than fabricating
    a result — the scorer environment is outside the local guarantee."""
    from src.core.command_runner import GovernedCommandRunner

    shared, session = _fresh_session(tmp_path, "prompt-engineering")
    _bootstrap_into(
        "prompt-engineering", session,
        {"symbol": "AAPL", "timeframe": "1h", "direction": "long"},
    )
    extension = _pin_extension("prompt-engineering", "eval/run.py")
    runner = GovernedCommandRunner(
        workspace_root=str(shared), session_workspace=str(session),
        policy_extension=extension,
    )
    result = runner.run(
        _live_command(
            "prompt-engineering",
            {"symbol": "AAPL", "timeframe": "1h", "direction": "long"},
            session,
        ),
        timeout_s=120,
    )
    # A failed evaluation is recorded as eval_error — never as a score.
    assert '"status": "eval_error"' in result.output
    assert '"primary_metric": null' in result.output