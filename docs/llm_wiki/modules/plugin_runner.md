# plugin_runner Module

**Path:** `src/core/plugin_runner.py`

## Description

Governed subprocess runner for skill-supplied plugins (ARC-011 X-004 / P5-005).

This module implements the **plugin execution contract** recorded in the X-004
security spike (§6; design recorded in this module's docstring). Every skill-supplied
Python file — ``bootstrap.py``, ``parser.py``, ``preflight.py``,
``resolve_identity.py`` — runs in its own confined subprocess via this runner,
never ``import``-ed into the server process (X-004 D2).

Design contract (X-004 §6, verbatim where load-bearing):

* **Invocation:** ``PluginRunner.run(skill_dir, plugin, kind, input_json, *,
  caps, timeout_s) -> PluginResult``.
* **Subprocess:** ``sys.executable <plugin>``, no shell, ``start_new_session=True``
  (process-group for tree-kill). Mirrors ``GovernedCommandRunner``'s spawn shape.
* **ABI:** JSON on stdin, JSON on stdout, exit 0/non-zero. The plugin module
  exposes a pure function; the runner does the marshalling.
* **Capability block (default-deny):** ``caps.fs_write`` / ``network_egress`` /
  ``env`` / ``timeout_s`` / ``max_rss_mb`` / ``max_cpu_s``. Default per-kind
  caps come from ``skill_loader._DEFAULT_CAPS_BY_KIND`` (X-004 §6).
* **Env (X-004 §4.2 — strict):** ``PATH`` / ``LANG`` / ``HOME`` /
  ``PYTHONUNBUFFERED`` / venv ``PYTHONPATH`` + only manifest-declared ``env``
  keys. **No secrets, no ``AWS_*``, no service tokens.** This is strictly
  narrower than ``command_runner._CHILD_ENV_ALLOWLIST`` (the agent path), by
  design — plugins have no legitimate need for any of those.
* **Failure semantics (fail-closed):** crash / timeout / invalid-JSON /
  non-zero-exit ⇒ ``PluginResult(ok=False)`` + audit; **the exception never
  propagates to the server process** (the single-instance W14 guarantee).
* **Path confinement (D4):** the plugin's CWD is the session workspace;
  ``skills/`` is reachable read-only; writes are confined to the workspace when
  ``caps.fs_write == "workspace"``. Path confinement uses ``relative_to``
  checks against the declared roots.

The ``BootstrapRunner`` (P5-005, ``bootstrap_runner.py``) is the first
consumer; ``parser`` / ``preflight`` / ``resolve_identity`` plugins follow the
same contract.

Design decisions (P1-007 house style):

* **Sync subprocess + thread offload.** Like ``GovernedCommandRunner.run``,
  the blocking drain lives on a worker thread; the public ``run()`` is
  ``async`` and wraps the body in ``asyncio.to_thread`` so stop/cancel can
  reap the tree through the process registry and the bounded cleanup path.
* **No env inheritance.** The plugin child env is built fresh from the X-004
  §4.2 strict allow-list — it does NOT call ``command_runner._build_child_env``
  (that one is the agent path and carries experiment-legitimate creds plugins
  must never see).
* **Resource bounds.** ``src.core.process_limits`` enforces cumulative CPU,
  process-tree RSS, wall time, process count, and the configured output and
  filesystem quotas over the whole tree; breaches terminate immediately and
  the result is an attributed fail-closed record with explicit cleanup status.
* **Auditing is the caller's job.** ``PluginRunner`` returns a ``PluginResult``
  with ``error``/``returncode``/``timed_out``; the caller (``BootstrapRunner``
  / orchestrator) writes the ``audit_events`` row. Keeps the runner free of the
  DB handle (X-004 D3 — plugins' execution context gets no server internals).

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `asyncio` | `asyncio` |
| `dataclasses` | `dataclass`, `field`, `replace` |
| `json` | `json` |
| `logging` | `logging` |
| `os` | `os` |
| `pathlib` | `Path` |
| `src.core.isolation` | `SANDBOXED_PREFIX`, `TRUSTED_LOCAL_CODE`, `IsolationPolicy`, `IsolationUnavailableError`, `UnsupportedCapabilityError`, `wrap_command` |
| `src.core.process_limits` | `ProcessResourceCaps`, `TreeResourceGuard`, `UnenforceableResourceCapabilityError`, `bounded_drain`, `rlimit_prefix`, `signal_violation` |
| `src.core.skill_manifest` | `PluginCaps`, `PluginKind` |
| `subprocess` | `subprocess` |
| `sys` | `sys` |
| `threading` | `threading` |
| `time` | `time` |
| `types` | `MappingProxyType` |
| `typing` | `Any`, `Literal`, `Mapping`, `Optional` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/cli.py"]
    n1["src/core/bootstrap_runner.py"]
    n2["src/core/isolation.py"]
    n3["src/core/plugin_runner.py"]
    n4["src/core/process_limits.py"]
    n5["src/core/skill_manifest.py"]
    n6["tests/test_execution_isolation.py"]
    n7["tests/test_plugin_runner.py"]
    n8["tests/test_process_limits.py"]
    n9["tests/test_prompt_evaluator.py"]
    n10["tests/test_skill_prompt_engineering_e2e.py"]
    n0 --> n3
    n0 --> n5
    n1 --> n3
    n1 --> n5
    n3 --> n2
    n3 --> n4
    n3 --> n5
    n6 --> n2
    n6 --> n3
    n7 --> n3
    n7 --> n5
    n8 --> n3
    n8 --> n4
    n9 --> n1
    n9 --> n3
    n10 --> n3
    click n0 "../modules/cli.md"
    click n1 "../modules/bootstrap_runner.md"
    click n2 "../modules/isolation.md"
    click n3 "../modules/plugin_runner.md"
    click n4 "../modules/process_limits.md"
    click n5 "../modules/skill_manifest.md"
    click n6 "../modules/test_execution_isolation.md"
    click n7 "../modules/test_plugin_runner.md"
    click n8 "../modules/test_process_limits.md"
    click n9 "../modules/test_prompt_evaluator.md"
    click n10 "../modules/test_skill_prompt_engineering_e2e.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [cli](../modules/cli.md) |
| Inbound | [bootstrap_runner](../modules/bootstrap_runner.md) |
| Inbound | [test_execution_isolation](../modules/test_execution_isolation.md) |
| Inbound | [test_plugin_runner](../modules/test_plugin_runner.md) |
| Inbound | [test_process_limits](../modules/test_process_limits.md) |
| Inbound | [test_prompt_evaluator](../modules/test_prompt_evaluator.md) |
| Inbound | [test_skill_prompt_engineering_e2e](../modules/test_skill_prompt_engineering_e2e.md) |
| Outbound | [isolation](../modules/isolation.md) |
| Outbound | [process_limits](../modules/process_limits.md) |
| Outbound | [skill_manifest](../modules/skill_manifest.md) |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [PluginResult](../entities/PluginResult.md) | 197 | — | Outcome of one plugin invocation (X-004 §6 failure semantics). |
| [PluginRunner](../entities/PluginRunner.md) | 242 | — | Execute one skill plugin in a confined governed subprocess (X-004 §6). |
| [_PluginRunBody](../entities/PluginRunBody.md) | 512 | — | Inputs bundled for the worker-thread sync body. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_build_plugin_env` | `(*, declared_env_keys: Mapping[str, str] \| None = None, source_env: Mapping[str, str] \| None = None) -> dict[str, str]` | — | Build the env dict for a plugin subprocess (X-004 §4.2, strict). |
| `_declared_input_paths` | `(input_json: Mapping[str, Any]) -> tuple[str, ...]` | — | Absolute path values in the input JSON that name existing host files. |
| `_tail` | `(text: str, *, max_chars: int = 2000) -> str` | — | Return the trailing slice of ``text`` for error context. |
| `_violation_result` | `(body: '_PluginRunBody', *, proc: Any, started: float, violation: str, timed_out: bool, cleanup_incomplete: bool, raw: str) -> PluginResult` | — | Build the attributed failed result for one resource-cap breach. |
