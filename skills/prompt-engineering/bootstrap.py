"""P4-015 — Minimal bootstrap.py for the prompt-engineering skill (ARC-011).

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
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


_DEFAULT_PROMPT = """# Candidate prompt — iterate on this template.
You are a helpful assistant. Answer the user's question accurately.
"""

_DEFAULT_EVAL_SET = [
    {"input": "What is 2+2?", "expected": "4"},
    {"input": "Capital of France?", "expected": "Paris"},
]

_RENDERED = ["prompt.yaml", "eval_set.jsonl", "best_prompt.yaml"]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump({"error": f"invalid stdin JSON: {exc}"}, sys.stdout)
        return 2

    workspace = Path(payload.get("workspace") or "")
    mode = payload.get("mode", "live")
    if not str(workspace):
        json.dump({"error": "workspace is required"}, sys.stdout)
        return 2

    if mode == "dry":
        json.dump({"rendered": _RENDERED, "mode": "dry",
                   "note": "no files written in dry mode"}, sys.stdout)
        return 0

    workspace.mkdir(parents=True, exist_ok=True)

    # Write the initial prompt template.
    (workspace / "prompt.yaml").write_text(_DEFAULT_PROMPT, encoding="utf-8")

    # Write a minimal eval set (JSONL — one JSON object per line).
    with open(workspace / "eval_set.jsonl", "w", encoding="utf-8") as f:
        for example in _DEFAULT_EVAL_SET:
            f.write(json.dumps(example) + "\n")

    # Write a best_prompt.yaml placeholder (the agent writes the winner here).
    (workspace / "best_prompt.yaml").write_text(_DEFAULT_PROMPT, encoding="utf-8")

    json.dump({"rendered": _RENDERED, "mode": "live",
               "workspace": str(workspace)}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
