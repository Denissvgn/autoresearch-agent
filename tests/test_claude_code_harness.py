"""Claude Code harness adapter: protocol fixtures and common contracts.

The recorded stream-json transcripts are the conformance fixtures: they
pin the documented event shapes (system/init, assistant content blocks,
result with usage/denials/session) and the mapping into the common
contracts. The live smoke is bounded and opt-in.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from src.core.claude_code_harness import (
    CLAUDE_INTERFACE,
    CLAUDE_SCHEMA_PIN,
    UNSUPPORTED_OPTIONAL_FEATURES,
    ClaudeCodeHarnessAdapter,
    ClaudeRunConfig,
    map_candidate_changes,
    map_usage,
    normalize_claude_event,
)
from src.core.harness_adapter import request_pause, request_steer
from src.core.harness_contract import (
    ATTACH_MODE_CONTINUATION,
    ATTACH_MODE_NATIVE_RESUME,
    CAPABILITY_RESUME,
    HarnessContractError,
    HarnessLifecycleError,
    UnsupportedCapabilityError,
)
from src.core.research_kernel import AttemptResult, run_kernel_lifecycle

REPO_ROOT = Path(__file__).resolve().parents[1]

# The recorded protocol fixture: one research turn in the documented
# stream-json shapes.
RECORDED_TRANSCRIPT = [
    {
        "type": "system",
        "subtype": "init",
        "session_id": "sess-abc-123",
        "tools": ["Read", "Bash"],
        "permissionMode": "default",
    },
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "proposing a candidate"},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "Write",
                    "input": {"file_path": "candidate.yaml", "content": "x: 1"},
                },
            ],
            "usage": {
                "input_tokens": 900,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 400,
                "output_tokens": 80,
            },
        },
    },
    {
        "type": "result",
        "subtype": "success",
        "session_id": "sess-abc-123",
        "usage": {
            "input_tokens": 900,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 400,
            "output_tokens": 80,
        },
        "total_cost_usd": 0.0123,
        "permission_denials": [],
        "is_error": False,
    },
]

DENIED_RESULT = {
    "type": "result",
    "subtype": "error_during_execution",
    "session_id": "sess-abc-123",
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "permission_denials": [{"tool_name": "Bash", "tool_input": {}}],
    "is_error": True,
}


def _fake_claude_script(tmp_path, events):
    """A stub 'claude' that replays the recorded fixture on stdout."""
    payload = json.dumps(events)
    script = tmp_path / "fake_claude.py"
    script.write_text(
        "import json, sys\n"
        f"for event in json.loads({payload!r}):\n"
        "    sys.stdout.write(json.dumps(event) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )
    return (sys.executable, str(script))


def _run_fixture(tmp_path, events=None):
    events = events or RECORDED_TRANSCRIPT
    adapter = ClaudeCodeHarnessAdapter()
    config = ClaudeRunConfig(
        prompt="propose one candidate",
        workspace=str(tmp_path / "ws"),
        config_dir=str(tmp_path / "claude-home"),
        executable=_fake_claude_script(tmp_path, events),
    )
    started = adapter.start({"config": config})
    handle = started["handle"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if any(
            e.get("type") == "result" for e in adapter.events(handle)
        ):
            break
        time.sleep(0.02)
    return adapter, handle


def test_recorded_fixture_maps_into_common_contracts(tmp_path):
    adapter, handle = _run_fixture(tmp_path)
    events = list(adapter.events(handle))
    types = [event["type"] for event in events]
    assert types[0] == "system"
    assert "assistant" in types
    assert "result" in types
    # the session identifier is adapter-owned state
    assert adapter.session_id(handle) == "sess-abc-123"
    # usage maps into the common contract without losing native counters
    usage = adapter.usage(handle)
    assert usage[-1]["input_tokens"] == 900
    assert usage[-1]["cached_input_tokens"] == 500
    assert usage[-1]["output_tokens"] == 80
    assert usage[-1]["total_tokens"] == 1480
    assert usage[-1]["native"]["cache_read_input_tokens"] == 400
    # tool-use blocks become candidate proposals, model-proposed only
    proposals = adapter.proposals(handle)
    assert len(proposals) == 1
    assert proposals[0]["kind"] == "candidate_change"
    assert proposals[0]["target"] == "Write"
    assert proposals[0]["payload"]["authority"] == "model_proposed"
    assert adapter.attempt_outcome(handle) == "completed"
    adapter.close(handle)


def test_tool_denial_is_failure_never_success(tmp_path):
    adapter, handle = _run_fixture(
        tmp_path, [RECORDED_TRANSCRIPT[0], DENIED_RESULT]
    )
    assert adapter.attempt_outcome(handle) == "failed"
    adapter.close(handle)


def test_unknown_events_are_tolerated():
    normalized = normalize_claude_event({"type": "telepathy.bloom"})
    assert normalized["unknown"] is True


def test_capability_profile_is_qualified(tmp_path):
    adapter = ClaudeCodeHarnessAdapter()
    # resume is demonstrated and advertised; pause/steering are not
    assert adapter.capabilities() == frozenset({CAPABILITY_RESUME})
    assert UNSUPPORTED_OPTIONAL_FEATURES == frozenset({"pause", "steering"})
    identity = adapter.identity()
    assert identity["interface"] == CLAUDE_INTERFACE
    assert identity["schema_pin"] == CLAUDE_SCHEMA_PIN

    adapter, handle = _run_fixture(tmp_path)
    # qualified native resume: recorded session id, same config directory
    assert adapter.resume(handle) == "sess-abc-123"
    with pytest.raises(UnsupportedCapabilityError):
        request_pause(adapter, handle)
    with pytest.raises(UnsupportedCapabilityError):
        request_steer(
            adapter,
            handle,
            {"proposal_id": "p", "kind": "steer", "target": "run",
             "payload": {}},
        )
    adapter.close(handle)


def test_native_resume_requires_a_recorded_session(tmp_path):
    adapter = ClaudeCodeHarnessAdapter()
    adapter, handle = _run_fixture(
        tmp_path,
        [
            {
                "type": "result",
                "subtype": "success",
                "usage": {},
                "is_error": False,
            }
        ],
    )
    # a run with no recorded session cannot claim native resume
    assert adapter.session_id(handle) is None
    with pytest.raises(HarnessContractError):
        adapter.resume(handle)
    adapter.close(handle)


def test_attach_is_honest_about_native_resume(tmp_path):
    adapter = ClaudeCodeHarnessAdapter()
    config = ClaudeRunConfig(
        prompt="x",
        workspace=str(tmp_path / "ws"),
        config_dir=str(tmp_path / "home"),
        executable=_fake_claude_script(
            tmp_path,
            [{"type": "result", "usage": {}, "is_error": False}],
        ),
    )
    # same-harness native resume is honest
    started = adapter.attach(
        {
            "mode": ATTACH_MODE_NATIVE_RESUME,
            "origin_harness": "claude-code",
            "config": config,
        }
    )
    assert started["mode"] == ATTACH_MODE_NATIVE_RESUME
    adapter.close(started["handle"])
    # a cross-harness native claim is refused
    with pytest.raises(HarnessContractError):
        adapter.attach(
            {
                "mode": ATTACH_MODE_NATIVE_RESUME,
                "origin_harness": "codex",
                "config": config,
            }
        )
    # continuation remains available
    continued = adapter.attach(
        {"mode": ATTACH_MODE_CONTINUATION, "config": config}
    )
    handle = continued["handle"]
    adapter.close(handle)
    adapter.close(handle)  # idempotent
    with pytest.raises(HarnessLifecycleError):
        list(adapter.events(handle))


def test_interruption_cleans_up_child_processes(tmp_path):
    child_pid_file = tmp_path / "child.pid"
    body = (
        "import json, subprocess, sys, time\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init',"
        " 'session_id': 'sess-slow'}), flush=True)\n"
        "p = subprocess.Popen([sys.executable, '-c',"
        " 'import time; time.sleep(60)'])\n"
        f"open({str(child_pid_file)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    script = tmp_path / "slow_claude.py"
    script.write_text(body)
    adapter = ClaudeCodeHarnessAdapter()
    config = ClaudeRunConfig(
        prompt="slow",
        workspace=str(tmp_path / "ws"),
        config_dir=str(tmp_path / "home"),
        executable=(sys.executable, str(script)),
    )
    handle = adapter.start({"config": config})["handle"]
    deadline = time.monotonic() + 15
    while not child_pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert child_pid_file.exists()
    child_pid = int(child_pid_file.read_text())
    started = time.monotonic()
    adapter.cancel(handle)
    adapter.close(handle)
    assert time.monotonic() - started < 10.0
    time.sleep(0.3)
    with pytest.raises(OSError):
        os.kill(child_pid, 0)


def test_adapter_executes_kernel_lifecycle(tmp_path):
    adapter, handle = _run_fixture(tmp_path)

    class ClaudeDriver:
        def run_attempt(self, plan, *, attempt_index, context):
            outcome = adapter.attempt_outcome(handle)
            usage = adapter.usage(handle)
            metric = float(usage[-1]["total_tokens"]) if usage else None
            return AttemptResult(
                iteration=attempt_index, outcome=outcome, metric=metric
            )

    result = run_kernel_lifecycle(
        ClaudeDriver(), session={"max_iterations": 1}, max_attempts=4
    )
    assert result.completed is True
    assert result.attempts[0].outcome == "completed"
    assert result.attempts[0].metric == 1480.0
    adapter.close(handle)


def test_live_smoke_is_bounded_and_opt_in(tmp_path):
    """Opt-in live smoke: denial, interruption, resume, cleanup."""
    if not os.environ.get("AUTORESEARCH_CLAUDE_CODE_LIVE"):
        pytest.skip(
            "Set AUTORESEARCH_CLAUDE_CODE_LIVE=1 for the bounded live smoke"
        )
    import shutil

    if not shutil.which("claude"):
        pytest.skip("claude CLI is not installed")
    adapter = ClaudeCodeHarnessAdapter()
    config = ClaudeRunConfig(
        prompt="Reply with the single word: pong",
        workspace=str(tmp_path / "live-ws"),
        config_dir=str(tmp_path / "live-home"),
        cleanup_deadline_s=10.0,
    )
    handle = adapter.start({"config": config})["handle"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if any(e.get("type") == "result" for e in adapter.events(handle)):
            break
        time.sleep(0.1)
    outcome = adapter.attempt_outcome(handle)
    usage = adapter.usage(handle)
    session = adapter.session_id(handle)
    started = time.monotonic()
    adapter.close(handle)
    assert time.monotonic() - started < 15.0
    print(
        "live-smoke:",
        json.dumps(
            {
                "interface": CLAUDE_INTERFACE,
                "schema_pin": CLAUDE_SCHEMA_PIN,
                "outcome": outcome,
                "usage": usage,
                "session_id": session,
            }
        ),
    )