"""Claude Code harness adapter: the second independent external harness.

Interface selection (rechecked against the current official Claude Code
programmatic documentation at implementation time): the ``claude -p``
non-interactive CLI with ``--output-format stream-json`` — the Agent SDK
CLI's structured event stream. Human-oriented terminal prose is never
parsed; only the structured events are.

Pinned shape (``claude-code-stream-json.system-init.v2``): ``system/init``
carries the session identifier and tool/permission configuration,
``assistant`` events carry content blocks (text, tool_use) and Anthropic
usage, and ``result`` carries usage, total cost, permission denials, and
the session identifier. Authentication and hosting: the harness's own
Anthropic credential (``ANTHROPIC_API_KEY`` or an interactive login) runs
in a per-run ``CLAUDE_CONFIG_DIR`` so session state is adapter-owned and
isolated per hosted run — never the platform's operator credentials.

Qualified resume: native session resume IS a documented supported feature
(``--resume <session_id>`` within the same config directory), so it is
advertised with that exact qualification; pause and steering are not
demonstrated and are refused explicitly. Cancellation is process-group
supervision. The harness's own tools are ordinary tool access: never
evaluator execution and never promotion authority.
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
    ATTACH_MODE_NATIVE_RESUME,
    CAPABILITY_RESUME,
    HARNESS_CONTRACT_VERSION,
    HarnessContractError,
    HarnessLifecycleError,
)

CLAUDE_INTERFACE = "claude -p --output-format stream-json"
CLAUDE_SCHEMA_PIN = "claude-code-stream-json.system-init.v2"
CLAUDE_EVENT_TYPES = frozenset({"system", "user", "assistant", "result"})
CLAUDE_CONTENT_TYPES = frozenset({"text", "tool_use", "thinking"})

# Demonstrated for this transport: native session resume only.
UNSUPPORTED_OPTIONAL_FEATURES = frozenset({"pause", "steering"})

MAX_EVENT_BYTES = 256 * 1024
CLEANUP_DEADLINE_S = 5.0


@dataclass
class ClaudeRunConfig:
    """One supervised ``claude -p`` run."""

    prompt: str
    workspace: str
    config_dir: str
    executable: tuple[str, ...] = (
        "claude",
        "-p",
        "--output-format",
        "stream-json",
    )
    allowed_tools: str = "Read"
    permission_mode: str = "default"
    auth_env: Mapping[str, str] = field(default_factory=dict)
    max_event_bytes: int = MAX_EVENT_BYTES
    cleanup_deadline_s: float = CLEANUP_DEADLINE_S
    resume_session_id: Optional[str] = None


def normalize_claude_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Map one structured Claude Code event into the common contracts."""
    event_type = str(raw.get("type") or "")
    payload: dict[str, Any] = {}
    unknown = event_type not in CLAUDE_EVENT_TYPES

    if event_type == "system":
        payload = {
            "subtype": raw.get("subtype"),
            "session_id": raw.get("session_id"),
            "tools": raw.get("tools"),
            "permission_mode": raw.get("permissionMode"),
        }
    elif event_type == "assistant":
        message = dict(raw.get("message") or {})
        content = []
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "")
            content.append(
                {
                    "type": block_type,
                    "text": block.get("text"),
                    "name": block.get("name"),
                    "input": block.get("input"),
                    "id": block.get("id"),
                }
            )
            unknown = unknown or block_type not in CLAUDE_CONTENT_TYPES
        payload = {
            "content": content,
            "usage": dict(message.get("usage") or {}),
        }
    elif event_type == "result":
        payload = {
            "subtype": raw.get("subtype"),
            "session_id": raw.get("session_id"),
            "usage": dict(raw.get("usage") or {}),
            "total_cost_usd": raw.get("total_cost_usd"),
            "permission_denials": list(raw.get("permission_denials") or []),
            "is_error": bool(raw.get("is_error", False)),
        }
    elif event_type == "user":
        payload = {"role": "user"}
    else:
        payload = {"raw_type": event_type}

    return {
        "type": event_type or "unknown",
        "payload": payload,
        "unknown": unknown,
    }


def map_usage(usage: Mapping[str, Any]) -> dict[str, Any]:
    """The Anthropic usage shape into the common usage contract.

    ``cached_input_tokens`` sums the two Anthropic cache counters so no
    usage is lost; the native counters remain in ``native``.
    """
    cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cache_creation + cache_read,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": 0,
        "total_tokens": (
            input_tokens + cache_creation + cache_read + output_tokens
        ),
        "native": dict(usage),
    }


