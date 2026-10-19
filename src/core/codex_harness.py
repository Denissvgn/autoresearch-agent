"""Codex harness adapter: the first independent external harness.

Interface choice (rechecked against the official non-interactive docs at
implementation time): ``codex exec --json`` — the least complex officially
supported structured interface. Its stdout is a JSONL event stream
(``thread.started``, ``turn.started``, ``item.*``, ``turn.completed`` with
usage, ``turn.failed``, ``error``) with progress on stderr.

Version pinning: the stream carries no schema version, so the adapter
pins the documented field shape (post-v0.44.0: ``item.type`` and
``agent_message``), parses defensively through the normalizer, records
``codex --version`` and the transport at start, and refuses to run live
without the caller's opt-in.

Demonstrated features only: the exec transport demonstrates no native
pause/resume, so neither is advertised — the SDK refuses them explicitly
rather than pretending. Cancellation is process-group supervision, not a
native feature claim. The harness's own tools are ordinary tool access:
they are never evaluator execution and never promotion authority.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Optional

from src.core.harness_contract import (
    ATTACH_MODE_CONTINUATION,
    HARNESS_CONTRACT_VERSION,
    HarnessContractError,
    HarnessLifecycleError,
)

CODEX_INTERFACE = "codex exec --json"
CODEX_SCHEMA_PIN = "codex-exec-jsonl.item-type.v0.44.0"
CODEX_EVENT_TYPES = frozenset(
    {
        "thread.started",
        "turn.started",
        "item.started",
        "item.updated",
        "item.completed",
        "turn.completed",
        "turn.failed",
        "error",
    }
)
CODEX_ITEM_TYPES = frozenset(
    {
        "agent_message",
        "command_execution",
        "reasoning",
        "file_change",
        "mcp_tool_call",
        "web_search",
        "plan_update",
    }
)

# Optional features this transport does not demonstrate: recorded, never
# faked. The harness SDK refuses them explicitly.
UNSUPPORTED_OPTIONAL_FEATURES = frozenset({"pause", "resume", "steering"})

MAX_EVENT_BYTES = 256 * 1024
CLEANUP_DEADLINE_S = 5.0


@dataclass
class CodexRunConfig:
    """One supervised ``codex exec`` run."""

    prompt: str
    workspace: str
    executable: tuple[str, ...] = ("codex", "exec", "--json")
    sandbox: str = "read-only"
    version: str = "unrecorded"
    auth_mode: str = "unrecorded"
    max_event_bytes: int = MAX_EVENT_BYTES
    cleanup_deadline_s: float = CLEANUP_DEADLINE_S
    env: Mapping[str, str] = field(default_factory=dict)


def normalize_codex_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Map one native Codex event into the common harness contracts.

    Defensive across the known schema drift: both ``item.type`` (current)
    and ``item_type`` (pre-v0.44.0) are accepted; unknown shapes are
    surfaced as unknown events, never dropped and never trusted.
    """
    event_type = str(raw.get("type") or "")
    payload: dict[str, Any] = {}
    unknown = event_type not in CODEX_EVENT_TYPES

    if event_type == "thread.started":
        payload = {"thread_id": raw.get("thread_id")}
    elif event_type == "turn.completed":
        payload = {"usage": dict(raw.get("usage") or {})}
    elif event_type == "turn.failed":
        payload = {
            "error": raw.get("error") or raw.get("message") or "turn failed"
        }
    elif event_type == "error":
        payload = {"error": raw.get("message") or raw.get("error") or "error"}
    elif event_type.startswith("item."):
        item = dict(raw.get("item") or {})
        item_type = str(item.get("type") or item.get("item_type") or "")
        if item_type == "assistant_message":
            # pre-v0.44.0 vocabulary: canonicalize, never lose the value
            item_type = "agent_message"
        payload = {
            "item_id": item.get("id"),
            "item_type": item_type,
            "status": item.get("status"),
            "text": item.get("text"),
            "command": item.get("command"),
            "changes": item.get("changes"),
        }
        unknown = unknown or item_type not in CODEX_ITEM_TYPES

    return {
        "type": event_type or "unknown",
        "payload": payload,
        "unknown": unknown,
    }


