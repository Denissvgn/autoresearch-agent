# bootstrap Module

**Path:** `skills/prompt-engineering/bootstrap.py`

## Description

P4-015 — Minimal bootstrap.py for the prompt-engineering skill (ARC-011).

Renders the session workspace: writes the candidate ``prompt.yaml``, the
``eval_set.jsonl`` the deterministic scorer runs against, and the
``best_prompt.yaml`` placeholder the agent writes the winner into.

ABI (P5-005 / X-004 §6 — fixed by review C4, 2026-08-15): JSON on stdin,
JSON object on stdout, exit 0/non-zero. The earlier argparse-CLI shape was
incompatible with the governed ``PluginRunner`` (which fails closed on
non-JSON stdout) and was invoked by nothing::

    {"workspace": "<abs path>", "mode": "live" | "dry", "skill_params": {}}

The emitted JSON echoes the rendered file list (the ``BootstrapRunner``
hashes + indexes them into the ``session_bootstrap.v1`` artifact, P5-006).
The eval script itself is NOT copied into the workspace: it executes from
the read-only packaged skill dir via the command policy's ``script_paths``
resolution (review C4) — the agent-writable session workspace must never
supply executable code to a governed command.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `eval.dataset` | `load_examples` |
| `json` | `json` |
| `pathlib` | `Path` |
| `sys` | `sys` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `main` | `() -> int` | — | — |
