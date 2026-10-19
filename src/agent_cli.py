"""Attached-agent CLI: machine-readable commands over the agent API.

Every command prints one JSON object on stdout and uses a stable exit
code. Credentials are referenced (an environment variable or a file),
never passed as arguments, and error output is redacted. Bounded waits
and a persisted event cursor make the workflow safe to interrupt and
reconnect.

Exit codes (stable, published):
    0  success
    1  generic error
    2  usage or validation refusal (nothing was written)
    3  authentication/authorization refused
    4  idempotency conflict
    5  size or rate limit refused
    6  bounded wait timed out
    7  transport or API failure
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

from src.agent_client import (
    DEFAULT_CREDENTIAL_ENV,
    DEFAULT_TIMEOUT_S,
    AgentAuthError,
    AgentClient,
    AgentClientError,
    AgentConflictError,
    AgentLimitError,
    resolve_credential,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_CONFLICT = 4
EXIT_LIMIT = 5
EXIT_TIMEOUT = 6
EXIT_TRANSPORT = 7

EXIT_CODES = {
    EXIT_OK: "success",
    EXIT_ERROR: "error",
    EXIT_USAGE: "usage",
    EXIT_AUTH: "auth",
    EXIT_CONFLICT: "conflict",
    EXIT_LIMIT: "limit",
    EXIT_TIMEOUT: "timeout",
    EXIT_TRANSPORT: "transport",
}

# The published JSON envelopes (output schemas) for machine consumers.
SCHEMA_RESULT = {
    "ok": "bool",
    "data": "object (command-specific)",
}
SCHEMA_ERROR = {
    "ok": "bool",
    "error": {"code": "string (stable)", "message": "string", "status": "int|null"},
}
SCHEMA_EVENTS = {
    "ok": "bool",
    "data": {
        "run_id": "string",
        "events": "array of {event_id, type, sequence, payload}",
        "cursor": "int",
    },
}


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def _ok(data: dict[str, Any]) -> int:
    _emit({"ok": True, "data": data})
    return EXIT_OK


def _fail(code: str, message: str, status: Optional[int] = None) -> int:
    _emit(
        {
            "ok": False,
            "error": {"code": code, "message": message, "status": status},
        }
    )
    return {
        "auth": EXIT_AUTH,
        "conflict": EXIT_CONFLICT,
        "limit": EXIT_LIMIT,
        "timeout": EXIT_TIMEOUT,
        "usage": EXIT_USAGE,
        "transport": EXIT_TRANSPORT,
    }.get(code, EXIT_ERROR)


def build_agent_parser(sub: Any) -> None:
    """Register the ``agent`` command group on the CLI's subparsers."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--credential-env",
        default=DEFAULT_CREDENTIAL_ENV,
        help="environment variable holding the scoped credential",
    )
    common.add_argument(
        "--credential-file",
        default=None,
        help="file holding the scoped credential (never pass it on argv)",
    )
    common.add_argument(
        "--base-url",
        default=None,
        help="API base URL (default: $AUTORESEARCH_API_URL)",
    )
    common.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help="bounded wait / request timeout in seconds",
    )
    agent = sub.add_parser(
        "agent", help="attached-agent research workflow (machine-readable)"
    )
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)

    run = agent_sub.add_parser(
        "run", help="create or attach a run", parents=[common]
    )
    run.add_argument("mode", choices=["create", "attach"])
    run.add_argument("--instrument", default="EURUSD")
    run.add_argument("--timeframe", default="1h")
    run.add_argument("--max-iterations", type=int, default=3)
    run.add_argument("--max-budget-usd", type=float, default=7.5)

    constraints = agent_sub.add_parser(
        "constraints", help="run constraints", parents=[common]
    )
    constraints.add_argument("--run", required=True)

    submit = agent_sub.add_parser(
        "submit", help="stage one candidate", parents=[common]
    )
    submit.add_argument("--run", required=True)
    submit.add_argument("--content-file", required=True)
    submit.add_argument("--idempotency-key", required=True)

    evaluate = agent_sub.add_parser(
        "evaluate", help="request evaluation", parents=[common]
    )
    evaluate.add_argument("--run", required=True)
    evaluate.add_argument(
        "--wait",
        action="store_true",
        help="wait (bounded by --timeout) for a result",
    )

    results = agent_sub.add_parser(
        "results", help="inspect results", parents=[common]
    )
    results.add_argument("--run", required=True)

    preview = agent_sub.add_parser(
        "preview", help="promotion preview", parents=[common]
    )
    preview.add_argument("--run", required=True)

    lifecycle = agent_sub.add_parser(
        "lifecycle", help="pause/resume/stop", parents=[common]
    )
    lifecycle.add_argument("--run", required=True)
    lifecycle.add_argument("action", choices=["pause", "resume", "stop"])

    events = agent_sub.add_parser(
        "events", help="poll events (reconnect)", parents=[common]
    )
    events.add_argument("--run", required=True)
    events.add_argument(
        "--cursor-file",
        default=None,
        help="persisted cursor (read and written across invocations)",
    )


