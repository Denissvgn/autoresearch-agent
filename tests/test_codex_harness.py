"""Codex harness adapter: recorded protocol fixtures and common contracts.

The recorded transcripts are the conformance fixtures: they pin the
documented ``codex exec --json`` shapes (current and the known pre-v0.44
drift) and the mapping into the common event/proposal/usage contracts.
The live smoke is bounded and opt-in.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from src.core.codex_harness import (
    CODEX_INTERFACE,
    CODEX_SCHEMA_PIN,
    UNSUPPORTED_OPTIONAL_FEATURES,
    CodexHarnessAdapter,
    CodexRunConfig,
    map_candidate_changes,
    map_usage,
    normalize_codex_event,
)
from src.core.harness_adapter import request_pause, request_steer
from src.core.harness_contract import (
    ATTACH_MODE_CONTINUATION,
    ATTACH_MODE_NATIVE_RESUME,
    HarnessContractError,
    HarnessLifecycleError,
    UnsupportedCapabilityError,
)
from src.core.research_kernel import AttemptResult, run_kernel_lifecycle

REPO_ROOT = Path(__file__).resolve().parents[1]

# The recorded protocol fixture: a small real research lifecycle in the
# documented exec --json shapes (thread -> turn -> items -> usage).
RECORDED_TRANSCRIPT = [
    {"type": "thread.started", "thread_id": "0199a213-81c0-7800-8aa1-bb"},
    {"type": "turn.started"},
    {
        "type": "item.started",
        "item": {
            "id": "item_0",
            "type": "command_execution",
            "command": "bash -lc ls",
            "status": "in_progress",
        },
    },
    {
        "type": "item.completed",
        "item": {
            "id": "item_0",
            "type": "command_execution",
            "command": "bash -lc ls",
            "status": "completed",
        },
    },
    {
        "type": "item.completed",
        "item": {
            "id": "item_1",
            "type": "file_change",
            "status": "completed",
            "changes": [{"path": "candidate.yaml", "kind": "add"}],
        },
    },
    {
        "type": "item.completed",
        "item": {
            "id": "item_2",
            "type": "agent_message",
            "text": "candidate proposed",
            "status": "completed",
        },
    },
    {
        "type": "turn.completed",
        "usage": {
            "input_tokens": 1200,
            "cached_input_tokens": 800,
            "output_tokens": 150,
            "reasoning_output_tokens": 60,
            "total_tokens": 1350,
        },
    },
]

# The known schema drift (pre-v0.44.0): item_type + assistant_message.
LEGACY_ITEM = {
    "type": "item.completed",
    "item": {"id": "item_9", "item_type": "assistant_message", "text": "hi"},
}


def _fake_codex_script(tmp_path, events):
    """A stub 'codex' that replays the recorded fixture on stdout."""
    payload = json.dumps(events)
    script = tmp_path / "fake_codex.py"
    script.write_text(
        "import json, sys\n"
        f"for event in json.loads({payload!r}):\n"
        "    sys.stdout.write(json.dumps(event) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )
    return (sys.executable, str(script))


def _run_fixture(tmp_path, events=None):
    events = events or RECORDED_TRANSCRIPT
    adapter = CodexHarnessAdapter()
    config = CodexRunConfig(
        prompt="propose one candidate",
        workspace=str(tmp_path / "ws"),
        executable=_fake_codex_script(tmp_path, events),
    )
    started = adapter.start({"config": config})
    handle = started["handle"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state_events = list(adapter.events(handle))
        if any(e.get("type") == "turn.completed" for e in state_events):
            break
        time.sleep(0.02)
    return adapter, handle


def test_recorded_fixture_maps_into_common_contracts(tmp_path):
    adapter, handle = _run_fixture(tmp_path)
    events = list(adapter.events(handle))
    types = [event["type"] for event in events]
    assert types[0] == "thread.started"
    assert "turn.started" in types
    assert "turn.completed" in types
    # usage maps into the common usage contract
    usage = adapter.usage(handle)
    assert usage == [
        {
            "input_tokens": 1200,
            "cached_input_tokens": 800,
            "output_tokens": 150,
            "reasoning_output_tokens": 60,
            "total_tokens": 1350,
        }
    ]
    # file changes become candidate proposals, model-proposed only
    proposals = adapter.proposals(handle)
    assert len(proposals) == 1
    assert proposals[0]["kind"] == "candidate_change"
    assert proposals[0]["payload"]["authority"] == "model_proposed"
    adapter.close(handle)


def test_legacy_schema_drift_parses_defensively():
    normalized = normalize_codex_event(LEGACY_ITEM)
    assert normalized["payload"]["item_type"] == "agent_message"
    assert normalized["unknown"] is False


def test_unknown_native_events_are_tolerated():
    normalized = normalize_codex_event({"type": "telepathy.bloom"})
    assert normalized["unknown"] is True
    assert normalized["type"] == "telepathy.bloom"


def test_only_demonstrated_features_are_advertised():
    adapter = CodexHarnessAdapter()
    assert adapter.capabilities() == frozenset()
    assert UNSUPPORTED_OPTIONAL_FEATURES == frozenset(
        {"pause", "resume", "steering"}
    )
    identity = adapter.identity()
    assert identity["interface"] == CODEX_INTERFACE
    assert identity["schema_pin"] == CODEX_SCHEMA_PIN
    # unsupported optional capabilities are refused explicitly by the SDK
    handle = adapter.start(
        {
            "config": CodexRunConfig(
                prompt="x",
                workspace="/tmp/codex-contract",
                executable=_fake_codex_script(
                    Path("/tmp"), [{"type": "turn.completed", "usage": {}}]
                ),
            )
        }
    )["handle"]
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


def test_attach_is_honest_and_close_is_idempotent(tmp_path):
    adapter = CodexHarnessAdapter()
    config = CodexRunConfig(
        prompt="x",
        workspace=str(tmp_path / "ws"),
        executable=_fake_codex_script(tmp_path, [{"type": "turn.completed"}]),
    )
    with pytest.raises(HarnessContractError):
        adapter.attach(
            {"mode": ATTACH_MODE_NATIVE_RESUME, "config": config}
        )
    started = adapter.attach({"mode": ATTACH_MODE_CONTINUATION, "config": config})
    assert started["mode"] == ATTACH_MODE_CONTINUATION
    handle = started["handle"]
    adapter.close(handle)
    adapter.close(handle)  # idempotent
    with pytest.raises(HarnessLifecycleError):
        list(adapter.events(handle))


def test_denied_permissions_fail_never_hang_or_succeed(tmp_path):
    adapter = CodexHarnessAdapter()
    adapter, handle = _run_fixture(tmp_path)
    # a denial is recorded and the attempt outcome is failed, never success
    adapter.record_permission_denial(handle, "workspace write denied")
    assert adapter.attempt_outcome(handle) == "failed"
    # and the launch used explicit non-interactive policy: no approval
    # routing that could hang an unattended run
    state = adapter._runs[handle]
    assert state["config"].sandbox == "read-only"
    adapter.close(handle)


def test_adapter_executes_kernel_lifecycle(tmp_path):
    # the recorded lifecycle drives the kernel through the same decision
    # operations the built-in driver uses
    adapter, handle = _run_fixture(tmp_path)

    class CodexDriver:
        def __init__(self):
            self.calls = 0

        def run_attempt(self, plan, *, attempt_index, context):
            self.calls += 1
            outcome = adapter.attempt_outcome(handle)
            usage = adapter.usage(handle)
            metric = None
            if usage:
                metric = float(usage[-1]["total_tokens"])
            return AttemptResult(
                iteration=attempt_index, outcome=outcome, metric=metric
            )

    result = run_kernel_lifecycle(
        CodexDriver(),
        session={"max_iterations": 1},
        max_attempts=4,
    )
    assert result.completed is True
    assert result.attempts[0].outcome == "completed"
    assert result.attempts[0].metric == 1350.0
    adapter.close(handle)


def test_live_smoke_is_bounded_and_opt_in(tmp_path):
    """Opt-in live smoke: explicit version, auth mode, usage, teardown."""
    if not os.environ.get("AUTORESEARCH_CODEX_LIVE"):
        pytest.skip("Set AUTORESEARCH_CODEX_LIVE=1 for the bounded live smoke")
    import shutil

    if not shutil.which("codex"):
        pytest.skip("codex CLI is not installed")
    adapter = CodexHarnessAdapter()
    config = CodexRunConfig(
        prompt="Reply with the single word: pong",
        workspace=str(tmp_path / "live-ws"),
        auth_mode=os.environ.get("CODEX_AUTH_MODE", "unrecorded"),
        cleanup_deadline_s=10.0,
    )
    started = adapter.start({"config": config})
    handle = started["handle"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if any(
            e.get("type") in ("turn.completed", "turn.failed", "error")
            for e in adapter.events(handle)
        ):
            break
        time.sleep(0.1)
    outcome = adapter.attempt_outcome(handle)
    usage = adapter.usage(handle)
    # explicit teardown evidence
    started_close = time.monotonic()
    adapter.close(handle)
    assert time.monotonic() - started_close < 15.0
    print(
        "live-smoke:",
        json.dumps(
            {
                "interface": CODEX_INTERFACE,
                "schema_pin": CODEX_SCHEMA_PIN,
                "auth_mode": config.auth_mode,
                "outcome": outcome,
                "usage": usage,
            }
        ),
    )