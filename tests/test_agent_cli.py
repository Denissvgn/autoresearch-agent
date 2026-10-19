"""Attached-agent CLI: schemas, exit codes, redaction, reconnect.

The workflow is proven from an external program (the shell example)
against a real server, and the installed-package smoke runs outside the
checkout. Credentials never appear in arguments or logs.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from src.agent_cli import (
    EXIT_AUTH,
    EXIT_CODES,
    EXIT_CONFLICT,
    EXIT_LIMIT,
    EXIT_OK,
    EXIT_TIMEOUT,
    EXIT_TRANSPORT,
    EXIT_USAGE,
    SCHEMA_ERROR,
    SCHEMA_RESULT,
    set_transport,
)
from src.api.agent import init as init_agent
from src.api.agent import router as agent_router
from src.core.scoped_credentials import (
    PERM_EVALUATE,
    PERM_LIFECYCLE,
    PERM_READ,
    PERM_SUBMIT,
    issue_scoped_credential,
)
from src.core.state_store import SQLiteStateStore

KEY = "cli-credential-key"
RUN_ID = "res-cli-1"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _credential():
    return issue_scoped_credential(
        subject="agent-1",
        run_id=RUN_ID,
        tenant_id="tenant-a",
        key=KEY,
        permissions=(PERM_READ, PERM_SUBMIT, PERM_EVALUATE, PERM_LIFECYCLE),
    )


class _Probe:
    def request_pause(self, research_id):
        pass

    def request_resume(self, research_id):
        pass

    def request_stop(self, research_id):
        pass


def _app_and_store(tmp_path):
    from fastapi import FastAPI

    async def _build():
        store = SQLiteStateStore(str(tmp_path / "state.db"))
        await store.initialize()
        return store

    import asyncio

    store = asyncio.run(_build())
    app = FastAPI()
    app.include_router(agent_router, prefix="/api/v1")
    init_agent(store, orchestrator=_Probe(), credential_key=KEY)
    return app, store


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    app, _store = _app_and_store(tmp_path)
    set_transport(httpx.ASGITransport(app=app))
    monkeypatch.setenv("AUTORESEARCH_AGENT_CREDENTIAL", _credential())
    monkeypatch.setenv("AUTORESEARCH_API_URL", "http://test")
    yield
    set_transport(None)


def _run_cli(argv):
    import contextlib
    import io

    from src.cli import main

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(argv)
    payload = json.loads(out.getvalue()) if out.getvalue().strip() else None
    return code, payload


def test_json_envelopes_and_schema_fields(cli_env, tmp_path):
    code, payload = _run_cli(
        ["agent", "run", "create", "--instrument", "EURUSD"]
    )
    assert code == EXIT_OK
    assert set(payload) == set(SCHEMA_RESULT)
    assert payload["ok"] is True
    assert payload["data"]["run_id"] == RUN_ID

    code, payload = _run_cli(["agent", "constraints", "--run", RUN_ID])
    assert code == EXIT_OK
    assert payload["data"]["max_budget_usd"] == 7.5

    candidate = tmp_path / "c.txt"
    candidate.write_text("knob: 0.42")
    code, payload = _run_cli(
        [
            "agent",
            "submit",
            "--run",
            RUN_ID,
            "--content-file",
            str(candidate),
            "--idempotency-key",
            "k1",
        ]
    )
    assert code == EXIT_OK
    assert payload["data"]["authority"] == "model_proposed"

    for argv in (
        ["agent", "evaluate", "--run", RUN_ID],
        ["agent", "results", "--run", RUN_ID],
        ["agent", "preview", "--run", RUN_ID],
        ["agent", "lifecycle", "--run", RUN_ID, "pause"],
    ):
        code, payload = _run_cli(argv)
        assert code == EXIT_OK, (argv, payload)
        assert payload["ok"] is True

    code, payload = _run_cli(["agent", "events", "--run", RUN_ID])
    assert code == EXIT_OK
    assert set(payload["data"]) == set(SCHEMA_EVENTS_DATA)


SCHEMA_EVENTS_DATA = {"run_id", "events", "cursor"}


def test_error_envelope_and_exit_codes(cli_env, monkeypatch, tmp_path):
    # missing credential reference -> usage (2)
    monkeypatch.delenv("AUTORESEARCH_AGENT_CREDENTIAL")
    code, payload = _run_cli(["agent", "results", "--run", RUN_ID])
    assert code == EXIT_USAGE
    assert set(payload) == set(SCHEMA_ERROR)
    assert payload["error"]["code"] == "usage"

    # a credential for another run is refused -> auth (3)
    monkeypatch.setenv(
        "AUTORESEARCH_AGENT_CREDENTIAL",
        issue_scoped_credential(
            subject="agent-1", run_id="res-other", key=KEY
        ),
    )
    code, payload = _run_cli(["agent", "results", "--run", RUN_ID])
    assert code == EXIT_AUTH
    assert payload["error"]["code"] == "auth"

    # the published exit-code vocabulary is stable
    assert EXIT_CODES == {
        EXIT_OK: "success",
        1: "error",
        EXIT_USAGE: "usage",
        EXIT_AUTH: "auth",
        EXIT_CONFLICT: "conflict",
        EXIT_LIMIT: "limit",
        EXIT_TIMEOUT: "timeout",
        EXIT_TRANSPORT: "transport",
    }


def test_credentials_never_leak_in_arguments_or_logs(cli_env, capsys):
    # there is no credential argument to leak: only references exist
    import argparse

    from src.agent_cli import build_agent_parser

    def all_options(parser):
        options = set()
        for action in parser._actions:
            options.update(action.option_strings)
            if isinstance(action, argparse._SubParsersAction):
                for sub_parser in action.choices.values():
                    options.update(all_options(sub_parser))
        return options

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build_agent_parser(sub)
    options = all_options(parser)
    assert "--credential-env" in options
    assert "--credential-file" in options
    # a raw token flag does not exist anywhere in the tree
    assert "--credential" not in options

    # even a transport error echoing the token is redacted
    from src.agent_client import AgentClient, redact

    credential = os.environ["AUTORESEARCH_AGENT_CREDENTIAL"]
    assert "***" in redact(f"boom {credential}", credential)
    client = AgentClient(
        base_url="http://127.0.0.1:1",
        credential=credential,
        timeout_s=0.5,
    )
    try:
        import asyncio

        asyncio.run(client.results(RUN_ID))
    except Exception as exc:  # noqa: BLE001 — any transport failure
        assert credential not in str(exc)
    else:  # pragma: no cover — the port is closed by definition
        raise AssertionError("expected a transport failure")
    finally:
        asyncio.run(client.close())


def test_event_cursor_persists_across_interruption(cli_env, tmp_path):
    cursor_file = tmp_path / "cursor.json"
    code, payload = _run_cli(
        [
            "agent",
            "events",
            "--run",
            RUN_ID,
            "--cursor-file",
            str(cursor_file),
        ]
    )
    assert code == EXIT_OK
    assert payload["data"]["cursor"] == 0
    assert json.loads(cursor_file.read_text())["cursor"] == 0

    # an event arrives while the consumer is interrupted
    _run_cli(["agent", "evaluate", "--run", RUN_ID])

    # reconnect resumes from the persisted cursor
    code, payload = _run_cli(
        [
            "agent",
            "events",
            "--run",
            RUN_ID,
            "--cursor-file",
            str(cursor_file),
        ]
    )
    assert code == EXIT_OK
    assert payload["data"]["events"], payload
    assert payload["data"]["cursor"] >= 1


def test_bounded_wait_times_out(cli_env):
    started = time.monotonic()
    code, payload = _run_cli(
        [
            "agent",
            "evaluate",
            "--run",
            RUN_ID,
            "--wait",
            "--timeout",
            "0.4",
        ]
    )
    elapsed = time.monotonic() - started
    assert code == EXIT_TIMEOUT
    assert payload["error"]["code"] == "timeout"
    assert elapsed < 5.0, f"wait was not bounded: {elapsed:.2f}s"


def test_external_driver_example_completes_workflow(tmp_path):
    """The shell driver knows only the CLI and its exit codes."""
    app, store = _app_and_store(tmp_path)

    import uvicorn

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "test server did not start"

    env = {
        **os.environ,
        "AUTORESEARCH_API_URL": f"http://127.0.0.1:{port}",
        "AUTORESEARCH_AGENT_CREDENTIAL": _credential(),
        "AGENT_RUN_ID": RUN_ID,
        "PYTHONPATH": str(REPO_ROOT),
    }
    result = subprocess.run(
        ["sh", str(REPO_ROOT / "examples" / "attached_agent_driver.sh")],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    # the credential never appears in the driver's output
    assert env["AUTORESEARCH_AGENT_CREDENTIAL"] not in result.stdout
    assert env["AUTORESEARCH_AGENT_CREDENTIAL"] not in result.stderr
    server.should_exit = True
    thread.join(timeout=10)


def test_installed_cli_smoke_outside_checkout(tmp_path):
    """Installed-layout smoke for the CLI (env-gated on release artifacts)."""
    dist_dir = os.environ.get("AUTORESEARCH_DIST_DIR")
    if not dist_dir:
        pytest.skip("Set AUTORESEARCH_DIST_DIR to freshly built artifacts")
    import zipfile

    wheels = list(Path(dist_dir).glob("*.whl"))
    assert len(wheels) == 1, wheels
    installed = tmp_path / "installed"
    with zipfile.ZipFile(wheels[0]) as archive:
        archive.extractall(installed)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    probe = (
        "import sys\n"
        f"sys.path.insert(0, {str(installed)!r})\n"
        "from src.cli import main\n"
        "try:\n"
        "    main(['agent', 'run', '--help'])\n"
        "except SystemExit as exc:\n"
        "    assert exc.code == 0, exc.code\n"
        "print('cli-smoke-ok')\n"
    )
    script = scratch / "probe.py"
    script.write_text(probe)
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(scratch),
    )
    assert result.returncode == 0, result.stderr
    assert "cli-smoke-ok" in result.stdout