def map_usage(usage: Mapping[str, Any]) -> dict[str, Any]:
    """The Codex usage object into the common usage contract."""
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(usage.get("cached_input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_output_tokens": int(
            usage.get("reasoning_output_tokens") or 0
        ),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def map_candidate_changes(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """File-change items become candidate proposals (model-proposed)."""
    proposals = []
    for event in events:
        payload = event.get("payload") or {}
        if event.get("type") == "item.completed" and payload.get(
            "item_type"
        ) == "file_change":
            proposals.append(
                {
                    "proposal_id": str(payload.get("item_id") or "change"),
                    "kind": "candidate_change",
                    "target": "workspace",
                    "payload": {
                        "changes": payload.get("changes"),
                        "authority": "model_proposed",
                    },
                }
            )
    return proposals


class CodexHarnessAdapter:
    """The Codex harness behind the common contracts."""

    def __init__(self, *, name: str = "codex", version: str = "1.0.0") -> None:
        self._name = name
        self._version = version
        self._next_handle = 0
        self._runs: dict[str, dict[str, Any]] = {}

    # -- HarnessAdapter (harness contract) ----------------------------
    def identity(self) -> Mapping[str, Any]:
        return {
            "name": self._name,
            "version": self._version,
            "contract_version": HARNESS_CONTRACT_VERSION,
            "interface": CODEX_INTERFACE,
            "schema_pin": CODEX_SCHEMA_PIN,
            "permissions": {"stream": True, "cancel": True},
        }

    def capabilities(self) -> frozenset[str]:
        # only demonstrated native features are advertised; the exec
        # transport demonstrates no native pause/resume/steering
        return frozenset()

    def start(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        config = request.get("config")
        if not isinstance(config, CodexRunConfig):
            raise HarnessContractError(
                "codex runs require a CodexRunConfig in the request"
            )
        self._next_handle += 1
        handle = f"codex-h{self._next_handle}"
        state = {
            "config": config,
            "events": [],
            "process": None,
            "reader": None,
            "cancelled": False,
            "denied": False,
        }
        self._runs[handle] = state
        self._launch(state)
        return {"handle": handle, "mode": ATTACH_MODE_CONTINUATION}

    def attach(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        mode = str(request.get("mode") or ATTACH_MODE_CONTINUATION)
        if mode != ATTACH_MODE_CONTINUATION:
            # the exec transport demonstrates no native transcript resume
            raise HarnessContractError(
                "codex exec has no demonstrated native transcript resume; "
                "cross-run rejoin is continuation only"
            )
        return self.start(request)

    def events(self, handle: str) -> Iterator[Mapping[str, Any]]:
        state = self._runs.get(handle)
        if state is None:
            raise HarnessLifecycleError(
                f"no open handle {handle!r} for the event stream"
            )
        return iter(list(state["events"]))

    def cancel(self, handle: str) -> None:
        state = self._require_open(handle, "cancel")
        state["cancelled"] = True
        process = state.get("process")
        if process is not None and process.poll() is None:
            self._kill_group(process, state["config"].cleanup_deadline_s)

    def close(self, handle: str) -> None:
        # idempotent teardown
        state = self._runs.pop(handle, None)
        if state is not None:
            process = state.get("process")
            if process is not None and process.poll() is None:
                self._kill_group(process, state["config"].cleanup_deadline_s)

    def proposals(self, handle: str) -> list[dict[str, Any]]:
        state = self._require_open(handle, "proposals")
        return map_candidate_changes(list(state["events"]))

    def usage(self, handle: str) -> list[dict[str, Any]]:
        state = self._require_open(handle, "usage")
        return [
            map_usage((event.get("payload") or {}).get("usage") or {})
            for event in state["events"]
            if event.get("type") == "turn.completed"
        ]

    def record_permission_denial(self, handle: str, detail: str) -> None:
        """A denied permission is an explicit failure, never success.

        Unattended runs must not hang on approval: the exec transport is
        launched with explicit sandbox policy, and a denial is recorded as
        a failed attempt outcome.
        """
        state = self._require_open(handle, "permission")
        state["denied"] = True
        state["events"].append(
            {
                "type": "error",
                "payload": {"error": f"permission denied: {detail}"},
                "unknown": False,
            }
        )

    def attempt_outcome(self, handle: str) -> str:
        """The run's outcome in the kernel's vocabulary."""
        state = self._require_open(handle, "outcome")
        if state["denied"]:
            return "failed"
        for event in state["events"]:
            if event.get("type") in ("turn.failed", "error"):
                return "failed"
        return "completed"

    # -- the supervised codex run -------------------------------------
    def _launch(self, state: dict[str, Any]) -> None:
        config: CodexRunConfig = state["config"]
        os.makedirs(config.workspace, exist_ok=True)
        env = dict(os.environ)
        env.update({k: str(v) for k, v in config.env.items()})
        command = list(config.executable) + [
            "--sandbox",
            config.sandbox,
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
        ]
        process = subprocess.Popen(
            command,
            cwd=config.workspace,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        state["process"] = process
        assert process.stdin is not None
        process.stdin.write(config.prompt.encode("utf-8"))
        process.stdin.close()
        reader = threading.Thread(
            target=self._read_stream, args=(process, state), daemon=True
        )
        state["reader"] = reader
        reader.start()

    def _read_stream(self, process: Any, state: dict[str, Any]) -> None:
        config: CodexRunConfig = state["config"]
        assert process.stdout is not None
        buffer = b""
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self._handle_line(line, state, config)
            if len(buffer) > config.max_event_bytes:
                buffer = buffer[-config.max_event_bytes :]
        if buffer.strip():
            self._handle_line(buffer, state, config)

    def _handle_line(
        self, line: bytes, state: dict[str, Any], config: CodexRunConfig
    ) -> None:
        if len(line) > config.max_event_bytes:
            return
        try:
            raw = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(raw, dict):
            return
        state["events"].append(normalize_codex_event(raw))

    def _kill_group(self, process: Any, deadline_s: float) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + deadline_s
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return
            time.sleep(0.02)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=deadline_s)

    def _require_open(self, handle: str, op: str) -> dict[str, Any]:
        state = self._runs.get(handle)
        if state is None:
            raise HarnessLifecycleError(
                f"{op} on unknown or closed handle {handle!r}"
            )
        return state
