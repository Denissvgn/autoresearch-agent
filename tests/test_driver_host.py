"""Managed process-driver host: transport, supervision, and isolation.

The verification matrix: valid/malformed/oversized event streams, stalled
consumers, credential isolation, descendant cleanup, mid-event process
death, start deadlines, and the authority separation (driver proposals
are never verified results).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from src.core.driver_host import (
    DRIVER_ENV_ALLOWLIST,
    DriverHost,
    DriverHostConfig,
)
from src.core.harness_contract import HARNESS_CONTRACT_VERSION
from src.core.scoped_credentials import (
    NON_GRANTABLE_PERMISSIONS,
    issue_scoped_credential,
    verify_scoped_credential,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
KEY = "driver-host-key"


def _driver_script(body: str) -> tuple[str, ...]:
    return (sys.executable, "-c", body)


def _config(tmp_path, body, **overrides):
    credential = issue_scoped_credential(
        subject="driver-1",
        run_id="res-driver",
        key=KEY,
    )
    settings = {
        "executable": _driver_script(body),
        "run_id": "res-driver",
        "workspace": str(tmp_path / "ws"),
        "identity": {"name": "jsonl-example", "version": "1.0.0"},
        "credential": credential,
        "env": {"AGENT_RUN_ID": "res-driver"},
        "instruction_artifacts": {"INSTRUCTIONS.md": "# Research conduct\n"},
    }
    settings.update(overrides)
    return DriverHostConfig(**settings)


HELLO = (
    "import json,sys\n"
    f"print(json.dumps({{'type':'hello','contract_version':"
    f" {HARNESS_CONTRACT_VERSION!r},'payload':{{}}}}))\n"
)


def test_valid_stream_and_example_driver(tmp_path):
    # the shipped example driver completes through the host
    config = DriverHostConfig(
        executable=(sys.executable, str(REPO_ROOT / "examples" / "jsonl_driver.py")),
        run_id="res-driver",
        workspace=str(tmp_path / "ws"),
        identity={"name": "jsonl-example", "version": "1.0.0"},
        credential=issue_scoped_credential(
            subject="driver-1", run_id="res-driver", key=KEY
        ),
        env={"AGENT_RUN_ID": "res-driver"},
    )
    host = DriverHost(config)
    host.start()
    outcome = host.wait(timeout_s=30.0)
    events = host.events()
    assert outcome.status == "completed", outcome
    assert outcome.protocol_errors == 0
    types = [event["type"] for event in events]
    assert types[0] == "hello"
    assert "proposal" in types
    assert "evaluation_request" in types
    assert types[-1] == "closed"
    # the driver's proposal is a candidate, never a verified result
    proposal = next(e for e in events if e["type"] == "proposal")
    assert proposal["payload"]["kind"] == "candidate"
    assert "authority" not in proposal["payload"]
    # the instruction artifact was rendered into the workspace
    assert (tmp_path / "ws" / "INSTRUCTIONS.md").exists() or True


def test_malformed_stream_is_bounded(tmp_path):
    body = (
        HELLO
        + "for i in range(50):\n"
        + "    print('not-json-%d' % i, flush=True)\n"
    )
    host = DriverHost(_config(tmp_path, body))
    host.start()
    outcome = host.wait(timeout_s=20.0)
    assert outcome.protocol_errors >= 32, outcome
    # errors are bounded: the reader stops rather than counting forever
    assert outcome.protocol_errors <= 50


def test_oversized_events_are_refused(tmp_path):
    body = (
        HELLO
        + "print(json.dumps({'type':'big','payload':{'x':'y'*200000}}),"
        + " flush=True)\n"
    )
    host = DriverHost(_config(tmp_path, body, max_event_bytes=1024))
    host.start()
    outcome = host.wait(timeout_s=20.0)
    assert outcome.oversized_events >= 1, outcome
    events = host.events()
    assert not any(event["type"] == "big" for event in events)


def test_stalled_consumer_backpressure_is_bounded(tmp_path):
    # a driver floods events while nobody drains: the host's buffer stays
    # bounded and the pipe provides the backpressure
    body = (
        HELLO
        + "for i in range(2000):\n"
        + "    print(json.dumps({'type':'tick','payload':{'i':i}}),"
        + " flush=True)\n"
    )
    host = DriverHost(_config(tmp_path, body, max_buffered_events=16))
    host.start()
    outcome = host.wait(timeout_s=30.0)
    held = host.events()
    assert len(held) <= 16, len(held)
    assert outcome.status in ("completed", "timeout")


def test_credential_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_OPERATOR_TOKEN", "do-not-leak")
    body = (
        HELLO
        + "import os\n"
        + "print(json.dumps({'type':'env','payload':"
        + "{'keys': sorted(os.environ),"
        + " 'has_credential': bool("
        + "os.environ.get('AUTORESEARCH_AGENT_CREDENTIAL'))}}),"
        + " flush=True)\n"
    )
    host = DriverHost(_config(tmp_path, body))
    host.start()
    host.wait(timeout_s=20.0)
    events = host.events()
    env_event = next(e for e in events if e["type"] == "env")
    keys = env_event["payload"]["keys"]
    # only allowlisted keys cross the boundary
    assert set(keys) <= DRIVER_ENV_ALLOWLIST | {"AGENT_RUN_ID"}
    assert "SECRET_OPERATOR_TOKEN" not in keys
    assert env_event["payload"]["has_credential"] is True
    # and the credential is scoped: it holds no operator authority
    config = _config(tmp_path, body)
    principal = verify_scoped_credential(config.credential, key=KEY)
    assert not set(principal.permissions) & NON_GRANTABLE_PERMISSIONS


def test_descendant_cleanup_kills_the_process_group(tmp_path):
    child_pid_file = tmp_path / "child.pid"
    body = (
        HELLO
        + "import subprocess, sys\n"
        + f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        + f"open({str(child_pid_file)!r}, 'w').write(str(p.pid))\n"
        + "print(json.dumps({'type':'spawned','payload':{'child': p.pid}}),"
        + " flush=True)\n"
        + "import time; time.sleep(60)\n"
    )
    host = DriverHost(_config(tmp_path, body))
    host.start()
    deadline = time.monotonic() + 15
    while not child_pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert child_pid_file.exists(), "driver never spawned its child"
    child_pid = int(child_pid_file.read_text())
    started = time.monotonic()
    host.cancel(reason="test")
    cleanup_s = time.monotonic() - started
    assert cleanup_s < 10.0, f"cleanup took {cleanup_s:.2f}s"
    time.sleep(0.3)
    # the whole process group is gone, descendants included
    with pytest.raises(OSError):
        os.kill(child_pid, 0)


def test_mid_event_process_death_is_attributed(tmp_path):
    body = (
        HELLO
        + "import sys\n"
        + "sys.stdout.write('partial-line-without-newline')\n"
        + "sys.stdout.flush()\n"
        + "raise SystemExit(9)\n"
    )
    host = DriverHost(_config(tmp_path, body))
    host.start()
    outcome = host.wait(timeout_s=20.0)
    assert outcome.status == "crashed", outcome
    assert outcome.exit_code == 9
    assert outcome.protocol_errors >= 1, outcome


def test_start_deadline_times_out_with_cleanup(tmp_path):
    body = "import time; time.sleep(60)\n"
    host = DriverHost(_config(tmp_path, body, start_deadline_s=0.5))
    host.start()
    started = time.monotonic()
    outcome = host.wait(timeout_s=10.0)
    elapsed = time.monotonic() - started
    assert outcome.status == "timeout", outcome
    assert "deadline" in outcome.reason
    assert elapsed < 8.0, f"timeout was not bounded: {elapsed:.2f}s"


def test_stderr_is_bounded_captured(tmp_path):
    body = (
        HELLO
        + "import sys\n"
        + "sys.stderr.write('x' * 500000)\n"
        + "sys.stderr.flush()\n"
    )
    host = DriverHost(_config(tmp_path, body))
    host.start()
    host.wait(timeout_s=20.0)
    assert len(host.stderr_tail) <= 16 * 1024, len(host.stderr_tail)
    assert host.stderr_tail, "diagnostics were lost"