def map_candidate_changes(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Tool-use content blocks become candidate proposals (model-proposed)."""
    proposals = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in (event.get("payload") or {}).get("content") or []:
            if block.get("type") != "tool_use":
                continue
            proposals.append(
                {
                    "proposal_id": str(block.get("id") or "tool-use"),
                    "kind": "candidate_change",
                    "target": str(block.get("name") or "tool"),
                    "payload": {
                        "input": block.get("input"),
                        "authority": "model_proposed",
                    },
                }
            )
    return proposals


class ClaudeCodeHarnessAdapter:
    """The Claude Code harness behind the common contracts."""

    def __init__(self, *, name: str = "claude-code", version: str = "1.0.0") -> None:
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
            "interface": CLAUDE_INTERFACE,
            "schema_pin": CLAUDE_SCHEMA_PIN,
            "permissions": {"stream": True, "cancel": True, "resume": True},
        }

    def capabilities(self) -> frozenset[str]:
        # resume is demonstrated (native --resume within the same config
        # directory); pause and steering are not and stay unadvertised
        return frozenset({CAPABILITY_RESUME})

    def resume(self, handle: str, *, session_id: Optional[str] = None) -> str:
        """Qualified native resume: same harness, same config directory.

        Returns the session id the next run must resume. Cross-harness
        transcript resume is never claimed — that is continuation.
        """
        state = self._require_open(handle, "resume")
        target = session_id or state.get("session_id")
        if not target:
            raise HarnessContractError(
                "native resume requires a recorded session id"
            )
        state["resume_session_id"] = target
        return target

    def start(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        config = request.get("config")
        if not isinstance(config, ClaudeRunConfig):
            raise HarnessContractError(
                "claude runs require a ClaudeRunConfig in the request"
            )
        self._next_handle += 1
        handle = f"claude-h{self._next_handle}"
        state = {
            "config": config,
            "events": [],
            "session_id": config.resume_session_id,
            "resume_session_id": None,
            "process": None,
            "reader": None,
            "cancelled": False,
            "denied": False,
        }
        self._runs[handle] = state
        self._launch(state)
        return {"handle": handle, "mode": ATTACH_MODE_NATIVE_RESUME}

    def attach(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        mode = str(request.get("mode") or ATTACH_MODE_CONTINUATION)
        if mode == ATTACH_MODE_NATIVE_RESUME:
            # native transcript resume is only honest for the same harness
            # with a recorded session in the same config directory
            origin = request.get("origin_harness")
            if origin not in (None, self._name):
                raise HarnessContractError(
                    "cross-harness attach cannot claim native transcript "
                    "resume"
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

    def session_id(self, handle: str) -> Optional[str]:
        state = self._require_open(handle, "session")
        return state.get("session_id")

    def proposals(self, handle: str) -> list[dict[str, Any]]:
        state = self._require_open(handle, "proposals")
        return map_candidate_changes(list(state["events"]))

    def usage(self, handle: str) -> list[dict[str, Any]]:
        state = self._require_open(handle, "usage")
        reports = []
        for event in state["events"]:
            payload = event.get("payload") or {}
            usage = payload.get("usage")
            if usage:
                reports.append(map_usage(usage))
        return reports

    def attempt_outcome(self, handle: str) -> str:
        """The run's outcome in the kernel's vocabulary.

        Permission denials and error results are failures — a denied tool
        never becomes success and never hangs an unattended run.
        """
        state = self._require_open(handle, "outcome")
        for event in state["events"]:
            payload = event.get("payload") or {}
            if event.get("type") == "result":
                if payload.get("permission_denials") or payload.get("is_error"):
                    return "failed"
                return "completed"
            if event.get("unknown") and event.get("type") not in (
                "system",
                "user",
                "assistant",
                "result",
            ):
                return "failed"
        return "completed"

    # -- the supervised claude run ------------------------------------
    def _launch(self, state: dict[str, Any]) -> None:
        config: ClaudeRunConfig = state["config"]
        os.makedirs(config.workspace, exist_ok=True)
        os.makedirs(config.config_dir, exist_ok=True)
        # host isolation: the harness's own credential and a per-run config
        # directory — never the platform's operator credentials
        env = {
            key: value
            for key, value in os.environ.items()
            if key in ("PATH", "HOME", "LANG", "LC_ALL")
        }
        env["CLAUDE_CONFIG_DIR"] = config.config_dir
        env.update({k: str(v) for k, v in config.auth_env.items()})
        command = list(config.executable) + [
            "--verbose",
            "--allowedTools",
            config.allowed_tools,
            "--permission-mode",
            config.permission_mode,
            "--max-turns",
            "1",
        ]
        if config.resume_session_id:
            command += ["--resume", config.resume_session_id]
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
        config: ClaudeRunConfig = state["config"]
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
        self, line: bytes, state: dict[str, Any], config: ClaudeRunConfig
    ) -> None:
        if len(line) > config.max_event_bytes:
            return
        try:
            raw = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(raw, dict):
            return
        normalized = normalize_claude_event(raw)
        if normalized["type"] == "system":
            state["session_id"] = normalized["payload"].get("session_id")
        state["events"].append(normalized)

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