def _client(args: argparse.Namespace) -> AgentClient:
    import os

    credential = resolve_credential(
        credential_env=args.credential_env,
        credential_file=args.credential_file,
    )
    base_url = args.base_url or os.environ.get(
        "AUTORESEARCH_API_URL", "http://127.0.0.1:8000"
    )
    return AgentClient(
        base_url=base_url,
        credential=credential,
        timeout_s=args.timeout,
        transport=_TRANSPORT,
    )


# Set by tests (and the conformance fixture) to run against an in-process
# app; production uses real HTTP against --base-url.
_TRANSPORT = None


def set_transport(transport: Any) -> None:
    """Inject an httpx transport (tests and the conformance fixture)."""
    global _TRANSPORT
    _TRANSPORT = transport


def _load_cursor(path: Optional[str]) -> int:
    if not path:
        return 0
    cursor_path = Path(path)
    if not cursor_path.exists():
        return 0
    try:
        return int(json.loads(cursor_path.read_text()).get("cursor", 0))
    except (ValueError, json.JSONDecodeError):
        return 0


def _save_cursor(path: Optional[str], cursor: int) -> None:
    if path:
        Path(path).write_text(json.dumps({"cursor": int(cursor)}))


async def cmd_agent(args: argparse.Namespace) -> int:
    try:
        client = _client(args)
    except AgentAuthError as exc:
        return _fail("usage", f"credential reference failed: {exc}")
    except OSError as exc:
        return _fail("usage", f"credential reference failed: {exc}")
    try:
        return await _dispatch(client, args)
    except AgentAuthError as exc:
        return _fail("auth", str(exc), exc.status)
    except AgentConflictError as exc:
        return _fail("conflict", str(exc), exc.status)
    except AgentLimitError as exc:
        return _fail("limit", str(exc), exc.status)
    except AgentClientError as exc:
        return _fail("transport", str(exc), exc.status)
    finally:
        await client.close()


async def _dispatch(client: AgentClient, args: argparse.Namespace) -> int:
    command = args.agent_command
    if command == "run":
        data = await client.create_or_attach(
            mode=args.mode,
            instrument=args.instrument,
            timeframe=args.timeframe,
            max_iterations=args.max_iterations,
            max_budget_usd=args.max_budget_usd,
        )
        return _ok(data)
    if command == "constraints":
        return _ok(await client.constraints(args.run))
    if command == "submit":
        content = Path(args.content_file).read_bytes()
        data = await client.submit_candidate(
            args.run,
            content=content,
            idempotency_key=args.idempotency_key,
        )
        return _ok(data)
    if command == "evaluate":
        data = await client.request_evaluation(args.run)
        if not args.wait:
            return _ok(data)
        return await _wait_for_results(client, args.run, args.timeout)
    if command == "results":
        return _ok(await client.results(args.run))
    if command == "preview":
        return _ok(await client.promotion_preview(args.run))
    if command == "lifecycle":
        return _ok(await client.lifecycle(args.run, action=args.action))
    if command == "events":
        cursor = _load_cursor(args.cursor_file)
        data = await client.events(args.run, cursor=cursor)
        _save_cursor(args.cursor_file, data.get("cursor", cursor))
        return _ok(data)
    return _fail("usage", f"unknown agent command: {command}")


async def _wait_for_results(
    client: AgentClient, run_id: str, timeout_s: float
) -> int:
    """Bounded wait: poll for a result until the deadline, never forever."""
    deadline = time.monotonic() + max(0.0, timeout_s)
    while True:
        data = await client.results(run_id)
        if data.get("results"):
            return _ok(data)
        if time.monotonic() >= deadline:
            return _fail(
                "timeout",
                f"no result within {timeout_s}s",
            )
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))


AGENT_COMMANDS = {"agent": cmd_agent}